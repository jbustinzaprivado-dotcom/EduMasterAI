"""Resumen del panel (§4.1). En la Fase 1 solo hay KPIs de lo que ya existe (usuarios y accesos);
los académicos llegan en las Fases 2-3. Cada KPI informa valor, comparación, fuente y fecha (§4.1)."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import DB, Principal, require
from app.modules.audit.models import AuditLog
from app.modules.identity.models import Organization, Role, User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class Kpi(BaseModel):
    key: str
    label: str
    value: int
    previous: int | None  # valor del periodo comparable; None si no aplica
    unit: str
    source: str
    updated_at: datetime


class Summary(BaseModel):
    scope: str  # "plataforma", "institución" o "personal"
    generated_at: datetime
    kpis: list[Kpi]


@router.get("/summary", response_model=Summary)
def summary(db: DB, principal: Principal = require("dashboard.read")) -> Summary:
    now = datetime.now(UTC)
    day, two_days = now - timedelta(hours=24), now - timedelta(hours=48)

    def logins(since: datetime, until: datetime, *, own: bool) -> int:
        q = select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "auth.login", AuditLog.occurred_at >= since, AuditLog.occurred_at < until
        )
        if own:
            q = q.where(AuditLog.actor_id == principal.user.id)
        elif not principal.is_global:
            q = q.where(AuditLog.organization_id == principal.organization_id)
        return db.scalar(q) or 0

    def users_with(role: str | None = None) -> int:
        q = select(func.count()).select_from(User).where(User.status == "active")
        if not principal.is_global:
            q = q.where(User.organization_id == principal.organization_id)
        if role:
            q = q.where(User.roles.any(Role.code == role))
        return db.scalar(q) or 0

    # Sin permiso para ver usuarios, el resumen es personal.
    if not principal.can("user.read"):
        kpis = [
            Kpi(key="my_logins_24h", label="Mis accesos (24 h)", value=logins(day, now, own=True),
                previous=logins(two_days, day, own=True), unit="accesos", source="audit_logs", updated_at=now),
        ]
        return Summary(scope="personal", generated_at=now, kpis=kpis)

    kpis = [
        Kpi(key="active_users", label="Usuarios activos", value=users_with(), previous=None,
            unit="usuarios", source="users", updated_at=now),
        Kpi(key="students", label="Estudiantes registrados", value=users_with("estudiante"), previous=None,
            unit="estudiantes", source="users + user_roles", updated_at=now),
        Kpi(key="instructors", label="Docentes", value=users_with("docente"), previous=None,
            unit="docentes", source="users + user_roles", updated_at=now),
        Kpi(key="logins_24h", label="Accesos (24 h)", value=logins(day, now, own=False),
            previous=logins(two_days, day, own=False), unit="accesos", source="audit_logs", updated_at=now),
    ]
    if principal.is_global:
        orgs = db.scalar(
            select(func.count()).select_from(Organization)
            .where(Organization.status == "active", Organization.is_platform.is_(False))
        ) or 0
        kpis.insert(0, Kpi(key="organizations", label="Instituciones activas", value=orgs, previous=None,
                           unit="instituciones", source="organizations", updated_at=now))
    return Summary(scope="plataforma" if principal.is_global else "institución", generated_at=now, kpis=kpis)
