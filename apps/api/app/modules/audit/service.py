"""Registro de acciones auditables (§11.1). Se guarda en la misma transacción que la acción."""

import uuid

from sqlalchemy.orm import Session

from app.core.context import client_ip, correlation_id
from app.modules.audit.models import AuditLog


def record(
    db: Session,
    *,
    action: str,
    resource: str,
    resource_id: object = None,
    actor_id: uuid.UUID | None = None,
    organization_id: uuid.UUID | None = None,
    details: dict | None = None,
) -> AuditLog:
    entry = AuditLog(
        action=action,
        resource=resource,
        resource_id=str(resource_id) if resource_id is not None else None,
        actor_id=actor_id,
        organization_id=organization_id,
        details=details,
        ip=client_ip.get(),
        correlation_id=correlation_id.get(),
    )
    db.add(entry)
    return entry
