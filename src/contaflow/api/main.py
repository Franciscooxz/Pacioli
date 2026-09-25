"""Punto de entrada de la API FastAPI."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from contaflow.api.middleware import RequestIdMiddleware
from contaflow.api.routers import auth, companies, documents, failures, health, metrics, rules
from contaflow.config import get_settings
from contaflow.core.observability import setup_observability

setup_observability()

app = FastAPI(
    title="contaflow",
    version="0.1.0",
    description=(
        "Automatizacion contable sobre Odoo para firmas colombianas. "
        "La informacion procesada no reemplaza asesoria contable profesional; "
        "la responsabilidad profesional es del contador publico."
    ),
)

app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(rules.router)
app.include_router(companies.router)
app.include_router(failures.router)
app.include_router(metrics.router)

# Recolecta metricas HTTP; el endpoint /metrics (protegido) lo sirve metrics.router.
Instrumentator().instrument(app)
