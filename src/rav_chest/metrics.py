from __future__ import annotations

from typing import Dict, List, Sequence

import numpy as np
from sklearn.metrics import brier_score_loss, f1_score, roc_auc_score


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def threshold_predictions(probs: np.ndarray, thresholds: np.ndarray) -> np.ndarray:
    return (probs >= thresholds[None, :]).astype(np.int32)


def per_class_thresholds(
    class_names: Sequence[str],
    default_threshold: float,
    overrides: Dict[str, float] | None = None,
) -> np.ndarray:
    overrides = overrides or {}
    return np.array(
        [float(overrides.get(name, default_threshold)) for name in class_names],
        dtype=np.float32,
    )


def compute_metrics(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    class_names: Sequence[str],
    thresholds: np.ndarray,
) -> Dict[str, object]:
    y_pred = threshold_predictions(y_prob, thresholds)

    macro_auroc_values: List[float] = []
    macro_f1_values: List[float] = []
    macro_brier_values: List[float] = []
    per_class: Dict[str, Dict[str, float | None]] = {}

    for i, name in enumerate(class_names):
        true_i = y_true[:, i]
        prob_i = y_prob[:, i]
        pred_i = y_pred[:, i]

        auroc_i = None
        try:
            auroc_i = float(roc_auc_score(true_i, prob_i))
            macro_auroc_values.append(auroc_i)
        except ValueError:
            pass

        f1_i = float(f1_score(true_i, pred_i, zero_division=0))
        macro_f1_values.append(f1_i)

        brier_i = float(brier_score_loss(true_i, prob_i))
        macro_brier_values.append(brier_i)

        per_class[name] = {
            "auroc": auroc_i,
            "f1": f1_i,
            "brier": brier_i,
            "threshold": float(thresholds[i]),
            "prevalence": float(np.mean(true_i)),
            "predicted_positive_rate": float(np.mean(pred_i)),
        }

    macro = {
        "auroc": float(np.mean(macro_auroc_values)) if macro_auroc_values else None,
        "f1": float(np.mean(macro_f1_values)),
        "brier": float(np.mean(macro_brier_values)),
    }
    return {"macro": macro, "per_class": per_class}

