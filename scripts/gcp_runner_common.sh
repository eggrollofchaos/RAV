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
  run_project_command "active" "ops" "$@"
}

run_submit_with_job() {
  local job_command="$1"
  shift

  run_project_command "active" "submit_with_job" "${job_command}" "$@"
}

run_build_command() {
  run_project_command "active" "build" "$@"
}

run_monitor_command() {
  run_project_command "active" "monitor" "$@"
}

run_version_command() {
  run_project_command "loaded" "version" "$@"
}

run_project_command() {
  local config_mode="$1"
  local command_name="$2"
  shift 2 || true

  if declare -F spot_runner_wrapper_run_project_standard_command_required >/dev/null 2>&1; then
    spot_runner_wrapper_run_project_standard_command_required \
      "${RUNNER_DIR}" \
      "${RUNNER_HINT_MESSAGE}" \
      "RUNNER_ADAPTER_LIB_LOADED" \
      "${config_mode}" \
      "${RAV_GCP_ENV_PATH:-}" \
      "${RAV_GCP_ENV_DEFAULT}" \
      "${RUNNER_PROFILE}" \
      "${command_name}" \
      "$@"
    return "$?"
  fi

  spot_runner_wrapper_run_project_command_with_mode_required \
    "${RUNNER_DIR}" \
    "${RUNNER_HINT_MESSAGE}" \
    "RUNNER_ADAPTER_LIB_LOADED" \
    "${config_mode}" \
    "${RAV_GCP_ENV_PATH:-}" \
    "${RAV_GCP_ENV_DEFAULT}" \
    "${RUNNER_PROFILE}" \
    "${command_name}" \
    "$@"
}

run_reconciler_deploy() {
  if declare -F spot_runner_wrapper_run_project_standard_command_required >/dev/null 2>&1 || \
    declare -F spot_runner_wrapper_run_project_command_with_mode_required >/dev/null 2>&1; then
    run_project_command "loaded" "reconciler_deploy" "$@"
    return "$?"
  fi

  spot_runner_wrapper_run_project_reconciler_deploy_with_loaded_config_required \
    "${RUNNER_DIR}" \
    "${RUNNER_HINT_MESSAGE}" \
    "RUNNER_ADAPTER_LIB_LOADED" \
    "${RAV_GCP_ENV_PATH:-}" \
    "${RAV_GCP_ENV_DEFAULT}" \
    "${RUNNER_PROFILE}" \
    "$@"
}
