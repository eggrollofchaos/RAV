# RAV Live Repo Summary

*Last updated: 2026-06-24 20:20 EDT*
*Configured emphasis window: current RAV closeout and active CheXpert/GCP follow-ups; older durable context stays in retrospectives and KB entries.*
*Current emphasis window: 2026-05-29 -> 2026-06-24, with older still-live blockers retained as needed.*
*Audience: incoming coding agent. Use this for current state. Older or removed detail lives in `repo_summary_history.md`; do not evict material solely because it is older than the configured window.*

> Legend: **[V]** verified from code/git/GitHub/logs | **[I]** inference | **[?]** unresolved.

## 1. Executive Snapshot

- **[V]** Current canonical branch / SHA: `main` at `73e5606` (`origin/main`) when this summary was seeded.
- **[V]** Most important merged change: RAV now carries the cross-tool memory mirror in `CLAUDE.md`; agent-tooling scripts/hooks are centrally managed and ignored locally.
- **[V]** Most important open loop: CheXpert threshold sweep remains P0 in `pm/backlog.md`; tune validation thresholds, freeze them, then evaluate test.
- **[?]** Most important unresolved question: where full/large CheXpert-scale data should live for Sean workstation or any future local GPU run.

## 2. Recent Timeline

| When | Ref | Where | Why it matters |
|---|---|---|---|
| 2026-06-24 20:20 EDT | `codex-cld/session-closeout-coord` | docs/coordination + KB/retro | `coord-update` overlay/starter docs were added and the long historical session was audited against existing split retrospectives. |
| 2026-06-17 | `73e5606` | `main` | Cross-tool `CLAUDE.md` memory mirror landed; this is the current root truth for agent startup context. |
| 2026-06-04 | closeout retros | docs/retrospectives + PM | RAV planning, CheXpert local prep, Streamlit/LLM MVP, GCP runner operations, and Sean workstation RAV GPU closeouts were captured. |
| 2026-05-29 | CheXpert split retros | docs/retrospectives + KB | CheXpert GCP/dataset ops, training stability, and model evaluation/thresholding were split out of the earlier omnibus closeout. |

## 3. Current Technical State

### Runtime / stack

- **[V]** RAV is a Streamlit/PyTorch radiology prototype for chest X-ray classification, structured findings, grounded reports, and optional LLM rewrite/Q&A.
- **[V]** Primary local data path is CheXpert-small under `data/raw/chexpert/CheXpert-v1.0-small`; full CheXpert belongs on GCP/external storage unless storage is planned.
- **[V]** GCP orchestration is a thin RAV adapter over sibling `gcp-spot-runner`; shared runner docs remain canonical for orchestration behavior.
- **[V]** Sean workstation is a usable CUDA smoke/iteration host for RAV, but RAV keeps workstation access details in the global ai-coding-agents KB and workload constraints locally.

### Active lanes

- **[V]** CheXpert model-quality lane: threshold tuning before backbone churn.
- **[V]** Demo/application lane: Streamlit/LLM MVP exists; needs real-checkpoint end-to-end validation before demo claims.
- **[V]** GCP runner lane: wrappers and docs exist; long runs still need image/data/GPU freshness checks.
- **[V]** Coordination lane: `docs/coordination/` is now the tracked live/history/template surface; per-session shift notes stay ignored.

## 4. Active Findings / Open Loops

1. **CheXpert thresholds**
   - **[V]** What is known: AUROC showed useful ranking signal, while default thresholds collapsed at least one class in tiny local test evidence.
   - **[?]** What is still unresolved: tuned validation thresholds and frozen test evaluation.
   - Next action: run the threshold sweep tracked in `pm/backlog.md`.

2. **Dataset/storage placement**
   - **[V]** What is known: local CheXpert-small is small enough for development; full CheXpert is not safe for internal-disk work without a plan.
   - **[?]** What is still unresolved: whether Sean workstation gets external storage, a complete subset, or only smoke data.
   - Next action: decide placement before copying large datasets.

3. **Coordination bootstrap**
   - **[V]** What is known: RAV now has coord-update overlay config, tracked starter coordination docs, and a project Q&A bank.
   - **[?]** What is still unresolved: first real orchestrator pass after future agents add shift notes.
   - Next action: run `$coord-update pull` at session start and `$coord-update agent` before yielding material changes.

## 5. Issues / PRs / Ownership Signals

| Issue / PR | Owner signal | Current state |
|---|---|---|
| `pm/backlog.md` P0 threshold sweep | next RAV model-quality session | OPEN |
| `pm/backlog.md` P1 primary training/eval/app validation | next RAV implementation session | OPEN |
| `pm/issues.md` P1 CheXpert split provenance / LLM authority risks | next RAV demo/claims review | OPEN |

## 6. Validation / Proof Ledger

| Date | Run / command / artifact | Branch / SHA | Status | Notes |
|---|---|---|---|---|
| 2026-06-24 | `python3 .../scripts/check_coord_overlay.py .claude/skills/coord-update/overlay.local.md` | root local overlay | pass | Overlay validates with `flat-list` backlog dialect and F1-F5 enabled. |
| 2026-06-24 | `python3 .../scripts/retro-context.py ...` | `codex-cld/session-closeout-coord` | pass | Found existing split retros and prior session closeout for historical-session audit. |
| 2026-06-04 | CheXpert local prep + sanity check | `main` historical closeout | pass | Prep completed in about 5.3s; sanity with `--skip-file-check` passed. |
| 2026-05-29 / 2026-06-04 | RAV local GPU smoke on Sean workstation | external Windows host | pass | CUDA train/eval smoke succeeded; model-quality use still needs complete data/threshold plan. |

## 7. Recommended Next Steps

1. Run CheXpert validation threshold sweep and frozen test evaluation.
2. Validate Streamlit end-to-end with a real checkpoint and `.env` OpenAI path.
3. Run GCP data/image/GPU freshness preflight before any expensive long cloud run.
4. Use `$coord-update agent` after future material RAV work so live coordination can age into this summary.

## 8. Key References

- `docs/INDEX.md`
- `docs/coordination/repo_summary_history.md`
- `docs/coordination/shift_coordination_note_template.md`
- `docs/knowledge-base/qa/2026-06-24_rav-ops.md`
- `docs/knowledge-base/learnings/2026-05-29_rav-chexpert-ops.md`
- `docs/knowledge-base/learnings/2026-06-24_rav-coordination-closeout.md`
- `docs/retrospectives/2026-06-24_coord-update-historical-session-closeout.md`
- `pm/backlog.md`

## 9. Historical Notes Pointer

- Older detail removed from this live summary belongs in `repo_summary_history.md`.
- Durable work history lives primarily in `docs/retrospectives/` and `docs/knowledge-base/`; this file is a current-state memo, not an archive.
