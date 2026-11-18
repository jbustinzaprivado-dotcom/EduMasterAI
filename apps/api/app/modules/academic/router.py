"""Endpoints del core académico (§4.3, §4.6, §10.2): cursos, ofertas, matrículas, eventos y evaluaciones."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import DB, CurrentPrincipal, Principal, require
from app.core.errors import AppError, forbidden, not_found
from app.modules.academic import service
from app.modules.academic.models import (
    Assessment,
    AssessmentAttempt,
    Course,
    CourseActivity,
    CourseOffering,
    CourseUnit,
    Enrollment,
)
from app.modules.academic.schemas import (
    ActivityOut,
    AssessmentIn,
    AssessmentOut,
    AttemptOut,
    CourseIn,
    CourseOut,
    CoursePatch,
    EnrollIn,
    EventIn,
    EventOut,
    GradeIn,
    MyAttempt,
    MyEnrollment,
    OfferingIn,
    OfferingOut,
    RosterRow,
    SubmissionIn,
    UnitOut,
)
from app.modules.audit.service import record
from app.modules.certificates.service import try_auto_issue
from app.modules.notifications.service import notify
from app.modules.identity.models import Role, User

router = APIRouter(tags=["académico"])


# ---------- serialización ----------

def _units(course: Course) -> list[UnitOut]:
    return [
        UnitOut(id=u.id, position=u.position, title=u.title, activities=[
            ActivityOut(id=a.id, position=a.position, title=a.title, kind=a.kind,
                        estimated_minutes=a.estimated_minutes, required=a.required)
            for a in u.activities
        ])
        for u in course.units
    ]


def _course_out(db: DB, course: Course, *, with_units: bool = False) -> CourseOut:
    offerings = db.scalar(select(func.count()).select_from(CourseOffering).where(CourseOffering.course_id == course.id))
    return CourseOut(
        id=course.id, code=course.code, title=course.title, description=course.description, level=course.level,
        status=course.status, unit_count=len(course.units),
        activity_count=sum(len(u.activities) for u in course.units), offering_count=offerings or 0,
        units=_units(course) if with_units else None,
    )


def _offering_out(db: DB, principal: Principal, o: CourseOffering, *, with_units: bool = False) -> OfferingOut:
    enrolled, completed, avg = db.execute(
        select(func.count(), func.count().filter(Enrollment.status == "completed"), func.avg(Enrollment.progress))
        .where(Enrollment.offering_id == o.id, Enrollment.status != "dropped")
    ).one()
    mine = None
    if principal.can("learning"):
        enrollment = db.scalar(select(Enrollment).where(Enrollment.offering_id == o.id,
                                                         Enrollment.student_id == principal.user.id))
        if enrollment:
            mine = MyEnrollment(
                id=enrollment.id, status=enrollment.status, progress=enrollment.progress,
                completed_activity_ids=sorted(service.completed_activity_ids(db, principal.user.id, o.id), key=str),
            )
    return OfferingOut(
        id=o.id, course_id=o.course_id, course_code=o.course.code, course_title=o.course.title,
        course_level=o.course.level, instructor_id=o.instructor_id, instructor_name=o.instructor.full_name,
        period=o.period, cohort=o.cohort, starts_on=o.starts_on, ends_on=o.ends_on, status=o.status,
        enrolled=enrolled, completed=completed, avg_progress=round(avg, 4) if avg is not None else None,
        my_enrollment=mine, can_manage=service.can_manage_offering(principal, o),
        units=_units(o.course) if with_units else None,
    )


# ---------- cursos (catálogo) ----------

@router.get("/courses", response_model=list[CourseOut])
def list_courses(db: DB, principal: Principal = require("course.read.all")) -> list[CourseOut]:
    q = select(Course).order_by(Course.code)
    if not principal.is_global:
        q = q.where(Course.organization_id == principal.organization_id)
    return [_course_out(db, c) for c in db.scalars(q)]


@router.get("/courses/{course_id}", response_model=CourseOut)
def get_course(course_id: uuid.UUID, db: DB, principal: Principal = require("course.read.all")) -> CourseOut:
    course = db.get(Course, course_id)
    if course is None or not principal.can_see_org(course.organization_id):
        raise not_found("Curso")
    return _course_out(db, course, with_units=True)


@router.post("/courses", response_model=CourseOut, status_code=201)
def create_course(body: CourseIn, db: DB, principal: Principal = require("course.manage")) -> CourseOut:
    course = Course(organization_id=principal.organization_id, code=body.code, title=body.title.strip(),
                    description=body.description.strip(), level=body.level)
    for i, unit in enumerate(body.units, start=1):
        u = CourseUnit(position=i, title=unit.title.strip())
        u.activities = [CourseActivity(position=j, title=a.title.strip(), kind=a.kind,
                                       estimated_minutes=a.estimated_minutes, required=a.required)
                        for j, a in enumerate(unit.activities, start=1)]
        course.units.append(u)
    db.add(course)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "conflict", "Ya existe un curso con ese código en la institución.") from None
    record(db, action="course.created", resource="course", resource_id=course.id, actor_id=principal.user.id,
           organization_id=course.organization_id, details={"code": course.code})
    db.commit()
    return _course_out(db, course, with_units=True)


@router.patch("/courses/{course_id}", response_model=CourseOut)
def update_course(course_id: uuid.UUID, body: CoursePatch, db: DB,
                  principal: Principal = require("course.manage")) -> CourseOut:
    course = db.get(Course, course_id)
    if course is None or not principal.can_see_org(course.organization_id):
        raise not_found("Curso")
    if body.status == "published" and not any(u.activities for u in course.units):
        raise AppError(422, "validation_error", "No se puede publicar un curso sin actividades.")
    if body.status != course.status:
        record(db, action="course.status_changed", resource="course", resource_id=course.id,
               actor_id=principal.user.id, organization_id=course.organization_id,
               details={"status": [course.status, body.status]})
        course.status = body.status
        db.commit()
    return _course_out(db, course, with_units=True)


# ---------- ofertas ----------

@router.get("/offerings", response_model=list[OfferingOut])
def list_offerings(db: DB, principal: CurrentPrincipal) -> list[OfferingOut]:
    q = service.offerings_query(principal).order_by(CourseOffering.starts_on.desc())
    return [_offering_out(db, principal, o) for o in db.scalars(q)]


@router.get("/offerings/{offering_id}", response_model=OfferingOut)
def get_offering(offering_id: uuid.UUID, db: DB, principal: CurrentPrincipal) -> OfferingOut:
    return _offering_out(db, principal, service.get_offering(db, principal, offering_id), with_units=True)


@router.post("/offerings", response_model=OfferingOut, status_code=201)
def create_offering(body: OfferingIn, db: DB, principal: Principal = require("course.manage")) -> OfferingOut:
    course = db.get(Course, body.course_id)
    if course is None or not principal.can_see_org(course.organization_id):
        raise not_found("Curso")
    if course.status != "published":
        raise AppError(422, "validation_error", "Solo se ofertan cursos publicados.")
    instructor = db.get(User, body.instructor_id)
    if instructor is None or instructor.organization_id != course.organization_id or "docente" not in instructor.role_codes:
        raise AppError(422, "validation_error", "El docente debe pertenecer a la institución y tener rol docente.")
    if body.ends_on <= body.starts_on:
        raise AppError(422, "validation_error", "La fecha de fin debe ser posterior al inicio.")
    offering = CourseOffering(organization_id=course.organization_id, course_id=course.id,
                              instructor_id=instructor.id, period=body.period.strip(), cohort=body.cohort.strip(),
                              starts_on=body.starts_on, ends_on=body.ends_on)
    db.add(offering)
    db.flush()
    record(db, action="offering.created", resource="offering", resource_id=offering.id, actor_id=principal.user.id,
           organization_id=offering.organization_id,
           details={"course": course.code, "cohort": offering.cohort, "instructor": instructor.full_name})
    db.commit()
    db.refresh(offering)
    return _offering_out(db, principal, offering)


# ---------- matrículas ----------

@router.post("/offerings/{offering_id}/enrollments", status_code=201)
def enroll(offering_id: uuid.UUID, body: EnrollIn, db: DB, principal: Principal = require("course.manage")) -> dict:
    offering = service.get_offering(db, principal, offering_id)
    students = list(db.scalars(
        select(User).where(User.id.in_(body.student_ids), User.organization_id == offering.organization_id,
                           User.roles.any(Role.code == "estudiante"))
    ))
    if len(students) != len(set(body.student_ids)):
        raise AppError(422, "validation_error", "Todos deben ser estudiantes de la misma institución.")
    already = set(db.scalars(select(Enrollment.student_id).where(Enrollment.offering_id == offering.id)))
    created = 0
    for s in students:
        if s.id in already:
            continue
        db.add(Enrollment(organization_id=offering.organization_id, offering_id=offering.id, student_id=s.id))
        created += 1
    record(db, action="enrollment.created", resource="offering", resource_id=offering.id, actor_id=principal.user.id,
           organization_id=offering.organization_id, details={"students": created})
    notify(db, [s.id for s in students if s.id not in already], organization_id=offering.organization_id,
           kind="enrollment.created", title=f"Te matricularon en {offering.course.title}",
           body=f"{offering.cohort} · {offering.period} · Docente: {offering.instructor.full_name}",
           link=f"/cursos/{offering.id}")
    db.commit()
    return {"created": created, "skipped": len(students) - created}


@router.get("/offerings/{offering_id}/enrollments", response_model=list[RosterRow])
def roster(offering_id: uuid.UUID, db: DB, principal: CurrentPrincipal) -> list[RosterRow]:
    offering = service.get_offering(db, principal, offering_id)
    if not service.can_view_roster(principal, offering):
        raise forbidden()
    assessments = list(db.scalars(select(Assessment).where(Assessment.offering_id == offering.id)))
    scores = service.best_scores(db, offering.id)
    rows = []
    enrollments = db.scalars(select(Enrollment).where(Enrollment.offering_id == offering.id))
    for e in sorted(enrollments, key=lambda e: e.student.full_name):
        grade, weight = service.weighted_grade(assessments, scores, e.student_id)
        rows.append(RosterRow(
            enrollment_id=e.id, student_id=e.student_id, student_name=e.student.full_name,
            student_email=e.student.email, status=e.status, progress=e.progress,
            last_activity_at=e.last_activity_at, grade=grade, graded_weight=weight,
        ))
    return rows


# ---------- eventos de aprendizaje ----------

@router.post("/learning-events", response_model=EventOut)
def ingest(body: EventIn, db: DB, principal: Principal = require("learning")) -> EventOut:
    """Ingesta idempotente (§10.2): el estudiante solo registra eventos propios en cursos donde está matriculado."""
    enrollment = db.scalar(select(Enrollment).where(Enrollment.offering_id == body.offering_id,
                                                     Enrollment.student_id == principal.user.id))
    if enrollment is None:
        raise not_found("Matrícula")
    duplicate, enrollment = service.ingest_event(
        db, enrollment=enrollment, event_id=body.event_id, event_type=body.event_type,
        activity_id=body.activity_id, occurred_at=body.occurred_at, duration_seconds=body.duration_seconds,
        source=body.source,
    )
    db.commit()
    return EventOut(event_id=body.event_id, duplicate=duplicate, progress=enrollment.progress,
                    enrollment_status=enrollment.status)


# ---------- evaluaciones ----------

def _assessment_out(db: DB, principal: Principal, a: Assessment) -> AssessmentOut:
    out = AssessmentOut(
        id=a.id, offering_id=a.offering_id, course_title=a.offering.course.title, cohort=a.offering.cohort,
        title=a.title, kind=a.kind, instructions=a.instructions, max_score=a.max_score, weight=a.weight,
        due_at=a.due_at, max_attempts=a.max_attempts, can_manage=service.can_manage_offering(principal, a.offering),
    )
    if out.can_manage:
        out.submissions, out.graded = db.execute(
            select(func.count(func.distinct(AssessmentAttempt.student_id)),
                   func.count(func.distinct(AssessmentAttempt.student_id)).filter(AssessmentAttempt.score.is_not(None)))
            .where(AssessmentAttempt.assessment_id == a.id)
        ).one()
    if principal.can("learning"):
        attempts = list(db.scalars(select(AssessmentAttempt).where(
            AssessmentAttempt.assessment_id == a.id, AssessmentAttempt.student_id == principal.user.id
        ).order_by(AssessmentAttempt.attempt_no)))
        graded = [t for t in attempts if t.score is not None]
        best = max(graded, key=lambda t: t.score) if graded else None
        out.mine = MyAttempt(attempts=len(attempts),
                             last_submitted_at=attempts[-1].submitted_at if attempts else None,
                             best_score=best.score if best else None, feedback=best.feedback if best else None)
    return out


@router.get("/assessments", response_model=list[AssessmentOut])
def list_assessments(db: DB, principal: CurrentPrincipal) -> list[AssessmentOut]:
    visible = service.offerings_query(principal).with_only_columns(CourseOffering.id)
    rows = db.scalars(select(Assessment).where(Assessment.offering_id.in_(visible)).order_by(Assessment.due_at))
    return [_assessment_out(db, principal, a) for a in rows]


@router.post("/offerings/{offering_id}/assessments", response_model=AssessmentOut, status_code=201)
def create_assessment(offering_id: uuid.UUID, body: AssessmentIn, db: DB, principal: CurrentPrincipal) -> AssessmentOut:
    offering = service.get_offering(db, principal, offering_id)
    if not service.can_manage_offering(principal, offering):
        raise forbidden()
    total = db.scalar(select(func.coalesce(func.sum(Assessment.weight), 0)).where(Assessment.offering_id == offering.id))
    if total + body.weight > 1.0001:
        raise AppError(422, "validation_error", f"Los pesos de la oferta sumarían más de 100 % (ya suman {total:.0%}).")
    a = Assessment(organization_id=offering.organization_id, offering_id=offering.id, **body.model_dump())
    db.add(a)
    db.flush()
    record(db, action="assessment.created", resource="assessment", resource_id=a.id, actor_id=principal.user.id,
           organization_id=a.organization_id, details={"title": a.title, "weight": a.weight})
    students = db.scalars(select(Enrollment.student_id).where(Enrollment.offering_id == offering.id,
                                                              Enrollment.status == "active"))
    notify(db, list(students), organization_id=a.organization_id, kind="assessment.created",
           title=f"Nueva evaluación: {a.title}", body=f"{offering.course.title} · peso {round(a.weight * 100)} %",
           link="/evaluaciones")
    db.commit()
    db.refresh(a)
    return _assessment_out(db, principal, a)


@router.post("/assessments/{assessment_id}/submissions", response_model=AssessmentOut, status_code=201)
def submit(assessment_id: uuid.UUID, body: SubmissionIn, db: DB, principal: Principal = require("learning")) -> AssessmentOut:
    a = db.get(Assessment, assessment_id)
    enrollment = a and db.scalar(select(Enrollment).where(Enrollment.offering_id == a.offering_id,
                                                           Enrollment.student_id == principal.user.id))
    if a is None or enrollment is None:
        raise not_found("Evaluación")
    if enrollment.status == "dropped":
        raise AppError(422, "validation_error", "La matrícula está retirada.")
    count = db.scalar(select(func.count()).select_from(AssessmentAttempt).where(
        AssessmentAttempt.assessment_id == a.id, AssessmentAttempt.student_id == principal.user.id)) or 0
    if count >= a.max_attempts:
        raise AppError(422, "validation_error", "Ya usaste todos los intentos permitidos.")
    now = datetime.now(UTC)
    attempt = AssessmentAttempt(assessment_id=a.id, student_id=principal.user.id, attempt_no=count + 1,
                                answer=body.answer, submitted_at=now, late=now > a.due_at)
    db.add(attempt)
    db.flush()
    service.ingest_event(db, enrollment=enrollment, event_id=uuid.uuid4(), event_type="assessment_submitted",
                         activity_id=None, occurred_at=now, duration_seconds=0, source="web",
                         payload={"assessment_id": str(a.id), "attempt_no": attempt.attempt_no, "late": attempt.late})
    record(db, action="assessment.submitted", resource="assessment", resource_id=a.id, actor_id=principal.user.id,
           organization_id=a.organization_id, details={"attempt_no": attempt.attempt_no, "late": attempt.late})
    db.commit()
    return _assessment_out(db, principal, a)


@router.get("/assessments/{assessment_id}/attempts", response_model=list[AttemptOut])
def list_attempts(assessment_id: uuid.UUID, db: DB, principal: CurrentPrincipal) -> list[AttemptOut]:
    a = db.get(Assessment, assessment_id)
    if a is None or not principal.can_see_org(a.organization_id):
        raise not_found("Evaluación")
    if not service.can_manage_offering(principal, a.offering):
        raise forbidden()
    rows = db.scalars(select(AssessmentAttempt).where(AssessmentAttempt.assessment_id == a.id)
                      .order_by(AssessmentAttempt.submitted_at))
    return [_attempt_out(t) for t in rows]


def _attempt_out(t: AssessmentAttempt) -> AttemptOut:
    return AttemptOut(id=t.id, assessment_id=t.assessment_id, student_id=t.student_id, student_name=t.student.full_name,
                      attempt_no=t.attempt_no, answer=t.answer, submitted_at=t.submitted_at, late=t.late,
                      score=t.score, feedback=t.feedback, graded_at=t.graded_at)


@router.patch("/attempts/{attempt_id}", response_model=AttemptOut)
def grade(attempt_id: uuid.UUID, body: GradeIn, db: DB, principal: CurrentPrincipal) -> AttemptOut:
    """Nota oficial registrada por el docente (§4.6). Todo cambio de nota queda auditado (§11.1)."""
    t = db.get(AssessmentAttempt, attempt_id)
    if t is None or not principal.can_see_org(t.assessment.organization_id):
        raise not_found("Intento")
    if not service.can_manage_offering(principal, t.assessment.offering):
        raise forbidden()
    if body.score > t.assessment.max_score:
        raise AppError(422, "validation_error", f"La nota máxima es {t.assessment.max_score:g}.")
    previous = t.score
    t.score, t.feedback = body.score, body.feedback
    t.graded_by, t.graded_at = principal.user.id, datetime.now(UTC)
    record(db, action="grade.recorded", resource="attempt", resource_id=t.id, actor_id=principal.user.id,
           organization_id=t.assessment.organization_id,
           details={"assessment": t.assessment.title, "student": t.student.full_name, "score": [previous, body.score]})
    notify(db, [t.student_id], organization_id=t.assessment.organization_id, kind="grade.recorded",
           title=f"Nota publicada: {t.assessment.title}",
           body=f"{body.score:g}/{t.assessment.max_score:g}" + (f" · {body.feedback}" if body.feedback else ""),
           link="/evaluaciones")
    enrollment = db.scalar(select(Enrollment).where(Enrollment.offering_id == t.assessment.offering_id,
                                                    Enrollment.student_id == t.student_id))
    if enrollment is not None:
        db.flush()
        try_auto_issue(db, enrollment)  # una nota puede completar los criterios del certificado
    db.commit()
    return _attempt_out(t)
