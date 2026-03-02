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
SPOTCTL_MAIN="${RUNNER_DIR}/spotctl/__main__.py"

if [[ ! -f "$SPOTCTL_MAIN" ]]; then
  echo "ERROR: Shared spotctl entrypoint not found: $SPOTCTL_MAIN"
  echo "Set RUNNER_DIR to your gcp-spot-runner checkout."
  exit 1
fi

: "${FUNCTION_NAME:=rav-reconciler}"
: "${SCHEDULER_NAME:=rav-reconciler-trigger}"
DEFAULT_ARGS=(--profile rav --function-name "${FUNCTION_NAME}" --scheduler-name "${SCHEDULER_NAME}")
if [[ -n "${CONFIG_PATH}" ]]; then
  DEFAULT_ARGS+=(--config "${CONFIG_PATH}")
fi

exec env PYTHONPATH="${RUNNER_DIR}${PYTHONPATH:+:${PYTHONPATH}}" \
  python3 -m spotctl reconciler deploy "${DEFAULT_ARGS[@]}" "$@"
