"""Configuracion global de pytest.

Fijamos variables de entorno ANTES de importar cualquier modulo de contaflow,
porque Settings las exige al construirse (y get_settings esta cacheado).
"""

from __future__ import annotations

import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://contaflow:test@localhost:5432/contaflow",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")
os.environ.setdefault("MINIO_ROOT_USER", "minioadmin")
os.environ.setdefault("MINIO_ROOT_PASSWORD", "test")
os.environ.setdefault("MINIO_BUCKET", "contaflow-raw")
os.environ.setdefault("ENVIRONMENT", "test")
# Clave Fernet valida (32 bytes base64 urlsafe) para poder cifrar en tests.
os.environ.setdefault("FERNET_KEY", "ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg=")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-no-usar-en-produccion")
