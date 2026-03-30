#!/usr/bin/env python3
"""
Genera documentos Markdown, manifests y chunks de legislacion federal
desde una fuente declarativa JSON.

Esta primera version esta orientada a pilotos reproducibles. El siguiente
paso es sustituir o complementar el JSON manual con ingestores de Camara de
Diputados/DOF.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = REPO_ROOT / "sources" / "federal_legislation_pilots.json"
LEGISLATION_MANIFEST = REPO_ROOT / "indexes" / "legislation_manifest.jsonl"
LEGISLATION_CHUNKS = REPO_ROOT / "indexes" / "legislation_chunks.jsonl"
FEDERAL_MANIFEST = (
    REPO_ROOT / "mexico" / "legislation" / "manifests" / "federal_manifest.jsonl"
)


def json_dump_line(record: dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=True, separators=(",", ":")) + "\n"


def load_jsonl(path: Path, key_field: str) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    records: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        records[record[key_field]] = record
    return records


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json_dump_line(record) for record in records),
        encoding="utf-8",
    )


def normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def format_yaml_value(value: Any, indent: int = 0) -> list[str]:
    prefix = " " * indent
    if value is None:
        return [f"{prefix}null"]
    if isinstance(value, bool):
        return [f"{prefix}{str(value).lower()}"]
    if isinstance(value, (int, float)):
        return [f"{prefix}{value}"]
    if isinstance(value, list):
        if not value:
            return [f"{prefix}[]"]
        lines: list[str] = []
        for item in value:
            if isinstance(item, (str, int, float)) or item is None:
                item_value = format_yaml_value(item)[0].strip()
                lines.append(f"{prefix}- {item_value}")
            else:
                raise TypeError(f"Unsupported nested YAML list item: {type(item)!r}")
        return lines
    if isinstance(value, str):
        escaped = value.replace('"', '\\"')
        return [f'{prefix}"{escaped}"']
    raise TypeError(f"Unsupported YAML value type: {type(value)!r}")


def render_frontmatter(document: dict[str, Any], checksum: str) -> str:
    ordered_keys = [
        "doc_type",
        "country",
        "jurisdiction",
        "state_code",
        "municipality_code",
        "norm_id",
        "source_system",
        "source_id",
        "source_url",
        "official_publication",
        "official_publication_url",
        "title",
        "short_title",
        "category",
        "rank",
        "subject_tags",
        "publication_date",
        "effective_date",
        "last_reform_date",
        "consolidation_date",
        "status",
        "language",
        "version_type",
        "content_scope",
        "checksum_sha256",
    ]
    lines = ["---"]
    enriched = {
        "doc_type": "legislation",
        "country": "mx",
        "jurisdiction": "federal",
        "state_code": None,
        "municipality_code": None,
        "status": "vigente",
        "language": "es",
        "version_type": "consolidated",
        **document,
        "checksum_sha256": checksum,
    }
    for key in ordered_keys:
        value = enriched.get(key)
        if isinstance(value, list):
            lines.append(f"{key}:")
            lines.extend(format_yaml_value(value, indent=2))
        else:
            lines.append(f"{key}: {format_yaml_value(value)[0].strip()}")
    lines.append("---")
    return "\n".join(lines)


def render_markdown(document: dict[str, Any]) -> str:
    lines = [
        f"# {document['title']}",
        "",
        "## Metadata editorial",
        "",
    ]
    lines.extend(f"- {item}" for item in document["editorial_metadata"])
    lines.extend(["", "## Texto vigente", ""])

    for section in document["sections"]:
        path = section["section_path"]
        if path:
            for idx, section_title in enumerate(path):
                heading = "#" * (3 + idx)
                lines.extend([f"{heading} {section_title}", ""])
        for article in section["articles"]:
            lines.extend([f"#### Articulo {article['article_number']}", "", article["text"], ""])

    lines.extend(["## Notas de fuente", ""])
    lines.extend(f"- {item}" for item in document["notes"])
    lines.append("")
    return "\n".join(lines)


def build_document_file(document: dict[str, Any]) -> tuple[Path, str]:
    markdown_body = render_markdown(document)
    checksum = sha256_text(markdown_body)
    frontmatter = render_frontmatter(document, checksum)
    full_text = f"{frontmatter}\n{markdown_body}"
    output_path = REPO_ROOT / document["path"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(full_text, encoding="utf-8")
    return output_path, checksum


def build_manifest_record(document: dict[str, Any], chunk_count: int) -> dict[str, Any]:
    return {
        "doc_id": document["norm_id"],
        "path": document["path"],
        "doc_type": "legislation",
        "category": document["category"],
        "title": document["title"],
        "short_title": document["short_title"],
        "publication_date": document["publication_date"],
        "last_reform_date": document["last_reform_date"],
        "status": "vigente",
        "source_system": document["source_system"],
        "source_url": document["source_url"],
        "content_scope": document["content_scope"],
        "chunk_count": chunk_count,
    }


def build_chunk_record(document: dict[str, Any], section_path: list[str], article: dict[str, Any]) -> dict[str, Any]:
    article_number = article["article_number"]
    chunk_id = (
        f"{document['norm_id']}:art:{article_number.replace('.', '').replace(' ', '')}:"
        f"v{document['last_reform_date']}"
    )
    return {
        "chunk_id": chunk_id,
        "doc_id": document["norm_id"],
        "doc_type": "legislation",
        "jurisdiction": "federal",
        "category": document["category"],
        "rank": document["rank"],
        "title": document["title"],
        "article_number": article_number,
        "section_path": section_path,
        "heading": f"Articulo {article_number}",
        "text": article["text"],
        "text_normalized": normalize_text(article["text"]),
        "publication_date": document["publication_date"],
        "last_reform_date": document["last_reform_date"],
        "status": "vigente",
        "source_url": document["source_url"],
        "official_publication": document["official_publication"],
        "citation_label": f"{document['title']}, articulo {article_number}",
        "embedding_model": None,
        "checksum_sha256": sha256_text(article["text"]),
    }


def upsert_from_source(source_path: Path, merge_existing: bool = True) -> None:
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    manifest_records = (
        load_jsonl(LEGISLATION_MANIFEST, "doc_id") if merge_existing else {}
    )
    federal_manifest_records = (
        load_jsonl(FEDERAL_MANIFEST, "doc_id") if merge_existing else {}
    )
    chunk_records = load_jsonl(LEGISLATION_CHUNKS, "chunk_id") if merge_existing else {}

    for document in payload["documents"]:
        build_document_file(document)
        doc_chunks: list[dict[str, Any]] = []
        for section in document["sections"]:
            section_path = section["section_path"]
            for article in section["articles"]:
                doc_chunks.append(build_chunk_record(document, section_path, article))
        manifest_record = build_manifest_record(document, len(doc_chunks))
        manifest_records[manifest_record["doc_id"]] = manifest_record
        federal_manifest_records[manifest_record["doc_id"]] = manifest_record

        stale_chunk_ids = [chunk_id for chunk_id, rec in chunk_records.items() if rec["doc_id"] == document["norm_id"]]
        for chunk_id in stale_chunk_ids:
            chunk_records.pop(chunk_id, None)
        for chunk in doc_chunks:
            chunk_records[chunk["chunk_id"]] = chunk

    write_jsonl(
        LEGISLATION_MANIFEST,
        [manifest_records[key] for key in sorted(manifest_records)],
    )
    write_jsonl(
        FEDERAL_MANIFEST,
        [federal_manifest_records[key] for key in sorted(federal_manifest_records)],
    )
    write_jsonl(
        LEGISLATION_CHUNKS,
        [chunk_records[key] for key in sorted(chunk_records)],
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Importa legislacion federal declarativa y genera artifacts."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help="Ruta al JSON fuente con documentos declarativos.",
    )
    parser.add_argument(
        "--replace-all",
        action="store_true",
        help="Reemplaza completamente manifests y chunks en lugar de hacer merge por doc_id.",
    )
    args = parser.parse_args()
    upsert_from_source(args.source.resolve(), merge_existing=not args.replace_all)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
