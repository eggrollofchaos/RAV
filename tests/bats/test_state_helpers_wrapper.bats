#!/usr/bin/env bats
# tests/bats/test_state_helpers_wrapper.bats - adapter contract for state_helpers wrapper.

load test_helper

_make_fake_runner() {
  local fake_runner="$1"
  mkdir -p "$fake_runner"
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
