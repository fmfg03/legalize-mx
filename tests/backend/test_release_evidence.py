from __future__ import annotations

import base64
import copy
import importlib
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select


@pytest.fixture
def release_case(app_bundle, make_user):
    actor = make_user(email="release@example.com", display_name="Reviewer", role=app_bundle["enums"].UserRole.REVIEWER)
    other = make_user(email="other@example.com", display_name="Other", role=app_bundle["enums"].UserRole.REVIEWER)
    service = importlib.import_module("backend.app.release_service")
    schemas = importlib.import_module("backend.app.schemas.expedientes")
    storage = importlib.import_module("backend.app.storage")
    factory = app_bundle["db"].SessionLocal
    routes = app_bundle["expediente_routes"]
    request = SimpleNamespace(url=SimpleNamespace(path="/test"), method="POST")
    with factory() as db:
        expediente = routes.create_expediente(payload=schemas.ExpedienteCreate(title="Evidence test", matter_type="amparo"), request=request, current_user=actor["user"], db=db)
    bundle = {"response_type": "recommendation", "response_text": "Documento de prueba sin afirmaciones jurídicas.", "citations": [], "claims": []}

    def version_for(text):
        with factory() as db:
            detail = routes.create_document(
                expediente_id=str(expediente.id), request=request, current_user=actor["user"], db=db,
                payload=schemas.DocumentWithVersionCreate(
                    document={"document_type": "escrito", "title": "Texto"},
                    version={"source_kind": "generated", "file_name": "response.txt", "mime_type": "text/plain", "content_base64": base64.b64encode(text.encode()).decode()},
                ),
            )
        return detail.documents[-1].versions[0]

    version = version_for(bundle["response_text"])
    def evaluate(bundle_override=None, version_override=None):
        with factory() as db:
            return service.evaluate_release(db=db, actor_id=actor["user"].id, expediente_id=expediente.id, document_version_id=(version_override or version).id, bundle=bundle_override or bundle)

    def release(execution, *, actor_override=None, bundle_override=None, db=None):
        args = dict(actor_id=(actor_override or actor)["user"].id, expediente_id=expediente.id, execution_id=execution.id, bundle=bundle_override or bundle)
        if db is not None:
            return service.release_from_execution(db=db, **args)
        with factory() as db:
            return service.release_from_execution(db=db, **args)

    return dict(actor=actor, other=other, service=service, factory=factory, version=version, expediente=expediente, bundle=bundle, schemas=schemas, storage=storage, evaluate=evaluate, release=release, version_for=version_for, models=app_bundle["models"])


def test_real_gates_receipt_outbox_and_equivalent_retries(release_case):
    case = release_case
    execution = case["evaluate"]()
    assert execution.verdict == "approved"
    assert len(execution.evidence["gates"]) == 2
    assert all(g["verdict"] == "PASS" for g in execution.evidence["gates"])
    receipt = case["release"](execution)
    retry = case["release"](execution)
    assert receipt.id == retry.id
    assert receipt.execution_id == execution.id
    assert receipt.bundle_sha256 == execution.bundle_sha256
    with case["factory"]() as db:
        assert db.scalar(select(func.count()).select_from(case["models"].ReleaseReceipt)) == 1
        assert db.scalar(select(func.count()).select_from(case["models"].ReleaseOutbox)) == 1
        audit = db.scalar(select(case["models"].AuditLog).where(case["models"].AuditLog.action == "create_release_receipt"))
        assert audit.actor_user_id == case["actor"]["user"].id


def test_old_direct_approved_payload_and_forged_fields_rejected(app_bundle, release_case):
    case = release_case
    with TestClient(app_bundle["app"]) as client:
        url = f"/api/v1/expedientes/{case['expediente'].id}/release-receipts"
        headers = {"X-API-Key": case["actor"]["plaintext_api_key"]}
        assert client.post(url, headers=headers, json={"verdict": "approved", "gate_summary": {"passed": True}, "document_version_id": str(case["version"].id)}).status_code == 422
        assert client.post(url, headers=headers, json={"execution_id": str(uuid.uuid4()), "bundle": case["bundle"]}).status_code == 422
        evaluation_url = url.replace("release-receipts", "release-evaluations")
        assert client.post(evaluation_url, headers=headers, json={"document_version_id": str(case["version"].id), "bundle": case["bundle"], "actor_user_id": str(case["other"]["user"].id)}).status_code == 422
        response = client.post(evaluation_url, headers=headers, json={"document_version_id": str(case["version"].id), "bundle": case["bundle"]})
        assert response.status_code == 201, response.text
        released = client.post(url, headers=headers, json={"execution_id": response.json()["id"], "bundle": case["bundle"]})
        assert released.status_code == 201, released.text
        assert released.json()["execution_id"] == response.json()["id"]
    with case["factory"]() as db:
        audits = db.scalars(select(case["models"].AuditLog).where(case["models"].AuditLog.action.in_(["evaluate_release", "create_release_receipt"]))).all()
        assert len(audits) == 2
        assert all(log.method == "POST" and log.extra_json["channel"] == "rest_api_key" for log in audits)
        assert {log.route for log in audits} == {url, evaluation_url}
    with pytest.raises(ValidationError):
        case["schemas"].ReleaseReceiptCreate(execution_id=uuid.uuid4(), bundle=case["bundle"], verdict="approved")


