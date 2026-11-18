"""Entrenamiento y evaluación del modelo de riesgo de abandono (§9.4-§9.6).

Uso (desde ml/):  .venv/Scripts/python -m edumaster_ml.train
Pasos:
 1. Genera el dataset DEMO versionado y su ficha (datasheet).
 2. Entrena baselines interpretables: regresión logística y Gradient Boosting (§9.1 "Importante").
 3. Entrena la red multitarea (rama densa + GRU + fusión) con early stopping por PR-AUC de validación.
 4. Compara en prueba (split temporal), analiza por segmento (nivel del curso) y elige el candidato.
 5. Exporta pesos para la API (NumPy), métricas y model card a ml/registry/.
"""

from __future__ import annotations

import json
import random
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import torch
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, f1_score, precision_score, recall_score, roc_auc_score
from torch import nn

from edumaster_ml import REPO
from edumaster_ml.generate import datasheet, generate, to_arrays
from app.modules.ml.features import FEATURE_SCHEMA_VERSION, SEQ_FEATURES, TABULAR_FEATURES  # noqa: E402
from app.modules.ml.inference import RiskModel  # noqa: E402

SEED = 2026
MODEL_NAME = "riesgo-abandono"
REGISTRY = REPO / "ml" / "registry" / MODEL_NAME


def set_seeds(seed: int = SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


class MultiTaskRiskNet(nn.Module):
    """Diseño de §9.1 con la cabeza C (riesgo). Las cabezas A, B y D se suman cuando existan sus etiquetas;
    la pérdida multitarea enmascara las tareas sin etiqueta (§9.3)."""

    def __init__(self, n_tab: int, n_seq: int, hidden: int = 24, tab_hidden: int = 24, fusion: int = 32):
        super().__init__()
        self.tab = nn.Linear(n_tab, tab_hidden)
        self.gru = nn.GRU(n_seq, hidden, batch_first=True)
        self.fusion = nn.Linear(tab_hidden + hidden, fusion)
        self.norm = nn.LayerNorm(fusion)
        self.dropout = nn.Dropout(0.2)
        self.head = nn.Linear(fusion, 1)

    def forward(self, tab, seq):
        t = torch.relu(self.tab(tab))
        _, h = self.gru(seq)
        x = torch.relu(self.norm(self.fusion(torch.cat([t, h[-1]], dim=1))))
        return self.head(self.dropout(x)).squeeze(1)


def metrics(y: np.ndarray, p: np.ndarray, threshold: float) -> dict:
    pred = (p >= threshold).astype(int)
    return {
        "roc_auc": round(float(roc_auc_score(y, p)), 4),
        "pr_auc": round(float(average_precision_score(y, p)), 4),
        "f1": round(float(f1_score(y, pred, zero_division=0)), 4),
        "precision": round(float(precision_score(y, pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y, pred, zero_division=0)), 4),
        "brier": round(float(brier_score_loss(y, p)), 4),
        "threshold": round(float(threshold), 4),
        "positive_rate": round(float(y.mean()), 4),
    }


def best_threshold(y: np.ndarray, p: np.ndarray) -> float:
    """Umbral elegido en VALIDACIÓN: máximo F1 con recall ≥ 0.6 (alerta de apoyo: preferimos no omitir casos)."""
    best, best_f1 = 0.5, -1.0
    for thr in np.linspace(0.05, 0.95, 91):
        pred = (p >= thr).astype(int)
        if recall_score(y, pred, zero_division=0) < 0.6:
            continue
        f1 = f1_score(y, pred, zero_division=0)
        if f1 > best_f1:
            best, best_f1 = float(thr), f1
    return best


def calibration_bins(y: np.ndarray, p: np.ndarray, bins: int = 5) -> list[dict]:
    edges = np.linspace(0, 1, bins + 1)
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (p >= lo) & (p < hi if hi < 1 else p <= hi)
        if mask.sum():
            out.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": int(mask.sum()),
                        "mean_predicted": round(float(p[mask].mean()), 3), "observed_rate": round(float(y[mask].mean()), 3)})
    return out


