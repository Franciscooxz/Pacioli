"""user: una persona que usa el sistema, perteneciente a una firma (tenant).

Decision aprobada: un usuario pertenece a un solo tenant (FK tenant_id). El aislamiento
multi-tenant se deriva del usuario autenticado. La tabla se llama app_user porque
"user" es palabra reservada en PostgreSQL.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from contaflow.db import Base
from contaflow.models.base import TimestampMixin, UUIDPkMixin
from contaflow.models.enums import UserRole


class User(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "app_user"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # El email identifica el login; unico a nivel global.
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        PGEnum(UserRole, name="user_role", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=UserRole.MEMBER,
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
