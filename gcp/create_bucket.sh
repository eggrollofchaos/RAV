# Create bucket via CLI/API
# BUCKET is the GCS bucket name used by spot-runner for run state/checkpoints/results.

PROJECT="rav-ai-488706"
BUCKET="rav-ai-train-artifacts-488706"

gcloud storage buckets create "gs://${BUCKET}" \
  --project="${PROJECT}" \
  --location="us-east1" \
  --uniform-bucket-level-access

# Grant your training service account access

SA_EMAIL="rav-spot-trainer@${PROJECT}.iam.gserviceaccount.com"

gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.objectAdmin"