"""Reglas del core académico: visibilidad por rol (ABAC), progreso, eventos y notas."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import Select, exists, func, select
from sqlalchemy.orm import Session

from app.api.deps import Principal
from app.core.errors import AppError, not_found
from app.modules.academic.models import (
    Assessment,
    AssessmentAttempt,
    Course,
    CourseActivity,
    CourseOffering,
    CourseUnit,
    Enrollment,
    LearningEvent,
)
from app.modules.audit.service import record

# ---------- visibilidad (§3: RBAC + ABAC por institución, docente asignado y matrícula) ----------


def offerings_query(principal: Principal) -> Select:
    q = select(CourseOffering)
    if principal.is_global:
        return q
    q = q.where(CourseOffering.organization_id == principal.organization_id)
    if principal.can("course.read.all"):
        return q
    if principal.can("assessment.manage"):  # docente: solo las ofertas que dicta
        return q.where(CourseOffering.instructor_id == principal.user.id)
    if principal.can("learning"):  # estudiante: solo donde está matriculado
        return q.where(
            exists().where(Enrollment.offering_id == CourseOffering.id, Enrollment.student_id == principal.user.id)
        )
    return q.where(False)


def get_offering(db: Session, principal: Principal, offering_id: uuid.UUID) -> CourseOffering:
    offering = db.scalar(offerings_query(principal).where(CourseOffering.id == offering_id))
    if offering is None:
        raise not_found("Oferta")
    return offering


def can_manage_offering(principal: Principal, offering: CourseOffering) -> bool:
    """Crear evaluaciones y calificar: docente de la oferta, o coordinación/administración de la institución."""
    if not principal.can("assessment.manage"):
        return False
    if not principal.can_see_org(offering.organization_id):
        return False
    return principal.can("course.read.all") or offering.instructor_id == principal.user.id


def can_view_roster(principal: Principal, offering: CourseOffering) -> bool:
    """Notas individuales: administración, docente de la oferta y auditoría. El analista solo ve agregados (§3)."""
    return can_manage_offering(principal, offering) or (
        principal.can("audit.read") and principal.can_see_org(offering.organization_id)
    )


# ---------- contenido ----------


def required_activity_ids(db: Session, course_id: uuid.UUID) -> set[uuid.UUID]:
    rows = db.scalars(
        select(CourseActivity.id).join(CourseUnit).where(CourseUnit.course_id == course_id, CourseActivity.required)
    )
    return set(rows)


def activity_in_course(db: Session, activity_id: uuid.UUID, course_id: uuid.UUID) -> bool:
    return db.scalar(
        select(func.count()).select_from(CourseActivity).join(CourseUnit)
        .where(CourseActivity.id == activity_id, CourseUnit.course_id == course_id)
    ) == 1


def completed_activity_ids(db: Session, student_id: uuid.UUID, offering_id: uuid.UUID) -> set[uuid.UUID]:
    rows = db.scalars(
        select(LearningEvent.activity_id).where(
            LearningEvent.student_id == student_id,
            LearningEvent.offering_id == offering_id,
            LearningEvent.event_type == "activity_completed",
            LearningEvent.activity_id.is_not(None),
        ).distinct()
    )
    return set(rows)


# ---------- progreso y eventos ----------


def recompute_progress(db: Session, enrollment: Enrollment, *, actor_id: uuid.UUID | None = None,
                       audit: bool = True) -> None:
    """Progreso = actividades requeridas completadas / actividades requeridas (definición documentada, §4.4)."""
    required = required_activity_ids(db, enrollment.offering.course_id)
    done = completed_activity_ids(db, enrollment.student_id, enrollment.offering_id) & required
    enrollment.progress = round(len(done) / len(required), 4) if required else 0.0
    if enrollment.progress >= 1 and enrollment.status == "active":
        enrollment.status = "completed"
        enrollment.completed_at = datetime.now(UTC)
        if audit:  # la carga masiva DEMO no llena la bitácora con finalizaciones sintéticas
            record(db, action="course.completed", resource="enrollment", resource_id=enrollment.id,
                   actor_id=actor_id or enrollment.student_id, organization_id=enrollment.organization_id,
                   details={"offering_id": str(enrollment.offering_id)})


def ingest_event(
    db: Session,
    *,
    enrollment: Enrollment,
    event_id: uuid.UUID,
    event_type: str,
    activity_id: uuid.UUID | None,
    occurred_at: datetime | None,
    duration_seconds: int,
    source: str,
    payload: dict | None = None,
) -> tuple[bool, Enrollment]:
    """Registra un evento de forma idempotente y actualiza el progreso. Devuelve (duplicado, matrícula)."""
    existing = db.get(LearningEvent, event_id)
    if existing is not None:
        if existing.student_id != enrollment.student_id or existing.offering_id != enrollment.offering_id:
            raise AppError(409, "conflict", "El event_id ya existe con otro contenido.")
        return True, enrollment

    now = datetime.now(UTC)
    occurred = occurred_at or now
    if occurred.tzinfo is None:
        occurred = occurred.replace(tzinfo=UTC)
    if occurred > now + timedelta(minutes=5):
        raise AppError(422, "validation_error", "La fecha del evento está en el futuro.")
    if enrollment.status == "dropped":
        raise AppError(422, "validation_error", "La matrícula está retirada.")
    if activity_id is not None and not activity_in_course(db, activity_id, enrollment.offering.course_id):
        raise AppError(422, "validation_error", "La actividad no pertenece a este curso.")

    db.add(LearningEvent(
        event_id=event_id, organization_id=enrollment.organization_id, student_id=enrollment.student_id,
        offering_id=enrollment.offering_id, activity_id=activity_id, event_type=event_type, occurred_at=occurred,
        duration_seconds=duration_seconds, source=source, payload=payload,
    ))
    db.flush()
    if enrollment.last_activity_at is None or occurred > _aware(enrollment.last_activity_at):
        enrollment.last_activity_at = occurred
    if event_type == "activity_completed":
        recompute_progress(db, enrollment)
    return False, enrollment


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


# ---------- notas ----------


def best_scores(db: Session, offering_id: uuid.UUID, student_id: uuid.UUID | None = None) -> dict:
    """{(student_id, assessment_id): mejor nota oficial}. Regla del curso: cuenta el mejor intento calificado."""
    q = (
        select(AssessmentAttempt.student_id, AssessmentAttempt.assessment_id, func.max(AssessmentAttempt.score))
        .join(Assessment)
        .where(Assessment.offering_id == offering_id, AssessmentAttempt.score.is_not(None))
        .group_by(AssessmentAttempt.student_id, AssessmentAttempt.assessment_id)
    )
    if student_id:
        q = q.where(AssessmentAttempt.student_id == student_id)
    return {(s, a): score for s, a, score in db.execute(q)}


def weighted_grade(assessments: list[Assessment], scores: dict, student_id: uuid.UUID) -> tuple[float | None, float]:
    """Promedio ponderado en escala 0-20 de las evaluaciones ya calificadas, y el peso que suman."""
    total, weight = 0.0, 0.0
    for a in assessments:
        score = scores.get((student_id, a.id))
        if score is not None:
            total += a.weight * (score / a.max_score) * 20
            weight += a.weight
    return (round(total / weight, 2) if weight else None), round(weight, 4)
