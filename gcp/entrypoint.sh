#!/usr/bin/env bash
# entrypoint.sh — IXQT container entrypoint with state machine, preemption watcher, CAS transitions
set -euo pipefail

BUCKET="${GCS_BUCKET:-}"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%d_%H%M%S)}"
JOB_COMMAND_RAW="${JOB_COMMAND:-echo 'No JOB_COMMAND set'}"
JOB_COMMAND="$JOB_COMMAND_RAW"
DISCORD_WEBHOOK_URL="${DISCORD_WEBHOOK_URL:-}"
INSTANCE_NAME="$(curl -fsS -H 'Metadata-Flavor: Google' \
  'http://metadata.google.internal/computeMetadata/v1/instance/name' 2>/dev/null || hostname)"
INSTANCE_ZONE="$(curl -fsS -H 'Metadata-Flavor: Google' \
  'http://metadata.google.internal/computeMetadata/v1/instance/zone' 2>/dev/null || echo 'unknown')"
INSTANCE_ZONE="${INSTANCE_ZONE##*/}"
PROJECT_ID="$(curl -fsS -H 'Metadata-Flavor: Google' \
  'http://metadata.google.internal/computeMetadata/v1/project/project-id' 2>/dev/null || echo 'unknown')"

if [[ -z "$BUCKET" ]]; then
  echo "[$(date -u)] FATAL: GCS_BUCKET not set."
  exit 1
fi

# Decode base64-encoded JOB_COMMAND from VM metadata
if [[ "$JOB_COMMAND_RAW" =~ ^[A-Za-z0-9+/=]+$ ]]; then
  if DECODED_JOB_COMMAND="$(printf '%s' "$JOB_COMMAND_RAW" | base64 --decode 2>/dev/null)"; then
    if [[ -n "$DECODED_JOB_COMMAND" ]]; then
      JOB_COMMAND="$DECODED_JOB_COMMAND"
    fi
  fi
fi

_STATE_JSON_PATH="gs://${BUCKET}/runs/${RUN_ID}/state.json"
_STATUS_TXT_PATH="gs://${BUCKET}/runs/${RUN_ID}/status.txt"
_EVENTS_PREFIX="gs://${BUCKET}/runs/${RUN_ID}/events"

# ──── Helpers ────

_now_iso() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

_gcs_upload_string() {
  local gcs_path="$1" content="$2" content_type="${3:-application/json}"
  local tmp
  tmp="$(mktemp)"
  printf '%s' "$content" > "$tmp"
  gcloud storage cp "$tmp" "$gcs_path" --content-type="$content_type" >/dev/null 2>&1 || true
  rm -f "$tmp"
}

_gcs_write_critical() {
  # Critical write with retry 3x + fail-loud
  local gcs_path="$1" content="$2" content_type="${3:-application/json}"
  local tmp attempt
  tmp="$(mktemp)"
  printf '%s' "$content" > "$tmp"
  for attempt in 1 2 3; do
    if gcloud storage cp "$tmp" "$gcs_path" --content-type="$content_type" >/dev/null 2>&1; then
      rm -f "$tmp"
      return 0
    fi
    echo "[$(date -u)] WARNING: Critical write attempt ${attempt}/3 failed for ${gcs_path}" >&2
    sleep $((attempt * 2))
  done
  rm -f "$tmp"
  echo "[$(date -u)] ERROR: Critical write FAILED after 3 attempts for ${gcs_path}" >&2
  return 1
}

_discord_notify() {
  local msg="$1"
  if [[ -z "$DISCORD_WEBHOOK_URL" ]]; then
    return 0
  fi
  local payload
  payload="$(python3 -c "import json,sys; print(json.dumps({'content': sys.argv[1]}))" "$msg" 2>/dev/null || true)"
  if [[ -n "$payload" ]]; then
    curl -s --max-time 5 --retry 1 --retry-connrefused \
      -H "Content-Type: application/json" -d "$payload" \
      "$DISCORD_WEBHOOK_URL" >/dev/null 2>&1 || true
  fi
}

# ──── State machine: _write_state() via Python CAS ────
# Uses python3 + google-cloud-storage for if_generation_match CAS operations.

