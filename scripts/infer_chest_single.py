#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rav_chest.data import build_transform
from rav_chest.metrics import per_class_thresholds, sigmoid
from rav_chest.models import build_model
from rav_chest.reporting import probs_to_payload
from rav_chest.utils import load_yaml, save_json, select_device


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Infer chest findings for one image.")
    parser.add_argument("--image", type=str, required=True, help="Path to input image.")
    parser.add_argument(
        "--config",
        type=str,
        default="configs/primary/chest_chexpert.yaml",
    )
    parser.add_argument(
        "--checkpoint",
        type=str,
        default="",
        help="Optional checkpoint path. Defaults to <output_dir>/checkpoints/best.pt",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Optional JSON output path. Defaults to outputs/chest_baseline/reports/<image>.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = load_yaml(args.config)

    class_names = [str(x) for x in cfg["labels"]["columns"]]
    output_dir = Path(cfg["project"]["output_dir"])
    report_dir = output_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    ckpt_path = (
        Path(args.checkpoint)
        if args.checkpoint
        else output_dir / "checkpoints" / "best.pt"
    )
    if not ckpt_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {ckpt_path}")

    device = select_device(cfg["training"].get("device", "auto"))
    model = build_model(
        backbone=cfg["training"]["backbone"],
        num_classes=len(class_names),
        pretrained=False,
        dropout=float(cfg["training"]["dropout"]),
    ).to(device)
    state = torch.load(ckpt_path, map_location=device)
    model.load_state_dict(state["model_state"])
    model.eval()

    transform = build_transform(int(cfg["training"]["image_size"]))
    image = Image.open(args.image).convert("RGB")
    tensor = transform(image).unsqueeze(0).to(device)

    with torch.no_grad():
        logits = model(tensor).detach().cpu().numpy()
    probs = sigmoid(logits)[0]

    thresholds = per_class_thresholds(
        class_names=class_names,
        default_threshold=float(cfg["evaluation"]["default_threshold"]),
        overrides=cfg["evaluation"].get("threshold_overrides", {}),
    )
    payload = probs_to_payload(
        class_names=class_names,
        probs=np.asarray(probs),
        thresholds=np.asarray(thresholds),
    )
    payload["source_image"] = str(Path(args.image).resolve())
    payload["checkpoint"] = str(ckpt_path.resolve())

    if args.output:
        out_path = Path(args.output)
    else:
        out_path = report_dir / f"{Path(args.image).stem}.json"
    save_json(out_path, payload)

    print(f"Saved report payload to: {out_path}")
    print(payload["impression"])


if __name__ == "__main__":
    main()
