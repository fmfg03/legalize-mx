#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def infer_source_system(path: Path, fallback: str) -> str:
    if not path.exists():
        return fallback
    source_systems: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        value = str(entry.get("source_system") or "").strip()
        if value:
            source_systems.add(value)
    if not source_systems:
        return fallback
    if len(source_systems) == 1:
        return next(iter(source_systems))
    return "mixed:" + ",".join(sorted(source_systems))


def infer_document_kind(path: Path, fallback: str) -> str:
    if not path.exists():
        return fallback
    document_kinds: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        value = str(entry.get("document_kind") or "").strip()
        if value:
            document_kinds.add(value)
    if not document_kinds:
        return fallback
    if len(document_kinds) == 1:
        return next(iter(document_kinds))
    return "mixed:" + ",".join(sorted(document_kinds))


def main() -> int:
    parser = argparse.ArgumentParser(description="Emite recibo de lote para ingesta jurisprudencial.")
    parser.add_argument("--manifest", default="/root/legalize-mx/indexes/jurisprudence_manifest.jsonl")
    parser.add_argument("--chunks", default="/root/legalize-mx/indexes/jurisprudence_chunks.jsonl")
    parser.add_argument("--receipt-log", default="/root/legalize-mx/raw/scjn/receipts/jurisprudence_ingestion_receipts.jsonl")
    parser.add_argument("--document-kind", default="tesis")
    parser.add_argument("--source-system", default="scjn_sjf")
    args = parser.parse_args()

    manifest = Path(args.manifest)
    chunks = Path(args.chunks)
    receipt_log = Path(args.receipt_log)
    receipt_log.parent.mkdir(parents=True, exist_ok=True)

    receipt = {
        "receipt_type": "jurisprudence_ingestion_receipt",
        "created_at": utc_now_iso(),
        "document_kind": infer_document_kind(manifest, args.document_kind),
        "source_system": infer_source_system(manifest, args.source_system),
        "manifest_path": str(manifest),
        "chunks_path": str(chunks),
        "manifest_rows": count_jsonl(manifest),
        "chunk_rows": count_jsonl(chunks),
        "manifest_sha256": sha256_file(manifest) if manifest.exists() else None,
        "chunks_sha256": sha256_file(chunks) if chunks.exists() else None
    }
    with receipt_log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, ensure_ascii=False) + "\n")
    print(json.dumps({"ok": True, "receipt_log": str(receipt_log), "receipt": receipt}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
