---
title: RAV Streamlit, LLM, And MVP Documentation Closeout
slug: rav-streamlit-llm-mvp-closeout
type: retrospective
status: live
created: 2026-06-04
updated: 2026-06-04
owner: Alex Xin
scope: project
project: rav
tags: [streamlit, llm, mvp, metrics, documentation]
work-items: []
related:
  - docs/retrospectives/2026-06-04_rav-chest-first-planning-local-mvp.md
  - docs/retrospectives/2026-05-29_chexpert-model-evaluation-thresholding.md
  - docs/knowledge-base/learnings/2026-06-04_rav-mvp-app-ops.md
agent: Codex
agent-provider: OpenAI
agent-interface: Codex Desktop
agent-session-id: 019c9b75-9966-79d3-989b-ce0fd30e3473
session-label: RAV - GCP Updates
invocation-context: session-closeout: closeable
session-lifecycle: closeable
session-closeout-note: .agent-sessions/closed/session-closeout-019c9b75-9966-79d3-989b-ce0fd30e3473.md
---

# RAV Streamlit, LLM, And MVP Documentation Closeout - 2026-06-04

## Metadata

- Unit: RAV Streamlit app, OpenAI wrapper, and MVP documentation track.
- Unit type: initiative.
- Status: complete for current prototype scope; roadmap items remain tracked.
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
- Parent context: EECS E6895 RAV midterm MVP.
- Sources inspected: `app/streamlit_app.py`, `src/rav_chest/llm.py`, `scripts/llm_wrapper.py`, `.env.example`, `.streamlit/config.toml`, `src/rav_chest/version.py`, `README.md`, `docs/CHEST_RUNBOOK.md`, `docs/retrospectives/2026-06-04_rav-chest-first-planning-local-mvp.md`, `docs/retrospectives/2026-05-29_chexpert-model-evaluation-thresholding.md`, `docs/knowledge-base/learnings/2026-05-29_rav-chexpert-ops.md`, current conversation history.

## 1. Work Completed

| What | Why | How | Evidence |
|------|-----|-----|----------|
| Made Streamlit inference more demo-safe | Missing `best.pt` previously surfaced as an unhelpful failure | Added missing-checkpoint handling with expected path, training/eval next steps, and `last.pt` override hint | `app/streamlit_app.py` `render_missing_checkpoint_help()` |
| Added model metrics page | MVP needed model details, metrics, breakdowns, and graphics in the app | Reads metrics JSON, per-class CSV, confusion CSV, and history JSONL; renders summary metrics, tables, and loss curves | `app/streamlit_app.py` `render_model_metrics_page()` |
| Added natural-language agent page | Slides promised natural-language input/output; the app needed a small working prototype | Added OpenAI-grounded Q&A over latest inference payload or uploaded report JSON | `app/streamlit_app.py` `render_ask_agent_page()`; `src/rav_chest/llm.py` |
| Added OpenAI wrapper and `.env` loading | User wanted a simple wrapper and automatic API-key pickup | Implemented `resolve_openai_api_key()` with env plus project `.env`, CLI prompt/report rewrite modes, and `.env.example` | `src/rav_chest/llm.py`; `scripts/llm_wrapper.py`; `.env.example` |
| Cleaned Streamlit UX details | App needed to look like a project artifact rather than a raw script | Added version import, app title/sidebar, class project text, author R/A/V emphasis, copyright, dark blue theme, port `8503`, relative config paths, and smaller warning display | `app/streamlit_app.py`; `.streamlit/config.toml`; `src/rav_chest/version.py` |
| Preserved MVP roadmap reality | Project scope changed as Kaggle POC and CheXpert diverged | Updated docs to separate POC-vs-CheXpert status, note CheXpert Small from Kaggle, defer CheXpert Plus, and keep Gemini/MedAgentBench/MedGemma items as roadmap rather than shipped claims | `README.md`; `docs/CHEST_RUNBOOK.md`; current conversation history |

## 2. Ideas, Decisions, Questions Addressed

