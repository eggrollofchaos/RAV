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
./scripts/rav-gcp.sh build
./scripts/rav-gcp.sh version
./scripts/rav-gcp.sh --version

# submit
RUN_ID="rav-chexpert-$(date -u +%Y%m%d-%H%M%S)"
./scripts/rav-gcp.sh submit --run-id "$RUN_ID"

# monitor
./scripts/rav-gcp.sh status --run-id "$RUN_ID"
./scripts/rav-gcp.sh serial --run-id "$RUN_ID" 200
```

## 2) Common Failure Patterns

### A) `gcloud crashed (OSError): unexpected end of data`

Observed during `gcloud builds submit` source archiving.

What helped:
- Explicit `.gcloudignore` allowlist.
- Explicit staging dir (`--gcs-source-staging-dir`).
- Runner-owned fallback path via `spotctl build`:
  1) normal Cloud Build submit
  2) staged-source upload + Cloud Build submit

### A1) Docker `COPY gcp/state_transitions.json` fails in Cloud Build

Error looked like:
- `COPY failed: file not found in build context or excluded by .dockerignore: stat gcp/state_transitions.json: file does not exist`

Root cause:
- `gcp/state_transitions.json` was not in the Cloud Build upload context allowlist.

Fix applied in `RAV`:
- `.gcloudignore` now includes:
  - `!gcp/state_transitions.json`
- `rav-gcp.sh build` delegates to `spotctl build`, whose staged-source fallback uploads full source context from repo root.

Quick verification:
```bash
CLOUDSDK_CORE_DISABLE_PROMPTS=1 gcloud meta list-files-for-upload \
  | rg 'gcp/state_transitions\.json'
```

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

### C1) Startup fails mounting data disk on COS (`/mnt/spot-data` read-only)

Error looked like:
- `mkdir: cannot create directory '/mnt/spot-data': Read-only file system`
- `Script "startup-script" failed with error: exit status 1`

Root cause:
- On COS, `/mnt` can be read-only during startup in this runner path.
- Startup script failed before container launch, so no `run_manifest.json` or heartbeat was written.

Fix:
- Set writable host mount path in `gcp/rav_spot.env`:
  - `DATA_DISK_MOUNT_PATH="/var/lib/spot-data"`
- Re-submit the run.

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

### G) Dataset cache sync crashes after successful rsync (`$2: unbound variable`)

**Observed**: 2026-03-02 across multiple runs. `gcloud storage rsync` completed
successfully (223,652 files synced), but the job exited with code 1 immediately
after.

**Error**:
```
scripts/gcp_sync_chexpert_cache.sh: line 85: $2: unbound variable
```

**Root cause**:
- `_write_marker()` expects two args (`$1`=marker path, `$2`=URI).
- `sync_prefix()` line 104 called `_write_marker "$marker"` — missing the `"$uri"` argument.
- With `set -euo pipefail` (`nounset`), accessing `$2` inside `_write_marker` is fatal.

**Impact**:
- Training never started on any run that needed to write the cache marker (i.e.,
  first sync or any re-sync). Runs that hit an existing marker were unaffected.
- On spot VMs, this wasted the full rsync duration (~1.5h for 11 GB raw CheXpert)
  before failing.

**Fix**: Pass URI to `_write_marker`:
```diff
-  _write_marker "$marker"
+  _write_marker "$marker" "$uri"
```

### H) Immediate `job_exit_1` after introducing new config/script (stale image)

**Observed**: 2026-03-04 on run `rav-chexpert-5task-20260304-030500`.

**Error** (from `google_metadata_script_runner`):
```text
FileNotFoundError: [Errno 2] No such file or directory: 'configs/primary/chest_chexpert_5task_policy.yaml'
```

**Root cause**:
- Submit wrappers (`rav-gcp.sh submit` / `gcp_submit_chexpert_experiment.sh`)
  force `--skip-build` by default.
- A new local config/script was committed but the image in Artifact Registry was
  not rebuilt yet, so container startup could not find the new file.

**Fix**:
1. Rebuild image: `./scripts/rav-gcp.sh build`
2. Resubmit run with new `RUN_ID`.
3. Verify startup reaches heartbeat `phase=running` and reports `Using device: cuda`.

**Operational rule**:
- Any change under `configs/`, `scripts/`, `src/`, or `gcp/entrypoint.sh` that
  affects runtime must be followed by a build before submit.

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

- `./scripts/rav-gcp.sh delete --run-id <RUN_ID>` writes `.stop` then deletes VM.
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
./scripts/rav-gcp.sh status --run-id <RUN_ID>

# cloud system events
./scripts/rav-gcp.sh events --run-id <RUN_ID> --since 24h

# serial startup and container stdout/stderr
./scripts/rav-gcp.sh serial --run-id <RUN_ID> 250

# list all runner VMs
./scripts/rav-gcp.sh list all
```

