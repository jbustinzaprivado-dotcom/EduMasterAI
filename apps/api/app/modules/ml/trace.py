"""Recorrido real de una predicción por la red (§4.10, D51).

Repite la propagación hacia delante de `RiskModel` paso a paso y guarda las activaciones de cada capa. La
interfaz no puede dibujar las 24 + 24 + 32 neuronas, así que se eligen las que MÁS APORTARON a esta predicción,
de la salida hacia atrás:

1. Fusión: las neuronas con mayor |activación × peso hacia la salida| (aporte al logit).
2. Rama tabular y bloque temporal: las que más aportan a esas neuronas de fusión (antes de la normalización).
3. Entrada: las variables que más aportan a las neuronas tabulares elegidas, más un nodo para la secuencia semanal.

El aporte antes de LayerNorm es una aproximación para elegir qué mostrar; los valores de cada neurona y la
probabilidad final son exactos (una prueba verifica que coinciden con `RiskModel.predict`).
"""

from __future__ import annotations

import numpy as np

from app.modules.ml.features import SEQ_WEEKS, TABULAR_FEATURES
from app.modules.ml.inference import RiskModel, _relu, _sigmoid

SHORT_LABELS = {
    "active_days_14d": "Días activos (14 d)",
    "sessions_14d": "Sesiones (14 d)",
    "completion_ratio": "Avance obligatorio",
    "pace_gap": "Atraso vs. calendario",
    "assessment_mean": "Promedio de notas",
    "assessment_trend": "Tendencia de notas",
    "late_submissions_30d": "Entregas tardías",
    "missed_assessments": "Evaluaciones sin entregar",
    "content_engagement": "Consulta de contenidos",
    "days_since_last_activity": "Días sin conectarse",
}
HEADS = [("A", "Finalización"), ("B", "Dominio"), ("C", "Riesgo de abandono"), ("D", "Recomendaciones")]
ACTIVE_HEAD = 2  # solo la cabeza C está entrenada (D07)
SHOWN = {"input": 7, "projection": 6, "temporal": 6, "fusion": 5}  # + 1 nodo de secuencia en la entrada = 8


class TraceUnavailable(Exception):
    """El modelo publicado no tiene capas ocultas (baseline logístico)."""


def _top(scores: np.ndarray, k: int, allowed: list[int] | None = None) -> list[int]:
    idx = allowed if allowed is not None else list(range(len(scores)))
    best = sorted(idx, key=lambda i: -abs(float(scores[i])))[:k]
    return sorted(best)


def _edges(src_layer: str, src_ids: list[int], dst_layer: str, dst_ids: list[int], contrib, per_target: int = 2):
    """Para cada nodo destino, sus `per_target` fuentes con mayor |aporte|. Fuerza normalizada a [0, 1]."""
    raw = []
    for d in dst_ids:
        ranked = sorted(src_ids, key=lambda s: -abs(contrib(s, d)))[:per_target]
        raw += [(s, d, contrib(s, d)) for s in ranked]
    peak = max((abs(c) for *_, c in raw), default=0.0) or 1.0
    return [{"source_layer": src_layer, "source": s, "target_layer": dst_layer, "target": d,
             "strength": round(abs(c) / peak, 3), "sign": 1 if c >= 0 else -1} for s, d, c in raw]


def _node(index: int, label: str, value: float | None, peak: float) -> dict:
    intensity = 0.0 if value is None else min(abs(value) / (peak or 1.0), 1.0)
    return {"index": index, "label": label, "value": None if value is None else round(float(value), 4),
            "intensity": round(intensity, 3)}


def build(model: RiskModel, tabular: list[float], sequence: list[list[float]]) -> dict:
    if model.kind != "multitask_gru":
        raise TraceUnavailable
    w = model.w
    x = np.asarray(tabular, dtype=np.float64)
    seq = np.asarray(sequence, dtype=np.float64)

    # Propagación hacia delante, igual que RiskModel.logits pero conservando cada capa.
    tab = _relu(w["tab.weight"] @ x + w["tab.bias"])
    temporal = model._gru(seq[None])[0]
    cat = np.concatenate([tab, temporal])
    pre = w["fusion.weight"] @ cat + w["fusion.bias"]
    fused = _relu((pre - pre.mean()) / np.sqrt(pre.var() + 1e-5) * w["norm.weight"] + w["norm.bias"])
    head = w["head.weight"][0]
    logit = float(fused @ head + w["head.bias"][0])
    probability = float(_sigmoid(model.cal_a * logit + model.cal_b))

    n_tab = len(tab)
    w_fus = w["fusion.weight"]

    # Selección de la salida hacia atrás.
    fus_ids = _top(fused * head, SHOWN["fusion"])
    to_fusion = np.abs(w_fus[fus_ids] * cat).sum(axis=0)
    tab_ids = _top(to_fusion[:n_tab], SHOWN["projection"])
    gru_ids = _top(to_fusion[n_tab:], SHOWN["temporal"])
    to_tab = np.abs(w["tab.weight"][tab_ids] * x).sum(axis=0)
    named = [i for i, f in enumerate(TABULAR_FEATURES) if f in SHORT_LABELS]
    in_ids = _top(to_tab, SHOWN["input"], allowed=named)
    seq_node = len(TABULAR_FEATURES)  # índice convencional del nodo "secuencia"
    recent = float(seq[-2:].mean())

    layers = [
        {"id": "input", "name": "Entrada", "total": f"{len(TABULAR_FEATURES)} variables + secuencia",
         "nodes": [_node(i, SHORT_LABELS[TABULAR_FEATURES[i]], x[i], 1.0) for i in in_ids]
         + [_node(seq_node, f"Secuencia ({SEQ_WEEKS} semanas)", recent, 1.0)]},
        {"id": "projection", "name": "Rama tabular", "total": str(n_tab),
         "nodes": [_node(j, f"Neurona {j + 1}", tab[j], tab.max()) for j in tab_ids]},
        {"id": "temporal", "name": "Bloque temporal", "total": str(len(temporal)),
         "nodes": [_node(j, f"Neurona {j + 1}", temporal[j], np.abs(temporal).max()) for j in gru_ids]},
        {"id": "fusion", "name": "Fusión compartida", "total": str(len(fused)),
         "nodes": [_node(k, f"Neurona {k + 1}", fused[k], fused.max()) for k in fus_ids]},
        {"id": "heads", "name": "Cabezas de salida", "total": "1 activa · 3 planificadas",
         "nodes": [_node(i, f"{code} · {name}", probability if i == ACTIVE_HEAD else None, 1.0)
                   for i, (code, name) in enumerate(HEADS)]},
    ]

    gru_peak = np.abs(temporal).max() or 1.0
    edges = (
        _edges("input", in_ids, "projection", tab_ids, lambda i, j: w["tab.weight"][j, i] * x[i])
        + [{"source_layer": "input", "source": seq_node, "target_layer": "temporal", "target": j,
            "strength": round(abs(float(temporal[j])) / gru_peak, 3), "sign": 1 if temporal[j] >= 0 else -1}
           for j in gru_ids]
        + _edges("projection", tab_ids, "fusion", fus_ids, lambda j, k: w_fus[k, j] * cat[j])
        + _edges("temporal", gru_ids, "fusion", fus_ids, lambda j, k: w_fus[k, n_tab + j] * cat[n_tab + j])
        + _edges("fusion", fus_ids, "heads", [ACTIVE_HEAD], lambda k, _: head[k] * fused[k], per_target=SHOWN["fusion"])
    )
    return {"probability": probability, "logit": logit, "layers": layers, "edges": edges}
