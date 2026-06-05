---
title: CheXpert Local Data Prep Closeout
slug: chexpert-local-data-prep
type: retrospective
status: live
created: 2026-06-04
updated: 2026-06-04
owner: Alex Xin
scope: project
project: rav
tags: [chexpert, chexpert-small, data-management, local-storage, closeout]
work-items: []
related:
  - docs/retrospectives/2026-06-04_rav-chest-first-planning-local-mvp.md
  - docs/retrospectives/2026-05-29_chexpert-gcp-dataset-ops.md
  - docs/knowledge-base/learnings/2026-05-29_rav-chexpert-ops.md
  - docs/knowledge-base/decisions/data-management.md
agent: Codex
agent-provider: OpenAI
agent-interface: Codex Desktop
agent-session-id: 019c9aae-7002-7a40-9e22-75f7b632f021
session-label: Project planning
invocation-context: session-closeout: closeable
session-lifecycle: closeable
session-closeout-note: .agent-sessions/closed/session-closeout-019c9aae-7002-7a40-9e22-75f7b632f021.md
---

# CheXpert Local Data Prep Closeout - 2026-06-04

## Metadata

- Unit: CheXpert local download, storage triage, and processed CSV prep
- Unit type: initiative
- Status: data prep complete; primary training remains next
- Repo: RAV
- Branch / PR: `main`, ahead of `origin/main` by 2 commits; no PR inspected in this closeout
- Work item IDs: none identified
- Agent: Codex
- Agent provider: OpenAI
- Agent interface: Codex Desktop
- Agent session ID: `019c9aae-7002-7a40-9e22-75f7b632f021`
- Session label: `Project planning`
- Invocation context: `session-closeout: closeable`
- Session lifecycle: `closeable`
- Session closeout note: `.agent-sessions/closed/session-closeout-019c9aae-7002-7a40-9e22-75f7b632f021.md`
- Parent context: RAV primary CheXpert track
- Sources inspected: `data/raw/chexpert/CheXpert-v1.0-small/train.csv`, `data/raw/chexpert/CheXpert-v1.0-small/valid.csv`, `data/processed/chexpert_train.csv`, `data/processed/chexpert_val.csv`, `data/processed/chexpert_test.csv`, `scripts/prepare_chexpert_data.py`, `configs/primary/chest_chexpert.yaml`, `docs/CHEST_RUNBOOK.md`, `docs/retrospectives/2026-05-29_chexpert-gcp-dataset-ops.md`, `docs/knowledge-base/learnings/2026-05-29_rav-chexpert-ops.md`

## 1. Work Completed

| What | Why | How | Evidence |
|------|-----|-----|----------|
| Identified full CheXpert as too large for local internal-disk work | Avoid filling the MacBook drive with a roughly 471 GB full-dataset download | Shifted local path to CheXpert-small and kept full CheXpert for GCP/external-storage scenarios | Conversation record, `docs/CHEST_RUNBOOK.md`, prior `docs/retrospectives/2026-05-29_chexpert-gcp-dataset-ops.md` |
| Confirmed local CheXpert-small layout | Make the primary track runnable locally | Verified `data/raw/chexpert/CheXpert-v1.0-small` contains `train.csv`, `valid.csv`, `train/`, and `valid/` | `find data/raw/chexpert`, `du -sh data/raw/chexpert` reported about `541M` |
| Confirmed CSV scale | Set expectations for prep runtime and split sizes | Counted `223415` lines in `train.csv` and `235` lines in `valid.csv` including headers | `wc -l data/raw/chexpert/CheXpert-v1.0-small/{train.csv,valid.csv}` |
| Updated/used CheXpert prep defaults | Match the active local primary dataset | `scripts/prepare_chexpert_data.py` defaults to `data/raw/chexpert/CheXpert-v1.0-small`, uses a stratified valid split, and writes `data/processed/chexpert_*.csv` | `scripts/prepare_chexpert_data.py` |
| Verified prep runtime and outputs | Resolve the current "taking forever" report with evidence | Ran `.venv/bin/python scripts/prepare_chexpert_data.py --chexpert-root data/raw/chexpert/CheXpert-v1.0-small --output-dir data/processed --test-fraction-from-valid 0.1 --seed 42` | Completed in about `5.3s`; wrote `223414` train rows, `210` val rows, and `24` test rows |
| Ran lightweight data sanity check | Confirm split CSV structure before closeout | Ran `.venv/bin/python scripts/check_chest_data_sanity.py --config configs/primary/chest_chexpert.yaml --skip-file-check` | Status `pass`; no empty paths or duplicates; wrote `outputs/chest_baseline/metrics/data_sanity.json` |

