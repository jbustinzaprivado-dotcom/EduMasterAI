"""Inferencia del modelo de riesgo con NumPy (§9.7). La API no necesita PyTorch: usa los pesos exportados.

Tipos soportados:
- "multitask_gru": rama densa tabular + GRU sobre la secuencia semanal + fusión (diseño de §9.1).
- "logistic": regresión logística (baseline interpretable).
Las ecuaciones del GRU son las mismas de torch.nn.GRU; una prueba de ml/ verifica que coincidan.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.modules.ml.features import FEATURE_LABELS, TABULAR_FEATURES


def _sigmoid(x):
    return 1 / (1 + np.exp(-x))


def _relu(x):
    return np.maximum(x, 0)


@dataclass
class Explanation:
    feature: str
    label: str
    impact: float  # cuánto sube la probabilidad respecto de un valor típico


class RiskModel:
    def __init__(self, spec: dict):
        self.spec = spec
        self.kind = spec["kind"]
        self.threshold = float(spec["threshold"])
        self.reference = np.array(spec["reference_tabular"], dtype=np.float64)
        self.reference_seq = np.array(spec["reference_sequence"], dtype=np.float64)
        self.w = {k: np.array(v, dtype=np.float64) for k, v in spec["weights"].items()}
        # Calibración de Platt ajustada en validación: convierte el puntaje en una probabilidad honesta (§9.4).
        cal = spec.get("calibration") or {"a": 1.0, "b": 0.0}
        self.cal_a, self.cal_b = float(cal["a"]), float(cal["b"])

    @classmethod
    def load(cls, path: Path) -> "RiskModel":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    # ---------- forward ----------

    def _gru(self, seq: np.ndarray) -> np.ndarray:
        """seq: [lote, semanas, entradas] → último estado oculto [lote, H]."""
        w_ih, w_hh, b_ih, b_hh = self.w["gru.weight_ih"], self.w["gru.weight_hh"], self.w["gru.bias_ih"], self.w["gru.bias_hh"]
        hidden = w_hh.shape[1]
        h = np.zeros((seq.shape[0], hidden))
        for step in range(seq.shape[1]):
            gi = seq[:, step] @ w_ih.T + b_ih
            gh = h @ w_hh.T + b_hh
            r = _sigmoid(gi[:, :hidden] + gh[:, :hidden])
            z = _sigmoid(gi[:, hidden:2 * hidden] + gh[:, hidden:2 * hidden])
            n = np.tanh(gi[:, 2 * hidden:] + r * gh[:, 2 * hidden:])
            h = (1 - z) * n + z * h
        return h

    def logits(self, tabular: np.ndarray, sequence: np.ndarray) -> np.ndarray:
        tabular = np.atleast_2d(tabular).astype(np.float64)
        sequence = np.asarray(sequence, dtype=np.float64)
        if sequence.ndim == 2:
            sequence = sequence[None]
        if self.kind == "logistic":
            x = np.concatenate([tabular, sequence.reshape(len(sequence), -1)], axis=1)
            return x @ self.w["coef"] + self.w["intercept"]
        tab = _relu(tabular @ self.w["tab.weight"].T + self.w["tab.bias"])
        temporal = self._gru(sequence)
        fused = np.concatenate([tab, temporal], axis=1) @ self.w["fusion.weight"].T + self.w["fusion.bias"]
        mu = fused.mean(axis=1, keepdims=True)
        var = fused.var(axis=1, keepdims=True)
        fused = (fused - mu) / np.sqrt(var + 1e-5) * self.w["norm.weight"] + self.w["norm.bias"]
        fused = _relu(fused)  # Dropout no se aplica en inferencia
        return (fused @ self.w["head.weight"].T + self.w["head.bias"]).ravel()

    def predict(self, tabular, sequence) -> np.ndarray:
        return _sigmoid(self.cal_a * self.logits(tabular, sequence) + self.cal_b)

    # ---------- explicación ----------

    def explain(self, tabular: list[float], sequence: list[list[float]], top: int = 3) -> list[Explanation]:
        """Explicación por oclusión: se reemplaza cada variable por su valor típico (mediana de entrenamiento)
        y se mide cuánto baja la probabilidad. Es una aproximación, no prueba causalidad (§9.8)."""
        x = np.array(tabular, dtype=np.float64)
        seq = np.array(sequence, dtype=np.float64)
        base = float(self.predict(x, seq)[0])
        candidates = []
        for i, name in enumerate(TABULAR_FEATURES):
            if name.startswith("level_"):
                continue
            probe = x.copy()
            probe[i] = self.reference[i]
            candidates.append((name, base - float(self.predict(probe, seq)[0])))
        recent = seq.copy()
        recent[-2:] = self.reference_seq[-2:]
        candidates.append(("recent_weeks", base - float(self.predict(x, recent)[0])))
        candidates = [c for c in candidates if c[1] > 0.01]
        candidates.sort(key=lambda c: c[1], reverse=True)
        labels = {**FEATURE_LABELS, "recent_weeks": "menos actividad en las últimas semanas que lo habitual"}
        return [Explanation(name, labels[name], round(impact, 3)) for name, impact in candidates[:top]]
