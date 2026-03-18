#!/usr/bin/env bats
# tests/bats/test_state_helpers_wrapper.bats - adapter contract for state_helpers wrapper.

load test_helper

_make_fake_runner() {
  local fake_runner="$1"
  mkdir -p "$fake_runner/adapters"
  printf '%s\n' 'APP_VERSION = "v0.6.40-phase7-wrapper-runtime-init"' > "$fake_runner/version.py"
  cat > "$fake_runner/adapters/spot_runner_bootstrap.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
spot_runner_bootstrap_initialize_project_wrapper_runtime_wrapper_defaults_for_common_required() {
  local hint_message="${1:-Set RUNNER_DIR in gcp/rav_spot.env to your gcp-spot-runner checkout.}"
  local project_root="${2:-}"
  printf -v RUNNER_BOOTSTRAP_DIR_DEFAULT '%s' "${RUNNER_DIR:-${project_root}/../gcp-spot-runner}"
  printf -v RUNNER_HINT_MESSAGE '%s' "${hint_message}"
}
EOF
  chmod +x "$fake_runner/adapters/spot_runner_bootstrap.sh"
  cat > "$fake_runner/state_helpers.sh" <<'EOF'
#!/usr/bin/env bash
can_transition() {
  echo "shared-can-transition:$1:$2:$3"
  return 0
}
_state_transitions_hash() {
  echo "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
}
EOF
  chmod +x "$fake_runner/state_helpers.sh"
}

@test "RAV state_helpers wrapper delegates to shared runner implementation" {
  local fake_runner="$BATS_TEST_TMPDIR/fake-runner"
  _make_fake_runner "$fake_runner"

  run bash -c "
    RUNNER_DIR='$fake_runner'
    source '$REPO_ROOT/gcp/state_helpers.sh'
    can_transition RUNNING COMPLETE vm
  "
  assert_success
  assert_output "shared-can-transition:RUNNING:COMPLETE:vm"
}

@test "RAV state_helpers wrapper errors when runner cannot be resolved" {
  run bash -c "
    RUNNER_DIR='$BATS_TEST_TMPDIR/does-not-exist'
    source '$REPO_ROOT/gcp/state_helpers.sh'
  " 2>&1
  assert_failure
  assert_output --partial "Unable to locate gcp-spot-runner"
}
