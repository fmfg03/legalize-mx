from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from backend.app.config import settings


SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(value: str) -> str:
    cleaned = SAFE_FILENAME_RE.sub("_", value).strip("._")
    return cleaned or "document.bin"


def resolve_storage_path(storage_key: str) -> Path:
    root = settings.storage_root.resolve()
    target = (settings.storage_root / storage_key).resolve()
    if target != root and root not in target.parents:
        raise ValueError("storage_key resolves outside the configured storage root")
    return target


@dataclass
class StoredFile:
    storage_key: str
    size_bytes: int
    sha256: str


def store_document_payload(
    *,
    expediente_id: str,
    document_id: str,
    version_number: int,
    file_name: str,
    payload: bytes,
) -> StoredFile:
    storage_root = settings.storage_root
    safe_name = sanitize_filename(file_name)
    relative = Path(expediente_id) / str(document_id) / f"v{version_number:04d}__{safe_name}"
    target = storage_root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return StoredFile(
        storage_key=str(relative),
        size_bytes=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
    )


def store_document_bytes(
    *,
    expediente_id: str,
    document_id: str,
    version_number: int,
    file_name: str,
    content_base64: str,
) -> StoredFile:
    payload = base64.b64decode(content_base64.encode("utf-8"))
    return store_document_payload(
        expediente_id=expediente_id,
        document_id=document_id,
        version_number=version_number,
        file_name=file_name,
        payload=payload,
    )
