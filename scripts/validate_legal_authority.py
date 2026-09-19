#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import ssl
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import fetch_diputados_metadata as diputados_metadata
import validate_jurisprudence_grounding as grounding


EXIT_OK = 0
EXIT_FAIL = 1
EXIT_ERROR = 2
SCJN_API_BASE = "https://bicentenario.scjn.gob.mx/repositorio-scjn/api/v1"


@dataclass
class GateFailure:
    code: str
    message: str
    details: dict[str, Any]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def append_receipt(path: Path, receipt: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, ensure_ascii=False) + "\n")


def fetch_json(url: str, timeout: int, headers: dict[str, str] | None = None) -> Any:
    request = urllib.request.Request(
        url,
        headers=headers
        or {
            "Accept": "application/json",
            "User-Agent": "legalize-mx/0.1 authority gate",
        },
        method="GET",
    )
    context = ssl.create_default_context()
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_text(url: str, timeout: int, headers: dict[str, str] | None = None) -> str:
    request = urllib.request.Request(
        url,
        headers=headers or {"User-Agent": "legalize-mx/0.1 authority gate"},
        method="GET",
    )
    context = ssl.create_default_context()
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        return response.read().decode("utf-8", errors="replace")


def infer_scjn_kind(citation: dict[str, Any]) -> str:
    doc_id = str(citation.get("doc_id") or "")
    for candidate in ("tesis", "precedente", "voto", "acuerdo"):
        if candidate in doc_id:
            return candidate
    return "tesis"


def infer_source_id(citation: dict[str, Any]) -> str | None:
    source_url = str(citation.get("source_url") or "")
    parsed = urllib.parse.urlparse(source_url)
    if parsed.netloc.endswith("diputados.gob.mx") and parsed.path.endswith(".htm"):
        return Path(parsed.path).stem
    doc_id = str(citation.get("doc_id") or "")
    if doc_id.startswith("mx-federal-"):
        return doc_id.removeprefix("mx-federal-")
    return None