_write_state() {
  # Usage: _write_state NEW_STATE REASON [ACTOR]
  # Returns 0 on success, 1 on failure (terminal precedence, CAS race, etc.)
  local new_state="$1"
  local reason="${2:-}"
  local actor="${3:-vm}"

  python3 - "$new_state" "$reason" "$actor" <<'PYEOF'
import json, sys, os, uuid, datetime

new_state = sys.argv[1]
reason = sys.argv[2]
actor = sys.argv[3]

bucket_name = os.environ["GCS_BUCKET"]
run_id = os.environ["RUN_ID"]
instance_name = os.environ.get("INSTANCE_NAME", "unknown")
instance_zone = os.environ.get("INSTANCE_ZONE", "unknown")

# Load transitions
transitions_path = None
for p in ["/app/gcp/state_transitions.json", "/app/state_transitions.json"]:
    if os.path.exists(p):
        transitions_path = p
        break

TERMINAL = {"COMPLETE", "FAILED", "PARTIAL", "STOPPED"}
STATUS_COMPAT = {
    "RUNNING": "RUNNING", "COMPLETE": "COMPLETE", "FAILED": "FAILED",
    "PARTIAL": "PARTIAL", "PREEMPTED": "PREEMPTED", "ORPHANED": "PREEMPTED",
    "RESTARTING": "RUNNING", "STOPPED": "STOPPED",
}
VALID_ACTORS = {"vm", "reconciler", "local", "operator"}

if transitions_path:
    with open(transitions_path) as f:
        transitions = json.load(f)
else:
    # Inline fallback
    transitions = {
        "edges": {
            "null": ["RUNNING", "ORPHANED"],
            "RUNNING": ["COMPLETE","FAILED","PARTIAL","PREEMPTED","ORPHANED","STOPPED"],
            "PREEMPTED": ["RESTARTING","STOPPED"],
            "ORPHANED": ["RESTARTING","STOPPED"],
            "RESTARTING": ["RUNNING","ORPHANED","STOPPED"],
        },
        "actor_guards": {"null:ORPHANED": ["reconciler"]}
    }

if actor not in VALID_ACTORS:
    print(f"[write_state] ERROR: unknown actor '{actor}'", file=sys.stderr)
    sys.exit(1)

from google.cloud import storage
client = storage.Client()
bucket = client.bucket(bucket_name)
state_blob = bucket.blob(f"runs/{run_id}/state.json")

MAX_CAS_RETRIES = 3
for cas_attempt in range(MAX_CAS_RETRIES):
    # Read current state
    current_state = None
    current_data = {}
    generation = 0

    try:
        raw = state_blob.download_as_text()
        current_data = json.loads(raw)
        current_state = current_data.get("state")
        generation = state_blob.generation
    except Exception:
        # No state.json yet — first write
        generation = 0

    # Terminal check: cannot overwrite terminal states
    if current_state in TERMINAL:
        print(f"[write_state] Skipping {current_state} → {new_state}: current state is terminal", file=sys.stderr)
        sys.exit(1)

    # Validate transition
    from_key = "null" if current_state is None else current_state
    allowed = transitions.get("edges", {}).get(from_key, [])
    if new_state not in allowed:
        print(f"[write_state] Transition {from_key} → {new_state} not allowed", file=sys.stderr)
        sys.exit(1)

    # Actor guard check
    guard_key = f"{from_key}:{new_state}"
    guards = transitions.get("actor_guards", {}).get(guard_key, [])
    if guards and actor not in guards:
        print(f"[write_state] Actor '{actor}' not allowed for {guard_key}", file=sys.stderr)
        sys.exit(1)

    # Build new state.json
    state_version = current_data.get("state_version", current_data.get("generation", 0)) + 1
    history = current_data.get("history", [])
    history_entry = {
        "from": current_state, "to": new_state,
        "at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "by": actor, "reason": reason,
    }
    history.append(history_entry)
    if len(history) > 20:
        history = history[-20:]

    new_data = {
        "state": new_state,
        "prev_state": current_state,
        "state_version": state_version,
        "owner_id": instance_name,
        "instance_name": instance_name,
        "zone": instance_zone,
        "attempt": current_data.get("attempt", 0),
        "updated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "updated_by": actor,
        "reason": reason,
        "history": history,
    }

    # CAS write
    try:
        state_blob.upload_from_string(
            json.dumps(new_data, indent=2),
            content_type="application/json",
            if_generation_match=generation,
        )
    except Exception as e:
        if "conditionNotMet" in str(e) or "PreconditionFailed" in str(e):
            print(f"[write_state] CAS conflict (attempt {cas_attempt+1}/{MAX_CAS_RETRIES}), retrying...", file=sys.stderr)
            import time; time.sleep(1)
            continue
        print(f"[write_state] ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # Write status.txt with compatibility mapping (critical)
    status_txt_value = STATUS_COMPAT.get(new_state, new_state)
    status_blob = bucket.blob(f"runs/{run_id}/status.txt")
    for st_attempt in range(3):
        try:
            status_blob.upload_from_string(status_txt_value, content_type="text/plain")
            break
        except Exception:
            import time; time.sleep(st_attempt + 1)

    # Append event (best-effort)
    try:
        short_uuid = uuid.uuid4().hex[:8]
        ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        event_blob = bucket.blob(f"runs/{run_id}/events/{ts}_{actor}_{short_uuid}.json")
        event_blob.upload_from_string(json.dumps(history_entry), content_type="application/json")
    except Exception:
        pass

    print(f"[write_state] {from_key} → {new_state} (v{state_version}, by={actor}, reason={reason})")
    sys.exit(0)

print("[write_state] ERROR: CAS retries exhausted", file=sys.stderr)
sys.exit(1)
PYEOF
}

# ──── Startup terminal guard ────
# Read state.json BEFORE doing anything. If terminal, self-delete and exit.

_startup_terminal_guard() {
  echo "[$(date -u)] Checking state.json for terminal state..."
  local state_raw attempt
  for attempt in 1 2 3; do
    state_raw="$(gcloud storage cat "$_STATE_JSON_PATH" 2>/dev/null || true)"
    if [[ -n "$state_raw" ]]; then
      break
    fi
    if [[ $attempt -lt 3 ]]; then
      sleep 2
    fi
  done

  if [[ -n "$state_raw" ]]; then
    local current_state
    current_state="$(echo "$state_raw" | python3 -c "import json,sys; print(json.load(sys.stdin).get('state',''))" 2>/dev/null || true)"
    case "$current_state" in
      STOPPED|COMPLETE|FAILED|PARTIAL)
        echo "[$(date -u)] Terminal state detected: $current_state. Self-deleting VM."
        _discord_notify "WARN: [${RUN_ID}] VM started but state is $current_state. Self-deleting."
        _self_delete_vm
        exit 0
        ;;
    esac
  fi
  # No state.json or non-terminal — continue normally
}

