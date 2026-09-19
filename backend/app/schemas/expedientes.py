from __future__ import annotations

import base64
import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

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


class PartyCreate(BaseModel):
    role: PartyRole
    display_name: str
    entity_type: str | None = None
    identifier: str | None = None
    contact_data: dict[str, Any] = Field(default_factory=dict)


class PartyUpdate(BaseModel):
    role: PartyRole | None = None
    display_name: str | None = None
    entity_type: str | None = None
    identifier: str | None = None
    contact_data: dict[str, Any] | None = None


class ExpedienteCreate(BaseModel):
    expediente_number: str | None = None
    title: str
    matter_type: str
    jurisdiction_level: str | None = None
    jurisdiction_detail: str | None = None
    forum_or_recipient: str | None = None
    court_or_authority: str | None = None
    procedural_stage: str | None = None
    requested_outcome: str | None = None
    summary: str | None = None
    opened_on: date | None = None
    status: ExpedienteStatus = ExpedienteStatus.OPEN
    tags: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)
    parties: list[PartyCreate] = Field(default_factory=list)


class ExpedienteUpdate(BaseModel):
    expediente_number: str | None = None
    title: str | None = None
    matter_type: str | None = None
    jurisdiction_level: str | None = None
    jurisdiction_detail: str | None = None
    forum_or_recipient: str | None = None
    court_or_authority: str | None = None
    procedural_stage: str | None = None
    requested_outcome: str | None = None
    summary: str | None = None
    opened_on: date | None = None
    closed_on: date | None = None
    status: ExpedienteStatus | None = None
    tags: list[str] | None = None
    extra: dict[str, Any] | None = None


class PartyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: PartyRole
    display_name: str
    entity_type: str | None
    identifier: str | None
    contact_data: dict[str, Any]
    created_by_user_id: uuid.UUID | None
    updated_by_user_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class PartyListResponse(BaseModel):
    items: list[PartyRead]


class ExpedienteSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    expediente_number: str | None
    title: str
    matter_type: str
    jurisdiction_level: str | None
    procedural_stage: str | None
    status: ExpedienteStatus
    opened_on: date | None
    closed_on: date | None
    created_by_user_id: uuid.UUID | None
    updated_by_user_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class DocumentCreate(BaseModel):
    document_type: DocumentType
    title: str
    description: str | None = None
    status: DocumentStatus = DocumentStatus.ACTIVE
    issuing_authority: str | None = None
    source_reference: str | None = None
    event_date: date | None = None
    served_at: datetime | None = None
    filed_at: datetime | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class DocumentUpdate(BaseModel):
    document_type: DocumentType | None = None
    title: str | None = None
    description: str | None = None
    status: DocumentStatus | None = None
    issuing_authority: str | None = None
    source_reference: str | None = None
    event_date: date | None = None
    served_at: datetime | None = None
    filed_at: datetime | None = None
    extra: dict[str, Any] | None = None


class DocumentVersionCreate(BaseModel):
    source_kind: VersionSourceKind
    file_name: str
    mime_type: str | None = None
    created_by: str | None = None
    notes: str | None = None
    extracted_text: str | None = None
    content_base64: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

    @field_validator("content_base64")
    @classmethod
    def validate_base64(cls, value: str | None) -> str | None:
        if value is None:
            return value
        base64.b64decode(value.encode("utf-8"), validate=True)
        return value


class DocumentVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version_number: int
    source_kind: VersionSourceKind
    file_name: str
    mime_type: str | None
    storage_key: str | None
    sha256: str | None
    size_bytes: int | None
    notes: str | None
    created_by: str | None
    created_by_user_id: uuid.UUID | None
    extracted_text: str | None
    extra: dict[str, Any]
    created_at: datetime


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_type: DocumentType
    title: str
    description: str | None
    status: DocumentStatus
    issuing_authority: str | None
    source_reference: str | None
    event_date: date | None
    served_at: datetime | None
    filed_at: datetime | None
    current_version_id: uuid.UUID | None
    extra: dict[str, Any]
    created_by_user_id: uuid.UUID | None
    updated_by_user_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    versions: list[DocumentVersionRead] = Field(default_factory=list)


class DocumentListResponse(BaseModel):
    items: list[DocumentRead]


