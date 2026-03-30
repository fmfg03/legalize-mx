#!/usr/bin/env python3
"""
Ingesta end-to-end de una norma individual de Diputados.

Pipeline:
1. metadata por source_id
2. PDF -> texto plano
3. parser de texto plano -> JSON declarativo
4. importador -> Markdown + manifests + chunks

Pensado para ejecutarse con la venv del proyecto:
  /root/legalize-mx/.venv/bin/python scripts/ingest_diputados_norm.py ...
"""

from __future__ import annotations

import argparse
import json
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

import extract_diputados_pdf_text as extractor
import fetch_diputados_metadata as metadata
import ingestion_log_utils as log_utils
import import_federal_legislation as importer
import parse_legislation_plaintext as parser_mod


REPO_ROOT = Path(__file__).resolve().parents[1]


def iso_utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def default_path_for(category: str | None, source_id: str) -> str:
    if category == "constitution":
        return f"mexico/legislation/federal/constitution/{source_id}.md"
    if category == "code":
        return f"mexico/legislation/federal/codes/{source_id}.md"
    if category == "regulation":
        return f"mexico/legislation/federal/regulations/{source_id}.md"
    return f"mexico/legislation/federal/laws/{source_id}.md"


def default_rank_for(category: str | None) -> str:
    if category == "constitution":
        return "constitucion"
    if category == "code":
        return "codigo"
    if category == "regulation":
        return "reglamento"
    return "ley"


def build_import_metadata(meta: dict[str, Any], source_id: str, path_override: str | None) -> dict[str, Any]:
    title = meta.get("title") or source_id.upper()
    category = meta.get("category") or "law"
    path = path_override or default_path_for(category, source_id)
    publication_dates = meta.get("publication_dates") or []
    publication_date = publication_dates[0] if publication_dates else None
    last_reform = meta.get("last_reform_date")
    return {
        "norm_id": f"mx-federal-{source_id}",
        "path": path,
        "title": title,
        "short_title": meta.get("short_title") or source_id.upper(),
        "category": category,
        "rank": meta.get("rank") or default_rank_for(category),
        "subject_tags": [],
        "source_system": "diputados",
        "source_id": source_id,
        "source_url": meta.get("source_url") or f"https://www.diputados.gob.mx/LeyesBiblio/ref/{source_id}.htm",
        "official_publication": "DOF",
        "official_publication_url": meta.get("source_url") or f"https://www.diputados.gob.mx/LeyesBiblio/ref/{source_id}.htm",
        "publication_date": publication_date,
        "effective_date": publication_date,
        "last_reform_date": last_reform,
        "consolidation_date": last_reform,
        "content_scope": "parsed_plaintext",
        "editorial_metadata": [
            "Fuente principal: Camara de Diputados",
            "Medio oficial: Diario Oficial de la Federacion",
            f"Documento ingerido automaticamente desde source_id {source_id}.",
        ],
        "notes": [
            "Texto parseado desde extraccion PDF->texto plano.",
            "Requiere validacion de calidad antes de considerarse cobertura completa.",
        ],
    }


def fetch_single_metadata(source_id: str, timeout: int, retries: int, retry_delay: float) -> dict[str, Any]:
    records, errors = metadata.fetch_many([source_id], timeout, retries, retry_delay)
    if errors:
        raise RuntimeError(json.dumps(errors, ensure_ascii=True))
    if not records:
        raise RuntimeError(f"No se obtuvo metadata para {source_id}")
    return records[0]


