---
title: RAV MVP App Operations Learnings
slug: rav-mvp-app-ops
type: learning
status: live
created: 2026-06-04
updated: 2026-06-04
owner: Alex Xin
scope: project
project: rav
tags: [streamlit, llm, mvp, metrics, app-ops]
canonical: true
sources:
  - docs/retrospectives/2026-06-04_rav-chest-first-planning-local-mvp.md
  - docs/retrospectives/2026-06-04_rav-streamlit-llm-mvp-closeout.md
  - docs/retrospectives/2026-06-04_rav-gcp-runner-operations-addendum.md
related:
  - docs/knowledge-base/learnings/2026-05-29_rav-chexpert-ops.md
---

# RAV MVP App Operations Learnings

## Interpreter-Qualified Streamlit Commands

Use `python -m streamlit run app/streamlit_app.py` for local demo work. On this workstation, Conda and `.venv` can both contain Torch/Streamlit packages; invoking the bare `streamlit` executable can load the wrong Torch dylibs even when the `.venv` has a valid install.

## Missing Model Artifacts Are App States

The app should treat a missing `best.pt` as an expected state while training is underway. Show the project-relative checkpoint path, the training/eval commands, and the `last.pt` override option rather than surfacing a raw exception.

## Metrics Need Split And Threshold Provenance

Display AUROC, F1, confusion counts, support, threshold source, and split together. Perfect or near-perfect metrics on POC or tiny splits are smoke-test evidence, not model-quality proof.

## LLM Output Must Stay Grounded

The OpenAI wrapper is useful for report rewriting and report-grounded Q&A, but it must answer only from the inference payload. The model should state missing context instead of inventing findings, treatment, or clinical advice.

## POC And CheXpert Are Different Claims

Kaggle POC proves the app/data/model loop. CheXpert Small and larger CheXpert runs are the model-quality track. Docs, demos, and roadmap checkboxes need to say which dataset a claim applies to.
