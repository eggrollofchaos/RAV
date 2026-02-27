# GCP Notes (RAV)

Operational learnings and debugging notes from bringing CheXpert spot training online.

## Scope

- Repo: `RAV`
- Runner: external checkout at `../gcp-spot-runner`
- Date window: February 2026

## 1) Fast Sanity Checklist

Use this before each new run:

```bash
# verify context
gcloud auth list
gcloud config list

# verify key config values
rg -n '^(PROJECT|REGION|SA|BUCKET|IMAGE|RUNNER_DIR|GPU_TIMEOUT_SEC|POLL_INTERVAL|PROGRESS_STALL_POLLS)=' gcp/rav_spot.env

# build image
bash scripts/gcp_build_image.sh

# submit
RUN_ID="rav-chexpert-$(date -u +%Y%m%d-%H%M%S)"
bash scripts/gcp_submit_primary.sh --run-id "$RUN_ID"

# monitor
bash scripts/gcp_ops.sh status --run-id "$RUN_ID"
bash scripts/gcp_ops.sh serial --run-id "$RUN_ID" 200
```

## 2) Common Failure Patterns

### A) `gcloud crashed (OSError): unexpected end of data`

Observed during `gcloud builds submit` source archiving.

What helped:
- Explicit `.gcloudignore` allowlist.
- Explicit staging dir (`--gcs-source-staging-dir`).
- Fallback path in `scripts/gcp_build_image.sh`:
  1) normal Cloud Build submit
  2) staged tarball + Cloud Build submit
  3) local `docker buildx --push` (when daemon is available)

### B) Cloud Build 403 on source object (`storage.objects.get`)

Error looked like:
- `<PROJECT_NUMBER>-compute@developer.gserviceaccount.com does not have storage.objects.get`

Fix:
- Grant bucket read to build identity used by Cloud Build submit path:
  - `roles/storage.objectViewer` on bucket
- Optional but recommended:
  - `roles/logging.logWriter` for build logs

### C) No heartbeat + VM kill

Key detail:
- Heartbeat is written by `gcp/entrypoint.sh` inside the training container.
- If startup never reaches container launch, there will be no heartbeat and no run manifest.

Most common root cause in this project:
- GPU driver not ready in COS startup window.

### D) GPU driver never installs (COS)

**Root cause (2026-02-27)**: The `install-nvidia-driver=true` VM metadata does
**not** auto-install drivers on Container-Optimized OS. It only works on Deep
Learning VM images and GKE node pools. On plain COS, the `cos-gpu-installer`
service does not exist.

**Fix**: `startup.sh` now runs `cos-extensions install gpu` explicitly before
the GPU wait loop. Driver 535.288.01 installs in ~40s on T4.

### E) Container launch fails with exit 125 (GPU runtime)

Two variants observed on COS:

1. `--gpus all` -> `error running prestart hook ... Using requested mode 'cdi'`
   - COS uses CDI mode; the prestart hook is unsupported.
2. `--runtime=nvidia` -> `unknown or invalid runtime name: nvidia`
   - The nvidia runtime is not registered with Docker on COS.

**Fix**: Mount NVIDIA driver files and device nodes directly:
```
--volume /var/lib/nvidia/lib64:/usr/local/nvidia/lib64
--volume /var/lib/nvidia/bin:/usr/local/nvidia/bin
--device /dev/nvidia0 --device /dev/nvidiactl --device /dev/nvidia-uvm
-e LD_LIBRARY_PATH=/usr/local/nvidia/lib64
```

### F) GPU wait timeout (`FATAL: No GPU detected ...`)

Observed on `n1-standard-4 + T4` in `us-east1-c` before the cos-extensions fix.

Mitigations:
- Increase `GPU_TIMEOUT_SEC`.
- Keep no-heartbeat watchdog window >= GPU timeout window.

## 3) Timeout Alignment Rule

Given:
- `POLL_INTERVAL` seconds
- `PROGRESS_STALL_POLLS` polls
- no-heartbeat window = `POLL_INTERVAL * PROGRESS_STALL_POLLS`

Guideline:
- Ensure `POLL_INTERVAL * PROGRESS_STALL_POLLS >= GPU_TIMEOUT_SEC`

Example used:
- `GPU_TIMEOUT_SEC=1200`
- `POLL_INTERVAL=120`
- `PROGRESS_STALL_POLLS=10`  -> 1200s window

## 4) Mapping VM <-> RUN_ID

Spot-runner VM name includes a sanitized/hash form of run id.
Use metadata for exact run id:

```bash
INSTANCE="<vm-name>"
ZONE="<zone>"
PROJECT="<project>"

gcloud compute instances describe "$INSTANCE" --zone "$ZONE" --project "$PROJECT" --format=json \
  | jq -r '.metadata.items[]? | select(.key=="spot-run-id") | .value'
```

