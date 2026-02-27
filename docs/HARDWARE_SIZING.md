# Hardware Sizing (Chest-First)

This table is for the chest baseline (`densenet121`, 320x320 input, batch training with mixed precision where supported).

All numbers are planning estimates, not guarantees.

## 1) Training Profiles

| Profile | Example Hardware | Effective VRAM | Recommended Batch Size | Estimated Train Throughput (img/s) | Estimated Epoch Time (220k images) | Notes |
|---|---|---:|---:|---:|---:|---|
| Local dev | MacBook Pro M3 Pro (MPS) | Shared memory | 8-16 | 20-40 | 1.5-3.0 hours | Best for debugging and smoke runs |
| Budget cloud | NVIDIA T4 | 16 GB | 16-24 | 45-75 | 50-80 minutes | Good starter cloud profile |
| Balanced cloud | NVIDIA L4 | 24 GB | 24-40 | 90-140 | 25-40 minutes | Strong cost/perf for class projects |
| Faster cloud | NVIDIA A10G | 24 GB | 24-48 | 110-170 | 22-33 minutes | Reliable choice for repeated experiments |
| High-end | NVIDIA A100 | 40 GB+ | 64-128 | 220-350 | 10-17 minutes | Best for rapid hyperparameter sweeps |

## 2) Inference Profiles

| Profile | Typical Single-Image Latency | Notes |
|---|---:|---|
| CPU laptop | 150-450 ms | Works for Kaggle proof-of-concept, but slower batch workloads |
| M3 Pro (MPS) | 40-140 ms | Good local interactive experience |
| T4/L4 GPU | 15-60 ms | Suitable for multi-class prediction with moderate concurrency |
| A10G/A100 | 8-35 ms | Suitable for load testing and larger batch runs |

## 3) Localization Extension Sizing (VinDr Path)

For detection/localization (RetinaNet-style), budget ~1.8-2.5x the compute of classification baseline.

| Hardware | Suggested Batch Size @ 512 | Practical Guidance |
|---|---:|---|
| M3 Pro | 2-4 | Use small experiments only |
| T4 16 GB | 4-8 | Lower resolution if OOM |
| L4 / A10G 24 GB | 8-16 | Preferred for weekly iteration |
| A100 40 GB | 16-32 | Best for faster ablations |

## 4) Storage and I/O

Recommended minimums:
1. Raw data + processed cache: 200-400 GB.
2. Checkpoints + metrics + artifacts: 20-100 GB.
3. High-speed local SSD or equivalent attached volume.

Current dataset planning note:
1. Local development currently uses CheXpert-v1.0-small (Kaggle mirror) plus Kaggle POC data.
2. Full/regular CheXpert training is intended for GCP (WIP) due runtime and storage pressure.
3. CheXpert Plus is deferred for this class timeline (planning estimate: ~3.5 TB footprint).

## 5) Practical Recommendation for This Project

1. Development and smoke tests: run on M3 Pro.
2. Main training/evaluation: L4 or A10G profile.
3. Final ablations and deadline-week reruns: A10G+ or A100 if available.

## 6) OOM and Speed Tuning Checklist

If out-of-memory:
1. Reduce `batch_size`.
2. Reduce `image_size` from 320 to 256.
3. Disable heavy augmentations first.
4. Use gradient accumulation if needed.

If too slow:
1. Increase `num_workers`.
2. Validate data caching/storage throughput.
3. Profile dataloader and GPU utilization before changing model architecture.