## 2. Ideas, Decisions, Questions Addressed

| Item | Type | Resolution | Rationale | Evidence |
|------|------|------------|-----------|----------|
| Where should CheXpert-small live? | decision | `data/raw/chexpert/CheXpert-v1.0-small` | This matches the runbook and prep script defaults | `docs/CHEST_RUNBOOK.md`, `scripts/prepare_chexpert_data.py` |
| How small is the local copy? | question | Local evidence shows about `541M` in this repo | The active local copy is CheXpert-small, not the full Azure multi-batch release | `du -sh data/raw/chexpert` |
| Is the prepare script expected to be slow? | question | No, not for CheXpert-small CSV prep | The script reads two CSVs, cleans labels, splits `valid.csv`, and writes three CSVs; it does not scan all image files | `scripts/prepare_chexpert_data.py`, closeout timing run |
| Should the full Azure SAS download continue locally? | decision | No for the laptop unless external storage is explicitly available | The full release is far larger than the current local development need | Conversation record, `docs/retrospectives/2026-05-29_chexpert-gcp-dataset-ops.md` |

## 3. Issues Encountered And Resolved

| Issue | Impact | Resolution | Verification | Prevention / Learning |
|-------|--------|------------|--------------|---------------------|
| Full CheXpert download exceeded local storage comfort | Risked consuming the entire laptop disk | Stopped treating full CheXpert as the local default; use CheXpert-small locally | Active local `data/raw/chexpert` is about `541M` | Name dataset variants explicitly before starting downloads |
| `prepare_chexpert_data.py` appeared stuck | User could not tell whether the script was doing useful work | Checked for running prep process, inspected local data, then timed the script | No local prep process was found; direct run completed in about `5.3s` | If prep takes minutes, check `--chexpert-root`, Python environment, and whether a different dataset path is being used |
| Existing processed files could obscure whether current prep succeeded | Stale outputs can hide a failed or old run | Re-ran prep and observed row counts | `data/processed/chexpert_train.csv`, `data/processed/chexpert_val.csv`, `data/processed/chexpert_test.csv` updated by the closeout run | Treat prep command output as the source of truth for split counts |

## 4. Remaining Ideas, Decisions, Questions

| Item | Type | Priority | Time Horizon | Owner / Next Action | Tracking |
|------|------|----------|--------------|---------------------|----------|
| Run optional full file-existence sanity check | question | P2 | later | `python scripts/check_chest_data_sanity.py --config configs/primary/chest_chexpert.yaml` without `--skip-file-check` if image-path completeness is uncertain | `pm/backlog.md` |
| Train the primary CheXpert baseline | decision | P1 | near-term | `python scripts/train_chest_baseline.py --config configs/primary/chest_chexpert.yaml` | `pm/backlog.md` |
| Decide full CheXpert storage route | decision | P2 | later | Use GCP or external disk before attempting full local download again | `pm/issues.md` |

## 5. Remaining Issues

| Issue | Risk | Priority | Time Horizon | Owner / Next Action | Tracking |
|-------|------|----------|--------------|---------------------|----------|
| Tiny `valid.csv` produces a 24-row local test split at `test_fraction=0.1` | Useful for smoke testing only; not enough for model quality claims | P1 | near-term | Train/eval with this split only as an MVP smoke test, then use a larger evaluation set | `pm/issues.md` |
| If the user's terminal still shows prep running, it is likely not this repo/process | Could be a stale shell, wrong environment, or different root | P2 | immediate | Check `ps aux | rg '[p]repare_chexpert_data'` and rerun the documented command from repo root | This retrospective |

## 6. Learnings

### Local

- For the local CheXpert-small mirror, data prep should take seconds. Long runtime points to wrong root, wrong process, or a different dataset variant.
- `data/processed/chexpert_*.csv` can be regenerated safely from `train.csv` and `valid.csv`; it should not be hand-edited.

### Project

- Keep full CheXpert, CheXpert-small, and CheXpert Plus separated in docs, commands, and storage plans.
- The first CheXpert split is a pipeline smoke test, not a clinical-quality evaluation split.

### Global Candidates

- Large-dataset onboarding should include a "small local path vs full cloud path" decision before issuing download commands.

## 7. Strategic Fit

- Task / sprint: Make primary CheXpert data usable locally.
- Epic / initiative: RAV chest X-ray classifier primary baseline.
- Product / program / engagement: Agentic radiology prototype.
- Repo / project: RAV.
- Global framework: Storage-aware ML dataset onboarding.
