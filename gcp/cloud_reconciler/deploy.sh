#!/usr/bin/env bash
# Thin wrapper: delegate Cloud Reconciler deploy to shared gcp-spot-runner via RAV adapter helpers.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# shellcheck disable=SC1090
source "${REPO_ROOT}/scripts/gcp_runner_common.sh"

if [[ -n "${SPOT_CONFIG_PATH:-}" ]]; then
  RAV_GCP_ENV="${SPOT_CONFIG_PATH}"
fi

load_rav_spot_env_optional
apply_runner_defaults
check_runner_install

CONFIG_PATH="${RAV_GCP_ENV_PATH:-}"
DEFAULT_FUNCTION_NAME="rav-reconciler"
DEFAULT_SCHEDULER_NAME="rav-reconciler-trigger"

spot_runner_wrapper_run_project_reconciler_deploy_from_env_required \
  "${RUNNER_DIR}" \
  "${RUNNER_HINT_MESSAGE}" \
  "RUNNER_ADAPTER_LIB_LOADED" \
  "${CONFIG_PATH}" \
  "${RUNNER_PROFILE}" \
  "${DEFAULT_FUNCTION_NAME}" \
  "${DEFAULT_SCHEDULER_NAME}" \
  "$@"
