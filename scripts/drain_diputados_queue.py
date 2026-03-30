#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

import diputados_fetch_utils as fetch_utils


def main() -> int:
    parser = argparse.ArgumentParser(description="Reintenta descargas pendientes de Diputados.")
    parser.add_argument("--limit", type=int, default=None, help="Numero maximo de entradas a reprocesar")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout HTTP por solicitud")
    parser.add_argument("--retries", type=int, default=2, help="Numero de reintentos HTTP por entrada")
    parser.add_argument("--retry-delay", type=float, default=1.5, help="Espera entre reintentos")
    args = parser.parse_args()

    if not fetch_utils.QUEUE_PATH.exists():
        sys.stdout.write(json.dumps({"processed": 0, "remaining": 0, "message": "queue_empty"}, ensure_ascii=True) + "\n")
        return 0

    entries = [
        json.loads(line)
        for line in fetch_utils.QUEUE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    selected = entries[: args.limit] if args.limit else entries
    remaining = entries[len(selected) :] if args.limit else []
    processed = 0
    succeeded = 0
    failed = 0

    for entry in selected:
        processed += 1
        try:
            fetch_utils.fetch_url_with_cache(
                entry["url"],
                kind=entry["kind"],
                timeout=args.timeout,
                retries=args.retries,
                retry_delay=args.retry_delay,
                queue_context={
                    "job_type": entry.get("job_type"),
                    "source_id": entry.get("source_id"),
                },
                allow_stale_cache=False,
            )
            succeeded += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            entry["attempt_count"] = int(entry.get("attempt_count", 0)) + 1
            entry["last_error"] = str(exc)
            remaining.append(entry)

    fetch_utils.write_queue(remaining)
    sys.stdout.write(
        json.dumps(
            {
                "processed": processed,
                "succeeded": succeeded,
                "failed": failed,
                "remaining": len(remaining),
                "queue_path": str(fetch_utils.QUEUE_PATH),
            },
            ensure_ascii=True,
        )
        + "\n"
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
