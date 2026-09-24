"""source_document: el documento electronico tal como llego.

Append-only en la practica: los cambios de estado se registran en document_event; aqui
solo se actualiza el campo status (puntero al estado actual) y updated_at. El XML crudo
vive en MinIO (raw_xml_uri), nunca en la base.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from contaflow.db import Base
from contaflow.models.base import TimestampMixin, UUIDPkMixin
from contaflow.models.enums import DocType, DocumentStatus


class SourceDocument(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "source_document"
    __table_args__ = (
        # El CUFE es la idempotencia FINAL (tras parsear): unico a nivel de base.
        # Es nullable porque en estado RECEIVED aun no lo conocemos; Postgres permite
        # multiples NULL en una columna UNIQUE.
        UniqueConstraint("cufe", name="uq_source_document_cufe"),
        # Idempotencia PRE-parseo: el mismo XML crudo no se ingesta dos veces por empresa.
        UniqueConstraint("company_id", "raw_sha256", name="uq_source_document_company_sha256"),
        # Las notas credito se modelan con doc_type, NO con montos negativos.
        # (El CHECK se cumple tambien cuando total es NULL, en estado RECEIVED.)
        CheckConstraint("total >= 0", name="ck_source_document_total_no_negativo"),
        # Indices pensados para las consultas reales del producto.
        Index("ix_source_document_company_status", "company_id", "status"),
        Index("ix_source_document_company_issue_date", "company_id", "issue_date"),
        Index("ix_source_document_issuer_nit", "issuer_nit"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant.id", ondelete="RESTRICT"),
        nullable=False,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("company.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Datos derivados del parseo: NULL mientras el documento esta en RECEIVED.
    cufe: Mapped[str | None] = mapped_column(String(96), nullable=True)
    doc_type: Mapped[DocType | None] = mapped_column(
        PGEnum(DocType, name="doc_type", values_callable=lambda e: [m.value for m in e]),
        nullable=True,
    )
    document_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    issuer_nit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    issuer_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    receiver_nit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="COP")
    # TRM (pesos por unidad de moneda extranjera) cuando currency != COP. NULL en COP.
    # Los montos se guardan en la moneda original; la conversion a COP ocurre al contabilizar.
    trm: Mapped[Decimal | None] = mapped_column(Numeric(19, 6), nullable=True)

    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    total_tax: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    total_withholding: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    total: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)

    # Propuesta de clasificacion (motor de reglas). Se llena al pasar a CLASSIFIED
    # o PENDING_REVIEW; la correccion humana la sobreescribe mas adelante.
    proposed_account_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    proposed_cost_center: Mapped[str | None] = mapped_column(String(50), nullable=True)
    classification_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    classification_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classification_rule.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Evidencia y trazabilidad: siempre presentes desde RECEIVED.
    raw_xml_uri: Mapped[str] = mapped_column(String(1000), nullable=False)
    # SHA-256 del XML crudo tal como llego; clave de idempotencia pre-parseo.
    raw_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    # Referencia al origen (p. ej. UID del correo IMAP), util para auditar.
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[DocumentStatus] = mapped_column(
        PGEnum(
            DocumentStatus,
            name="document_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=DocumentStatus.RECEIVED,
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
