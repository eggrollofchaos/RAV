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

## Pinned Follow-Ups

- 2026-03-19: Extend `gcp/entrypoint.sh` `run_config.json` snapshots to include hook commands and hook failure policies, so standalone/debug runs preserve more of the runtime contract in cloud artifacts.
- 2026-03-19: Decide whether invalid hook-policy values in the RAV entrypoint should keep normalizing to `warn` for runner parity or fail fast with an explicit configuration error.
