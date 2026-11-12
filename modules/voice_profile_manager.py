
"""
File 62: modules/voice_profile_manager.py

AI Influencer Studio - Voice Profile Manager

Features:
- Create and manage character voice profiles
- Configure language and accent
- Configure pitch, speed, volume and emotion
- Save reference audio samples
- Assign profiles to characters
- Search, edit, duplicate and delete profiles
- Generate reusable voice direction prompts
- Export JSON and CSV
- Streamlit interface
- Built-in tests

Run:
    python -m modules.voice_profile_manager --test
"""

from __future__ import annotations

import csv
import json
import shutil
import tempfile
import uuid

from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
ASSET_DIR = BASE_DIR / "assets" / "voice_profiles"
OUTPUT_DIR = BASE_DIR / "outputs" / "voice_profiles"

DATABASE_FILE = DATA_DIR / "voice_profiles.json"

for folder in (DATA_DIR, ASSET_DIR, OUTPUT_DIR):
    folder.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _clean(value: Any, limit: int = 3000) -> str:
    return str(value or "").strip()[:limit]


def _read_database(
    database_path: Path | None = None
) -> dict:
    path = database_path or DATABASE_FILE

    if not path.exists():
        return {"profiles": []}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))

        if not isinstance(data, dict):
            return {"profiles": []}

        if not isinstance(data.get("profiles"), list):
            data["profiles"] = []

        return data

    except (OSError, json.JSONDecodeError):
        return {"profiles": []}


def _write_database(
    data: dict,
    database_path: Path | None = None
) -> None:
    path = database_path or DATABASE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_suffix(".tmp")

    temporary.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    temporary.replace(path)


def _find_profile(
    data: dict,
    profile_id: str
) -> dict | None:
    return next(
        (
            item for item in data["profiles"]
            if item.get("id") == profile_id
        ),
        None
    )


# ---------------------------------------------------------
# AUDIO REFERENCE STORAGE
# ---------------------------------------------------------

def save_audio_reference(
    source_path: str | Path,
    profile_id: str,
    destination_dir: Path | None = None
) -> str:
    source = Path(source_path)

    if not source.exists() or not source.is_file():
        raise FileNotFoundError("Audio reference not found.")

    allowed = {
        ".wav",
        ".mp3",
        ".ogg",
        ".m4a",
        ".flac"
    }

    if source.suffix.lower() not in allowed:
        raise ValueError("Unsupported audio format.")

    destination_dir = destination_dir or ASSET_DIR
    destination_dir.mkdir(parents=True, exist_ok=True)

    safe_name = "".join(
        char for char in source.name
        if char.isalnum() or char in "._-"
    )[:100]

    destination = destination_dir / (
        f"{profile_id}_{safe_name or 'sample.wav'}"
    )

    shutil.copy2(source, destination)

    return str(destination)


# ---------------------------------------------------------
# PROFILE CREATION
# ---------------------------------------------------------

def create_profile(
    character_name: str,
    profile_name: str,
    language: str = "English",
    accent: str = "",
    voice_type: str = "Neutral",
    pitch: int = 50,
    speed: float = 1.0,
    volume: int = 80,
    emotion: str = "Neutral",
    speaking_style: str = "",
    voice_description: str = "",
    pronunciation_notes: str = "",
    reference_audio: str | None = None,
    tags: list[str] | None = None,
    database_path: Path | None = None
) -> dict:
    """Create a voice profile."""

    character_name = _clean(character_name, 150)
    profile_name = _clean(profile_name, 150)

    if not character_name:
        raise ValueError("Character name is required.")

    if not profile_name:
        raise ValueError("Voice profile name is required.")

    if not 0 <= int(pitch) <= 100:
        raise ValueError("Pitch must be between 0 and 100.")

    if not 0.5 <= float(speed) <= 2.0:
        raise ValueError("Speed must be between 0.5 and 2.0.")

    if not 0 <= int(volume) <= 100:
        raise ValueError("Volume must be between 0 and 100.")

    data = _read_database(database_path)

    profile_id = _new_id()
    audio_path = None

    if reference_audio:
        audio_path = save_audio_reference(
            reference_audio,
            profile_id
        )

    profile = {
        "id": profile_id,
        "character_name": character_name,
        "profile_name": profile_name,
        "language": _clean(language, 100),
        "accent": _clean(accent, 150),
        "voice_type": _clean(voice_type, 100),
        "pitch": int(pitch),
        "speed": float(speed),
        "volume": int(volume),
        "emotion": _clean(emotion, 100),
        "speaking_style": _clean(speaking_style, 1000),
        "voice_description": _clean(
            voice_description, 2000
        ),
        "pronunciation_notes": _clean(
            pronunciation_notes, 2000
        ),
        "reference_audio": audio_path,
        "tags": [
            _clean(tag, 100)
            for tag in (tags or [])
            if _clean(tag, 100)
        ],
        "created_at": _now(),
        "updated_at": _now()
    }

    data["profiles"].append(profile)
    _write_database(data, database_path)

    return profile


