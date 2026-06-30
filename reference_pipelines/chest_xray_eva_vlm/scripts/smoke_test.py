from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import numpy as np
from PIL import Image
import torch

from rav_reference import llm
from rav_reference.llm import get_openai_client
from rav_reference.models import EvaXBinaryModel, load_checkpoint
from rav_reference.pipeline import (
    InferenceBundle,
    build_inference_transform,
    infer_from_pil,
)
from rav_reference.reporting import classify_confidence_tier, probs_to_payload


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    checkpoint_path = ROOT / "eva_x_tiny_binary_best.pt"

    imported = [
        "rav.version",
        "rav.utils",
        "rav.models",
        "rav.reporting",
        "rav.pipeline",
        "rav.llm",
    ]
    print(f"Imported modules: {', '.join(imported)}")

    checkpoint = load_checkpoint(checkpoint_path, map_location="cpu")
    model = EvaXBinaryModel()
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    model.eval()
    print("Checkpoint restore succeeded on CPU.")

    bundle = InferenceBundle(
        checkpoint_path=checkpoint_path,
        class_names=["NORMAL", "PNEUMONIA"],
        transform=build_inference_transform(),
        device=torch.device("cpu"),
        model=model,
    )
    synthetic = Image.fromarray(np.zeros((224, 224, 3), dtype=np.uint8))
    payload, probability = infer_from_pil(bundle, synthetic, threshold=0.5)
    expect(0.0 <= probability <= 1.0, "Sigmoid probability must be in [0, 1].")
    expect(
        payload["prediction"] in {"NORMAL", "PNEUMONIA"}, "Unexpected prediction label."
    )
    print(f"Synthetic inference succeeded with p_abnormal={probability:.6f}.")

    expect(classify_confidence_tier(0.3, 0.5) == "normal", "0.3 should be normal.")
    expect(
        classify_confidence_tier(0.6, 0.5) == "borderline", "0.6 should be borderline."
    )
    expect(
        classify_confidence_tier(0.75, 0.5) == "moderate", "0.75 should be moderate."
    )
    expect(classify_confidence_tier(0.9, 0.5) == "high", "0.9 should be high.")
    print("Tier boundary checks passed.")

    report_payload = probs_to_payload(0.75, 0.5)
    for key in [
        "prediction",
        "p_abnormal",
        "confidence_tier",
        "threshold",
        "impression",
    ]:
        expect(key in report_payload, f"Missing payload key: {key}")
    print("Report payload schema checks passed.")

    original_env = os.environ.pop("OPENAI_API_KEY", None)
    original_loader = llm._load_key_from_env_file
    llm._load_key_from_env_file = lambda path: ""
    try:
        try:
            get_openai_client()
        except ValueError:
            print("Missing API key behavior verified.")
        else:
            raise AssertionError(
                "get_openai_client() should raise when no API key is available."
            )
    finally:
        llm._load_key_from_env_file = original_loader
        if original_env is not None:
            os.environ["OPENAI_API_KEY"] = original_env

    print("Smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