def extract_text(
    source_id: str,
    text_file: str | None,
    timeout: int,
    retries: int,
    retry_delay: float,
) -> Path:
    if text_file:
        return Path(text_file)

    pdf_url = extractor.PDF_URL_TEMPLATE.format(source_id_upper=source_id.upper())
    pdf_bytes = extractor.fetch_bytes(pdf_url, timeout, retries, retry_delay)
    extractor.PDF_DIR.mkdir(parents=True, exist_ok=True)
    extractor.TEXT_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = extractor.PDF_DIR / f"{source_id}.pdf"
    pdf_path.write_bytes(pdf_bytes)
    text, _page_count = extractor.extract_pdf_text(pdf_path)
    text_path = extractor.TEXT_DIR / f"{source_id}.txt"
    text_path.write_text(text, encoding="utf-8")
    return text_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingesta end-to-end de una norma individual.")
    parser.add_argument("--source-id", required=True, help="Identificador de Diputados, por ejemplo ccf o cpf")
    parser.add_argument("--metadata-file", help="JSON local de metadata. Si se indica, omite el fetch remoto.")
    parser.add_argument("--text-file", help="TXT local. Si se indica, omite la descarga/extraccion PDF")
    parser.add_argument("--path", help="Ruta Markdown de destino dentro del repo")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout HTTP por solicitud")
    parser.add_argument("--retries", type=int, default=2, help="Numero de reintentos HTTP")
    parser.add_argument("--retry-delay", type=float, default=1.5, help="Espera entre reintentos")
    parser.add_argument("--keep-temp-json", action="store_true", help="Conserva el JSON intermedio en /tmp")
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Devuelve estado parcial en JSON en lugar de abortar con error opaco.",
    )
    args = parser.parse_args()

    source_id = args.source_id.lower()
    started_at = time.time()
    started_at_iso = iso_utc_now()
    result: dict[str, Any] = {
        "run_id": str(uuid.uuid4()),
        "source_id": source_id,
        "status": "started",
        "started_at": started_at_iso,
        "metadata": {"ok": False, "source": None},
        "text": {"ok": False, "path": None},
        "parse": {"ok": False, "section_count": 0, "article_count": 0},
        "import": {"ok": False, "path": None, "temp_json": None},
        "errors": [],
    }
    exit_code = 0

    meta: dict[str, Any] | None = None
    try:
        if args.metadata_file:
            meta = json.loads(Path(args.metadata_file).read_text(encoding="utf-8"))
            result["metadata"] = {"ok": True, "source": "local_file"}
        else:
            meta = fetch_single_metadata(source_id, args.timeout, args.retries, args.retry_delay)
            result["metadata"] = {"ok": True, "source": "remote_or_cache"}
    except Exception as exc:  # noqa: BLE001
        result["errors"].append({"stage": "metadata", "error": str(exc)})
        if not args.allow_partial:
            result["status"] = "error"
            exit_code = 1
            meta = None

    if meta is None:
        if result["status"] != "error":
            result["status"] = "partial"
        exit_code = 1
        result["duration_ms"] = int((time.time() - started_at) * 1000)
        result["finished_at"] = iso_utc_now()
        result["exit_code"] = exit_code
        log_path = log_utils.append_ingestion_log(result)
        result["log_path"] = str(log_path)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return exit_code

    import_metadata = build_import_metadata(meta, source_id, args.path)
    text_path: Path | None = None
    try:
        text_path = extract_text(source_id, args.text_file, args.timeout, args.retries, args.retry_delay)
        result["text"] = {"ok": True, "path": str(text_path)}
    except Exception as exc:  # noqa: BLE001
        result["errors"].append({"stage": "text", "error": str(exc)})
        if not args.allow_partial:
            result["status"] = "error"
            exit_code = 1

    if text_path is None:
        if result["status"] != "error":
            result["status"] = "partial"
        exit_code = 1
        result["duration_ms"] = int((time.time() - started_at) * 1000)
        result["finished_at"] = iso_utc_now()
        result["exit_code"] = exit_code
        log_path = log_utils.append_ingestion_log(result)
        result["log_path"] = str(log_path)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return exit_code

    sections = parser_mod.parse_plaintext(text_path.read_text(encoding="utf-8"))
    article_count = sum(len(section["articles"]) for section in sections)
    result["parse"] = {"ok": True, "section_count": len(sections), "article_count": article_count}
    document = parser_mod.build_document(import_metadata, sections)

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tmp:
        json.dump({"documents": [document]}, tmp, ensure_ascii=True, indent=2)
        tmp.write("\n")
        temp_path = Path(tmp.name)

    result["import"]["temp_json"] = str(temp_path)

    try:
        importer.upsert_from_source(temp_path, merge_existing=True)
        result["import"] = {
            "ok": True,
            "path": import_metadata["path"],
            "temp_json": str(temp_path),
        }
    except Exception as exc:  # noqa: BLE001
        result["errors"].append({"stage": "import", "error": str(exc)})
        if not args.allow_partial:
            result["status"] = "error"
            exit_code = 1

    if not args.keep_temp_json:
        temp_path.unlink(missing_ok=True)
        result["import"]["temp_json"] = None

    if result["status"] != "error":
        result["status"] = "ok" if not result["errors"] else "partial"
    if result["errors"]:
        exit_code = 1
    result["duration_ms"] = int((time.time() - started_at) * 1000)
    result["finished_at"] = iso_utc_now()
    result["exit_code"] = exit_code
    log_path = log_utils.append_ingestion_log(result)
    result["log_path"] = str(log_path)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