_self_delete_vm() {
  local token_json token
  token_json="$(curl -fsS -H 'Metadata-Flavor: Google' \
    'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token' 2>/dev/null || true)"
  token="$(echo "$token_json" | jq -r '.access_token // empty' 2>/dev/null || true)"
  if [[ -n "$token" ]] && [[ "$PROJECT_ID" != "unknown" ]] && [[ "$INSTANCE_ZONE" != "unknown" ]]; then
    curl -fsS -X DELETE \
      -H "Authorization: Bearer ${token}" \
      "https://compute.googleapis.com/compute/v1/projects/${PROJECT_ID}/zones/${INSTANCE_ZONE}/instances/${INSTANCE_NAME}" \
      >/dev/null 2>&1 || true
    echo "[$(date -u)] Self-delete issued for ${INSTANCE_NAME}"
  fi
}

# ──── Preemption watcher ────

_preemption_watcher() {
  # Polls metadata preemption endpoint every 5s
  # On preemption: CAS write PREEMPTED, send Discord, exit
  while true; do
    sleep 5
    # Synthetic test hook
    if [[ "${IXQT_TEST_SYNTH_PREEMPT:-}" == "1" ]]; then
      echo "[$(date -u)] SYNTH PREEMPT triggered"
      _handle_preemption
      return
    fi
    local preempted
    preempted="$(curl -sf -H 'Metadata-Flavor: Google' \
      'http://metadata.google.internal/computeMetadata/v1/instance/preempted' 2>/dev/null || echo 'FALSE')"
    if [[ "$preempted" == "TRUE" ]]; then
      echo "[$(date -u)] PREEMPTION DETECTED via metadata"
      _handle_preemption
      return
    fi
  done
}

_handle_preemption() {
  # CAS write PREEMPTED. If state is already terminal, skip.
  set +e
  _write_state "PREEMPTED" "preemption_detected" "vm"
  local rc=$?
  set -e

  if [[ $rc -eq 0 ]]; then
    echo "[$(date -u)] State written: PREEMPTED"
    _discord_notify "WARN: [${RUN_ID}] VM preempted on ${INSTANCE_NAME} (${INSTANCE_ZONE})"
  else
    echo "[$(date -u)] Could not write PREEMPTED (state may already be terminal)"
  fi

  # Kill heartbeat — VM is going down
  if [[ -n "${HB_PID:-}" ]]; then
    kill "$HB_PID" 2>/dev/null || true
  fi
}

# ──── Run startup guard ────
_startup_terminal_guard

