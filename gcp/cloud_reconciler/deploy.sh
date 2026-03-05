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
_require_runner_adapter_lib
if declare -F spot_runner_require_install >/dev/null 2>&1; then
  if ! spot_runner_require_install "${RUNNER_DIR}" "Set RUNNER_DIR in gcp/rav_spot.env to your gcp-spot-runner checkout." "spotctl/__main__.py" "adapters/spot_runner_common.sh"; then
    exit 1
  fi
elif declare -F spot_runner_check_install >/dev/null 2>&1; then
  if ! spot_runner_check_install "${RUNNER_DIR}" "spotctl/__main__.py" "adapters/spot_runner_common.sh"; then
    echo "Set RUNNER_DIR in gcp/rav_spot.env to your gcp-spot-runner checkout." >&2
    exit 1
  fi
else
  echo "Runner helper missing required install validation function." >&2
  echo "Set RUNNER_DIR in gcp/rav_spot.env to your gcp-spot-runner checkout." >&2
  exit 1
fi

CONFIG_PATH="${RAV_GCP_ENV_PATH:-}"

: "${FUNCTION_NAME:=rav-reconciler}"
: "${SCHEDULER_NAME:=rav-reconciler-trigger}"
if declare -F spot_runner_wrapper_run_reconciler_deploy_compat >/dev/null 2>&1; then
  spot_runner_wrapper_run_reconciler_deploy_compat \
    "${RUNNER_DIR}" \
    "${CONFIG_PATH}" \
    "rav" \
    "${FUNCTION_NAME}" \
    "${SCHEDULER_NAME}" \
    "$@"
  exit "$?"
fi

if declare -F spot_runner_run_reconciler_deploy_safe >/dev/null 2>&1; then
  spot_runner_run_reconciler_deploy_safe \
    "${RUNNER_DIR}" \
    "${CONFIG_PATH}" \
    "rav" \
    "${FUNCTION_NAME}" \
    "${SCHEDULER_NAME}" \
    "$@"
  exit "$?"
fi

args=(reconciler deploy --profile rav --function-name "${FUNCTION_NAME}" --scheduler-name "${SCHEDULER_NAME}")
if [[ -n "${CONFIG_PATH}" ]]; then
  args+=(--config "${CONFIG_PATH}")
fi
run_spotctl_with_config "${CONFIG_PATH}" "${args[@]}" "$@"
