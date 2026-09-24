"""Entorno de migraciones Alembic.

Usa el engine SINCRONO (psycopg) derivado de Settings, no la URL async de la API.
target_metadata es la Base declarativa de SQLAlchemy; a medida que agreguemos
modelos (Entrega 2) el autogenerate los detectara.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Importar los modelos registra sus tablas en Base.metadata (para el autogenerate).
import contaflow.models  # noqa: E402,F401
from contaflow.config import get_settings
from contaflow.db import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# La URL puede venir ya fijada por quien invoca (p. ej. los tests con testcontainers
# hacen config.set_main_option antes de correr command.upgrade). Si no, la tomamos de
# la configuracion de la app.
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", get_settings().sync_database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
