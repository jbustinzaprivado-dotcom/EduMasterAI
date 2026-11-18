"""Datos académicos DEMO (decisión D06): cursos, ofertas, matrículas, evaluaciones y 6 semanas de historia.

La historia se genera con perfiles sintéticos de estudiante (constante, irregular y en riesgo) para que
los paneles muestren patrones creíbles. Es reproducible (semilla fija) y todo va marcado como DEMO
(source="import", payload {"demo": true}). No representa a personas ni resultados reales.
"""

import random
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

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
from app.modules.academic.service import recompute_progress
from app.modules.identity.models import Organization, Role, User

# Las ofertas DEMO están en distintos momentos del ciclo: PY-101 casi termina, ML-301 va por la mitad.

# (código, título, nivel, estado, [(unidad, [(actividad, tipo, minutos)])])
COURSES = {
    "ANDINO": [
        ("PY-101", "Fundamentos de Python", "basico", "published", [
            ("Primeros pasos", [("Instalación del entorno", "lectura", 15), ("Variables y tipos de datos", "video", 20),
                                ("Práctica: calculadora", "practica", 40)]),
            ("Control de flujo", [("Condicionales", "video", 20), ("Bucles for y while", "lectura", 25),
                                  ("Práctica: adivina el número", "practica", 45)]),
            ("Funciones", [("Funciones y parámetros", "video", 25), ("Módulos y paquetes", "lectura", 20),
                           ("Práctica: biblioteca de utilidades", "practica", 50)]),
        ]),
        ("DS-201", "Análisis de datos con Pandas", "intermedio", "published", [
            ("Estructuras de datos", [("Series y DataFrames", "video", 25), ("Lectura de CSV y Excel", "lectura", 20),
                                      ("Práctica: explorar un dataset", "practica", 45)]),
            ("Limpieza", [("Valores nulos y duplicados", "video", 25), ("Tipos y fechas", "lectura", 20),
                          ("Práctica: limpiar ventas", "practica", 50)]),
            ("Agregación", [("groupby y pivot", "video", 30), ("Práctica: reporte mensual", "practica", 55)]),
        ]),
        ("ML-301", "Introducción al Machine Learning", "avanzado", "published", [
            ("Fundamentos", [("Aprendizaje supervisado", "video", 30), ("Train, validación y test", "lectura", 25)]),
            ("Modelos clásicos", [("Regresión logística", "video", 35), ("Árboles y boosting", "lectura", 30),
                                  ("Práctica: clasificador", "practica", 60)]),
            ("Evaluación", [("Métricas y calibración", "video", 30), ("Práctica: comparar modelos", "practica", 60)]),
        ]),
        ("WEB-110", "Desarrollo web con HTML y CSS", "basico", "draft", [
            ("Estructura", [("Etiquetas HTML", "video", 20)]),
        ]),
    ],
    "PACIFICO": [
        ("ATN-100", "Atención al cliente", "basico", "published", [
            ("Comunicación", [("Escucha activa", "video", 20), ("Práctica: role play", "practica", 30)]),
        ]),
    ],
}

# (institución, curso, docente, cohorte, estudiantes o None = todos, inició hace N días, duración en días,
#  evaluaciones [(título, tipo, peso, día de vencimiento)])
OFFERINGS = [
    ("ANDINO", "PY-101", "docente@andino.demo", "Grupo A", None, 63, 70,
     [("Cuestionario de sintaxis", "opcion_multiple", 0.2, 15), ("Proyecto: control de flujo", "practica", 0.3, 35),
      ("Examen final", "respuesta_corta", 0.5, 68)]),
    ("ANDINO", "DS-201", "docente2@andino.demo", "Grupo A", 8, 42, 75,
     [("Informe de exploración", "archivo", 0.3, 18), ("Limpieza de datos", "practica", 0.3, 38),
      ("Reporte final", "archivo", 0.4, 72)]),
    ("ANDINO", "ML-301", "docente@andino.demo", "Grupo B", 6, 30, 70,
     [("Quiz de fundamentos", "verdadero_falso", 0.25, 14), ("Clasificador", "practica", 0.35, 34),
      ("Comparación de modelos", "archivo", 0.4, 66)]),
    ("PACIFICO", "ATN-100", "docente@pacifico.demo", "Turno mañana", None, 20, 40,
     [("Role play evaluado", "practica", 0.5, 30)]),
]

