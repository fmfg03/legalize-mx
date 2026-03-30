#!/usr/bin/env python3
"""
Ejecuta un ciclo de ingesta jurisprudencial SCJN y persiste un snapshot JSON del resultado.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
BATCH_SCRIPT = REPO_ROOT / "scripts" / "run_scjn_jurisprudence_batch.py"
DEFAULT_BATCH_RUNS_DIR = REPO_ROOT / "raw" / "scjn" / "logs" / "batch_runs"
DEFAULT_LATEST_PATH = DEFAULT_BATCH_RUNS_DIR / "latest.json"


def iso_utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def build_batch_command(args: argparse.Namespace) -> list[str]:
    command = [sys.executable, str(BATCH_SCRIPT)]
    if args.all_kinds:
        command.append("--all-kinds")
    elif args.document_kind:
        command.extend(["--document-kind", args.document_kind])
    if args.page_size is not None:
        command.extend(["--page-size", str(args.page_size)])
    if args.pages_per_run is not None:
        command.extend(["--pages-per-run", str(args.pages_per_run)])
    if args.max_items is not None:
        command.extend(["--max-items", str(args.max_items)])
    if args.start_page is not None:
        command.extend(["--start-page", str(args.start_page)])
    if args.state_dir:
        command.extend(["--state-dir", args.state_dir])
    if args.skip_rebuild:
        command.append("--skip-rebuild")
    return command


def write_snapshot(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Ejecuta un ciclo jurisprudencial SCJN y guarda snapshot del lote.")
    parser.add_argument("--document-kind", choices=["tesis", "precedente", "voto", "acuerdo"])
    parser.add_argument("--all-kinds", action="store_true")
    parser.add_argument("--page-size", type=int, default=10)
    parser.add_argument("--pages-per-run", type=int, default=1)
    parser.add_argument("--max-items", type=int, default=None)
    parser.add_argument("--start-page", type=int, default=None)
    parser.add_argument("--state-dir", default="/root/legalize-mx/raw/scjn/state")
    parser.add_argument("--skip-rebuild", action="store_true")
    parser.add_argument("--batch-runs-dir", default=str(DEFAULT_BATCH_RUNS_DIR))
    parser.add_argument("--latest-path", default=str(DEFAULT_LATEST_PATH))
    args = parser.parse_args()

    if not args.all_kinds and not args.document_kind:
        args.all_kinds = True

    started_at = time.time()
    started_at_iso = iso_utc_now()
    cycle_id = str(uuid.uuid4())
    command = build_batch_command(args)
    completed = subprocess.run(command, capture_output=True, text=True, check=False)

    batch_summary: dict[str, Any] | None = None
    stdout = completed.stdout.strip()
    if stdout:
        try:
            batch_summary = json.loads(stdout)
        except json.JSONDecodeError:
            batch_summary = None

    snapshot = {
        "cycle_id": cycle_id,
        "started_at": started_at_iso,
        "finished_at": iso_utc_now(),
        "duration_ms": int((time.time() - started_at) * 1000),
        "batch_exit_code": completed.returncode,
        "command": command,
        "batch_summary": batch_summary,
    }
    if completed.stderr.strip():
        snapshot["stderr"] = completed.stderr.strip()
    if batch_summary is None:
        snapshot["stdout"] = stdout

    runs_dir = Path(args.batch_runs_dir)
    timestamp_slug = started_at_iso.replace(":", "").replace("-", "").replace("T", "-").replace("Z", "Z")
    snapshot_path = runs_dir / f"{timestamp_slug}-{cycle_id}.json"
    latest_path = Path(args.latest_path)

    write_snapshot(snapshot_path, snapshot)
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(snapshot_path, latest_path)

    output = {
        "cycle_id": cycle_id,
        "snapshot_path": str(snapshot_path),
        "latest_path": str(latest_path),
        "batch_exit_code": completed.returncode,
        "batch_summary": batch_summary,
    }
    print(json.dumps(output, ensure_ascii=True, indent=2))
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
