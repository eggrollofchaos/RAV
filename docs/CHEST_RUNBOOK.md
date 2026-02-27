# Chest Runbook

This repo now has two tracks:
1. Primary: CheXpert (default, recommended).
2. POC: Kaggle chest-xray-pneumonia (first-iteration proof of concept).

Dataset status (2026-02-27):
1. Active local primary dataset: CheXpert-v1.0-small (Kaggle mirror): https://www.kaggle.com/datasets/ashery/chexpert
2. Full/regular CheXpert at scale: planned via GCP training workflow (WIP).
3. CheXpert Plus: deferred for current class timeline due storage/ops footprint (~3.5 TB planning estimate).

Current app version: `v0.2.4-agent-qa-chat`
Changelog: `CHANGELOG.md`

## 1) Setup

```bash
cd /Users/wax/Documents/Programming/RAV
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python -c "import torch; print(torch.__version__)"
```

For `make` targets, either activate `.venv` first or pass `PYTHON=.venv/bin/python`.

## 2) Primary Track (CheXpert)

### Expected raw data layout

```text
data/raw/chexpert/CheXpert-v1.0-small/
  train.csv
  valid.csv
  train/
  valid/
```

For full/regular CheXpert runs, use the equivalent `CheXpert-v1.0/` root on GCP.

### Step A: Prepare processed CSVs

```bash
python scripts/prepare_chexpert_data.py \
  --chexpert-root data/raw/chexpert/CheXpert-v1.0-small \
  --output-dir data/processed \
  --test-fraction-from-valid 0.5 \
  --seed 42
```

This creates:
1. `data/processed/chexpert_train.csv`
2. `data/processed/chexpert_val.csv`
3. `data/processed/chexpert_test.csv`

### Step B: Train

```bash
python scripts/train_chest_baseline.py \
  --config configs/primary/chest_chexpert.yaml
```

Checkpoints are saved every epoch:
1. `outputs/chest_baseline/checkpoints/last.pt` (latest epoch)
2. `outputs/chest_baseline/checkpoints/best.pt` (best validation score so far)

Resume a long run:

```bash
python scripts/train_chest_baseline.py \
  --config configs/primary/chest_chexpert.yaml \
  --resume-checkpoint outputs/chest_baseline/checkpoints/last.pt
```

### Step C: Evaluate

```bash
python scripts/eval_chest_baseline.py \
  --config configs/primary/chest_chexpert.yaml \
  --split test
```

### Step D: Single-image inference

```bash
python scripts/infer_chest_single.py \
  --config configs/primary/chest_chexpert.yaml \
  --image /absolute/path/to/chest_xray.jpg
```

### Step E: Simple Streamlit UI

```bash
python -m streamlit run app/streamlit_app.py
```

In the UI:
1. Pick config preset (CheXpert primary by default).
2. Leave checkpoint blank to use `<output_dir>/checkpoints/best.pt`.
3. Upload image and click "Analyze Image".
4. Optional: enable `Rewrite impression with OpenAI` for side-by-side deterministic vs LLM rewrite output.
5. Optional: open page `Ask Agent` and ask natural-language follow-up questions grounded on the latest inference payload.
6. Downloaded report JSON includes `llm_rewrite` metadata when rewrite is enabled.

### Step F: While training, do these in parallel

1. Confirm Streamlit and Torch are from `.venv` (avoid mixed Conda/venv imports).
2. Add an ETA monitor from `outputs/.../metrics/history.jsonl`.
3. Prepare the exact test-time eval command against `checkpoints/best.pt`.
4. Run data sanity checks: class balance, missing files, split leakage.
5. Queue next experiment configs (`image_size`, `batch_size`, `lr`, backbone).
6. Add one-command wrappers (for example, `make train-poc`, `make eval-poc`).

Commands:

```bash
python scripts/monitor_training_eta.py \
  --config configs/primary/chest_chexpert.yaml \
  --watch

python scripts/check_chest_data_sanity.py \
  --config configs/primary/chest_chexpert.yaml
```

## 3) POC Track (Kaggle chest-xray-pneumonia)

### Step A: Prepare/extract and build CSVs

```bash
python scripts/poc/prepare_chest_pneumonia_data.py \
  --data-root data/poc/chest_xray_pneumonia/raw \
  --output-dir data/poc/chest_xray_pneumonia/processed
```

If you still have zip archives, put them under
`data/poc/chest_xray_pneumonia/source_archives/` and run:

```bash
python scripts/poc/prepare_chest_pneumonia_data.py \
  --zip-dir data/poc/chest_xray_pneumonia/source_archives \
  --data-root data/poc/chest_xray_pneumonia/raw \
  --output-dir data/poc/chest_xray_pneumonia/processed
```

This creates:
1. `data/poc/chest_xray_pneumonia/processed/chest_pneumonia_train.csv`
2. `data/poc/chest_xray_pneumonia/processed/chest_pneumonia_val.csv`
3. `data/poc/chest_xray_pneumonia/processed/chest_pneumonia_test.csv`

