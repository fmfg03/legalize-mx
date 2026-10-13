from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from backend.app.models import GateExecution, ReleaseOutbox, ReleaseReceipt
from backend.app.release_service import canonical_json, digest, validate_receipt_record


def write_event(path: Path, payload: dict) -> None:
    """Idempotent filesystem effect; event UUID, never a client path, is the destination."""
    data = (canonical_json(payload) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError("Existing outbox artifact differs from committed event")
        # Recovery may see a rename performed just before the preceding worker crashed.
        # Make that existing effect durable before marking delivery in the database.
        with path.open("rb") as handle:
            os.fsync(handle.fileno())
        sync_directory(path.parent)
        return
    descriptor, temp_name = tempfile.mkstemp(prefix=".outbox-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        sync_directory(path.parent)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def drain_outbox(session_factory, directory: Path, limit: int = 100) -> dict[str, int]:
    attempted = []
    delivered = 0
    for _ in range(limit):
        with session_factory() as db:
            event = db.scalar(select(ReleaseOutbox).where(
                ReleaseOutbox.delivered_at.is_(None), ReleaseOutbox.id.not_in(attempted),
            ).order_by(ReleaseOutbox.created_at, ReleaseOutbox.id).with_for_update(skip_locked=True).limit(1))
            if event is None:
                break
            attempted.append(event.id)
            event.attempts += 1
            try:
                payload = event.payload
                receipt = db.get(ReleaseReceipt, event.receipt_id)
                execution = db.get(GateExecution, receipt.execution_id) if receipt else None
                if execution is None or digest(payload) != event.payload_sha256:
                    raise ValueError("Outbox integrity check failed")
                validate_receipt_record(receipt, execution)
                expected = dict(receipt_id=str(receipt.id), bundle=execution.bundle, **execution.evidence)
                if payload != expected or digest(execution.evidence) != execution.evidence_sha256 or digest(payload["bundle"]) != receipt.bundle_sha256 or payload["actor_user_id"] != str(receipt.created_by_user_id) or payload["verdict"] != receipt.verdict.value or payload["execution_id"] != str(receipt.execution_id) or receipt.gate_summary != execution.evidence:
                    raise ValueError("Outbox event does not match committed receipt")
                write_event(directory / f"{event.id}.json", payload)
                event.delivered_at = datetime.now(timezone.utc)
                event.last_error = None
                delivered += 1
            except Exception as exc:
                event.last_error = type(exc).__name__
            db.commit()
    return {"attempted": len(attempted), "delivered": delivered, "failed": len(attempted) - delivered}
