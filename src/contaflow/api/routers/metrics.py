"""Endpoint /metrics (Prometheus), con proteccion opcional por token.

Si METRICS_TOKEN esta definido, exige Authorization: Bearer <token>. Sin el, queda
abierto (comodo en dev). En produccion: define el token o restringe /metrics por red.
"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from contaflow.config import get_settings

router = APIRouter(tags=["metrics"])
_bearer = HTTPBearer(auto_error=False)


def _token_ok(provided: str, expected: str) -> bool:
    return secrets.compare_digest(provided, expected)


async def _require_metrics_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    expected = get_settings().metrics_token
    if not expected:
        return  # abierto en dev
    if credentials is None or not _token_ok(credentials.credentials, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autorizado")


@router.get("/metrics", dependencies=[Depends(_require_metrics_token)])
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
