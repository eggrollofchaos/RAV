#!/usr/bin/env bats
# tests/bats/test_entrypoint.bats — Tests for IXQT gcp/entrypoint.sh structure
# Covers verification matrix items: #4, #5, #16, #19, #27

load test_helper

ENTRYPOINT="$REPO_ROOT/gcp/entrypoint.sh"
RUNNER_ENTRYPOINT="/Users/wax/Documents/Programming/gcp-spot-runner/entrypoint.sh"

# ── Structural checks (no execution — these scripts require Docker/GCP) ──

# #4: Preemption watcher in entrypoint.sh

@test "#4 preemption watcher function exists in IXQT entrypoint" {
    grep -q '_preemption_watcher()' "$ENTRYPOINT"
}

@test "#4 preemption watcher polls metadata endpoint" {
    grep -q 'instance/preempted' "$ENTRYPOINT"
}

@test "#4 synthetic test hook exists" {
    grep -q 'IXQT_TEST_SYNTH_PREEMPT' "$ENTRYPOINT"
}

@test "#4 handle_preemption function exists" {
    grep -q '_handle_preemption()' "$ENTRYPOINT"
}

@test "#4 preemption watcher started in background" {
    grep -q '_preemption_watcher &' "$ENTRYPOINT"
}

# #5: Terminal precedence in _write_state()

@test "#5 write_state checks terminal precedence" {
    grep -q 'current_state in TERMINAL' "$ENTRYPOINT"
}

@test "#5 write_state uses CAS (if_generation_match)" {
    grep -q 'if_generation_match' "$ENTRYPOINT"
}

# #27: Startup terminal guard

@test "#27 startup terminal guard function exists" {
    grep -q '_startup_terminal_guard()' "$ENTRYPOINT"
}

@test "#27 terminal guard checks STOPPED|COMPLETE|FAILED|PARTIAL" {
    grep -q 'STOPPED|COMPLETE|FAILED|PARTIAL' "$ENTRYPOINT"
}

@test "#27 terminal guard calls self-delete" {
    grep -q '_self_delete_vm' "$ENTRYPOINT"
}

@test "#27 terminal guard runs before state write" {
    local guard_line write_line
    guard_line=$(grep -n '_startup_terminal_guard' "$ENTRYPOINT" | tail -1 | cut -d: -f1)
    write_line=$(grep -n '_write_state.*RUNNING.*container_started' "$ENTRYPOINT" | head -1 | cut -d: -f1)
    [[ $guard_line -lt $write_line ]]
}

# Status compatibility mapping

@test "STATUS_COMPAT has ORPHANED → PREEMPTED mapping" {
    grep -q '"ORPHANED": "PREEMPTED"' "$ENTRYPOINT"
}

@test "STATUS_COMPAT has RESTARTING → RUNNING mapping" {
    grep -q '"RESTARTING": "RUNNING"' "$ENTRYPOINT"
}

# State transitions validation

@test "entrypoint loads state_transitions.json" {
    grep -q 'state_transitions.json' "$ENTRYPOINT"
}

# Enhanced trap

@test "cleanup trap kills both heartbeat and preemption watcher" {
    grep -q 'HB_PID' "$ENTRYPOINT"
    grep -q '_PREEMPT_PID' "$ENTRYPOINT"
}

# CAS transitions at all lifecycle points

@test "#4a state write: null/RESTARTING → RUNNING on startup" {
    grep -q '_write_state.*RUNNING.*container_started' "$ENTRYPOINT"
}

@test "#4a state write: RUNNING → COMPLETE on success" {
    grep -q '_write_state.*COMPLETE.*job_exit_0' "$ENTRYPOINT"
}

@test "#4a state write: RUNNING → FAILED on failure" {
    grep -q '_write_state.*FAILED.*job_exit' "$ENTRYPOINT"
}

# Discord notification

@test "discord_notify function exists in IXQT entrypoint" {
    grep -q '_discord_notify()' "$ENTRYPOINT"
}

# Critical write helper

@test "gcs_write_critical function exists" {
    grep -q '_gcs_write_critical()' "$ENTRYPOINT"
}

@test "gcs_write_critical retries 3 times" {
    grep -q 'for attempt in 1 2 3' "$ENTRYPOINT"
}

# Version logging (#38)

@test "#38 entrypoint logs state_transitions.json SHA-256" {
    grep -q 'SHA-256' "$ENTRYPOINT"
    grep -q 'sha256sum' "$ENTRYPOINT"
}

# ── gcp-spot-runner entrypoint ──

@test "runner entrypoint has preemption watcher" {
    grep -q '_preemption_watcher()' "$RUNNER_ENTRYPOINT"
}

@test "runner entrypoint has gcs_write_critical" {
    grep -q '_gcs_write_critical()' "$RUNNER_ENTRYPOINT"
}

@test "runner entrypoint has discord_notify" {
    grep -q '_discord_notify()' "$RUNNER_ENTRYPOINT"
}

@test "runner entrypoint cleanup kills heartbeat and preemption watcher" {
    grep -q '_HEARTBEAT_PID' "$RUNNER_ENTRYPOINT"
    grep -q '_PREEMPT_PID' "$RUNNER_ENTRYPOINT"
}

@test "runner entrypoint writes PREEMPTED via critical write" {
    grep -q '_gcs_write_critical.*PREEMPTED' "$RUNNER_ENTRYPOINT"
}
