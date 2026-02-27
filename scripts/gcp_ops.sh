#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/gcp_runner_common.sh"

load_rav_spot_env
apply_runner_defaults
check_required_spot_vars
check_runner_install
configure_gcloud_runtime

run_ops_command "$@"