# ---------------------------------------------------------
# PROFILE RETRIEVAL
# ---------------------------------------------------------

def list_profiles(
    character_name: str | None = None,
    database_path: Path | None = None
) -> list[dict]:
    data = _read_database(database_path)
    profiles = data["profiles"]

    if character_name:
        target = character_name.lower().strip()

        profiles = [
            item for item in profiles
            if item.get("character_name", "").lower()
            == target
        ]

    return sorted(
        profiles,
        key=lambda item: item.get("updated_at", ""),
        reverse=True
    )


def get_profile(
    profile_id: str,
    database_path: Path | None = None
) -> dict | None:
    data = _read_database(database_path)
    return _find_profile(data, profile_id)


# ---------------------------------------------------------
# UPDATE PROFILE
# ---------------------------------------------------------

def update_profile(
    profile_id: str,
    database_path: Path | None = None,
    **changes
) -> dict:
    allowed_fields = {
        "character_name",
        "profile_name",
        "language",
        "accent",
        "voice_type",
        "pitch",
        "speed",
        "volume",
        "emotion",
        "speaking_style",
        "voice_description",
        "pronunciation_notes",
        "tags"
    }

    data = _read_database(database_path)
    profile = _find_profile(data, profile_id)

    if not profile:
        raise ValueError("Voice profile not found.")

    for key, value in changes.items():

        if key not in allowed_fields:
            continue

        if key == "pitch":
            value = int(value)

            if not 0 <= value <= 100:
                raise ValueError("Pitch must be 0-100.")

        elif key == "speed":
            value = float(value)

            if not 0.5 <= value <= 2.0:
                raise ValueError("Speed must be 0.5-2.0.")

        elif key == "volume":
            value = int(value)

            if not 0 <= value <= 100:
                raise ValueError("Volume must be 0-100.")

        elif key == "tags":
            value = [
                _clean(tag, 100)
                for tag in (value or [])
                if _clean(tag, 100)
            ]

        else:
            value = _clean(value)

        profile[key] = value

    if not profile.get("character_name"):
        raise ValueError("Character name cannot be empty.")

    if not profile.get("profile_name"):
        raise ValueError("Profile name cannot be empty.")

    profile["updated_at"] = _now()

    _write_database(data, database_path)

    return profile


# ---------------------------------------------------------
# DUPLICATE AND DELETE
# ---------------------------------------------------------

def duplicate_profile(
    profile_id: str,
    database_path: Path | None = None
) -> dict:
    data = _read_database(database_path)
    original = _find_profile(data, profile_id)

    if not original:
        raise ValueError("Voice profile not found.")

    duplicate = dict(original)

    duplicate["id"] = _new_id()
    duplicate["profile_name"] += " Copy"
    duplicate["created_at"] = _now()
    duplicate["updated_at"] = _now()

    data["profiles"].append(duplicate)

    _write_database(data, database_path)

    return duplicate


