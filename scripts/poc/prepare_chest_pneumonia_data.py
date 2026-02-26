#!/usr/bin/env python3
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path
from typing import Dict, List

import pandas as pd


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare Kaggle chest-xray-pneumonia splits for RAV baseline config."
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default="data/poc/chest_xray_pneumonia/raw",
        help="Directory expected to contain train/val/test after extraction.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/poc/chest_xray_pneumonia/processed",
        help="Directory where CSV files are written.",
    )
    parser.add_argument(
        "--zip-dir",
        type=str,
        default="",
        help="Optional directory containing train/val/test zip files to extract first.",
    )
    parser.add_argument(
        "--force-extract",
        action="store_true",
        help="Re-extract archives even if split folders already exist.",
    )
    return parser.parse_args()


def extract_archives(zip_dir: Path, data_root: Path, force_extract: bool) -> None:
    split_dirs_exist = all((data_root / split).exists() for split in ("train", "val", "test"))
    if split_dirs_exist and not force_extract:
        print("Split directories already exist; skipping extraction.")
        return

    archives = sorted(zip_dir.glob("*.zip"))
    if not archives:
        raise FileNotFoundError(f"No zip files found in: {zip_dir}")

    data_root.mkdir(parents=True, exist_ok=True)
    for archive in archives:
        print(f"Extracting: {archive}")
        with zipfile.ZipFile(archive, "r") as zf:
            zf.extractall(data_root)


def classify_label(class_dir_name: str) -> Dict[str, int]:
    name = class_dir_name.strip().upper()
    if name == "PNEUMONIA":
        return {"Pneumonia": 1, "No Finding": 0}
    if name == "NORMAL":
        return {"Pneumonia": 0, "No Finding": 1}
    raise ValueError(
        f"Unknown class folder '{class_dir_name}'. "
        "Expected folders named NORMAL and/or PNEUMONIA."
    )


def build_split_df(data_root: Path, split: str) -> pd.DataFrame:
    split_dir = data_root / split
    if not split_dir.exists():
        raise FileNotFoundError(f"Missing split directory: {split_dir}")

    rows: List[Dict[str, object]] = []
    for class_dir in sorted(split_dir.iterdir()):
        if not class_dir.is_dir() or class_dir.name.startswith("."):
            continue

        labels = classify_label(class_dir.name)
        for image_path in sorted(class_dir.rglob("*")):
            if not image_path.is_file():
                continue
            if image_path.name.startswith("."):
                continue
            if image_path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue

            rows.append(
                {
                    "Path": str(image_path.relative_to(data_root)),
                    "Pneumonia": labels["Pneumonia"],
                    "No Finding": labels["No Finding"],
                }
            )

    if not rows:
        raise ValueError(f"No image files found under: {split_dir}")

    df = pd.DataFrame(rows)
    return df.sort_values("Path").reset_index(drop=True)


def main() -> None:
    args = parse_args()
    data_root = Path(args.data_root)
    output_dir = Path(args.output_dir)

    if args.zip_dir:
        extract_archives(
            zip_dir=Path(args.zip_dir),
            data_root=data_root,
            force_extract=args.force_extract,
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    for split in ("train", "val", "test"):
        df = build_split_df(data_root=data_root, split=split)
        out_path = output_dir / f"chest_pneumonia_{split}.csv"
        df.to_csv(out_path, index=False)
        print(f"Wrote {split}: {len(df)} rows -> {out_path}")


if __name__ == "__main__":
    main()
