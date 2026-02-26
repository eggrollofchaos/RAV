#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rav_chest.pipeline import infer_from_pil, load_inference_bundle
from rav_chest.utils import save_json


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
    bundle = load_inference_bundle(args.config, args.checkpoint)
    output_dir = Path(bundle.cfg["project"]["output_dir"])
    report_dir = output_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    image = Image.open(args.image).convert("RGB")
    payload, _ = infer_from_pil(bundle, image)
    payload["source_image"] = str(Path(args.image).resolve())

    if args.output:
        out_path = Path(args.output)
    else:
        out_path = report_dir / f"{Path(args.image).stem}.json"
    save_json(out_path, payload)

    print(f"Saved report payload to: {out_path}")
    print(payload["impression"])


if __name__ == "__main__":
    main()
