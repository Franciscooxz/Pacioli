"""Enumeraciones del dominio, mapeadas a tipos ENUM nativos de PostgreSQL.

Se declaran como StrEnum con name == value para que el valor almacenado en la base
sea legible (p. ej. 'FACTURA_VENTA') y estable frente a refactors de codigo.
"""

from __future__ import annotations

from enum import StrEnum


class DocType(StrEnum):
    """Tipos de documento electronico que maneja el sistema (contexto DIAN)."""

    FACTURA_VENTA = "FACTURA_VENTA"
    FACTURA_COMPRA = "FACTURA_COMPRA"
    NOTA_CREDITO = "NOTA_CREDITO"
    NOTA_DEBITO = "NOTA_DEBITO"
    DOCUMENTO_SOPORTE = "DOCUMENTO_SOPORTE"
    NOMINA_ELECTRONICA = "NOMINA_ELECTRONICA"


class DocumentStatus(StrEnum):
    """Estados de source_document.

    Flujo feliz: RECEIVED -> PARSED -> CLASSIFIED -> PENDING_REVIEW -> POSTED.
    Ramas de error: PARSE_FAILED, POSTING_FAILED, REJECTED.
    """

    RECEIVED = "RECEIVED"
    PARSED = "PARSED"
    CLASSIFIED = "CLASSIFIED"
    PENDING_REVIEW = "PENDING_REVIEW"
    POSTED = "POSTED"
    PARSE_FAILED = "PARSE_FAILED"
    POSTING_FAILED = "POSTING_FAILED"
    REJECTED = "REJECTED"


class DocumentEventType(StrEnum):
    """Tipos de evento en la bitacora append-only document_event."""

    RECEIVED = "RECEIVED"
    PARSED = "PARSED"
    PARSE_FAILED = "PARSE_FAILED"
    CLASSIFIED = "CLASSIFIED"
    SENT_TO_REVIEW = "SENT_TO_REVIEW"
    REVIEWED = "REVIEWED"
    POSTED = "POSTED"
    POSTING_FAILED = "POSTING_FAILED"
    REJECTED = "REJECTED"
    REVERSED = "REVERSED"


class TaxCategory(StrEnum):
    """Categoria de un impuesto o retencion (contexto tributario colombiano)."""

    IVA = "IVA"
    RETEFUENTE = "RETEFUENTE"
    RETEIVA = "RETEIVA"
    RETEICA = "RETEICA"
    OTRO = "OTRO"


class FailureStage(StrEnum):
    """Etapa del pipeline donde un correo o una tarea fallo de forma terminal.

    Un fallo terminal es el que ya no se reintenta: agoto los reintentos de Celery, o es
    un error de datos que no tiene sentido repetir (un correo que no se puede abrir).
    """

    MAIL_EXTRACTION = "MAIL_EXTRACTION"
    INGEST = "INGEST"
    PARSE = "PARSE"
    CLASSIFY = "CLASSIFY"
    LLM_SUGGEST = "LLM_SUGGEST"
    POST = "POST"


class UserRole(StrEnum):
    """Rol de un usuario dentro de su firma contable (tenant)."""

    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


class ActorType(StrEnum):
    """Quien origino un evento.

    Para USER, el identificador concreto va en document_event.actor_id (aun no
    tenemos tabla de usuarios; se guarda como texto hasta que exista).
    """

    SYSTEM = "SYSTEM"
    RULE_ENGINE = "RULE_ENGINE"
    USER = "USER"
