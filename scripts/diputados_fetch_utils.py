#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = REPO_ROOT / "raw" / "diputados"
CACHE_ROOT = RAW_ROOT / "cache"
QUEUE_ROOT = RAW_ROOT / "queue"
QUEUE_PATH = QUEUE_ROOT / "pending_downloads.jsonl"
USER_AGENT = "legalize-mx/0.1 (+https://legalize-mx.local)"


def ensure_dirs() -> None:
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    QUEUE_ROOT.mkdir(parents=True, exist_ok=True)


def sha1_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def cache_paths(url: str, kind: str) -> tuple[Path, Path]:
    ensure_dirs()
    key = sha1_text(f"{kind}:{url}")
    ext = "bin" if kind == "binary" else "txt"
    payload = CACHE_ROOT / f"{key}.{ext}"
    meta = CACHE_ROOT / f"{key}.json"
    return payload, meta


def load_cached(url: str, kind: str) -> tuple[bytes | None, dict[str, Any] | None]:
    payload_path, meta_path = cache_paths(url, kind)
    if not payload_path.exists() or not meta_path.exists():
        return None, None
    payload = payload_path.read_bytes()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return payload, meta


def store_cached(url: str, kind: str, payload: bytes, response_meta: dict[str, Any]) -> dict[str, Any]:
    payload_path, meta_path = cache_paths(url, kind)
    payload_path.write_bytes(payload)
    meta = {
        "url": url,
        "kind": kind,
        "cached_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "size_bytes": len(payload),
        **response_meta,
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return meta


def queue_key(entry: dict[str, Any]) -> str:
    parts = [
        str(entry.get("url", "") or ""),
        str(entry.get("kind", "") or ""),
        str(entry.get("job_type", "") or ""),
        str(entry.get("source_id", "") or ""),
    ]
    return sha1_text("|".join(parts))


def append_queue(entry: dict[str, Any]) -> None:
    ensure_dirs()
    existing: dict[str, dict[str, Any]] = {}
    if QUEUE_PATH.exists():
        for line in QUEUE_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                existing[row["queue_key"]] = row

    enriched = {
        "queue_key": queue_key(entry),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "attempt_count": 0,
        **entry,
    }
    if enriched["queue_key"] in existing:
        previous = existing[enriched["queue_key"]]
        enriched["created_at"] = previous.get("created_at", enriched["created_at"])
        enriched["attempt_count"] = previous.get("attempt_count", 0)
    existing[enriched["queue_key"]] = enriched

    QUEUE_PATH.write_text(
        "".join(json.dumps(existing[key], ensure_ascii=True) + "\n" for key in sorted(existing)),
        encoding="utf-8",
    )


def write_queue(entries: list[dict[str, Any]]) -> None:
    ensure_dirs()
    QUEUE_PATH.write_text(
        "".join(json.dumps(entry, ensure_ascii=True) + "\n" for entry in entries),
        encoding="utf-8",
    )


def fetch_url_with_cache(
    url: str,
    *,
    kind: str,
    timeout: int,
    retries: int,
    retry_delay: float,
    queue_context: dict[str, Any] | None = None,
    allow_stale_cache: bool = True,
) -> tuple[bytes, dict[str, Any]]:
    ensure_dirs()
    last_error: Exception | None = None
    cached_payload, cached_meta = load_cached(url, kind)

    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                payload = response.read()
                response_meta = {
                    "status": getattr(response, "status", None),
                    "content_type": response.headers.get_content_type(),
                    "content_length": response.headers.get("Content-Length"),
                }
                cache_meta = store_cached(url, kind, payload, response_meta)
                return payload, {"cache_hit": False, "stale_cache": False, **cache_meta}
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt >= retries:
                break
            time.sleep(retry_delay)

    if cached_payload is not None and allow_stale_cache:
        stale_meta = {"cache_hit": True, "stale_cache": True, **(cached_meta or {})}
        return cached_payload, stale_meta

    append_queue(
        {
            "url": url,
            "kind": kind,
            "job_type": (queue_context or {}).get("job_type"),
            "source_id": (queue_context or {}).get("source_id"),
            "timeout": timeout,
            "retries": retries,
            "retry_delay": retry_delay,
            "last_error": str(last_error) if last_error else "unknown_error",
        }
    )
    assert last_error is not None
    raise last_error
