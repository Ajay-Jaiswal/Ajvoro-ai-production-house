
"""
AI Influencer Studio
File 29: Character Gallery

Features:
- Visual character gallery
- Character reference image previews
- Search and category filtering
- Favorite characters
- Character profile details
- Identity prompt preview
- Character selection
- JSON-backed gallery preferences
- Integration with character_consistency.py
- Built-in tests

Run tests:
    python -m modules.character_gallery --test

Streamlit integration:
    from modules import character_gallery
    character_gallery.render(st)
"""

from __future__ import annotations

import argparse
import json
import tempfile
import unittest

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

APP_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = APP_ROOT / "data"

GALLERY_FILE = DATA_DIR / "character_gallery.json"

MAX_PREFERENCES_BYTES = 5 * 1024 * 1024


# ---------------------------------------------------------
# CHARACTER CONSISTENCY INTEGRATION
# ---------------------------------------------------------

try:
    from modules import character_consistency
except ImportError:
    try:
        import character_consistency
    except ImportError:
        character_consistency = None


def _require_character_manager():
    if character_consistency is None:
        raise RuntimeError(
            "character_consistency.py is required. "
            "Please create File 28 first."
        )

    return character_consistency


# ---------------------------------------------------------
# GENERAL UTILITIES
# ---------------------------------------------------------

def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def empty_store() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": now(),
        "favorites": [],
        "selected_character": None,
    }


# ---------------------------------------------------------
# GALLERY PREFERENCE STORAGE
# ---------------------------------------------------------

def get_storage_path(
    path: str | Path | None = None,
) -> Path:

    if path is not None:
        return Path(path).expanduser().resolve()

    return GALLERY_FILE.resolve()


def load_preferences(
    path: str | Path | None = None,
) -> dict[str, Any]:

    storage = get_storage_path(path)

    if not storage.exists():
        return empty_store()

    if storage.stat().st_size > MAX_PREFERENCES_BYTES:
        raise ValueError("Gallery preferences file is too large.")

    try:
        data = json.loads(
            storage.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Gallery preferences contain invalid JSON."
        ) from exc

    if not isinstance(data, dict):
        raise ValueError("Invalid gallery preferences.")

    favorites = data.get("favorites", [])

    if not isinstance(favorites, list):
        favorites = []

    favorites = [
        item for item in favorites
        if isinstance(item, str)
    ]

    selected = data.get("selected_character")

    if not isinstance(selected, str):
        selected = None

    return {
        "version": 1,
        "updated_at": data.get("updated_at", now()),
        "favorites": list(dict.fromkeys(favorites)),
        "selected_character": selected,
    }


def save_preferences(
    preferences: dict[str, Any],
    path: str | Path | None = None,
) -> None:

    if not isinstance(preferences, dict):
        raise ValueError("Preferences must be a dictionary.")

    favorites = preferences.get("favorites", [])

    if not isinstance(favorites, list):
        raise ValueError("Favorites must be a list.")

    if not all(isinstance(item, str) for item in favorites):
        raise ValueError("Invalid favorite character IDs.")

    selected = preferences.get("selected_character")

    if selected is not None and not isinstance(selected, str):
        raise ValueError("Invalid selected character ID.")

    storage = get_storage_path(path)
    storage.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "version": 1,
        "updated_at": now(),
        "favorites": list(dict.fromkeys(favorites)),
        "selected_character": selected,
    }

    temporary = storage.with_name(storage.name + ".tmp")

    try:
        temporary.write_text(
            json.dumps(data, indent=2),
            encoding="utf-8",
        )

        temporary.replace(storage)

    except OSError:
        temporary.unlink(missing_ok=True)
        raise


# ---------------------------------------------------------
# CHARACTER DATA
# ---------------------------------------------------------

def get_characters() -> list[dict[str, Any]]:
    manager = _require_character_manager()
    return manager.list_characters()


def get_character(
    character_id: str,
) -> dict[str, Any] | None:

    manager = _require_character_manager()

    return manager.get_character(character_id)


