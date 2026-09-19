from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import release_legal_response as release_gate  # noqa: E402
import validate_legal_authority as authority  # noqa: E402
import validate_jurisprudence_grounding as grounding  # noqa: E402


def test_authority_gate_accepts_live_fixture_when_local_index_missing():
    bundle = json.loads((REPO_ROOT / "fixtures" / "assistant_response_live_resolution.json").read_text(encoding="utf-8"))
    policy = json.loads((REPO_ROOT / "config" / "legal_authority_resolution_policy.json").read_text(encoding="utf-8"))
    fixture = json.loads((REPO_ROOT / "fixtures" / "legal_authority_live_fixture.json").read_text(encoding="utf-8"))
    providers = json.loads((REPO_ROOT / "sources" / "licensed_authority_connectors.json").read_text(encoding="utf-8"))
    verdict, summary, failures, supplemental, resolutions = authority.evaluate_bundle(
        bundle=bundle,
        root=REPO_ROOT,
        policy=policy,
        live_fixture=fixture,
        provider_registry={item["provider_id"]: item for item in providers["providers"]},
    )
    assert verdict == "PASS"
    assert summary["verified_live"] == 2
    assert not failures
    assert supplemental["jurisprudence_chunks"]
    assert supplemental["legislation_chunks"]
    assert any(item["citation_id"] == "cit-live-juris-1" and item["verified_live"] for item in resolutions)


def test_grounding_gate_accepts_supplemental_live_jurisprudence_chunks():
    bundle = json.loads((REPO_ROOT / "fixtures" / "assistant_response_live_resolution.json").read_text(encoding="utf-8"))
    policy = json.loads((REPO_ROOT / "config" / "jurisprudence_grounding_policy.json").read_text(encoding="utf-8"))
    fixture = json.loads((REPO_ROOT / "fixtures" / "legal_authority_live_fixture.json").read_text(encoding="utf-8"))
    providers = json.loads((REPO_ROOT / "sources" / "licensed_authority_connectors.json").read_text(encoding="utf-8"))
    _, _, _, supplemental, _ = authority.evaluate_bundle(
        bundle=bundle,
        root=REPO_ROOT,
        policy=json.loads((REPO_ROOT / "config" / "legal_authority_resolution_policy.json").read_text(encoding="utf-8")),
        live_fixture=fixture,
        provider_registry={item["provider_id"]: item for item in providers["providers"]},
    )
    legislation_chunks, jurisprudence_chunks = grounding.load_indexes(REPO_ROOT)
    verdict, summary, failures = grounding.evaluate_bundle(
        bundle=bundle,
        policy=policy,
        legislation_chunks=legislation_chunks,
        jurisprudence_chunks=jurisprudence_chunks,
        supplemental_legislation_chunks=supplemental["legislation_chunks"],
        supplemental_jurisprudence_chunks=supplemental["jurisprudence_chunks"],
    )
    assert verdict == "PASS"
    assert summary["validated_jurisprudence_citations"] == 1
    assert not failures


def test_release_gate_approves_bundle_with_live_fixture_support(tmp_path: Path):
    bundle_path = REPO_ROOT / "fixtures" / "assistant_response_live_resolution.json"
    exit_code, payload = release_gate.release_bundle(
        bundle_path=bundle_path,
        root=REPO_ROOT,
        release_policy_path=REPO_ROOT / "config" / "legal_response_release_policy.json",
        grounding_policy_path=REPO_ROOT / "config" / "jurisprudence_grounding_policy.json",
        authority_policy_path=REPO_ROOT / "config" / "legal_authority_resolution_policy.json",
        authority_provider_path=REPO_ROOT / "sources" / "licensed_authority_connectors.json",
        grounding_receipt_log=tmp_path / "grounding.jsonl",
        authority_receipt_log=tmp_path / "authority.jsonl",
        release_receipt_log=tmp_path / "release.jsonl",
        release_dir=tmp_path / "releases",
        authority_live_fixture_path=REPO_ROOT / "fixtures" / "legal_authority_live_fixture.json",
    )
    assert exit_code == 0
    assert payload["release_verdict"] == "APPROVED"
    assert payload["authority_verdict"] == "PASS"
    assert payload["gate_verdict"] == "PASS"
