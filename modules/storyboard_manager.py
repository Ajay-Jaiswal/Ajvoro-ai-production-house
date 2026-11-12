
"""
AI Influencer Studio
File 36: modules/storyboard_manager.py

Professional Storyboard Manager

This module manages:
- Multiple storyboards
- Scene sequencing
- Shot duration and camera directions
- Continuity notes
- Scene prompt integration
- JSON export
- Streamlit interface

This module organizes scenes. It does not render videos.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------
# OPTIONAL SCENE COMPOSER INTEGRATION
# ---------------------------------------------------------

try:
    from modules import scene_composer
except ImportError:
    scene_composer = None


# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
EXPORT_DIR = PROJECT_ROOT / "outputs" / "storyboards"

DATABASE_FILE = DATA_DIR / "storyboards.json"

STORYBOARD_STATUSES = [
    "Draft",
    "In Progress",
    "Ready",
    "Approved",
    "Archived",
]

SHOT_TYPES = [
    "Establishing Shot",
    "Extreme Wide Shot",
    "Wide Shot",
    "Full Shot",
    "Medium Shot",
    "Close-up",
    "Extreme Close-up",
    "Insert Shot",
    "Reaction Shot",
    "Transition Shot",
    "Custom",
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
    value = re.sub(
        r"[^a-zA-Z0-9_-]+",
        "_",
        str(value or ""),
    )

    return value.strip("_")[:80] or "storyboard"


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
            "storyboards": [],
        }

    try:
        with database_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            raise ValueError("Invalid storyboard database.")

        if not isinstance(data.get("storyboards"), list):
            data["storyboards"] = []

        data.setdefault("version", 1)
        data.setdefault("updated_at", _now())

        return data

    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Unable to read storyboard database: {exc}"
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
# SCENE INTEGRATION
# ---------------------------------------------------------

def list_available_scenes() -> list[dict]:
    if scene_composer is None:
        return []

    try:
        return scene_composer.list_scenes()
    except Exception:
        return []


def get_scene(scene_id: str) -> dict | None:
    if scene_composer is None or not scene_id:
        return None

    try:
        return scene_composer.get_scene(scene_id)
    except Exception:
        return None


def get_scene_prompt(scene_id: str) -> str:
    if scene_composer is None:
        return ""

    try:
        return scene_composer.build_scene_prompt(
            scene_id=scene_id
        )
    except Exception:
        return ""


# ---------------------------------------------------------
# VALIDATION
# ---------------------------------------------------------

def validate_storyboard(details: dict) -> dict:
    if not isinstance(details, dict):
        raise ValueError("Storyboard details must be a dictionary.")

    name = _clean(details.get("name"), 120)

    if not name:
        raise ValueError("Storyboard name is required.")

    status = _clean(
        details.get("status", "Draft")
    )

    if status not in STORYBOARD_STATUSES:
        raise ValueError("Invalid storyboard status.")

    return {
        "name": name,
        "description": _clean(details.get("description")),
        "project_name": _clean(details.get("project_name"), 150),
        "genre": _clean(details.get("genre"), 100),
        "target_platform": _clean(
            details.get("target_platform"), 100
        ),
        "aspect_ratio": _clean(
            details.get("aspect_ratio", "16:9"), 30
        ),
        "fps": int(details.get("fps", 24)),
        "status": status,
        "notes": _clean(details.get("notes")),
    }


def validate_shot(shot: dict) -> dict:
    if not isinstance(shot, dict):
        raise ValueError("Shot details must be a dictionary.")

    title = _clean(shot.get("title"), 150)

    if not title:
        raise ValueError("Shot title is required.")

    try:
        duration = float(
            shot.get("duration_seconds", 8)
        )
    except (ValueError, TypeError):
        raise ValueError("Shot duration must be numeric.")

    if not 0.1 <= duration <= 600:
        raise ValueError(
            "Shot duration must be between 0.1 and 600 seconds."
        )

    shot_type = _clean(
        shot.get("shot_type", "Medium Shot")
    )

    if shot_type not in SHOT_TYPES:
        raise ValueError("Invalid shot type.")

    try:
        scene_order = int(shot.get("scene_order", 1))
    except (ValueError, TypeError):
        raise ValueError("Scene order must be an integer.")

    if scene_order < 1:
        raise ValueError("Scene order must be at least 1.")

    return {
        "id": _clean(shot.get("id")) or _new_id(),
        "scene_id": _clean(shot.get("scene_id"), 100),
        "title": title,
        "description": _clean(shot.get("description")),
        "shot_type": shot_type,
        "camera_direction": _clean(
            shot.get("camera_direction")
        ),
        "character_action": _clean(
            shot.get("character_action")
        ),
        "dialogue": _clean(
            shot.get("dialogue")
        ),
        "sound_effects": _clean(
            shot.get("sound_effects")
        ),
        "music_notes": _clean(
            shot.get("music_notes")
        ),
        "continuity_notes": _clean(
            shot.get("continuity_notes")
        ),
        "transition": _clean(
            shot.get("transition")
        ),
        "duration_seconds": duration,
        "scene_order": scene_order,
        "created_at": shot.get("created_at") or _now(),
        "updated_at": _now(),
    }


# ---------------------------------------------------------
# STORYBOARD CRUD
# ---------------------------------------------------------

def create_storyboard(
    details: dict,
    path: Path | str | None = None,
) -> dict:
    database = load_database(path)

    cleaned = validate_storyboard(details)

    storyboard = {
        "id": _new_id(),
        **cleaned,
        "shots": [],
        "created_at": _now(),
        "updated_at": _now(),
    }

    database["storyboards"].append(storyboard)

    save_database(database, path)

    return storyboard.copy()


def get_storyboard(
    storyboard_id: str,
    path: Path | str | None = None,
) -> dict | None:
    database = load_database(path)

    for storyboard in database["storyboards"]:
        if storyboard.get("id") == storyboard_id:
            return storyboard.copy()

    return None


def list_storyboards(
    search: str = "",
    status: str = "",
    path: Path | str | None = None,
) -> list[dict]:
    database = load_database(path)

    search = str(search or "").strip().lower()
    results = []

    for storyboard in database["storyboards"]:
        if status and storyboard.get("status") != status:
            continue

        searchable = " ".join([
            storyboard.get("name", ""),
            storyboard.get("description", ""),
            storyboard.get("project_name", ""),
            storyboard.get("genre", ""),
        ]).lower()

        if search and search not in searchable:
            continue

        results.append(storyboard.copy())

    results.sort(
        key=lambda item: item.get("updated_at", ""),
        reverse=True,
    )

    return results


def update_storyboard(
    storyboard_id: str,
    updates: dict,
    path: Path | str | None = None,
) -> dict:
    database = load_database(path)

    for index, storyboard in enumerate(database["storyboards"]):
        if storyboard.get("id") != storyboard_id:
            continue

        merged = {
            **storyboard,
            **updates,
        }

        cleaned = validate_storyboard(merged)

        updated = {
            **storyboard,
            **cleaned,
            "updated_at": _now(),
        }

        database["storyboards"][index] = updated
        save_database(database, path)

        return updated.copy()

    raise ValueError("Storyboard not found.")


def delete_storyboard(
    storyboard_id: str,
    path: Path | str | None = None,
) -> bool:
    database = load_database(path)

    original_count = len(database["storyboards"])

    database["storyboards"] = [
        item for item in database["storyboards"]
        if item.get("id") != storyboard_id
    ]

    if len(database["storyboards"]) == original_count:
        return False

    save_database(database, path)
    return True


def duplicate_storyboard(
    storyboard_id: str,
    new_name: str | None = None,
    path: Path | str | None = None,
) -> dict:
    original = get_storyboard(storyboard_id, path)

    if not original:
        raise ValueError("Storyboard not found.")

    details = {
        key: original.get(key, "")
        for key in [
            "name",
            "description",
            "project_name",
            "genre",
            "target_platform",
            "aspect_ratio",
            "fps",
        ]
    }

    details["name"] = (
        new_name or f"{original['name']} Copy"
    )

    details["status"] = "Draft"

    duplicate = create_storyboard(details, path)

    for shot in original.get("shots", []):
        add_shot(
            duplicate["id"],
            {
                **shot,
                "id": _new_id(),
            },
            path=path,
            validate_scene=False,
        )

    return get_storyboard(duplicate["id"], path)


# ---------------------------------------------------------
# SHOT MANAGEMENT
# ---------------------------------------------------------

def add_shot(
    storyboard_id: str,
    shot_details: dict,
    path: Path | str | None = None,
    validate_scene: bool = True,
) -> dict:
    database = load_database(path)

    for storyboard in database["storyboards"]:
        if storyboard.get("id") != storyboard_id:
            continue

        shot = validate_shot(shot_details)

        scene_id = shot.get("scene_id")

        if scene_id and validate_scene:
            if get_scene(scene_id) is None:
                raise ValueError(
                    f"Scene not found: {scene_id}"
                )

        existing_ids = {
            item.get("id")
            for item in storyboard.get("shots", [])
        }

        if shot["id"] in existing_ids:
            shot["id"] = _new_id()

        storyboard.setdefault("shots", []).append(shot)

        reorder_shots_in_record(storyboard)

        storyboard["updated_at"] = _now()

        save_database(database, path)

        return shot.copy()

    raise ValueError("Storyboard not found.")


def update_shot(
    storyboard_id: str,
    shot_id: str,
    updates: dict,
    path: Path | str | None = None,
    validate_scene: bool = True,
) -> dict:
    database = load_database(path)

    for storyboard in database["storyboards"]:
        if storyboard.get("id") != storyboard_id:
            continue

        shots = storyboard.get("shots", [])

        for index, shot in enumerate(shots):
            if shot.get("id") != shot_id:
                continue

            merged = {
                **shot,
                **updates,
            }

            updated = validate_shot(merged)

            scene_id = updated.get("scene_id")

            if scene_id and validate_scene:
                if get_scene(scene_id) is None:
                    raise ValueError(
                        f"Scene not found: {scene_id}"
                    )

            shots[index] = updated

            reorder_shots_in_record(storyboard)

            storyboard["updated_at"] = _now()

            save_database(database, path)

            return updated.copy()

    raise ValueError("Shot not found.")


def delete_shot(
    storyboard_id: str,
    shot_id: str,
    path: Path | str | None = None,
) -> bool:
    database = load_database(path)

    for storyboard in database["storyboards"]:
        if storyboard.get("id") != storyboard_id:
            continue

        shots = storyboard.get("shots", [])

        original_count = len(shots)

        storyboard["shots"] = [
            shot for shot in shots
            if shot.get("id") != shot_id
        ]

        if len(storyboard["shots"]) == original_count:
            return False

        reorder_shots_in_record(storyboard)

        storyboard["updated_at"] = _now()

        save_database(database, path)

        return True

    return False


def reorder_shots_in_record(storyboard: dict) -> list[dict]:
    shots = storyboard.get("shots", [])

    shots.sort(
        key=lambda item: (
            int(item.get("scene_order", 1)),
            item.get("created_at", ""),
        )
    )

    for index, shot in enumerate(shots, start=1):
        shot["scene_order"] = index

    storyboard["shots"] = shots

    return shots


def reorder_shot(
    storyboard_id: str,
    shot_id: str,
    new_position: int,
    path: Path | str | None = None,
) -> list[dict]:
    database = load_database(path)

    for storyboard in database["storyboards"]:
        if storyboard.get("id") != storyboard_id:
            continue

        shots = storyboard.get("shots", [])

        selected = next(
            (
                shot for shot in shots
                if shot.get("id") == shot_id
            ),
            None,
        )

        if selected is None:
            raise ValueError("Shot not found.")

        if not 1 <= new_position <= len(shots):
            raise ValueError("Invalid shot position.")

        shots.remove(selected)

        shots.insert(
            new_position - 1,
            selected,
        )

        for index, shot in enumerate(shots, start=1):
            shot["scene_order"] = index
            shot["updated_at"] = _now()

        storyboard["shots"] = shots
        storyboard["updated_at"] = _now()

        save_database(database, path)

        return [shot.copy() for shot in shots]

    raise ValueError("Storyboard not found.")


# ---------------------------------------------------------
# STORYBOARD CALCULATIONS
# ---------------------------------------------------------

def get_storyboard_duration(
    storyboard_id: str,
    path: Path | str | None = None,
) -> float:
    storyboard = get_storyboard(storyboard_id, path)

    if not storyboard:
        raise ValueError("Storyboard not found.")

    return round(
        sum(
            float(shot.get("duration_seconds", 0))
            for shot in storyboard.get("shots", [])
        ),
        2,
    )


def get_storyboard_statistics(
    path: Path | str | None = None,
) -> dict:
    storyboards = list_storyboards(path=path)

    total_shots = sum(
        len(item.get("shots", []))
        for item in storyboards
    )

    total_duration = sum(
        float(shot.get("duration_seconds", 0))
        for item in storyboards
        for shot in item.get("shots", [])
    )

    statuses = {}

    for storyboard in storyboards:
        status = storyboard.get("status", "Draft")
        statuses[status] = statuses.get(status, 0) + 1

    return {
        "total_storyboards": len(storyboards),
        "total_shots": total_shots,
        "total_duration_seconds": round(total_duration, 2),
        "statuses": statuses,
    }


# ---------------------------------------------------------
# STORYBOARD PROMPT EXPORT
# ---------------------------------------------------------

def build_storyboard_document(
    storyboard_id: str,
    path: Path | str | None = None,
) -> dict:
    storyboard = get_storyboard(storyboard_id, path)

    if not storyboard:
        raise ValueError("Storyboard not found.")

    ordered_shots = sorted(
        storyboard.get("shots", []),
        key=lambda item: item.get("scene_order", 1),
    )

    document_shots = []

    for shot in ordered_shots:
        scene_id = shot.get("scene_id", "")

        scene_prompt = (
            get_scene_prompt(scene_id)
            if scene_id
            else ""
        )

        document_shots.append({
            "shot_number": shot.get("scene_order"),
            "title": shot.get("title"),
            "duration_seconds": shot.get("duration_seconds"),
            "shot_type": shot.get("shot_type"),
            "description": shot.get("description"),
            "camera_direction": shot.get("camera_direction"),
            "character_action": shot.get("character_action"),
            "dialogue": shot.get("dialogue"),
            "sound_effects": shot.get("sound_effects"),
            "music_notes": shot.get("music_notes"),
            "continuity_notes": shot.get("continuity_notes"),
            "transition": shot.get("transition"),
            "scene_prompt": scene_prompt,
        })

    return {
        "storyboard": {
            "id": storyboard["id"],
            "name": storyboard["name"],
            "description": storyboard["description"],
            "project_name": storyboard["project_name"],
            "genre": storyboard["genre"],
            "target_platform": storyboard["target_platform"],
            "aspect_ratio": storyboard["aspect_ratio"],
            "fps": storyboard["fps"],
            "status": storyboard["status"],
        },
        "total_shots": len(document_shots),
        "total_duration_seconds": get_storyboard_duration(
            storyboard_id,
            path,
        ),
        "shots": document_shots,
        "generated_at": _now(),
    }


def export_storyboard(
    storyboard_id: str,
    output_dir: Path | str | None = None,
    path: Path | str | None = None,
) -> Path:
    document = build_storyboard_document(
        storyboard_id,
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
            document["storyboard"]["name"]
        )
        + "_storyboard.json"
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

    st.title("Professional Storyboard Manager")

    st.caption(
        "Organize cinematic scenes into a complete shooting sequence."
    )

    tab_create, tab_manage, tab_stats = st.tabs([
        "Create Storyboard",
        "Manage Storyboards",
        "Statistics",
    ])

    # -----------------------------------------------------
    # CREATE STORYBOARD
    # -----------------------------------------------------

    with tab_create:
        st.subheader("Create new storyboard")

        with st.form("create_storyboard_form"):
            name = st.text_input(
                "Storyboard name",
                placeholder="Example: AI Influencer Episode 1",
            )

            project_name = st.text_input(
                "Project name",
            )

            description = st.text_area(
                "Description",
            )

            col1, col2 = st.columns(2)

            with col1:
                genre = st.selectbox(
                    "Genre",
                    [
                        "Cinematic",
                        "Fantasy",
                        "Sci-Fi",
                        "Horror",
                        "Action",
                        "Fashion",
                        "Lifestyle",
                        "Documentary",
                        "Commercial",
                        "Custom",
                    ],
                )

                target_platform = st.selectbox(
                    "Target platform",
                    [
                        "YouTube",
                        "YouTube Shorts",
                        "Instagram Reels",
                        "TikTok",
                        "Film",
                        "Other",
                    ],
                )

            with col2:
                aspect_ratio = st.selectbox(
                    "Aspect ratio",
                    ["16:9", "9:16", "1:1", "4:5", "21:9"],
                )

                fps = st.selectbox(
                    "Frame rate",
                    [24, 25, 30, 50, 60],
                )

            notes = st.text_area(
                "Storyboard notes",
            )

            submitted = st.form_submit_button(
                "Create Storyboard",
                type="primary",
            )

        if submitted:
            try:
                storyboard = create_storyboard({
                    "name": name,
                    "project_name": project_name,
                    "description": description,
                    "genre": genre,
                    "target_platform": target_platform,
                    "aspect_ratio": aspect_ratio,
                    "fps": fps,
                    "notes": notes,
                    "status": "Draft",
                })

                st.success(
                    f"Created storyboard: {storyboard['name']}"
                )

            except Exception as exc:
                st.error(str(exc))

    # -----------------------------------------------------
    # MANAGE STORYBOARDS
    # -----------------------------------------------------

    with tab_manage:
        st.subheader("Storyboard library")

        search = st.text_input(
            "Search storyboard",
            key="storyboard_search",
        )

        storyboards = list_storyboards(search=search)

        if not storyboards:
            st.info("Create your first storyboard.")

        for storyboard in storyboards:
            storyboard_id = storyboard["id"]

            with st.expander(
                f"{storyboard['name']} — "
                f"{len(storyboard.get('shots', []))} shots"
            ):
                st.write(storyboard.get("description", ""))

                duration = get_storyboard_duration(
                    storyboard_id
                )

                st.metric(
                    "Total duration",
                    f"{duration:.1f} seconds",
                )

                # Add a shot.
                st.markdown("**Add shot**")

                available_scenes = list_available_scenes()

                scene_options = {
                    "No linked scene": ""
                }

                for scene in available_scenes:
                    scene_id = str(scene.get("id", ""))

                    if scene_id:
                        scene_options[
                            f"{scene.get('name', 'Scene')} ({scene_id[:8]})"
                        ] = scene_id

                with st.form(
                    f"add_shot_form_{storyboard_id}"
                ):
                    shot_title = st.text_input(
                        "Shot title",
                        key=f"title_{storyboard_id}",
                    )

                    scene_label = st.selectbox(
                        "Link saved scene",
                        list(scene_options.keys()),
                        key=f"scene_{storyboard_id}",
                    )

                    shot_description = st.text_area(
                        "Shot description",
                        key=f"description_{storyboard_id}",
                    )

                    col1, col2 = st.columns(2)

                    with col1:
                        shot_type = st.selectbox(
                            "Shot type",
                            SHOT_TYPES,
                            key=f"type_{storyboard_id}",
                        )

                        shot_duration = st.number_input(
                            "Duration (seconds)",
                            min_value=0.1,
                            max_value=600.0,
                            value=8.0,
                            key=f"duration_{storyboard_id}",
                        )

                    with col2:
                        camera_direction = st.text_input(
                            "Camera direction",
                            key=f"camera_{storyboard_id}",
                        )

                        transition = st.selectbox(
                            "Transition",
                            [
                                "Cut",
                                "Fade In",
                                "Fade Out",
                                "Cross Dissolve",
                                "Wipe",
                                "Match Cut",
                                "Hard Cut",
                                "None",
                            ],
                            key=f"transition_{storyboard_id}",
                        )

                    character_action = st.text_area(
                        "Character action",
                        key=f"action_{storyboard_id}",
                    )

                    dialogue = st.text_area(
                        "Dialogue / narration",
                        key=f"dialogue_{storyboard_id}",
                    )

                    sound_effects = st.text_input(
                        "Sound effects",
                        key=f"sound_{storyboard_id}",
                    )

                    music_notes = st.text_input(
                        "Music notes",
                        key=f"music_{storyboard_id}",
                    )

                    continuity_notes = st.text_area(
                        "Continuity notes",
                        key=f"continuity_{storyboard_id}",
                    )

                    add_submitted = st.form_submit_button(
                        "Add Shot"
                    )

                if add_submitted:
                    try:
                        add_shot(
                            storyboard_id,
                            {
                                "title": shot_title,
                                "scene_id": scene_options[scene_label],
                                "description": shot_description,
                                "shot_type": shot_type,
                                "duration_seconds": shot_duration,
                                "camera_direction": camera_direction,
                                "character_action": character_action,
                                "dialogue": dialogue,
                                "sound_effects": sound_effects,
                                "music_notes": music_notes,
                                "continuity_notes": continuity_notes,
                                "transition": transition,
                                "scene_order": len(
                                    storyboard.get("shots", [])
                                ) + 1,
                            },
                        )

                        st.success("Shot added.")
                        st.rerun()

                    except Exception as exc:
                        st.error(str(exc))

                st.divider()
                st.markdown("**Shot sequence**")

                current = get_storyboard(storyboard_id)

                shots = sorted(
                    current.get("shots", []),
                    key=lambda item: item.get("scene_order", 1),
                )

                if not shots:
                    st.info("No shots added yet.")

                for shot in shots:
                    with st.container(border=True):
                        st.markdown(
                            f"**Shot {shot['scene_order']}: "
                            f"{shot['title']}**"
                        )

                        st.caption(
                            f"{shot['shot_type']} | "
                            f"{shot['duration_seconds']} sec"
                        )

                        st.write(
                            shot.get("description") or "No description."
                        )

                        if shot.get("camera_direction"):
                            st.write(
                                "Camera: "
                                + shot["camera_direction"]
                            )

                        if shot.get("continuity_notes"):
                            st.caption(
                                "Continuity: "
                                + shot["continuity_notes"]
                            )

                        left, right = st.columns(2)

                        with left:
                            if st.button(
                                "Move Up",
                                key=f"up_{storyboard_id}_{shot['id']}",
                                disabled=shot["scene_order"] == 1,
                            ):
                                reorder_shot(
                                    storyboard_id,
                                    shot["id"],
                                    shot["scene_order"] - 1,
                                )
                                st.rerun()

                        with right:
                            if st.button(
                                "Move Down",
                                key=f"down_{storyboard_id}_{shot['id']}",
                                disabled=shot["scene_order"] == len(shots),
                            ):
                                reorder_shot(
                                    storyboard_id,
                                    shot["id"],
                                    shot["scene_order"] + 1,
                                )
                                st.rerun()

                        with st.expander("Edit or remove shot"):
                            with st.form(
                                f"edit_shot_{storyboard_id}_{shot['id']}"
                            ):
                                new_title = st.text_input(
                                    "Title",
                                    value=shot["title"],
                                )

                                new_description = st.text_area(
                                    "Description",
                                    value=shot["description"],
                                )

                                new_camera = st.text_input(
                                    "Camera direction",
                                    value=shot["camera_direction"],
                                )

                                new_action = st.text_area(
                                    "Character action",
                                    value=shot["character_action"],
                                )

                                new_duration = st.number_input(
                                    "Duration",
                                    min_value=0.1,
                                    max_value=600.0,
                                    value=float(
                                        shot["duration_seconds"]
                                    ),
                                )

                                new_continuity = st.text_area(
                                    "Continuity notes",
                                    value=shot["continuity_notes"],
                                )

                                save_shot = st.form_submit_button(
                                    "Save Shot Changes"
                                )

                            if save_shot:
                                try:
                                    update_shot(
                                        storyboard_id,
                                        shot["id"],
                                        {
                                            "title": new_title,
                                            "description": new_description,
                                            "camera_direction": new_camera,
                                            "character_action": new_action,
                                            "duration_seconds": new_duration,
                                            "continuity_notes": new_continuity,
                                        },
                                    )

                                    st.success("Shot updated.")
                                    st.rerun()

                                except Exception as exc:
                                    st.error(str(exc))

                            confirm_delete = st.checkbox(
                                "Confirm shot deletion",
                                key=f"confirm_shot_{shot['id']}",
                            )

                            if st.button(
                                "Delete Shot",
                                key=f"delete_shot_{shot['id']}",
                                disabled=not confirm_delete,
                            ):
                                delete_shot(
                                    storyboard_id,
                                    shot["id"],
                                )
                                st.success("Shot deleted.")
                                st.rerun()

                st.divider()

                # Storyboard operations.
                col1, col2, col3 = st.columns(3)

                with col1:
                    if st.button(
                        "Export Storyboard",
                        key=f"export_{storyboard_id}",
                    ):
                        try:
                            output = export_storyboard(
                                storyboard_id
                            )
                            st.success(f"Exported: {output}")
                        except Exception as exc:
                            st.error(str(exc))

                with col2:
                    if st.button(
                        "Duplicate Storyboard",
                        key=f"duplicate_{storyboard_id}",
                    ):
                        try:
                            duplicate_storyboard(storyboard_id)
                            st.success("Storyboard duplicated.")
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))

                with col3:
                    if st.button(
                        "Delete Storyboard",
                        key=f"delete_{storyboard_id}",
                    ):
                        st.session_state[
                            f"confirm_storyboard_{storyboard_id}"
                        ] = True

                if st.session_state.get(
                    f"confirm_storyboard_{storyboard_id}",
                    False,
                ):
                    st.warning(
                        "Confirm that you want to delete this storyboard."
                    )

                    if st.button(
                        "Yes, permanently delete",
                        key=f"confirm_delete_{storyboard_id}",
                    ):
                        delete_storyboard(storyboard_id)
                        st.session_state[
                            f"confirm_storyboard_{storyboard_id}"
                        ] = False
                        st.rerun()

                    if st.button(
                        "Cancel deletion",
                        key=f"cancel_delete_{storyboard_id}",
                    ):
                        st.session_state[
                            f"confirm_storyboard_{storyboard_id}"
                        ] = False
                        st.rerun()

    # -----------------------------------------------------
    # STATISTICS
    # -----------------------------------------------------

    with tab_stats:
        stats = get_storyboard_statistics()

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Storyboards",
            stats["total_storyboards"],
        )

        col2.metric(
            "Total shots",
            stats["total_shots"],
        )

        col3.metric(
            "Total duration",
            f"{stats['total_duration_seconds']:.1f} sec",
        )

        st.subheader("Storyboard status")

        if stats["statuses"]:
            for status, count in stats["statuses"].items():
                st.write(f"- {status}: {count}")
        else:
            st.info("No storyboard data available.")


# ---------------------------------------------------------
# BUILT-IN TESTS
# ---------------------------------------------------------

def run_tests() -> bool:
    import tempfile
    import unittest

    class StoryboardTests(unittest.TestCase):

        def setUp(self):
            self.temp = tempfile.TemporaryDirectory()
            self.root = Path(self.temp.name)
            self.database = self.root / "storyboards.json"

        def tearDown(self):
            self.temp.cleanup()

        def sample_storyboard(self):
            return {
                "name": "Episode One",
                "description": "A cinematic opening.",
                "project_name": "AI Influencer Film",
                "genre": "Sci-Fi",
                "target_platform": "YouTube",
                "aspect_ratio": "16:9",
                "fps": 24,
                "status": "Draft",
            }

        def sample_shot(self, title="Opening Shot", order=1):
            return {
                "title": title,
                "description": "A city appears.",
                "shot_type": "Establishing Shot",
                "duration_seconds": 8,
                "scene_order": order,
                "camera_direction": "Slow push in",
                "character_action": "",
                "dialogue": "",
                "sound_effects": "Wind",
                "music_notes": "Suspense music",
                "continuity_notes": "Keep the blue color palette.",
                "transition": "Fade In",
            }

        def create_sample(self):
            return create_storyboard(
                self.sample_storyboard(),
                self.database,
            )

        def test_empty_database(self):
            self.assertEqual(
                load_database(self.database)["storyboards"],
                [],
            )

        def test_create_storyboard(self):
            storyboard = self.create_sample()

            self.assertTrue(storyboard["id"])
            self.assertEqual(storyboard["name"], "Episode One")

        def test_reject_empty_name(self):
            details = self.sample_storyboard()
            details["name"] = ""

            with self.assertRaises(ValueError):
                create_storyboard(details, self.database)

        def test_get_storyboard(self):
            storyboard = self.create_sample()

            result = get_storyboard(
                storyboard["id"],
                self.database,
            )

            self.assertEqual(result["id"], storyboard["id"])

        def test_update_storyboard(self):
            storyboard = self.create_sample()

            result = update_storyboard(
                storyboard["id"],
                {"name": "Episode Updated"},
                self.database,
            )

            self.assertEqual(result["name"], "Episode Updated")

        def test_delete_storyboard(self):
            storyboard = self.create_sample()

            self.assertTrue(
                delete_storyboard(
                    storyboard["id"],
                    self.database,
                )
            )

            self.assertIsNone(
                get_storyboard(
                    storyboard["id"],
                    self.database,
                )
            )

        def test_add_shot(self):
            storyboard = self.create_sample()

            shot = add_shot(
                storyboard["id"],
                self.sample_shot(),
                path=self.database,
                validate_scene=False,
            )

            self.assertTrue(shot["id"])

        def test_add_shot_rejects_empty_title(self):
            storyboard = self.create_sample()
            shot = self.sample_shot()
            shot["title"] = ""

            with self.assertRaises(ValueError):
                add_shot(
                    storyboard["id"],
                    shot,
                    path=self.database,
                    validate_scene=False,
                )

        def test_add_shot_rejects_invalid_duration(self):
            storyboard = self.create_sample()
            shot = self.sample_shot()
            shot["duration_seconds"] = 900

            with self.assertRaises(ValueError):
                add_shot(
                    storyboard["id"],
                    shot,
                    path=self.database,
                    validate_scene=False,
                )

        def test_update_shot(self):
            storyboard = self.create_sample()

            shot = add_shot(
                storyboard["id"],
                self.sample_shot(),
                path=self.database,
                validate_scene=False,
            )

            updated = update_shot(
                storyboard["id"],
                shot["id"],
                {"title": "Updated Opening"},
                path=self.database,
                validate_scene=False,
            )

            self.assertEqual(
                updated["title"],
                "Updated Opening",
            )

        def test_delete_shot(self):
            storyboard = self.create_sample()

            shot = add_shot(
                storyboard["id"],
                self.sample_shot(),
                path=self.database,
                validate_scene=False,
            )

            self.assertTrue(
                delete_shot(
                    storyboard["id"],
                    shot["id"],
                    self.database,
                )
            )

        def test_reorder_shots(self):
            storyboard = self.create_sample()

            first = add_shot(
                storyboard["id"],
                self.sample_shot("First", 1),
                path=self.database,
                validate_scene=False,
            )

            second = add_shot(
                storyboard["id"],
                self.sample_shot("Second", 2),
                path=self.database,
                validate_scene=False,
            )

            reordered = reorder_shot(
                storyboard["id"],
                second["id"],
                1,
                self.database,
            )

            self.assertEqual(
                reordered[0]["id"],
                second["id"],
            )

            self.assertEqual(
                reordered[0]["scene_order"],
                1,
            )

        def test_duration_calculation(self):
            storyboard = self.create_sample()

            add_shot(
                storyboard["id"],
                self.sample_shot("First", 1),
                path=self.database,
                validate_scene=False,
            )

            add_shot(
                storyboard["id"],
                {
                    **self.sample_shot("Second", 2),
                    "duration_seconds": 10,
                },
                path=self.database,
                validate_scene=False,
            )

            duration = get_storyboard_duration(
                storyboard["id"],
                self.database,
            )

            self.assertEqual(duration, 18)

        def test_duplicate_storyboard(self):
            storyboard = self.create_sample()

            add_shot(
                storyboard["id"],
                self.sample_shot(),
                path=self.database,
                validate_scene=False,
            )

            duplicate = duplicate_storyboard(
                storyboard["id"],
                path=self.database,
            )

            self.assertNotEqual(
                duplicate["id"],
                storyboard["id"],
            )

            self.assertEqual(
                len(duplicate["shots"]),
                1,
            )

        def test_search_storyboards(self):
            self.create_sample()

            results = list_storyboards(
                search="Episode",
                path=self.database,
            )

            self.assertEqual(len(results), 1)

        def test_statistics(self):
            storyboard = self.create_sample()

            add_shot(
                storyboard["id"],
                self.sample_shot(),
                path=self.database,
                validate_scene=False,
            )

            stats = get_storyboard_statistics(self.database)

            self.assertEqual(stats["total_storyboards"], 1)
            self.assertEqual(stats["total_shots"], 1)
            self.assertEqual(stats["total_duration_seconds"], 8)

        def test_export_storyboard(self):
            storyboard = self.create_sample()

            add_shot(
                storyboard["id"],
                self.sample_shot(),
                path=self.database,
                validate_scene=False,
            )

            output = export_storyboard(
                storyboard["id"],
                self.root / "exports",
                self.database,
            )

            self.assertTrue(output.exists())

            with output.open("r", encoding="utf-8") as file:
                data = json.load(file)

            self.assertEqual(data["total_shots"], 1)

        def test_build_storyboard_document(self):
            storyboard = self.create_sample()

            add_shot(
                storyboard["id"],
                self.sample_shot(),
                path=self.database,
                validate_scene=False,
            )

            document = build_storyboard_document(
                storyboard["id"],
                self.database,
            )

            self.assertEqual(
                document["storyboard"]["name"],
                "Episode One",
            )

            self.assertEqual(len(document["shots"]), 1)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        StoryboardTests
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

    print("AI Influencer Studio - Storyboard Manager")
    print("Run tests with:")
    print("python -m modules.storyboard_manager --test")
