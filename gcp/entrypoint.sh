#!/usr/bin/env bash
set -euo pipefail

BUCKET="${GCS_BUCKET:-}"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%d_%H%M%S)}"
JOB_COMMAND="${JOB_COMMAND:-echo 'No JOB_COMMAND set'}"
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

_now_iso() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

_gcs_upload_string() {
  local gcs_path="$1"
  local content="$2"
  local content_type="${3:-application/json}"
  local tmp
  tmp="$(mktemp)"
  printf '%s' "$content" > "$tmp"
  gcloud storage cp "$tmp" "$gcs_path" --content-type="$content_type" >/dev/null 2>&1 || true
  rm -f "$tmp"
}

echo "[$(date -u)] Starting run ${RUN_ID} on ${INSTANCE_NAME} (${INSTANCE_ZONE})"
echo "[$(date -u)] Job: ${JOB_COMMAND}"

START_EPOCH="$(date +%s)"
HB_EXIT=0
HB_PHASE="running"

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

_heartbeat_loop() {
  while true; do
    sleep 30
    local now_epoch
    now_epoch="$(date +%s)"
    local uptime=$((now_epoch - START_EPOCH))
    local hb
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
cleanup() {
  kill "$HB_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

set +e
bash -lc "$JOB_COMMAND"
JOB_EXIT=$?
set -e

HB_EXIT=$JOB_EXIT
HB_PHASE="finished"
echo "[$(date -u)] Job finished with exit code ${JOB_EXIT}"

if [[ -d /app/results ]]; then
  echo "[$(date -u)] Uploading /app/results to GCS..."
  gcloud storage cp -r /app/results/* "gs://${BUCKET}/runs/${RUN_ID}/results/" >/dev/null 2>&1 || true
fi

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
_gcs_upload_string "$_manifest_path" "$_final_manifest"

echo "[$(date -u)] Issuing self-delete request..."
ACCESS_TOKEN_JSON="$(curl -fsS -H 'Metadata-Flavor: Google' \
  'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token' 2>/dev/null || true)"
TOKEN="$(echo "$ACCESS_TOKEN_JSON" | jq -r '.access_token // empty' 2>/dev/null || true)"
if [[ -n "$TOKEN" ]] && [[ "$PROJECT_ID" != "unknown" ]] && [[ "$INSTANCE_ZONE" != "unknown" ]]; then
  curl -fsS -X DELETE \
    -H "Authorization: Bearer ${TOKEN}" \
    "https://compute.googleapis.com/compute/v1/projects/${PROJECT_ID}/zones/${INSTANCE_ZONE}/instances/${INSTANCE_NAME}" \
    >/dev/null 2>&1 || true
fi

exit "$JOB_EXIT"
