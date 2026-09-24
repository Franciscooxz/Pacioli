"""Almacenamiento del XML/PDF crudo en MinIO (S3-compatible).

El crudo se guarda SIEMPRE, tal cual llego, antes de parsearlo: es la evidencia ante
una auditoria de la DIAN. La interfaz RawStorage permite inyectar un doble en tests.
"""

from __future__ import annotations

import io
from pathlib import PurePosixPath
from typing import Protocol, runtime_checkable

from minio import Minio

from contaflow.config import get_settings

_URI_SCHEME = "s3://"


def get_minio_client() -> Minio:
    """Construye un cliente MinIO a partir de la configuracion."""
    settings = get_settings()
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_root_user,
        secret_key=settings.minio_root_password,
        secure=settings.minio_secure,
    )


def _safe_name(filename: str) -> str:
    """Evita path traversal: nos quedamos solo con el nombre base."""
    base = PurePosixPath(filename.replace("\\", "/")).name
    return base or "documento.xml"


@runtime_checkable
class RawStorage(Protocol):
    """Contrato minimo de almacenamiento del crudo."""

    def put_raw(self, company_id: str, sha256: str, filename: str, data: bytes) -> str:
        """Guarda el crudo y devuelve su URI. Idempotente por (company, sha, nombre)."""
        ...

    def get_raw(self, uri: str) -> bytes:
        """Recupera el crudo por su URI."""
        ...


class MinioStorage:
    """Implementacion de RawStorage sobre MinIO."""

    def __init__(self, client: Minio | None = None, bucket: str | None = None) -> None:
        self._client = client or get_minio_client()
        self._bucket = bucket or get_settings().minio_bucket

    def ensure_bucket(self) -> None:
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)

    def put_raw(self, company_id: str, sha256: str, filename: str, data: bytes) -> str:
        self.ensure_bucket()
        key = f"{company_id}/{sha256}/{_safe_name(filename)}"
        self._client.put_object(
            self._bucket,
            key,
            io.BytesIO(data),
            length=len(data),
            content_type="application/xml",
        )
        return f"{_URI_SCHEME}{self._bucket}/{key}"

    def get_raw(self, uri: str) -> bytes:
        if not uri.startswith(_URI_SCHEME):
            raise ValueError(f"URI de almacenamiento invalida: {uri!r}")
        bucket, _, key = uri[len(_URI_SCHEME) :].partition("/")
        response = self._client.get_object(bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()