def delete_profile(
    profile_id: str,
    database_path: Path | None = None
) -> bool:
    data = _read_database(database_path)
    profile = _find_profile(data, profile_id)

    if not profile:
        return False

    data["profiles"] = [
        item for item in data["profiles"]
        if item.get("id") != profile_id
    ]

    audio_path = profile.get("reference_audio")

    # Avoid deleting audio shared by a duplicate profile.
    if audio_path:
        still_used = any(
            item.get("reference_audio") == audio_path
            for item in data["profiles"]
        )

        if not still_used:
            try:
                Path(audio_path).unlink(missing_ok=True)
            except OSError:
                pass

    _write_database(data, database_path)

    return True


# ---------------------------------------------------------
# SEARCH
# ---------------------------------------------------------

def search_profiles(
    query: str,
    database_path: Path | None = None
) -> list[dict]:
    query = _clean(query).lower()

    if not query:
        return list_profiles(database_path=database_path)

    results = []

    for profile in list_profiles(
        database_path=database_path
    ):
        searchable = " ".join([
            profile.get("character_name", ""),
            profile.get("profile_name", ""),
            profile.get("language", ""),
            profile.get("accent", ""),
            profile.get("voice_type", ""),
            profile.get("emotion", ""),
            profile.get("voice_description", ""),
            " ".join(profile.get("tags", []))
        ]).lower()

        if query in searchable:
            results.append(profile)

    return results


# ---------------------------------------------------------
# VOICE PROMPT GENERATOR
# ---------------------------------------------------------

def build_voice_prompt(
    profile_id: str,
    database_path: Path | None = None
) -> str:
    profile = get_profile(
        profile_id,
        database_path
    )

    if not profile:
        raise ValueError("Voice profile not found.")

    lines = [
        f"Character: {profile['character_name']}",
        f"Voice identity: {profile['profile_name']}",
        f"Language: {profile['language']}",
        f"Accent: {profile['accent']}",
        f"Voice type: {profile['voice_type']}",
        f"Pitch setting: {profile['pitch']}/100",
        f"Speaking speed: {profile['speed']}x",
        f"Volume setting: {profile['volume']}/100",
        f"Emotion: {profile['emotion']}",
        f"Speaking style: {profile['speaking_style']}",
        f"Voice description: {profile['voice_description']}",
        (
            "Pronunciation notes: "
            + profile["pronunciation_notes"]
        )
    ]

    return "\n".join(
        line for line in lines
        if line.split(":", 1)[-1].strip()
    )


# ---------------------------------------------------------
# STATISTICS
# ---------------------------------------------------------

def get_statistics(
    database_path: Path | None = None
) -> dict:
    profiles = list_profiles(
        database_path=database_path
    )

    characters = {
        item.get("character_name")
        for item in profiles
    }

    languages = {}

    for profile in profiles:
        language = profile.get("language", "Unknown")
        languages[language] = (
            languages.get(language, 0) + 1
        )

    return {
        "total_profiles": len(profiles),
        "total_characters": len(characters),
        "profiles_with_audio": sum(
            1 for item in profiles
            if item.get("reference_audio")
        ),
        "languages": languages
    }


# ---------------------------------------------------------
# EXPORT
# ---------------------------------------------------------

