#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/gcp_runner_common.sh"

load_rav_spot_env
apply_runner_defaults
check_required_spot_vars
check_runner_install
configure_gcloud_runtime

SYNC_INTERVAL_SEC_VALUE="${SYNC_INTERVAL_SEC:-180}"
DEFAULT_JOB_COMMAND="set -euo pipefail; bash scripts/gcp_train_with_checkpoint_sync.sh --config configs/poc/chest_pneumonia_binary.yaml --eval-split test --sync-interval-sec ${SYNC_INTERVAL_SEC_VALUE}"
JOB_COMMAND_VALUE="${JOB_COMMAND_POC:-$DEFAULT_JOB_COMMAND}"

echo "Submitting POC (Kaggle) run via spot runner..."
echo "Runner: ${RUNNER_DIR}"
echo "Image:  ${IMAGE}"
echo "Bucket: ${BUCKET}"
if [[ -n "${CLOUDSDK_PYTHON:-}" ]]; then
  echo "gcloud Python: ${CLOUDSDK_PYTHON}"
fi

run_submit_with_job "$JOB_COMMAND_VALUE" "$@"
