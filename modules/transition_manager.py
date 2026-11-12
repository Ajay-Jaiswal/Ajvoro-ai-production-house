
"""
AI Influencer Studio
File 38: modules/transition_manager.py

Cinematic Transition Manager.

This module manages transition metadata and applies
transition settings to timeline clips.

It does not render video effects. FFmpeg integration
will handle actual video rendering later.
"""

from __future__ import annotations

import json
import re
import uuid

from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------
# OPTIONAL TIMELINE INTEGRATION
# ---------------------------------------------------------

try:
    from modules import timeline_editor
except ImportError:
    timeline_editor = None


# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT_DIR / "data"
EXPORT_DIR = ROOT_DIR / "outputs" / "transitions"

DATABASE_FILE = DATA_DIR / "transition_presets.json"


# ---------------------------------------------------------
# TRANSITION TYPES
# ---------------------------------------------------------

TRANSITION_TYPES = [
    "Cut",
    "Fade",
    "Cross Dissolve",
    "Wipe",
    "Zoom",
    "Slide",
    "Blur",
    "Flash",
    "Dip to Black",
    "Dip to White",
    "Spin",
    "Glitch",
    "Light Leak",
    "Morph",
    "Custom",
]


DIRECTIONS = [
    "Left",
    "Right",
    "Up",
    "Down",
    "Center",
    "Outward",
    "Inward",
    "None",
]


BUILT_IN_PRESETS = [
    {
        "name": "Smooth Fade",
        "transition_type": "Fade",
        "duration": 1.0,
        "direction": "None",
        "description": "A smooth fade between shots.",
    },
    {
        "name": "Cinematic Dissolve",
        "transition_type": "Cross Dissolve",
        "duration": 1.5,
        "direction": "None",
        "description": "Gradually blends two cinematic shots.",
    },
    {
        "name": "Fast Left Wipe",
        "transition_type": "Wipe",
        "duration": 0.7,
        "direction": "Left",
        "description": "Fast directional wipe.",
    },
    {
        "name": "Right Slide",
        "transition_type": "Slide",
        "duration": 0.8,
        "direction": "Right",
        "description": "Moves the next shot from the right.",
    },
    {
        "name": "Zoom In",
        "transition_type": "Zoom",
        "duration": 1.0,
        "direction": "Inward",
        "description": "Zooms into the next shot.",
    },
    {
        "name": "Zoom Out",
        "transition_type": "Zoom",
        "duration": 1.0,
        "direction": "Outward",
        "description": "Pulls back into the next shot.",
    },
    {
        "name": "Dip to Black",
        "transition_type": "Dip to Black",
        "duration": 1.2,
        "direction": "None",
        "description": "Dark cinematic scene transition.",
    },
    {
        "name": "Dip to White",
        "transition_type": "Dip to White",
        "duration": 1.0,
        "direction": "None",
        "description": "Bright flash-like transition.",
    },
    {
        "name": "Flash Cut",
        "transition_type": "Flash",
        "duration": 0.3,
        "direction": "None",
        "description": "Quick bright flash between shots.",
    },
    {
        "name": "Soft Blur",
        "transition_type": "Blur",
        "duration": 1.0,
        "direction": "None",
        "description": "Soft blur transition.",
    },
    {
        "name": "Glitch Impact",
        "transition_type": "Glitch",
        "duration": 0.4,
        "direction": "None",
        "description": "Digital glitch transition for action scenes.",
    },
    {
        "name": "Light Leak",
        "transition_type": "Light Leak",
        "duration": 1.3,
        "direction": "None",
        "description": "Warm cinematic light leak.",
    },
    {
        "name": "Spin Transition",
        "transition_type": "Spin",
        "duration": 0.8,
        "direction": "Clockwise",
        "description": "Rotating transition between shots.",
    },
    {
        "name": "Center Zoom",
        "transition_type": "Zoom",
        "duration": 0.6,
        "direction": "Center",
        "description": "Quick central zoom transition.",
    },
    {
        "name": "Hard Cut",
        "transition_type": "Cut",
        "duration": 0.0,
        "direction": "None",
        "description": "Instant cut between shots.",
    },
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
        or "transition"
    )


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
            "presets": [],
            "favorites": [],
        }

    try:
        with database_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            raise ValueError("Invalid transition database.")

        data.setdefault("presets", [])
        data.setdefault("favorites", [])
        data.setdefault("version", 1)

        return data

    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Cannot load transition database: {exc}"
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

    database["updated_at"] = _now()
    database["version"] = 1

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
# VALIDATION
# ---------------------------------------------------------