## 8) External Runner Fixes Applied

In `../gcp-spot-runner` (see its `CHANGELOG.md` for full details):
- `spotctl` (primary CLI)
  - `build`/`submit`/`ops`/`monitor` command surface now fronted by `python3 -m spotctl`
  - `submit.sh` and `ops.sh` are compatibility shims over `spotctl`
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
- `scripts/rav-gcp.sh` is the canonical operator wrapper over `scripts/gcp_*.sh`.
- `scripts/gcp_build_image.sh` remains a thin build wrapper.
- `scripts/gcp_runner_common.sh` includes `GPU_TIMEOUT_SEC` default/propagation.

## 9) Operational Commands Quick Reference

### Submit / Kill / Resubmit

```bash
# Submit a new run (auto-generates RUN_ID)
./scripts/rav-gcp.sh submit

# Submit reusing existing image (skip Cloud Build)
./scripts/rav-gcp.sh submit --skip-build

# Kill ALL runner VMs and submit fresh
./scripts/rav-gcp.sh submit --skip-build --cleanup-all --yes

# Resume a previous run (same RUN_ID = downloads last.pt)
./scripts/rav-gcp.sh submit --run-id <RUN_ID>
```

### Kill a stuck VM

```bash
# Option A: rav-gcp safe stop (writes .stop + deletes VM)
./scripts/rav-gcp.sh delete --yes

# Option B: direct gcloud (does NOT write .stop — may auto-restart)
gcloud compute instances list --project=rav-ai-488706
gcloud compute instances delete <VM_NAME> --zone=us-east1-c --project=rav-ai-488706 --quiet
```

Note: `rav-gcp.sh submit` only cleans up VMs matching the **same
RUN_ID label**. A new submit won't kill VMs from a prior run. Use `--cleanup-all`
or `rav-gcp.sh delete` to kill VMs from other runs first.

### Monitor

```bash
./scripts/rav-gcp.sh id                           # resolve active run id / vm name
./scripts/rav-gcp.sh status                       # manifest + heartbeat summary
./scripts/rav-gcp.sh health --json                # health snapshot as JSON
./scripts/rav-gcp.sh serial 200                   # last 200 lines of serial console
./scripts/rav-gcp.sh events --since 24h           # cloud system events
./scripts/rav-gcp.sh list all                     # all runner VMs
./scripts/rav-gcp.sh watch 60                     # auto-refresh every 60s
./scripts/rav-gcp.sh monitor --single --pin-run-id  # tmux monitor workspace
```

### Cloud Logging (for deeper serial output)

```bash
gcloud logging read 'logName:"google_metadata_script_runner"' \
  --project=rav-ai-488706 --freshness=1h --limit=50 \
  --format='value(timestamp,jsonPayload.message)'
```

## 10) Spot VM Resilience (v0.2.6)

After Feb 27 preemption incident (two VMs preempted without notification or auto-restart), the following was added:

