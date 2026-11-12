
"""
AI Influencer Studio
File 39: modules/audio_mixer.py

Professional Audio Mixer and Audio Track Manager.

This module manages audio assets and mixing metadata.
It does not perform actual audio rendering or mixing.
Actual rendering can be integrated with FFmpeg later.
"""

from __future__ import annotations

import json
import re
import uuid

from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------
# OPTIONAL INTEGRATION
# ---------------------------------------------------------

try:
    from modules import timeline_editor
except ImportError:
    timeline_editor = None

try:
    from modules import asset_manager
except ImportError:
    asset_manager = None


# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT_DIR / "data"
AUDIO_DIR = ROOT_DIR / "assets" / "audio"
EXPORT_DIR = ROOT_DIR / "outputs" / "audio_mixes"

DATABASE_FILE = DATA_DIR / "audio_mixer.json"

SUPPORTED_AUDIO = {
    ".mp3",
    ".wav",
    ".ogg",
    ".m4a",
    ".aac",
    ".flac",
    ".wma",
}


# ---------------------------------------------------------
# AUDIO TRACK TYPES
# ---------------------------------------------------------

TRACK_TYPES = [
    "Background Music",
    "Voice Over",
    "Dialogue",
    "Sound Effects",
    "Ambience",
    "Custom",
]

PAN_MODES = [
    "Center",
    "Left",
    "Right",
]

EASING_TYPES = [
    "linear",
    "ease-in",
    "ease-out",
    "ease-in-out",
]


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _id() -> str:
    return uuid.uuid4().hex[:12]


def _clean(value: Any, limit: int = 1000) -> str:
    return str(value or "").strip()[:limit]


def _safe_filename(value: str) -> str:
    return (
        re.sub(r"[^a-zA-Z0-9_-]+", "_", value)
        .strip("_")[:80]
        or "audio"
    )


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)


def _positive_number(
    value: Any,
    field_name: str,
    minimum: float = 0,
    maximum: float = 100000,
) -> float:

    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be numeric.")

    if not minimum <= number <= maximum:
        raise ValueError(
            f"{field_name} must be between {minimum} and {maximum}."
        )

    return round(number, 3)


# ---------------------------------------------------------
# DATABASE
# ---------------------------------------------------------

def load_database(
    path: Path | str | None = None,
) -> dict:

    database_path = Path(path) if path else DATABASE_FILE

    if not database_path.exists():
        return {
            "version": 1,
            "updated_at": _now(),
            "projects": {},
        }

    try:
        with database_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            raise ValueError("Invalid audio database.")

        data.setdefault("projects", {})
        data.setdefault("version", 1)

        return data

    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Cannot read audio database: {exc}"
        ) from exc


def save_database(
    database: dict,
    path: Path | str | None = None,
) -> None:

    database_path = Path(path) if path else DATABASE_FILE

    database_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    database["version"] = 1
    database["updated_at"] = _now()

    temporary = database_path.with_name(
        database_path.name + ".tmp"
    )

    with temporary.open("w", encoding="utf-8") as file:
        json.dump(
            database,
            file,
            indent=4,
            ensure_ascii=False,
        )

    temporary.replace(database_path)


# ---------------------------------------------------------
# PROJECT MANAGEMENT
# ---------------------------------------------------------

def create_mix(
    name: str,
    description: str = "",
    path: Path | str | None = None,
) -> dict:

    name = _clean(name, 120)

    if not name:
        raise ValueError("Mix name is required.")

    database = load_database(path)

    mix_id = _id()

    mix = {
        "id": mix_id,
        "name": name,
        "description": _clean(description, 2000),
        "tracks": [],
        "master_volume": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "created_at": _now(),
        "updated_at": _now(),
    }

    database["projects"][mix_id] = mix

    save_database(database, path)

    return mix.copy()


def get_mix(
    mix_id: str,
    path: Path | str | None = None,
) -> dict | None:

    database = load_database(path)

    mix = database["projects"].get(mix_id)

    return mix.copy() if mix else None


