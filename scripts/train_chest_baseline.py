#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rav_chest.data import CheXpertDataset, DEFAULT_LABELS, skip_none_collate
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
    parser.add_argument(
        "--resume-checkpoint",
        type=str,
        default="",
        help="Optional checkpoint to resume from (typically <output_dir>/checkpoints/last.pt).",
    )
    return parser.parse_args()


def make_loaders(
    cfg: Dict[str, object],
    class_names: List[str],
    device: torch.device,
) -> Tuple[DataLoader, DataLoader]:
    data_cfg = cfg["data"]
    train_cfg = cfg.get("training", {})
    label_cfg = cfg.get("labels", {})
    augment_cfg = train_cfg.get("augment", {})
    if not isinstance(augment_cfg, dict):
        augment_cfg = {}
    uncertain_overrides = label_cfg.get("uncertain_overrides", {})
    if not isinstance(uncertain_overrides, dict):
        uncertain_overrides = {}

    train_ds = CheXpertDataset(
        csv_path=data_cfg["train_csv"],
        image_root=data_cfg["image_root"],
        label_columns=class_names,
        path_column=data_cfg.get("path_column", "Path"),
        image_size=int(cfg["training"]["image_size"]),
        uncertain_value=float(cfg["labels"]["uncertain_value"]),
        uncertain_overrides=uncertain_overrides,
        train=True,
        augment=augment_cfg,
    )
    val_ds = CheXpertDataset(
        csv_path=data_cfg["val_csv"],
        image_root=data_cfg["image_root"],
        label_columns=class_names,
        path_column=data_cfg.get("path_column", "Path"),
        image_size=int(cfg["training"]["image_size"]),
        uncertain_value=float(cfg["labels"]["uncertain_value"]),
        uncertain_overrides=uncertain_overrides,
        train=False,
        augment={"enabled": False},
    )

    pin = bool(cfg["training"]["pin_memory"]) and device.type == "cuda"

    train_loader = DataLoader(
        train_ds,
        batch_size=int(cfg["training"]["batch_size"]),
        shuffle=True,
        num_workers=int(cfg["training"]["num_workers"]),
        pin_memory=pin,
        collate_fn=skip_none_collate,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=int(cfg["training"]["batch_size"]),
        shuffle=False,
        num_workers=int(cfg["training"]["num_workers"]),
        pin_memory=pin,
        collate_fn=skip_none_collate,
    )
    return train_loader, val_loader


def build_pos_weight_from_dataset(
    train_ds: CheXpertDataset,
    class_names: List[str],
    cap: float | None = None,
) -> torch.Tensor:
    weights: List[float] = []
    total = float(len(train_ds.df))
    for col in class_names:
        raw = pd.to_numeric(train_ds.df[col], errors="coerce").to_numpy(dtype=np.float32)
        mapped = np.where(
            np.isnan(raw),
            0.0,
            np.where(
                raw == -1.0,
                train_ds.uncertain_overrides.get(col, train_ds.uncertain_value),
                np.where(raw > 0.0, 1.0, 0.0),
            ),
        )
        pos = float(mapped.sum())
        neg = max(0.0, total - pos)

        # If positives (or negatives) are absent, keep neutral weighting.
        if pos <= 0.0 or neg <= 0.0:
            weight = 1.0
        else:
            weight = neg / pos

        if cap is not None:
            weight = min(weight, cap)
        weights.append(float(weight))
    return torch.tensor(weights, dtype=torch.float32)


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
        for batch in loader:
            if batch is None:
                continue
            images, labels, _ = batch
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


def score_from_metrics(
    metric_payload: Dict[str, object] | None,
    *,
    val_loss: float | None = None,
    selection_metric: str = "auto",
) -> float:
    selection_metric = str(selection_metric).strip().lower()
    if selection_metric == "val_loss":
        return -float(val_loss) if val_loss is not None else -1.0

    if not metric_payload:
        return -1.0

    macro = metric_payload.get("macro", {})
    if not isinstance(macro, dict):
        return -1.0

    auroc = macro.get("auroc")
    if selection_metric == "auroc":
        if auroc is None:
            return -1.0
        return float(auroc)

    f1 = macro.get("f1")
    if selection_metric == "f1":
        if f1 is None:
            return -1.0
        return float(f1)

    if auroc is not None:
        return float(auroc)

    if f1 is not None:
        return float(f1)
    return -1.0


