"""Modelos SQLAlchemy. Importar todo aqui para que Base.metadata los registre
(necesario para el autogenerate de Alembic y para create_all en tests).
"""

from __future__ import annotations

from contaflow.models.company import Company
from contaflow.models.document_event import DocumentEvent
from contaflow.models.document_line import DocumentLine
from contaflow.models.document_tax import DocumentTax
from contaflow.models.ingestion_failure import IngestionFailure
from contaflow.models.posting import Posting
from contaflow.models.rule import ClassificationRule
from contaflow.models.source_document import SourceDocument
from contaflow.models.tenant import Tenant
from contaflow.models.user import User

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
