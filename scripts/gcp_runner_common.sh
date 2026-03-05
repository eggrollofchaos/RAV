#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAV_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

RAV_GCP_ENV_DEFAULT="${RAV_ROOT}/gcp/rav_spot.env"
RUNNER_DIR_DEFAULT="${RAV_ROOT}/../gcp-spot-runner"
RAV_GCP_ENV_PATH=""
RUNNER_ADAPTER_LIB_LOADED="0"

_bootstrap_runner_adapter_lib() {
  local bootstrap_lib="${RUNNER_DIR_DEFAULT}/adapters/spot_runner_common.sh"
  if [[ -f "${bootstrap_lib}" ]]; then
    # shellcheck disable=SC1090
    source "${bootstrap_lib}"
  fi
}

_bootstrap_runner_adapter_lib

load_rav_spot_env_optional() {
  if ! declare -F spot_runner_load_env_optional >/dev/null 2>&1; then
    RAV_GCP_ENV_PATH=""
    return 0
  fi

  local cfg_path=""
  if ! spot_runner_load_env_optional "${RAV_ROOT}" "RAV_GCP_ENV" "${RAV_GCP_ENV_DEFAULT}" cfg_path; then
    RAV_GCP_ENV_PATH=""
    return 0
  fi
  RAV_GCP_ENV_PATH="${cfg_path}"
}

load_rav_spot_env() {
  load_rav_spot_env_optional
  if [[ -n "${RAV_GCP_ENV_PATH}" ]]; then
    return 0
  fi
  local cfg="${RAV_GCP_ENV:-${RAV_GCP_ENV_DEFAULT}}"
  if [[ "${cfg}" != /* ]]; then
    cfg="${RAV_ROOT}/${cfg}"
  fi
  echo "Missing ${cfg}. Copy gcp/rav_spot.env.example to gcp/rav_spot.env and fill it." >&2
  exit 1
}

apply_runner_defaults() {
  RUNNER_DIR="$(spot_runner_resolve_runner_dir_compat "${RAV_ROOT}" "${RUNNER_DIR_DEFAULT}" "RUNNER_DIR")"
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

_require_runner_adapter_lib() {
  if ! spot_runner_require_wrapper_runtime "${RUNNER_DIR}" "Set RUNNER_DIR in gcp/rav_spot.env to your gcp-spot-runner checkout." "RUNNER_ADAPTER_LIB_LOADED"; then
    exit 1
  fi
}

configure_gcloud_runtime() {
  : "${CLOUDSDK_CORE_DISABLE_PROMPTS:=1}"
  export CLOUDSDK_CORE_DISABLE_PROMPTS
  : "${CLOUDSDK_PYTHON_SITEPACKAGES:=0}"
  export CLOUDSDK_PYTHON_SITEPACKAGES

  if [[ -n "${CLOUDSDK_PYTHON:-}" ]]; then
    return 0
  fi

  local py_candidates=(
    "${RAV_ROOT}/.venv/bin/python3.12"
    "${RAV_ROOT}/.venv/bin/python3"
  )

  local py
  for py in "${py_candidates[@]}"; do
    if [[ -x "$py" ]]; then
      export CLOUDSDK_PYTHON="$py"
      return 0
    fi
  done

  if command -v python3.12 >/dev/null 2>&1; then
    export CLOUDSDK_PYTHON="$(command -v python3.12)"
  fi
}

check_required_spot_vars() {
  local missing=()
  local key
  for key in PROJECT REGION SA IMAGE BUCKET; do
    if [[ -z "${!key:-}" ]]; then
      missing+=("$key")
    fi
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    echo "Missing required gcp/rav_spot.env values: ${missing[*]}" >&2
    exit 1
  fi
}

check_runner_install() {
  _require_runner_adapter_lib
  local required=(
    spotctl/__main__.py
    submit_legacy.sh
    ops_legacy.sh
    lib.sh
    startup.sh
  )
  if ! spot_runner_require_install "${RUNNER_DIR}" "Set RUNNER_DIR in gcp/rav_spot.env to your gcp-spot-runner checkout." "${required[@]}"; then
    exit 1
  fi
}

run_spotctl_with_config() {
  _require_runner_adapter_lib
  local config_path="$1"
  shift

  spot_runner_wrapper_run_spotctl_compat "${RUNNER_DIR}" "${config_path}" "$@"
  return "$?"
}

_run_profiled_with_config() {
  local config_path="$1"
  local profile_name="$2"
  local command_name="$3"
  shift 3

  _require_runner_adapter_lib
  spot_runner_wrapper_run_profiled_compat "${RUNNER_DIR}" "${config_path}" "${profile_name}" "${command_name}" "$@"
  return "$?"
}

run_submit_with_job() {
  local job_command="$1"
  shift

  local config_path="${RAV_GCP_ENV_PATH:-${RAV_GCP_ENV_DEFAULT}}"
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

  _run_profiled_with_config "${config_path}" "rav" "submit" \
    --job-command "${job_command}" \
    "${args[@]}"
}

run_ops_command() {
  local config_path="${RAV_GCP_ENV_PATH:-${RAV_GCP_ENV_DEFAULT}}"
  local args=("$@")
  if [[ ${#args[@]} -eq 0 ]]; then
    args=(status)
  fi

  _run_profiled_with_config "${config_path}" "rav" "ops" "${args[@]}"
}

run_build_command() {
  local config_path="${RAV_GCP_ENV_PATH:-${RAV_GCP_ENV_DEFAULT}}"
  local args=("$@")

  _run_profiled_with_config "${config_path}" "rav" "build" "${args[@]}"
}

run_monitor_command() {
  local config_path="${RAV_GCP_ENV_PATH:-${RAV_GCP_ENV_DEFAULT}}"
  local args=("$@")

  _run_profiled_with_config "${config_path}" "rav" "monitor" "${args[@]}"
}

run_version_command() {
  local config_path="${RAV_GCP_ENV_PATH:-}"
  run_spotctl_with_config "${config_path}" version "$@"
}
