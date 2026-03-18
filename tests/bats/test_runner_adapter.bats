#!/usr/bin/env bats
# tests/bats/test_runner_adapter.bats — adapter contract tests for RAV wrappers.

load test_helper

CAPTURE_PATH=""

_capture_stub() {
  CAPTURE_PATH="$1"
  spot_runner_wrapper_require_project_runtime_or_exit() { :; }
  spot_runner_wrapper_apply_rav_defaults() {
    : "${DATA_DISK_ENABLED:=true}"
    : "${DATA_DISK_MOUNT_PATH:=/var/lib/spot-data}"
    : "${DATA_DISK_DEVICE_NAME:=spot-data}"
    : "${DATA_DISK_FS_TYPE:=ext4}"
  }
  spot_runner_wrapper_apply_rav_defaults_required() {
    local _hint_message="${1:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
    spot_runner_wrapper_apply_rav_defaults
  }
  spot_runner_wrapper_setup_project_runtime_required() {
    local project_root="$1"
    local default_runner_dir="$2"
    local runner_env_var_name="$3"
    local runner_output_var_name="$4"
    local profile_name="$5"
    local hint_message="${6:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
    local env_mode="${7:-optional}"
    local env_var_name="${8:-RAV_GCP_ENV}"
    local default_env_path="${9:-}"
    local output_env_var_name="${10:-RAV_GCP_ENV_PATH}"

    if [[ "${env_mode}" == "required" ]]; then
      spot_runner_wrapper_load_project_env_required_compat_or_exit \
        "${project_root}" \
        "${env_var_name}" \
        "${default_env_path}" \
        "${output_env_var_name}" \
        "${hint_message}"
    else
      spot_runner_wrapper_load_project_env_optional_compat \
        "${project_root}" \
        "${env_var_name}" \
        "${default_env_path}" \
        "${output_env_var_name}" \
        "${hint_message}"
    fi

    spot_runner_wrapper_apply_project_runner_defaults_required \
      "${project_root}" \
      "${default_runner_dir}" \
      "${runner_env_var_name}" \
      "${runner_output_var_name}" \
      "${profile_name}" \
      "${hint_message}"
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
  spot_runner_wrapper_run_project_profile_command_wrapper_defaults_required() {
    local runner_dir="$1"
    local hint_message="${2:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
    local loaded_var_name="${3:-RUNNER_ADAPTER_LIB_LOADED}"
    local profile_name="${4:-default}"
    local command_name="${5:-}"
    local current_config_path="${6:-}"
    local default_config_path="${7:-}"
    shift 7 || true
    spot_runner_wrapper_run_project_profile_command_with_paths_required \
      "${runner_dir}" \
      "${hint_message}" \
      "${loaded_var_name}" \
      "${profile_name}" \
      "${command_name}" \
      "${current_config_path}" \
      "${default_config_path}" \
      "$@"
  }
  spot_runner_wrapper_setup_project_profile_runtime_required() {
    local project_root="$1"
    local default_runner_dir="$2"
    local hint_message="${3:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
    local profile_name="${4:-default}"
    local env_var_name="${5:-RAV_GCP_ENV}"
    local default_env_path="${6:-}"
    local output_env_var_name="${7:-RAV_GCP_ENV_PATH}"
    local env_mode="${8:-optional}"
    local missing_env_message="${9:-Missing required project environment file.}"
    local require_spot_vars="${10:-0}"
    local configure_gcloud="${11:-0}"
    local gcloud_project_root="${12:-${project_root}}"
    if [[ $# -gt 12 ]]; then
      shift 12
    else
      set --
    fi
    spot_runner_wrapper_setup_project_runtime_required \
      "${project_root}" \
      "${default_runner_dir}" \
      "RUNNER_DIR" \
      "RUNNER_DIR" \
      "${profile_name}" \
      "${hint_message}" \
      "${env_mode}" \
      "${env_var_name}" \
      "${default_env_path}" \
      "${output_env_var_name}" \
      "${missing_env_message}" \
      "${require_spot_vars}" \
      "${configure_gcloud}" \
      "${gcloud_project_root}" \
      "$@"
  }
  run_spotctl_with_config() {
    printf '%s\n' "$@" > "$CAPTURE_PATH"
  }
  _require_runner_adapter_lib() { :; }
  spot_runner_wrapper_run_spotctl_compat() {
    local _runner_dir="$1"
    shift
    run_spotctl_with_config "$@"
  }
  spot_runner_wrapper_run_version_compat() {
    local _runner_dir="$1"
    local config_path="${2:-}"
    shift 2 || true
    run_spotctl_with_config "${config_path}" version "$@"
  }
  spot_runner_run_profiled_compat() {
    local _runner_dir="$1"
    local config_path="$2"
    local profile_name="$3"
    local command_name="$4"
    shift 4
    printf '%s\n' "$config_path" > "$CAPTURE_PATH"
    printf '%s\n' "$command_name" >> "$CAPTURE_PATH"
    printf '%s\n' "--profile" "$profile_name" >> "$CAPTURE_PATH"
    if [[ -n "$config_path" ]]; then
      printf '%s\n' "--config" "$config_path" >> "$CAPTURE_PATH"
    fi
    printf '%s\n' "$@" >> "$CAPTURE_PATH"
  }
  spot_runner_run_profiled() { spot_runner_run_profiled_compat "$@"; }
  spot_runner_wrapper_run_project_spotctl_with_config() {
    local _runner_dir="$1"
    local _hint_message="$2"
    local _loaded_var="$3"
    local config_path="$4"
    shift 4
    run_spotctl_with_config "$config_path" "$@"
  }
  spot_runner_wrapper_run_project_profiled_with_config() {
    local _runner_dir="$1"
    local _hint_message="$2"
    local _loaded_var="$3"
    local config_path="$4"
    local profile_name="$5"
    local command_name="$6"
    shift 6
    printf '%s\n' "$config_path" > "$CAPTURE_PATH"
    printf '%s\n' "$command_name" >> "$CAPTURE_PATH"
    printf '%s\n' "--profile" "$profile_name" >> "$CAPTURE_PATH"
    if [[ -n "$config_path" ]]; then
      printf '%s\n' "--config" "$config_path" >> "$CAPTURE_PATH"
    fi
    printf '%s\n' "$@" >> "$CAPTURE_PATH"
  }
  spot_runner_wrapper_run_project_submit_with_job_compat() {
    local runner_dir="$1"
    local hint_message="$2"
    local loaded_var_name="$3"
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
    spot_runner_wrapper_run_project_profiled_with_config \
      "$runner_dir" \
      "$hint_message" \
      "$loaded_var_name" \
      "$config_path" \
      "$profile_name" \
      "submit" \
      --job-command "$job_command" \
      "${args[@]}"
  }
  spot_runner_wrapper_run_project_ops() {
    local _runner_dir="$1"
    local _hint_message="$2"
    local _loaded_var="$3"
    local config_path="$4"
    local profile_name="$5"
    shift 5
    local args=("$@")
    if [[ ${#args[@]} -eq 0 ]]; then
      args=(status)
    fi
    spot_runner_wrapper_run_project_profiled_with_config \
      "$_runner_dir" "$_hint_message" "$_loaded_var" "$config_path" "$profile_name" "ops" "${args[@]}"
  }
  spot_runner_wrapper_run_project_profiled_command() {
    local _runner_dir="$1"
    local _hint_message="$2"
    local _loaded_var="$3"
    local config_path="$4"
    local profile_name="$5"
    local command_name="$6"
    shift 6
    spot_runner_wrapper_run_project_profiled_with_config \
      "$_runner_dir" "$_hint_message" "$_loaded_var" "$config_path" "$profile_name" "$command_name" "$@"
  }
  spot_runner_wrapper_run_project_build_with_config() {
    local _runner_dir="$1"
    local _hint_message="$2"
    local _loaded_var="$3"
    local config_path="$4"
    local profile_name="$5"
    shift 5
    spot_runner_wrapper_run_project_profiled_command \
      "$_runner_dir" "$_hint_message" "$_loaded_var" "$config_path" "$profile_name" "build" "$@"
  }
  spot_runner_wrapper_run_project_monitor_with_config() {
    local _runner_dir="$1"
    local _hint_message="$2"
    local _loaded_var="$3"
    local config_path="$4"
    local profile_name="$5"
    shift 5
    spot_runner_wrapper_run_project_profiled_command \
      "$_runner_dir" "$_hint_message" "$_loaded_var" "$config_path" "$profile_name" "monitor" "$@"
  }
  spot_runner_wrapper_run_project_version() {
    local _runner_dir="$1"
    local _hint_message="$2"
    local _loaded_var="$3"
    local config_path="$4"
    shift 4
    run_spotctl_with_config "$config_path" version "$@"
  }
  RUNNER_DIR="${RUNNER_DIR:-/tmp/fake-runner}"
}

@test "run_project_command ops delegates to shared profiled compat helper" {
  source "$REPO_ROOT/scripts/gcp_runner_common.sh"
  local captured="$BATS_TEST_TMPDIR/profiled_compat_args.txt"

  spot_runner_wrapper_run_project_ops() {
    printf '%s\n' "$@" > "$captured"
  }
  RUNNER_DIR="/tmp/fake-runner"
  RAV_GCP_ENV_PATH="/tmp/rav_spot.env"

  run_project_command ops watch 20 --json

  run cat "$captured"
  assert_success
  assert_line --index 0 "/tmp/fake-runner"
  assert_line --index 1 "Set RUNNER_DIR in gcp/rav_spot.env to your gcp-spot-runner checkout."
  assert_line --index 2 "RUNNER_ADAPTER_LIB_LOADED"
  assert_line --index 3 "/tmp/rav_spot.env"
  assert_line --index 4 "rav"
  assert_line --index 5 "watch"
  assert_line --index 6 "20"
  assert_line --index 7 "--json"
}

@test "prepare_submit_shell delegates to shared project helper when available" {
  source "$REPO_ROOT/scripts/gcp_runner_common.sh"
  local captured="$BATS_TEST_TMPDIR/prepare_project_submit_args.txt"

  spot_runner_wrapper_prepare_project_submit_shell_entrypoint_compat_or_fallback() {
    printf '%s\n' "$@" > "$captured"
  }

  prepare_submit_shell "_RAV_ITER_CAFFEINATED,_IXQT_CAFFEINATED" --run-id rav-caf-3 --dry-run

  run cat "$captured"
  assert_success
  assert_line --index 0 "_RAV_ITER_CAFFEINATED,_IXQT_CAFFEINATED"
  assert_line --index 1 "--run-id"
  assert_line --index 2 "rav-caf-3"
  assert_line --index 3 "--dry-run"
}

@test "prepare_submit_shell resolves rav default guard alias when none is provided" {
  source "$REPO_ROOT/scripts/gcp_runner_common.sh"
  local captured="$BATS_TEST_TMPDIR/prepare_project_submit_default_alias_args.txt"

  spot_runner_wrapper_prepare_project_submit_shell_entrypoint_compat_or_fallback() {
    printf '%s\n' "$@" > "$captured"
  }

  prepare_submit_shell --run-id rav-caf-4 --dry-run

  run cat "$captured"
  assert_success
  assert_line --index 0 "_RAV_CAFFEINATED,_IXQT_CAFFEINATED"
  assert_line --index 1 "--run-id"
  assert_line --index 2 "rav-caf-4"
  assert_line --index 3 "--dry-run"
}

@test "run_rav_build_wrapper delegates through shared build-wrapper common defaults helper" {
  source "$REPO_ROOT/scripts/gcp_runner_common.sh"
  local captured="$BATS_TEST_TMPDIR/build_wrapper_common_args.txt"
  local runtime_capture="$BATS_TEST_TMPDIR/build_wrapper_common_runtime_args.txt"

  prepare_rav_runtime() {
    printf '%s\n' "$@" > "$runtime_capture"
    IMAGE="us-east1-docker.pkg.dev/demo/rav/train:latest"
    PROJECT="demo-project"
    REGION="us-east1"
    BUCKET="demo-bucket"
  }
  spot_runner_wrapper_run_project_build_wrapper_defaults_for_common_required() {
    printf '%s\n' "$@" > "$captured"
  }

  run run_rav_build_wrapper --dry-run
  assert_success

  run cat "$runtime_capture"
  assert_success
  assert_line --index 0 "required"
  assert_line --index 1 "1"
  assert_line --index 2 "1"

  run cat "$captured"
  assert_success
  assert_line --index 0 "Set RUNNER_DIR in gcp/rav_spot.env to your gcp-spot-runner checkout."
  assert_line --index 1 "run_project_command"
  assert_line --index 2 "$REPO_ROOT"
  assert_line --index 3 "$REPO_ROOT/gcp/cloudbuild.rav.yaml"
  assert_line --index 4 "us-east1-docker.pkg.dev/demo/rav/train:latest"
  assert_line --index 5 -- "--"
  assert_line --index 6 "--gcs-source-staging-dir"
  assert_line --index 7 "gs://demo-bucket/cloudbuild/source"
  assert_line --index 8 "--dry-run"
}

_setup_temp_submit_wrappers() {
  export TEMP_REPO="$BATS_TEST_TMPDIR/repo"
  mkdir -p "$TEMP_REPO/scripts"
  cp "$REPO_ROOT/scripts/gcp_submit_primary.sh" "$TEMP_REPO/scripts/gcp_submit_primary.sh"
  cp "$REPO_ROOT/scripts/gcp_submit_poc.sh" "$TEMP_REPO/scripts/gcp_submit_poc.sh"
  cp "$REPO_ROOT/scripts/gcp_build_image.sh" "$TEMP_REPO/scripts/gcp_build_image.sh"
  cp "$REPO_ROOT/scripts/gcp_ops.sh" "$TEMP_REPO/scripts/gcp_ops.sh"
  cp "$REPO_ROOT/scripts/gcp_monitor.sh" "$TEMP_REPO/scripts/gcp_monitor.sh"
  cp "$REPO_ROOT/scripts/gcp_version.sh" "$TEMP_REPO/scripts/gcp_version.sh"
  cp "$REPO_ROOT/scripts/rav-gcp.sh" "$TEMP_REPO/scripts/rav-gcp.sh"
  chmod +x \
    "$TEMP_REPO/scripts/gcp_submit_primary.sh" \
    "$TEMP_REPO/scripts/gcp_submit_poc.sh" \
    "$TEMP_REPO/scripts/gcp_build_image.sh" \
    "$TEMP_REPO/scripts/gcp_ops.sh" \
    "$TEMP_REPO/scripts/gcp_monitor.sh" \
    "$TEMP_REPO/scripts/gcp_version.sh" \
    "$TEMP_REPO/scripts/rav-gcp.sh"
}

_make_caffeinate_stub() {
  local bin_dir="$1"
  mkdir -p "$bin_dir"
  cat > "$bin_dir/caffeinate" <<'CAFFEINATE_STUB'
#!/usr/bin/env bash
set -euo pipefail
printf 'CAFFEINATED=%s\n' "${_SPOT_CAFFEINATED:-}" > "${CAFFEINATE_LOG}"
printf '%s\n' "$@" >> "${CAFFEINATE_LOG}"
if [[ "${1:-}" == "-i" ]]; then
  shift
fi
exec "$@"
CAFFEINATE_STUB
  chmod +x "$bin_dir/caffeinate"
}

_write_fake_runner_common() {
  local log_path="$1"
  : > "$log_path"
cat > "$TEMP_REPO/scripts/gcp_runner_common.sh" <<SCRIPT
#!/usr/bin/env bash
set -euo pipefail
RAV_ROOT="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")/.." && pwd)"
load_rav_spot_env() { :; }
load_rav_spot_env_optional() { :; }
apply_runner_defaults() {
  : "\${RUNNER_DIR:=/tmp/fake-runner}"
  : "\${IMAGE:=us-east1-docker.pkg.dev/demo/rav/train:latest}"
  : "\${BUCKET:=demo-bucket}"
}
check_required_spot_vars() { :; }
check_runner_install() { :; }
configure_gcloud_runtime() { :; }
prepare_rav_runtime() {
  local env_mode="\${1:-required}"
  local require_spot_vars="\${2:-1}"
  local configure_gcloud="\${3:-1}"
  if [[ "\${env_mode}" == "required" ]]; then
    load_rav_spot_env
  else
    load_rav_spot_env_optional
  fi
  apply_runner_defaults
  if [[ "\${require_spot_vars}" == "1" ]]; then
    check_required_spot_vars
  fi
  check_runner_install
  if [[ "\${configure_gcloud}" == "1" ]]; then
    configure_gcloud_runtime
  fi
}
spot_runner_wrapper_run_project_build_entrypoint_required() {
  local _hint_message="\${1:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local runtime_function_name="\${2:-}"
  local build_function_name="\${3:-}"
  local source_path="\${4:-}"
  local cloudbuild_config_path="\${5:-}"
  local image_value="\${6:-}"
  shift 6 || true

  local runtime_args=()
  local build_passthrough_args=()
  local saw_delimiter=0
  while [[ \$# -gt 0 ]]; do
    if [[ "\$1" == "--" ]]; then
      saw_delimiter=1
      shift
      break
    fi
    runtime_args+=("\$1")
    shift
  done
  if [[ "\${saw_delimiter}" == "1" ]]; then
    build_passthrough_args=("\$@")
  else
    build_passthrough_args=("\${runtime_args[@]}")
    runtime_args=()
  fi

  local build_args=(
    --source "\${source_path}"
    --cloudbuild-config "\${cloudbuild_config_path}"
  )
  if [[ -n "\${image_value}" ]]; then
    build_args+=(--image "\${image_value}")
  fi
  build_args+=("\${build_passthrough_args[@]}")

  "\${runtime_function_name}" "\${runtime_args[@]}"
  "\${build_function_name}" "\${build_args[@]}"
}
spot_runner_wrapper_run_project_build_command_entrypoint_required() {
  local _hint_message="\${1:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local runtime_function_name="\${2:-}"
  local command_function_name="\${3:-}"
  local source_path="\${4:-}"
  local cloudbuild_config_path="\${5:-}"
  local image_value="\${6:-}"
  shift 6 || true

  local runtime_args=()
  local build_passthrough_args=()
  local saw_delimiter=0
  while [[ \$# -gt 0 ]]; do
    if [[ "\$1" == "--" ]]; then
      saw_delimiter=1
      shift
      break
    fi
    build_passthrough_args+=("\$1")
    shift
  done
  if [[ "\${saw_delimiter}" == "1" ]]; then
    runtime_args=("\${build_passthrough_args[@]}")
    build_passthrough_args=("\$@")
  fi
  if [[ -z "\${runtime_function_name}" && "\${saw_delimiter}" == "1" && "\${#runtime_args[@]}" -gt 0 ]]; then
    build_passthrough_args=("\${runtime_args[@]}" "\${build_passthrough_args[@]}")
    runtime_args=()
  fi

  local build_args=(
    --source "\${source_path}"
    --cloudbuild-config "\${cloudbuild_config_path}"
  )
  if [[ -n "\${image_value}" ]]; then
    build_args+=(--image "\${image_value}")
  fi
  build_args+=("\${build_passthrough_args[@]}")

  if [[ -n "\${runtime_function_name}" ]]; then
    "\${runtime_function_name}" "\${runtime_args[@]}"
  fi
  "\${command_function_name}" build "\${build_args[@]}"
}
spot_runner_wrapper_run_project_build_wrapper_defaults_required() {
  local _hint_message="\${1:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local runtime_function_name="\${2:-}"
  local command_function_name="\${3:-}"
  local source_path="\${4:-}"
  local cloudbuild_config_path="\${5:-}"
  local image_value="\${6:-}"
  shift 6 || true

  spot_runner_wrapper_run_project_build_command_entrypoint_required \
    "\${_hint_message}" \
    "\${runtime_function_name}" \
    "\${command_function_name}" \
    "\${source_path}" \
    "\${cloudbuild_config_path}" \
    "\${image_value}" \
    "\$@"
}
spot_runner_wrapper_run_project_build_wrapper_defaults_for_common_required() {
  local _hint_message="\${1:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local runtime_function_name="\${2:-}"
  local command_function_name="\${3:-}"
  local source_path="\${4:-}"
  local cloudbuild_config_path="\${5:-}"
  local image_value="\${6:-}"
  shift 6 || true

  spot_runner_wrapper_run_project_build_wrapper_defaults_required \
    "\${_hint_message}" \
    "\${runtime_function_name}" \
    "\${command_function_name}" \
    "\${source_path}" \
    "\${cloudbuild_config_path}" \
    "\${image_value}" \
    "\$@"
}
spot_runner_wrapper_run_project_command_entrypoint_required() {
  local _hint_message="\${1:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local runtime_function_name="\${2:-}"
  local command_function_name="\${3:-}"
  shift 3 || true

  local runtime_args=()
  local command_args=()
  local saw_delimiter=0
  while [[ \$# -gt 0 ]]; do
    if [[ "\$1" == "--" ]]; then
      saw_delimiter=1
      shift
      break
    fi
    runtime_args+=("\$1")
    shift
  done
  command_args=("\$@")

  if [[ -z "\${runtime_function_name}" && "\${saw_delimiter}" == "1" && "\${#runtime_args[@]}" -gt 0 ]]; then
    command_args=("\${runtime_args[@]}" "\${command_args[@]}")
    runtime_args=()
  fi

  if [[ -n "\${runtime_function_name}" ]]; then
    "\${runtime_function_name}" "\${runtime_args[@]}"
  fi
  "\${command_function_name}" "\${command_args[@]}"
}
spot_runner_wrapper_run_project_named_command_entrypoint_required() {
  local _hint_message="\${1:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local runtime_function_name="\${2:-}"
  local command_dispatch_function_name="\${3:-}"
  local command_name="\${4:-}"
  shift 4 || true

  local runtime_args=()
  local command_args=()
  local saw_delimiter=0
  while [[ \$# -gt 0 ]]; do
    if [[ "\$1" == "--" ]]; then
      saw_delimiter=1
      shift
      break
    fi
    runtime_args+=("\$1")
    shift
  done
  if [[ "\${saw_delimiter}" == "1" ]]; then
    command_args=("\$@")
  else
    command_args=("\${runtime_args[@]}")
    runtime_args=()
  fi

  "\${runtime_function_name}" "\${runtime_args[@]}"
  "\${command_dispatch_function_name}" "\${command_name}" "\${command_args[@]}"
}
spot_runner_wrapper_run_project_named_command_from_script_entrypoint_required() {
  local _hint_message="\${1:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local runtime_function_name="\${2:-}"
  local command_dispatch_function_name="\${3:-}"
  local script_path="\${4:-}"
  local script_prefix="\${5:-}"
  local script_suffix="\${6:-}"
  shift 6 || true

  local script_name="\${script_path##*/}"
  local command_name="\${script_name}"
  if [[ -n "\${script_prefix}" ]]; then
    command_name="\${command_name#"\${script_prefix}"}"
  fi
  if [[ -n "\${script_suffix}" ]]; then
    command_name="\${command_name%"\${script_suffix}"}"
  fi

  spot_runner_wrapper_run_project_named_command_entrypoint_required \
    "\${_hint_message}" \
    "\${runtime_function_name}" \
    "\${command_dispatch_function_name}" \
    "\${command_name}" \
    "\$@"
}
spot_runner_wrapper_run_project_profile_named_command_from_script_entrypoint_required() {
  local _hint_message="\${1:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local runtime_function_name="\${2:-}"
  local command_dispatch_function_name="\${3:-}"
  local script_path="\${4:-}"
  local script_prefix="\${5:-}"
  local script_suffix="\${6:-}"
  local profile_name="\${7:-}"
  shift 7 || true

  local script_name="\${script_path##*/}"
  local command_name="\${script_name}"
  if [[ -n "\${script_prefix}" ]]; then
    command_name="\${command_name#"\${script_prefix}"}"
  fi
  if [[ -n "\${script_suffix}" ]]; then
    command_name="\${command_name%"\${script_suffix}"}"
  fi

  local env_mode="required"
  local require_spot_vars="1"
  local configure_gcloud="1"
  case "\${profile_name}" in
    rav)
      if [[ "\${command_name}" == "version" ]]; then
        env_mode="optional"
        require_spot_vars="0"
        configure_gcloud="1"
      fi
      ;;
    ixqt)
      env_mode="optional"
      require_spot_vars="0"
      configure_gcloud="0"
      ;;
  esac

  "\${runtime_function_name}" "\${env_mode}" "\${require_spot_vars}" "\${configure_gcloud}"
  "\${command_dispatch_function_name}" "\${command_name}" "\$@"
}
spot_runner_wrapper_run_project_profile_named_command_for_callsite_entrypoint_required() {
  local _hint_message="\${1:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local runtime_function_name="\${2:-}"
  local command_dispatch_function_name="\${3:-}"
  local profile_name="\${4:-}"
  local script_prefix="\${5:-}"
  local script_suffix="\${6:-}"
  local callsite_depth="\${7:-2}"
  shift 7 || true

  local script_path="\${BASH_SOURCE[\${callsite_depth}]:-\$0}"
  spot_runner_wrapper_run_project_profile_named_command_from_script_entrypoint_required \
    "\${_hint_message}" \
    "\${runtime_function_name}" \
    "\${command_dispatch_function_name}" \
    "\${script_path}" \
    "\${script_prefix}" \
    "\${script_suffix}" \
    "\${profile_name}" \
    "\$@"
}
spot_runner_wrapper_standard_wrapper_naming_for_profile_required() {
  local profile_name="\${1:-}"
  local prefix_output_var="\${2:-}"
  local suffix_output_var="\${3:-}"

  local resolved_script_prefix=""
  local resolved_script_suffix=".sh"
  case "\${profile_name}" in
    ixqt)
      resolved_script_suffix="_spot.sh"
      ;;
    rav)
      resolved_script_prefix="gcp_"
      resolved_script_suffix=".sh"
      ;;
  esac

  printf -v "\${prefix_output_var}" '%s' "\${resolved_script_prefix}"
  printf -v "\${suffix_output_var}" '%s' "\${resolved_script_suffix}"
}
spot_runner_wrapper_run_project_standard_wrapper_defaults_required() {
  local _hint_message="\${1:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local runtime_function_name="\${2:-}"
  local command_dispatch_function_name="\${3:-}"
  local profile_name="\${4:-}"
  local callsite_depth="\${5:-2}"
  shift 5 || true
  local delegated_callsite_depth=\$((callsite_depth + 1))

  local script_prefix=""
  local script_suffix=""
  spot_runner_wrapper_standard_wrapper_naming_for_profile_required \
    "\${profile_name}" \
    script_prefix \
    script_suffix

  spot_runner_wrapper_run_project_profile_named_command_for_callsite_entrypoint_required \
    "\${_hint_message}" \
    "\${runtime_function_name}" \
    "\${command_dispatch_function_name}" \
    "\${profile_name}" \
    "\${script_prefix}" \
    "\${script_suffix}" \
    "\${delegated_callsite_depth}" \
    "\$@"
}
spot_runner_wrapper_run_project_standard_wrapper_defaults_for_common_required() {
  local _hint_message="\${1:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local runtime_function_name="\${2:-}"
  local command_dispatch_function_name="\${3:-}"
  local profile_name="\${4:-}"
  shift 4 || true

  spot_runner_wrapper_run_project_standard_wrapper_defaults_required \
    "\${_hint_message}" \
    "\${runtime_function_name}" \
    "\${command_dispatch_function_name}" \
    "\${profile_name}" \
    "3" \
    "\$@"
}
spot_runner_wrapper_run_project_submit_entrypoint_required() {
  local _hint_message="\${1:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local submit_shell_function_name="\${2:-}"
  local runtime_function_name="\${3:-}"
  local submit_function_name="\${4:-}"
  local job_command="\${5:-}"
  shift 5 || true

  local runtime_args=()
  local submit_args=()
  local saw_delimiter=0
  while [[ \$# -gt 0 ]]; do
    if [[ "\$1" == "--" ]]; then
      saw_delimiter=1
      shift
      break
    fi
    runtime_args+=("\$1")
    shift
  done
  if [[ "\${saw_delimiter}" == "1" ]]; then
    submit_args=("\$@")
  else
    submit_args=("\${runtime_args[@]}")
    runtime_args=()
  fi

  "\${submit_shell_function_name}" "\${submit_args[@]}"
  if [[ -n "\${runtime_function_name}" ]]; then
    "\${runtime_function_name}" "\${runtime_args[@]}"
  fi
  "\${submit_function_name}" "\${job_command}" "\${submit_args[@]}"
}
spot_runner_wrapper_run_project_submit_wrapper_defaults_required() {
  local _hint_message="\${1:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local submit_shell_function_name="\${2:-}"
  local runtime_function_name="\${3:-}"
  local submit_function_name="\${4:-}"
  local job_command="\${5:-}"
  shift 5 || true
  spot_runner_wrapper_run_project_submit_entrypoint_required \
    "\${_hint_message}" \
    "\${submit_shell_function_name}" \
    "\${runtime_function_name}" \
    "\${submit_function_name}" \
    "\${job_command}" \
    "\$@"
}
spot_runner_maybe_reexec_caffeinate_compat() {
  local guard_var="\${1:-_SPOT_CAFFEINATED}"
  shift 2 || true
  if [[ -n "\${!guard_var:-}" ]]; then
    return 0
  fi
  if ! command -v caffeinate >/dev/null 2>&1; then
    return 0
  fi
  exec env "\${guard_var}=1" caffeinate -i "\$0" "\$@"
}
spot_runner_prepare_submit_shell_compat() {
  local guard_var="\${1:-_SPOT_CAFFEINATED}"
  local guard_alias_csv="\${2:-}"
  shift 2 || true
  spot_runner_maybe_reexec_caffeinate_compat "\${guard_var}" "\${guard_alias_csv}" "\$@"
  trap '' HUP
}
prepare_submit_shell() {
  local guard_alias_csv="_RAV_CAFFEINATED,_IXQT_CAFFEINATED"
  if [[ "\${1:-}" == _*CAFFEINATED* ]]; then
    guard_alias_csv="\$1"
    shift || true
  fi
  spot_runner_prepare_submit_shell_compat "_SPOT_CAFFEINATED" "\${guard_alias_csv}" "\$@"
}
run_submit_entrypoint_with_job() {
  local job_command="\$1"
  shift || true
  spot_runner_wrapper_run_project_submit_wrapper_defaults_required \
    "\${RUNNER_HINT_MESSAGE:-Set RUNNER_DIR to your gcp-spot-runner checkout.}" \
    "prepare_submit_shell" \
    "" \
    "run_submit_with_job" \
    "\${job_command}" \
    -- \
    "\$@"
}
prepare_rav_submit_runtime_and_print_context() {
  local _submit_label="\$1"
  local _config_path="\${2:-}"
  prepare_rav_runtime "required" "1" "1"
  echo "Submitting \${_submit_label} via spot runner..."
  if [[ -n "\${_config_path}" ]]; then
    echo "Config: \${_config_path}"
  fi
  echo "Runner: \${RUNNER_DIR}"
  echo "Image:  \${IMAGE}"
  echo "Bucket: \${BUCKET}"
  if [[ -n "\${CLOUDSDK_PYTHON:-}" ]]; then
    echo "gcloud Python: \${CLOUDSDK_PYTHON}"
  fi
}
run_submit_with_job() {
  local job_command="\$1"
  shift
  printf 'JOB_COMMAND=%s\n' "\$job_command" > "$log_path"
  printf '%s\n' "\$@" >> "$log_path"
}
run_build_command() {
  printf 'BUILD\n' > "$log_path"
  printf '%s\n' "\$@" >> "$log_path"
}
run_project_command() {
  local command_name="\$1"
  shift || true
  case "\${command_name}" in
    ops)
      printf 'OPS\n' > "$log_path"
      ;;
    monitor)
      printf 'MONITOR\n' > "$log_path"
      ;;
    version)
      printf 'VERSION\n' > "$log_path"
      ;;
    *)
      printf '%s\n' "\${command_name^^}" > "$log_path"
      ;;
  esac
  printf '%s\n' "\$@" >> "$log_path"
}
run_rav_standard_command_wrapper() {
  spot_runner_wrapper_run_project_standard_wrapper_defaults_for_common_required \
    "\${RUNNER_HINT_MESSAGE:-Set RUNNER_DIR to your gcp-spot-runner checkout.}" \
    "prepare_rav_runtime" \
    "run_project_command" \
    "rav" \
    "\$@"
}
run_rav_build_wrapper() {
  prepare_rav_runtime "required" "1" "1"
  local source_staging_dir="\${GCS_SOURCE_STAGING_DIR:-gs://\${BUCKET}/cloudbuild/source}"
  spot_runner_wrapper_run_project_build_wrapper_defaults_for_common_required \
    "\${RUNNER_HINT_MESSAGE:-Set RUNNER_DIR to your gcp-spot-runner checkout.}" \
    "" \
    "run_project_command" \
    "\${RAV_ROOT}" \
    "\${RAV_ROOT}/gcp/cloudbuild.rav.yaml" \
    "\${IMAGE}" \
    -- \
    --gcs-source-staging-dir "\${source_staging_dir}" \
    "\$@"
}
SCRIPT
  chmod +x "$TEMP_REPO/scripts/gcp_runner_common.sh"
}

_write_dispatch_stub() {
  local target="$1"
  local log_path="$2"
  local label="$3"
  cat > "$target" <<SCRIPT
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$label" > "$log_path"
printf '%s\n' "\$@" >> "$log_path"
SCRIPT
  chmod +x "$target"
}

@test "run_submit_with_job delegates to spotctl submit with rav profile + job override" {
  source "$REPO_ROOT/scripts/gcp_runner_common.sh"
  local captured="$BATS_TEST_TMPDIR/submit_args.txt"
  _capture_stub "$captured"

  RAV_GCP_ENV_PATH="/tmp/rav_spot.env"
  run_submit_with_job "echo hi" --run-id rav-123 --no-gpu

  run cat "$captured"
  assert_success
  assert_line --index 0 "/tmp/rav_spot.env"
  assert_line --index 1 "submit"
  assert_line --index 2 "--profile"
  assert_line --index 3 "rav"
  assert_line --index 4 "--config"
  assert_line --index 5 "/tmp/rav_spot.env"
  assert_line --index 6 "--job-command"
  assert_line --index 7 "echo hi"
  assert_line --index 8 "--skip-build"
  assert_line --index 9 "--run-id"
  assert_line --index 10 "rav-123"
  assert_line --index 11 "--no-gpu"
}

@test "run_submit_with_job does not duplicate --skip-build when already provided" {
  source "$REPO_ROOT/scripts/gcp_runner_common.sh"
  local captured="$BATS_TEST_TMPDIR/submit_skip_args.txt"
  _capture_stub "$captured"

  RAV_GCP_ENV_PATH="/tmp/rav_spot.env"
  run_submit_with_job "echo hi" --skip-build --run-id rav-123

  local skip_count
  skip_count="$(grep -c '^--skip-build$' "$captured" || true)"
  [ "$skip_count" -eq 1 ]
}

@test "run_project_command ops defaults to status with rav profile + config" {
  source "$REPO_ROOT/scripts/gcp_runner_common.sh"
  local captured="$BATS_TEST_TMPDIR/ops_default_args.txt"
  _capture_stub "$captured"

  RAV_GCP_ENV_PATH="/tmp/rav_spot.env"
  run_project_command ops

  run cat "$captured"
  assert_success
  assert_line --index 0 "/tmp/rav_spot.env"
  assert_line --index 1 "ops"
  assert_line --index 2 "--profile"
  assert_line --index 3 "rav"
  assert_line --index 4 "--config"
  assert_line --index 5 "/tmp/rav_spot.env"
  assert_line --index 6 "status"
}

@test "run_project_command ops forwards explicit ops args unchanged" {
  source "$REPO_ROOT/scripts/gcp_runner_common.sh"
  local captured="$BATS_TEST_TMPDIR/ops_passthrough_args.txt"
  _capture_stub "$captured"

  RAV_GCP_ENV_PATH="/tmp/rav_spot.env"
  run_project_command ops delete --run-id rav-999 --yes

  run cat "$captured"
  assert_success
  assert_line --index 6 "delete"
  assert_line --index 7 "--run-id"
  assert_line --index 8 "rav-999"
  assert_line --index 9 "--yes"
}

@test "run_project_command ops forwards watch json args unchanged" {
  source "$REPO_ROOT/scripts/gcp_runner_common.sh"
  local captured="$BATS_TEST_TMPDIR/ops_watch_json_args.txt"
  _capture_stub "$captured"

  RAV_GCP_ENV_PATH="/tmp/rav_spot.env"
  run_project_command ops watch 20 --json

  run cat "$captured"
  assert_success
  assert_line --index 6 "watch"
  assert_line --index 7 "20"
  assert_line --index 8 "--json"
}

@test "run_build_command delegates to spotctl build with rav profile + config" {
  source "$REPO_ROOT/scripts/gcp_runner_common.sh"
  local captured="$BATS_TEST_TMPDIR/build_args.txt"
  _capture_stub "$captured"

  RAV_GCP_ENV_PATH="/tmp/rav_spot.env"
  run_build_command --source /tmp/rav-src --cloudbuild-config /tmp/cloudbuild.yaml --dry-run

  run cat "$captured"
  assert_success
  assert_line --index 0 "/tmp/rav_spot.env"
  assert_line --index 1 "build"
  assert_line --index 2 "--profile"
  assert_line --index 3 "rav"
  assert_line --index 4 "--config"
  assert_line --index 5 "/tmp/rav_spot.env"
  assert_line --index 6 "--source"
  assert_line --index 7 "/tmp/rav-src"
  assert_line --index 8 "--cloudbuild-config"
  assert_line --index 9 "/tmp/cloudbuild.yaml"
  assert_line --index 10 "--dry-run"
}

@test "run_project_command monitor delegates to spotctl monitor with rav profile + config" {
  source "$REPO_ROOT/scripts/gcp_runner_common.sh"
  local captured="$BATS_TEST_TMPDIR/monitor_args.txt"
  _capture_stub "$captured"

  RAV_GCP_ENV_PATH="/tmp/rav_spot.env"
  run_project_command monitor --single --no-attach

  run cat "$captured"
  assert_success
  assert_line --index 0 "/tmp/rav_spot.env"
  assert_line --index 1 "monitor"
  assert_line --index 2 "--profile"
  assert_line --index 3 "rav"
  assert_line --index 4 "--config"
  assert_line --index 5 "/tmp/rav_spot.env"
  assert_line --index 6 "--single"
  assert_line --index 7 "--no-attach"
}

@test "run_project_command version delegates to spotctl version" {
  source "$REPO_ROOT/scripts/gcp_runner_common.sh"
  local captured="$BATS_TEST_TMPDIR/version_args.txt"
  _capture_stub "$captured"

  RAV_GCP_ENV_PATH="/tmp/rav_spot.env"
  run_project_command version

  run cat "$captured"
  assert_success
  assert_line --index 0 "/tmp/rav_spot.env"
  assert_line --index 1 "version"
}

@test "run_project_command version omits config when no env file is loaded" {
  source "$REPO_ROOT/scripts/gcp_runner_common.sh"
  local captured="$BATS_TEST_TMPDIR/version_args_no_config.txt"
  _capture_stub "$captured"

  RAV_GCP_ENV_PATH=""
  run_project_command version

  run cat "$captured"
  assert_success
  [ "${#lines[@]}" -eq 1 ]
  assert_line --index 0 "version"
}

@test "gcp_submit_primary default job command uses checkpoint sync wrapper" {
  _setup_temp_submit_wrappers
  local call_log="$BATS_TEST_TMPDIR/submit_primary_default.log"
  _write_fake_runner_common "$call_log"

  run env -u RAV_GCP_ENV bash -c "cd '$TEMP_REPO' && ./scripts/gcp_submit_primary.sh --run-id rav-123 --no-gpu" 2>&1
  assert_success

  run cat "$call_log"
  assert_success
  assert_line --index 0 --partial "JOB_COMMAND=set -euo pipefail; bash scripts/gcp_train_with_checkpoint_sync.sh"
  assert_line --index 0 --partial "--config configs/primary/chest_chexpert.yaml"
  assert_line --index 0 --partial "--eval-split val"
  assert_line --index 0 --partial "--sync-interval-sec 180"
  assert_line --index 1 "--run-id"
  assert_line --index 2 "rav-123"
  assert_line --index 3 "--no-gpu"
}

@test "gcp_submit_primary default job command respects SYNC_INTERVAL_SEC override" {
  _setup_temp_submit_wrappers
  local call_log="$BATS_TEST_TMPDIR/submit_primary_sync_interval.log"
  _write_fake_runner_common "$call_log"

  run env -u RAV_GCP_ENV SYNC_INTERVAL_SEC=90 bash -c "cd '$TEMP_REPO' && ./scripts/gcp_submit_primary.sh --run-id rav-124" 2>&1
  assert_success

  run cat "$call_log"
  assert_success
  assert_line --index 0 --partial "--sync-interval-sec 90"
}

@test "gcp_submit_primary uses JOB_COMMAND_PRIMARY override verbatim" {
  _setup_temp_submit_wrappers
  local call_log="$BATS_TEST_TMPDIR/submit_primary_override.log"
  _write_fake_runner_common "$call_log"
  local override_cmd="set -euo pipefail; python3 scripts/custom_primary.py --resume"

  run env -u RAV_GCP_ENV JOB_COMMAND_PRIMARY="$override_cmd" bash -c "cd '$TEMP_REPO' && ./scripts/gcp_submit_primary.sh --run-id rav-125" 2>&1
  assert_success

  run cat "$call_log"
  assert_success
  assert_line --index 0 "JOB_COMMAND=${override_cmd}"
  refute_line --partial "gcp_train_with_checkpoint_sync.sh"
}

@test "gcp_build_image wrapper delegates through shared build-wrapper defaults contract" {
  _setup_temp_submit_wrappers
  local call_log="$BATS_TEST_TMPDIR/build_wrapper.log"
  _write_fake_runner_common "$call_log"

  run env -u RAV_GCP_ENV bash -c "cd '$TEMP_REPO' && ./scripts/gcp_build_image.sh --dry-run" 2>&1
  assert_success

  run cat "$call_log"
  assert_success
  assert_line --index 0 "BUILD"
  assert_line --index 1 "--source"
  assert_line --index 2 "$TEMP_REPO"
  assert_line --index 3 "--cloudbuild-config"
  assert_line --index 4 "$TEMP_REPO/gcp/cloudbuild.rav.yaml"
  assert_line --index 5 "--image"
  assert_line --index 6 "us-east1-docker.pkg.dev/demo/rav/train:latest"
  assert_line --index 7 "--gcs-source-staging-dir"
  assert_line --index 8 --partial "/cloudbuild/source"
  assert_line --index 9 "--dry-run"
}

@test "gcp_monitor wrapper delegates to shared run_project_command monitor dispatch" {
  _setup_temp_submit_wrappers
  local call_log="$BATS_TEST_TMPDIR/monitor_wrapper.log"
  _write_fake_runner_common "$call_log"

  run env -u RAV_GCP_ENV bash -c "cd '$TEMP_REPO' && ./scripts/gcp_monitor.sh --single --json" 2>&1
  assert_success

  run cat "$call_log"
  assert_success
  assert_line --index 0 "MONITOR"
  assert_line --index 1 "--single"
  assert_line --index 2 "--json"
}

@test "gcp_version wrapper delegates to shared run_project_command version dispatch" {
  _setup_temp_submit_wrappers
  local call_log="$BATS_TEST_TMPDIR/version_wrapper.log"
  _write_fake_runner_common "$call_log"

  run env -u RAV_GCP_ENV bash -c "cd '$TEMP_REPO' && ./scripts/gcp_version.sh --help" 2>&1
  assert_success

  run cat "$call_log"
  assert_success
  assert_line --index 0 "VERSION"
  assert_line --index 1 "--help"
}

@test "rav-gcp submit/primary dispatch to gcp_submit_primary wrapper" {
  _setup_temp_submit_wrappers
  local call_log="$BATS_TEST_TMPDIR/rav_gcp_submit.log"
  _write_dispatch_stub "$TEMP_REPO/scripts/gcp_submit_primary.sh" "$call_log" "PRIMARY"

  run env -u RAV_GCP_ENV bash -c "cd '$TEMP_REPO' && ./scripts/rav-gcp.sh submit --run-id rav-cli-1 --dry-run" 2>&1
  assert_success

  run cat "$call_log"
  assert_success
  assert_line --index 0 "PRIMARY"
  assert_line --index 1 "--run-id"
  assert_line --index 2 "rav-cli-1"
  assert_line --index 3 "--dry-run"

  run env -u RAV_GCP_ENV bash -c "cd '$TEMP_REPO' && ./scripts/rav-gcp.sh primary --run-id rav-cli-2 --no-gpu" 2>&1
  assert_success

  run cat "$call_log"
  assert_success
  assert_line --index 0 "PRIMARY"
  assert_line --index 1 "--run-id"
  assert_line --index 2 "rav-cli-2"
  assert_line --index 3 "--no-gpu"
}

@test "rav-gcp poc/build/monitor aliases dispatch to corresponding wrappers" {
  _setup_temp_submit_wrappers

  local poc_log="$BATS_TEST_TMPDIR/rav_gcp_poc.log"
  local build_log="$BATS_TEST_TMPDIR/rav_gcp_build.log"
  local monitor_log="$BATS_TEST_TMPDIR/rav_gcp_monitor.log"
  local version_log="$BATS_TEST_TMPDIR/rav_gcp_version.log"
  _write_dispatch_stub "$TEMP_REPO/scripts/gcp_submit_poc.sh" "$poc_log" "POC"
  _write_dispatch_stub "$TEMP_REPO/scripts/gcp_build_image.sh" "$build_log" "BUILD"
  _write_dispatch_stub "$TEMP_REPO/scripts/gcp_monitor.sh" "$monitor_log" "MONITOR"
  _write_dispatch_stub "$TEMP_REPO/scripts/gcp_version.sh" "$version_log" "VERSION"

  run env -u RAV_GCP_ENV bash -c "cd '$TEMP_REPO' && ./scripts/rav-gcp.sh poc --run-id rav-poc-cli-1 --dry-run" 2>&1
  assert_success
  run cat "$poc_log"
  assert_success
  assert_line --index 0 "POC"
  assert_line --index 1 "--run-id"
  assert_line --index 2 "rav-poc-cli-1"
  assert_line --index 3 "--dry-run"

  run env -u RAV_GCP_ENV bash -c "cd '$TEMP_REPO' && ./scripts/rav-gcp.sh build --dry-run" 2>&1
  assert_success
  run cat "$build_log"
  assert_success
  assert_line --index 0 "BUILD"
  assert_line --index 1 "--dry-run"

  run env -u RAV_GCP_ENV bash -c "cd '$TEMP_REPO' && ./scripts/rav-gcp.sh monitor --single --json" 2>&1
  assert_success
  run cat "$monitor_log"
  assert_success
  assert_line --index 0 "MONITOR"
  assert_line --index 1 "--single"
  assert_line --index 2 "--json"

  run env -u RAV_GCP_ENV bash -c "cd '$TEMP_REPO' && ./scripts/rav-gcp.sh version --help" 2>&1
  assert_success
  run cat "$version_log"
  assert_success
  assert_line --index 0 "VERSION"
  assert_line --index 1 "--help"

  run env -u RAV_GCP_ENV bash -c "cd '$TEMP_REPO' && ./scripts/rav-gcp.sh --version" 2>&1
  assert_success
  run cat "$version_log"
  assert_success
  assert_line --index 0 "VERSION"
  [ "${#lines[@]}" -eq 1 ]

  run env -u RAV_GCP_ENV bash -c "cd '$TEMP_REPO' && ./scripts/rav-gcp.sh -V" 2>&1
  assert_success
  run cat "$version_log"
  assert_success
  assert_line --index 0 "VERSION"
  [ "${#lines[@]}" -eq 1 ]
}

@test "rav-gcp ops aliases dispatch through gcp_ops wrapper" {
  _setup_temp_submit_wrappers
  local call_log="$BATS_TEST_TMPDIR/rav_gcp_ops.log"
  _write_dispatch_stub "$TEMP_REPO/scripts/gcp_ops.sh" "$call_log" "OPS"

  run env -u RAV_GCP_ENV bash -c "cd '$TEMP_REPO' && ./scripts/rav-gcp.sh id --run-id rav-ops-0" 2>&1
  assert_success
  run cat "$call_log"
  assert_success
  assert_line --index 0 "OPS"
  assert_line --index 1 "id"
  assert_line --index 2 "--run-id"
  assert_line --index 3 "rav-ops-0"

  run env -u RAV_GCP_ENV bash -c "cd '$TEMP_REPO' && ./scripts/rav-gcp.sh ops status --run-id rav-ops-1" 2>&1
  assert_success
  run cat "$call_log"
  assert_success
  assert_line --index 0 "OPS"
  assert_line --index 1 "status"
  assert_line --index 2 "--run-id"
  assert_line --index 3 "rav-ops-1"

  run env -u RAV_GCP_ENV bash -c "cd '$TEMP_REPO' && ./scripts/rav-gcp.sh events --run-id rav-ops-2 --since 12h" 2>&1
  assert_success
  run cat "$call_log"
  assert_success
  assert_line --index 0 "OPS"
  assert_line --index 1 "events"
  assert_line --index 2 "--run-id"
  assert_line --index 3 "rav-ops-2"
  assert_line --index 4 "--since"
  assert_line --index 5 "12h"

  run env -u RAV_GCP_ENV bash -c "cd '$TEMP_REPO' && ./scripts/rav-gcp.sh health --run-id rav-ops-h --json" 2>&1
  assert_success
  run cat "$call_log"
  assert_success
  assert_line --index 0 "OPS"
  assert_line --index 1 "health"
  assert_line --index 2 "--run-id"
  assert_line --index 3 "rav-ops-h"
  assert_line --index 4 "--json"

  run env -u RAV_GCP_ENV bash -c "cd '$TEMP_REPO' && ./scripts/rav-gcp.sh delete --run-id rav-ops-3 --yes" 2>&1
  assert_success
  run cat "$call_log"
  assert_success
  assert_line --index 0 "OPS"
  assert_line --index 1 "delete"
  assert_line --index 2 "--run-id"
  assert_line --index 3 "rav-ops-3"
  assert_line --index 4 "--yes"
}

@test "rav-gcp unknown command exits non-zero with usage hint" {
  _setup_temp_submit_wrappers

  run env -u RAV_GCP_ENV bash -c "cd '$TEMP_REPO' && ./scripts/rav-gcp.sh definitely-unknown" 2>&1
  assert_failure
  assert_output --partial "Unknown command: definitely-unknown"
  assert_output --partial "Run './scripts/rav-gcp.sh help' for usage."
}

@test "gcp_submit_primary re-execs through caffeinate guard with _SPOT_CAFFEINATED" {
  _setup_temp_submit_wrappers
  local call_log="$BATS_TEST_TMPDIR/submit_primary_caffeinate.log"
  _write_fake_runner_common "$call_log"

  local fake_bin="$BATS_TEST_TMPDIR/fake-bin-caffeinate-primary"
  local caffeinate_log="$BATS_TEST_TMPDIR/caffeinate_primary.log"
  export CAFFEINATE_LOG="$caffeinate_log"
  _make_caffeinate_stub "$fake_bin"

  run env -u RAV_GCP_ENV PATH="$fake_bin:$PATH" bash -c "cd '$TEMP_REPO' && ./scripts/gcp_submit_primary.sh --run-id rav-caf-1 --dry-run" 2>&1
  assert_success

  run sed -n '1,8p' "$caffeinate_log"
  assert_success
  assert_line --index 0 "CAFFEINATED=1"
  assert_line --index 1 "-i"
  assert_line --index 2 "./scripts/gcp_submit_primary.sh"
  assert_line --index 3 "--run-id"
  assert_line --index 4 "rav-caf-1"
  assert_line --index 5 "--dry-run"

  run cat "$call_log"
  assert_success
  assert_line --index 1 "--run-id"
  assert_line --index 2 "rav-caf-1"
  assert_line --index 3 "--dry-run"
}

@test "gcp_submit_poc re-execs through caffeinate guard with _SPOT_CAFFEINATED" {
  _setup_temp_submit_wrappers
  local call_log="$BATS_TEST_TMPDIR/submit_poc_caffeinate.log"
  _write_fake_runner_common "$call_log"

  local fake_bin="$BATS_TEST_TMPDIR/fake-bin-caffeinate-poc"
  local caffeinate_log="$BATS_TEST_TMPDIR/caffeinate_poc.log"
  export CAFFEINATE_LOG="$caffeinate_log"
  _make_caffeinate_stub "$fake_bin"

  run env -u RAV_GCP_ENV PATH="$fake_bin:$PATH" bash -c "cd '$TEMP_REPO' && ./scripts/gcp_submit_poc.sh --run-id rav-caf-2 --dry-run" 2>&1
  assert_success

  run sed -n '1,8p' "$caffeinate_log"
  assert_success
  assert_line --index 0 "CAFFEINATED=1"
  assert_line --index 1 "-i"
  assert_line --index 2 "./scripts/gcp_submit_poc.sh"
  assert_line --index 3 "--run-id"
  assert_line --index 4 "rav-caf-2"
  assert_line --index 5 "--dry-run"

  run cat "$call_log"
  assert_success
  assert_line --index 1 "--run-id"
  assert_line --index 2 "rav-caf-2"
  assert_line --index 3 "--dry-run"
}

@test "gcp_submit_poc default job command uses checkpoint sync wrapper" {
  _setup_temp_submit_wrappers
  local call_log="$BATS_TEST_TMPDIR/submit_poc_default.log"
  _write_fake_runner_common "$call_log"

  run env -u RAV_GCP_ENV bash -c "cd '$TEMP_REPO' && ./scripts/gcp_submit_poc.sh --run-id rav-poc-1 --dry-run" 2>&1
  assert_success

  run cat "$call_log"
  assert_success
  assert_line --index 0 --partial "JOB_COMMAND=set -euo pipefail; bash scripts/gcp_train_with_checkpoint_sync.sh"
  assert_line --index 0 --partial "--config configs/poc/chest_pneumonia_binary.yaml"
  assert_line --index 0 --partial "--eval-split test"
  assert_line --index 0 --partial "--sync-interval-sec 180"
  assert_line --index 1 "--run-id"
  assert_line --index 2 "rav-poc-1"
  assert_line --index 3 "--dry-run"
}

@test "gcp_submit_poc uses JOB_COMMAND_POC override verbatim" {
  _setup_temp_submit_wrappers
  local call_log="$BATS_TEST_TMPDIR/submit_poc_override.log"
  _write_fake_runner_common "$call_log"
  local override_cmd="set -euo pipefail; python3 scripts/custom_poc.py --epochs 1"

  run env -u RAV_GCP_ENV JOB_COMMAND_POC="$override_cmd" bash -c "cd '$TEMP_REPO' && ./scripts/gcp_submit_poc.sh --run-id rav-poc-2" 2>&1
  assert_success

  run cat "$call_log"
  assert_success
  assert_line --index 0 "JOB_COMMAND=${override_cmd}"
  refute_line --partial "gcp_train_with_checkpoint_sync.sh"
}

@test "reconciler deploy wrapper calls spotctl with rav profile + config" {
  local fake_runner="$BATS_TEST_TMPDIR/fake-runner"
  mkdir -p "$fake_runner/spotctl" "$fake_runner/adapters"
  touch "$fake_runner/spotctl/__main__.py"
cat > "$fake_runner/adapters/spot_runner_common.sh" <<'ADAPTER_STUB'
#!/usr/bin/env bash
set -euo pipefail
spot_runner_wrapper_load_env_optional() {
  local root_dir="$1"
  local env_var_name="$2"
  local default_path="$3"
  local output_var_name="${4:-}"
  local cfg="${!env_var_name:-${default_path}}"
  if [[ "${cfg}" != /* ]]; then
    cfg="${root_dir}/${cfg}"
  fi
  if [[ -n "${output_var_name}" ]]; then
    printf -v "${output_var_name}" '%s' "${cfg}"
  fi
}
spot_runner_wrapper_load_project_env_optional() {
  spot_runner_wrapper_load_env_optional "$@"
}
spot_runner_wrapper_load_project_env_optional_compat() {
  spot_runner_wrapper_load_project_env_optional "$@"
}
spot_runner_wrapper_load_project_env_required_compat_or_exit() {
  local root_dir="$1"
  local env_var_name="$2"
  local default_path="$3"
  local output_var_name="${4:-RAV_GCP_ENV_PATH}"
  spot_runner_wrapper_load_project_env_optional_compat "$root_dir" "$env_var_name" "$default_path" "$output_var_name"
}
spot_runner_resolve_runner_dir_compat() {
  local _project_root="$1"
  local bootstrap_dir="$2"
  local env_var_name="$3"
  printf '%s\n' "${!env_var_name:-${bootstrap_dir}}"
}
spot_runner_wrapper_resolve_project_runner_dir_or_exit() {
  local project_root="$1"
  local bootstrap_dir="$2"
  local env_var_name="$3"
  local output_var_name="${4:-RUNNER_DIR}"
  local resolved_dir=""
  resolved_dir="$(spot_runner_resolve_runner_dir_compat "${project_root}" "${bootstrap_dir}" "${env_var_name}")"
  printf -v "${output_var_name}" '%s' "${resolved_dir}"
}
spot_runner_wrapper_resolve_project_runner_dir_compat_or_exit() {
  spot_runner_wrapper_resolve_project_runner_dir_or_exit "$@"
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
spot_runner_wrapper_setup_project_runtime_required() {
  local project_root="$1"
  local default_runner_dir="$2"
  local runner_env_var_name="$3"
  local runner_output_var_name="$4"
  local profile_name="$5"
  local hint_message="${6:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local env_mode="${7:-optional}"
  local env_var_name="${8:-RAV_GCP_ENV}"
  local default_env_path="${9:-}"
  local output_env_var_name="${10:-RAV_GCP_ENV_PATH}"

  if [[ "${env_mode}" == "required" ]]; then
    spot_runner_wrapper_load_project_env_required_compat_or_exit \
      "${project_root}" \
      "${env_var_name}" \
      "${default_env_path}" \
      "${output_env_var_name}" \
      "${hint_message}"
  else
    spot_runner_wrapper_load_project_env_optional_compat \
      "${project_root}" \
      "${env_var_name}" \
      "${default_env_path}" \
      "${output_env_var_name}" \
      "${hint_message}"
  fi

  spot_runner_wrapper_apply_project_runner_defaults_required \
    "${project_root}" \
    "${default_runner_dir}" \
    "${runner_env_var_name}" \
    "${runner_output_var_name}" \
    "${profile_name}" \
    "${hint_message}"
}
spot_runner_wrapper_setup_project_profile_runtime_required() {
  local project_root="$1"
  local default_runner_dir="$2"
  local hint_message="${3:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local profile_name="${4:-default}"
  local env_var_name="${5:-RAV_GCP_ENV}"
  local default_env_path="${6:-}"
  local output_env_var_name="${7:-RAV_GCP_ENV_PATH}"
  local env_mode="${8:-optional}"
  local missing_env_message="${9:-Missing required project environment file.}"
  local require_spot_vars="${10:-0}"
  local configure_gcloud="${11:-0}"
  local gcloud_project_root="${12:-${project_root}}"
  if [[ $# -gt 12 ]]; then
    shift 12
  else
    set --
  fi
  spot_runner_wrapper_setup_project_runtime_required \
    "${project_root}" \
    "${default_runner_dir}" \
    "RUNNER_DIR" \
    "RUNNER_DIR" \
    "${profile_name}" \
    "${hint_message}" \
    "${env_mode}" \
    "${env_var_name}" \
    "${default_env_path}" \
    "${output_env_var_name}" \
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
spot_runner_wrapper_resolve_active_config_path_required() {
  spot_runner_wrapper_resolve_active_config_path "$@"
}
spot_runner_wrapper_resolve_loaded_config_path_required() {
  spot_runner_wrapper_resolve_loaded_config_path "$@"
}
spot_runner_require_wrapper_runtime_or_exit() { :; }
spot_runner_wrapper_require_project_runtime_or_exit() {
  local _runner_dir="$1"
  local _hint_message="${2:-}"
  local loaded_var_name="${3:-RUNNER_ADAPTER_LIB_LOADED}"
  printf -v "${loaded_var_name}" '%s' "1"
}
spot_runner_wrapper_apply_spot_config_path_override() {
  local output_var_name="$1"
  if [[ -n "${SPOT_CONFIG_PATH:-}" ]]; then
    printf -v "${output_var_name}" '%s' "${SPOT_CONFIG_PATH}"
  fi
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
spot_runner_wrapper_apply_spot_config_path_override_required() {
  local output_var_name="$1"
  local hint_message="${2:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  spot_runner_wrapper_require_function_or_hint "spot_runner_wrapper_apply_spot_config_path_override" "${hint_message}"
  spot_runner_wrapper_apply_spot_config_path_override "${output_var_name}"
}
spot_runner_wrapper_run_project_reconciler_command_entrypoint_required() {
  local _hint_message="${1:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local config_env_var_name="${2:-}"
  local runtime_function_name="${3:-}"
  local command_function_name="${4:-}"
  if [[ $# -gt 4 ]]; then
    shift 4
  else
    set --
  fi

  local runtime_args=()
  local command_args=()
  local saw_delimiter=0
  while [[ $# -gt 0 ]]; do
    if [[ "$1" == "--" ]]; then
      saw_delimiter=1
      shift
      break
    fi
    command_args+=("$1")
    shift
  done
  if [[ "${saw_delimiter}" == "1" ]]; then
    runtime_args=("${command_args[@]}")
    command_args=("$@")
  fi
  if [[ -z "${runtime_function_name}" && "${saw_delimiter}" == "1" && "${#runtime_args[@]}" -gt 0 ]]; then
    command_args=("${runtime_args[@]}" "${command_args[@]}")
    runtime_args=()
  fi

  spot_runner_wrapper_apply_spot_config_path_override_required "${config_env_var_name}"
  if [[ -n "${runtime_function_name}" ]]; then
    "${runtime_function_name}" "${runtime_args[@]}"
  fi
  "${command_function_name}" "reconciler_deploy" "${command_args[@]}"
}
spot_runner_wrapper_run_project_reconciler_wrapper_defaults_required() {
  local _hint_message="${1:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local config_env_var_name="${2:-}"
  local runtime_function_name="${3:-}"
  local command_function_name="${4:-}"
  shift 4 || true

  if [[ -n "${runtime_function_name}" ]]; then
    spot_runner_wrapper_run_project_reconciler_command_entrypoint_required \
      "${_hint_message}" \
      "${config_env_var_name}" \
      "${runtime_function_name}" \
      "${command_function_name}" \
      "optional" \
      "0" \
      "0" \
      -- \
      "$@"
    return "$?"
  fi

  spot_runner_wrapper_run_project_reconciler_command_entrypoint_required \
    "${_hint_message}" \
    "${config_env_var_name}" \
    "" \
    "${command_function_name}" \
    "$@"
}
spot_runner_wrapper_profile_reconciler_defaults() {
  local profile_name="${1:-default}"
  local function_name_var="${2:-}"
  local scheduler_name_var="${3:-}"

  local function_name=""
  local scheduler_name=""
  case "${profile_name}" in
    ixqt)
      function_name="ixqt-reconciler"
      scheduler_name="ixqt-reconciler-trigger"
      ;;
    rav)
      function_name="rav-reconciler"
      scheduler_name="rav-reconciler-trigger"
      ;;
    *)
      function_name="${profile_name}-reconciler"
      scheduler_name="${profile_name}-reconciler-trigger"
      ;;
  esac

  if [[ -n "${function_name_var}" && -n "${scheduler_name_var}" ]]; then
    printf -v "${function_name_var}" '%s' "${function_name}"
    printf -v "${scheduler_name_var}" '%s' "${scheduler_name}"
    return 0
  fi

  printf '%s\n' "${function_name}"
  printf '%s\n' "${scheduler_name}"
}
spot_runner_wrapper_profile_reconciler_defaults_required() {
  spot_runner_wrapper_profile_reconciler_defaults "$@"
}
spot_runner_wrapper_run_project_standard_command_compat_required() {
  local runner_dir="$1"
  local hint_message="${2:-}"
  local loaded_var_name="${3:-RUNNER_ADAPTER_LIB_LOADED}"
  local config_mode="${4:-active}"
  local current_config_path="${5:-}"
  local default_config_path="${6:-}"
  local profile_name="${7:-default}"
  local command_name="${8:-}"
  shift 8 || true

  local config_path=""
  case "${config_mode}" in
    active)
      config_path="$(spot_runner_wrapper_resolve_active_config_path_required "${current_config_path}" "${default_config_path}" "${hint_message}")"
      ;;
    loaded)
      config_path="$(spot_runner_wrapper_resolve_loaded_config_path_required "${current_config_path}" "${default_config_path}" "${hint_message}")"
      ;;
    *)
      echo "Unsupported config-path mode: ${config_mode}" >&2
      return 1
      ;;
  esac

  case "${command_name}" in
    reconciler_deploy)
      spot_runner_wrapper_run_project_reconciler_deploy_with_profile_defaults_required \
        "${runner_dir}" \
        "${hint_message}" \
        "${loaded_var_name}" \
        "${config_path}" \
        "${profile_name}" \
        "$@"
      ;;
    *)
      echo "Unsupported project command with mode: ${command_name}" >&2
      return 1
      ;;
  esac
}
spot_runner_wrapper_run_project_standard_command_active_required() {
  local runner_dir="$1"
  local hint_message="${2:-}"
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
  local hint_message="${2:-}"
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
spot_runner_wrapper_run_project_profile_command_wrapper_defaults_required() {
  local runner_dir="$1"
  local hint_message="${2:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  local loaded_var_name="${3:-RUNNER_ADAPTER_LIB_LOADED}"
  local profile_name="${4:-default}"
  local command_name="${5:-}"
  local current_config_path="${6:-}"
  local default_config_path="${7:-}"
  shift 7 || true

  spot_runner_wrapper_run_project_profile_command_with_paths_required \
    "${runner_dir}" \
    "${hint_message}" \
    "${loaded_var_name}" \
    "${profile_name}" \
    "${command_name}" \
    "${current_config_path}" \
    "${default_config_path}" \
    "$@"
}
spot_runner_wrapper_apply_rav_defaults() {
  : "${DATA_DISK_ENABLED:=true}"
  : "${DATA_DISK_MOUNT_PATH:=/var/lib/spot-data}"
  : "${DATA_DISK_DEVICE_NAME:=spot-data}"
  : "${DATA_DISK_FS_TYPE:=ext4}"
}
spot_runner_wrapper_apply_rav_defaults_required() {
  local _hint_message="${1:-Set RUNNER_DIR to your gcp-spot-runner checkout.}"
  spot_runner_wrapper_apply_rav_defaults
}
spot_runner_wrapper_profile_hint() {
  local profile_name="${1:-default}"
  if [[ "${profile_name}" == "rav" ]]; then
    printf '%s\n' "Set RUNNER_DIR in gcp/rav_spot.env to your gcp-spot-runner checkout."
    return 0
  fi
  printf '%s\n' "Set RUNNER_DIR to your gcp-spot-runner checkout."
}
spot_runner_wrapper_profile_required_files() {
  printf '%s\n' adapters/spot_runner_bootstrap.sh spotctl/__main__.py submit_legacy.sh ops_legacy.sh lib.sh startup.sh
}
spot_runner_wrapper_require_project_runtime_for_profile_or_exit() {
  local runner_dir="$1"
  local profile_name="$2"
  local loaded_var_name="${3:-RUNNER_ADAPTER_LIB_LOADED}"
  local hint_message
  hint_message="$(spot_runner_wrapper_profile_hint "${profile_name}")"
  spot_runner_wrapper_require_project_runtime_or_exit "${runner_dir}" "${hint_message}" "${loaded_var_name}"
}
spot_runner_require_install() { return 0; }
spot_runner_wrapper_require_project_install_or_exit() { return 0; }
spot_runner_wrapper_require_project_install_for_profile_or_exit() { return 0; }
spot_runner_wrapper_require_project_install_for_profile_compat_or_exit() { return 0; }
spot_runner_wrapper_configure_gcloud_runtime() { :; }
spot_runner_wrapper_check_required_spot_vars() { :; }
spot_runner_check_install() {
  local runner_dir="$1"
  shift
  local file
  for file in "$@"; do
    [[ -f "${runner_dir}/${file}" ]] || return 1
  done
}
spot_runner_run_spotctl_safe() {
  spot_runner_run_spotctl "$@"
}
spot_runner_run_spotctl_compat() {
  spot_runner_run_spotctl_safe "$@"
}
spot_runner_wrapper_run_spotctl_compat() {
  spot_runner_run_spotctl_compat "$@"
}
spot_runner_wrapper_run_project_spotctl_with_config() {
  local runner_dir="$1"
  local _hint_message="${2:-}"
  local _loaded_var_name="${3:-RUNNER_ADAPTER_LIB_LOADED}"
  local config_path="$4"
  shift 4
  spot_runner_wrapper_run_spotctl_compat "${runner_dir}" "${config_path}" "$@"
}
spot_runner_wrapper_run_project_reconciler_deploy_entrypoint_compat() {
  local runner_dir="$1"
  local _hint_message="${2:-}"
  local _loaded_var_name="${3:-RUNNER_ADAPTER_LIB_LOADED}"
  local config_path="$4"
  local profile_name="$5"
  local function_name="$6"
  local scheduler_name="$7"
  shift 7
  spot_runner_wrapper_run_reconciler_deploy_compat \
    "${runner_dir}" \
    "${config_path}" \
    "${profile_name}" \
    "${function_name}" \
    "${scheduler_name}" \
    "$@"
}
spot_runner_wrapper_run_project_reconciler_deploy_entrypoint_compat_or_fallback() {
  spot_runner_wrapper_run_project_reconciler_deploy_entrypoint_compat "$@"
}
spot_runner_wrapper_run_project_reconciler_deploy_from_env() {
  local runner_dir="$1"
  local hint_message="${2:-}"
  local loaded_var_name="${3:-RUNNER_ADAPTER_LIB_LOADED}"
  local config_path="$4"
  local profile_name="$5"
  local default_function_name="$6"
  local default_scheduler_name="$7"
  shift 7

  local function_name="${FUNCTION_NAME:-${default_function_name}}"
  local scheduler_name="${SCHEDULER_NAME:-${default_scheduler_name}}"
  spot_runner_wrapper_run_project_reconciler_deploy_entrypoint_compat_or_fallback \
    "${runner_dir}" \
    "${hint_message}" \
    "${loaded_var_name}" \
    "${config_path}" \
    "${profile_name}" \
    "${function_name}" \
    "${scheduler_name}" \
    "$@"
}
spot_runner_wrapper_run_project_reconciler_deploy_from_env_required() {
  spot_runner_wrapper_run_project_reconciler_deploy_from_env "$@"
}
spot_runner_wrapper_run_project_reconciler_deploy_with_profile_defaults_required() {
  local runner_dir="$1"
  local hint_message="${2:-}"
  local loaded_var_name="${3:-RUNNER_ADAPTER_LIB_LOADED}"
  local config_path="$4"
  local profile_name="$5"
  shift 5

  local default_function_name=""
  local default_scheduler_name=""
  spot_runner_wrapper_profile_reconciler_defaults_required \
    "${profile_name}" \
    default_function_name \
    default_scheduler_name \
    "${hint_message}"

  spot_runner_wrapper_run_project_reconciler_deploy_from_env_required \
    "${runner_dir}" \
    "${hint_message}" \
    "${loaded_var_name}" \
    "${config_path}" \
    "${profile_name}" \
    "${default_function_name}" \
    "${default_scheduler_name}" \
    "$@"
}
spot_runner_wrapper_run_project_reconciler_deploy_with_loaded_config_required() {
  local runner_dir="$1"
  local hint_message="${2:-}"
  local loaded_var_name="${3:-RUNNER_ADAPTER_LIB_LOADED}"
  local current_config_path="${4:-}"
  local default_config_path="${5:-}"
  local profile_name="${6:-default}"
  shift 6

  local config_path=""
  config_path="$(spot_runner_wrapper_resolve_loaded_config_path_required "${current_config_path}" "${default_config_path}" "${hint_message}")"

  spot_runner_wrapper_run_project_reconciler_deploy_with_profile_defaults_required \
    "${runner_dir}" \
    "${hint_message}" \
    "${loaded_var_name}" \
    "${config_path}" \
    "${profile_name}" \
    "$@"
}
spot_runner_wrapper_run_reconciler_deploy_compat() {
  local runner_dir="$1"
  local config_path="$2"
  local profile_name="$3"
  local function_name="$4"
  local scheduler_name="$5"
  shift 5
  local args=(
    reconciler
    deploy
    --profile "$profile_name"
    --function-name "$function_name"
    --scheduler-name "$scheduler_name"
  )
  if [[ -n "${config_path}" ]]; then
    args+=(--config "$config_path")
  fi
  spot_runner_wrapper_run_spotctl_compat "${runner_dir}" "${config_path}" "${args[@]}" "$@"
}
spot_runner_run_spotctl() {
  local runner_dir="$1"
  local config_path="$2"
  shift 2
  local env_args=()
  if [[ -n "${config_path}" ]]; then
    env_args+=(SPOT_CONFIG_PATH="${config_path}")
  fi
  env "${env_args[@]}" \
    PYTHONPATH="${runner_dir}${PYTHONPATH:+:${PYTHONPATH}}" \
    python3 -m spotctl "$@"
}
ADAPTER_STUB
  chmod +x "$fake_runner/adapters/spot_runner_common.sh"

  local fake_bin="$BATS_TEST_TMPDIR/fake-bin"
  mkdir -p "$fake_bin"
  local call_log="$BATS_TEST_TMPDIR/python3_calls.log"
  local env_log="$BATS_TEST_TMPDIR/python3_env.log"
  export CALL_LOG="$call_log"
  export ENV_LOG="$env_log"

  cat > "$fake_bin/python3" <<'PYTHON3_STUB'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$@" > "${CALL_LOG}"
printf 'PYTHONPATH=%s\n' "${PYTHONPATH:-}" > "${ENV_LOG}"
PYTHON3_STUB
  chmod +x "$fake_bin/python3"

  local cfg="$BATS_TEST_TMPDIR/rav_spot.env"
  echo 'PROJECT="demo-project"' > "$cfg"

  run env \
    PATH="$fake_bin:$PATH" \
    RUNNER_DIR="$fake_runner" \
    SPOT_CONFIG_PATH="$cfg" \
    "$REPO_ROOT/gcp/cloud_reconciler/deploy.sh" \
    --dry-run true

  assert_success

  run cat "$call_log"
  assert_success
  assert_line --index 0 "-m"
  assert_line --index 1 "spotctl"
  assert_line --index 2 "reconciler"
  assert_line --index 3 "deploy"
  assert_line --index 4 "--profile"
  assert_line --index 5 "rav"
  assert_line --index 6 "--function-name"
  assert_line --index 7 "rav-reconciler"
  assert_line --index 8 "--scheduler-name"
  assert_line --index 9 "rav-reconciler-trigger"
  assert_line --index 10 "--config"
  assert_line --index 11 "$cfg"
  assert_line --index 12 "--dry-run"
  assert_line --index 13 "true"

  run cat "$env_log"
  assert_success
  assert_line --partial "PYTHONPATH=${fake_runner}"
}
