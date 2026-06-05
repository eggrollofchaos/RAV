# RAV Issues

Open risks surfaced by retrospectives and session closeouts.

## 2026-06-04

- P0 immediate: Current local CheXpert test split remains smoke-only; use larger held-out evaluation before diagnostic claims. Source: [Sean Workstation RAV Local GPU Closeout](../docs/retrospectives/2026-06-04_sean-workstation-rav-local-gpu.md).
- P1 near-term: CheXpert-small's valid-derived local test split is 24 rows at the current `0.1` test fraction, so primary-track metrics need a larger evaluation set before quality claims. Source: [CheXpert Local Data Prep Closeout](../docs/retrospectives/2026-06-04_chexpert-local-data-prep.md).
- P1 near-term: Sean workstation free disk is not yet confirmed sufficient for full CheXpert-scale copies. Source: [Sean Workstation RAV Local GPU Closeout](../docs/retrospectives/2026-06-04_sean-workstation-rav-local-gpu.md).
- P1 near-term: CheXpert has no public official test split in this workflow; validation/test metrics must state split provenance and avoid clinical-quality claims. Source: [RAV Streamlit, LLM, And MVP Documentation Closeout](../docs/retrospectives/2026-06-04_rav-streamlit-llm-mvp-closeout.md).
- P1 near-term: LLM output can sound more authoritative than the underlying model/data support; keep research-only UI language and context-grounded prompts. Source: [RAV Streamlit, LLM, And MVP Documentation Closeout](../docs/retrospectives/2026-06-04_rav-streamlit-llm-mvp-closeout.md).
- P1 near-term: Long CheXpert GCP runs still depend on cloud quota, image freshness, dataset freshness, and GPU startup health; run preflight checks before expensive submits. Source: [RAV GCP Runner Operations Addendum](../docs/retrospectives/2026-06-04_rav-gcp-runner-operations-addendum.md).
- P2 later: Full CheXpert should not be downloaded to the internal laptop disk without an external storage or cloud plan. Source: [CheXpert Local Data Prep Closeout](../docs/retrospectives/2026-06-04_chexpert-local-data-prep.md).
