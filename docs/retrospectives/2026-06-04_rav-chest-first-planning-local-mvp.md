---
title: RAV Chest-First Planning And Local MVP Closeout
slug: rav-chest-first-planning-local-mvp
type: retrospective
status: live
created: 2026-06-04
updated: 2026-06-04
owner: Alex Xin
scope: project
project: rav
tags: [planning, chest-first, chexpert, kaggle-poc, streamlit, radiology-ai]
work-items: []
related:
  - docs/retrospectives/2026-06-04_chexpert-local-data-prep.md
  - docs/retrospectives/2026-06-04_rav-streamlit-llm-mvp-closeout.md
  - docs/knowledge-base/decisions/data-management.md
  - docs/knowledge-base/learnings/2026-05-29_rav-chexpert-ops.md
agent: Codex
agent-provider: OpenAI
agent-interface: Codex Desktop
agent-session-id: 019c9aae-7002-7a40-9e22-75f7b632f021
session-label: Project planning
invocation-context: session-closeout: closeable
session-lifecycle: closeable
session-closeout-note: .agent-sessions/closed/session-closeout-019c9aae-7002-7a40-9e22-75f7b632f021.md
---

# RAV Chest-First Planning And Local MVP Closeout - 2026-06-04

## Metadata

- Unit: RAV chest-first planning and local MVP scaffold
- Unit type: initiative
- Status: complete for this session
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
- Parent context: RAV agentic AI for radiology course project
- Sources inspected: `README.md`, `PDF/EECS E6895 - Initial Proposal - Radiologist - RAV.pdf`, `PDF/EECS E6895 - Project Plan - Radiologist - RAV - Archive.pdf`, `docs/CHEST_RUNBOOK.md`, `docs/HARDWARE_SIZING.md`, `app/streamlit_app.py`, `src/rav_chest/pipeline.py`, `configs/primary/chest_chexpert.yaml`, `configs/poc/chest_pneumonia_binary.yaml`, `scripts/prepare_chexpert_data.py`, `scripts/poc/prepare_chest_pneumonia_data.py`, `scripts/train_chest_baseline.py`, `scripts/eval_chest_baseline.py`, `scripts/infer_chest_single.py`, `docs/retrospectives/2026-05-29_chexpert-gcp-dataset-ops.md`, `docs/knowledge-base/learnings/2026-05-29_rav-chexpert-ops.md`

## 1. Work Completed

| What | Why | How | Evidence |
|------|-----|-----|----------|
| Reviewed project proposal context and alternative reference slides | Preserve professor-approved scope while turning it into an executable plan | Used the official proposal PDFs as the durable project brief and the alternate Google Slides as reference context from the session | `PDF/EECS E6895 - Initial Proposal - Radiologist - RAV.pdf`, `PDF/EECS E6895 - Project Plan - Radiologist - RAV - Archive.pdf`, conversation record |
| Compared brain scan and chest X-ray routes, including tumor-specific concerns | Choose a feasible MVP while honoring the user's interest in tumors | Evaluated data availability, model ecosystem, coding lift, and external blockers; kept brain tumor work as a future track | `README.md` sections 3, 9, and 10 |
| Locked a chest-first direction | Reduce timeline risk for the course project | Selected chest X-ray as primary, with CheXpert primary data and Kaggle pneumonia as first POC | `README.md`, `docs/CHEST_RUNBOOK.md`, `docs/knowledge-base/decisions/data-management.md` |
| Built the local classification pipeline scaffold | Create an end-to-end baseline before experimenting with VLMs | Added data loading, model factory, metrics/reporting, train/eval/inference scripts, and primary/POC configs | `src/rav_chest/`, `scripts/train_chest_baseline.py`, `scripts/eval_chest_baseline.py`, `scripts/infer_chest_single.py`, `configs/primary/chest_chexpert.yaml`, `configs/poc/chest_pneumonia_binary.yaml` |
| Separated POC Kaggle pneumonia artifacts from primary CheXpert | Keep demo/first-iteration code from confusing the primary track | Moved POC prep under `scripts/poc/`, routed POC data/config/output paths under `data/poc/` and `outputs/poc/` | `scripts/poc/prepare_chest_pneumonia_data.py`, `configs/poc/chest_pneumonia_binary.yaml`, `docs/CHEST_RUNBOOK.md` |
| Added Streamlit UI path | Let the team build and demo while datasets or training runs are still in progress | Created upload/inference, metrics, report display, optional LLM rewrite, and grounded Q&A surfaces | `app/streamlit_app.py`, `src/rav_chest/pipeline.py`, `src/rav_chest/llm.py`, `scripts/llm_wrapper.py` |
| Documented local setup and run commands | Make the project reproducible for teammates | Added chest runbook, hardware sizing, README plan, requirements, and `.gitignore` coverage for envs, outputs, and data | `README.md`, `docs/CHEST_RUNBOOK.md`, `docs/HARDWARE_SIZING.md`, `.gitignore`, `requirements.txt` |

## 2. Ideas, Decisions, Questions Addressed

