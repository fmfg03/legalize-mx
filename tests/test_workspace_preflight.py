from __future__ import annotations

from scripts.run_operator_console import (
    build_defendability_messages,
    build_section_draft_messages,
    build_revision_messages,
    extract_json_object,
    find_section_document,
    find_document_version,
    get_draft_section_spec,
    get_synthesis_state,
    has_approved_receipt_for_version,
    normalize_defendability_gate,
    normalize_revision_payload,
    normalize_preflight_checklist,
)


def test_extract_json_object_handles_fenced_json() -> None:
    raw = """```json
    {
      "summary_status": "dudoso",
      "summary_note": "Falta personeria",
      "items": []
    }
    ```"""
    parsed = extract_json_object(raw)
    assert parsed["summary_status"] == "dudoso"
    assert parsed["summary_note"] == "Falta personeria"


def test_normalize_preflight_checklist_fills_missing_items() -> None:
    raw = {
        "summary_status": "acreditado",
        "summary_note": "Base suficiente",
        "items": [
            {
                "key": "personalidad",
                "label": "Personalidad",
                "status": "acreditado",
                "evidence": "Consta en demanda.",
                "risk": "",
                "next_action": "Ninguna",
            }
        ],
    }
    normalized = normalize_preflight_checklist(raw)
    assert normalized["summary_status"] == "acreditado"
    assert len(normalized["items"]) == 9
    assert normalized["items"][0]["key"] == "personalidad"
    assert normalized["items"][0]["status"] == "acreditado"
    assert normalized["items"][1]["key"] == "personeria"
    assert normalized["items"][1]["status"] == "faltante"


def test_get_synthesis_state_defaults_to_missing() -> None:
    status, synthesis = get_synthesis_state({"extra": {}})
    assert status == "missing"
    assert synthesis is None


def test_get_synthesis_state_returns_current_synthesis() -> None:
    expediente = {
        "extra": {
            "synthesis_status": "current",
            "latest_synthesis": {
                "title": "Sintesis vigente del expediente",
                "content": "Hechos confirmados...",
            },
        }
    }
    status, synthesis = get_synthesis_state(expediente)
    assert status == "current"
    assert synthesis["title"] == "Sintesis vigente del expediente"


def test_get_draft_section_spec_returns_known_section() -> None:
    spec = get_draft_section_spec("conceptos")
    assert spec["key"] == "conceptos"
    assert spec["label"] == "Conceptos de violacion"


def test_find_section_document_matches_bundle_and_section() -> None:
    expediente = {
        "documents": [
            {
                "id": "doc-1",
                "title": "Amparo indirecto - Antecedentes",
                "document_type": "demanda",
                "extra": {
                    "draft_bundle_title": "Amparo indirecto",
                    "draft_section_key": "antecedentes",
                },
            }
        ]
    }
    found = find_section_document(
        expediente,
        bundle_title="Amparo indirecto",
        section_key="antecedentes",
        document_type="demanda",
    )
    assert found is not None
    assert found["id"] == "doc-1"


def test_build_section_draft_messages_uses_synthesis_and_section() -> None:
    expediente = {
        "title": "Juicio de amparo",
        "expediente_number": "123/2026",
        "matter_type": "amparo",
        "jurisdiction_level": "federal",
        "court_or_authority": "Juzgado de Distrito",
        "summary": "Acto reclamado en tramite.",
        "parties": [{"display_name": "Quejoso Uno", "role": "quejoso"}],
        "documents": [
            {
                "title": "Demanda inicial",
                "document_type": "demanda",
                "versions": [
                    {
                        "extracted_text": "Se interpone demanda de amparo indirecto contra acto reclamado.",
                        "created_at": "2026-04-10T10:00:00Z",
                    }
                ],
            }
        ],
        "extra": {
            "pre_merits_checklist": {
                "summary_status": "dudoso",
                "summary_note": "Falta revisar personeria.",
            }
        },
    }
    messages, snippets = build_section_draft_messages(
        expediente,
        bundle_title="Amparo indirecto",
        section_key="antecedentes",
        document_type="demanda",
        prompt="Enfatiza la secuencia procesal.",
        synthesis={
            "content": "1. Expediente Snapshot\n2. Hechos Confirmados\n3. Cronologia Relevante",
            "generated_at": "2026-04-10T11:00:00Z",
        },
    )
    assert len(messages) == 2
    assert "Base Documental Usada" in messages[0]["content"]
    assert "Seccion solicitada: Antecedentes" in messages[1]["content"]
    assert "Sintesis vigente" in messages[1]["content"]
    assert snippets[0]["title"] == "Demanda inicial"


def test_find_document_version_returns_document_and_version() -> None:
    expediente = {
        "documents": [
            {
                "id": "doc-1",
                "title": "Escrito",
                "versions": [{"id": "ver-1", "version_number": 1}],
            }
        ]
    }
    document, version = find_document_version(expediente, "ver-1")
    assert document is not None
    assert version is not None
    assert document["id"] == "doc-1"
    assert version["version_number"] == 1


def test_has_approved_receipt_for_version_detects_guard() -> None:
    expediente = {
        "release_receipts": [
            {"document_version_id": "ver-1", "verdict": "approved", "execution_id": "exec-1"},
            {"document_version_id": "ver-2", "verdict": "blocked"},
            {"document_version_id": "ver-3", "verdict": "approved"},
        ]
    }
    assert has_approved_receipt_for_version(expediente, "ver-1") is True
    assert has_approved_receipt_for_version(expediente, "ver-2") is False
    assert has_approved_receipt_for_version(expediente, "ver-3") is False


