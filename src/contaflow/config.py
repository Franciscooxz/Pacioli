"""Configuracion de la aplicacion via Pydantic Settings.

Todas las opciones se leen de variables de entorno (o de un archivo .env en
desarrollo). No hay valores por defecto para secretos: si falta uno, la app no
arranca, que es justo lo que queremos en produccion.
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Base de datos (nuestra) ---
    # URL async con driver asyncpg, la usa FastAPI.
    database_url: str

    # --- Redis ---
    redis_url: str

    # --- MinIO ---
    minio_endpoint: str
    minio_root_user: str
    minio_root_password: str
    minio_secure: bool = False
    minio_bucket: str = "contaflow-raw"

    # --- Cifrado en reposo (Fernet) ---
    # Clave urlsafe base64 de 32 bytes. Generar con:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    fernet_key: str
    # Claves viejas (separadas por coma) que aun deben poder descifrar, para rotacion.
    fernet_keys_secondary: str | None = None

    # --- Autenticacion (JWT) ---
    # Secreto para firmar los tokens. Generar con:
    #   python -c "import secrets; print(secrets.token_urlsafe(48))"
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # --- Observabilidad ---
    log_level: str = "INFO"
    log_json: bool = True
    # Si esta vacio, Sentry queda desactivado (no-op).
    sentry_dsn: str | None = None
    # Si se define, /metrics exige Authorization: Bearer <token>. Vacio = abierto (dev).
    metrics_token: str | None = None

    # --- Clasificacion ---
    # Confianza minima para clasificar automaticamente; por debajo va a revision humana.
    classification_confidence_threshold: Decimal = Decimal("0.80")

    # --- Posting a Odoo ---
    # Si es True, un documento CLASSIFIED se contabiliza sin intervencion humana.
    auto_post: bool = False

    # --- LLM (residuo ambiguo) ---
    # Si esta vacio, el paso LLM queda desactivado (no-op). El LLM solo sugiere; el
    # documento sigue en PENDING_REVIEW para que un humano confirme.
    anthropic_api_key: str | None = None
    llm_model: str = "claude-opus-5"

    # --- CORS (frontend) ---
    # Origenes permitidos para el navegador, separados por coma.
    cors_origins: str = "http://localhost:3000"

    # --- General ---
    environment: str = "development"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def sync_database_url(self) -> str:
        """URL con driver sincrono (psycopg), para Celery y Alembic.

        Celery 5 es sincrono; mezclar un engine async dentro de sus tareas es una
        fuente clasica de bugs de event loop. Derivamos la URL sync de la async
        para no duplicar credenciales.
        """
        return self.database_url.replace("+asyncpg", "+psycopg")


@lru_cache
def get_settings() -> Settings:
    """Instancia unica de Settings (cacheada)."""
    return Settings()  # los valores se cargan del entorno / .env