def export_json(
    database_path: Path | None = None,
    output_path: Path | None = None
) -> Path:
    data = _read_database(database_path)

    output_path = output_path or (
        OUTPUT_DIR / f"voice_profiles_{_now().replace(':', '-')}.json"
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    output_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    return output_path


def export_csv(
    database_path: Path | None = None,
    output_path: Path | None = None
) -> Path:
    profiles = list_profiles(
        database_path=database_path
    )

    output_path = output_path or (
        OUTPUT_DIR / f"voice_profiles_{_now().replace(':', '-')}.csv"
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    fields = [
        "id",
        "character_name",
        "profile_name",
        "language",
        "accent",
        "voice_type",
        "pitch",
        "speed",
        "volume",
        "emotion",
        "speaking_style",
        "voice_description",
        "pronunciation_notes",
        "reference_audio",
        "created_at",
        "updated_at"
    ]

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fields,
            extrasaction="ignore"
        )

        writer.writeheader()
        writer.writerows(profiles)

    return output_path


# ---------------------------------------------------------
# STREAMLIT INTERFACE
# ---------------------------------------------------------

def render() -> None:
    import streamlit as st

    st.title("Voice Profile Manager")

    st.caption(
        "Create consistent voice settings for your AI characters."
    )

    create_tab, library_tab, export_tab = st.tabs([
        "Create Voice",
        "Voice Library",
        "Export"
    ])

    # -----------------------------------------------------
    # CREATE
    # -----------------------------------------------------

    with create_tab:
        st.subheader("Create Character Voice Profile")

        with st.form("voice_profile_create_form"):

            character = st.text_input(
                "Character Name",
                placeholder="Example: Eira"
            )

            profile_name = st.text_input(
                "Voice Profile Name",
                placeholder="Example: Eira Main Voice"
            )

            language = st.selectbox(
                "Language",
                [
                    "English",
                    "Hindi",
                    "Hinglish",
                    "Marathi",
                    "Spanish",
                    "French",
                    "German",
                    "Other"
                ]
            )

            accent = st.text_input(
                "Accent",
                placeholder="Example: Indian English"
            )

            voice_type = st.selectbox(
                "Voice Type",
                [
                    "Neutral",
                    "Deep Male",
                    "Soft Male",
                    "Female",
                    "Deep Female",
                    "Child",
                    "Narrator",
                    "Elderly",
                    "Custom"
                ]
            )

            pitch = st.slider(
                "Pitch",
                min_value=0,
                max_value=100,
                value=50
            )

            speed = st.slider(
                "Speaking Speed",
                min_value=0.5,
                max_value=2.0,
                value=1.0,
                step=0.05
            )

            volume = st.slider(
                "Volume",
                min_value=0,
                max_value=100,
                value=80
            )

            emotion = st.selectbox(
                "Default Emotion",
                [
                    "Neutral",
                    "Happy",
                    "Sad",
                    "Angry",
                    "Fearful",
                    "Whispering",
                    "Confident",
                    "Mysterious",
                    "Cinematic",
                    "Dramatic"
                ]
            )

            speaking_style = st.text_area(
                "Speaking Style",
                placeholder=(
                    "Slow cinematic delivery, "
                    "clear pronunciation and controlled pauses."
                )
            )

            description = st.text_area(
                "Voice Description",
                placeholder=(
                    "Warm, deep and natural voice "
                    "with a cinematic tone."
                )
            )

            pronunciation = st.text_area(
                "Pronunciation Notes"
            )

            tags_text = st.text_input(
                "Tags",
                placeholder="narrator, fantasy, cinematic"
            )

            uploaded_audio = st.file_uploader(
                "Reference Audio Sample",
                type=["wav", "mp3", "ogg", "m4a", "flac"]
            )

            submitted = st.form_submit_button(
                "Save Voice Profile",
                type="primary"
            )

            if submitted:
                try:
                    audio_path = None

                    if uploaded_audio:
                        temporary_dir = (
                            ASSET_DIR / "uploads"
                        )
                        temporary_dir.mkdir(
                            parents=True,
                            exist_ok=True
                        )

                        temporary_path = (
                            temporary_dir
                            / f"{uuid.uuid4().hex}_{Path(uploaded_audio.name).name}"
                        )

                        temporary_path.write_bytes(
                            uploaded_audio.getvalue()
                        )

                        audio_path = str(temporary_path)

                    profile = create_profile(
                        character_name=character,
                        profile_name=profile_name,
                        language=language,
                        accent=accent,
                        voice_type=voice_type,
                        pitch=pitch,
                        speed=speed,
                        volume=volume,
                        emotion=emotion,
                        speaking_style=speaking_style,
                        voice_description=description,
                        pronunciation_notes=pronunciation,
                        reference_audio=audio_path,
                        tags=[
                            tag.strip()
                            for tag in tags_text.split(",")
                            if tag.strip()
                        ]
                    )

                    st.success(
                        "Voice profile saved: "
                        + profile["profile_name"]
                    )

                except Exception as exc:
                    st.error(f"Could not save profile: {exc}")

    # -----------------------------------------------------
    # LIBRARY
    # -----------------------------------------------------

    with library_tab:
        st.subheader("Saved Voice Profiles")

        query = st.text_input(
            "Search voice profiles"
        )

        profiles = (
            search_profiles(query)
            if query
            else list_profiles()
        )

        stats = get_statistics()

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Voice Profiles",
            stats["total_profiles"]
        )

        col2.metric(
            "Characters",
            stats["total_characters"]
        )

        col3.metric(
            "Audio Samples",
            stats["profiles_with_audio"]
        )

        if not profiles:
            st.info("No voice profiles found.")

        for profile in profiles:
            with st.expander(
                f"{profile['character_name']} — "
                f"{profile['profile_name']}"
            ):
                st.write(
                    f"**Language:** {profile['language']}"
                )

                st.write(
                    f"**Accent:** {profile['accent'] or '-'}"
                )

                st.write(
                    f"**Voice Type:** {profile['voice_type']}"
                )

                st.write(
                    f"**Emotion:** {profile['emotion']}"
                )

                st.write(
                    f"**Pitch:** {profile['pitch']}/100"
                )

                st.write(
                    f"**Speed:** {profile['speed']}x"
                )

                st.write(
                    f"**Volume:** {profile['volume']}/100"
                )

                st.write(
                    profile.get("voice_description", "")
                )

                audio_path = profile.get("reference_audio")

                if audio_path and Path(audio_path).is_file():
                    st.audio(audio_path)

                prompt = build_voice_prompt(profile["id"])

                st.text_area(
                    "Voice Direction Prompt",
                    value=prompt,
                    height=200,
                    key=f"voice_prompt_{profile['id']}"
                )

                st.download_button(
                    "Download Voice Prompt",
                    data=prompt,
                    file_name=(
                        f"{profile['profile_name']}.txt"
                    ),
                    mime="text/plain",
                    key=f"voice_download_{profile['id']}"
                )

                with st.form(
                    f"voice_edit_{profile['id']}"
                ):
                    new_name = st.text_input(
                        "Profile Name",
                        value=profile["profile_name"],
                        key=f"voice_name_{profile['id']}"
                    )

                    new_emotion = st.selectbox(
                        "Default Emotion",
                        [
                            "Neutral",
                            "Happy",
                            "Sad",
                            "Angry",
                            "Fearful",
                            "Whispering",
                            "Confident",
                            "Mysterious",
                            "Cinematic",
                            "Dramatic"
                        ],
                        index=(
                            [
                                "Neutral",
                                "Happy",
                                "Sad",
                                "Angry",
                                "Fearful",
                                "Whispering",
                                "Confident",
                                "Mysterious",
                                "Cinematic",
                                "Dramatic"
                            ].index(profile["emotion"])
                            if profile["emotion"] in [
                                "Neutral",
                                "Happy",
                                "Sad",
                                "Angry",
                                "Fearful",
                                "Whispering",
                                "Confident",
                                "Mysterious",
                                "Cinematic",
                                "Dramatic"
                            ]
                            else 0
                        ),
                        key=f"voice_emotion_{profile['id']}"
                    )

                    new_speed = st.number_input(
                        "Speed",
                        min_value=0.5,
                        max_value=2.0,
                        value=float(profile["speed"]),
                        step=0.05,
                        key=f"voice_speed_{profile['id']}"
                    )

                    edit = st.form_submit_button(
                        "Update Profile"
                    )

                    if edit:
                        try:
                            update_profile(
                                profile["id"],
                                profile_name=new_name,
                                emotion=new_emotion,
                                speed=new_speed
                            )

                            st.success("Profile updated.")
                            st.rerun()

                        except Exception as exc:
                            st.error(str(exc))

                col_a, col_b = st.columns(2)

                with col_a:
                    if st.button(
                        "Duplicate",
                        key=f"voice_duplicate_{profile['id']}"
                    ):
                        duplicate_profile(profile["id"])
                        st.success("Profile duplicated.")
                        st.rerun()

                with col_b:
                    if st.button(
                        "Delete",
                        key=f"voice_delete_{profile['id']}"
                    ):
                        st.session_state[
                            "delete_voice_profile"
                        ] = profile["id"]

                if st.session_state.get(
                    "delete_voice_profile"
                ) == profile["id"]:

                    st.warning(
                        "Confirm deletion of this voice profile."
                    )

                    if st.button(
                        "Confirm Delete",
                        key=f"voice_confirm_{profile['id']}"
                    ):
                        delete_profile(profile["id"])

                        st.session_state.pop(
                            "delete_voice_profile",
                            None
                        )

                        st.success("Profile deleted.")
                        st.rerun()

    # -----------------------------------------------------
    # EXPORT
    # -----------------------------------------------------

    with export_tab:
        st.subheader("Export Voice Profiles")

        if st.button("Generate JSON"):
            try:
                path = export_json()

                st.download_button(
                    "Download JSON",
                    data=path.read_bytes(),
                    file_name=path.name,
                    mime="application/json"
                )

            except Exception as exc:
                st.error(str(exc))

        if st.button("Generate CSV"):
            try:
                path = export_csv()

                st.download_button(
                    "Download CSV",
                    data=path.read_bytes(),
                    file_name=path.name,
                    mime="text/csv"
                )

            except Exception as exc:
                st.error(str(exc))


