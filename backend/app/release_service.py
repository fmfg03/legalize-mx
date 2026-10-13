from __future__ import annotations

import hashlib
import json
import uuid
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.audit import record_audit_log
from backend.app.config import REPO_ROOT, settings
from backend.app.models import AppUser, DocumentVersion, ExpedienteDocument, GateExecution, ReleaseOutbox, ReleaseReceipt
from backend.app.models.enums import ReleaseVerdict, UserRole
from backend.app.storage import resolve_storage_path
from backend.app.document_text import ExtractedDocument, extract_document
from scripts.legal_release_gates import evaluate_release_gates

POLICY_NAMES = ("legal_response_release_policy", "legal_authority_resolution_policy", "jurisprudence_grounding_policy")


@dataclass(frozen=True)
class ReleaseAuditContext:
    channel: str = "internal"
    route: str | None = None
    method: str | None = None
    tool: str | None = None


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def reject(message: str, code: int = 409):
    raise HTTPException(status_code=code, detail=message)


def check_reviewer(db: Session, actor_id: uuid.UUID):
    actor = db.get(AppUser, actor_id)
    if actor is None or not actor.is_active or actor.role not in {UserRole.REVIEWER, UserRole.ADMIN}:
        reject("Active reviewer required", 403)


def version_snapshot(db: Session, expediente_id: uuid.UUID, version_id: uuid.UUID) -> ExtractedDocument:
    version = db.scalar(select(DocumentVersion).join(
        ExpedienteDocument, DocumentVersion.document_id == ExpedienteDocument.id,
    ).where(DocumentVersion.id == version_id, ExpedienteDocument.expediente_id == expediente_id))
    if version is None or version.storage_key is None or version.sha256 is None:
        reject("Stored document version required in this expediente", 422)
    try:
        return extract_document(resolve_storage_path(version.storage_key), version.file_name, version.sha256)
    except (OSError, UnicodeError, ValueError, subprocess.TimeoutExpired):
        reject("Stored document extraction or integrity check failed", 422)


def policy_snapshot(root: Path):
    names = POLICY_NAMES
    policies = [json.loads((root / "config" / f"{name}.json").read_text(encoding="utf-8")) for name in names]
    release, authority, grounding = policies
    required = [authority["policy_id"], grounding["policy_id"]]
    if set(release["required_gates"]) != set(required) or len(release["required_gates"]) != 2:
        reject("Unsupported required gates in server policy", 503)
    hashes = {name: digest(policy) for name, policy in zip(names, policies)}
    for name in ("legislation_chunks", "jurisprudence_chunks"):
        hashes[name] = hashlib.sha256((root / "indexes" / f"{name}.jsonl").read_bytes()).hexdigest()
    return policies, hashes


def evaluate_release(
    *, db: Session, actor_id: uuid.UUID, expediente_id: uuid.UUID,
    document_version_id: uuid.UUID, bundle: dict[str, Any], root: Path = REPO_ROOT,
    audit_context: ReleaseAuditContext = ReleaseAuditContext(),
) -> GateExecution:
    check_reviewer(db, actor_id)
    # Take a JSON snapshot so later caller mutations cannot change evaluated data.
    try:
        bundle = json.loads(canonical_json(bundle))
    except (TypeError, ValueError):
        reject("Bundle must contain finite JSON values", 422)
    extracted = version_snapshot(db, expediente_id, document_version_id)
    text = extracted.text
    if bundle.get("response_text") != text:
        reject("Bundle response_text must match the stored version", 422)
    policies, hashes = policy_snapshot(root)
    release_policy, authority_policy, grounding_policy = policies
    if bundle.get("response_type") not in release_policy["protected_response_types"]:
        reject("A protected response_type is required for document release", 422)
    gates = []
    try:
        # Prevent existing URL substring matching from making client-selected network requests.
        for citation in bundle.get("citations", []):
            if not isinstance(citation, dict):
                raise ValueError("Invalid citation")
            source = urlsplit(citation.get("source_url", ""))
            if source.scheme != "https" or source.hostname not in {"www.diputados.gob.mx", "www.dof.gob.mx", "dof.gob.mx", "sjf2.scjn.gob.mx", "www.scjn.gob.mx", "bicentenario.scjn.gob.mx"} or source.username or source.password or source.port not in {None, 443}:
                raise ValueError("Citation source is not an enabled official source")
            if citation.get("provider_id"):
                raise ValueError("Licensed connectors are not enabled for backend release")
        authority_result, grounding_result = evaluate_release_gates(
            bundle=bundle, root=root, authority_policy=authority_policy,
            grounding_policy=grounding_policy, provider_registry={},
        )
        for policy, result in ((authority_policy, authority_result), (grounding_policy, grounding_result)):
            verdict, summary, failures = result[:3]
            gates.append(dict(gate_id=policy["policy_id"], verdict=verdict, summary=summary,
                              failures=[dict(code=f.code, message=f.message, details=f.details) for f in failures]))
    except Exception:
        # No exception, unavailable resolver or malformed input may become APPROVED.
        gates = [dict(gate_id=p["policy_id"], verdict="ERROR", summary={}, failures=[{"code": "gate.execution_error"}]) for p in (authority_policy, grounding_policy)]
    # A concurrent policy/index update invalidates this execution rather than binding different inputs.
    if policy_snapshot(root)[1] != hashes:
        reject("Server gate inputs changed during evaluation")
    verdict = "approved" if all(g["verdict"] == "PASS" and not g["failures"] for g in gates) else "blocked"
    execution_id = uuid.uuid4()
    bundle_hash = digest(bundle)
    document_hash = extracted.document_sha256
    evidence = dict(
        execution_id=str(execution_id), actor_user_id=str(actor_id), expediente_id=str(expediente_id),
        document_version_id=str(document_version_id), bundle_sha256=bundle_hash,
        document_sha256=document_hash, extraction=extracted.evidence,
        policy_hashes=hashes, policy_snapshot=dict(zip(POLICY_NAMES, policies)), verdict=verdict, gates=gates,
    )
    execution = GateExecution(
        id=execution_id, actor_user_id=actor_id, expediente_id=expediente_id,
        document_version_id=document_version_id, bundle=bundle, bundle_sha256=bundle_hash,
        document_sha256=document_hash, policy_hashes=hashes, verdict=verdict,
        evidence=evidence, evidence_sha256=digest(evidence),
    )
    db.add(execution)
    record_audit_log(db=db, actor_user_id=actor_id, action="evaluate_release", entity_type="gate_execution", entity_id=execution_id, expediente_id=expediente_id,
                     route=audit_context.route, method=audit_context.method,
                     extra={"verdict": verdict, "bundle_sha256": bundle_hash, "channel": audit_context.channel, "tool": audit_context.tool})
    db.commit()
    db.refresh(execution)
    return execution


