#!/usr/bin/env bats
# tests/bats/test_runner_adapter.bats — adapter contract tests for RAV wrappers.

load test_helper

CAPTURE_PATH=""

_capture_stub() {
  CAPTURE_PATH="$1"
  run_spotctl_with_config() {
    printf '%s\n' "$@" > "$CAPTURE_PATH"
  }
}

_setup_temp_submit_wrappers() {
  export TEMP_REPO="$BATS_TEST_TMPDIR/repo"
  mkdir -p "$TEMP_REPO/scripts"
  cp "$REPO_ROOT/scripts/gcp_submit_primary.sh" "$TEMP_REPO/scripts/gcp_submit_primary.sh"
  cp "$REPO_ROOT/scripts/gcp_submit_poc.sh" "$TEMP_REPO/scripts/gcp_submit_poc.sh"
  cp "$REPO_ROOT/scripts/gcp_build_image.sh" "$TEMP_REPO/scripts/gcp_build_image.sh"
  cp "$REPO_ROOT/scripts/gcp_ops.sh" "$TEMP_REPO/scripts/gcp_ops.sh"
  cp "$REPO_ROOT/scripts/gcp_monitor.sh" "$TEMP_REPO/scripts/gcp_monitor.sh"
  cp "$REPO_ROOT/scripts/rav-gcp.sh" "$TEMP_REPO/scripts/rav-gcp.sh"
  chmod +x \
    "$TEMP_REPO/scripts/gcp_submit_primary.sh" \
    "$TEMP_REPO/scripts/gcp_submit_poc.sh" \
    "$TEMP_REPO/scripts/gcp_build_image.sh" \
    "$TEMP_REPO/scripts/gcp_ops.sh" \
    "$TEMP_REPO/scripts/gcp_monitor.sh" \
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
apply_runner_defaults() {
  : "\${RUNNER_DIR:=/tmp/fake-runner}"
  : "\${IMAGE:=us-east1-docker.pkg.dev/demo/rav/train:latest}"
  : "\${BUCKET:=demo-bucket}"
}
check_required_spot_vars() { :; }
check_runner_install() { :; }
configure_gcloud_runtime() { :; }
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
run_monitor_command() {
  printf 'MONITOR\n' > "$log_path"
  printf '%s\n' "\$@" >> "$log_path"
}
run_ops_command() {
  printf 'OPS\n' > "$log_path"
  printf '%s\n' "\$@" >> "$log_path"
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

@test "apply_runner_defaults aligns data disk defaults with rav profile contract" {
  source "$REPO_ROOT/scripts/gcp_runner_common.sh"
  RUNNER_DIR="$REPO_ROOT/../gcp-spot-runner"

  unset DATA_DISK_ENABLED DATA_DISK_MOUNT_PATH DATA_DISK_DEVICE_NAME DATA_DISK_FS_TYPE DATA_DISK_TYPE DATA_DISK_SIZE_GB
  apply_runner_defaults

  [ "$DATA_DISK_ENABLED" = "true" ]
  [ "$DATA_DISK_MOUNT_PATH" = "/var/lib/spot-data" ]
  [ "$DATA_DISK_DEVICE_NAME" = "spot-data" ]
  [ "$DATA_DISK_FS_TYPE" = "ext4" ]
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

@test "run_ops_command defaults to status with rav profile + config" {
  source "$REPO_ROOT/scripts/gcp_runner_common.sh"
  local captured="$BATS_TEST_TMPDIR/ops_default_args.txt"
  _capture_stub "$captured"

  RAV_GCP_ENV_PATH="/tmp/rav_spot.env"
  run_ops_command

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

@test "run_ops_command forwards explicit ops args unchanged" {
  source "$REPO_ROOT/scripts/gcp_runner_common.sh"
  local captured="$BATS_TEST_TMPDIR/ops_passthrough_args.txt"
  _capture_stub "$captured"

  RAV_GCP_ENV_PATH="/tmp/rav_spot.env"
  run_ops_command delete --run-id rav-999 --yes

  run cat "$captured"
  assert_success
  assert_line --index 6 "delete"
  assert_line --index 7 "--run-id"
  assert_line --index 8 "rav-999"
  assert_line --index 9 "--yes"
}

@test "run_ops_command forwards watch json args unchanged" {
  source "$REPO_ROOT/scripts/gcp_runner_common.sh"
  local captured="$BATS_TEST_TMPDIR/ops_watch_json_args.txt"
  _capture_stub "$captured"

  RAV_GCP_ENV_PATH="/tmp/rav_spot.env"
  run_ops_command watch 20 --json

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

@test "run_monitor_command delegates to spotctl monitor with rav profile + config" {
  source "$REPO_ROOT/scripts/gcp_runner_common.sh"
  local captured="$BATS_TEST_TMPDIR/monitor_args.txt"
  _capture_stub "$captured"

  RAV_GCP_ENV_PATH="/tmp/rav_spot.env"
  run_monitor_command --single --no-attach

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

@test "gcp_build_image wrapper delegates to shared run_build_command" {
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

@test "gcp_monitor wrapper delegates to shared run_monitor_command" {
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
  _write_dispatch_stub "$TEMP_REPO/scripts/gcp_submit_poc.sh" "$poc_log" "POC"
  _write_dispatch_stub "$TEMP_REPO/scripts/gcp_build_image.sh" "$build_log" "BUILD"
  _write_dispatch_stub "$TEMP_REPO/scripts/gcp_monitor.sh" "$monitor_log" "MONITOR"

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
}

@test "rav-gcp ops aliases dispatch through gcp_ops wrapper" {
  _setup_temp_submit_wrappers
  local call_log="$BATS_TEST_TMPDIR/rav_gcp_ops.log"
  _write_dispatch_stub "$TEMP_REPO/scripts/gcp_ops.sh" "$call_log" "OPS"

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
spot_runner_check_install() {
  local runner_dir="$1"
  shift
  local file
  for file in "$@"; do
    [[ -f "${runner_dir}/${file}" ]] || return 1
  done
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