def list_mixes(
    path: Path | str | None = None,
) -> list[dict]:

    database = load_database(path)

    return [
        mix.copy()
        for mix in database["projects"].values()
    ]


def update_mix(
    mix_id: str,
    updates: dict,
    path: Path | str | None = None,
) -> dict:

    database = load_database(path)

    mix = database["projects"].get(mix_id)

    if not mix:
        raise ValueError("Audio mix not found.")

    if "name" in updates:
        name = _clean(updates["name"], 120)

        if not name:
            raise ValueError("Mix name cannot be empty.")

        mix["name"] = name

    if "description" in updates:
        mix["description"] = _clean(
            updates["description"],
            2000,
        )

    if "master_volume" in updates:
        mix["master_volume"] = _positive_number(
            updates["master_volume"],
            "Master volume",
            0,
            2,
        )

    if "sample_rate" in updates:
        sample_rate = int(
            _positive_number(
                updates["sample_rate"],
                "Sample rate",
                8000,
                192000,
            )
        )

        mix["sample_rate"] = sample_rate

    if "channels" in updates:
        channels = int(
            _positive_number(
                updates["channels"],
                "Channels",
                1,
                2,
            )
        )

        mix["channels"] = channels

    mix["updated_at"] = _now()

    database["projects"][mix_id] = mix

    save_database(database, path)

    return mix.copy()


def delete_mix(
    mix_id: str,
    path: Path | str | None = None,
) -> bool:

    database = load_database(path)

    if mix_id not in database["projects"]:
        return False

    del database["projects"][mix_id]

    save_database(database, path)

    return True


# ---------------------------------------------------------
# AUDIO TRACK VALIDATION
# ---------------------------------------------------------

def validate_track(details: dict) -> dict:

    if not isinstance(details, dict):
        raise ValueError("Track details must be a dictionary.")

    name = _clean(details.get("name"), 120)

    if not name:
        raise ValueError("Track name is required.")

    track_type = _clean(
        details.get("track_type", "Custom")
    )

    if track_type not in TRACK_TYPES:
        raise ValueError("Unsupported audio track type.")

    volume = _positive_number(
        details.get("volume", 1.0),
        "Volume",
        0,
        2,
    )

    pan = _positive_number(
        details.get("pan", 0),
        "Pan",
        -1,
        1,
    )

    start = _positive_number(
        details.get("start", 0),
        "Start time",
    )

    source_offset = _positive_number(
        details.get("source_offset", 0),
        "Source offset",
    )

    duration = details.get("duration")

    if duration is not None:
        duration = _positive_number(
            duration,
            "Duration",
            0.001,
            100000,
        )

    fade_in = _positive_number(
        details.get("fade_in", 0),
        "Fade-in",
        0,
        60,
    )

    fade_out = _positive_number(
        details.get("fade_out", 0),
        "Fade-out",
        0,
        60,
    )

    if duration is not None and fade_in + fade_out > duration:
        raise ValueError(
            "Combined fade durations cannot exceed track duration."
        )

    easing_in = _clean(
        details.get("fade_in_easing", "linear")
    )

    easing_out = _clean(
        details.get("fade_out_easing", "linear")
    )

    if easing_in not in EASING_TYPES:
        raise ValueError("Invalid fade-in easing.")

    if easing_out not in EASING_TYPES:
        raise ValueError("Invalid fade-out easing.")

    return {
        "name": name,
        "track_type": track_type,
        "audio_path": _clean(
            details.get("audio_path"),
            2000,
        ),
        "volume": volume,
        "pan": pan,
        "start": start,
        "source_offset": source_offset,
        "duration": duration,
        "fade_in": fade_in,
        "fade_out": fade_out,
        "fade_in_easing": easing_in,
        "fade_out_easing": easing_out,
        "muted": bool(details.get("muted", False)),
        "enabled": bool(details.get("enabled", True)),
        "loop": bool(details.get("loop", False)),
        "notes": _clean(details.get("notes"), 2000),
    }


# ---------------------------------------------------------
# AUDIO TRACK CRUD
# ---------------------------------------------------------

