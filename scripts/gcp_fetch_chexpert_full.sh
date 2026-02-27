#!/usr/bin/env bash
#
# One-time transfer: download full CheXpert (417 GB) from Azure (Stanford AIMI)
# and upload to GCS so training VMs can sync from there.
#
# Intended to run from a GCE VM in the same region as your bucket for speed.
# Can also run locally, but the upload will be slower.
#
# Usage:
#   bash scripts/gcp_fetch_chexpert_full.sh --sas-url "<AZURE_SAS_URL>"
#
# The SAS URL comes from Stanford AIMI after you accept the CheXpert DUA:
#   https://stanfordaimi.azurewebsites.net/datasets/8cbd9ed4-2eb9-4565-affc-111cf4f7ebe2
#
# Options:
#   --sas-url URL        (required) Azure SAS URL from Stanford AIMI download page
#   --local-dir DIR      Local staging directory (default: /tmp/chexpert-full)
#   --gcs-prefix URI     GCS destination (default: gs://$BUCKET/datasets/chexpert-full)
#   --skip-download      Skip Azure download, only upload local-dir to GCS
#   --skip-upload        Skip GCS upload, only download from Azure to local-dir
#   --keep-local         Don't delete local staging dir after upload
#   --run-prepare        Run prepare_chexpert_data.py and upload processed CSVs too
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAV_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Defaults
SAS_URL=""
LOCAL_DIR="/tmp/chexpert-full"
GCS_PREFIX=""
BUCKET="${BUCKET:-}"
SKIP_DOWNLOAD=false
SKIP_UPLOAD=false
KEEP_LOCAL=false
RUN_PREPARE=false

# ---------- arg parsing ----------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --sas-url)       SAS_URL="$2"; shift 2 ;;
    --local-dir)     LOCAL_DIR="$2"; shift 2 ;;
    --gcs-prefix)    GCS_PREFIX="$2"; shift 2 ;;
    --skip-download) SKIP_DOWNLOAD=true; shift ;;
    --skip-upload)   SKIP_UPLOAD=true; shift ;;
    --keep-local)    KEEP_LOCAL=true; shift ;;
    --run-prepare)   RUN_PREPARE=true; shift ;;
    *)
      echo "Unknown flag: $1" >&2
      exit 1
      ;;
  esac
done

# Load BUCKET from rav_spot.env if not already set
if [[ -z "$BUCKET" ]]; then
  env_file="${RAV_ROOT}/gcp/rav_spot.env"
  if [[ -f "$env_file" ]]; then
    BUCKET="$(grep -E '^BUCKET=' "$env_file" | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")"
  fi
fi

if [[ -z "$BUCKET" && "$SKIP_UPLOAD" != true ]]; then
  echo "BUCKET not set. Export it, or ensure gcp/rav_spot.env has BUCKET=..." >&2
  exit 1
fi

: "${GCS_PREFIX:=gs://${BUCKET}/datasets/chexpert-full}"

if [[ "$SKIP_DOWNLOAD" != true && -z "$SAS_URL" ]]; then
  echo "ERROR: --sas-url is required (unless --skip-download)." >&2
  echo "" >&2
  echo "Get your SAS URL from Stanford AIMI:" >&2
  echo "  https://stanfordaimi.azurewebsites.net/datasets/8cbd9ed4-2eb9-4565-affc-111cf4f7ebe2" >&2
  exit 1
fi

# ---------- helpers ----------
log() { echo "[$(date '+%H:%M:%S')] $*"; }

