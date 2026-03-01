#!/usr/bin/env bats
# tests/bats/test_state_machine.bats — Tests for gcp/state_helpers.sh + state_transitions.json
# Covers verification matrix items: #5, #30, #31, #38

load test_helper

# Source state_helpers.sh (uses real jq, not shimmed)
_source_state_helpers() {
    source "$REPO_ROOT/gcp/state_helpers.sh"
}

# ── Terminal state checks ──

@test "terminal states: COMPLETE is terminal" {
    _source_state_helpers
    run _is_terminal_state "COMPLETE"
    assert_success
}

@test "terminal states: FAILED is terminal" {
    _source_state_helpers
    run _is_terminal_state "FAILED"
    assert_success
}

@test "terminal states: PARTIAL is terminal" {
    _source_state_helpers
    run _is_terminal_state "PARTIAL"
    assert_success
}

@test "terminal states: STOPPED is terminal" {
    _source_state_helpers
    run _is_terminal_state "STOPPED"
    assert_success
}

@test "terminal states: RUNNING is not terminal" {
    _source_state_helpers
    run _is_terminal_state "RUNNING"
    assert_failure
}

@test "terminal states: PREEMPTED is not terminal" {
    _source_state_helpers
    run _is_terminal_state "PREEMPTED"
    assert_failure
}

@test "terminal states: ORPHANED is not terminal" {
    _source_state_helpers
    run _is_terminal_state "ORPHANED"
    assert_failure
}

@test "terminal states: RESTARTING is not terminal" {
    _source_state_helpers
    run _is_terminal_state "RESTARTING"
    assert_failure
}

# ── Status compatibility mapping ──

@test "status compat: RUNNING → RUNNING" {
    _source_state_helpers
    run _status_compat_map "RUNNING"
    assert_output "RUNNING"
}

@test "status compat: ORPHANED → PREEMPTED" {
    _source_state_helpers
    run _status_compat_map "ORPHANED"
    assert_output "PREEMPTED"
}

@test "status compat: RESTARTING → RUNNING" {
    _source_state_helpers
    run _status_compat_map "RESTARTING"
    assert_output "RUNNING"
}

@test "status compat: STOPPED → STOPPED" {
    _source_state_helpers
    run _status_compat_map "STOPPED"
    assert_output "STOPPED"
}

@test "status compat: PREEMPTED → PREEMPTED" {
    _source_state_helpers
    run _status_compat_map "PREEMPTED"
    assert_output "PREEMPTED"
}

@test "status compat: PARTIAL → PARTIAL" {
    _source_state_helpers
    run _status_compat_map "PARTIAL"
    assert_output "PARTIAL"
}

# ── Transition validation (can_transition) ──

@test "transition: null → RUNNING allowed for vm" {
    _source_state_helpers
    run can_transition "null" "RUNNING" "vm"
    assert_success
}

@test "transition: null → ORPHANED allowed for reconciler" {
    _source_state_helpers
    run can_transition "null" "ORPHANED" "reconciler"
    assert_success
}

@test "#31 actor guard: null → ORPHANED rejected for vm" {
    _source_state_helpers
    run can_transition "null" "ORPHANED" "vm"
    assert_failure
    assert_output --partial "guarded"
}

@test "#31 actor guard: null → ORPHANED rejected for local" {
    _source_state_helpers
    run can_transition "null" "ORPHANED" "local"
    assert_failure
    assert_output --partial "guarded"
}

@test "transition: RUNNING → COMPLETE allowed" {
    _source_state_helpers
    run can_transition "RUNNING" "COMPLETE" "vm"
    assert_success
}

@test "transition: RUNNING → FAILED allowed" {
    _source_state_helpers
    run can_transition "RUNNING" "FAILED" "vm"
    assert_success
}

@test "transition: RUNNING → PARTIAL allowed" {
    _source_state_helpers
    run can_transition "RUNNING" "PARTIAL" "vm"
    assert_success
}

@test "transition: RUNNING → PREEMPTED allowed" {
    _source_state_helpers
    run can_transition "RUNNING" "PREEMPTED" "vm"
    assert_success
}

@test "transition: RUNNING → ORPHANED allowed" {
    _source_state_helpers
    run can_transition "RUNNING" "ORPHANED" "reconciler"
    assert_success
}

@test "transition: RUNNING → STOPPED allowed" {
    _source_state_helpers
    run can_transition "RUNNING" "STOPPED" "operator"
    assert_success
}

