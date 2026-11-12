"""Character Studio UI and persistent reference-image handling.

This module manages character profiles and reference images only. It does not
perform text-to-image generation; that requires a separately installed model.
"""
from __future__ import annotations

import io
import re
import uuid
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError

import config
import database

ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_IMAGE_BYTES = config.MAX_IMAGE_UPLOAD_MB * 1024 * 1024
MAX_IMAGE_DIMENSION = 2048


def _safe_asset_directory() -> Path:
    """Create and return the persistent character-image directory."""
    root = Path(config.ASSETS_DIR).resolve()
    directory = (root / "characters").resolve()
    if directory != root and root not in directory.parents:
        raise ValueError("Character asset directory must stay inside assets/.")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _safe_character_name(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip()).strip("_-")
    return name[:40] or "character"


def save_reference_image(
    image_bytes: bytes,
    character_name: str,
) -> str:
    """Validate and normalize an uploaded image into persistent assets/.

    The image is re-encoded as JPEG, which strips metadata and avoids trusting
    the uploaded filename or extension. Returns a project-relative path.
    """
    if not isinstance(image_bytes, (bytes, bytearray)) or not image_bytes:
        raise ValueError("Please upload a non-empty image.")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise ValueError(
            f"Image is too large. Maximum size is {config.MAX_IMAGE_UPLOAD_MB} MB."
        )

    try:
        with Image.open(io.BytesIO(image_bytes)) as probe:
            image_format = (probe.format or "").upper()
            if image_format not in ALLOWED_IMAGE_FORMATS:
                raise ValueError("Use a JPEG, PNG, or WEBP image.")
            probe.verify()

        with Image.open(io.BytesIO(image_bytes)) as source:
            image = ImageOps.exif_transpose(source)
            image.load()
            if image.width < 1 or image.height < 1:
                raise ValueError("The uploaded image has invalid dimensions.")
            image.thumbnail(
                (MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION),
                Image.Resampling.LANCZOS,
            )
            if image.mode not in ("RGB", "L"):
                # Flatten transparency against a neutral background.
                if "A" in image.getbands():
                    rgba = image.convert("RGBA")
                    background = Image.new("RGBA", rgba.size, "white")
                    image = Image.alpha_composite(background, rgba).convert("RGB")
                else:
                    image = image.convert("RGB")
            elif image.mode == "L":
                image = image.convert("RGB")

            directory = _safe_asset_directory()
            filename = (
                f"{_safe_character_name(character_name)}_"
                f"{uuid.uuid4().hex[:12]}.jpg"
            )
            destination = directory / filename
            temporary = directory / f".{filename}.tmp"
            try:
                image.save(temporary, format="JPEG", quality=88, optimize=True)
                temporary.replace(destination)
            finally:
                if temporary.exists():
                    temporary.unlink(missing_ok=True)

            return destination.relative_to(Path(config.BASE_DIR).resolve()).as_posix()

    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("The uploaded file is not a valid supported image.") from exc


def resolve_character_image(image_path: str | None) -> Path | None:
    """Resolve a database image path, allowing files only under assets/."""
    if not image_path:
        return None
    base = Path(config.BASE_DIR).resolve()
    assets = Path(config.ASSETS_DIR).resolve()
    candidate = (base / image_path).resolve()
    if assets not in candidate.parents or candidate.is_symlink():
        return None
    if not candidate.is_file():
        return None
    return candidate


def build_character_description(appearance: str, prompt: str) -> str:
    parts = []
    if appearance.strip():
        parts.append(f"Appearance: {appearance.strip()}")
    if prompt.strip():
        parts.append(f"Character prompt: {prompt.strip()}")
    return "\n".join(parts)


