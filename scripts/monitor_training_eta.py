#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rav_chest.utils import load_yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Estimate training ETA from metrics history.jsonl."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/poc/chest_pneumonia_binary.yaml",
        help="Config used by the training run.",
    )
    parser.add_argument(
        "--history-path",
        type=str,
        default="",
        help="Optional history path. Defaults to <output_dir>/metrics/history.jsonl.",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Continuously watch history file and print updates.",
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=15.0,
        help="Polling interval in watch mode.",
    )
    return parser.parse_args()


def _format_seconds(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    hours, remainder = divmod(seconds, 3600)
    minutes, sec = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m {sec}s"
    if minutes:
        return f"{minutes}m {sec}s"
    return f"{sec}s"


def _load_rows(path: Path) -> List[Dict[str, float]]:
    rows: List[Dict[str, float]] = []
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                # Ignore a partial line while training is actively writing.
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _summarize(rows: List[Dict[str, float]], total_epochs: int) -> Dict[str, object]:
    rows = sorted(rows, key=lambda row: int(row.get("epoch", 0)))
    last = rows[-1]
    completed = int(last.get("epoch", 0))

    epoch_seconds_values = [
        float(row["epoch_seconds"])
        for row in rows
        if isinstance(row.get("epoch_seconds"), (int, float)) and float(row["epoch_seconds"]) > 0
    ]
    avg_epoch_seconds = (
        sum(epoch_seconds_values) / len(epoch_seconds_values)
        if epoch_seconds_values
        else 0.0
    )

    elapsed_seconds = 0.0
    if isinstance(last.get("elapsed_seconds"), (int, float)):
        elapsed_seconds = float(last["elapsed_seconds"])
    elif epoch_seconds_values:
        elapsed_seconds = sum(epoch_seconds_values)

    remaining_epochs = max(0, total_epochs - completed)
    eta_seconds = avg_epoch_seconds * float(remaining_epochs)
    eta_at = datetime.now() + timedelta(seconds=eta_seconds)

    return {
        "completed": completed,
        "total_epochs": total_epochs,
        "remaining_epochs": remaining_epochs,
        "avg_epoch_seconds": avg_epoch_seconds,
        "elapsed_seconds": elapsed_seconds,
        "eta_seconds": eta_seconds,
        "eta_at": eta_at,
        "last": last,
    }


def _print_summary(summary: Dict[str, object], history_path: Path) -> None:
    last = summary["last"]
    print(f"history: {history_path}")
    print(
        "progress: "
        f"{summary['completed']}/{summary['total_epochs']} epochs "
        f"(remaining {summary['remaining_epochs']})"
    )
    print(
        f"timing: elapsed={_format_seconds(float(summary['elapsed_seconds']))} "
        f"avg_epoch={_format_seconds(float(summary['avg_epoch_seconds']))} "
        f"eta={_format_seconds(float(summary['eta_seconds']))}"
    )
    print(f"eta_at: {summary['eta_at'].strftime('%Y-%m-%d %H:%M:%S')}")
    print(
        "last: "
        f"train_loss={float(last.get('train_loss', 0.0)):.4f} "
        f"val_loss={float(last.get('val_loss', 0.0)):.4f} "
        f"val_macro_auroc={float(last.get('val_macro_auroc', -1.0)):.4f} "
        f"val_macro_f1={float(last.get('val_macro_f1', 0.0)):.4f}"
    )


def main() -> None:
    args = parse_args()
    cfg = load_yaml(args.config)
    total_epochs = int(cfg["training"]["epochs"])
    history_path = (
        Path(args.history_path)
        if args.history_path
        else Path(cfg["project"]["output_dir"]) / "metrics" / "history.jsonl"
    )

    if not args.watch:
        if not history_path.exists():
            raise FileNotFoundError(f"History file not found: {history_path}")
        rows = _load_rows(history_path)
        if not rows:
            raise RuntimeError(
                f"History file exists but has no readable rows yet: {history_path}"
            )
        _print_summary(_summarize(rows, total_epochs), history_path)
        return

    last_reported_epoch = -1
    printed_waiting = False
    interval = max(1.0, float(args.interval_seconds))
    while True:
        if not history_path.exists():
            if not printed_waiting:
                print(f"Waiting for history file: {history_path}")
                printed_waiting = True
            time.sleep(interval)
            continue

        rows = _load_rows(history_path)
        if not rows:
            if not printed_waiting:
                print(f"Waiting for first epoch row in: {history_path}")
                printed_waiting = True
            time.sleep(interval)
            continue

        printed_waiting = False
        summary = _summarize(rows, total_epochs)
        completed = int(summary["completed"])
        if completed != last_reported_epoch:
            _print_summary(summary, history_path)
            print("")
            last_reported_epoch = completed

        if completed >= total_epochs:
            print("Training appears complete.")
            break
        time.sleep(interval)


if __name__ == "__main__":
    main()
