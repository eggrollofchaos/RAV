# Chest Runbook

This repo now has two tracks:
1. Primary: CheXpert (default, recommended).
2. POC: Kaggle chest-xray-pneumonia (first-iteration proof of concept).

## 1) Setup

```bash
cd /Users/wax/Documents/Programming/RAV
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python -c "import torch; print(torch.__version__)"
```

## 2) Primary Track (CheXpert)

### Expected raw data layout

```text
data/raw/chexpert/CheXpert-v1.0/
  train.csv
  valid.csv
  train/
  valid/
```

### Step A: Prepare processed CSVs

```bash
python scripts/prepare_chexpert_data.py \
  --chexpert-root data/raw/chexpert/CheXpert-v1.0 \
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

If data file errors occur:
1. Re-run the appropriate prepare script.
2. Check config paths under `data.image_root` and `data.*_csv`.
