"""Autenticacion: hashing de contrasenas (argon2) y tokens JWT (access + refresh).

El access token es corto (minutos) y viaja en cada request; el refresh token dura dias
y solo sirve para emitir nuevos access tokens. El payload lleva el tenant y el rol para
no tener que consultarlos en cada request.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error

from contaflow.config import get_settings

_hasher = PasswordHasher()

TokenType = Literal["access", "refresh"]


class TokenError(Exception):
    """El token es invalido, expiro o no es del tipo esperado."""


def hash_password(plaintext: str) -> str:
    return _hasher.hash(plaintext)


def verify_password(password_hash: str, plaintext: str) -> bool:
    try:
        return _hasher.verify(password_hash, plaintext)
    except Argon2Error:
        return False


def _create_token(subject: str, token_type: TokenType, expires: timedelta, **extra: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires,
        **extra,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: uuid.UUID, tenant_id: uuid.UUID, role: str) -> str:
    settings = get_settings()
    return _create_token(
        str(user_id),
        "access",
        timedelta(minutes=settings.access_token_expire_minutes),
        tid=str(tenant_id),
        role=role,
    )


def create_refresh_token(user_id: uuid.UUID) -> str:
    settings = get_settings()
    return _create_token(
        str(user_id),
        "refresh",
        timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError as exc:
        raise TokenError(f"Token invalido: {exc}") from exc
    if payload.get("type") != expected_type:
        raise TokenError(f"Se esperaba un token '{expected_type}'")
    return payload
