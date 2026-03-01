#!/usr/bin/env bash
# deploy.sh — Deploy the cloud reconciler as a Cloud Function (gen2) + Cloud Scheduler
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAV_GCP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

PROJECT="${PROJECT:-ixqt-488109}"
REGION="${REGION:-us-east1}"
BUCKET="${BUCKET:-ixqt-training-488109}"
FUNCTION_NAME="${FUNCTION_NAME:-ixqt-reconciler}"
SCHEDULER_NAME="${SCHEDULER_NAME:-ixqt-reconciler-trigger}"
SA="${SA:-ixqt-compute@${PROJECT}.iam.gserviceaccount.com}"
SCHEDULE="${SCHEDULE:-*/5 * * * *}"  # Every 5 minutes
DRY_RUN="${DRY_RUN:-true}"

echo "=== Deploying Cloud Reconciler ==="
echo "Project:    $PROJECT"
echo "Region:     $REGION"
echo "Bucket:     $BUCKET"
echo "Function:   $FUNCTION_NAME"
echo "DRY_RUN:    $DRY_RUN"
echo ""

# Enable required APIs
echo "Enabling APIs..."
gcloud services enable \
  cloudfunctions.googleapis.com \
  cloudscheduler.googleapis.com \
  secretmanager.googleapis.com \
  compute.googleapis.com \
  run.googleapis.com \
  --project="$PROJECT"

# Prepare deploy staging directory
STAGING_DIR="$(mktemp -d)"
trap "rm -rf $STAGING_DIR" EXIT

# Copy source files
cp "${SCRIPT_DIR}/main.py" "$STAGING_DIR/"
cp "${SCRIPT_DIR}/state_machine.py" "$STAGING_DIR/"
cp "${SCRIPT_DIR}/requirements.txt" "$STAGING_DIR/"
cp "${RAV_GCP_DIR}/state_transitions.json" "$STAGING_DIR/"

echo "Deploying Cloud Function..."
gcloud functions deploy "$FUNCTION_NAME" \
  --gen2 \
  --project="$PROJECT" \
  --region="$REGION" \
  --runtime=python312 \
  --source="$STAGING_DIR" \
  --entry-point=reconcile_http \
  --trigger-http \
  --no-allow-unauthenticated \
  --service-account="$SA" \
  --set-env-vars="BUCKET=$BUCKET,PROJECT=$PROJECT,DRY_RUN=$DRY_RUN" \
  --memory=256Mi \
  --timeout=120s \
  --max-instances=1

# Get the function URL
FUNCTION_URL="$(gcloud functions describe "$FUNCTION_NAME" \
  --project="$PROJECT" --region="$REGION" --gen2 \
  --format='value(serviceConfig.uri)' 2>/dev/null || true)"

if [[ -z "$FUNCTION_URL" ]]; then
  echo "WARNING: Could not retrieve function URL. Skipping scheduler setup."
  exit 0
fi

echo "Function URL: $FUNCTION_URL"

# Create or update Cloud Scheduler job
echo "Setting up Cloud Scheduler..."
if gcloud scheduler jobs describe "$SCHEDULER_NAME" --project="$PROJECT" --location="$REGION" &>/dev/null; then
  gcloud scheduler jobs update http "$SCHEDULER_NAME" \
    --project="$PROJECT" \
    --location="$REGION" \
    --schedule="$SCHEDULE" \
    --uri="$FUNCTION_URL" \
    --http-method=POST \
    --oidc-service-account-email="$SA" \
    --oidc-token-audience="$FUNCTION_URL"
  echo "Scheduler job updated."
else
  gcloud scheduler jobs create http "$SCHEDULER_NAME" \
    --project="$PROJECT" \
    --location="$REGION" \
    --schedule="$SCHEDULE" \
    --uri="$FUNCTION_URL" \
    --http-method=POST \
    --oidc-service-account-email="$SA" \
    --oidc-token-audience="$FUNCTION_URL" \
    --time-zone="UTC"
  echo "Scheduler job created."
fi

echo ""
echo "=== Deploy Complete ==="
echo "Reconciler: $FUNCTION_URL"
echo "Schedule:   $SCHEDULE (UTC)"
echo "DRY_RUN:    $DRY_RUN"
echo ""
echo "To switch from dry-run to live:"
echo "  DRY_RUN=false $0"
echo ""
echo "To pause:"
echo "  gcloud scheduler jobs pause $SCHEDULER_NAME --project=$PROJECT --location=$REGION"