| Item | Type | Resolution | Rationale | Evidence |
|------|------|------------|-----------|----------|
| Should Streamlit use the shell `streamlit` executable? | decision | Prefer `python -m streamlit run app/streamlit_app.py` | It keeps Streamlit inside the active `.venv` and avoids Conda Torch linker mismatches | `README.md`; `docs/CHEST_RUNBOOK.md` |
| Should `.env` need manual sourcing? | decision | No; RAV code reads `.env` directly for `OPENAI_API_KEY` | Simple prototype UX beats shell-state dependence, while `.env.example` documents the contract | `src/rav_chest/llm.py`; `.env.example` |
| Are perfect AUROC/F1 metrics trustworthy? | question | Not by themselves, especially on tiny or validation-only splits | POC or small-split metrics can be smoke-test evidence while still being unrealistic as generalization evidence | `docs/retrospectives/2026-05-29_chexpert-model-evaluation-thresholding.md`; current conversation history |
| Is the LLM path clinical decision support? | decision | No; it is a research-prototype writing/Q&A layer grounded only in model output context | The system prompt forbids treatment advice and requires missing context to be named directly | `src/rav_chest/llm.py` |

## 3. Issues Encountered And Resolved

| Issue | Impact | Resolution | Verification | Prevention / Learning |
|-------|--------|------------|--------------|---------------------|
| Conda Torch loaded when running Streamlit | Streamlit could fail with unresolved Torch dylib symbols despite `.venv` Torch being installed | Use `.venv` Python module invocation instead of whichever `streamlit` appears first on `PATH` | User-confirmed `.venv` MPS availability; docs now show `python -m streamlit` | Prefer interpreter-qualified app commands in mixed Conda/venv setups |
| `use_container_width` deprecation | Future Streamlit compatibility warning cluttered the app | Migrated calls to `width="stretch"` | `app/streamlit_app.py` uses `width="stretch"` | Treat UI deprecation warnings as cheap cleanup before demos |
| Missing checkpoint looked like a model/app failure | User could not tell whether training was required or path was wrong | Added direct expected checkpoint display and concrete commands | `app/streamlit_app.py` | Missing model artifacts should be first-class app states |
| Config path was hard to read | Absolute paths forced horizontal scrolling | Displayed project-relative paths when possible | `to_project_relative()` in `app/streamlit_app.py` | Operator paths should be short enough for app panels |

## 4. Remaining Ideas, Decisions, Questions

| Item | Type | Priority | Time Horizon | Owner / Next Action | Tracking |
|------|------|----------|--------------|---------------------|----------|
| Gemini fine-tuning path from slides | idea | P2 | later | Decide whether to keep Gemini 1.5 Flash in scope now that OpenAI wrapper exists | `pm/ideas.md` |
| MCP/MedAgentBench evaluation | idea | P2 | later | Keep as roadmap until model/eval pipeline is stable | `pm/ideas.md` |
| MedGemma qualitative scoring | idea | P2 | later | Evaluate after deterministic metrics and threshold provenance are stable | `pm/ideas.md` |
| Streamlit demo smoke test with real checkpoint and OpenAI key | question | P1 | near-term | Run app end to end before class demo | `pm/backlog.md` |

## 5. Remaining Issues

| Issue | Risk | Priority | Time Horizon | Owner / Next Action | Tracking |
|-------|------|----------|--------------|---------------------|----------|
| CheXpert has no public official test split in this workflow | Validation can become model-selection evidence but not final blind test evidence | P1 | near-term | Keep reporting split provenance and use larger held-out evaluation | `pm/issues.md` |
| LLM output can sound more authoritative than the model supports | Prototype could imply clinical confidence beyond data quality | P1 | near-term | Keep research-only text and context-grounding guardrails visible | `pm/issues.md` |

## 6. Learnings

### Local

- In a class-project MVP, a graceful missing-checkpoint state is more valuable than a stack trace.
- `python -m streamlit` is the safest command when Conda and `.venv` both exist on the same Mac.
- AUROC, F1, confusion matrices, and support counts need to be shown together; a perfect headline metric can be misleading on small splits.

### Project

- Keep Kaggle POC, CheXpert Small, CheXpert Full, and CheXpert Plus distinct in every roadmap/doc reference.
- LLM wrapper output should remain tied to saved inference payloads so provenance survives demos and report downloads.

### Global Candidates

- Research-prototype medical apps need explicit missing-artifact UX, split provenance, and LLM guardrails before adding fancier model backbones.

## 7. Strategic Fit

- Task / sprint: MVP app readiness and project documentation.
- Epic / initiative: RAV radiology AI agent prototype.
- Product / program / engagement: EECS E6895 Spring 2026 midterm project.
- Repo / project: RAV.
- Global framework: class-project AI prototype discipline.
