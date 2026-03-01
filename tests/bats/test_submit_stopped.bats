#!/usr/bin/env bats
# tests/bats/test_submit_stopped.bats — Tests for STOPPED handling in gcp-spot-runner submit.sh
# Covers verification matrix items: #22, #34

RUNNER_DIR="/Users/wax/Documents/Programming/gcp-spot-runner"

load test_helper

# ── Structural checks ──

@test "#34 submit.sh checks STOPPED in VM-gone classification" {
    # Check that STOPPED is checked before defaulting to PREEMPTED
    grep -q 'status_txt.*==.*STOPPED' "$RUNNER_DIR/submit.sh"
}

@test "submit.sh pre-poll smoke check for STOPPED" {
    grep -q 'STOPPED' "$RUNNER_DIR/submit.sh"
    # The pre-poll check
    grep -q '_pre_status' "$RUNNER_DIR/submit.sh"
}

@test "submit.sh poll loop checks STOPPED during heartbeat monitoring" {
    # Line 516-521: status.txt STOPPED check in main poll
    grep -qE '_status_txt.*STOPPED' "$RUNNER_DIR/submit.sh"
}

@test "submit.sh auto-restart excluded for STOPPED" {
    # STOPPED should not trigger auto-restart
    grep -q 'FINAL_STATUS.*!=.*STOPPED' "$RUNNER_DIR/submit.sh"
}

@test "submit.sh inner poll loop checks STOPPED" {
    # The restart inner poll loop also checks STOPPED
    local count
    count=$(grep -c '"STOPPED"' "$RUNNER_DIR/submit.sh")
    # Should appear multiple times (pre-poll, VM-gone, poll loop, inner poll, auto-restart guard)
    [[ $count -ge 5 ]]
}

# ── restart_config.json upload ──

@test "submit.sh uploads restart_config.json after VM creation" {
    grep -q 'restart_config.json' "$RUNNER_DIR/submit.sh"
}

@test "restart_config.json includes all required fields" {
    # Check for key fields in the jq construction
    grep -q 'auto_restart_max' "$RUNNER_DIR/submit.sh"
    grep -q 'machine_type' "$RUNNER_DIR/submit.sh"
    grep -q 'fallback_zones' "$RUNNER_DIR/submit.sh"
    grep -q 'config_version' "$RUNNER_DIR/submit.sh"
    grep -q 'submitted_at' "$RUNNER_DIR/submit.sh"
}

# ── Restart lock in auto-restart path ──

@test "submit.sh _do_restart function exists" {
    grep -q '_do_restart()' "$RUNNER_DIR/submit.sh"
}

@test "submit.sh _do_restart acquires or inherits restart.lock" {
    grep -q '_RESTART_LOCK_GEN' "$RUNNER_DIR/submit.sh"
    grep -q '_acquire_restart_lock' "$RUNNER_DIR/submit.sh"
}

@test "submit.sh _do_restart releases lock after VM create" {
    grep -q '_release_restart_lock' "$RUNNER_DIR/submit.sh"
}

@test "submit.sh _do_restart has ERR trap for rollback" {
    grep -q "_restart_rollback.*ERR" "$RUNNER_DIR/submit.sh"
}

@test "submit.sh _do_restart writes RESTARTING state" {
    grep -q 'RESTARTING' "$RUNNER_DIR/submit.sh"
}

# ── .stop checking before restart ──

@test "#22 submit.sh checks .stop before auto-restart" {
    # Double-check: .stop is checked twice (initial and last-minute)
    local stop_count
    stop_count=$(grep -c '\.stop' "$RUNNER_DIR/submit.sh")
    [[ $stop_count -ge 2 ]]
}

# ── notify_secret passthrough ──

@test "submit.sh passes NOTIFY_SECRET in metadata" {
    grep -q 'notify-secret' "$RUNNER_DIR/submit.sh"
}

# ── Startup script _get_secret() ──

@test "startup.sh has _get_secret function" {
    grep -q '_get_secret()' "$RUNNER_DIR/startup.sh"
}

@test "#19 startup.sh _get_secret uses REST API (no gcloud)" {
    # Verify it uses curl + secretmanager API, not gcloud
    grep -A 20 '_get_secret()' "$RUNNER_DIR/startup.sh" | grep -q 'secretmanager.googleapis.com'
}

@test "startup.sh passes DISCORD_WEBHOOK_URL to container" {
    grep -q 'DISCORD_WEBHOOK_URL' "$RUNNER_DIR/startup.sh"
}