@test "transition: PREEMPTED → RESTARTING allowed" {
    _source_state_helpers
    run can_transition "PREEMPTED" "RESTARTING" "local"
    assert_success
}

@test "transition: PREEMPTED → STOPPED allowed" {
    _source_state_helpers
    run can_transition "PREEMPTED" "STOPPED" "operator"
    assert_success
}

@test "transition: ORPHANED → RESTARTING allowed" {
    _source_state_helpers
    run can_transition "ORPHANED" "RESTARTING" "reconciler"
    assert_success
}

@test "transition: RESTARTING → RUNNING allowed" {
    _source_state_helpers
    run can_transition "RESTARTING" "RUNNING" "vm"
    assert_success
}

@test "transition: RESTARTING → ORPHANED allowed" {
    _source_state_helpers
    run can_transition "RESTARTING" "ORPHANED" "reconciler"
    assert_success
}

@test "transition: RESTARTING → STOPPED allowed" {
    _source_state_helpers
    run can_transition "RESTARTING" "STOPPED" "operator"
    assert_success
}

# ── Disallowed transitions ──

@test "#5 terminal precedence: COMPLETE → anything rejected" {
    _source_state_helpers
    run can_transition "COMPLETE" "RUNNING" "vm"
    assert_failure
    assert_output --partial "not allowed"
}

@test "terminal: FAILED → RUNNING rejected" {
    _source_state_helpers
    run can_transition "FAILED" "RUNNING" "vm"
    assert_failure
}

@test "terminal: STOPPED → RUNNING rejected" {
    _source_state_helpers
    run can_transition "STOPPED" "RUNNING" "vm"
    assert_failure
}

@test "terminal: PARTIAL → anything rejected" {
    _source_state_helpers
    run can_transition "PARTIAL" "RUNNING" "vm"
    assert_failure
}

@test "invalid: RUNNING → RESTARTING not allowed" {
    _source_state_helpers
    run can_transition "RUNNING" "RESTARTING" "local"
    assert_failure
}

@test "invalid: PREEMPTED → RUNNING not allowed (must go through RESTARTING)" {
    _source_state_helpers
    run can_transition "PREEMPTED" "RUNNING" "vm"
    assert_failure
}

@test "invalid: null → COMPLETE not allowed" {
    _source_state_helpers
    run can_transition "null" "COMPLETE" "vm"
    assert_failure
}

# ── Actor validation ──

@test "actor: empty actor rejected" {
    _source_state_helpers
    run can_transition "RUNNING" "COMPLETE" ""
    assert_failure
    assert_output --partial "actor is required"
}

@test "actor: unknown actor rejected" {
    _source_state_helpers
    run can_transition "RUNNING" "COMPLETE" "unknown_actor"
    assert_failure
    assert_output --partial "unknown actor"
}

@test "actor: valid actors accepted" {
    _source_state_helpers
    for actor in vm reconciler local operator; do
        run can_transition "RUNNING" "COMPLETE" "$actor"
        assert_success
    done
}

# ── Hash verification ──

@test "#38 transitions hash: SHA-256 is 64 hex chars" {
    _source_state_helpers
    run _state_transitions_hash
    assert_success
    # SHA-256 hash should be 64 hex chars
    [[ "${#output}" -eq 64 ]]
    [[ "$output" =~ ^[0-9a-f]{64}$ ]]
}

@test "#38 transitions hash: matches shasum directly" {
    _source_state_helpers
    local expected
    expected="$(shasum -a 256 "$REPO_ROOT/gcp/state_transitions.json" | cut -c1-64)"
    run _state_transitions_hash
    assert_output "$expected"
}

# ── state_transitions.json integrity ──

@test "transitions file: valid JSON" {
    run jq empty "$REPO_ROOT/gcp/state_transitions.json"
    assert_success
}

@test "transitions file: has edges and actor_guards keys" {
    local keys
    keys="$(jq -r 'keys[]' "$REPO_ROOT/gcp/state_transitions.json" | sort)"
    [[ "$keys" == *"actor_guards"* ]]
    [[ "$keys" == *"edges"* ]]
}

@test "transitions file: all edge targets are valid states" {
    local valid_states="RUNNING COMPLETE FAILED PARTIAL PREEMPTED ORPHANED RESTARTING STOPPED"
    local all_targets
    all_targets="$(jq -r '.edges | [.[] | .[]] | unique | .[]' "$REPO_ROOT/gcp/state_transitions.json")"
    while IFS= read -r target; do
        [[ " $valid_states " == *" $target "* ]] || fail "Unknown target state: $target"
    done <<< "$all_targets"
}