@pytest.mark.parametrize("kind", ["bundle", "evidence", "actor", "execution", "verdict", "missing_gate", "document", "expiry", "version_column", "hash_column", "execution_binding"])
def test_missing_or_altered_evidence_fails_closed(release_case, kind):
    case = release_case
    execution = case["evaluate"]()
    args = {}
    if kind == "actor":
        args["actor_override"] = case["other"]
    elif kind == "execution":
        execution = SimpleNamespace(id=uuid.uuid4())
    elif kind == "bundle":
        altered = copy.deepcopy(case["bundle"])
        altered["request_id"] = "different"
        args["bundle_override"] = altered
    elif kind == "document":
        case["storage"].resolve_storage_path(case["version"].storage_key).write_text("Changed text")
    else:
        alternate_version = case["version_for"]("Otra versión") if kind == "version_column" else None
        with case["factory"]() as db:
            stored = db.get(case["models"].GateExecution, execution.id)
            if kind == "evidence":
                stored.evidence = {**stored.evidence, "actor_user_id": str(case["other"]["user"].id)}
            elif kind == "verdict":
                stored.verdict = "blocked"
            elif kind == "missing_gate":
                stored.evidence = {**stored.evidence, "gates": []}
                stored.evidence_sha256 = case["service"].digest(stored.evidence)
            elif kind == "expiry":
                stored.created_at = datetime.now(timezone.utc) - timedelta(days=1)
            elif kind == "version_column":
                stored.document_version_id = alternate_version.id
            elif kind == "hash_column":
                stored.bundle_sha256 = "0" * 64
            elif kind == "execution_binding":
                stored.evidence = {**stored.evidence, "execution_id": str(uuid.uuid4())}
                stored.evidence_sha256 = case["service"].digest(stored.evidence)
            db.commit()
    with pytest.raises(HTTPException):
        case["release"](execution, **args)
    with case["factory"]() as db:
        assert db.scalar(select(func.count()).select_from(case["models"].ReleaseReceipt)) == 0
        assert db.scalar(select(func.count()).select_from(case["models"].ReleaseOutbox)) == 0


def test_bundle_must_match_persisted_version_and_scope(release_case):
    case = release_case
    with pytest.raises(HTTPException):
        case["evaluate"]({**case["bundle"], "response_text": "Different text"})
    with pytest.raises(HTTPException):
        case["evaluate"]({**case["bundle"], "response_type": "bypass"})


def test_real_grounding_blocks_invented_jurisprudence(release_case, monkeypatch):
    case = release_case
    bundle = json.loads((Path(__file__).parents[2] / "fixtures/assistant_response_fail_fake_jurisprudence.json").read_text())
    bundle["citations"][0]["source_url"] = "https://sjf2.scjn.gob.mx/detalle/tesis/9999999"
    authority = importlib.import_module("scripts.validate_legal_authority")
    monkeypatch.setattr(authority, "verify_scjn_live", lambda *args, **kwargs: {"verified": False, "reason": "not_found", "adapter": "scjn_sjf_api"})
    version = case["version_for"](bundle["response_text"])
    execution = case["evaluate"](bundle, version)
    assert execution.verdict == "blocked"
    receipt = case["release"](execution, bundle_override=bundle)
    assert receipt.verdict.value == "blocked"
    assert any(g["failures"] for g in execution.evidence["gates"])
    assert execution.evidence["gates"][1]["verdict"] == "FAIL"
    assert any(f["code"] == "claim.jurisprudence.unsupported" for f in execution.evidence["gates"][1]["failures"])


def test_resolver_exception_and_unsupported_network_source_block(release_case, monkeypatch):
    case = release_case
    def unavailable(**kwargs):
        raise OSError("resolver unavailable")
    monkeypatch.setattr(case["service"], "evaluate_release_gates", unavailable)
    execution = case["evaluate"]()
    assert execution.verdict == "blocked"
    assert case["release"](execution).verdict.value == "blocked"
    monkeypatch.undo()
    execution = case["evaluate"]({**case["bundle"], "citations": [{"source_url": "https://evil.example/dof.gob.mx"}]})
    assert execution.verdict == "blocked"


