#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import ssl
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_catalog(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_json(url: str, timeout: int) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "legalize-mx/0.1 (+https://bicentenario.scjn.gob.mx/repositorio-scjn)",
        },
        method="GET",
    )
    context = ssl.create_default_context()
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        return json.loads(response.read().decode("utf-8"))


def load_existing_snapshot_index(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    index: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        index[str(entry["registry_id"])] = entry
    return index


def write_snapshot_index(path: Path, entries: list[dict[str, Any]]) -> None:
    payload = "\n".join(json.dumps(entry, ensure_ascii=False) for entry in entries)
    if payload:
        payload += "\n"
    path.write_text(payload, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Descarga payloads crudos de jurisprudencia desde el catalogo SCJN.")
    parser.add_argument("--catalog", required=True, help="Catalogo JSON generado previamente.")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--output-dir", default="/root/legalize-mx/raw/scjn/payloads")
    parser.add_argument("--snapshot-index", default="/root/legalize-mx/raw/scjn/snapshots")
    args = parser.parse_args()

    catalog = load_catalog(Path(args.catalog))
    document_kind = catalog["document_kind"]
    source_index = catalog["source_index"]

    output_dir = Path(args.output_dir) / document_kind
    output_dir.mkdir(parents=True, exist_ok=True)

    snapshot_dir = Path(args.snapshot_index)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_index_path = snapshot_dir / f"{document_kind}_snapshots.jsonl"
    snapshot_index = load_existing_snapshot_index(snapshot_index_path)

    selected_items = catalog.get("items", [])[args.offset : args.offset + args.limit]
    written_files: list[str] = []
    written_snapshot_entries: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for item in selected_items:
        registry_id = str(item["registry_id"])
        source_url = item.get("source_url") or catalog["api_contract"]["detail"].replace("{registry_id}", registry_id)
        try:
            payload = fetch_json(source_url, args.timeout)
        except Exception as exc:  # noqa: BLE001
            failures.append({"registry_id": registry_id, "source_url": source_url, "error": str(exc)})
            continue

        fetched_at = utc_now_iso()
        payload_path = output_dir / f"{registry_id}.json"
        normalized_payload = {
            **payload,
            "source_system": catalog["source_system"],
            "document_kind": document_kind,
            "registry_id": registry_id,
            "source_url": source_url,
            "retrieved_at": fetched_at,
            "source_payload_path": str(payload_path.relative_to(Path("/root/legalize-mx"))),
        }
        payload_text = json.dumps(normalized_payload, ensure_ascii=False, indent=2) + "\n"
        payload_path.write_text(payload_text, encoding="utf-8")
        written_files.append(str(payload_path))

        snapshot_entry = {
            "source_system": catalog["source_system"],
            "document_kind": document_kind,
            "registry_id": registry_id,
            "fetched_at": fetched_at,
            "source_url": source_url,
            "payload_sha256": sha256_text(payload_text),
            "payload_relpath": str(payload_path.relative_to(Path("/root/legalize-mx"))),
            "pdf_url": None,
            "pdf_relpath": None,
            "certificate_sha256": payload.get("huellaDigital"),
            "etag": None,
            "last_modified": None,
        }
        snapshot_index[registry_id] = snapshot_entry
        written_snapshot_entries.append(snapshot_entry)

    ordered_entries = [snapshot_index[key] for key in sorted(snapshot_index.keys())]
    write_snapshot_index(snapshot_index_path, ordered_entries)

    receipt = {
        "generated_at": utc_now_iso(),
        "status": "ok" if not failures else "partial",
        "catalog": args.catalog,
        "document_kind": document_kind,
        "source_index": source_index,
        "planned_downloads": len(selected_items),
        "written_payloads": len(written_files),
        "written_files": written_files,
        "written_snapshots": len(written_snapshot_entries),
        "snapshot_index": str(snapshot_index_path),
        "failures": failures,
    }
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
