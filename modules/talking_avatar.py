"""Talking Avatar Studio UI and workflow preparation.

This module selects saved character profiles and collects dialogue/voice settings.
It does not synthesize speech, animate a face, or generate lip-synced video.
A separate local inference engine must provide those capabilities.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import config
import database
import storage

SUPPORTED_AUDIO = {"wav", "mp3", "ogg", "m4a"}
SUPPORTED_VIDEO = {"mp4", "webm", "mov"}
SUPPORTED_OUTPUT = SUPPORTED_AUDIO | SUPPORTED_VIDEO
MAX_DIALOGUE_CHARS = 5000

LANGUAGE_VOICES = {
    "English": ["English - Female 1", "English - Male 1"],
    "Hindi": ["Hindi - Female 1", "Hindi - Male 1"],
    "Hinglish": ["Hinglish - Female 1", "Hinglish - Male 1"],
    "Marathi": ["Marathi - Female 1", "Marathi - Male 1"],
}
EMOTIONS = [
    "Neutral", "Happy", "Sad", "Angry", "Excited", "Calm",
    "Fearful", "Confident", "Whispering",
]


def _current_user_id(app: Any) -> int | None:
    user = app.session_state.get("auth_user")
    if isinstance(user, dict) and user.get("id") is not None:
        try:
            return int(user["id"])
        except (TypeError, ValueError):
            return None
    return None


def resolve_character_image(image_path: str | None) -> Path | None:
    """Resolve a character reference only when it is inside assets/."""
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


def list_available_characters(user_id: int | None = None) -> list[dict[str, Any]]:
    """Return saved character records, optionally scoped to the signed-in user."""
    return database.list_characters(user_id=user_id)


def build_workflow(
    *, character: dict[str, Any], dialogue: str, language: str, voice: str,
    emotion: str, speed: float, pitch: float, volume: float,
    output_format: str,
) -> dict[str, Any]:
    """Validate and build settings; this does not run an AI model."""
    clean_dialogue = dialogue.strip()
    if not clean_dialogue:
        raise ValueError("Enter dialogue before preparing the workflow.")
    if len(clean_dialogue) > MAX_DIALOGUE_CHARS:
        raise ValueError(f"Dialogue must be {MAX_DIALOGUE_CHARS} characters or fewer.")
    if not character or character.get("id") is None:
        raise ValueError("Select a saved character first.")
    if language not in LANGUAGE_VOICES:
        raise ValueError("Choose a supported language.")
    if voice not in LANGUAGE_VOICES[language]:
        raise ValueError("Choose a voice that matches the selected language.")
    if emotion not in EMOTIONS:
        raise ValueError("Choose a supported emotion.")
    if not 0.7 <= float(speed) <= 1.3:
        raise ValueError("Speech speed must be between 0.7x and 1.3x.")
    if not -5.0 <= float(pitch) <= 5.0:
        raise ValueError("Pitch adjustment must be between -5 and +5.")
    if not 0.0 <= float(volume) <= 1.0:
        raise ValueError("Volume must be between 0 and 1.")
    extension = output_format.lower().lstrip(".")
    if extension not in SUPPORTED_OUTPUT:
        raise ValueError("Choose a supported audio or video output format.")

    return {
        "character_id": int(character["id"]),
        "character_name": str(character.get("name", "Character")),
        "character_image": character.get("image_path"),
        "dialogue": clean_dialogue,
        "language": language,
        "voice": voice,
        "emotion": emotion,
        "speed": round(float(speed), 2),
        "pitch": round(float(pitch), 2),
        "volume": round(float(volume), 2),
        "output_format": extension,
        "inference_status": "not_run",
    }


def save_generated_output(data: bytes, extension: str) -> dict[str, Any]:
    """Register real engine output in output/ so storage.py applies its 1-hour TTL.

    Call this only with bytes returned by a real synthesis/video inference engine.
    """
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise ValueError("Generated output is empty.")
    suffix = extension.lower().lstrip(".")
    if suffix not in SUPPORTED_OUTPUT:
        raise ValueError("Unsupported audio/video output format.")

    output_root = Path(config.OUTPUT_DIR).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    destination = output_root / f"talking_avatar_{uuid.uuid4().hex}.{suffix}"
    with destination.open("xb") as handle:
        handle.write(data)
    try:
        return storage.register_output(destination)
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def _render_character_preview(app: Any, character: dict[str, Any]) -> None:
    image_path = resolve_character_image(character.get("image_path"))
    if image_path:
        app.image(
            str(image_path), caption=f"Character reference: {character['name']}",
            use_container_width=True,
        )
    else:
        app.info("This character has no valid saved reference image.")


def _render_generated_outputs(app: Any) -> None:
    outputs = storage.list_outputs()
    matches = [
        item for item in outputs
        if Path(item["name"]).name.startswith("talking_avatar_")
    ]
    if not matches:
        app.info("No generated talking-avatar audio or video files yet.")
        return

    for item in matches:
        path = Path(item["path"])
        suffix = path.suffix.lower().lstrip(".")
        app.caption(f"{item['name']} — expires in {item['remaining_seconds']} seconds")
        if suffix in SUPPORTED_AUDIO:
            app.audio(str(path))
        elif suffix in SUPPORTED_VIDEO:
            app.video(str(path))
        with path.open("rb") as handle:
            app.download_button(
                "Download output", handle.read(), file_name=item["name"],
                key=f"talking_avatar_download_{item['name']}",
            )


def render(app: Any) -> None:
    """Render Talking Avatar Studio inside the main Streamlit app."""
    app.title("Talking Avatar Studio")
    app.caption(
        "Prepare dialogue and voice settings for a saved character. "
        "Speech synthesis, facial animation, and lip-sync require a real local engine."
    )

    try:
        characters = list_available_characters(_current_user_id(app))
    except Exception as exc:
        app.error(f"Could not load the character library: {exc}")
        return

    if not characters:
        app.warning("Your character library is empty. Create a character in Character Studio first.")
        return

    labels = {f"{item['name']} (ID: {item['id']})": item for item in characters}
    selected_label = app.selectbox(
        "Select saved character", list(labels.keys()),
        key="talking_avatar_character_select",
    )
    character = labels[selected_label]

    preview_col, details_col = app.columns([1, 2])
    with preview_col:
        _render_character_preview(app, character)
    with details_col:
        app.subheader(character["name"])
        app.write(character.get("description") or "No character description saved.")
        app.caption(f"Character ID: {character['id']}")

    app.divider()
    app.subheader("Dialogue and voice")
    dialogue = app.text_area(
        "Dialogue", placeholder="Type the words your character should say...",
        height=140, max_chars=MAX_DIALOGUE_CHARS,
        key="talking_avatar_dialogue",
    )

    col_a, col_b = app.columns(2)
    with col_a:
        language = app.selectbox(
            "Language", list(LANGUAGE_VOICES.keys()), key="talking_avatar_language"
        )
        voice = app.selectbox(
            "Voice", LANGUAGE_VOICES[language], key="talking_avatar_voice"
        )
        emotion = app.selectbox(
            "Emotion", EMOTIONS, key="talking_avatar_emotion"
        )
    with col_b:
        speed = app.slider(
            "Speech speed", min_value=0.7, max_value=1.3,
            value=1.0, step=0.05, key="talking_avatar_speed",
        )
        pitch = app.slider(
            "Pitch adjustment", min_value=-5.0, max_value=5.0,
            value=0.0, step=0.5, key="talking_avatar_pitch",
        )
        volume = app.slider(
            "Volume", min_value=0.0, max_value=1.0,
            value=0.85, step=0.05, key="talking_avatar_volume",
        )

    output_format = app.selectbox(
        "Desired output format", ["wav", "mp3", "mp4", "webm"],
        format_func=lambda value: value.upper(), key="talking_avatar_output_format",
    )

    app.info(
        "This screen is a workflow editor, not a generator. Saving settings does not "
        "create speech or animate the character. No model inference is run by this module."
    )

    if app.button("Prepare Talking Avatar Workflow", type="primary", use_container_width=True):
        try:
            workflow = build_workflow(
                character=character, dialogue=dialogue, language=language,
                voice=voice, emotion=emotion, speed=speed, pitch=pitch,
                volume=volume, output_format=output_format,
            )
            app.session_state["talking_avatar_workflow"] = workflow
            app.success("Workflow settings validated and saved in this session.")
        except ValueError as exc:
            app.error(str(exc))

    workflow = app.session_state.get("talking_avatar_workflow")
    if workflow:
        app.subheader("Prepared workflow")
        app.json(workflow)
        app.warning(
            "Inference status: NOT RUN. Connect a compatible local TTS/lip-sync engine "
            "before expecting audio or video output."
        )

    app.divider()
    app.subheader("Generated output preview")
    try:
        _render_generated_outputs(app)
    except Exception as exc:
        app.error(f"Could not load generated outputs: {exc}")
