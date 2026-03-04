#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import sys
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

from rav_chest.metrics import compute_confusion_matrices, compute_metrics, per_class_thresholds
from rav_chest.utils import ensure_dir, load_yaml, save_json, select_device


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate CheXpert 5-task mixed uncertainty policy model.")
    parser.add_argument("--config", type=str, default="configs/primary/chest_chexpert_5task_policy.yaml")
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


def build_transform(image_size: int) -> transforms.Compose:
    return transforms.Compose(
        [
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )


class CheXpertRawDataset(Dataset):
    def __init__(
        self,
        csv_path: str | Path,
        image_root: str | Path,
        class_names: Sequence[str],
        path_column: str,
        image_size: int,
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

        self.transform = build_transform(image_size=image_size)

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


def map_eval_labels(raw_labels: torch.Tensor, class_names: Sequence[str], u_ones: set[str]) -> torch.Tensor:
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
    if "binary" in outputs:
        device = outputs["binary"].device
        batch_size = int(outputs["binary"].shape[0])
    else:
        logits0 = next(iter(outputs["multiclass"].values()))
        device = logits0.device
        batch_size = int(logits0.shape[0])

    probs = torch.zeros((batch_size, len(class_names)), device=device)
    binary_index = {name: i for i, name in enumerate(binary_labels)}

    for c_idx, name in enumerate(class_names):
        if name in multiclass_labels:
            logits = outputs["multiclass"][name]
            pair = logits[:, :2]
            probs[:, c_idx] = torch.softmax(pair, dim=1)[:, 1]
        else:
            b_idx = binary_index[name]
            probs[:, c_idx] = torch.sigmoid(outputs["binary"][:, b_idx])

    return probs


def eval_loss(
    outputs: Dict[str, object],
    raw_labels: torch.Tensor,
    class_names: Sequence[str],
    binary_labels: Sequence[str],
    multiclass_labels: Sequence[str],
    u_ones: set[str],
) -> torch.Tensor:
    class_to_col = {name: i for i, name in enumerate(class_names)}
    binary_to_head = {name: i for i, name in enumerate(binary_labels)}

    losses: List[torch.Tensor] = []

    for name in binary_labels:
        head_idx = binary_to_head[name]
        col_idx = class_to_col[name]
        logits = outputs["binary"][:, head_idx]
        raw = raw_labels[:, col_idx]
        targets = torch.where(raw > 0, torch.ones_like(raw), torch.zeros_like(raw))
        if name in u_ones:
            targets = torch.where(raw == -1, torch.ones_like(raw), targets)
        else:
            targets = torch.where(raw == -1, torch.zeros_like(raw), targets)
        valid = ~torch.isnan(raw)
        if torch.any(valid):
            loss_vec = F.binary_cross_entropy_with_logits(logits, targets, reduction="none")
            losses.append(loss_vec[valid].mean())

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


def run_eval(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
    class_names: Sequence[str],
    binary_labels: Sequence[str],
    multiclass_labels: Sequence[str],
    u_ones: set[str],
) -> tuple[float, np.ndarray, np.ndarray]:
    model.eval()
    losses: List[float] = []
    probs_all: List[np.ndarray] = []
    labels_all: List[np.ndarray] = []

    with torch.no_grad():
        for batch in tqdm(loader, desc="Evaluating", leave=False):
            if batch is None:
                continue
            images, raw_labels, _ = batch
            images = images.to(device, non_blocking=True)
            raw_labels = raw_labels.to(device, non_blocking=True)

            outputs = model(images)
            loss = eval_loss(
                outputs=outputs,
                raw_labels=raw_labels,
                class_names=class_names,
                binary_labels=binary_labels,
                multiclass_labels=multiclass_labels,
                u_ones=u_ones,
            )
            probs = class_probabilities(
                outputs=outputs,
                class_names=class_names,
                binary_labels=binary_labels,
                multiclass_labels=multiclass_labels,
            )
            mapped = map_eval_labels(raw_labels, class_names, u_ones)

            losses.append(float(loss.item()))
            probs_all.append(probs.detach().cpu().numpy())
            labels_all.append(mapped.detach().cpu().numpy())

    mean_loss = float(np.mean(losses)) if losses else 0.0
    probs_np = np.concatenate(probs_all, axis=0)
    true_np = np.concatenate(labels_all, axis=0)
    return mean_loss, probs_np, true_np


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
    u_ones, u_multiclass, _ = parse_policy(cfg, class_names)
    binary_labels = [name for name in class_names if name not in u_multiclass]
    multiclass_labels = [name for name in class_names if name in u_multiclass]

    output_dir = Path(cfg["project"]["output_dir"])
    eval_dir = ensure_dir(output_dir / "metrics")
    ckpt_path = Path(args.checkpoint) if args.checkpoint else output_dir / "checkpoints" / "best.pt"
    if not ckpt_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {ckpt_path}")

    device = select_device(cfg["training"].get("device", "auto"))
    print(f"Using device: {device}")

    split_csv_key = "val_csv" if args.split == "val" else "test_csv"
    dataset = CheXpertRawDataset(
        csv_path=cfg["data"][split_csv_key],
        image_root=cfg["data"]["image_root"],
        class_names=class_names,
        path_column=cfg["data"].get("path_column", "Path"),
        image_size=int(cfg["training"]["image_size"]),
    )

    num_workers = int(cfg["training"].get("num_workers", 4)) if int(args.num_workers) < 0 else int(args.num_workers)
    loader = DataLoader(
        dataset,
        batch_size=int(cfg["training"].get("batch_size", 16)),
        shuffle=False,
        num_workers=num_workers,
        pin_memory=bool(cfg["training"].get("pin_memory", True)) and device.type == "cuda",
        collate_fn=skip_none_collate,
    )
    print(f"Using DataLoader num_workers={num_workers}")

    model = CheXpertFiveTaskModel(
        backbone=str(cfg["training"]["backbone"]),
        binary_labels=binary_labels,
        multiclass_labels=multiclass_labels,
        pretrained=False,
        dropout=float(cfg["training"].get("dropout", 0.2)),
    ).to(device)

    state = torch.load(ckpt_path, map_location=device)
    model.load_state_dict(state["model_state"])

    thresholds = per_class_thresholds(
        class_names=class_names,
        default_threshold=float(cfg["evaluation"].get("default_threshold", 0.5)),
        overrides=cfg["evaluation"].get("threshold_overrides", {}),
    )

    loss, probs, true = run_eval(
        model=model,
        loader=loader,
        device=device,
        class_names=class_names,
        binary_labels=binary_labels,
        multiclass_labels=multiclass_labels,
        u_ones=u_ones,
    )

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
