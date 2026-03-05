#!/usr/bin/env bash
# Thin wrapper for shared state helper implementation.
# Canonical source:
#   gcp-spot-runner/state_helpers.sh

_STATE_HELPERS_WRAPPER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_STATE_HELPERS_PROJECT_ROOT="$(cd "${_STATE_HELPERS_WRAPPER_DIR}/.." && pwd)"

_state_helpers_fail() {
  echo "ERROR: $*" >&2
  return 1 2>/dev/null || exit 1
}

# shellcheck disable=SC1090
source "${_STATE_HELPERS_PROJECT_ROOT}/scripts/gcp_runner_common.sh"

if declare -F _resolve_runner_dir_for_wrapper >/dev/null 2>&1; then
  if ! RUNNER_DIR="$(_resolve_runner_dir_for_wrapper 2>/dev/null)"; then
    _state_helpers_fail "Unable to locate gcp-spot-runner. Set RUNNER_DIR or GCP_SPOT_RUNNER_DIR."
  fi
fi

if declare -F spot_runner_source_state_helpers_runtime_or_exit >/dev/null 2>&1; then
  spot_runner_source_state_helpers_runtime_or_exit \
    "${RUNNER_DIR}" \
    "${_STATE_HELPERS_PROJECT_ROOT}" \
    "Set RUNNER_DIR or GCP_SPOT_RUNNER_DIR to your gcp-spot-runner checkout."
elif [[ -f "${RUNNER_DIR}/state_helpers.sh" ]]; then
  # shellcheck disable=SC1090
  source "${RUNNER_DIR}/state_helpers.sh"
else
  _state_helpers_fail "Unable to locate gcp-spot-runner. Set RUNNER_DIR or GCP_SPOT_RUNNER_DIR."
fi
