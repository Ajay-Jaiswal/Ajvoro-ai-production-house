
"""
AI Influencer Studio
File 37: modules/timeline_editor.py

Professional Timeline Editor

Features:
- Multiple timelines
- Multiple tracks
- Storyboard shot import
- Clip management and ordering
- Clip duration and start position
- Transitions
- Audio and effects placeholders
- Timeline calculations
- JSON export
- Streamlit interface
- Built-in tests

This module prepares timeline data.
It does not render or encode video.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------
# OPTIONAL STORYBOARD INTEGRATION
# ---------------------------------------------------------

try:
    from modules import storyboard_manager
except ImportError:
    storyboard_manager = None


# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
EXPORT_DIR = PROJECT_ROOT / "outputs" / "timelines"

DATABASE_FILE = DATA_DIR / "timelines.json"

TRACK_TYPES = [
    "Video",
    "Audio",
    "Music",
    "Effects",
    "Text",
]

TRANSITIONS = [
    "Cut",
    "Fade",
    "Cross Dissolve",
    "Wipe",
    "Zoom",
    "Slide Left",
    "Slide Right",
    "Dip to Black",
    "None",
]

TIMELINE_STATUSES = [
    "Draft",
    "In Progress",
    "Ready",
    "Approved",
    "Archived",
]


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _clean(value: Any, limit: int = 3000) -> str:
    return str(value or "").strip()[:limit]


def _safe_filename(value: str) -> str:
    result = re.sub(
        r"[^a-zA-Z0-9_-]+",
        "_",
        str(value or ""),
    )
    return result.strip("_")[:80] or "timeline"


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)


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
            "timelines": [],
        }

    try:
        with database_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            raise ValueError("Invalid timeline database.")

        if not isinstance(data.get("timelines"), list):
            data["timelines"] = []

        data.setdefault("version", 1)
        data.setdefault("updated_at", _now())

        return data

    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Unable to load timeline database: {exc}"
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
# STORYBOARD INTEGRATION
# ---------------------------------------------------------

def list_storyboards() -> list[dict]:
    if storyboard_manager is None:
        return []

    try:
        return storyboard_manager.list_storyboards()
    except Exception:
        return []


def get_storyboard(storyboard_id: str) -> dict | None:
    if storyboard_manager is None:
        return None

    try:
        return storyboard_manager.get_storyboard(
            storyboard_id
        )
    except Exception:
        return None


# ---------------------------------------------------------
# VALIDATION
# ---------------------------------------------------------

def validate_timeline(details: dict) -> dict:
    if not isinstance(details, dict):
        raise ValueError("Timeline details must be a dictionary.")

    name = _clean(details.get("name"), 120)

    if not name:
        raise ValueError("Timeline name is required.")

    status = _clean(
        details.get("status", "Draft")
    )

    if status not in TIMELINE_STATUSES:
        raise ValueError("Invalid timeline status.")

    try:
        fps = int(details.get("fps", 24))
    except (TypeError, ValueError):
        raise ValueError("FPS must be an integer.")

    if not 1 <= fps <= 120:
        raise ValueError("FPS must be between 1 and 120.")

    aspect_ratio = _clean(
        details.get("aspect_ratio", "16:9"),
        30,
    )

    return {
        "name": name,
        "description": _clean(details.get("description")),
        "project_name": _clean(details.get("project_name"), 150),
        "storyboard_id": _clean(details.get("storyboard_id"), 100),
        "aspect_ratio": aspect_ratio,
        "fps": fps,
        "status": status,
    }


def validate_track(details: dict) -> dict:
    if not isinstance(details, dict):
        raise ValueError("Track details must be a dictionary.")

    name = _clean(details.get("name"), 100)

    if not name:
        raise ValueError("Track name is required.")

    track_type = _clean(
        details.get("track_type", "Video")
    )

    if track_type not in TRACK_TYPES:
        raise ValueError("Invalid track type.")

    return {
        "id": _clean(details.get("id")) or _new_id(),
        "name": name,
        "track_type": track_type,
        "muted": bool(details.get("muted", False)),
        "locked": bool(details.get("locked", False)),
        "visible": bool(details.get("visible", True)),
        "clips": [],
        "created_at": details.get("created_at") or _now(),
        "updated_at": _now(),
    }


def validate_clip(details: dict) -> dict:
    if not isinstance(details, dict):
        raise ValueError("Clip details must be a dictionary.")

    name = _clean(details.get("name"), 150)

    if not name:
        raise ValueError("Clip name is required.")

    try:
        start = float(details.get("start", 0))
        duration = float(details.get("duration", 8))
    except (TypeError, ValueError):
        raise ValueError("Start and duration must be numeric.")

    if start < 0:
        raise ValueError("Clip start cannot be negative.")

    if not 0.1 <= duration <= 36000:
        raise ValueError(
            "Clip duration must be between 0.1 and 36000 seconds."
        )

    transition_in = _clean(
        details.get("transition_in", "Cut")
    )

    transition_out = _clean(
        details.get("transition_out", "Cut")
    )

    if transition_in not in TRANSITIONS:
        raise ValueError("Invalid incoming transition.")

    if transition_out not in TRANSITIONS:
        raise ValueError("Invalid outgoing transition.")

    try:
        volume = float(details.get("volume", 1.0))
    except (TypeError, ValueError):
        raise ValueError("Volume must be numeric.")

    if not 0 <= volume <= 2:
        raise ValueError("Volume must be between 0 and 2.")

    return {
        "id": _clean(details.get("id")) or _new_id(),
        "name": name,
        "source_type": _clean(
            details.get("source_type", "Manual")
        ),
        "source_id": _clean(details.get("source_id"), 100),
        "source_path": _clean(details.get("source_path"), 1000),
        "start": round(start, 3),
        "duration": round(duration, 3),
        "transition_in": transition_in,
        "transition_out": transition_out,
        "volume": volume,
        "notes": _clean(details.get("notes")),
        "enabled": bool(details.get("enabled", True)),
        "created_at": details.get("created_at") or _now(),
        "updated_at": _now(),
    }


# ---------------------------------------------------------
# TIMELINE CRUD
# ---------------------------------------------------------

def create_timeline(
    details: dict,
    path: Path | str | None = None,
    validate_storyboard: bool = False,
) -> dict:
    database = load_database(path)

    cleaned = validate_timeline(details)

    storyboard_id = cleaned["storyboard_id"]

    if storyboard_id and validate_storyboard:
        if get_storyboard(storyboard_id) is None:
            raise ValueError("Linked storyboard was not found.")

    timeline = {
        "id": _new_id(),
        **cleaned,
        "tracks": [],
        "created_at": _now(),
        "updated_at": _now(),
    }

    database["timelines"].append(timeline)

    save_database(database, path)

    return timeline.copy()


def get_timeline(
    timeline_id: str,
    path: Path | str | None = None,
) -> dict | None:
    database = load_database(path)

    for timeline in database["timelines"]:
        if timeline.get("id") == timeline_id:
            return timeline.copy()

    return None


def list_timelines(
    search: str = "",
    status: str = "",
    path: Path | str | None = None,
) -> list[dict]:
    database = load_database(path)

    search = str(search or "").strip().lower()
    results = []

    for timeline in database["timelines"]:
        if status and timeline.get("status") != status:
            continue

        searchable = " ".join([
            timeline.get("name", ""),
            timeline.get("description", ""),
            timeline.get("project_name", ""),
        ]).lower()

        if search and search not in searchable:
            continue

        results.append(timeline.copy())

    results.sort(
        key=lambda item: item.get("updated_at", ""),
        reverse=True,
    )

    return results


def update_timeline(
    timeline_id: str,
    updates: dict,
    path: Path | str | None = None,
) -> dict:
    database = load_database(path)

    for index, timeline in enumerate(database["timelines"]):
        if timeline.get("id") != timeline_id:
            continue

        cleaned = validate_timeline({
            **timeline,
            **updates,
        })

        updated = {
            **timeline,
            **cleaned,
            "updated_at": _now(),
        }

        database["timelines"][index] = updated
        save_database(database, path)

        return updated.copy()

    raise ValueError("Timeline not found.")


def delete_timeline(
    timeline_id: str,
    path: Path | str | None = None,
) -> bool:
    database = load_database(path)

    original_count = len(database["timelines"])

    database["timelines"] = [
        item for item in database["timelines"]
        if item.get("id") != timeline_id
    ]

    if len(database["timelines"]) == original_count:
        return False

    save_database(database, path)

    return True


# ---------------------------------------------------------
# TRACK MANAGEMENT
# ---------------------------------------------------------

def add_track(
    timeline_id: str,
    details: dict,
    path: Path | str | None = None,
) -> dict:
    database = load_database(path)

    for timeline in database["timelines"]:
        if timeline.get("id") != timeline_id:
            continue

        track = validate_track(details)

        existing_ids = {
            item.get("id")
            for item in timeline.get("tracks", [])
        }

        if track["id"] in existing_ids:
            track["id"] = _new_id()

        timeline.setdefault("tracks", []).append(track)
        timeline["updated_at"] = _now()

        save_database(database, path)

        return track.copy()

    raise ValueError("Timeline not found.")


def get_track(
    timeline_id: str,
    track_id: str,
    path: Path | str | None = None,
) -> dict | None:
    timeline = get_timeline(timeline_id, path)

    if not timeline:
        return None

    for track in timeline.get("tracks", []):
        if track.get("id") == track_id:
            return track.copy()

    return None


def update_track(
    timeline_id: str,
    track_id: str,
    updates: dict,
    path: Path | str | None = None,
) -> dict:
    database = load_database(path)

    for timeline in database["timelines"]:
        if timeline.get("id") != timeline_id:
            continue

        for index, track in enumerate(timeline.get("tracks", [])):
            if track.get("id") != track_id:
                continue

            merged = {
                **track,
                **updates,
            }

            updated = validate_track(merged)
            updated["clips"] = track.get("clips", [])
            updated["updated_at"] = _now()

            timeline["tracks"][index] = updated
            timeline["updated_at"] = _now()

            save_database(database, path)

            return updated.copy()

    raise ValueError("Track not found.")


def delete_track(
    timeline_id: str,
    track_id: str,
    path: Path | str | None = None,
) -> bool:
    database = load_database(path)

    for timeline in database["timelines"]:
        if timeline.get("id") != timeline_id:
            continue

        tracks = timeline.get("tracks", [])
        original_count = len(tracks)

        timeline["tracks"] = [
            track for track in tracks
            if track.get("id") != track_id
        ]

        if len(timeline["tracks"]) == original_count:
            return False

        timeline["updated_at"] = _now()
        save_database(database, path)

        return True

    return False


# ---------------------------------------------------------
# CLIP MANAGEMENT
# ---------------------------------------------------------

def add_clip(
    timeline_id: str,
    track_id: str,
    details: dict,
    path: Path | str | None = None,
) -> dict:
    database = load_database(path)

    for timeline in database["timelines"]:
        if timeline.get("id") != timeline_id:
            continue

        for track in timeline.get("tracks", []):
            if track.get("id") != track_id:
                continue

            if track.get("locked"):
                raise ValueError("This track is locked.")

            clip = validate_clip(details)

            existing_ids = {
                item.get("id")
                for item in track.get("clips", [])
            }

            if clip["id"] in existing_ids:
                clip["id"] = _new_id()

            track.setdefault("clips", []).append(clip)

            track["clips"].sort(
                key=lambda item: item.get("start", 0)
            )

            track["updated_at"] = _now()
            timeline["updated_at"] = _now()

            save_database(database, path)

            return clip.copy()

    raise ValueError("Timeline or track not found.")


def update_clip(
    timeline_id: str,
    track_id: str,
    clip_id: str,
    updates: dict,
    path: Path | str | None = None,
) -> dict:
    database = load_database(path)

    for timeline in database["timelines"]:
        if timeline.get("id") != timeline_id:
            continue

        for track in timeline.get("tracks", []):
            if track.get("id") != track_id:
                continue

            if track.get("locked"):
                raise ValueError("This track is locked.")

            for index, clip in enumerate(track.get("clips", [])):
                if clip.get("id") != clip_id:
                    continue

                updated = validate_clip({
                    **clip,
                    **updates,
                })

                track["clips"][index] = updated

                track["clips"].sort(
                    key=lambda item: item.get("start", 0)
                )

                track["updated_at"] = _now()
                timeline["updated_at"] = _now()

                save_database(database, path)

                return updated.copy()

    raise ValueError("Clip not found.")


def delete_clip(
    timeline_id: str,
    track_id: str,
    clip_id: str,
    path: Path | str | None = None,
) -> bool:
    database = load_database(path)

    for timeline in database["timelines"]:
        if timeline.get("id") != timeline_id:
            continue

        for track in timeline.get("tracks", []):
            if track.get("id") != track_id:
                continue

            if track.get("locked"):
                raise ValueError("This track is locked.")

            clips = track.get("clips", [])
            original_count = len(clips)

            track["clips"] = [
                clip for clip in clips
                if clip.get("id") != clip_id
            ]

            if len(track["clips"]) == original_count:
                return False

            track["updated_at"] = _now()
            timeline["updated_at"] = _now()

            save_database(database, path)

            return True

    return False


def move_clip(
    timeline_id: str,
    track_id: str,
    clip_id: str,
    new_start: float,
    path: Path | str | None = None,
) -> dict:
    return update_clip(
        timeline_id,
        track_id,
        clip_id,
        {"start": new_start},
        path,
    )


def move_clip_to_track(
    timeline_id: str,
    source_track_id: str,
    destination_track_id: str,
    clip_id: str,
    path: Path | str | None = None,
) -> dict:
    database = load_database(path)

    timeline = next(
        (
            item for item in database["timelines"]
            if item.get("id") == timeline_id
        ),
        None,
    )

    if timeline is None:
        raise ValueError("Timeline not found.")

    tracks = timeline.get("tracks", [])

    source = next(
        (
            item for item in tracks
            if item.get("id") == source_track_id
        ),
        None,
    )

    destination = next(
        (
            item for item in tracks
            if item.get("id") == destination_track_id
        ),
        None,
    )

    if source is None or destination is None:
        raise ValueError("Source or destination track not found.")

    if source.get("locked") or destination.get("locked"):
        raise ValueError("Cannot move clips on locked tracks.")

    if source is destination:
        raise ValueError("Choose a different destination track.")

    clip = next(
        (
            item for item in source.get("clips", [])
            if item.get("id") == clip_id
        ),
        None,
    )

    if clip is None:
        raise ValueError("Clip not found.")

    destination["clips"].append(clip)
    destination["clips"].sort(
        key=lambda item: item.get("start", 0)
    )

    source["clips"] = [
        item for item in source["clips"]
        if item.get("id") != clip_id
    ]

    source["updated_at"] = _now()
    destination["updated_at"] = _now()
    timeline["updated_at"] = _now()

    save_database(database, path)

    return clip.copy()


# ---------------------------------------------------------
# STORYBOARD IMPORT
# ---------------------------------------------------------

def import_storyboard(
    timeline_id: str,
    storyboard_id: str,
    track_id: str,
    path: Path | str | None = None,
) -> list[dict]:
    storyboard = get_storyboard(storyboard_id)

    if storyboard is None:
        raise ValueError("Storyboard not found.")

    timeline = get_timeline(timeline_id, path)

    if timeline is None:
        raise ValueError("Timeline not found.")

    track = get_track(
        timeline_id,
        track_id,
        path,
    )

    if track is None:
        raise ValueError("Track not found.")

    if track.get("locked"):
        raise ValueError("This track is locked.")

    created = []

    existing_clips = track.get("clips", [])

    start_position = max(
        (
            clip["start"] + clip["duration"]
            for clip in existing_clips
        ),
        default=0,
    )

    shots = sorted(
        storyboard.get("shots", []),
        key=lambda item: item.get("scene_order", 1),
    )

    for shot in shots:
        clip = add_clip(
            timeline_id,
            track_id,
            {
                "name": shot.get("title", "Storyboard Shot"),
                "source_type": "Storyboard",
                "source_id": shot.get("id", ""),
                "start": start_position,
                "duration": shot.get("duration_seconds", 8),
                "notes": shot.get("description", ""),
                "transition_in": "Cut",
                "transition_out": (
                    shot.get("transition", "Cut")
                    if shot.get("transition") in TRANSITIONS
                    else "Cut"
                ),
            },
            path,
        )

        created.append(clip)

        start_position += clip["duration"]

    return created


# ---------------------------------------------------------
# TIMELINE CALCULATIONS
# ---------------------------------------------------------

def get_track_duration(track: dict) -> float:
    end_times = []

    for clip in track.get("clips", []):
        if not clip.get("enabled", True):
            continue

        end_times.append(
            float(clip.get("start", 0))
            + float(clip.get("duration", 0))
        )

    return round(max(end_times, default=0), 3)


def get_timeline_duration(
    timeline_id: str,
    path: Path | str | None = None,
) -> float:
    timeline = get_timeline(timeline_id, path)

    if not timeline:
        raise ValueError("Timeline not found.")

    return round(
        max(
            (
                get_track_duration(track)
                for track in timeline.get("tracks", [])
            ),
            default=0,
        ),
        3,
    )


def get_timeline_statistics(
    path: Path | str | None = None,
) -> dict:
    timelines = list_timelines(path=path)

    total_tracks = 0
    total_clips = 0
    total_duration = 0

    for timeline in timelines:
        tracks = timeline.get("tracks", [])

        total_tracks += len(tracks)

        for track in tracks:
            total_clips += len(track.get("clips", []))

        total_duration += get_timeline_duration(
            timeline["id"],
            path,
        )

    return {
        "total_timelines": len(timelines),
        "total_tracks": total_tracks,
        "total_clips": total_clips,
        "total_duration_seconds": round(total_duration, 3),
    }


# ---------------------------------------------------------
# EXPORT
# ---------------------------------------------------------

def build_timeline_document(
    timeline_id: str,
    path: Path | str | None = None,
) -> dict:
    timeline = get_timeline(timeline_id, path)

    if not timeline:
        raise ValueError("Timeline not found.")

    return {
        "timeline": {
            "id": timeline["id"],
            "name": timeline["name"],
            "description": timeline["description"],
            "project_name": timeline["project_name"],
            "aspect_ratio": timeline["aspect_ratio"],
            "fps": timeline["fps"],
            "status": timeline["status"],
        },
        "duration_seconds": get_timeline_duration(
            timeline_id,
            path,
        ),
        "tracks": timeline.get("tracks", []),
        "exported_at": _now(),
        "rendering_status": (
            "Timeline prepared; video rendering not performed."
        ),
    }


def export_timeline(
    timeline_id: str,
    output_dir: Path | str | None = None,
    path: Path | str | None = None,
) -> Path:
    document = build_timeline_document(
        timeline_id,
        path,
    )

    destination = (
        Path(output_dir)
        if output_dir
        else EXPORT_DIR
    )

    destination.mkdir(parents=True, exist_ok=True)

    filename = (
        _safe_filename(
            document["timeline"]["name"]
        )
        + "_timeline.json"
    )

    output = destination / filename

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

    st.title("Professional Timeline Editor")

    st.caption(
        "Arrange storyboard shots, video clips, audio tracks "
        "and transitions into an editing sequence."
    )

    tab_create, tab_editor, tab_stats = st.tabs([
        "Create Timeline",
        "Timeline Editor",
        "Statistics",
    ])

    # -----------------------------------------------------
    # CREATE TIMELINE
    # -----------------------------------------------------

    with tab_create:
        st.subheader("New timeline")

        available_storyboards = list_storyboards()

        storyboard_options = {
            "None": ""
        }

        for item in available_storyboards:
            item_id = item.get("id", "")

            if item_id:
                storyboard_options[
                    f"{item.get('name', 'Storyboard')} ({item_id[:8]})"
                ] = item_id

        with st.form("create_timeline_form"):
            name = st.text_input(
                "Timeline name",
                placeholder="Example: Episode 1 Final Edit",
            )

            description = st.text_area(
                "Description",
            )

            project_name = st.text_input(
                "Project name",
            )

            storyboard_label = st.selectbox(
                "Import storyboard",
                list(storyboard_options.keys()),
            )

            col1, col2 = st.columns(2)

            with col1:
                aspect_ratio = st.selectbox(
                    "Aspect ratio",
                    ["16:9", "9:16", "1:1", "4:5", "21:9"],
                )

            with col2:
                fps = st.selectbox(
                    "Frame rate",
                    [24, 25, 30, 50, 60],
                )

            submitted = st.form_submit_button(
                "Create Timeline",
                type="primary",
            )

        if submitted:
            try:
                timeline = create_timeline({
                    "name": name,
                    "description": description,
                    "project_name": project_name,
                    "storyboard_id": storyboard_options[
                        storyboard_label
                    ],
                    "aspect_ratio": aspect_ratio,
                    "fps": fps,
                    "status": "Draft",
                })

                # Create a default video track.
                video_track = add_track(
                    timeline["id"],
                    {
                        "name": "Video 1",
                        "track_type": "Video",
                    },
                )

                if timeline["storyboard_id"]:
                    import_storyboard(
                        timeline["id"],
                        timeline["storyboard_id"],
                        video_track["id"],
                    )

                st.success(
                    f"Timeline created: {timeline['name']}"
                )

            except Exception as exc:
                st.error(str(exc))

    # -----------------------------------------------------
    # TIMELINE EDITOR
    # -----------------------------------------------------

    with tab_editor:
        st.subheader("Edit timeline")

        timelines = list_timelines()

        if not timelines:
            st.info("Create a timeline first.")
        else:
            timeline_options = {
                f"{item['name']} ({item['id'][:8]})": item["id"]
                for item in timelines
            }

            selected_label = st.selectbox(
                "Select timeline",
                list(timeline_options.keys()),
            )

            timeline_id = timeline_options[selected_label]

            timeline = get_timeline(timeline_id)

            if timeline:
                duration = get_timeline_duration(timeline_id)

                col1, col2, col3 = st.columns(3)

                col1.metric(
                    "Timeline duration",
                    f"{duration:.2f} sec",
                )

                col2.metric(
                    "Tracks",
                    len(timeline.get("tracks", [])),
                )

                col3.metric(
                    "FPS",
                    timeline["fps"],
                )

                st.divider()

                # Add tracks.
                st.markdown("**Add a track**")

                with st.form(
                    f"add_track_form_{timeline_id}"
                ):
                    track_name = st.text_input(
                        "Track name",
                    )

                    track_type = st.selectbox(
                        "Track type",
                        TRACK_TYPES,
                    )

                    add_track_submit = st.form_submit_button(
                        "Add Track"
                    )

                if add_track_submit:
                    try:
                        add_track(
                            timeline_id,
                            {
                                "name": track_name,
                                "track_type": track_type,
                            },
                        )

                        st.success("Track added.")
                        st.rerun()

                    except Exception as exc:
                        st.error(str(exc))

                st.divider()

                # Track overview.
                current = get_timeline(timeline_id)

                for track in current.get("tracks", []):
                    track_id = track["id"]

                    with st.expander(
                        f"{track['name']} — {track['track_type']}"
                        f" ({len(track.get('clips', []))} clips)"
                    ):
                        st.write(
                            f"Track duration: "
                            f"{get_track_duration(track):.2f} sec"
                        )

                        st.write(
                            f"Locked: {track['locked']} | "
                            f"Muted: {track['muted']}"
                        )

                        # Track controls.
                        col1, col2 = st.columns(2)

                        with col1:
                            muted = st.checkbox(
                                "Mute track",
                                value=track["muted"],
                                key=f"mute_{track_id}",
                            )

                        with col2:
                            locked = st.checkbox(
                                "Lock track",
                                value=track["locked"],
                                key=f"lock_{track_id}",
                            )

                        if st.button(
                            "Save Track Settings",
                            key=f"save_track_{track_id}",
                        ):
                            try:
                                update_track(
                                    timeline_id,
                                    track_id,
                                    {
                                        "muted": muted,
                                        "locked": locked,
                                    },
                                )
                                st.success("Track settings saved.")
                                st.rerun()
                            except Exception as exc:
                                st.error(str(exc))

                        st.divider()

                        # Add clip.
                        st.markdown("**Add clip**")

                        with st.form(
                            f"add_clip_form_{track_id}"
                        ):
                            clip_name = st.text_input(
                                "Clip name",
                                key=f"clip_name_{track_id}",
                            )

                            col_a, col_b = st.columns(2)

                            with col_a:
                                clip_start = st.number_input(
                                    "Start position (seconds)",
                                    min_value=0.0,
                                    value=0.0,
                                    key=f"clip_start_{track_id}",
                                )

                            with col_b:
                                clip_duration = st.number_input(
                                    "Duration (seconds)",
                                    min_value=0.1,
                                    value=8.0,
                                    key=f"clip_duration_{track_id}",
                                )

                            source_path = st.text_input(
                                "Local media path (optional)",
                                key=f"clip_path_{track_id}",
                            )

                            transition_in = st.selectbox(
                                "Transition in",
                                TRANSITIONS,
                                key=f"transition_in_{track_id}",
                            )

                            transition_out = st.selectbox(
                                "Transition out",
                                TRANSITIONS,
                                key=f"transition_out_{track_id}",
                            )

                            notes = st.text_area(
                                "Clip notes",
                                key=f"clip_notes_{track_id}",
                            )

                            clip_submit = st.form_submit_button(
                                "Add Clip"
                            )

                        if clip_submit:
                            try:
                                add_clip(
                                    timeline_id,
                                    track_id,
                                    {
                                        "name": clip_name,
                                        "source_type": "Manual",
                                        "source_path": source_path,
                                        "start": clip_start,
                                        "duration": clip_duration,
                                        "transition_in": transition_in,
                                        "transition_out": transition_out,
                                        "notes": notes,
                                    },
                                )

                                st.success("Clip added.")
                                st.rerun()

                            except Exception as exc:
                                st.error(str(exc))

                        # Display clips.
                        st.markdown("**Clips**")

                        clips = sorted(
                            track.get("clips", []),
                            key=lambda item: item["start"],
                        )

                        if not clips:
                            st.info("No clips on this track.")

                        for clip in clips:
                            with st.container(border=True):
                                st.markdown(
                                    f"**{clip['name']}**"
                                )

                                st.caption(
                                    f"Start: {clip['start']} sec | "
                                    f"Duration: {clip['duration']} sec"
                                )

                                st.caption(
                                    f"In: {clip['transition_in']} | "
                                    f"Out: {clip['transition_out']}"
                                )

                                with st.form(
                                    f"edit_clip_{track_id}_{clip['id']}"
                                ):
                                    new_name = st.text_input(
                                        "Name",
                                        value=clip["name"],
                                    )

                                    new_start = st.number_input(
                                        "Start",
                                        min_value=0.0,
                                        value=float(clip["start"]),
                                    )

                                    new_duration = st.number_input(
                                        "Duration",
                                        min_value=0.1,
                                        value=float(clip["duration"]),
                                    )

                                    new_transition_in = st.selectbox(
                                        "Transition in",
                                        TRANSITIONS,
                                        index=TRANSITIONS.index(
                                            clip["transition_in"]
                                        ),
                                    )

                                    new_transition_out = st.selectbox(
                                        "Transition out",
                                        TRANSITIONS,
                                        index=TRANSITIONS.index(
                                            clip["transition_out"]
                                        ),
                                    )

                                    save_clip = st.form_submit_button(
                                        "Save Clip"
                                    )

                                if save_clip:
                                    try:
                                        update_clip(
                                            timeline_id,
                                            track_id,
                                            clip["id"],
                                            {
                                                "name": new_name,
                                                "start": new_start,
                                                "duration": new_duration,
                                                "transition_in": new_transition_in,
                                                "transition_out": new_transition_out,
                                            },
                                        )

                                        st.success("Clip updated.")
                                        st.rerun()

                                    except Exception as exc:
                                        st.error(str(exc))

                                if st.button(
                                    "Delete Clip",
                                    key=f"delete_clip_{track_id}_{clip['id']}",
                                ):
                                    try:
                                        delete_clip(
                                            timeline_id,
                                            track_id,
                                            clip["id"],
                                        )
                                        st.success("Clip deleted.")
                                        st.rerun()
                                    except Exception as exc:
                                        st.error(str(exc))

                        st.divider()

                        confirm_track_delete = st.checkbox(
                            "Confirm track deletion",
                            key=f"confirm_track_delete_{track_id}",
                        )

                        if st.button(
                            "Delete Track",
                            key=f"delete_track_{track_id}",
                            disabled=not confirm_track_delete,
                        ):
                            try:
                                delete_track(
                                    timeline_id,
                                    track_id,
                                )
                                st.success("Track deleted.")
                                st.rerun()
                            except Exception as exc:
                                st.error(str(exc))

                st.divider()

                if st.button(
                    "Export Timeline JSON",
                    key=f"export_timeline_{timeline_id}",
                ):
                    try:
                        output = export_timeline(timeline_id)

                        with output.open("rb") as file:
                            st.download_button(
                                "Download Timeline JSON",
                                data=file.read(),
                                file_name=output.name,
                                mime="application/json",
                            )

                    except Exception as exc:
                        st.error(str(exc))

    # -----------------------------------------------------
    # STATISTICS
    # -----------------------------------------------------

    with tab_stats:
        stats = get_timeline_statistics()

        col1, col2 = st.columns(2)

        col1.metric(
            "Total Timelines",
            stats["total_timelines"],
        )

        col2.metric(
            "Total Tracks",
            stats["total_tracks"],
        )

        col3, col4 = st.columns(2)

        col3.metric(
            "Total Clips",
            stats["total_clips"],
        )

        col4.metric(
            "Combined Duration",
            f"{stats['total_duration_seconds']:.2f} sec",
        )


# ---------------------------------------------------------
# BUILT-IN TESTS
# ---------------------------------------------------------

def run_tests() -> bool:
    import tempfile
    import unittest

    class TimelineTests(unittest.TestCase):

        def setUp(self):
            self.temp = tempfile.TemporaryDirectory()
            self.root = Path(self.temp.name)
            self.database = self.root / "timelines.json"

        def tearDown(self):
            self.temp.cleanup()

        def create_sample(self):
            return create_timeline(
                {
                    "name": "Episode Timeline",
                    "description": "Test timeline",
                    "project_name": "Test Project",
                    "aspect_ratio": "16:9",
                    "fps": 24,
                },
                path=self.database,
            )

        def create_track(self, timeline_id):
            return add_track(
                timeline_id,
                {
                    "name": "Video Track",
                    "track_type": "Video",
                },
                self.database,
            )

        def create_clip(self, timeline_id, track_id):
            return add_clip(
                timeline_id,
                track_id,
                {
                    "name": "Opening Clip",
                    "start": 0,
                    "duration": 8,
                },
                self.database,
            )

        def test_empty_database(self):
            self.assertEqual(
                load_database(self.database)["timelines"],
                [],
            )

        def test_create_timeline(self):
            timeline = self.create_sample()

            self.assertTrue(timeline["id"])
            self.assertEqual(
                timeline["name"],
                "Episode Timeline",
            )

        def test_reject_empty_name(self):
            with self.assertRaises(ValueError):
                create_timeline(
                    {"name": ""},
                    path=self.database,
                )

        def test_get_timeline(self):
            timeline = self.create_sample()

            result = get_timeline(
                timeline["id"],
                self.database,
            )

            self.assertEqual(
                result["id"],
                timeline["id"],
            )

        def test_update_timeline(self):
            timeline = self.create_sample()

            result = update_timeline(
                timeline["id"],
                {"name": "Updated Timeline"},
                self.database,
            )

            self.assertEqual(
                result["name"],
                "Updated Timeline",
            )

        def test_delete_timeline(self):
            timeline = self.create_sample()

            self.assertTrue(
                delete_timeline(
                    timeline["id"],
                    self.database,
                )
            )

            self.assertIsNone(
                get_timeline(
                    timeline["id"],
                    self.database,
                )
            )

        def test_add_track(self):
            timeline = self.create_sample()
            track = self.create_track(timeline["id"])

            self.assertEqual(
                track["track_type"],
                "Video",
            )

        def test_add_clip(self):
            timeline = self.create_sample()
            track = self.create_track(timeline["id"])

            clip = self.create_clip(
                timeline["id"],
                track["id"],
            )

            self.assertEqual(clip["duration"], 8)

        def test_reject_invalid_clip_duration(self):
            timeline = self.create_sample()
            track = self.create_track(timeline["id"])

            with self.assertRaises(ValueError):
                add_clip(
                    timeline["id"],
                    track["id"],
                    {
                        "name": "Invalid Clip",
                        "duration": 0,
                    },
                    self.database,
                )

        def test_update_clip(self):
            timeline = self.create_sample()
            track = self.create_track(timeline["id"])
            clip = self.create_clip(
                timeline["id"],
                track["id"],
            )

            result = update_clip(
                timeline["id"],
                track["id"],
                clip["id"],
                {"duration": 12},
                self.database,
            )

            self.assertEqual(result["duration"], 12)

        def test_delete_clip(self):
            timeline = self.create_sample()
            track = self.create_track(timeline["id"])
            clip = self.create_clip(
                timeline["id"],
                track["id"],
            )

            self.assertTrue(
                delete_clip(
                    timeline["id"],
                    track["id"],
                    clip["id"],
                    self.database,
                )
            )

        def test_move_clip(self):
            timeline = self.create_sample()
            track = self.create_track(timeline["id"])
            clip = self.create_clip(
                timeline["id"],
                track["id"],
            )

            moved = move_clip(
                timeline["id"],
                track["id"],
                clip["id"],
                10,
                self.database,
            )

            self.assertEqual(moved["start"], 10)

        def test_track_duration(self):
            track = {
                "clips": [
                    {
                        "start": 0,
                        "duration": 8,
                        "enabled": True,
                    },
                    {
                        "start": 8,
                        "duration": 10,
                        "enabled": True,
                    },
                ]
            }

            self.assertEqual(
                get_track_duration(track),
                18,
            )

        def test_timeline_duration(self):
            timeline = self.create_sample()
            track = self.create_track(timeline["id"])

            self.create_clip(
                timeline["id"],
                track["id"],
            )

            self.assertEqual(
                get_timeline_duration(
                    timeline["id"],
                    self.database,
                ),
                8,
            )

        def test_locked_track_rejects_clip(self):
            timeline = self.create_sample()
            track = self.create_track(timeline["id"])

            update_track(
                timeline["id"],
                track["id"],
                {"locked": True},
                self.database,
            )

            with self.assertRaises(ValueError):
                add_clip(
                    timeline["id"],
                    track["id"],
                    {"name": "Blocked Clip"},
                    self.database,
                )

        def test_move_clip_between_tracks(self):
            timeline = self.create_sample()

            first = self.create_track(timeline["id"])

            second = add_track(
                timeline["id"],
                {
                    "name": "Video Track 2",
                    "track_type": "Video",
                },
                self.database,
            )

            clip = self.create_clip(
                timeline["id"],
                first["id"],
            )

            moved = move_clip_to_track(
                timeline["id"],
                first["id"],
                second["id"],
                clip["id"],
                self.database,
            )

            self.assertEqual(moved["id"], clip["id"])

            self.assertEqual(
                len(get_track(
                    timeline["id"],
                    first["id"],
                    self.database,
                )["clips"]),
                0,
            )

            self.assertEqual(
                len(get_track(
                    timeline["id"],
                    second["id"],
                    self.database,
                )["clips"]),
                1,
            )

        def test_statistics(self):
            timeline = self.create_sample()
            track = self.create_track(timeline["id"])

            self.create_clip(
                timeline["id"],
                track["id"],
            )

            stats = get_timeline_statistics(self.database)

            self.assertEqual(stats["total_timelines"], 1)
            self.assertEqual(stats["total_tracks"], 1)
            self.assertEqual(stats["total_clips"], 1)

        def test_export_timeline(self):
            timeline = self.create_sample()
            track = self.create_track(timeline["id"])

            self.create_clip(
                timeline["id"],
                track["id"],
            )

            output = export_timeline(
                timeline["id"],
                self.root / "exports",
                self.database,
            )

            self.assertTrue(output.exists())

            with output.open("r", encoding="utf-8") as file:
                data = json.load(file)

            self.assertEqual(
                data["duration_seconds"],
                8,
            )

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        TimelineTests
    )

    result = unittest.TextTestRunner(verbosity=2).run(suite)

    return result.wasSuccessful()


# ---------------------------------------------------------
# COMMAND LINE
# ---------------------------------------------------------

if __name__ == "__main__":
    import sys

    if "--test" in sys.argv:
        success = run_tests()
        raise SystemExit(0 if success else 1)

    print("AI Influencer Studio - Timeline Editor")
    print("Run tests using:")
    print("python -m modules.timeline_editor --test")