def test_policy_drift_requires_new_evaluation(release_case, monkeypatch):
    case = release_case
    execution = case["evaluate"]()
    snapshot = case["service"].policy_snapshot
    def drift(root):
        policies, hashes = snapshot(root)
        return policies, {**hashes, "legislation_chunks": "changed"}
    monkeypatch.setattr(case["service"], "policy_snapshot", drift)
    with pytest.raises(HTTPException):
        case["release"](execution)


def test_rollback_and_recovery_keep_receipt_and_event_atomic(release_case, monkeypatch):
    case = release_case
    execution = case["evaluate"]()
    with case["factory"]() as db:
        def failure():
            raise OSError("commit failed")
        monkeypatch.setattr(db, "commit", failure)
        with pytest.raises(OSError):
            case["release"](execution, db=db)
    with case["factory"]() as db:
        assert db.scalar(select(func.count()).select_from(case["models"].ReleaseReceipt)) == 0
        assert db.scalar(select(func.count()).select_from(case["models"].ReleaseOutbox)) == 0
        assert db.scalar(select(func.count()).select_from(case["models"].AuditLog).where(case["models"].AuditLog.action == "create_release_receipt")) == 0
    assert case["release"](execution).execution_id == execution.id


def test_concurrent_equivalent_release_requests_are_idempotent(release_case):
    case = release_case
    execution = case["evaluate"]()
    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(lambda _: case["release"](execution), range(2)))
    assert receipts[0].id == receipts[1].id


def test_outbox_retry_and_crash_after_effect_are_idempotent(release_case, tmp_path, monkeypatch):
    case = release_case
    outbox = importlib.import_module("backend.app.outbox")
    case["release"](case["evaluate"]())
    write = outbox.write_event
    def crash(path, payload):
        write(path, payload)
        raise OSError("crashed after filesystem effect")
    monkeypatch.setattr(outbox, "write_event", crash)
    assert outbox.drain_outbox(case["factory"], tmp_path)["failed"] == 1
    assert len(list(tmp_path.glob("*.json"))) == 1
    monkeypatch.setattr(outbox, "write_event", write)
    assert outbox.drain_outbox(case["factory"], tmp_path)["delivered"] == 1
    assert outbox.drain_outbox(case["factory"], tmp_path)["attempted"] == 0
    assert len(list(tmp_path.glob("*.json"))) == 1
    with case["factory"]() as db:
        event = db.scalar(select(case["models"].ReleaseOutbox))
        assert event.attempts == 2
        assert event.delivered_at is not None
        assert event.last_error is None


def test_tampered_outbox_never_delivers(release_case, tmp_path):
    case = release_case
    case["release"](case["evaluate"]())
    with case["factory"]() as db:
        event = db.scalar(select(case["models"].ReleaseOutbox))
        event.payload = {**event.payload, "verdict": "bypass"}
        db.commit()
    outbox = importlib.import_module("backend.app.outbox")
    assert outbox.drain_outbox(case["factory"], tmp_path)["failed"] == 1
    assert not list(tmp_path.glob("*.json"))


@pytest.mark.parametrize("target,field", [
    ("receipt", "document_version_id"), ("receipt", "expediente_id"),
    ("receipt", "created_by_user_id"), ("receipt", "bundle_sha256"),
    ("execution", "verdict"), ("execution", "actor_user_id"),
    ("execution", "bundle_sha256"),
])
def test_outbox_checks_all_committed_bindings(release_case, tmp_path, target, field):
    case = release_case
    execution = case["evaluate"]()
    receipt = case["release"](execution)
    with case["factory"]() as db:
        record = db.get(case["models"].ReleaseReceipt if target == "receipt" else case["models"].GateExecution, receipt.id if target == "receipt" else execution.id)
        value = "blocked" if field == "verdict" else "0" * 64 if field == "bundle_sha256" else case["other"]["user"].id if field in {"actor_user_id", "created_by_user_id"} else None
        if field == "document_version_id":
            value = case["version_for"]("Otra versión").id
        if field == "expediente_id":
            # A null receipt expediente is allowed by the legacy schema; it must not deliver.
            value = None
        setattr(record, field, value)
        db.commit()
    outbox = importlib.import_module("backend.app.outbox")
    assert outbox.drain_outbox(case["factory"], tmp_path)["failed"] == 1
    assert not list(tmp_path.glob("*.json"))


