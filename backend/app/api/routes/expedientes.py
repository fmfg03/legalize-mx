from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.app.audit import dumps_audit_details, record_audit_log
from backend.app.db import get_db
from backend.app.deps import require_audit_user, require_operator_user, require_read_user, require_reviewer_user
from backend.app.models import (
    AppUser,
    AuditLog,
    Deadline,
    DocumentVersion,
    Expediente,
    ExpedienteDocument,
    ExpedienteEvent,
    Party,
    ReleaseReceipt,
)
from backend.app.models.enums import DeadlineStatus, DocumentType, EventType, ExpedienteStatus, VersionSourceKind
from backend.app.procedural_deadlines import (
    infer_track_id,
    procedural_deadline_matches,
    procedural_deadline_tracks,
    procedural_track_summary,
)
from backend.app.schemas.expedientes import (
    AuditLogListResponse,
    CalendarAgendaItemRead,
    CalendarAgendaResponse,
    DeadlineCreate,
    DeadlineListResponse,
    DeadlineRead,
    DeadlineUpdate,
    DocumentListResponse,
    DocumentRead,
    DocumentUpdate,
    DocumentVersionRead,
    DocumentVersionCreate,
    DocumentWithVersionCreate,
    EventCreate,
    EventCreateResult,
    EventRead,
    ExpedienteCreate,
    ExpedienteDetail,
    ExpedienteSummary,
    ExpedienteUpdate,
    PartyCreate,
    PartyListResponse,
    PartyRead,
    PartyUpdate,
    ProceduralDeadlineSuggestionRead,
    ProceduralDeadlineTrackListResponse,
    ReleaseReceiptCreate,
    ReleaseReceiptListResponse,
    ReleaseReceiptRead,
)
from backend.app.storage import resolve_storage_path, store_document_bytes, store_document_payload


router = APIRouter(prefix="/expedientes", tags=["expedientes"])


def get_expediente_or_404(db: Session, expediente_id: str) -> Expediente:
    try:
        parsed_id = uuid.UUID(str(expediente_id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expediente not found") from exc
    stmt = (
        select(Expediente)
        .options(
            selectinload(Expediente.parties),
            selectinload(Expediente.documents).selectinload(ExpedienteDocument.versions),
            selectinload(Expediente.events),
            selectinload(Expediente.deadlines),
        )
        .where(Expediente.id == parsed_id)
    )
    expediente = db.scalar(stmt)
    if expediente is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expediente not found")
    return expediente


def get_document_or_404(expediente: Expediente, document_id: str) -> ExpedienteDocument:
    document = next((item for item in expediente.documents if str(item.id) == document_id), None)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


def get_document_version_or_404(document: ExpedienteDocument, version_id: str) -> DocumentVersion:
    version = next((item for item in document.versions if str(item.id) == version_id), None)
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document version not found")
    return version


def get_party_or_404(expediente: Expediente, party_id: str) -> Party:
    party = next((item for item in expediente.parties if str(item.id) == party_id), None)
    if party is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Party not found")
    return party


def get_deadline_or_404(expediente: Expediente, deadline_id: str) -> Deadline:
    deadline = next((item for item in expediente.deadlines if str(item.id) == deadline_id), None)
    if deadline is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deadline not found")
    return deadline


def procedural_rule_exists(expediente: Expediente, *, event_id: uuid.UUID, rule_id: str) -> bool:
    for deadline in expediente.deadlines:
        extra = deadline.extra if isinstance(deadline.extra, dict) else {}
        if (
            str(extra.get("generated_from_event_id") or "") == str(event_id)
            and str(extra.get("procedural_rule_id") or "") == rule_id
        ):
            return True
    return False


def build_procedural_deadlines(
    *,
    expediente: Expediente,
    event: ExpedienteEvent,
    document: ExpedienteDocument | None,
    current_user: AppUser,
    db: Session,
    request: Request,
) -> tuple[list[Deadline], list[ProceduralDeadlineSuggestionRead]]:
    created_deadlines: list[Deadline] = []
    matched_rules: list[ProceduralDeadlineSuggestionRead] = []
    for match in procedural_deadline_matches(expediente=expediente, event=event, document=document):
        matched_rules.append(
            ProceduralDeadlineSuggestionRead(
                rule_id=match.rule_id,
                track_id=match.track_id,
                track_label=match.track_label,
                label=match.deadline_label,
                due_at=match.due_at,
                status=match.status,
                notes=match.notes,
                source_article=match.source_article,
                source_url=match.source_url,
                requires_review=match.requires_review,
                computation_kind=match.computation_kind,
                warning=match.warning,
            )
        )
        if procedural_rule_exists(expediente, event_id=event.id, rule_id=match.rule_id):
            continue
        deadline = Deadline(
            expediente_id=expediente.id,
            document_id=document.id if document is not None else None,
            label=match.deadline_label,
            due_at=match.due_at,
            status=match.status,
            notes=match.notes,
            extra=match.extra,
            created_by_user_id=current_user.id,
            updated_by_user_id=current_user.id,
        )
        db.add(deadline)
        db.flush()
        record_audit_log(
            db=db,
            actor_user_id=current_user.id,
            action="auto_create_deadline",
            entity_type="deadline",
            entity_id=deadline.id,
            expediente_id=expediente.id,
            document_id=deadline.document_id,
            route=str(request.url.path),
            method=request.method,
            details=dumps_audit_details(
                {
                    "label": deadline.label,
                    "due_at": deadline.due_at.isoformat(),
                    "procedural_rule_id": match.rule_id,
                    "generated_from_event_id": str(event.id),
                }
            ),
        )
        created_deadlines.append(deadline)
    return created_deadlines, matched_rules


def get_audit_logs_for_expediente(
    db: Session,
    expediente: Expediente,
    *,
    action: str | None = None,
    entity_type: str | None = None,
    actor_user_id: uuid.UUID | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: int = 100,
) -> list[AuditLog]:
    stmt = select(AuditLog).where(AuditLog.expediente_id == expediente.id)
    if action:
        stmt = stmt.where(AuditLog.action == action.strip())
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type.strip())
    if actor_user_id is not None:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
    if created_from is not None:
        stmt = stmt.where(AuditLog.created_at >= created_from)
    if created_to is not None:
        stmt = stmt.where(AuditLog.created_at <= created_to)
    stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit)
    return list(db.scalars(stmt).all())