def get_character_image(
    character: dict[str, Any],
) -> str | None:
    """
    Return the first existing reference image.

    Image paths are validated against the configured
    character asset directory.
    """

    references = character.get("reference_images", [])

    if not isinstance(references, list):
        return None

    manager = _require_character_manager()

    for reference in references:

        try:
            path = Path(reference).resolve(strict=True)

            if not path.is_file():
                continue

            if path.suffix.lower() not in manager.IMAGE_EXTENSIONS:
                continue

            if not manager._inside(
                path,
                manager.CHARACTER_DIR,
            ):
                continue

            return str(path)

        except (OSError, ValueError, RuntimeError):
            continue

    return None


# ---------------------------------------------------------
# SEARCH AND FILTERING
# ---------------------------------------------------------

def search_characters(
    query: str = "",
    favorites_only: bool = False,
    path: str | Path | None = None,
) -> list[dict[str, Any]]:

    characters = get_characters()

    preferences = load_preferences(path)

    favorites = set(preferences["favorites"])

    query = query.strip().casefold()

    results = []

    for character in characters:

        if favorites_only and character["id"] not in favorites:
            continue

        searchable = " ".join(
            str(value)
            for value in character.values()
            if isinstance(value, (str, int, float))
        ).casefold()

        if query and query not in searchable:
            continue

        results.append(character)

    return results


# ---------------------------------------------------------
# FAVORITES
# ---------------------------------------------------------

def is_favorite(
    character_id: str,
    path: str | Path | None = None,
) -> bool:

    preferences = load_preferences(path)

    return character_id in preferences["favorites"]


def toggle_favorite(
    character_id: str,
    path: str | Path | None = None,
) -> bool:

    if get_character(character_id) is None:
        raise ValueError("Character not found.")

    preferences = load_preferences(path)

    favorites = preferences["favorites"]

    if character_id in favorites:
        favorites.remove(character_id)
        result = False
    else:
        favorites.append(character_id)
        result = True

    save_preferences(preferences, path)

    return result


# ---------------------------------------------------------
# SELECTED CHARACTER
# ---------------------------------------------------------

def select_character(
    character_id: str,
    path: str | Path | None = None,
) -> dict[str, Any]:

    character = get_character(character_id)

    if character is None:
        raise ValueError("Character not found.")

    preferences = load_preferences(path)

    preferences["selected_character"] = character_id

    save_preferences(preferences, path)

    return character


def get_selected_character(
    path: str | Path | None = None,
) -> dict[str, Any] | None:

    preferences = load_preferences(path)

    character_id = preferences["selected_character"]

    if not character_id:
        return None

    character = get_character(character_id)

    if character is None:
        preferences["selected_character"] = None
        save_preferences(preferences, path)

    return character


# ---------------------------------------------------------
# GALLERY STATISTICS
# ---------------------------------------------------------

def get_gallery_statistics(
    path: str | Path | None = None,
) -> dict[str, int]:

    characters = get_characters()

    preferences = load_preferences(path)

    favorites = set(preferences["favorites"])

    with_images = sum(
        get_character_image(character) is not None
        for character in characters
    )

    return {
        "total_characters": len(characters),
        "favorites": sum(
            character["id"] in favorites
            for character in characters
        ),
        "with_images": with_images,
        "without_images": len(characters) - with_images,
    }


# ---------------------------------------------------------
# CHARACTER PROFILE INFORMATION
# ---------------------------------------------------------

def get_profile_summary(
    character: dict[str, Any],
) -> dict[str, str]:

    fields = [
        "age_description",
        "skin_tone",
        "eye_color",
        "hair_color",
        "hair_style",
        "default_outfit",
        "visual_style",
    ]

    return {
        field: str(character.get(field, "")).strip()
        for field in fields
        if str(character.get(field, "")).strip()
    }


def build_identity_prompt(
    character_id: str,
) -> str:

    manager = _require_character_manager()

    character = get_character(character_id)

    if character is None:
        raise ValueError("Character not found.")

    return manager.build_identity_prompt(character)


# ---------------------------------------------------------
# STREAMLIT GALLERY CARD
# ---------------------------------------------------------

