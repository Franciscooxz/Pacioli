"""Crea un usuario (y su firma/tenant si no existe). Onboarding manual por ahora.

Uso (dentro del contenedor):
    python -m contaflow.scripts.crear_usuario <email> <password> [nombre_firma] [ADMIN|MEMBER]
"""

from __future__ import annotations

import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from contaflow.core.auth import hash_password
from contaflow.db import SyncSessionLocal
from contaflow.models.enums import UserRole
from contaflow.models.tenant import Tenant
from contaflow.models.user import User


def _get_or_create_tenant(session: Session, name: str) -> Tenant:
    tenant = session.scalar(select(Tenant).where(Tenant.name == name))
    if tenant is None:
        tenant = Tenant(name=name)
        session.add(tenant)
        session.flush()
    return tenant


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(
            "Uso: python -m contaflow.scripts.crear_usuario <email> <password> "
            "[nombre_firma] [ADMIN|MEMBER]"
        )
        return 2

    email = argv[1]
    password = argv[2]
    tenant_name = argv[3] if len(argv) > 3 else "Firma Demo"
    role = UserRole(argv[4]) if len(argv) > 4 else UserRole.ADMIN

    with SyncSessionLocal() as session:
        if session.scalar(select(User).where(User.email == email)) is not None:
            print(f"Ya existe un usuario con email {email}")
            return 1
        tenant = _get_or_create_tenant(session, tenant_name)
        user = User(
            tenant_id=tenant.id,
            email=email,
            password_hash=hash_password(password),
            role=role,
        )
        session.add(user)
        session.commit()
        print(f"Usuario creado: {email} (rol {role.value}) en firma '{tenant_name}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