def apply_partial_update(
    *,
    updates: dict[str, object],
    target: object,
    disallow_none_fields: set[str] | None = None,
    default_on_none: dict[str, object] | None = None,
) -> None:
    disallow_none_fields = disallow_none_fields or set()
    default_on_none = default_on_none or {}
    for field_name, value in updates.items():
        if value is None:
            if field_name in disallow_none_fields:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"{field_name} cannot be null",
                )
            if field_name in default_on_none:
                value = default_on_none[field_name]
        setattr(target, field_name, value)


@router.get("", response_model=list[ExpedienteSummary])
def list_expedientes(
    expediente_number: str | None = Query(default=None),
    matter_type: str | None = Query(default=None),
    jurisdiction_level: str | None = Query(default=None),
    status_filter: ExpedienteStatus | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    _: AppUser = Depends(require_read_user),
    db: Session = Depends(get_db),
) -> list[Expediente]:
    stmt = select(Expediente)
    if expediente_number:
        stmt = stmt.where(Expediente.expediente_number.ilike(f"%{expediente_number.strip()}%"))
    if matter_type:
        stmt = stmt.where(Expediente.matter_type == matter_type.strip())
    if jurisdiction_level:
        stmt = stmt.where(Expediente.jurisdiction_level == jurisdiction_level.strip())
    if status_filter:
        stmt = stmt.where(Expediente.status == status_filter)
    if q:
        needle = f"%{q.strip()}%"
        stmt = stmt.where(
            Expediente.title.ilike(needle)
            | Expediente.summary.ilike(needle)
            | Expediente.court_or_authority.ilike(needle)
        )
    stmt = stmt.order_by(Expediente.updated_at.desc()).limit(limit)
    return list(db.scalars(stmt).all())


@router.get("/meta/procedural-deadline-tracks", response_model=ProceduralDeadlineTrackListResponse)
def list_procedural_deadline_tracks(
    _: AppUser = Depends(require_read_user),
) -> ProceduralDeadlineTrackListResponse:
    return ProceduralDeadlineTrackListResponse(items=procedural_deadline_tracks())


