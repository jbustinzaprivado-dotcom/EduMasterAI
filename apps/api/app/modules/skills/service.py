"""Motor de dominio v1 (§4.9, decisión D34): evidencias normalizadas → nivel estimado.

Evidencias por competencia:
- Nota oficial (mejor intento calificado) de cada evaluación vinculada: valor nota/máximo, peso 2 × peso de la evaluación.
- Avance en la unidad vinculada (actividades obligatorias completadas / total de la unidad): peso 0.5.
Puntaje = Σ(peso·valor) / (Σ peso + 0.5). El 0.5 extra actúa como prudencia: con poca evidencia el nivel no sube.
Niveles: <0.2 principiante · <0.4 elemental · <0.6 intermedio · <0.8 avanzado · ≥0.8 experto.
Es una ESTIMACIÓN (reglas v1); el nivel oficial es el validado por el docente. La cabeza B de §9.1 la reemplazará.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.academic.models import Assessment, AssessmentAttempt, CourseOffering, Enrollment
from app.modules.academic.service import completed_activity_ids
from app.modules.skills.models import LEVELS, AssessmentSkill, CourseSkill, Skill, SkillValidation

ENGINE = "dominio-reglas-v1"
PRIOR = 0.5
THRESHOLDS = [0.2, 0.4, 0.6, 0.8]


def level_of(score: float) -> int:
    """1..5"""
    return 1 + sum(score >= t for t in THRESHOLDS)


@dataclass
class Evidence:
    source: str  # evaluacion | unidad
    label: str
    value: float
    weight: float


@dataclass
class SkillState:
    skill_id: uuid.UUID
    score: float | None = None
    estimated_level: int | None = None
    evidences: list[Evidence] = field(default_factory=list)
    validated_level: int | None = None
    validated_note: str | None = None
    validated_by: uuid.UUID | None = None
    validated_at: object = None


def student_states(db: Session, student_id: uuid.UUID, offering_ids: list[uuid.UUID] | None = None) -> dict[uuid.UUID, SkillState]:
    """Estado de cada competencia del estudiante a partir de sus matrículas (opcionalmente solo algunas ofertas)."""
    q = select(Enrollment).where(Enrollment.student_id == student_id, Enrollment.status != "dropped")
    if offering_ids is not None:
        q = q.where(Enrollment.offering_id.in_(offering_ids))
    enrollments = list(db.scalars(q))
    evidences: dict[uuid.UUID, list[Evidence]] = defaultdict(list)

    for e in enrollments:
        offering: CourseOffering = e.offering
        course_skills = list(db.scalars(select(CourseSkill).where(CourseSkill.course_id == offering.course_id)
                                        .order_by(CourseSkill.position)))
        if not course_skills:
            continue
        done = completed_activity_ids(db, student_id, offering.id)
        units = list(offering.course.units)
        for cs in course_skills:
            if cs.position <= len(units):
                unit = units[cs.position - 1]
                required = [a.id for a in unit.activities if a.required]
                if required:
                    ratio = sum(a in done for a in required) / len(required)
                    evidences[cs.skill_id].append(Evidence("unidad", f"{offering.course.code} · Unidad {unit.position}: "
                                                           f"{unit.title}", round(ratio, 3), 0.5 * cs.weight))
        assessments = list(db.scalars(select(Assessment).where(Assessment.offering_id == offering.id)))
        links = defaultdict(list)
        for link in db.scalars(select(AssessmentSkill).where(AssessmentSkill.assessment_id.in_([a.id for a in assessments]))):
            links[link.assessment_id].append(link.skill_id)
        for a in assessments:
            graded = [t.score for t in db.scalars(select(AssessmentAttempt).where(
                AssessmentAttempt.assessment_id == a.id, AssessmentAttempt.student_id == student_id,
                AssessmentAttempt.score.is_not(None)))]
            if not graded:
                continue
            for skill_id in links.get(a.id, []):
                evidences[skill_id].append(Evidence("evaluacion", f"{offering.course.code} · {a.title}",
                                                    round(max(graded) / a.max_score, 3), 2 * a.weight))

    states: dict[uuid.UUID, SkillState] = {}
    for skill_id, evs in evidences.items():
        total_w = sum(ev.weight for ev in evs)
        score = sum(ev.weight * ev.value for ev in evs) / (total_w + PRIOR)
        states[skill_id] = SkillState(skill_id=skill_id, score=round(score, 3), estimated_level=level_of(score), evidences=evs)

    for v in db.scalars(select(SkillValidation).where(SkillValidation.student_id == student_id)
                        .order_by(SkillValidation.validated_at)):
        s = states.setdefault(v.skill_id, SkillState(skill_id=v.skill_id))
        s.validated_level, s.validated_note, s.validated_by, s.validated_at = v.level, v.note, v.validated_by, v.validated_at
    return states


def skills_of_offerings(db: Session, offerings: list[CourseOffering]) -> list[Skill]:
    course_ids = {o.course_id for o in offerings}
    if not course_ids:
        return []
    ids = set(db.scalars(select(CourseSkill.skill_id).where(CourseSkill.course_id.in_(course_ids))))
    return list(db.scalars(select(Skill).where(Skill.id.in_(ids)).order_by(Skill.code))) if ids else []


def heatmap(db: Session, offerings: list[CourseOffering]) -> dict:
    """Matriz competencia × nivel con el número de estudiantes (estimado y validado por separado)."""
    skills = skills_of_offerings(db, offerings)
    students = set(db.scalars(select(Enrollment.student_id).where(
        Enrollment.offering_id.in_([o.id for o in offerings]), Enrollment.status != "dropped"))) if offerings else set()
    offering_ids = [o.id for o in offerings]
    est = {s.id: [0] * 5 for s in skills}
    val = {s.id: [0] * 5 for s in skills}
    for sid in students:
        for skill_id, state in student_states(db, sid, offering_ids).items():
            if skill_id not in est:
                continue
            if state.estimated_level:
                est[skill_id][state.estimated_level - 1] += 1
            if state.validated_level:
                val[skill_id][state.validated_level - 1] += 1
    return {
        "levels": LEVELS, "engine": ENGINE, "students": len(students),
        "rows": [{"skill_id": str(s.id), "code": s.code, "name": s.name, "estimated": est[s.id], "validated": val[s.id]}
                 for s in skills],
    }
