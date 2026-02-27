#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rav_chest.data import CheXpertDataset
from rav_chest.metrics import (
    compute_confusion_matrices,
    compute_metrics,
    per_class_thresholds,
    sigmoid,
)
from rav_chest.models import build_model
from rav_chest.utils import ensure_dir, load_yaml, save_json, select_device


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate chest baseline classifier.")
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
        "--split",
        type=str,
        default="test",
        choices=["val", "test"],
        help="Which split CSV to evaluate.",
    )
    parser.add_argument(
        "--num-workers",
        type=int,
        default=-1,
        help="Override DataLoader workers. Use -1 to read from config.",
    )
    return parser.parse_args()


def run_eval(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
    criterion: nn.Module,
) -> tuple[float, np.ndarray, np.ndarray]:
    model.eval()
    losses: List[float] = []
    logits_all: List[np.ndarray] = []
    labels_all: List[np.ndarray] = []

    with torch.no_grad():
        for images, labels, _ in tqdm(loader, desc="Evaluating", leave=False):
            images = images.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)
            logits = model(images)
            loss = criterion(logits, labels)

            losses.append(float(loss.item()))
            logits_all.append(logits.detach().cpu().numpy())
            labels_all.append(labels.detach().cpu().numpy())

    mean_loss = float(np.mean(losses)) if losses else 0.0
    probs = sigmoid(np.concatenate(logits_all, axis=0))
    true = np.concatenate(labels_all, axis=0)
    return mean_loss, probs, true


def write_per_class_csv(path: Path, metrics: Dict[str, object]) -> None:
    per_class = metrics["per_class"]
    fields = [
        "class_name",
        "auroc",
        "f1",
        "brier",
        "threshold",
        "prevalence",
        "predicted_positive_rate",
    ]

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for class_name, row in per_class.items():
            out = dict(row)
            out["class_name"] = class_name
            writer.writerow(out)


def write_confusion_csv(path: Path, confusion: Dict[str, Dict[str, float | int]]) -> None:
    fields = [
        "class_name",
        "tp",
        "tn",
        "fp",
        "fn",
        "support_positive",
        "support_negative",
        "threshold",
        "sensitivity",
        "specificity",
        "precision",
        "npv",
        "accuracy",
    ]

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for class_name, row in confusion.items():
            out = dict(row)
            out["class_name"] = class_name
            writer.writerow(out)


def select_primary_class(class_names: List[str]) -> str:
    for name in class_names:
        if name.strip().lower() != "no finding":
            return name
    return class_names[0]


def main() -> None:
    args = parse_args()
    cfg = load_yaml(args.config)

    class_names = [str(x) for x in cfg["labels"]["columns"]]
    output_dir = Path(cfg["project"]["output_dir"])
    eval_dir = ensure_dir(output_dir / "metrics")
    ckpt_path = (
        Path(args.checkpoint)
        if args.checkpoint
        else output_dir / "checkpoints" / "best.pt"
    )
    if not ckpt_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {ckpt_path}")

    device = select_device(cfg["training"].get("device", "auto"))
    print(f"Using device: {device}")

    split_csv_key = "val_csv" if args.split == "val" else "test_csv"
    dataset = CheXpertDataset(
        csv_path=cfg["data"][split_csv_key],
        image_root=cfg["data"]["image_root"],
        label_columns=class_names,
        path_column=cfg["data"].get("path_column", "Path"),
        image_size=int(cfg["training"]["image_size"]),
        uncertain_value=float(cfg["labels"]["uncertain_value"]),
    )
    num_workers = (
        int(cfg["training"]["num_workers"])
        if int(args.num_workers) < 0
        else int(args.num_workers)
    )
    loader = DataLoader(
        dataset,
        batch_size=int(cfg["training"]["batch_size"]),
        shuffle=False,
        num_workers=num_workers,
        pin_memory=bool(cfg["training"]["pin_memory"]) and device.type == "cuda",
    )
    print(f"Using DataLoader num_workers={num_workers}")

    model = build_model(
        backbone=cfg["training"]["backbone"],
        num_classes=len(class_names),
        pretrained=False,
        dropout=float(cfg["training"]["dropout"]),
    ).to(device)

    state = torch.load(ckpt_path, map_location=device)
    model.load_state_dict(state["model_state"])

    thresholds = per_class_thresholds(
        class_names=class_names,
        default_threshold=float(cfg["evaluation"]["default_threshold"]),
        overrides=cfg["evaluation"].get("threshold_overrides", {}),
    )
    criterion = nn.BCEWithLogitsLoss()

    loss, probs, true = run_eval(model, loader, device, criterion)
    metrics = compute_metrics(
        y_true=true,
        y_prob=probs,
        class_names=class_names,
        thresholds=thresholds,
    )
    confusion = compute_confusion_matrices(
        y_true=true,
        y_prob=probs,
        class_names=class_names,
        thresholds=thresholds,
    )
    metrics["split"] = args.split
    metrics["loss"] = loss
    metrics["checkpoint"] = str(ckpt_path)
    metrics["confusion_matrices"] = confusion

    save_json(eval_dir / f"{args.split}_metrics.json", metrics)
    write_per_class_csv(eval_dir / f"{args.split}_per_class.csv", metrics)
    write_confusion_csv(eval_dir / f"{args.split}_confusion_per_class.csv", confusion)

    primary_class = select_primary_class(class_names)
    primary_conf = confusion[primary_class]
    print(
        f"{args.split} {primary_class} confusion: "
        f"TP={primary_conf['tp']} TN={primary_conf['tn']} "
        f"FP={primary_conf['fp']} FN={primary_conf['fn']}"
    )
    print(f"{args.split} loss={loss:.4f}, macro={metrics['macro']}")


if __name__ == "__main__":
    main()
