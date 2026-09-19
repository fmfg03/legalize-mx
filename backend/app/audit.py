from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models import AuditLog


def record_audit_log(
    *,
    db: Session,
    actor_user_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    expediente_id: uuid.UUID | None = None,
    document_id: uuid.UUID | None = None,
    route: str | None = None,
    method: str | None = None,
    details: str | None = None,
    extra: dict[str, Any] | None = None,
) -> AuditLog:
    log = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        expediente_id=expediente_id,
        document_id=document_id,
        route=route,
        method=method,
        details=details,
        extra_json=extra or {},
    )
    db.add(log)
    return log


def dumps_audit_details(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True)
