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


def compute_confusion_matrices(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    class_names: Sequence[str],
    thresholds: np.ndarray,
) -> Dict[str, Dict[str, float | int]]:
    y_pred = threshold_predictions(y_prob, thresholds)
    out: Dict[str, Dict[str, float | int]] = {}

    for i, name in enumerate(class_names):
        true_i = (y_true[:, i] >= 0.5).astype(np.int32)
        pred_i = y_pred[:, i].astype(np.int32)

        tp = int(np.sum((true_i == 1) & (pred_i == 1)))
        tn = int(np.sum((true_i == 0) & (pred_i == 0)))
        fp = int(np.sum((true_i == 0) & (pred_i == 1)))
        fn = int(np.sum((true_i == 1) & (pred_i == 0)))

        support_pos = int(np.sum(true_i == 1))
        support_neg = int(np.sum(true_i == 0))
        total = int(len(true_i))

        sensitivity = float(tp / (tp + fn)) if (tp + fn) else 0.0
        specificity = float(tn / (tn + fp)) if (tn + fp) else 0.0
        precision = float(tp / (tp + fp)) if (tp + fp) else 0.0
        npv = float(tn / (tn + fn)) if (tn + fn) else 0.0
        accuracy = float((tp + tn) / total) if total else 0.0

        out[str(name)] = {
            "tp": tp,
            "tn": tn,
            "fp": fp,
            "fn": fn,
            "support_positive": support_pos,
            "support_negative": support_neg,
            "threshold": float(thresholds[i]),
            "sensitivity": sensitivity,
            "specificity": specificity,
            "precision": precision,
            "npv": npv,
            "accuracy": accuracy,
        }

    return out


def optimize_thresholds(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    class_names: Sequence[str],
    *,
    objective: str = "f1",
    threshold_candidates: np.ndarray | None = None,
    default_threshold: float = 0.5,
) -> tuple[np.ndarray, Dict[str, Dict[str, float]]]:
    objective = str(objective).strip().lower()
    if objective != "f1":
        raise ValueError(f"Unsupported threshold objective '{objective}'. Supported: f1")

    if threshold_candidates is None:
        threshold_candidates = np.linspace(0.05, 0.95, num=19, dtype=np.float32)
    else:
        threshold_candidates = np.asarray(threshold_candidates, dtype=np.float32)

    tuned: List[float] = []
    details: Dict[str, Dict[str, float]] = {}

    for i, name in enumerate(class_names):
        true_i = y_true[:, i].astype(np.int32)
        prob_i = y_prob[:, i]

        best_threshold = float(default_threshold)
        best_score = -1.0
        best_balanced_accuracy = -1.0
        best_prevalence_gap = float("inf")
        best_stats = {
            "f1": 0.0,
            "sensitivity": 0.0,
            "specificity": 0.0,
            "precision": 0.0,
            "predicted_positive_rate": 0.0,
            "prevalence": float(np.mean(true_i)),
        }

        for threshold in threshold_candidates:
            pred_i = (prob_i >= float(threshold)).astype(np.int32)

            tp = int(np.sum((true_i == 1) & (pred_i == 1)))
            tn = int(np.sum((true_i == 0) & (pred_i == 0)))
            fp = int(np.sum((true_i == 0) & (pred_i == 1)))
            fn = int(np.sum((true_i == 1) & (pred_i == 0)))

            sensitivity = float(tp / (tp + fn)) if (tp + fn) else 0.0
            specificity = float(tn / (tn + fp)) if (tn + fp) else 0.0
            precision = float(tp / (tp + fp)) if (tp + fp) else 0.0
            predicted_positive_rate = float(np.mean(pred_i))
            prevalence = float(np.mean(true_i))
            score = float(f1_score(true_i, pred_i, zero_division=0))
            balanced_accuracy = 0.5 * (sensitivity + specificity)
            prevalence_gap = abs(predicted_positive_rate - prevalence)

            better = score > best_score
            if not better and np.isclose(score, best_score):
                better = balanced_accuracy > best_balanced_accuracy
            if not better and np.isclose(score, best_score) and np.isclose(
                balanced_accuracy, best_balanced_accuracy
            ):
                better = prevalence_gap < best_prevalence_gap

            if better:
                best_threshold = float(threshold)
                best_score = score
                best_balanced_accuracy = balanced_accuracy
                best_prevalence_gap = prevalence_gap
                best_stats = {
                    "f1": score,
                    "sensitivity": sensitivity,
                    "specificity": specificity,
                    "precision": precision,
                    "predicted_positive_rate": predicted_positive_rate,
                    "prevalence": prevalence,
                }

        tuned.append(best_threshold)
        details[str(name)] = {
            "threshold": best_threshold,
            **best_stats,
        }

    return np.asarray(tuned, dtype=np.float32), details
