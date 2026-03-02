#!/usr/bin/env bash
# Thin wrapper: delegate Cloud Reconciler deploy to shared gcp-spot-runner.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
RUNNER_DIR="${RUNNER_DIR:-${REPO_ROOT}/../gcp-spot-runner}"
RUNNER_DEPLOY="${RUNNER_DIR}/cloud_reconciler/deploy.sh"

if [[ ! -x "$RUNNER_DEPLOY" ]]; then
  echo "ERROR: Shared deploy script not found: $RUNNER_DEPLOY"
  echo "Set RUNNER_DIR to your gcp-spot-runner checkout."
  exit 1
fi

# Load local project defaults if available.
if [[ -f "${REPO_ROOT}/gcp/rav_spot.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${REPO_ROOT}/gcp/rav_spot.env"
  set +a
fi

: "${FUNCTION_NAME:=rav-reconciler}"
: "${SCHEDULER_NAME:=rav-reconciler-trigger}"

export FUNCTION_NAME
export SCHEDULER_NAME

exec "$RUNNER_DEPLOY" "$@"
