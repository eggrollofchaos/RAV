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

# ── gcp-spot-runner ──

@test "caffeinate present in gcp-spot-runner submit.sh" {
    grep -q "caffeinate -i" /Users/wax/Documents/Programming/gcp-spot-runner/submit.sh
}

@test "HUP trap present in gcp-spot-runner submit.sh" {
    grep -q "trap '' HUP" /Users/wax/Documents/Programming/gcp-spot-runner/submit.sh
}

@test "caffeinate guard in gcp-spot-runner uses _SPOT_CAFFEINATED" {
    grep -q '_SPOT_CAFFEINATED' /Users/wax/Documents/Programming/gcp-spot-runner/submit.sh
}

# ── #2: Linux (no caffeinate binary) skip ──

@test "#2 caffeinate guard skips when binary not found" {
    # The guard has 'command -v caffeinate' check
    # In a system without caffeinate, the exec line is skipped
    grep -q 'command -v caffeinate' "$REPO_ROOT/scripts/gcp_submit_primary.sh"
}

# ── #3: set -E (errtrace) for ERR trap support ──

@test "gcp-spot-runner submit.sh uses set -Eeuo pipefail" {
    grep -q 'set -Eeuo pipefail' /Users/wax/Documents/Programming/gcp-spot-runner/submit.sh
}

# ── Verify caffeinate comes before set -euo ──

@test "caffeinate appears before set -e in gcp-spot-runner" {
    local caff_line hup_line set_line
    caff_line=$(grep -n 'caffeinate -i' /Users/wax/Documents/Programming/gcp-spot-runner/submit.sh | head -1 | cut -d: -f1)
    set_line=$(grep -n 'set -Eeuo' /Users/wax/Documents/Programming/gcp-spot-runner/submit.sh | head -1 | cut -d: -f1)
    [[ $caff_line -lt $set_line ]]
}

@test "HUP trap appears before set -e in gcp-spot-runner" {
    local hup_line set_line
    hup_line=$(grep -n "trap '' HUP" /Users/wax/Documents/Programming/gcp-spot-runner/submit.sh | head -1 | cut -d: -f1)
    set_line=$(grep -n 'set -Eeuo' /Users/wax/Documents/Programming/gcp-spot-runner/submit.sh | head -1 | cut -d: -f1)
    [[ $hup_line -lt $set_line ]]
}
