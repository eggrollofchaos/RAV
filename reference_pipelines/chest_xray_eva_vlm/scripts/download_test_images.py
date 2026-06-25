from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download a small Kaggle chest-pneumonia test sample for QA evaluation."
    )
    parser.add_argument("--num-samples", type=int, default=5)
    parser.add_argument("--output-dir", default="test_images")
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def download_test_data(num_samples: int, output_dir: str | Path, seed: int) -> None:
    from dotenv import load_dotenv
    from kaggle.api.kaggle_api_extended import KaggleApi

    load_dotenv()
    rng = random.Random(seed)
    dataset = "paultimothymooney/chest-xray-pneumonia"
    temp_dir = Path("temp_kaggle_chest_xray")
    dest_dir = Path(output_dir)

    temp_dir.mkdir(exist_ok=True)
    dest_dir.mkdir(exist_ok=True)

    api = KaggleApi()
    api.authenticate()
    api.dataset_download_files(dataset, path=temp_dir, unzip=True)

    test_root = temp_dir / "chest_xray" / "test"
    if not test_root.exists():
        test_root = temp_dir / "chest_xray" / "chest_xray" / "test"
    if not test_root.exists():
        raise FileNotFoundError(f"Could not find Kaggle test split under {temp_dir}")

    try:
        for category in ("NORMAL", "PNEUMONIA"):
            source_dir = test_root / category
            output_subdir = dest_dir / category.lower()
            output_subdir.mkdir(exist_ok=True)

            images = sorted(source_dir.glob("*.jpeg")) + sorted(
                source_dir.glob("*.jpg")
            )
            for image in rng.sample(images, min(num_samples, len(images))):
                shutil.copy(image, output_subdir / image.name)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def main() -> None:
    args = parse_args()
    download_test_data(args.num_samples, args.output_dir, args.seed)


if __name__ == "__main__":
    main()
