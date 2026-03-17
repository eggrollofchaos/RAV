#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAV_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

RAV_GCP_ENV_DEFAULT="${RAV_ROOT}/gcp/rav_spot.env"
RUNNER_DIR_DEFAULT_PRIMARY="${RAV_ROOT}/../gcp-spot-runner"
RUNNER_DIR_DEFAULT_WORKTREE="${RAV_ROOT}/../gcp-spot-runner-codex"
RAV_GCP_ENV_PATH=""
RUNNER_ADAPTER_LIB_LOADED="0"
RUNNER_PROFILE="rav"
RUNNER_BOOTSTRAP_DIR_DEFAULT="${RUNNER_DIR_DEFAULT_PRIMARY}"
RUNNER_HINT_DEFAULT="Set RUNNER_DIR in gcp/rav_spot.env to your gcp-spot-runner checkout."
RUNNER_HINT_MESSAGE="${RUNNER_HINT_DEFAULT}"

_bootstrap_runner_adapter_lib() {
  local bootstrap_lib=""
  local candidate=""
  for candidate in "${RUNNER_DIR:-}" "${RUNNER_DIR_DEFAULT_PRIMARY}" "${RUNNER_DIR_DEFAULT_WORKTREE}"; do
    [[ -n "${candidate}" ]] || continue
    if [[ "${candidate}" != /* ]]; then
      candidate="${RAV_ROOT}/${candidate}"
    fi
    bootstrap_lib="${candidate}/adapters/spot_runner_bootstrap.sh"
    if [[ -f "${bootstrap_lib}" ]]; then
      break
    fi
  done

  if [[ -n "${bootstrap_lib}" && -f "${bootstrap_lib}" ]]; then
    # shellcheck disable=SC1090
    source "${bootstrap_lib}"
  fi

  spot_runner_bootstrap_initialize_project_wrapper_from_candidates_required \
    "${RAV_ROOT}" \
    "${RUNNER_PROFILE}" \
    "${RUNNER_HINT_DEFAULT}" \
    RUNNER_BOOTSTRAP_DIR_DEFAULT \
    "RUNNER_DIR" \
    RUNNER_HINT_MESSAGE \
    "${RUNNER_DIR_DEFAULT_PRIMARY}" \
    "${RUNNER_DIR_DEFAULT_WORKTREE}"
}

_bootstrap_runner_adapter_lib

load_rav_spot_env_optional() {
  spot_runner_wrapper_load_project_env_optional_compat "${RAV_ROOT}" "RAV_GCP_ENV" "${RAV_GCP_ENV_DEFAULT}" RAV_GCP_ENV_PATH "${RUNNER_HINT_MESSAGE}"
}

load_rav_spot_env() {
  spot_runner_wrapper_load_project_env_required_compat_or_exit \
    "${RAV_ROOT}" \
    "RAV_GCP_ENV" \
    "${RAV_GCP_ENV_DEFAULT}" \
    RAV_GCP_ENV_PATH \
    "${RUNNER_HINT_MESSAGE}" \
    "Copy gcp/rav_spot.env.example to gcp/rav_spot.env and fill it."
}

apply_runner_defaults() {
  spot_runner_wrapper_apply_project_runner_defaults_required \
    "${RAV_ROOT}" \
    "${RUNNER_BOOTSTRAP_DIR_DEFAULT}" \
    "RUNNER_DIR" \
    "RUNNER_DIR" \
    "${RUNNER_PROFILE}" \
    "${RUNNER_HINT_MESSAGE}"
}

check_runner_install() {
  spot_runner_wrapper_require_project_install_for_profile_compat_or_exit "${RUNNER_DIR}" "${RUNNER_PROFILE}" "${RUNNER_HINT_MESSAGE}"
}

prepare_rav_runtime() {
  local env_mode="${1:-required}"
  local require_spot_vars="${2:-1}"
  local configure_gcloud="${3:-1}"
  local missing_env_message="${4:-Copy gcp/rav_spot.env.example to gcp/rav_spot.env and fill it.}"

  spot_runner_wrapper_setup_project_runtime_required \
    "${RAV_ROOT}" \
    "${RUNNER_BOOTSTRAP_DIR_DEFAULT}" \
    "RUNNER_DIR" \
    "RUNNER_DIR" \
    "${RUNNER_PROFILE}" \
    "${RUNNER_HINT_MESSAGE}" \
    "${env_mode}" \
    "RAV_GCP_ENV" \
    "${RAV_GCP_ENV_DEFAULT}" \
    "RAV_GCP_ENV_PATH" \
    "${missing_env_message}" \
    "${require_spot_vars}" \
    "${configure_gcloud}" \
    "${RAV_ROOT}"
}

_active_config_path() {
  spot_runner_wrapper_resolve_active_config_path_required \
    "${RAV_GCP_ENV_PATH:-}" \
    "${RAV_GCP_ENV_DEFAULT}" \
    "1" \
    "${RUNNER_HINT_MESSAGE}"
}

_loaded_config_path() {
  spot_runner_wrapper_resolve_loaded_config_path_required \
    "${RAV_GCP_ENV_PATH:-}" \
    "${RAV_GCP_ENV_DEFAULT}" \
    "${RUNNER_HINT_MESSAGE}"
}

prepare_submit_shell() {
  local guard_alias_csv="${1:-_IXQT_CAFFEINATED}"
  shift || true
  spot_runner_wrapper_prepare_project_submit_shell_entrypoint_required \
    "${RUNNER_HINT_MESSAGE}" \
    "${guard_alias_csv}" \
    "$@"
}

configure_gcloud_runtime() {
  spot_runner_wrapper_configure_gcloud_runtime "${RUNNER_DIR}" "${RAV_ROOT}"
}

check_required_spot_vars() {
  spot_runner_wrapper_check_required_spot_vars
}

run_spotctl_with_config() {
  local config_path="$1"
  shift
  spot_runner_wrapper_run_project_spotctl_with_config "${RUNNER_DIR}" "${RUNNER_HINT_MESSAGE}" "RUNNER_ADAPTER_LIB_LOADED" "${config_path}" "$@"
}

run_ops_command() {
  local config_path
  config_path="$(_active_config_path)"
  spot_runner_wrapper_run_project_ops "${RUNNER_DIR}" "${RUNNER_HINT_MESSAGE}" "RUNNER_ADAPTER_LIB_LOADED" "${config_path}" "${RUNNER_PROFILE}" "$@"
}

run_submit_with_job() {
  local job_command="$1"
  shift

  local config_path
  config_path="$(_active_config_path)"
  spot_runner_wrapper_run_project_submit_with_job_compat \
    "${RUNNER_DIR}" \
    "${RUNNER_HINT_MESSAGE}" \
    "RUNNER_ADAPTER_LIB_LOADED" \
    "${config_path}" \
    "${RUNNER_PROFILE}" \
    "${job_command}" \
    "$@"
}

run_build_command() {
  local config_path
  config_path="$(_active_config_path)"
  spot_runner_wrapper_run_project_build_with_config \
    "${RUNNER_DIR}" \
    "${RUNNER_HINT_MESSAGE}" \
    "RUNNER_ADAPTER_LIB_LOADED" \
    "${config_path}" \
    "${RUNNER_PROFILE}" \
    "$@"
}

run_monitor_command() {
  local config_path
  config_path="$(_active_config_path)"
  spot_runner_wrapper_run_project_monitor_with_config \
    "${RUNNER_DIR}" \
    "${RUNNER_HINT_MESSAGE}" \
    "RUNNER_ADAPTER_LIB_LOADED" \
    "${config_path}" \
    "${RUNNER_PROFILE}" \
    "$@"
}

run_version_command() {
  local config_path
  config_path="$(_loaded_config_path)"
  spot_runner_wrapper_run_project_version "${RUNNER_DIR}" "${RUNNER_HINT_MESSAGE}" "RUNNER_ADAPTER_LIB_LOADED" "${config_path}" "$@"
}

run_reconciler_deploy() {
  spot_runner_wrapper_run_project_reconciler_deploy_with_loaded_config_required \
    "${RUNNER_DIR}" \
    "${RUNNER_HINT_MESSAGE}" \
    "RUNNER_ADAPTER_LIB_LOADED" \
    "${RAV_GCP_ENV_PATH:-}" \
    "${RAV_GCP_ENV_DEFAULT}" \
    "${RUNNER_PROFILE}" \
    "$@"
}
