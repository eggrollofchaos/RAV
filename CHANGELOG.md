# Changelog

All notable changes to this project are documented in this file.

## Unreleased

## v0.2.12-profile-runtime-submit - 2026-03-02

Updated:
- `scripts/gcp_runner_common.sh` submit/ops path simplified to profile runtime invocation (no temporary generated config files):
  - submit: `spotctl submit --profile rav --config gcp/rav_spot.env --job-command "<cmd>"`
  - ops: `spotctl ops --profile rav --config gcp/rav_spot.env ...`
- App version to `v0.2.12-profile-runtime-submit`.
- Runner lineage docs synchronized to `gcp-spot-runner v0.5.3-submit-job-command-override` in:
  - `README.md`
  - `gcp/GCP_NOTES.md`

## v0.2.11-reconciler-profile-wrapper - 2026-03-02

Updated:
- `gcp/cloud_reconciler/deploy.sh` now delegates reconciler deploy with explicit shared profile resolution:
  - `python3 -m spotctl reconciler deploy --profile rav`
  - optional `--config gcp/rav_spot.env` (or `SPOT_CONFIG_PATH`) for env overlay values.
- App version to `v0.2.11-reconciler-profile-wrapper`.
- Runner lineage docs synchronized to `gcp-spot-runner v0.5.2-reconciler-profile-runtime` in:
  - `README.md`
  - `gcp/GCP_NOTES.md`

## v0.2.10-spotctl-direct-wrapper - 2026-03-02

Updated:
- `scripts/gcp_runner_common.sh` now delegates submit/ops directly to `python3 -m spotctl` with `SPOT_CONFIG_PATH`, instead of temp symlinked runner script execution.
- `gcp/cloud_reconciler/deploy.sh` now delegates via shared runner interface:
  - `python3 -m spotctl reconciler deploy`
  instead of invoking runner deploy internals directly.
- Runner install checks now validate `spotctl` + legacy backend files in `gcp-spot-runner`.
- App version to `v0.2.10-spotctl-direct-wrapper`.
- Runner lineage docs synchronized to `gcp-spot-runner v0.5.0-spotctl-cli-shims` in:
  - `README.md`
  - `gcp/GCP_NOTES.md`

## v0.2.9-reconciler-centralized-wrapper - 2026-03-02

Updated:
- `gcp/cloud_reconciler/main.py` and `state_machine.py` are now thin wrappers that execute shared source from `gcp-spot-runner/cloud_reconciler/`.
- `gcp/cloud_reconciler/deploy.sh` now delegates deployment to shared runner deploy script.
- `gcp/cloud_reconciler/requirements.txt` now points to shared runner requirements.
- App version to `v0.2.9-reconciler-centralized-wrapper`.
- Spot runner lineage version in README to `gcp-spot-runner v0.4.0-reconciler-centralization`.

## v0.2.8-reconciler-phase1-hardening - 2026-03-02

Updated:
- GCP persistent-disk docs and defaults now use a writable COS mount path:
  - `DATA_DISK_MOUNT_PATH="/var/lib/spot-data"`
  - Avoids startup failure: `mkdir: cannot create directory '/mnt/spot-data': Read-only file system`
- GCP troubleshooting docs now include explicit diagnosis/remediation for the COS read-only mount-path failure.
- GCP docs now call out region selection flexibility (for example `us-central1`) when `us-east1` is shared/constrained.
- Cloud reconciler hardening (Phase 1 reliability):
  - `gcp/cloud_reconciler/state_machine.py`: transition-file path resolution now works in both source and flat Cloud Function deploy layouts.
  - `gcp/cloud_reconciler/main.py`: restart attempt persistence fixed via `attempt_override`; restart now fails closed when `startup_script` is missing.
  - `gcp/cloud_reconciler/main.py`: persistent data disk now attaches on reconciler restarts, including startup metadata for mount behavior.
  - `gcp/cloud_reconciler/main.py`: restart zone is pinned when `data_disk_enabled=true` to avoid cross-zone disk attach failures.
  - `gcp/cloud_reconciler/main.py` + `deploy.sh`: removed IXQT-pinned defaults; runtime/deploy config is now env-driven.
- Reconciler tests expanded:
  - `tests/test_reconciler.py`: added behavior tests for incremented-attempt persistence, disk-zone pinning, and startup-script requirement.
  - `tests/test_state_machine.py`: added transitions path resolution coverage.
- App version to `v0.2.8-reconciler-phase1-hardening`.
- Spot runner lineage version in README to `gcp-spot-runner v0.3.1-phase1-reliability-hardening`.

## v0.2.7-gcp-docs-version-sync - 2026-03-01

Added:
- Cross-repo version lineage documentation in README (`RAV` + `gcp-spot-runner` mapping).
- GCP notes updates for recent CheXpert incident triage and run-history interpretation.

Updated:
- App version to `v0.2.7-gcp-docs-version-sync`.
- Documentation pointers for active GCP operations notes and runner-version context.

## v0.2.6-gcp-spot-resilience - 2026-03-01

