"""Consulta de la bitácora (§11.1). No hay endpoints para modificarla ni borrarla."""

import base64
import uuid
from datetime import datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import and_, or_, select

from app.api.deps import DB, CurrentPrincipal
from app.core.errors import forbidden
from app.modules.audit.models import AuditLog
from app.modules.identity.models import User

router = APIRouter(prefix="/audit-logs", tags=["auditoría"])

# Texto legible de cada acción para el feed de actividad.
ACTION_LABELS = {
    "auth.login": "Inició sesión",
    "auth.login_failed": "Intento de inicio de sesión fallido",
    "auth.logout": "Cerró sesión",
    "auth.refresh_reuse": "Sesión revocada por reutilización de token",
    "org.created": "Creó una institución",
    "user.created": "Creó un usuario",
    "user.updated": "Modificó un usuario",
    "user.roles_changed": "Cambió los roles de un usuario",
    "course.created": "Creó un curso",
    "course.status_changed": "Cambió el estado de un curso",
    "offering.created": "Abrió una oferta de curso",
    "enrollment.created": "Matriculó estudiantes",
    "course.completed": "Completó un curso",
    "assessment.created": "Creó una evaluación",
    "assessment.submitted": "Entregó una evaluación",
    "grade.recorded": "Registró una nota oficial",
    "model.published": "Aprobó y publicó un modelo de IA",
    "predictions.generated": "Generó predicciones de riesgo",
    "prediction.reviewed": "Revisó una alerta de riesgo",
    "certificate.issued": "Emitió un certificado",
    "certificate.revoked": "Anuló un certificado",
    "certificate.downloaded": "Descargó un certificado",
    "community.ocultado": "Ocultó contenido de la comunidad",
    "community.restaurado": "Restauró contenido de la comunidad",
    "community.desestimado": "Desestimó un reporte de la comunidad",
}


class AuditOut(BaseModel):
    id: uuid.UUID
    occurred_at: datetime
    action: str
    label: str
    resource: str
    resource_id: str | None
    actor_id: uuid.UUID | None
    actor_name: str | None
    organization_id: uuid.UUID | None
    ip: str | None
    correlation_id: str | None
    details: dict | None


class AuditPage(BaseModel):
    items: list[AuditOut]
    next_cursor: str | None  # paginación por cursor (§10.1)


def _encode_cursor(row: AuditLog) -> str:
    """Cursor opaco (fecha + id del último elemento) en base64 URL-safe: viaja limpio en la URL."""
    return base64.urlsafe_b64encode(f"{row.occurred_at.isoformat()}|{row.id}".encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime | None, uuid.UUID | None]:
    try:
        ts, last_id = base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
        return datetime.fromisoformat(ts), uuid.UUID(last_id)
    except ValueError:
        return None, None  # cursor inválido: se ignora y se devuelve la primera página


@router.get("", response_model=AuditPage)
def list_audit_logs(
    db: DB,
    principal: CurrentPrincipal,
    action: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
) -> AuditPage:
    query = select(AuditLog)
    if principal.can("audit.read"):
        if not principal.is_global:
            query = query.where(AuditLog.organization_id == principal.organization_id)
    elif principal.can("audit.read.own"):
        query = query.where(AuditLog.actor_id == principal.user.id)
    else:
        raise forbidden()

    if action:
        query = query.where(AuditLog.action == action)
    if cursor:
        ts_value, id_value = _decode_cursor(cursor)
        if ts_value is not None:
            query = query.where(
                or_(AuditLog.occurred_at < ts_value,
                    and_(AuditLog.occurred_at == ts_value, AuditLog.id < id_value))
            )

    rows = list(db.scalars(query.order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc()).limit(limit + 1)))
    has_more = len(rows) > limit
    rows = rows[:limit]

    actor_ids = {r.actor_id for r in rows if r.actor_id}
    names = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_(actor_ids)))} if actor_ids else {}

    items = [
        AuditOut(
            id=r.id, occurred_at=r.occurred_at, action=r.action, label=ACTION_LABELS.get(r.action, r.action),
            resource=r.resource, resource_id=r.resource_id, actor_id=r.actor_id,
            actor_name=names.get(r.actor_id) if r.actor_id else None, organization_id=r.organization_id,
            ip=r.ip, correlation_id=r.correlation_id, details=r.details,
        )
        for r in rows
    ]
    next_cursor = _encode_cursor(rows[-1]) if has_more else None
    return AuditPage(items=items, next_cursor=next_cursor)
