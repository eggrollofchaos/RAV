from __future__ import annotations

from typing import Any


def classify_confidence_tier(p_abnormal: float, threshold: float) -> str:
    probability = float(p_abnormal)
    cutoff = float(threshold)

    if probability <= cutoff:
        return "normal"
    if probability <= 0.7:
        return "borderline"
    if probability <= 0.8:
        return "moderate"
    return "high"


def generate_impression(p_abnormal: float, threshold: float) -> str:
    probability = float(p_abnormal)
    tier = classify_confidence_tier(probability, threshold)

    if tier == "normal":
        return "Normal chest X-ray."
    if tier == "borderline":
        return f"Borderline pneumonia-like abnormality signal (confidence: {probability:.2f})."
    if tier == "moderate":
        return f"Findings suggest pneumonia-like abnormality (confidence: {probability:.2f})."
    return f"High-confidence pneumonia-like abnormality signal (confidence: {probability:.2f})."


def probs_to_payload(p_abnormal: float, threshold: float) -> dict[str, Any]:
    probability = float(p_abnormal)
    cutoff = float(threshold)
    tier = classify_confidence_tier(probability, cutoff)

    return {
        "prediction": "PNEUMONIA" if probability > cutoff else "NORMAL",
        "p_abnormal": round(probability, 6),
        "confidence_tier": tier,
        "threshold": round(cutoff, 6),
        "impression": generate_impression(probability, cutoff),
    }
