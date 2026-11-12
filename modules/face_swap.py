"""Face Swap Studio UI for AI Influencer Studio.

This module provides upload, preview, model discovery, and output registration.
It deliberately does not simulate face swapping. Real inference is enabled only
when a compatible engine is installed and integrated.
"""
from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import Any

import streamlit as st

import config
import storage

SUPPORTED_IMAGE_TYPES = ["jpg", "jpeg", "png", "webp"]
SUPPORTED_VIDEO_TYPES = ["mp4", "mov", "avi", "mkv"]
MODEL_SEARCH_DIRS = (
    Path(config.BASE_DIR) / "models",
    Path(config.ENGINES_DIR) / "models",
)


def discover_models() -> list[Path]:
    """Find likely InsightFace INSwapper ONNX model files without loading them."""
    candidates: list[Path] = []
    for directory in MODEL_SEARCH_DIRS:
        try:
            resolved_dir = directory.resolve()
            if not resolved_dir.is_dir():
                continue
            for path in resolved_dir.glob("*.onnx"):
                try:
                    resolved = path.resolve(strict=True)
                    if resolved.is_file() and not path.is_symlink():
                        candidates.append(resolved)
                except OSError:
                    continue
        except OSError:
            continue

    # Prefer known INSwapper model names, but keep other ONNX files visible.
    candidates.sort(
        key=lambda p: ("inswapper" not in p.name.lower(), p.name.lower())
    )
    return candidates


def compatible_engine_available() -> bool:
    """Return True only when a real engine module can be imported."""
    try:
        from engines import face_swap_engine  # type: ignore[import-not-found]

        return callable(getattr(face_swap_engine, "swap_face", None))
    except Exception:
        return False


def save_generated_result(
    data: bytes,
    extension: str,
    *,
    prefix: str = "face_swap",
) -> dict[str, Any]:
    """Save actual engine output in output/ and register its one-hour TTL."""
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise ValueError("The generated result is empty.")

    suffix = extension.lower().lstrip(".")
    if suffix not in {"jpg", "jpeg", "png", "webp", "mp4", "mov"}:
        raise ValueError("Unsupported generated output format.")

    output_root = Path(config.OUTPUT_DIR).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    filename = f"{prefix}_{uuid.uuid4().hex}.{suffix}"
    destination = output_root / filename

    # Exclusive creation avoids overwriting another output.
    with destination.open("xb") as handle:
        handle.write(data)

    try:
        return storage.register_output(destination)
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def _show_image_preview(uploaded: Any, label: str) -> None:
    if uploaded is None:
        return
    st.image(uploaded, caption=label, use_container_width=True)


def _show_target_preview(uploaded: Any) -> None:
    if uploaded is None:
        return
    extension = Path(uploaded.name).suffix.lower()
    if extension in {".mp4", ".mov", ".avi", ".mkv"}:
        st.video(uploaded)
    else:
        st.image(uploaded, caption="Target image", use_container_width=True)


def render(app: Any = st) -> None:
    """Render the Face Swap Studio page."""
    app.title("Face Swap Studio")
    app.caption(
        "Prepare source and target media, inspect available models, and "
        "preview inputs. Face swapping requires a real inference engine."
    )

    model_files = discover_models()
    engine_ready = compatible_engine_available()

    with app.container(border=True):
        app.subheader("Inference environment")
        col_a, col_b = app.columns(2)
        with col_a:
            app.metric("ONNX models found", len(model_files))
        with col_b:
            app.metric("Face-swap engine", "Available" if engine_ready else "Not installed")

        if model_files:
            model_labels = [str(path.relative_to(config.BASE_DIR)) for path in model_files]
            selected_model_label = app.selectbox(
                "Select ONNX model (discovery only)", model_labels
            )
            selected_model = model_files[model_labels.index(selected_model_label)]
            app.caption(f"Model file: `{selected_model}`")
            app.warning(
                "A model file being present does not prove compatibility. "
                "The engine must validate its architecture and providers."
            )
        else:
            app.selectbox(
                "Select ONNX model",
                ["No ONNX model found"],
                disabled=True,
            )
            app.info(
                "No ONNX model was found. Place a properly licensed, "
                "compatible model in `models/` or `engines/models/`."
            )

        if not engine_ready:
            app.warning(
                "Inference is unavailable: `engines/face_swap_engine.py` "
                "with a callable `swap_face` function is not installed. "
                "No face swap will be attempted and no fake result will be shown."
            )

    app.subheader("1. Upload source face")
    source_upload = app.file_uploader(
        "Source face image",
        type=SUPPORTED_IMAGE_TYPES,
        key="face_swap_source_upload",
        help="Upload a clear image of the person whose face you are authorized to use.",
    )
    if source_upload is not None:
        _show_image_preview(source_upload, "Source face")

    app.subheader("2. Upload target media")
    target_upload = app.file_uploader(
        "Target image or video",
        type=SUPPORTED_IMAGE_TYPES + SUPPORTED_VIDEO_TYPES,
        key="face_swap_target_upload",
        help="Choose the image or video in which the face would be replaced.",
    )
    if target_upload is not None:
        _show_target_preview(target_upload)

    app.subheader("3. Processing settings")
    settings_left, settings_right = app.columns(2)
    with settings_left:
        provider = app.selectbox(
            "Execution provider",
            ["CPU only"],
            help="The initial configuration targets low-memory CPU-only Windows systems.",
        )
    with settings_right:
        preview_scale = app.selectbox(
            "Preview resolution",
            ["Low (320 px)", "Medium (480 px)"],
            index=0,
        )

    app.caption(
        f"Selected: {provider}; {preview_scale}. These are preparation settings; "
        "they do not start inference."
    )

    if app.button(
        "Check readiness",
        use_container_width=True,
        key="face_swap_readiness",
    ):
        if source_upload is None:
            app.error("Upload a source face image first.")
        elif target_upload is None:
            app.error("Upload target media first.")
        elif not model_files:
            app.error("A compatible ONNX model is missing.")
        elif not engine_ready:
            app.error("The face-swap inference engine is missing.")
        else:
            app.success(
                "Inputs and engine entry point are present. Model compatibility "
                "and actual inference still need engine-level validation."
            )

    app.divider()
    app.subheader("Generated results")
    try:
        results = storage.list_outputs()
        face_results = [
            item for item in results
            if Path(item["name"]).name.startswith("face_swap_")
        ]
        if not face_results:
            app.info("No generated face-swap results are available yet.")
        else:
            for item in face_results:
                app.write(f"**{item['name']}** — expires in {item['remaining_seconds']} seconds")
                result_path = Path(item["path"])
                if result_path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                    app.image(str(result_path), use_container_width=True)
                elif result_path.suffix.lower() in {".mp4", ".mov"}:
                    app.video(str(result_path))
                with result_path.open("rb") as handle:
                    app.download_button(
                        "Download result",
                        data=handle.read(),
                        file_name=item["name"],
                        key=f"download_{item['name']}",
                    )
    except Exception as exc:
        app.error(f"Could not load generated results: {exc}")
