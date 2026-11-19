"""Ruta de aprendizaje DEMO (§4.2). Idempotente."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.academic.models import Course, CourseOffering, Enrollment
from app.modules.identity.models import Organization, User
from app.modules.paths.models import LearningPath, PathAssignment, PathStep


def run(db: Session) -> None:
    org = db.scalar(select(Organization).where(Organization.code == "ANDINO"))
    if org is None or db.scalar(select(LearningPath.id).where(LearningPath.organization_id == org.id).limit(1)):
        return
    courses = {c.code: c for c in db.scalars(select(Course).where(Course.organization_id == org.id))}
    coordinator = db.scalar(select(User).where(User.email == "coordinacion@andino.demo"))
    path = LearningPath(
        organization_id=org.id, code="RUTA-DATOS", title="Analista de datos junior",
        objective="Formar perfiles capaces de programar en Python, limpiar y analizar datos y entrenar modelos "
                  "supervisados básicos.",
        competencies=["Programación en Python", "Limpieza y análisis de datos", "Modelos supervisados"],
        target_weeks=30, status="published", created_by=coordinator.id,
    )
    path.steps = [PathStep(position=1, course_id=courses["PY-101"].id),
                  PathStep(position=2, course_id=courses["DS-201"].id),
                  PathStep(position=3, course_id=courses["ML-301"].id, min_grade=12)]
    db.add(path)
    db.add(LearningPath(
        organization_id=org.id, code="RUTA-WEB", title="Desarrollo web inicial (borrador)",
        objective="Primeros pasos en HTML y CSS para construir páginas estáticas accesibles.",
        competencies=["HTML semántico", "CSS"], target_weeks=8, created_by=coordinator.id,
        steps=[PathStep(position=1, course_id=courses["WEB-110"].id)],
    ))
    db.flush()
    # Se asigna a la cohorte de PY-101 (toda la promoción que empezó la ruta).
    py = db.scalar(select(CourseOffering).where(CourseOffering.course_id == courses["PY-101"].id))

    for sid in db.scalars(select(Enrollment.student_id).where(Enrollment.offering_id == py.id)):
        db.add(PathAssignment(organization_id=org.id, path_id=path.id, student_id=sid, assigned_by=coordinator.id,
                              source=f"cohorte {py.cohort} · PY-101", assigned_at=py.starts_on,
                              target_date=py.starts_on + timedelta(weeks=30)))
    db.commit()
