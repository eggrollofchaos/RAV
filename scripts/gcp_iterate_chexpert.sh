#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/gcp_runner_common.sh"

# Prevent macOS idle sleep and survive terminal close.
spot_runner_maybe_reexec_caffeinate_compat "_SPOT_CAFFEINATED" "_RAV_ITER_CAFFEINATED,_IXQT_CAFFEINATED" "$@"
trap '' HUP

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/gcp_iterate_chexpert.sh [options]

Options:
  --target-f1 FLOAT           Stop once a run reaches this best val_macro_f1 (default: 0.42)
  --max-runs N                Maximum runs to submit (default: 6)
  --run-prefix STR            Run ID prefix (default: rav-chexpert-iter)
  --configs CSV               Comma-separated config list
  --summary PATH              Summary JSONL output path
  -h, --help                  Show help

Default config queue:
  configs/primary/chest_chexpert_5task_policy.yaml,
  configs/primary/chest_chexpert_u0_regularized.yaml,
  configs/primary/chest_chexpert_u1_regularized.yaml,
  configs/primary/chest_chexpert_umixed_regularized.yaml,
  configs/primary/chest_chexpert_umixed_regularized_posw.yaml,
  configs/primary/chest_chexpert_effb0_umixed_posw.yaml
EOF
}

TARGET_F1="0.42"
MAX_RUNS="6"
RUN_PREFIX="rav-chexpert-iter"
SUMMARY_PATH="outputs/chexpert_iteration/summary.jsonl"
CONFIG_CSV="configs/primary/chest_chexpert_5task_policy.yaml,configs/primary/chest_chexpert_u0_regularized.yaml,configs/primary/chest_chexpert_u1_regularized.yaml,configs/primary/chest_chexpert_umixed_regularized.yaml,configs/primary/chest_chexpert_umixed_regularized_posw.yaml,configs/primary/chest_chexpert_effb0_umixed_posw.yaml"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target-f1)
      TARGET_F1="$2"
      shift 2
      ;;
    --max-runs)
      MAX_RUNS="$2"
      shift 2
      ;;
    --run-prefix)
      RUN_PREFIX="$2"
      shift 2
      ;;
    --configs)
      CONFIG_CSV="$2"
      shift 2
      ;;
    --summary)
      SUMMARY_PATH="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if ! [[ "$MAX_RUNS" =~ ^[0-9]+$ ]] || [[ "$MAX_RUNS" -le 0 ]]; then
  echo "--max-runs must be a positive integer." >&2
  exit 2
fi

load_rav_spot_env
apply_runner_defaults
check_required_spot_vars
check_runner_install
configure_gcloud_runtime

mkdir -p "$(dirname "$SUMMARY_PATH")"

IFS=',' read -r -a CONFIGS <<< "$CONFIG_CSV"
if [[ "${#CONFIGS[@]}" -eq 0 ]]; then
  echo "No configs provided." >&2
  exit 2
fi

for cfg in "${CONFIGS[@]}"; do
  if [[ ! -f "${RAV_ROOT}/${cfg}" ]]; then
    echo "Config not found: ${RAV_ROOT}/${cfg}" >&2
    exit 2
  fi
done

get_best_f1() {
  local run_id="$1"
  local gcs_hist="gs://${BUCKET}/runs/${run_id}/checkpoint_sync/metrics/history.jsonl"
  gcloud storage cat "$gcs_hist" 2>/dev/null | python3 -c '
import json, math, sys
best = float("-inf")
seen = False
for raw in sys.stdin:
    raw = raw.strip()
    if not raw:
        continue
    try:
        row = json.loads(raw)
    except json.JSONDecodeError:
        continue
    v = row.get("val_macro_f1")
    if isinstance(v, (int, float)):
        if math.isnan(v):
            continue
        seen = True
        if float(v) > best:
            best = float(v)
if not seen:
    print("nan")
else:
    print(f"{best:.6f}")
'
}

run_count=0
for cfg in "${CONFIGS[@]}"; do
  run_count=$((run_count + 1))
  if [[ "$run_count" -gt "$MAX_RUNS" ]]; then
    echo "Reached --max-runs=${MAX_RUNS}. Stopping."
    break
  fi

  stamp="$(date +%Y%m%d-%H%M%S)"
  cfg_base="$(basename "$cfg" .yaml | tr '_' '-')"
  run_id="${RUN_PREFIX}-${cfg_base}-${stamp}"
  echo "=== Iteration ${run_count}/${MAX_RUNS} ==="
  echo "Config: ${cfg}"
  echo "Run ID: ${run_id}"

  set +e
  bash "${SCRIPT_DIR}/gcp_submit_chexpert_experiment.sh" --config "$cfg" --run-id "$run_id"
  submit_rc=$?
  set -e

  best_f1="$(get_best_f1 "$run_id")"
  now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  python3 - <<PY >> "$SUMMARY_PATH"
import json
print(json.dumps({
  'timestamp_utc': '$now_iso',
  'run_id': '$run_id',
  'config': '$cfg',
  'submit_exit_code': $submit_rc,
  'best_val_macro_f1': '$best_f1',
}))
PY

  echo "Submit exit code: ${submit_rc}"
  echo "Best val_macro_f1: ${best_f1}"

  if [[ "$best_f1" != "nan" ]]; then
    if python3 - <<PY
import sys
best=float('$best_f1')
target=float('$TARGET_F1')
raise SystemExit(0 if best >= target else 1)
PY
    then
      echo "Target reached: best_f1=${best_f1} >= target=${TARGET_F1}"
      echo "Summary: ${SUMMARY_PATH}"
      exit 0
    fi
  fi

done

echo "No run reached target_f1=${TARGET_F1}."
echo "Summary: ${SUMMARY_PATH}"
exit 1
