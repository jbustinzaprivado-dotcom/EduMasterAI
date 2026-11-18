"""Generador del dataset sintético DEMO para riesgo de abandono (§8, decisión D06).

No representa personas reales ni permite afirmar validez educativa (§8.1). Sirve para probar el pipeline,
el entrenamiento y la interfaz. Cada fila es una matrícula observada en un instante de corte `t`:
- Variables: solo hechos anteriores a `t` (features.compute), sin fuga de información (§8.5).
- Etiqueta `target_dropout_risk` (definición operacional documentada): en los 14 días siguientes a `t`
  el estudiante no registra ningún evento y no ha completado el curso.

Comportamiento latente por estudiante: compromiso continuo, posible desconexión progresiva a partir de un
día de inicio, y pausas temporales que NO terminan en abandono (para que el problema no sea trivial).
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import numpy as np

from edumaster_ml import REPO  # noqa: F401  (agrega la API al path)
from app.modules.ml.features import (  # noqa: E402
    FEATURE_SCHEMA_VERSION,
    SEQ_FEATURES,
    SEQ_WEEKS,
    TABULAR_FEATURES,
    AssessmentRec,
    EnrollmentContext,
    EventRec,
    compute,
)

DATASET_NAME = "riesgo-abandono-demo"
LABEL_HORIZON_DAYS = 14
FIRST_START = datetime(2024, 3, 4, tzinfo=UTC)
LAST_START = datetime(2026, 6, 1, tzinfo=UTC)
# Separación temporal (§8.5): entrenamiento con cohortes antiguas, validación y prueba con posteriores.
VAL_FROM = datetime(2025, 7, 1, tzinfo=UTC)
TEST_FROM = datetime(2026, 1, 1, tzinfo=UTC)


@dataclass
class Sample:
    split: str
    level: str
    tabular: list[float]
    sequence: list[list[float]]
    label: int


def _simulate(rng: random.Random, start: datetime) -> tuple[EnrollmentContext, list[EventRec], list[AssessmentRec], int]:
    duration = rng.randint(56, 84)
    level = rng.choice(["basico", "basico", "intermedio", "avanzado"])
    n_act = rng.randint(8, 14)
    activities = [uuid.UUID(int=rng.getrandbits(128)) for _ in range(n_act)]
    ctx = EnrollmentContext(starts_on=start, ends_on=start + timedelta(days=duration), level=level,
                            required_ids=set(activities))
    release = [int(k * duration * 0.85 / n_act) for k in range(n_act)]

    engagement = rng.betavariate(2.2, 1.8)
    level_penalty = {"basico": 0.0, "intermedio": 0.04, "avanzado": 0.08}[level]
    declines = rng.random() < 0.18 + 0.35 * (1 - engagement) + level_penalty
    onset = rng.uniform(0.1, 0.8) * duration if declines else math.inf
    decay = rng.uniform(0.08, 0.35)
    pause_start = rng.uniform(0.2, 0.7) * duration if rng.random() < 0.22 else math.inf
    pause_len = rng.randint(5, 10)

    events: list[EventRec] = []
    nxt = 0
    for day in range(duration):
        p = 0.12 + 0.55 * engagement
        if day > onset:
            p *= math.exp(-decay * (day - onset))
        if pause_start <= day < pause_start + pause_len:
            p *= 0.05
        if rng.random() > p:
            continue
        t = start + timedelta(days=day, hours=rng.randint(7, 22), minutes=rng.randint(0, 59))
        events.append(EventRec(t, "session_started", rng.randint(10, 75) * 60))
        for _ in range(rng.choice([1, 1, 2])):
            if nxt >= n_act or release[nxt] > day:
                break
            t += timedelta(minutes=rng.randint(2, 8))
            events.append(EventRec(t, "lesson_viewed", rng.randint(10, 40) * 60, activities[nxt]))
            if rng.random() < 0.45 + 0.45 * engagement:
                t += timedelta(minutes=rng.randint(10, 40))
                events.append(EventRec(t, "activity_completed", 0, activities[nxt]))
                nxt += 1

    assessments = []
    for frac in sorted(rng.uniform(0.15, 0.95) for _ in range(3)):
        due = start + timedelta(days=frac * duration, hours=23)
        day = (due - start).days
        current = engagement * (math.exp(-decay * (day - onset)) if day > onset else 1.0)
        if pause_start <= day < pause_start + pause_len:
            current *= 0.5
        if rng.random() < 0.25 + 0.75 * current:
            late = rng.random() < 0.6 * (1 - current)
            submitted = due + (timedelta(hours=rng.randint(2, 72)) if late else -timedelta(hours=rng.randint(1, 96)))
            score = min(1.0, max(0.0, rng.gauss(0.35 + 0.55 * engagement, 0.12)))
            assessments.append(AssessmentRec(due, submitted, late, submitted + timedelta(days=2), score))
        else:
            assessments.append(AssessmentRec(due))
    return ctx, events, assessments, duration


def _label(ctx: EnrollmentContext, events: list[EventRec], t: datetime) -> int:
    horizon = t + timedelta(days=LABEL_HORIZON_DAYS)
    completed = {e.activity_id for e in events if e.event_type == "activity_completed" and e.occurred_at < horizon}
    if ctx.required_ids <= completed:
        return 0  # completó el curso: no es abandono
    return int(not any(t <= e.occurred_at < horizon for e in events))


def generate(n: int = 6000, seed: int = 2026) -> list[Sample]:
    rng = random.Random(seed)
    span = (LAST_START - FIRST_START).days
    samples = []
    for _ in range(n):
        start = FIRST_START + timedelta(days=rng.randint(0, span))
        ctx, events, assessments, duration = _simulate(rng, start)
        cut_day = rng.randint(14, duration - LABEL_HORIZON_DAYS)
        t = start + timedelta(days=cut_day)
        # Quien ya abandonó antes del corte (sin eventos en las 3 semanas previas) no se evalúa: no hay nada que prevenir.
        if not any(t - timedelta(days=21) <= e.occurred_at < t for e in events):
            continue
        tabular, sequence = compute(ctx, events, assessments, t)
        split = "test" if start >= TEST_FROM else "val" if start >= VAL_FROM else "train"
        samples.append(Sample(split, ctx.level, tabular, sequence, _label(ctx, events, t)))
    return samples


def to_arrays(samples: list[Sample], split: str):
    rows = [s for s in samples if s.split == split]
    return (np.array([s.tabular for s in rows], dtype=np.float32),
            np.array([s.sequence for s in rows], dtype=np.float32),
            np.array([s.label for s in rows], dtype=np.float32),
            [s.level for s in rows])


def datasheet(samples: list[Sample], seed: int, n: int) -> dict:
    """Ficha del dataset (§9.6 paso 12): versión, definición, balance por split y huella."""
    payload = json.dumps([[s.split, s.tabular, s.sequence, s.label] for s in samples]).encode()
    by_split = {}
    for split in ("train", "val", "test"):
        rows = [s for s in samples if s.split == split]
        by_split[split] = {"rows": len(rows), "positives": sum(s.label for s in rows),
                           "positive_rate": round(sum(s.label for s in rows) / max(len(rows), 1), 4)}
    return {
        "name": DATASET_NAME, "version": f"v1-seed{seed}", "demo": True,
        "description": "Dataset SINTÉTICO generado por simulación. No contiene personas reales ni permite "
                       "afirmar validez educativa (§8.1).",
        "requested_enrollments": n, "rows": len(samples),
        "label": f"target_dropout_risk = 1 si no hay eventos en los {LABEL_HORIZON_DAYS} días siguientes al corte "
                 "y el curso no está completado.",
        "population": "Matrículas con actividad en las 3 semanas previas al corte.",
        "split": {"method": "temporal por fecha de inicio de la cohorte",
                  "train": f"< {VAL_FROM.date()}", "val": f"{VAL_FROM.date()} – {TEST_FROM.date()}",
                  "test": f">= {TEST_FROM.date()}", **by_split},
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "tabular_features": TABULAR_FEATURES, "sequence": {"weeks": SEQ_WEEKS, "features": SEQ_FEATURES},
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
