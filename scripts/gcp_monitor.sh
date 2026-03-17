#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/gcp_runner_common.sh"

spot_runner_wrapper_run_project_named_command_entrypoint_required \
  "${RUNNER_HINT_MESSAGE:-Set RUNNER_DIR to your gcp-spot-runner checkout.}" \
  "prepare_rav_runtime" \
  "run_project_command" \
  "monitor" \
  "required" \
  "1" \
  "1" \
  -- \
  "$@"
