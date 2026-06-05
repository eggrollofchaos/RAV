---
title: RAV Data Management Decisions
slug: data-management
type: decision
status: live
created: 2026-06-04
updated: 2026-06-04
owner: Alex Xin
scope: project
project: rav
tags: [data-management, chest-first, chexpert, kaggle-poc, radiology-ai]
canonical: false
sources:
  - docs/retrospectives/2026-06-04_rav-chest-first-planning-local-mvp.md
  - docs/retrospectives/2026-06-04_chexpert-local-data-prep.md
related:
  - docs/knowledge-base/learnings/2026-05-29_rav-chexpert-ops.md
metadata:
  high_water_mark: 2
---

# RAV Data Management Decisions

## [DEC-DAT-001] Use Chest-First CheXpert Route For The Course MVP

- Date: 2026-06-04
- Status: accepted
- Scope: project
- Sources: `docs/retrospectives/2026-06-04_rav-chest-first-planning-local-mvp.md`

### Context

The project considered a brain scan route, including tumor-specific MRI/CT data, and a chest X-ray route. Brain tumor work has stronger tumor-specific depth but higher coding lift: volumetric data handling, segmentation/evaluation complexity, higher compute, and more moving parts for a course MVP.

### Decision

Use the chest X-ray route for the MVP, with CheXpert-style multi-label classification as the primary baseline. Keep brain tumor work as a future track after the chest pipeline, UI, and evaluation loop are demonstrable.

### Rationale

Chest X-ray data and 2D model pipelines reduce external blockers, support faster local iteration, and pair better with a grounded report-generation demo. Tumor-adjacent chest labels remain possible later through datasets such as VinDr-CXR, but they are not required for the first MVP.

### Consequences

- The first deliverable optimizes for feasibility, reproducibility, and demo quality.
- Brain tumor segmentation/reporting remains deferred rather than rejected.
- Early model claims must stay scoped to chest X-ray findings, not general radiology diagnosis.

## [DEC-DAT-002] Keep Kaggle Pneumonia As POC And CheXpert-Small As Local Primary Data

- Date: 2026-06-04
- Status: accepted
- Scope: project
- Sources: `docs/retrospectives/2026-06-04_rav-chest-first-planning-local-mvp.md`, `docs/retrospectives/2026-06-04_chexpert-local-data-prep.md`

### Context

The team initially had a Kaggle chest pneumonia dataset proposal. CheXpert offers a better primary target because it supports multi-label thoracic findings and a more realistic radiology taxonomy, but full CheXpert is too large for comfortable local MacBook storage.

### Decision

Use Kaggle chest-xray-pneumonia only as the first-iteration POC path. Use CheXpert-small under `data/raw/chexpert/CheXpert-v1.0-small` as the local primary data path. Reserve full CheXpert for GCP or external-storage workflows.

### Rationale

The POC dataset is fast and useful for validating code. CheXpert-small keeps the primary label taxonomy available locally without the full dataset's storage burden. Full-data work belongs in the cloud path already captured by the GCP CheXpert retrospectives.

### Consequences

- POC scripts, data, and outputs must stay clearly marked under `poc` paths.
- Local primary training can start without reattempting a roughly 471 GB full download.
- Metrics from the tiny CheXpert-small valid-derived test split are smoke-test evidence only.
