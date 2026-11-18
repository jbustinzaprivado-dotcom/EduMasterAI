"""Variables del modelo de riesgo de abandono (§8.3). Python puro: lo usan igual el entrenamiento (ml/)
y la inferencia en la API, así no hay diferencias entre cómo se entrena y cómo se predice.

Regla anti-fuga (§8.5): solo se usan hechos ocurridos ANTES del instante de predicción `t`.
Todas las variables quedan aproximadamente en [0, 1] para que el modelo no dependa de un escalador.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

FEATURE_SCHEMA_VERSION = 1

TABULAR_FEATURES = [
    "active_days_14d",  # días con actividad en los últimos 14 / 14
    "sessions_14d",  # sesiones en 14 días / 14 (tope 1)
    "completion_ratio",  # actividades requeridas completadas / total
    "pace_gap",  # avance esperado por calendario − avance real (0 si va al día)
    "assessment_mean",  # promedio de notas oficiales conocidas (0-1); 0.5 si aún no hay
    "assessment_trend",  # última nota − primera nota, llevada a [0, 1] (0.5 = sin cambio)
    "late_submissions_30d",  # entregas tardías / entregas de los últimos 30 días
    "missed_assessments",  # evaluaciones vencidas sin entrega / vencidas
    "content_engagement",  # lecciones vistas en 14 días / 10 (tope 1)
    "days_since_last_activity",  # días desde el último evento / 30 (tope 1)
    "level_basico",
    "level_intermedio",
    "level_avanzado",
]

# Texto prudente para explicar cada variable (§9.8: sin afirmar causalidad).
FEATURE_LABELS = {
    "active_days_14d": "pocos días con actividad en las últimas 2 semanas",
    "sessions_14d": "pocas sesiones recientes",
    "completion_ratio": "bajo avance en actividades obligatorias",
    "pace_gap": "atraso frente al calendario del curso",
    "assessment_mean": "notas oficiales bajas",
    "assessment_trend": "notas en descenso",
    "late_submissions_30d": "entregas fuera de plazo",
    "missed_assessments": "evaluaciones vencidas sin entregar",
    "content_engagement": "poca consulta de contenidos",
    "days_since_last_activity": "varios días sin conectarse",
    "level_basico": "nivel del curso",
    "level_intermedio": "nivel del curso",
    "level_avanzado": "nivel del curso",
}

SEQ_WEEKS = 6
SEQ_FEATURES = ["active_days", "sessions", "completions", "hours"]


@dataclass
class EventRec:
    occurred_at: datetime
    event_type: str
    duration_seconds: int = 0
    activity_id: object = None


@dataclass
class AssessmentRec:
    due_at: datetime
    submitted_at: datetime | None = None
    late: bool = False
    graded_at: datetime | None = None
    score_ratio: float | None = None  # nota / nota máxima


@dataclass
class EnrollmentContext:
    starts_on: datetime
    ends_on: datetime
    level: str
    required_ids: set = field(default_factory=set)


def _clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def compute(ctx: EnrollmentContext, events: list[EventRec], assessments: list[AssessmentRec], t: datetime
            ) -> tuple[list[float], list[list[float]]]:
    """Devuelve (vector tabular, secuencia semanal [SEQ_WEEKS x 4]) en el instante t."""
    past = [e for e in events if e.occurred_at < t]
    d14, d30 = t - timedelta(days=14), t - timedelta(days=30)
    recent = [e for e in past if e.occurred_at >= d14]

    active_days = len({e.occurred_at.date() for e in recent})
    sessions = sum(1 for e in recent if e.event_type == "session_started")
    lessons = sum(1 for e in recent if e.event_type == "lesson_viewed")
    completed = {e.activity_id for e in past if e.event_type == "activity_completed"} & ctx.required_ids
    completion = len(completed) / len(ctx.required_ids) if ctx.required_ids else 0.0
    span = max((ctx.ends_on - ctx.starts_on).total_seconds(), 1)
    expected = _clip((t - ctx.starts_on).total_seconds() / (span * 0.85))
    last = max((e.occurred_at for e in past), default=None)
    idle_days = (t - last).total_seconds() / 86400 if last else (t - ctx.starts_on).total_seconds() / 86400

    graded = sorted((a for a in assessments if a.graded_at is not None and a.graded_at < t and a.score_ratio is not None),
                    key=lambda a: a.due_at)
    mean = sum(a.score_ratio for a in graded) / len(graded) if graded else 0.5
    trend = 0.5 + (graded[-1].score_ratio - graded[0].score_ratio) / 2 if len(graded) >= 2 else 0.5
    recent_subs = [a for a in assessments if a.submitted_at is not None and d30 <= a.submitted_at < t]
    late = sum(a.late for a in recent_subs) / len(recent_subs) if recent_subs else 0.0
    due = [a for a in assessments if a.due_at < t]
    missed = sum(1 for a in due if a.submitted_at is None or a.submitted_at >= t) / len(due) if due else 0.0

    tabular = [
        active_days / 14,
        _clip(sessions / 14),
        completion,
        _clip(expected - completion),
        mean,
        _clip(trend),
        late,
        missed,
        _clip(lessons / 10),
        _clip(idle_days / 30),
        1.0 if ctx.level == "basico" else 0.0,
        1.0 if ctx.level == "intermedio" else 0.0,
        1.0 if ctx.level == "avanzado" else 0.0,
    ]

    sequence = []
    for w in range(SEQ_WEEKS, 0, -1):  # de la semana más antigua a la más reciente
        since, until = t - timedelta(weeks=w), t - timedelta(weeks=w - 1)
        week = [e for e in past if since <= e.occurred_at < until]
        sequence.append([
            len({e.occurred_at.date() for e in week}) / 7,
            _clip(sum(1 for e in week if e.event_type == "session_started") / 7),
            _clip(sum(1 for e in week if e.event_type == "activity_completed") / 3),
            _clip(sum(e.duration_seconds for e in week) / 3600 / 5),
        ])
    return tabular, sequence
