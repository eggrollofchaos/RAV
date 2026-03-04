from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Sequence

import logging
import pandas as pd
import torch
from PIL import Image, UnidentifiedImageError
from torch.utils.data import Dataset
from torchvision import transforms

logger = logging.getLogger(__name__)


DEFAULT_LABELS: List[str] = [
    "Atelectasis",
    "Cardiomegaly",
    "Consolidation",
    "Edema",
    "Enlarged Cardiomediastinum",
    "Fracture",
    "Lung Lesion",
    "Lung Opacity",
    "No Finding",
    "Pleural Effusion",
    "Pleural Other",
    "Pneumonia",
    "Pneumothorax",
    "Support Devices",
]


def build_transform(
    image_size: int,
    train: bool = False,
    augment: Dict[str, Any] | None = None,
) -> transforms.Compose:
    ops: List[Any] = [transforms.Resize((image_size, image_size))]
    augment = augment or {}
    augment_enabled = bool(augment.get("enabled", False))

    if train and augment_enabled:
        hflip_prob = float(augment.get("hflip_prob", 0.5))
        rotation_degrees = float(augment.get("rotation_degrees", 7.0))
        translate = float(augment.get("translate", 0.02))
        scale_min = float(augment.get("scale_min", 0.95))
        scale_max = float(augment.get("scale_max", 1.05))
        brightness = float(augment.get("brightness", 0.05))
        contrast = float(augment.get("contrast", 0.05))

        if hflip_prob > 0.0:
            ops.append(
                transforms.RandomHorizontalFlip(
                    p=max(0.0, min(1.0, hflip_prob))
                )
            )

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
            ops.append(
                transforms.ColorJitter(
                    brightness=brightness,
                    contrast=contrast,
                )
            )

    ops.extend(
        [
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ]
    )
    return transforms.Compose(ops)


def skip_none_collate(batch):
    """Filter out None samples (corrupt images) and collate the rest."""
    batch = [item for item in batch if item is not None]
    if not batch:
        return None
    return torch.utils.data.dataloader.default_collate(batch)


class CheXpertDataset(Dataset):
    def __init__(
        self,
        csv_path: str | Path,
        image_root: str | Path,
        label_columns: Sequence[str],
        path_column: str = "Path",
        image_size: int = 320,
        uncertain_value: float = 1.0,
        uncertain_overrides: Dict[str, float] | None = None,
        train: bool = False,
        augment: Dict[str, Any] | None = None,
    ) -> None:
        self.csv_path = Path(csv_path)
        self.image_root = Path(image_root)
        self.path_column = path_column
        self.label_columns = list(label_columns)
        self.uncertain_value = float(uncertain_value)
        self.uncertain_overrides = {
            str(k): float(v) for k, v in (uncertain_overrides or {}).items()
        }
        self.transform = build_transform(
            image_size=image_size,
            train=train,
            augment=augment,
        )

        self.df = pd.read_csv(self.csv_path)
        required = [self.path_column, *self.label_columns]
        missing = [col for col in required if col not in self.df.columns]
        if missing:
            raise ValueError(
                f"Missing columns in {self.csv_path}: {missing}. "
                f"Expected at least: {required}."
            )
        self.df = self.df.reset_index(drop=True)

    def __len__(self) -> int:
        return len(self.df)

    def _resolve_path(self, raw_path: str) -> Path:
        p = Path(raw_path)
        if p.is_absolute():
            return p
        return (self.image_root / p).resolve()

    def _normalize_label(self, value: float, label_name: str) -> float:
        if pd.isna(value):
            return 0.0
        if float(value) == -1.0:
            return self.uncertain_overrides.get(label_name, self.uncertain_value)
        return 1.0 if float(value) > 0 else 0.0

    def __getitem__(self, idx: int):
        row = self.df.iloc[idx]
        image_path = self._resolve_path(str(row[self.path_column]))
        try:
            image = Image.open(image_path).convert("RGB")
        except (UnidentifiedImageError, OSError) as exc:
            logger.warning("Skipping corrupt image %s: %s", image_path, exc)
            return None
        image_tensor = self.transform(image)

        label_values = [self._normalize_label(row[col], col) for col in self.label_columns]
        labels = torch.tensor(label_values, dtype=torch.float32)
        return image_tensor, labels, str(image_path)