def add_track(
    mix_id: str,
    details: dict,
    path: Path | str | None = None,
) -> dict:

    database = load_database(path)

    mix = database["projects"].get(mix_id)

    if not mix:
        raise ValueError("Audio mix not found.")

    cleaned = validate_track(details)

    track = {
        "id": _id(),
        **cleaned,
        "created_at": _now(),
        "updated_at": _now(),
    }

    mix["tracks"].append(track)
    mix["updated_at"] = _now()

    save_database(database, path)

    return track.copy()


def get_track(
    mix_id: str,
    track_id: str,
    path: Path | str | None = None,
) -> dict | None:

    mix = get_mix(mix_id, path)

    if not mix:
        return None

    for track in mix["tracks"]:
        if track["id"] == track_id:
            return track.copy()

    return None


def update_track(
    mix_id: str,
    track_id: str,
    updates: dict,
    path: Path | str | None = None,
) -> dict:

    database = load_database(path)

    mix = database["projects"].get(mix_id)

    if not mix:
        raise ValueError("Audio mix not found.")

    for index, track in enumerate(mix["tracks"]):

        if track["id"] != track_id:
            continue

        cleaned = validate_track({
            **track,
            **updates,
        })

        updated = {
            **track,
            **cleaned,
            "updated_at": _now(),
        }

        mix["tracks"][index] = updated
        mix["updated_at"] = _now()

        save_database(database, path)

        return updated.copy()

    raise ValueError("Audio track not found.")


def remove_track(
    mix_id: str,
    track_id: str,
    path: Path | str | None = None,
) -> bool:

    database = load_database(path)

    mix = database["projects"].get(mix_id)

    if not mix:
        return False

    original = len(mix["tracks"])

    mix["tracks"] = [
        track
        for track in mix["tracks"]
        if track["id"] != track_id
    ]

    if len(mix["tracks"]) == original:
        return False

    mix["updated_at"] = _now()

    save_database(database, path)

    return True


# ---------------------------------------------------------
# AUDIO IMPORT
# ---------------------------------------------------------

def validate_audio_file(
    audio_path: Path | str,
    must_exist: bool = True,
) -> Path:

    source = Path(audio_path).expanduser().resolve()

    if source.suffix.lower() not in SUPPORTED_AUDIO:
        raise ValueError("Unsupported audio format.")

    if must_exist and not source.is_file():
        raise FileNotFoundError(
            f"Audio file not found: {source}"
        )

    return source


def import_audio(
    mix_id: str,
    audio_path: Path | str,
    track_type: str = "Background Music",
    name: str | None = None,
    start: float = 0,
    copy_to_library: bool = True,
    path: Path | str | None = None,
) -> dict:

    source = validate_audio_file(audio_path)

    if track_type not in TRACK_TYPES:
        raise ValueError("Invalid audio track type.")

    stored_path = source

    if copy_to_library:

        ensure_directories()

        mix_folder = AUDIO_DIR / _safe_filename(mix_id)

        mix_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        filename = (
            uuid.uuid4().hex[:8]
            + "_"
            + _safe_filename(source.stem)
            + source.suffix.lower()
        )

        destination = mix_folder / filename

        # Avoid overwriting an existing asset.
        with source.open("rb") as src:
            with destination.open("xb") as dst:
                while True:
                    chunk = src.read(1024 * 1024)

                    if not chunk:
                        break

                    dst.write(chunk)

        stored_path = destination.resolve()

    return add_track(
        mix_id,
        {
            "name": name or source.stem,
            "track_type": track_type,
            "audio_path": str(stored_path),
            "start": start,
            "volume": 1.0,
        },
        path,
    )


# ---------------------------------------------------------
# TRACK CONTROLS
# ---------------------------------------------------------

def set_volume(
    mix_id: str,
    track_id: str,
    volume: float,
    path: Path | str | None = None,
) -> dict:

    return update_track(
        mix_id,
        track_id,
        {"volume": volume},
        path,
    )


def set_muted(
    mix_id: str,
    track_id: str,
    muted: bool,
    path: Path | str | None = None,
) -> dict:

    return update_track(
        mix_id,
        track_id,
        {"muted": muted},
        path,
    )


