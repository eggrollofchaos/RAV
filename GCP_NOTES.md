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

### D) GPU wait timeout (`FATAL: No GPU detected ...`)

Observed repeatedly on `n1-standard-4 + T4` in `us-east1-c`.

Findings:
- PCI device can be visible before NVIDIA modules are ready.
- Driver install readiness can exceed 15 minutes in some attempts.

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

In `../gcp-spot-runner`:
- `startup.sh`
  - configurable `GPU_TIMEOUT_SEC` via VM metadata
  - richer GPU diagnostics in serial output
- `submit.sh`
  - pass `spot-gpu-timeout-sec` metadata
  - restart-loop no-heartbeat handling (prevent hanging restart attempts)
- previously fixed:
  - lock header format
  - missing `_gcs_upload_string` path
  - status variable typo

In `RAV`:
- `gcp/entrypoint.sh` decodes base64 job command metadata.
- `scripts/gcp_build_image.sh` hardened build fallback behavior.
- `scripts/gcp_runner_common.sh` includes `GPU_TIMEOUT_SEC` default/propagation.

## 9) Current Recommendation for CheXpert Spot Runs

Starting point:
- `GPU_TIMEOUT_SEC="1200"`
- `POLL_INTERVAL="120"`
- `PROGRESS_STALL_POLLS="10"`
- zone fallback enabled (`us-east1-b/c/d`)

If repeated GPU timeout persists:
- try alternate zone
- use larger machine shape temporarily
- evaluate non-spot for baseline validation run
