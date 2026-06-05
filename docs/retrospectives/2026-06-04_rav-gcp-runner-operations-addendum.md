---
title: RAV GCP Runner Operations Addendum
slug: rav-gcp-runner-operations-addendum
type: retrospective
status: live
created: 2026-06-04
updated: 2026-06-04
owner: Alex Xin
scope: project
project: rav
tags: [gcp, spot-runner, chexpert, checkpointing, operations]
work-items: []
related:
  - docs/retrospectives/2026-05-29_chexpert-gcp-dataset-ops.md
  - docs/retrospectives/2026-05-29_chexpert-training-stability.md
  - docs/knowledge-base/learnings/2026-05-29_rav-chexpert-ops.md
agent: Codex
agent-provider: OpenAI
agent-interface: Codex Desktop
agent-session-id: 019c9b75-9966-79d3-989b-ce0fd30e3473
session-label: RAV - GCP Updates
invocation-context: session-closeout: closeable
session-lifecycle: closeable
session-closeout-note: .agent-sessions/closed/session-closeout-019c9b75-9966-79d3-989b-ce0fd30e3473.md
---

# RAV GCP Runner Operations Addendum - 2026-06-04

## Metadata

- Unit: RAV GCP spot-runner integration and operator workflow addendum.
- Unit type: initiative addendum.
- Status: complete for current wrapper/operator knowledge; active experiments continue separately.
- Repo: `/Users/wax/coding/RAV`.
- Branch / PR: `main`, no PR identified in this closeout.
- Work item IDs: none identified.
- Agent: Codex.
- Agent provider: OpenAI.
- Agent interface: Codex Desktop.
- Agent session ID: `019c9b75-9966-79d3-989b-ce0fd30e3473`.
- Session label: `RAV - GCP Updates`.
- Invocation context: `session-closeout: closeable`.
- Session lifecycle: closeable.
- Session closeout note: `.agent-sessions/closed/session-closeout-019c9b75-9966-79d3-989b-ce0fd30e3473.md`.
- Parent context: RAV CheXpert remote training and shared `gcp-spot-runner` adapter work.
- Sources inspected: `scripts/rav-gcp.sh`, `scripts/gcp_runner_common.sh`, `scripts/gcp_submit_chexpert_experiment.sh`, `scripts/gcp_train_with_checkpoint_sync.sh`, `configs/primary/chest_chexpert_5task_policy.yaml`, `gcp/GETTING_STARTED.md`, `gcp/GCP_NOTES.md`, `CHANGELOG.md`, `docs/retrospectives/2026-05-29_chexpert-gcp-dataset-ops.md`, `docs/retrospectives/2026-05-29_chexpert-training-stability.md`, `docs/knowledge-base/learnings/2026-05-29_rav-chexpert-ops.md`, current conversation history.

## 1. Work Completed

| What | Why | How | Evidence |
|------|-----|-----|----------|
| Settled package boundary for GCP runner | RAV needed fast GCP training without copying the whole runner into the repo | Kept `gcp-spot-runner` as sibling external runner and RAV as thin profile/workload adapter | `scripts/gcp_runner_common.sh`; `gcp/GETTING_STARTED.md`; `gcp/GCP_NOTES.md` |
| Built command-first RAV GCP surface | User needed repeatable build/submit/status/serial/delete commands | Added `scripts/rav-gcp.sh` and thin wrappers for build, submit, ops, monitor, version, POC, primary, and CheXpert experiments | `scripts/rav-gcp.sh`; `scripts/gcp_submit_chexpert_experiment.sh` |
| Captured image freshness rule | Stale container images caused runtime files/configs to be missing on VM | Documented build-before-submit when configs/scripts/src/runtime files change; submit wrappers default to skip build | `gcp/GETTING_STARTED.md`; `gcp/GCP_NOTES.md`; `CHANGELOG.md` |
| Added checkpoint-safe cloud training loop | Spot runs need restart/resume semantics | Wrapped training with periodic upload of `last.pt`, `best.pt`, metrics, per-class CSVs, and confusion CSVs to GCS | `scripts/gcp_train_with_checkpoint_sync.sh` |
| Clarified 5-task launch command | User needed the exact "5task VM" command | Confirmed the command is the CheXpert experiment wrapper with `configs/primary/chest_chexpert_5task_policy.yaml` | `scripts/gcp_submit_chexpert_experiment.sh`; `configs/primary/chest_chexpert_5task_policy.yaml` |
| Preserved operational failure learnings | Cloud Build, service account permissions, GPU startup windows, heartbeat windows, and stale-image failures were easy to re-hit | Centralized notes in GCP docs and changelog; kept status/serial/event commands visible | `gcp/GCP_NOTES.md`; `gcp/GETTING_STARTED.md`; `CHANGELOG.md` |