Added:
- **State machine** (`gcp/state_transitions.json`, `gcp/state_helpers.sh`): Canonical state contract (RUNNING, COMPLETE, FAILED, PARTIAL, PREEMPTED, ORPHANED, RESTARTING, STOPPED) with CAS transitions via GCS `if_generation_match`.
- **Preemption watcher** (`gcp/entrypoint.sh`): Background process polls GCE metadata preemption endpoint every 5s; on preempt, CAS writes PREEMPTED state, sends Discord notification, kills heartbeat.
- **`_write_state()` CAS helper** (`gcp/entrypoint.sh`): Python-based state transitions with state_transitions.json validation, status.txt compatibility mapping, event logging.
- **Startup terminal guard** (`gcp/entrypoint.sh`): VM reads state.json before owner-lock; self-deletes on terminal state (STOPPED/COMPLETE/FAILED/PARTIAL).
- **Cloud reconciler** (`gcp/cloud_reconciler/`): Cloud Function for two-stage stale detection (heartbeat stale + VM confirmed gone), status.txt drift repair, restart orchestration via restart.lock.
- **`restart_config.json`** (`scripts/gcp_submit_primary.sh`): Authoritative restart source written at submit time with all VM parameters.
- **STOPPED handling** in submit scripts: poll loop, status classification, and pre-poll smoke check all handle STOPPED as terminal.
- **`caffeinate` + HUP trap** (`scripts/gcp_submit_primary.sh`, `scripts/gcp_submit_poc.sh`): Prevent macOS idle sleep and survive terminal close.
- **Secret Manager integration** (`scripts/gcp_runner_common.sh`): `ixqt-notify-secret` metadata passed to VMs for Discord webhook resolution via REST API.
- **BATS tests** (`tests/bats/`): 119 tests covering state machine, preemption watcher, CAS transitions, reconciler detection/restart, restart.lock protocol, status.txt drift repair.
- **Python tests** (`tests/test_reconciler.py`, `tests/test_state_machine.py`): 77 tests for reconciler and state machine logic.

Updated:
- PARTIAL status migration: now canonical `PARTIAL` (detail in `status_meta.json`, not in status string).
- `gcp/Dockerfile.train` packages `state_transitions.json` into container image.
- App version to `v0.2.6-gcp-spot-resilience`.

## v0.2.5 - 2026-02-28

Updated:
- Moved GCP_NOTES to `gcp/`, documented GPU fix and ops commands.

## v0.2.4-agent-qa-chat - 2026-02-27

Added:
- Natural-language model Q&A support in `src/rav_chest/llm.py` via `answer_question_about_report`.
- New Streamlit `Ask Agent` page with chat-style interaction grounded in report context.
- Inference payload persistence in Streamlit session state so users can run inference then ask follow-up questions immediately.

Updated:
- Sidebar model selector now supports both rewrite and Q&A flows (`LLM Model (Rewrite/Q&A)`).
- App version to `v0.2.4-agent-qa-chat`.

## v0.2.3-gcp-build-hardening - 2026-02-27

Added:
- Explicit Cloud Build upload rules in `.gcloudignore` (source-only allowlist plus cache/artifact exclusions).
- Centralized one-off GCP setup/fix commands section in `gcp/GETTING_STARTED.md`.

Updated:
- GCP wrapper runtime hardening in `scripts/gcp_runner_common.sh`:
  - `CLOUDSDK_CORE_DISABLE_PROMPTS=1`
  - `CLOUDSDK_PYTHON_SITEPACKAGES=0`
  - auto-select `CLOUDSDK_PYTHON` from local `.venv` when available
  - normalize `RUNNER_DIR` to an absolute path
- GCP wrapper scripts now consistently apply runtime config before invoking gcloud/runner:
  - `scripts/gcp_build_image.sh`
  - `scripts/gcp_submit_primary.sh`
  - `scripts/gcp_submit_poc.sh`
  - `scripts/gcp_ops.sh`
- App version to `v0.2.3-gcp-build-hardening`.

## v0.2.2-gcp-getting-started-docs - 2026-02-27

Added:
- GCP onboarding/quickstart guide at `gcp/GETTING_STARTED.md`.

Updated:
- Added cross-links to the guide from README and chest runbook GCP sections.
- App version to `v0.2.2-gcp-getting-started-docs`.

## v0.2.1-gcp-spot-checkpoint-resume - 2026-02-27

Added:
- GCP training wrapper at `scripts/gcp_train_with_checkpoint_sync.sh` to make spot runs preemption-safe.
- Periodic sync of checkpoints/metrics to GCS during training (`SYNC_INTERVAL_SEC`).
- Bootstrap resume behavior: auto-download `last.pt` from GCS and pass `--resume-checkpoint` when available.
- `--run-id` resume workflow documented for both primary and POC submit paths.

Updated:
- Spot submit wrappers now route both tracks through checkpoint-sync wrapper:
  - `scripts/gcp_submit_primary.sh`
  - `scripts/gcp_submit_poc.sh`
- `gcp/rav_spot.env.example` with `SYNC_INTERVAL_SEC` and updated override examples.
- README + runbook GCP sections with explicit checkpoint sync/resume behavior.
- App version to `v0.2.1-gcp-spot-checkpoint-resume`.

## v0.2.0-openai-llm-rewrite - 2026-02-27

Added:
- OpenAI API wrapper module at `src/rav_chest/llm.py`.
- CLI wrapper at `scripts/llm_wrapper.py` with prompt mode and report-JSON rewrite mode.
- Optional Streamlit inference rewrite flow:
  - Sidebar toggle `Rewrite impression with OpenAI`.
  - Model selector `LLM Model`.
  - Side-by-side deterministic vs rewritten impression display.
  - `llm_rewrite` metadata persisted in downloaded report JSON.
- Automatic `.env` API key resolution for `OPENAI_API_KEY`.
- `.env.example` template for local key setup.

Updated:
- `requirements.txt` with `openai>=1.0,<2`.
- README and runbook usage docs for wrapper + Streamlit LLM rewrite flow.
- Sidebar app version string to `v0.2.0-openai-llm-rewrite`.
