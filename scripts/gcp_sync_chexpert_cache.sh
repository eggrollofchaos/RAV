#!/usr/bin/env bash
set -euo pipefail

RAW_URI=""
PROCESSED_URI=""
CACHE_ROOT="data"
MARKER_NAME="chexpert"
FORCE_SYNC=false

usage() {
  cat <<'EOF'
Usage: gcp_sync_chexpert_cache.sh --raw-uri gs://... --processed-uri gs://... [options]

Options:
  --raw-uri URI           GCS URI for raw CheXpert prefix (required)
  --processed-uri URI     GCS URI for processed prefix (required)
  --cache-root PATH       Local cache root (default: data)
  --marker-name NAME      Marker namespace (default: chexpert)
  --force                 Force re-sync even when cache marker exists
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --raw-uri)
      RAW_URI="$2"
      shift 2
      ;;
    --processed-uri)
      PROCESSED_URI="$2"
      shift 2
      ;;
    --cache-root)
      CACHE_ROOT="$2"
      shift 2
      ;;
    --marker-name)
      MARKER_NAME="$2"
      shift 2
      ;;
    --force)
      FORCE_SYNC=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$RAW_URI" || -z "$PROCESSED_URI" ]]; then
  echo "Both --raw-uri and --processed-uri are required." >&2
  usage >&2
  exit 2
fi

RAW_DIR="${CACHE_ROOT}/raw/chexpert"
PROCESSED_DIR="${CACHE_ROOT}/processed"
STATE_DIR="${CACHE_ROOT}/.sync_state"
RAW_MARKER="${STATE_DIR}/${MARKER_NAME}_raw.marker"
PROCESSED_MARKER="${STATE_DIR}/${MARKER_NAME}_processed.marker"

mkdir -p "$RAW_DIR" "$PROCESSED_DIR" "$STATE_DIR"

_has_files() {
  local dir="$1"
  find "$dir" -type f -print -quit 2>/dev/null | grep -q .
}

_marker_matches_uri() {
  local marker="$1"
  local uri="$2"
  [[ -f "$marker" ]] || return 1
  grep -Fqx "uri=${uri}" "$marker"
}

_write_marker() {
  local marker="$1"
  local uri="$2"
  {
    echo "uri=${uri}"
    echo "synced_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  } > "$marker"
}

sync_prefix() {
  local uri="$1"
  local target="$2"
  local marker="$3"

  if [[ "$FORCE_SYNC" != true ]] && _marker_matches_uri "$marker" "$uri" && _has_files "$target"; then
    echo "[cache] hit: ${target} (marker=${marker})"
    return 0
  fi

  echo "[cache] syncing ${uri} -> ${target}"
  gcloud storage rsync -r "$uri" "$target"
  _write_marker "$marker"
}

sync_prefix "$RAW_URI" "$RAW_DIR" "$RAW_MARKER"
sync_prefix "$PROCESSED_URI" "$PROCESSED_DIR" "$PROCESSED_MARKER"

echo "[cache] sync complete"
