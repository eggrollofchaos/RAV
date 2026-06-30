from __future__ import annotations

import json
import os
from pathlib import Path
from collections.abc import Callable
from typing import Any, Mapping

from PIL import Image

from .utils import pil_to_base64

DEFAULT_REASONING_MODEL = "gpt-4.1"
DEFAULT_QA_MODEL = "gpt-4.1-mini"
VISION_SYSTEM_PROMPT = (
    "You are a concise radiology assistant for a research prototype. "
    "Describe only visible chest X-ray findings, acknowledge uncertainty, "
    "and do not provide treatment advice."
)
AGENT_QA_SYSTEM_PROMPT = (
    "You are a helpful and concise radiology assistant for a research prototype. "
    "Your goal is to explain findings, classification results, and general radiology concepts. "
    "While you should prioritize the provided context, you can use your general medical knowledge to explain *why* certain findings lead to a classification or to define terms. "
    "If information is missing from the specific image context, you may provide general educational information while clearly stating it is not specific to this case."
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


def resolve_openai_api_key(explicit_key: str | None = None) -> str:
    if explicit_key:
        return explicit_key

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


def get_openai_client(
    api_key: str | None = None,
    base_url: str | None = None,
):
    from openai import OpenAI

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

    parts: list[str] = []
    for item in getattr(response, "output", []) or []:
        content = getattr(item, "content", None)
        if content is None and isinstance(item, dict):
            content = item.get("content")
        if not content:
            continue
        for chunk in content:
            if isinstance(chunk, dict):
                chunk_type = chunk.get("type")
                chunk_text = chunk.get("text")
            else:
                chunk_type = getattr(chunk, "type", None)
                chunk_text = getattr(chunk, "text", None)
            if chunk_type in {"output_text", "text"} and isinstance(chunk_text, str):
                parts.append(chunk_text)
    return "".join(parts).strip()


def build_reasoning_prompt(p_abnormal: float, tier: str) -> str:
    probability = float(p_abnormal)
    normalized_tier = tier.strip().lower()

    if normalized_tier == "borderline":
        return f"""
A binary chest X-ray classifier assigned this image an abnormal probability of {probability:.2f}, indicating a borderline abnormal signal.

- Carefully describe any subtle or equivocal imaging findings.
- Discuss alternative normal variants that could mimic abnormality.
- Emphasize uncertainty.
- Provide low-confidence differential considerations only if justified.

Avoid strong conclusions and clearly state limitations.
""".strip()

    if normalized_tier == "moderate":
        return f"""
A binary chest X-ray classifier assigned this image an abnormal probability of {probability:.2f}.

- Describe observable imaging features.
- Provide a short differential diagnosis list.
- Indicate level of certainty.
- Avoid definitive medical diagnosis.
- Emphasize that interpretation is preliminary and image-only.
""".strip()

    if normalized_tier == "high":
        return f"""
A binary chest X-ray classifier assigned this image an abnormal probability of {probability:.2f}.

Given the strong abnormal signal:

- Describe the dominant and most likely radiographic patterns visible.
- Explain which imaging features most strongly support abnormality.
- Provide 2-3 likely explanations.
- Indicate level of certainty.
- Avoid definitive diagnosis.

Focus on prominent findings rather than subtle ones.
""".strip()

    raise ValueError(f"Unsupported reasoning tier for image analysis: {tier!r}")


def analyze_xray_image(
    image: Image.Image,
    p_abnormal: float,
    tier: str,
    model: str = DEFAULT_REASONING_MODEL,
) -> str:
    client = get_openai_client()
    prompt = build_reasoning_prompt(p_abnormal, tier)
    encoded_image = pil_to_base64(image, fmt="JPEG", max_size=512)

    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_image",
                        "image_url": f"data:image/jpeg;base64,{encoded_image}",
                    },
                    {"type": "input_text", "text": prompt},
                ],
            }
        ],
        instructions=VISION_SYSTEM_PROMPT,
        temperature=0.2,
        max_output_tokens=400,
    )

    text = _extract_output_text(response)
    if not text:
        raise RuntimeError("Model returned an empty reasoning response.")
    return text


