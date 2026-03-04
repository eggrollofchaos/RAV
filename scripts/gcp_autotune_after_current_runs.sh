#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

RUN_A="${1:-rav-chexpert-u0-reg-20260304-011014}"
RUN_B="${2:-u1w1-0304-013919}"
TARGET_F1="${TARGET_F1:-0.42}"
MAX_RUNS="${MAX_RUNS:-4}"
CONFIGS="${CONFIGS:-configs/primary/chest_chexpert_5task_policy.yaml,configs/primary/chest_chexpert_umixed_regularized.yaml,configs/primary/chest_chexpert_umixed_regularized_posw.yaml,configs/primary/chest_chexpert_effb0_umixed_posw.yaml}"

is_terminal_phase() {
  local run_id="$1"
  local raw phase
  raw="$(gcloud storage cat "gs://rav-ai-train-artifacts-488706/runs/${run_id}/run_manifest.json" 2>/dev/null || true)"
  if [[ -z "$raw" ]]; then
    return 1
  fi
  phase="$(printf "%s" "$raw" | python3 -c 'import json,sys; print(str(json.load(sys.stdin).get("phase",""))).lower()' 2>/dev/null || true)"
  case "$phase" in
    complete|failed|partial|stopped) return 0 ;;
    *) return 1 ;;
  esac
}

wait_for_run() {
  local run_id="$1"
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] waiting for run ${run_id} to reach terminal phase"
  while true; do
    if is_terminal_phase "$run_id"; then
      echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] run ${run_id} reached terminal phase"
      break
    fi
    sleep 120
  done
}

wait_for_run "$RUN_A"
wait_for_run "$RUN_B"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] starting iteration queue"
bash scripts/gcp_iterate_chexpert.sh \
  --target-f1 "$TARGET_F1" \
  --max-runs "$MAX_RUNS" \
  --configs "$CONFIGS"