def test_dof_availability_and_client_quote_are_not_evidence(release_case, monkeypatch):
    case = release_case
    authority = importlib.import_module("scripts.validate_legal_authority")
    monkeypatch.setattr(authority, "fetch_text", lambda *_: "DOF disponible, sin artículo citado")
    text = "El artículo inventado permite omitir una audiencia."
    bundle = {"response_type": "legal_opinion", "response_text": text,
        "citations": [{"citation_id": "c1", "doc_type": "legislation", "doc_id": "invented", "title": "Ley inventada", "locator": "articulo 9999", "jurisdiction": "federal", "source_url": "https://www.dof.gob.mx/", "quote": text}],
        "claims": [{"claim_id": "a1", "kind": "legislation", "citation_ids": ["c1"]}]}
    execution = case["evaluate"](bundle, case["version_for"](text))
    assert execution.verdict == "blocked"
    assert case["release"](execution, bundle_override=bundle).verdict.value == "blocked"


def test_contradictory_canonical_jurisprudence_identity_is_blocked(release_case, monkeypatch):
    case = release_case
    authority = importlib.import_module("scripts.validate_legal_authority")
    monkeypatch.setattr(authority, "verify_scjn_live", lambda *_args, **_kwargs: {"verified": False, "reason": "title_mismatch"})
    bundle = json.loads((Path(__file__).parents[2] / "fixtures/assistant_response_pass_with_jurisprudence.json").read_text())
    bundle["citations"] = [dict(bundle["citations"][0], title="Título inventado", registry_id="9999999", source_url="https://sjf2.scjn.gob.mx/detalle/tesis/9999999")]
    bundle["claims"] = [{"claim_id": "cl1", "kind": "jurisprudence", "citation_ids": [bundle["citations"][0]["citation_id"]]}]
    execution = case["evaluate"](bundle, case["version_for"](bundle["response_text"]))
    assert execution.verdict == "blocked"


@pytest.mark.parametrize("source", ["https://www.dof.gob.mx/", "https://bicentenario.scjn.gob.mx/repositorio-scjn/api/v1/tesis/999999999"])
def test_live_jurisprudence_source_is_server_bound(release_case, monkeypatch, source):
    authority = importlib.import_module("scripts.validate_legal_authority")
    fetched = []
    def fetch(url, *_args, **_kwargs):
        fetched.append(url)
        return {"Rubro": "Título canónico", "Texto": "Texto canónico del servidor.", "TipoTesis": "Jurisprudencia", "source_url": "https://www.dof.gob.mx/"}
    monkeypatch.setattr(authority, "fetch_json", fetch)
    text = "Una jurisprudencia respalda esta conclusión."
    bundle = {"response_type": "legal_opinion", "response_text": text,
        "citations": [{"citation_id": "c1", "doc_type": "jurisprudence", "doc_id": "mx-sjf-tesis-999999999", "registry_id": "999999999", "title": "Título canónico", "locator": "Registro 999999999", "jurisdiction": "mx-federal", "source_url": source, "quote": "Texto canónico del servidor."}],
        "claims": [{"claim_id": "a1", "kind": "jurisprudence", "citation_ids": ["c1"]}]}
    execution = release_case["evaluate"](bundle, release_case["version_for"](text))
    assert fetched == ["https://bicentenario.scjn.gob.mx/repositorio-scjn/api/v1/tesis/999999999"]
    assert execution.verdict == ("blocked" if source == "https://www.dof.gob.mx/" else "approved")



def copied_policy_root(tmp_path):
    import shutil
    source = Path(__file__).parents[2]
    root = tmp_path / "policies"
    for folder in ("config", "indexes"):
        shutil.copytree(source / folder, root / folder)
    return root


def test_versioned_server_policy_ids_release_and_deliver_snapshot(release_case, tmp_path):
    case = release_case
    root = copied_policy_root(tmp_path)
    names = case["service"].POLICY_NAMES
    policies = [json.loads((root / "config" / (name + ".json")).read_text()) for name in names]
    for policy in policies:
        policy["policy_id"] = policy["policy_id"].replace("-v1", "-v2")
    policies[0]["required_gates"] = [policy["policy_id"] for policy in policies[1:]]
    for name, policy in zip(names, policies):
        (root / "config" / (name + ".json")).write_text(json.dumps(policy))
    with case["factory"]() as db:
        execution = case["service"].evaluate_release(db=db, actor_id=case["actor"]["user"].id, expediente_id=case["expediente"].id, document_version_id=case["version"].id, bundle=case["bundle"], root=root)
        receipt = case["service"].release_from_execution(db=db, actor_id=case["actor"]["user"].id, expediente_id=case["expediente"].id, execution_id=execution.id, bundle=case["bundle"], root=root)
        assert receipt.verdict.value == "approved"
        assert receipt.policy_id == policies[0]["policy_id"]
        assert {g["gate_id"] for g in execution.evidence["gates"]} == set(policies[0]["required_gates"])
    # Export validates the committed v2 snapshot even though the repository is v1.
    assert importlib.import_module("backend.app.outbox").drain_outbox(case["factory"], tmp_path / "exports")["delivered"] == 1


