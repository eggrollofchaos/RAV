---
title: RAV CheXpert Operations Learnings
slug: rav-chexpert-ops
type: learning
status: live
created: 2026-05-29
updated: 2026-06-04
owner: Alex Xin
scope: project
project: rav
tags: [chexpert, chexpert-small, gcp, local-storage, training, evaluation, thresholding]
canonical: false
sources:
  - docs/retrospectives/2026-05-29_chexpert-gcp-dataset-ops.md
  - docs/retrospectives/2026-05-29_chexpert-training-stability.md
  - docs/retrospectives/2026-05-29_chexpert-model-evaluation-thresholding.md
  - docs/retrospectives/2026-06-04_sean-workstation-rav-local-gpu.md
  - docs/retrospectives/2026-06-04_rav-gcp-runner-operations-addendum.md
  - docs/retrospectives/2026-06-04_chexpert-local-data-prep.md
related: []
---

# RAV CheXpert Operations Learnings

## Thresholds Before Backbones

When a CheXpert model shows reasonable AUROC but weak F1 or class collapse, tune per-class thresholds on validation before switching architectures. The current 5-task DenseNet121 run had useful ranking signal, but the default operating point overcalled Atelectasis in the tiny local test split.

## Small Splits Are Smoke Tests

The local CheXpert test split is useful for verifying that checkpoints, transforms, label mapping, and metrics run end to end. It is too small for diagnostic or model-selection claims. Larger held-out evaluation should happen before treating any metric as stable.

## Remote Training Depends On Operational Details

For GCP spot training on COS, persistent disk paths and dataset sync behavior are part of model reliability. Use `DATA_DISK_MOUNT_PATH="/var/lib/spot-data"` for writable persistent storage, keep checkpoint sync enabled, and use controlled run IDs so interrupted spot work can resume cleanly.

## Local GPU Is A Smoke/Iteration Lane First

Sean's workstation gives RAV a usable CUDA lane for quick train/eval smoke runs and lower-cost iteration, but it does not automatically replace GCP or make model-quality metrics stronger. Keep access/setup details in the global workstation reference, and use RAV-local docs to record workload-specific constraints: incomplete local data snapshots, disk headroom, and whether a run is a smoke test or a benchmark-quality evaluation.

## Local Prep Should Be Seconds For CheXpert-Small

For the local CheXpert-small mirror, `scripts/prepare_chexpert_data.py` should read `train.csv` and `valid.csv`, split the validation rows, and write processed CSVs in seconds. If it appears to run for minutes, check that the command is using `--chexpert-root data/raw/chexpert/CheXpert-v1.0-small`, that the process is actually running in this repo, and that it is not pointed at a full or partially downloaded dataset tree.

## Name CheXpert Variants Before Downloading

CheXpert-small, full CheXpert, and CheXpert Plus have very different storage profiles. Use CheXpert-small for local development, keep full CheXpert on GCP or external storage, and keep CheXpert Plus deferred unless the project explicitly budgets for a multi-terabyte footprint.

## Split Operational And Model Retrospectives

CheXpert sessions can span infrastructure, runtime stability, and model quality. Keep those closeouts separate because each initiative has different evidence, risks, and next actions. Infrastructure can be closeable while threshold tuning remains a tracked follow-up.

## Next-Run Checklist

- Tune thresholds on `val`, save the threshold JSON, then evaluate `test` with that frozen file.
- If tuned thresholds still fail, run `configs/primary/chest_chexpert_umixed_regularized_posw.yaml` before changing backbone.
- Treat current local test metrics as smoke-test evidence only.
- Use Sean's workstation for CUDA smoke/iteration only after checking data completeness, disk headroom, and workstation-use etiquette for longer jobs.

## Three Freshness Gates Before Expensive GCP Runs

Before submitting long CheXpert runs, check these separately:

- **Image freshness:** rebuild when `configs/`, `scripts/`, `src/`, or runtime entrypoint files changed.
- **Data freshness:** verify GCS dataset object counts, sizes, and sample reads.
- **Accelerator freshness:** confirm the VM/container sees the requested GPU before treating slow progress as model behavior.

These gates prevent stale-image `FileNotFoundError`, partial dataset surprises, and silent CPU fallback from looking like training instability.

## `RUN_ID` Controls Resume Semantics

Use the same `RUN_ID` when continuing the same experiment so checkpoint sync can restore `last.pt`. Use a new `RUN_ID` only for a distinct experiment or a deliberately fresh run.
