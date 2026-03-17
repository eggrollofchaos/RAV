#!/usr/bin/env bash
# Thin wrapper: delegate Cloud Reconciler deploy to shared gcp-spot-runner via RAV adapter helpers.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# shellcheck disable=SC1090
source "${REPO_ROOT}/scripts/gcp_runner_common.sh"

spot_runner_wrapper_run_project_reconciler_command_entrypoint_required \
  "${RUNNER_HINT_MESSAGE}" \
  "RAV_GCP_ENV" \
  "prepare_rav_runtime" \
  "run_project_command" \
  "optional" \
  "0" \
  "0" \
  -- \
  "$@"
