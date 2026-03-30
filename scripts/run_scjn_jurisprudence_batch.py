#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DOCUMENT_DIR_BY_KIND = {
    "tesis": "tesis",
    "precedente": "precedentes",
    "voto": "votos",
    "acuerdo": "acuerdos",
}
ALL_KINDS = ["tesis", "precedente", "voto", "acuerdo"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_command(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, capture_output=True, text=True)
    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    payload: dict[str, Any]
    try:
        payload = json.loads(stdout) if stdout else {}
    except json.JSONDecodeError:
        payload = {"stdout": stdout}
    payload["_exit_code"] = completed.returncode
    if stderr:
        payload["_stderr"] = stderr
    return payload


def load_state(path: Path, document_kind: str) -> dict[str, Any]:
    if not path.exists():
        return {
            "document_kind": document_kind,
            "next_page": 0,
            "completed": False,
            "runs": 0,
        }
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_documents(document_kind: str, items: list[dict[str, Any]], scripts_dir: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    payload_dir = Path("/root/legalize-mx/raw/scjn/payloads") / document_kind
    output_dir = Path("/root/legalize-mx/mexico/jurisprudence/sjf") / DOCUMENT_DIR_BY_KIND[document_kind]
    output_dir.mkdir(parents=True, exist_ok=True)

    if document_kind == "tesis":
        normalizer = scripts_dir / "normalize_scjn_tesis.py"
    else:
        normalizer = scripts_dir / "normalize_scjn_jurisprudence_document.py"

    for item in items:
        registry_id = str(item["registry_id"])
        input_path = payload_dir / f"{registry_id}.json"
        output_path = output_dir / f"mx-sjf-{document_kind}-{registry_id}.json"
        command = [sys.executable, str(normalizer)]
        if document_kind != "tesis":
            command.extend(["--document-kind", document_kind])
        command.extend(["--input", str(input_path), "--output", str(output_path)])
        result = run_command(command)
        result["registry_id"] = registry_id
        result["input"] = str(input_path)
        result["output_path"] = str(output_path)
        results.append(result)
        if result.get("_exit_code") != 0:
            break
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Orquesta lotes incrementales de jurisprudencia SCJN por pagina.")
    parser.add_argument("--document-kind", choices=ALL_KINDS)
    parser.add_argument("--all-kinds", action="store_true")
    parser.add_argument("--page-size", type=int, default=10)
    parser.add_argument("--pages-per-run", type=int, default=1)
    parser.add_argument("--max-items", type=int, default=None)
    parser.add_argument("--start-page", type=int, default=None, help="Sobrescribe el estado incremental.")
    parser.add_argument("--state-dir", default="/root/legalize-mx/raw/scjn/state")
    parser.add_argument("--skip-rebuild", action="store_true")
    args = parser.parse_args()

    if not args.all_kinds and not args.document_kind:
        raise SystemExit("Se requiere --document-kind o --all-kinds.")

    scripts_dir = Path("/root/legalize-mx/scripts")
    kinds = ALL_KINDS if args.all_kinds else [args.document_kind]
    state_dir = Path(args.state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "started_at": utc_now_iso(),
        "page_size": args.page_size,
        "pages_per_run": args.pages_per_run,
        "kinds": [],
    }

    any_normalized = False
    exit_code = 0

    for document_kind in kinds:
        state_path = state_dir / f"{document_kind}_batch_state.json"
        state = load_state(state_path, document_kind)
        start_page = args.start_page if args.start_page is not None else int(state.get("next_page", 0))

        catalog_path = Path(f"/root/legalize-mx/raw/scjn/catalog/{document_kind}_catalog.json")
        catalog_command = [
            sys.executable,
            str(scripts_dir / "fetch_scjn_jurisprudence_catalog.py"),
            "--document-kind",
            document_kind,
            "--page-size",
            str(args.page_size),
            "--start-page",
            str(start_page),
            "--max-pages",
            str(args.pages_per_run),
            "--output",
            str(catalog_path),
        ]
        if args.max_items is not None:
            catalog_command.extend(["--max-items", str(args.max_items)])
        catalog_result = run_command(catalog_command)

        kind_summary: dict[str, Any] = {
            "document_kind": document_kind,
            "start_page": start_page,
            "catalog": catalog_result,
        }
        if catalog_result.get("_exit_code") != 0:
            exit_code = 1
            kind_summary["status"] = "catalog_failed"
            summary["kinds"].append(kind_summary)
            continue

        catalog = load_json(catalog_path)
        items = catalog.get("items", [])
        kind_summary["items"] = len(items)
        kind_summary["count_total"] = catalog.get("count_total")
        kind_summary["source_index"] = catalog.get("source_index")

        if not items:
            state.update(
                {
                    "completed": True,
                    "last_run_at": utc_now_iso(),
                    "last_status": "no_items",
                    "last_count_total": catalog.get("count_total"),
                }
            )
            save_state(state_path, state)
            kind_summary["status"] = "no_items"
            kind_summary["state_path"] = str(state_path)
            summary["kinds"].append(kind_summary)
            continue

        documents_result = run_command(
            [
                sys.executable,
                str(scripts_dir / "fetch_scjn_jurisprudence_documents.py"),
                "--catalog",
                str(catalog_path),
                "--limit",
                str(len(items)),
            ]
        )
        kind_summary["documents"] = documents_result
        if documents_result.get("_exit_code") != 0:
            exit_code = 1
            kind_summary["status"] = "documents_failed"
            summary["kinds"].append(kind_summary)
            continue

        normalize_results = normalize_documents(document_kind, items, scripts_dir)
        kind_summary["normalized"] = normalize_results
        failed_normalization = next((entry for entry in normalize_results if entry.get("_exit_code") != 0), None)
        if failed_normalization:
            exit_code = 1
            kind_summary["status"] = "normalize_failed"
            summary["kinds"].append(kind_summary)
            continue

        any_normalized = True
        pages_fetched = int(catalog.get("pages_fetched") or 0)
        total_pages = ((int(catalog.get("count_total") or 0) + args.page_size - 1) // args.page_size) if catalog.get("count_total") else 0
        next_page = start_page + pages_fetched
        state.update(
            {
                "next_page": next_page,
                "completed": total_pages > 0 and next_page >= total_pages,
                "runs": int(state.get("runs", 0)) + 1,
                "last_run_at": utc_now_iso(),
                "last_status": "ok",
                "last_count_total": catalog.get("count_total"),
                "last_source_index": catalog.get("source_index"),
                "last_registry_ids": [str(item["registry_id"]) for item in items],
                "last_pages_fetched": pages_fetched,
                "last_page_size": args.page_size,
            }
        )
        save_state(state_path, state)
        kind_summary["status"] = "ok"
        kind_summary["state_path"] = str(state_path)
        kind_summary["next_page"] = next_page
        kind_summary["completed"] = state["completed"]
        summary["kinds"].append(kind_summary)

    if any_normalized and not args.skip_rebuild:
        summary["rebuild_manifest"] = run_command([sys.executable, str(scripts_dir / "build_jurisprudence_manifest.py")])
        summary["rebuild_chunks"] = run_command([sys.executable, str(scripts_dir / "build_jurisprudence_chunks.py")])
        summary["receipt"] = run_command([sys.executable, str(scripts_dir / "emit_jurisprudence_ingestion_receipt.py")])
        if any(section.get("_exit_code") != 0 for section in [summary["rebuild_manifest"], summary["rebuild_chunks"], summary["receipt"]]):
            exit_code = 1

    summary["finished_at"] = utc_now_iso()
    summary["exit_code"] = exit_code
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