def set_fades(
    mix_id: str,
    track_id: str,
    fade_in: float = 0,
    fade_out: float = 0,
    path: Path | str | None = None,
) -> dict:

    return update_track(
        mix_id,
        track_id,
        {
            "fade_in": fade_in,
            "fade_out": fade_out,
        },
        path,
    )


def move_track(
    mix_id: str,
    track_id: str,
    new_start: float,
    path: Path | str | None = None,
) -> dict:

    return update_track(
        mix_id,
        track_id,
        {"start": new_start},
        path,
    )


# ---------------------------------------------------------
# TIMELINE INTEGRATION
# ---------------------------------------------------------

def sync_audio_to_timeline(
    mix_id: str,
    timeline_id: str,
    track_id: str,
    timeline_track_id: str,
    path: Path | str | None = None,
) -> dict:

    if timeline_editor is None:
        raise RuntimeError("Timeline editor is unavailable.")

    audio_track = get_track(
        mix_id,
        track_id,
        path,
    )

    if not audio_track:
        raise ValueError("Audio track not found.")

    if not audio_track["audio_path"]:
        raise ValueError("Audio track has no source file.")

    timeline_track = timeline_editor.get_track(
        timeline_id,
        timeline_track_id,
    )

    if not timeline_track:
        raise ValueError("Timeline destination track not found.")

    clip_details = {
        "name": audio_track["name"],
        "start": audio_track["start"],
        "duration": audio_track["duration"] or 1.0,
        "source": audio_track["audio_path"],
        "notes": json.dumps({
            "audio_track_id": track_id,
            "volume": audio_track["volume"],
            "pan": audio_track["pan"],
            "fade_in": audio_track["fade_in"],
            "fade_out": audio_track["fade_out"],
            "muted": audio_track["muted"],
        }),
    }

    created_clip = timeline_editor.add_clip(
        timeline_id,
        timeline_track_id,
        clip_details,
    )

    return {
        "audio_track_id": track_id,
        "timeline_clip": created_clip,
        "message": "Audio metadata copied to timeline.",
    }


# ---------------------------------------------------------
# MIX STATISTICS
# ---------------------------------------------------------

def get_mix_statistics(
    mix_id: str,
    path: Path | str | None = None,
) -> dict:

    mix = get_mix(mix_id, path)

    if not mix:
        raise ValueError("Audio mix not found.")

    tracks = mix["tracks"]

    type_counts = {}

    for track in tracks:
        kind = track["track_type"]

        type_counts[kind] = (
            type_counts.get(kind, 0) + 1
        )

    active_tracks = [
        track for track in tracks
        if track["enabled"] and not track["muted"]
    ]

    durations = [
        track["start"] + track["duration"]
        for track in tracks
        if track["duration"] is not None
    ]

    return {
        "total_tracks": len(tracks),
        "active_tracks": len(active_tracks),
        "muted_tracks": sum(
            1 for track in tracks if track["muted"]
        ),
        "background_music": type_counts.get(
            "Background Music", 0
        ),
        "voice_overs": type_counts.get(
            "Voice Over", 0
        ),
        "dialogue": type_counts.get(
            "Dialogue", 0
        ),
        "sound_effects": type_counts.get(
            "Sound Effects", 0
        ),
        "track_types": type_counts,
        "estimated_duration": max(durations, default=0),
    }


# ---------------------------------------------------------
# MIX EXPORT
# ---------------------------------------------------------

def export_mix(
    mix_id: str,
    output_dir: Path | str | None = None,
    path: Path | str | None = None,
) -> Path:

    mix = get_mix(mix_id, path)

    if not mix:
        raise ValueError("Audio mix not found.")

    destination = (
        Path(output_dir)
        if output_dir
        else EXPORT_DIR
    )

    destination.mkdir(
        parents=True,
        exist_ok=True,
    )

    output = destination / (
        _safe_filename(mix["name"])
        + "_mix.json"
    )

    document = {
        "format": "ai-influencer-studio-audio-mix",
        "version": 1,
        "exported_at": _now(),
        "mix": mix,
        "statistics": get_mix_statistics(
            mix_id,
            path,
        ),
        "rendering_status": "metadata_only",
    }

    temporary = output.with_name(
        output.name + ".tmp"
    )

    with temporary.open("w", encoding="utf-8") as file:
        json.dump(
            document,
            file,
            indent=4,
            ensure_ascii=False,
        )

    temporary.replace(output)

    return output


