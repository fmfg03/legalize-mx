#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def iter_documents(root: Path):
    for path in sorted(root.rglob("*.json")):
        yield path


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconstruye el manifest jurisprudencial desde documentos canónicos JSON.")
    parser.add_argument("--input-dir", default="/root/legalize-mx/mexico/jurisprudence/sjf")
    parser.add_argument("--output", default="/root/legalize-mx/indexes/jurisprudence_manifest.jsonl")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output = Path(args.output)
    rows = []
    for path in iter_documents(input_dir):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("doc_type") != "jurisprudence":
            continue
        rows.append(
            {
                "doc_id": doc["doc_id"],
                "doc_type": doc["doc_type"],
                "document_kind": doc["document_kind"],
                "registry_id": doc["registry_id"],
                "title": doc["title"],
                "citation_label": doc.get("citation_label"),
                "jurisdiction": doc["jurisdiction"],
                "source_system": doc["source_system"],
                "source_url": doc["source_url"],
                "document_path": str(path),
                "publication_date": doc.get("publication_date"),
                "last_seen_at": doc.get("last_seen_at"),
                "status": doc["status"],
                "text_checksum_sha256": doc.get("text_checksum_sha256"),
                "metadata_checksum_sha256": doc.get("metadata_checksum_sha256")
            }
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({"ok": True, "output": str(output), "rows": len(rows)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