def execution_gate_ids(execution: GateExecution) -> set[str]:
    # Existing v1 evidence remains immutable. An invalid present snapshot cannot
    # fall back to legacy validation or select current mutable policy inputs.
    if "policy_snapshot" not in execution.evidence:
        return {"legalize-mx-legal-authority-verification-v1", "legalize-mx-jurisprudence-grounding-v1"}
    snapshot = execution.evidence["policy_snapshot"]
    if not isinstance(snapshot, dict) or any(not isinstance(snapshot.get(name), dict) for name in POLICY_NAMES):
        reject("Stored server policy snapshot invalid")
    if any(digest(snapshot[name]) != execution.policy_hashes.get(name) for name in POLICY_NAMES):
        reject("Stored server policy snapshot hash mismatch")
    ids = [snapshot[name].get("policy_id") for name in POLICY_NAMES]
    if not all(isinstance(value, str) and value.strip() for value in ids):
        reject("Stored server policy IDs invalid")
    required = snapshot[POLICY_NAMES[0]].get("required_gates")
    if not isinstance(required, list) or len(required) != 2 or not all(isinstance(value, str) and value.strip() for value in required) or len(set(required)) != 2:
        reject("Stored required gates invalid")
    if set(required) != set(ids[1:]):
        reject("Stored required gates do not match policy IDs")
    return set(required)


def validate_execution_record(execution: GateExecution) -> None:
    evidence = execution.evidence
    expected = dict(
        execution_id=str(execution.id), actor_user_id=str(execution.actor_user_id),
        expediente_id=str(execution.expediente_id), document_version_id=str(execution.document_version_id),
        bundle_sha256=execution.bundle_sha256, document_sha256=execution.document_sha256,
        policy_hashes=execution.policy_hashes, verdict=execution.verdict,
    )
    if digest(execution.bundle) != execution.bundle_sha256 or not evidence or digest(evidence) != execution.evidence_sha256 or any(evidence.get(k) != v for k, v in expected.items()):
        reject("Gate execution record integrity check failed")
    gates = evidence.get("gates")
    if not isinstance(gates, list) or len(gates) != 2 or not all(isinstance(g, dict) for g in gates):
        reject("Required gate evidence missing")
    gate_ids = {g.get("gate_id") for g in gates}
    if gate_ids != execution_gate_ids(execution):
        reject("Required gate evidence missing")
    verdict = "approved" if all(g.get("verdict") == "PASS" and g.get("failures") == [] for g in gates) else "blocked"
    if execution.verdict != verdict:
        reject("Gate verdict does not match evidence")


def validate_receipt_record(receipt: ReleaseReceipt, execution: GateExecution) -> None:
    validate_execution_record(execution)
    if (
        receipt.execution_id != execution.id
        or receipt.created_by_user_id != execution.actor_user_id
        or receipt.expediente_id != execution.expediente_id
        or receipt.document_version_id != execution.document_version_id
        or receipt.bundle_sha256 != execution.bundle_sha256
        or receipt.verdict.value != execution.verdict
        or receipt.response_type != execution.bundle.get("response_type")
        or receipt.gate_summary != execution.evidence
        or ("policy_snapshot" in execution.evidence and receipt.policy_id != execution.evidence["policy_snapshot"][POLICY_NAMES[0]].get("policy_id"))
    ):
        reject("Existing receipt does not match gate execution")


