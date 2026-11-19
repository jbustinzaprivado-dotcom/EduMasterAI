"""Avance de un estudiante en su ruta (§4.2): estado por etapa, siguiente paso y cierre automático."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.academic.models import Assessment, CourseOffering, Enrollment
from app.modules.academic.service import best_scores, weighted_grade
from app.modules.audit.service import record
from app.modules.notifications.service import notify
from app.modules.paths.models import PathAssignment, PathStep


@dataclass
class StepProgress:
    step_id: object
    position: int
    course_id: object
    course_code: str
    course_title: str
    min_grade: float | None
    status: str  # completado | en_curso | disponible | bloqueado | dispensado
    progress: float
    grade: float | None
    offering_id: object | None
    available_offering_id: object | None  # oferta activa para matricularse si aún no lo está
    available_offering_label: str | None
    note: str


@dataclass
class AssignmentProgress:
    progress: float
    completed_steps: int
    total_steps: int
    steps: list[StepProgress] = field(default_factory=list)
    next_step: StepProgress | None = None
    on_track: bool | None = None  # comparado con la fecha objetivo


def _enrollment_for(db: Session, student_id, course_id) -> Enrollment | None:
    rows = db.scalars(select(Enrollment).join(CourseOffering).where(
        Enrollment.student_id == student_id, CourseOffering.course_id == course_id, Enrollment.status != "dropped"))
    rows = list(rows)
    # Prioriza una matrícula completada; si no, la más reciente.
    return max(rows, key=lambda e: (e.status == "completed", e.enrolled_at), default=None)


def _grade(db: Session, enrollment: Enrollment) -> float | None:
    assessments = list(db.scalars(select(Assessment).where(Assessment.offering_id == enrollment.offering_id)))
    grade, _ = weighted_grade(assessments, best_scores(db, enrollment.offering_id, enrollment.student_id),
                              enrollment.student_id)
    return grade


def _step_done(db: Session, step: PathStep, enrollment: Enrollment | None) -> tuple[bool, float | None]:
    if enrollment is None or enrollment.status != "completed":
        return False, _grade(db, enrollment) if enrollment else None
    grade = _grade(db, enrollment)
    if step.min_grade is not None and (grade is None or grade < step.min_grade):
        return False, grade
    return True, grade


def progress(db: Session, assignment: PathAssignment, now: datetime | None = None) -> AssignmentProgress:
    now = now or datetime.now(UTC)
    waived = {str(x["step_id"]) for x in assignment.exceptions or []}
    steps, previous_done, completed = [], True, 0
    for step in assignment.path.steps:
        enrollment = _enrollment_for(db, assignment.student_id, step.course_id)
        if str(step.id) in waived:
            status, done, grade, note = "dispensado", True, None, "Excepción autorizada por coordinación."
        else:
            done, grade = _step_done(db, step, enrollment)
            if done:
                status, note = "completado", "Criterio de logro cumplido."
            elif not previous_done:
                status, note = "bloqueado", "Requiere completar la etapa anterior."
            elif enrollment is not None and enrollment.status == "active":
                status, note = "en_curso", f"Avance {round(enrollment.progress * 100)} % en el curso."
            elif enrollment is not None and enrollment.status == "completed":
                status, note = "en_curso", f"Curso completado; falta nota mínima {step.min_grade:g}."
            else:
                status, note = "disponible", "Aún sin matrícula en este curso."
        available = None
        if status == "disponible":
            available = db.scalar(select(CourseOffering).where(
                CourseOffering.course_id == step.course_id, CourseOffering.status == "active",
                CourseOffering.ends_on > now).order_by(CourseOffering.starts_on.desc()).limit(1))
        steps.append(StepProgress(
            step_id=step.id, position=step.position, course_id=step.course_id, course_code=step.course.code,
            course_title=step.course.title, min_grade=step.min_grade, status=status,
            progress=1.0 if done else (enrollment.progress if enrollment else 0.0), grade=grade,
            offering_id=enrollment.offering_id if enrollment else None,
            available_offering_id=available.id if available else None,
            available_offering_label=f"{available.cohort} · {available.period}" if available else None, note=note,
        ))
        completed += int(done)
        previous_done = previous_done and done
    total = len(steps)
    result = AssignmentProgress(progress=round(completed / total, 4) if total else 0.0, completed_steps=completed,
                                total_steps=total, steps=steps)
    result.next_step = next((s for s in steps if s.status in ("en_curso", "disponible")), None)
    if assignment.target_date and assignment.status == "active":
        span = (assignment.target_date - assignment.assigned_at).total_seconds()
        expected = min(1.0, max(0.0, (now - assignment.assigned_at).total_seconds() / span)) if span > 0 else 1.0
        result.on_track = result.progress + 1e-9 >= expected - 0.15
    return result


def refresh_status(db: Session, assignment: PathAssignment) -> AssignmentProgress:
    """Cierra la asignación cuando se cumplen todas las etapas (evento de logro, §4.2)."""
    p = progress(db, assignment)
    if assignment.status == "active" and p.total_steps and p.completed_steps == p.total_steps:
        assignment.status, assignment.completed_at = "completed", datetime.now(UTC)
        record(db, action="path.completed", resource="path_assignment", resource_id=assignment.id,
               actor_id=assignment.student_id, organization_id=assignment.organization_id,
               details={"path": assignment.path.title})
        notify(db, [assignment.student_id], organization_id=assignment.organization_id, kind="path.completed",
               title=f"¡Completaste la ruta {assignment.path.title}!", body="Cumpliste todas las etapas.", link="/rutas")
    return p
