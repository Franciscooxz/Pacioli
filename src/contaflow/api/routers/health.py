"""Endpoint GET /health: estado real de Postgres, Redis y MinIO.

Devuelve 200 si todo esta arriba y 503 si algun servicio esta caido, con el
detalle por servicio en el cuerpo.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from contaflow.api.deps import check_minio, check_postgres, check_redis

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(
    response: Response,
    postgres_up: bool = Depends(check_postgres),
    redis_up: bool = Depends(check_redis),
    minio_up: bool = Depends(check_minio),
) -> dict[str, object]:
    services = {
        "postgres": postgres_up,
        "redis": redis_up,
        "minio": minio_up,
    }
    all_up = all(services.values())
    response.status_code = 200 if all_up else 503
    return {
        "status": "ok" if all_up else "degraded",
        "services": {name: ("up" if up else "down") for name, up in services.items()},
    }
