#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import validate_jurisprudence_grounding as grounding


EXIT_OK = 0
EXIT_BLOCKED = 1
EXIT_ERROR = 2


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def slug_for_bundle(bundle: Dict[str, Any], bundle_path: Path) -> str:
    request_id = bundle.get("request_id")
    if isinstance(request_id, str) and request_id.strip():
        return request_id.strip()
    return bundle_path.stem


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ruta obligatoria de liberacion para escritos juridicos con bloqueo de jurisprudencia inventada."
    )
    parser.add_argument("--bundle", required=True, help="Bundle JSON del escrito juridico.")
    parser.add_argument(
        "--root",
        default="/root/legalize-mx",
        help="Raiz del repositorio legalize-mx.",
    )
    parser.add_argument(
        "--release-policy",
        default="/root/legalize-mx/config/legal_response_release_policy.json",
        help="Politica declarativa de liberacion.",
    )
    parser.add_argument(
        "--grounding-policy",
        default="/root/legalize-mx/config/jurisprudence_grounding_policy.json",
        help="Politica declarativa del gate jurisprudencial.",
    )
    parser.add_argument(
        "--grounding-receipt-log",
        default="/root/legalize-mx/raw/guardrails/receipts/jurisprudence_grounding_gate_receipts.jsonl",
        help="Bitacora JSONL del gate jurisprudencial.",
    )
    parser.add_argument(
        "--release-receipt-log",
        default="/root/legalize-mx/raw/guardrails/receipts/legal_response_release_receipts.jsonl",
        help="Bitacora JSONL de liberacion de escritos.",
    )
    parser.add_argument(
        "--release-dir",
        default="/root/legalize-mx/raw/guardrails/releases",
        help="Directorio donde se guarda el bundle aprobado o bloqueado.",
    )
    args = parser.parse_args()

    root = Path(args.root)
    bundle_path = Path(args.bundle)
    release_policy_path = Path(args.release_policy)
    grounding_policy_path = Path(args.grounding_policy)
    grounding_receipt_log = Path(args.grounding_receipt_log)
    release_receipt_log = Path(args.release_receipt_log)
    release_dir = Path(args.release_dir)

    try:
        bundle = grounding.load_json(bundle_path)
        release_policy = grounding.load_json(release_policy_path)
        grounding_policy = grounding.load_json(grounding_policy_path)
        legislation_chunks, jurisprudence_chunks = grounding.load_indexes(root)
    except Exception as exc:  # noqa: BLE001
        print(
            json.dumps(
                {
                    "release_verdict": "ERROR",
                    "exit_code": EXIT_ERROR,
                    "error": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return EXIT_ERROR

    response_type = bundle.get("response_type")
    protected_types = set(release_policy.get("protected_response_types", []))
    if isinstance(response_type, str) and response_type not in protected_types:
        release_verdict = "BYPASS"
        slug = slug_for_bundle(bundle, bundle_path)
        artifact_path = release_dir / "bypass" / f"{slug}.json"
        write_json(artifact_path, bundle)
        release_receipt = {
            "receipt_type": "legal_response_release_receipt",
            "policy_id": release_policy.get("policy_id"),
            "created_at": utc_now_iso(),
            "bundle_path": str(bundle_path),
            "bundle_sha256": sha256_text(json.dumps(bundle, ensure_ascii=False, sort_keys=True)),
            "response_type": response_type,
            "release_verdict": release_verdict,
            "release_reason": "response_type_out_of_scope",
            "release_artifact_path": str(artifact_path),
        }
        append_jsonl(release_receipt_log, release_receipt)
        print(
            json.dumps(
                {
                    "release_verdict": release_verdict,
                    "exit_code": EXIT_OK,
                    "release_receipt_log": str(release_receipt_log),
                    "release_artifact_path": str(artifact_path),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return EXIT_OK

    gate_verdict, gate_summary, gate_failures = grounding.evaluate_bundle(
        bundle=bundle,
        policy=grounding_policy,
        legislation_chunks=legislation_chunks,
        jurisprudence_chunks=jurisprudence_chunks,
    )
    gate_receipt = grounding.build_receipt(
        bundle_path=bundle_path,
        bundle=bundle,
        policy_path=grounding_policy_path,
        policy=grounding_policy,
        verdict=gate_verdict,
        failures=gate_failures,
        summary=gate_summary,
    )
    grounding.append_receipt(grounding_receipt_log, gate_receipt)

    release_verdict = "APPROVED" if gate_verdict == "PASS" else "BLOCKED"
    bucket = "approved" if release_verdict == "APPROVED" else "blocked"
    slug = slug_for_bundle(bundle, bundle_path)
    artifact_path = release_dir / bucket / f"{slug}.json"
    write_json(artifact_path, bundle)

    release_receipt = {
        "receipt_type": "legal_response_release_receipt",
        "policy_id": release_policy.get("policy_id"),
        "created_at": utc_now_iso(),
        "bundle_path": str(bundle_path),
        "bundle_sha256": sha256_text(json.dumps(bundle, ensure_ascii=False, sort_keys=True)),
        "response_type": response_type,
        "request_id": bundle.get("request_id"),
        "release_verdict": release_verdict,
        "release_reason": "grounding_gate_passed" if release_verdict == "APPROVED" else "grounding_gate_failed",
        "required_gates": release_policy.get("required_gates", []),
        "gates": [
            {
                "gate_id": grounding_policy.get("policy_id"),
                "verdict": gate_verdict,
                "summary": gate_summary,
                "failure_count": len(gate_failures),
            }
        ],
        "release_artifact_path": str(artifact_path),
        "release_policy_path": str(release_policy_path),
        "release_policy_sha256": sha256_text(json.dumps(release_policy, ensure_ascii=False, sort_keys=True)),
    }
    append_jsonl(release_receipt_log, release_receipt)

    print(
        json.dumps(
            {
                "release_verdict": release_verdict,
                "exit_code": EXIT_OK if release_verdict == "APPROVED" else EXIT_BLOCKED,
                "gate_verdict": gate_verdict,
                "gate_summary": gate_summary,
                "gate_failures": [
                    {
                        "code": failure.code,
                        "message": failure.message,
                        "details": failure.details,
                    }
                    for failure in gate_failures
                ],
                "grounding_receipt_log": str(grounding_receipt_log),
                "release_receipt_log": str(release_receipt_log),
                "release_artifact_path": str(artifact_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return EXIT_OK if release_verdict == "APPROVED" else EXIT_BLOCKED


if __name__ == "__main__":
    raise SystemExit(main())