def create_character_record(
    *,
    name: str,
    age: int,
    appearance: str,
    style: str,
    prompt: str,
    image_bytes: bytes | None = None,
    user_id: int | None = None,
) -> int:
    """Persist a character profile and optional reference image safely."""
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Character name is required.")
    if not 1 <= int(age) <= 120:
        raise ValueError("Age must be between 1 and 120.")
    if not appearance.strip():
        raise ValueError("Please describe the character's appearance.")
    if not style.strip():
        raise ValueError("Please select a visual style.")

    saved_image_path: str | None = None
    if image_bytes:
        saved_image_path = save_reference_image(image_bytes, clean_name)

    settings = {
        "age": int(age),
        "appearance": appearance.strip(),
        "style": style.strip(),
        "prompt": prompt.strip(),
        "reference_image": bool(saved_image_path),
    }

    try:
        return database.create_character(
            clean_name,
            user_id=user_id,
            description=build_character_description(appearance, prompt),
            image_path=saved_image_path,
            settings=settings,
        )
    except Exception:
        # Avoid leaving an unreferenced image if the database insert fails.
        if saved_image_path:
            image_file = resolve_character_image(saved_image_path)
            if image_file:
                image_file.unlink(missing_ok=True)
        raise


def _current_user_id() -> int | None:
    try:
        import streamlit as st
        user = st.session_state.get("auth_user")
        if isinstance(user, dict) and user.get("id"):
            return int(user["id"])
    except Exception:
        pass
    return None


def render(st: Any) -> None:
    """Render the Character Studio inside the main Streamlit application."""
    st.title("Character Studio")
    st.caption(
        "Create persistent character profiles and organize reference images. "
        "This module stores prompts; it does not generate images by itself."
    )

    create_tab, library_tab = st.tabs(["Create Character", "Character Library"])

    with create_tab:
        with st.form("character_create_form", clear_on_submit=False):
            name = st.text_input("Character name", max_chars=80)
            age = st.number_input("Age", min_value=1, max_value=120, value=25, step=1)
            appearance = st.text_area(
                "Appearance",
                placeholder="Describe face, hair, body type, clothing, and distinguishing features...",
                height=110,
            )
            style = st.selectbox(
                "Visual style",
                [
                    "Photorealistic",
                    "Cinematic 3D",
                    "Anime",
                    "Stylized 3D",
                    "Illustration",
                    "Fashion editorial",
                    "Custom",
                ],
            )
            prompt = st.text_area(
                "Character prompt",
                placeholder="Write a reusable prompt describing the character...",
                height=110,
            )
            uploaded = st.file_uploader(
                "Reference image (optional)",
                type=["jpg", "jpeg", "png", "webp"],
                help=f"Maximum {config.MAX_IMAGE_UPLOAD_MB} MB. Saved permanently in assets/characters/.",
            )
            submitted = st.form_submit_button(
                "Save Character", type="primary", use_container_width=True
            )

        if submitted:
            try:
                image_bytes = uploaded.getvalue() if uploaded is not None else None
                character_id = create_character_record(
                    name=name,
                    age=int(age),
                    appearance=appearance,
                    style=style,
                    prompt=prompt,
                    image_bytes=image_bytes,
                    user_id=_current_user_id(),
                )
                st.success(f"Character saved successfully. ID: {character_id}")
            except (ValueError, OSError) as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"Could not save character: {exc}")

    with library_tab:
        try:
            characters = database.list_characters(user_id=_current_user_id())
        except Exception as exc:
            st.error(f"Could not load character library: {exc}")
            return

        if not characters:
            st.info("Your character library is empty. Create your first character.")
            return

        labels = {
            f"{item['name']} (ID: {item['id']})": item for item in characters
        }
        selected_label = st.selectbox(
            "Select a saved character", list(labels.keys()),
            key="character_library_selection",
        )
        selected = labels[selected_label]
        image_file = resolve_character_image(selected.get("image_path"))

        left, right = st.columns([1, 2])
        with left:
            if image_file:
                st.image(str(image_file), caption=selected["name"], use_container_width=True)
            else:
                st.info("No reference image saved for this character.")
        with right:
            settings = selected.get("settings", {})
            st.subheader(selected["name"])
            st.write(f"**Age:** {settings.get('age', 'Not specified')}")
            st.write(f"**Style:** {settings.get('style', 'Not specified')}")
            st.write("**Appearance**")
            st.write(settings.get("appearance", selected.get("description", "")))
            st.write("**Character prompt**")
            st.write(settings.get("prompt", "Not specified"))
            st.caption(f"Character ID: {selected['id']}")

        if st.button("Use selected character", use_container_width=True):
            st.session_state["selected_character_id"] = selected["id"]
            st.session_state["selected_character"] = selected
            st.success(f"Selected {selected['name']} for your next workflow.")
