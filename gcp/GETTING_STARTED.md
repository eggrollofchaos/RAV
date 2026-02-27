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

Job runs but no resume occurs:
- Confirm you reused exactly the same `--run-id`.
- Confirm prior checkpoint exists in GCS at:
  - `gs://<BUCKET>/runs/<RUN_ID>/checkpoint_sync/checkpoints/last.pt`

No artifacts in `results/`:
- Check training wrapper logs and run manifest via `gcp_ops.sh events`.
- Ensure training reached final copy stage into `/app/results`.
