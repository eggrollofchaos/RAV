#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAV_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

RAV_GCP_ENV_DEFAULT="${RAV_ROOT}/gcp/rav_spot.env"
RUNNER_DIR_DEFAULT="${RAV_ROOT}/../gcp-spot-runner"

load_rav_spot_env() {
  local cfg="${RAV_GCP_ENV:-${RAV_GCP_ENV_DEFAULT}}"
  if [[ ! -f "$cfg" ]]; then
    echo "Missing ${cfg}. Copy gcp/rav_spot.env.example to gcp/rav_spot.env and fill it." >&2
    exit 1
  fi
  set -a
  # shellcheck disable=SC1090
  source "$cfg"
  set +a
}

apply_runner_defaults() {
  : "${RUNNER_DIR:=${RUNNER_DIR_DEFAULT}}"
  if [[ "${RUNNER_DIR}" != /* ]]; then
    RUNNER_DIR="${RAV_ROOT}/${RUNNER_DIR}"
  fi
  RUNNER_DIR="$(cd "${RUNNER_DIR}" && pwd)"
  : "${ZONE:=us-east1-c}"
  if ! declare -p FALLBACK_ZONES >/dev/null 2>&1; then
    FALLBACK_ZONES=("us-east1-b" "us-east1-c" "us-east1-d")
  fi
  : "${MACHINE_TYPE:=n1-standard-8}"
  : "${GPU_TYPE:=nvidia-tesla-t4}"
  : "${BOOT_DISK_SIZE:=100}"
  : "${BOOT_DISK_TYPE:=pd-ssd}"
  : "${CONTAINER_NAME:=rav-trainer}"
  : "${CONDA_ENV:=}"
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
  local required=(
    submit.sh
    ops.sh
    lib.sh
    startup.sh
  )
  local file
  for file in "${required[@]}"; do
    if [[ ! -f "${RUNNER_DIR}/${file}" ]]; then
      echo "Runner file missing: ${RUNNER_DIR}/${file}" >&2
      echo "Set RUNNER_DIR in gcp/rav_spot.env to your gcp-spot-runner checkout." >&2
      exit 1
    fi
  done
}

_emit_var() {
  local cfg="$1"
  local name="$2"
  local value="${!name-}"
  printf '%s=%q\n' "$name" "$value" >> "$cfg"
}

write_runner_config() {
  local cfg="$1"
  local job_command="$2"

  : > "$cfg"
  _emit_var "$cfg" PROJECT
  _emit_var "$cfg" REGION
  _emit_var "$cfg" SA
  _emit_var "$cfg" IMAGE
  _emit_var "$cfg" BUCKET
  _emit_var "$cfg" ZONE
  _emit_var "$cfg" MACHINE_TYPE
  _emit_var "$cfg" GPU_TYPE
  _emit_var "$cfg" BOOT_DISK_SIZE
  _emit_var "$cfg" BOOT_DISK_TYPE
  _emit_var "$cfg" CONTAINER_NAME
  _emit_var "$cfg" CONDA_ENV
  _emit_var "$cfg" MAX_RUNTIME_SEC
  _emit_var "$cfg" POLL_INTERVAL
  _emit_var "$cfg" HEARTBEAT_STALE_SEC
  _emit_var "$cfg" HEARTBEAT_STALE_MAX
  _emit_var "$cfg" PROGRESS_STALL_POLLS
  _emit_var "$cfg" MAX_RESTARTS
  _emit_var "$cfg" RESTART_BACKOFF_SEC
  _emit_var "$cfg" WALL_CLOCK_DEADLINE
  _emit_var "$cfg" DEADLINE_TZ
  _emit_var "$cfg" OWNER_LOCK_STALE_SEC
  _emit_var "$cfg" METADATA_PREFIX
  _emit_var "$cfg" RUNNER_LABEL
  _emit_var "$cfg" LOG_LEVEL
  _emit_var "$cfg" DISCORD_WEBHOOK_URL

  printf 'FALLBACK_ZONES=(' >> "$cfg"
  local zone
  for zone in "${FALLBACK_ZONES[@]}"; do
    printf '%q ' "$zone" >> "$cfg"
  done
  printf ')\n' >> "$cfg"
  printf 'JOB_COMMAND=%q\n' "$job_command" >> "$cfg"
}

run_submit_with_job() {
  local job_command="$1"
  shift

  local tmp_dir
  tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/rav-spot-submit-XXXXXX")"

  local file
  for file in submit.sh lib.sh startup.sh cloudbuild.yaml entrypoint.sh Dockerfile; do
    if [[ -f "${RUNNER_DIR}/${file}" ]]; then
      ln -s "${RUNNER_DIR}/${file}" "${tmp_dir}/${file}"
    fi
  done

  write_runner_config "${tmp_dir}/config.env" "$job_command"

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

  set +e
  (
    cd "$tmp_dir"
    ./submit.sh "${args[@]}"
  )
  local status=$?
  set -e
  rm -rf "$tmp_dir"
  return "$status"
}

run_ops_command() {
  local tmp_dir
  tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/rav-spot-ops-XXXXXX")"

  local file
  for file in ops.sh lib.sh; do
    ln -s "${RUNNER_DIR}/${file}" "${tmp_dir}/${file}"
  done

  write_runner_config "${tmp_dir}/config.env" "${JOB_COMMAND:-echo noop}"

  local args=("$@")
  if [[ ${#args[@]} -eq 0 ]]; then
    args=(status)
  fi

  set +e
  (
    cd "$tmp_dir"
    ./ops.sh "${args[@]}"
  )
  local status=$?
  set -e
  rm -rf "$tmp_dir"
  return "$status"
}