- **State machine** (`state_transitions.json`): Canonical states with CAS transitions via `if_generation_match`. Terminal states (COMPLETE, FAILED, PARTIAL, STOPPED) cannot be overwritten.
- **State helper wrapper** (`gcp/state_helpers.sh`): Thin wrapper that sources shared `gcp-spot-runner/state_helpers.sh` for transition validation helpers.
- **Preemption watcher**: Background process in container polls GCE metadata every 5s. On preempt → CAS PREEMPTED + Discord notification.
- **Startup terminal guard**: Container reads `state.json` before owner-lock. If terminal → self-delete, no work executed.
- **Cloud reconciler** (`cloud_reconciler/`): Thin wrappers that delegate to shared implementation in `gcp-spot-runner/cloud_reconciler/` (stale detection + restart, two-stage heartbeat stale + VM gone → ORPHANED).
- **Restart lock** (`restart.lock`): Shared GCS lock prevents dual restart from local orchestrator + reconciler.
- **`caffeinate` + HUP trap**: Local submit scripts survive terminal close and macOS idle sleep.

## 11) Current Recommendation for CheXpert Spot Runs

Starting point:
- `GPU_TIMEOUT_SEC="1200"`
- `POLL_INTERVAL="120"`
- `PROGRESS_STALL_POLLS="10"`
- zone fallback enabled (`us-east1-b/c/d`)

If repeated GPU timeout persists:
- try alternate zone
- use larger machine shape temporarily
- evaluate non-spot for baseline validation run

## 12) Incident: CheXpert-Small Run Ended with `exit_code=1` (Not Preemption)

Run investigated:
- `RUN_ID=rav-chexpert-20260228-073711`
- Manifest:
  - `phase=finished`
  - `exit_code=1`
  - `started_at=2026-02-28T09:19:49Z`
  - `finished_at=2026-02-28T10:53:58Z`
- Attempts:
  - `instances/0.json` created at `2026-02-28T07:37:44Z`
  - `instances/1.json` created at `2026-02-28T09:17:03Z`

Preemption verdict:
- `./scripts/rav-gcp.sh preempt --run-id rav-chexpert-20260228-073711 --since 72h`
  returned no preemption events.
- This failure mode was app-level/container exit, not spot preemption.

Observed behavior before failure:
- Startup completed image pull + GPU driver install.
- Container job command started and entered dataset sync:
  - `gcloud storage rsync -r gs://.../datasets/chexpert/raw data/raw/chexpert`
  - Log progress reached `listed 223652...`.
- Run never produced training artifacts:
  - `checkpoint_sync/metrics/history.jsonl` exists but size is `0`.
  - No `results/**` objects.

Likely failure stage:
- Failure occurred during or immediately after large dataset `rsync` in the
  startup job command, before `train_chest_baseline.py` produced metrics/checkpoints.
- Exact terminal error line was not retained in available Cloud Logging slices
  (copy-line volume dominated metadata-script output).

**Root cause confirmed (2026-03-02):**
- Same bug as Section 2 → G: `_write_marker "$marker"` missing `"$uri"` arg in
  `gcp_sync_chexpert_cache.sh`. The rsync finished successfully, then `set -u`
  killed the script at `_write_marker` line 85 (`$2: unbound variable`).
- Fix applied: pass URI to `_write_marker` (see Section 2 → G for details).

Related stale run note:
- `RUN_ID=rav-chexpert-20260228-070057` has `.stop` and stale heartbeat but
  manifest still reports `phase=running`.

Action item:
- Persist full startup/container stdout+stderr to GCS per run
  (for example `gs://<BUCKET>/runs/<RUN_ID>/startup.log`) so next non-zero exit
  has a recoverable terminal error line.

## 13) DataLoader shared memory exhaustion (`--shm-size`)

**Observed**: 2026-03-02. Training ran 3 epochs successfully, then crashed:
```
RuntimeError: DataLoader worker killed by signal: Bus error. Out of shared memory.
```

**Root cause**:
- Docker defaults `/dev/shm` to 64 MB.
- PyTorch DataLoader workers use shared memory for IPC (passing tensors from
  worker processes back to the main training process via `multiprocessing`).