### Step B: Train/eval with POC config

```bash
python scripts/train_chest_baseline.py \
  --config configs/poc/chest_pneumonia_binary.yaml

python scripts/eval_chest_baseline.py \
  --config configs/poc/chest_pneumonia_binary.yaml \
  --split test
```

Resume POC run:

```bash
python scripts/train_chest_baseline.py \
  --config configs/poc/chest_pneumonia_binary.yaml \
  --resume-checkpoint outputs/poc/chest_pneumonia_binary/checkpoints/last.pt
```

Optional POC UI:

```bash
python -m streamlit run app/streamlit_app.py
```
Then pick `POC (Kaggle Binary)` in the sidebar preset.

## 4) Output Locations

Primary (CheXpert):
1. `outputs/chest_baseline/checkpoints/`
2. `outputs/chest_baseline/metrics/`
3. `outputs/chest_baseline/reports/`

POC (Kaggle):
1. `outputs/poc/chest_pneumonia_binary/checkpoints/`
2. `outputs/poc/chest_pneumonia_binary/metrics/`
3. `outputs/poc/chest_pneumonia_binary/reports/`

## 5) Troubleshooting

If `import torch` fails with linker errors:
1. Confirm you are using `.venv`.
2. Reinstall dependencies in `.venv`.
3. Verify with:

```bash
python -c "import torch; print(torch.__version__)"
```

If `streamlit run ...` still loads `/opt/anaconda3/...`:
1. Use `python -m streamlit run app/streamlit_app.py`.
2. Confirm `which python` points to `/Users/wax/Documents/Programming/RAV/.venv/bin/python`.

If data file errors occur:
1. Re-run the appropriate prepare script.
2. Check config paths under `data.image_root` and `data.*_csv`.

## 6) MVP Minimum Required

1. `best.pt` exists and is loadable for inference.
2. Held-out metrics exist with AUROC/F1 in `outputs/.../metrics/`.
3. `scripts/infer_chest_single.py` returns valid findings on a sample image.
4. Streamlit UI runs from `.venv` and defaults to `best.pt`.
5. Findings/report text is grounded in predicted labels only.
6. Repro steps in this runbook and `README.md` are current and executable.

## 7) Convenience Make Targets

```bash
make train-primary
make eval-primary
make sanity-primary
make eta-primary-watch
make streamlit

make train-poc
make eval-poc
make sanity-poc
make eta-poc-watch
```

## 8) Optional OpenAI LLM Wrapper

Use this only as a post-processing layer (never to invent new findings).

```bash
# one-time: cp .env.example .env and set your real key in .env

# direct prompt mode
python scripts/llm_wrapper.py \
  --prompt "Rewrite this radiology impression in plain language."

# report rewrite mode from existing model payload JSON
python scripts/llm_wrapper.py \
  --report-json outputs/poc/chest_pneumonia_binary/reports/sample.json
```

Notes:
1. `OPENAI_API_KEY` is auto-loaded from `.env` by the wrapper/app when not already exported.
2. The same model rewrite path is available directly in Streamlit via the sidebar toggle.

## 9) Optional GCP Spot Runner Integration

This repo includes thin wrappers for the external `gcp-spot-runner` project.
Detailed guide: `gcp/GETTING_STARTED.md`

Setup:
```bash
cp gcp/rav_spot.env.example gcp/rav_spot.env
# edit gcp/rav_spot.env with PROJECT/REGION/SA/BUCKET/IMAGE/RUNNER_DIR
# optional: SYNC_INTERVAL_SEC controls periodic checkpoint sync cadence
```

Build image (required):
```bash
bash scripts/gcp_build_image.sh
```

Submit spot jobs:
```bash
bash scripts/gcp_submit_primary.sh
bash scripts/gcp_submit_poc.sh
```

Resume a previous run by reusing the same run ID:
```bash
bash scripts/gcp_submit_primary.sh --run-id rav-chexpert-001
bash scripts/gcp_submit_poc.sh --run-id rav-poc-001
```

Ops/status:
```bash
bash scripts/gcp_ops.sh status
bash scripts/gcp_ops.sh list
bash scripts/gcp_ops.sh events --since 24h
```

Notes:
1. Docker is required for this integration (cloud build + containerized VM execution).
2. Wrapper submit scripts force `--skip-build`; build/push image first.
3. Submit wrappers run `scripts/gcp_train_with_checkpoint_sync.sh` for both primary and POC.
4. During training, wrapper syncs `checkpoints/last.pt`, `checkpoints/best.pt`, and metrics to GCS every `SYNC_INTERVAL_SEC`.
5. On restart with the same `RUN_ID`, wrapper downloads `last.pt` and resumes via `--resume-checkpoint`.
6. Wrapper job commands copy relevant `outputs/...` into `/app/results/...` so runner upload picks them up.
