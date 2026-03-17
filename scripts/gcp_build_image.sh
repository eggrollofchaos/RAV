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

spot_runner_wrapper_run_project_build_wrapper_defaults_required \
  "${RUNNER_HINT_MESSAGE:-Set RUNNER_DIR to your gcp-spot-runner checkout.}" \
  "" \
  "run_project_command" \
  "${RAV_ROOT}" \
  "${RAV_ROOT}/gcp/cloudbuild.rav.yaml" \
  "${IMAGE}" \
  -- \
  --gcs-source-staging-dir "${SOURCE_STAGING_DIR}" \
  "$@"

echo "Build complete: ${IMAGE}"