def load_live_fixture(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {"citations": {}}
    return load_json(path)


def load_provider_registry(path: Path) -> dict[str, dict[str, Any]]:
    payload = load_json(path)
    return {item["provider_id"]: item for item in payload.get("providers", [])}


def local_match_for_citation(
    citation: dict[str, Any],
    *,
    legislation_chunks: list[dict[str, Any]],
    jurisprudence_chunks: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if citation.get("doc_type") == "jurisprudence":
        for chunk in jurisprudence_chunks:
            if citation.get("doc_id") and chunk.get("doc_id") == citation.get("doc_id"):
                return {"match_type": "doc_id", "chunk": chunk}
            if citation.get("registry_id") and chunk.get("registry_id") == citation.get("registry_id"):
                return {"match_type": "registry_id", "chunk": chunk}
            if citation.get("source_url") and chunk.get("source_url") == citation.get("source_url"):
                return {"match_type": "source_url", "chunk": chunk}
        return None
    if citation.get("doc_type") == "legislation":
        for chunk in legislation_chunks:
            if chunk.get("doc_id") == citation.get("doc_id") and chunk.get("source_url") == citation.get("source_url"):
                return {"match_type": "doc_id+source_url", "chunk": chunk}
        return None
    return None


def build_supplemental_jurisprudence_chunks(citation: dict[str, Any], payload: dict[str, Any]) -> list[dict[str, Any]]:
    registry_id = str(payload.get("registry_id") or citation.get("registry_id") or "").strip()
    title = grounding.normalize_space(payload.get("title") or payload.get("Rubro") or payload.get("rubro"))
    text = grounding.normalize_space(payload.get("text") or payload.get("Texto") or payload.get("texto"))
    doc_id = str(citation.get("doc_id") or f"mx-sjf-{infer_scjn_kind(citation)}-{registry_id}")
    source_url = payload.get("source_url") or citation.get("source_url")
    base_record = {
        "doc_id": doc_id,
        "doc_type": "jurisprudence",
        "document_kind": infer_scjn_kind(citation),
        "registry_id": registry_id,
        "title": title,
        "type": payload.get("type") or payload.get("TipoTesis"),
        "epoch": payload.get("epoch") or payload.get("Epoca"),
        "instance": payload.get("instance") or payload.get("Instancia"),
        "organ": payload.get("organ") or payload.get("Tribunal"),
        "matter": payload.get("matter") or payload.get("MateriasTesis") or [],
        "publication_date": payload.get("publication_date") or payload.get("FechaPublicacion"),
        "source_url": source_url,
        "citation_label": payload.get("citation_label") or title or citation.get("title"),
    }
    return [
        {
            **base_record,
            "chunk_id": f"{doc_id}:rubro",
            "section": "rubro",
            "text": title,
        },
        {
            **base_record,
            "chunk_id": f"{doc_id}:texto",
            "section": "texto",
            "text": text,
        },
    ]


def build_supplemental_legislation_chunks(citation: dict[str, Any], payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "chunk_id": f"{citation['doc_id']}:{citation.get('locator', 'live').replace(' ', '_')}:live",
            "doc_id": citation["doc_id"],
            "doc_type": "legislation",
            "jurisdiction": citation.get("jurisdiction"),
            "title": payload.get("title") or citation.get("title"),
            "source_url": payload.get("source_url") or citation.get("source_url"),
            "text": payload.get("text") or citation.get("quote") or "",
            "citation_label": payload.get("citation_label") or f"{citation.get('title')}, {citation.get('locator')}",
        }
    ]


def verify_scjn_live(citation: dict[str, Any], *, timeout: int) -> dict[str, Any]:
    registry_id = str(citation.get("registry_id") or "").strip()
    if not registry_id:
        return {"verified": False, "reason": "missing_registry_id", "adapter": "scjn_sjf_api"}
    kind = infer_scjn_kind(citation)
    payload = fetch_json(f"{SCJN_API_BASE}/{kind}/{registry_id}", timeout)
    title = grounding.normalize_space(payload.get("Rubro") or payload.get("rubro"))
    if citation.get("title") and grounding.normalize_space(citation["title"]).lower() != title.lower():
        return {
            "verified": False,
            "reason": "title_mismatch",
            "adapter": "scjn_sjf_api",
            "canonical_title": title,
            "payload": payload,
        }
    tipo = grounding.normalize_space(payload.get("TipoTesis") or payload.get("tipoTesis"))
    binding_status = "binding" if "jurisprud" in tipo.lower() else "persuasive"
    payload = {**payload, "registry_id": registry_id}
    return {
        "verified": True,
        "adapter": "scjn_sjf_api",
        "binding_status": binding_status,
        "payload": payload,
        "supplemental_jurisprudence_chunks": build_supplemental_jurisprudence_chunks(citation, payload),
    }


def verify_legislation_live(citation: dict[str, Any], *, timeout: int) -> dict[str, Any]:
    source_url = str(citation.get("source_url") or "")
    if "diputados.gob.mx" in source_url:
        source_id = infer_source_id(citation)
        if not source_id:
            return {"verified": False, "reason": "missing_source_id", "adapter": "diputados_ref"}
        records, errors = diputados_metadata.fetch_many([source_id], timeout=timeout, retries=1, retry_delay=0.0)
        if errors or not records:
            return {"verified": False, "reason": "diputados_fetch_failed", "adapter": "diputados_ref", "errors": errors}
        record = records[0]
        if citation.get("title") and grounding.normalize_space(citation["title"]).lower() != grounding.normalize_space(record.get("title")).lower():
            return {"verified": False, "reason": "title_mismatch", "adapter": "diputados_ref", "payload": record}
        return {
            "verified": True,
            "adapter": "diputados_ref",
            "binding_status": "binding",
            "payload": record,
            "supplemental_legislation_chunks": build_supplemental_legislation_chunks(citation, record),
        }
    if "dof.gob.mx" in source_url:
        body = fetch_text(source_url, timeout)
        if not body.strip():
            return {"verified": False, "reason": "empty_dof_body", "adapter": "dof_live"}
        payload = {"title": citation.get("title"), "source_url": source_url}
        return {
            "verified": True,
            "adapter": "dof_live",
            "binding_status": "binding",
            "payload": payload,
            "supplemental_legislation_chunks": build_supplemental_legislation_chunks(citation, payload),
        }
    return {"verified": False, "reason": "unsupported_legislation_source", "adapter": "legislation_live"}


def verify_licensed_live(citation: dict[str, Any], *, provider_registry: dict[str, dict[str, Any]], timeout: int) -> dict[str, Any]:
    provider_id = citation.get("provider_id")
    if not provider_id or provider_id not in provider_registry:
        return {"verified": False, "reason": "provider_unknown", "adapter": "licensed_provider"}
    provider = provider_registry[provider_id]
    base_url = os.getenv(provider["base_url_env"], "").strip()
    api_key = os.getenv(provider["api_key_env"], "").strip()
    if not base_url or not api_key:
        return {"verified": False, "reason": "provider_unconfigured", "adapter": provider_id}
    query = urllib.parse.quote(str(citation.get("locator") or citation.get("title") or ""))
    template = provider.get("query_url_template")
    if not template:
        return {"verified": False, "reason": "query_template_missing", "adapter": provider_id}
    url = template.format(base_url=base_url.rstrip("/"), query=query)
    payload = fetch_text(url, timeout, headers={"Authorization": f"Bearer {api_key}", "User-Agent": "legalize-mx/0.1"})
    if not payload.strip():
        return {"verified": False, "reason": "empty_provider_response", "adapter": provider_id}
    result_payload = {"title": citation.get("title"), "source_url": citation.get("source_url"), "provider_id": provider_id}
    supplemental = build_supplemental_jurisprudence_chunks(citation, {**result_payload, "text": citation.get("quote") or citation.get("title") or ""}) if citation.get("doc_type") == "jurisprudence" else build_supplemental_legislation_chunks(citation, result_payload)
    return {
        "verified": True,
        "adapter": provider_id,
        "binding_status": "unknown",
        "payload": result_payload,
        "supplemental_jurisprudence_chunks": supplemental if citation.get("doc_type") == "jurisprudence" else [],
        "supplemental_legislation_chunks": supplemental if citation.get("doc_type") == "legislation" else [],
    }


def verify_live_authority(
    citation: dict[str, Any],
    *,
    policy: dict[str, Any],
    provider_registry: dict[str, dict[str, Any]],
    live_fixture: dict[str, Any],
    timeout: int,
) -> dict[str, Any]:
    fixture_payload = live_fixture.get("citations", {}).get(citation.get("citation_id"))
    if fixture_payload is not None:
        result = dict(fixture_payload)
        result.setdefault("adapter", "fixture")
        if result.get("verified"):
            if citation.get("doc_type") == "jurisprudence":
                result.setdefault(
                    "supplemental_jurisprudence_chunks",
                    build_supplemental_jurisprudence_chunks(citation, result.get("payload", {})),
                )
            elif citation.get("doc_type") == "legislation":
                result.setdefault(
                    "supplemental_legislation_chunks",
                    build_supplemental_legislation_chunks(citation, result.get("payload", {})),
                )
        return result

    if citation.get("provider_id"):
        return verify_licensed_live(citation, provider_registry=provider_registry, timeout=timeout)
    if citation.get("doc_type") == "jurisprudence":
        return verify_scjn_live(citation, timeout=timeout)
    if citation.get("doc_type") == "legislation":
        return verify_legislation_live(citation, timeout=timeout)
    return {"verified": False, "reason": "unsupported_doc_type", "adapter": "unknown"}


def build_receipt(
    *,
    bundle_path: Path,
    bundle: dict[str, Any],
    policy_path: Path,
    policy: dict[str, Any],
    verdict: str,
    summary: dict[str, Any],
    failures: list[GateFailure],
    resolutions: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "receipt_type": "legal_authority_verification_receipt",
        "gate_id": policy.get("policy_id"),
        "created_at": utc_now_iso(),
        "verdict": verdict,
        "bundle_path": str(bundle_path),
        "bundle_sha256": sha256_text(json.dumps(bundle, ensure_ascii=False, sort_keys=True)),
        "policy_path": str(policy_path),
        "policy_sha256": sha256_text(json.dumps(policy, ensure_ascii=False, sort_keys=True)),
        "summary": summary,
        "resolutions": resolutions,
        "failures": [
            {"code": failure.code, "message": failure.message, "details": failure.details}
            for failure in failures
        ],
    }


def evaluate_bundle(
    *,
    bundle: dict[str, Any],
    root: Path,
    policy: dict[str, Any],
    live_fixture: dict[str, Any] | None = None,
    provider_registry: dict[str, dict[str, Any]] | None = None,
    timeout: int = 20,
) -> tuple[str, dict[str, Any], list[GateFailure], dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    live_fixture = live_fixture or {"citations": {}}
    provider_registry = provider_registry or {}
    legislation_chunks, jurisprudence_chunks = grounding.load_indexes(root)
    failures: list[GateFailure] = []
    supplemental = {"legislation_chunks": [], "jurisprudence_chunks": []}
    resolutions: list[dict[str, Any]] = []

    require_live_for = set(policy.get("require_live_for_doc_types", []))
    citations = bundle.get("citations") if isinstance(bundle.get("citations"), list) else []
    for citation in citations:
        if not isinstance(citation, dict):
            failures.append(GateFailure("citation.invalid", "Una cita no es objeto JSON.", {}))
            continue
        local_match = local_match_for_citation(
            citation,
            legislation_chunks=legislation_chunks,
            jurisprudence_chunks=jurisprudence_chunks,
        )
        live_result = verify_live_authority(
            citation,
            policy=policy,
            provider_registry=provider_registry,
            live_fixture=live_fixture,
            timeout=timeout,
        )
        verified_local = local_match is not None
        verified_live = bool(live_result.get("verified"))

        if citation.get("doc_type") in require_live_for and not verified_live:
            failures.append(
                GateFailure(
                    "authority.live.required",
                    "La politica exige verificacion live para esta cita y no se obtuvo.",
                    {"citation_id": citation.get("citation_id"), "adapter": live_result.get("adapter"), "reason": live_result.get("reason")},
                )
            )

        if not verified_local and not verified_live:
            failures.append(
                GateFailure(
                    "authority.unresolved",
                    "La cita no pudo verificarse ni localmente ni por resolvedor autorizado.",
                    {"citation_id": citation.get("citation_id"), "adapter": live_result.get("adapter"), "reason": live_result.get("reason")},
                )
            )

        if verified_live and citation.get("asserted_authority_role") == "binding" and live_result.get("binding_status") not in ("binding", "unknown"):
            failures.append(
                GateFailure(
                    "authority.binding.unsatisfied",
                    "La cita se presento como vinculante pero el resolvedor no la confirmo como tal.",
                    {"citation_id": citation.get("citation_id"), "binding_status": live_result.get("binding_status")},
                )
            )

        supplemental["jurisprudence_chunks"].extend(live_result.get("supplemental_jurisprudence_chunks", []))
        supplemental["legislation_chunks"].extend(live_result.get("supplemental_legislation_chunks", []))
        resolutions.append(
            {
                "citation_id": citation.get("citation_id"),
                "verified_local": verified_local,
                "verified_live": verified_live,
                "local_match_type": None if local_match is None else local_match["match_type"],
                "live_adapter": live_result.get("adapter"),
                "live_reason": live_result.get("reason"),
            }
        )

    summary = {
        "citations_total": len(citations),
        "verified_local": sum(1 for item in resolutions if item["verified_local"]),
        "verified_live": sum(1 for item in resolutions if item["verified_live"]),
        "supplemental_jurisprudence_chunks": len(supplemental["jurisprudence_chunks"]),
        "supplemental_legislation_chunks": len(supplemental["legislation_chunks"]),
        "failure_count": len(failures),
    }
    verdict = "PASS" if not failures else "FAIL"
    return verdict, summary, failures, supplemental, resolutions


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida autoridad juridica contra corpus local y resolvedores autorizados.")
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--root", default="/root/legalize-mx")
    parser.add_argument("--policy", default="/root/legalize-mx/config/legal_authority_resolution_policy.json")
    parser.add_argument("--providers", default="/root/legalize-mx/sources/licensed_authority_connectors.json")
    parser.add_argument("--live-fixture", default=None)
    parser.add_argument("--receipt-log", default="/root/legalize-mx/raw/guardrails/receipts/legal_authority_verification_receipts.jsonl")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()

    root = Path(args.root)
    bundle_path = Path(args.bundle)
    policy_path = Path(args.policy)
    providers_path = Path(args.providers)
    live_fixture_path = Path(args.live_fixture) if args.live_fixture else None
    receipt_log = Path(args.receipt_log)

    try:
        bundle = load_json(bundle_path)
        policy = load_json(policy_path)
        live_fixture = load_live_fixture(live_fixture_path)
        provider_registry = load_provider_registry(providers_path)
        verdict, summary, failures, supplemental, resolutions = evaluate_bundle(
            bundle=bundle,
            root=root,
            policy=policy,
            live_fixture=live_fixture,
            provider_registry=provider_registry,
            timeout=args.timeout,
        )
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"verdict": "ERROR", "exit_code": EXIT_ERROR, "error": str(exc)}, ensure_ascii=False, indent=2))
        return EXIT_ERROR

    receipt = build_receipt(
        bundle_path=bundle_path,
        bundle=bundle,
        policy_path=policy_path,
        policy=policy,
        verdict=verdict,
        summary=summary,
        failures=failures,
        resolutions=resolutions,
    )
    append_receipt(receipt_log, receipt)
    print(
        json.dumps(
            {
                "verdict": verdict,
                "exit_code": EXIT_OK if verdict == "PASS" else EXIT_FAIL,
                "summary": summary,
                "supplemental": supplemental,
                "failures": [
                    {"code": failure.code, "message": failure.message, "details": failure.details}
                    for failure in failures
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return EXIT_OK if verdict == "PASS" else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main())
