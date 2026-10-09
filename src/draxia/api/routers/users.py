"""Gestion de usuarios de la firma. Solo ADMIN; aislada por tenant."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from draxia.api.deps import get_current_user, require_admin
from draxia.core.auth import hash_password
from draxia.db import get_async_session
from draxia.models.user import User
from draxia.schemas.user import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/assignable", response_model=list[UserOut])
async def list_assignable_users(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[User]:
    """Usuarios activos del tenant, para el selector de revisor. No requiere ser admin."""
    result = await session.scalars(
        select(User)
        .where(User.tenant_id == current_user.tenant_id, User.active.is_(True))
        .order_by(User.email)
    )
    return list(result)


@router.get("", response_model=list[UserOut])
async def list_users(
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
) -> list[User]:
    result = await session.scalars(
        select(User).where(User.tenant_id == current_user.tenant_id).order_by(User.email)
    )
    return list(result)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
) -> User:
    user = User(
        tenant_id=current_user.tenant_id,
        email=str(body.email),
        password_hash=hash_password(body.password),
        role=body.role,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Ya existe un usuario con ese correo"
        ) from exc
    await session.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
) -> User:
    # Un admin no puede degradarse ni desactivarse a si mismo (evita quedar bloqueado).
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No puedes cambiar tu propio rol o estado",
        )
    user = await session.get(User, user_id)
    if user is None or user.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await session.commit()
    await session.refresh(user)
    return user
