
"""
AI Influencer Studio
File 34: modules/pose_gallery.py

Visual gallery for poses stored in modules/pose_library.py.

Features:
- Search and filter saved poses.
- Favorite and select poses.
- Display pose reference images.
- Generate and copy pose prompts.
- Store gallery preferences locally.
- Export favorite pose collections.

This module does not perform AI image generation.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------
# MODULE INTEGRATION
# ---------------------------------------------------------

try:
    from modules import pose_library
except ImportError:
    pose_library = None

try:
    from modules import character_consistency
except ImportError:
    character_consistency = None


# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
PREFERENCES_FILE = DATA_DIR / "pose_gallery_preferences.json"


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _default_preferences() -> dict:
    return {
        "version": 1,
        "favorites": [],
        "selected_pose_id": "",
        "updated_at": _now(),
    }


# ---------------------------------------------------------
# PREFERENCES DATABASE
# ---------------------------------------------------------

def load_preferences(
    path: Path | str | None = None,
) -> dict:
    preferences_path = (
        Path(path) if path else PREFERENCES_FILE
    )

    if not preferences_path.exists():
        return _default_preferences()

    try:
        with preferences_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            raise ValueError("Invalid preferences database.")

        data.setdefault("version", 1)
        data.setdefault("favorites", [])
        data.setdefault("selected_pose_id", "")

        if not isinstance(data["favorites"], list):
            data["favorites"] = []

        return data

    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(
            f"Could not load pose gallery preferences: {exc}"
        ) from exc


def save_preferences(
    preferences: dict,
    path: Path | str | None = None,
) -> None:
    preferences_path = (
        Path(path) if path else PREFERENCES_FILE
    )

    preferences_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    preferences["version"] = 1
    preferences["updated_at"] = _now()

    temporary = preferences_path.with_name(
        preferences_path.name + ".tmp"
    )

    with temporary.open("w", encoding="utf-8") as file:
        json.dump(
            preferences,
            file,
            indent=4,
            ensure_ascii=False,
        )

    temporary.replace(preferences_path)


# ---------------------------------------------------------
# POSE ACCESS
# ---------------------------------------------------------

def get_poses(
    search: str = "",
    category: str = "",
    character_id: str = "",
) -> list[dict]:
    if pose_library is None:
        raise RuntimeError("pose_library.py is unavailable.")

    return pose_library.list_poses(
        search=search,
        category=category,
        character_id=character_id,
    )


def get_pose(pose_id: str) -> dict | None:
    if pose_library is None:
        return None

    return pose_library.get_pose(pose_id)


def get_pose_image(
    record: dict,
) -> Path | None:
    if pose_library is None:
        return None

    return pose_library.get_reference_image_path(record)


def get_characters() -> list[dict]:
    if character_consistency is None:
        return []

    try:
        return character_consistency.list_characters()
    except Exception:
        return []


# ---------------------------------------------------------
# FAVORITES
# ---------------------------------------------------------

def is_favorite(
    pose_id: str,
    path: Path | str | None = None,
) -> bool:
    preferences = load_preferences(path)

    return pose_id in preferences["favorites"]


def toggle_favorite(
    pose_id: str,
    path: Path | str | None = None,
) -> bool:
    """
    Toggle a pose favorite.

    Returns True if pose is now a favorite,
    False if it was removed from favorites.
    """
    if not get_pose(pose_id):
        raise ValueError("Pose not found.")

    preferences = load_preferences(path)
    favorites = preferences["favorites"]

    if pose_id in favorites:
        favorites.remove(pose_id)
        result = False
    else:
        favorites.append(pose_id)
        result = True

    save_preferences(preferences, path)

    return result


def list_favorites(
    path: Path | str | None = None,
) -> list[dict]:
    preferences = load_preferences(path)

    favorite_ids = set(preferences["favorites"])

    return [
        pose
        for pose in get_poses()
        if pose.get("id") in favorite_ids
    ]


# ---------------------------------------------------------
# SELECTED POSE
# ---------------------------------------------------------

def select_pose(
    pose_id: str,
    path: Path | str | None = None,
) -> dict:
    pose = get_pose(pose_id)

    if not pose:
        raise ValueError("Pose not found.")

    preferences = load_preferences(path)
    preferences["selected_pose_id"] = pose_id

    save_preferences(preferences, path)

    return pose


def get_selected_pose(
    path: Path | str | None = None,
) -> dict | None:
    preferences = load_preferences(path)

    pose_id = preferences.get("selected_pose_id", "")

    if not pose_id:
        return None

    return get_pose(pose_id)


# ---------------------------------------------------------
# GALLERY STATISTICS
# ---------------------------------------------------------

def get_gallery_statistics(
    path: Path | str | None = None,
) -> dict:
    preferences = load_preferences(path)
    poses = get_poses()

    favorite_ids = set(preferences["favorites"])

    categories = {}

    total_images = 0

    for pose in poses:
        category = pose.get("category", "Custom")

        categories[category] = (
            categories.get(category, 0) + 1
        )

        total_images += len(
            pose.get("reference_images", [])
        )

    return {
        "total_poses": len(poses),
        "favorite_poses": sum(
            1 for pose in poses
            if pose.get("id") in favorite_ids
        ),
        "total_reference_images": total_images,
        "categories": categories,
        "selected_pose_id": preferences.get(
            "selected_pose_id", ""
        ),
    }


# ---------------------------------------------------------
# PROMPT ACCESS
# ---------------------------------------------------------

def build_pose_prompt(pose_id: str) -> str:
    if pose_library is None:
        raise RuntimeError("pose_library.py is unavailable.")

    return pose_library.build_pose_prompt(
        pose_id=pose_id
    )


# ---------------------------------------------------------
# FAVORITES EXPORT
# ---------------------------------------------------------

def export_favorites(
    output_path: Path | str,
    preferences_path: Path | str | None = None,
) -> Path:
    preferences = load_preferences(preferences_path)

    favorite_ids = set(preferences["favorites"])

    poses = [
        pose for pose in get_poses()
        if pose.get("id") in favorite_ids
    ]

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "exported_at": _now(),
        "total_favorites": len(poses),
        "poses": poses,
    }

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
# STREAMLIT GALLERY
# ---------------------------------------------------------

def render(st: Any) -> None:
    _ensure_directories()

    st.title("Pose Gallery")
    st.caption(
        "Browse, organize and reuse your saved character poses."
    )

    if pose_library is None:
        st.error("pose_library.py could not be loaded.")
        return

    try:
        all_poses = get_poses()
    except Exception as exc:
        st.error(f"Could not load poses: {exc}")
        return

    if not all_poses:
        st.info(
            "Your pose gallery is empty. Create poses in Pose Library first."
        )
        return

    preferences = load_preferences()

    # -----------------------------------------------------
    # OVERVIEW
    # -----------------------------------------------------

    stats = get_gallery_statistics()

    col1, col2, col3 = st.columns(3)

    col1.metric("Total Poses", stats["total_poses"])
    col2.metric("Favorites", stats["favorite_poses"])
    col3.metric(
        "Reference Images",
        stats["total_reference_images"],
    )

    st.divider()

    # -----------------------------------------------------
    # SEARCH AND FILTERS
    # -----------------------------------------------------

    st.subheader("Find a pose")

    search = st.text_input(
        "Search",
        placeholder="Search pose name, description or style...",
        key="pose_gallery_search",
    )

    category_options = [
        "All Categories"
    ] + sorted({
        pose.get("category", "Custom")
        for pose in all_poses
    })

    category = st.selectbox(
        "Category",
        category_options,
    )

    characters = get_characters()

    character_options = {
        "All Characters": ""
    }

    for character in characters:
        character_id = str(character.get("id", ""))

        if character_id:
            character_options[
                character.get("name", character_id)
            ] = character_id

    character_filter = st.selectbox(
        "Character",
        list(character_options.keys()),
    )

    favorites_only = st.checkbox(
        "Show favorites only",
        value=False,
    )

    poses = get_poses(
        search=search,
        category=(
            "" if category == "All Categories"
            else category
        ),
        character_id=character_options[
            character_filter
        ],
    )

    if favorites_only:
        favorite_ids = set(
            load_preferences()["favorites"]
        )

        poses = [
            pose for pose in poses
            if pose.get("id") in favorite_ids
        ]

    st.caption(f"{len(poses)} matching pose(s)")

    # -----------------------------------------------------
    # GALLERY CARDS
    # -----------------------------------------------------

    if not poses:
        st.info("No matching poses found.")
    else:
        columns = st.columns(3)

        for index, pose in enumerate(poses):
            pose_id = pose["id"]

            with columns[index % 3]:
                st.markdown(f"**{pose.get('name', 'Pose')}**")
                st.caption(pose.get("category", "Custom"))

                references = pose.get("reference_images", [])
                displayed_image = False

                for reference in references:
                    image_path = get_pose_image(reference)

                    if image_path:
                        st.image(
                            str(image_path),
                            use_container_width=True,
                        )
                        displayed_image = True
                        break

                if not displayed_image:
                    st.caption("No preview image available.")

                description = pose.get("description", "")

                if description:
                    st.write(description[:160])

                favorite = is_favorite(pose_id)

                if st.button(
                    (
                        "Remove Favorite"
                        if favorite
                        else "Add Favorite"
                    ),
                    key=f"favorite_{pose_id}",
                    use_container_width=True,
                ):
                    try:
                        toggle_favorite(pose_id)
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

                selected = (
                    preferences.get("selected_pose_id")
                    == pose_id
                )

                if st.button(
                    (
                        "Selected Pose"
                        if selected
                        else "Select Pose"
                    ),
                    key=f"select_{pose_id}",
                    use_container_width=True,
                    disabled=selected,
                ):
                    try:
                        select_pose(pose_id)
                        st.success("Default pose updated.")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

                with st.expander("View pose details"):
                    st.write(
                        pose.get("description")
                        or "No description."
                    )

                    prompt = build_pose_prompt(pose_id)

                    st.text_area(
                        "Reusable prompt",
                        value=prompt,
                        height=180,
                        key=f"gallery_prompt_{pose_id}",
                    )

                    st.download_button(
                        "Download prompt",
                        data=prompt,
                        file_name=f"pose_{pose_id}.txt",
                        mime="text/plain",
                        key=f"gallery_download_{pose_id}",
                    )

    # -----------------------------------------------------
    # SELECTED POSE
    # -----------------------------------------------------

    st.divider()
    st.subheader("Default selected pose")

    selected_pose = get_selected_pose()

    if selected_pose:
        st.write(
            f"**{selected_pose.get('name', 'Unnamed Pose')}**"
        )

        st.caption(
            f"Category: {selected_pose.get('category', 'Custom')}"
        )

        if st.button(
            "Clear Selected Pose",
            key="clear_selected_pose",
        ):
            current = load_preferences()
            current["selected_pose_id"] = ""
            save_preferences(current)
            st.rerun()
    else:
        st.info("No default pose selected.")

    # -----------------------------------------------------
    # EXPORT
    # -----------------------------------------------------

    st.divider()
    st.subheader("Export favorites")

    if stats["favorite_poses"] == 0:
        st.caption("Add some favorites before exporting.")
    else:
        if st.button("Prepare Favorites Export"):
            try:
                output = (
                    PROJECT_ROOT
                    / "outputs"
                    / "pose_gallery"
                    / "favorite_poses.json"
                )

                exported = export_favorites(output)

                st.success(f"Exported: {exported}")

            except Exception as exc:
                st.error(f"Export failed: {exc}")


# ---------------------------------------------------------
# BUILT-IN TESTS
# ---------------------------------------------------------

def run_tests() -> bool:
    import tempfile
    import unittest
    from unittest.mock import patch

    class PoseGalleryTests(unittest.TestCase):

        def setUp(self):
            self.temp = tempfile.TemporaryDirectory()
            self.root = Path(self.temp.name)
            self.preferences_path = (
                self.root / "preferences.json"
            )

            self.sample_poses = [
                {
                    "id": "pose_1",
                    "name": "Heroic Standing",
                    "category": "Standing",
                    "description": "A heroic pose",
                    "reference_images": [],
                },
                {
                    "id": "pose_2",
                    "name": "Walking Pose",
                    "category": "Walking",
                    "description": "A walking pose",
                    "reference_images": [],
                },
            ]

        def tearDown(self):
            self.temp.cleanup()

        def mock_get_pose(self, pose_id):
            return next(
                (
                    pose for pose in self.sample_poses
                    if pose["id"] == pose_id
                ),
                None,
            )

        def test_default_preferences(self):
            preferences = load_preferences(
                self.preferences_path
            )

            self.assertEqual(preferences["favorites"], [])
            self.assertEqual(
                preferences["selected_pose_id"],
                "",
            )

        def test_save_and_load_preferences(self):
            preferences = _default_preferences()
            preferences["favorites"] = ["pose_1"]

            save_preferences(
                preferences,
                self.preferences_path,
            )

            loaded = load_preferences(
                self.preferences_path
            )

            self.assertEqual(
                loaded["favorites"],
                ["pose_1"],
            )

        def test_is_favorite(self):
            preferences = _default_preferences()
            preferences["favorites"] = ["pose_1"]

            save_preferences(
                preferences,
                self.preferences_path,
            )

            self.assertTrue(
                is_favorite(
                    "pose_1",
                    self.preferences_path,
                )
            )

        def test_toggle_favorite_add(self):
            with patch(
                __name__ + ".get_pose",
                side_effect=self.mock_get_pose,
            ):
                result = toggle_favorite(
                    "pose_1",
                    self.preferences_path,
                )

            self.assertTrue(result)
            self.assertTrue(
                is_favorite(
                    "pose_1",
                    self.preferences_path,
                )
            )

        def test_toggle_favorite_remove(self):
            preferences = _default_preferences()
            preferences["favorites"] = ["pose_1"]

            save_preferences(
                preferences,
                self.preferences_path,
            )

            with patch(
                __name__ + ".get_pose",
                side_effect=self.mock_get_pose,
            ):
                result = toggle_favorite(
                    "pose_1",
                    self.preferences_path,
                )

            self.assertFalse(result)
            self.assertFalse(
                is_favorite(
                    "pose_1",
                    self.preferences_path,
                )
            )

        def test_reject_missing_pose_favorite(self):
            with patch(
                __name__ + ".get_pose",
                return_value=None,
            ):
                with self.assertRaises(ValueError):
                    toggle_favorite(
                        "missing",
                        self.preferences_path,
                    )

        def test_select_pose(self):
            with patch(
                __name__ + ".get_pose",
                side_effect=self.mock_get_pose,
            ):
                result = select_pose(
                    "pose_1",
                    self.preferences_path,
                )

            self.assertEqual(result["id"], "pose_1")

            preferences = load_preferences(
                self.preferences_path
            )

            self.assertEqual(
                preferences["selected_pose_id"],
                "pose_1",
            )

        def test_selected_pose(self):
            preferences = _default_preferences()
            preferences["selected_pose_id"] = "pose_2"

            save_preferences(
                preferences,
                self.preferences_path,
            )

            with patch(
                __name__ + ".get_pose",
                side_effect=self.mock_get_pose,
            ):
                result = get_selected_pose(
                    self.preferences_path
                )

            self.assertEqual(result["id"], "pose_2")

        def test_statistics(self):
            with patch(
                __name__ + ".get_poses",
                return_value=self.sample_poses,
            ):
                result = get_gallery_statistics(
                    self.preferences_path
                )

            self.assertEqual(result["total_poses"], 2)

        def test_export_favorites(self):
            preferences = _default_preferences()
            preferences["favorites"] = ["pose_1"]

            save_preferences(
                preferences,
                self.preferences_path,
            )

            output = self.root / "favorites.json"

            with patch(
                __name__ + ".get_poses",
                return_value=self.sample_poses,
            ):
                result = export_favorites(
                    output,
                    self.preferences_path,
                )

            self.assertTrue(result.exists())

            with result.open("r", encoding="utf-8") as file:
                data = json.load(file)

            self.assertEqual(data["total_favorites"], 1)

        def test_prompt_builder(self):
            with patch(
                __name__ + ".pose_library"
            ) as mock_library:
                mock_library.build_pose_prompt.return_value = (
                    "Standing confidently"
                )

                result = build_pose_prompt("pose_1")

            self.assertEqual(
                result,
                "Standing confidently",
            )

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        PoseGalleryTests
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

    print("AI Influencer Studio - Pose Gallery")
    print("Run tests using:")
    print("python -m modules.pose_gallery --test")
