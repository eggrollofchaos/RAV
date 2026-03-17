#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/gcp_runner_common.sh"

set -euo pipefail

prepare_rav_runtime "required" "1" "1"

# Runtime is already prepared above; submit entrypoint helper handles submit-shell + submit call.
_rav_runtime_already_prepared() { :; }

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

spot_runner_wrapper_run_project_submit_entrypoint_required \
  "${RUNNER_HINT_MESSAGE:-Set RUNNER_DIR to your gcp-spot-runner checkout.}" \
  "prepare_submit_shell" \
  "_rav_runtime_already_prepared" \
  "run_submit_with_job" \
  "${JOB_COMMAND_VALUE}" \
  -- \
  "$@"
