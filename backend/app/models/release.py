from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class GateExecution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "gate_executions"

    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_users.id", ondelete="RESTRICT"), nullable=False)
    expediente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("expedientes.id", ondelete="RESTRICT"), nullable=False)
    document_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document_versions.id", ondelete="RESTRICT"), nullable=False)
    bundle: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    bundle_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    document_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_hashes: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    verdict: Mapped[str] = mapped_column(String(16), nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class ReleaseOutbox(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "release_outbox"

    receipt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("release_receipts.id", ondelete="RESTRICT"), nullable=False, unique=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