def build_agent_qa_prompt(report_payload: Mapping[str, Any], question: str) -> str:
    if not question.strip():
        raise ValueError("Question must be non-empty.")

    context = {
        "source_filename": report_payload.get("source_filename"),
        "impression": str(report_payload.get("impression", "")).strip(),
        "reasoning": report_payload.get("reasoning"),
        "p_abnormal": report_payload.get("p_abnormal"),
        "threshold": report_payload.get("threshold"),
        "confidence_tier": report_payload.get("confidence_tier"),
        "reasoning_error": report_payload.get("reasoning_error"),
    }
    context_json = json.dumps(context, ensure_ascii=True, indent=2)
    return (
        "Use the provided context as the primary source for answering the user question. "
        "If the question is about general medical concepts or explaining the significance of the findings (e.g., 'What is a confidence tier?', 'Why is pneumonia abnormal?'), "
        "use your internal knowledge to provide a helpful and educational response.\n\n"
        "Rules:\n"
        "- Be concise and professional.\n"
        "- If the answer is specific to the image but not in the context, clearly state: 'The specific analysis of this image doesn't mention [X], but generally...' \n"
        "- Always maintain a helpful and informative tone.\n\n"
        f"Context:\n{context_json}\n\n"
        f"User question:\n{question.strip()}"
    )


def answer_question_about_report(
    report_payload: Mapping[str, Any],
    question: str,
    model: str = DEFAULT_QA_MODEL,
) -> str:
    client = get_openai_client()
    prompt = build_agent_qa_prompt(report_payload, question)
    response = client.responses.create(
        model=model,
        instructions=AGENT_QA_SYSTEM_PROMPT,
        input=prompt,
        temperature=0.1,
        max_output_tokens=260,
    )

    text = _extract_output_text(response)
    if not text:
        raise RuntimeError("Model returned an empty answer.")
    return text


# ---------------------------------------------------------------------------
# Llama (local) backend
# ---------------------------------------------------------------------------

DEFAULT_LLAMA_MODEL = "0llheaven/Llama-3.2-11B-Vision-Radiology-mini"


def load_llama_model(
    model_name: str = DEFAULT_LLAMA_MODEL,
    load_in_4bit: bool = True,
):
    from unsloth import FastVisionModel

    model, tokenizer = FastVisionModel.from_pretrained(
        model_name,
        load_in_4bit=load_in_4bit,
        use_gradient_checkpointing="unsloth",
    )
    FastVisionModel.for_inference(model)
    return model, tokenizer


def _llama_generate_with_image(model, tokenizer, image, prompt, max_new_tokens=400):
    import torch

    image_copy = image.copy()
    image_copy.thumbnail((448, 448), Image.Resampling.LANCZOS)
    messages = [
        {
            "role": "user",
            "content": [{"type": "image"}, {"type": "text", "text": prompt}],
        }
    ]
    text_prompt = tokenizer.apply_chat_template(messages, add_generation_prompt=True)
    inputs = tokenizer(
        text=text_prompt,
        images=image_copy,
        add_special_tokens=False,
        return_tensors="pt",
    )
    device = next(model.parameters()).device
    inputs = {
        key: value.to(device) if torch.is_tensor(value) else value
        for key, value in inputs.items()
    }
    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=0.6,
            top_p=0.9,
            use_cache=False,
        )
    input_len = inputs["input_ids"].shape[-1]
    return tokenizer.decode(output[0][input_len:], skip_special_tokens=True).strip()


