#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/gcp_runner_common.sh"

prepare_rav_runtime "required" "1" "1"

# Runtime is already prepared above; build entrypoint helper handles only build arg composition here.
_rav_runtime_already_prepared() { :; }

echo "Building/pushing image: ${IMAGE}"
echo "Project: ${PROJECT} | Region: ${REGION}"
if [[ -n "${CLOUDSDK_PYTHON:-}" ]]; then
  echo "gcloud Python: ${CLOUDSDK_PYTHON}"
fi
SOURCE_STAGING_DIR="${GCS_SOURCE_STAGING_DIR:-gs://${BUCKET}/cloudbuild/source}"
echo "Source staging dir: ${SOURCE_STAGING_DIR}"

spot_runner_wrapper_run_project_build_entrypoint_required \
  "${RUNNER_HINT_MESSAGE:-Set RUNNER_DIR to your gcp-spot-runner checkout.}" \
  "_rav_runtime_already_prepared" \
  "run_build_command" \
  "${RAV_ROOT}" \
  "${RAV_ROOT}/gcp/cloudbuild.rav.yaml" \
  "${IMAGE}" \
  -- \
  --gcs-source-staging-dir "${SOURCE_STAGING_DIR}" \
  "$@"

echo "Build complete: ${IMAGE}"
