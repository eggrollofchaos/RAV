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
  local candidate=""
  local bootstrap_lib=""
  local candidates=()

  if [[ -n "${RUNNER_DIR:-}" ]]; then
    candidates+=("${RUNNER_DIR}")
  fi
  candidates+=("${RUNNER_DIR_DEFAULT_PRIMARY}" "${RUNNER_DIR_DEFAULT_WORKTREE}")

  for candidate in "${candidates[@]}"; do
    [[ -n "${candidate}" ]] || continue
    if [[ "${candidate}" != /* ]]; then
      candidate="${RAV_ROOT}/${candidate}"
    fi
    bootstrap_lib="${candidate}/adapters/spot_runner_bootstrap.sh"
    if [[ ! -f "${bootstrap_lib}" ]]; then
      continue
    fi
    # shellcheck disable=SC1090
    source "${bootstrap_lib}"
    break
  done

  if declare -F spot_runner_bootstrap_initialize_wrapper_entrypoint_compat_or_fallback >/dev/null 2>&1; then
    spot_runner_bootstrap_initialize_wrapper_entrypoint_compat_or_fallback "${RAV_ROOT}" RUNNER_BOOTSTRAP_DIR_DEFAULT "RUNNER_DIR" "${RUNNER_DIR_DEFAULT_PRIMARY}" "${RUNNER_DIR_DEFAULT_WORKTREE}" && return 0
  fi
  if declare -F spot_runner_bootstrap_initialize_wrapper_compat >/dev/null 2>&1; then
    spot_runner_bootstrap_initialize_wrapper_compat "${RAV_ROOT}" RUNNER_BOOTSTRAP_DIR_DEFAULT "RUNNER_DIR" "${RUNNER_DIR_DEFAULT_PRIMARY}" "${RUNNER_DIR_DEFAULT_WORKTREE}" && return 0
  fi
}

_bootstrap_runner_adapter_lib

if declare -F spot_runner_wrapper_assign_profile_hint_entrypoint_compat_or_fallback >/dev/null 2>&1; then
  spot_runner_wrapper_assign_profile_hint_entrypoint_compat_or_fallback "${RUNNER_PROFILE}" "${RUNNER_HINT_DEFAULT}" RUNNER_HINT_MESSAGE
elif declare -F spot_runner_wrapper_assign_profile_hint_compat >/dev/null 2>&1; then
  spot_runner_wrapper_assign_profile_hint_compat "${RUNNER_PROFILE}" "${RUNNER_HINT_DEFAULT}" RUNNER_HINT_MESSAGE
fi

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
  spot_runner_wrapper_resolve_project_runner_dir_compat_or_exit "${RAV_ROOT}" "${RUNNER_BOOTSTRAP_DIR_DEFAULT}" "RUNNER_DIR" RUNNER_DIR "${RUNNER_HINT_MESSAGE}"

  if [[ "$(type -t spot_runner_wrapper_apply_rav_defaults || true)" != "function" ]]; then
    echo "Runner helper missing required function: spot_runner_wrapper_apply_rav_defaults" >&2
    echo "${RUNNER_HINT_MESSAGE}" >&2
    exit 1
  fi
  spot_runner_wrapper_apply_rav_defaults
}

check_runner_install() {
  spot_runner_wrapper_require_project_install_for_profile_compat_or_exit "${RUNNER_DIR}" "${RUNNER_PROFILE}" "${RUNNER_HINT_MESSAGE}"
}

prepare_submit_shell() {
  local guard_alias_csv="${1:-_IXQT_CAFFEINATED}"
  shift || true
  if declare -F spot_runner_wrapper_prepare_project_submit_shell_entrypoint_compat_or_fallback >/dev/null 2>&1; then
    spot_runner_wrapper_prepare_project_submit_shell_entrypoint_compat_or_fallback "${guard_alias_csv}" "$@"
    return "$?"
  fi
  if declare -F spot_runner_wrapper_prepare_project_submit_shell_entrypoint_compat >/dev/null 2>&1; then
    spot_runner_wrapper_prepare_project_submit_shell_entrypoint_compat "${guard_alias_csv}" "$@"
    return "$?"
  fi
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

_run_profiled_with_config() {
  local config_path="$1"
  local profile_name="$2"
  local command_name="$3"
  shift 3

  spot_runner_wrapper_run_project_profiled_with_config "${RUNNER_DIR}" "${RUNNER_HINT_MESSAGE}" "RUNNER_ADAPTER_LIB_LOADED" "${config_path}" "${profile_name}" "${command_name}" "$@"
}

run_submit_with_job() {
  local job_command="$1"
  shift

  local config_path="${RAV_GCP_ENV_PATH:-${RAV_GCP_ENV_DEFAULT}}"
  spot_runner_wrapper_run_project_submit_with_job_compat \
    "${RUNNER_DIR}" \
    "${RUNNER_HINT_MESSAGE}" \
    "RUNNER_ADAPTER_LIB_LOADED" \
    "${config_path}" \
    "rav" \
    "${job_command}" \
    "$@"
}

run_ops_command() {
  local config_path="${RAV_GCP_ENV_PATH:-${RAV_GCP_ENV_DEFAULT}}"
  spot_runner_wrapper_run_project_ops "${RUNNER_DIR}" "${RUNNER_HINT_MESSAGE}" "RUNNER_ADAPTER_LIB_LOADED" "${config_path}" "rav" "$@"
}

run_build_command() {
  local config_path="${RAV_GCP_ENV_PATH:-${RAV_GCP_ENV_DEFAULT}}"
  spot_runner_wrapper_run_project_profiled_command "${RUNNER_DIR}" "${RUNNER_HINT_MESSAGE}" "RUNNER_ADAPTER_LIB_LOADED" "${config_path}" "rav" "build" "$@"
}

run_monitor_command() {
  local config_path="${RAV_GCP_ENV_PATH:-${RAV_GCP_ENV_DEFAULT}}"
  spot_runner_wrapper_run_project_profiled_command "${RUNNER_DIR}" "${RUNNER_HINT_MESSAGE}" "RUNNER_ADAPTER_LIB_LOADED" "${config_path}" "rav" "monitor" "$@"
}

run_version_command() {
  local config_path="${RAV_GCP_ENV_PATH:-}"
  spot_runner_wrapper_run_project_version "${RUNNER_DIR}" "${RUNNER_HINT_MESSAGE}" "RUNNER_ADAPTER_LIB_LOADED" "${config_path}" "$@"
}