def render_character_card(
    st: Any,
    character: dict[str, Any],
    favorites: set[str],
) -> None:

    character_id = character["id"]

    image_path = get_character_image(character)

    with st.container(border=True):

        if image_path:
            st.image(
                image_path,
                use_container_width=True,
            )
        else:
            st.markdown("### No reference image")
            st.caption("Add an image in Character Consistency.")

        favorite = character_id in favorites

        st.markdown(
            f"**{character.get('name', 'Unnamed Character')}**"
        )

        if character.get("visual_style"):
            st.caption(character["visual_style"])

        if character.get("eye_color"):
            st.write(
                "Eyes:",
                character["eye_color"],
            )

        if character.get("hair_color"):
            st.write(
                "Hair:",
                character["hair_color"],
            )

        col1, col2 = st.columns(2)

        with col1:
            if st.button(
                "★ Favorite" if favorite else "☆ Favorite",
                key=f"favorite_{character_id}",
                use_container_width=True,
            ):
                toggle_favorite(character_id)
                st.rerun()

        with col2:
            if st.button(
                "Select",
                key=f"select_{character_id}",
                use_container_width=True,
            ):
                select_character(character_id)
                st.session_state["gallery_selected"] = character_id
                st.rerun()

        with st.expander("Character details"):

            summary = get_profile_summary(character)

            if summary:
                for field, value in summary.items():
                    st.write(
                        f"**{field.replace('_', ' ').title()}:** "
                        f"{value}"
                    )
            else:
                st.info("No additional profile information.")

            if st.button(
                "View identity prompt",
                key=f"identity_{character_id}",
            ):

                prompt = build_identity_prompt(character_id)

                st.code(
                    prompt,
                    language="text",
                )


# ---------------------------------------------------------
# MAIN STREAMLIT PAGE
# ---------------------------------------------------------

def render(st: Any) -> None:

    ensure_directories()

    st.title("AI Character Gallery")

    st.write(
        "Browse, organize, select, and manage your saved "
        "AI influencer characters."
    )

    try:
        characters = get_characters()
        preferences = load_preferences()

    except Exception as exc:
        st.error(f"Unable to load character gallery: {exc}")
        return

    favorites = set(preferences["favorites"])

    stats = get_gallery_statistics()

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Characters",
        stats["total_characters"],
    )

    col2.metric(
        "Favorites",
        stats["favorites"],
    )

    col3.metric(
        "With images",
        stats["with_images"],
    )

    col4.metric(
        "Without images",
        stats["without_images"],
    )

    st.divider()

    selected = get_selected_character()

    if selected:

        st.success(
            f"Currently selected: {selected['name']}"
        )

    # Filters
    filter_col, search_col = st.columns([1, 2])

    with filter_col:
        favorites_only = st.checkbox(
            "Favorites only",
            key="gallery_favorites_only",
        )

    with search_col:
        search = st.text_input(
            "Search characters",
            placeholder="Name, hairstyle, eye color...",
            key="gallery_search",
        )

    results = search_characters(
        query=search,
        favorites_only=favorites_only,
    )

    st.markdown("### Character collection")

    if not results:
        st.info(
            "No matching characters. Create a character "
            "in Character Consistency Manager first."
        )
        return

    # Gallery columns
    columns_per_row = 3

    for start in range(
        0,
        len(results),
        columns_per_row,
    ):

        row = results[start:start + columns_per_row]

        columns = st.columns(columns_per_row)

        for column, character in zip(columns, row):

            with column:
                render_character_card(
                    st,
                    character,
                    favorites,
                )

    st.divider()

    # Selection details
    selected = get_selected_character()

    if selected:

        with st.expander(
            "Selected character details",
            expanded=True,
        ):

            st.subheader(selected["name"])

            image_path = get_character_image(selected)

            if image_path:
                st.image(
                    image_path,
                    width=250,
                )

            st.write(
                "Character ID:",
                selected["id"],
            )

            if st.button("Clear selection"):
                preferences = load_preferences()
                preferences["selected_character"] = None
                save_preferences(preferences)
                st.rerun()


# ---------------------------------------------------------
# BUILT-IN TESTS
# ---------------------------------------------------------

