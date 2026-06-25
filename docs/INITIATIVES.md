# RAV Initiatives

Status date: 2026-06-25

This is the cleanup inventory for active, completed, and deferred RAV work. Percentages are planning estimates, not model-quality claims. The raw README checklist is 38/62 complete (~61%), but several unchecked items are intentionally deferred rather than required for the current MVP.

## Initiative Snapshot

| Initiative | Current State | Progress | Remaining Work |
|---|---|---:|---|
| POC chest pneumonia baseline | Kaggle binary POC has training/eval/inference/UI flow and grounded report output. | 95% | Maintenance only: keep commands current and avoid treating POC metrics as CheXpert evidence. |
| Core RAV chest pipeline | `src/rav_chest/`, train/eval/infer scripts, metrics, reporting, and Streamlit pages exist. | 85% | Add lightweight schema/import checks, keep docs synced with exact config/output paths, and harden artifact provenance. |
| Primary CheXpert baseline | CheXpert-small prep exists; primary training and held-out evaluation artifacts remain pending. | 45% | Run primary training, save `best.pt`, evaluate with split/threshold provenance, and verify Streamlit metrics page against primary artifacts. |
| CheXpert 5-task / model-quality variants | Policy training/eval scripts and configs exist; threshold tuning remains the next quality gate. | 50% | Produce `val_tuned_thresholds.json`, freeze thresholds for test eval, then decide whether `umixed_regularized_posw` or EfficientNet deserves a full run. |
| GCP training and runner adapter | Wrapper/operator docs, state helpers, GCP submit/build/ops paths, and Bats adapter tests exist. | 75% | Verify GCS dataset completeness before long runs, rebuild images when code/config changes, and keep runner contract docs in sync with `gcp-spot-runner`. |
| Streamlit and grounded LLM UX | POC UI works; OpenAI rewrite/Q&A path is present and context-grounded. | 80% | Validate with primary CheXpert artifacts, keep missing-checkpoint UX current, and decide if local VLM backends are worth activating. |
| Imported EVA-X binary lane | Sanitized reference pipeline copied from the older chest X-ray prototype under `reference_pipelines/chest_xray_eva_vlm/`. | 35% | Treat as comparison/reference until `timm`, EVA-X MIM weights, checkpoint provenance, and a config bridge are intentionally added. |
| Imported local VLM reasoning lane | Llama and CheXagent backend code copied as optional reference code. | 25% | Keep optional and GPU-gated; activate only after stable classifier artifacts and dependency budget exist. |
| Imported MedGemma judge / QA evaluation lane | Judge and QA evaluator code copied as optional reference code. | 25% | Run only against exported, provenance-bearing report payloads; add small sample-set fixtures before using scores in docs. |
| Localization / tumor-adjacent chest lane | Config placeholder exists; VinDr-CXR/nodule/mass work remains deferred. | 10% | Start after primary CheXpert metrics are credible; define labels, localization metrics, and data access first. |
| Brain tumor route | Explicitly deferred by data-management decision. | 0% active | Revisit after chest MVP is demonstrable; likely needs separate 3D/segmentation architecture. |
| Documentation and PM governance | Docs, retrospectives, KB, and PM surfaces exist, but status was scattered. | 70% | Keep this file, README, `docs/INDEX.md`, PM surfaces, CHANGELOG, and taxonomy aligned when lanes move. |

## Near-Term Order

1. Primary CheXpert baseline: train, evaluate, and verify app metrics with `outputs/chest_baseline/`.
2. Threshold/model-quality pass: tune validation thresholds before switching backbones.
3. GCP long-run preflight: object counts, sample reads, image freshness, accelerator health.
4. Optional imported-lane activation: choose one, preferably EVA-X comparison first; local VLM/judge lanes wait for stable report payloads.
5. Deferred tracks: localization and brain/tumor routes stay parked until the primary chest pipeline has credible metrics.

## Imported Lane Boundaries

The older prototype imported here had useful code but also classroom deliverables, personal/team prose, notebooks, screenshots, checkpoints, and final-report claims. This cleanup keeps only reusable code and design notes. It does not import:

- notebooks, PDFs, screenshots, videos, or checkpoints;
- course/team/person-identifying prose;
- Colab or Google Drive paths;
- broad external-generalization claims without reproducible evidence.

Canonical imported reference path:

- `reference_pipelines/chest_xray_eva_vlm/README.md`

## Source Surfaces Used

- `README.md`
- `docs/CHEST_RUNBOOK.md`
- `docs/HARDWARE_SIZING.md`
- `docs/knowledge-base/decisions/data-management.md`
- `docs/knowledge-base/learnings/2026-05-29_rav-chexpert-ops.md`
- `docs/knowledge-base/learnings/2026-06-04_rav-mvp-app-ops.md`
- `docs/retrospectives/`
- `pm/backlog.md`
- `pm/issues.md`
- `pm/ideas.md`
- `pm/done.md`
