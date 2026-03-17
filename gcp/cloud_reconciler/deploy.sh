#!/usr/bin/env bash
# Thin wrapper: delegate Cloud Reconciler deploy to shared gcp-spot-runner via RAV adapter helpers.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# shellcheck disable=SC1090
source "${REPO_ROOT}/scripts/gcp_runner_common.sh"

spot_runner_wrapper_apply_spot_config_path_override_required RAV_GCP_ENV "${RUNNER_HINT_MESSAGE}"

prepare_rav_runtime "optional" "0" "0"

run_project_command "reconciler_deploy" "$@"
