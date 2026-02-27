# Chest Runbook

This repo now has two tracks:
1. Primary: CheXpert (default, recommended).
2. POC: Kaggle chest-xray-pneumonia (first-iteration proof of concept).

Dataset status (2026-02-27):
1. Active local primary dataset: CheXpert-v1.0-small (Kaggle mirror): https://www.kaggle.com/datasets/ashery/chexpert
2. Full/regular CheXpert at scale: planned via GCP training workflow (WIP).
3. CheXpert Plus: deferred for current class timeline due storage/ops footprint (~3.5 TB planning estimate).

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
