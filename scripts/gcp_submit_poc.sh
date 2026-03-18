#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/gcp_runner_common.sh"

set -euo pipefail

prepare_rav_submit_runtime_and_print_context "POC (Kaggle) run"

SYNC_INTERVAL_SEC_VALUE="${SYNC_INTERVAL_SEC:-180}"
DEFAULT_JOB_COMMAND="set -euo pipefail; bash scripts/gcp_train_with_checkpoint_sync.sh --config configs/poc/chest_pneumonia_binary.yaml --eval-split test --sync-interval-sec ${SYNC_INTERVAL_SEC_VALUE}"
JOB_COMMAND_VALUE="${JOB_COMMAND_POC:-$DEFAULT_JOB_COMMAND}"

run_submit_entrypoint_with_job "${JOB_COMMAND_VALUE}" "$@"
