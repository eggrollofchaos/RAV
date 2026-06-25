from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import torch
from torch import nn, optim
from torch.utils.data import DataLoader
from torchvision import datasets, transforms

from .pipeline import build_inference_transform

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def get_train_transforms() -> transforms.Compose:
    return transforms.Compose(
        [
            transforms.Resize(256),
            transforms.RandomCrop(224),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.ToTensor(),
            transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ]
    )


def load_datasets(data_dir: str):
    root = Path(data_dir)
    train_dir = root / "train"
    val_dir = root / "val"
    test_dir = root / "test"
    for split_dir in (train_dir, val_dir, test_dir):
        if not split_dir.exists():
            raise FileNotFoundError(f"Missing dataset split directory: {split_dir}")

    train_dataset = datasets.ImageFolder(
        root=str(train_dir), transform=get_train_transforms()
    )
    val_dataset = datasets.ImageFolder(
        root=str(val_dir), transform=build_inference_transform()
    )
    test_dataset = datasets.ImageFolder(
        root=str(test_dir), transform=build_inference_transform()
    )
    return train_dataset, val_dataset, test_dataset


def create_dataloaders(
    train_ds,
    val_ds,
    test_ds,
    batch_size: int = 32,
    num_workers: int = 4,
):
    train_loader = DataLoader(
        train_ds, batch_size=batch_size, shuffle=True, num_workers=num_workers
    )
    val_loader = DataLoader(
        val_ds, batch_size=batch_size, shuffle=False, num_workers=num_workers
    )
    test_loader = DataLoader(
        test_ds, batch_size=batch_size, shuffle=False, num_workers=num_workers
    )
    return train_loader, val_loader, test_loader


