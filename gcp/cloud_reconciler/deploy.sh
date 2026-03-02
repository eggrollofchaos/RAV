#!/usr/bin/env bash
# Thin wrapper: delegate Cloud Reconciler deploy to shared gcp-spot-runner.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
RUNNER_DIR="${RUNNER_DIR:-${REPO_ROOT}/../gcp-spot-runner}"

# Load local project defaults if available.
if [[ -f "${REPO_ROOT}/gcp/rav_spot.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${REPO_ROOT}/gcp/rav_spot.env"
  set +a
fi

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

export FUNCTION_NAME
export SCHEDULER_NAME

exec env PYTHONPATH="${RUNNER_DIR}${PYTHONPATH:+:${PYTHONPATH}}" \
  python3 -m spotctl reconciler deploy "$@"
