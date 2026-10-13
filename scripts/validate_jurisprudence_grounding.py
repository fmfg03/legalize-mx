#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


EXIT_OK = 0
EXIT_FAIL = 1
EXIT_ERROR = 2


@dataclass
class GateFailure:
    code: str
    message: str
    details: Dict[str, Any]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        rows.append(json.loads(raw))
    return rows


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def build_receipt(
    *,
    bundle_path: Path,
    bundle: Dict[str, Any],
    policy_path: Path,
    policy: Dict[str, Any],
    verdict: str,
    failures: List[GateFailure],
    summary: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "receipt_type": "jurisprudence_grounding_gate_receipt",
        "gate_id": policy.get("policy_id"),
        "created_at": utc_now_iso(),
        "verdict": verdict,
        "bundle_path": str(bundle_path),
        "bundle_sha256": sha256_text(json.dumps(bundle, ensure_ascii=False, sort_keys=True)),
        "policy_path": str(policy_path),
        "policy_sha256": sha256_text(json.dumps(policy, ensure_ascii=False, sort_keys=True)),
        "summary": summary,
        "failures": [
            {
                "code": failure.code,
                "message": failure.message,
                "details": failure.details,
            }
            for failure in failures
        ],
    }


def append_receipt(path: Path, receipt: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, ensure_ascii=False) + "\n")


def validate_bundle_shape(bundle: Dict[str, Any]) -> List[GateFailure]:
    failures: List[GateFailure] = []
    if not isinstance(bundle.get("response_text"), str) or not bundle["response_text"].strip():
        failures.append(GateFailure("bundle.response_text.missing", "El paquete no contiene `response_text` valido.", {}))
    citations = bundle.get("citations")
    if not isinstance(citations, list):
        failures.append(GateFailure("bundle.citations.invalid", "El paquete no contiene una lista `citations`.", {}))
    claims = bundle.get("claims")
    if not isinstance(claims, list):
        failures.append(GateFailure("bundle.claims.invalid", "El paquete no contiene una lista `claims`.", {}))
    return failures


def validate_citation_fields(citation: Dict[str, Any]) -> List[GateFailure]:
    failures: List[GateFailure] = []
    required = ["citation_id", "doc_type", "doc_id", "title", "locator", "jurisdiction", "source_url"]
    for key in required:
        value = citation.get(key)
        if not isinstance(value, str) or not value.strip():
            failures.append(
                GateFailure(
                    "citation.field.missing",
                    f"La cita carece de `{key}`.",
                    {"citation_id": citation.get("citation_id"), "field": key},
                )
            )
    quote = citation.get("quote")
    quote_sha256 = citation.get("quote_sha256")
    if quote is not None and quote_sha256 is not None:
        if sha256_text(quote) != quote_sha256:
            failures.append(
                GateFailure(
                    "citation.quote.hash_mismatch",
                    "La cita declara `quote_sha256` que no coincide con `quote`.",
                    {"citation_id": citation.get("citation_id")},
                )
            )
    return failures


def load_indexes(root: Path) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    legislation = load_jsonl(root / "indexes" / "legislation_chunks.jsonl")
    jurisprudence = load_jsonl(root / "indexes" / "jurisprudence_chunks.jsonl")
    return legislation, jurisprudence


def match_jurisprudence_citation(
    citation: Dict[str, Any],
    jurisprudence_chunks: List[Dict[str, Any]],
    require_quote: bool,
) -> Tuple[bool, Dict[str, Any] | None, str]:
    citation_id = citation.get("citation_id")
    candidates: List[Dict[str, Any]] = []
    for chunk in jurisprudence_chunks:
        if citation.get("doc_id") and chunk.get("doc_id") == citation.get("doc_id"):
            candidates.append(chunk)
            continue
        if citation.get("chunk_id") and chunk.get("chunk_id") == citation.get("chunk_id"):
            candidates.append(chunk)
            continue
        if citation.get("registry_id") and chunk.get("registry_id") == citation.get("registry_id"):
            candidates.append(chunk)
            continue
        if citation.get("source_url") and chunk.get("source_url") == citation.get("source_url"):
            candidates.append(chunk)
            continue
    if not candidates:
        return False, None, f"Sin coincidencia en indice local para {citation_id}."

    source_url = citation.get("source_url")
    title = normalize_space(citation.get("title", "")).lower()
    exact: List[Dict[str, Any]] = []
    for chunk in candidates:
        if any(citation.get(field) and str(chunk.get(field, "")) != str(citation[field]) for field in ("doc_id", "registry_id", "chunk_id")):
            continue
        if source_url and chunk.get("source_url") != source_url:
            continue
        if title and normalize_space(chunk.get("title", "")).lower() != title:
            continue
        exact.append(chunk)
    if not exact:
        return False, None, f"Los identificadores o metadatos de {citation_id} contradicen la evidencia del servidor."
    candidates = exact

    quote = citation.get("quote")
    if require_quote and (not isinstance(quote, str) or not quote.strip()):
        return False, None, f"La cita jurisprudencial {citation_id} no trae `quote` verificable."

    if isinstance(quote, str) and quote.strip():
        quote_norm = normalize_space(quote)
        quoted = [chunk for chunk in candidates if quote_norm in normalize_space(chunk.get("text", ""))]
        if not quoted:
            return False, None, f"La `quote` de {citation_id} no aparece en el indice local."
        candidates = quoted

    if len(candidates) > 1:
        return False, None, f"La cita jurisprudencial {citation_id} es ambigua en el indice local."

    return True, candidates[0], "ok"


