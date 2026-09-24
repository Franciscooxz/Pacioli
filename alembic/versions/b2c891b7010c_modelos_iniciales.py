"""modelos iniciales

Revision ID: b2c891b7010c
Revises:
Create Date: 2026-09-18 05:04:42.168362

Notas de revision manual (Entrega 2):
- Las columnas cifradas (odoo_password, imap_password) se declaran como LargeBinary
  (BYTEA) en la base. El cifrado/descifrado es responsabilidad de la app
  (EncryptedStr); la migracion no depende de tipos de la aplicacion.
- Se agrega a mano el trigger append-only de document_event (el autogenerate no
  detecta triggers).
- El downgrade borra explicitamente los tipos ENUM: drop_table no los elimina y sin
  esto un re-upgrade fallaria con "type already exists".
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b2c891b7010c"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Nombres de los tipos ENUM nativos, para poder borrarlos en el downgrade.
ENUM_TYPES = ("doc_type", "document_status", "document_event_type", "actor_type")


def upgrade() -> None:
    op.create_table(
        "tenant",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("nit", sa.String(length=20), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "company",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("nit", sa.String(length=20), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("odoo_url", sa.String(length=500), nullable=True),
        sa.Column("odoo_db", sa.String(length=200), nullable=True),
        sa.Column("odoo_username", sa.String(length=200), nullable=True),
        sa.Column("odoo_password", sa.LargeBinary(), nullable=True),
        sa.Column("imap_host", sa.String(length=255), nullable=True),
        sa.Column("imap_port", sa.Integer(), nullable=True),
        sa.Column("imap_username", sa.String(length=255), nullable=True),
        sa.Column("imap_password", sa.LargeBinary(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "nit", name="uq_company_tenant_nit"),
    )
    op.create_index(op.f("ix_company_tenant_id"), "company", ["tenant_id"], unique=False)
    op.create_table(
        "source_document",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("cufe", sa.String(length=96), nullable=False),
        sa.Column(
            "doc_type",
            postgresql.ENUM(
                "FACTURA_VENTA",
                "FACTURA_COMPRA",
                "NOTA_CREDITO",
                "NOTA_DEBITO",
                "DOCUMENTO_SOPORTE",
                "NOMINA_ELECTRONICA",
                name="doc_type",
            ),
            nullable=False,
        ),
        sa.Column("document_number", sa.String(length=50), nullable=False),
        sa.Column("issuer_nit", sa.String(length=20), nullable=False),
        sa.Column("issuer_name", sa.String(length=300), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("total", sa.Numeric(precision=19, scale=2), nullable=False),
        sa.Column("raw_xml_uri", sa.String(length=1000), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "RECEIVED",
                "PARSED",
                "CLASSIFIED",
                "PENDING_REVIEW",
                "POSTED",
                "PARSE_FAILED",
                "POSTING_FAILED",
                "REJECTED",
                name="document_status",
            ),
            nullable=False,
        ),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("total >= 0", name="ck_source_document_total_no_negativo"),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cufe", name="uq_source_document_cufe"),
    )
    op.create_index(
        "ix_source_document_company_issue_date",
        "source_document",
        ["company_id", "issue_date"],
        unique=False,
    )
    op.create_index(
        "ix_source_document_company_status",
        "source_document",
        ["company_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_source_document_issuer_nit", "source_document", ["issuer_nit"], unique=False
    )
    op.create_table(
        "classification_rule",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("issuer_nit", sa.String(length=20), nullable=True),
        sa.Column("match_pattern", sa.String(length=500), nullable=True),
        sa.Column("account_code", sa.String(length=20), nullable=False),
        sa.Column("cost_center", sa.String(length=50), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_classification_rule_confidence_rango",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_classification_rule_company_issuer_priority",
        "classification_rule",
        ["company_id", "issuer_nit", "priority"],
        unique=False,
    )
    op.create_table(
        "document_event",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column(
            "event_type",
            postgresql.ENUM(
                "RECEIVED",
                "PARSED",
                "PARSE_FAILED",
                "CLASSIFIED",
                "SENT_TO_REVIEW",
                "REVIEWED",
                "POSTED",
                "POSTING_FAILED",
                "REJECTED",
                "REVERSED",
                name="document_event_type",
            ),
            nullable=False,
        ),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "actor_type",
            postgresql.ENUM("SYSTEM", "RULE_ENGINE", "USER", name="actor_type"),
            nullable=False,
        ),
        sa.Column("actor_id", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["source_document.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_document_event_document_created",
        "document_event",
        ["document_id", "created_at"],
        unique=False,
    )

    # --- Trigger append-only sobre document_event (agregado a mano) ---
    # Rechaza UPDATE y DELETE a nivel de base: la bitacora es evidencia inmutable.
    op.execute(
        """
        CREATE FUNCTION contaflow_document_event_no_mutations()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'document_event es append-only: % no permitido', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_document_event_no_update_delete
        BEFORE UPDATE OR DELETE ON document_event
        FOR EACH ROW EXECUTE FUNCTION contaflow_document_event_no_mutations();
        """
    )

    op.create_table(
        "posting",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("odoo_move_id", sa.BigInteger(), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversed_by", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["source_document.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reversed_by"], ["posting.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("odoo_move_id", name="uq_posting_odoo_move_id"),
    )
    op.create_index("ix_posting_document_id", "posting", ["document_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_posting_document_id", table_name="posting")
    op.drop_table("posting")

    op.execute("DROP TRIGGER IF EXISTS trg_document_event_no_update_delete ON document_event")
    op.execute("DROP FUNCTION IF EXISTS contaflow_document_event_no_mutations()")
    op.drop_index("ix_document_event_document_created", table_name="document_event")
    op.drop_table("document_event")

    op.drop_index(
        "ix_classification_rule_company_issuer_priority", table_name="classification_rule"
    )
    op.drop_table("classification_rule")

    op.drop_index("ix_source_document_issuer_nit", table_name="source_document")
    op.drop_index("ix_source_document_company_status", table_name="source_document")
    op.drop_index("ix_source_document_company_issue_date", table_name="source_document")
    op.drop_table("source_document")

    op.drop_index(op.f("ix_company_tenant_id"), table_name="company")
    op.drop_table("company")
    op.drop_table("tenant")

    # drop_table no elimina los tipos ENUM; hay que borrarlos explicitamente.
    for enum_name in ENUM_TYPES:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
