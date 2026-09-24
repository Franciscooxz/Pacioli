"""cola de fallidos (dead-letter)

Revision ID: f3a9c1d20b47
Revises: 2fc47db2e269
Create Date: 2026-09-19 10:00:00.000000

Notas de revision manual (Fase A):
- Crea la tabla ingestion_failure y el tipo ENUM failure_stage.
- Los FK son nullable: un fallo muy temprano (correo que no se pudo abrir) puede no
  tener aun documento asociado.
- No lleva trigger append-only: resolved_at debe poder actualizarse para marcar un
  fallo como atendido.
- El downgrade borra explicitamente el tipo ENUM (drop_table no lo elimina).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f3a9c1d20b47"
down_revision: str | None = "2fc47db2e269"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ingestion_failure",
        sa.Column("tenant_id", sa.UUID(), nullable=True),
        sa.Column("company_id", sa.UUID(), nullable=True),
        sa.Column("document_id", sa.UUID(), nullable=True),
        sa.Column(
            "stage",
            postgresql.ENUM(
                "MAIL_EXTRACTION",
                "INGEST",
                "PARSE",
                "CLASSIFY",
                "LLM_SUGGEST",
                "POST",
                name="failure_stage",
            ),
            nullable=False,
        ),
        sa.Column("task_name", sa.String(length=200), nullable=True),
        sa.Column("source_ref", sa.String(length=200), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("raw_uri", sa.String(length=1000), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["document_id"], ["source_document.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ingestion_failure_company_created",
        "ingestion_failure",
        ["company_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_ingestion_failure_stage", "ingestion_failure", ["stage"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_ingestion_failure_stage", table_name="ingestion_failure")
    op.drop_index("ix_ingestion_failure_company_created", table_name="ingestion_failure")
    op.drop_table("ingestion_failure")
    op.execute("DROP TYPE IF EXISTS failure_stage")