def load_previous_elapsed_seconds(history_path: Path) -> float:
    if not history_path.exists():
        return 0.0

    last_line = ""
    with history_path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if line:
                last_line = line

    if not last_line:
        return 0.0

    try:
        row = json.loads(last_line)
    except json.JSONDecodeError:
        return 0.0
    if not isinstance(row, dict):
        return 0.0

    value = row.get("elapsed_seconds", 0.0)
    return float(value) if isinstance(value, (int, float)) else 0.0


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

    train_loader, val_loader = make_loaders(cfg, class_names, device)

    model = build_model(
        backbone=cfg["training"]["backbone"],
        num_classes=num_classes,
        pretrained=bool(cfg["training"]["pretrained"]),
        dropout=float(cfg["training"]["dropout"]),
    ).to(device)

    pos_weight = None
    if bool(cfg["training"].get("use_pos_weight", False)):
        cap_raw = cfg["training"].get("pos_weight_cap")
        cap = float(cap_raw) if cap_raw is not None else None
        if isinstance(train_loader.dataset, CheXpertDataset):
            pos_weight = build_pos_weight_from_dataset(
                train_loader.dataset,
                class_names,
                cap=cap,
            )
            print(
                "Using BCE pos_weight: "
                f"min={float(pos_weight.min()):.3f} "
                f"max={float(pos_weight.max()):.3f} "
                f"mean={float(pos_weight.mean()):.3f}"
            )
        else:
            print("WARN: use_pos_weight requested, but train dataset type is unexpected. Skipping.")
    criterion = nn.BCEWithLogitsLoss(
        pos_weight=pos_weight.to(device) if pos_weight is not None else None
    )
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
    scaler = torch.amp.GradScaler("cuda", enabled=amp_enabled)

    selection_metric = str(cfg["training"].get("selection_metric", "auto")).strip().lower()
    early_stopping_patience = int(cfg["training"].get("early_stopping_patience", 0))
    early_stopping_min_delta = float(cfg["training"].get("early_stopping_min_delta", 0.0))
    bad_epochs = 0

    thresholds = per_class_thresholds(
        class_names=class_names,
        default_threshold=float(cfg["evaluation"]["default_threshold"]),
        overrides=cfg["evaluation"].get("threshold_overrides", {}),
    )

    best_score = -1.0
    start_epoch = 1
    history_mode = "w"
    elapsed_offset_seconds = 0.0

    if args.resume_checkpoint:
        resume_path = Path(args.resume_checkpoint)
        if not resume_path.exists():
            raise FileNotFoundError(f"Resume checkpoint not found: {resume_path}")

        state = torch.load(resume_path, map_location=device)
        model.load_state_dict(state["model_state"])
        if "optimizer_state" in state:
            optimizer.load_state_dict(state["optimizer_state"])
        if "scheduler_state" in state:
            scheduler.load_state_dict(state["scheduler_state"])

        resumed_epoch = int(state.get("epoch", 0))
        start_epoch = resumed_epoch + 1
        history_mode = "a" if (metrics_dir / "history.jsonl").exists() else "w"
        elapsed_offset_seconds = load_previous_elapsed_seconds(metrics_dir / "history.jsonl")
        best_score = score_from_metrics(
            state.get("val_metrics"),
            selection_metric=selection_metric,
        )

        best_ckpt_path = ckpt_dir / "best.pt"
        if best_ckpt_path.exists():
            best_state = torch.load(best_ckpt_path, map_location="cpu")
            best_score = max(
                best_score,
                score_from_metrics(
                    best_state.get("val_metrics"),
                    selection_metric=selection_metric,
                ),
            )

        print(
            f"Resuming from checkpoint: {resume_path} "
            f"(completed epoch {resumed_epoch}, next epoch {start_epoch})"
        )

    epochs = int(cfg["training"]["epochs"])
    if start_epoch > epochs:
        print(
            f"Nothing to run: start_epoch={start_epoch} exceeds configured epochs={epochs}. "
            "Training already complete for this config."
        )
        return

    run_start = time.time()
    history_path = metrics_dir / "history.jsonl"
    with history_path.open(history_mode, encoding="utf-8") as history_file:
        for epoch in range(start_epoch, epochs + 1):
            epoch_start = time.time()
            model.train()
            train_losses: List[float] = []

            progress = tqdm(train_loader, desc=f"Epoch {epoch}/{epochs}", leave=False)
            for batch in progress:
                if batch is None:
                    continue
                images, labels, _ = batch
                images = images.to(device, non_blocking=True)
                labels = labels.to(device, non_blocking=True)

                optimizer.zero_grad(set_to_none=True)

                with torch.amp.autocast("cuda", enabled=amp_enabled):
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
            score = score_from_metrics(
                metric_payload,
                val_loss=val_loss,
                selection_metric=selection_metric,
            )

            epoch_seconds = time.time() - epoch_start
            elapsed_seconds = elapsed_offset_seconds + (time.time() - run_start)
            avg_epoch_seconds = elapsed_seconds / float(epoch)
            eta_seconds = max(0.0, avg_epoch_seconds * float(epochs - epoch))

            row = {
                "epoch": epoch,
                "train_loss": train_loss,
                "val_loss": val_loss,
                "val_macro_auroc": val_auroc if val_auroc is not None else -1.0,
                "val_macro_f1": val_f1,
                "selection_score": score,
                "lr": float(optimizer.param_groups[0]["lr"]),
                "epoch_seconds": epoch_seconds,
                "elapsed_seconds": elapsed_seconds,
                "eta_seconds": eta_seconds,
            }
            history_file.write(json.dumps(row) + "\n")
            history_file.flush()

            print(
                f"epoch={epoch} "
                f"train_loss={train_loss:.4f} "
                f"val_loss={val_loss:.4f} "
                f"val_macro_auroc={row['val_macro_auroc']:.4f} "
                f"val_macro_f1={val_f1:.4f} "
                f"{selection_metric}={score:.4f} "
                f"epoch_seconds={epoch_seconds:.1f} "
                f"eta_seconds={eta_seconds:.1f}"
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

            improved = score > (best_score + early_stopping_min_delta)
            if improved:
                best_score = score
                bad_epochs = 0
                torch.save(last_payload, ckpt_dir / "best.pt")
                save_json(metrics_dir / "best_val_metrics.json", metric_payload)
            else:
                bad_epochs += 1

            if early_stopping_patience > 0 and bad_epochs >= early_stopping_patience:
                print(
                    "Early stopping triggered: "
                    f"no {selection_metric} improvement for {bad_epochs} epochs "
                    f"(patience={early_stopping_patience}, min_delta={early_stopping_min_delta})."
                )
                break

    print(f"Training complete. Best score={best_score:.4f}.")


if __name__ == "__main__":
    main()
