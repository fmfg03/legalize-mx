from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import legal_release_gates as release_gate  # noqa: E402
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


def test_shared_gates_use_server_fixture_text_without_emitting_release(tmp_path: Path):
    bundle = json.loads((REPO_ROOT / "fixtures/assistant_response_live_resolution.json").read_text())
    fixture = json.loads((REPO_ROOT / "fixtures/legal_authority_live_fixture.json").read_text())
    authority_result, grounding_result = release_gate.evaluate_release_gates(
        bundle=bundle, root=REPO_ROOT,
        grounding_policy=json.loads((REPO_ROOT / "config/jurisprudence_grounding_policy.json").read_text()),
        authority_policy=json.loads((REPO_ROOT / "config/legal_authority_resolution_policy.json").read_text()),
        provider_registry={}, live_fixture=fixture,
    )
    assert authority_result[0] == "PASS"
    assert grounding_result[0] == "PASS"
    assert not list(tmp_path.iterdir())
