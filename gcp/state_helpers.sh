#!/usr/bin/env bash
# Thin wrapper for shared state helper implementation.
# Canonical source:
#   gcp-spot-runner/state_helpers.sh

_STATE_HELPERS_WRAPPER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_STATE_HELPERS_PROJECT_ROOT="$(cd "${_STATE_HELPERS_WRAPPER_DIR}/.." && pwd)"

# shellcheck disable=SC1090
source "${_STATE_HELPERS_PROJECT_ROOT}/scripts/gcp_runner_common.sh"

# Ensure RUNNER_DIR is resolved via shared runner-default logic when not pre-exported.
spot_runner_wrapper_ensure_project_runner_defaults_if_unset_required \
  "${_STATE_HELPERS_PROJECT_ROOT}" \
  "${RUNNER_BOOTSTRAP_DIR_DEFAULT}" \
  "RUNNER_DIR" \
  "RUNNER_DIR" \
  "${RUNNER_PROFILE}" \
  "${RUNNER_HINT_MESSAGE}"

if ! spot_runner_wrapper_source_project_state_helpers_required_or_fail \
  "${RUNNER_DIR}" \
  "${_STATE_HELPERS_PROJECT_ROOT}" \
  "Set RUNNER_DIR or GCP_SPOT_RUNNER_DIR to your gcp-spot-runner checkout." \
  "Unable to locate gcp-spot-runner. Set RUNNER_DIR or GCP_SPOT_RUNNER_DIR."; then
  return 1 2>/dev/null || exit 1
fi