@pytest.mark.parametrize("change", ["policy", "index", "document", "expiry"])
def test_committed_retry_ignores_mutable_inputs_without_duplicating(release_case, tmp_path, change):
    case = release_case
    root = copied_policy_root(tmp_path)
    actor_id, expediente_id = case["actor"]["user"].id, case["expediente"].id
    with case["factory"]() as db:
        execution = case["service"].evaluate_release(db=db, actor_id=actor_id, expediente_id=expediente_id, document_version_id=case["version"].id, bundle=case["bundle"], root=root)
        execution_id = execution.id
        receipt = case["service"].release_from_execution(db=db, actor_id=actor_id, expediente_id=expediente_id, execution_id=execution_id, bundle=case["bundle"], root=root)
        receipt_id = receipt.id
    if change == "policy":
        path = root / "config/legal_response_release_policy.json"
        policy = json.loads(path.read_text())
        policy["description"] = "Changed after committed release"
        path.write_text(json.dumps(policy))
    elif change == "index":
        with (root / "indexes/legislation_chunks.jsonl").open("a") as stream:
            stream.write('\n{"doc_id":"new-after-commit"}\n')
    elif change == "document":
        case["storage"].resolve_storage_path(case["version"].storage_key).unlink()
    else:
        with case["factory"]() as db:
            db.get(case["models"].GateExecution, execution_id).created_at = datetime.now(timezone.utc) - timedelta(days=1)
            db.commit()
    execution = SimpleNamespace(id=execution_id)
    with case["factory"]() as db:
        retried = case["service"].release_from_execution(db=db, actor_id=actor_id, expediente_id=expediente_id, execution_id=execution_id, bundle=case["bundle"], root=root,
            audit_context=case["service"].ReleaseAuditContext(channel="mcp_oauth", route="/mcp", method="POST", tool="release_document"))
        assert retried.id == receipt_id
    with pytest.raises(HTTPException):
        case["release"](execution, actor_override=case["other"])
    with pytest.raises(HTTPException):
        case["release"](execution, bundle_override={**case["bundle"], "request_id": "different"})
    with case["factory"]() as db:
        assert db.scalar(select(func.count()).select_from(case["models"].ReleaseReceipt)) == 1
        assert db.scalar(select(func.count()).select_from(case["models"].ReleaseOutbox)) == 1
        audits = db.scalars(select(case["models"].AuditLog).where(case["models"].AuditLog.action == "create_release_receipt")).all()
        assert len(audits) == 1 and audits[0].extra_json["channel"] == "internal"


def test_legacy_execution_snapshot_is_not_rewritten(release_case, tmp_path):
    case = release_case
    execution = case["evaluate"]()
    with case["factory"]() as db:
        record = db.get(case["models"].GateExecution, execution.id)
        record.evidence = {k: v for k, v in record.evidence.items() if k != "policy_snapshot"}
        record.evidence_sha256 = case["service"].digest(record.evidence)
        legacy_evidence = copy.deepcopy(record.evidence)
        db.commit()
    receipt = case["release"](execution)
    assert receipt.gate_summary == legacy_evidence
    assert case["release"](execution).id == receipt.id
    assert importlib.import_module("backend.app.outbox").drain_outbox(case["factory"], tmp_path)["delivered"] == 1
    with case["factory"]() as db:
        assert db.get(case["models"].GateExecution, execution.id).evidence == legacy_evidence


@pytest.mark.parametrize("snapshot", [None, {}, {"legal_response_release_policy": {"required_gates": ["unknown"]}}])
def test_invalid_present_policy_snapshot_cannot_use_legacy_fallback(release_case, snapshot):
    case = release_case
    execution = case["evaluate"]()
    with case["factory"]() as db:
        record = db.get(case["models"].GateExecution, execution.id)
        record.evidence = {**record.evidence, "policy_snapshot": snapshot}
        record.evidence_sha256 = case["service"].digest(record.evidence)
        db.commit()
    with pytest.raises(HTTPException):
        case["release"](execution)
