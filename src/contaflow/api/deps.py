"""Dependencias de la API, incluidas las sondas de conectividad del healthcheck.

Cada sonda se expone como dependencia FastAPI para poder sobreescribirla en tests
(app.dependency_overrides) sin necesitar la infraestructura real levantada.
"""

from __future__ import annotations

import asyncio
import uuid

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from contaflow.config import get_settings
from contaflow.core.auth import TokenError, decode_token
from contaflow.db import async_engine, get_async_session
from contaflow.ingestion.storage import get_minio_client
from contaflow.models.user import User

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_async_session),
) -> User:
    """Valida el access token y devuelve el usuario autenticado."""
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales invalidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise invalid
    try:
        payload = decode_token(credentials.credentials, "access")
    except TokenError as exc:
        raise invalid from exc

    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise invalid
    user = await session.get(User, uuid.UUID(subject))
    if user is None or not user.active:
        raise invalid
    return user


async def check_postgres() -> bool:
    """Verifica conectividad real con Postgres ejecutando un SELECT 1."""
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 - la sonda reporta estado, no propaga
        return False


async def check_redis() -> bool:
    """Verifica conectividad real con Redis via PING."""
    settings = get_settings()
    client: aioredis.Redis = aioredis.from_url(settings.redis_url)
    try:
        return bool(await client.ping())
    except Exception:  # noqa: BLE001
        return False
    finally:
        await client.aclose()


async def check_minio() -> bool:
    """Verifica conectividad real con MinIO listando buckets.

    El cliente de minio es sincrono; lo corremos en un hilo para no bloquear el
    event loop de la API.
    """
    try:
        client = get_minio_client()
        await asyncio.to_thread(client.list_buckets)
        return True
    except Exception:  # noqa: BLE001
        return False
