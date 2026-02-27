# Create compute VM service account via CLI/API

PROJECT="rav-ai-488706"
SA_NAME="rav-spot-trainer"
SA_EMAIL="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"

# 1) Create service account
gcloud iam service-accounts create "${SA_NAME}" \
--project "${PROJECT}" \
--display-name "RAV Spot Trainer"

# 2) Grant runtime roles (adjust as needed)
gcloud projects add-iam-policy-binding "${PROJECT}" \
--member="serviceAccount:${SA_EMAIL}" \
--role="roles/storage.objectAdmin"

gcloud projects add-iam-policy-binding "${PROJECT}" \
--member="serviceAccount:${SA_EMAIL}" \
--role="roles/artifactregistry.reader"

gcloud projects add-iam-policy-binding "${PROJECT}" \
--member="serviceAccount:${SA_EMAIL}" \
--role="roles/compute.instanceAdmin.v1"

gcloud projects add-iam-policy-binding "${PROJECT}" \
--member="serviceAccount:${SA_EMAIL}" \
--role="roles/logging.logWriter"

# 3) Allow your user to attach this SA to VMs
gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
--project "${PROJECT}" \
--member="user:wei.alex.xin@gmail.com" \
--role="roles/iam.serviceAccountUser"