def validate_transition(details: dict) -> dict:

    if not isinstance(details, dict):
        raise ValueError("Transition details must be a dictionary.")

    name = _clean(details.get("name"), 120)

    if not name:
        raise ValueError("Transition name is required.")

    transition_type = _clean(
        details.get("transition_type", "Fade")
    )

    if transition_type not in TRANSITION_TYPES:
        raise ValueError("Unsupported transition type.")

    direction = _clean(
        details.get("direction", "None")
    )

    if direction not in DIRECTIONS:
        raise ValueError("Unsupported transition direction.")

    try:
        duration = float(details.get("duration", 1.0))
    except (TypeError, ValueError):
        raise ValueError("Duration must be numeric.")

    if not 0 <= duration <= 30:
        raise ValueError(
            "Transition duration must be between 0 and 30 seconds."
        )

    try:
        intensity = float(details.get("intensity", 0.5))
    except (TypeError, ValueError):
        raise ValueError("Intensity must be numeric.")

    if not 0 <= intensity <= 1:
        raise ValueError("Intensity must be between 0 and 1.")

    try:
        easing = _clean(
            details.get("easing", "ease-in-out")
        )

        allowed_easing = [
            "linear",
            "ease-in",
            "ease-out",
            "ease-in-out",
        ]

        if easing not in allowed_easing:
            raise ValueError("Unsupported easing option.")

    except TypeError:
        raise ValueError("Invalid easing option.")

    return {
        "name": name,
        "transition_type": transition_type,
        "duration": round(duration, 3),
        "direction": direction,
        "intensity": round(intensity, 3),
        "easing": easing,
        "description": _clean(
            details.get("description"),
            2000,
        ),
        "sound_effect": _clean(
            details.get("sound_effect"),
            200,
        ),
        "tags": [
            _clean(tag, 40)
            for tag in details.get("tags", [])
            if _clean(tag, 40)
        ][:20],
        "enabled": bool(details.get("enabled", True)),
    }


# ---------------------------------------------------------
# BUILT-IN PRESETS
# ---------------------------------------------------------

def get_builtin_presets() -> list[dict]:

    result = []

    for preset in BUILT_IN_PRESETS:
        item = {
            **preset,
            "id": "builtin_" + _safe_filename(
                preset["name"].lower()
            ),
            "is_builtin": True,
            "favorite": False,
        }

        result.append(item)

    return result


# ---------------------------------------------------------
# PRESET CRUD
# ---------------------------------------------------------

def create_preset(
    details: dict,
    path: Path | str | None = None,
) -> dict:

    database = load_database(path)
    cleaned = validate_transition(details)

    duplicate = any(
        preset.get("name", "").lower() == cleaned["name"].lower()
        for preset in database["presets"]
    )

    if duplicate:
        raise ValueError(
            "A custom preset with this name already exists."
        )

    preset = {
        "id": _id(),
        **cleaned,
        "is_builtin": False,
        "created_at": _now(),
        "updated_at": _now(),
    }

    database["presets"].append(preset)

    save_database(database, path)

    return preset.copy()


def get_preset(
    preset_id: str,
    path: Path | str | None = None,
) -> dict | None:

    for preset in get_builtin_presets():
        if preset["id"] == preset_id:
            return preset

    database = load_database(path)

    for preset in database["presets"]:
        if preset.get("id") == preset_id:
            return preset.copy()

    return None


def list_presets(
    search: str = "",
    transition_type: str = "",
    include_builtin: bool = True,
    path: Path | str | None = None,
) -> list[dict]:

    database = load_database(path)

    presets = list(database["presets"])

    if include_builtin:
        presets.extend(get_builtin_presets())

    search = str(search or "").lower().strip()

    results = []

    for preset in presets:

        if (
            transition_type
            and preset.get("transition_type") != transition_type
        ):
            continue

        searchable = " ".join([
            preset.get("name", ""),
            preset.get("description", ""),
            " ".join(preset.get("tags", [])),
        ]).lower()

        if search and search not in searchable:
            continue

        results.append(preset.copy())

    return results


