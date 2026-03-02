#!/usr/bin/env bats
# tests/bats/test_state_transitions_parity.bats - ensure local transition map stays in sync with runner canonical.

load test_helper

_resolve_runner_dir() {
  local explicit candidate
  explicit="${RUNNER_DIR:-${GCP_SPOT_RUNNER_DIR:-}}"
  if [[ -n "$explicit" ]]; then
    if [[ "$explicit" != /* ]]; then
      explicit="${REPO_ROOT}/${explicit}"
    fi
    [[ -d "$explicit" ]] && { cd "$explicit" && pwd; return 0; }
    return 1
  fi

  for candidate in \
    "${REPO_ROOT}/../gcp-spot-runner" \
    "${REPO_ROOT}/gcp-spot-runner"; do
    if [[ -d "$candidate" ]]; then
      cd "$candidate" && pwd
      return 0
    fi
  done
  return 1
}

@test "RAV state_transitions.json matches runner canonical map" {
  local runner_dir
  runner_dir="$(_resolve_runner_dir)"
  [ -n "$runner_dir" ]

  local local_map="$REPO_ROOT/gcp/state_transitions.json"
  local canonical_map="$runner_dir/cloud_reconciler/state_transitions.json"
  [ -f "$local_map" ]
  [ -f "$canonical_map" ]

  local local_hash canonical_hash
  local_hash="$(shasum -a 256 "$local_map" | cut -c1-64)"
  canonical_hash="$(shasum -a 256 "$canonical_map" | cut -c1-64)"
  [ "$local_hash" = "$canonical_hash" ]
}
