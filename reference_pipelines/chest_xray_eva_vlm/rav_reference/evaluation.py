"""MedGemma-based evaluation judge for radiology assistant responses."""

from __future__ import annotations

import json
from typing import Any

DEFAULT_JUDGE_MODEL = "google/medgemma-1.5-4b-it"


def load_medgemma_judge(model_id: str = DEFAULT_JUDGE_MODEL):
    """Load the MedGemma judge model with 4-bit quantization."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    tokenizer = AutoTokenizer.from_pretrained(model_id)
    quant_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=quant_config,
        device_map="auto",
    )
    model.eval()
    return model, tokenizer


def evaluate_response(
    model,
    tokenizer,
    question: str,
    answer: str,
    context: str,
    ground_truth: str = "Verify clinical accuracy.",
    max_new_tokens: int = 300,
) -> dict[str, Any]:
    """Score a radiology assistant response using MedGemma as judge."""
    import torch

    prompt = (
        "Evaluate the radiology assistant answer based on context. "
        "Return JSON with 'correctness_score' (1-5) and 'justification'.\n\n"
        f"CONTEXT: {context}\n"
        f"Q: {question}\n"
        f"A: {answer}\n"
        f"GT: {ground_truth}"
    )

    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=0.1,
        )
    raw = tokenizer.decode(
        outputs[0][inputs.input_ids.shape[1] :], skip_special_tokens=True
    )

    # Try to parse the JSON from the response
    result: dict[str, Any] = {
        "raw": raw,
        "correctness_score": None,
        "justification": None,
    }
    try:
        # Find JSON in the response (model may include extra text around it)
        start = raw.index("{")
        end = raw.rindex("}") + 1
        parsed = json.loads(raw[start:end])
        result["correctness_score"] = parsed.get("correctness_score")
        result["justification"] = parsed.get("justification")
    except (ValueError, json.JSONDecodeError):
        # If JSON parsing fails, return the raw text; caller can display it as-is
        pass

    return result
