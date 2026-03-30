#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = REPO_ROOT / "raw" / "diputados" / "logs"
INGESTION_LOG_PATH = LOG_DIR / "ingestion_log.jsonl"


def ensure_log_dir() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def append_ingestion_log(record: dict[str, Any]) -> Path:
    ensure_log_dir()
    enriched = {
        "logged_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        **record,
    }
    with INGESTION_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(enriched, ensure_ascii=True) + "\n")
    return INGESTION_LOG_PATH
