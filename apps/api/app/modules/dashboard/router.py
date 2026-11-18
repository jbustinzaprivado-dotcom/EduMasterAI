"""Resumen del panel (§4.1, §4.4). Cada KPI informa valor, comparación, fuente y fecha.

Definiciones documentadas (§4.4, "evitar métricas ambiguas"):
- Estudiante activo: tuvo al menos un evento de aprendizaje válido en la ventana.
- Horas de aprendizaje: suma de duration_seconds de los eventos (sesiones y lecciones) en la ventana.
- Tasa de finalización: matrículas completadas / matrículas no retiradas.
- Progreso: actividades requeridas completadas / actividades requeridas.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import DB, Principal, require
from app.modules.academic.models import Course, CourseOffering, Enrollment, LearningEvent
from app.modules.academic.service import offerings_query
from app.modules.audit.models import AuditLog
from app.modules.identity.models import Organization, Role, User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class Kpi(BaseModel):
    key: str
    label: str
    value: float
    previous: float | None  # valor del periodo comparable; None si no aplica
    unit: str
    source: str
    updated_at: datetime


class Summary(BaseModel):
    scope: str  # "plataforma", "institución" o "personal"
    generated_at: datetime
    kpis: list[Kpi]


class WeekPoint(BaseModel):
    week_start: datetime
    active_students: int
    activities_completed: int
    hours: float


class Completion(BaseModel):
    completed: int
    in_progress: int
    not_started: int
    total: int


def _visible_offerings(principal: Principal):
    return offerings_query(principal).with_only_columns(CourseOffering.id)


def _events(principal: Principal):
    """Eventos visibles: los propios para el estudiante; los de sus ofertas para el resto."""
    q = select(LearningEvent).where(LearningEvent.offering_id.in_(_visible_offerings(principal)))
    if principal.can("learning") and not principal.can("course.read.all"):
        q = q.where(LearningEvent.student_id == principal.user.id)
    return q


def _enrollments(principal: Principal):
    q = select(Enrollment).where(Enrollment.offering_id.in_(_visible_offerings(principal)), Enrollment.status != "dropped")
    if principal.can("learning") and not principal.can("course.read.all"):
        q = q.where(Enrollment.student_id == principal.user.id)
    return q


@router.get("/summary", response_model=Summary)
def summary(db: DB, principal: Principal = require("dashboard.read")) -> Summary:
    now = datetime.now(UTC)
    events = _events(principal).subquery()
    enrollments = _enrollments(principal).subquery()

    def active_students(since: datetime, until: datetime) -> int:
        return db.scalar(select(func.count(func.distinct(events.c.student_id)))
                         .where(events.c.occurred_at >= since, events.c.occurred_at < until)) or 0

    def hours(since: datetime, until: datetime) -> float:
        secs = db.scalar(select(func.coalesce(func.sum(events.c.duration_seconds), 0))
                         .where(events.c.occurred_at >= since, events.c.occurred_at < until)) or 0
        return round(secs / 3600, 1)

    def logins(since: datetime, until: datetime, *, own: bool) -> int:
        q = select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "auth.login", AuditLog.occurred_at >= since, AuditLog.occurred_at < until)
        if own:
            q = q.where(AuditLog.actor_id == principal.user.id)
        elif not principal.is_global:
            q = q.where(AuditLog.organization_id == principal.organization_id)
        return db.scalar(q) or 0

    total, completed, avg_progress = db.execute(
        select(func.count(), func.count().filter(enrollments.c.status == "completed"), func.avg(enrollments.c.progress))
    ).one()
    completion_rate = round(100 * completed / total, 1) if total else 0.0
    d7, d14, d30, d60, d1, d2 = (now - timedelta(days=n) for n in (7, 14, 30, 60, 1, 2))

    def kpi(key, label, value, previous, unit, source):
        return Kpi(key=key, label=label, value=value, previous=previous, unit=unit, source=source, updated_at=now)

    # Estudiante (sin permisos de lectura amplia): resumen personal.
    if principal.can("learning") and not principal.can("course.read.all"):
        return Summary(scope="personal", generated_at=now, kpis=[
            kpi("my_courses", "Mis cursos", total, None, "cursos", "enrollments"),
            kpi("my_progress", "Mi progreso promedio", round(100 * (avg_progress or 0), 1), None, "%", "enrollments.progress"),
            kpi("my_hours_7d", "Mis horas (7 días)", hours(d7, now), hours(d14, d7), "horas", "learning_events"),
            kpi("my_logins_24h", "Mis accesos (24 h)", logins(d1, now, own=True), logins(d2, d1, own=True),
                "accesos", "audit_logs"),
        ])

    courses_q = select(func.count()).select_from(Course).where(Course.status == "published")
    students_q = select(func.count()).select_from(User).where(User.status == "active", User.roles.any(Role.code == "estudiante"))
    if not principal.is_global:
        courses_q = courses_q.where(Course.organization_id == principal.organization_id)
        students_q = students_q.where(User.organization_id == principal.organization_id)

    kpis = [
        kpi("active_students_7d", "Estudiantes activos (7 días)", active_students(d7, now), active_students(d14, d7),
            "estudiantes", "learning_events"),
        kpi("students", "Estudiantes registrados", db.scalar(students_q) or 0, None, "estudiantes", "users"),
        kpi("courses", "Cursos publicados", db.scalar(courses_q) or 0, None, "cursos", "courses"),
        kpi("enrollments", "Matrículas vigentes", total, None, "matrículas", "enrollments"),
        kpi("learning_hours_30d", "Horas de aprendizaje (30 días)", hours(d30, now), hours(d60, d30), "horas",
            "learning_events"),
        kpi("completion_rate", "Tasa de finalización", completion_rate, None, "%", "enrollments"),
        kpi("logins_24h", "Accesos (24 h)", logins(d1, now, own=False), logins(d2, d1, own=False), "accesos",
            "audit_logs"),
    ]
    alerts = _open_alerts(db, principal)
    if alerts is not None:
        kpis.insert(1, kpi("risk_alerts", "Alertas de riesgo por revisar", alerts, None, "estudiantes",
                           "predictions (modelo publicado)"))
    if principal.is_global:
        orgs = db.scalar(select(func.count()).select_from(Organization)
                         .where(Organization.status == "active", Organization.is_platform.is_(False))) or 0
        kpis.insert(0, kpi("organizations", "Instituciones activas", orgs, None, "instituciones", "organizations"))
    scope = "plataforma" if principal.is_global else "institución"
    if not principal.can("course.read.all"):
        scope = "mis cursos"  # docente: sus ofertas
    return Summary(scope=scope, generated_at=now, kpis=kpis)


def _open_alerts(db, principal: Principal) -> int | None:
    """Matrículas cuya última predicción es de riesgo alto y sigue pendiente de revisión. None si no hay modelo."""
    from app.modules.ml.models import Prediction
    from app.modules.ml.service import active_deployment

    if active_deployment(db, principal.organization_id) is None:
        return None
    latest = {}
    rows = db.scalars(select(Prediction).where(Prediction.offering_id.in_(_visible_offerings(principal)))
                      .order_by(Prediction.created_at))
    for p in rows:
        latest[p.enrollment_id] = p
    return sum(1 for p in latest.values() if p.risk_level == "alto" and p.review_status == "pendiente")


@router.get("/progress-series", response_model=list[WeekPoint])
def progress_series(db: DB, principal: Principal = require("dashboard.read"), weeks: int = 8) -> list[WeekPoint]:
    """Serie semanal de actividad (§4.4): estudiantes activos, actividades completadas y horas."""
    weeks = max(1, min(weeks, 26))
    now = datetime.now(UTC)
    start_of_week = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    events = _events(principal).subquery()
    points = []
    for i in range(weeks - 1, -1, -1):
        since = start_of_week - timedelta(weeks=i)
        until = since + timedelta(weeks=1)
        active, completed, secs = db.execute(
            select(func.count(func.distinct(events.c.student_id)),
                   func.count().filter(events.c.event_type == "activity_completed"),
                   func.coalesce(func.sum(events.c.duration_seconds), 0))
            .where(events.c.occurred_at >= since, events.c.occurred_at < until)
        ).one()
        points.append(WeekPoint(week_start=since, active_students=active, activities_completed=completed,
                                hours=round(secs / 3600, 1)))
    return points


@router.get("/completion", response_model=Completion)
def completion(db: DB, principal: Principal = require("dashboard.read")) -> Completion:
    """Finalización de cursos (§4.1): completado, en progreso y no iniciado."""
    e = _enrollments(principal).subquery()
    done, progress, zero, total = db.execute(
        select(func.count().filter(e.c.status == "completed"),
               func.count().filter(e.c.status == "active", e.c.progress > 0),
               func.count().filter(e.c.status == "active", e.c.progress == 0),
               func.count())
    ).one()
    return Completion(completed=done, in_progress=progress, not_started=zero, total=total)
