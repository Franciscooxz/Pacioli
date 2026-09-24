"""Configuracion de SQLAlchemy 2.0.

Decision A1 (aprobada): la API usa un engine ASYNC (asyncpg) y Celery/Alembic un
engine SYNC (psycopg). Cada mundo usa su herramienta natural. Ambos comparten la
misma URL logica; solo cambia el driver (ver Settings.sync_database_url).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from contaflow.config import get_settings


class Base(DeclarativeBase):
    """Base declarativa comun a todos los modelos ORM."""


# --- Engine async (API) ---
_settings = get_settings()

async_engine: AsyncEngine = create_async_engine(
    _settings.database_url,
    pool_pre_ping=True,
    future=True,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=async_engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_async_session() -> AsyncIterator[AsyncSession]:
    """Dependencia FastAPI: entrega una AsyncSession y la cierra al terminar."""
    async with AsyncSessionLocal() as session:
        yield session


# --- Engine sync (Celery / scripts) ---
sync_engine = create_engine(
    _settings.sync_database_url,
    pool_pre_ping=True,
    future=True,
)

SyncSessionLocal: sessionmaker[Session] = sessionmaker(
    bind=sync_engine,
    expire_on_commit=False,
    autoflush=False,
)
