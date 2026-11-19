"""Endpoints de rutas de aprendizaje (§4.2).

Coordinación/administración (path.manage) crea, publica, versiona, asigna y autoriza excepciones.
Docentes y lectura amplia consultan rutas y avances; el estudiante ve solo sus asignaciones.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter
from pydantic import AwareDatetime, BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import DB, CurrentPrincipal, Principal, require
from app.core.errors import AppError, forbidden, not_found
from app.modules.academic.models import Course, Enrollment
from app.modules.academic.service import get_offering
from app.modules.audit.models import AuditLog
from app.modules.audit.service import record
from app.modules.identity.models import Role, User
from app.modules.notifications.service import notify
from app.modules.paths import service
from app.modules.paths.models import LearningPath, PathAssignment, PathStep

router = APIRouter(tags=["rutas"])


# ---------- contratos ----------

class StepIn(BaseModel):
    course_id: uuid.UUID
    min_grade: float | None = Field(default=None, ge=0, le=20)


class PathIn(BaseModel):
    code: str = Field(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    title: str = Field(min_length=3, max_length=160)
    objective: str = Field(min_length=10, max_length=2000)
    competencies: list[str] = Field(default_factory=list, max_length=20)
    target_weeks: int = Field(default=12, ge=1, le=104)
    steps: list[StepIn] = Field(min_length=1, max_length=20)

    @field_validator("code")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


class PathPatch(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=160)
    objective: str | None = Field(default=None, min_length=10, max_length=2000)
    competencies: list[str] | None = Field(default=None, max_length=20)
    target_weeks: int | None = Field(default=None, ge=1, le=104)
    steps: list[StepIn] | None = Field(default=None, min_length=1, max_length=20)


class StepOut(BaseModel):
    id: uuid.UUID
    position: int
    course_id: uuid.UUID
    course_code: str
    course_title: str
    min_grade: float | None


class PathOut(BaseModel):
    id: uuid.UUID
    code: str
    title: str
    objective: str
    competencies: list[str]
    target_weeks: int
    status: str
    version: int
    steps: list[StepOut]
    assigned: int
    completed: int
    updated_at: datetime


class StepProgressOut(BaseModel):
    step_id: uuid.UUID
    position: int
    course_id: uuid.UUID
    course_code: str
    course_title: str
    min_grade: float | None
    status: str
    progress: float
    grade: float | None
    offering_id: uuid.UUID | None
    available_offering_id: uuid.UUID | None
    available_offering_label: str | None
    note: str


class AssignmentOut(BaseModel):
    id: uuid.UUID
    path_id: uuid.UUID
    path_title: str
    path_objective: str
    competencies: list[str]
    student_id: uuid.UUID
    student_name: str
    source: str
    assigned_at: datetime
    target_date: datetime | None
    status: str
    progress: float
    completed_steps: int
    total_steps: int
    on_track: bool | None
    exceptions: list[dict]
    steps: list[StepProgressOut] | None = None
    next_step: StepProgressOut | None = None


# ---------- helpers ----------

def _path_out(db: DB, p: LearningPath) -> PathOut:
    rows = list(db.scalars(select(PathAssignment.status).where(PathAssignment.path_id == p.id,
                                                               PathAssignment.status != "cancelled")))
    return PathOut(
        id=p.id, code=p.code, title=p.title, objective=p.objective, competencies=p.competencies or [],
        target_weeks=p.target_weeks, status=p.status, version=p.version, updated_at=p.updated_at,
        steps=[StepOut(id=s.id, position=s.position, course_id=s.course_id, course_code=s.course.code,
                       course_title=s.course.title, min_grade=s.min_grade) for s in p.steps],
        assigned=len(rows), completed=sum(r == "completed" for r in rows),
    )


def _assignment_out(db: DB, a: PathAssignment, detail: bool) -> AssignmentOut:
    p = service.refresh_status(db, a)
    sp = lambda s: StepProgressOut(**s.__dict__)  # noqa: E731
    return AssignmentOut(
        id=a.id, path_id=a.path_id, path_title=a.path.title, path_objective=a.path.objective,
        competencies=a.path.competencies or [], student_id=a.student_id, student_name=a.student.full_name,
        source=a.source, assigned_at=a.assigned_at, target_date=a.target_date, status=a.status,
        progress=p.progress, completed_steps=p.completed_steps, total_steps=p.total_steps, on_track=p.on_track,
        exceptions=a.exceptions or [], steps=[sp(s) for s in p.steps] if detail else None,
        next_step=sp(p.next_step) if detail and p.next_step else None,
    )


def _get_path(db: DB, principal: Principal, path_id: uuid.UUID) -> LearningPath:
    p = db.get(LearningPath, path_id)
    if p is None or not principal.can_see_org(p.organization_id):
        raise not_found("Ruta")
    return p


def _staff(principal: Principal) -> bool:
    return principal.can("path.manage") or principal.can("course.read.all") or principal.can("assessment.manage")


def _build_steps(db: DB, principal: Principal, steps: list[StepIn]) -> list[PathStep]:
    seen = set()
    out = []
    for i, s in enumerate(steps, start=1):
        course = db.get(Course, s.course_id)
        if course is None or not principal.can_see_org(course.organization_id):
            raise AppError(422, "validation_error", "Hay un curso que no existe en la institución.")
        if course.status == "archived":
            raise AppError(422, "validation_error", f"El curso {course.code} está archivado.")
        if course.id in seen:
            raise AppError(422, "validation_error", f"El curso {course.code} está repetido en la ruta.")
        seen.add(course.id)
        out.append(PathStep(position=i, course_id=course.id, min_grade=s.min_grade))
    return out


# ---------- rutas ----------

@router.get("/paths", response_model=list[PathOut])
def list_paths(db: DB, principal: CurrentPrincipal) -> list[PathOut]:
    if not _staff(principal):
        raise forbidden()
    q = select(LearningPath).order_by(LearningPath.status, LearningPath.title)
    if not principal.is_global:
        q = q.where(LearningPath.organization_id == principal.organization_id)
    return [_path_out(db, p) for p in db.scalars(q)]


@router.post("/paths", response_model=PathOut, status_code=201)
def create_path(body: PathIn, db: DB, principal: Principal = require("path.manage")) -> PathOut:
    path = LearningPath(organization_id=principal.organization_id, code=body.code, title=body.title.strip(),
                        objective=body.objective.strip(), competencies=[c.strip() for c in body.competencies if c.strip()],
                        target_weeks=body.target_weeks, created_by=principal.user.id)
    path.steps = _build_steps(db, principal, body.steps)
    db.add(path)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "conflict", "Ya existe una ruta con ese código.") from None
    record(db, action="path.created", resource="path", resource_id=path.id, actor_id=principal.user.id,
           organization_id=path.organization_id, details={"code": path.code, "steps": len(path.steps)})
    db.commit()
    db.refresh(path)
    return _path_out(db, path)


@router.patch("/paths/{path_id}", response_model=PathOut)
def update_path(path_id: uuid.UUID, body: PathPatch, db: DB, principal: Principal = require("path.manage")) -> PathOut:
    """Editar una ruta publicada crea una nueva versión y queda en el historial (§4.2)."""
    p = _get_path(db, principal, path_id)
    if p.status == "archived":
        raise AppError(422, "validation_error", "La ruta está archivada.")
    changes = {}
    for field in ("title", "objective", "competencies", "target_weeks"):
        value = getattr(body, field)
        if value is not None and value != getattr(p, field):
            changes[field] = [getattr(p, field), value]
            setattr(p, field, value)
    if body.steps is not None:
        new_steps = _build_steps(db, principal, body.steps)
        old = [(str(s.course_id), s.min_grade) for s in p.steps]
        new = [(str(s.course_id), s.min_grade) for s in new_steps]
        if old != new:
            changes["steps"] = [[s.course.code for s in p.steps],
                                [db.get(Course, s.course_id).code for s in new_steps]]
            p.steps = new_steps
    if changes:
        if p.status == "published":
            p.version += 1
        record(db, action="path.updated", resource="path", resource_id=p.id, actor_id=principal.user.id,
               organization_id=p.organization_id, details={"version": p.version, **changes})
        db.commit()
        db.refresh(p)
    return _path_out(db, p)


class StatusIn(BaseModel):
    status: str = Field(pattern="^(published|archived)$")


@router.post("/paths/{path_id}/status", response_model=PathOut)
def set_status(path_id: uuid.UUID, body: StatusIn, db: DB, principal: Principal = require("path.manage")) -> PathOut:
    p = _get_path(db, principal, path_id)
    if body.status == "published":
        drafts = [s.course.code for s in p.steps if s.course.status != "published"]
        if drafts:
            raise AppError(422, "validation_error", f"Publica antes los cursos: {', '.join(drafts)}.")
    if body.status != p.status:
        record(db, action=f"path.{body.status}", resource="path", resource_id=p.id, actor_id=principal.user.id,
               organization_id=p.organization_id, details={"version": p.version})
        p.status = body.status
        db.commit()
    return _path_out(db, p)


class HistoryItem(BaseModel):
    occurred_at: datetime
    action: str
    actor_name: str | None
    details: dict | None


@router.get("/paths/{path_id}/history", response_model=list[HistoryItem])
def history(path_id: uuid.UUID, db: DB, principal: CurrentPrincipal) -> list[HistoryItem]:
    """Historial de cambios de la ruta, tomado de la bitácora inmutable (§4.2, §11.1)."""
    if not _staff(principal):
        raise forbidden()
    p = _get_path(db, principal, path_id)
    rows = list(db.scalars(select(AuditLog).where(AuditLog.resource == "path", AuditLog.resource_id == str(p.id))
                           .order_by(AuditLog.occurred_at.desc())))
    names = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_({r.actor_id for r in rows if r.actor_id})))}
    return [HistoryItem(occurred_at=r.occurred_at, action=r.action, actor_name=names.get(r.actor_id), details=r.details)
            for r in rows]


# ---------- asignaciones ----------

class AssignIn(BaseModel):
    student_ids: list[uuid.UUID] = Field(default_factory=list, max_length=500)
    cohort_offering_id: uuid.UUID | None = None  # asigna a toda la cohorte de esa oferta
    target_date: AwareDatetime | None = None


@router.post("/paths/{path_id}/assignments", status_code=201)
def assign(path_id: uuid.UUID, body: AssignIn, db: DB, principal: Principal = require("path.manage")) -> dict:
    p = _get_path(db, principal, path_id)
    if p.status != "published":
        raise AppError(422, "validation_error", "Solo se asignan rutas publicadas.")
    if not body.student_ids and not body.cohort_offering_id:
        raise AppError(422, "validation_error", "Indica estudiantes o una cohorte.")
    targets: dict[uuid.UUID, str] = {}
    if body.cohort_offering_id:
        offering = get_offering(db, principal, body.cohort_offering_id)
        for sid in db.scalars(select(Enrollment.student_id).where(Enrollment.offering_id == offering.id,
                                                                  Enrollment.status != "dropped")):
            targets[sid] = f"cohorte {offering.cohort} · {offering.course.code}"
    if body.student_ids:
        valid = set(db.scalars(select(User.id).where(User.id.in_(body.student_ids), User.organization_id == p.organization_id,
                                                     User.roles.any(Role.code == "estudiante"))))
        if len(valid) != len(set(body.student_ids)):
            raise AppError(422, "validation_error", "Todos deben ser estudiantes de la institución.")
        for sid in valid:
            targets.setdefault(sid, "individual")
    active = set(db.scalars(select(PathAssignment.student_id).where(PathAssignment.path_id == p.id,
                                                                    PathAssignment.status == "active")))
    created = []
    for sid, source in targets.items():
        if sid in active:
            continue
        created.append(PathAssignment(organization_id=p.organization_id, path_id=p.id, student_id=sid,
                                      assigned_by=principal.user.id, source=source, target_date=body.target_date))
    db.add_all(created)
    record(db, action="path.assigned", resource="path", resource_id=p.id, actor_id=principal.user.id,
           organization_id=p.organization_id, details={"students": len(created), "skipped": len(targets) - len(created)})
    notify(db, [a.student_id for a in created], organization_id=p.organization_id, kind="path.assigned",
           title=f"Nueva ruta de aprendizaje: {p.title}", body=p.objective[:140], link="/rutas")
    db.commit()
    return {"created": len(created), "skipped": len(targets) - len(created)}


@router.get("/paths/{path_id}/assignments", response_model=list[AssignmentOut])
def path_assignments(path_id: uuid.UUID, db: DB, principal: CurrentPrincipal) -> list[AssignmentOut]:
    if not (principal.can("path.manage") or principal.can("audit.read") or principal.can("assessment.manage")):
        raise forbidden()  # avance nominal: gestión, auditoría y docentes; el analista no (§3)
    p = _get_path(db, principal, path_id)
    rows = list(db.scalars(select(PathAssignment).where(PathAssignment.path_id == p.id,
                                                        PathAssignment.status != "cancelled")))
    out = [_assignment_out(db, a, detail=False) for a in rows]
    db.commit()  # refresh_status puede cerrar asignaciones completadas
    return sorted(out, key=lambda a: (a.status == "completed", a.progress, a.student_name))


class ExceptionIn(BaseModel):
    step_id: uuid.UUID
    reason: str = Field(min_length=10, max_length=500)


@router.post("/path-assignments/{assignment_id}/exceptions", response_model=AssignmentOut)
def grant_exception(assignment_id: uuid.UUID, body: ExceptionIn, db: DB,
                    principal: Principal = require("path.manage")) -> AssignmentOut:
    """Excepción autorizada (§4.2): dispensa una etapa con motivo, p. ej. por convalidación."""
    a = db.get(PathAssignment, assignment_id)
    if a is None or not principal.can_see_org(a.organization_id):
        raise not_found("Asignación")
    if body.step_id not in {s.id for s in a.path.steps}:
        raise AppError(422, "validation_error", "La etapa no pertenece a la ruta.")
    if any(str(x["step_id"]) == str(body.step_id) for x in a.exceptions or []):
        raise AppError(409, "conflict", "Esa etapa ya está dispensada.")
    a.exceptions = [*(a.exceptions or []), {"step_id": str(body.step_id), "reason": body.reason.strip(),
                                            "granted_by": principal.user.full_name,
                                            "granted_at": datetime.now().astimezone().isoformat()}]
    record(db, action="path.exception", resource="path", resource_id=a.path_id, actor_id=principal.user.id,
           organization_id=a.organization_id, details={"student": a.student.full_name, "reason": body.reason.strip()})
    out = _assignment_out(db, a, detail=True)
    db.commit()
    return out


@router.get("/my/paths", response_model=list[AssignmentOut])
def my_paths(db: DB, principal: Principal = require("learning")) -> list[AssignmentOut]:
    rows = list(db.scalars(select(PathAssignment).where(PathAssignment.student_id == principal.user.id,
                                                        PathAssignment.status != "cancelled")
                           .order_by(PathAssignment.assigned_at.desc())))
    out = [_assignment_out(db, a, detail=True) for a in rows]
    db.commit()
    return out


@router.get("/path-assignments/{assignment_id}", response_model=AssignmentOut)
def get_assignment(assignment_id: uuid.UUID, db: DB, principal: CurrentPrincipal) -> AssignmentOut:
    a = db.get(PathAssignment, assignment_id)
    if a is None or not principal.can_see_org(a.organization_id):
        raise not_found("Asignación")
    if a.student_id != principal.user.id and not (principal.can("path.manage") or principal.can("audit.read")
                                                  or principal.can("assessment.manage")):
        raise not_found("Asignación")
    out = _assignment_out(db, a, detail=True)
    db.commit()
    return out