ensure_azcopy() {
  if command -v azcopy &>/dev/null; then
    log "azcopy found: $(command -v azcopy)"
    return 0
  fi

  log "Installing azcopy..."
  local tmp_dir
  tmp_dir="$(mktemp -d)"

  local os_name
  os_name="$(uname -s | tr '[:upper:]' '[:lower:]')"
  local arch
  arch="$(uname -m)"
  # Map arm64 → arm64, x86_64 → amd64
  case "$arch" in
    x86_64)  arch="amd64" ;;
    aarch64) arch="arm64" ;;
    arm64)   arch="arm64" ;;
  esac

  local url="https://aka.ms/downloadazcopy-v10-${os_name}-${arch}"
  if [[ "$os_name" == "darwin" ]]; then
    # macOS download is a zip
    curl -sL "$url" -o "${tmp_dir}/azcopy.zip"
    unzip -qo "${tmp_dir}/azcopy.zip" -d "${tmp_dir}"
    local bin
    bin="$(find "${tmp_dir}" -name azcopy -type f | head -1)"
  else
    curl -sL "$url" | tar xz --strip-components=1 -C "${tmp_dir}"
    local bin="${tmp_dir}/azcopy"
  fi

  chmod +x "$bin"
  mkdir -p "${RAV_ROOT}/.local/bin"
  mv "$bin" "${RAV_ROOT}/.local/bin/azcopy"
  rm -rf "$tmp_dir"
  export PATH="${RAV_ROOT}/.local/bin:${PATH}"
  log "azcopy installed to ${RAV_ROOT}/.local/bin/azcopy"
}

# ---------- download from Azure ----------
download_from_azure() {
  log "Downloading CheXpert full from Azure → ${LOCAL_DIR}"
  log "This is ~417 GB. Expect 30-90 min on a GCE VM, longer locally."
  mkdir -p "$LOCAL_DIR"

  ensure_azcopy

  # azcopy handles resume automatically via its journal
  azcopy copy "$SAS_URL" "$LOCAL_DIR" --recursive=true --from-to=BlobLocal --log-level=WARNING

  local size
  size="$(du -sh "$LOCAL_DIR" | cut -f1)"
  log "Download complete. Local size: ${size}"
}

# ---------- upload to GCS ----------
upload_to_gcs() {
  log "Uploading ${LOCAL_DIR} → ${GCS_PREFIX}/raw/"
  gcloud storage rsync -r "${LOCAL_DIR}/" "${GCS_PREFIX}/raw/" \
    --no-clobber \
    --checksums-only

  log "Upload complete: ${GCS_PREFIX}/raw/"
}

# ---------- optional: prepare processed CSVs ----------
run_prepare_step() {
  log "Running prepare_chexpert_data.py on downloaded data..."
  local processed_dir="${LOCAL_DIR}/processed"
  mkdir -p "$processed_dir"

  # Find the CheXpert root (look for train.csv)
  local chexpert_root
  chexpert_root="$(find "$LOCAL_DIR" -name train.csv -maxdepth 3 -print -quit 2>/dev/null)"
  if [[ -z "$chexpert_root" ]]; then
    log "WARNING: Could not find train.csv under ${LOCAL_DIR}. Skipping prepare step."
    return 1
  fi
  chexpert_root="$(dirname "$chexpert_root")"
  log "Found CheXpert root: ${chexpert_root}"

  python3 "${RAV_ROOT}/scripts/prepare_chexpert_data.py" \
    --chexpert-root "$chexpert_root" \
    --output-dir "$processed_dir"

  log "Uploading processed CSVs → ${GCS_PREFIX}/processed/"
  gcloud storage rsync -r "${processed_dir}/" "${GCS_PREFIX}/processed/"
  log "Processed CSVs uploaded."
}

# ---------- main ----------
log "=== CheXpert Full Dataset Transfer ==="
log "Local staging: ${LOCAL_DIR}"
log "GCS target:    ${GCS_PREFIX}"
echo ""

if [[ "$SKIP_DOWNLOAD" != true ]]; then
  download_from_azure
else
  log "Skipping download (--skip-download)"
fi

if [[ "$SKIP_UPLOAD" != true ]]; then
  upload_to_gcs
  if [[ "$RUN_PREPARE" == true ]]; then
    run_prepare_step
  fi
else
  log "Skipping upload (--skip-upload)"
fi

if [[ "$KEEP_LOCAL" != true && "$SKIP_UPLOAD" != true ]]; then
  log "Cleaning up local staging dir: ${LOCAL_DIR}"
  rm -rf "$LOCAL_DIR"
else
  log "Keeping local staging dir: ${LOCAL_DIR}"
fi

log "=== Done ==="
log "To use in training, update JOB_COMMAND_PRIMARY in gcp/rav_spot.env:"
log "  gcloud storage rsync -r ${GCS_PREFIX}/raw/ data/raw/chexpert/"
log "  gcloud storage rsync -r ${GCS_PREFIX}/processed/ data/processed/"