def update_preset(
    preset_id: str,
    updates: dict,
    path: Path | str | None = None,
) -> dict:

    database = load_database(path)

    for index, preset in enumerate(database["presets"]):

        if preset.get("id") != preset_id:
            continue

        cleaned = validate_transition({
            **preset,
            **updates,
        })

        updated = {
            **preset,
            **cleaned,
            "updated_at": _now(),
        }

        database["presets"][index] = updated

        save_database(database, path)

        return updated.copy()

    raise ValueError(
        "Custom preset not found. Built-in presets cannot be edited."
    )


def delete_preset(
    preset_id: str,
    path: Path | str | None = None,
) -> bool:

    database = load_database(path)

    original = len(database["presets"])

    database["presets"] = [
        preset for preset in database["presets"]
        if preset.get("id") != preset_id
    ]

    if len(database["presets"]) == original:
        return False

    database["favorites"] = [
        item for item in database["favorites"]
        if item != preset_id
    ]

    save_database(database, path)

    return True


# ---------------------------------------------------------
# FAVORITES
# ---------------------------------------------------------

def toggle_favorite(
    preset_id: str,
    path: Path | str | None = None,
) -> bool:

    if get_preset(preset_id, path) is None:
        raise ValueError("Preset not found.")

    database = load_database(path)

    if preset_id in database["favorites"]:
        database["favorites"].remove(preset_id)
        favorite = False
    else:
        database["favorites"].append(preset_id)
        favorite = True

    save_database(database, path)

    return favorite


def list_favorites(
    path: Path | str | None = None,
) -> list[dict]:

    database = load_database(path)

    return [
        preset
        for preset_id in database["favorites"]
        if (preset := get_preset(preset_id, path)) is not None
    ]


# ---------------------------------------------------------
# TIMELINE INTEGRATION
# ---------------------------------------------------------

