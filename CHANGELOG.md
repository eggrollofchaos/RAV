# Changelog

All notable changes to this project are documented in this file.

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
