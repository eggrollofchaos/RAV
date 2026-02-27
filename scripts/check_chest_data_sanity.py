#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Sequence, Set, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rav_chest.utils import ensure_dir, load_yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run data sanity checks for chest train/val/test CSV splits."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/poc/chest_pneumonia_binary.yaml",
        help="Path to training config YAML.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Optional output JSON path. Defaults to <output_dir>/metrics/data_sanity.json.",
    )
    parser.add_argument(
        "--skip-file-check",
        action="store_true",
        help="Skip checking whether each referenced image file exists.",
    )
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=20,
        help="Max number of sample paths to include for each issue.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero on warnings as well as errors.",
    )
    return parser.parse_args()


def _resolve_image_path(image_root: Path, raw_path: str) -> Path:
    p = Path(raw_path)
    if p.is_absolute():
        return p
    return (image_root / p).resolve()


def _split_summary(
    split_name: str,
    csv_path: Path,
    image_root: Path,
    path_column: str,
    label_columns: Sequence[str],
    skip_file_check: bool,
    sample_limit: int,
) -> Tuple[Dict[str, Any], Set[str], List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    summary: Dict[str, Any] = {
        "split": split_name,
        "csv_path": str(csv_path),
    }

    if not csv_path.exists():
        errors.append(f"{split_name}: missing CSV file {csv_path}")
        summary["row_count"] = 0
        summary["error"] = "missing_csv"
        return summary, set(), errors, warnings

    df = pd.read_csv(csv_path)
    summary["row_count"] = int(len(df))

    required_cols = [path_column, *label_columns]
    missing_cols = [col for col in required_cols if col not in df.columns]
    summary["missing_columns"] = missing_cols
    if missing_cols:
        errors.append(f"{split_name}: missing required columns {missing_cols}")
        return summary, set(), errors, warnings

    raw_paths = df[path_column]
    norm_paths = raw_paths.fillna("").astype(str).str.strip()
    empty_path_mask = raw_paths.isna() | norm_paths.eq("")
    non_empty_paths = norm_paths[~empty_path_mask]

    summary["empty_path_count"] = int(empty_path_mask.sum())
    if summary["empty_path_count"] > 0:
        errors.append(f"{split_name}: {summary['empty_path_count']} empty paths")

    dup_mask = non_empty_paths.duplicated(keep=False)
    duplicate_values = non_empty_paths[dup_mask]
    summary["duplicate_path_count"] = int(non_empty_paths.duplicated().sum())
    if summary["duplicate_path_count"] > 0:
        warnings.append(
            f"{split_name}: {summary['duplicate_path_count']} duplicated path rows within split"
        )
        summary["duplicate_path_samples"] = (
            duplicate_values.head(sample_limit).astype(str).tolist()
        )
    else:
        summary["duplicate_path_samples"] = []

    unique_paths = set(non_empty_paths.astype(str).tolist())
    summary["unique_path_count"] = len(unique_paths)

    if not skip_file_check:
        missing_files: List[str] = []
        for rel_path in sorted(unique_paths):
            if not _resolve_image_path(image_root, rel_path).exists():
                missing_files.append(rel_path)
                if len(missing_files) >= sample_limit:
                    break
        missing_total = 0
        if missing_files:
            # Full count in a second pass to keep sample list bounded.
            missing_total = sum(
                1
                for rel_path in unique_paths
                if not _resolve_image_path(image_root, rel_path).exists()
            )
            errors.append(f"{split_name}: {missing_total} image files missing on disk")
        summary["missing_file_count"] = int(missing_total)
        summary["missing_file_samples"] = missing_files
    else:
        summary["missing_file_count"] = None
        summary["missing_file_samples"] = []

    label_stats: Dict[str, Dict[str, Any]] = {}
    for label in label_columns:
        values = pd.to_numeric(df[label], errors="coerce")
        non_null = int(values.notna().sum())
        positive = int((values > 0).sum())
        zero = int((values == 0).sum())
        uncertain = int((values == -1).sum())
        positive_rate = (positive / non_null) if non_null else None
        label_stats[label] = {
            "non_null_count": non_null,
            "missing_count": int(values.isna().sum()),
            "positive_count": positive,
            "zero_count": zero,
            "uncertain_count": uncertain,
            "positive_rate": positive_rate,
        }
        if non_null == 0:
            warnings.append(f"{split_name}: label '{label}' has no numeric values")

    summary["label_stats"] = label_stats
    if int(summary["row_count"]) == 0:
        errors.append(f"{split_name}: split has zero rows")

    return summary, unique_paths, errors, warnings


def main() -> None:
    args = parse_args()
    cfg = load_yaml(args.config)

    output_dir = ensure_dir(Path(cfg["project"]["output_dir"]))
    out_path = (
        Path(args.output)
        if args.output
        else output_dir / "metrics" / "data_sanity.json"
    )
    ensure_dir(out_path.parent)

    image_root = Path(cfg["data"]["image_root"])
    path_column = str(cfg["data"].get("path_column", "Path"))
    label_columns = [str(x) for x in cfg["labels"]["columns"]]

    split_key_map = [("train", "train_csv"), ("val", "val_csv"), ("test", "test_csv")]
    split_summaries: Dict[str, Dict[str, Any]] = {}
    split_paths: Dict[str, Set[str]] = {}
    errors: List[str] = []
    warnings: List[str] = []

    for split_name, split_key in split_key_map:
        if split_key not in cfg["data"]:
            continue
        summary, unique_paths, split_errors, split_warnings = _split_summary(
            split_name=split_name,
            csv_path=Path(cfg["data"][split_key]),
            image_root=image_root,
            path_column=path_column,
            label_columns=label_columns,
            skip_file_check=bool(args.skip_file_check),
            sample_limit=max(1, int(args.sample_limit)),
        )
        split_summaries[split_name] = summary
        split_paths[split_name] = unique_paths
        errors.extend(split_errors)
        warnings.extend(split_warnings)

    overlap_summary: List[Dict[str, Any]] = []
    for left, right in combinations(split_paths.keys(), 2):
        overlap = split_paths[left].intersection(split_paths[right])
        overlap_count = len(overlap)
        payload = {
            "left_split": left,
            "right_split": right,
            "overlap_count": overlap_count,
            "overlap_samples": sorted(list(overlap))[: max(1, int(args.sample_limit))],
        }
        overlap_summary.append(payload)
        if overlap_count > 0:
            errors.append(
                f"{left}/{right}: {overlap_count} overlapping image paths between splits"
            )

    status = "pass"
    if errors:
        status = "fail"
    elif warnings:
        status = "warn"

    report: Dict[str, Any] = {
        "status": status,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": str(Path(args.config)),
        "image_root": str(image_root),
        "path_column": path_column,
        "labels": label_columns,
        "split_summaries": split_summaries,
        "cross_split_overlap": overlap_summary,
        "errors": errors,
        "warnings": warnings,
    }

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)

    print(f"Data sanity status: {status}")
    for split_name in ("train", "val", "test"):
        if split_name not in split_summaries:
            continue
        item = split_summaries[split_name]
        print(
            f"{split_name}: rows={item.get('row_count', 0)} "
            f"empty_paths={item.get('empty_path_count', 0)} "
            f"duplicates={item.get('duplicate_path_count', 0)} "
            f"missing_files={item.get('missing_file_count', 'skipped')}"
        )
    if errors:
        print("Errors:")
        for msg in errors:
            print(f"- {msg}")
    if warnings:
        print("Warnings:")
        for msg in warnings:
            print(f"- {msg}")
    print(f"Wrote report: {out_path}")

    if errors or (args.strict and warnings):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
