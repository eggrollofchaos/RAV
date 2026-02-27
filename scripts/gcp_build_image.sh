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
SOURCE_STAGING_DIR="${GCS_SOURCE_STAGING_DIR:-gs://${BUCKET}/cloudbuild/source}"
echo "Source staging dir: ${SOURCE_STAGING_DIR}"

cloud_build_submit() {
  gcloud builds submit "${RAV_ROOT}" \
    --project="${PROJECT}" \
    --region="${REGION}" \
    --config="${RAV_ROOT}/gcp/cloudbuild.rav.yaml" \
    --substitutions="_IMAGE=${IMAGE}" \
    --gcs-source-staging-dir="${SOURCE_STAGING_DIR}"
}

staged_tarball_cloud_build_submit() {
  local tmp_dir tar_path source_object rc
  rc=0
  tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/rav-cloudbuild-src-XXXXXX")"
  tar_path="${tmp_dir}/source.tgz"
  source_object="gs://${BUCKET}/cloudbuild/source/manual-$(date -u +%Y%m%d-%H%M%S)-$$.tgz"

  echo "Preparing explicit source tarball at ${tar_path}..."
  (
    cd "${RAV_ROOT}"
    tar -czf "${tar_path}" \
      requirements.txt \
      .dockerignore \
      .gcloudignore \
      src \
      scripts \
      configs \
      app \
      gcp/Dockerfile.train \
      gcp/entrypoint.sh \
      gcp/cloudbuild.rav.yaml
  )

  echo "Uploading staged source to ${source_object}..."
  gcloud storage cp "${tar_path}" "${source_object}" --project="${PROJECT}" || rc=$?

  if [[ "$rc" -eq 0 ]]; then
    echo "Submitting Cloud Build from staged tarball..."
    gcloud builds submit "${source_object}" \
      --project="${PROJECT}" \
      --region="${REGION}" \
      --config="${RAV_ROOT}/gcp/cloudbuild.rav.yaml" \
      --substitutions="_IMAGE=${IMAGE}" || rc=$?
  fi

  rm -rf "${tmp_dir}"
  return "$rc"
}

docker_daemon_available() {
  docker info >/dev/null 2>&1
}

local_docker_buildx_push() {
  local ar_host="${IMAGE%%/*}"
  echo "Falling back to local docker buildx push..."
  gcloud auth configure-docker "${ar_host}" --quiet
  docker buildx build \
    --platform linux/amd64 \
    -f "${RAV_ROOT}/gcp/Dockerfile.train" \
    -t "${IMAGE}" \
    --push \
    "${RAV_ROOT}"
}

if ! cloud_build_submit; then
  echo "Cloud Build submit failed."
  echo "Attempting fallback via staged source tarball + Cloud Build..."
  if ! staged_tarball_cloud_build_submit; then
    echo "Staged tarball fallback failed."
    if docker_daemon_available; then
      echo "Attempting final fallback via local docker buildx..."
      local_docker_buildx_push
    else
      echo "Docker daemon is not running; local buildx fallback is unavailable." >&2
      echo "Start Docker Desktop/Colima and rerun this script, or fix Cloud Build permissions and rerun." >&2
      exit 1
    fi
  fi
fi

echo "Build complete: ${IMAGE}"
