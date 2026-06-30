# RAV Ideas

Speculative or deferred ideas surfaced by retrospectives and session closeouts.

## 2026-06-04

- P2 later: Decide when to use Sean's local GPU versus GCP for RAV runs; local GPU is best for smoke/iteration, while GCP is still useful for data locality, reproducibility, and unattended jobs. Source: [Sean Workstation RAV Local GPU Closeout](../docs/retrospectives/2026-06-04_sean-workstation-rav-local-gpu.md).
- P2 later: Add a localization/tumor-adjacent chest track through VinDr-CXR or similar once primary CheXpert metrics exist. Source: [RAV Chest-First Planning And Local MVP Closeout](../docs/retrospectives/2026-06-04_rav-chest-first-planning-local-mvp.md).
- P2 later: Decide whether the OpenAI wrapper supersedes, complements, or defers the original Gemini 1.5 Flash fine-tuning idea from the slides. Source: [RAV Streamlit, LLM, And MVP Documentation Closeout](../docs/retrospectives/2026-06-04_rav-streamlit-llm-mvp-closeout.md).
- P2 later: Revisit MedAgentBench/MCP integration after deterministic model/eval artifacts are stable. Source: [RAV Streamlit, LLM, And MVP Documentation Closeout](../docs/retrospectives/2026-06-04_rav-streamlit-llm-mvp-closeout.md).
- P2 later: Revisit MedGemma-style qualitative judging after the app can export stable inference and metrics payloads. Source: [RAV Streamlit, LLM, And MVP Documentation Closeout](../docs/retrospectives/2026-06-04_rav-streamlit-llm-mvp-closeout.md).
- P3 someday: Revisit the brain tumor route with BraTS or UPENN-GBM after the chest MVP is demonstrable. Source: [RAV Chest-First Planning And Local MVP Closeout](../docs/retrospectives/2026-06-04_rav-chest-first-planning-local-mvp.md).

## 2026-06-25

- P2 later: Compare imported EVA-X Tiny against the current POC backbone choices once the active CheXpert baseline is stable. Source: [RAV Initiatives](../docs/INITIATIVES.md).
- P2 later: Promote the imported MedGemma judge lane into the active app only if users need local qualitative scoring and the output payload contract is stable. Source: [Chest X-Ray EVA-VLM Reference Pipelines](../reference_pipelines/chest_xray_eva_vlm/README.md).