# ---------------------------------------------------------
# STREAMLIT UI
# ---------------------------------------------------------

def render(st: Any) -> None:

    ensure_directories()

    st.title("Professional Audio Mixer")

    st.caption(
        "Manage background music, voice-overs, "
        "dialogue and sound-effect tracks."
    )

    tab_projects, tab_tracks, tab_import, tab_export = st.tabs([
        "Mix Projects",
        "Audio Tracks",
        "Import Audio",
        "Export",
    ])

    # -----------------------------------------------------
    # PROJECTS
    # -----------------------------------------------------

    with tab_projects:

        st.subheader("Create audio mix")

        with st.form("create_audio_mix"):

            name = st.text_input(
                "Mix name",
                placeholder="Episode 01 Audio",
            )

            description = st.text_area(
                "Description",
            )

            submitted = st.form_submit_button(
                "Create Mix",
            )

        if submitted:

            try:
                mix = create_mix(
                    name,
                    description,
                )

                st.success(
                    f"Created audio mix: {mix['name']}"
                )

            except Exception as exc:
                st.error(str(exc))

        mixes = list_mixes()

        st.subheader("Saved mixes")

        if not mixes:
            st.info("No audio mixes created.")

        for mix in mixes:

            with st.container(border=True):

                st.write(f"**{mix['name']}**")

                st.caption(
                    f"Tracks: {len(mix['tracks'])} | "
                    f"ID: {mix['id']}"
                )

                if st.button(
                    "Delete Mix",
                    key=f"delete_mix_{mix['id']}",
                ):

                    delete_mix(mix["id"])

                    st.success("Mix deleted.")

                    st.rerun()

    # -----------------------------------------------------
    # SELECT MIX
    # -----------------------------------------------------

    mixes = list_mixes()

    mix_options = {
        mix["name"] + " (" + mix["id"][:8] + ")":
        mix["id"]
        for mix in mixes
    }

    selected_mix_id = None

    if mix_options:

        selected_label = st.selectbox(
            "Select audio mix",
            list(mix_options.keys()),
            key="audio_selected_mix",
        )

        selected_mix_id = mix_options[selected_label]

    # -----------------------------------------------------
    # TRACKS
    # -----------------------------------------------------

    with tab_tracks:

        if not selected_mix_id:
            st.info("Create an audio mix first.")

        else:

            mix = get_mix(selected_mix_id)

            st.subheader("Track controls")

            master_volume = st.slider(
                "Master volume",
                0.0,
                2.0,
                float(mix["master_volume"]),
                0.05,
            )

            if st.button("Save Master Volume"):
                update_mix(
                    selected_mix_id,
                    {"master_volume": master_volume},
                )

                st.success("Master volume saved.")

            for track in mix["tracks"]:

                with st.container(border=True):

                    st.write(f"**{track['name']}**")

                    st.caption(
                        f"{track['track_type']} | "
                        f"Start: {track['start']} sec"
                    )

                    col1, col2 = st.columns(2)

                    with col1:

                        volume = st.slider(
                            "Volume",
                            0.0,
                            2.0,
                            float(track["volume"]),
                            0.05,
                            key=f"volume_{track['id']}",
                        )

                        muted = st.checkbox(
                            "Mute",
                            value=track["muted"],
                            key=f"mute_{track['id']}",
                        )

                    with col2:

                        fade_in = st.number_input(
                            "Fade-in seconds",
                            min_value=0.0,
                            max_value=60.0,
                            value=float(track["fade_in"]),
                            step=0.1,
                            key=f"fadein_{track['id']}",
                        )

                        fade_out = st.number_input(
                            "Fade-out seconds",
                            min_value=0.0,
                            max_value=60.0,
                            value=float(track["fade_out"]),
                            step=0.1,
                            key=f"fadeout_{track['id']}",
                        )

                    if st.button(
                        "Save Track Settings",
                        key=f"save_track_{track['id']}",
                    ):

                        try:
                            update_track(
                                selected_mix_id,
                                track["id"],
                                {
                                    "volume": volume,
                                    "muted": muted,
                                    "fade_in": fade_in,
                                    "fade_out": fade_out,
                                },
                            )

                            st.success("Track updated.")

                        except Exception as exc:
                            st.error(str(exc))

                    if st.button(
                        "Remove Track",
                        key=f"remove_track_{track['id']}",
                    ):

                        remove_track(
                            selected_mix_id,
                            track["id"],
                        )

                        st.rerun()

    # -----------------------------------------------------
    # IMPORT AUDIO
    # -----------------------------------------------------

    with tab_import:

        if not selected_mix_id:
            st.info("Create an audio mix first.")

        else:

            st.subheader("Upload audio")

            uploaded = st.file_uploader(
                "Choose an audio file",
                type=[
                    "mp3",
                    "wav",
                    "ogg",
                    "m4a",
                    "aac",
                    "flac",
                    "wma",
                ],
            )

            track_type = st.selectbox(
                "Audio track type",
                TRACK_TYPES,
            )

            track_name = st.text_input(
                "Track name",
            )

            start = st.number_input(
                "Start time (seconds)",
                min_value=0.0,
                value=0.0,
                step=0.5,
            )

            if st.button(
                "Import Audio",
                disabled=uploaded is None,
            ):

                try:
                    ensure_directories()

                    suffix = Path(uploaded.name).suffix.lower()

                    if suffix not in SUPPORTED_AUDIO:
                        raise ValueError(
                            "Unsupported audio format."
                        )

                    temporary = (
                        AUDIO_DIR
                        / (
                            "upload_"
                            + uuid.uuid4().hex
                            + suffix
                        )
                    )

                    temporary.write_bytes(
                        uploaded.getvalue()
                    )

                    try:
                        track = import_audio(
                            selected_mix_id,
                            temporary,
                            track_type=track_type,
                            name=track_name or uploaded.name,
                            start=start,
                            copy_to_library=True,
                        )
                    finally:
                        temporary.unlink(missing_ok=True)

                    st.success(
                        f"Imported audio: {track['name']}"
                    )

                except Exception as exc:
                    st.error(str(exc))

    # -----------------------------------------------------
    # EXPORT
    # -----------------------------------------------------

    with tab_export:

        if not selected_mix_id:
            st.info("Create an audio mix first.")

        else:

            st.subheader("Mix statistics")

            stats = get_mix_statistics(
                selected_mix_id
            )

            col1, col2, col3 = st.columns(3)

            col1.metric(
                "Total Tracks",
                stats["total_tracks"],
            )

            col2.metric(
                "Active Tracks",
                stats["active_tracks"],
            )

            col3.metric(
                "Muted Tracks",
                stats["muted_tracks"],
            )

            st.json(stats["track_types"])

            if st.button(
                "Generate Mix Configuration",
                type="primary",
            ):

                try:
                    output = export_mix(
                        selected_mix_id
                    )

                    with output.open("rb") as file:

                        st.download_button(
                            "Download Audio Mix JSON",
                            data=file.read(),
                            file_name=output.name,
                            mime="application/json",
                        )

                except Exception as exc:
                    st.error(str(exc))