Useful labels in list output:
- `labels.runner_label`
- `labels.run_id` (sanitized/hash form)

## 5) Stop/Restart Semantics

- `bash scripts/gcp_ops.sh delete --run-id <RUN_ID>` writes `.stop` then deletes VM.
- Deleting VM directly without `.stop` can allow auto-restart.
- `.stop` location:
  - `gs://<BUCKET>/runs/<RUN_ID>/.stop`

## 6) Project/Console Mismatch Trap

A frequent confusion source:
- `gcloud compute instances list` uses active `gcloud` project unless `--project` provided.
- Cloud Console may be showing a different project/filter.

Always confirm:

```bash
gcloud config list
gcloud compute instances list --project=<expected-project>
```

## 7) Useful Monitoring Commands

```bash
# run summary (manifest/config/heartbeat/instance history)
bash scripts/gcp_ops.sh status --run-id <RUN_ID>

# cloud system events
bash scripts/gcp_ops.sh events --run-id <RUN_ID> --since 24h

# serial startup and container stdout/stderr
bash scripts/gcp_ops.sh serial --run-id <RUN_ID> 250

# list all runner VMs
bash scripts/gcp_ops.sh list all
```

## 8) External Runner Fixes Applied

In `../gcp-spot-runner` (see its `CHANGELOG.md` for full details):
- `startup.sh`
  - GPU driver install via `cos-extensions install gpu` (COS doesn't auto-install)
  - Volume-mount GPU passthrough (neither `--gpus all` nor `--runtime=nvidia` works on COS)
  - Configurable `GPU_TIMEOUT_SEC` via VM metadata
  - Richer GPU diagnostics in serial output
- `submit.sh`
  - Pass `spot-gpu-timeout-sec` metadata
  - Restart-loop no-heartbeat handling
  - `_gcs_upload_string` moved for `--cleanup-all`
  - `$STATUS` -> `$FINAL_STATUS` typo fix
- `entrypoint.sh`
  - Base64 JOB_COMMAND decode
  - GCS conditional header syntax fix
- `lib.sh`
  - GCS conditional header syntax fix

In `RAV`:
- `gcp/entrypoint.sh` decodes base64 job command metadata.
- `scripts/gcp_build_image.sh` hardened build fallback behavior.
- `scripts/gcp_runner_common.sh` includes `GPU_TIMEOUT_SEC` default/propagation.

## 9) Operational Commands Quick Reference

### Submit / Kill / Resubmit

```bash
# Submit a new run (auto-generates RUN_ID)
bash scripts/gcp_submit_primary.sh

# Submit reusing existing image (skip Cloud Build)
bash scripts/gcp_submit_primary.sh --skip-build

# Kill ALL runner VMs and submit fresh
bash scripts/gcp_submit_primary.sh --skip-build --cleanup-all --yes

# Resume a previous run (same RUN_ID = downloads last.pt)
bash scripts/gcp_submit_primary.sh --run-id <RUN_ID>
```

### Kill a stuck VM

```bash
# Option A: ops.sh safe stop (writes .stop + deletes VM)
bash scripts/gcp_ops.sh delete --yes

# Option B: direct gcloud (does NOT write .stop — may auto-restart)
gcloud compute instances list --project=rav-ai-488706
gcloud compute instances delete <VM_NAME> --zone=us-east1-c --project=rav-ai-488706 --quiet
```

Note: `gcp_submit_primary.sh` Phase 0 only cleans up VMs matching the **same
RUN_ID label**. A new submit won't kill VMs from a prior run. Use `--cleanup-all`
or `gcp_ops.sh delete` to kill VMs from other runs first.

### Monitor

```bash
bash scripts/gcp_ops.sh status                    # manifest + heartbeat summary
bash scripts/gcp_ops.sh serial 200                # last 200 lines of serial console
bash scripts/gcp_ops.sh events --since 24h        # cloud system events
bash scripts/gcp_ops.sh list all                   # all runner VMs
bash scripts/gcp_ops.sh watch 60                   # auto-refresh every 60s
```

### Cloud Logging (for deeper serial output)

```bash
gcloud logging read 'logName:"google_metadata_script_runner"' \
  --project=rav-ai-488706 --freshness=1h --limit=50 \
  --format='value(timestamp,jsonPayload.message)'
```

## 10) Current Recommendation for CheXpert Spot Runs

Starting point:
- `GPU_TIMEOUT_SEC="1200"`
- `POLL_INTERVAL="120"`
- `PROGRESS_STALL_POLLS="10"`
- zone fallback enabled (`us-east1-b/c/d`)

If repeated GPU timeout persists:
- try alternate zone
- use larger machine shape temporarily
- evaluate non-spot for baseline validation run
