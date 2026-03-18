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

spot_runner_bootstrap_initialize_project_wrapper_from_default_candidates_required \
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

  spot_runner_wrapper_setup_project_profile_runtime_wrapper_defaults_for_common_required \
    "${RUNNER_HINT_MESSAGE}" \
    "${RAV_ROOT}" \
    "${RUNNER_BOOTSTRAP_DIR_DEFAULT}" \
    "${RUNNER_PROFILE}" \
    "RAV_GCP_ENV" \
    "${RAV_GCP_ENV_DEFAULT}" \
    "RAV_GCP_ENV_PATH" \
    "${env_mode}" \
    "${missing_env_message}" \
    "${require_spot_vars}" \
    "${configure_gcloud}"
}

prepare_submit_shell() {
  spot_runner_wrapper_prepare_project_submit_shell_for_profile_wrapper_defaults_for_common_required \
    "${RUNNER_HINT_MESSAGE}" \
    "${RUNNER_PROFILE}" \
    "$@"
}

run_submit_entrypoint_with_job() {
  local job_command="$1"
  shift || true

  spot_runner_wrapper_run_project_submit_wrapper_defaults_for_common_required \
    "${RUNNER_HINT_MESSAGE:-Set RUNNER_DIR to your gcp-spot-runner checkout.}" \
    "prepare_submit_shell" \
    "" \
    "run_submit_with_job" \
    "${job_command}" \
    -- \
    "$@"
}

prepare_rav_submit_runtime_and_print_context() {
  local submit_label="$1"
  local config_path="${2:-}"

  prepare_rav_runtime "required" "1" "1"

  echo "Submitting ${submit_label} via spot runner..."
  if [[ -n "${config_path}" ]]; then
    echo "Config: ${config_path}"
  fi
  echo "Runner: ${RUNNER_DIR}"
  echo "Image:  ${IMAGE}"
  echo "Bucket: ${BUCKET}"
  if [[ -n "${CLOUDSDK_PYTHON:-}" ]]; then
    echo "gcloud Python: ${CLOUDSDK_PYTHON}"
  fi
}

run_submit_with_job() {
  local job_command="$1"
  shift

  run_project_command "submit_with_job" "${job_command}" "$@"
}

run_build_command() {
  run_project_command "build" "$@"
}

run_project_command() {
  local command_name="$1"
  shift || true

  spot_runner_wrapper_run_project_profile_command_wrapper_defaults_for_common_required \
    "${RUNNER_DIR}" \
    "${RUNNER_HINT_MESSAGE}" \
    "RUNNER_ADAPTER_LIB_LOADED" \
    "${RUNNER_PROFILE}" \
    "${command_name}" \
    "${RAV_GCP_ENV_PATH:-}" \
    "${RAV_GCP_ENV_DEFAULT}" \
    "$@"
}

run_rav_standard_command_wrapper() {
  spot_runner_wrapper_run_project_standard_wrapper_defaults_for_common_required \
    "${RUNNER_HINT_MESSAGE:-Set RUNNER_DIR to your gcp-spot-runner checkout.}" \
    "prepare_rav_runtime" \
    "run_project_command" \
    "${RUNNER_PROFILE}" \
    "$@"
}

run_rav_build_wrapper() {
  prepare_rav_runtime "required" "1" "1"

  echo "Building/pushing image: ${IMAGE}"
  echo "Project: ${PROJECT} | Region: ${REGION}"
  if [[ -n "${CLOUDSDK_PYTHON:-}" ]]; then
    echo "gcloud Python: ${CLOUDSDK_PYTHON}"
  fi
  local source_staging_dir="${GCS_SOURCE_STAGING_DIR:-gs://${BUCKET}/cloudbuild/source}"
  echo "Source staging dir: ${source_staging_dir}"

  spot_runner_wrapper_run_project_build_wrapper_defaults_for_common_required \
    "${RUNNER_HINT_MESSAGE:-Set RUNNER_DIR to your gcp-spot-runner checkout.}" \
    "" \
    "run_project_command" \
    "${RAV_ROOT}" \
    "${RAV_ROOT}/gcp/cloudbuild.rav.yaml" \
    "${IMAGE}" \
    -- \
    --gcs-source-staging-dir "${source_staging_dir}" \
    "$@"

  echo "Build complete: ${IMAGE}"
}
