#!/usr/bin/env python3
"""
Scheduler sencillo para ingesta por lotes de normas de Diputados.

Responsabilidades:
1. resolver la lista de source_id a procesar
2. consultar el log de ingesta para saltar exitos previos si se pide resume
3. ejecutar la ingesta unitaria de forma secuencial
4. cortar el lote si se supera un umbral de errores
5. drenar opcionalmente la cola de descargas pendientes
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import drain_diputados_queue as drain_queue
import ingestion_log_utils as log_utils


REPO_ROOT = Path(__file__).resolve().parents[1]
INGEST_SCRIPT = REPO_ROOT / "scripts" / "ingest_diputados_norm.py"


def load_source_ids_from_inventory(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    inventory = payload.get("inventory") or []
    source_ids: list[str] = []
    for entry in inventory:
        source_id = (entry.get("source_id") or "").strip().lower()
        if source_id:
            source_ids.append(source_id)
    return source_ids


def load_source_ids_from_file(path: Path) -> list[str]:
    source_ids: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip().lower()
        if not line or line.startswith("#"):
            continue
        source_ids.append(line)
    return source_ids


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def load_latest_log_by_source() -> dict[str, dict[str, Any]]:
    if not log_utils.INGESTION_LOG_PATH.exists():
        return {}

    latest: dict[str, dict[str, Any]] = {}
    for line in log_utils.INGESTION_LOG_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        source_id = row.get("source_id")
        if source_id:
            latest[str(source_id).lower()] = row
    return latest


def should_skip_for_resume(
    source_id: str,
    latest_log: dict[str, Any] | None,
    *,
    resume_from_log: bool,
    retry_partials: bool,
    refresh: bool,
) -> tuple[bool, str | None]:
    if refresh or not resume_from_log or not latest_log:
        return False, None

    status = latest_log.get("status")
    if status == "ok":
        return True, "latest_status_ok"
    if status == "partial" and not retry_partials:
        return True, "latest_status_partial"
    return False, None


def resolve_local_fixture(source_id: str, directory: Path | None, suffixes: list[str]) -> Path | None:
    if directory is None:
        return None
    for suffix in suffixes:
        candidate = directory / f"{source_id}{suffix}"
        if candidate.exists():
            return candidate
    return None


def build_ingest_command(
    source_id: str,
    *,
    timeout: int,
    retries: int,
    retry_delay: float,
    allow_partial: bool,
    metadata_path: Path | None,
    text_path: Path | None,
) -> list[str]:
    command = [sys.executable, str(INGEST_SCRIPT), "--source-id", source_id]
    command.extend(["--timeout", str(timeout), "--retries", str(retries), "--retry-delay", str(retry_delay)])
    if allow_partial:
        command.append("--allow-partial")
    if metadata_path:
        command.extend(["--metadata-file", str(metadata_path)])
    if text_path:
        command.extend(["--text-file", str(text_path)])
    return command


def run_single_ingestion(command: list[str]) -> tuple[int, dict[str, Any] | None, str]:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    stdout = completed.stdout.strip()
    payload: dict[str, Any] | None = None
    if stdout:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = None
    return completed.returncode, payload, stdout


def drain_queue_once(limit: int | None, timeout: int, retries: int, retry_delay: float) -> dict[str, Any]:
    original_argv = sys.argv[:]
    argv = [
        "drain_diputados_queue.py",
        "--timeout",
        str(timeout),
        "--retries",
        str(retries),
        "--retry-delay",
        str(retry_delay),
    ]
    if limit is not None:
        argv.extend(["--limit", str(limit)])
    try:
        sys.argv = argv
        try:
            exit_code = drain_queue.main()
        except SystemExit as exc:
            exit_code = int(exc.code or 0)
    finally:
        sys.argv = original_argv

    remaining = None
    if drain_queue.fetch_utils.QUEUE_PATH.exists():
        remaining = sum(
            1
            for line in drain_queue.fetch_utils.QUEUE_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    return {
        "ok": exit_code == 0,
        "exit_code": exit_code,
        "queue_path": str(drain_queue.fetch_utils.QUEUE_PATH),
        "remaining": remaining,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Ejecuta ingestas unitarias en lote.")
    parser.add_argument("--source-ids", nargs="*", help="Lista explicita de source_id")
    parser.add_argument("--source-ids-file", help="Archivo de texto con un source_id por linea")
    parser.add_argument("--inventory-file", help="JSON de inventario generado por bootstrap_federal_inventory.py")
    parser.add_argument("--limit", type=int, default=None, help="Numero maximo de normas a procesar")
    parser.add_argument("--resume-from-log", action="store_true", help="Salta exitos previos segun el log")
    parser.add_argument(
        "--retry-partials",
        action="store_true",
        help="Si se usa con --resume-from-log, vuelve a intentar normas en estado partial",
    )
    parser.add_argument("--refresh", action="store_true", help="Ignora el log y fuerza reproceso")
    parser.add_argument("--allow-partial", action="store_true", help="Propaga --allow-partial al wrapper unitario")
    parser.add_argument("--drain-queue", action="store_true", help="Drena la cola de descargas al final del lote")
    parser.add_argument("--queue-limit", type=int, default=None, help="Numero maximo de entradas a drenar")
    parser.add_argument("--sleep-between", type=float, default=0.0, help="Espera entre normas")
    parser.add_argument("--max-errors", type=int, default=None, help="Corta el lote al llegar a este numero de errores")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout HTTP por solicitud")
    parser.add_argument("--retries", type=int, default=2, help="Numero de reintentos HTTP")
    parser.add_argument("--retry-delay", type=float, default=1.5, help="Espera entre reintentos HTTP")
    parser.add_argument(
        "--metadata-dir",
        help="Directorio opcional con fixtures locales de metadata nombrados como <source_id>-meta.json",
    )
    parser.add_argument(
        "--text-dir",
        help="Directorio opcional con fixtures locales de texto nombrados como <source_id>.txt o <source_id>-offline.txt",
    )
    args = parser.parse_args()

    source_ids: list[str] = []
    if args.source_ids:
        source_ids.extend(str(value).lower() for value in args.source_ids if value)
    if args.source_ids_file:
        source_ids.extend(load_source_ids_from_file(Path(args.source_ids_file)))
    if args.inventory_file:
        source_ids.extend(load_source_ids_from_inventory(Path(args.inventory_file)))

    source_ids = dedupe_preserve_order(source_ids)
    if args.limit:
        source_ids = source_ids[: args.limit]

    if not source_ids:
        parser.error("Se requiere al menos una fuente: --source-ids, --source-ids-file o --inventory-file")

    latest_logs = load_latest_log_by_source()
    metadata_dir = Path(args.metadata_dir) if args.metadata_dir else None
    text_dir = Path(args.text_dir) if args.text_dir else None

    summary: dict[str, Any] = {
        "selected_count": len(source_ids),
        "processed": 0,
        "ok": 0,
        "partial": 0,
        "error": 0,
        "skipped": [],
        "results": [],
        "stopped_early": False,
        "queue_drain": None,
    }

    error_count = 0

    for source_id in source_ids:
        skip, reason = should_skip_for_resume(
            source_id,
            latest_logs.get(source_id),
            resume_from_log=args.resume_from_log,
            retry_partials=args.retry_partials,
            refresh=args.refresh,
        )
        if skip:
            summary["skipped"].append({"source_id": source_id, "reason": reason})
            continue

        metadata_path = resolve_local_fixture(source_id, metadata_dir, ["-meta.json"])
        text_path = resolve_local_fixture(source_id, text_dir, [".txt", "-offline.txt"])
        command = build_ingest_command(
            source_id,
            timeout=args.timeout,
            retries=args.retries,
            retry_delay=args.retry_delay,
            allow_partial=args.allow_partial,
            metadata_path=metadata_path,
            text_path=text_path,
        )
        returncode, payload, stdout = run_single_ingestion(command)
        summary["processed"] += 1

        if payload is None:
            payload = {
                "source_id": source_id,
                "status": "error",
                "errors": [{"stage": "batch_wrapper", "error": "non_json_stdout"}],
                "raw_stdout": stdout,
                "exit_code": returncode,
            }

        status = payload.get("status") or "error"
        if status == "ok":
            summary["ok"] += 1
        elif status == "partial":
            summary["partial"] += 1
            error_count += 1
        else:
            summary["error"] += 1
            error_count += 1

        summary["results"].append(payload)

        if args.max_errors is not None and error_count >= args.max_errors:
            summary["stopped_early"] = True
            break
        if args.sleep_between > 0:
            time.sleep(args.sleep_between)

    if args.drain_queue:
        summary["queue_drain"] = drain_queue_once(
            args.queue_limit,
            args.timeout,
            args.retries,
            args.retry_delay,
        )

    print(json.dumps(summary, ensure_ascii=True, indent=2))
    return 0 if summary["error"] == 0 and summary["partial"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