@router.get("/agenda/calendar", response_model=CalendarAgendaResponse)
def get_calendar_agenda(
    days_back: int = Query(default=7, ge=0, le=180),
    days_forward: int = Query(default=90, ge=1, le=365),
    include_satisfied: bool = Query(default=False),
    _: AppUser = Depends(require_read_user),
    db: Session = Depends(get_db),
) -> CalendarAgendaResponse:
    now = datetime.now(timezone.utc)
    window_start = now.replace(tzinfo=None)
    window_end = now.replace(tzinfo=None)
    window_start = window_start - timedelta(days=days_back)
    window_end = window_end + timedelta(days=days_forward)

    deadline_stmt = (
        select(Deadline, Expediente)
        .join(Expediente, Deadline.expediente_id == Expediente.id)
        .where(Deadline.due_at >= window_start, Deadline.due_at <= window_end)
    )
    if not include_satisfied:
        deadline_stmt = deadline_stmt.where(Deadline.status == DeadlineStatus.OPEN)
    deadline_rows = db.execute(deadline_stmt.order_by(Deadline.due_at.asc())).all()

    event_stmt = (
        select(ExpedienteEvent, Expediente)
        .join(Expediente, ExpedienteEvent.expediente_id == Expediente.id)
        .where(
            ExpedienteEvent.event_type == EventType.AUDIENCIA,
            ExpedienteEvent.event_date >= window_start,
            ExpedienteEvent.event_date <= window_end,
        )
        .order_by(ExpedienteEvent.event_date.asc())
    )
    event_rows = db.execute(event_stmt).all()

    items: list[CalendarAgendaItemRead] = []
    for deadline, expediente in deadline_rows:
        extra = deadline.extra if isinstance(deadline.extra, dict) else {}
        items.append(
            CalendarAgendaItemRead(
                kind="deadline",
                expediente_id=expediente.id,
                expediente_title=expediente.title,
                expediente_number=expediente.expediente_number,
                title=deadline.label,
                starts_at=deadline.due_at,
                status=str(deadline.status),
                notes=deadline.notes,
                document_id=deadline.document_id,
                source=str(extra.get("procedural_track_label") or "manual"),
                rule_id=str(extra.get("procedural_rule_id") or "") or None,
            )
        )
    for event, expediente in event_rows:
        items.append(
            CalendarAgendaItemRead(
                kind="audiencia",
                expediente_id=expediente.id,
                expediente_title=expediente.title,
                expediente_number=expediente.expediente_number,
                title=event.title,
                starts_at=event.event_date,
                status=str(event.event_type),
                notes=event.description,
                document_id=event.document_id,
                source="audiencia",
                rule_id=None,
            )
        )
    items.sort(key=lambda item: item.starts_at)
    return CalendarAgendaResponse(items=items, generated_at=datetime.now(timezone.utc))


@router.post("", response_model=ExpedienteDetail, status_code=status.HTTP_201_CREATED)
def create_expediente(
    payload: ExpedienteCreate,
    request: Request,
    current_user: AppUser = Depends(require_operator_user),
    db: Session = Depends(get_db),
) -> Expediente:
    expediente = Expediente(
        expediente_number=payload.expediente_number,
        title=payload.title,
        matter_type=payload.matter_type,
        jurisdiction_level=payload.jurisdiction_level,
        jurisdiction_detail=payload.jurisdiction_detail,
        forum_or_recipient=payload.forum_or_recipient,
        court_or_authority=payload.court_or_authority,
        procedural_stage=payload.procedural_stage,
        requested_outcome=payload.requested_outcome,
        summary=payload.summary,
        opened_on=payload.opened_on,
        status=payload.status,
        tags=payload.tags,
        extra=payload.extra,
        created_by_user_id=current_user.id,
        updated_by_user_id=current_user.id,
    )
    for party_payload in payload.parties:
        expediente.parties.append(
            Party(
                role=party_payload.role,
                display_name=party_payload.display_name,
                entity_type=party_payload.entity_type,
                identifier=party_payload.identifier,
                contact_data=party_payload.contact_data,
                created_by_user_id=current_user.id,
                updated_by_user_id=current_user.id,
            )
        )
    db.add(expediente)
    db.flush()
    record_audit_log(
        db=db,
        actor_user_id=current_user.id,
        action="create_expediente",
        entity_type="expediente",
        entity_id=expediente.id,
        expediente_id=expediente.id,
        route=str(request.url.path),
        method=request.method,
        details=dumps_audit_details(
            {
                "expediente_number": expediente.expediente_number,
                "matter_type": expediente.matter_type,
                "title": expediente.title,
            }
        ),
    )
    db.commit()
    db.refresh(expediente)
    return get_expediente_or_404(db, str(expediente.id))