def _llama_generate_text_only(model, tokenizer, prompt, max_new_tokens=260):
    import torch

    messages = [
        {
            "role": "user",
            "content": [{"type": "text", "text": prompt}],
        }
    ]
    text_prompt = tokenizer.apply_chat_template(messages, add_generation_prompt=True)
    inputs = tokenizer(
        text=text_prompt,
        add_special_tokens=False,
        return_tensors="pt",
    )
    device = next(model.parameters()).device
    inputs = {
        key: value.to(device) if torch.is_tensor(value) else value
        for key, value in inputs.items()
    }
    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=0.1,
            top_p=0.9,
            use_cache=False,
        )
    input_len = inputs["input_ids"].shape[-1]
    return tokenizer.decode(output[0][input_len:], skip_special_tokens=True).strip()


def analyze_xray_image_llama(
    image: Image.Image,
    p_abnormal: float,
    tier: str,
    model,
    tokenizer,
    max_new_tokens: int = 400,
) -> str:
    prompt = VISION_SYSTEM_PROMPT + "\n\n" + build_reasoning_prompt(p_abnormal, tier)
    text = _llama_generate_with_image(model, tokenizer, image, prompt, max_new_tokens)
    if not text:
        raise RuntimeError("Llama model returned an empty reasoning response.")
    return text


def answer_question_about_report_llama(
    report_payload: Mapping[str, Any],
    question: str,
    model,
    tokenizer,
    max_new_tokens: int = 260,
) -> str:
    prompt = (
        AGENT_QA_SYSTEM_PROMPT
        + "\n\n"
        + build_agent_qa_prompt(report_payload, question)
    )
    text = _llama_generate_text_only(model, tokenizer, prompt, max_new_tokens)
    if not text:
        raise RuntimeError("Llama model returned an empty answer.")
    return text


def make_llama_generate_fn(
    model, tokenizer, max_new_tokens: int = 128
) -> Callable[[Image.Image, str], str]:
    """Return a ``(image, prompt) -> str`` callable using the Llama backend.

    Default ``max_new_tokens=128`` matches CLI parity.  The Streamlit UI uses
    ``_llama_generate_with_image`` directly with ``max_new_tokens=400``.
    """

    def generate(image: Image.Image, prompt: str) -> str:
        return _llama_generate_with_image(
            model, tokenizer, image, prompt, max_new_tokens
        )

    return generate


# ---------------------------------------------------------------------------
# CheXagent backend
# ---------------------------------------------------------------------------


def load_chexagent(
    model_name: str = "StanfordAIMI/CheXagent-2-3b-srrg-findings",
    device: Any = "cuda",
):
    """Load a CheXagent model and tokenizer.

    ``device`` is normalized to a plain string for ``device_map`` (HuggingFace
    expects ``"cuda"`` / ``"cpu"``, not ``torch.device(...)``).
    """
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    device_str = str(device)
    torch_dtype = torch.bfloat16 if device_str != "cpu" else torch.float32
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        trust_remote_code=True,
        torch_dtype=torch_dtype,
        device_map=device_str,
        low_cpu_mem_usage=True,
    )
    model.eval()
    return model, tokenizer


def make_chexagent_generate_fn(
    model, tokenizer, device: Any = "cuda"
) -> Callable[[Image.Image, str], str]:
    """Return a ``(image, prompt) -> str`` callable using CheXagent."""
    import os
    import tempfile

    device_str = str(device)

    def generate(image: Image.Image, prompt: str) -> str:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
            tmp_path = tmp_file.name

        try:
            image_to_save = image if image.mode == "RGB" else image.convert("RGB")
            image_to_save.save(tmp_path)
            query = tokenizer.from_list_format([{"image": tmp_path}, {"text": prompt}])
            conversation = [
                {"from": "system", "value": "You are a helpful assistant."},
                {"from": "human", "value": query},
            ]
            input_ids = tokenizer.apply_chat_template(
                conversation,
                add_generation_prompt=True,
                return_tensors="pt",
            )
            output = model.generate(
                input_ids.to(device_str),
                do_sample=False,
                num_beams=1,
                temperature=1.0,
                top_p=1.0,
                use_cache=True,
                max_new_tokens=512,
            )[0]
            return tokenizer.decode(output[input_ids.size(1) : -1])
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    return generate
