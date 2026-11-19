"""Catálogo DEMO de competencias y vínculos (§4.9). Idempotente."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.academic.models import Assessment, Course, CourseOffering
from app.modules.identity.models import Organization
from app.modules.skills.models import AssessmentSkill, CourseSkill, Skill

# área: (nombre, [(código, nombre)])
CATALOG = {
    "PROG": ("Programación", [("PROG-PY", "Sintaxis de Python"), ("PROG-CTRL", "Control de flujo"),
                              ("PROG-FUNC", "Funciones y modularidad")]),
    "DATA": ("Datos", [("DATA-EXP", "Exploración de datos"), ("DATA-LIMP", "Limpieza de datos"),
                       ("DATA-AGG", "Agregación y reportes")]),
    "ML": ("Aprendizaje automático", [("ML-FUND", "Fundamentos de ML"), ("ML-SUP", "Modelos supervisados"),
                                      ("ML-EVAL", "Evaluación de modelos")]),
}
# Curso → competencias en el orden de sus unidades.
COURSES = {"PY-101": ["PROG-PY", "PROG-CTRL", "PROG-FUNC"], "DS-201": ["DATA-EXP", "DATA-LIMP", "DATA-AGG"],
           "ML-301": ["ML-FUND", "ML-SUP", "ML-EVAL"]}
ASSESSMENTS = {
    "Cuestionario de sintaxis": ["PROG-PY"], "Proyecto: control de flujo": ["PROG-CTRL"],
    "Examen final": ["PROG-PY", "PROG-CTRL", "PROG-FUNC"], "Informe de exploración": ["DATA-EXP"],
    "Limpieza de datos": ["DATA-LIMP"], "Reporte final": ["DATA-AGG", "DATA-LIMP"],
    "Quiz de fundamentos": ["ML-FUND"], "Clasificador": ["ML-SUP"], "Comparación de modelos": ["ML-EVAL"],
}


def run(db: Session) -> None:
    org = db.scalar(select(Organization).where(Organization.code == "ANDINO"))
    if org is None or db.scalar(select(Skill.id).where(Skill.organization_id == org.id).limit(1)):
        return
    by_code = {}
    for area_code, (area_name, children) in CATALOG.items():
        area = Skill(organization_id=org.id, code=area_code, name=area_name)
        db.add(area)
        db.flush()
        for code, name in children:
            by_code[code] = Skill(organization_id=org.id, code=code, name=name, parent_id=area.id)
            db.add(by_code[code])
    db.flush()
    courses = {c.code: c for c in db.scalars(select(Course).where(Course.organization_id == org.id))}
    for course_code, skill_codes in COURSES.items():
        for i, code in enumerate(skill_codes, start=1):
            db.add(CourseSkill(course_id=courses[course_code].id, skill_id=by_code[code].id, position=i))
    for a in db.scalars(select(Assessment).join(CourseOffering).where(CourseOffering.organization_id == org.id)):
        for code in ASSESSMENTS.get(a.title, []):
            db.add(AssessmentSkill(assessment_id=a.id, skill_id=by_code[code].id))
    db.commit()
