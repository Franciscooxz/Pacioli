"""Tareas Celery de ingesta. Son envoltorios delgados sobre ingestion.pipeline.

Toda ingesta, parseo y llamada a Odoo corre aqui, nunca en un request HTTP. Los
errores transitorios (IMAP/MinIO/BD caidos) se reintentan con backoff exponencial;
los de datos (XML corrupto) NO se reintentan: el pipeline los marca PARSE_FAILED.
"""

from __future__ import annotations

import logging
import uuid

from minio.error import S3Error
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from contaflow.classification.llm_classifier import ClaudeAccountSuggester, suggest_for_document
from contaflow.classification.rule_engine import classify_document
from contaflow.config import get_settings
from contaflow.core.exceptions import OdooConnectionError
from contaflow.db import SyncSessionLocal
from contaflow.ingestion.imap_reader import ImapMailbox
from contaflow.ingestion.pipeline import parse_source_document, process_mailbox
from contaflow.ingestion.storage import MinioStorage
from contaflow.models.company import Company
from contaflow.models.enums import DocumentStatus
from contaflow.models.source_document import SourceDocument
from contaflow.odoo.client import XmlRpcOdooClient
from contaflow.odoo.posting import post_document
from contaflow.workers.celery_app import celery_app
from contaflow.workers.dead_letter import DeadLetterTask

logger = logging.getLogger(__name__)

# Errores transitorios: vale la pena reintentar (infra caida, no datos malos).
_TRANSIENT = (OSError, OperationalError, S3Error, OdooConnectionError)


@celery_app.task(name="contaflow.workers.tasks.poll_mailboxes")  # type: ignore[untyped-decorator]
def poll_mailboxes() -> int:
    """Tarea periodica (Celery Beat): encola la ingesta de cada empresa activa."""
    with SyncSessionLocal() as session:
        company_ids = list(session.scalars(select(Company.id).where(Company.active.is_(True))))
    for company_id in company_ids:
        ingest_company.delay(str(company_id))
    logger.info("poll_mailboxes: %d empresas encoladas", len(company_ids))
    return len(company_ids)


@celery_app.task(  # type: ignore[untyped-decorator]
    name="contaflow.workers.tasks.ingest_company",
    base=DeadLetterTask,
    autoretry_for=_TRANSIENT,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def ingest_company(company_id: str) -> int:
    """Conecta al buzon de una empresa e ingesta los adjuntos XML no leidos."""
    with SyncSessionLocal() as session:
        company = session.get(Company, uuid.UUID(company_id))
        if company is None:
            logger.warning("ingest_company: empresa %s no existe", company_id)
            return 0
        if not (company.imap_host and company.imap_username and company.imap_password):
            logger.warning("ingest_company: empresa %s sin credenciales IMAP", company_id)
            return 0

        storage = MinioStorage()
        mailbox = ImapMailbox(
            host=company.imap_host,
            port=company.imap_port or 993,
            username=company.imap_username,
            password=company.imap_password,
        )
        try:
            created = process_mailbox(
                session,
                storage,
                mailbox,
                company,
                enqueue_parse=lambda doc_id: parse_document.delay(str(doc_id)),
            )
        finally:
            mailbox.close()
    logger.info("ingest_company %s: %d documentos nuevos", company_id, len(created))
    return len(created)


@celery_app.task(  # type: ignore[untyped-decorator]
    name="contaflow.workers.tasks.parse_document",
    base=DeadLetterTask,
    autoretry_for=_TRANSIENT,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def parse_document(document_id: str) -> str:
    """Parsea un documento en RECEIVED y, si queda PARSED, encola su clasificacion."""
    with SyncSessionLocal() as session:
        storage = MinioStorage()
        status = parse_source_document(session, storage, uuid.UUID(document_id))
    if status is DocumentStatus.PARSED:
        classify_document_task.delay(document_id)
    return status.value


@celery_app.task(  # type: ignore[untyped-decorator]
    name="contaflow.workers.tasks.classify_document",
    base=DeadLetterTask,
    autoretry_for=_TRANSIENT,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def classify_document_task(document_id: str) -> str:
    """Clasifica un documento PARSED con el motor de reglas."""
    settings = get_settings()
    with SyncSessionLocal() as session:
        status = classify_document(session, uuid.UUID(document_id))
    # Auto-posting opcional (por defecto desactivado: control humano).
    if status is DocumentStatus.CLASSIFIED and settings.auto_post:
        post_document_task.delay(document_id)
    # Residuo ambiguo -> sugerencia LLM (si hay API key configurada).
    elif status is DocumentStatus.PENDING_REVIEW and settings.anthropic_api_key:
        llm_suggest_task.delay(document_id)
    return status.value


@celery_app.task(  # type: ignore[untyped-decorator]
    name="contaflow.workers.tasks.llm_suggest",
    base=DeadLetterTask,
    autoretry_for=_TRANSIENT,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def llm_suggest_task(document_id: str) -> str:
    """Pide una sugerencia de cuenta al LLM para un documento en PENDING_REVIEW."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        return "LLM_DISABLED"
    suggester = ClaudeAccountSuggester(settings.anthropic_api_key, settings.llm_model)
    with SyncSessionLocal() as session:
        status = suggest_for_document(session, suggester, uuid.UUID(document_id))
    return status.value


@celery_app.task(  # type: ignore[untyped-decorator]
    name="contaflow.workers.tasks.post_document",
    base=DeadLetterTask,
    autoretry_for=_TRANSIENT,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def post_document_task(document_id: str) -> str:
    """Contabiliza un documento CLASSIFIED en Odoo (usa las credenciales de la empresa)."""
    with SyncSessionLocal() as session:
        doc = session.get(SourceDocument, uuid.UUID(document_id))
        if doc is None:
            logger.warning("post_document: documento %s no existe", document_id)
            return "NOT_FOUND"
        company = session.get(Company, doc.company_id)
        if company is None or not (
            company.odoo_url and company.odoo_db and company.odoo_username and company.odoo_password
        ):
            logger.warning("post_document: empresa sin credenciales de Odoo (%s)", document_id)
            return doc.status.value
        client = XmlRpcOdooClient(
            company.odoo_url, company.odoo_db, company.odoo_username, company.odoo_password
        )
        status = post_document(session, client, uuid.UUID(document_id))
    return status.value