# Perfiles sintéticos: probabilidad diaria de estudiar, de completar lo que abre, y nota media esperada.
# stop: fracción del curso tras la cual el estudiante en riesgo deja de conectarse.
PROFILES = {
    "constante": dict(study=0.55, complete=0.85, score=16.5, late=0.05, stop=None),
    "irregular": dict(study=0.24, complete=0.55, score=12.5, late=0.30, stop=None),
    "en_riesgo": dict(study=0.30, complete=0.50, score=9.5, late=0.55, stop=0.3),
}


# La cuenta DEMO de estudiante siempre es "en riesgo": sirve para mostrar la alerta en la exposición.
FIXED_PROFILES = {"estudiante@andino.demo": "en_riesgo"}


def _assign_profiles(students: list[User], seed: int) -> dict[uuid.UUID, str]:
    """Reparto reproducible (ordenado por correo, no por UUID): 45 % constante, 35 % irregular, 20 % en riesgo."""
    students = sorted(students, key=lambda u: u.email)
    n = len(students)
    n_risk, n_irregular = round(n * 0.2), round(n * 0.35)
    names = ["en_riesgo"] * n_risk + ["irregular"] * n_irregular + ["constante"] * (n - n_risk - n_irregular)
    random.Random(seed).shuffle(names)
    profiles = {u.id: name for u, name in zip(students, names)}
    for u in students:
        if u.email in FIXED_PROFILES:
            profiles[u.id] = FIXED_PROFILES[u.email]
    return profiles


def seed_structure(db: Session, today: datetime) -> None:
    """Cursos, ofertas, matrículas y evaluaciones. Idempotente por código de curso."""
    orgs = {o.code: o for o in db.scalars(select(Organization))}
    for org_code, courses in COURSES.items():
        org = orgs[org_code]
        for code, title, level, status, units in courses:
            if db.scalar(select(Course).where(Course.organization_id == org.id, Course.code == code)):
                continue
            course = Course(organization_id=org.id, code=code, title=title, level=level, status=status,
                            description=f"Curso DEMO de nivel {level}.")
            for i, (unit_title, activities) in enumerate(units, start=1):
                unit = CourseUnit(position=i, title=unit_title)
                unit.activities = [CourseActivity(position=j, title=t, kind=k, estimated_minutes=m)
                                   for j, (t, k, m) in enumerate(activities, start=1)]
                course.units.append(unit)
            db.add(course)
    db.flush()

    for org_code, code, instructor_email, cohort, size, days_ago, duration, assessments in OFFERINGS:
        start = today - timedelta(days=days_ago)
        org = orgs[org_code]
        course = db.scalar(select(Course).where(Course.organization_id == org.id, Course.code == code))
        if db.scalar(select(CourseOffering).where(CourseOffering.course_id == course.id)):
            continue
        instructor = db.scalar(select(User).where(User.organization_id == org.id, User.email == instructor_email))
        offering = CourseOffering(organization_id=org.id, course_id=course.id, instructor_id=instructor.id,
                                  period="2026-II", cohort=cohort, starts_on=start,
                                  ends_on=start + timedelta(days=duration))
        db.add(offering)
        db.flush()
        students = list(db.scalars(
            select(User).where(User.organization_id == org.id, User.roles.any(Role.code == "estudiante"))
            .order_by(User.email)
        ))
        for s in students[:size] if size else students:
            db.add(Enrollment(organization_id=org.id, offering_id=offering.id, student_id=s.id,
                              enrolled_at=start - timedelta(days=3)))
        for title, kind, weight, day in assessments:
            db.add(Assessment(organization_id=org.id, offering_id=offering.id, title=title, kind=kind,
                              weight=weight, max_score=20, due_at=start + timedelta(days=day, hours=23),
                              instructions="Evaluación DEMO.", max_attempts=2 if kind == "opcion_multiple" else 1))
    db.commit()


