from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import streamlit as st
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rav_chest.pipeline import infer_from_pil, load_inference_bundle
from rav_chest.utils import load_yaml
from rav_chest.version import APP_VERSION


DEFAULT_CONFIGS = {
    "Primary (CheXpert)": "configs/primary/chest_chexpert.yaml",
    "POC (Kaggle Binary)": "configs/poc/chest_pneumonia_binary.yaml",
}
LATEST_REPORT_STATE_KEY = "latest_inference_payload"
AGENT_CHAT_STATE_KEY = "agent_chat_messages"


def resolve_project_path(path_str: str) -> Path:
    path = Path(path_str).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def resolve_config_path(config_path: str) -> Path:
    return resolve_project_path(config_path)


def to_project_relative(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


@st.cache_resource(show_spinner=False)
def load_bundle_cached(config_path: str, checkpoint_override: str):
    resolved_config = str(resolve_config_path(config_path))
    resolved_checkpoint = checkpoint_override.strip()
    if resolved_checkpoint:
        resolved_checkpoint = str(resolve_project_path(resolved_checkpoint))
    return load_inference_bundle(resolved_config, resolved_checkpoint)


@st.cache_data(show_spinner=False)
def _load_yaml_cached(config_path: str, mtime: float) -> Dict[str, Any]:
    del mtime
    return load_yaml(config_path)


def load_config_if_exists(config_path: str) -> Dict[str, Any] | None:
    p = resolve_config_path(config_path)
    if not p.exists():
        return None
    return _load_yaml_cached(str(p), p.stat().st_mtime)


@st.cache_data(show_spinner=False)
def _load_json_cached(path: str, mtime: float) -> Dict[str, Any]:
    del mtime
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def load_json_if_exists(path: Path) -> Dict[str, Any] | None:
    if not path.exists():
        return None
    return _load_json_cached(str(path), path.stat().st_mtime)


@st.cache_data(show_spinner=False)
def _load_csv_cached(path: str, mtime: float) -> pd.DataFrame:
    del mtime
    return pd.read_csv(path)


def load_csv_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return _load_csv_cached(str(path), path.stat().st_mtime)


@st.cache_data(show_spinner=False)
def _load_history_cached(path: str, mtime: float) -> pd.DataFrame:
    del mtime
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("epoch")


def load_history_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return _load_history_cached(str(path), path.stat().st_mtime)


def resolve_expected_checkpoint(
    config_path: str, checkpoint_override: str
) -> Path | None:
    override = checkpoint_override.strip()
    if override:
        return resolve_project_path(override)

    try:
        cfg = load_yaml(str(resolve_config_path(config_path)))
        output_dir = resolve_project_path(str(cfg["project"]["output_dir"]))
        return (output_dir / "checkpoints" / "best.pt").resolve()
    except Exception:
        return None


def resolve_output_dir(config_path: str) -> Path | None:
    cfg = load_config_if_exists(config_path)
    if cfg is None:
        return None
    try:
        return resolve_project_path(str(cfg["project"]["output_dir"]))
    except Exception:
        return None


def fmt_float(value: Any, digits: int = 4) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "N/A"


def render_missing_checkpoint_help(config_path: str, checkpoint_override: str) -> None:
    expected = resolve_expected_checkpoint(config_path, checkpoint_override)
    config_display = to_project_relative(resolve_config_path(config_path))
    st.error("Checkpoint is missing. Train first or provide a valid checkpoint path.")

    if expected:
        st.code(f"missing_checkpoint={to_project_relative(expected)}")

    st.caption("Next steps")
    st.code(
        "\n".join(
            [
                f"python scripts/train_chest_baseline.py --config {config_display}",
                f"python scripts/eval_chest_baseline.py --config {config_display} --split test",
                f"python -m streamlit run app/streamlit_app.py",
            ]
        ),
        language="bash",
    )

    if expected:
        last_ckpt = expected.with_name("last.pt")
        st.info(
            "If training is still running, try the checkpoint override field with:\n"
            f"`{to_project_relative(last_ckpt)}`"
        )


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
    st.dataframe(df, width="stretch", hide_index=True)


def render_probabilities(bundle, probs) -> None:
    rows = []
    for name, p, t in zip(
        bundle.class_names, probs.tolist(), bundle.thresholds.tolist()
    ):
        rows.append(
            {
                "Finding": name,
                "Probability": round(float(p), 4),
                "Threshold": round(float(t), 4),
                "Positive": bool(p >= t),
            }
        )
    df = pd.DataFrame(rows).sort_values("Probability", ascending=False)
    st.dataframe(df, width="stretch", hide_index=True)


def build_probabilities_map(bundle, probs) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for name, p in zip(bundle.class_names, probs.tolist()):
        out[str(name)] = round(float(p), 6)
    return out


def maybe_answer_question_with_llm(
    payload: Dict[str, Any], question: str, llm_model: str
) -> Dict[str, Any]:
    try:
        from rav_chest.llm import answer_question_about_report
    except Exception as exc:
        return {"ok": False, "error": f"LLM module unavailable: {exc}"}

    model_name = llm_model.strip() or "gpt-4.1-mini"
    try:
        answer = answer_question_about_report(
            report_payload=payload,
            question=question,
            probabilities=payload.get("probabilities", {}),
            source_filename=str(payload.get("source_filename", "")).strip() or None,
            model=model_name,
        )
        return {"ok": True, "model": model_name, "text": answer}
    except ValueError as exc:
        return {"ok": False, "model": model_name, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "model": model_name, "error": f"{type(exc).__name__}: {exc}"}


def maybe_rewrite_impression_with_llm(
    payload: Dict[str, Any], llm_model: str
) -> Dict[str, Any]:
    try:
        from rav_chest.llm import rewrite_report_impression
    except Exception as exc:
        return {"ok": False, "error": f"LLM module unavailable: {exc}"}

    model_name = llm_model.strip() or "gpt-4.1-mini"
    try:
        rewritten = rewrite_report_impression(report_payload=payload, model=model_name)
        return {"ok": True, "model": model_name, "text": rewritten}
    except ValueError as exc:
        return {"ok": False, "model": model_name, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "model": model_name, "error": f"{type(exc).__name__}: {exc}"}


def render_inference_page(
    config_path: str,
    checkpoint_override: str,
    show_all_probs: bool,
    llm_rewrite_enabled: bool,
    llm_model: str,
) -> None:
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
        st.image(image, caption=uploaded.name, width="stretch")

    run = st.button("Analyze Image", type="primary", width="stretch")
    if not run:
        return

    with col2:
        try:
            with st.spinner("Loading model and running inference..."):
                t0 = time.perf_counter()
                bundle = load_bundle_cached(config_path, checkpoint_override)
                payload, probs = infer_from_pil(bundle, image)
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
        except FileNotFoundError:
            render_missing_checkpoint_help(config_path, checkpoint_override)
            return
        except Exception as exc:
            st.error("Inference failed. Check config/checkpoint paths.")
            st.exception(exc)
            return

        st.success(f"Inference complete in {elapsed_ms:.1f} ms")
        llm_rewrite_text = ""
        llm_rewrite_error = ""
        llm_rewrite_model = llm_model.strip() or "gpt-4.1-mini"

        if llm_rewrite_enabled:
            i_col1, i_col2 = st.columns(2)
            with i_col1:
                st.subheader("Impression (Deterministic)")
                st.write(payload["impression"])
            with i_col2:
                st.subheader("Impression (LLM Rewrite)")
                with st.spinner(f"Rewriting with OpenAI ({llm_rewrite_model})..."):
                    rewrite_result = maybe_rewrite_impression_with_llm(
                        payload=payload,
                        llm_model=llm_rewrite_model,
                    )
                if bool(rewrite_result.get("ok")):
                    llm_rewrite_text = str(rewrite_result.get("text", "")).strip()
                    st.write(llm_rewrite_text)
                else:
                    llm_rewrite_error = str(
                        rewrite_result.get("error", "Unknown error")
                    )
                    st.caption("LLM rewrite unavailable for this run.")
                    st.error(llm_rewrite_error)
        else:
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
        payload["probabilities"] = build_probabilities_map(bundle, probs)
        payload["llm_rewrite"] = {
            "enabled": bool(llm_rewrite_enabled),
            "model": llm_rewrite_model if llm_rewrite_enabled else None,
            "rewritten_impression": llm_rewrite_text if llm_rewrite_text else None,
            "error": llm_rewrite_error if llm_rewrite_error else None,
        }
        st.session_state[LATEST_REPORT_STATE_KEY] = dict(payload)
        payload_json = json.dumps(payload, indent=2)
        st.download_button(
            label="Download Report JSON",
            data=payload_json,
            file_name=f"{Path(uploaded.name).stem}_report.json",
            mime="application/json",
            width="stretch",
        )


def render_ask_agent_page(llm_model: str) -> None:
    st.subheader("Ask Agent")
    st.caption("Ask natural-language questions grounded in model findings.")

    context_source = st.radio(
        "Context Source",
        ["Latest inference in this session", "Upload report JSON"],
        index=0,
        horizontal=True,
    )

    payload: Dict[str, Any] | None = None
    if context_source == "Latest inference in this session":
        cached_payload = st.session_state.get(LATEST_REPORT_STATE_KEY)
        if isinstance(cached_payload, dict):
            payload = dict(cached_payload)
        else:
            st.info("Run one inference first, then ask questions here.")
    else:
        report_json = st.file_uploader(
            "Upload report JSON",
            type=["json"],
            key="ask_agent_report_json",
            accept_multiple_files=False,
        )
        if report_json is not None:
            try:
                parsed = json.load(report_json)
                if isinstance(parsed, dict):
                    payload = parsed
                else:
                    st.error("Report JSON must be an object.")
            except Exception as exc:
                st.error(f"Unable to parse JSON: {exc}")

    if payload is None:
        return

    preview = {
        "source_filename": payload.get("source_filename"),
        "impression": payload.get("impression"),
        "critical_flags": payload.get("critical_flags", []),
        "findings": payload.get("findings", []),
    }
    with st.expander("Context Preview", expanded=False):
        st.json(preview)

    if AGENT_CHAT_STATE_KEY not in st.session_state:
        st.session_state[AGENT_CHAT_STATE_KEY] = []
    messages = st.session_state[AGENT_CHAT_STATE_KEY]

    clear_col, _ = st.columns([1, 4])
    with clear_col:
        if st.button("Clear Chat", width="stretch"):
            st.session_state[AGENT_CHAT_STATE_KEY] = []
            st.rerun()

    for msg in messages:
        role = str(msg.get("role", "assistant"))
        content = str(msg.get("content", ""))
        with st.chat_message(role):
            st.markdown(content)

    question = st.chat_input("Ask a question about findings, confidence, or rationale.")
    if not question:
        return

    messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            result = maybe_answer_question_with_llm(
                payload=payload,
                question=question,
                llm_model=llm_model,
            )
        if bool(result.get("ok")):
            answer_text = str(result.get("text", "")).strip()
            st.markdown(answer_text)
            messages.append({"role": "assistant", "content": answer_text})
        else:
            err = str(result.get("error", "Unknown error"))
            st.error(err)
            messages.append({"role": "assistant", "content": f"Error: {err}"})

    st.session_state[AGENT_CHAT_STATE_KEY] = messages


def render_model_metrics_page(
    config_path: str,
    checkpoint_override: str,
    metrics_split: str,
) -> None:
    cfg = load_config_if_exists(config_path)
    config_display = to_project_relative(resolve_config_path(config_path))
    if cfg is None:
        st.error(f"Config file not found: {config_display}")
        return

    output_dir = resolve_output_dir(config_path)
    if output_dir is None:
        st.error("Unable to resolve output directory from config.")
        return

    st.subheader("Model Details")
    class_names = [str(x) for x in cfg.get("labels", {}).get("columns", [])]
    training_cfg = cfg.get("training", {})
    selected_ckpt = resolve_expected_checkpoint(config_path, checkpoint_override)
    selected_ckpt_display = (
        to_project_relative(selected_ckpt) if selected_ckpt else "N/A"
    )
    selected_ckpt_exists = bool(selected_ckpt and selected_ckpt.exists())

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Classes", len(class_names), width="stretch")
    col2.metric("Backbone", str(training_cfg.get("backbone", "N/A")), width="stretch")
    col3.metric(
        "Image Size", str(training_cfg.get("image_size", "N/A")), width="stretch"
    )
    col4.metric(
        "Configured Epochs", str(training_cfg.get("epochs", "N/A")), width="stretch"
    )

    st.caption("Run Paths")
    st.code(
        "\n".join(
            [
                f"config={config_display}",
                f"output_dir={to_project_relative(output_dir)}",
                f"checkpoint={selected_ckpt_display}",
                f"checkpoint_exists={selected_ckpt_exists}",
            ]
        )
    )

    metrics_dir = output_dir / "metrics"
    st.subheader(f"Evaluation Metrics ({metrics_split})")
    metrics_json_path = metrics_dir / f"{metrics_split}_metrics.json"
    per_class_csv_path = metrics_dir / f"{metrics_split}_per_class.csv"
    confusion_csv_path = metrics_dir / f"{metrics_split}_confusion_per_class.csv"

    metrics_payload = load_json_if_exists(metrics_json_path)
    if metrics_payload is None:
        st.warning(
            f"No {metrics_split} metrics found yet at {to_project_relative(metrics_json_path)}. "
            f"Run: python scripts/eval_chest_baseline.py --config {config_path} --split {metrics_split}"
        )
    else:
        macro = metrics_payload.get("macro", {})
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Loss", fmt_float(metrics_payload.get("loss")), width="stretch")
        m2.metric("Macro AUROC", fmt_float(macro.get("auroc")), width="stretch")
        m3.metric("Macro F1", fmt_float(macro.get("f1")), width="stretch")
        m4.metric("Macro Brier", fmt_float(macro.get("brier")), width="stretch")
        st.caption(f"Metrics file: {to_project_relative(metrics_json_path)}")

    per_class_df = load_csv_if_exists(per_class_csv_path)
    if not per_class_df.empty:
        st.caption("Per-Class Metrics")
        st.dataframe(per_class_df, width="stretch", hide_index=True)
    else:
        st.info(
            f"No per-class CSV found yet: {to_project_relative(per_class_csv_path)}"
        )

    confusion_df = load_csv_if_exists(confusion_csv_path)
    if not confusion_df.empty:
        st.caption("Confusion Breakdown")
        st.dataframe(confusion_df, width="stretch", hide_index=True)
    else:
        st.info(
            f"No confusion CSV found yet: {to_project_relative(confusion_csv_path)}"
        )

    st.subheader("Training History")
    history_path = metrics_dir / "history.jsonl"
    history_df = load_history_if_exists(history_path)
    if history_df.empty:
        st.info(f"No history found yet: {to_project_relative(history_path)}")
        return

    numeric_cols = ["epoch", "train_loss", "val_loss"]
    for col in numeric_cols:
        if col in history_df.columns:
            history_df[col] = pd.to_numeric(history_df[col], errors="coerce")

    if {"epoch", "train_loss", "val_loss"}.issubset(history_df.columns):
        st.caption("Loss Curves")
        st.line_chart(
            history_df, x="epoch", y=["train_loss", "val_loss"], width="stretch"
        )

    st.caption(f"History file: {to_project_relative(history_path)}")
    st.dataframe(history_df.tail(10), width="stretch", hide_index=True)


def main() -> None:
    st.set_page_config(page_title="RAV - Radiology AI Agent", layout="wide")
    st.title("RAV - Radiology AI Agent")
    st.caption("Research prototype only. Not for clinical use.")

    with st.sidebar:
        st.title("🤖 RAV - Radiology AI Agent")
        st.caption(APP_VERSION)

        st.subheader("Page")
        page = st.radio(
            "Page",
            ["Inference", "Model Metrics", "Ask Agent"],
            index=0,
            label_visibility="collapsed",
        )

        st.header("Run Settings")
        preset_name = st.selectbox(
            "Config Preset", list(DEFAULT_CONFIGS.keys()), index=0
        )
        preset_path = DEFAULT_CONFIGS[preset_name]

        config_path = st.text_input("Config Path", value=preset_path)
        checkpoint_override = st.text_input(
            "Checkpoint Path (optional)",
            value="",
            help="Leave blank to use <output_dir>/checkpoints/best.pt from config.",
        )
        show_all_probs = st.checkbox("Show all class probabilities", value=True)
        llm_rewrite_enabled = st.checkbox(
            "Rewrite impression with OpenAI",
            value=False,
            disabled=(page != "Inference"),
            help="Uses OPENAI_API_KEY from .env or environment when enabled.",
        )
        llm_model = st.text_input(
            "LLM Model (Rewrite/Q&A)",
            value="gpt-4.1-mini",
            disabled=(page == "Model Metrics" or (page == "Inference" and not llm_rewrite_enabled)),
        )
        metrics_split = st.selectbox(
            "Metrics Split",
            ["test", "val"],
            index=0,
            disabled=(page != "Model Metrics"),
        )

        expected_ckpt = resolve_expected_checkpoint(config_path, checkpoint_override)
        if expected_ckpt and not expected_ckpt.exists():
            st.caption(
                f"⚠ Checkpoint not found yet: {to_project_relative(expected_ckpt)}"
            )

        st.divider()

        st.markdown("Midterm Project EECS E6895 Spring 2026")
        st.markdown(
            (
                "<div style='font-size:0.9rem; line-height:1.35;'>"
                "<span style='font-size:1.12rem; font-weight:900; color:#60A5FA;'>R</span>ithika Devarakonda<br>"
                "Wei <span style='font-size:1.12rem; font-weight:900; color:#60A5FA;'>A</span>lexander Xin<br>"
                "<span style='font-size:1.12rem; font-weight:900; color:#60A5FA;'>V</span>ikas Chelur"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div style='font-size:0.68rem; opacity:0.8;'>Copyright &copy; 2026</div>",
            unsafe_allow_html=True,
        )

    if page == "Inference":
        render_inference_page(
            config_path,
            checkpoint_override,
            show_all_probs,
            llm_rewrite_enabled,
            llm_model,
        )
    elif page == "Ask Agent":
        render_ask_agent_page(llm_model=llm_model)
    else:
        render_model_metrics_page(config_path, checkpoint_override, metrics_split)


if __name__ == "__main__":
    main()
