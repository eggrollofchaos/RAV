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
spot_runner_wrapper_load_project_env_optional_compat() {
  local root_dir="$1"
  local env_var_name="$2"
  local default_path="$3"
  local output_var_name="${4:-}"
  spot_runner_wrapper_load_env_optional "${root_dir}" "${env_var_name}" "${default_path}" "${output_var_name}"
}
spot_runner_wrapper_load_project_env_required_compat_or_exit() {
  local root_dir="$1"
  local env_var_name="$2"
  local default_path="$3"
  local output_var_name="${4:-}"
  local _hint_message="${5:-}"
  local missing_message="${6:-Missing required project environment file.}"
  spot_runner_wrapper_load_project_env_optional_compat "${root_dir}" "${env_var_name}" "${default_path}" "${output_var_name}"
  if [[ -z "${!output_var_name:-}" ]]; then
    local cfg="${!env_var_name:-${default_path}}"
    if [[ "${cfg}" != /* ]]; then
      cfg="${root_dir}/${cfg}"
    fi
    echo "Missing ${cfg}. ${missing_message}" >&2
    exit 1
  fi
}
spot_runner_resolve_runner_dir_compat() {
  local _project_root="$1"
  local bootstrap_dir="$2"
  local env_var_name="$3"
  printf '%s\n' "${!env_var_name:-${bootstrap_dir}}"
}
spot_runner_wrapper_resolve_project_runner_dir_compat_or_exit() {
  local project_root="$1"
  local bootstrap_dir="$2"
  local env_var_name="$3"
  local output_var_name="${4:-RUNNER_DIR}"
  local _hint_message="${5:-}"
  local resolved_dir=""
  resolved_dir="$(spot_runner_resolve_runner_dir_compat "${project_root}" "${bootstrap_dir}" "${env_var_name}")"
  printf -v "${output_var_name}" '%s' "${resolved_dir}"
}
spot_runner_wrapper_profile_apply_defaults_required() {
  local _profile_name="${1:-default}"
  local _hint_message="${2:-}"
  :
}
spot_runner_wrapper_apply_project_runner_defaults_required() {
  local root_dir="$1"
  local default_dir="$2"
  local env_var_name="$3"
  local output_var_name="${4:-RUNNER_DIR}"
  local profile_name="${5:-default}"
  local hint_message="${6:-}"
  spot_runner_wrapper_resolve_project_runner_dir_compat_or_exit \
    "${root_dir}" \
    "${default_dir}" \
    "${env_var_name}" \
    "${output_var_name}" \
    "${hint_message}"
  spot_runner_wrapper_profile_apply_defaults_required "${profile_name}" "${hint_message}"
}
spot_runner_wrapper_ensure_project_runner_defaults_if_unset() {
  local root_dir="$1"
  local default_dir="$2"
  local env_var_name="$3"
  local output_var_name="${4:-RUNNER_DIR}"
  local profile_name="${5:-default}"
  local hint_message="${6:-}"
  if [[ -n "${!output_var_name:-}" ]]; then
    return 0
  fi
  spot_runner_wrapper_apply_project_runner_defaults_required \
    "${root_dir}" \
    "${default_dir}" \
    "${env_var_name}" \
    "${output_var_name}" \
    "${profile_name}" \
    "${hint_message}"
}
spot_runner_wrapper_ensure_project_runner_defaults_if_unset_required() {
  spot_runner_wrapper_ensure_project_runner_defaults_if_unset "$@"
}
spot_runner_wrapper_setup_project_runtime_required() {
  local root_dir="$1"
  local default_runner_dir="$2"
  local runner_env_var_name="${3:-RUNNER_DIR}"
  local runner_output_var_name="${4:-RUNNER_DIR}"
  local profile_name="${5:-default}"
  local hint_message="${6:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local env_mode="${7:-optional}"
  local env_var_name="${8:-}"
  local env_default_path="${9:-}"
  local env_output_var_name="${10:-PROJECT_GCP_ENV_PATH}"
  local missing_env_message="${11:-Missing required project environment file.}"
  local require_spot_vars="${12:-0}"
  local configure_gcloud="${13:-0}"
  local gcloud_project_root="${14:-${root_dir}}"

  case "${env_mode}" in
    required)
      spot_runner_wrapper_load_project_env_required_compat_or_exit \
        "${root_dir}" \
        "${env_var_name}" \
        "${env_default_path}" \
        "${env_output_var_name}" \
        "${hint_message}" \
        "${missing_env_message}"
      ;;
    optional)
      spot_runner_wrapper_load_project_env_optional_compat \
        "${root_dir}" \
        "${env_var_name}" \
        "${env_default_path}" \
        "${env_output_var_name}" \
        "${hint_message}"
      ;;
    *)
      ;;
  esac

  spot_runner_wrapper_apply_project_runner_defaults_required \
    "${root_dir}" \
    "${default_runner_dir}" \
    "${runner_env_var_name}" \
    "${runner_output_var_name}" \
    "${profile_name}" \
    "${hint_message}"

  local runner_dir="${!runner_output_var_name:-}"
  if [[ "${require_spot_vars}" == "1" ]]; then
    spot_runner_wrapper_check_required_spot_vars "${hint_message}"
  fi
  spot_runner_wrapper_require_project_install_for_profile_compat_or_exit \
    "${runner_dir}" \
    "${profile_name}" \
    "${hint_message}"
  if [[ "${configure_gcloud}" == "1" ]]; then
    spot_runner_wrapper_configure_gcloud_runtime "${runner_dir}" "${gcloud_project_root}" "${hint_message}"
  fi
}
spot_runner_wrapper_setup_project_profile_runtime_required() {
  local root_dir="$1"
  local default_runner_dir="$2"
  local hint_message="${3:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local profile_name="${4:-default}"
  local env_var_name="${5:-}"
  local env_default_path="${6:-}"
  local env_output_var_name="${7:-PROJECT_GCP_ENV_PATH}"
  local env_mode="${8:-optional}"
  local missing_env_message="${9:-Missing required project environment file.}"
  local require_spot_vars="${10:-0}"
  local configure_gcloud="${11:-0}"
  local gcloud_project_root="${12:-${root_dir}}"
  if [[ $# -gt 12 ]]; then
    shift 12
  else
    set --
  fi
  spot_runner_wrapper_setup_project_runtime_required \
    "${root_dir}" \
    "${default_runner_dir}" \
    "RUNNER_DIR" \
    "RUNNER_DIR" \
    "${profile_name}" \
    "${hint_message}" \
    "${env_mode}" \
    "${env_var_name}" \
    "${env_default_path}" \
    "${env_output_var_name}" \
    "${missing_env_message}" \
    "${require_spot_vars}" \
    "${configure_gcloud}" \
    "${gcloud_project_root}" \
    "$@"
}
spot_runner_wrapper_resolve_active_config_path() {
  local current_config_path="${1:-}"
  local default_config_path="${2:-}"
  local use_default_when_empty="${3:-1}"
  if [[ -n "${current_config_path}" ]]; then
    printf '%s\n' "${current_config_path}"
    return 0
  fi
  if [[ "${use_default_when_empty}" == "1" && -n "${default_config_path}" ]]; then
    printf '%s\n' "${default_config_path}"
  fi
}
spot_runner_wrapper_resolve_loaded_config_path() {
  local current_config_path="${1:-}"
  local default_config_path="${2:-}"
  spot_runner_wrapper_resolve_active_config_path "${current_config_path}" "${default_config_path}" "0"
}
spot_runner_wrapper_resolve_config_path() {
  local mode="${1:-active}"
  local current_config_path="${2:-}"
  local default_config_path="${3:-}"
  case "${mode}" in
    active)
      spot_runner_wrapper_resolve_active_config_path "${current_config_path}" "${default_config_path}" "1"
      ;;
    loaded)
      spot_runner_wrapper_resolve_loaded_config_path "${current_config_path}" "${default_config_path}"
      ;;
    *)
      echo "Unsupported config-path mode: ${mode}" >&2
      return 1
      ;;
  esac
}
spot_runner_wrapper_resolve_active_config_path_required() {
  spot_runner_wrapper_resolve_active_config_path "$@"
}
spot_runner_wrapper_resolve_loaded_config_path_required() {
  spot_runner_wrapper_resolve_loaded_config_path "$@"
}
spot_runner_wrapper_resolve_config_path_required() {
  spot_runner_wrapper_resolve_config_path "$@"
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
spot_runner_bootstrap_initialize_project_wrapper_from_candidates_required() {
  spot_runner_bootstrap_initialize_project_wrapper_required "$@"
}
spot_runner_bootstrap_initialize_project_wrapper_from_default_candidates_required() {
  spot_runner_bootstrap_initialize_project_wrapper_from_candidates_required "$@"
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
spot_runner_wrapper_source_project_state_helpers_required_or_fail() {
  local runner_dir="$1"
  local project_root="$2"
  local hint_message="${3:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local error_message="${4:-Unable to locate gcp-spot-runner. Set RUNNER_DIR or GCP_SPOT_RUNNER_DIR.}"
  if spot_runner_wrapper_source_project_state_helpers_required "${runner_dir}" "${project_root}" "${hint_message}"; then
    return 0
  fi
  echo "ERROR: ${error_message}" >&2
  return 1
}
spot_runner_wrapper_init_project_state_helpers_wrapper_required() {
  local project_root="$1"
  local default_runner_dir="$2"
  local profile_name="${3:-default}"
  local hint_message="${4:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local error_message="${5:-Unable to locate gcp-spot-runner. Set RUNNER_DIR or GCP_SPOT_RUNNER_DIR.}"
  local runner_env_var_name="${6:-RUNNER_DIR}"
  local runner_output_var_name="${7:-RUNNER_DIR}"

  spot_runner_wrapper_ensure_project_runner_defaults_if_unset_required \
    "${project_root}" \
    "${default_runner_dir}" \
    "${runner_env_var_name}" \
    "${runner_output_var_name}" \
    "${profile_name}" \
    "${hint_message}" || return "$?"

  local runner_dir="${!runner_output_var_name:-}"
  spot_runner_wrapper_source_project_state_helpers_required_or_fail \
    "${runner_dir}" \
    "${project_root}" \
    "${hint_message}" \
    "${error_message}"
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
spot_runner_wrapper_run_project_build_with_config() {
  local runner_dir="$1"
  local _hint_message="${2:-}"
  local _loaded_var_name="${3:-RUNNER_ADAPTER_LIB_LOADED}"
  local config_path="$4"
  local profile_name="$5"
  shift 5
  spot_runner_wrapper_run_profiled_compat "$runner_dir" "$config_path" "$profile_name" "build" "$@"
}
spot_runner_wrapper_run_project_monitor_with_config() {
  local runner_dir="$1"
  local _hint_message="${2:-}"
  local _loaded_var_name="${3:-RUNNER_ADAPTER_LIB_LOADED}"
  local config_path="$4"
  local profile_name="$5"
  shift 5
  spot_runner_wrapper_run_profiled_compat "$runner_dir" "$config_path" "$profile_name" "monitor" "$@"
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
spot_runner_wrapper_run_project_ops() {
  local runner_dir="$1"
  local _hint_message="${2:-}"
  local _loaded_var_name="${3:-RUNNER_ADAPTER_LIB_LOADED}"
  local config_path="$4"
  local profile_name="$5"
  shift 5
  local args=("$@")
  if [[ ${#args[@]} -eq 0 ]]; then
    args=(status)
  fi
  spot_runner_wrapper_run_profiled_compat "$runner_dir" "$config_path" "$profile_name" "ops" "${args[@]}"
}
spot_runner_wrapper_run_project_version() {
  local runner_dir="$1"
  local _hint_message="${2:-}"
  local _loaded_var_name="${3:-RUNNER_ADAPTER_LIB_LOADED}"
  local config_path="${4:-}"
  shift 4 || true
  spot_runner_wrapper_run_spotctl_compat "$runner_dir" "$config_path" version "$@"
}
spot_runner_wrapper_profile_reconciler_defaults() {
  local profile_name="${1:-default}"
  local function_name_out="${2:-DEFAULT_FUNCTION_NAME}"
  local scheduler_name_out="${3:-DEFAULT_SCHEDULER_NAME}"
  local function_name=""
  case "${profile_name}" in
    ixqt)
      function_name="ixqt-cloud-reconciler"
      ;;
    rav)
      function_name="rav-cloud-reconciler"
      ;;
    *)
      function_name="spot-reconciler"
      ;;
  esac
  local scheduler_name="${function_name}-scheduler"
  printf -v "${function_name_out}" '%s' "${function_name}"
  printf -v "${scheduler_name_out}" '%s' "${scheduler_name}"
}
spot_runner_wrapper_run_project_reconciler_deploy_with_profile_defaults_required() {
  local runner_dir="$1"
  local _hint_message="${2:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local _loaded_var_name="${3:-RUNNER_ADAPTER_LIB_LOADED}"
  local config_path="${4:-}"
  local profile_name="${5:-default}"
  shift 5 || true

  local function_name=""
  local scheduler_name=""
  spot_runner_wrapper_profile_reconciler_defaults "${profile_name}" function_name scheduler_name
  function_name="${FUNCTION_NAME:-${function_name}}"
  scheduler_name="${SCHEDULER_NAME:-${scheduler_name}}"

  spot_runner_wrapper_run_spotctl_compat \
    "${runner_dir}" \
    "${config_path}" \
    reconciler \
    deploy \
    --profile "${profile_name}" \
    --function-name "${function_name}" \
    --scheduler-name "${scheduler_name}" \
    "$@"
}
spot_runner_wrapper_run_project_command_with_mode() {
  local runner_dir="$1"
  local hint_message="${2:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local loaded_var_name="${3:-RUNNER_ADAPTER_LIB_LOADED}"
  local config_mode="${4:-active}"
  local current_config_path="${5:-}"
  local default_config_path="${6:-}"
  local profile_name="${7:-default}"
  local command_name="${8:-}"
  shift 8 || true

  local config_path=""
  config_path="$(spot_runner_wrapper_resolve_config_path_required "${config_mode}" "${current_config_path}" "${default_config_path}" "${hint_message}")" || return "$?"

  case "${command_name}" in
    ops)
      spot_runner_wrapper_run_project_ops "${runner_dir}" "${hint_message}" "${loaded_var_name}" "${config_path}" "${profile_name}" "$@"
      ;;
    build)
      spot_runner_wrapper_run_project_build_with_config "${runner_dir}" "${hint_message}" "${loaded_var_name}" "${config_path}" "${profile_name}" "$@"
      ;;
    monitor)
      spot_runner_wrapper_run_project_monitor_with_config "${runner_dir}" "${hint_message}" "${loaded_var_name}" "${config_path}" "${profile_name}" "$@"
      ;;
    version)
      spot_runner_wrapper_run_project_version "${runner_dir}" "${hint_message}" "${loaded_var_name}" "${config_path}" "$@"
      ;;
    reconciler_deploy)
      spot_runner_wrapper_run_project_reconciler_deploy_with_profile_defaults_required "${runner_dir}" "${hint_message}" "${loaded_var_name}" "${config_path}" "${profile_name}" "$@"
      ;;
    submit_with_job)
      if [[ $# -lt 1 ]]; then
        echo "Missing submit_with_job command argument: job command" >&2
        return 2
      fi
      local job_command="$1"
      shift
      spot_runner_wrapper_run_project_submit_with_job_compat "${runner_dir}" "${hint_message}" "${loaded_var_name}" "${config_path}" "${profile_name}" "${job_command}" "$@"
      ;;
    *)
      echo "Unsupported project command with mode: ${command_name}" >&2
      return 1
      ;;
  esac
}
spot_runner_wrapper_run_project_command_with_mode_required() {
  spot_runner_wrapper_run_project_command_with_mode "$@"
}
spot_runner_wrapper_run_project_standard_command_required() {
  spot_runner_wrapper_run_project_command_with_mode_required "$@"
}
spot_runner_wrapper_run_project_standard_command_compat_required() {
  spot_runner_wrapper_run_project_standard_command_required "$@"
}
spot_runner_wrapper_run_project_standard_command_active_required() {
  local runner_dir="$1"
  local hint_message="${2:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local loaded_var_name="${3:-RUNNER_ADAPTER_LIB_LOADED}"
  local current_config_path="${4:-}"
  local default_config_path="${5:-}"
  local profile_name="${6:-default}"
  local command_name="${7:-}"
  shift 7 || true

  spot_runner_wrapper_run_project_standard_command_compat_required \
    "${runner_dir}" \
    "${hint_message}" \
    "${loaded_var_name}" \
    "active" \
    "${current_config_path}" \
    "${default_config_path}" \
    "${profile_name}" \
    "${command_name}" \
    "$@"
}
spot_runner_wrapper_run_project_standard_command_loaded_required() {
  local runner_dir="$1"
  local hint_message="${2:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local loaded_var_name="${3:-RUNNER_ADAPTER_LIB_LOADED}"
  local current_config_path="${4:-}"
  local default_config_path="${5:-}"
  local profile_name="${6:-default}"
  local command_name="${7:-}"
  shift 7 || true

  spot_runner_wrapper_run_project_standard_command_compat_required \
    "${runner_dir}" \
    "${hint_message}" \
    "${loaded_var_name}" \
    "loaded" \
    "${current_config_path}" \
    "${default_config_path}" \
    "${profile_name}" \
    "${command_name}" \
    "$@"
}
spot_runner_wrapper_project_command_config_mode() {
  local profile_name="${1:-default}"
  local command_name="${2:-}"
  case "${profile_name}:${command_name}" in
    ixqt:*)
      printf '%s\n' "loaded"
      ;;
    rav:version|rav:reconciler_deploy)
      printf '%s\n' "loaded"
      ;;
    rav:ops|rav:build|rav:monitor|rav:submit_with_job)
      printf '%s\n' "active"
      ;;
    *:version|*:reconciler_deploy)
      printf '%s\n' "loaded"
      ;;
    *)
      printf '%s\n' "active"
      ;;
  esac
}
spot_runner_wrapper_run_project_profile_command_required() {
  local runner_dir="$1"
  local hint_message="${2:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local loaded_var_name="${3:-RUNNER_ADAPTER_LIB_LOADED}"
  local current_config_path="${4:-}"
  local default_config_path="${5:-}"
  local profile_name="${6:-default}"
  local command_name="${7:-}"
  shift 7 || true

  local config_mode=""
  config_mode="$(spot_runner_wrapper_project_command_config_mode "${profile_name}" "${command_name}")"

  spot_runner_wrapper_run_project_standard_command_compat_required \
    "${runner_dir}" \
    "${hint_message}" \
    "${loaded_var_name}" \
    "${config_mode}" \
    "${current_config_path}" \
    "${default_config_path}" \
    "${profile_name}" \
    "${command_name}" \
    "$@"
}
spot_runner_wrapper_run_project_profile_command_with_paths_required() {
  local runner_dir="$1"
  local hint_message="${2:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local loaded_var_name="${3:-RUNNER_ADAPTER_LIB_LOADED}"
  local profile_name="${4:-default}"
  local command_name="${5:-}"
  local current_config_path="${6:-}"
  local default_config_path="${7:-}"
  shift 7 || true

  spot_runner_wrapper_run_project_profile_command_required \
    "${runner_dir}" \
    "${hint_message}" \
    "${loaded_var_name}" \
    "${current_config_path}" \
    "${default_config_path}" \
    "${profile_name}" \
    "${command_name}" \
    "$@"
}
spot_runner_wrapper_run_project_command_entrypoint_required() {
  local _hint_message="${1:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local runtime_function_name="${2:-}"
  local command_function_name="${3:-}"
  shift 3 || true

  local runtime_args=()
  while [[ $# -gt 0 ]]; do
    if [[ "$1" == "--" ]]; then
      shift
      break
    fi
    runtime_args+=("$1")
    shift
  done

  "${runtime_function_name}" "${runtime_args[@]}"
  "${command_function_name}" "$@"
}
spot_runner_wrapper_run_project_build_entrypoint_required() {
  local _hint_message="${1:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local runtime_function_name="${2:-}"
  local build_function_name="${3:-}"
  local source_path="${4:-}"
  local cloudbuild_config_path="${5:-}"
  local image_value="${6:-}"
  shift 6 || true

  local runtime_args=()
  local build_passthrough_args=()
  local saw_delimiter=0
  while [[ $# -gt 0 ]]; do
    if [[ "$1" == "--" ]]; then
      saw_delimiter=1
      shift
      break
    fi
    runtime_args+=("$1")
    shift
  done
  if [[ "${saw_delimiter}" == "1" ]]; then
    build_passthrough_args=("$@")
  else
    build_passthrough_args=("${runtime_args[@]}")
    runtime_args=()
  fi

  local build_args=(
    --source "${source_path}"
    --cloudbuild-config "${cloudbuild_config_path}"
  )
  if [[ -n "${image_value}" ]]; then
    build_args+=(--image "${image_value}")
  fi
  build_args+=("${build_passthrough_args[@]}")

  "${runtime_function_name}" "${runtime_args[@]}"
  "${build_function_name}" "${build_args[@]}"
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
spot_runner_wrapper_profile_submit_guard_aliases() {
  local profile_name="${1:-default}"
  case "${profile_name}" in
    rav)
      printf '%s\n' "_RAV_CAFFEINATED,_IXQT_CAFFEINATED"
      ;;
    *)
      printf '%s\n' "_IXQT_CAFFEINATED"
      ;;
  esac
}
spot_runner_wrapper_prepare_project_submit_shell_for_profile_compat() {
  local profile_name="${1:-default}"
  local guard_alias_csv_override="${2:-}"
  shift 2 || true

  local guard_alias_csv="${guard_alias_csv_override}"
  if [[ -z "${guard_alias_csv}" ]]; then
    guard_alias_csv="$(spot_runner_wrapper_profile_submit_guard_aliases "${profile_name}")"
  fi

  spot_runner_wrapper_prepare_project_submit_shell_entrypoint_compat_or_fallback "${guard_alias_csv}" "$@"
}
spot_runner_wrapper_prepare_project_submit_shell_for_profile_required() {
  local _hint_message="${1:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local profile_name="${2:-default}"
  local guard_alias_csv_override="${3:-}"
  shift 3 || true
  spot_runner_wrapper_prepare_project_submit_shell_for_profile_compat \
    "${profile_name}" \
    "${guard_alias_csv_override}" \
    "$@"
}
spot_runner_wrapper_prepare_project_submit_shell_for_profile_from_args_required() {
  local hint_message="${1:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local profile_name="${2:-default}"
  shift 2 || true

  local guard_alias_csv_override=""
  if [[ "${1:-}" == _*CAFFEINATED* ]]; then
    guard_alias_csv_override="$1"
    shift || true
  fi

  spot_runner_wrapper_prepare_project_submit_shell_for_profile_required \
    "${hint_message}" \
    "${profile_name}" \
    "${guard_alias_csv_override}" \
    "$@"
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
