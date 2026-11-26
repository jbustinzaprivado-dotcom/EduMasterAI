"""Recorrido real de una predicción por la red (§4.10, D51, D52).

Repite la propagación hacia delante de `RiskModel` paso a paso y guarda las activaciones de cada capa, para un
estudiante o para todo el grupo de una oferta (D52: se promedian las activaciones y los aportes de cada persona).
La interfaz no puede dibujar las 24 + 24 + 32 neuronas, así que se eligen las que MÁS APORTARON, de la salida
hacia atrás:

1. Fusión: las neuronas con mayor |activación × peso hacia la salida| (aporte al logit).
2. Rama tabular y bloque temporal: las que más aportan a esas neuronas de fusión (antes de la normalización).
3. Entrada: las variables que más aportan a las neuronas tabulares elegidas, más un nodo para la secuencia semanal.

El aporte antes de LayerNorm es una aproximación para elegir qué mostrar; los valores de cada neurona y la
probabilidad son exactos (una prueba verifica que coinciden con `RiskModel.predict`).
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
    return sorted(sorted(idx, key=lambda i: -abs(float(scores[i])))[:k])


def _edges(src_layer: str, src_ids: list[int], dst_layer: str, dst_ids: list[int], contrib, per_target: int = 2,
           per_source: int = 2):
    """Conexiones a mostrar: para cada destino sus `per_target` fuentes con mayor |aporte medio|, y para cada fuente
    sus `per_source` destinos principales (D53: así toda neurona mostrada tiene un camino hasta la salida y se puede
    seguir el recorrido de cada variable). Fuerza normalizada a [0, 1]."""
    pairs: dict[tuple[int, int], float] = {}
    for d in dst_ids:
        for s in sorted(src_ids, key=lambda s: -abs(contrib(s, d)))[:per_target]:
            pairs[(s, d)] = contrib(s, d)
    for s in src_ids:
        for d in sorted(dst_ids, key=lambda d: -abs(contrib(s, d)))[:per_source]:
            pairs[(s, d)] = contrib(s, d)
    raw = [(s, d, c) for (s, d), c in pairs.items()]
    peak = max((abs(c) for *_, c in raw), default=0.0) or 1.0
    return [{"source_layer": src_layer, "source": s, "target_layer": dst_layer, "target": d,
             "strength": round(abs(c) / peak, 3), "sign": 1 if c >= 0 else -1} for s, d, c in raw]


def _node(index: int, label: str, value: float | None, peak: float) -> dict:
    intensity = 0.0 if value is None else min(abs(value) / (peak or 1.0), 1.0)
    return {"index": index, "label": label, "value": None if value is None else round(float(value), 4),
            "intensity": round(intensity, 3)}


def build(model: RiskModel, tabulars: list[list[float]], sequences: list[list[list[float]]]) -> dict:
    """Traza de una o varias matrículas. Con varias, cada valor es el promedio del grupo."""
    if model.kind != "multitask_gru":
        raise TraceUnavailable
    if not tabulars:
        raise ValueError("Sin matrículas que recorrer")
    w = model.w
    x = np.asarray(tabulars, dtype=np.float64)  # [n, 13]
    seq = np.asarray(sequences, dtype=np.float64)  # [n, semanas, 4]

    # Propagación hacia delante, igual que RiskModel.logits pero conservando cada capa.
    tab = _relu(x @ w["tab.weight"].T + w["tab.bias"])  # [n, 24]
    temporal = model._gru(seq)  # [n, 24]
    cat = np.concatenate([tab, temporal], axis=1)  # [n, 48]
    pre = cat @ w["fusion.weight"].T + w["fusion.bias"]
    mu, var = pre.mean(axis=1, keepdims=True), pre.var(axis=1, keepdims=True)
    fused = _relu((pre - mu) / np.sqrt(var + 1e-5) * w["norm.weight"] + w["norm.bias"])  # [n, 32]
    head = w["head.weight"][0]
    logits = fused @ head + w["head.bias"][0]
    probabilities = _sigmoid(model.cal_a * logits + model.cal_b)  # [n]

    n_tab = tab.shape[1]
    w_fus, w_tab = w["fusion.weight"], w["tab.weight"]

    # Selección de la salida hacia atrás, con el aporte absoluto medio del grupo.
    fus_ids = _top(np.abs(fused * head).mean(axis=0), SHOWN["fusion"])
    to_fusion = np.abs(w_fus[fus_ids][None] * cat[:, None, :]).sum(axis=1).mean(axis=0)  # [48]
    tab_ids = _top(to_fusion[:n_tab], SHOWN["projection"])
    gru_ids = _top(to_fusion[n_tab:], SHOWN["temporal"])
    to_tab = np.abs(w_tab[tab_ids][None] * x[:, None, :]).sum(axis=1).mean(axis=0)  # [13]
    named = [i for i, f in enumerate(TABULAR_FEATURES) if f in SHORT_LABELS]
    in_ids = _top(to_tab, SHOWN["input"], allowed=named)
    seq_node = len(TABULAR_FEATURES)  # índice convencional del nodo "secuencia"

    m_x, m_tab, m_tmp, m_cat, m_fus = x.mean(0), tab.mean(0), temporal.mean(0), cat.mean(0), fused.mean(0)
    probability = float(probabilities.mean())

    layers = [
        {"id": "input", "name": "Entrada", "total": f"{len(TABULAR_FEATURES)} variables + secuencia",
         "nodes": [_node(i, SHORT_LABELS[TABULAR_FEATURES[i]], m_x[i], 1.0) for i in in_ids]
         + [_node(seq_node, f"Secuencia ({SEQ_WEEKS} semanas)", float(seq[:, -2:].mean()), 1.0)]},
        {"id": "projection", "name": "Rama tabular", "total": str(n_tab),
         "nodes": [_node(j, f"Neurona {j + 1}", m_tab[j], m_tab.max()) for j in tab_ids]},
        {"id": "temporal", "name": "Bloque temporal", "total": str(temporal.shape[1]),
         "nodes": [_node(j, f"Neurona {j + 1}", m_tmp[j], np.abs(m_tmp).max()) for j in gru_ids]},
        {"id": "fusion", "name": "Fusión compartida", "total": str(fused.shape[1]),
         "nodes": [_node(k, f"Neurona {k + 1}", m_fus[k], m_fus.max()) for k in fus_ids]},
        {"id": "heads", "name": "Cabezas de salida", "total": "1 activa · 3 planificadas",
         "nodes": [_node(i, f"{code} · {name}", probability if i == ACTIVE_HEAD else None, 1.0)
                   for i, (code, name) in enumerate(HEADS)]},
    ]

    # Aporte medio con signo de cada conexión (para un estudiante, es su aporte exacto).
    gru_peak = np.abs(m_tmp).max() or 1.0
    edges = (
        _edges("input", in_ids, "projection", tab_ids, lambda i, j: w_tab[j, i] * m_x[i])
        + [{"source_layer": "input", "source": seq_node, "target_layer": "temporal", "target": j,
            "strength": round(abs(float(m_tmp[j])) / gru_peak, 3), "sign": 1 if m_tmp[j] >= 0 else -1}
           for j in gru_ids]
        + _edges("projection", tab_ids, "fusion", fus_ids, lambda j, k: w_fus[k, j] * m_cat[j])
        + _edges("temporal", gru_ids, "fusion", fus_ids, lambda j, k: w_fus[k, n_tab + j] * m_cat[n_tab + j])
        + _edges("fusion", fus_ids, "heads", [ACTIVE_HEAD], lambda k, _: float((fused[:, k] * head[k]).mean()),
                 per_target=SHOWN["fusion"])
    )
    return {"probability": probability, "probabilities": [float(p) for p in probabilities],
            "layers": layers, "edges": edges}
