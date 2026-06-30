from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image
import torch
from torch import nn
from torchvision import transforms

from .models import (
    class_names_from_checkpoint,
    load_checkpoint,
    load_eva_x_binary_from_checkpoint,
)
from .reporting import probs_to_payload
from .utils import select_device


@dataclass
class InferenceBundle:
    checkpoint_path: Path
    class_names: list[str]
    transform: Any
    device: torch.device
    model: nn.Module


def build_inference_transform() -> transforms.Compose:
    return transforms.Compose(
        [
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=(0.485, 0.456, 0.406),
                std=(0.229, 0.224, 0.225),
            ),
        ]
    )


def load_inference_bundle(
    checkpoint_path: str | Path,
    device_hint: str = "auto",
) -> InferenceBundle:
    resolved = Path(checkpoint_path).expanduser().resolve()
    checkpoint = load_checkpoint(resolved, map_location="cpu")
    device = select_device(device_hint)
    model = load_eva_x_binary_from_checkpoint(checkpoint, device=device)

    return InferenceBundle(
        checkpoint_path=resolved,
        class_names=class_names_from_checkpoint(checkpoint),
        transform=build_inference_transform(),
        device=device,
        model=model,
    )


def infer_from_pil(
    bundle: InferenceBundle,
    image: Image.Image,
    threshold: float = 0.5,
) -> tuple[dict[str, Any], float]:
    tensor = bundle.transform(image.convert("RGB")).unsqueeze(0).to(bundle.device)

    with torch.no_grad():
        logits = bundle.model(tensor)
        probability = float(torch.sigmoid(logits).item())

    return probs_to_payload(probability, threshold), probability
