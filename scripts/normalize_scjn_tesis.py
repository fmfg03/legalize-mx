#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Normaliza un payload crudo de tesis SCJN a documento canónico.")
    parser.add_argument("--input", required=True, help="Payload crudo JSON.")
    parser.add_argument("--output", required=True, help="Documento canónico JSON.")
    parser.add_argument("--parser-version", default="scjn-tesis-normalizer-v1")
    args = parser.parse_args()

    raw = json.loads(Path(args.input).read_text(encoding="utf-8"))
    registry_id = str(
        raw.get("registry_id")
        or raw.get("idTesis")
        or raw.get("IUS")
        or raw.get("registro_digital")
        or ""
    ).strip()
    title = normalize_space(raw.get("title") or raw.get("Rubro") or raw.get("rubro") or "")
    text = normalize_space(raw.get("text") or raw.get("Texto") or raw.get("texto") or "")
    if not registry_id or not title or not text:
        raise SystemExit("Payload insuficiente: se requiere registry_id, title/rubro y text/texto.")

    document = {
        "doc_type": "jurisprudence",
        "document_kind": "tesis",
        "country": "mx",
        "jurisdiction": "federal",
        "court_system": "poder_judicial_federacion",
        "source_system": raw.get("source_system") or "scjn_sjf",
        "doc_id": f"mx-sjf-tesis-{registry_id}",
        "registry_id": registry_id,
        "canonical_url": raw.get("canonical_url"),
        "source_url": raw.get("source_url") or raw.get("Ruta") or raw.get("url") or "",
        "retrieved_at": raw.get("retrieved_at"),
        "title": title,
        "rubro": title,
        "subtitle": raw.get("subtitle"),
        "type": raw.get("type") or raw.get("tipoTesis") or raw.get("TipoTesis"),
        "epoch": raw.get("epoch") or raw.get("epoca") or raw.get("Epoca"),
        "instance": raw.get("instance") or raw.get("instancia") or raw.get("Instancia"),
        "organ": raw.get("organ") or raw.get("organoJuris") or raw.get("Tribunal"),
        "matter": raw.get("matter") or raw.get("materias") or raw.get("MateriasTesis") or [],
        "case_type": raw.get("case_type"),
        "case_numbers": raw.get("case_numbers") or [],
        "publication_date": raw.get("publication_date") or raw.get("fechaPublicado") or raw.get("FechaPublicacion"),
        "binding_note_date": raw.get("binding_note_date"),
        "mandatory_effect": raw.get("mandatory_effect"),
        "citation_label": raw.get("citation_label") or (f"{raw.get('tesis')} | registro digital {registry_id}" if raw.get("tesis") else f"Tesis con registro digital {registry_id}"),
        "text": text,
        "text_normalized": text.lower(),
        "source_payload_path": raw.get("source_payload_path"),
        "source_pdf_url": raw.get("source_pdf_url") or raw.get("RutaPdf"),
        "source_pdf_path": raw.get("source_pdf_path"),
        "source_certificate_sha256": raw.get("source_certificate_sha256"),
        "parser_version": args.parser_version,
        "last_seen_at": raw.get("last_seen_at"),
        "related_documents": raw.get("related_documents") or [],
        "interpreted_norms": raw.get("interpreted_norms") or [],
        "status": raw.get("status") or "vigente_en_fuente",
        "text_checksum_sha256": sha256_text(text),
        "metadata_checksum_sha256": sha256_text(json.dumps({k: v for k, v in raw.items() if k not in {"text", "Texto", "texto"}}, ensure_ascii=False, sort_keys=True))
    }

    Path(args.output).write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "doc_id": document["doc_id"], "output": args.output}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
