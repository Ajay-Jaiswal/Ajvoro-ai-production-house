"""Lightweight Voice Studio workflow UI.

This module prepares TTS settings and previews real engine outputs. It does not
synthesize speech. Connect a local TTS engine before calling save_generated_audio.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

LANGUAGE_VOICES = {
    "English": {"Male": ["English Male 1", "English Male 2"], "Female": ["English Female 1", "English Female 2"]},
    "Hindi": {"Male": ["Hindi Male 1", "Hindi Male 2"], "Female": ["Hindi Female 1", "Hindi Female 2"]},
    "Hinglish": {"Male": ["Hinglish Male 1"], "Female": ["Hinglish Female 1"]},
    "Marathi": {"Male": ["Marathi Male 1"], "Female": ["Marathi Female 1"]},
}
EMOTIONS = ["Neutral", "Happy", "Sad", "Angry", "Excited", "Calm", "Fearful", "Confident", "Whispering"]
AUDIO_FORMATS = {"wav": "audio/wav", "mp3": "audio/mpeg", "ogg": "audio/ogg", "flac": "audio/flac"}
MAX_TEXT_CHARS = 12000
MAX_BATCH_LINES = 50


def split_batch_dialogue(text: str) -> list[str]:
    """Treat each non-empty line as one batch utterance."""
    if not isinstance(text, str):
        raise ValueError("Dialogue must be text.")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("Enter at least one dialogue line.")
    if len(lines) > MAX_BATCH_LINES:
        raise ValueError(f"Batch supports at most {MAX_BATCH_LINES} non-empty lines.")
    if sum(map(len, lines)) > MAX_TEXT_CHARS:
        raise ValueError(f"Total dialogue must not exceed {MAX_TEXT_CHARS} characters.")
    return lines


def build_tts_workflow(*, dialogue: str, language: str, gender: str, voice: str,
                       emotion: str, speed: float, pitch: float, volume: float,
                       output_format: str, batch_mode: bool = False) -> dict[str, Any]:
    """Validate UI settings and return a serializable TTS job description."""
    if language not in LANGUAGE_VOICES:
        raise ValueError("Select a supported language.")
    if gender not in LANGUAGE_VOICES[language]:
        raise ValueError("Select Male or Female voice type.")
    if voice not in LANGUAGE_VOICES[language][gender]:
        raise ValueError("The selected voice does not match the language and voice type.")
    if emotion not in EMOTIONS:
        raise ValueError("Select a supported emotion.")
    if not 0.7 <= float(speed) <= 1.3:
        raise ValueError("Speed must be between 0.7x and 1.3x.")
    if not -5.0 <= float(pitch) <= 5.0:
        raise ValueError("Pitch must be between -5 and +5.")
    if not 0.0 <= float(volume) <= 1.0:
        raise ValueError("Volume must be between 0 and 1.")
    fmt = str(output_format).lower().lstrip(".")
    if fmt not in AUDIO_FORMATS:
        raise ValueError("Choose WAV, MP3, OGG or FLAC output.")
    utterances = split_batch_dialogue(dialogue) if batch_mode else [dialogue.strip()]
    if not batch_mode and (not utterances[0] or len(utterances[0]) > MAX_TEXT_CHARS):
        raise ValueError("Enter dialogue text (up to 12,000 characters).")
    return {
        "job_id": uuid.uuid4().hex,
        "dialogue": dialogue.strip(),
        "utterances": utterances,
        "batch_mode": bool(batch_mode),
        "language": language,
        "gender": gender,
        "voice": voice,
        "emotion": emotion,
        "speed": round(float(speed), 2),
        "pitch": round(float(pitch), 2),
        "volume": round(float(volume), 2),
        "output_format": fmt,
        "inference_status": "not_run",
    }


def save_generated_audio(data: bytes, extension: str) -> dict[str, Any]:
    """Persist genuine TTS engine bytes and register them for one-hour cleanup."""
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise ValueError("Generated audio is empty.")
    fmt = str(extension).lower().lstrip(".")
    if fmt not in AUDIO_FORMATS:
        raise ValueError("Unsupported audio format.")

    import config  # imported only when the integrated app calls this helper
    import storage

    root = Path(config.OUTPUT_DIR).resolve()
    root.mkdir(parents=True, exist_ok=True)
    target = root / f"voice_studio_{uuid.uuid4().hex}.{fmt}"
    with target.open("xb") as stream:
        stream.write(data)
    try:
        return storage.register_output(target)
    except Exception:
        target.unlink(missing_ok=True)
        raise


def _get_characters(user_id: int | None) -> list[dict[str, Any]]:
    import database
    return database.list_characters(user_id=user_id)


def _user_id(app: Any) -> int | None:
    user = app.session_state.get("auth_user")
    if isinstance(user, dict) and user.get("id") is not None:
        try:
            return int(user["id"])
        except (ValueError, TypeError):
            return None
    return None


def _show_outputs(app: Any) -> None:
    import storage
    for item in storage.list_outputs():
        path = Path(item.get("path", ""))
        if not path.is_file() or not path.name.startswith("voice_studio_"):
            continue
        app.caption(f"{path.name} · expires in {item.get('remaining_seconds', '?')} seconds")
        app.audio(str(path))
        app.download_button("Download audio", path.read_bytes(), file_name=path.name,
                            key=f"voice_download_{path.name}")


def render(app: Any) -> None:
    """Render Voice Studio in the parent Streamlit application."""
    app.title("Voice Studio")
    app.caption("Prepare TTS jobs and preview real generated audio. No speech is synthesized by this interface alone.")

    try:
        characters = _get_characters(_user_id(app))
    except Exception as exc:
        app.error(f"Could not load saved characters: {exc}")
        characters = []
    if characters:
        labels = {f"{c.get('name', 'Character')} (ID {c.get('id')})": c for c in characters}
        selected = app.selectbox("Optional character", ["No character"] + list(labels), key="voice_character")
        if selected != "No character":
            c = labels[selected]
            app.write(f"Selected character: **{c.get('name', 'Character')}**")
            image_path = c.get("image_path")
            if image_path:
                try:
                    import config
                    base = Path(config.BASE_DIR).resolve()
                    assets = Path(config.ASSETS_DIR).resolve()
                    candidate = (base / image_path).resolve()
                    if assets in candidate.parents and candidate.is_file() and not candidate.is_symlink():
                        app.image(str(candidate), width=220)
                except Exception:
                    app.caption("Character reference image could not be previewed.")
    else:
        app.info("No saved characters found. You can still prepare a voice-only workflow.")

    dialogue = app.text_area("Dialogue (one line per utterance for batch mode)", height=180,
                             max_chars=MAX_TEXT_CHARS, key="voice_dialogue")
    batch = app.checkbox("Batch mode — generate one audio file per non-empty line", value=False)
    left, right = app.columns(2)
    with left:
        language = app.selectbox("Language", list(LANGUAGE_VOICES), key="voice_language")
        gender = app.selectbox("Voice type", ["Male", "Female"], key="voice_gender")
        voice = app.selectbox("Voice", LANGUAGE_VOICES[language][gender], key="voice_choice")
        emotion = app.selectbox("Emotion", EMOTIONS, key="voice_emotion")
    with right:
        speed = app.slider("Speed", 0.7, 1.3, 1.0, 0.05, key="voice_speed")
        pitch = app.slider("Pitch", -5.0, 5.0, 0.0, 0.5, key="voice_pitch")
        volume = app.slider("Volume", 0.0, 1.0, 0.85, 0.05, key="voice_volume")
        output_format = app.selectbox("Audio format", list(AUDIO_FORMATS), format_func=str.upper,
                                      key="voice_format")

    app.info("Workflow preparation only: connect a compatible local TTS engine to produce actual audio. Voice names are configuration labels, not installed voices.")
    if app.button("Prepare TTS Workflow", type="primary", use_container_width=True):
        try:
            job = build_tts_workflow(dialogue=dialogue, language=language, gender=gender,
                                     voice=voice, emotion=emotion, speed=speed, pitch=pitch,
                                     volume=volume, output_format=output_format, batch_mode=batch)
            app.session_state["voice_studio_job"] = job
            app.success(f"Validated workflow with {len(job['utterances'])} utterance(s). No inference was run.")
        except ValueError as exc:
            app.error(str(exc))

    job = app.session_state.get("voice_studio_job")
    if job:
        app.subheader("Prepared TTS job")
        app.json(job)
        app.warning("Inference status: NOT RUN. Audio will appear here only after a real TTS engine generates and registers it.")

    app.divider()
    app.subheader("Generated audio preview")
    try:
        _show_outputs(app)
    except Exception as exc:
        app.error(f"Could not load generated audio: {exc}")
