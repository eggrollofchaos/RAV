#!/usr/bin/env bash
# tests/bats/test_helper.bash — Shared setup for RAV GCP shell tests.

BATS_TEST_DIRNAME="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"

# Deterministic env
export TZ=UTC
export LC_ALL=C

# Shim PATH — shims intercept external commands (gcloud, curl, etc.)
export PATH="$BATS_TEST_DIRNAME/shims:$PATH"
export RAV_BATS_TEST=1

# Project env
export PROJECT="ixqt-488109"
export ZONE="us-east1-c"
export BUCKET="ixqt-training-488109"
export RUN_ID="test-20260228-120000"
export REGION="us-east1"

# Shim call log — initialized per-test in setup()
export SHIM_LOG="$BATS_TEST_TMPDIR/shim_calls.log"

load "$BATS_TEST_DIRNAME/lib/bats-support/load"
load "$BATS_TEST_DIRNAME/lib/bats-assert/load"

setup() {
    : > "$SHIM_LOG"
    # Defaults — tests override what they need
    export GCLOUD_VM_EXISTS="true"
    export GCLOUD_CREATE_RESULT="ok"
    export GCLOUD_STORAGE_CAT_RESULT=""
    export GCLOUD_STORAGE_STAT_GEN="1234567890"
    export GCLOUD_STORAGE_CP_RESULT="ok"
    export CURL_PREEMPT_RESULT="FALSE"
    export CURL_TOKEN_RESULT='{"access_token":"fake-token","expires_in":3600,"token_type":"Bearer"}'
    export DISCORD_WEBHOOK_URL=""
    # Unset per-zone create vars
    unset GCLOUD_CREATE_RESULT_us_east1_c 2>/dev/null || true
    unset GCLOUD_CREATE_RESULT_us_east1_b 2>/dev/null || true
    unset GCLOUD_CREATE_RESULT_us_east1_d 2>/dev/null || true
}

fixture_path()    { echo "$BATS_TEST_DIRNAME/fixtures/$1"; }
fixture_content() { cat "$BATS_TEST_DIRNAME/fixtures/$1"; }

assert_shim_called()  { grep -qF "$1" "$SHIM_LOG" || fail "Expected shim call: $1"; }
refute_shim_called()  { ! grep -qF "$1" "$SHIM_LOG" || fail "Unexpected shim call: $1"; }
count_shim_calls()    { grep -cF "$1" "$SHIM_LOG" || echo 0; }
