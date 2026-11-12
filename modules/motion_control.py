"""Motion Control Studio: reference preparation and output registration.

This module prepares a motion-transfer job. It does NOT perform motion transfer,
pose estimation, video generation, or character animation. A real local engine
must consume the prepared workflow and produce output bytes separately.
"""
from __future__ import annotations

import io
import uuid
from pathlib import Path
from typing import Any

import config
import database
import storage
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_MB = 12
MAX_VIDEO_MB = 100
MAX_PROMPT_CHARS = 2000
MIN_DURATION = 1
MAX_DURATION = 30
VIDEO_EXTENSIONS = {"mp4", "mov", "webm", "mkv"}
IMAGE_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}


def _base_dir() -> Path:
    return Path(config.BASE_DIR).resolve()


def _assets_dir() -> Path:
    return Path(config.ASSETS_DIR).resolve()


def _motion_assets_dir() -> Path:
    path = _assets_dir() / "motion_control"
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def _safe_saved_path(value: str | Path | None, *, assets_only: bool = True) -> Path | None:
    """Resolve a stored path without allowing traversal outside the asset tree."""
    if not value:
        return None
    raw = Path(value)
    candidate = raw.resolve() if raw.is_absolute() else (_base_dir() / raw).resolve()
    allowed = _assets_dir() if assets_only else _base_dir()
    if candidate == allowed or allowed not in candidate.parents:
        return None
    if candidate.is_symlink() or not candidate.is_file():
        return None
    return candidate


def list_available_characters(user_id: int | None = None) -> list[dict[str, Any]]:
    """Load saved character records from the existing character database."""
    return database.list_characters(user_id=user_id)


def _current_user_id(app: Any) -> int | None:
    user = app.session_state.get("auth_user")
    if isinstance(user, dict) and user.get("id") is not None:
        try:
            return int(user["id"])
        except (TypeError, ValueError):
            return None
    return None


def save_reference_image(upload: Any) -> Path:
    """Validate and persist an uploaded image in assets/motion_control/."""
    if upload is None:
        raise ValueError("Upload a motion reference image first.")
    raw = upload.getvalue()
    if not raw:
        raise ValueError("The uploaded image is empty.")
    if len(raw) > MAX_IMAGE_MB * 1024 * 1024:
        raise ValueError(f"Image must be {MAX_IMAGE_MB} MB or smaller.")
    try:
        with Image.open(io.BytesIO(raw)) as image:
            fmt = (image.format or "").upper()
            if fmt not in IMAGE_FORMATS:
                raise ValueError("Use a JPEG, PNG, or WEBP reference image.")
            if image.width > 6000 or image.height > 6000:
                raise ValueError("Image dimensions must not exceed 6000 × 6000.")
            image = ImageOps.exif_transpose(image)
            image.load()
            if fmt == "JPEG":
                image = image.convert("RGB")
            suffix = IMAGE_FORMATS[fmt]
            destination = _motion_assets_dir() / f"motion_ref_{uuid.uuid4().hex}{suffix}"
            save_options = {"quality": 92} if fmt == "JPEG" else {}
            image.save(destination, format=fmt, **save_options)
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("The uploaded file is not a valid supported image.") from exc
    return destination


def save_reference_video(upload: Any) -> Path:
    """Persist a supported video reference without decoding it."""
    if upload is None:
        raise ValueError("Upload a motion reference video first.")
    name = Path(getattr(upload, "name", "reference.mp4")).name
    suffix = Path(name).suffix.lower().lstrip(".")
    if suffix not in VIDEO_EXTENSIONS:
        raise ValueError("Use an MP4, MOV, WEBM, or MKV video.")
    raw = upload.getvalue()
    if not raw:
        raise ValueError("The uploaded video is empty.")
    if len(raw) > MAX_VIDEO_MB * 1024 * 1024:
        raise ValueError(f"Video must be {MAX_VIDEO_MB} MB or smaller.")
    destination = _motion_assets_dir() / f"motion_video_{uuid.uuid4().hex}.{suffix}"
    with destination.open("xb") as handle:
        handle.write(raw)
    return destination


def build_workflow(
    *, character: dict[str, Any], motion_prompt: str,
    movement_intensity: float, duration_seconds: int,
    reference_image: str | Path | None = None,
    reference_video: str | Path | None = None,
) -> dict[str, Any]:
    """Validate and describe a motion-transfer job; no inference is performed."""
    prompt = motion_prompt.strip()
    if not character or character.get("id") is None:
        raise ValueError("Select a saved character first.")
    if not prompt:
        raise ValueError("Enter a motion prompt.")
    if len(prompt) > MAX_PROMPT_CHARS:
        raise ValueError(f"Motion prompt must be {MAX_PROMPT_CHARS} characters or fewer.")
    intensity = float(movement_intensity)
    if not 0.0 <= intensity <= 1.0:
        raise ValueError("Movement intensity must be between 0 and 1.")
    duration = int(duration_seconds)
    if not MIN_DURATION <= duration <= MAX_DURATION:
        raise ValueError(f"Duration must be between {MIN_DURATION} and {MAX_DURATION} seconds.")

    image_path = _safe_saved_path(reference_image) if reference_image else None
    video_path = _safe_saved_path(reference_video) if reference_video else None
    if reference_image and image_path is None:
        raise ValueError("The saved reference image path is invalid.")
    if reference_video and video_path is None:
        raise ValueError("The saved reference video path is invalid.")

    return {
        "character_id": int(character["id"]),
        "character_name": str(character.get("name", "Character")),
        "character_image": character.get("image_path"),
        "motion_prompt": prompt,
        "movement_intensity": round(intensity, 2),
        "duration_seconds": duration,
        "reference_image": str(image_path) if image_path else None,
        "reference_video": str(video_path) if video_path else None,
        "inference_status": "not_run",
    }


