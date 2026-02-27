#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rav_chest.llm import (
    DEFAULT_MODEL,
    DEFAULT_SYSTEM_PROMPT,
    generate_text,
    rewrite_report_impression,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simple OpenAI LLM wrapper for prompt calls and report rewriting."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prompt", type=str, default="", help="Direct prompt text.")
    mode.add_argument(
        "--prompt-file",
        type=str,
        default="",
        help="Path to a text file containing the prompt.",
    )
    mode.add_argument(
        "--report-json",
        type=str,
        default="",
        help="Path to report payload JSON (uses findings+impression rewrite mode).",
    )
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-output-tokens", type=int, default=300)
    parser.add_argument("--system-prompt", type=str, default=DEFAULT_SYSTEM_PROMPT)
    parser.add_argument(
        "--base-url",
        type=str,
        default="",
        help="Optional OpenAI-compatible base URL override.",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default="",
        help="Optional API key override. Defaults to OPENAI_API_KEY env var.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Optional text output path.",
    )
    return parser.parse_args()


def _load_prompt(args: argparse.Namespace) -> str:
    if args.prompt:
        return args.prompt
    if args.prompt_file:
        return Path(args.prompt_file).read_text(encoding="utf-8")
    return ""


def main() -> None:
    args = parse_args()
    api_key = args.api_key.strip() or None
    base_url = args.base_url.strip() or None

    if args.report_json:
        payload = json.loads(Path(args.report_json).read_text(encoding="utf-8"))
        text = rewrite_report_impression(
            report_payload=payload,
            model=args.model,
            temperature=float(args.temperature),
            max_output_tokens=int(args.max_output_tokens),
            api_key=api_key,
            base_url=base_url,
        )
    else:
        prompt = _load_prompt(args)
        text = generate_text(
            prompt=prompt,
            model=args.model,
            system_prompt=args.system_prompt,
            temperature=float(args.temperature),
            max_output_tokens=int(args.max_output_tokens),
            api_key=api_key,
            base_url=base_url,
        )

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
        print(f"Saved output to: {out_path}")
    print(text)


if __name__ == "__main__":
    main()

