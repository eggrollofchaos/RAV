#!/usr/bin/env bats
# tests/bats/test_lib_restart.bats — Tests for gcp-spot-runner lib.sh restart lock helpers
# Covers verification matrix items: #28, #35

RUNNER_DIR="/Users/wax/Documents/Programming/gcp-spot-runner"

load test_helper

_source_lib() {
    # Source lib.sh with required env
    export BUCKET="ixqt-training-488109"
    export RUN_ID="test-20260228-120000"
    export PROJECT="ixqt-488109"
    export ZONE="us-east1-c"
    export REGION="us-east1"
    export SA="test@test.iam.gserviceaccount.com"
    export IMAGE="test:latest"
    export JOB_COMMAND="echo test"
    export RUNNER_LABEL="spot-runner"
    export LOG_LEVEL="DEBUG"
    source "$RUNNER_DIR/lib.sh"
}

# ── Restart lock path ──

@test "restart_lock_path returns correct GCS path" {
    _source_lib
    run _restart_lock_path
    assert_output "gs://ixqt-training-488109/runs/test-20260228-120000/restart.lock"
}

# ── Restart lock variables ──

@test "restart lock vars initialized empty by default" {
    _source_lib
    [[ -z "$_RESTART_LOCK_GEN" ]]
    [[ "$_RESTART_LOCK_ACTOR" == "local" ]]
    [[ -z "$_RESTART_PREV_STATE" ]]
}

@test "restart lock vars inherited from env" {
    export _RESTART_LOCK_GEN="12345"
    export _RESTART_LOCK_ACTOR="reconciler"
    export _RESTART_PREV_STATE="PREEMPTED"
    _source_lib
    [[ "$_RESTART_LOCK_GEN" == "12345" ]]
    [[ "$_RESTART_LOCK_ACTOR" == "reconciler" ]]
    [[ "$_RESTART_PREV_STATE" == "PREEMPTED" ]]
}

# ── Acquire restart lock ──

@test "acquire_restart_lock calls gcloud with generation-match:0" {
    _source_lib
    export GCLOUD_STORAGE_CP_ATOMIC_RESULT="ok"
    run _acquire_restart_lock 2>&1
    assert_success
    assert_shim_called "gcloud storage cp"
    assert_shim_called "x-goog-if-generation-match=0"
}

@test "acquire_restart_lock fails when lock exists" {
    _source_lib
    export GCLOUD_STORAGE_CP_ATOMIC_RESULT="locked"
    run _acquire_restart_lock 2>&1
    assert_failure
}

# ── Release restart lock ──

@test "release_restart_lock calls gcloud storage rm" {
    _source_lib
    run _release_restart_lock "1234567890"
    assert_shim_called "gcloud storage rm"
    assert_shim_called "x-goog-if-generation-match=1234567890"
}

@test "release_restart_lock without gen uses simple rm" {
    _source_lib
    run _release_restart_lock ""
    assert_shim_called "gcloud storage rm"
    refute_shim_called "x-goog-if-generation-match"
}

# ── Owner lock preconditioned clearance ──

@test "clear_owner_lock succeeds when no lock exists" {
    _source_lib
    export GCLOUD_STORAGE_CAT_OWNER_LOCK=""
    run _clear_owner_lock_preconditioned
    assert_success
    assert_output --partial "No owner lock to clear"
}

@test "clear_owner_lock clears when VM is gone" {
    _source_lib
    export GCLOUD_STORAGE_CAT_OWNER_LOCK='{"instance":"old-vm","zone":"us-east1-c"}'
    export GCLOUD_VM_EXISTS="false"
    run _clear_owner_lock_preconditioned
    assert_success
    assert_output --partial "Owner lock cleared"
}

@test "clear_owner_lock aborts when VM still exists" {
    _source_lib
    export GCLOUD_STORAGE_CAT_OWNER_LOCK='{"instance":"alive-vm","zone":"us-east1-c"}'
    export GCLOUD_VM_EXISTS="true"
    run _clear_owner_lock_preconditioned
    assert_failure
    assert_output --partial "still exists"
}

# ── Restart rollback ──

@test "#35 restart_rollback releases lock and notifies" {
    _source_lib
    export _RESTART_LOCK_GEN="1234567890"
    export _RESTART_PREV_STATE="PREEMPTED"
    export GCLOUD_STORAGE_CAT_RESULT='{"state":"RESTARTING","prev_state":"PREEMPTED","state_version":3}'
    run _restart_rollback 2>&1
    assert_shim_called "gcloud storage rm"  # Lock release
    assert_output --partial "Restart rollback triggered"
    assert_output --partial "Releasing restart lock"
}

@test "restart_rollback without lock gen skips lock release" {
    _source_lib
    export _RESTART_LOCK_GEN=""
    export _RESTART_PREV_STATE="PREEMPTED"
    run _restart_rollback 2>&1
    refute_shim_called "gcloud storage rm.*restart.lock"
    assert_output --partial "Restart rollback triggered"
}

# ── Notification helper ──

@test "notify sends to Discord when webhook set" {
    _source_lib
    export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/test"
    run _notify "test message" "info"
    assert_shim_called "curl"
}

@test "notify skips Discord when webhook empty" {
    _source_lib
    export DISCORD_WEBHOOK_URL=""
    run _notify "test message" "info"
    refute_shim_called "curl"
}

# ── Sanitize helpers ──

@test "sanitize_label produces valid GCP label" {
    _source_lib
    run _sanitize_label "My_Run-ID_2026"
    assert_success
    # Should be lowercase, alphanumeric + hyphens, max 63 chars
    [[ "$output" =~ ^[a-z0-9][a-z0-9-]*$ ]]
    [[ ${#output} -le 63 ]]
}

@test "sanitize_vm_name produces valid GCE name" {
    _source_lib
    run _sanitize_vm_name "spot-runner-test-20260228-0"
    assert_success
    [[ "$output" =~ ^[a-z] ]]
    [[ ${#output} -le 63 ]]
}

# ── GCS lock (submit lock) ──

@test "acquire_gcs_lock uses generation-match:0" {
    _source_lib
    export GCLOUD_STORAGE_CP_ATOMIC_RESULT="ok"
    run _acquire_gcs_lock "gs://bucket/test.lock" '{"test":true}'
    assert_success
    assert_shim_called "x-goog-if-generation-match=0"
}

@test "acquire_gcs_lock fails when lock exists" {
    _source_lib
    export GCLOUD_STORAGE_CP_ATOMIC_RESULT="locked"
    run _acquire_gcs_lock "gs://bucket/test.lock" '{"test":true}'
    assert_failure
}
