"""asignacion de revisor y comentarios

Revision ID: a1b2c3d4e5f6
Revises: f6a4d8c2b3e1
Create Date: 2026-10-09 10:00:00.000000

Notas (backlog revision humana):
- source_document.assigned_user_id: revisor asignado (SET NULL si el usuario se borra).
- document_comment: notas humanas por documento, tabla aparte de la bitacora de sistema.
  No lleva trigger append-only: no se edita/borra desde la app, pero no necesita el
  candado a nivel de base que si tiene document_event.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "f6a4d8c2b3e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "source_document",
        sa.Column("assigned_user_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_source_document_assigned_user",
        "source_document",
        "app_user",
        ["assigned_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "document_comment",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("author_id", sa.UUID(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["document_id"], ["source_document.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["author_id"], ["app_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_document_comment_document_created",
        "document_comment",
        ["document_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_document_comment_document_created", table_name="document_comment")
    op.drop_table("document_comment")
    op.drop_constraint(
        "fk_source_document_assigned_user", "source_document", type_="foreignkey"
    )
    op.drop_column("source_document", "assigned_user_id")
