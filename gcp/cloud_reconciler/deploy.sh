#!/usr/bin/env bash
# Thin wrapper: delegate Cloud Reconciler deploy to shared gcp-spot-runner.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
RUNNER_DIR="${RUNNER_DIR:-${REPO_ROOT}/../gcp-spot-runner}"
CONFIG_PATH="${SPOT_CONFIG_PATH:-${REPO_ROOT}/gcp/rav_spot.env}"
if [[ -n "${CONFIG_PATH}" ]] && [[ "${CONFIG_PATH}" != /* ]]; then
  CONFIG_PATH="${REPO_ROOT}/${CONFIG_PATH}"
fi
[[ -f "${CONFIG_PATH}" ]] || CONFIG_PATH=""

if [[ "${RUNNER_DIR}" != /* ]]; then
  RUNNER_DIR="${REPO_ROOT}/${RUNNER_DIR}"
fi
RUNNER_DIR="$(cd "${RUNNER_DIR}" && pwd)"
ADAPTER_LIB="${RUNNER_DIR}/adapters/spot_runner_common.sh"
if [[ ! -f "$ADAPTER_LIB" ]]; then
  echo "ERROR: Shared adapter helper not found: $ADAPTER_LIB"
  echo "Set RUNNER_DIR to your gcp-spot-runner checkout."
  exit 1
fi
# shellcheck disable=SC1090
source "$ADAPTER_LIB"
if ! spot_runner_check_install "$RUNNER_DIR" "spotctl/__main__.py" "adapters/spot_runner_common.sh"; then
  echo "Set RUNNER_DIR to your gcp-spot-runner checkout."
  exit 1
fi

: "${FUNCTION_NAME:=rav-reconciler}"
: "${SCHEDULER_NAME:=rav-reconciler-trigger}"
DEFAULT_ARGS=(--profile rav --function-name "${FUNCTION_NAME}" --scheduler-name "${SCHEDULER_NAME}")
if [[ -n "${CONFIG_PATH}" ]]; then
  DEFAULT_ARGS+=(--config "${CONFIG_PATH}")
fi

spot_runner_run_spotctl "${RUNNER_DIR}" "${CONFIG_PATH}" \
  reconciler deploy "${DEFAULT_ARGS[@]}" "$@"
