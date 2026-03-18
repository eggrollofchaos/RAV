#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/gcp_runner_common.sh"

set -euo pipefail

prepare_rav_submit_runtime_and_print_context "PRIMARY (CheXpert) run"

SYNC_INTERVAL_SEC_VALUE="${SYNC_INTERVAL_SEC:-180}"
DEFAULT_JOB_COMMAND="set -euo pipefail; bash scripts/gcp_train_with_checkpoint_sync.sh --config configs/primary/chest_chexpert.yaml --eval-split val --sync-interval-sec ${SYNC_INTERVAL_SEC_VALUE}"
JOB_COMMAND_VALUE="${JOB_COMMAND_PRIMARY:-$DEFAULT_JOB_COMMAND}"

if [[ "${JOB_COMMAND_VALUE}" == *"gcp_sync_chexpert_cache.sh"* ]]; then
  echo "WARN: JOB_COMMAND_PRIMARY includes gcp_sync_chexpert_cache.sh."
  echo "      rav profile pre_job_sync hook may already run dataset sync; this can duplicate sync time."
fi

run_submit_entrypoint_with_job "${JOB_COMMAND_VALUE}" "$@"