class EventCreate(BaseModel):
    event_type: EventType
    title: str
    event_date: datetime
    description: str | None = None
    document_id: uuid.UUID | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: EventType
    title: str
    event_date: datetime
    description: str | None
    document_id: uuid.UUID | None
    created_by_user_id: uuid.UUID | None
    updated_by_user_id: uuid.UUID | None
    created_at: datetime


class ProceduralDeadlineSuggestionRead(BaseModel):
    rule_id: str
    track_id: str
    track_label: str
    label: str
    due_at: datetime
    status: DeadlineStatus
    notes: str | None = None
    source_article: str | None = None
    source_url: str | None = None
    requires_review: bool = True
    computation_kind: str
    warning: str | None = None


class EventCreateResult(BaseModel):
    event: EventRead
    created_deadlines: list["DeadlineRead"] = Field(default_factory=list)
    matched_rules: list[ProceduralDeadlineSuggestionRead] = Field(default_factory=list)


class DeadlineCreate(BaseModel):
    label: str
    due_at: datetime
    status: DeadlineStatus = DeadlineStatus.OPEN
    notes: str | None = None
    document_id: uuid.UUID | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class DeadlineUpdate(BaseModel):
    label: str | None = None
    due_at: datetime | None = None
    status: DeadlineStatus | None = None
    notes: str | None = None
    document_id: uuid.UUID | None = None
    extra: dict[str, Any] | None = None


class DeadlineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str
    due_at: datetime
    status: DeadlineStatus
    notes: str | None
    document_id: uuid.UUID | None
    extra: dict[str, Any]
    created_by_user_id: uuid.UUID | None
    updated_by_user_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class DeadlineListResponse(BaseModel):
    items: list[DeadlineRead]


class ProceduralDeadlineTrackRead(BaseModel):
    id: str
    label: str
    status: str
    scope: str | None = None
    jurisdiction_level: str | None = None
    matter_types: list[str] = Field(default_factory=list)
    notes: str | None = None
    rule_count: int = 0
    sources: list[dict[str, Any]] = Field(default_factory=list)


class ProceduralDeadlineTrackListResponse(BaseModel):
    items: list[ProceduralDeadlineTrackRead]


class CalendarAgendaItemRead(BaseModel):
    kind: str
    expediente_id: uuid.UUID
    expediente_title: str
    expediente_number: str | None = None
    title: str
    starts_at: datetime
    status: str | None = None
    notes: str | None = None
    document_id: uuid.UUID | None = None
    source: str | None = None
    rule_id: str | None = None


class CalendarAgendaResponse(BaseModel):
    items: list[CalendarAgendaItemRead]
    generated_at: datetime


class ReleaseReceiptCreate(BaseModel):
    verdict: ReleaseVerdict
    response_type: str | None = None
    policy_id: str | None = None
    bundle_path: str | None = None
    artifact_path: str | None = None
    bundle_sha256: str | None = None
    document_version_id: uuid.UUID | None = None
    gate_summary: dict[str, Any] = Field(default_factory=dict)


class ReleaseReceiptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    verdict: ReleaseVerdict
    response_type: str | None
    policy_id: str | None
    bundle_path: str | None
    artifact_path: str | None
    bundle_sha256: str | None
    document_version_id: uuid.UUID | None
    created_by_user_id: uuid.UUID | None
    gate_summary: dict[str, Any]
    created_at: datetime


class ReleaseReceiptListResponse(BaseModel):
    items: list[ReleaseReceiptRead]


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    expediente_id: uuid.UUID | None
    document_id: uuid.UUID | None
    route: str | None
    method: str | None
    details: str | None
    extra_json: dict[str, Any]
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogRead]


class ExpedienteDetail(ExpedienteSummary):
    forum_or_recipient: str | None
    court_or_authority: str | None
    jurisdiction_detail: str | None
    requested_outcome: str | None
    summary: str | None
    tags: list[str]
    extra: dict[str, Any]
    parties: list[PartyRead] = Field(default_factory=list)
    documents: list[DocumentRead] = Field(default_factory=list)
    events: list[EventRead] = Field(default_factory=list)
    deadlines: list[DeadlineRead] = Field(default_factory=list)


class DocumentWithVersionCreate(BaseModel):
    document: DocumentCreate
    version: DocumentVersionCreate | None = None