# ---------------------------------------------------------
# BUILT-IN TESTS
# ---------------------------------------------------------

def run_tests() -> None:
    print("Running Voice Profile Manager tests...")

    with tempfile.TemporaryDirectory() as temp:
        database = Path(temp) / "test_voice.json"

        # Create profile.
        profile = create_profile(
            character_name="Eira",
            profile_name="Eira Cinematic Voice",
            language="English",
            accent="Indian English",
            voice_type="Female",
            pitch=45,
            speed=0.9,
            volume=80,
            emotion="Mysterious",
            speaking_style="Slow cinematic narration",
            voice_description="Soft and clear voice",
            database_path=database
        )

        assert profile["character_name"] == "Eira"
        assert profile["speed"] == 0.9

        # Retrieve profile.
        found = get_profile(
            profile["id"],
            database
        )

        assert found is not None

        # Update profile.
        update_profile(
            profile["id"],
            database_path=database,
            emotion="Dramatic",
            speed=1.1
        )

        updated = get_profile(
            profile["id"],
            database
        )

        assert updated["emotion"] == "Dramatic"
        assert updated["speed"] == 1.1

        # Search.
        results = search_profiles(
            "Eira",
            database
        )

        assert len(results) == 1

        # Prompt generation.
        prompt = build_voice_prompt(
            profile["id"],
            database
        )

        assert "Eira" in prompt
        assert "English" in prompt

        # Duplicate.
        duplicate = duplicate_profile(
            profile["id"],
            database
        )

        assert duplicate["id"] != profile["id"]

        # Statistics.
        stats = get_statistics(database)

        assert stats["total_profiles"] == 2
        assert stats["total_characters"] == 1

        # Export.
        json_path = Path(temp) / "voices.json"
        csv_path = Path(temp) / "voices.csv"

        export_json(database, json_path)
        export_csv(database, csv_path)

        assert json_path.exists()
        assert csv_path.exists()

        # Delete.
        assert delete_profile(
            profile["id"],
            database
        )

        assert get_profile(
            profile["id"],
            database
        ) is None

        # Validation.
        try:
            create_profile(
                character_name="Test",
                profile_name="Invalid",
                pitch=120,
                database_path=database
            )
            raise AssertionError("Invalid pitch was accepted.")

        except ValueError:
            pass

    print("All Voice Profile Manager tests passed.")


# ---------------------------------------------------------
# COMMAND LINE
# ---------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Voice Profile Manager"
    )

    parser.add_argument(
        "--test",
        action="store_true"
    )

    args = parser.parse_args()

    if args.test:
        run_tests()
    else:
        print("Voice Profile Manager")
        print("Use --test to run built-in tests.")