| Item | Type | Resolution | Rationale | Evidence |
|------|------|------------|-----------|----------|
| Brain scans or chest X-rays first? | decision | Chest X-ray first; brain tumor route deferred | Chest X-ray has lower coding lift, stronger available baselines, simpler 2D data, and fewer timeline blockers | `README.md`, `docs/knowledge-base/decisions/data-management.md` |
| How to include tumors? | question | Keep tumor-adjacent chest labels as optional future localization/data work; defer deep tumor work to brain route | Chest X-ray can cover nodule/mass/lung tumor in some datasets, but brain MRI tumor segmentation is the richer tumor-specific path | `README.md` sections 4, 5, 9 |
| CheXpert or Kaggle pneumonia? | decision | CheXpert is primary; Kaggle pneumonia is POC | CheXpert supports multi-label thoracic findings, while the Kaggle set is useful for a fast binary proof of concept | `configs/primary/chest_chexpert.yaml`, `configs/poc/chest_pneumonia_binary.yaml`, `docs/CHEST_RUNBOOK.md` |
| Python venv or Conda? | decision | Use `.venv` for this project unless a dependency later requires Conda | The current PyTorch/Streamlit stack works with project-local venv and keeps activation/runtime simple | `docs/CHEST_RUNBOOK.md`, `.gitignore` |
| Free-form report generation or constrained output? | decision | Use structured findings and template reports first; optional LLM rewrite must stay grounded | Reduces hallucination risk and keeps model outputs auditable | `src/rav_chest/reporting.py`, `src/rav_chest/llm.py`, `app/streamlit_app.py` |

## 3. Issues Encountered And Resolved

| Issue | Impact | Resolution | Verification | Prevention / Learning |
|-------|--------|------------|--------------|---------------------|
| `FileNotFoundError` for `data/processed/chexpert_train.csv` | Training could not start before processed CSVs existed | Added/used CheXpert prep flow and documented run order | `scripts/prepare_chexpert_data.py`, `docs/CHEST_RUNBOOK.md` |
| POC and primary data paths risked blending together | Hard to know whether code was demo-only or primary-track | Clearly marked POC scripts/config/data/output paths | `scripts/poc/prepare_chest_pneumonia_data.py`, `configs/poc/chest_pneumonia_binary.yaml`, `docs/CHEST_RUNBOOK.md` |
| Full CheXpert download was too large for the laptop disk | Could consume most of the internal drive and slow work | Switched local active work to CheXpert-small; full CheXpert remains cloud/external-storage work | `docs/retrospectives/2026-06-04_chexpert-local-data-prep.md` |
| CheXpert prep appeared to be taking too long | Could mask a wrong root, stale process, or unexpectedly huge data path | Re-ran prep locally against CheXpert-small; it completed successfully in about 5.3 seconds | Closeout timing run; `data/processed/chexpert_*.csv` |

## 4. Remaining Ideas, Decisions, Questions

| Item | Type | Priority | Time Horizon | Owner / Next Action | Tracking |
|------|------|----------|--------------|---------------------|----------|
| Train the primary CheXpert baseline locally | decision | P1 | near-term | Run `python scripts/train_chest_baseline.py --config configs/primary/chest_chexpert.yaml` from `.venv` | `pm/backlog.md` |
| Validate Streamlit with a trained CheXpert checkpoint | question | P1 | near-term | After training, run eval and open `python -m streamlit run app/streamlit_app.py` | `pm/backlog.md` |
| Add localization/tumor-adjacent dataset path | idea | P2 | later | Revisit VinDr-CXR or similar after baseline metrics exist | `pm/ideas.md` |
| Revisit brain tumor route | idea | P3 | someday | Consider BraTS/UPENN-GBM after the chest MVP is demonstrable | `pm/ideas.md` |

## 5. Remaining Issues

| Issue | Risk | Priority | Time Horizon | Owner / Next Action | Tracking |
|-------|------|----------|--------------|---------------------|----------|
| CheXpert-small valid-derived test split is tiny | Metrics can be useful for smoke tests but not strong model-quality claims | P1 | near-term | Treat early metrics as operational validation, then evaluate on a larger/official held-out split | `pm/issues.md` |
| Full CheXpert cannot reasonably live on the internal laptop disk | Repeating the full Azure download locally can exhaust disk space | P2 | later | Use CheXpert-small locally; use GCP/external disk for full-data runs | `pm/issues.md` |

## 6. Learnings

### Local

- A chest-first plan gives this course project a real demo path without sacrificing a future brain/tumor track.
- POC artifacts need loud directory boundaries; otherwise demo success can be mistaken for primary-model readiness.
- Streamlit is useful before the model is fully trained because it validates payload shape, report grounding, and presentation flow.

### Project

- Dataset strategy should name the variant every time: Kaggle pneumonia POC, CheXpert-small, full CheXpert, and CheXpert Plus are operationally different things.
- Report generation should remain constrained to structured findings until calibration and label quality are stronger.

### Global Candidates

- For course ML apps, build the UI/reporting harness early when long dataset and training loops are expected; it keeps demo work unblocked.
- When a project has a quick POC dataset and a serious primary dataset, encode that separation in paths, config names, run IDs, and docs.

## 7. Strategic Fit

- Task / sprint: Turn proposal materials into an executable local MVP.
- Epic / initiative: RAV chest X-ray classifier and grounded report prototype.
- Product / program / engagement: Agentic AI for radiology course project.
- Repo / project: RAV.
- Global framework: Evidence-first ML project scaffolding with durable closeouts.