@router.patch("/{expediente_id}", response_model=ExpedienteDetail)
def update_expediente(
    expediente_id: str,
    payload: ExpedienteUpdate,
    request: Request,
    current_user: AppUser = Depends(require_operator_user),
    db: Session = Depends(get_db),
) -> Expediente:
    expediente = get_expediente_or_404(db, expediente_id)
    updates = payload.model_dump(exclude_unset=True)
    apply_partial_update(
        updates=updates,
        target=expediente,
        disallow_none_fields={"title", "matter_type", "status"},
        default_on_none={"tags": [], "extra": {}},
    )
    expediente.updated_by_user_id = current_user.id
    record_audit_log(
        db=db,
        actor_user_id=current_user.id,
        action="update_expediente",
        entity_type="expediente",
        entity_id=expediente.id,
        expediente_id=expediente.id,
        route=str(request.url.path),
        method=request.method,
        details=dumps_audit_details({"updated_fields": sorted(updates.keys())}),
    )
    db.commit()
    return get_expediente_or_404(db, expediente_id)


@router.get("/{expediente_id}", response_model=ExpedienteDetail)
def get_expediente(
    expediente_id: str,
    _: AppUser = Depends(require_read_user),
    db: Session = Depends(get_db),
) -> Expediente:
    return get_expediente_or_404(db, expediente_id)


@router.get("/{expediente_id}/audit-logs", response_model=AuditLogListResponse)
def list_audit_logs(
    expediente_id: str,
    action: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    actor_user_id: str | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    _: AppUser = Depends(require_audit_user),
    db: Session = Depends(get_db),
) -> AuditLogListResponse:
    expediente = get_expediente_or_404(db, expediente_id)
    if not isinstance(created_from, datetime):
        created_from = None
    if not isinstance(created_to, datetime):
        created_to = None
    parsed_actor_id: uuid.UUID | None = None
    if actor_user_id:
        try:
            parsed_actor_id = uuid.UUID(actor_user_id)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="actor_user_id is invalid") from exc
    items = get_audit_logs_for_expediente(
        db,
        expediente,
        action=action,
        entity_type=entity_type,
        actor_user_id=parsed_actor_id,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
    )
    return AuditLogListResponse(items=items)


@router.get("/{expediente_id}/parties", response_model=PartyListResponse)
def list_parties(
    expediente_id: str,
    _: AppUser = Depends(require_read_user),
    db: Session = Depends(get_db),
) -> PartyListResponse:
    expediente = get_expediente_or_404(db, expediente_id)
    return PartyListResponse(items=expediente.parties)


@router.post("/{expediente_id}/parties", response_model=PartyRead, status_code=status.HTTP_201_CREATED)
def create_party(
    expediente_id: str,
    payload: PartyCreate,
    request: Request,
    current_user: AppUser = Depends(require_operator_user),
    db: Session = Depends(get_db),
) -> Party:
    expediente = get_expediente_or_404(db, expediente_id)
    party = Party(
        expediente_id=expediente.id,
        role=payload.role,
        display_name=payload.display_name,
        entity_type=payload.entity_type,
        identifier=payload.identifier,
        contact_data=payload.contact_data,
        created_by_user_id=current_user.id,
        updated_by_user_id=current_user.id,
    )
    db.add(party)
    db.flush()
    record_audit_log(
        db=db,
        actor_user_id=current_user.id,
        action="create_party",
        entity_type="party",
        entity_id=party.id,
        expediente_id=expediente.id,
        route=str(request.url.path),
        method=request.method,
        details=dumps_audit_details({"display_name": party.display_name, "role": party.role}),
    )
    db.commit()
    db.refresh(party)
    return party


