#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

import torch
from PIL import Image
from dotenv import load_dotenv

# Add project root to sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

# Load credentials from .env
load_dotenv()

from rav_reference.qa_evaluator import QAEvaluator, QASample, MedGemmaJudge
from rav_reference.llm import (
    load_chexagent,
    make_chexagent_generate_fn,
    load_llama_model,
    make_llama_generate_fn,
)


def get_model_fn(model_type: str, device: str):
    if model_type == "chexagent":
        model, tokenizer = load_chexagent(device=device)
        gen_fn = make_chexagent_generate_fn(model, tokenizer, device=device)
        return lambda img, q, ctx: gen_fn(img, q)
    elif model_type == "llama":
        gen_fn = make_llama_generate_fn(*load_llama_model())
        return lambda img, q, ctx: gen_fn(img, q)
    elif model_type == "openai":
        from rav_reference.llm import answer_question_about_report

        def openai_fn(image: Image.Image, question: str, context: str | None = None):
            payload = {"impression": context or "Findings available in context."}
            return answer_question_about_report(payload, question)

        return openai_fn
    else:
        raise ValueError(f"Unknown model type: {model_type}")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate Radiology Assistant QA capabilities. "
            "Requires pre-generated test data: run scripts/download_test_images.py "
            "then scripts/generate_test_json.py first."
        ),
    )
    parser.add_argument(
        "--test-data",
        type=str,
        default="qa_test_samples.json",
        help="Path to QA test samples JSON.",
    )
    parser.add_argument(
        "--model",
        type=str,
        choices=["chexagent", "llama", "openai"],
        default="chexagent",
        help="Model to evaluate.",
    )
    parser.add_argument(
        "--judge-model",
        type=str,
        default="google/medgemma-1.5-4b-it",
        help="Med-Gemma model ID for judging.",
    )
    parser.add_argument(
        "--use-judge",
        action="store_true",
        help="Whether to use Med-Gemma for qualitative evaluation.",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cuda" if torch.cuda.is_available() else "cpu",
        help="Device to use.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="evaluation_report.json",
        help="Path to save evaluation results.",
    )

    args = parser.parse_args()

    # Load test data
    with open(args.test_data, "r") as f:
        data = json.load(f)

    samples = [
        QASample(
            image_path=s.get("image_path"),
            question=s.get("question"),
            ground_truth=s.get("ground_truth"),
            context=s.get("context"),
        )
        for s in data
    ]

    print(f"Loaded {len(samples)} samples for evaluation.")

    # Load model
    print(f"Loading model: {args.model}...")
    qa_model_fn = get_model_fn(args.model, args.device)

    # Initialize Evaluator
    judge = None
    if args.use_judge:
        print(f"Loading judge model: {args.judge_model}...")
        try:
            judge = MedGemmaJudge(model_id=args.judge_model, device=args.device)
        except Exception as e:
            print(f"Warning: Failed to load Med-Gemma judge: {e}")
            print("Proceeding with quantitative metrics only.")

    evaluator = QAEvaluator(judge=judge)

    # Run evaluation
    print("Running evaluation...")
    results = evaluator.run_evaluation(samples, qa_model_fn)

    # Save results
    with open(args.output, "w") as f:

        def serialize(obj):
            if isinstance(obj, QASample):
                return {
                    "image_path": obj.image_path,
                    "question": obj.question,
                    "ground_truth": obj.ground_truth,
                    "context": obj.context,
                }
            return obj.__dict__ if hasattr(obj, "__dict__") else str(obj)

        json.dump(results, f, indent=2, default=serialize)

    print(f"Evaluation complete. Report saved to {args.output}")


if __name__ == "__main__":
    main()
