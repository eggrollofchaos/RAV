#!/usr/bin/env bash
# tests/bats/test_helper.bash — Shared setup for RAV GCP shell tests.

BATS_TEST_DIRNAME="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"

# Deterministic env
export TZ=UTC
export LC_ALL=C

# Shim PATH — shims intercept external commands (gcloud, curl, etc.)
export PATH="$BATS_TEST_DIRNAME/shims:$PATH"
export RAV_BATS_TEST=1

# Project env
export PROJECT="ixqt-488109"
export ZONE="us-east1-c"
export BUCKET="ixqt-training-488109"
export RUN_ID="test-20260228-120000"
export REGION="us-east1"

# Shim call log — initialized per-test in setup()
export SHIM_LOG="$BATS_TEST_TMPDIR/shim_calls.log"

load "$BATS_TEST_DIRNAME/lib/bats-support/load"
load "$BATS_TEST_DIRNAME/lib/bats-assert/load"

# Fallback adapter stubs — used in CI where gcp-spot-runner is not available.
# When the real adapter is present, _bootstrap_runner_adapter_lib overwrites these.
spot_runner_wrapper_load_env_optional() {
  local root_dir="$1"
  local env_var_name="$2"
  local default_path="$3"
  local output_var_name="${4:-}"
  local cfg="${!env_var_name:-${default_path}}"
  if [[ "${cfg}" != /* ]]; then
    cfg="${root_dir}/${cfg}"
  fi
  if [[ -f "${cfg}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${cfg}"
    set +a
  fi
  if [[ -n "${output_var_name}" ]]; then
    printf -v "${output_var_name}" '%s' "${cfg}"
  fi
}
spot_runner_resolve_runner_dir_compat() {
  local _project_root="$1"
  local bootstrap_dir="$2"
  local env_var_name="$3"
  printf '%s\n' "${!env_var_name:-${bootstrap_dir}}"
}
spot_runner_bootstrap_initialize_project_wrapper() {
  local project_root="$1"
  local _profile_name="${2:-default}"
  local default_hint="${3:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local output_var_name="${4:-RUNNER_BOOTSTRAP_DIR_DEFAULT}"
  local env_var_name="${5:-RUNNER_DIR}"
  local hint_output_var_name="${6:-RUNNER_HINT_MESSAGE}"
  shift 6 || true
  local candidate="${!env_var_name:-${1:-${project_root}/../gcp-spot-runner}}"
  if [[ "${candidate}" != /* ]]; then
    candidate="${project_root}/${candidate}"
  fi
  printf -v "${output_var_name}" '%s' "${candidate}"
  printf -v "${hint_output_var_name}" '%s' "${default_hint}"
}
spot_runner_bootstrap_initialize_project_wrapper_required() {
  spot_runner_bootstrap_initialize_project_wrapper "$@"
}
spot_runner_require_wrapper_runtime_or_exit() {
  local _runner_dir="$1"
  local _hint="${2:-}"
  local loaded_var_name="${3:-RUNNER_ADAPTER_LIB_LOADED}"
  printf -v "${loaded_var_name}" '%s' "1"
}
spot_runner_wrapper_require_function_or_hint() {
  local function_name="$1"
  local hint_message="${2:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  if [[ "$(type -t "${function_name}" || true)" == "function" ]]; then
    return 0
  fi
  echo "Runner helper missing required function: ${function_name}" >&2
  echo "${hint_message}" >&2
  return 1
}
spot_runner_wrapper_source_project_state_helpers_or_fail() {
  local runner_dir="$1"
  local project_root="${2:-}"
  local hint_message="${3:-Set RUNNER_DIR or GCP_SPOT_RUNNER_DIR to your gcp-spot-runner checkout.}"
  local helper_path="${runner_dir}/state_helpers.sh"
  if [[ -f "${helper_path}" ]]; then
    # shellcheck disable=SC1090
    source "${helper_path}"
    return 0
  fi
  echo "${hint_message}" >&2
  return 1
}
spot_runner_wrapper_source_project_state_helpers_required() {
  spot_runner_wrapper_source_project_state_helpers_or_fail "$@"
}
spot_runner_require_install_or_exit() { return 0; }
spot_runner_wrapper_apply_rav_defaults() {
  : "${ZONE:=us-east1-c}"
  if ! declare -p FALLBACK_ZONES >/dev/null 2>&1; then
    FALLBACK_ZONES=("us-east1-b" "us-east1-c" "us-east1-d")
  fi
  : "${MACHINE_TYPE:=n1-standard-8}"
  : "${GPU_TYPE:=nvidia-tesla-t4}"
  : "${BOOT_DISK_SIZE:=100}"
  : "${BOOT_DISK_TYPE:=pd-ssd}"
  : "${DATA_DISK_ENABLED:=true}"
  : "${DATA_DISK_NAME:=}"
  : "${DATA_DISK_SIZE_GB:=500}"
  : "${DATA_DISK_TYPE:=pd-ssd}"
  : "${DATA_DISK_DEVICE_NAME:=spot-data}"
  : "${DATA_DISK_MOUNT_PATH:=/var/lib/spot-data}"
  : "${DATA_DISK_FS_TYPE:=ext4}"
  : "${CONTAINER_NAME:=rav-trainer}"
  : "${CONDA_ENV:=}"
  : "${GPU_TIMEOUT_SEC:=600}"
  : "${MAX_RUNTIME_SEC:=172800}"
  : "${POLL_INTERVAL:=120}"
  : "${HEARTBEAT_STALE_SEC:=600}"
  : "${HEARTBEAT_STALE_MAX:=3}"
  : "${PROGRESS_STALL_POLLS:=6}"
  : "${MAX_RESTARTS:=3}"
  : "${RESTART_BACKOFF_SEC:=60}"
  : "${WALL_CLOCK_DEADLINE:=}"
  : "${DEADLINE_TZ:=America/New_York}"
  : "${OWNER_LOCK_STALE_SEC:=300}"
  : "${METADATA_PREFIX:=spot}"
  : "${RUNNER_LABEL:=spot-runner}"
  : "${LOG_LEVEL:=INFO}"
  : "${DISCORD_WEBHOOK_URL:=}"
  : "${NOTIFY_SECRET:=}"
}
spot_runner_wrapper_apply_rav_defaults_required() {
  local _hint_message="${1:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  spot_runner_wrapper_apply_rav_defaults
}
# Inner functions — tests may override these to capture arguments.
spot_runner_run_spotctl_compat() {
  local runner_dir="$1"
  local config_path="$2"
  shift 2
  printf '%s\n' "spotctl" "$@"
}
spot_runner_run_profiled_compat() {
  local runner_dir="$1"
  local config_path="$2"
  local profile_name="$3"
  local command_name="$4"
  shift 4
  printf '%s\n' "$command_name" "--profile" "$profile_name"
  if [[ -n "$config_path" ]]; then
    printf '%s\n' "--config" "$config_path"
  fi
  printf '%s\n' "$@"
}
# Wrapper functions — delegate to inner functions so test overrides take effect.
spot_runner_wrapper_run_spotctl_compat() {
  spot_runner_run_spotctl_compat "$@"
}
spot_runner_wrapper_run_profiled_compat() {
  spot_runner_run_profiled_compat "$@"
}
spot_runner_wrapper_run_ops_compat() {
  local runner_dir="$1"
  local config_path="$2"
  local profile_name="$3"
  shift 3
  local args=("$@")
  if [[ ${#args[@]} -eq 0 ]]; then
    args=(status)
  fi
  spot_runner_wrapper_run_profiled_compat "$runner_dir" "$config_path" "$profile_name" "ops" "${args[@]}"
}
spot_runner_wrapper_run_profiled_command_compat() {
  local runner_dir="$1"
  local config_path="$2"
  local profile_name="$3"
  local command_name="$4"
  shift 4
  spot_runner_wrapper_run_profiled_compat "$runner_dir" "$config_path" "$profile_name" "$command_name" "$@"
}
spot_runner_wrapper_run_version_compat() {
  local runner_dir="$1"
  local config_path="${2:-}"
  shift 2 || true
  spot_runner_wrapper_run_spotctl_compat "$runner_dir" "$config_path" version "$@"
}
spot_runner_wrapper_run_project_submit_with_job_compat() {
  local runner_dir="$1"
  local _hint_message="${2:-}"
  local _loaded_var_name="${3:-RUNNER_ADAPTER_LIB_LOADED}"
  local config_path="$4"
  local profile_name="$5"
  local job_command="$6"
  shift 6
  local args=("$@")
  local has_skip_build=false
  local arg
  for arg in "${args[@]}"; do
    if [[ "$arg" == "--skip-build" ]]; then
      has_skip_build=true
      break
    fi
  done
  if [[ "$has_skip_build" != true ]]; then
    args=(--skip-build "${args[@]}")
  fi
  spot_runner_wrapper_run_profiled_compat \
    "$runner_dir" \
    "$config_path" \
    "$profile_name" \
    "submit" \
    --job-command "$job_command" \
    "${args[@]}"
}
spot_runner_maybe_reexec_caffeinate_compat() {
  local guard_var="${1:-_SPOT_CAFFEINATED}"
  shift 2 || true
  if [[ -n "${!guard_var:-}" ]]; then
    return 0
  fi
  if ! command -v caffeinate >/dev/null 2>&1; then
    return 0
  fi
  exec env "${guard_var}=1" caffeinate -i "$0" "$@"
}
spot_runner_prepare_submit_shell_compat() {
  local guard_var="${1:-_SPOT_CAFFEINATED}"
  local guard_alias_csv="${2:-}"
  shift 2 || true
  spot_runner_maybe_reexec_caffeinate_compat "${guard_var}" "${guard_alias_csv}" "$@"
  trap '' HUP
}
spot_runner_wrapper_prepare_project_submit_shell_entrypoint_compat_or_fallback() {
  local guard_alias_csv="${1:-_IXQT_CAFFEINATED}"
  shift || true
  spot_runner_prepare_submit_shell_compat "_SPOT_CAFFEINATED" "${guard_alias_csv}" "$@"
}
spot_runner_wrapper_prepare_project_submit_shell_entrypoint_required() {
  local _hint_message="${1:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local guard_alias_csv="${2:-_IXQT_CAFFEINATED}"
  shift 2 || true
  spot_runner_wrapper_prepare_project_submit_shell_entrypoint_compat_or_fallback "${guard_alias_csv}" "$@"
}

setup() {
    : > "$SHIM_LOG"
    # Defaults — tests override what they need
    export GCLOUD_VM_EXISTS="true"
    export GCLOUD_CREATE_RESULT="ok"
    export GCLOUD_STORAGE_CAT_RESULT=""
    export GCLOUD_STORAGE_STAT_GEN="1234567890"
    export GCLOUD_STORAGE_CP_RESULT="ok"
    export CURL_PREEMPT_RESULT="FALSE"
    export CURL_TOKEN_RESULT='{"access_token":"fake-token","expires_in":3600,"token_type":"Bearer"}'
    export DISCORD_WEBHOOK_URL=""
    # Unset per-zone create vars
    unset GCLOUD_CREATE_RESULT_us_east1_c 2>/dev/null || true
    unset GCLOUD_CREATE_RESULT_us_east1_b 2>/dev/null || true
    unset GCLOUD_CREATE_RESULT_us_east1_d 2>/dev/null || true
}

fixture_path()    { echo "$BATS_TEST_DIRNAME/fixtures/$1"; }
fixture_content() { cat "$BATS_TEST_DIRNAME/fixtures/$1"; }

assert_shim_called()  { grep -qF "$1" "$SHIM_LOG" || fail "Expected shim call: $1"; }
refute_shim_called()  { ! grep -qF "$1" "$SHIM_LOG" || fail "Unexpected shim call: $1"; }
count_shim_calls()    { grep -cF "$1" "$SHIM_LOG" || echo 0; }