def test_normalize_revision_payload_builds_diff_and_defaults() -> None:
    normalized = normalize_revision_payload(
        {
            "change_scope": "narrow",
            "confidence": "alto",
            "justification": ["Aclara plazo", "Quita redundancia"],
            "revised_text": "Linea uno ajustada\nLinea dos",
        },
        current_text="Linea uno\nLinea dos",
        requested_mode="narrow",
    )
    assert normalized["change_scope"] == "narrow"
    assert normalized["confidence"] == "alto"
    assert normalized["changed"] is True
    assert "--- version_actual" in normalized["diff_text"]
    assert "Aclara plazo" in normalized["justification"]


def test_build_revision_messages_mentions_mode_and_text() -> None:
    expediente = {
        "title": "Juicio de amparo",
        "expediente_number": "123/2026",
        "matter_type": "amparo",
        "jurisdiction_level": "federal",
        "court_or_authority": "Juzgado de Distrito",
        "parties": [{"display_name": "Quejoso Uno", "role": "quejoso"}],
        "documents": [],
        "extra": {
            "pre_merits_checklist": {
                "summary_status": "dudoso",
                "summary_note": "Falta revisar personeria.",
            }
        },
    }
    messages = build_revision_messages(
        expediente,
        document={"title": "Demanda - Hechos", "document_type": "demanda"},
        version={"version_number": 2, "extracted_text": "Texto base del escrito."},
        revision_mode="narrow",
        objective="Corrige estilo sin reescribir todo.",
        synthesis={"content": "Sintesis vigente"},
    )
    assert len(messages) == 2
    assert '"revised_text"' in messages[0]["content"]
    assert "Modo de revision: narrow" in messages[1]["content"]
    assert "Texto actual a revisar" in messages[1]["content"]


def test_build_defendability_messages_mentions_support_questions() -> None:
    expediente = {
        "title": "Juicio de amparo",
        "expediente_number": "123/2026",
        "parties": [{"display_name": "Quejoso Uno", "role": "quejoso"}],
        "documents": [],
    }
    messages = build_defendability_messages(
        expediente,
        document={"title": "Demanda - Conceptos", "document_type": "demanda"},
        version={"version_number": 1, "extracted_text": "Texto del escrito."},
        synthesis={"content": "Sintesis vigente"},
    )
    assert len(messages) == 2
    assert '"support_status"' in messages[0]["content"]
    assert "Que evidencia sostiene este punto" in messages[1]["content"]


def test_normalize_defendability_gate_blocks_for_critical_checklist_failures() -> None:
    expediente = {
        "extra": {
            "pre_merits_checklist": {
                "items": [
                    {"key": "personalidad", "status": "faltante"},
                    {"key": "personeria", "status": "acreditado"},
                    {"key": "poderes", "status": "acreditado"},
                    {"key": "legitimacion", "status": "acreditado"},
                    {"key": "emplazamiento_notificacion", "status": "acreditado"},
                    {"key": "plazos_preclusion", "status": "acreditado"},
                ]
            }
        }
    }
    gate = normalize_defendability_gate(
        expediente,
        {
            "summary_status": "defendable",
            "summary_note": "Texto usable",
            "items": [
                {
                    "claim": "Existe interes juridico",
                    "support_status": "acreditado",
                    "evidence_basis": "Demanda",
                    "expediente_support": "Hechos",
                    "missing_for_court": "",
                }
            ],
        },
    )
    assert gate["summary_status"] == "blocked"
    assert "personalidad:faltante" in gate["blocking_reasons"]


def test_normalize_defendability_gate_marks_review_required_for_inferred_support() -> None:
    expediente = {
        "extra": {
            "pre_merits_checklist": {
                "items": [
                    {"key": "personalidad", "status": "acreditado"},
                    {"key": "personeria", "status": "acreditado"},
                    {"key": "poderes", "status": "acreditado"},
                    {"key": "legitimacion", "status": "acreditado"},
                    {"key": "emplazamiento_notificacion", "status": "acreditado"},
                    {"key": "plazos_preclusion", "status": "acreditado"},
                ]
            }
        }
    }
    gate = normalize_defendability_gate(
        expediente,
        {
            "summary_status": "defendable",
            "summary_note": "Con reservas",
            "items": [
                {
                    "claim": "La afectacion es actual",
                    "support_status": "inferido",
                    "evidence_basis": "Lectura conjunta",
                    "expediente_support": "No textual",
                    "missing_for_court": "Constancia expresa",
                }
            ],
        },
    )
    assert gate["summary_status"] == "review_required"


def test_normalize_defendability_gate_blocks_for_unaccredited_claims() -> None:
    expediente = {"extra": {"pre_merits_checklist": {"items": []}}}
    gate = normalize_defendability_gate(
        expediente,
        {
            "summary_status": "review_required",
            "summary_note": "Falta soporte",
            "items": [
                {
                    "claim": "Se acredito notificacion valida",
                    "support_status": "no_acreditado",
                    "evidence_basis": "",
                    "expediente_support": "",
                    "missing_for_court": "Cedula o razon actuarial",
                }
            ],
        },
    )
    assert gate["summary_status"] == "blocked"
