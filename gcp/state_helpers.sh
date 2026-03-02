#!/usr/bin/env bash
# Thin wrapper for shared state helper implementation.
# Canonical source:
#   gcp-spot-runner/state_helpers.sh

_STATE_HELPERS_WRAPPER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

_state_helpers_fail() {
  echo "ERROR: $*" >&2
  return 1 2>/dev/null || exit 1
}

_resolve_runner_dir() {
  local repo_root explicit candidate
  repo_root="$(cd "${_STATE_HELPERS_WRAPPER_DIR}/.." && pwd)"
  explicit="${RUNNER_DIR:-${GCP_SPOT_RUNNER_DIR:-}}"

  if [[ -n "$explicit" ]]; then
    if [[ "$explicit" != /* ]]; then
      explicit="${repo_root}/${explicit}"
    fi
    if [[ -d "$explicit" ]]; then
      cd "$explicit" && pwd
      return 0
    fi
    return 1
  fi

  for candidate in \
    "${repo_root}/../gcp-spot-runner" \
    "${repo_root}/gcp-spot-runner"; do
    if [[ -d "$candidate" ]]; then
      cd "$candidate" && pwd
      return 0
    fi
  done
  return 1
}

_STATE_HELPERS_RUNNER_DIR="$(_resolve_runner_dir)" || _state_helpers_fail \
  "Unable to locate gcp-spot-runner. Set RUNNER_DIR or GCP_SPOT_RUNNER_DIR."
_STATE_HELPERS_SHARED="${_STATE_HELPERS_RUNNER_DIR}/state_helpers.sh"
[[ -f "${_STATE_HELPERS_SHARED}" ]] || _state_helpers_fail \
  "Missing shared state helper file: ${_STATE_HELPERS_SHARED}"

# shellcheck disable=SC1090
source "${_STATE_HELPERS_SHARED}"
