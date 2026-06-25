# Chest X-Ray EVA-VLM Reference Pipelines

This directory preserves reusable code and design notes from the older chest X-ray prototype, stripped of class, teammate, notebook, PDF, screenshot, checkpoint, and personal-history artifacts.

Use this as a reference lane, not as the default RAV runtime. The active RAV path remains `src/rav_chest/`, `configs/`, `scripts/train_chest_baseline.py`, and `app/streamlit_app.py`.

## Imported Lanes

| Lane | Files | Use When | Status |
|---|---|---|---|
| EVA-X binary POC | `rav_reference/eva_x.py`, `rav_reference/models.py`, `rav_reference/training.py`, `scripts/train.py`, `scripts/diagnose.py` | Revisit the Kaggle pneumonia binary classifier or compare EVA-X Tiny against the current DenseNet/ResNet/EfficientNet baselines. | Reference-only; requires `timm` and an EVA-X MIM checkpoint for training. |
| Local VLM reasoning | `rav_reference/llm.py` | Re-add local Llama or CheXagent reasoning after stable classifier artifacts exist. | Optional GPU lane; dependencies are intentionally separate. |
| MedGemma judge / QA evaluation | `rav_reference/evaluation.py`, `rav_reference/qa_evaluator.py`, `scripts/download_test_images.py`, `scripts/generate_test_json.py`, `scripts/evaluate_radiology_assistant.py` | Evaluate generated report/Q&A answers with a local judge and text metrics. | Optional evaluation lane; needs Hugging Face access, Kaggle credentials for sample downloads, and GPU memory for local judging. |

## What Was Excluded

- Notebooks, PDFs, screenshots, and the trained checkpoint.
- Course/team/person-identifying prose.
- Broad final-report claims that need stronger evidence before they belong in RAV docs.
- Colab/Drive paths and runtime assumptions.

## Useful Imported Decisions

1. Keep backend dependencies lazy. Core classifier imports should not require local VLM or judge packages.
2. Treat threshold and confidence-tier policy as runtime state, not cached model state.
3. Keep checkpoint construction, inference restore, and training resume as separate code paths.
4. Use a judge lane only against exported, provenance-bearing inference payloads.

## Verification

The reference code should at least compile:

```bash
python -m compileall reference_pipelines/chest_xray_eva_vlm
```

The full smoke test expects a local `eva_x_tiny_binary_best.pt` checkpoint and optional model dependencies, so it is not part of default RAV verification.

Optional dependency files:

- `requirements-core.txt` for the EVA-X reference lane.
- `requirements-llama.txt` for local Llama reasoning.
- `requirements-chexagent.txt` for CheXagent reasoning.
- `requirements-judge.txt` for MedGemma/QA evaluation helpers.
