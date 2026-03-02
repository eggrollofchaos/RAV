#!/usr/bin/env bats
# tests/bats/test_version_parity.bats — RAV version/lineage metadata parity contracts.

load test_helper

_rav_app_version_py() {
  sed -nE 's/^APP_VERSION = "([^"]+)"/\1/p' "$REPO_ROOT/src/rav_chest/version.py" | head -n1
}

_rav_app_version_readme() {
  sed -nE 's/^Current app version: `([^`]+)`/\1/p' "$REPO_ROOT/README.md" | head -n1
}

_rav_app_version_notes() {
  grep -m1 -E '`RAV` app version:' "$REPO_ROOT/gcp/GCP_NOTES.md" \
    | sed -E 's/.*`RAV` app version: `([^`]+)`.*/\1/'
}

_rav_app_version_changelog() {
  grep -m1 -E 'App version to `' "$REPO_ROOT/CHANGELOG.md" \
    | sed -E 's/.*App version to `([^`]+)`.*/\1/'
}

_runner_lineage_readme() {
  sed -nE 's/^Spot runner lineage version: `gcp-spot-runner ([^`]+)`/\1/p' "$REPO_ROOT/README.md" | head -n1
}

_runner_lineage_notes() {
  grep -m1 -E '`gcp-spot-runner` runner version:' "$REPO_ROOT/gcp/GCP_NOTES.md" \
    | sed -E 's/.*`gcp-spot-runner` runner version: `([^`]+)`.*/\1/'
}

_runner_lineage_changelog() {
  grep -m1 -E 'Runner lineage docs synchronized to `gcp-spot-runner ' "$REPO_ROOT/CHANGELOG.md" \
    | sed -E 's/.*`gcp-spot-runner ([^`]+)`.*/\1/'
}

_runner_version_py_if_present() {
  local runner_version_py="$REPO_ROOT/../gcp-spot-runner/version.py"
  if [[ ! -f "$runner_version_py" ]]; then
    printf ''
    return 0
  fi
  sed -nE 's/^APP_VERSION = "([^"]+)"/\1/p' "$runner_version_py" | head -n1
}

@test "README app version matches src/rav_chest/version.py APP_VERSION" {
  local v_py v_readme
  v_py="$(_rav_app_version_py)"
  v_readme="$(_rav_app_version_readme)"

  [ -n "$v_py" ]
  [ -n "$v_readme" ]
  [ "$v_readme" = "$v_py" ]
}

@test "GCP_NOTES + changelog app version references match src/rav_chest/version.py APP_VERSION" {
  local v_py v_notes v_changelog
  v_py="$(_rav_app_version_py)"
  v_notes="$(_rav_app_version_notes)"
  v_changelog="$(_rav_app_version_changelog)"

  [ -n "$v_py" ]
  [ -n "$v_notes" ]
  [ -n "$v_changelog" ]
  [ "$v_notes" = "$v_py" ]
  [ "$v_changelog" = "$v_py" ]
}

@test "runner lineage version references are consistent across README/GCP_NOTES/changelog" {
  local v_readme v_notes v_changelog
  v_readme="$(_runner_lineage_readme)"
  v_notes="$(_runner_lineage_notes)"
  v_changelog="$(_runner_lineage_changelog)"

  [ -n "$v_readme" ]
  [ -n "$v_notes" ]
  [ -n "$v_changelog" ]
  [ "$v_readme" = "$v_notes" ]
  [ "$v_readme" = "$v_changelog" ]
}

@test "runner lineage version matches shared runner version.py when sibling checkout is present" {
  local runner_version_py="$REPO_ROOT/../gcp-spot-runner/version.py"
  if [[ ! -f "$runner_version_py" ]]; then
    skip "Skipping: sibling gcp-spot-runner checkout not present"
  fi

  local v_readme v_runner
  v_readme="$(_runner_lineage_readme)"
  v_runner="$(_runner_version_py_if_present)"

  [ -n "$v_readme" ]
  [ -n "$v_runner" ]
  [ "$v_readme" = "$v_runner" ]
}
