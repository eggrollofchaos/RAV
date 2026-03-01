#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash scripts/gcp_train_with_checkpoint_sync.sh --config <yaml> [options]

Options:
  --config PATH                 Training config YAML (required)
  --eval-split SPLIT            Eval split after training (default: none)
  --sync-interval-sec N         Periodic GCS sync interval in seconds (default: 180)
  --gcs-prefix GS_URI           Override GCS prefix (default: gs://$GCS_BUCKET/runs/$RUN_ID/checkpoint_sync)
  --skip-eval                   Skip post-train eval
  -h, --help                    Show this help

Environment:
  GCS_BUCKET                    Required by spot runner
  RUN_ID                        Required by spot runner
EOF
}

CONFIG=""
EVAL_SPLIT=""
SYNC_INTERVAL_SEC=180
GCS_PREFIX=""
SKIP_EVAL=false
PYTHON_BIN="${PYTHON_BIN:-python3}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)
      CONFIG="$2"
      shift 2
      ;;
    --eval-split)
      EVAL_SPLIT="$2"
      shift 2
      ;;
    --sync-interval-sec)
      SYNC_INTERVAL_SEC="$2"
      shift 2
      ;;
    --gcs-prefix)
      GCS_PREFIX="$2"
      shift 2
      ;;
    --skip-eval)
      SKIP_EVAL=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$CONFIG" ]]; then
  echo "--config is required." >&2
  usage
  exit 1
fi

: "${GCS_BUCKET:?GCS_BUCKET is required}"
: "${RUN_ID:?RUN_ID is required}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python interpreter not found: ${PYTHON_BIN}" >&2
  exit 127
fi

if [[ -z "$GCS_PREFIX" ]]; then
  GCS_PREFIX="gs://${GCS_BUCKET}/runs/${RUN_ID}/checkpoint_sync"
fi

if ! [[ "$SYNC_INTERVAL_SEC" =~ ^[0-9]+$ ]] || [[ "$SYNC_INTERVAL_SEC" -le 0 ]]; then
  echo "--sync-interval-sec must be a positive integer." >&2
  exit 1
fi

OUTPUT_DIR="$("$PYTHON_BIN" -c 'import sys,yaml; cfg=yaml.safe_load(open(sys.argv[1])); print(cfg["project"]["output_dir"])' "$CONFIG")"
CHECKPOINT_DIR="${OUTPUT_DIR}/checkpoints"
METRICS_DIR="${OUTPUT_DIR}/metrics"
REPORTS_DIR="${OUTPUT_DIR}/reports"

GCS_CHECKPOINT_DIR="${GCS_PREFIX}/checkpoints"
GCS_METRICS_DIR="${GCS_PREFIX}/metrics"
GCS_REPORTS_DIR="${GCS_PREFIX}/reports"

mkdir -p "$CHECKPOINT_DIR" "$METRICS_DIR" "$REPORTS_DIR" /app/results

echo "[$(date -u)] Sync bootstrap"
echo "  RUN_ID=${RUN_ID}"
echo "  CONFIG=${CONFIG}"
echo "  OUTPUT_DIR=${OUTPUT_DIR}"
echo "  GCS_PREFIX=${GCS_PREFIX}"

sync_once() {
  local src dst

  for src in "${CHECKPOINT_DIR}/last.pt" "${CHECKPOINT_DIR}/best.pt"; do
    if [[ -f "$src" ]]; then
      dst="${GCS_CHECKPOINT_DIR}/$(basename "$src")"
      gcloud storage cp "$src" "$dst" >/dev/null 2>&1 || true
    fi
  done

  if [[ -f "${METRICS_DIR}/history.jsonl" ]]; then
    gcloud storage cp "${METRICS_DIR}/history.jsonl" "${GCS_METRICS_DIR}/history.jsonl" >/dev/null 2>&1 || true
  fi

  for src in "${METRICS_DIR}"/*_metrics.json "${METRICS_DIR}"/*_per_class.csv "${METRICS_DIR}"/*_confusion_per_class.csv; do
    if [[ -f "$src" ]]; then
      dst="${GCS_METRICS_DIR}/$(basename "$src")"
      gcloud storage cp "$src" "$dst" >/dev/null 2>&1 || true
    fi
  done
}

bootstrap_resume_checkpoint() {
  local remote_last="${GCS_CHECKPOINT_DIR}/last.pt"
  local local_last="${CHECKPOINT_DIR}/last.pt"
  if gcloud storage ls "$remote_last" >/dev/null 2>&1; then
    echo "[$(date -u)] Found remote checkpoint; downloading ${remote_last}"
    gcloud storage cp "$remote_last" "$local_last" >/dev/null 2>&1 || true
    if [[ -f "$local_last" ]]; then
      echo "$local_last"
      return 0
    fi
  fi
  echo ""
}

SYNC_STOP=0
sync_loop() {
  while [[ "$SYNC_STOP" -eq 0 ]]; do
    sleep "$SYNC_INTERVAL_SEC"
    sync_once
  done
}

trap_cleanup() {
  SYNC_STOP=1
  if [[ -n "${SYNC_PID:-}" ]]; then
    kill "$SYNC_PID" >/dev/null 2>&1 || true
  fi
  sync_once
}
trap trap_cleanup EXIT INT TERM

RESUME_CKPT="$(bootstrap_resume_checkpoint)"

echo "[$(date -u)] Starting periodic sync loop (${SYNC_INTERVAL_SEC}s)"
sync_loop &
SYNC_PID=$!

TRAIN_CMD=("$PYTHON_BIN" scripts/train_chest_baseline.py --config "$CONFIG")
if [[ -n "$RESUME_CKPT" ]]; then
  echo "[$(date -u)] Resuming from ${RESUME_CKPT}"
  TRAIN_CMD+=(--resume-checkpoint "$RESUME_CKPT")
fi

echo "[$(date -u)] Running training command:"
printf '  %q ' "${TRAIN_CMD[@]}"
echo
"${TRAIN_CMD[@]}"

if [[ "$SKIP_EVAL" != true ]] && [[ -n "$EVAL_SPLIT" ]]; then
  echo "[$(date -u)] Running eval on split=${EVAL_SPLIT}"
  "$PYTHON_BIN" scripts/eval_chest_baseline.py --config "$CONFIG" --split "$EVAL_SPLIT" || true
fi

sync_once

RESULTS_COPY_TARGET="/app/results/${OUTPUT_DIR}"
mkdir -p "$(dirname "$RESULTS_COPY_TARGET")"
rm -rf "$RESULTS_COPY_TARGET"
cp -R "$OUTPUT_DIR" "$RESULTS_COPY_TARGET"

echo "[$(date -u)] Finished train+sync wrapper."