def train_network(train, val, epochs: int = 80, patience: int = 10):
    set_seeds()
    xt, st, yt, _ = train
    xv, sv, yv, _ = val
    model = MultiTaskRiskNet(xt.shape[1], st.shape[2])
    pos_weight = torch.tensor((1 - yt.mean()) / max(yt.mean(), 1e-6))
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    optim = torch.optim.Adam(model.parameters(), lr=3e-3, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(optim, mode="max", factor=0.5, patience=4)
    tensors = [torch.tensor(a) for a in (xt, st, yt)]
    best, best_state, waited, history = -1.0, None, 0, []
    for epoch in range(epochs):
        model.train()
        order = torch.randperm(len(yt))
        losses = []
        for i in range(0, len(order), 128):
            idx = order[i:i + 128]
            optim.zero_grad()
            loss = loss_fn(model(tensors[0][idx], tensors[1][idx]), tensors[2][idx])
            loss.backward()
            optim.step()
            losses.append(loss.item())
        model.eval()
        with torch.no_grad():
            pv = torch.sigmoid(model(torch.tensor(xv), torch.tensor(sv))).numpy()
        score = average_precision_score(yv, pv)
        sched.step(score)
        history.append({"epoch": epoch + 1, "loss": round(float(np.mean(losses)), 4), "val_pr_auc": round(float(score), 4)})
        if score > best + 1e-4:
            best, best_state, waited = score, {k: v.clone() for k, v in model.state_dict().items()}, 0
        else:
            waited += 1
            if waited >= patience:  # early stopping (§9.4)
                break
    model.load_state_dict(best_state)
    model.eval()
    return model, history


def export_network(model: MultiTaskRiskNet) -> dict:
    sd = {k: v.detach().numpy().tolist() for k, v in model.state_dict().items()}
    return {
        "tab.weight": sd["tab.weight"], "tab.bias": sd["tab.bias"],
        "gru.weight_ih": sd["gru.weight_ih_l0"], "gru.weight_hh": sd["gru.weight_hh_l0"],
        "gru.bias_ih": sd["gru.bias_ih_l0"], "gru.bias_hh": sd["gru.bias_hh_l0"],
        "fusion.weight": sd["fusion.weight"], "fusion.bias": sd["fusion.bias"],
        "norm.weight": sd["norm.weight"], "norm.bias": sd["norm.bias"],
        "head.weight": sd["head.weight"], "head.bias": sd["head.bias"],
    }


def main(n: int = 14000) -> dict:
    started = time.time()
    set_seeds()
    samples = generate(n=n, seed=SEED)
    sheet = datasheet(samples, SEED, n)
    train, val, test = (to_arrays(samples, s) for s in ("train", "val", "test"))
    flat = lambda d: np.concatenate([d[0], d[1].reshape(len(d[1]), -1)], axis=1)  # noqa: E731

    results, scores, calibrations = {}, {}, {}
    # Baselines (§9.1): primero lo simple e interpretable.
    logreg = LogisticRegression(max_iter=2000, class_weight="balanced").fit(flat(train), train[2])
    gbm = HistGradientBoostingClassifier(random_state=SEED, class_weight="balanced").fit(flat(train), train[2])
    net, history = train_network(train, val)
    logit = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / np.clip(1 - p, 1e-6, 1))  # noqa: E731
    raw = {  # puntajes sin calibrar (logits)
        "logistic_regression": lambda d: logreg.decision_function(flat(d)),
        "gradient_boosting": lambda d: logit(gbm.predict_proba(flat(d))[:, 1]),
        "multitask_gru": lambda d: net(torch.tensor(d[0]), torch.tensor(d[1])).detach().numpy(),
    }
    for name, score in raw.items():
        # El entrenamiento con pesos por clase infla las probabilidades: se calibran con Platt en validación.
        zv, zt = score(val), score(test)
        platt = LogisticRegression().fit(zv.reshape(-1, 1), val[2])
        a, b = float(platt.coef_[0][0]), float(platt.intercept_[0])
        pv, pt = 1 / (1 + np.exp(-(a * zv + b))), 1 / (1 + np.exp(-(a * zt + b)))
        thr = best_threshold(val[2], pv)
        results[name] = {"validation": metrics(val[2], pv, thr), "test": metrics(test[2], pt, thr)}
        scores[name], calibrations[name] = (pv, pt, thr), {"a": a, "b": b}

    # Selección SOLO con validación (la prueba se mira al final). Regla de §9.1: la red se publica únicamente
    # si mejora al mejor baseline desplegable en PR-AUC (≥ 0.005) sin empeorar la calibración (Brier).
    base_v, net_v = results["logistic_regression"]["validation"], results["multitask_gru"]["validation"]
    network_wins = net_v["pr_auc"] >= base_v["pr_auc"] + 0.005 and net_v["brier"] <= base_v["brier"] + 0.002
    best_name = "multitask_gru" if network_wins else "logistic_regression"
    overall_best = max(results, key=lambda k: results[k]["validation"]["pr_auc"])

    _, pt, thr = scores[best_name]
    levels = np.array(test[3])
    segments = {lvl: metrics(test[2][levels == lvl], pt[levels == lvl], thr) for lvl in sorted(set(test[3]))
                if test[2][levels == lvl].sum() > 0}

    reference_tab = np.median(train[0], axis=0).tolist()
    reference_seq = np.median(train[1], axis=0).tolist()
    if best_name == "multitask_gru":
        weights, kind = export_network(net), "multitask_gru"
    else:
        weights = {"coef": logreg.coef_[0].tolist(), "intercept": float(logreg.intercept_[0])}
        kind = "logistic"

    version = "1.0.0"
    spec = {
        "name": MODEL_NAME, "version": version, "kind": kind, "task": "dropout_risk",
        "threshold": thr, "calibration": calibrations[best_name], "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "tabular_features": TABULAR_FEATURES, "sequence_features": SEQ_FEATURES,
        "reference_tabular": reference_tab, "reference_sequence": reference_seq, "weights": weights,
    }

    # Verificación: la inferencia NumPy de la API reproduce las probabilidades del modelo entrenado.
    api_p = RiskModel(spec).predict(test[0], test[1])
    max_diff = float(np.abs(api_p - pt).max())
    assert max_diff < 1e-4, f"La inferencia NumPy difiere del modelo entrenado ({max_diff})"

    out = REGISTRY / version
    out.mkdir(parents=True, exist_ok=True)
    card = {
        "name": MODEL_NAME, "version": version, "kind": kind, "task": "Riesgo de abandono (cabeza C de §9.1)",
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"), "seed": SEED,
        "dataset": {k: sheet[k] for k in ("name", "version", "rows", "sha256", "label", "population", "split")},
        "selection": {"criterion": "La red se publica solo si supera al baseline logístico en PR-AUC de validación "
                                   "(≥ 0.005) sin empeorar el Brier; si no, se publica el baseline (§9.1).",
                      "chosen": best_name, "network_wins": network_wins, "best_overall_validation": overall_best},
        "results": results, "segments_test": segments,
        "calibration_test": calibration_bins(test[2], pt),
        "training_history": history,
        "numpy_vs_training_max_diff": max_diff,
        "limitations": [
            "Entrenado SOLO con datos sintéticos DEMO: no es válido para decisiones sobre personas reales (§8.1).",
            "Es una alerta de apoyo para el docente; nunca sanciona ni califica (§2.4, §9.8).",
            "La probabilidad es una estimación, no un diagnóstico; los factores explican correlaciones, no causas.",
            "No usa variables sensibles. Debe recalibrarse y reevaluarse con datos institucionales autorizados.",
        ],
        "status": "candidate",
        "training_seconds": round(time.time() - started, 1),
    }
    (out / "model.json").write_text(json.dumps(spec), encoding="utf-8")
    (out / "model_card.json").write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    (REPO / "ml" / "datasets").mkdir(exist_ok=True)
    (REPO / "ml" / "datasets" / "riesgo-abandono-demo.datasheet.json").write_text(
        json.dumps(sheet, ensure_ascii=False, indent=2), encoding="utf-8")
    return card


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    card = main()
    for name, r in card["results"].items():
        v, t = r["validation"], r["test"]
        print(f"{name:22s} val PR-AUC {v['pr_auc']:.3f} | test ROC-AUC {t['roc_auc']:.3f} PR-AUC {t['pr_auc']:.3f} "
              f"F1 {t['f1']:.3f} recall {t['recall']:.3f} Brier {t['brier']:.3f}")
    print("Elegido:", card["selection"], "· tiempo", card["training_seconds"], "s")
