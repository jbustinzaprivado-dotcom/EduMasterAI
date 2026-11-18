"""Pruebas de ML (§13): fuga de información, equivalencia de la inferencia y definición de la etiqueta."""

import random
import uuid
from datetime import UTC, datetime, timedelta

import numpy as np
import torch

from edumaster_ml.generate import _label, _simulate
from edumaster_ml.train import MultiTaskRiskNet, export_network
from app.modules.ml.features import SEQ_WEEKS, TABULAR_FEATURES, AssessmentRec, EnrollmentContext, EventRec, compute
from app.modules.ml.inference import RiskModel

T0 = datetime(2026, 3, 1, tzinfo=UTC)


def _ctx():
    acts = {uuid.uuid4() for _ in range(4)}
    return EnrollmentContext(T0, T0 + timedelta(days=60), "intermedio", acts), sorted(acts, key=str)


def test_variables_ignoran_hechos_futuros():
    ctx, acts = _ctx()
    t = T0 + timedelta(days=20)
    past = [EventRec(T0 + timedelta(days=d), "session_started", 1800) for d in (2, 9, 15, 19)]
    past.append(EventRec(T0 + timedelta(days=10), "activity_completed", 0, acts[0]))
    future = [EventRec(T0 + timedelta(days=d), "activity_completed", 0, acts[1]) for d in (21, 30)]
    grades = [AssessmentRec(T0 + timedelta(days=25), T0 + timedelta(days=24), False, T0 + timedelta(days=26), 0.9)]
    a = compute(ctx, past, [], t)
    b = compute(ctx, past + future, grades, t)  # eventos y notas posteriores a t
    assert a == b
    tab, seq = a
    assert len(tab) == len(TABULAR_FEATURES) and len(seq) == SEQ_WEEKS
    assert tab[TABULAR_FEATURES.index("completion_ratio")] == 0.25
    assert tab[TABULAR_FEATURES.index("level_intermedio")] == 1.0


def test_etiqueta_de_abandono():
    ctx, acts = _ctx()
    t = T0 + timedelta(days=20)
    active = [EventRec(t + timedelta(days=3), "session_started")]
    assert _label(ctx, active, t) == 0  # vuelve dentro del horizonte
    assert _label(ctx, [], t) == 1  # 14 días sin eventos
    done = [EventRec(t - timedelta(days=1), "activity_completed", 0, a) for a in acts]
    assert _label(ctx, done, t) == 0  # completó el curso: no es abandono


def test_simulacion_reproducible():
    a = _simulate(random.Random(7), T0)
    b = _simulate(random.Random(7), T0)
    assert [e.occurred_at for e in a[1]] == [e.occurred_at for e in b[1]]


def test_inferencia_numpy_igual_a_pytorch():
    torch.manual_seed(0)
    net = MultiTaskRiskNet(len(TABULAR_FEATURES), 4).eval()
    spec = {"kind": "multitask_gru", "threshold": 0.5, "reference_tabular": [0.5] * len(TABULAR_FEATURES),
            "reference_sequence": [[0.2] * 4] * SEQ_WEEKS, "weights": export_network(net)}
    tab = np.random.rand(16, len(TABULAR_FEATURES)).astype(np.float32)
    seq = np.random.rand(16, SEQ_WEEKS, 4).astype(np.float32)
    expected = torch.sigmoid(net(torch.tensor(tab), torch.tensor(seq))).detach().numpy()
    assert np.abs(RiskModel(spec).predict(tab, seq) - expected).max() < 1e-5


def test_explicacion_nombra_factores_prudentes():
    torch.manual_seed(1)
    spec = {"kind": "logistic", "threshold": 0.5, "reference_tabular": [0.0] * len(TABULAR_FEATURES),
            "reference_sequence": [[0.0] * 4] * SEQ_WEEKS,
            "weights": {"coef": [0.0] * 9 + [4.0] + [0.0] * 3 + [0.0] * SEQ_WEEKS * 4, "intercept": -2.0}}
    tab = [0.0] * len(TABULAR_FEATURES)
    tab[TABULAR_FEATURES.index("days_since_last_activity")] = 1.0
    factors = RiskModel(spec).explain(tab, [[0.0] * 4] * SEQ_WEEKS)
    assert factors[0].feature == "days_since_last_activity" and "sin conectarse" in factors[0].label
