# RAV Documentation Index

This is the canonical documentation map for RAV.

## Source-of-Truth Routing

1. Shared GCP runner orchestration behavior (submit/ops/monitor/reconciler/state transitions/restart):
   `../gcp-spot-runner/docs/INDEX.md` (canonical outside this repo).
2. RAV adapter/workload behavior and operator workflows: this repo docs.
3. If there is a conflict, shared runner docs win and RAV docs should be updated to match.

## Start Here

- [../README.md](../README.md) — product overview and primary operator entrypoints.
- [INITIATIVES.md](INITIATIVES.md) — current initiative inventory, progress, remaining work, and imported-lane boundaries.

## Core Operator Docs

- [../gcp/GETTING_STARTED.md](../gcp/GETTING_STARTED.md) — concise command-first GCP quickstart, including `gcp_*.sh` wrapper naming contract.
- [../gcp/GCP_NOTES.md](../gcp/GCP_NOTES.md) — end-to-end GCP runbook, incidents, and recovery notes.
- [../gcp/DATASET_TRANSFER.md](../gcp/DATASET_TRANSFER.md) — one-time large dataset transfer workflow.
- [CHEST_RUNBOOK.md](CHEST_RUNBOOK.md) — end-to-end chest-track experiment/operator runbook.
- [retrospectives/](retrospectives/) — durable work closeouts and closeout-linked retrospectives, including the 2026-06-04 chest-first planning, CheXpert local data-prep, Streamlit/LLM MVP, Sean workstation, and GCP runner addendum closeouts.
- [knowledge-base/](knowledge-base/) — curated project learnings and decisions extracted from retrospectives and incidents, including RAV data-management decisions, MVP app ops, and CheXpert cloud-training learnings.
- [../reference_pipelines/chest_xray_eva_vlm/README.md](../reference_pipelines/chest_xray_eva_vlm/README.md) — sanitized reference lanes imported from the older chest X-ray prototype.
- [coordination/](coordination/) — live coordination summary, history, and shift-note template for the repo-local `$coord-update` protocol.
- [knowledge-base/qa/2026-06-24_rav-ops.md](knowledge-base/qa/2026-06-24_rav-ops.md) — RAV operational Q&A bank used by coord-update.

## Project Management

- [../pm/backlog.md](../pm/backlog.md) — actionable follow-ups surfaced by closeouts.
- [../pm/issues.md](../pm/issues.md) — open risks surfaced by closeouts.
- [../pm/ideas.md](../pm/ideas.md) — deferred roadmap ideas surfaced by closeouts.
- [../pm/done.md](../pm/done.md) — completed closeout capture index.

## Maintenance Rule

When adding/moving docs, update this file in the same change so the map stays authoritative.
