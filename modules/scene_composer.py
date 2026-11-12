
"""
AI Influencer Studio
File 35: modules/scene_composer.py

Cinematic Scene Composer

Features:
- Create and manage cinematic scenes.
- Link saved characters, outfits and poses.
- Configure camera, environment, lighting and atmosphere.
- Generate reusable cinematic prompts.
- Save, edit, duplicate and delete scenes.
- Export scenes as JSON.

This module prepares prompts. It does not perform AI generation.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------
# OPTIONAL MODULE INTEGRATION
# ---------------------------------------------------------

try:
    from modules import character_consistency
except ImportError:
    character_consistency = None

try:
    from modules import outfit_manager
except ImportError:
    outfit_manager = None

try:
    from modules import pose_library
except ImportError:
    pose_library = None


# ---------------------------------------------------------
# PATHS AND SETTINGS
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
SCENE_DIR = PROJECT_ROOT / "outputs" / "scenes"

DATABASE_FILE = DATA_DIR / "scenes.json"

CAMERA_SHOTS = [
    "Extreme Close-up",
    "Close-up",
    "Medium Close-up",
    "Medium Shot",
    "Medium Full Shot",
    "Full Body",
    "Wide Shot",
    "Extreme Wide Shot",
    "Establishing Shot",
]

CAMERA_ANGLES = [
    "Eye Level",
    "Low Angle",
    "High Angle",
    "Bird's Eye View",
    "Worm's Eye View",
    "Dutch Angle",
    "Over-the-Shoulder",
    "Profile View",
    "Three-Quarter View",
]

CAMERA_MOVEMENTS = [
    "Static",
    "Slow Push In",
    "Slow Pull Out",
    "Pan Left",
    "Pan Right",
    "Tilt Up",
    "Tilt Down",
    "Tracking Shot",
    "Orbit Shot",
    "Crane Shot",
    "Handheld",
]

LIGHTING_OPTIONS = [
    "Natural Daylight",
    "Golden Hour",
    "Soft Studio Lighting",
    "Cinematic Rembrandt",
    "Dramatic Side Lighting",
    "Backlighting",
    "Neon Lighting",
    "Moonlight",
    "Low-Key Lighting",
    "High-Key Lighting",
]

WEATHER_OPTIONS = [
    "Clear",
    "Cloudy",
    "Rain",
    "Heavy Rain",
    "Snow",
    "Fog",
    "Storm",
    "Dust",
    "None",
]

VISUAL_STYLES = [
    "Photorealistic",
    "Hollywood Cinematic",
    "Realistic 3D CGI",
    "Fashion Editorial",
    "Documentary",
    "Fantasy",
    "Sci-Fi",
    "Anime",
    "Commercial Photography",
    "Custom",
]

SCENE_STATUSES = [
    "Draft",
    "Ready",
    "Approved",
    "Archived",
]

SCENE_FIELDS = [
    "name",
    "description",
    "scene_type",
    "location",
    "background",
    "time_of_day",
    "weather",
    "atmosphere",
    "camera_shot",
    "camera_angle",
    "camera_movement",
    "lens",
    "lighting",
    "color_palette",
    "visual_style",
    "special_effects",
    "action",
    "duration_seconds",
    "aspect_ratio",
    "negative_prompt",
]


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_id(value: str) -> str:
    value = str(value or "").strip()

    if not value:
        raise ValueError("ID is required.")

    return re.sub(
        r"[^a-zA-Z0-9_-]",
        "_",
        value,
    )[:100]


def _ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SCENE_DIR.mkdir(parents=True, exist_ok=True)


def _clean(value: Any, limit: int = 2000) -> str:
    return str(value or "").strip()[:limit]


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
            "scenes": [],
        }

    try:
        with database_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            raise ValueError("Invalid scene database.")

        if not isinstance(data.get("scenes"), list):
            data["scenes"] = []

        data.setdefault("version", 1)
        data.setdefault("updated_at", _now())

        return data

    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(
            f"Could not load scene database: {exc}"
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
# LINKED MODULE DATA
# ---------------------------------------------------------

def list_characters() -> list[dict]:
    if character_consistency is None:
        return []

    try:
        return character_consistency.list_characters()
    except Exception:
        return []


def list_outfits() -> list[dict]:
    if outfit_manager is None:
        return []

    try:
        return outfit_manager.list_outfits()
    except Exception:
        return []


def list_poses() -> list[dict]:
    if pose_library is None:
        return []

    try:
        return pose_library.list_poses()
    except Exception:
        return []


def get_character(character_id: str) -> dict | None:
    if not character_id or character_consistency is None:
        return None

    return character_consistency.get_character(character_id)


def get_outfit(outfit_id: str) -> dict | None:
    if not outfit_id or outfit_manager is None:
        return None

    return outfit_manager.get_outfit(outfit_id)


def get_pose(pose_id: str) -> dict | None:
    if not pose_id or pose_library is None:
        return None

    return pose_library.get_pose(pose_id)


# ---------------------------------------------------------
# VALIDATION
# ---------------------------------------------------------

def _validate_link(
    field: str,
    value: str,
    lookup_function,
) -> None:
    if not value:
        return

    if lookup_function is None:
        raise ValueError(
            f"Cannot validate {field}: its module is unavailable."
        )

    try:
        result = lookup_function(value)
    except Exception as exc:
        raise ValueError(
            f"Could not validate {field}: {exc}"
        ) from exc

    if not result:
        raise ValueError(
            f"Selected {field} was not found: {value}"
        )


def validate_scene(
    details: dict,
    validate_links: bool = True,
) -> dict:
    if not isinstance(details, dict):
        raise ValueError("Scene details must be a dictionary.")

    name = _clean(details.get("name"), 100)

    if not name:
        raise ValueError("Scene name is required.")

    duration = details.get("duration_seconds", 8)

    try:
        duration = int(duration)
    except (ValueError, TypeError):
        raise ValueError("Duration must be a number.")

    if not 1 <= duration <= 600:
        raise ValueError("Duration must be between 1 and 600 seconds.")

    cleaned = {}

    for field in SCENE_FIELDS:
        value = details.get(field, "")

        if field == "name":
            cleaned[field] = name

        elif field == "duration_seconds":
            cleaned[field] = duration

        else:
            cleaned[field] = _clean(value)

    cleaned["character_id"] = _clean(
        details.get("character_id")
    )

    cleaned["outfit_id"] = _clean(
        details.get("outfit_id")
    )

    cleaned["pose_id"] = _clean(
        details.get("pose_id")
    )

    status = _clean(
        details.get("status", "Draft")
    )

    if status not in SCENE_STATUSES:
        raise ValueError("Invalid scene status.")

    cleaned["status"] = status

    if validate_links:
        if cleaned["character_id"]:
            _validate_link(
                "character",
                cleaned["character_id"],
                get_character if character_consistency else None,
            )

        if cleaned["outfit_id"]:
            _validate_link(
                "outfit",
                cleaned["outfit_id"],
                get_outfit if outfit_manager else None,
            )

        if cleaned["pose_id"]:
            _validate_link(
                "pose",
                cleaned["pose_id"],
                get_pose if pose_library else None,
            )

    return cleaned


# ---------------------------------------------------------
# SCENE CRUD
# ---------------------------------------------------------

def create_scene(
    details: dict,
    path: Path | str | None = None,
    validate_links: bool = True,
) -> dict:
    database = load_database(path)

    cleaned = validate_scene(
        details,
        validate_links=validate_links,
    )

    scene = {
        "id": uuid.uuid4().hex[:12],
        **cleaned,
        "created_at": _now(),
        "updated_at": _now(),
    }

    database["scenes"].append(scene)
    save_database(database, path)

    return scene.copy()


def get_scene(
    scene_id: str,
    path: Path | str | None = None,
) -> dict | None:
    database = load_database(path)

    for scene in database["scenes"]:
        if scene.get("id") == scene_id:
            return scene.copy()

    return None


def list_scenes(
    search: str = "",
    status: str = "",
    path: Path | str | None = None,
) -> list[dict]:
    database = load_database(path)

    search_text = str(search or "").strip().lower()
    results = []

    for scene in database["scenes"]:
        if status and scene.get("status") != status:
            continue

        searchable = " ".join(
            str(scene.get(field, ""))
            for field in SCENE_FIELDS
        ).lower()

        if search_text and search_text not in searchable:
            continue

        results.append(scene.copy())

    results.sort(
        key=lambda item: item.get("updated_at", ""),
        reverse=True,
    )

    return results


def update_scene(
    scene_id: str,
    updates: dict,
    path: Path | str | None = None,
    validate_links: bool = True,
) -> dict:
    database = load_database(path)

    for index, scene in enumerate(database["scenes"]):
        if scene.get("id") != scene_id:
            continue

        merged = {
            **scene,
            **updates,
        }

        cleaned = validate_scene(
            merged,
            validate_links=validate_links,
        )

        updated = {
            **scene,
            **cleaned,
            "updated_at": _now(),
        }

        database["scenes"][index] = updated
        save_database(database, path)

        return updated.copy()

    raise ValueError("Scene not found.")


def duplicate_scene(
    scene_id: str,
    new_name: str | None = None,
    path: Path | str | None = None,
    validate_links: bool = True,
) -> dict:
    original = get_scene(scene_id, path)

    if not original:
        raise ValueError("Scene not found.")

    details = {
        field: original.get(field, "")
        for field in SCENE_FIELDS
    }

    details.update({
        "character_id": original.get("character_id", ""),
        "outfit_id": original.get("outfit_id", ""),
        "pose_id": original.get("pose_id", ""),
        "status": "Draft",
    })

    details["name"] = (
        new_name or f"{original['name']} Copy"
    )

    return create_scene(
        details,
        path=path,
        validate_links=validate_links,
    )


def delete_scene(
    scene_id: str,
    path: Path | str | None = None,
) -> bool:
    database = load_database(path)

    original_count = len(database["scenes"])

    database["scenes"] = [
        scene for scene in database["scenes"]
        if scene.get("id") != scene_id
    ]

    if len(database["scenes"]) == original_count:
        return False

    save_database(database, path)
    return True


# ---------------------------------------------------------
# SCENE PROMPT BUILDER
# ---------------------------------------------------------

def build_scene_prompt(
    scene_id: str | None = None,
    scene: dict | None = None,
    include_negative: bool = True,
) -> str:
    """Build a cinematic prompt from a saved scene."""

    if scene is None:
        if not scene_id:
            raise ValueError("Provide a scene ID or scene data.")

        scene = get_scene(scene_id)

    if not scene:
        raise ValueError("Scene not found.")

    sections = []

    sections.append(
        f"Cinematic scene: {scene.get('name', 'Untitled Scene')}"
    )

    # Character identity.
    character_id = scene.get("character_id", "")

    if character_id:
        character = get_character(character_id)

        if character:
            try:
                identity = (
                    character_consistency.build_identity_prompt(
                        character_id
                    )
                )

                if identity:
                    sections.append(
                        f"Character identity:\n{identity}"
                    )

            except Exception:
                sections.append(
                    f"Maintain character identity: {character_id}"
                )

    # Outfit.
    outfit_id = scene.get("outfit_id", "")

    if outfit_id:
        outfit = get_outfit(outfit_id)

        if outfit:
            try:
                outfit_prompt = outfit_manager.build_outfit_prompt(
                    outfit_id
                )

                if outfit_prompt:
                    sections.append(
                        f"Outfit:\n{outfit_prompt}"
                    )

            except Exception:
                sections.append(
                    f"Use saved outfit: {outfit.get('name', outfit_id)}"
                )

    # Pose.
    pose_id = scene.get("pose_id", "")

    if pose_id:
        pose = get_pose(pose_id)

        if pose:
            try:
                pose_prompt = pose_library.build_pose_prompt(
                    pose_id=pose_id
                )

                if pose_prompt:
                    sections.append(
                        f"Character pose:\n{pose_prompt}"
                    )

            except Exception:
                sections.append(
                    f"Use saved pose: {pose.get('name', pose_id)}"
                )

    # Environment and camera details.
    prompt_fields = [
        ("Scene description", "description"),
        ("Scene type", "scene_type"),
        ("Location", "location"),
        ("Background", "background"),
        ("Time of day", "time_of_day"),
        ("Weather", "weather"),
        ("Atmosphere", "atmosphere"),
        ("Camera shot", "camera_shot"),
        ("Camera angle", "camera_angle"),
        ("Camera movement", "camera_movement"),
        ("Lens", "lens"),
        ("Lighting", "lighting"),
        ("Color palette", "color_palette"),
        ("Visual style", "visual_style"),
        ("Action", "action"),
        ("Special effects", "special_effects"),
        ("Aspect ratio", "aspect_ratio"),
    ]

    for label, field in prompt_fields:
        value = str(scene.get(field, "")).strip()

        if value:
            sections.append(f"{label}: {value}")

    duration = scene.get("duration_seconds")

    if duration:
        sections.append(
            f"Target scene duration: {duration} seconds."
        )

    sections.append(
        "Maintain consistent character identity, outfit details, "
        "body proportions and visual continuity throughout the scene."
    )

    if include_negative:
        negative = str(
            scene.get("negative_prompt", "")
        ).strip()

        if negative:
            sections.append(
                f"Negative prompt: {negative}"
            )

    return "\n\n".join(sections)


# ---------------------------------------------------------
# SCENE STATISTICS
# ---------------------------------------------------------

def get_statistics(
    path: Path | str | None = None,
) -> dict:
    scenes = list_scenes(path=path)

    statuses = {}

    for scene in scenes:
        status = scene.get("status", "Draft")
        statuses[status] = statuses.get(status, 0) + 1

    return {
        "total_scenes": len(scenes),
        "draft_scenes": statuses.get("Draft", 0),
        "ready_scenes": statuses.get("Ready", 0),
        "approved_scenes": statuses.get("Approved", 0),
        "archived_scenes": statuses.get("Archived", 0),
        "linked_characters": len({
            scene.get("character_id")
            for scene in scenes
            if scene.get("character_id")
        }),
        "total_duration_seconds": sum(
            int(scene.get("duration_seconds", 0))
            for scene in scenes
        ),
        "statuses": statuses,
    }


# ---------------------------------------------------------
# EXPORT
# ---------------------------------------------------------

def export_scene(
    scene_id: str,
    output_dir: Path | str | None = None,
) -> Path:
    scene = get_scene(scene_id)

    if not scene:
        raise ValueError("Scene not found.")

    destination = (
        Path(output_dir)
        if output_dir
        else SCENE_DIR
    )

    destination.mkdir(parents=True, exist_ok=True)

    filename = (
        f"scene_{_safe_id(scene_id)}.json"
    )

    output_path = destination / filename

    payload = {
        "scene": scene,
        "generated_prompt": build_scene_prompt(
            scene=scene
        ),
        "exported_at": _now(),
    }

    temporary = output_path.with_name(
        output_path.name + ".tmp"
    )

    with temporary.open("w", encoding="utf-8") as file:
        json.dump(
            payload,
            file,
            indent=4,
            ensure_ascii=False,
        )

    temporary.replace(output_path)

    return output_path


def export_all_scenes(
    output_path: Path | str,
    path: Path | str | None = None,
) -> Path:
    """Export all saved scenes and their prompts."""
    scenes = list_scenes(path=path)

    payload = {
        "exported_at": _now(),
        "total_scenes": len(scenes),
        "scenes": [
            {
                "scene": scene,
                "prompt": build_scene_prompt(scene=scene),
            }
            for scene in scenes
        ],
    }

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    temporary = output.with_name(output.name + ".tmp")

    with temporary.open("w", encoding="utf-8") as file:
        json.dump(
            payload,
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
    _ensure_directories()

    st.title("Cinematic Scene Composer")

    st.caption(
        "Combine characters, outfits, poses, camera settings "
        "and environments into reusable cinematic scenes."
    )

    tab_create, tab_scenes, tab_stats = st.tabs([
        "Create Scene",
        "Scene Library",
        "Statistics",
    ])

    characters = list_characters()
    outfits = list_outfits()
    poses = list_poses()

    # -----------------------------------------------------
    # CREATE SCENE
    # -----------------------------------------------------

    with tab_create:
        st.subheader("New cinematic scene")

        character_options = {
            "None": ""
        }

        for item in characters:
            item_id = str(item.get("id", ""))

            if item_id:
                character_options[
                    f"{item.get('name', 'Character')} ({item_id[:8]})"
                ] = item_id

        outfit_options = {
            "None": ""
        }

        for item in outfits:
            item_id = str(item.get("id", ""))

            if item_id:
                outfit_options[
                    f"{item.get('name', 'Outfit')} ({item_id[:8]})"
                ] = item_id

        pose_options = {
            "None": ""
        }

        for item in poses:
            item_id = str(item.get("id", ""))

            if item_id:
                pose_options[
                    f"{item.get('name', 'Pose')} ({item_id[:8]})"
                ] = item_id

        with st.form("scene_create_form"):

            name = st.text_input(
                "Scene name",
                placeholder="Example: Hero enters the city",
            )

            description = st.text_area(
                "Scene description",
                placeholder="Describe what happens in the scene...",
            )

            col1, col2 = st.columns(2)

            with col1:
                character_label = st.selectbox(
                    "Select character",
                    list(character_options.keys()),
                )

                outfit_label = st.selectbox(
                    "Select outfit",
                    list(outfit_options.keys()),
                )

                pose_label = st.selectbox(
                    "Select pose",
                    list(pose_options.keys()),
                )

                scene_type = st.text_input(
                    "Scene type",
                    placeholder="Action, fashion, portrait, fantasy...",
                )

                location = st.text_input(
                    "Location",
                    placeholder="Example: Futuristic city rooftop",
                )

                background = st.text_area(
                    "Background",
                    placeholder="Describe the environment...",
                )

                time_of_day = st.selectbox(
                    "Time of day",
                    [
                        "Morning",
                        "Afternoon",
                        "Golden Hour",
                        "Sunset",
                        "Night",
                        "Midnight",
                        "Custom",
                    ],
                )

                weather = st.selectbox(
                    "Weather",
                    WEATHER_OPTIONS,
                )

                atmosphere = st.text_input(
                    "Atmosphere",
                    placeholder="Mysterious, dramatic, peaceful...",
                )

            with col2:
                camera_shot = st.selectbox(
                    "Camera shot",
                    CAMERA_SHOTS,
                )

                camera_angle = st.selectbox(
                    "Camera angle",
                    CAMERA_ANGLES,
                )

                camera_movement = st.selectbox(
                    "Camera movement",
                    CAMERA_MOVEMENTS,
                )

                lens = st.text_input(
                    "Lens",
                    value="35mm cinematic lens",
                )

                lighting = st.selectbox(
                    "Lighting",
                    LIGHTING_OPTIONS,
                )

                color_palette = st.text_input(
                    "Color palette",
                    placeholder="Teal and orange, icy blue...",
                )

                visual_style = st.selectbox(
                    "Visual style",
                    VISUAL_STYLES,
                )

                special_effects = st.text_area(
                    "Special effects",
                    placeholder="Particles, fog, sparks, rain...",
                )

                action = st.text_area(
                    "Character action",
                    placeholder="Describe the character's movement...",
                )

            col3, col4, col5 = st.columns(3)

            with col3:
                duration = st.number_input(
                    "Duration (seconds)",
                    min_value=1,
                    max_value=600,
                    value=8,
                )

            with col4:
                aspect_ratio = st.selectbox(
                    "Aspect ratio",
                    ["16:9", "9:16", "1:1", "4:5", "21:9"],
                )

            with col5:
                status = st.selectbox(
                    "Status",
                    SCENE_STATUSES,
                )

            negative_prompt = st.text_area(
                "Negative prompt",
                placeholder="Distorted face, extra fingers, inconsistent clothing...",
            )

            submitted = st.form_submit_button(
                "Create Scene",
                type="primary",
            )

        if submitted:
            try:
                scene = create_scene({
                    "name": name,
                    "description": description,
                    "character_id": character_options[
                        character_label
                    ],
                    "outfit_id": outfit_options[
                        outfit_label
                    ],
                    "pose_id": pose_options[pose_label],
                    "scene_type": scene_type,
                    "location": location,
                    "background": background,
                    "time_of_day": time_of_day,
                    "weather": weather,
                    "atmosphere": atmosphere,
                    "camera_shot": camera_shot,
                    "camera_angle": camera_angle,
                    "camera_movement": camera_movement,
                    "lens": lens,
                    "lighting": lighting,
                    "color_palette": color_palette,
                    "visual_style": visual_style,
                    "special_effects": special_effects,
                    "action": action,
                    "duration_seconds": int(duration),
                    "aspect_ratio": aspect_ratio,
                    "negative_prompt": negative_prompt,
                    "status": status,
                })

                st.success(
                    f"Scene created: {scene['name']}"
                )

            except Exception as exc:
                st.error(f"Could not create scene: {exc}")

    # -----------------------------------------------------
    # SCENE LIBRARY
    # -----------------------------------------------------

    with tab_scenes:
        st.subheader("Saved scenes")

        search = st.text_input(
            "Search scenes",
            placeholder="Search scene name, location or description",
            key="scene_search",
        )

        status_filter = st.selectbox(
            "Filter by status",
            ["All"] + SCENE_STATUSES,
        )

        scenes = list_scenes(
            search=search,
            status=(
                "" if status_filter == "All"
                else status_filter
            ),
        )

        if not scenes:
            st.info("No matching scenes found.")

        for scene in scenes:
            with st.expander(
                f"{scene['name']} — {scene['status']}"
            ):
                st.write(
                    scene.get("description")
                    or "No scene description."
                )

                st.caption(
                    f"Duration: {scene['duration_seconds']} seconds"
                )

                st.caption(
                    f"Aspect ratio: {scene['aspect_ratio']}"
                )

                st.caption(
                    f"Character ID: {scene.get('character_id') or 'None'}"
                )

                st.caption(
                    f"Outfit ID: {scene.get('outfit_id') or 'None'}"
                )

                st.caption(
                    f"Pose ID: {scene.get('pose_id') or 'None'}"
                )

                prompt = build_scene_prompt(scene=scene)

                st.text_area(
                    "Generated cinematic prompt",
                    value=prompt,
                    height=240,
                    key=f"scene_prompt_{scene['id']}",
                )

                st.download_button(
                    "Download prompt",
                    data=prompt,
                    file_name=f"scene_{scene['id']}.txt",
                    mime="text/plain",
                    key=f"scene_prompt_download_{scene['id']}",
                )

                st.divider()
                st.markdown("**Edit scene**")

                with st.form(
                    f"edit_scene_{scene['id']}"
                ):
                    edit_name = st.text_input(
                        "Scene name",
                        value=scene.get("name", ""),
                    )

                    edit_description = st.text_area(
                        "Description",
                        value=scene.get("description", ""),
                    )

                    edit_location = st.text_input(
                        "Location",
                        value=scene.get("location", ""),
                    )

                    edit_background = st.text_area(
                        "Background",
                        value=scene.get("background", ""),
                    )

                    edit_action = st.text_area(
                        "Action",
                        value=scene.get("action", ""),
                    )

                    edit_lighting = st.selectbox(
                        "Lighting",
                        LIGHTING_OPTIONS,
                        index=(
                            LIGHTING_OPTIONS.index(
                                scene["lighting"]
                            )
                            if scene.get("lighting") in LIGHTING_OPTIONS
                            else 0
                        ),
                    )

                    edit_status = st.selectbox(
                        "Status",
                        SCENE_STATUSES,
                        index=SCENE_STATUSES.index(
                            scene.get("status", "Draft")
                        ),
                    )

                    edit_save = st.form_submit_button(
                        "Save Changes"
                    )

                if edit_save:
                    try:
                        update_scene(
                            scene["id"],
                            {
                                "name": edit_name,
                                "description": edit_description,
                                "location": edit_location,
                                "background": edit_background,
                                "action": edit_action,
                                "lighting": edit_lighting,
                                "status": edit_status,
                            },
                        )

                        st.success("Scene updated.")
                        st.rerun()

                    except Exception as exc:
                        st.error(str(exc))

                col_a, col_b, col_c = st.columns(3)

                with col_a:
                    if st.button(
                        "Duplicate",
                        key=f"duplicate_scene_{scene['id']}",
                    ):
                        try:
                            duplicate_scene(scene["id"])
                            st.success("Scene duplicated.")
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))

                with col_b:
                    if st.button(
                        "Export JSON",
                        key=f"export_scene_{scene['id']}",
                    ):
                        try:
                            output = export_scene(scene["id"])
                            st.success(f"Exported: {output}")
                        except Exception as exc:
                            st.error(str(exc))

                with col_c:
                    confirm = st.checkbox(
                        "Confirm delete",
                        key=f"confirm_scene_delete_{scene['id']}",
                    )

                    if st.button(
                        "Delete",
                        key=f"delete_scene_{scene['id']}",
                        disabled=not confirm,
                    ):
                        if delete_scene(scene["id"]):
                            st.success("Scene deleted.")
                            st.rerun()
                        else:
                            st.error("Scene not found.")

        st.divider()

        if st.button("Export All Scenes"):
            try:
                output = export_all_scenes(
                    SCENE_DIR / "all_scenes.json"
                )

                st.success(f"Exported: {output}")

            except Exception as exc:
                st.error(str(exc))

    # -----------------------------------------------------
    # STATISTICS
    # -----------------------------------------------------

    with tab_stats:
        st.subheader("Scene statistics")

        stats = get_statistics()

        col1, col2, col3 = st.columns(3)

        col1.metric("Total Scenes", stats["total_scenes"])
        col2.metric("Draft Scenes", stats["draft_scenes"])
        col3.metric("Approved Scenes", stats["approved_scenes"])

        col4, col5, col6 = st.columns(3)

        col4.metric("Ready Scenes", stats["ready_scenes"])
        col5.metric("Linked Characters", stats["linked_characters"])
        col6.metric(
            "Total Duration",
            f"{stats['total_duration_seconds']} sec",
        )

        st.markdown("**Scene status breakdown**")

        if stats["statuses"]:
            for label, count in stats["statuses"].items():
                st.write(f"- {label}: {count}")
        else:
            st.info("No scenes have been created.")


# ---------------------------------------------------------
# BUILT-IN TESTS
# ---------------------------------------------------------

def run_tests() -> bool:
    import tempfile
    import unittest

    class SceneComposerTests(unittest.TestCase):

        def setUp(self):
            self.temp = tempfile.TemporaryDirectory()
            self.root = Path(self.temp.name)
            self.database = self.root / "scenes.json"

        def tearDown(self):
            self.temp.cleanup()

        def sample_scene(self):
            return {
                "name": "Hero City Scene",
                "description": "A hero enters a futuristic city.",
                "scene_type": "Sci-Fi",
                "location": "Futuristic city",
                "background": "Tall neon buildings",
                "time_of_day": "Night",
                "weather": "Fog",
                "atmosphere": "Mysterious",
                "camera_shot": "Wide Shot",
                "camera_angle": "Low Angle",
                "camera_movement": "Slow Push In",
                "lens": "35mm",
                "lighting": "Neon Lighting",
                "color_palette": "Blue and purple",
                "visual_style": "Hollywood Cinematic",
                "special_effects": "Floating particles",
                "action": "Character walks forward",
                "duration_seconds": 8,
                "aspect_ratio": "16:9",
                "negative_prompt": "Blurry face",
                "status": "Draft",
            }

        def test_empty_database(self):
            database = load_database(self.database)

            self.assertEqual(database["scenes"], [])

        def test_save_and_load_database(self):
            database = load_database(self.database)
            database["scenes"].append({"id": "test"})

            save_database(database, self.database)

            loaded = load_database(self.database)

            self.assertEqual(len(loaded["scenes"]), 1)

        def test_create_scene(self):
            scene = create_scene(
                self.sample_scene(),
                path=self.database,
                validate_links=False,
            )

            self.assertTrue(scene["id"])
            self.assertEqual(
                scene["name"],
                "Hero City Scene",
            )

        def test_reject_empty_name(self):
            details = self.sample_scene()
            details["name"] = ""

            with self.assertRaises(ValueError):
                create_scene(
                    details,
                    path=self.database,
                    validate_links=False,
                )

        def test_reject_invalid_duration(self):
            details = self.sample_scene()
            details["duration_seconds"] = 900

            with self.assertRaises(ValueError):
                create_scene(
                    details,
                    path=self.database,
                    validate_links=False,
                )

        def test_get_scene(self):
            scene = create_scene(
                self.sample_scene(),
                path=self.database,
                validate_links=False,
            )

            result = get_scene(
                scene["id"],
                self.database,
            )

            self.assertEqual(result["id"], scene["id"])

        def test_search_scenes(self):
            create_scene(
                self.sample_scene(),
                path=self.database,
                validate_links=False,
            )

            results = list_scenes(
                search="futuristic",
                path=self.database,
            )

            self.assertEqual(len(results), 1)

        def test_status_filter(self):
            create_scene(
                self.sample_scene(),
                path=self.database,
                validate_links=False,
            )

            results = list_scenes(
                status="Draft",
                path=self.database,
            )

            self.assertEqual(len(results), 1)

        def test_update_scene(self):
            scene = create_scene(
                self.sample_scene(),
                path=self.database,
                validate_links=False,
            )

            updated = update_scene(
                scene["id"],
                {"name": "Updated Scene"},
                path=self.database,
                validate_links=False,
            )

            self.assertEqual(
                updated["name"],
                "Updated Scene",
            )

        def test_duplicate_scene(self):
            scene = create_scene(
                self.sample_scene(),
                path=self.database,
                validate_links=False,
            )

            duplicate = duplicate_scene(
                scene["id"],
                path=self.database,
                validate_links=False,
            )

            self.assertNotEqual(
                scene["id"],
                duplicate["id"],
            )

            self.assertEqual(
                duplicate["status"],
                "Draft",
            )

        def test_delete_scene(self):
            scene = create_scene(
                self.sample_scene(),
                path=self.database,
                validate_links=False,
            )

            result = delete_scene(
                scene["id"],
                self.database,
            )

            self.assertTrue(result)

            self.assertIsNone(
                get_scene(scene["id"], self.database)
            )

        def test_build_scene_prompt(self):
            scene = self.sample_scene()

            prompt = build_scene_prompt(scene=scene)

            self.assertIn("Hero City Scene", prompt)
            self.assertIn("Futuristic city", prompt)
            self.assertIn("Low Angle", prompt)
            self.assertIn("Blurry face", prompt)

        def test_build_prompt_without_negative(self):
            scene = self.sample_scene()

            prompt = build_scene_prompt(
                scene=scene,
                include_negative=False,
            )

            self.assertNotIn("Negative prompt:", prompt)

        def test_statistics(self):
            create_scene(
                self.sample_scene(),
                path=self.database,
                validate_links=False,
            )

            stats = get_statistics(self.database)

            self.assertEqual(stats["total_scenes"], 1)
            self.assertEqual(stats["draft_scenes"], 1)
            self.assertEqual(
                stats["total_duration_seconds"],
                8,
            )

        def test_export_scene(self):
            scene = create_scene(
                self.sample_scene(),
                path=self.database,
                validate_links=False,
            )

            output = export_scene(
                scene["id"],
                self.root / "exports",
            )

            self.assertTrue(output.exists())

            with output.open("r", encoding="utf-8") as file:
                data = json.load(file)

            self.assertIn("scene", data)
            self.assertIn("generated_prompt", data)

        def test_export_all_scenes(self):
            create_scene(
                self.sample_scene(),
                path=self.database,
                validate_links=False,
            )

            output = export_all_scenes(
                self.root / "all_scenes.json",
                path=self.database,
            )

            self.assertTrue(output.exists())

            with output.open("r", encoding="utf-8") as file:
                data = json.load(file)

            self.assertEqual(data["total_scenes"], 1)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        SceneComposerTests
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

    print("AI Influencer Studio - Scene Composer")
    print("Run tests using:")
    print("python -m modules.scene_composer --test")
