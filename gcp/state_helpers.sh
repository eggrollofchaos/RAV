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

_RESOLVER_CANDIDATES=()
if [[ -n "${RUNNER_DIR:-${GCP_SPOT_RUNNER_DIR:-}}" ]]; then
  _EXPLICIT_RUNNER="${RUNNER_DIR:-${GCP_SPOT_RUNNER_DIR:-}}"
  if [[ "${_EXPLICIT_RUNNER}" != /* ]]; then
    _EXPLICIT_RUNNER="${_STATE_HELPERS_PROJECT_ROOT}/${_EXPLICIT_RUNNER}"
  fi
  _RESOLVER_CANDIDATES+=("${_EXPLICIT_RUNNER}/adapters/state_helpers_wrapper.sh")
fi
_RESOLVER_CANDIDATES+=(
  "${_STATE_HELPERS_PROJECT_ROOT}/../gcp-spot-runner/adapters/state_helpers_wrapper.sh"
  "${_STATE_HELPERS_PROJECT_ROOT}/gcp-spot-runner/adapters/state_helpers_wrapper.sh"
)

_STATE_HELPERS_RESOLVER=""
for _candidate in "${_RESOLVER_CANDIDATES[@]}"; do
  if [[ -f "${_candidate}" ]]; then
    _STATE_HELPERS_RESOLVER="${_candidate}"
    break
  fi
done
[[ -n "${_STATE_HELPERS_RESOLVER}" ]] || _state_helpers_fail \
  "Unable to locate gcp-spot-runner. Set RUNNER_DIR or GCP_SPOT_RUNNER_DIR."

# shellcheck disable=SC1090
source "${_STATE_HELPERS_RESOLVER}"
spot_runner_source_state_helpers_wrapper "${_STATE_HELPERS_PROJECT_ROOT}"
