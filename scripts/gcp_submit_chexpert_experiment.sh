#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/gcp_runner_common.sh"

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/gcp_submit_chexpert_experiment.sh --config <yaml> [runner submit args]

Examples:
  bash scripts/gcp_submit_chexpert_experiment.sh \
    --config configs/primary/chest_chexpert_u0_regularized.yaml

  bash scripts/gcp_submit_chexpert_experiment.sh \
    --config configs/primary/chest_chexpert_u1_regularized.yaml \
    --run-id rav-chexpert-u1-20260304-120000
EOF
}

CONFIG_PATH=""
FORWARD_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)
      CONFIG_PATH="${2:-}"
      shift 2
      ;;
    --config=*)
      CONFIG_PATH="${1#*=}"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      FORWARD_ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ -z "$CONFIG_PATH" ]]; then
  echo "--config is required." >&2
  usage >&2
  exit 2
fi

if [[ ! -f "${RAV_ROOT}/${CONFIG_PATH}" ]]; then
  echo "Config not found: ${RAV_ROOT}/${CONFIG_PATH}" >&2
  exit 2
fi

prepare_rav_submit_runtime_and_print_context "CheXpert experiment" "${CONFIG_PATH}"

SYNC_INTERVAL_SEC_VALUE="${SYNC_INTERVAL_SEC:-180}"
JOB_COMMAND_VALUE="set -euo pipefail; \
  bash scripts/gcp_sync_chexpert_cache.sh --raw-uri gs://${BUCKET}/datasets/chexpert/raw --processed-uri gs://${BUCKET}/datasets/chexpert/processed --cache-root data; \
  bash scripts/gcp_train_with_checkpoint_sync.sh --config ${CONFIG_PATH} --eval-split val --sync-interval-sec ${SYNC_INTERVAL_SEC_VALUE}"

run_submit_entrypoint_with_job "${JOB_COMMAND_VALUE}" "${FORWARD_ARGS[@]}"