def apply_transition(
    timeline_id: str,
    track_id: str,
    clip_id: str,
    preset_id: str,
    transition_position: str = "in",
    path: Path | str | None = None,
) -> dict:

    if timeline_editor is None:
        raise RuntimeError(
            "Timeline editor module is unavailable."
        )

    preset = get_preset(preset_id, path)

    if preset is None:
        raise ValueError("Transition preset not found.")

    if transition_position not in ("in", "out"):
        raise ValueError(
            "Transition position must be 'in' or 'out'."
        )

    clip = timeline_editor.get_track(
        timeline_id,
        track_id,
    )

    if clip is None:
        raise ValueError("Timeline track not found.")

    target = next(
        (
            item for item in clip.get("clips", [])
            if item.get("id") == clip_id
        ),
        None,
    )

    if target is None:
        raise ValueError("Timeline clip not found.")

    transition_value = (
        preset["transition_type"]
        if preset["transition_type"] in [
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
        else "Cut"
    )

    # File 37 currently supports only transition names.
    # Preserve full preset settings in clip notes.
    metadata = {
        "preset_id": preset["id"],
        "name": preset["name"],
        "transition_type": preset["transition_type"],
        "duration": preset["duration"],
        "direction": preset["direction"],
        "intensity": preset["intensity"],
        "easing": preset["easing"],
    }

    notes = target.get("notes", "")

    marker = (
        "\n[Transition Manager "
        + transition_position.upper()
        + "] "
        + json.dumps(metadata, ensure_ascii=False)
    )

    notes = re.sub(
        r"\n\[Transition Manager "
        + transition_position.upper()
        + r"\] .*",
        "",
        notes,
    )

    updates = {
        "notes": notes + marker,
    }

    if transition_position == "in":
        updates["transition_in"] = transition_value
    else:
        updates["transition_out"] = transition_value

    return timeline_editor.update_clip(
        timeline_id,
        track_id,
        clip_id,
        updates,
    )


# ---------------------------------------------------------
# EXPORT
# ---------------------------------------------------------

def export_presets(
    output_dir: Path | str | None = None,
    path: Path | str | None = None,
) -> Path:

    presets = list_presets(path=path)

    destination = (
        Path(output_dir)
        if output_dir
        else EXPORT_DIR
    )

    destination.mkdir(
        parents=True,
        exist_ok=True,
    )

    output = destination / "transition_presets.json"

    document = {
        "version": 1,
        "exported_at": _now(),
        "total_presets": len(presets),
        "presets": presets,
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
# STATISTICS
# ---------------------------------------------------------

def get_statistics(
    path: Path | str | None = None,
) -> dict:

    custom = list_presets(
        include_builtin=False,
        path=path,
    )

    builtins = get_builtin_presets()

    favorites = list_favorites(path)

    counts = {}

    for preset in custom + builtins:
        kind = preset["transition_type"]

        counts[kind] = counts.get(kind, 0) + 1

    return {
        "builtin_presets": len(builtins),
        "custom_presets": len(custom),
        "total_presets": len(custom) + len(builtins),
        "favorites": len(favorites),
        "type_breakdown": counts,
    }


# ---------------------------------------------------------
# STREAMLIT UI
# ---------------------------------------------------------

def render(st: Any) -> None:

    ensure_directories()

    st.title("Cinematic Transition Manager")

    st.caption(
        "Create and organize reusable transitions "
        "for your video editing timelines."
    )

    tab_library, tab_create, tab_favorites, tab_stats = st.tabs([
        "Transition Library",
        "Create Preset",
        "Favorites",
        "Statistics",
    ])

    # -----------------------------------------------------
    # LIBRARY
    # -----------------------------------------------------

    with tab_library:

        search = st.text_input(
            "Search transitions",
            key="transition_search",
        )

        transition_type = st.selectbox(
            "Filter type",
            ["All"] + TRANSITION_TYPES,
        )

        selected_type = (
            ""
            if transition_type == "All"
            else transition_type
        )

        presets = list_presets(
            search=search,
            transition_type=selected_type,
        )

        st.write(f"Found {len(presets)} transitions.")

        for preset in presets:

            with st.container(border=True):

                st.subheader(preset["name"])

                st.caption(
                    f"{preset['transition_type']} | "
                    f"{preset['duration']} sec | "
                    f"{preset['direction']}"
                )

                st.write(
                    preset.get("description", "")
                )

                col1, col2 = st.columns(2)

                with col1:
                    if st.button(
                        "Favorite",
                        key=f"favorite_{preset['id']}",
                    ):
                        try:
                            toggle_favorite(preset["id"])
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))

                with col2:
                    st.write(
                        "Built-in"
                        if preset.get("is_builtin")
                        else "Custom"
                    )

                st.markdown("**Apply to timeline**")

                if timeline_editor is not None:

                    timelines = timeline_editor.list_timelines()

                    if timelines:

                        timeline_options = {
                            item["name"] + " (" + item["id"][:8] + ")":
                            item["id"]
                            for item in timelines
                        }

                        selected_timeline_label = st.selectbox(
                            "Timeline",
                            list(timeline_options.keys()),
                            key=f"timeline_{preset['id']}",
                        )

                        selected_timeline_id = timeline_options[
                            selected_timeline_label
                        ]

                        selected_timeline = (
                            timeline_editor.get_timeline(
                                selected_timeline_id
                            )
                        )

                        tracks = (
                            selected_timeline.get("tracks", [])
                            if selected_timeline
                            else []
                        )

                        track_options = {
                            item["name"] + " (" + item["id"][:8] + ")":
                            item["id"]
                            for item in tracks
                        }

                        if track_options:

                            selected_track_label = st.selectbox(
                                "Track",
                                list(track_options.keys()),
                                key=f"track_{preset['id']}",
                            )

                            selected_track_id = track_options[
                                selected_track_label
                            ]

                            track = timeline_editor.get_track(
                                selected_timeline_id,
                                selected_track_id,
                            )

                            clips = (
                                track.get("clips", [])
                                if track
                                else []
                            )

                            clip_options = {
                                item["name"] + " (" + item["id"][:8] + ")":
                                item["id"]
                                for item in clips
                            }

                            if clip_options:

                                selected_clip_label = st.selectbox(
                                    "Clip",
                                    list(clip_options.keys()),
                                    key=f"clip_{preset['id']}",
                                )

                                selected_clip_id = clip_options[
                                    selected_clip_label
                                ]

                                position = st.radio(
                                    "Apply transition",
                                    ["in", "out"],
                                    horizontal=True,
                                    key=f"position_{preset['id']}",
                                )

                                if st.button(
                                    "Apply Transition",
                                    key=f"apply_{preset['id']}",
                                    type="primary",
                                ):
                                    try:
                                        apply_transition(
                                            selected_timeline_id,
                                            selected_track_id,
                                            selected_clip_id,
                                            preset["id"],
                                            position,
                                        )

                                        st.success(
                                            "Transition settings applied."
                                        )

                                    except Exception as exc:
                                        st.error(str(exc))

                            else:
                                st.info("Add clips to this track first.")

                        else:
                            st.info("Add a track to your timeline first.")

                    else:
                        st.info("Create a timeline first.")

                if not preset.get("is_builtin"):

                    if st.button(
                        "Delete Custom Preset",
                        key=f"delete_{preset['id']}",
                    ):
                        if delete_preset(preset["id"]):
                            st.success("Preset deleted.")
                            st.rerun()

    # -----------------------------------------------------
    # CREATE PRESET
    # -----------------------------------------------------

    with tab_create:

        st.subheader("Create custom transition")

        with st.form("create_transition_form"):

            name = st.text_input(
                "Preset name",
                placeholder="My Cinematic Transition",
            )

            kind = st.selectbox(
                "Transition type",
                TRANSITION_TYPES,
            )

            duration = st.slider(
                "Duration (seconds)",
                min_value=0.0,
                max_value=10.0,
                value=1.0,
                step=0.1,
            )

            direction = st.selectbox(
                "Direction",
                DIRECTIONS,
            )

            intensity = st.slider(
                "Intensity",
                min_value=0.0,
                max_value=1.0,
                value=0.5,
                step=0.05,
            )

            easing = st.selectbox(
                "Easing",
                [
                    "linear",
                    "ease-in",
                    "ease-out",
                    "ease-in-out",
                ],
            )

            description = st.text_area(
                "Description",
            )

            sound_effect = st.text_input(
                "Sound effect reference",
                placeholder="Optional local audio asset name",
            )

            submitted = st.form_submit_button(
                "Save Transition",
                type="primary",
            )

        if submitted:

            try:
                preset = create_preset({
                    "name": name,
                    "transition_type": kind,
                    "duration": duration,
                    "direction": direction,
                    "intensity": intensity,
                    "easing": easing,
                    "description": description,
                    "sound_effect": sound_effect,
                })

                st.success(
                    f"Created preset: {preset['name']}"
                )

            except Exception as exc:
                st.error(str(exc))

    # -----------------------------------------------------
    # FAVORITES
    # -----------------------------------------------------

    with tab_favorites:

        favorites = list_favorites()

        st.subheader("Favorite transitions")

        if not favorites:
            st.info("No favorite transitions yet.")

        for preset in favorites:

            with st.container(border=True):

                st.write(f"**{preset['name']}**")

                st.caption(
                    f"{preset['transition_type']} | "
                    f"{preset['duration']} sec"
                )

                if st.button(
                    "Remove Favorite",
                    key=f"unfavorite_{preset['id']}",
                ):
                    toggle_favorite(preset["id"])
                    st.rerun()

    # -----------------------------------------------------
    # STATISTICS
    # -----------------------------------------------------

    with tab_stats:

        stats = get_statistics()

        col1, col2 = st.columns(2)

        col1.metric(
            "Built-in Presets",
            stats["builtin_presets"],
        )

        col2.metric(
            "Custom Presets",
            stats["custom_presets"],
        )

        col3, col4 = st.columns(2)

        col3.metric(
            "Total Presets",
            stats["total_presets"],
        )

        col4.metric(
            "Favorites",
            stats["favorites"],
        )

        st.subheader("Transition type breakdown")

        st.json(stats["type_breakdown"])

        if st.button("Export All Presets"):

            try:
                output = export_presets()

                with output.open("rb") as file:
                    st.download_button(
                        "Download Presets JSON",
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

    class TransitionTests(unittest.TestCase):

        def setUp(self):
            self.temp = tempfile.TemporaryDirectory()
            self.root = Path(self.temp.name)
            self.database = self.root / "transitions.json"

        def tearDown(self):
            self.temp.cleanup()

        def sample(self):
            return {
                "name": "My Transition",
                "transition_type": "Fade",
                "duration": 1.5,
                "direction": "None",
                "intensity": 0.5,
                "easing": "ease-in-out",
                "description": "Test transition",
            }

        def test_empty_database(self):
            data = load_database(self.database)
            self.assertEqual(data["presets"], [])

        def test_builtin_presets(self):
            presets = get_builtin_presets()
            self.assertGreaterEqual(len(presets), 15)

        def test_create_preset(self):
            preset = create_preset(
                self.sample(),
                self.database,
            )

            self.assertEqual(
                preset["name"],
                "My Transition",
            )

        def test_reject_empty_name(self):
            data = self.sample()
            data["name"] = ""

            with self.assertRaises(ValueError):
                create_preset(data, self.database)

        def test_reject_invalid_type(self):
            data = self.sample()
            data["transition_type"] = "Unknown"

            with self.assertRaises(ValueError):
                validate_transition(data)

        def test_reject_invalid_duration(self):
            data = self.sample()
            data["duration"] = 50

            with self.assertRaises(ValueError):
                validate_transition(data)

        def test_reject_invalid_intensity(self):
            data = self.sample()
            data["intensity"] = 2

            with self.assertRaises(ValueError):
                validate_transition(data)

        def test_get_preset(self):
            preset = create_preset(
                self.sample(),
                self.database,
            )

            result = get_preset(
                preset["id"],
                self.database,
            )

            self.assertEqual(
                result["id"],
                preset["id"],
            )

        def test_list_presets(self):
            create_preset(
                self.sample(),
                self.database,
            )

            results = list_presets(
                include_builtin=False,
                path=self.database,
            )

            self.assertEqual(len(results), 1)

        def test_update_preset(self):
            preset = create_preset(
                self.sample(),
                self.database,
            )

            updated = update_preset(
                preset["id"],
                {"duration": 2.5},
                self.database,
            )

            self.assertEqual(updated["duration"], 2.5)

        def test_delete_preset(self):
            preset = create_preset(
                self.sample(),
                self.database,
            )

            self.assertTrue(
                delete_preset(
                    preset["id"],
                    self.database,
                )
            )

            self.assertIsNone(
                get_preset(
                    preset["id"],
                    self.database,
                )
            )

        def test_favorites(self):
            preset = create_preset(
                self.sample(),
                self.database,
            )

            result = toggle_favorite(
                preset["id"],
                self.database,
            )

            self.assertTrue(result)

            self.assertEqual(
                len(list_favorites(self.database)),
                1,
            )

        def test_remove_favorite(self):
            preset = create_preset(
                self.sample(),
                self.database,
            )

            toggle_favorite(
                preset["id"],
                self.database,
            )

            result = toggle_favorite(
                preset["id"],
                self.database,
            )

            self.assertFalse(result)

        def test_export(self):
            create_preset(
                self.sample(),
                self.database,
            )

            output = export_presets(
                self.root / "exports",
                self.database,
            )

            self.assertTrue(output.exists())

            with output.open("r", encoding="utf-8") as file:
                data = json.load(file)

            self.assertGreater(
                data["total_presets"],
                0,
            )

        def test_statistics(self):
            create_preset(
                self.sample(),
                self.database,
            )

            stats = get_statistics(self.database)

            self.assertEqual(
                stats["custom_presets"],
                1,
            )

            self.assertGreater(
                stats["builtin_presets"],
                0,
            )

        def test_builtin_cannot_be_deleted(self):
            builtin = get_builtin_presets()[0]

            self.assertFalse(
                delete_preset(
                    builtin["id"],
                    self.database,
                )
            )

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        TransitionTests
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

    print("AI Influencer Studio - Transition Manager")
    print("Run tests:")
    print("python -m modules.transition_manager --test")
