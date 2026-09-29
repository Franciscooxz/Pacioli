"""Modelos SQLAlchemy. Importar todo aqui para que Base.metadata los registre
(necesario para el autogenerate de Alembic y para create_all en tests).
"""

from __future__ import annotations

from draxia.models.company import Company
from draxia.models.document_event import DocumentEvent
from draxia.models.document_line import DocumentLine
from draxia.models.document_tax import DocumentTax
from draxia.models.ingestion_failure import IngestionFailure
from draxia.models.posting import Posting
from draxia.models.rule import ClassificationRule
from draxia.models.source_document import SourceDocument
from draxia.models.tenant import Tenant
from draxia.models.user import User

__all__ = [
    "Company",
    "ClassificationRule",
    "DocumentEvent",
    "DocumentLine",
    "DocumentTax",
    "IngestionFailure",
    "Posting",
    "SourceDocument",
    "Tenant",
    "User",
]
