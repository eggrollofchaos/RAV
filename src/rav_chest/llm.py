from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from openai import OpenAI

DEFAULT_MODEL = "gpt-4.1-mini"
DEFAULT_SYSTEM_PROMPT = (
    "You are a concise medical writing assistant. "
    "Do not invent clinical facts that are not provided."
)


def _parse_env_value(raw: str) -> str:
    value = raw.strip()
    if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
        value = value[1:-1]
    return value.strip()


def _load_key_from_env_file(path: Path) -> str:
    if not path.exists():
        return ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() != "OPENAI_API_KEY":
            continue
        parsed = _parse_env_value(value)
        if parsed:
            os.environ.setdefault("OPENAI_API_KEY", parsed)
            return parsed
    return ""


def resolve_openai_api_key(explicit_api_key: str | None = None) -> str:
    if explicit_api_key:
        return explicit_api_key

    env_key = os.getenv("OPENAI_API_KEY", "").strip()
    if env_key:
        return env_key

    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parents[2] / ".env",
    ]
    for path in candidates:
        key = _load_key_from_env_file(path)
        if key:
            return key
    return ""


def get_openai_client(api_key: str | None = None, base_url: str | None = None) -> OpenAI:
    key = resolve_openai_api_key(api_key)
    if not key:
        raise ValueError(
            "Missing OPENAI_API_KEY. Put it in .env, export it, or pass api_key explicitly."
        )
    kwargs: dict[str, Any] = {"api_key": key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def _extract_output_text(response: Any) -> str:
    text = getattr(response, "output_text", "")
    if isinstance(text, str) and text.strip():
        return text.strip()

    chunks: list[str] = []
    outputs = getattr(response, "output", []) or []
    for item in outputs:
        content = getattr(item, "content", None)
        if content is None and isinstance(item, dict):
            content = item.get("content")
        if not content:
            continue
        for part in content:
            if isinstance(part, dict):
                part_type = part.get("type")
                part_text = part.get("text")
            else:
                part_type = getattr(part, "type", None)
                part_text = getattr(part, "text", None)
            if part_type in {"output_text", "text"} and isinstance(part_text, str):
                chunks.append(part_text)
    return "".join(chunks).strip()


def generate_text(
    prompt: str,
    model: str = DEFAULT_MODEL,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    temperature: float = 0.2,
    max_output_tokens: int = 300,
    api_key: str | None = None,
    base_url: str | None = None,
    client: OpenAI | None = None,
) -> str:
    if not prompt.strip():
        raise ValueError("Prompt must be non-empty.")

    openai_client = client or get_openai_client(api_key=api_key, base_url=base_url)
    response = openai_client.responses.create(
        model=model,
        instructions=system_prompt.strip(),
        input=prompt.strip(),
        temperature=float(temperature),
        max_output_tokens=int(max_output_tokens),
    )
    text = _extract_output_text(response)
    if not text:
        raise RuntimeError("Model returned an empty response.")
    return text


def build_report_rewrite_prompt(report_payload: Mapping[str, Any]) -> str:
    findings = report_payload.get("findings", [])
    source_impression = str(report_payload.get("impression", "")).strip()
    payload_text = json.dumps(
        {"findings": findings, "impression": source_impression},
        ensure_ascii=True,
        indent=2,
    )
    return (
        "Rewrite the radiology impression for clarity in 1-2 concise sentences.\n"
        "Rules:\n"
        "- Use only the findings provided.\n"
        "- Do not add new diagnoses or uncertainty not present in inputs.\n"
        "- Keep wording clinically neutral.\n\n"
        "Input payload:\n"
        f"{payload_text}"
    )


def rewrite_report_impression(
    report_payload: Mapping[str, Any],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.1,
    max_output_tokens: int = 180,
    api_key: str | None = None,
    base_url: str | None = None,
    client: OpenAI | None = None,
) -> str:
    prompt = build_report_rewrite_prompt(report_payload)
    return generate_text(
        prompt=prompt,
        model=model,
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        api_key=api_key,
        base_url=base_url,
        client=client,
    )
