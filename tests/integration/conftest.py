"""Fixtures de integracion: una PostgreSQL efimera por modulo via testcontainers.

Sobre esa base se aplica la migracion de Alembic real (no create_all), de modo que
los tests validan tambien la migracion y el trigger append-only.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import httpx
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from contaflow.db import Base, get_async_session

try:  # testcontainers >= 4.9 movio los modulos a .community
    from testcontainers.community.postgres import PostgresContainer
except ImportError:  # pragma: no cover - compatibilidad con versiones previas
    from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="module")
def pg_engine() -> Iterator[Engine]:
    with PostgresContainer("postgres:16", driver="psycopg") as postgres:
        url = postgres.get_connection_url()  # postgresql+psycopg://...

        cfg = Config("alembic.ini")
        cfg.set_main_option("script_location", "alembic")
        cfg.set_main_option("sqlalchemy.url", url)
        command.upgrade(cfg, "head")

        engine = create_engine(url, future=True)
        try:
            yield engine
        finally:
            engine.dispose()


@pytest.fixture(autouse=True)
def _clean_tables(pg_engine: Engine) -> Iterator[None]:
    """Aisla cada test: vacia las tablas al terminar.

    TRUNCATE no dispara el trigger append-only de document_event (ese es a nivel de
    fila para UPDATE/DELETE, no para TRUNCATE), asi que podemos limpiar sin pelearnos
    con la inmutabilidad.
    """
    yield
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with pg_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest_asyncio.fixture
async def api_client(pg_engine: Engine) -> AsyncIterator[httpx.AsyncClient]:
    """Cliente HTTP async contra la app, con la sesion apuntada a la base efimera."""
    from contaflow.api.main import app

    async_url = pg_engine.url.set(drivername="postgresql+asyncpg")
    engine = create_async_engine(async_url)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_session() -> AsyncIterator[object]:
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_async_session] = _override_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
    await engine.dispose()