class CharacterGalleryTests(unittest.TestCase):

    def setUp(self):

        self.temp_dir = tempfile.TemporaryDirectory()

        self.root = Path(self.temp_dir.name)

        self.database = self.root / "characters.json"
        self.preferences = self.root / "gallery.json"
        self.assets = self.root / "character_assets"

        self.original_database = (
            character_consistency.DATABASE_FILE
            if character_consistency is not None
            else None
        )

        self.original_assets = (
            character_consistency.CHARACTER_DIR
            if character_consistency is not None
            else None
        )

        self.character = None

        if character_consistency is not None:

            character_consistency.DATABASE_FILE = self.database
            character_consistency.CHARACTER_DIR = self.assets

            self.character = character_consistency.create_character(
                {
                    "name": "Sophia",
                    "eye_color": "Brown",
                    "hair_color": "Black",
                    "hair_style": "Long hair",
                },
                path=self.database,
                asset_root=self.assets,
            )

    def tearDown(self):

        if character_consistency is not None:

            character_consistency.DATABASE_FILE = (
                self.original_database
            )

            character_consistency.CHARACTER_DIR = (
                self.original_assets
            )

        self.temp_dir.cleanup()

    def test_empty_preferences(self):

        result = load_preferences(self.preferences)

        self.assertEqual(result["favorites"], [])

    def test_save_and_load_preferences(self):

        data = {
            "favorites": ["abc123"],
            "selected_character": "abc123",
        }

        save_preferences(data, self.preferences)

        result = load_preferences(self.preferences)

        self.assertEqual(result["favorites"], ["abc123"])
        self.assertEqual(
            result["selected_character"],
            "abc123",
        )

    def test_favorite_character(self):

        if self.character is None:
            self.skipTest("Character manager unavailable.")

        result = toggle_favorite(
            self.character["id"],
            self.preferences,
        )

        self.assertTrue(result)

    def test_remove_favorite(self):

        if self.character is None:
            self.skipTest("Character manager unavailable.")

        toggle_favorite(
            self.character["id"],
            self.preferences,
        )

        result = toggle_favorite(
            self.character["id"],
            self.preferences,
        )

        self.assertFalse(result)

    def test_select_character(self):

        if self.character is None:
            self.skipTest("Character manager unavailable.")

        result = select_character(
            self.character["id"],
            self.preferences,
        )

        self.assertEqual(result["name"], "Sophia")

    def test_get_selected_character(self):

        if self.character is None:
            self.skipTest("Character manager unavailable.")

        select_character(
            self.character["id"],
            self.preferences,
        )

        result = get_selected_character(
            self.preferences
        )

        self.assertEqual(result["name"], "Sophia")

    def test_search_character(self):

        if self.character is None:
            self.skipTest("Character manager unavailable.")

        results = search_characters(
            query="sophia",
        )

        self.assertTrue(
            any(
                item["id"] == self.character["id"]
                for item in results
            )
        )

    def test_profile_summary(self):

        if self.character is None:
            self.skipTest("Character manager unavailable.")

        summary = get_profile_summary(self.character)

        self.assertEqual(summary["eye_color"], "Brown")

    def test_character_statistics(self):

        if self.character is None:
            self.skipTest("Character manager unavailable.")

        stats = get_gallery_statistics()

        self.assertEqual(stats["total_characters"], 1)

    def test_invalid_preferences(self):

        with self.assertRaises(ValueError):

            save_preferences(
                {
                    "favorites": "not-a-list",
                },
                self.preferences,
            )

    def test_unknown_character_favorite(self):

        if self.character is None:
            self.skipTest("Character manager unavailable.")

        with self.assertRaises(ValueError):

            toggle_favorite(
                "00000000000000000000000000000000",
                self.preferences,
            )


def run_tests() -> bool:

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        CharacterGalleryTests
    )

    result = unittest.TextTestRunner(
        verbosity=2
    ).run(suite)

    return result.wasSuccessful()


# ---------------------------------------------------------
# COMMAND LINE
# ---------------------------------------------------------

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="AI Influencer Studio Character Gallery"
    )

    parser.add_argument(
        "--test",
        action="store_true",
        help="Run built-in tests",
    )

    args = parser.parse_args()

    if args.test:
        success = run_tests()
        raise SystemExit(0 if success else 1)

    ensure_directories()

    print("AI Influencer Studio - Character Gallery")
    print(f"Preferences: {GALLERY_FILE}")
    print("Run this module through your Streamlit application.")
