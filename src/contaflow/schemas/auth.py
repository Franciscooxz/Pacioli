"""Schemas de entrada/salida para autenticacion."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr

from contaflow.models.enums import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105 - tipo de token OAuth, no un secreto


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: UserRole
    tenant_id: uuid.UUID
