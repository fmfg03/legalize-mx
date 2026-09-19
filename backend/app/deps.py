from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.models import ApiKey, AppUser
from backend.app.models.enums import UserRole
from backend.app.security import hash_api_key


def _extract_api_key(authorization: str | None, x_api_key: str | None) -> str:
    if x_api_key and x_api_key.strip():
        return x_api_key.strip()
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        if token:
            return token
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> AppUser:
    raw_key = _extract_api_key(authorization=authorization, x_api_key=x_api_key)
    stmt = select(ApiKey).join(AppUser).where(ApiKey.secret_hash == hash_api_key(raw_key))
    api_key = db.scalar(stmt)
    now = datetime.now(timezone.utc)
    if api_key is None or not api_key.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    if api_key.expires_at is not None:
        expiry_now = now if api_key.expires_at.tzinfo is not None else now.replace(tzinfo=None)
        if api_key.expires_at <= expiry_now:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key expired")
    user = api_key.user
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")
    api_key.last_used_at = now
    user.last_seen_at = now
    db.flush()
    return user


def require_admin_user(current_user: AppUser = Depends(get_current_user)) -> AppUser:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return current_user


def require_read_user(current_user: AppUser = Depends(get_current_user)) -> AppUser:
    return current_user


def require_operator_user(current_user: AppUser = Depends(get_current_user)) -> AppUser:
    if current_user.role not in {UserRole.ADMIN, UserRole.OPERATOR}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operator role required")
    return current_user


def require_reviewer_user(current_user: AppUser = Depends(get_current_user)) -> AppUser:
    if current_user.role not in {UserRole.ADMIN, UserRole.REVIEWER}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Reviewer role required")
    return current_user


def require_audit_user(current_user: AppUser = Depends(get_current_user)) -> AppUser:
    if current_user.role not in {UserRole.ADMIN, UserRole.OPERATOR, UserRole.REVIEWER}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Audit access requires operator or reviewer role")
    return current_user
