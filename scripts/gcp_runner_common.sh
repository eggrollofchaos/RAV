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

RUNNER_BOOTSTRAP_ENV_CANDIDATE="${RUNNER_DIR:-}"
if [[ -n "${RUNNER_BOOTSTRAP_ENV_CANDIDATE}" && "${RUNNER_BOOTSTRAP_ENV_CANDIDATE}" != /* ]]; then
  RUNNER_BOOTSTRAP_ENV_CANDIDATE="${RAV_ROOT}/${RUNNER_BOOTSTRAP_ENV_CANDIDATE}"
fi

RUNNER_BOOTSTRAP_LIB=""
for RUNNER_BOOTSTRAP_CANDIDATE in "${RUNNER_BOOTSTRAP_ENV_CANDIDATE}" "${RUNNER_DIR_DEFAULT_PRIMARY}" "${RUNNER_DIR_DEFAULT_WORKTREE}"; do
  [[ -n "${RUNNER_BOOTSTRAP_CANDIDATE}" ]] || continue
  RUNNER_BOOTSTRAP_LIB="${RUNNER_BOOTSTRAP_CANDIDATE}/adapters/spot_runner_bootstrap.sh"
  if [[ -f "${RUNNER_BOOTSTRAP_LIB}" ]]; then
    # shellcheck disable=SC1090
    source "${RUNNER_BOOTSTRAP_LIB}"
    break
  fi
done

spot_runner_bootstrap_initialize_project_wrapper_from_candidates_required \
  "${RAV_ROOT}" \
  "${RUNNER_PROFILE}" \
  "${RUNNER_HINT_DEFAULT}" \
  RUNNER_BOOTSTRAP_DIR_DEFAULT \
  "RUNNER_DIR" \
  RUNNER_HINT_MESSAGE \
  "${RUNNER_DIR_DEFAULT_PRIMARY}" \
  "${RUNNER_DIR_DEFAULT_WORKTREE}"

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

prepare_submit_shell() {
  local guard_alias_csv="${1:-_IXQT_CAFFEINATED}"
  shift || true
  spot_runner_wrapper_prepare_project_submit_shell_entrypoint_required \
    "${RUNNER_HINT_MESSAGE}" \
    "${guard_alias_csv}" \
    "$@"
}

run_ops_command() {
  local config_path
  config_path="$(spot_runner_wrapper_resolve_config_path_required \
    "active" \
    "${RAV_GCP_ENV_PATH:-}" \
    "${RAV_GCP_ENV_DEFAULT}" \
    "${RUNNER_HINT_MESSAGE}")"
  spot_runner_wrapper_run_project_ops "${RUNNER_DIR}" "${RUNNER_HINT_MESSAGE}" "RUNNER_ADAPTER_LIB_LOADED" "${config_path}" "${RUNNER_PROFILE}" "$@"
}

run_submit_with_job() {
  local job_command="$1"
  shift

  local config_path
  config_path="$(spot_runner_wrapper_resolve_config_path_required \
    "active" \
    "${RAV_GCP_ENV_PATH:-}" \
    "${RAV_GCP_ENV_DEFAULT}" \
    "${RUNNER_HINT_MESSAGE}")"
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
  config_path="$(spot_runner_wrapper_resolve_config_path_required \
    "active" \
    "${RAV_GCP_ENV_PATH:-}" \
    "${RAV_GCP_ENV_DEFAULT}" \
    "${RUNNER_HINT_MESSAGE}")"
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
  config_path="$(spot_runner_wrapper_resolve_config_path_required \
    "active" \
    "${RAV_GCP_ENV_PATH:-}" \
    "${RAV_GCP_ENV_DEFAULT}" \
    "${RUNNER_HINT_MESSAGE}")"
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
  config_path="$(spot_runner_wrapper_resolve_config_path_required \
    "loaded" \
    "${RAV_GCP_ENV_PATH:-}" \
    "${RAV_GCP_ENV_DEFAULT}" \
    "${RUNNER_HINT_MESSAGE}")"
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
