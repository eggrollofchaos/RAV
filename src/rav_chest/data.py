from __future__ import annotations

from pathlib import Path
from typing import List, Sequence

import pandas as pd
import torch
from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms


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


def build_transform(image_size: int) -> transforms.Compose:
    return transforms.Compose(
        [
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ]
    )


class CheXpertDataset(Dataset):
    def __init__(
        self,
        csv_path: str | Path,
        image_root: str | Path,
        label_columns: Sequence[str],
        path_column: str = "Path",
        image_size: int = 320,
        uncertain_value: float = 1.0,
    ) -> None:
        self.csv_path = Path(csv_path)
        self.image_root = Path(image_root)
        self.path_column = path_column
        self.label_columns = list(label_columns)
        self.uncertain_value = float(uncertain_value)
        self.transform = build_transform(image_size)

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

    def _normalize_label(self, value: float) -> float:
        if pd.isna(value):
            return 0.0
        if float(value) == -1.0:
            return self.uncertain_value
        return 1.0 if float(value) > 0 else 0.0

    def __getitem__(self, idx: int):
        row = self.df.iloc[idx]
        image_path = self._resolve_path(str(row[self.path_column]))
        image = Image.open(image_path).convert("RGB")
        image_tensor = self.transform(image)

        label_values = [self._normalize_label(row[col]) for col in self.label_columns]
        labels = torch.tensor(label_values, dtype=torch.float32)
        return image_tensor, labels, str(image_path)

