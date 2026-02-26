#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

import pandas as pd
from sklearn.model_selection import train_test_split


LABEL_COLUMNS: List[str] = [
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare CheXpert train/val/test CSVs for the RAV chest pipeline."
    )
    parser.add_argument(
        "--chexpert-root",
        type=str,
        default="data/raw/chexpert/CheXpert-v1.0",
        help="Directory containing CheXpert train.csv, valid.csv, and image folders.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/processed",
        help="Directory where processed CSVs are written.",
    )
    parser.add_argument(
        "--test-fraction-from-valid",
        type=float,
        default=0.5,
        help="Fraction of valid.csv assigned to test set (rest stays val).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for split reproducibility.",
    )
    return parser.parse_args()


def _normalize_path(path_value: str) -> str:
    # Official CSV paths are typically relative like "CheXpert-v1.0/train/...".
    # Strip whitespace and any leading './' for consistency.
    p = path_value.strip()
    if p.startswith("./"):
        p = p[2:]
    return p


def _clean_split(df: pd.DataFrame) -> pd.DataFrame:
    required = ["Path", *LABEL_COLUMNS]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"CheXpert CSV is missing required columns: {missing}")

    out = df[required].copy()
    out["Path"] = out["Path"].astype(str).map(_normalize_path)
    for col in LABEL_COLUMNS:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def main() -> None:
    args = parse_args()
    root = Path(args.chexpert_root)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    train_csv = root / "train.csv"
    valid_csv = root / "valid.csv"
    if not train_csv.exists() or not valid_csv.exists():
        raise FileNotFoundError(
            "Could not find CheXpert CSVs. Expected:\n"
            f"- {train_csv}\n"
            f"- {valid_csv}"
        )

    train_df = _clean_split(pd.read_csv(train_csv))
    valid_df = _clean_split(pd.read_csv(valid_csv))

    test_fraction = float(args.test_fraction_from_valid)
    if not (0.0 < test_fraction < 1.0):
        raise ValueError("--test-fraction-from-valid must be between 0 and 1.")

    strat = valid_df["No Finding"].fillna(0)
    if strat.nunique() < 2:
        strat = None

    val_df, test_df = train_test_split(
        valid_df,
        test_size=test_fraction,
        random_state=int(args.seed),
        shuffle=True,
        stratify=strat,
    )
    val_df = val_df.reset_index(drop=True)
    test_df = test_df.reset_index(drop=True)

    train_out = output_dir / "chexpert_train.csv"
    val_out = output_dir / "chexpert_val.csv"
    test_out = output_dir / "chexpert_test.csv"

    train_df.to_csv(train_out, index=False)
    val_df.to_csv(val_out, index=False)
    test_df.to_csv(test_out, index=False)

    print(f"Wrote train: {len(train_df)} rows -> {train_out}")
    print(f"Wrote val:   {len(val_df)} rows -> {val_out}")
    print(f"Wrote test:  {len(test_df)} rows -> {test_out}")


if __name__ == "__main__":
    main()

