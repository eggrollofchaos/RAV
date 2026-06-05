---
title: CheXpert Training Stability Closeout
slug: chexpert-training-stability
type: retrospective
status: live
created: 2026-05-29
updated: 2026-05-29
owner: Alex Xin
scope: project
project: rav
tags: [chexpert, training, gcp, spot, checkpointing, stability]
work-items: []
related:
  - docs/knowledge-base/learnings/2026-05-29_rav-chexpert-ops.md
  - docs/retrospectives/2026-05-29_chexpert-remote-training-evaluation.md
agent: Codex
agent-provider: OpenAI
agent-interface: Codex Desktop
agent-session-id: 019db9e1-7c41-7f81-b0f8-a353bbed6f1c
session-label: RAV - Models - Idle
invocation-context: session-closeout: closeable
session-lifecycle: closeable
session-closeout-note: .agent-sessions/closed/session-closeout-019db9e1-7c41-7f81-b0f8-a353bbed6f1c.md
---

# CheXpert Training Stability Closeout - 2026-05-29

## Metadata

- Unit: CheXpert Small remote training stability
- Unit type: initiative
- Status: complete for current session
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
- Sources inspected: `scripts/train_chexpert_5task_policy.py`, `scripts/gcp_train_with_checkpoint_sync.sh`, `scripts/gcp_submit_chexpert_experiment.sh`, `gcp/GCP_NOTES.md`, `gcp/GETTING_STARTED.md`, conversation run logs

## 1. Work Completed

| What | Why | How | Evidence |
|------|-----|-----|----------|
| Investigated whether earlier CheXpert Small runs ended from preemption | Needed root cause before changing runner behavior | Checked VM status, serial logs, metadata/run manifests, and exit codes | Conversation record and `gcp/GCP_NOTES.md` |
| Identified non-preemption runtime failures | Avoid chasing spot capacity when the container/runtime was failing | Differentiated exit code failures from cloud preemptions | `gcp/GCP_NOTES.md`, run-log discussion |
| Fixed/validated shared memory and restart behavior | DataLoader/runtime failures blocked long training | Preserved the `--shm-size=2g` fix and retried with persistent checkpoint sync | `gcp/GCP_NOTES.md`, successful run notes |
| Fixed stage-2 pseudo-label device mismatch | Training crashed when indexing pseudo-label tensors across devices | Moved gather indices to the pseudo-label tensor device before indexing | `scripts/train_chexpert_5task_policy.py`, successful follow-up run |
| Confirmed one clean 5-task run completed | Needed proof that GCE VM training can finish end to end | Relaunched corrected image and monitored logs through early stopping | Conversation record: `rav-chexpert-5task-fix-20260304-192759` exited `0` |

## 2. Ideas, Decisions, Questions Addressed

| Item | Type | Resolution | Rationale | Evidence |
|------|------|------------|-----------|----------|
| Was the failed run preempted? | question | No, the relevant failure was runtime/container-side | Run state and logs did not match a preemption-only failure | Conversation record |
| Is the current training loop viable remotely? | question | Yes for CheXpert Small 5-task baseline | The corrected run completed and checkpoint sync preserved metrics/checkpoints | `scripts/gcp_train_with_checkpoint_sync.sh`, conversation record |
| Should each submit create fresh state? | decision | Use explicit run IDs and persistent data disk behavior deliberately | Fresh run IDs are useful for experiments, but same run ID matters for resume semantics | `gcp/GETTING_STARTED.md` |

## 3. Issues Encountered And Resolved

| Issue | Impact | Resolution | Verification | Prevention / Learning |
|-------|--------|------------|--------------|---------------------|
| DataLoader shared memory exhaustion | Training could crash under container defaults | Used larger shared memory for container execution | Later run completed cleanly | Keep container runtime settings documented next to training wrappers |
| One-shot restart bug after immediate preemption/failure | Runner did not always retry as expected | Documented root cause and fixed restart loop behavior in runner-adjacent work | `gcp/GCP_NOTES.md` | Distinguish retry policy from workload exit handling |
| Stage-2 pseudo-label indexing device mismatch | 5-task training failed after entering self-trained stage | Moved indices to pseudo-label tensor device before indexing | Corrected run passed stage 2 and completed | Tensor indices must live on the indexed tensor's device |

## 4. Remaining Ideas, Decisions, Questions

| Item | Type | Priority | Time Horizon | Owner / Next Action | Tracking |
|------|------|----------|--------------|---------------------|----------|
| Keep run IDs deterministic for resumed experiments | decision | P1 | near-term | Use named run IDs for continuing the same experiment | Session closeout note |
| Decide whether to automate post-run eval on both `val` and `test` | idea | P2 | later | Consider wrapper support after threshold workflow stabilizes | Not tracked elsewhere |

## 5. Remaining Issues

| Issue | Risk | Priority | Time Horizon | Owner / Next Action | Tracking |
|-------|------|----------|--------------|---------------------|----------|
| Tool-runner local Torch execution can stall | Agent-run local sweeps may not finish despite normal terminal success | P2 | near-term | Use user's terminal or GCP for longer Torch jobs | This retrospective |

## 6. Learnings

### Local

- The remote training path is now viable enough for controlled experiments.
- Preemption analysis should start with exact exit codes and serial logs, not with the presence of spot VMs alone.

### Project

- Checkpoint sync should remain default for every cloud training path.
- Runtime fixes need to be captured in operator docs because they are easy to lose between image rebuilds.

### Global Candidates

- ML spot-runner closeouts should preserve run IDs, image freshness assumptions, and exact metric artifact paths.

## 7. Strategic Fit

- Task / sprint: Prove CheXpert Small can train remotely without crashing.
- Epic / initiative: RAV chest X-ray classifier cloud training.
- Product / program / engagement: Medical imaging experimentation workflow.
- Repo / project: RAV.
- Global framework: Reliable spot GPU training with resumable checkpoints.