@router.patch("/{expediente_id}/parties/{party_id}", response_model=PartyRead)
def update_party(
    expediente_id: str,
    party_id: str,
    payload: PartyUpdate,
    request: Request,
    current_user: AppUser = Depends(require_operator_user),
    db: Session = Depends(get_db),
) -> Party:
    expediente = get_expediente_or_404(db, expediente_id)
    party = get_party_or_404(expediente, party_id)
    updates = payload.model_dump(exclude_unset=True)
    apply_partial_update(
        updates=updates,
        target=party,
        disallow_none_fields={"role", "display_name"},
        default_on_none={"contact_data": {}},
    )
    party.updated_by_user_id = current_user.id
    record_audit_log(
        db=db,
        actor_user_id=current_user.id,
        action="update_party",
        entity_type="party",
        entity_id=party.id,
        expediente_id=expediente.id,
        route=str(request.url.path),
        method=request.method,
        details=dumps_audit_details({"updated_fields": sorted(updates.keys())}),
    )
    db.commit()
    db.refresh(party)
    return party


@router.post("/{expediente_id}/documents", response_model=ExpedienteDetail, status_code=status.HTTP_201_CREATED)
def create_document(
    expediente_id: str,
    payload: DocumentWithVersionCreate,
    request: Request,
    current_user: AppUser = Depends(require_operator_user),
    db: Session = Depends(get_db),
) -> Expediente:
    expediente = get_expediente_or_404(db, expediente_id)
    document = ExpedienteDocument(
        expediente_id=expediente.id,
        document_type=payload.document.document_type,
        title=payload.document.title,
        description=payload.document.description,
        status=payload.document.status,
        issuing_authority=payload.document.issuing_authority,
        source_reference=payload.document.source_reference,
        event_date=payload.document.event_date,
        served_at=payload.document.served_at,
        filed_at=payload.document.filed_at,
        extra=payload.document.extra,
        created_by_user_id=current_user.id,
        updated_by_user_id=current_user.id,
    )
    db.add(document)
    db.flush()

    if payload.version is not None:
        version = build_document_version(document=document, payload=payload.version, db=db, current_user=current_user)
        document.current_version = version

    record_audit_log(
        db=db,
        actor_user_id=current_user.id,
        action="create_document",
        entity_type="document",
        entity_id=document.id,
        expediente_id=expediente.id,
        document_id=document.id,
        route=str(request.url.path),
        method=request.method,
        details=dumps_audit_details({"document_type": document.document_type, "title": document.title}),
    )
    db.commit()
    return get_expediente_or_404(db, expediente_id)


@router.get("/{expediente_id}/documents", response_model=DocumentListResponse)
def list_documents(
    expediente_id: str,
    document_type: DocumentType | None = Query(default=None),
    _: AppUser = Depends(require_read_user),
    db: Session = Depends(get_db),
) -> DocumentListResponse:
    expediente = get_expediente_or_404(db, expediente_id)
    items = expediente.documents
    if document_type is not None:
        items = [item for item in items if item.document_type == document_type]
    ordered = sorted(
        items,
        key=lambda item: (item.event_date is None, item.event_date or item.updated_at.date(), item.updated_at),
        reverse=True,
    )
    return DocumentListResponse(items=ordered)


@router.get("/{expediente_id}/documents/{document_id}", response_model=DocumentRead)
def get_document(
    expediente_id: str,
    document_id: str,
    _: AppUser = Depends(require_read_user),
    db: Session = Depends(get_db),
) -> ExpedienteDocument:
    expediente = get_expediente_or_404(db, expediente_id)
    return get_document_or_404(expediente, document_id)


@router.patch("/{expediente_id}/documents/{document_id}", response_model=DocumentRead)
def update_document(
    expediente_id: str,
    document_id: str,
    payload: DocumentUpdate,
    request: Request,
    current_user: AppUser = Depends(require_operator_user),
    db: Session = Depends(get_db),
) -> ExpedienteDocument:
    expediente = get_expediente_or_404(db, expediente_id)
    document = get_document_or_404(expediente, document_id)
    updates = payload.model_dump(exclude_unset=True)
    apply_partial_update(
        updates=updates,
        target=document,
        disallow_none_fields={"document_type", "title", "status"},
        default_on_none={"extra": {}},
    )
    document.updated_by_user_id = current_user.id
    record_audit_log(
        db=db,
        actor_user_id=current_user.id,
        action="update_document",
        entity_type="document",
        entity_id=document.id,
        expediente_id=expediente.id,
        document_id=document.id,
        route=str(request.url.path),
        method=request.method,
        details=dumps_audit_details({"updated_fields": sorted(updates.keys())}),
    )
    db.commit()
    db.refresh(document)
    return document


