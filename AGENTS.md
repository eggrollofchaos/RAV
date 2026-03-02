# AGENTS Routing

## Mission

Use this file plus `docs/INDEX.md` to route quickly to canonical docs and code surfaces.

## Canonical Behavior Order

1. Shared GCP orchestration behavior (submit/ops/monitor/reconciler/state/restart):
   - `../gcp-spot-runner/docs/INDEX.md`
2. RAV adapter/workload behavior in this repo:
   - `gcp/GCP_NOTES.md`
   - `gcp/GETTING_STARTED.md`
   - `gcp/DATASET_TRANFER.md`
   - `docs/CHEST_RUNBOOK.md`
3. If there is a conflict, treat `gcp-spot-runner/docs/*` as canonical and update RAV docs to match.

## Documentation Maintenance Rule

When adding or changing docs, update `docs/INDEX.md` in the same change.
