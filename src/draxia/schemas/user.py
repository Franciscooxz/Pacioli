"""Schemas de gestion de usuarios de la firma (solo ADMIN)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from draxia.models.enums import UserRole


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: UserRole
    active: bool


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    role: UserRole = UserRole.MEMBER


class UserUpdate(BaseModel):
    role: UserRole | None = None
    active: bool | None = None
