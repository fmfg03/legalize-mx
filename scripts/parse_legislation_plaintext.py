#!/usr/bin/env python3
"""
Convierte texto plano de una norma individual en un documento declarativo
compatible con import_federal_legislation.py.

Entrada:
1. metadata JSON de una norma
2. archivo .txt con el texto extraido y ya mas o menos limpio

Salida:
- JSON con {"documents": [doc]}

Esta version resuelve:
1. deteccion de encabezados juridicos
2. deteccion de articulos
3. agrupacion por section_path
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ARTICLE_RE = re.compile(r"^(ART[IÍ]CULO|Articulo)\s+([0-9A-Za-z./ºo-]+)\.?$", re.IGNORECASE)
HEADING_RE = re.compile(
    r"^(LIBRO|TITULO|T[IÍ]TULO|CAPITULO|CAP[IÍ]TULO|SECCION|SECCI[ÓO]N|DISPOSICIONES TRANSITORIAS|TRANSITORIOS?)\b",
    re.IGNORECASE,
)
MULTISPACE_RE = re.compile(r"\s+")


HEADING_LEVELS = {
    "libro": 0,
    "titulo": 1,
    "título": 1,
    "capitulo": 2,
    "capítulo": 2,
    "seccion": 3,
    "sección": 3,
    "disposiciones transitorias": 4,
    "transitorios": 4,
    "transitorio": 4,
}


def clean_line(line: str) -> str:
    return MULTISPACE_RE.sub(" ", line.strip())


def heading_level(heading: str) -> int:
    lowered = heading.lower()
    for prefix, level in HEADING_LEVELS.items():
        if lowered.startswith(prefix):
            return level
    return 99


def parse_plaintext(text: str) -> list[dict[str, Any]]:
    lines = [clean_line(line) for line in text.splitlines()]
    lines = [line for line in lines if line]

    sections: list[dict[str, Any]] = []
    current_path: list[str] = []
    current_article: dict[str, Any] | None = None

    def flush_article() -> None:
        nonlocal current_article
        if not current_article:
            return
        article_text = "\n\n".join(current_article["paragraphs"]).strip()
        if article_text:
            target_path = list(current_path)
            if sections and sections[-1]["section_path"] == target_path:
                sections[-1]["articles"].append(
                    {"article_number": current_article["article_number"], "text": article_text}
                )
            else:
                sections.append(
                    {
                        "section_path": target_path,
                        "articles": [
                            {
                                "article_number": current_article["article_number"],
                                "text": article_text,
                            }
                        ],
                    }
                )
        current_article = None

    for line in lines:
        article_match = ARTICLE_RE.match(line)
        if article_match:
            flush_article()
            current_article = {"article_number": article_match.group(2), "paragraphs": []}
            continue

        if HEADING_RE.match(line):
            flush_article()
            level = heading_level(line)
            current_path = current_path[:level]
            current_path.append(line)
            continue

        if current_article is not None:
            current_article["paragraphs"].append(line)

    flush_article()
    return sections


def build_document(metadata: dict[str, Any], sections: list[dict[str, Any]]) -> dict[str, Any]:
    category = metadata.get("category") or "law"
    rank = metadata.get("rank") or "ley"
    return {
        "norm_id": metadata["norm_id"],
        "path": metadata["path"],
        "title": metadata["title"],
        "short_title": metadata.get("short_title"),
        "category": category,
        "rank": rank,
        "subject_tags": metadata.get("subject_tags", []),
        "source_system": metadata["source_system"],
        "source_id": metadata.get("source_id"),
        "source_url": metadata["source_url"],
        "official_publication": metadata.get("official_publication", "DOF"),
        "official_publication_url": metadata.get("official_publication_url", metadata["source_url"]),
        "publication_date": metadata.get("publication_date"),
        "effective_date": metadata.get("effective_date"),
        "last_reform_date": metadata.get("last_reform_date"),
        "consolidation_date": metadata.get("consolidation_date") or metadata.get("last_reform_date"),
        "content_scope": metadata.get("content_scope", "parsed_plaintext"),
        "editorial_metadata": metadata.get(
            "editorial_metadata",
            [
                "Fuente principal: Camara de Diputados",
                "Medio oficial: Diario Oficial de la Federacion",
                "Documento generado mediante parser de texto plano.",
            ],
        ),
        "notes": metadata.get(
            "notes",
            [
                "Texto parseado desde una extraccion de texto plano.",
                "Requiere revision de calidad antes de asumirse como ingesta completa.",
            ],
        ),
        "sections": sections,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parsea texto plano de una norma y genera JSON compatible con el importador."
    )
    parser.add_argument("--metadata", required=True, help="Archivo JSON con metadata de una norma")
    parser.add_argument("--text", required=True, help="Archivo TXT con texto plano de la norma")
    parser.add_argument("--output", help="Archivo JSON de salida")
    args = parser.parse_args()

    metadata = json.loads(Path(args.metadata).read_text(encoding="utf-8"))
    text = Path(args.text).read_text(encoding="utf-8")
    sections = parse_plaintext(text)
    document = build_document(metadata, sections)
    payload = {"documents": [document]}
    output = json.dumps(payload, ensure_ascii=True, indent=2) + "\n"

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
