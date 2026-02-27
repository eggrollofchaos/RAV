# GCP Spot Runner Quickstart

This guide gets you from zero to a running RAV training job on GCP Spot VMs with checkpoint-safe resume.

## 1) What this setup does

- Builds a training image from this repo.
- Submits a Spot VM job through your external `gcp-spot-runner` checkout.
- Runs training inside the container via `scripts/gcp_train_with_checkpoint_sync.sh`.
- Syncs checkpoints + metrics to GCS during training.
- Auto-resumes from `last.pt` when preempted, as long as you reuse the same `RUN_ID`.

## 2) Prerequisites

- `gcloud` CLI installed and authenticated.
- Docker installed locally (used for Cloud Build submit context and image pipeline).
- A GCP project with billing enabled.
- A GCS bucket for run state/artifacts.
- Artifact Registry Docker repo (example repo name below: `rav-train`).
- Service account with permissions for:
  - Compute Engine instance create/delete
  - Artifact Registry pull
  - Cloud Storage read/write
  - Logging/monitoring as needed by your runner
- A local checkout of `gcp-spot-runner` (outside this repo), e.g. `../gcp-spot-runner`.

## 3) One-time GCP bootstrap (if needed)

Set your project first:

```bash
gcloud config set project <PROJECT_ID>
```

Create an Artifact Registry Docker repo (skip if it already exists):

```bash
gcloud artifacts repositories create rav-train \
  --repository-format=docker \
  --location=us-east1
```

Create a bucket (skip if it already exists):

```bash
gcloud storage buckets create gs://<BUCKET_NAME> --location=us-east1
```

## 4) Configure this repo

Copy env template:

```bash
cp gcp/rav_spot.env.example gcp/rav_spot.env
```

Edit `gcp/rav_spot.env` and set at minimum:

- `PROJECT`
- `REGION`
- `SA`
- `BUCKET`
- `IMAGE`
- `RUNNER_DIR`

Recommended starting values:

- `REGION="us-east1"`
- `ZONE="us-east1-c"`
- `FALLBACK_ZONES=("us-east1-b" "us-east1-c" "us-east1-d")`
- `GPU_TYPE="nvidia-tesla-t4"`
- `GPU_TIMEOUT_SEC="600"` (or `900` if driver init is slow in your zone)
- `SYNC_INTERVAL_SEC="180"`

`IMAGE` should match your Artifact Registry path, for example:

```bash
IMAGE="us-east1-docker.pkg.dev/<PROJECT_ID>/rav-train/rav-chest:latest"
```

## 5) Build and push training image

From repo root:

```bash
bash scripts/gcp_build_image.sh
```

This uses `gcp/cloudbuild.rav.yaml` and `gcp/Dockerfile.train`.

## 6) Submit training jobs

Primary (CheXpert):

```bash
bash scripts/gcp_submit_primary.sh
```

POC (Kaggle binary):

```bash
bash scripts/gcp_submit_poc.sh
```

Both wrappers run checkpoint-safe training with periodic sync.

## 7) Resume behavior (important)

To resume after preemption, submit again with the same `RUN_ID`:

```bash
bash scripts/gcp_submit_primary.sh --run-id rav-chexpert-001
# later resume:
bash scripts/gcp_submit_primary.sh --run-id rav-chexpert-001
```

Same for POC:

```bash
bash scripts/gcp_submit_poc.sh --run-id rav-poc-001
```

How it works:

- Wrapper syncs `last.pt` and metrics to:
  - `gs://<BUCKET>/runs/<RUN_ID>/checkpoint_sync/...`
- On restart with same run ID, wrapper downloads `last.pt` and appends `--resume-checkpoint` automatically.

## 8) Monitor and operate runs

```bash
bash scripts/gcp_ops.sh status
bash scripts/gcp_ops.sh list
bash scripts/gcp_ops.sh events --since 24h
```

## 9) Where outputs go

During/after run, expect artifacts under:

- `gs://<BUCKET>/runs/<RUN_ID>/checkpoint_sync/checkpoints/`
- `gs://<BUCKET>/runs/<RUN_ID>/checkpoint_sync/metrics/`
- `gs://<BUCKET>/runs/<RUN_ID>/results/`

Inside the repo conventions:

- Primary outputs: `outputs/chest_baseline/...`
- POC outputs: `outputs/poc/chest_pneumonia_binary/...`

## 10) Common command sequence

```bash
# 0) configure once
cp gcp/rav_spot.env.example gcp/rav_spot.env

# 1) build image
bash scripts/gcp_build_image.sh

# 2) submit
bash scripts/gcp_submit_primary.sh --run-id rav-chexpert-001

# 3) monitor
bash scripts/gcp_ops.sh status

# 4) if preempted / interrupted, resume
bash scripts/gcp_submit_primary.sh --run-id rav-chexpert-001
```