def legislation_citation_matches(citation: Dict[str, Any], chunk: Dict[str, Any]) -> bool:
    if any(chunk.get(field) != citation.get(field) for field in ("doc_id", "source_url")):
        return False
    if normalize_space(chunk.get("title", "")).lower() != normalize_space(citation.get("title", "")).lower():
        return False
    locator = normalize_space(citation.get("locator", "")).lower()
    expected_locator = normalize_space(chunk.get("locator") or chunk.get("heading") or "").lower()
    if not locator or locator != expected_locator:
        return False
    quote = citation.get("quote")
    return isinstance(quote, str) and bool(quote.strip()) and normalize_space(quote) in normalize_space(chunk.get("text", ""))


def detect_forbidden_mentions(text: str, patterns: List[str]) -> List[str]:
    hits: List[str] = []
    for pattern in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            hits.append(pattern)
    return hits


def evaluate_bundle(
    *,
    bundle: Dict[str, Any],
    policy: Dict[str, Any],
    legislation_chunks: List[Dict[str, Any]],
    jurisprudence_chunks: List[Dict[str, Any]],
    supplemental_legislation_chunks: List[Dict[str, Any]] | None = None,
    supplemental_jurisprudence_chunks: List[Dict[str, Any]] | None = None,
) -> Tuple[str, Dict[str, Any], List[GateFailure]]:
    legislation_chunks = legislation_chunks + list(supplemental_legislation_chunks or [])
    jurisprudence_chunks = jurisprudence_chunks + list(supplemental_jurisprudence_chunks or [])
    failures = validate_bundle_shape(bundle)
    citations = bundle.get("citations") if isinstance(bundle.get("citations"), list) else []
    claims = bundle.get("claims") if isinstance(bundle.get("claims"), list) else []
    citation_map: Dict[str, Dict[str, Any]] = {}
    validated_jurisprudence_citation_ids: List[str] = []
    validated_legislation_citation_ids: List[str] = []

    for citation in citations:
        if not isinstance(citation, dict):
            failures.append(GateFailure("citation.invalid", "Una entrada de `citations` no es objeto JSON.", {}))
            continue
        failures.extend(validate_citation_fields(citation))
        citation_id = citation.get("citation_id")
        if isinstance(citation_id, str) and citation_id:
            citation_map[citation_id] = citation

        if citation.get("doc_type") == "jurisprudence":
            ok, matched_chunk, message = match_jurisprudence_citation(
                citation,
                jurisprudence_chunks,
                bool(policy.get("require_quote_for_jurisprudence", True)),
            )
            if ok and matched_chunk is not None:
                validated_jurisprudence_citation_ids.append(citation_id)
            else:
                failures.append(
                    GateFailure(
                        "jurisprudence.citation.unverified",
                        "La cita jurisprudencial no pudo verificarse contra el indice local.",
                        {"citation_id": citation_id, "reason": message},
                    )
                )
        elif citation.get("doc_type") == "legislation":
            if any(
                legislation_citation_matches(citation, chunk)
                for chunk in legislation_chunks
            ):
                validated_legislation_citation_ids.append(citation_id)
            else:
                failures.append(
                    GateFailure(
                        "legislation.citation.unverified",
                        "La cita legislativa no coincide con el indice local.",
                        {"citation_id": citation_id},
                    )
                )
        else:
            failures.append(GateFailure("citation.doc_type.unsupported", "Tipo de cita no soportado.", {"citation_id": citation_id}))

    jurisprudence_kinds = set(policy.get("jurisprudence_claim_kinds", []))
    for claim in claims:
        if not isinstance(claim, dict):
            failures.append(GateFailure("claim.invalid", "Una entrada de `claims` no es objeto JSON.", {}))
            continue
        claim_id = claim.get("claim_id")
        citation_ids = claim.get("citation_ids")
        if not isinstance(citation_ids, list):
            failures.append(
                GateFailure(
                    "claim.citations.invalid",
                    "El claim no contiene `citation_ids` valido.",
                    {"claim_id": claim_id},
                )
            )
            continue

        missing_ids = [citation_id for citation_id in citation_ids if citation_id not in citation_map]
        if missing_ids:
            failures.append(
                GateFailure(
                    "claim.citations.missing",
                    "El claim referencia citas inexistentes en el bundle.",
                    {"claim_id": claim_id, "missing_citation_ids": missing_ids},
                )
            )

        claim_kind = claim.get("kind")
        if claim_kind in jurisprudence_kinds:
            if not any(citation_id in validated_jurisprudence_citation_ids for citation_id in citation_ids):
                failures.append(
                    GateFailure(
                        "claim.jurisprudence.unsupported",
                        "El claim jurisprudencial no tiene una cita jurisprudencial verificada.",
                        {"claim_id": claim_id, "citation_ids": citation_ids},
                    )
                )

    forbidden_hits = detect_forbidden_mentions(bundle.get("response_text", ""), policy.get("forbidden_without_evidence_patterns", []))
    if forbidden_hits and not validated_jurisprudence_citation_ids:
        failures.append(
            GateFailure(
                "response.jurisprudence.unsupported",
                "La respuesta menciona jurisprudencia pero no tiene evidencia jurisprudencial verificada.",
                {"matched_patterns": forbidden_hits},
            )
        )

    verdict = "PASS" if not failures else "FAIL"
    summary = {
        "citations_total": len(citations),
        "claims_total": len(claims),
        "validated_legislation_citations": len(validated_legislation_citation_ids),
        "validated_jurisprudence_citations": len(validated_jurisprudence_citation_ids),
        "jurisprudence_index_entries": len(jurisprudence_chunks),
        "forbidden_pattern_hits": forbidden_hits,
        "failure_count": len(failures),
    }
    return verdict, summary, failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida que una salida juridica no invente jurisprudencia.")
    parser.add_argument("--bundle", required=True, help="Ruta al paquete JSON de salida del asistente.")
    parser.add_argument(
        "--policy",
        default="/root/legalize-mx/config/jurisprudence_grounding_policy.json",
        help="Politica declarativa del gate.",
    )
    parser.add_argument(
        "--root",
        default="/root/legalize-mx",
        help="Raiz del repositorio legalize-mx.",
    )
    parser.add_argument(
        "--receipt-log",
        default="/root/legalize-mx/raw/guardrails/receipts/jurisprudence_grounding_gate_receipts.jsonl",
        help="JSONL donde se anexan los recibos del gate.",
    )
    parser.add_argument(
        "--no-write-receipt",
        action="store_true",
        help="No persiste el recibo. Solo imprime el resultado.",
    )
    args = parser.parse_args()

    root = Path(args.root)
    bundle_path = Path(args.bundle)
    policy_path = Path(args.policy)
    receipt_log = Path(args.receipt_log)

    try:
        bundle = load_json(bundle_path)
        policy = load_json(policy_path)
        legislation_chunks, jurisprudence_chunks = load_indexes(root)
    except Exception as exc:  # noqa: BLE001
        print(
            json.dumps(
                {
                    "verdict": "ERROR",
                    "exit_code": EXIT_ERROR,
                    "error": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return EXIT_ERROR

    verdict, summary, failures = evaluate_bundle(
        bundle=bundle,
        policy=policy,
        legislation_chunks=legislation_chunks,
        jurisprudence_chunks=jurisprudence_chunks,
    )
    receipt = build_receipt(
        bundle_path=bundle_path,
        bundle=bundle,
        policy_path=policy_path,
        policy=policy,
        verdict=verdict,
        failures=failures,
        summary=summary,
    )

    if not args.no_write_receipt:
        append_receipt(receipt_log, receipt)

    output = {
        "verdict": verdict,
        "exit_code": EXIT_OK if verdict == "PASS" else EXIT_FAIL,
        "summary": summary,
        "failures": receipt["failures"],
        "receipt_log": None if args.no_write_receipt else str(receipt_log),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return EXIT_OK if verdict == "PASS" else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main())
