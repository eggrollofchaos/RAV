from __future__ import annotations

import numpy as np
import torch
from sklearn.metrics import confusion_matrix, roc_auc_score


def evaluate_full(
    model, loader, device: str | torch.device, name: str = "Eval"
) -> dict[str, object]:
    model.eval()

    all_labels = []
    all_probs = []
    all_preds = []

    with torch.no_grad():
        for images, labels in loader:
            images = images.to(device)
            labels = labels.to(device)

            logits = model(images)
            probs = torch.sigmoid(logits)
            preds = (probs > 0.5).int().squeeze(1)

            all_labels.extend(labels.cpu().numpy())
            all_probs.extend(probs.squeeze(1).cpu().numpy())
            all_preds.extend(preds.cpu().numpy())

    all_labels = np.array(all_labels)
    all_preds = np.array(all_preds)
    all_probs = np.array(all_probs)

    acc = (all_preds == all_labels).mean()
    tn, fp, fn, tp = confusion_matrix(all_labels, all_preds).ravel()
    sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
    auc = roc_auc_score(all_labels, all_probs)

    print(f"\n{name} Results:")
    print(f"Accuracy: {acc * 100:.2f}%")
    print(f"Sensitivity (Recall Pneumonia): {sensitivity:.4f}")
    print(f"Specificity (Recall Normal): {specificity:.4f}")
    print(f"AUROC: {auc:.4f}")
    print("\nConfusion Matrix:")
    print(f"TN: {tn}  FP: {fp}")
    print(f"FN: {fn}  TP: {tp}")

    return {
        "accuracy": acc,
        "sensitivity": sensitivity,
        "specificity": specificity,
        "auc": auc,
        "confusion_matrix": (tn, fp, fn, tp),
    }
