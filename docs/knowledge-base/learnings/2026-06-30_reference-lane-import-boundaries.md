---
title: Reference Lane Import Boundaries
slug: reference-lane-import-boundaries
type: learning
status: live
created: 2026-06-30
updated: 2026-06-30
owner: Alex Xin
scope: project
project: rav
tags: [reference-pipelines, provenance, class-projects, cleanup, documentation]
canonical: false
sources:
  - docs/retrospectives/2026-06-30_rav-cleanup-reference-lanes-closeout.md
  - docs/INITIATIVES.md
  - reference_pipelines/chest_xray_eva_vlm/README.md
related:
  - docs/knowledge-base/learnings/2026-06-24_rav-coordination-closeout.md
  - docs/knowledge-base/learnings/2026-06-04_rav-mvp-app-ops.md
---

# Reference Lane Import Boundaries

## Pattern

When an older prototype has useful code but mixed provenance, import it as a
separate reference lane first. Do not wire it into active runtime paths until
the dependency, checkpoint, data, and evaluation contracts are explicit.

## RAV Application

The chest X-ray prototype contributed reusable EVA-X, local VLM, and MedGemma/QA
code. The cleanup kept those pieces under
`reference_pipelines/chest_xray_eva_vlm/` and left the active RAV runtime
untouched.

The import deliberately excluded notebooks, PDFs, screenshots, videos,
checkpoints, course/team/person-identifying prose, Colab/Drive paths, and broad
external-generalization claims without reproducible evidence.

## Reuse Checklist

- Name the lane as reference or experimental in path and README.
- Keep optional heavyweight dependencies in separate requirements files.
- Preserve runnable smoke/help checks that do not need private checkpoints.
- Scan for source-project, class, personal, and cloud-notebook strings before
  merging.
- Track activation as follow-up work, not as an implied shipped capability.

## Promotion Notes

This overlaps with the Classes KB's submission-artifact provenance and public
project story lessons, so no parent Classes KB duplicate was created. The
project-specific RAV rule is narrower: quarantine useful prototype code until it
earns active-runtime status.
