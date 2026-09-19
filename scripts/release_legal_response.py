#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import validate_jurisprudence_grounding as grounding
import validate_legal_authority as authority


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


def release_bundle(
    *,
    bundle_path: Path,
    root: Path,
    release_policy_path: Path,
    grounding_policy_path: Path,
    authority_policy_path: Path,
    authority_provider_path: Path,
    grounding_receipt_log: Path,
    authority_receipt_log: Path,
    release_receipt_log: Path,
    release_dir: Path,
    authority_live_fixture_path: Path | None = None,
) -> tuple[int, dict[str, Any]]:
    bundle = grounding.load_json(bundle_path)
    release_policy = grounding.load_json(release_policy_path)
    grounding_policy = grounding.load_json(grounding_policy_path)
    authority_policy = authority.load_json(authority_policy_path)
    provider_registry = authority.load_provider_registry(authority_provider_path)
    live_fixture = authority.load_live_fixture(authority_live_fixture_path)
    legislation_chunks, jurisprudence_chunks = grounding.load_indexes(root)

    authority_verdict, authority_summary, authority_failures, supplemental, resolutions = authority.evaluate_bundle(
        bundle=bundle,
        root=root,
        policy=authority_policy,
        live_fixture=live_fixture,
        provider_registry=provider_registry,
    )
    authority_receipt = authority.build_receipt(
        bundle_path=bundle_path,
        bundle=bundle,
        policy_path=authority_policy_path,
        policy=authority_policy,
        verdict=authority_verdict,
        summary=authority_summary,
        failures=authority_failures,
        resolutions=resolutions,
    )
    authority.append_receipt(authority_receipt_log, authority_receipt)

    gate_verdict, gate_summary, gate_failures = grounding.evaluate_bundle(
        bundle=bundle,
        policy=grounding_policy,
        legislation_chunks=legislation_chunks,
        jurisprudence_chunks=jurisprudence_chunks,
        supplemental_legislation_chunks=supplemental["legislation_chunks"],
        supplemental_jurisprudence_chunks=supplemental["jurisprudence_chunks"],
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

    release_verdict = "APPROVED" if authority_verdict == "PASS" and gate_verdict == "PASS" else "BLOCKED"
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
        "response_type": bundle.get("response_type"),
        "request_id": bundle.get("request_id"),
        "release_verdict": release_verdict,
        "release_reason": "all_required_gates_passed" if release_verdict == "APPROVED" else "required_gate_failed",
        "required_gates": release_policy.get("required_gates", []),
        "gates": [
            {
                "gate_id": authority_policy.get("policy_id"),
                "verdict": authority_verdict,
                "summary": authority_summary,
                "failure_count": len(authority_failures),
            },
            {
                "gate_id": grounding_policy.get("policy_id"),
                "verdict": gate_verdict,
                "summary": gate_summary,
                "failure_count": len(gate_failures),
            },
        ],
        "release_artifact_path": str(artifact_path),
        "release_policy_path": str(release_policy_path),
        "release_policy_sha256": sha256_text(json.dumps(release_policy, ensure_ascii=False, sort_keys=True)),
    }
    append_jsonl(release_receipt_log, release_receipt)
    payload = {
        "release_verdict": release_verdict,
        "exit_code": EXIT_OK if release_verdict == "APPROVED" else EXIT_BLOCKED,
        "authority_verdict": authority_verdict,
        "authority_summary": authority_summary,
        "authority_failures": [
            {"code": failure.code, "message": failure.message, "details": failure.details}
            for failure in authority_failures
        ],
        "gate_verdict": gate_verdict,
        "gate_summary": gate_summary,
        "gate_failures": [
            {"code": failure.code, "message": failure.message, "details": failure.details}
            for failure in gate_failures
        ],
        "authority_receipt_log": str(authority_receipt_log),
        "grounding_receipt_log": str(grounding_receipt_log),
        "release_receipt_log": str(release_receipt_log),
        "release_artifact_path": str(artifact_path),
    }
    return EXIT_OK if release_verdict == "APPROVED" else EXIT_BLOCKED, payload


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
        "--authority-policy",
        default="/root/legalize-mx/config/legal_authority_resolution_policy.json",
        help="Politica declarativa del gate de autoridad juridica.",
    )
    parser.add_argument(
        "--authority-providers",
        default="/root/legalize-mx/sources/licensed_authority_connectors.json",
        help="Registro de adapters para fuentes licenciadas.",
    )
    parser.add_argument(
        "--authority-live-fixture",
        default=None,
        help="Fixture opcional para simular resolvedores live en pruebas.",
    )
    parser.add_argument(
        "--grounding-receipt-log",
        default="/root/legalize-mx/raw/guardrails/receipts/jurisprudence_grounding_gate_receipts.jsonl",
        help="Bitacora JSONL del gate jurisprudencial.",
    )
    parser.add_argument(
        "--authority-receipt-log",
        default="/root/legalize-mx/raw/guardrails/receipts/legal_authority_verification_receipts.jsonl",
        help="Bitacora JSONL del gate de autoridad juridica.",
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
    authority_policy_path = Path(args.authority_policy)
    authority_provider_path = Path(args.authority_providers)
    authority_live_fixture_path = Path(args.authority_live_fixture) if args.authority_live_fixture else None
    grounding_receipt_log = Path(args.grounding_receipt_log)
    authority_receipt_log = Path(args.authority_receipt_log)
    release_receipt_log = Path(args.release_receipt_log)
    release_dir = Path(args.release_dir)

    try:
        bundle = grounding.load_json(bundle_path)
        release_policy = grounding.load_json(release_policy_path)
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

    exit_code, payload = release_bundle(
        bundle_path=bundle_path,
        root=root,
        release_policy_path=release_policy_path,
        grounding_policy_path=grounding_policy_path,
        authority_policy_path=authority_policy_path,
        authority_provider_path=authority_provider_path,
        grounding_receipt_log=grounding_receipt_log,
        authority_receipt_log=authority_receipt_log,
        release_receipt_log=release_receipt_log,
        release_dir=release_dir,
        authority_live_fixture_path=authority_live_fixture_path,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
