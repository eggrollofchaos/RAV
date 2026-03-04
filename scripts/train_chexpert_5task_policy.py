#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from PIL import Image, UnidentifiedImageError
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision import models, transforms
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rav_chest.metrics import compute_metrics, per_class_thresholds
from rav_chest.utils import ensure_dir, load_yaml, save_json, select_device, set_seed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train CheXpert 5-task mixed uncertainty policy model.")
    parser.add_argument(
        "--config",
        type=str,
        default="configs/primary/chest_chexpert_5task_policy.yaml",
        help="Path to YAML config file.",
    )
    parser.add_argument(
        "--resume-checkpoint",
        type=str,
        default="",
        help="Optional checkpoint to resume from (typically <output_dir>/checkpoints/last.pt).",
    )
    return parser.parse_args()


def build_transform(image_size: int, train: bool, augment: Dict[str, object] | None) -> transforms.Compose:
    ops: List[object] = [transforms.Resize((image_size, image_size))]
    augment = augment or {}
    if train and bool(augment.get("enabled", False)):
        hflip_prob = float(augment.get("hflip_prob", 0.5))
        rotation_degrees = float(augment.get("rotation_degrees", 7.0))
        translate = float(augment.get("translate", 0.02))
        scale_min = float(augment.get("scale_min", 0.95))
        scale_max = float(augment.get("scale_max", 1.05))
        brightness = float(augment.get("brightness", 0.05))
        contrast = float(augment.get("contrast", 0.05))

        if hflip_prob > 0.0:
            ops.append(transforms.RandomHorizontalFlip(p=max(0.0, min(1.0, hflip_prob))))
        if rotation_degrees > 0.0 or translate > 0.0 or scale_min != 1.0 or scale_max != 1.0:
            affine_translate = (translate, translate) if translate > 0.0 else None
            ops.append(
                transforms.RandomAffine(
                    degrees=rotation_degrees,
                    translate=affine_translate,
                    scale=(scale_min, scale_max),
                )
            )
        if brightness > 0.0 or contrast > 0.0:
            ops.append(transforms.ColorJitter(brightness=brightness, contrast=contrast))

    ops.extend(
        [
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )
    return transforms.Compose(ops)


class CheXpertRawDataset(Dataset):
    def __init__(
        self,
        csv_path: str | Path,
        image_root: str | Path,
        class_names: Sequence[str],
        path_column: str,
        image_size: int,
        train: bool,
        augment: Dict[str, object] | None,
    ) -> None:
        self.csv_path = Path(csv_path)
        self.image_root = Path(image_root)
        self.class_names = [str(x) for x in class_names]
        self.path_column = str(path_column)
        self.df = pd.read_csv(self.csv_path).reset_index(drop=True)

        required = [self.path_column, *self.class_names]
        missing = [c for c in required if c not in self.df.columns]
        if missing:
            raise ValueError(f"Missing columns in {self.csv_path}: {missing}")

        self.transform = build_transform(image_size=image_size, train=train, augment=augment)

    def __len__(self) -> int:
        return len(self.df)

    def _resolve_path(self, raw_path: str) -> Path:
        p = Path(raw_path)
        if p.is_absolute():
            return p
        return (self.image_root / p).resolve()

    def __getitem__(self, idx: int):
        row = self.df.iloc[idx]
        image_path = self._resolve_path(str(row[self.path_column]))
        try:
            image = Image.open(image_path).convert("RGB")
        except (UnidentifiedImageError, OSError) as exc:
            print(f"Skipping corrupt image {image_path}: {exc}")
            return None

        image_tensor = self.transform(image)
        labels: List[float] = []
        for name in self.class_names:
            value = pd.to_numeric(row[name], errors="coerce")
            labels.append(float(value) if not pd.isna(value) else float("nan"))
        raw_labels = torch.tensor(labels, dtype=torch.float32)
        return image_tensor, raw_labels, int(idx)


def skip_none_collate(batch):
    batch = [x for x in batch if x is not None]
    if not batch:
        return None
    return torch.utils.data.dataloader.default_collate(batch)


class CheXpertFiveTaskModel(nn.Module):
    def __init__(
        self,
        backbone: str,
        binary_labels: Sequence[str],
        multiclass_labels: Sequence[str],
        pretrained: bool,
        dropout: float,
    ) -> None:
        super().__init__()
        self.backbone_name = backbone.lower()
        self.binary_labels = [str(x) for x in binary_labels]
        self.multiclass_labels = [str(x) for x in multiclass_labels]

        feature_extractor, feature_dim = self._build_feature_extractor(
            backbone=self.backbone_name,
            pretrained=pretrained,
        )
        self.feature_extractor = feature_extractor
        self.dropout = nn.Dropout(p=float(dropout))

        self.binary_head = None
        if self.binary_labels:
            self.binary_head = nn.Linear(feature_dim, len(self.binary_labels))

        self.multiclass_heads = nn.ModuleDict(
            {name: nn.Linear(feature_dim, 3) for name in self.multiclass_labels}
        )

    @staticmethod
    def _build_feature_extractor(backbone: str, pretrained: bool) -> Tuple[nn.Module, int]:
        if backbone == "densenet121":
            weights = models.DenseNet121_Weights.DEFAULT if pretrained else None
            base = models.densenet121(weights=weights)
            in_features = int(base.classifier.in_features)
            base.classifier = nn.Identity()
            return base, in_features

        if backbone == "resnet50":
            weights = models.ResNet50_Weights.DEFAULT if pretrained else None
            base = models.resnet50(weights=weights)
            in_features = int(base.fc.in_features)
            base.fc = nn.Identity()
            return base, in_features

        if backbone == "efficientnet_b0":
            weights = models.EfficientNet_B0_Weights.DEFAULT if pretrained else None
            base = models.efficientnet_b0(weights=weights)
            in_features = int(base.classifier[1].in_features)
            base.classifier = nn.Identity()
            return base, in_features

        raise ValueError(
            f"Unsupported backbone '{backbone}'. Supported: densenet121, resnet50, efficientnet_b0"
        )

    def forward(self, x: torch.Tensor) -> Dict[str, object]:
        features = self.feature_extractor(x)
        features = self.dropout(features)

        out: Dict[str, object] = {}
        if self.binary_head is not None:
            out["binary"] = self.binary_head(features)
        out["multiclass"] = {name: head(features) for name, head in self.multiclass_heads.items()}
        return out


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
    f1 = macro.get("f1")

    if selection_metric == "auroc":
        return float(auroc) if auroc is not None else -1.0
    if selection_metric == "f1":
        return float(f1) if f1 is not None else -1.0

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


def parse_policy(cfg: Dict[str, object], class_names: Sequence[str]) -> Tuple[set[str], set[str], set[str]]:
    policy_cfg = cfg.get("labels", {}).get("policy", {})
    if not isinstance(policy_cfg, dict):
        policy_cfg = {}

    default_u_ones = {"Atelectasis", "Edema"}
    default_u_multiclass = {"Cardiomegaly", "Pleural Effusion"}
    default_u_selftrained = {"Consolidation"}

    u_ones = set(policy_cfg.get("u_ones", list(default_u_ones)))
    u_multiclass = set(policy_cfg.get("u_multiclass", list(default_u_multiclass)))
    u_selftrained = set(policy_cfg.get("u_selftrained", list(default_u_selftrained)))

    class_set = set(class_names)
    u_ones &= class_set
    u_multiclass &= class_set
    u_selftrained &= class_set

    overlap = (u_ones & u_multiclass) | (u_ones & u_selftrained) | (u_multiclass & u_selftrained)
    if overlap:
        raise ValueError(f"Policy label overlap detected: {sorted(overlap)}")

    return u_ones, u_multiclass, u_selftrained


def map_eval_labels(
    raw_labels: torch.Tensor,
    class_names: Sequence[str],
    u_ones: set[str],
) -> torch.Tensor:
    # Eval mapping for local split with uncertain labels:
    # - U-Ones labels map -1 -> 1
    # - Others map -1 -> 0
    mapped = torch.zeros_like(raw_labels)
    for i, name in enumerate(class_names):
        raw = raw_labels[:, i]
        val = torch.where(raw > 0, torch.ones_like(raw), torch.zeros_like(raw))
        if name in u_ones:
            val = torch.where(raw == -1, torch.ones_like(raw), val)
        else:
            val = torch.where(raw == -1, torch.zeros_like(raw), val)
        val = torch.where(torch.isnan(raw), torch.zeros_like(raw), val)
        mapped[:, i] = val
    return mapped


def class_probabilities(
    outputs: Dict[str, object],
    class_names: Sequence[str],
    binary_labels: Sequence[str],
    multiclass_labels: Sequence[str],
) -> torch.Tensor:
    batch_size = None
    if "binary" in outputs:
        batch_size = int(outputs["binary"].shape[0])
    else:
        for logits in outputs["multiclass"].values():
            batch_size = int(logits.shape[0])
            break
    assert batch_size is not None

    probs = torch.zeros((batch_size, len(class_names)), device=next(iter(outputs["multiclass"].values())).device if outputs["multiclass"] else outputs["binary"].device)

    binary_index = {name: i for i, name in enumerate(binary_labels)}

    for c_idx, name in enumerate(class_names):
        if name in multiclass_labels:
            logits = outputs["multiclass"][name]
            pair = logits[:, :2]
            prob_pos = torch.softmax(pair, dim=1)[:, 1]
            probs[:, c_idx] = prob_pos
        else:
            b_idx = binary_index[name]
            probs[:, c_idx] = torch.sigmoid(outputs["binary"][:, b_idx])

    return probs


def compute_batch_loss(
    outputs: Dict[str, object],
    raw_labels: torch.Tensor,
    indices: torch.Tensor,
    class_names: Sequence[str],
    binary_labels: Sequence[str],
    multiclass_labels: Sequence[str],
    u_ones: set[str],
    u_selftrained: set[str],
    stage: int,
    pseudo_labels: torch.Tensor | None,
    selftrained_pos: Dict[str, int],
) -> torch.Tensor:
    class_to_col = {name: i for i, name in enumerate(class_names)}
    binary_to_col = {name: class_to_col[name] for name in binary_labels}
    binary_to_head = {name: i for i, name in enumerate(binary_labels)}

    losses: List[torch.Tensor] = []

    # Binary losses (U-Ones / U-Zeros / U-SelfTrained)
    for name in binary_labels:
        head_idx = binary_to_head[name]
        col_idx = binary_to_col[name]
        logits = outputs["binary"][:, head_idx]
        raw = raw_labels[:, col_idx]

        if name in u_selftrained:
            if stage == 1:
                valid = (~torch.isnan(raw)) & (raw != -1)
                targets = torch.where(raw > 0, torch.ones_like(raw), torch.zeros_like(raw))
            else:
                if pseudo_labels is None:
                    valid = (~torch.isnan(raw)) & (raw != -1)
                    targets = torch.where(raw > 0, torch.ones_like(raw), torch.zeros_like(raw))
                else:
                    pseudo_col = selftrained_pos[name]
                    pseudo = pseudo_labels[indices, pseudo_col].to(raw.device)
                    targets_known = torch.where(raw > 0, torch.ones_like(raw), torch.zeros_like(raw))
                    targets = torch.where(raw == -1, pseudo, targets_known)
                    valid = ~torch.isnan(raw)
                    valid = valid & ~((raw == -1) & torch.isnan(pseudo))
        else:
            mapped = torch.where(raw > 0, torch.ones_like(raw), torch.zeros_like(raw))
            mapped = torch.where(raw == -1, torch.ones_like(raw) if name in u_ones else torch.zeros_like(raw), mapped)
            targets = mapped
            valid = ~torch.isnan(raw)

        if torch.any(valid):
            loss_vec = F.binary_cross_entropy_with_logits(logits, targets, reduction="none")
            losses.append(loss_vec[valid].mean())

    # Multiclass losses (U-MultiClass)
    for name in multiclass_labels:
        logits = outputs["multiclass"][name]
        raw = raw_labels[:, class_to_col[name]]
        targets = torch.full((raw.shape[0],), -100, dtype=torch.long, device=raw.device)

        targets = torch.where(raw == 0, torch.zeros_like(targets), targets)
        targets = torch.where(raw > 0, torch.ones_like(targets), targets)
        targets = torch.where(raw == -1, torch.full_like(targets, 2), targets)

        valid = targets != -100
        if torch.any(valid):
            losses.append(F.cross_entropy(logits[valid], targets[valid]))

    if not losses:
        return torch.tensor(0.0, device=raw_labels.device)
    return torch.stack(losses).mean()


def generate_pseudo_labels(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
    class_names: Sequence[str],
    binary_labels: Sequence[str],
    u_selftrained: set[str],
) -> torch.Tensor:
    if not u_selftrained:
        return torch.empty((len(loader.dataset), 0), dtype=torch.float32)

    selftrained_labels = [name for name in binary_labels if name in u_selftrained]
    self_pos = {name: i for i, name in enumerate(selftrained_labels)}
    binary_head = {name: i for i, name in enumerate(binary_labels)}

    pseudo = torch.full((len(loader.dataset), len(selftrained_labels)), float("nan"), dtype=torch.float32)

    model.eval()
    with torch.no_grad():
        for batch in loader:
            if batch is None:
                continue
            images, _, indices = batch
            images = images.to(device, non_blocking=True)
            outputs = model(images)
            for label in selftrained_labels:
                h = binary_head[label]
                p = torch.sigmoid(outputs["binary"][:, h]).detach().cpu()
                pseudo[indices, self_pos[label]] = p

    return pseudo


def evaluate(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
    class_names: Sequence[str],
    binary_labels: Sequence[str],
    multiclass_labels: Sequence[str],
    u_ones: set[str],
    u_selftrained: set[str],
    stage: int,
    pseudo_labels: torch.Tensor | None,
    selftrained_pos: Dict[str, int],
    thresholds: np.ndarray,
) -> Tuple[float, np.ndarray, np.ndarray, Dict[str, object]]:
    model.eval()
    losses: List[float] = []
    probs_all: List[np.ndarray] = []
    true_all: List[np.ndarray] = []

    with torch.no_grad():
        for batch in loader:
            if batch is None:
                continue
            images, raw_labels, indices = batch
            images = images.to(device, non_blocking=True)
            raw_labels = raw_labels.to(device, non_blocking=True)
            indices = indices.to(device, non_blocking=True)

            outputs = model(images)
            loss = compute_batch_loss(
                outputs=outputs,
                raw_labels=raw_labels,
                indices=indices,
                class_names=class_names,
                binary_labels=binary_labels,
                multiclass_labels=multiclass_labels,
                u_ones=u_ones,
                u_selftrained=u_selftrained,
                stage=stage,
                pseudo_labels=pseudo_labels,
                selftrained_pos=selftrained_pos,
            )
            losses.append(float(loss.item()))

            probs = class_probabilities(
                outputs=outputs,
                class_names=class_names,
                binary_labels=binary_labels,
                multiclass_labels=multiclass_labels,
            )
            true_mapped = map_eval_labels(raw_labels=raw_labels, class_names=class_names, u_ones=u_ones)
            probs_all.append(probs.detach().cpu().numpy())
            true_all.append(true_mapped.detach().cpu().numpy())

    mean_loss = float(np.mean(losses)) if losses else 0.0
    probs_np = np.concatenate(probs_all, axis=0)
    true_np = np.concatenate(true_all, axis=0)

    metrics = compute_metrics(
        y_true=true_np,
        y_prob=probs_np,
        class_names=class_names,
        thresholds=np.asarray(thresholds, dtype=np.float32),
    )
    return mean_loss, probs_np, true_np, metrics


def main() -> None:
    args = parse_args()
    cfg = load_yaml(args.config)

    seed = int(cfg["project"]["seed"])
    set_seed(seed)

    class_names = [str(x) for x in cfg["labels"]["columns"]]
    u_ones, u_multiclass, u_selftrained = parse_policy(cfg, class_names)

    binary_labels = [name for name in class_names if name not in u_multiclass]
    multiclass_labels = [name for name in class_names if name in u_multiclass]
    selftrained_labels = [name for name in binary_labels if name in u_selftrained]
    selftrained_pos = {name: i for i, name in enumerate(selftrained_labels)}

    output_dir = ensure_dir(Path(cfg["project"]["output_dir"]))
    ckpt_dir = ensure_dir(output_dir / "checkpoints")
    metrics_dir = ensure_dir(output_dir / "metrics")

    device = select_device(cfg["training"].get("device", "auto"))
    print(f"Using device: {device}")
    print(f"Policy: u_ones={sorted(u_ones)} u_multiclass={sorted(u_multiclass)} u_selftrained={sorted(u_selftrained)}")

    train_ds = CheXpertRawDataset(
        csv_path=cfg["data"]["train_csv"],
        image_root=cfg["data"]["image_root"],
        class_names=class_names,
        path_column=cfg["data"].get("path_column", "Path"),
        image_size=int(cfg["training"]["image_size"]),
        train=True,
        augment=cfg["training"].get("augment", {}),
    )
    # Non-augmented train loader for pseudo-label generation.
    train_eval_ds = CheXpertRawDataset(
        csv_path=cfg["data"]["train_csv"],
        image_root=cfg["data"]["image_root"],
        class_names=class_names,
        path_column=cfg["data"].get("path_column", "Path"),
        image_size=int(cfg["training"]["image_size"]),
        train=False,
        augment={"enabled": False},
    )
    val_ds = CheXpertRawDataset(
        csv_path=cfg["data"]["val_csv"],
        image_root=cfg["data"]["image_root"],
        class_names=class_names,
        path_column=cfg["data"].get("path_column", "Path"),
        image_size=int(cfg["training"]["image_size"]),
        train=False,
        augment={"enabled": False},
    )

    pin = bool(cfg["training"].get("pin_memory", True)) and device.type == "cuda"
    num_workers = int(cfg["training"].get("num_workers", 4))
    batch_size = int(cfg["training"].get("batch_size", 16))

    train_loader = DataLoader(
        train_ds,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=pin,
        collate_fn=skip_none_collate,
    )
    train_eval_loader = DataLoader(
        train_eval_ds,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=pin,
        collate_fn=skip_none_collate,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=pin,
        collate_fn=skip_none_collate,
    )

    model = CheXpertFiveTaskModel(
        backbone=str(cfg["training"]["backbone"]),
        binary_labels=binary_labels,
        multiclass_labels=multiclass_labels,
        pretrained=bool(cfg["training"].get("pretrained", True)),
        dropout=float(cfg["training"].get("dropout", 0.2)),
    ).to(device)

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(cfg["training"].get("lr", 1e-4)),
        weight_decay=float(cfg["training"].get("weight_decay", 1e-5)),
    )

    epochs_stage1 = int(cfg["training"].get("epochs_stage1", 3))
    epochs_stage2 = int(cfg["training"].get("epochs_stage2", 3))
    total_epochs = int(cfg["training"].get("epochs", epochs_stage1 + epochs_stage2))
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=total_epochs)

    amp_enabled = device.type == "cuda" and bool(cfg["training"].get("amp", True))
    scaler = torch.amp.GradScaler("cuda", enabled=amp_enabled)

    thresholds = per_class_thresholds(
        class_names=class_names,
        default_threshold=float(cfg["evaluation"].get("default_threshold", 0.5)),
        overrides=cfg["evaluation"].get("threshold_overrides", {}),
    )

    selection_metric = str(cfg["training"].get("selection_metric", "f1")).strip().lower()
    early_stopping_patience = int(cfg["training"].get("early_stopping_patience", 0))
    early_stopping_min_delta = float(cfg["training"].get("early_stopping_min_delta", 0.0))
    bad_epochs = 0

    best_score = -1.0
    start_epoch = 1
    history_mode = "w"
    elapsed_offset_seconds = 0.0
    pseudo_labels: torch.Tensor | None = None

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

        if "pseudo_labels" in state and state["pseudo_labels"] is not None:
            pseudo_labels = state["pseudo_labels"].float().cpu()

        best_ckpt_path = ckpt_dir / "best.pt"
        if best_ckpt_path.exists():
            best_state = torch.load(best_ckpt_path, map_location="cpu")
            best_score = max(
                best_score,
                score_from_metrics(best_state.get("val_metrics"), selection_metric=selection_metric),
            )

        print(
            f"Resuming from checkpoint: {resume_path} "
            f"(completed epoch {resumed_epoch}, next epoch {start_epoch})"
        )

    if start_epoch > total_epochs:
        print(
            f"Nothing to run: start_epoch={start_epoch} exceeds configured epochs={total_epochs}."
        )
        return

    run_start = time.time()
    history_path = metrics_dir / "history.jsonl"

    with history_path.open(history_mode, encoding="utf-8") as history_file:
        for epoch in range(start_epoch, total_epochs + 1):
            stage = 1 if epoch <= epochs_stage1 else 2

            # Build pseudo-labels once when entering stage 2.
            if stage == 2 and u_selftrained and pseudo_labels is None:
                print("Generating pseudo-labels for U-SelfTrained labels...")
                pseudo_labels = generate_pseudo_labels(
                    model=model,
                    loader=train_eval_loader,
                    device=device,
                    class_names=class_names,
                    binary_labels=binary_labels,
                    u_selftrained=u_selftrained,
                )

            epoch_start = time.time()
            model.train()
            train_losses: List[float] = []

            progress = tqdm(train_loader, desc=f"Epoch {epoch}/{total_epochs} [stage={stage}]", leave=False)
            for batch in progress:
                if batch is None:
                    continue
                images, raw_labels, indices = batch
                images = images.to(device, non_blocking=True)
                raw_labels = raw_labels.to(device, non_blocking=True)
                indices = indices.to(device, non_blocking=True)

                optimizer.zero_grad(set_to_none=True)

                with torch.amp.autocast("cuda", enabled=amp_enabled):
                    outputs = model(images)
                    loss = compute_batch_loss(
                        outputs=outputs,
                        raw_labels=raw_labels,
                        indices=indices,
                        class_names=class_names,
                        binary_labels=binary_labels,
                        multiclass_labels=multiclass_labels,
                        u_ones=u_ones,
                        u_selftrained=u_selftrained,
                        stage=stage,
                        pseudo_labels=pseudo_labels,
                        selftrained_pos=selftrained_pos,
                    )

                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()

                train_losses.append(float(loss.item()))
                progress.set_postfix(loss=f"{loss.item():.4f}")

            scheduler.step()

            train_loss = float(np.mean(train_losses)) if train_losses else 0.0
            val_loss, _, _, metric_payload = evaluate(
                model=model,
                loader=val_loader,
                device=device,
                class_names=class_names,
                binary_labels=binary_labels,
                multiclass_labels=multiclass_labels,
                u_ones=u_ones,
                u_selftrained=u_selftrained,
                stage=stage,
                pseudo_labels=pseudo_labels,
                selftrained_pos=selftrained_pos,
                thresholds=thresholds,
            )

            val_auroc = metric_payload["macro"]["auroc"]
            val_f1 = float(metric_payload["macro"]["f1"])
            score = score_from_metrics(
                metric_payload,
                val_loss=val_loss,
                selection_metric=selection_metric,
            )

            epoch_seconds = time.time() - epoch_start
            elapsed_seconds = elapsed_offset_seconds + (time.time() - run_start)
            avg_epoch_seconds = elapsed_seconds / float(epoch)
            eta_seconds = max(0.0, avg_epoch_seconds * float(total_epochs - epoch))

            row = {
                "epoch": epoch,
                "stage": stage,
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
                f"stage={stage} "
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
                "model_kind": "chexpert_5task_policy",
                "model_state": model.state_dict(),
                "optimizer_state": optimizer.state_dict(),
                "scheduler_state": scheduler.state_dict(),
                "class_names": class_names,
                "binary_labels": binary_labels,
                "multiclass_labels": multiclass_labels,
                "u_ones": sorted(u_ones),
                "u_multiclass": sorted(u_multiclass),
                "u_selftrained": sorted(u_selftrained),
                "thresholds": thresholds.tolist(),
                "config": cfg,
                "val_metrics": metric_payload,
                "pseudo_labels": pseudo_labels,
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
