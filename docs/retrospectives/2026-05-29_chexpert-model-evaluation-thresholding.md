---
title: CheXpert Model Evaluation And Thresholding Closeout
slug: chexpert-model-evaluation-thresholding
type: retrospective
status: live
created: 2026-05-29
updated: 2026-06-04
owner: Alex Xin
scope: project
project: rav
tags: [chexpert, evaluation, thresholding, calibration, closeout]
work-items: []
related:
  - docs/knowledge-base/learnings/2026-05-29_rav-chexpert-ops.md
  - docs/retrospectives/2026-05-29_chexpert-remote-training-evaluation.md
  - docs/retrospectives/2026-06-04_sean-workstation-rav-local-gpu.md
agent: Codex
agent-provider: OpenAI
agent-interface: Codex Desktop
agent-session-id: 019db9e1-7c41-7f81-b0f8-a353bbed6f1c
session-label: RAV - Models - Idle
invocation-context: session-closeout: closeable
session-lifecycle: closeable
session-closeout-note: .agent-sessions/closed/session-closeout-019db9e1-7c41-7f81-b0f8-a353bbed6f1c.md
---

# CheXpert Model Evaluation And Thresholding Closeout - 2026-05-29

## Metadata

- Unit: CheXpert model quality evaluation and threshold tuning
- Unit type: initiative
- Status: closed out
- Repo: RAV
- Branch / PR: `main`, no PR identified in this session
- Work item IDs: none identified
- Agent: Codex
- Agent provider: OpenAI
- Agent interface: Codex Desktop
- Agent session ID: `019db9e1-7c41-7f81-b0f8-a353bbed6f1c`
- Session label: `RAV - Models - Idle`
- Invocation context: `session-closeout: closeable`
- Session lifecycle: `closeable`
- Session closeout note: `.agent-sessions/closed/session-closeout-019db9e1-7c41-7f81-b0f8-a353bbed6f1c.md`
- Parent context: RAV chest X-ray classifier track
- Sources inspected: `scripts/eval_chexpert_5task_policy.py`, `src/rav_chest/metrics.py`, `configs/primary/chest_chexpert_5task_policy.yaml`, `configs/primary/chest_chexpert_umixed_regularized_posw.yaml`, `configs/primary/chest_chexpert_effb0_umixed_posw.yaml`, conversation metrics output, `docs/retrospectives/2026-06-04_sean-workstation-rav-local-gpu.md`

## 1. Work Completed

| What | Why | How | Evidence |
|------|-----|-----|----------|
| Interpreted completed 5-task run quality | Needed to decide whether to change model, thresholds, or data | Read validation and local test metrics, including per-class confusion | Conversation record: validation macro AUROC about `0.8917`, validation macro F1 about `0.6604`; local test macro AUROC about `0.8801`, macro F1 about `0.5474` |
| Identified primary failure mode | Atelectasis default operating point predicted every local test case positive | Compared AUROC to thresholded confusion metrics | Conversation record: Atelectasis predicted positive rate `1.0`, specificity `0.0` on 24-row smoke test |
| Recommended threshold tuning before switching backbone | Avoid unnecessary model churn | Reasoned from ranking signal versus threshold collapse | `scripts/eval_chexpert_5task_policy.py`, `src/rav_chest/metrics.py` |
| Added validation threshold sweep support | Needed a repeatable way to tune on `val` and freeze thresholds for `test` | Added CLI flags for tuning, threshold file save/load, threshold source metadata, and per-class optimization | `scripts/eval_chexpert_5task_policy.py`, `src/rav_chest/metrics.py` |
| Defined next controlled ablations | Needed clear fallback if thresholding fails | Chose `umixed_regularized_posw` before `effb0_umixed_posw` | `configs/primary/chest_chexpert_umixed_regularized_posw.yaml`, `configs/primary/chest_chexpert_effb0_umixed_posw.yaml` |
| Linked local GPU execution context | Needed to preserve that Sean's workstation is an execution venue, not a model-quality conclusion | Added cross-reference to the RAV local GPU closeout | `docs/retrospectives/2026-06-04_sean-workstation-rav-local-gpu.md` |

## 2. Ideas, Decisions, Questions Addressed

