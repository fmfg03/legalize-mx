from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from backend.app.models.enums import (
    DeadlineStatus,
    DocumentStatus,
    DocumentType,
    EventType,
    ExpedienteStatus,
    PartyRole,
    ReleaseVerdict,
    VersionSourceKind,
)


class AuditActorMixin:
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("app_users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("app_users.id", ondelete="SET NULL"), nullable=True, index=True
    )


class AuditCreatedByMixin:
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("app_users.id", ondelete="SET NULL"), nullable=True, index=True
    )


class Expediente(UUIDPrimaryKeyMixin, TimestampMixin, AuditActorMixin, Base):
    __tablename__ = "expedientes"

    expediente_number: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    matter_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    jurisdiction_level: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    jurisdiction_detail: Mapped[str | None] = mapped_column(String(255), nullable=True)
    forum_or_recipient: Mapped[str | None] = mapped_column(String(255), nullable=True)
    court_or_authority: Mapped[str | None] = mapped_column(String(255), nullable=True)
    procedural_stage: Mapped[str | None] = mapped_column(String(128), nullable=True)
    requested_outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    opened_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    closed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[ExpedienteStatus] = mapped_column(
        Enum(ExpedienteStatus, name="expediente_status"), default=ExpedienteStatus.OPEN, nullable=False
    )
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    parties: Mapped[list["Party"]] = relationship(back_populates="expediente", cascade="all, delete-orphan")
    documents: Mapped[list["ExpedienteDocument"]] = relationship(
        back_populates="expediente", cascade="all, delete-orphan"
    )
    events: Mapped[list["ExpedienteEvent"]] = relationship(
        back_populates="expediente", cascade="all, delete-orphan"
    )
    deadlines: Mapped[list["Deadline"]] = relationship(
        back_populates="expediente", cascade="all, delete-orphan"
    )
    release_receipts: Mapped[list["ReleaseReceipt"]] = relationship(
        back_populates="expediente", cascade="all, delete-orphan"
    )


class Party(UUIDPrimaryKeyMixin, TimestampMixin, AuditActorMixin, Base):
    __tablename__ = "expediente_parties"

    expediente_id: Mapped[str] = mapped_column(ForeignKey("expedientes.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[PartyRole] = mapped_column(Enum(PartyRole, name="party_role"), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    identifier: Mapped[str | None] = mapped_column(String(128), nullable=True)
    contact_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    expediente: Mapped["Expediente"] = relationship(back_populates="parties")


class ExpedienteDocument(UUIDPrimaryKeyMixin, TimestampMixin, AuditActorMixin, Base):
    __tablename__ = "expediente_documents"

    expediente_id: Mapped[str] = mapped_column(ForeignKey("expedientes.id", ondelete="CASCADE"), nullable=False)
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="document_type"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status"), default=DocumentStatus.ACTIVE, nullable=False
    )
    issuing_authority: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    served_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    filed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("document_versions.id", ondelete="SET NULL"), nullable=True
    )
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    expediente: Mapped["Expediente"] = relationship(back_populates="documents")
    current_version: Mapped["DocumentVersion | None"] = relationship(
        foreign_keys=[current_version_id], post_update=True
    )
    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        foreign_keys="DocumentVersion.document_id",
        order_by="DocumentVersion.version_number",
    )
    linked_events: Mapped[list["ExpedienteEvent"]] = relationship(back_populates="document")
    linked_deadlines: Mapped[list["Deadline"]] = relationship(back_populates="document")


class DocumentVersion(UUIDPrimaryKeyMixin, TimestampMixin, AuditCreatedByMixin, Base):
    __tablename__ = "document_versions"
    __table_args__ = (UniqueConstraint("document_id", "version_number", name="uq_document_versions_doc_version"),)

    document_id: Mapped[str] = mapped_column(
        ForeignKey("expediente_documents.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_kind: Mapped[VersionSourceKind] = mapped_column(
        Enum(VersionSourceKind, name="version_source_kind"), nullable=False
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True, unique=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    document: Mapped["ExpedienteDocument"] = relationship(back_populates="versions", foreign_keys=[document_id])
    release_receipts: Mapped[list["ReleaseReceipt"]] = relationship(
        back_populates="document_version", cascade="all, delete-orphan"
    )


class ExpedienteEvent(UUIDPrimaryKeyMixin, TimestampMixin, AuditActorMixin, Base):
    __tablename__ = "expediente_events"

    expediente_id: Mapped[str] = mapped_column(ForeignKey("expedientes.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[str | None] = mapped_column(
        ForeignKey("expediente_documents.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[EventType] = mapped_column(Enum(EventType, name="event_type"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    expediente: Mapped["Expediente"] = relationship(back_populates="events")
    document: Mapped["ExpedienteDocument | None"] = relationship(back_populates="linked_events")


class Deadline(UUIDPrimaryKeyMixin, TimestampMixin, AuditActorMixin, Base):
    __tablename__ = "expediente_deadlines"

    expediente_id: Mapped[str] = mapped_column(ForeignKey("expedientes.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[str | None] = mapped_column(
        ForeignKey("expediente_documents.id", ondelete="SET NULL"), nullable=True
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[DeadlineStatus] = mapped_column(
        Enum(DeadlineStatus, name="deadline_status"), default=DeadlineStatus.OPEN, nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    expediente: Mapped["Expediente"] = relationship(back_populates="deadlines")
    document: Mapped["ExpedienteDocument | None"] = relationship(back_populates="linked_deadlines")


class ReleaseReceipt(UUIDPrimaryKeyMixin, TimestampMixin, AuditCreatedByMixin, Base):
    __tablename__ = "release_receipts"

    expediente_id: Mapped[str | None] = mapped_column(ForeignKey("expedientes.id", ondelete="SET NULL"), nullable=True)
    document_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("document_versions.id", ondelete="SET NULL"), nullable=True
    )
    verdict: Mapped[ReleaseVerdict] = mapped_column(
        Enum(ReleaseVerdict, name="release_verdict"), nullable=False
    )
    response_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    policy_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    bundle_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    artifact_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    bundle_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gate_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    expediente: Mapped["Expediente | None"] = relationship(back_populates="release_receipts")
    document_version: Mapped["DocumentVersion | None"] = relationship(back_populates="release_receipts")