# ---------------------------------------------------------
# BUILT-IN TESTS
# ---------------------------------------------------------

def run_tests() -> bool:

    import tempfile
    import unittest

    class AudioMixerTests(unittest.TestCase):

        def setUp(self):
            self.temp = tempfile.TemporaryDirectory()
            self.root = Path(self.temp.name)
            self.database = self.root / "audio.json"

            self.mix = create_mix(
                "Test Mix",
                path=self.database,
            )

        def tearDown(self):
            self.temp.cleanup()

        def sample_track(self):
            return {
                "name": "Background Music",
                "track_type": "Background Music",
                "volume": 0.8,
                "pan": 0,
                "start": 0,
                "duration": 20,
                "fade_in": 2,
                "fade_out": 2,
            }

        def test_create_mix(self):
            self.assertEqual(
                self.mix["name"],
                "Test Mix",
            )

        def test_get_mix(self):
            result = get_mix(
                self.mix["id"],
                self.database,
            )

            self.assertIsNotNone(result)

        def test_list_mixes(self):
            self.assertEqual(
                len(list_mixes(self.database)),
                1,
            )

        def test_update_mix(self):
            result = update_mix(
                self.mix["id"],
                {"master_volume": 0.5},
                self.database,
            )

            self.assertEqual(
                result["master_volume"],
                0.5,
            )

        def test_create_track(self):
            track = add_track(
                self.mix["id"],
                self.sample_track(),
                self.database,
            )

            self.assertEqual(
                track["track_type"],
                "Background Music",
            )

        def test_get_track(self):
            track = add_track(
                self.mix["id"],
                self.sample_track(),
                self.database,
            )

            result = get_track(
                self.mix["id"],
                track["id"],
                self.database,
            )

            self.assertIsNotNone(result)

        def test_update_track(self):
            track = add_track(
                self.mix["id"],
                self.sample_track(),
                self.database,
            )

            result = update_track(
                self.mix["id"],
                track["id"],
                {"volume": 0.5},
                self.database,
            )

            self.assertEqual(result["volume"], 0.5)

        def test_remove_track(self):
            track = add_track(
                self.mix["id"],
                self.sample_track(),
                self.database,
            )

            self.assertTrue(
                remove_track(
                    self.mix["id"],
                    track["id"],
                    self.database,
                )
            )

        def test_invalid_track_type(self):
            data = self.sample_track()
            data["track_type"] = "Invalid"

            with self.assertRaises(ValueError):
                validate_track(data)

        def test_invalid_volume(self):
            data = self.sample_track()
            data["volume"] = 5

            with self.assertRaises(ValueError):
                validate_track(data)

        def test_invalid_fades(self):
            data = self.sample_track()
            data["fade_in"] = 15
            data["fade_out"] = 15

            with self.assertRaises(ValueError):
                validate_track(data)

        def test_mute_track(self):
            track = add_track(
                self.mix["id"],
                self.sample_track(),
                self.database,
            )

            result = set_muted(
                self.mix["id"],
                track["id"],
                True,
                self.database,
            )

            self.assertTrue(result["muted"])

        def test_track_statistics(self):
            add_track(
                self.mix["id"],
                self.sample_track(),
                self.database,
            )

            stats = get_mix_statistics(
                self.mix["id"],
                self.database,
            )

            self.assertEqual(stats["total_tracks"], 1)

        def test_delete_mix(self):
            self.assertTrue(
                delete_mix(
                    self.mix["id"],
                    self.database,
                )
            )

            self.assertIsNone(
                get_mix(
                    self.mix["id"],
                    self.database,
                )
            )

        def test_export_mix(self):
            add_track(
                self.mix["id"],
                self.sample_track(),
                self.database,
            )

            output = export_mix(
                self.mix["id"],
                self.root / "exports",
                self.database,
            )

            self.assertTrue(output.exists())

        def test_audio_extension_validation(self):
            with self.assertRaises(ValueError):
                validate_audio_file(
                    self.root / "test.exe",
                    must_exist=False,
                )

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        AudioMixerTests
    )

    result = unittest.TextTestRunner(
        verbosity=2
    ).run(suite)

    return result.wasSuccessful()


# ---------------------------------------------------------
# COMMAND LINE
# ---------------------------------------------------------

if __name__ == "__main__":
    import sys

    if "--test" in sys.argv:
        success = run_tests()
        raise SystemExit(0 if success else 1)

    print("AI Influencer Studio - Professional Audio Mixer")
    print("Run tests:")
    print("python -m modules.audio_mixer --test")
