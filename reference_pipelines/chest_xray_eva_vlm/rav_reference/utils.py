from __future__ import annotations

import base64
import io

from PIL import Image
import torch


def select_device(hint: str | None = "auto") -> torch.device:
    normalized = (hint or "auto").strip().lower()

    if normalized == "cpu":
        return torch.device("cpu")

    if normalized == "mps":
        if torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")

    if normalized in {"cuda", "gpu"}:
        if torch.cuda.is_available():
            return torch.device("cuda")
        return torch.device("cpu")

    if torch.cuda.is_available():
        return torch.device("cuda")

    if torch.backends.mps.is_available():
        return torch.device("mps")

    return torch.device("cpu")


def load_image(source: str) -> Image.Image:
    """Load an image from a local path or URL and return as RGB PIL Image.

    ``requests`` is imported lazily inside the URL branch — it is a transitive
    dependency (via streamlit, transformers, huggingface_hub) and is not pinned
    explicitly in requirements.txt.
    """
    if source.startswith(("http://", "https://")):
        import requests  # transitive dep, not explicitly pinned

        response = requests.get(source, timeout=30)
        response.raise_for_status()
        return Image.open(io.BytesIO(response.content)).convert("RGB")
    return Image.open(source).convert("RGB")


def pil_to_base64(
    image: Image.Image,
    fmt: str = "JPEG",
    max_size: int = 512,
) -> str:
    prepared = image.convert("RGB").copy()
    prepared.thumbnail((max_size, max_size))

    buffer = io.BytesIO()
    prepared.save(buffer, format=fmt, optimize=True, quality=90)
    return base64.b64encode(buffer.getvalue()).decode("ascii")