def seed_history(db: Session, now: datetime, seed: int = 2026) -> int:
    """Genera la historia DEMO solo si la institución aún no tiene eventos. Devuelve eventos creados."""
    if db.scalar(select(LearningEvent.event_id).limit(1)):
        return 0
    rng = random.Random(seed)
    created = 0

    enrollments = list(db.scalars(select(Enrollment).order_by(Enrollment.offering_id, Enrollment.student_id)))
    profiles = _assign_profiles(list({e.student_id: e.student for e in enrollments}.values()), seed)
    for enrollment in enrollments:
        offering = enrollment.offering
        profile_name = profiles[enrollment.student_id]
        p = PROFILES[profile_name]
        activities = [a for u in offering.course.units for a in u.activities]
        start = offering.starts_on
        duration = (offering.ends_on - start).days
        days = min(duration, (now - start).days)
        # Las actividades se liberan a lo largo del curso (calendario), no todas el primer día.
        release_day = [int(k * duration * 0.85 / len(activities)) for k in range(len(activities))]
        next_activity = 0

        for day in range(days):
            if p["stop"] and day >= p["stop"] * duration + rng.randint(-3, 3):
                break  # el estudiante en riesgo deja de conectarse
            if rng.random() > p["study"]:
                continue
            t = start + timedelta(days=day, hours=rng.randint(8, 21), minutes=rng.randint(0, 59))
            session_minutes = rng.randint(15, 70)
            _event(db, enrollment, "session_started", None, t, session_minutes * 60)
            created += 1
            for _ in range(rng.choice([1, 1, 2])):
                if next_activity >= len(activities) or release_day[next_activity] > day:
                    break
                activity = activities[next_activity]
                t += timedelta(minutes=rng.randint(2, 10))
                _event(db, enrollment, "lesson_viewed", activity.id, t, activity.estimated_minutes * 60)
                created += 1
                if rng.random() < p["complete"]:
                    t += timedelta(minutes=activity.estimated_minutes)
                    _event(db, enrollment, "activity_completed", activity.id, t, 0)
                    created += 1
                    next_activity += 1

        # Entregas y notas oficiales de las evaluaciones ya vencidas.
        for assessment in db.scalars(select(Assessment).where(Assessment.offering_id == offering.id)):
            if assessment.due_at > now:
                continue
            stopped = p["stop"] and (assessment.due_at - start).days > p["stop"] * duration
            if stopped or rng.random() > (0.95 if profile_name == "constante" else 0.75):
                continue
            late = rng.random() < p["late"]
            submitted = assessment.due_at + (timedelta(hours=rng.randint(2, 60)) if late else -timedelta(hours=rng.randint(1, 72)))
            score = max(0.0, min(20.0, round(rng.gauss(p["score"], 2.2))))
            db.add(AssessmentAttempt(
                assessment_id=assessment.id, student_id=enrollment.student_id, attempt_no=1,
                answer="Entrega DEMO.", submitted_at=submitted, late=late, score=score,
                feedback="Calificación DEMO.", graded_by=offering.instructor_id,
                graded_at=submitted + timedelta(days=2),
            ))
            _event(db, enrollment, "assessment_submitted", None, submitted, 0,
                   {"demo": True, "assessment_id": str(assessment.id), "late": late})
            created += 1
        db.flush()
        recompute_progress(db, enrollment, audit=False)  # una vez por matrícula, con todos sus eventos
        if enrollment.completed_at is not None:
            enrollment.completed_at = enrollment.last_activity_at
    db.commit()
    return created


def _event(db: Session, enrollment: Enrollment, event_type: str, activity_id, occurred: datetime, duration: int,
           payload: dict | None = None) -> None:
    """Inserción directa (carga masiva DEMO). La API usa ingest_event, que valida y deduplica."""
    db.add(LearningEvent(
        event_id=uuid.uuid4(), organization_id=enrollment.organization_id, student_id=enrollment.student_id,
        offering_id=enrollment.offering_id, activity_id=activity_id, event_type=event_type, occurred_at=occurred,
        duration_seconds=min(duration, 14400), source="import", payload=payload or {"demo": True},
    ))
    if enrollment.last_activity_at is None or occurred > enrollment.last_activity_at:
        enrollment.last_activity_at = occurred


def run(db: Session, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    seed_structure(db, now.replace(hour=0, minute=0, second=0, microsecond=0))
    return seed_history(db, now)
