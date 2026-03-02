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
  chmod +x "$TEMP_REPO/scripts/gcp_submit_primary.sh" "$TEMP_REPO/scripts/gcp_submit_poc.sh"
}

_write_fake_runner_common() {
  local log_path="$1"
  : > "$log_path"
  cat > "$TEMP_REPO/scripts/gcp_runner_common.sh" <<SCRIPT
#!/usr/bin/env bash
set -euo pipefail
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
SCRIPT
  chmod +x "$TEMP_REPO/scripts/gcp_runner_common.sh"
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
  mkdir -p "$fake_runner/spotctl"
  touch "$fake_runner/spotctl/__main__.py"

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
