#!/usr/bin/env python3
"""
Ejecuta un ciclo de ingesta por lotes y persiste un snapshot JSON del resultado.
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
BATCH_SCRIPT = REPO_ROOT / "scripts" / "run_ingestion_batch.py"
DEFAULT_BATCH_RUNS_DIR = REPO_ROOT / "raw" / "diputados" / "logs" / "batch_runs"
DEFAULT_LATEST_PATH = DEFAULT_BATCH_RUNS_DIR / "latest.json"


def iso_utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def build_batch_command(args: argparse.Namespace) -> list[str]:
    command = [sys.executable, str(BATCH_SCRIPT)]

    if args.source_ids:
        command.extend(["--source-ids", *args.source_ids])
    if args.source_ids_file:
        command.extend(["--source-ids-file", args.source_ids_file])
    if args.inventory_file:
        command.extend(["--inventory-file", args.inventory_file])
    if args.limit is not None:
        command.extend(["--limit", str(args.limit)])
    if args.resume_from_log:
        command.append("--resume-from-log")
    if args.retry_partials:
        command.append("--retry-partials")
    if args.refresh:
        command.append("--refresh")
    if args.allow_partial:
        command.append("--allow-partial")
    if args.drain_queue:
        command.append("--drain-queue")
    if args.queue_limit is not None:
        command.extend(["--queue-limit", str(args.queue_limit)])
    if args.sleep_between > 0:
        command.extend(["--sleep-between", str(args.sleep_between)])
    if args.max_errors is not None:
        command.extend(["--max-errors", str(args.max_errors)])
    command.extend(["--timeout", str(args.timeout)])
    command.extend(["--retries", str(args.retries)])
    command.extend(["--retry-delay", str(args.retry_delay)])
    if args.metadata_dir:
        command.extend(["--metadata-dir", args.metadata_dir])
    if args.text_dir:
        command.extend(["--text-dir", args.text_dir])

    return command


def write_snapshot(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Ejecuta un ciclo de ingesta y guarda snapshot del lote.")
    parser.add_argument("--source-ids", nargs="*", help="Lista explicita de source_id")
    parser.add_argument("--source-ids-file", help="Archivo de texto con un source_id por linea")
    parser.add_argument("--inventory-file", help="JSON de inventario generado por bootstrap_federal_inventory.py")
    parser.add_argument("--limit", type=int, default=None, help="Numero maximo de normas a procesar")
    parser.add_argument("--resume-from-log", action="store_true", help="Salta exitos previos segun el log")
    parser.add_argument("--retry-partials", action="store_true", help="Reintenta normas en estado partial")
    parser.add_argument("--refresh", action="store_true", help="Ignora el log y fuerza reproceso")
    parser.add_argument("--allow-partial", action="store_true", help="Permite estados partial en el wrapper unitario")
    parser.add_argument("--drain-queue", action="store_true", help="Drena la cola al final del lote")
    parser.add_argument("--queue-limit", type=int, default=None, help="Numero maximo de entradas de cola a drenar")
    parser.add_argument("--sleep-between", type=float, default=0.0, help="Espera entre normas")
    parser.add_argument("--max-errors", type=int, default=None, help="Corta el lote al llegar a este numero de errores")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout HTTP por solicitud")
    parser.add_argument("--retries", type=int, default=2, help="Numero de reintentos HTTP")
    parser.add_argument("--retry-delay", type=float, default=1.5, help="Espera entre reintentos HTTP")
    parser.add_argument("--metadata-dir", help="Directorio opcional con fixtures locales de metadata")
    parser.add_argument("--text-dir", help="Directorio opcional con fixtures locales de texto")
    parser.add_argument(
        "--batch-runs-dir",
        default=str(DEFAULT_BATCH_RUNS_DIR),
        help="Directorio donde guardar snapshots JSON del lote",
    )
    parser.add_argument(
        "--latest-path",
        default=str(DEFAULT_LATEST_PATH),
        help="Ruta del ultimo snapshot consolidado",
    )
    args = parser.parse_args()

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