class Trainer:
    def __init__(self, model, criterion, optimizer, device: str | torch.device):
        self.model = model
        self.criterion = criterion
        self.optimizer = optimizer
        self.device = device
        self.use_amp = torch.cuda.is_available()
        self.amp_device = "cuda" if self.use_amp else "cpu"
        self.scaler = torch.amp.GradScaler(self.amp_device, enabled=self.use_amp)

    def train_epoch(self, loader) -> float:
        self.model.train()
        running_loss = 0.0

        for image, label in loader:
            image = image.to(self.device, non_blocking=True)
            label = label.to(self.device, non_blocking=True).unsqueeze(1).float()

            self.optimizer.zero_grad(set_to_none=True)

            with torch.amp.autocast(self.amp_device, enabled=self.use_amp):
                logits = self.model(image)
                loss = self.criterion(logits, label)

            self.scaler.scale(loss).backward()
            self.scaler.step(self.optimizer)
            self.scaler.update()

            running_loss += loss.detach().float().item()

        avg_loss = running_loss / len(loader)
        print(f"Training loss: {avg_loss:.4f}")
        return avg_loss

    def validate_epoch(self, loader) -> float:
        self.model.eval()
        total = 0
        correct = 0
        running_loss = 0.0

        with torch.no_grad():
            for image, label in loader:
                image = image.to(self.device)
                label = label.to(self.device).unsqueeze(1).float()

                logits = self.model(image)
                loss = self.criterion(logits, label)
                pred = (torch.sigmoid(logits) > 0.5).float()

                total += label.size(0)
                correct += (pred == label).sum().item()
                running_loss += loss.item()

        avg_loss = running_loss / len(loader)
        accuracy = 100 * correct / total
        print(f"Validation loss: {avg_loss:.4f}")
        print(f"Validation acc: {accuracy:.2f}%")
        return avg_loss

    def test(
        self, test_dataset, test_loader, save_csv_path: str | None = None
    ) -> pd.DataFrame:
        self.model.eval()
        predictions = {
            "image_path": [],
            "y_pred": [],
            "confidence": [],
            "label": [],
        }

        with torch.no_grad():
            count = 0
            for image, label in test_loader:
                batch_size = len(label)
                image = image.to(self.device)
                logits = self.model(image)

                y_prob = torch.sigmoid(logits)
                y_pred = (y_prob > 0.5).int()

                predictions["y_pred"].extend(y_pred.cpu().numpy().flatten().tolist())
                predictions["confidence"].extend(
                    y_prob.cpu().numpy().flatten().tolist()
                )
                predictions["label"].extend(label.cpu().numpy().tolist())

                paths = test_dataset.samples[count : count + batch_size]
                predictions["image_path"].extend([path[0] for path in paths])
                count += batch_size

        frame = pd.DataFrame(predictions)
        if save_csv_path:
            output_path = Path(save_csv_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            frame.to_csv(output_path, index=False)
        return frame


def train_with_early_stopping(
    trainer: Trainer,
    train_loader,
    val_loader,
    num_epochs: int,
    patience: int,
    min_delta: float,
    ckpt_path: str,
    class_to_idx,
    start_epoch: int = 0,
    best_val_loss: float = float("inf"),
) -> dict[str, Any]:
    ckpt_path_obj = Path(ckpt_path)
    ckpt_path_obj.parent.mkdir(parents=True, exist_ok=True)

    epochs_no_improve = 0
    best_epoch = start_epoch - 1
    best_state = {
        "model": {
            key: value.detach().cpu()
            for key, value in trainer.model.state_dict().items()
        },
        "optimizer": trainer.optimizer.state_dict(),
        "epoch": best_epoch,
        "best_val_loss": best_val_loss,
    }
    history = {
        "train_loss": [],
        "val_loss": [],
        "best_epoch": best_epoch,
        "best_val_loss": best_val_loss,
    }

    for epoch in range(start_epoch, num_epochs):
        print(f"\nEpoch {epoch + 1}")
        train_loss = trainer.train_epoch(train_loader)
        val_loss = trainer.validate_epoch(val_loader)

        history["train_loss"].append(train_loss)
        history["val_loss"].append(val_loss)

        if val_loss < best_val_loss - min_delta:
            best_val_loss = val_loss
            best_epoch = epoch
            epochs_no_improve = 0
            best_state = {
                "model": {
                    key: value.detach().cpu()
                    for key, value in trainer.model.state_dict().items()
                },
                "optimizer": trainer.optimizer.state_dict(),
                "epoch": epoch,
                "best_val_loss": best_val_loss,
            }
            torch.save(
                {
                    "epoch": epoch,
                    "best_val_loss": best_val_loss,
                    "model_state_dict": trainer.model.state_dict(),
                    "optimizer_state_dict": trainer.optimizer.state_dict(),
                    "class_to_idx": class_to_idx,
                },
                ckpt_path_obj,
            )
            print(f"New best model at epoch {epoch + 1} | saved to: {ckpt_path_obj}")
        else:
            epochs_no_improve += 1
            print(f"No improvement ({epochs_no_improve}/{patience})")

        if epochs_no_improve >= patience:
            print("Early stopping triggered")
            break

    trainer.model.load_state_dict(best_state["model"])
    trainer.model.to(trainer.device)
    trainer.model.eval()

    history["best_epoch"] = best_state["epoch"]
    history["best_val_loss"] = best_state["best_val_loss"]
    return history


def resume_from_checkpoint(
    model: nn.Module,
    ckpt_path: str,
    lr: float = 1e-4,
    weight_decay: float = 1e-4,
) -> tuple[optim.Optimizer, dict[str, Any]]:
    """Restore model + optimizer from a training checkpoint.

    Returns ``(optimizer, metadata)`` where ``metadata["epoch"]`` is the **raw**
    epoch stored in the checkpoint (0-indexed).  The caller is responsible for
    computing ``start_epoch = metadata["epoch"] + 1``.
    """
    checkpoint = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
    metadata = {
        "epoch": checkpoint["epoch"],
        "best_val_loss": checkpoint["best_val_loss"],
        "class_to_idx": checkpoint.get("class_to_idx"),
    }
    return optimizer, metadata
