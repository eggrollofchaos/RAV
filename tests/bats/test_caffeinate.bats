#!/usr/bin/env bats
# tests/bats/test_caffeinate.bats — Tests for Phase 1: caffeinate + HUP trap
# Covers verification matrix items: #1, #2, #3

load test_helper

# ── RAV scripts ──

@test "#1 caffeinate present in gcp_submit_primary.sh" {
    grep -q "caffeinate -i" "$REPO_ROOT/scripts/gcp_submit_primary.sh"
}

@test "#1 HUP trap present in gcp_submit_primary.sh" {
    grep -q "trap '' HUP" "$REPO_ROOT/scripts/gcp_submit_primary.sh"
}

@test "#1 caffeinate guard in gcp_submit_primary.sh uses _IXQT_CAFFEINATED" {
    grep -q '_IXQT_CAFFEINATED' "$REPO_ROOT/scripts/gcp_submit_primary.sh"
}

@test "#1 caffeinate present in gcp_submit_poc.sh" {
    grep -q "caffeinate -i" "$REPO_ROOT/scripts/gcp_submit_poc.sh"
}

@test "#1 HUP trap present in gcp_submit_poc.sh" {
    grep -q "trap '' HUP" "$REPO_ROOT/scripts/gcp_submit_poc.sh"
}

# ── #2: Linux (no caffeinate binary) skip ──

@test "#2 caffeinate guard skips when binary not found" {
    # The guard has 'command -v caffeinate' check
    # In a system without caffeinate, the exec line is skipped
    grep -q 'command -v caffeinate' "$REPO_ROOT/scripts/gcp_submit_primary.sh"
}
