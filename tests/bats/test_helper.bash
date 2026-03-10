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
spot_runner_require_wrapper_runtime_or_exit() {
  local _runner_dir="$1"
  local _hint="${2:-}"
  local loaded_var_name="${3:-RUNNER_ADAPTER_LIB_LOADED}"
  printf -v "${loaded_var_name}" '%s' "1"
}
spot_runner_require_install_or_exit() { return 0; }
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
