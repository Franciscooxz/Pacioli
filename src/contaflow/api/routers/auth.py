"""Endpoints de autenticacion: login, refresh y perfil del usuario actual."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from contaflow.api.deps import get_current_user
from contaflow.core.auth import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from contaflow.db import get_async_session
from contaflow.models.user import User
from contaflow.schemas.auth import LoginRequest, RefreshRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _tokens_for(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id, user.tenant_id, user.role.value),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_async_session),
) -> TokenResponse:
    user = await session.scalar(select(User).where(User.email == body.email))
    # Verificamos el hash siempre que exista para no filtrar si el email existe.
    if user is None or not user.active or not verify_password(user.password_hash, body.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contrasena incorrectos",
        )
    return _tokens_for(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    session: AsyncSession = Depends(get_async_session),
) -> TokenResponse:
    try:
        payload = decode_token(body.refresh_token, "refresh")
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token invalido"
        ) from exc
    subject = payload.get("sub")
    user = await session.get(User, uuid.UUID(subject)) if isinstance(subject, str) else None
    if user is None or not user.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no valido")
    return _tokens_for(user)


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
