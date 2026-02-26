from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import torch
from PIL import Image
from torch import nn

from rav_chest.data import build_transform
from rav_chest.metrics import per_class_thresholds, sigmoid
from rav_chest.models import build_model
from rav_chest.reporting import probs_to_payload
from rav_chest.utils import load_yaml, select_device


@dataclass
class InferenceBundle:
    config_path: Path
    checkpoint_path: Path
    cfg: Dict[str, Any]
    class_names: List[str]
    thresholds: np.ndarray
    transform: Any
    device: torch.device
    model: nn.Module


def resolve_checkpoint_path(cfg: Dict[str, Any], checkpoint_override: str = "") -> Path:
    if checkpoint_override:
        return Path(checkpoint_override)
    output_dir = Path(cfg["project"]["output_dir"])
    return output_dir / "checkpoints" / "best.pt"


def load_inference_bundle(
    config_path: str | Path,
    checkpoint_override: str = "",
) -> InferenceBundle:
    config_path = Path(config_path)
    cfg = load_yaml(config_path)

    class_names = [str(x) for x in cfg["labels"]["columns"]]
    checkpoint_path = resolve_checkpoint_path(cfg, checkpoint_override)
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

    device = select_device(cfg["training"].get("device", "auto"))
    model = build_model(
        backbone=cfg["training"]["backbone"],
        num_classes=len(class_names),
        pretrained=False,
        dropout=float(cfg["training"]["dropout"]),
    ).to(device)

    state = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(state["model_state"])
    model.eval()

    thresholds = per_class_thresholds(
        class_names=class_names,
        default_threshold=float(cfg["evaluation"]["default_threshold"]),
        overrides=cfg["evaluation"].get("threshold_overrides", {}),
    )
    transform = build_transform(int(cfg["training"]["image_size"]))

    return InferenceBundle(
        config_path=config_path,
        checkpoint_path=checkpoint_path,
        cfg=cfg,
        class_names=class_names,
        thresholds=thresholds,
        transform=transform,
        device=device,
        model=model,
    )


def infer_from_pil(
    bundle: InferenceBundle,
    image: Image.Image,
) -> Tuple[Dict[str, Any], np.ndarray]:
    tensor = bundle.transform(image.convert("RGB")).unsqueeze(0).to(bundle.device)
    with torch.no_grad():
        logits = bundle.model(tensor).detach().cpu().numpy()

    probs = sigmoid(logits)[0]
    payload = probs_to_payload(
        class_names=bundle.class_names,
        probs=np.asarray(probs),
        thresholds=np.asarray(bundle.thresholds),
    )
    payload["checkpoint"] = str(bundle.checkpoint_path.resolve())
    payload["config"] = str(bundle.config_path.resolve())
    return payload, probs

