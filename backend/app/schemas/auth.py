from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.app.models.enums import UserRole


class UserCreate(BaseModel):
    email: str
    display_name: str
    role: UserRole = UserRole.OPERATOR
    is_active: bool = True


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    role: UserRole
    is_active: bool
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime


class UserListResponse(BaseModel):
    items: list[UserRead]


class UserUpdate(BaseModel):
    display_name: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None


class ApiKeyCreate(BaseModel):
    label: str
    expires_at: datetime | None = None


class ApiKeyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    label: str
    key_prefix: str
    is_active: bool
    expires_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime


class ApiKeyUpdate(BaseModel):
    label: str | None = None
    is_active: bool | None = None
    expires_at: datetime | None = None


class ApiKeyListResponse(BaseModel):
    items: list[ApiKeyRead]


class ApiKeyWithSecret(ApiKeyRead):
    plaintext_api_key: str