def save_generated_output(data: bytes, extension: str) -> dict[str, Any]:
    """Save actual engine output and register it for storage.py's one-hour TTL."""
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise ValueError("Generated output is empty.")
    suffix = extension.lower().lstrip(".")
    if suffix not in VIDEO_EXTENSIONS:
        raise ValueError("Motion output must be MP4, MOV, WEBM, or MKV.")
    output_dir = Path(config.OUTPUT_DIR).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"motion_control_{uuid.uuid4().hex}.{suffix}"
    with destination.open("xb") as handle:
        handle.write(data)
    try:
        return storage.register_output(destination)
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def _preview_character(app: Any, character: dict[str, Any]) -> None:
    path = _safe_saved_path(character.get("image_path"))
    if path:
        app.image(str(path), caption=f"Saved character: {character.get('name', 'Character')}", use_container_width=True)
    else:
        app.info("No valid saved character reference image was found.")


def _show_outputs(app: Any) -> None:
    try:
        outputs = storage.list_outputs()
    except Exception as exc:
        app.error(f"Could not read registered outputs: {exc}")
        return
    for item in outputs:
        name = str(item.get("name", ""))
        if not name.startswith("motion_control_"):
            continue
        path = Path(item["path"])
        app.caption(f"{name} — expires in {item.get('remaining_seconds', '?')} seconds")
        if path.is_file():
            app.video(str(path))
            app.download_button(
                "Download motion output", path.read_bytes(), file_name=name,
                key=f"motion_download_{name}",
            )


def render(app: Any) -> None:
    """Render the Motion Control Studio page."""
    app.title("Motion Control Studio")
    app.caption("Prepare character motion-transfer jobs using reference media and prompts.")
    try:
        characters = list_available_characters(_current_user_id(app))
    except Exception as exc:
        app.error(f"Could not load saved characters: {exc}")
        return
    if not characters:
        app.warning("No saved characters found. Create one in Character Studio first.")
        return

    labels = {f"{c.get('name', 'Character')} (ID: {c.get('id')})": c for c in characters}
    selected = app.selectbox("Select saved character", list(labels), key="motion_character_select")
    character = labels[selected]
    left, right = app.columns([1, 2])
    with left:
        _preview_character(app, character)
    with right:
        app.subheader(str(character.get("name", "Character")))
        app.write(character.get("description") or "No character description saved.")
        app.caption(f"Character ID: {character.get('id')}")

    app.divider()
    app.subheader("Motion reference media")
    image_upload = app.file_uploader(
        "Reference image (optional)", type=["jpg", "jpeg", "png", "webp"],
        key="motion_reference_image_upload",
    )
    video_upload = app.file_uploader(
        "Motion reference video (optional)", type=["mp4", "mov", "webm", "mkv"],
        key="motion_reference_video_upload",
    )
    col_image, col_video = app.columns(2)
    with col_image:
        if image_upload is not None:
            app.image(image_upload, caption="Uploaded motion reference image", use_container_width=True)
    with col_video:
        if video_upload is not None:
            app.video(video_upload)

    app.subheader("Motion instructions")
    prompt = app.text_area(
        "Motion prompt", placeholder="Example: The character slowly turns toward the camera, then raises one hand.",
        max_chars=MAX_PROMPT_CHARS, height=110, key="motion_prompt",
    )
    intensity = app.slider(
        "Movement intensity", min_value=0.0, max_value=1.0, value=0.5,
        step=0.05, help="A requested engine setting; it does not animate the character here.",
        key="motion_intensity",
    )
    duration = app.slider(
        "Output duration (seconds)", min_value=MIN_DURATION, max_value=MAX_DURATION,
        value=5, step=1, key="motion_duration",
    )

    app.info(
        "Workflow preparation only: this module does not perform pose tracking, "
        "motion transfer, or video generation. A compatible local AI engine must "
        "be integrated to produce an animated result."
    )
    if app.button("Prepare Motion Workflow", type="primary", use_container_width=True):
        try:
            saved_image = save_reference_image(image_upload) if image_upload else None
            saved_video = save_reference_video(video_upload) if video_upload else None
            workflow = build_workflow(
                character=character, motion_prompt=prompt,
                movement_intensity=intensity, duration_seconds=duration,
                reference_image=saved_image, reference_video=saved_video,
            )
            app.session_state["motion_control_workflow"] = workflow
            app.success("Motion workflow validated. No AI inference has been run.")
        except (ValueError, OSError) as exc:
            app.error(str(exc))

    workflow = app.session_state.get("motion_control_workflow")
    if workflow:
        app.subheader("Prepared workflow")
        app.json(workflow)
        app.warning("Inference status: NOT RUN. No motion-transfer video has been generated.")

    app.divider()
    app.subheader("Generated motion output")
    _show_outputs(app)
