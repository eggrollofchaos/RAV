#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/gcp_runner_common.sh"

prepare_rav_runtime "required" "1" "1"

echo "Building/pushing image: ${IMAGE}"
echo "Project: ${PROJECT} | Region: ${REGION}"
if [[ -n "${CLOUDSDK_PYTHON:-}" ]]; then
  echo "gcloud Python: ${CLOUDSDK_PYTHON}"
fi
SOURCE_STAGING_DIR="${GCS_SOURCE_STAGING_DIR:-gs://${BUCKET}/cloudbuild/source}"
echo "Source staging dir: ${SOURCE_STAGING_DIR}"

run_build_command \
  --source "${RAV_ROOT}" \
  --cloudbuild-config "${RAV_ROOT}/gcp/cloudbuild.rav.yaml" \
  --image "${IMAGE}" \
  --gcs-source-staging-dir "${SOURCE_STAGING_DIR}" \
  "$@"

echo "Build complete: ${IMAGE}"
