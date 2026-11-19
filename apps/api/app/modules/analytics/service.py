"""Analítica educativa (§4.4): indicadores con definición documentada, filtros y desgloses.

Flujo de §4.4: eventos → validación (en la ingesta) → agregación (aquí) → consulta → visualización → exportación auditada.
Las consultas leen tablas transaccionales; con volumen real se moverían a vistas materializadas (§7.3).
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Principal
from app.modules.academic.models import Assessment, AssessmentAttempt, CourseOffering, Enrollment, LearningEvent
from app.modules.academic.service import best_scores, offerings_query, weighted_grade

# Definiciones publicadas junto a cada número (§4.4: "evitar métricas ambiguas").
DEFINITIONS = {
    "participation_rate": ("Participación", "%", "Estudiantes con al menos un evento de aprendizaje en el rango / "
                           "matriculados vigentes (no retirados)."),
    "active_hours": ("Tiempo activo", "h", "Suma de la duración de sesiones y lecciones registradas en el rango. "
                     "No supone que una pestaña abierta sea atención."),
    "avg_active_days": ("Días activos por estudiante", "días", "Promedio de días distintos con actividad en el rango, "
                        "entre los matriculados vigentes."),
    "submissions": ("Entregas", "entregas", "Intentos de evaluación enviados dentro del rango."),
    "on_time_rate": ("Entregas a tiempo", "%", "Entregas del rango hechas antes del vencimiento / entregas del rango."),
    "attempts_per_assessment": ("Intentos por evaluación", "intentos", "Intentos del rango / pares distintos "
                                "(estudiante, evaluación) con al menos un intento."),
    "avg_progress": ("Progreso promedio", "%", "Actividades obligatorias completadas / total, promedio de las "
                     "matrículas vigentes. Estado actual, no depende del rango."),
    "completion_rate": ("Finalización", "%", "Matrículas completadas / matrículas vigentes. Estado actual."),
    "avg_grade": ("Nota promedio", "/20", "Promedio de la nota oficial ponderada (mejor intento calificado, escala "
                  "0-20) de quienes tienen al menos una nota. Estado actual."),
}


@dataclass
class Filters:
    date_from: datetime
    date_to: datetime
    offering_id: uuid.UUID | None = None
    instructor_id: uuid.UUID | None = None
    cohort: str | None = None
    period: str | None = None

    def describe(self, db: Session) -> dict:
        out = {"desde": self.date_from.date().isoformat(), "hasta": self.date_to.date().isoformat()}
        if self.offering_id:
            o = db.get(CourseOffering, self.offering_id)
            out["oferta"] = f"{o.course.code} · {o.cohort}" if o else str(self.offering_id)
        if self.instructor_id:
            from app.modules.identity.models import User

            u = db.get(User, self.instructor_id)
            out["docente"] = u.full_name if u else str(self.instructor_id)
        if self.cohort:
            out["cohorte"] = self.cohort
        if self.period:
            out["periodo"] = self.period
        return out


def default_range(now: datetime | None = None) -> tuple[datetime, datetime]:
    now = now or datetime.now(UTC)
    return (now - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0), now


def visible_offerings(db: Session, principal: Principal, f: Filters) -> list[CourseOffering]:
    q = offerings_query(principal)
    if f.offering_id:
        q = q.where(CourseOffering.id == f.offering_id)
    if f.instructor_id:
        q = q.where(CourseOffering.instructor_id == f.instructor_id)
    if f.cohort:
        q = q.where(CourseOffering.cohort == f.cohort)
    if f.period:
        q = q.where(CourseOffering.period == f.period)
    return list(db.scalars(q.order_by(CourseOffering.period.desc())))


def _pct(a: float, b: float) -> float | None:
    return round(a / b, 4) if b else None


def compute(db: Session, offerings: list[CourseOffering], f: Filters) -> dict:
    """Devuelve totales, filas por oferta, filas por estudiante y serie semanal."""
    ids = [o.id for o in offerings]
    enrollments = list(db.scalars(select(Enrollment).where(Enrollment.offering_id.in_(ids), Enrollment.status != "dropped"))) if ids else []
    events = list(db.scalars(select(LearningEvent).where(
        LearningEvent.offering_id.in_(ids), LearningEvent.occurred_at >= f.date_from,
        LearningEvent.occurred_at < f.date_to))) if ids else []
    attempts = list(db.scalars(select(AssessmentAttempt).join(Assessment).where(
        Assessment.offering_id.in_(ids), AssessmentAttempt.submitted_at >= f.date_from,
        AssessmentAttempt.submitted_at < f.date_to))) if ids else []
    assessments_by_offering = defaultdict(list)
    for a in db.scalars(select(Assessment).where(Assessment.offering_id.in_(ids))) if ids else []:
        assessments_by_offering[a.offering_id].append(a)

    # Agregados por (oferta, estudiante).
    days, hours, subs, late, pairs = defaultdict(set), defaultdict(float), defaultdict(int), defaultdict(int), defaultdict(set)
    for e in events:
        key = (e.offering_id, e.student_id)
        days[key].add(e.occurred_at.date())
        hours[key] += e.duration_seconds / 3600
    for t in attempts:
        key = (t.assessment.offering_id, t.student_id)
        subs[key] += 1
        late[key] += int(t.late)
        pairs[key].add(t.assessment_id)

    grades = {}
    for o in offerings:
        scores = best_scores(db, o.id)
        for e in (x for x in enrollments if x.offering_id == o.id):
            grades[(o.id, e.student_id)], _ = weighted_grade(assessments_by_offering[o.id], scores, e.student_id)

    def summarize(rows: list[Enrollment]) -> dict:
        keys = [(e.offering_id, e.student_id) for e in rows]
        n = len(rows)
        n_subs = sum(subs[k] for k in keys)
        graded = [grades[k] for k in keys if grades.get(k) is not None]
        return {
            "enrolled": n,
            "participation_rate": _pct(sum(1 for k in keys if days[k]), n),
            "active_hours": round(sum(hours[k] for k in keys), 1),
            "avg_active_days": round(sum(len(days[k]) for k in keys) / n, 2) if n else None,
            "submissions": n_subs,
            "on_time_rate": _pct(n_subs - sum(late[k] for k in keys), n_subs),
            "attempts_per_assessment": round(n_subs / sum(len(pairs[k]) for k in keys), 2) if sum(len(pairs[k]) for k in keys) else None,
            "avg_progress": round(sum(e.progress for e in rows) / n, 4) if n else None,
            "completion_rate": _pct(sum(e.status == "completed" for e in rows), n),
            "avg_grade": round(sum(graded) / len(graded), 2) if graded else None,
        }

    by_offering = []
    for o in offerings:
        rows = [e for e in enrollments if e.offering_id == o.id]
        by_offering.append({"offering_id": o.id, "course_code": o.course.code, "course_title": o.course.title,
                            "cohort": o.cohort, "period": o.period, "instructor": o.instructor.full_name,
                            **summarize(rows)})

    students = []
    for e in sorted(enrollments, key=lambda e: (e.offering.course.code, e.student.full_name)):
        k = (e.offering_id, e.student_id)
        students.append({
            "student_name": e.student.full_name, "student_email": e.student.email, "course_code": e.offering.course.code,
            "cohort": e.offering.cohort, "active_days": len(days[k]), "active_hours": round(hours[k], 1),
            "submissions": subs[k], "late_submissions": late[k], "progress": round(e.progress, 4),
            "status": e.status, "grade": grades.get(k),
            "last_activity_at": e.last_activity_at.isoformat() if e.last_activity_at else None,
        })

    # Serie semanal dentro del rango.
    weekly = []
    start = f.date_from - timedelta(days=f.date_from.weekday())
    while start < f.date_to:
        end = start + timedelta(weeks=1)
        week_events = [e for e in events if start <= e.occurred_at < end]
        weekly.append({"week_start": start.isoformat(), "active_students": len({e.student_id for e in week_events}),
                       "hours": round(sum(e.duration_seconds for e in week_events) / 3600, 1),
                       "submissions": sum(1 for t in attempts if start <= t.submitted_at < end)})
        start = end

    return {"totals": summarize(enrollments), "by_offering": by_offering, "students": students, "weekly": weekly}
