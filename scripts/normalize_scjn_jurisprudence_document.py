#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ID_FIELD_BY_KIND = {
    "precedente": "idEjecutoria",
    "voto": "idVoto",
    "acuerdo": "idAcuerdo",
}
KIND_LABEL_BY_KIND = {
    "precedente": "Precedente",
    "voto": "Voto",
    "acuerdo": "Acuerdo",
}


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_space(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def build_citation_label(raw: dict[str, Any], document_kind: str, registry_id: str) -> str:
    primary = normalize_space(raw.get("tesis") or raw.get("rubro"))
    kind_label = KIND_LABEL_BY_KIND[document_kind]
    if primary:
        return f"{primary} | registro digital {registry_id}"
    return f"{kind_label} con registro digital {registry_id}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Normaliza payloads crudos SCJN de precedente, voto o acuerdo.")
    parser.add_argument("--document-kind", required=True, choices=["precedente", "voto", "acuerdo"])
    parser.add_argument("--input", required=True, help="Payload crudo JSON.")
    parser.add_argument("--output", required=True, help="Documento canónico JSON.")
    parser.add_argument("--parser-version", default="scjn-jurisprudence-normalizer-v1")
    args = parser.parse_args()

    raw = json.loads(Path(args.input).read_text(encoding="utf-8"))
    id_field = ID_FIELD_BY_KIND[args.document_kind]
    registry_id = str(raw.get("registry_id") or raw.get(id_field) or "").strip()
    title = normalize_space(raw.get("rubro") or raw.get("asunto") or raw.get("clasificacion"))
    text = normalize_space(raw.get("texto"))
    if not registry_id or not title or not text:
        raise SystemExit(f"Payload insuficiente para {args.document_kind}: se requiere {id_field}, rubro y texto.")

    document = {
        "doc_type": "jurisprudence",
        "document_kind": args.document_kind,
        "country": "mx",
        "jurisdiction": "federal",
        "court_system": "poder_judicial_federacion",
        "source_system": raw.get("source_system") or "scjn_bicentenario_repository",
        "doc_id": f"mx-sjf-{args.document_kind}-{registry_id}",
        "registry_id": registry_id,
        "canonical_url": raw.get("canonical_url"),
        "source_url": raw.get("source_url") or "",
        "retrieved_at": raw.get("retrieved_at"),
        "title": title,
        "rubro": title,
        "subtitle": normalize_space(raw.get("clasificacion") or raw.get("ponente") or raw.get("promovente")),
        "type": args.document_kind,
        "epoch": raw.get("epoca"),
        "instance": raw.get("instancia"),
        "organ": raw.get("organoJuris"),
        "matter": raw.get("materias") or [],
        "case_type": normalize_space(raw.get("clasificacion")),
        "case_numbers": [],
        "publication_date": None,
        "binding_note_date": raw.get("notaPublica"),
        "mandatory_effect": None,
        "citation_label": build_citation_label(raw, args.document_kind, registry_id),
        "text": text,
        "text_normalized": text.lower(),
        "source_payload_path": raw.get("source_payload_path"),
        "source_pdf_url": raw.get("source_pdf_url"),
        "source_pdf_path": raw.get("source_pdf_path"),
        "source_certificate_sha256": raw.get("huellaDigital") or raw.get("source_certificate_sha256"),
        "parser_version": args.parser_version,
        "last_seen_at": raw.get("retrieved_at"),
        "related_documents": [],
        "interpreted_norms": [],
        "status": raw.get("status") or "vigente_en_fuente",
        "text_checksum_sha256": sha256_text(text),
        "metadata_checksum_sha256": sha256_text(json.dumps({k: v for k, v in raw.items() if k not in {"text", "Texto", "texto"}}, ensure_ascii=False, sort_keys=True)),
    }

    Path(args.output).write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "doc_id": document["doc_id"], "output": args.output}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
