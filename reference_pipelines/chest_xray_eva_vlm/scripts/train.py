from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch
import torch.nn as nn
from torch import optim

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rav_reference.training import (
    Trainer,
    train_with_early_stopping,
    load_datasets,
    create_dataloaders,
    resume_from_checkpoint,
)
from rav_reference.metrics import evaluate_full
from rav_reference.models import create_model_for_training


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train the EVA-X chest X-ray classifier."
    )
    parser.add_argument(
        "--data-dir", required=True, help="Dataset root containing train/ val/ test/"
    )
    parser.add_argument(
        "--pretrained-weights", required=True, help="Path to EVA-X pretrained weights"
    )
    parser.add_argument(
        "--checkpoint-dir", required=True, help="Directory for the best checkpoint"
    )
    parser.add_argument("--resume-from", help="Optional checkpoint to resume from")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--patience", type=int, default=4)
    parser.add_argument("--min-delta", type=float, default=1e-3)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--pos-weight", type=float, default=0.70)
    parser.add_argument("--num-workers", type=int, default=4)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    train_dataset, val_dataset, test_dataset = load_datasets(args.data_dir)
    train_loader, val_loader, test_loader = create_dataloaders(
        train_dataset,
        val_dataset,
        test_dataset,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
    )

    best_val_loss = float("inf")
    start_epoch = 0

    if args.resume_from:
        model = create_model_for_training(args.pretrained_weights, device)
        optimizer, metadata = resume_from_checkpoint(
            model,
            args.resume_from,
            lr=args.lr,
            weight_decay=args.weight_decay,
        )
        best_val_loss = metadata["best_val_loss"]
        start_epoch = metadata["epoch"] + 1
    else:
        model = create_model_for_training(args.pretrained_weights, device)
        optimizer = optim.AdamW(
            model.parameters(), lr=args.lr, weight_decay=args.weight_decay
        )

    criterion = nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor([args.pos_weight], device=device)
    )
    trainer = Trainer(model, criterion, optimizer, device)

    checkpoint_path = Path(args.checkpoint_dir) / "eva_x_tiny_binary_best.pt"
    history = train_with_early_stopping(
        trainer,
        train_loader,
        val_loader,
        num_epochs=args.epochs,
        patience=args.patience,
        min_delta=args.min_delta,
        ckpt_path=str(checkpoint_path),
        class_to_idx=getattr(train_dataset, "class_to_idx", None),
        start_epoch=start_epoch,
        best_val_loss=best_val_loss,
    )

    print(
        f"Restored best model from epoch {history['best_epoch'] + 1} "
        f"(best_val_loss={history['best_val_loss']:.4f})"
    )
    print(f"Best checkpoint saved at: {checkpoint_path}")
    evaluate_full(trainer.model, test_loader, device, name="Test")


if __name__ == "__main__":
    main()