- With `num_workers > 0`, memory-mapped tensor buffers in `/dev/shm` eventually
  exceed 64 MB, triggering SIGBUS.

**Fix**: Add `--shm-size=2g` to the `docker run` command in
`gcp-spot-runner/startup.sh`:
```bash
docker run --name spot-runner --rm \
  --shm-size=2g \
  ...
```

**Note**: PyTorch does not detect or warn about insufficient shared memory
ahead of time. The crash typically happens several epochs in (after enough
workers have accumulated shared buffers), making it hard to diagnose.

## 14) Immediate preemption not retried (one-shot restart bug)

**Observed**: 2026-03-02 run `20260302-184203802-4ba0`. VM was preempted,
auto-restart created a new VM, but the new VM was immediately preempted again.
The script exited without further retries despite `MAX_RESTARTS=3`.

**Root cause**:
- The auto-restart block in `submit_legacy.sh` was structured as a one-shot
  `if/elif/else`. After `_do_restart()` created a VM and the inner poll loop
  detected the VM was gone (immediately preempted), `FINAL_STATUS` was set to
  `PREEMPTED` and execution fell through to Phase 4 (final status) without
  re-checking the restart condition.
- `ATTEMPT` was incremented to 1 but never compared against `MAX_RESTARTS`
  again.

**Fix**: Converted the outer `if` to a `while...do` loop with `break` on every
non-retryable branch (`.stop` found, exhausted, deadline, rollback failure).
The retryable path (inner poll exits with PREEMPTED/FAILED/TIMEOUT) now loops
back and re-evaluates the restart condition.

Also bumped `MAX_RESTARTS` from 3 to 10 (matching IXQT) in both:
- `gcp-spot-runner/profiles/rav.yaml` (`restart.max_restarts`)
- `RAV/gcp/rav_spot.env` (`MAX_RESTARTS`)

## 15) Documentation and Version Alignment (IXQT -> RAV -> gcp-spot-runner)

Current version map:
- `RAV` app version: `v0.2.27-shared-submit-compat-helpers` (`src/rav_chest/version.py`)
- `gcp-spot-runner` runner version: `v0.6.19-shared-submit-compat-helpers` (`version.py`)
- Reconciler ownership: `RAV/gcp/cloud_reconciler/` is wrapper-only; canonical logic is in `gcp-spot-runner/cloud_reconciler/`.
- State-helper ownership: `RAV/gcp/state_helpers.sh` is wrapper-only; canonical helper implementation is in `gcp-spot-runner/state_helpers.sh`.
- Runner invocation path: `RAV/scripts/gcp_runner_common.sh` now delegates directly to `python3 -m spotctl` with profile runtime flags:
  - `submit --profile rav --config gcp/rav_spot.env --job-command "<cmd>"`
  - `ops --profile rav --config gcp/rav_spot.env`
  - `monitor --profile rav [--single|--dual|--pin-run-id|--follow-latest]`
  - `rav` profile hook fields now propagate to runtime (`pre_job_sync`, `resume_bootstrap`, `results_finalize` with `fail|warn|ignore` policies).
  No temporary generated config file is required for submit/ops.
- Reconciler deploy path: `RAV/gcp/cloud_reconciler/deploy.sh` now delegates through:
  - `python3 -m spotctl reconciler deploy --profile rav`
  - optional `--config gcp/rav_spot.env` when present (or `SPOT_CONFIG_PATH` override).

Primary docs by repo:
- `RAV`:
  - `README.md`
  - `CHANGELOG.md`
  - `gcp/GCP_NOTES.md`
- `gcp-spot-runner`:
  - `README.md`
  - `CHANGELOG.md`
  - `GCP_FINDINGS_REVIEW_2026-03-01.md`

Operational note:
- Keep this version map synchronized whenever submit/startup/entrypoint behavior
  changes so runbooks and incident triage steps always match the deployed
  runner behavior.
