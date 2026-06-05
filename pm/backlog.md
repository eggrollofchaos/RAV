# RAV Backlog

Actionable follow-ups surfaced by retrospectives and session closeouts.

## 2026-06-04

- P0 immediate: Run the CheXpert validation threshold sweep in a normal local/GPU runtime, save `val_tuned_thresholds.json`, then evaluate test with frozen thresholds. Source: [Sean Workstation RAV Local GPU Closeout](../docs/retrospectives/2026-06-04_sean-workstation-rav-local-gpu.md).
- P2 later: Run optional full CheXpert file-existence sanity check without `--skip-file-check` if image-path completeness is uncertain. Source: [CheXpert Local Data Prep Closeout](../docs/retrospectives/2026-06-04_chexpert-local-data-prep.md).
- P1 near-term: Train the primary CheXpert baseline with `python scripts/train_chest_baseline.py --config configs/primary/chest_chexpert.yaml`. Source: [RAV Chest-First Planning And Local MVP Closeout](../docs/retrospectives/2026-06-04_rav-chest-first-planning-local-mvp.md).
- P1 near-term: Evaluate the trained CheXpert checkpoint and validate the Streamlit flow with that checkpoint. Source: [RAV Chest-First Planning And Local MVP Closeout](../docs/retrospectives/2026-06-04_rav-chest-first-planning-local-mvp.md).
- P1 near-term: Decide complete dataset placement for Sean workstation before copying full CheXpert-scale data. Source: [Sean Workstation RAV Local GPU Closeout](../docs/retrospectives/2026-06-04_sean-workstation-rav-local-gpu.md).
- P1 near-term: Run Streamlit end-to-end with a real checkpoint, report download, model metrics page, and OpenAI `.env` path before the class demo. Source: [RAV Streamlit, LLM, And MVP Documentation Closeout](../docs/retrospectives/2026-06-04_rav-streamlit-llm-mvp-closeout.md).
- P1 near-term: Verify CheXpert GCS dataset completeness with object counts, size checks, and sample reads before long full-data training. Source: [RAV GCP Runner Operations Addendum](../docs/retrospectives/2026-06-04_rav-gcp-runner-operations-addendum.md).
- P2 later: Keep RAV wrapper docs synchronized when `gcp-spot-runner` changes required profile/wrapper contracts. Source: [RAV GCP Runner Operations Addendum](../docs/retrospectives/2026-06-04_rav-gcp-runner-operations-addendum.md).
