"""Métricas con incertidumbre: con 43 neutrales en test, una cifra sin intervalo engaña."""

import numpy as np
from sklearn.metrics import confusion_matrix, f1_score

from caso_uso_llm.classify.datasets import LABELS

N_BOOT = 2000


def f1_macro(y, pred) -> float:
    return float(f1_score(y, pred, labels=list(LABELS), average="macro", zero_division=0))


def per_class_f1(y, pred) -> dict[str, float]:
    scores = f1_score(y, pred, labels=list(LABELS), average=None, zero_division=0)
    return {lab: round(float(s), 4) for lab, s in zip(LABELS, scores, strict=True)}


def bootstrap_ci(y, pred, seed: int, n: int = N_BOOT) -> tuple[float, float]:
    """IC 95 % del F1 macro remuestreando las filas del test."""
    y, pred = np.asarray(y), np.asarray(pred)
    rng = np.random.default_rng(seed)
    stats = [f1_macro(y[i], pred[i]) for i in rng.integers(0, len(y), (n, len(y)))]
    lo, hi = np.percentile(stats, [2.5, 97.5])
    return round(float(lo), 4), round(float(hi), 4)


def paired_bootstrap(y, pred_a, pred_b, seed: int, n: int = N_BOOT) -> dict:
    """Diferencia F1(a) − F1(b) sobre los MISMOS remuestreos: ¿es mayor que el ruido del test?"""
    y, a, b = np.asarray(y), np.asarray(pred_a), np.asarray(pred_b)
    rng = np.random.default_rng(seed)
    diffs = np.array(
        [f1_macro(y[i], a[i]) - f1_macro(y[i], b[i]) for i in rng.integers(0, len(y), (n, len(y)))]
    )
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return {
        "diff": round(f1_macro(y, a) - f1_macro(y, b), 4),
        "ci95": (round(float(lo), 4), round(float(hi), 4)),
        "p_a_better": round(float((diffs > 0).mean()), 3),
    }


def confusion(y, pred) -> list[list[int]]:
    return confusion_matrix(y, pred, labels=list(LABELS)).tolist()
