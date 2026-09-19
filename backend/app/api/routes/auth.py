from __future__ import annotations

from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.audit import dumps_audit_details, record_audit_log
from backend.app.db import get_db
from backend.app.deps import get_current_user, require_admin_user
from backend.app.models import ApiKey, AppUser, AuditLog
from backend.app.schemas.auth import (
    ApiKeyCreate,
    ApiKeyListResponse,
    ApiKeyRead,
    ApiKeyUpdate,
    ApiKeyWithSecret,
    UserCreate,
    UserListResponse,
    UserRead,
    UserUpdate,
)
from backend.app.schemas.expedientes import AuditLogListResponse
from backend.app.security import generate_api_key


router = APIRouter(tags=["auth"])


def parse_uuid_or_404(value: str, detail: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc


def parse_user_id_or_404(user_id: str) -> uuid.UUID:
    return parse_uuid_or_404(user_id, "User not found")


def parse_api_key_id_or_404(api_key_id: str) -> uuid.UUID:
    return parse_uuid_or_404(api_key_id, "API key not found")


def get_user_or_404(db: Session, user_id: str) -> AppUser:
    user = db.scalar(select(AppUser).where(AppUser.id == parse_user_id_or_404(user_id)))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def get_api_key_for_user_or_404(db: Session, user_id: uuid.UUID, api_key_id: str) -> ApiKey:
    api_key = db.scalar(
        select(ApiKey).where(ApiKey.user_id == user_id, ApiKey.id == parse_api_key_id_or_404(api_key_id))
    )
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    return api_key


@router.get("/auth/me", response_model=UserRead)
def get_me(current_user: AppUser = Depends(get_current_user)) -> AppUser:
    return current_user


@router.get("/admin/users", response_model=UserListResponse)
def list_users(
    _: AppUser = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> UserListResponse:
    items = list(db.scalars(select(AppUser).order_by(AppUser.created_at.desc())).all())
    return UserListResponse(items=items)


@router.post("/admin/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    request: Request,
    admin_user: AppUser = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> AppUser:
    existing = db.scalar(select(AppUser).where(AppUser.email == payload.email.strip().lower()))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User email already exists")
    user = AppUser(
        email=payload.email.strip().lower(),
        display_name=payload.display_name.strip(),
        role=payload.role,
        is_active=payload.is_active,
    )
    db.add(user)
    db.flush()
    record_audit_log(
        db=db,
        actor_user_id=admin_user.id,
        action="create_user",
        entity_type="app_user",
        entity_id=user.id,
        route=str(request.url.path),
        method=request.method,
        details=dumps_audit_details({"email": user.email, "role": user.role}),
        extra={"created_user_id": str(user.id)},
    )
    db.commit()
    db.refresh(user)
    return user


@router.patch("/admin/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: str,
    payload: UserUpdate,
    request: Request,
    admin_user: AppUser = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> AppUser:
    user = get_user_or_404(db, user_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return user
    if user.id == admin_user.id and updates.get("is_active") is False:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Admin cannot deactivate the current user")
    if "display_name" in updates and isinstance(updates["display_name"], str):
        updates["display_name"] = updates["display_name"].strip()
    for field_name, value in updates.items():
        setattr(user, field_name, value)
    db.flush()
    record_audit_log(
        db=db,
        actor_user_id=admin_user.id,
        action="update_user",
        entity_type="app_user",
        entity_id=user.id,
        route=str(request.url.path),
        method=request.method,
        details=dumps_audit_details({"updated_fields": sorted(updates.keys())}),
        extra={"target_user_id": str(user.id)},
    )
    db.commit()
    db.refresh(user)
    return user


@router.post("/admin/users/{user_id}/api-keys", response_model=ApiKeyWithSecret, status_code=status.HTTP_201_CREATED)
def create_api_key(
    user_id: str,
    payload: ApiKeyCreate,
    request: Request,
    admin_user: AppUser = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> ApiKeyWithSecret:
    user = get_user_or_404(db, user_id)
    plaintext_api_key, key_prefix, secret_hash = generate_api_key()
    api_key = ApiKey(
        user_id=user.id,
        label=payload.label.strip(),
        key_prefix=key_prefix,
        secret_hash=secret_hash,
        expires_at=payload.expires_at,
    )
    db.add(api_key)
    db.flush()
    record_audit_log(
        db=db,
        actor_user_id=admin_user.id,
        action="create_api_key",
        entity_type="api_key",
        entity_id=api_key.id,
        route=str(request.url.path),
        method=request.method,
        details=dumps_audit_details({"user_id": str(user.id), "label": api_key.label}),
        extra={"target_user_id": str(user.id), "key_prefix": key_prefix},
    )
    db.commit()
    db.refresh(api_key)
    return ApiKeyWithSecret.model_validate(
        {
            "id": api_key.id,
            "user_id": api_key.user_id,
            "label": api_key.label,
            "key_prefix": api_key.key_prefix,
            "is_active": api_key.is_active,
            "expires_at": api_key.expires_at,
            "last_used_at": api_key.last_used_at,
            "created_at": api_key.created_at,
            "plaintext_api_key": plaintext_api_key,
        }
    )


@router.get("/admin/users/{user_id}/api-keys", response_model=ApiKeyListResponse)
def list_api_keys(
    user_id: str,
    _: AppUser = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> ApiKeyListResponse:
    user = get_user_or_404(db, user_id)
    items = list(db.scalars(select(ApiKey).where(ApiKey.user_id == user.id).order_by(ApiKey.created_at.desc())).all())
    return ApiKeyListResponse(items=items)


@router.patch("/admin/users/{user_id}/api-keys/{api_key_id}", response_model=ApiKeyRead)
def update_api_key(
    user_id: str,
    api_key_id: str,
    payload: ApiKeyUpdate,
    request: Request,
    admin_user: AppUser = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> ApiKey:
    user = get_user_or_404(db, user_id)
    api_key = get_api_key_for_user_or_404(db, user.id, api_key_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return api_key
    if "label" in updates and isinstance(updates["label"], str):
        updates["label"] = updates["label"].strip()
    for field_name, value in updates.items():
        setattr(api_key, field_name, value)
    db.flush()
    record_audit_log(
        db=db,
        actor_user_id=admin_user.id,
        action="update_api_key",
        entity_type="api_key",
        entity_id=api_key.id,
        route=str(request.url.path),
        method=request.method,
        details=dumps_audit_details({"updated_fields": sorted(updates.keys())}),
        extra={"target_user_id": str(user.id), "key_prefix": api_key.key_prefix},
    )
    db.commit()
    db.refresh(api_key)
    return api_key


@router.get("/admin/audit-logs", response_model=AuditLogListResponse)
def list_audit_logs(
    actor_user_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    expediente_id: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    _: AppUser = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> AuditLogListResponse:
    if not isinstance(created_from, datetime):
        created_from = None
    if not isinstance(created_to, datetime):
        created_to = None
    stmt = select(AuditLog)
    if actor_user_id:
        stmt = stmt.where(AuditLog.actor_user_id == parse_user_id_or_404(actor_user_id))
    if action:
        stmt = stmt.where(AuditLog.action == action.strip())
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type.strip())
    if expediente_id:
        stmt = stmt.where(AuditLog.expediente_id == parse_uuid_or_404(expediente_id, "Expediente not found"))
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == parse_uuid_or_404(entity_id, "Entity not found"))
    if created_from:
        stmt = stmt.where(AuditLog.created_at >= created_from)
    if created_to:
        stmt = stmt.where(AuditLog.created_at <= created_to)
    stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit)
    return AuditLogListResponse(items=list(db.scalars(stmt).all()))