def release_from_execution(
    *, db: Session, actor_id: uuid.UUID, expediente_id: uuid.UUID,
    execution_id: uuid.UUID, bundle: dict[str, Any], root: Path = REPO_ROOT,
    audit_context: ReleaseAuditContext = ReleaseAuditContext(),
) -> ReleaseReceipt:
    check_reviewer(db, actor_id)
    execution = db.scalar(select(GateExecution).where(GateExecution.id == execution_id).with_for_update())
    if execution is None:
        reject("Server gate execution evidence required", 422)
    if execution.actor_user_id != actor_id or execution.expediente_id != expediente_id:
        reject("Gate execution belongs to a different actor or expediente", 403)
    validate_execution_record(execution)
    try:
        bundle_hash = digest(bundle)
    except (TypeError, ValueError):
        reject("Invalid bundle", 422)
    if digest(execution.bundle) != execution.bundle_sha256 or bundle_hash != execution.bundle_sha256:
        reject("Bundle does not match evaluated evidence")
    receipt = db.scalar(select(ReleaseReceipt).where(ReleaseReceipt.execution_id == execution.id))
    if receipt is not None:
        validate_receipt_record(receipt, execution)
        return receipt
    extracted = version_snapshot(db, expediente_id, execution.document_version_id)
    if extracted.document_sha256 != execution.document_sha256 or extracted.text != bundle.get("response_text") or extracted.evidence != execution.evidence.get("extraction"):
        reject("Document does not match evaluated evidence")
    policies, hashes = policy_snapshot(root)
    if hashes != execution.policy_hashes:
        reject("Server gate inputs changed; evaluate again")
    evidence = execution.evidence
    expected = dict(
        execution_id=str(execution.id), actor_user_id=str(actor_id), expediente_id=str(expediente_id),
        document_version_id=str(execution.document_version_id), bundle_sha256=bundle_hash,
        document_sha256=execution.document_sha256, policy_hashes=hashes, verdict=execution.verdict,
    )
    if not evidence or digest(evidence) != execution.evidence_sha256 or any(evidence.get(k) != v for k, v in expected.items()):
        reject("Gate evidence integrity check failed")
    gates = evidence.get("gates")
    if not isinstance(gates, list) or len(gates) != 2 or {g.get("gate_id") for g in gates if isinstance(g, dict)} != set(policies[0]["required_gates"]):
        reject("Required gate evidence missing")
    computed_verdict = "approved" if all(g.get("verdict") == "PASS" and g.get("failures") == [] for g in gates) else "blocked"
    if execution.verdict != computed_verdict:
        reject("Gate verdict does not match evidence")
    created = execution.created_at.replace(tzinfo=timezone.utc) if execution.created_at.tzinfo is None else execution.created_at
    if (datetime.now(timezone.utc) - created).total_seconds() > settings.release_evidence_max_age_seconds:
        reject("Gate evidence expired; evaluate again")
    receipt = ReleaseReceipt(
        id=uuid.uuid4(), execution_id=execution.id, expediente_id=expediente_id,
        document_version_id=execution.document_version_id, created_by_user_id=actor_id,
        verdict=ReleaseVerdict(computed_verdict), response_type=bundle["response_type"],
        policy_id=policies[0]["policy_id"], bundle_sha256=bundle_hash, gate_summary=evidence,
    )
    try:
        db.add(receipt)
        db.flush()
        payload = dict(receipt_id=str(receipt.id), bundle=execution.bundle, **evidence)
        db.add(ReleaseOutbox(receipt_id=receipt.id, payload=payload, payload_sha256=digest(payload)))
        record_audit_log(db=db, actor_user_id=actor_id, action="create_release_receipt", entity_type="release_receipt", entity_id=receipt.id, expediente_id=expediente_id,
                         route=audit_context.route, method=audit_context.method,
                         extra={"execution_id": str(execution.id), "bundle_sha256": bundle_hash, "verdict": computed_verdict, "channel": audit_context.channel, "tool": audit_context.tool})
        db.commit()
    except IntegrityError:
        db.rollback()
        # The unique execution_id arbitrates equivalent concurrent retries (including SQLite).
        if db.scalar(select(ReleaseReceipt.id).where(ReleaseReceipt.execution_id == execution_id)) is None:
            raise
        return release_from_execution(db=db, actor_id=actor_id, expediente_id=expediente_id, execution_id=execution_id, bundle=bundle, root=root, audit_context=audit_context)
    except Exception:
        db.rollback()
        raise
    db.refresh(receipt)
    return receipt