## 11) Troubleshooting

`Missing gcp/rav_spot.env`:
- Copy from template and fill required values.

`Runner file missing ...`:
- `RUNNER_DIR` is wrong or runner checkout is incomplete.

`Permission denied` errors from GCP:
- Verify active account/project:
  - `gcloud auth list`
  - `gcloud config list`
- Verify service account roles and bucket/image permissions.

`NO HEARTBEAT` shortly after launch:
- Check serial logs; common cause is GPU driver not ready before timeout.
- Increase `GPU_TIMEOUT_SEC` in `gcp/rav_spot.env` (for example `900`) and resubmit.

Job runs but no resume occurs:
- Confirm you reused exactly the same `--run-id`.
- Confirm prior checkpoint exists in GCS at:
  - `gs://<BUCKET>/runs/<RUN_ID>/checkpoint_sync/checkpoints/last.pt`

No artifacts in `results/`:
- Check training wrapper logs and run manifest via `gcp_ops.sh events`.
- Ensure training reached final copy stage into `/app/results`.

## 12) Centralized One-Off Commands

Use this section as the command reference for setup/verification/fixes.

### Variables

```bash
PROJECT="rav-ai-488706"
REGION="us-east1"
REPO="rav-train"
BUCKET="rav-ai-train-artifacts-488706"
SA_NAME="rav-spot-trainer"
SA_EMAIL="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/rav-chest:latest"
```

### Check/Create Artifact Registry Repo

```bash
gcloud artifacts repositories describe "$REPO" \
  --location="$REGION" \
  --project="$PROJECT"

gcloud artifacts repositories create "$REPO" \
  --repository-format=docker \
  --location="$REGION" \
  --project="$PROJECT"
```

### Check/Create Bucket

```bash
gcloud storage ls "gs://${BUCKET}"

gcloud storage buckets create "gs://${BUCKET}" \
  --project="$PROJECT" \
  --location="$REGION" \
  --uniform-bucket-level-access
```

### Create/Grant Runtime Service Account

```bash
gcloud iam service-accounts create "$SA_NAME" \
  --project "$PROJECT" \
  --display-name "RAV Spot Trainer"

gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.objectAdmin"

gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/artifactregistry.reader"

gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/compute.instanceAdmin.v1"

gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/logging.logWriter"
```

### Fix Cloud Build 403 on Source Objects

Error pattern:
- `storage.objects.get` denied for `<project-number>-compute@developer.gserviceaccount.com`.

Fix:

```bash
PROJECT_NUM="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"
CB_COMPUTE_SA="${PROJECT_NUM}-compute@developer.gserviceaccount.com"
CB_BUILD_SA="${PROJECT_NUM}@cloudbuild.gserviceaccount.com"

for SA in "$CB_COMPUTE_SA" "$CB_BUILD_SA"; do
  gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
    --member="serviceAccount:${SA}" \
    --role="roles/storage.objectAdmin"
done

for SA in "$CB_COMPUTE_SA" "$CB_BUILD_SA"; do
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:${SA}" \
    --role="roles/artifactregistry.writer"
done
```

### Sync Datasets to GCS

See [DATASET_TRANSFER.md](DATASET_TRANSFER.md) for the full walkthrough (CheXpert Small from Kaggle, CheXpert Full from Azure via a temporary GCE VM).

Quick reference for CheXpert Small (already downloaded locally):

```bash
gcloud storage rsync -r data/raw/chexpert "gs://${BUCKET}/datasets/chexpert/raw"
gcloud storage rsync -r data/processed "gs://${BUCKET}/datasets/chexpert/processed"
```

### Build Commands

Wrapper build:

```bash
bash scripts/gcp_build_image.sh
```

Direct Cloud Build with explicit staging dir:

```bash
gcloud builds submit . \
  --project="$PROJECT" \
  --region="$REGION" \
  --config="gcp/cloudbuild.rav.yaml" \
  --substitutions="_IMAGE=${IMAGE}" \
  --gcs-source-staging-dir="gs://${BUCKET}/cloudbuild/source"
```

Fallback if `gcloud builds submit` crashes locally:

```bash
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
docker buildx build \
  --platform linux/amd64 \
  -f gcp/Dockerfile.train \
  -t "$IMAGE" \
  --push \
  .
```

### Launch and Resume

```bash
bash scripts/gcp_submit_primary.sh --dry-run
bash scripts/gcp_submit_primary.sh --run-id rav-chexpert-001
bash scripts/gcp_submit_primary.sh --run-id rav-chexpert-001  # resume
```
