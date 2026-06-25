---
title: RAV Coordination And Closeout Learning
slug: rav-coordination-closeout
type: learning
status: live
created: 2026-06-24
updated: 2026-06-24
owner: Alex Xin
scope: project
project: rav
tags: [coord-update, session-closeout, retrospectives, qa, pm]
canonical: false
sources:
  - docs/retrospectives/2026-06-24_coord-update-historical-session-closeout.md
related:
  - docs/coordination/live_repo_summary.md
  - docs/knowledge-base/qa/2026-06-24_rav-ops.md
  - docs/knowledge-base/learnings/2026-05-29_rav-chexpert-ops.md
---

# RAV Coordination And Closeout Learning

## Use Existing Split Retros Before Writing A New Omnibus

The long RAV historical session already had durable split records for
CheXpert GCP/dataset ops, training stability, model evaluation/thresholding,
GCP runner operations, Streamlit/LLM MVP work, local data prep, and Sean
workstation RAV local GPU work. The correct closeout was to audit and link
those records, then add a narrow new retro for the missing coord-update setup.

## Match Coord-Update To Local PM Shape

RAV's backlog is a flat dated bullet list, so the coord-update overlay must use
`backlog_dialect: "flat-list"`. Enabling F1-F5 is useful here: orchestrator
passes can reconcile Q&A/backlog state, pull mode can summarize active PM
items, and agents can tag Q&A proposals. F6 strategy-doc refresh is unnecessary
until RAV has a canonical strategy snapshot surface.

## Keep Shift Notes Local And Current Truth Tracked

Track `docs/coordination/live_repo_summary.md`,
`docs/coordination/repo_summary_history.md`, and
`docs/coordination/shift_coordination_note_template.md`. Keep
`docs/coordination/shift_coordination_note__*.md` ignored. Shift notes are
session buffers; live summary, history, retrospectives, KB, and PM are durable
project truth.
