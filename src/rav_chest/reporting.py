from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence

import numpy as np


CRITICAL_FINDINGS = {"Pneumothorax", "Pleural Effusion", "Edema"}


@dataclass
class Finding:
    name: str
    confidence: float
    threshold: float
    is_positive: bool


def build_structured_findings(
    class_names: Sequence[str],
    probs: Sequence[float],
    thresholds: Sequence[float],
    top_k: int = 6,
) -> Dict[str, object]:
    findings: List[Finding] = []
    for name, p, t in zip(class_names, probs, thresholds):
        findings.append(
            Finding(
                name=name,
                confidence=float(p),
                threshold=float(t),
                is_positive=bool(p >= t),
            )
        )

    positive = [f for f in findings if f.is_positive]
    positive_sorted = sorted(positive, key=lambda x: x.confidence, reverse=True)[:top_k]
    critical = [f.name for f in positive_sorted if f.name in CRITICAL_FINDINGS]

    return {
        "findings": [
            {
                "name": f.name,
                "confidence": round(f.confidence, 4),
                "threshold": round(f.threshold, 4),
            }
            for f in positive_sorted
        ],
        "critical_flags": critical,
    }


def generate_impression(payload: Dict[str, object]) -> str:
    findings = payload.get("findings", [])
    critical_flags = payload.get("critical_flags", [])

    if not findings:
        return "No high-confidence acute cardiopulmonary abnormality identified."

    finding_names = [item["name"] for item in findings]
    if len(finding_names) == 1:
        findings_text = finding_names[0]
    else:
        findings_text = ", ".join(finding_names[:-1]) + f", and {finding_names[-1]}"

    impression = f"Findings suggest: {findings_text}."
    if critical_flags:
        impression += " Critical attention recommended for: " + ", ".join(critical_flags) + "."
    return impression


def probs_to_payload(
    class_names: Sequence[str],
    probs: np.ndarray,
    thresholds: np.ndarray,
) -> Dict[str, object]:
    structured = build_structured_findings(
        class_names=class_names,
        probs=probs.tolist(),
        thresholds=thresholds.tolist(),
    )
    structured["impression"] = generate_impression(structured)
    return structured

