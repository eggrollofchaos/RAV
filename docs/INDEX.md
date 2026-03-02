# RAV Documentation Index

This is the canonical documentation map for RAV.

## Source-of-Truth Routing

1. Shared GCP runner orchestration behavior (submit/ops/monitor/reconciler/state transitions/restart):
   `../gcp-spot-runner/docs/INDEX.md` (canonical outside this repo).
2. RAV adapter/workload behavior and operator workflows: this repo docs.
3. If there is a conflict, shared runner docs win and RAV docs should be updated to match.

## Start Here

- [../README.md](../README.md) — product overview and primary operator entrypoints.

## Core Operator Docs

- [../gcp/GETTING_STARTED.md](../gcp/GETTING_STARTED.md) — concise command-first GCP quickstart.
- [../gcp/GCP_NOTES.md](../gcp/GCP_NOTES.md) — end-to-end GCP runbook, incidents, and recovery notes.
- [../gcp/DATASET_TRANFER.md](../gcp/DATASET_TRANFER.md) — one-time large dataset transfer workflow.
- [CHEST_RUNBOOK.md](CHEST_RUNBOOK.md) — end-to-end chest-track experiment/operator runbook.

## Maintenance Rule

When adding/moving docs, update this file in the same change so the map stays authoritative.
