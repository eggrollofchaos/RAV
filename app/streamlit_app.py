from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd
import streamlit as st
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rav_chest.pipeline import infer_from_pil, load_inference_bundle


DEFAULT_CONFIGS = {
    "Primary (CheXpert)": ROOT / "configs" / "primary" / "chest_chexpert.yaml",
    "POC (Kaggle Binary)": ROOT / "configs" / "poc" / "chest_pneumonia_binary.yaml",
}


@st.cache_resource(show_spinner=False)
def load_bundle_cached(config_path: str, checkpoint_override: str):
    return load_inference_bundle(config_path, checkpoint_override)


def render_findings_table(payload: dict) -> None:
    findings = payload.get("findings", [])
    if not findings:
        st.info("No positive findings at current thresholds.")
        return

    df = pd.DataFrame(findings)
    df = df.rename(
        columns={
            "name": "Finding",
            "confidence": "Confidence",
            "threshold": "Threshold",
        }
    )
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_probabilities(bundle, probs) -> None:
    rows = []
    for name, p, t in zip(bundle.class_names, probs.tolist(), bundle.thresholds.tolist()):
        rows.append(
            {
                "Finding": name,
                "Probability": round(float(p), 4),
                "Threshold": round(float(t), 4),
                "Positive": bool(p >= t),
            }
        )
    df = pd.DataFrame(rows).sort_values("Probability", ascending=False)
    st.dataframe(df, use_container_width=True, hide_index=True)


def main() -> None:
    st.set_page_config(page_title="RAV Chest X-ray Demo", layout="wide")
    st.title("RAV Chest X-ray Demo")
    st.caption("Research prototype only. Not for clinical use.")

    with st.sidebar:
        st.header("Inference Settings")
        preset_name = st.selectbox("Config Preset", list(DEFAULT_CONFIGS.keys()), index=0)
        preset_path = str(DEFAULT_CONFIGS[preset_name])

        config_path = st.text_input("Config Path", value=preset_path)
        checkpoint_override = st.text_input(
            "Checkpoint Path (optional)",
            value="",
            help="Leave blank to use <output_dir>/checkpoints/best.pt from config.",
        )
        show_all_probs = st.checkbox("Show all class probabilities", value=True)

    uploaded = st.file_uploader(
        "Upload chest X-ray image",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=False,
    )

    if not uploaded:
        st.info("Upload an image to run inference.")
        return

    image = Image.open(uploaded).convert("RGB")
    col1, col2 = st.columns([1, 1.2])
    with col1:
        st.image(image, caption=uploaded.name, use_container_width=True)

    run = st.button("Analyze Image", type="primary", use_container_width=True)
    if not run:
        return

    with col2:
        try:
            with st.spinner("Loading model and running inference..."):
                t0 = time.perf_counter()
                bundle = load_bundle_cached(config_path, checkpoint_override)
                payload, probs = infer_from_pil(bundle, image)
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
        except Exception as exc:
            st.error("Inference failed. Check config/checkpoint paths.")
            st.exception(exc)
            return

        st.success(f"Inference complete in {elapsed_ms:.1f} ms")
        st.subheader("Impression")
        st.write(payload["impression"])

        critical = payload.get("critical_flags", [])
        if critical:
            st.warning("Critical flags: " + ", ".join(critical))

        st.subheader("Positive Findings")
        render_findings_table(payload)

        st.subheader("Run Metadata")
        st.code(
            "\n".join(
                [
                    f"config={payload.get('config', 'N/A')}",
                    f"checkpoint={payload.get('checkpoint', 'N/A')}",
                    f"device={bundle.device}",
                ]
            )
        )

        if show_all_probs:
            st.subheader("All Probabilities")
            render_probabilities(bundle, probs)

        payload["source_filename"] = uploaded.name
        payload_json = json.dumps(payload, indent=2)
        st.download_button(
            label="Download Report JSON",
            data=payload_json,
            file_name=f"{Path(uploaded.name).stem}_report.json",
            mime="application/json",
            use_container_width=True,
        )


if __name__ == "__main__":
    main()