def build_document_version(
    *,
    document: ExpedienteDocument,
    payload: DocumentVersionCreate,
    db: Session,
    current_user: AppUser,
) -> DocumentVersion:
    current_version = db.scalar(
        select(func.max(DocumentVersion.version_number)).where(DocumentVersion.document_id == document.id)
    )
    next_version = int(current_version or 0) + 1
    storage_key = None
    size_bytes = None
    sha256 = None
    if payload.content_base64 is not None:
        stored = store_document_bytes(
            expediente_id=str(document.expediente_id),
            document_id=str(document.id),
            version_number=next_version,
            file_name=payload.file_name,
            content_base64=payload.content_base64,
        )
        storage_key = stored.storage_key
        size_bytes = stored.size_bytes
        sha256 = stored.sha256

    version = DocumentVersion(
        document_id=document.id,
        version_number=next_version,
        source_kind=payload.source_kind,
        file_name=payload.file_name,
        mime_type=payload.mime_type,
        storage_key=storage_key,
        sha256=sha256,
        size_bytes=size_bytes,
        notes=payload.notes,
        created_by=payload.created_by or current_user.email,
        extracted_text=payload.extracted_text,
        extra=payload.extra,
        created_by_user_id=current_user.id,
    )
    db.add(version)
    db.flush()
    return version