echo "[$(date -u)] Starting run ${RUN_ID} on ${INSTANCE_NAME} (${INSTANCE_ZONE})"
echo "[$(date -u)] Job: ${JOB_COMMAND}"

# Log state_transitions.json hash for version tracking
if [[ -f /app/gcp/state_transitions.json ]]; then
  echo "[$(date -u)] state_transitions.json SHA-256: $(sha256sum /app/gcp/state_transitions.json 2>/dev/null | cut -c1-64 || echo 'unknown')"
elif [[ -f /app/state_transitions.json ]]; then
  echo "[$(date -u)] state_transitions.json SHA-256: $(sha256sum /app/state_transitions.json 2>/dev/null | cut -c1-64 || echo 'unknown')"
fi

# ──── CAS: null/RESTARTING → RUNNING ────

set +e
_write_state "RUNNING" "container_started" "vm"
set -e

START_EPOCH="$(date +%s)"
HB_EXIT=0
HB_PHASE="running"

# ──── Upload run manifest ────

_manifest_path="gs://${BUCKET}/runs/${RUN_ID}/run_manifest.json"
_run_manifest="$(jq -n \
  --argjson schema_version 1 \
  --arg run_id "$RUN_ID" \
  --arg instance "$INSTANCE_NAME" \
  --arg zone "$INSTANCE_ZONE" \
  --arg phase "running" \
  --argjson exit_code null \
  --arg started_at "$(_now_iso)" \
  '{schema_version:$schema_version, run_id:$run_id, instance:$instance, zone:$zone, phase:$phase, exit_code:$exit_code, started_at:$started_at, finished_at:null}'
)"
_gcs_upload_string "$_manifest_path" "$_run_manifest"

# ──── Background heartbeat loop ────

_heartbeat_loop() {
  while true; do
    sleep 30
    local now_epoch uptime hb
    now_epoch="$(date +%s)"
    uptime=$((now_epoch - START_EPOCH))
    hb="$(jq -n \
      --arg timestamp "$(_now_iso)" \
      --arg phase "$HB_PHASE" \
      --argjson uptime_sec "$uptime" \
      --argjson exit_code "$HB_EXIT" \
      '{timestamp:$timestamp, phase:$phase, uptime_sec:$uptime_sec, exit_code:$exit_code}'
    )"
    _gcs_upload_string "gs://${BUCKET}/runs/${RUN_ID}/heartbeat.json" "$hb"
  done
}

_heartbeat_loop &
HB_PID=$!

# ──── Launch preemption watcher ────
_preemption_watcher &
_PREEMPT_PID=$!

# ──── Enhanced cleanup trap ────
_cleanup() {
  kill "$HB_PID" 2>/dev/null || true
  kill "$_PREEMPT_PID" 2>/dev/null || true
}
trap _cleanup EXIT INT TERM

# ──── Run the job ────

set +e
bash -lc "$JOB_COMMAND"
JOB_EXIT=$?
set -e

HB_EXIT=$JOB_EXIT
HB_PHASE="finished"
echo "[$(date -u)] Job finished with exit code ${JOB_EXIT}"

# ──── Upload results ────

if [[ -d /app/results ]]; then
  echo "[$(date -u)] Uploading /app/results to GCS..."
  gcloud storage cp -r /app/results/* "gs://${BUCKET}/runs/${RUN_ID}/results/" >/dev/null 2>&1 || true
fi

# ──── CAS: RUNNING → terminal state ────

if [[ $JOB_EXIT -eq 0 ]]; then
  _write_state "COMPLETE" "job_exit_0" "vm" || true
else
  _write_state "FAILED" "job_exit_${JOB_EXIT}" "vm" || true
fi

# ──── Update run manifest ────

_final_manifest="$(jq -n \
  --argjson schema_version 1 \
  --arg run_id "$RUN_ID" \
  --arg instance "$INSTANCE_NAME" \
  --arg zone "$INSTANCE_ZONE" \
  --arg phase "finished" \
  --argjson exit_code "$JOB_EXIT" \
  --arg started_at "$(date -u -d @"$START_EPOCH" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || _now_iso)" \
  --arg finished_at "$(_now_iso)" \
  '{schema_version:$schema_version, run_id:$run_id, instance:$instance, zone:$zone, phase:$phase, exit_code:$exit_code, started_at:$started_at, finished_at:$finished_at}'
)"
_gcs_write_critical "$_manifest_path" "$_final_manifest" || true

# ──── Self-delete VM ────

echo "[$(date -u)] Issuing self-delete request..."
_self_delete_vm

exit "$JOB_EXIT"
