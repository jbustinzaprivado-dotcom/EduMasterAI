"""Motor de recomendaciones v1 (§4.5, §4.11, decisiones D27 y D55).

Flujo de §4.11: candidatos → reglas de negocio → recomendación explicada → feedback.
- Los candidatos salen de señales observadas: siguiente actividad pendiente, entregas próximas, notas bajas
  e inactividad. La salida del modelo de riesgo solo ajusta la PRIORIDAD de "retomar"; nunca se le muestra
  al estudiante su puntaje (D22).
- La cabeza D de §9.1 (ranking aprendido) se entrenará cuando haya feedback suficiente: este motor lo recoge.
- D55 suma reglas con datos que el sistema ya tiene: evaluaciones vencidas, intentos para mejorar la nota,
  competencias con nivel bajo, cercanía al certificado, la siguiente etapa de una ruta y anuncios sin leer.
  Cada sugerencia dice por qué va en ese lugar (priority_reason) y, al cerrarse, por qué (resolution_note).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.academic.models import Assessment, AssessmentAttempt, Enrollment
from app.modules.academic.service import best_scores, completed_activity_ids, weighted_grade
from app.modules.certificates.service import MIN_GRADE, MIN_GRADED_WEIGHT
from app.modules.ml.models import Prediction
from app.modules.notifications.models import Notification
from app.modules.paths import service as paths
from app.modules.paths.models import PathAssignment
from app.modules.recommendations.models import Recommendation
from app.modules.skills import service as skills
from app.modules.skills.models import LEVELS, CourseSkill, Skill

ENGINE = "reglas-v1"
GOOD_RATIO = 0.7  # 14/20: por debajo, si quedan intentos, conviene intentarlo de nuevo
OVERDUE_DAYS = 14  # una evaluación vencida se sugiere hasta 14 días después
OPEN = ("nueva", "aceptada")


@dataclass
class Candidate:
    kind: str
    target_type: str
    target_id: object
    title: str
    reason: str
    expected_impact: str
    priority: float
    why: str = ""  # por qué va en este lugar de la lista


def _aware(dt: datetime | None) -> datetime | None:
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=UTC)


def _fmt_date(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%d/%m")


def candidates(db: Session, enrollment: Enrollment, now: datetime) -> tuple[list[Candidate], bool]:
    """Devuelve (candidatos, se usó la señal del modelo de riesgo)."""
    offering = enrollment.offering
    course = offering.course
    units = list(course.units)
    activities = [(u, a) for u in units for a in u.activities]
    required = [(u, a) for u, a in activities if a.required]
    done = completed_activity_ids(db, enrollment.student_id, offering.id)
    pending = [(u, a) for u, a in required if a.id not in done]
    span = max((offering.ends_on - offering.starts_on).total_seconds(), 1)
    expected = min(1.0, max(0.0, (now - offering.starts_on).total_seconds() / (span * 0.85)))
    gap = max(0.0, expected - enrollment.progress)
    last = _aware(enrollment.last_activity_at)
    idle_days = int((now - last).total_seconds() // 86400) if last else (now - offering.starts_on).days

    latest = db.scalar(select(Prediction).where(Prediction.enrollment_id == enrollment.id)
                       .order_by(Prediction.created_at.desc()).limit(1))
    high_risk = bool(latest and latest.risk_level == "alto")
    out: list[Candidate] = []

    # Retomar: inactividad. Se sugiere la actividad pendiente más corta para volver con poco esfuerzo.
    retake_target = None
    if idle_days >= 7 and pending:
        unit, act = min(pending, key=lambda ua: (ua[1].estimated_minutes, ua[0].position, ua[1].position))
        retake_target = act.id
        out.append(Candidate(
            "retomar", "activity", act.id, f"Retoma con «{act.title}»",
            f"Llevas {idle_days} días sin actividad en este curso. «{act.title}» (Unidad {unit.position}) toma unos "
            f"{act.estimated_minutes} minutos: es un buen punto para volver.",
            "Volver a la rutina con una tarea corta", 0.9 + (0.08 if high_risk else 0.0),
            f"{idle_days} días sin actividad",
        ))

    # Siguiente actividad obligatoria en el orden del curso.
    if pending and pending[0][1].id != retake_target:
        unit, act = pending[0]
        pace = (f"Llevas {round(enrollment.progress * 100)} % del curso y el calendario va por {round(expected * 100)} %."
                if gap > 0.05 else "Vas al ritmo del calendario.")
        out.append(Candidate(
            "siguiente_actividad", "activity", act.id, f"Continúa con «{act.title}»",
            f"Es la siguiente actividad obligatoria de la Unidad {unit.position} ({unit.title}). {pace}",
            f"+{round(100 / len(required))} % de avance del curso", 0.5 + min(gap, 0.4),
            f"atraso de {round(gap * 100)} puntos frente al calendario" if gap > 0.05 else "sigue el orden del curso",
        ))

    assessments = list(db.scalars(select(Assessment).where(Assessment.offering_id == offering.id)
                                  .order_by(Assessment.due_at)))
    attempts = {}
    for t in db.scalars(select(AssessmentAttempt).where(
            AssessmentAttempt.student_id == enrollment.student_id,
            AssessmentAttempt.assessment_id.in_([a.id for a in assessments]))):
        attempts.setdefault(t.assessment_id, []).append(t)

    for a in assessments:
        mine = attempts.get(a.id, [])
        due = _aware(a.due_at)
        # Entrega próxima: vence en los próximos 7 días y aún no se entregó.
        if not mine and now < due <= now + timedelta(days=7):
            days = max(0, (due - now).days)
            out.append(Candidate(
                "entrega_proxima", "assessment", a.id, f"Entrega «{a.title}»",
                f"Vence el {_fmt_date(due)} ({'hoy' if days == 0 else f'en {days} días'}) y aún no la entregas. "
                f"Pesa {round(a.weight * 100)} % de la nota del curso.",
                f"Hasta {round(a.weight * 100)} % de la nota final", 1.0 - days / 20,
                "vence hoy" if days == 0 else f"vence en {days} días",
            ))
        # Vencida sin entregar (D55): aún se puede entregar, queda marcada como tardía.
        if not mine and now - timedelta(days=OVERDUE_DAYS) < due <= now:
            out.append(Candidate(
                "vencida", "assessment", a.id, f"Entrega «{a.title}» aunque ya venció",
                f"Venció el {_fmt_date(due)} y no la entregaste. Todavía puedes entregarla: quedará marcada como tardía "
                f"y tu docente decide la nota. Pesa {round(a.weight * 100)} % de la nota del curso.",
                f"Hasta {round(a.weight * 100)} % de la nota final", 0.97,
                f"venció hace {max(1, (now - due).days)} días",
            ))
        # Mejorar la nota (D55): quedan intentos y la mejor nota está por debajo de 14/20. Cuenta el mejor intento (D18).
        graded = [t.score for t in mine if t.score is not None]
        left = a.max_attempts - len(mine)
        if graded and left > 0 and max(graded) / a.max_score < GOOD_RATIO:
            out.append(Candidate(
                "mejorar_nota", "assessment", a.id, f"Mejora tu nota en «{a.title}»",
                f"Sacaste {max(graded):g}/{a.max_score:g} y te {'queda 1 intento' if left == 1 else f'quedan {left} intentos'}. "
                f"Cuenta tu mejor nota, así que intentarlo no te puede bajar el promedio.",
                f"Hasta {round(a.weight * 100)} % de la nota final", 0.8,
                f"{left} intento{'s' if left > 1 else ''} disponible{'s' if left > 1 else ''}",
            ))
        # Reforzar: la mejor nota oficial quedó por debajo del 55 %.
        if graded and units:
            ratio = max(graded) / a.max_score
            if ratio < 0.55:
                fraction = (due - offering.starts_on).total_seconds() / span
                unit = units[min(len(units) - 1, int(fraction * len(units)))]
                practice = next((x for x in unit.activities if x.kind == "practica"), unit.activities[0] if unit.activities else None)
                if practice is not None:
                    out.append(Candidate(
                        "reforzar", "activity", practice.id, f"Repasa «{practice.title}»",
                        f"Tu nota en «{a.title}» fue {max(graded):g}/{a.max_score:g}. Repasar «{practice.title}» "
                        f"(Unidad {unit.position}) refuerza esos temas antes de lo que viene.",
                        "Mejor base para las próximas evaluaciones", 0.6 + (0.55 - ratio),
                        f"nota de {round(ratio * 100)} % en «{a.title}»",
                    ))

    out += _skill_candidates(db, enrollment, units)
    out += _certificate_candidate(db, enrollment, pending, assessments)
    out += _path_candidates(db, enrollment)
    out += _announcement_candidates(db, enrollment)
    return out, latest is not None


def _skill_candidates(db: Session, enrollment: Enrollment, units) -> list[Candidate]:
    """Competencia con nivel estimado bajo (D34) con evidencia de notas: se sugiere practicar su unidad."""
    offering = enrollment.offering
    links = list(db.scalars(select(CourseSkill).where(CourseSkill.course_id == offering.course_id)))
    if not links:
        return []
    states = skills.student_states(db, enrollment.student_id, [offering.id])
    out = []
    for cs in links:
        s = states.get(cs.skill_id)
        graded = s and any(ev.source == "evaluacion" for ev in s.evidences)
        if not graded or s.estimated_level is None or s.estimated_level > 2 or (s.validated_level or 0) > 2:
            continue
        skill = db.get(Skill, cs.skill_id)
        unit = units[cs.position - 1] if 0 < cs.position <= len(units) else None
        practice = next((a for a in unit.activities if a.kind == "practica"), None) if unit else None
        where = f" Practica «{practice.title}» (Unidad {unit.position})." if practice else (
            f" Repasa la Unidad {unit.position}." if unit else "")
        out.append(Candidate(
            "competencia", "skill", cs.skill_id, f"Fortalece «{skill.name}»",
            f"Tu nivel estimado en «{skill.name}» es {LEVELS[s.estimated_level - 1]}, según tus notas y tu avance.{where} "
            f"Es una estimación orientativa: el nivel oficial lo valida tu docente.",
            "Subir de nivel en esa competencia", 0.55 + 0.05 * (3 - s.estimated_level),
            f"nivel estimado {LEVELS[s.estimated_level - 1]}",
        ))
    return out


def _certificate_candidate(db: Session, enrollment: Enrollment, pending, assessments) -> list[Candidate]:
    """Cerca del certificado (D29): avance de 70 % o más y algo concreto que falta."""
    if enrollment.progress < 0.7:
        return []
    grade, weight = weighted_grade(assessments, best_scores(db, enrollment.offering_id, enrollment.student_id),
                                   enrollment.student_id)
    missing = []
    if pending:
        missing.append(f"{len(pending)} actividad{'es' if len(pending) > 1 else ''} obligatoria{'s' if len(pending) > 1 else ''}")
    if assessments and weight < MIN_GRADED_WEIGHT:
        missing.append(f"que se califique al menos {round(MIN_GRADED_WEIGHT * 100)} % del peso (hoy {round(weight * 100)} %)")
    if grade is not None and grade < MIN_GRADE:
        missing.append(f"subir tu nota a {MIN_GRADE:g} (hoy {grade:.1f})")
    if not missing:
        return []
    return [Candidate(
        "certificado", "offering", enrollment.offering_id, "Estás cerca de tu certificado",
        f"Llevas {round(enrollment.progress * 100)} % del curso. Para certificarte te falta: {'; '.join(missing)}.",
        "Certificado oficial verificable", 0.7 + 0.2 * enrollment.progress,
        f"{round(enrollment.progress * 100)} % del curso completado",
    )]


def _path_candidates(db: Session, enrollment: Enrollment) -> list[Candidate]:
    """Este curso es la etapa que sigue en una ruta asignada (D32) y aún no se empieza."""
    if enrollment.progress > 0:
        return []
    out = []
    course_id = enrollment.offering.course_id
    for assignment in db.scalars(select(PathAssignment).where(PathAssignment.student_id == enrollment.student_id,
                                                              PathAssignment.status == "active")):
        prog = paths.progress(db, assignment)
        step = next((s for s in prog.steps if s.course_id == course_id), None)
        if step is None or step.status != "en_curso" or step.position == 1:
            continue
        out.append(Candidate(
            "ruta", "path", assignment.id, f"Empieza «{step.course_title}», tu siguiente etapa",
            f"Completaste la etapa anterior de la ruta «{assignment.path.title}». «{step.course_title}» es la etapa "
            f"{step.position} de {prog.total_steps} y ya está desbloqueada.",
            "Avanzar en tu ruta de aprendizaje", 0.75, f"etapa {step.position} de {prog.total_steps} desbloqueada",
        ))
    return out


def _announcement_candidates(db: Session, enrollment: Enrollment) -> list[Candidate]:
    """Anuncios del docente en este curso que el estudiante no ha leído (aviso sin leer)."""
    out = []
    marker = f"oferta={enrollment.offering_id}&post="
    for n in db.scalars(select(Notification).where(
            Notification.user_id == enrollment.student_id, Notification.kind == "community.announcement",
            Notification.read_at.is_(None), Notification.link.contains(marker))):
        try:
            post_id = uuid.UUID(n.link.split("post=")[1][:36])
        except (ValueError, IndexError):
            continue
        out.append(Candidate(
            "anuncio", "post", post_id, n.title.split(": ", 1)[-1] if ": " in n.title else n.title,
            f"Tu docente publicó un anuncio en el curso y aún no lo lees: «{n.body[:120]}».",
            "Enterarte de cambios y avisos del curso", 0.85, "anuncio sin leer",
        ))
    return out


def _is_done(db: Session, enrollment: Enrollment, r: Recommendation, done: set, submitted: set) -> bool:
    """¿El estudiante cumplió lo sugerido? Distingue 'completada' de 'expirada' al cerrar una sugerencia."""
    if r.kind == "retomar":
        return enrollment.last_activity_at is not None and _aware(enrollment.last_activity_at) > _aware(r.created_at)
    if r.kind == "certificado":
        return enrollment.status == "completed"
    if r.kind == "ruta":
        return enrollment.progress > 0
    if r.kind == "anuncio":
        return True  # deja de aplicar al leerlo
    if r.kind == "competencia":
        s = skills.student_states(db, enrollment.student_id, [enrollment.offering_id]).get(r.target_id)
        return bool(s and ((s.estimated_level or 0) > 2 or (s.validated_level or 0) > 2))
    if r.target_type == "activity":
        return r.target_id in done
    return r.target_id in submitted


RESOLUTION = {
    "completada": {
        "retomar": "Volviste a conectarte.", "certificado": "Completaste el curso.", "ruta": "Empezaste la etapa.",
        "anuncio": "Leíste el anuncio.", "competencia": "Tu nivel subió.", "mejorar_nota": "Usaste otro intento.",
        "entrega_proxima": "La entregaste.", "vencida": "La entregaste.",
    },
    "expirada": {
        "entrega_proxima": "La fecha de entrega pasó.", "certificado": "El curso terminó.",
        "siguiente_actividad": "Otra actividad pasó a ser la siguiente.",
        "vencida": "Pasaron más de 14 días desde el vencimiento.",
    },
}


def refresh(db: Session, enrollment: Enrollment, now: datetime | None = None) -> None:
    """Sincroniza las recomendaciones de una matrícula con su situación actual.
    Lo que dejó de aplicar se cierra: 'completada' si el estudiante lo hizo, 'expirada' si no."""
    now = now or datetime.now(UTC)
    existing = {(r.kind, r.target_id): r for r in db.scalars(
        select(Recommendation).where(Recommendation.enrollment_id == enrollment.id))}
    if enrollment.status != "active":
        current, used_model = [], False
    else:
        current, used_model = candidates(db, enrollment, now)
    source = ENGINE + ("+riesgo" if used_model else "")
    seen = set()
    for c in current:
        key = (c.kind, c.target_id)
        seen.add(key)
        r = existing.get(key)
        if r is None:
            db.add(Recommendation(
                organization_id=enrollment.organization_id, enrollment_id=enrollment.id,
                student_id=enrollment.student_id, offering_id=enrollment.offering_id, kind=c.kind,
                target_type=c.target_type, target_id=c.target_id, title=c.title, reason=c.reason,
                expected_impact=c.expected_impact, priority=round(c.priority, 4), priority_reason=c.why,
                source=source, created_at=now,
            ))
        elif r.status in OPEN or r.status == "expirada":
            if r.status == "expirada":
                r.status, r.resolved_at, r.resolution_note = "nueva", None, None  # la situación volvió a darse
            r.title, r.reason, r.expected_impact = c.title, c.reason, c.expected_impact
            r.priority, r.priority_reason, r.source = round(c.priority, 4), c.why, source
        # 'descartada' y 'completada' se respetan: no se vuelven a insistir.

    done = completed_activity_ids(db, enrollment.student_id, enrollment.offering_id)
    submitted = set(db.scalars(select(AssessmentAttempt.assessment_id).where(
        AssessmentAttempt.student_id == enrollment.student_id)))
    for key, r in existing.items():
        if key in seen or r.status not in OPEN:
            continue
        r.status = "completada" if _is_done(db, enrollment, r, done, submitted) else "expirada"
        r.resolved_at = now
        r.resolution_note = RESOLUTION[r.status].get(r.kind) or (
            "Lo hiciste." if r.status == "completada" else "Dejó de aplicar: tu situación en el curso cambió.")
    db.flush()