## 2. Ideas, Decisions, Questions Addressed

| Item | Type | Resolution | Rationale | Evidence |
|------|------|------------|-----------|----------|
| Import shared runner or copy code? | decision | Treat `gcp-spot-runner` as a sibling dependency and keep RAV wrappers thin | Shared orchestration belongs in one place; RAV owns workload config/scripts | `scripts/gcp_runner_common.sh`; `gcp/GCP_NOTES.md` |
| Put data in Docker image? | decision | No; keep datasets and checkpoints in GCS/persistent disk paths | Data in build context caused slow/fragile builds and would bloat images | `gcp/DATASET_TRANSFER.md`; `gcp/GCP_NOTES.md` |
| How should a preempted run resume? | decision | Reuse the same `RUN_ID` when continuing the same experiment | Same run ID lets wrapper find synced `last.pt` and resume without fragmenting artifacts | `gcp/GETTING_STARTED.md`; `scripts/gcp_train_with_checkpoint_sync.sh` |
| How do we see training progress? | question | Use serial/status/events plus synced `history.jsonl` where available | Training progress may be inside container stdout, serial logs, and GCS metrics | `scripts/rav-gcp.sh`; `gcp/GETTING_STARTED.md` |

## 3. Issues Encountered And Resolved

| Issue | Impact | Resolution | Verification | Prevention / Learning |
|-------|--------|------------|--------------|---------------------|
| `gcloud builds submit` source archiving crashed | Blocked image build | Captured staged-source and local-build fallback paths, plus Cloud SDK Python isolation guidance | `gcp/GCP_NOTES.md` | Keep build contexts small and do not point Cloud SDK at fragile venv internals |
| Cloud Build staged source 403 | Fallback build could not read staged tarball | Identified missing read permission for the build service account | `gcp/GCP_NOTES.md` | Treat service-account bucket access as part of build setup |
| VM killed for no heartbeat while GPU setup was still within expected window | Training restarted before GPU driver setup could finish | Aligned heartbeat no-progress window with GPU timeout | `gcp/GCP_NOTES.md` | Timeout windows must be compared as products, not isolated constants |
| New config missing inside container | Run failed immediately with `FileNotFoundError` | Rebuild image before submitting when runtime files change | `gcp/GCP_NOTES.md` | Every runtime config/script change needs an image freshness check |

## 4. Remaining Ideas, Decisions, Questions

| Item | Type | Priority | Time Horizon | Owner / Next Action | Tracking |
|------|------|----------|--------------|---------------------|----------|
| Verify CheXpert dataset completeness in GCS | question | P1 | near-term | Run object count/size/sample-read checks before long full-data training | `pm/backlog.md` |
| Decide next CheXpert experiment after threshold tuning | decision | P1 | near-term | Use validation-threshold results before launching next config | `docs/retrospectives/2026-05-29_chexpert-model-evaluation-thresholding.md`; `pm/backlog.md` |
| Keep runner lineage synchronized | idea | P2 | later | Update RAV docs when `gcp-spot-runner` changes required wrapper contracts | `pm/backlog.md` |

## 5. Remaining Issues

| Issue | Risk | Priority | Time Horizon | Owner / Next Action | Tracking |
|-------|------|----------|--------------|---------------------|----------|
| Long CheXpert runs still depend on cloud quota, image freshness, dataset freshness, and GPU startup health | A single stale layer can waste hours | P1 | near-term | Run preflight checks before each expensive submit | `pm/issues.md` |

## 6. Learnings

### Local

- For RAV cloud training, check image freshness, data freshness, and GPU visibility before interpreting model logs.
- `RUN_ID` is not just a label; it controls checkpoint resume and artifact continuity.
- `serial`, `status`, and synced metrics answer different questions; use all three during remote training.

### Project

- The RAV repo should stay a workload adapter over `gcp-spot-runner`, not a fork of the runner.
- Every GCP doc should name whether behavior is runner-owned or RAV-owned.

### Global Candidates

- ML spot-runner projects should document three freshness gates together: source image, runtime data, and accelerator availability.

## 7. Strategic Fit

- Task / sprint: Make RAV CheXpert training operable on GCP.
- Epic / initiative: Remote model fitting and experiment iteration.
- Product / program / engagement: EECS E6895 RAV model-development workflow.
- Repo / project: RAV.
- Global framework: reusable cloud training operations.
