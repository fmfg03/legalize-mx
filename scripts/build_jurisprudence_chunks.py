#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_jsonl(path: Path):
    if not path.exists():
        return []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            yield json.loads(line)


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera chunks jurisprudenciales desde el manifest.")
    parser.add_argument("--manifest", default="/root/legalize-mx/indexes/jurisprudence_manifest.jsonl")
    parser.add_argument("--output", default="/root/legalize-mx/indexes/jurisprudence_chunks.jsonl")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    output = Path(args.output)
    rows = []
    for entry in load_jsonl(manifest_path):
        document = json.loads(Path(entry["document_path"]).read_text(encoding="utf-8"))
        sections = []
        rubro = (document.get("rubro") or "").strip()
        text = (document.get("text") or "").strip()
        if rubro:
            sections.append(("rubro", rubro))
        if text:
            sections.append(("texto", text))
        precedents = document.get("related_documents") or []
        if precedents:
            sections.append(("precedentes", "\n".join(precedents)))

        for section, body in sections:
            rows.append(
                {
                    "chunk_id": f"{document['doc_id']}:{section}",
                    "doc_id": document["doc_id"],
                    "doc_type": "jurisprudence",
                    "document_kind": document["document_kind"],
                    "registry_id": document["registry_id"],
                    "title": document["title"],
                    "type": document.get("type"),
                    "epoch": document.get("epoch"),
                    "instance": document.get("instance"),
                    "organ": document.get("organ"),
                    "matter": document.get("matter") or [],
                    "section": section,
                    "text": body,
                    "publication_date": document.get("publication_date"),
                    "binding_note_date": document.get("binding_note_date"),
                    "source_url": document["source_url"],
                    "citation_label": document.get("citation_label") or document["title"],
                    "binding_weight": None,
                    "mandatory_effect": document.get("mandatory_effect"),
                    "interpreted_norms": document.get("interpreted_norms") or [],
                    "case_numbers": document.get("case_numbers") or [],
                    "retrieval_priority": 1.0 if section == "texto" else 0.8,
                    "checksum_sha256": document.get("text_checksum_sha256")
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
