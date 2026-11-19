"""Endpoints de dominio de habilidades (§4.9, §10.2 GET /analytics/skill-mastery).

- Catálogo jerárquico: lo consulta cualquier rol de la institución; lo gestiona coordinación/administración.
- Heatmap competencia × nivel: personal con analytics.read (agregado).
- Detalle por estudiante: el propio estudiante, sus docentes, gestión y auditoría.
- Validación docente: el docente de una oferta donde el estudiante cursa la competencia, o la gestión.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import DB, CurrentPrincipal, Principal, require
from app.core.errors import AppError, forbidden, not_found
from app.modules.academic.models import Assessment, Course, CourseOffering, Enrollment
from app.modules.academic.service import can_manage_offering, offerings_query
from app.modules.audit.service import record
from app.modules.identity.models import User
from app.modules.notifications.service import notify
from app.modules.skills import service
from app.modules.skills.models import LEVELS, AssessmentSkill, CourseSkill, Skill, SkillValidation

router = APIRouter(tags=["habilidades"])


class SkillIn(BaseModel):
    code: str = Field(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=3, max_length=160)
    description: str = Field(default="", max_length=1000)
    parent_id: uuid.UUID | None = None

    @field_validator("code")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


class SkillOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: str
    parent_id: uuid.UUID | None
    courses: list[str]


@router.get("/skills", response_model=list[SkillOut])
def catalog(db: DB, principal: CurrentPrincipal) -> list[SkillOut]:
    skills = list(db.scalars(select(Skill).where(Skill.organization_id == principal.organization_id).order_by(Skill.code)))
    courses = {}
    for cs, code in db.execute(select(CourseSkill, Course.code).join(Course, Course.id == CourseSkill.course_id)):
        courses.setdefault(cs.skill_id, []).append(code)
    return [SkillOut(id=s.id, code=s.code, name=s.name, description=s.description, parent_id=s.parent_id,
                     courses=sorted(courses.get(s.id, []))) for s in skills]


@router.post("/skills", response_model=SkillOut, status_code=201)
def create_skill(body: SkillIn, db: DB, principal: Principal = require("course.manage")) -> SkillOut:
    if body.parent_id:
        parent = db.get(Skill, body.parent_id)
        if parent is None or parent.organization_id != principal.organization_id:
            raise AppError(422, "validation_error", "La competencia padre no existe.")
        if parent.parent_id is not None:
            raise AppError(422, "validation_error", "El catálogo tiene dos niveles: área y competencia.")
    skill = Skill(organization_id=principal.organization_id, code=body.code, name=body.name.strip(),
                  description=body.description.strip(), parent_id=body.parent_id)
    db.add(skill)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "conflict", "Ya existe una competencia con ese código.") from None
    record(db, action="skill.created", resource="skill", resource_id=skill.id, actor_id=principal.user.id,
           organization_id=skill.organization_id, details={"code": skill.code})
    db.commit()
    return SkillOut(id=skill.id, code=skill.code, name=skill.name, description=skill.description,
                    parent_id=skill.parent_id, courses=[])


class CourseSkillIn(BaseModel):
    skill_id: uuid.UUID
    weight: float = Field(default=1.0, gt=0, le=1)


@router.put("/courses/{course_id}/skills")
def set_course_skills(course_id: uuid.UUID, body: list[CourseSkillIn], db: DB,
                      principal: Principal = require("course.manage")) -> dict:
    """Competencias del curso en orden: la 1.ª se evidencia en la unidad 1, la 2.ª en la unidad 2… (D34)."""
    course = db.get(Course, course_id)
    if course is None or not principal.can_see_org(course.organization_id):
        raise not_found("Curso")
    for item in body:
        s = db.get(Skill, item.skill_id)
        if s is None or s.organization_id != course.organization_id or s.parent_id is None:
            raise AppError(422, "validation_error", "Usa competencias (no áreas) de la institución.")
    for cs in db.scalars(select(CourseSkill).where(CourseSkill.course_id == course.id)):
        db.delete(cs)
    db.flush()
    for i, item in enumerate(body, start=1):
        db.add(CourseSkill(course_id=course.id, skill_id=item.skill_id, position=i, weight=item.weight))
    record(db, action="skill.course_linked", resource="course", resource_id=course.id, actor_id=principal.user.id,
           organization_id=course.organization_id, details={"skills": len(body)})
    db.commit()
    return {"course": course.code, "skills": len(body)}


@router.put("/assessments/{assessment_id}/skills")
def set_assessment_skills(assessment_id: uuid.UUID, skill_ids: list[uuid.UUID], db: DB, principal: CurrentPrincipal) -> dict:
    a = db.get(Assessment, assessment_id)
    if a is None or not principal.can_see_org(a.organization_id):
        raise not_found("Evaluación")
    if not can_manage_offering(principal, a.offering):
        raise forbidden()
    allowed = set(db.scalars(select(CourseSkill.skill_id).where(CourseSkill.course_id == a.offering.course_id)))
    if not set(skill_ids) <= allowed:
        raise AppError(422, "validation_error", "Solo competencias vinculadas al curso.")
    for link in db.scalars(select(AssessmentSkill).where(AssessmentSkill.assessment_id == a.id)):
        db.delete(link)
    db.flush()
    for sid in dict.fromkeys(skill_ids):
        db.add(AssessmentSkill(assessment_id=a.id, skill_id=sid))
    db.commit()
    return {"assessment": a.title, "skills": len(set(skill_ids))}


@router.get("/analytics/skill-mastery")
def skill_mastery(db: DB, principal: CurrentPrincipal, offering_id: uuid.UUID | None = None) -> dict:
    """Heatmap de §4.9: estudiantes por competencia y nivel, estimado y validado por separado."""
    if not principal.can("analytics.read"):
        raise forbidden()
    q = offerings_query(principal)
    if offering_id:
        q = q.where(CourseOffering.id == offering_id)
    return service.heatmap(db, list(db.scalars(q)))


class EvidenceOut(BaseModel):
    source: str
    label: str
    value: float
    weight: float


class StudentSkillOut(BaseModel):
    skill_id: uuid.UUID
    code: str
    name: str
    area: str | None
    score: float | None
    estimated_level: int | None
    estimated_label: str | None
    validated_level: int | None
    validated_label: str | None
    validated_note: str | None
    validated_by: str | None
    validated_at: datetime | None
    evidences: list[EvidenceOut]


def _student_view(db: DB, student_id: uuid.UUID, offering_ids=None) -> list[StudentSkillOut]:
    states = service.student_states(db, student_id, offering_ids)
    if not states:
        return []
    skills = {s.id: s for s in db.scalars(select(Skill).where(Skill.id.in_(states.keys())))}
    parents = {s.id: s.name for s in db.scalars(select(Skill).where(Skill.id.in_({s.parent_id for s in skills.values() if s.parent_id})))}
    names = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_({st.validated_by for st in states.values() if st.validated_by})))}
    out = []
    for sid, st in states.items():
        s = skills[sid]
        out.append(StudentSkillOut(
            skill_id=sid, code=s.code, name=s.name, area=parents.get(s.parent_id), score=st.score,
            estimated_level=st.estimated_level, estimated_label=LEVELS[st.estimated_level - 1] if st.estimated_level else None,
            validated_level=st.validated_level, validated_label=LEVELS[st.validated_level - 1] if st.validated_level else None,
            validated_note=st.validated_note, validated_by=names.get(st.validated_by), validated_at=st.validated_at,
            evidences=[EvidenceOut(**e.__dict__) for e in st.evidences],
        ))
    return sorted(out, key=lambda x: x.code)


@router.get("/my/skills", response_model=list[StudentSkillOut])
def my_skills(db: DB, principal: Principal = require("learning")) -> list[StudentSkillOut]:
    return _student_view(db, principal.user.id)


def _can_see_student(db: DB, principal: Principal, student_id: uuid.UUID) -> list[uuid.UUID] | None:
    """Ofertas del estudiante visibles para quien consulta (None = todas, para gestión/auditoría)."""
    student = db.get(User, student_id)
    if student is None or not principal.can_see_org(student.organization_id):
        raise not_found("Estudiante")
    if principal.can("course.manage") or principal.can("audit.read"):
        return None
    if principal.can("assessment.manage"):  # docente: solo sus ofertas donde está el estudiante
        ids = list(db.scalars(select(CourseOffering.id).join(Enrollment, Enrollment.offering_id == CourseOffering.id).where(
            Enrollment.student_id == student_id, CourseOffering.instructor_id == principal.user.id)))
        if ids:
            return ids
    raise not_found("Estudiante")


@router.get("/skills/students/{student_id}", response_model=list[StudentSkillOut])
def student_skills(student_id: uuid.UUID, db: DB, principal: CurrentPrincipal) -> list[StudentSkillOut]:
    return _student_view(db, student_id, _can_see_student(db, principal, student_id))


class ValidationIn(BaseModel):
    student_id: uuid.UUID
    skill_id: uuid.UUID
    level: int = Field(ge=1, le=5)
    note: str = Field(min_length=5, max_length=1000)


@router.post("/skills/validations", response_model=list[StudentSkillOut], status_code=201)
def validate(body: ValidationIn, db: DB, principal: CurrentPrincipal) -> list[StudentSkillOut]:
    """El docente valida o corrige el nivel con evidencia propia (§4.9). Queda auditado y se avisa al estudiante."""
    offering_ids = _can_see_student(db, principal, body.student_id)
    if not (principal.can("course.manage") or principal.can("assessment.manage")):
        raise forbidden()
    skill = db.get(Skill, body.skill_id)
    if skill is None or not principal.can_see_org(skill.organization_id):
        raise not_found("Competencia")
    states = service.student_states(db, body.student_id, offering_ids)
    if body.skill_id not in states and offering_ids is not None:
        raise AppError(422, "validation_error", "La competencia no se trabaja en tus cursos con este estudiante.")
    estimated = states.get(body.skill_id).estimated_level if body.skill_id in states else None
    db.add(SkillValidation(organization_id=skill.organization_id, student_id=body.student_id, skill_id=skill.id,
                           level=body.level, note=body.note.strip(), estimated_level_at_validation=estimated,
                           validated_by=principal.user.id))
    record(db, action="skill.validated", resource="skill", resource_id=skill.id, actor_id=principal.user.id,
           organization_id=skill.organization_id,
           details={"student": db.get(User, body.student_id).full_name, "level": LEVELS[body.level - 1],
                    "estimated": LEVELS[estimated - 1] if estimated else None})
    notify(db, [body.student_id], organization_id=skill.organization_id, kind="skill.validated",
           title=f"Tu docente validó «{skill.name}»: {LEVELS[body.level - 1]}", body=body.note.strip()[:140],
           link="/habilidades")
    db.commit()
    return _student_view(db, body.student_id, offering_ids)

