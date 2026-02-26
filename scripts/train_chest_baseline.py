#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rav_chest.data import CheXpertDataset, DEFAULT_LABELS
from rav_chest.metrics import compute_metrics, per_class_thresholds, sigmoid
from rav_chest.models import build_model
from rav_chest.utils import ensure_dir, load_yaml, save_json, select_device, set_seed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train chest X-ray baseline classifier.")
    parser.add_argument(
        "--config",
        type=str,
        default="configs/primary/chest_chexpert.yaml",
        help="Path to YAML config file.",
    )
    return parser.parse_args()


def make_loaders(cfg: Dict[str, object], class_names: List[str]) -> Tuple[DataLoader, DataLoader]:
    data_cfg = cfg["data"]
    train_ds = CheXpertDataset(
        csv_path=data_cfg["train_csv"],
        image_root=data_cfg["image_root"],
        label_columns=class_names,
        path_column=data_cfg.get("path_column", "Path"),
        image_size=int(cfg["training"]["image_size"]),
        uncertain_value=float(cfg["labels"]["uncertain_value"]),
    )
    val_ds = CheXpertDataset(
        csv_path=data_cfg["val_csv"],
        image_root=data_cfg["image_root"],
        label_columns=class_names,
        path_column=data_cfg.get("path_column", "Path"),
        image_size=int(cfg["training"]["image_size"]),
        uncertain_value=float(cfg["labels"]["uncertain_value"]),
    )

    train_loader = DataLoader(
        train_ds,
        batch_size=int(cfg["training"]["batch_size"]),
        shuffle=True,
        num_workers=int(cfg["training"]["num_workers"]),
        pin_memory=bool(cfg["training"]["pin_memory"]),
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=int(cfg["training"]["batch_size"]),
        shuffle=False,
        num_workers=int(cfg["training"]["num_workers"]),
        pin_memory=bool(cfg["training"]["pin_memory"]),
    )
    return train_loader, val_loader


def eval_loop(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
    criterion: nn.Module,
) -> Tuple[float, np.ndarray, np.ndarray]:
    model.eval()
    losses: List[float] = []
    logits_all: List[np.ndarray] = []
    labels_all: List[np.ndarray] = []

    with torch.no_grad():
        for images, labels, _ in loader:
            images = images.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)
            logits = model(images)
            loss = criterion(logits, labels)
            losses.append(float(loss.item()))

            logits_all.append(logits.detach().cpu().numpy())
            labels_all.append(labels.detach().cpu().numpy())

    mean_loss = float(np.mean(losses)) if losses else 0.0
    logits_np = np.concatenate(logits_all, axis=0)
    labels_np = np.concatenate(labels_all, axis=0)
    probs_np = sigmoid(logits_np)
    return mean_loss, probs_np, labels_np


def main() -> None:
    args = parse_args()
    cfg = load_yaml(args.config)

    seed = int(cfg["project"]["seed"])
    set_seed(seed)

    class_names = cfg["labels"].get("columns", DEFAULT_LABELS)
    class_names = [str(name) for name in class_names]
    num_classes = len(class_names)

    output_dir = ensure_dir(Path(cfg["project"]["output_dir"]))
    ckpt_dir = ensure_dir(output_dir / "checkpoints")
    metrics_dir = ensure_dir(output_dir / "metrics")

    device = select_device(cfg["training"].get("device", "auto"))
    print(f"Using device: {device}")

    train_loader, val_loader = make_loaders(cfg, class_names)

    model = build_model(
        backbone=cfg["training"]["backbone"],
        num_classes=num_classes,
        pretrained=bool(cfg["training"]["pretrained"]),
        dropout=float(cfg["training"]["dropout"]),
    ).to(device)

    criterion = nn.BCEWithLogitsLoss()
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(cfg["training"]["lr"]),
        weight_decay=float(cfg["training"]["weight_decay"]),
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer,
        T_max=int(cfg["training"]["epochs"]),
    )

    amp_enabled = device.type == "cuda" and bool(cfg["training"].get("amp", True))
    scaler = torch.cuda.amp.GradScaler(enabled=amp_enabled)

    thresholds = per_class_thresholds(
        class_names=class_names,
        default_threshold=float(cfg["evaluation"]["default_threshold"]),
        overrides=cfg["evaluation"].get("threshold_overrides", {}),
    )

    best_score = -1.0
    history: List[Dict[str, float]] = []

    epochs = int(cfg["training"]["epochs"])
    for epoch in range(1, epochs + 1):
        model.train()
        train_losses: List[float] = []

        progress = tqdm(train_loader, desc=f"Epoch {epoch}/{epochs}", leave=False)
        for images, labels, _ in progress:
            images = images.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)

            optimizer.zero_grad(set_to_none=True)

            with torch.cuda.amp.autocast(enabled=amp_enabled):
                logits = model(images)
                loss = criterion(logits, labels)

            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()

            train_losses.append(float(loss.item()))
            progress.set_postfix(loss=f"{loss.item():.4f}")

        scheduler.step()

        train_loss = float(np.mean(train_losses)) if train_losses else 0.0
        val_loss, val_probs, val_true = eval_loop(model, val_loader, device, criterion)
        metric_payload = compute_metrics(
            y_true=val_true,
            y_prob=val_probs,
            class_names=class_names,
            thresholds=thresholds,
        )
        val_auroc = metric_payload["macro"]["auroc"]
        val_f1 = metric_payload["macro"]["f1"]
        score = val_auroc if val_auroc is not None else val_f1

        row = {
            "epoch": epoch,
            "train_loss": train_loss,
            "val_loss": val_loss,
            "val_macro_auroc": val_auroc if val_auroc is not None else -1.0,
            "val_macro_f1": val_f1,
            "lr": float(optimizer.param_groups[0]["lr"]),
        }
        history.append(row)

        print(
            f"epoch={epoch} "
            f"train_loss={train_loss:.4f} "
            f"val_loss={val_loss:.4f} "
            f"val_macro_auroc={row['val_macro_auroc']:.4f} "
            f"val_macro_f1={val_f1:.4f}"
        )

        last_payload = {
            "epoch": epoch,
            "model_state": model.state_dict(),
            "optimizer_state": optimizer.state_dict(),
            "scheduler_state": scheduler.state_dict(),
            "class_names": class_names,
            "thresholds": thresholds.tolist(),
            "config": cfg,
            "val_metrics": metric_payload,
        }
        torch.save(last_payload, ckpt_dir / "last.pt")

        if score > best_score:
            best_score = score
            torch.save(last_payload, ckpt_dir / "best.pt")
            save_json(metrics_dir / "best_val_metrics.json", metric_payload)

    with (metrics_dir / "history.jsonl").open("w", encoding="utf-8") as f:
        for row in history:
            f.write(json.dumps(row) + "\n")

    print(f"Training complete. Best score={best_score:.4f}.")


if __name__ == "__main__":
    main()