@router.post(
    "/{expediente_id}/documents/{document_id}/versions",
    response_model=DocumentVersionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_document_version(
    expediente_id: str,
    document_id: str,
    payload: DocumentVersionCreate,
    request: Request,
    current_user: AppUser = Depends(require_operator_user),
    db: Session = Depends(get_db),
) -> DocumentVersion:
    expediente = get_expediente_or_404(db, expediente_id)
    document = get_document_or_404(expediente, document_id)
    version = build_document_version(document=document, payload=payload, db=db, current_user=current_user)
    document.current_version = version
    document.updated_by_user_id = current_user.id
    record_audit_log(
        db=db,
        actor_user_id=current_user.id,
        action="create_document_version",
        entity_type="document_version",
        entity_id=version.id,
        expediente_id=expediente.id,
        document_id=document.id,
        route=str(request.url.path),
        method=request.method,
        details=dumps_audit_details({"version_number": version.version_number, "source_kind": version.source_kind}),
    )
    db.commit()
    db.refresh(version)
    return version


@router.get(
    "/{expediente_id}/documents/{document_id}/versions/{version_id}",
    response_model=DocumentVersionRead,
)
def get_document_version(
    expediente_id: str,
    document_id: str,
    version_id: str,
    _: AppUser = Depends(require_read_user),
    db: Session = Depends(get_db),
) -> DocumentVersion:
    expediente = get_expediente_or_404(db, expediente_id)
    document = get_document_or_404(expediente, document_id)
    return get_document_version_or_404(document, version_id)


@router.get("/{expediente_id}/documents/{document_id}/versions/{version_id}/download")
def download_document_version(
    expediente_id: str,
    document_id: str,
    version_id: str,
    _: AppUser = Depends(require_read_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    expediente = get_expediente_or_404(db, expediente_id)
    document = get_document_or_404(expediente, document_id)
    version = get_document_version_or_404(document, version_id)
    if version.storage_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document version has no stored file")
    try:
        file_path = resolve_storage_path(version.storage_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    if not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored file not found")
    return FileResponse(
        path=file_path,
        media_type=version.mime_type or "application/octet-stream",
        filename=version.file_name,
    )


@router.post(
    "/{expediente_id}/documents/{document_id}/upload",
    response_model=DocumentVersionRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document_version(
    expediente_id: str,
    document_id: str,
    request: Request,
    source_kind: VersionSourceKind = Form(...),
    notes: str | None = Form(default=None),
    extracted_text: str | None = Form(default=None),
    created_by: str | None = Form(default=None),
    mime_type: str | None = Form(default=None),
    extra_json: str | None = Form(default=None),
    file: UploadFile = File(...),
    current_user: AppUser = Depends(require_operator_user),
    db: Session = Depends(get_db),
) -> DocumentVersion:
    expediente = get_expediente_or_404(db, expediente_id)
    document = get_document_or_404(expediente, document_id)

    current_version = db.scalar(
        select(func.max(DocumentVersion.version_number)).where(DocumentVersion.document_id == document.id)
    )
    next_version = int(current_version or 0) + 1
    payload_bytes = await file.read()
    try:
        extra = json.loads(extra_json) if extra_json else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"extra_json is not valid JSON: {exc.msg}",
        ) from exc
    if extra_json and not isinstance(extra, dict):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="extra_json must be an object")

    stored = store_document_payload(
        expediente_id=str(document.expediente_id),
        document_id=str(document.id),
        version_number=next_version,
        file_name=file.filename or "document.bin",
        payload=payload_bytes,
    )

    version = DocumentVersion(
        document_id=document.id,
        version_number=next_version,
        source_kind=source_kind,
        file_name=file.filename or "document.bin",
        mime_type=mime_type or file.content_type,
        storage_key=stored.storage_key,
        sha256=stored.sha256,
        size_bytes=stored.size_bytes,
        notes=notes,
        created_by=created_by or current_user.email,
        extracted_text=extracted_text,
        extra=extra,
        created_by_user_id=current_user.id,
    )
    db.add(version)
    db.flush()
    document.current_version = version
    document.updated_by_user_id = current_user.id
    record_audit_log(
        db=db,
        actor_user_id=current_user.id,
        action="upload_document_version",
        entity_type="document_version",
        entity_id=version.id,
        expediente_id=expediente.id,
        document_id=document.id,
        route=str(request.url.path) if request else None,
        method=request.method if request else None,
        details=dumps_audit_details({"file_name": version.file_name, "version_number": version.version_number}),
    )
    db.commit()
    db.refresh(version)
    return version


@router.post("/{expediente_id}/events", response_model=EventCreateResult, status_code=status.HTTP_201_CREATED)
def create_event(
    expediente_id: str,
    payload: EventCreate,
    request: Request,
    current_user: AppUser = Depends(require_operator_user),
    db: Session = Depends(get_db),
) -> EventCreateResult:
    expediente = get_expediente_or_404(db, expediente_id)
    document = None
    if payload.document_id is not None:
        document = get_document_or_404(expediente, str(payload.document_id))
    event = ExpedienteEvent(
        expediente_id=expediente.id,
        document_id=document.id if document is not None else None,
        event_type=payload.event_type,
        title=payload.title,
        description=payload.description,
        event_date=payload.event_date,
        extra=payload.extra,
        created_by_user_id=current_user.id,
        updated_by_user_id=current_user.id,
    )
    db.add(event)
    db.flush()
    record_audit_log(
        db=db,
        actor_user_id=current_user.id,
        action="create_event",
        entity_type="event",
        entity_id=event.id,
        expediente_id=expediente.id,
        document_id=event.document_id,
        route=str(request.url.path),
        method=request.method,
        details=dumps_audit_details({"event_type": event.event_type, "title": event.title}),
    )
    created_deadlines, matched_rules = build_procedural_deadlines(
        expediente=expediente,
        event=event,
        document=document,
        current_user=current_user,
        db=db,
        request=request,
    )
    db.commit()
    db.refresh(event)
    for deadline in created_deadlines:
        db.refresh(deadline)
    return EventCreateResult(event=event, created_deadlines=created_deadlines, matched_rules=matched_rules)


@router.get("/{expediente_id}/deadlines", response_model=DeadlineListResponse)
def list_deadlines(
    expediente_id: str,
    _: AppUser = Depends(require_read_user),
    db: Session = Depends(get_db),
) -> DeadlineListResponse:
    expediente = get_expediente_or_404(db, expediente_id)
    ordered = sorted(expediente.deadlines, key=lambda item: item.due_at)
    return DeadlineListResponse(items=ordered)


@router.post("/{expediente_id}/deadlines", response_model=DeadlineRead, status_code=status.HTTP_201_CREATED)
def create_deadline(
    expediente_id: str,
    payload: DeadlineCreate,
    request: Request,
    current_user: AppUser = Depends(require_operator_user),
    db: Session = Depends(get_db),
) -> Deadline:
    expediente = get_expediente_or_404(db, expediente_id)
    deadline = Deadline(
        expediente_id=expediente.id,
        document_id=payload.document_id,
        label=payload.label,
        due_at=payload.due_at,
        status=payload.status,
        notes=payload.notes,
        extra=payload.extra,
        created_by_user_id=current_user.id,
        updated_by_user_id=current_user.id,
    )
    db.add(deadline)
    db.flush()
    record_audit_log(
        db=db,
        actor_user_id=current_user.id,
        action="create_deadline",
        entity_type="deadline",
        entity_id=deadline.id,
        expediente_id=expediente.id,
        document_id=deadline.document_id,
        route=str(request.url.path),
        method=request.method,
        details=dumps_audit_details({"label": deadline.label, "due_at": deadline.due_at.isoformat()}),
    )
    db.commit()
    db.refresh(deadline)
    return deadline


@router.patch("/{expediente_id}/deadlines/{deadline_id}", response_model=DeadlineRead)
def update_deadline(
    expediente_id: str,
    deadline_id: str,
    payload: DeadlineUpdate,
    request: Request,
    current_user: AppUser = Depends(require_operator_user),
    db: Session = Depends(get_db),
) -> Deadline:
    expediente = get_expediente_or_404(db, expediente_id)
    deadline = get_deadline_or_404(expediente, deadline_id)
    updates = payload.model_dump(exclude_unset=True)
    apply_partial_update(
        updates=updates,
        target=deadline,
        disallow_none_fields={"label", "due_at", "status"},
        default_on_none={"extra": {}},
    )
    deadline.updated_by_user_id = current_user.id
    record_audit_log(
        db=db,
        actor_user_id=current_user.id,
        action="update_deadline",
        entity_type="deadline",
        entity_id=deadline.id,
        expediente_id=expediente.id,
        document_id=deadline.document_id,
        route=str(request.url.path),
        method=request.method,
        details=dumps_audit_details({"updated_fields": sorted(updates.keys())}),
    )
    db.commit()
    db.refresh(deadline)
    return deadline


@router.get("/{expediente_id}/release-receipts", response_model=ReleaseReceiptListResponse)
def list_release_receipts(
    expediente_id: str,
    _: AppUser = Depends(require_read_user),
    db: Session = Depends(get_db),
) -> ReleaseReceiptListResponse:
    expediente = get_expediente_or_404(db, expediente_id)
    ordered = sorted(expediente.release_receipts, key=lambda item: item.created_at, reverse=True)
    return ReleaseReceiptListResponse(items=ordered)


@router.post(
    "/{expediente_id}/release-receipts",
    response_model=ReleaseReceiptRead,
    status_code=status.HTTP_201_CREATED,
)
def create_release_receipt(
    expediente_id: str,
    payload: ReleaseReceiptCreate,
    request: Request,
    current_user: AppUser = Depends(require_reviewer_user),
    db: Session = Depends(get_db),
) -> ReleaseReceipt:
    expediente = get_expediente_or_404(db, expediente_id)
    if payload.document_version_id is not None:
        version_stmt = (
            select(DocumentVersion)
            .join(ExpedienteDocument, DocumentVersion.document_id == ExpedienteDocument.id)
            .where(
                DocumentVersion.id == payload.document_version_id,
                ExpedienteDocument.expediente_id == expediente.id,
            )
        )
        version = db.scalar(version_stmt)
        if version is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="document_version_id does not belong to this expediente",
            )

    receipt = ReleaseReceipt(
        expediente_id=expediente.id,
        document_version_id=payload.document_version_id,
        verdict=payload.verdict,
        response_type=payload.response_type,
        policy_id=payload.policy_id,
        bundle_path=payload.bundle_path,
        artifact_path=payload.artifact_path,
        bundle_sha256=payload.bundle_sha256,
        gate_summary=payload.gate_summary,
        created_by_user_id=current_user.id,
    )
    db.add(receipt)
    db.flush()
    record_audit_log(
        db=db,
        actor_user_id=current_user.id,
        action="create_release_receipt",
        entity_type="release_receipt",
        entity_id=receipt.id,
        expediente_id=expediente.id,
        route=str(request.url.path),
        method=request.method,
        details=dumps_audit_details({"verdict": receipt.verdict, "response_type": receipt.response_type}),
    )
    db.commit()
    db.refresh(receipt)
    return receipt
