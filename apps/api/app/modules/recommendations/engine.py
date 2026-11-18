"""Motor de recomendaciones v1 (§4.5, §4.11, decisión D27).

Flujo de §4.11: candidatos → reglas de negocio → recomendación explicada → feedback.
- Los candidatos salen de señales observadas: siguiente actividad pendiente, entregas próximas, notas bajas
  e inactividad. La salida del modelo de riesgo solo ajusta la PRIORIDAD de "retomar"; nunca se le muestra
  al estudiante su puntaje (D22).
- La cabeza D de §9.1 (ranking aprendido) se entrenará cuando haya feedback suficiente: este motor lo recoge.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.academic.models import Assessment, AssessmentAttempt, Enrollment
from app.modules.academic.service import completed_activity_ids
from app.modules.ml.models import Prediction
from app.modules.recommendations.models import Recommendation

ENGINE = "reglas-v1"
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
            ))
        # Reforzar: la mejor nota oficial quedó por debajo del 55 %.
        graded = [t.score for t in mine if t.score is not None]
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
                    ))
    return out, latest is not None


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
                expected_impact=c.expected_impact, priority=round(c.priority, 4), source=source, created_at=now,
            ))
        elif r.status in OPEN or r.status == "expirada":
            if r.status == "expirada":
                r.status, r.resolved_at = "nueva", None  # la situación volvió a darse
            r.title, r.reason, r.expected_impact = c.title, c.reason, c.expected_impact
            r.priority, r.source = round(c.priority, 4), source
        # 'descartada' y 'completada' se respetan: no se vuelven a insistir.

    done = completed_activity_ids(db, enrollment.student_id, enrollment.offering_id)
    submitted = set(db.scalars(select(AssessmentAttempt.assessment_id).where(
        AssessmentAttempt.student_id == enrollment.student_id)))
    for key, r in existing.items():
        if key in seen or r.status not in OPEN:
            continue
        fulfilled = (r.target_id in done) if r.target_type == "activity" else (r.target_id in submitted)
        if r.kind == "retomar":
            fulfilled = enrollment.last_activity_at is not None and _aware(enrollment.last_activity_at) > _aware(r.created_at)
        r.status = "completada" if fulfilled else "expirada"
        r.resolved_at = now
    db.flush()

