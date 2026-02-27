#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/gcp_runner_common.sh"

load_rav_spot_env
apply_runner_defaults
check_required_spot_vars
configure_gcloud_runtime

echo "Building/pushing image: ${IMAGE}"
echo "Project: ${PROJECT} | Region: ${REGION}"
if [[ -n "${CLOUDSDK_PYTHON:-}" ]]; then
  echo "gcloud Python: ${CLOUDSDK_PYTHON}"
fi

gcloud builds submit "${RAV_ROOT}" \
  --project="${PROJECT}" \
  --region="${REGION}" \
  --config="${RAV_ROOT}/gcp/cloudbuild.rav.yaml" \
  --substitutions="_IMAGE=${IMAGE}"

echo "Build complete: ${IMAGE}"
