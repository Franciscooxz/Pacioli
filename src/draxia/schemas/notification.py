"""Schema del resumen de notificaciones in-app."""

from __future__ import annotations

from pydantic import BaseModel


class NotificationSummary(BaseModel):
    """Contadores de lo que requiere atencion del usuario (campana del topbar)."""

    pending_review: int  # documentos en revision (de la firma / empresa activa)
    assigned_to_me: int  # documentos revisables asignados al usuario actual
    failures: int  # fallos de ingesta sin resolver