| Item | Type | Resolution | Rationale | Evidence |
|------|------|------------|-----------|----------|
| Is the model good now? | question | Promising research signal, not diagnostically feasible | AUROC is useful, F1 is moderate, test split is tiny, and Atelectasis threshold collapsed | Conversation metrics and eval outputs |
| What is "good" for this model? | question | Use larger held-out evaluation, per-class sensitivity/specificity, and threshold stability before quality claims | A 24-row local split cannot estimate clinical performance | Conversation discussion |
| Should we try other models now? | decision | Try thresholds first, then controlled ablations | Threshold collapse is cheaper and more directly supported by current evidence | `src/rav_chest/metrics.py` |

## 3. Issues Encountered And Resolved

| Issue | Impact | Resolution | Verification | Prevention / Learning |
|-------|--------|------------|--------------|---------------------|
| Tiny test split makes metrics unstable | Could overfit conclusions to 24 rows | Reclassified local test result as smoke-test only | Conversation line count and metric support counts | Require larger/official held-out test before model-selection claims |
| Default thresholds caused Atelectasis all-positive predictions | Thresholded metrics became operationally poor despite decent AUROC | Added threshold tuning workflow | `scripts/eval_chexpert_5task_policy.py`, `src/rav_chest/metrics.py` | Tune thresholds on validation and freeze before test |
| Tool runner could not finish local threshold sweep reliably | Agent could not produce tuned thresholds directly | Preserved exact commands for user terminal and future session | Closeout note | Use terminal/GCP for longer Torch eval jobs |

## 4. Remaining Ideas, Decisions, Questions

| Item | Type | Priority | Time Horizon | Owner / Next Action | Tracking |
|------|------|----------|--------------|---------------------|----------|
| Run validation threshold sweep | decision | P0 | immediate | `.venv/bin/python scripts/eval_chexpert_5task_policy.py --config configs/primary/chest_chexpert_5task_policy.yaml --split val --checkpoint outputs/chest_baseline_5task_policy/checkpoints/best.pt --tune-thresholds --save-thresholds-file outputs/chest_baseline_5task_policy/metrics/val_tuned_thresholds.json` | Closeout note |
| Evaluate test with frozen validation thresholds | decision | P0 | immediate | `.venv/bin/python scripts/eval_chexpert_5task_policy.py --config configs/primary/chest_chexpert_5task_policy.yaml --split test --checkpoint outputs/chest_baseline_5task_policy/checkpoints/best.pt --thresholds-file outputs/chest_baseline_5task_policy/metrics/val_tuned_thresholds.json` | Closeout note |
| Decide whether to launch the `umixed_regularized_posw` run | decision | P1 | near-term | Launch only if tuned thresholds still show poor class behavior | Closeout note |
| Build a larger evaluation set | idea | P1 | near-term | Use a larger held-out or official CheXpert-style test before claiming model quality | Not tracked elsewhere |

## 5. Remaining Issues

| Issue | Risk | Priority | Time Horizon | Owner / Next Action | Tracking |
|-------|------|----------|--------------|---------------------|----------|
| Current local test split is too small | High metric variance and unstable class support | P0 | immediate | Treat as smoke test only | This retrospective |
| Atelectasis threshold behavior unresolved | Poor specificity at default threshold | P0 | immediate | Tune threshold and inspect confusion matrix | Closeout note |
| No tuned threshold artifact exists yet | Next eval still uses default thresholds unless generated | P0 | immediate | Generate `outputs/chest_baseline_5task_policy/metrics/val_tuned_thresholds.json` | Closeout note |

## 6. Learnings

### Local

- AUROC and F1 can tell different stories; for this run, AUROC suggests ranking signal while F1/confusion reveal a bad operating point.
- Threshold files should be artifacts, not ad hoc config edits, so validation and test remain separated.

### Project

- The RAV evaluation flow needs explicit threshold provenance in metrics JSON.
- Model switching should be a controlled ablation after cheaper calibration/threshold fixes are exhausted.

### Global Candidates

- ML closeouts should separate training stability from model quality; a run can be operationally successful and still not model-ready.

## 7. Strategic Fit

- Task / sprint: Interpret first successful CheXpert 5-task run and define next experiment.
- Epic / initiative: RAV chest X-ray classifier model quality.
- Product / program / engagement: Medical imaging experimentation workflow.
- Repo / project: RAV.
- Global framework: Evidence-based ML iteration closeout.
