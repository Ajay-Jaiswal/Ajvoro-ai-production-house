
"""
AI Influencer Studio
File 30: AI Character Outfit Manager

Features:
- Create multiple outfits for each character
- Casual, professional, party, fantasy and cinematic categories
- Save outfit descriptions
- Save colors, materials and accessories
- Generate character + outfit prompts
- Edit and duplicate outfits
- Delete outfits
- Search and filter outfits
- JSON-backed local storage
- Streamlit dashboard
- Built-in tests

Run:
    python -m modules.outfit_manager --test

Integration:
    from modules import outfit_manager
    outfit_manager.render(st)
"""

from __future__ import annotations

import argparse
import json
import re
import tempfile
import unittest
import uuid

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

APP_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = APP_ROOT / "data"

OUTFIT_FILE = DATA_DIR / "outfits.json"

MAX_OUTFITS = 10000
MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_TEXT_LENGTH = 5000

OUTFIT_CATEGORIES = [
    "Casual",
    "Professional",
    "Party",
    "Fantasy",
    "Cinematic",
    "Traditional",
    "Sportswear",
    "Travel",
    "Luxury",
    "Custom",
]

OUTFIT_FIELDS = [
    "name",
    "category",
    "description",
    "topwear",
    "bottomwear",
    "footwear",
    "colors",
    "materials",
    "accessories",
    "hairstyle",
    "makeup",
    "season",
    "occasion",
    "visual_style",
    "negative_prompt",
]


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


def require_character_manager():
    if character_consistency is None:
        raise RuntimeError(
            "character_consistency.py is required. "
            "Please create File 28 first."
        )

    return character_consistency


def get_characters() -> list[dict[str, Any]]:
    manager = require_character_manager()
    return manager.list_characters()


def get_character(character_id: str):
    manager = require_character_manager()
    return manager.get_character(character_id)


# ---------------------------------------------------------
# UTILITIES
# ---------------------------------------------------------

def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_text(
    value: Any,
    maximum: int = MAX_TEXT_LENGTH,
) -> str:

    if value is None:
        return ""

    value = str(value).strip()

    if len(value) > maximum:
        raise ValueError(
            f"Text cannot exceed {maximum} characters."
        )

    return value


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# DATABASE
# ---------------------------------------------------------

def empty_database() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": now(),
        "outfits": [],
    }


def get_database_path(
    path: str | Path | None = None,
) -> Path:

    if path is not None:
        return Path(path).expanduser().resolve()

    return OUTFIT_FILE.resolve()


def load_database(
    path: str | Path | None = None,
) -> dict[str, Any]:

    database_path = get_database_path(path)

    if not database_path.exists():
        return empty_database()

    if database_path.stat().st_size > MAX_FILE_SIZE:
        raise ValueError("Outfit database is too large.")

    try:
        data = json.loads(
            database_path.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Invalid outfit database JSON."
        ) from exc

    if not isinstance(data, dict):
        raise ValueError("Invalid outfit database.")

    outfits = data.get("outfits", [])

    if not isinstance(outfits, list):
        raise ValueError("Outfits must be a list.")

    valid = []

    for outfit in outfits:

        if not isinstance(outfit, dict):
            continue

        if not isinstance(outfit.get("id"), str):
            continue

        if not isinstance(outfit.get("character_id"), str):
            continue

        valid.append(outfit)

    return {
        "version": 1,
        "updated_at": data.get("updated_at", now()),
        "outfits": valid[:MAX_OUTFITS],
    }


def save_database(
    database: dict[str, Any],
    path: str | Path | None = None,
) -> None:

    if not isinstance(database, dict):
        raise ValueError("Database must be a dictionary.")

    outfits = database.get("outfits")

    if not isinstance(outfits, list):
        raise ValueError("Outfits must be a list.")

    if len(outfits) > MAX_OUTFITS:
        raise ValueError("Maximum outfit limit reached.")

    destination = get_database_path(path)

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    database["updated_at"] = now()

    temporary = destination.with_name(
        destination.name + ".tmp"
    )

    try:
        temporary.write_text(
            json.dumps(
                database,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        temporary.replace(destination)

    except OSError:
        temporary.unlink(missing_ok=True)
        raise


# ---------------------------------------------------------
# OUTFIT VALIDATION
# ---------------------------------------------------------

def validate_outfit(
    details: dict[str, Any],
) -> dict[str, str]:

    if not isinstance(details, dict):
        raise ValueError("Outfit details must be a dictionary.")

    unknown = set(details) - set(OUTFIT_FIELDS)

    if unknown:
        raise ValueError(
            "Unsupported outfit fields: "
            + ", ".join(sorted(unknown))
        )

    result = {}

    for field in OUTFIT_FIELDS:

        value = clean_text(details.get(field, ""))

        if field == "category" and value:
            if value not in OUTFIT_CATEGORIES:
                raise ValueError("Invalid outfit category.")

        result[field] = value

    if not result["name"]:
        raise ValueError("Outfit name is required.")

    if not result["category"]:
        result["category"] = "Custom"

    return result


# ---------------------------------------------------------
# CREATE OUTFIT
# ---------------------------------------------------------

def create_outfit(
    character_id: str,
    details: dict[str, Any],
    path: str | Path | None = None,
    validate_character_exists: bool = True,
) -> dict[str, Any]:

    if not re.fullmatch(r"[a-f0-9]{32}", character_id):
        raise ValueError("Invalid character ID.")

    if validate_character_exists:
        if get_character(character_id) is None:
            raise ValueError("Character not found.")

    validated = validate_outfit(details)

    database = load_database(path)

    if len(database["outfits"]) >= MAX_OUTFITS:
        raise ValueError("Maximum outfit limit reached.")

    outfit = {
        "id": uuid.uuid4().hex,
        "character_id": character_id,
        **validated,
        "created_at": now(),
        "updated_at": now(),
    }

    database["outfits"].append(outfit)

    save_database(database, path)

    return dict(outfit)


# ---------------------------------------------------------
# GET OUTFIT
# ---------------------------------------------------------

def get_outfit(
    outfit_id: str,
    path: str | Path | None = None,
) -> dict[str, Any] | None:

    database = load_database(path)

    for outfit in database["outfits"]:

        if outfit["id"] == outfit_id:
            return dict(outfit)

    return None


# ---------------------------------------------------------
# LIST OUTFITS
# ---------------------------------------------------------

def list_outfits(
    character_id: str | None = None,
    category: str | None = None,
    search: str = "",
    path: str | Path | None = None,
) -> list[dict[str, Any]]:

    database = load_database(path)

    search = search.strip().casefold()

    results = []

    for outfit in database["outfits"]:

        if character_id:
            if outfit["character_id"] != character_id:
                continue

        if category and category != "All":
            if outfit.get("category") != category:
                continue

        searchable = " ".join(
            str(outfit.get(field, ""))
            for field in OUTFIT_FIELDS
        ).casefold()

        if search and search not in searchable:
            continue

        results.append(dict(outfit))

    return sorted(
        results,
        key=lambda item: item.get("updated_at", ""),
        reverse=True,
    )


# ---------------------------------------------------------
# UPDATE OUTFIT
# ---------------------------------------------------------

def update_outfit(
    outfit_id: str,
    changes: dict[str, Any],
    path: str | Path | None = None,
) -> dict[str, Any]:

    if not isinstance(changes, dict):
        raise ValueError("Changes must be a dictionary.")

    database = load_database(path)

    for outfit in database["outfits"]:

        if outfit["id"] != outfit_id:
            continue

        details = {
            field: outfit.get(field, "")
            for field in OUTFIT_FIELDS
        }

        details.update(changes)

        validated = validate_outfit(details)

        outfit.update(validated)
        outfit["updated_at"] = now()

        save_database(database, path)

        return dict(outfit)

    raise ValueError("Outfit not found.")


# ---------------------------------------------------------
# DUPLICATE OUTFIT
# ---------------------------------------------------------

def duplicate_outfit(
    outfit_id: str,
    path: str | Path | None = None,
    validate_character_exists: bool = True,
) -> dict[str, Any]:

    original = get_outfit(outfit_id, path)

    if original is None:
        raise ValueError("Outfit not found.")

    details = {
        field: original.get(field, "")
        for field in OUTFIT_FIELDS
    }

    details["name"] += " Copy"

    return create_outfit(
        original["character_id"],
        details,
        path=path,
        validate_character_exists=validate_character_exists,
    )


# ---------------------------------------------------------
# DELETE OUTFIT
# ---------------------------------------------------------

def delete_outfit(
    outfit_id: str,
    path: str | Path | None = None,
) -> bool:

    database = load_database(path)

    original_count = len(database["outfits"])

    database["outfits"] = [
        item for item in database["outfits"]
        if item["id"] != outfit_id
    ]

    if len(database["outfits"]) == original_count:
        return False

    save_database(database, path)

    return True


# ---------------------------------------------------------
# OUTFIT PROMPT GENERATOR
# ---------------------------------------------------------

def build_outfit_prompt(
    outfit: dict[str, Any],
    character: dict[str, Any] | None = None,
) -> str:

    if not isinstance(outfit, dict):
        raise ValueError("Outfit must be a dictionary.")

    name = clean_text(outfit.get("name"))

    if not name:
        raise ValueError("Outfit name is required.")

    lines = [
        "AI CHARACTER OUTFIT GENERATION PROMPT",
        "",
    ]

    if character:

        character_name = clean_text(
            character.get("name", "Character")
        )

        lines.append(
            f"CHARACTER: {character_name}"
        )

        identity_fields = [
            ("Face", "face_shape"),
            ("Eyes", "eye_color"),
            ("Hair", "hair_color"),
            ("Hairstyle", "hair_style"),
            ("Skin tone", "skin_tone"),
            ("Distinctive features", "distinctive_features"),
        ]

        for label, field in identity_fields:

            value = clean_text(character.get(field, ""))

            if value:
                lines.append(f"{label}: {value}")

        lines.extend([
            "",
            "CHARACTER IDENTITY RULE:",
            "Preserve the original character's face, "
            "eye color, hairstyle and recognizable features.",
        ])

    lines.extend([
        "",
        f"OUTFIT NAME: {name}",
        f"CATEGORY: {clean_text(outfit.get('category'))}",
    ])

    fields = [
        ("Description", "description"),
        ("Topwear", "topwear"),
        ("Bottomwear", "bottomwear"),
        ("Footwear", "footwear"),
        ("Colors", "colors"),
        ("Materials", "materials"),
        ("Accessories", "accessories"),
        ("Hairstyle", "hairstyle"),
        ("Makeup", "makeup"),
        ("Season", "season"),
        ("Occasion", "occasion"),
        ("Visual style", "visual_style"),
    ]

    for label, field in fields:

        value = clean_text(outfit.get(field, ""))

        if value:
            lines.append(f"{label}: {value}")

    lines.extend([
        "",
        "RENDERING REQUIREMENTS:",
        "- High-quality detailed clothing textures.",
        "- Realistic fabric folds and materials.",
        "- Natural body proportions.",
        "- Accurate clothing colors.",
        "- Cinematic lighting.",
        "- Consistent character identity.",
    ])

    negative = clean_text(
        outfit.get("negative_prompt", "")
    )

    if negative:
        lines.extend([
            "",
            "NEGATIVE PROMPT:",
            negative,
        ])

    return "\n".join(lines)


# ---------------------------------------------------------
# STATISTICS
# ---------------------------------------------------------

def get_statistics(
    path: str | Path | None = None,
) -> dict[str, Any]:

    outfits = list_outfits(path=path)

    category_counts = {}

    for outfit in outfits:

        category = outfit.get("category", "Custom")

        category_counts[category] = (
            category_counts.get(category, 0) + 1
        )

    character_counts = {}

    for outfit in outfits:

        character_id = outfit["character_id"]

        character_counts[character_id] = (
            character_counts.get(character_id, 0) + 1
        )

    return {
        "total_outfits": len(outfits),
        "categories": category_counts,
        "characters_with_outfits": len(character_counts),
        "average_outfits_per_character": (
            round(len(outfits) / len(character_counts), 2)
            if character_counts else 0
        ),
    }


# ---------------------------------------------------------
# EXPORT OUTFITS
# ---------------------------------------------------------

def export_outfits(
    output_path: str | Path,
    path: str | Path | None = None,
) -> Path:

    destination = Path(output_path).expanduser().resolve()

    if destination.suffix.lower() != ".json":
        raise ValueError("Export must be a JSON file.")

    database = load_database(path)

    destination.parent.mkdir(parents=True, exist_ok=True)

    temporary = destination.with_name(
        destination.name + ".tmp"
    )

    try:
        temporary.write_text(
            json.dumps(
                database,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        temporary.replace(destination)

    except OSError:
        temporary.unlink(missing_ok=True)
        raise

    return destination


# ---------------------------------------------------------
# IMPORT OUTFITS
# ---------------------------------------------------------

def import_outfits(
    input_path: str | Path,
    path: str | Path | None = None,
    validate_character_exists: bool = True,
) -> int:

    source = Path(input_path).expanduser().resolve()

    if not source.is_file():
        raise FileNotFoundError("Import file not found.")

    if source.stat().st_size > MAX_FILE_SIZE:
        raise ValueError("Import file is too large.")

    data = json.loads(
        source.read_text(encoding="utf-8")
    )

    if not isinstance(data, dict):
        raise ValueError("Invalid import data.")

    incoming = data.get("outfits")

    if not isinstance(incoming, list):
        raise ValueError("Invalid outfits collection.")

    database = load_database(path)

    if len(database["outfits"]) + len(incoming) > MAX_OUTFITS:
        raise ValueError("Outfit limit exceeded.")

    imported = []

    for item in incoming:

        if not isinstance(item, dict):
            raise ValueError("Invalid outfit entry.")

        character_id = item.get("character_id")

        if not isinstance(character_id, str):
            raise ValueError("Invalid character ID.")

        if not re.fullmatch(r"[a-f0-9]{32}", character_id):
            raise ValueError("Invalid character ID.")

        if validate_character_exists:
            if get_character(character_id) is None:
                raise ValueError(
                    "Imported outfit references a missing character."
                )

        details = {
            field: item.get(field, "")
            for field in OUTFIT_FIELDS
        }

        validated = validate_outfit(details)

        imported.append({
            "id": uuid.uuid4().hex,
            "character_id": character_id,
            **validated,
            "created_at": now(),
            "updated_at": now(),
        })

    database["outfits"].extend(imported)

    save_database(database, path)

    return len(imported)


# ---------------------------------------------------------
# STREAMLIT INTERFACE
# ---------------------------------------------------------

def render(st: Any) -> None:

    ensure_directories()

    st.title("AI Character Outfit Studio")

    st.write(
        "Design and manage reusable outfits for your "
        "AI influencer characters."
    )

    try:
        characters = get_characters()

        if not characters:
            st.warning(
                "Create a character in Character Consistency "
                "Manager before creating outfits."
            )
            return

        stats = get_statistics()

    except Exception as exc:
        st.error(str(exc))
        return

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Total outfits",
        stats["total_outfits"],
    )

    col2.metric(
        "Categories",
        len(stats["categories"]),
    )

    col3.metric(
        "Characters with outfits",
        stats["characters_with_outfits"],
    )

    tabs = st.tabs([
        "Outfit Library",
        "Create Outfit",
        "Edit Outfit",
        "Prompt Studio",
        "Import / Export",
    ])

    character_options = {
        f"{item['name']} ({item['id'][:8]})": item
        for item in characters
    }

    # -----------------------------------------------------
    # OUTFIT LIBRARY
    # -----------------------------------------------------

    with tabs[0]:

        search = st.text_input(
            "Search outfits",
            key="outfit_search",
        )

        selected_category = st.selectbox(
            "Filter category",
            ["All"] + OUTFIT_CATEGORIES,
        )

        selected_character_label = st.selectbox(
            "Filter character",
            ["All"] + list(character_options.keys()),
        )

        character_id = None

        if selected_character_label != "All":
            character_id = character_options[
                selected_character_label
            ]["id"]

        outfits = list_outfits(
            character_id=character_id,
            category=selected_category,
            search=search,
        )

        if not outfits:
            st.info("No outfits found.")
        else:

            for outfit in outfits:

                character = get_character(
                    outfit["character_id"]
                )

                with st.container(border=True):

                    st.subheader(outfit["name"])

                    st.caption(
                        f"Category: {outfit['category']}"
                    )

                    if character:
                        st.write(
                            f"Character: {character['name']}"
                        )

                    if outfit.get("description"):
                        st.write(outfit["description"])

                    if st.button(
                        "Duplicate outfit",
                        key=f"duplicate_{outfit['id']}",
                    ):

                        duplicate_outfit(outfit["id"])
                        st.success("Outfit duplicated.")
                        st.rerun()

                    if st.button(
                        "Delete outfit",
                        key=f"delete_{outfit['id']}",
                    ):

                        st.session_state[
                            f"confirm_delete_{outfit['id']}"
                        ] = True

                    if st.session_state.get(
                        f"confirm_delete_{outfit['id']}",
                        False,
                    ):

                        if st.checkbox(
                            "Confirm deletion",
                            key=f"confirm_{outfit['id']}",
                        ):

                            if st.button(
                                "Confirm delete outfit",
                                key=f"final_delete_{outfit['id']}",
                            ):

                                delete_outfit(outfit["id"])
                                st.success("Outfit deleted.")
                                st.rerun()

    # -----------------------------------------------------
    # CREATE OUTFIT
    # -----------------------------------------------------

    with tabs[1]:

        st.subheader("Create a new outfit")

        with st.form("create_outfit_form"):

            character_label = st.selectbox(
                "Select character",
                list(character_options.keys()),
            )

            details = {}

            details["name"] = st.text_input(
                "Outfit name",
                placeholder="Example: Red Carpet Look",
            )

            details["category"] = st.selectbox(
                "Category",
                OUTFIT_CATEGORIES,
            )

            details["description"] = st.text_area(
                "Overall outfit description",
            )

            details["topwear"] = st.text_input(
                "Topwear",
            )

            details["bottomwear"] = st.text_input(
                "Bottomwear",
            )

            details["footwear"] = st.text_input(
                "Footwear",
            )

            details["colors"] = st.text_input(
                "Colors",
                placeholder="Black, gold, silver",
            )

            details["materials"] = st.text_input(
                "Materials",
                placeholder="Silk, cotton, leather",
            )

            details["accessories"] = st.text_area(
                "Accessories",
            )

            details["hairstyle"] = st.text_input(
                "Hairstyle",
            )

            details["makeup"] = st.text_input(
                "Makeup",
            )

            details["season"] = st.selectbox(
                "Season",
                [
                    "All seasons",
                    "Summer",
                    "Winter",
                    "Monsoon",
                    "Spring",
                    "Autumn",
                ],
            )

            details["occasion"] = st.text_input(
                "Occasion",
            )

            details["visual_style"] = st.text_input(
                "Visual style",
                value="Photorealistic cinematic fashion",
            )

            details["negative_prompt"] = st.text_area(
                "Negative prompt",
                placeholder="Wrong colors, distorted fabric...",
            )

            submitted = st.form_submit_button(
                "Save outfit",
                use_container_width=True,
            )

            if submitted:

                try:

                    selected_character = character_options[
                        character_label
                    ]

                    outfit = create_outfit(
                        selected_character["id"],
                        details,
                    )

                    st.success(
                        f"Outfit '{outfit['name']}' created."
                    )

                except (ValueError, OSError) as exc:
                    st.error(str(exc))

    # -----------------------------------------------------
    # EDIT OUTFIT
    # -----------------------------------------------------

    with tabs[2]:

        outfits = list_outfits()

        if not outfits:
            st.info("Create an outfit first.")
        else:

            outfit_options = {
                f"{item['name']} ({item['id'][:8]})": item
                for item in outfits
            }

            selected_label = st.selectbox(
                "Choose outfit to edit",
                list(outfit_options.keys()),
            )

            selected = outfit_options[selected_label]

            with st.form("edit_outfit_form"):

                changes = {}

                for field in OUTFIT_FIELDS:

                    value = selected.get(field, "")

                    if field == "category":

                        changes[field] = st.selectbox(
                            "Category",
                            OUTFIT_CATEGORIES,
                            index=(
                                OUTFIT_CATEGORIES.index(value)
                                if value in OUTFIT_CATEGORIES
                                else OUTFIT_CATEGORIES.index("Custom")
                            ),
                        )

                    elif field in [
                        "description",
                        "accessories",
                        "negative_prompt",
                    ]:

                        changes[field] = st.text_area(
                            field.replace("_", " ").title(),
                            value=value,
                        )

                    else:

                        changes[field] = st.text_input(
                            field.replace("_", " ").title(),
                            value=value,
                        )

                submitted = st.form_submit_button(
                    "Update outfit",
                )

                if submitted:

                    try:

                        update_outfit(
                            selected["id"],
                            changes,
                        )

                        st.success("Outfit updated.")
                        st.rerun()

                    except (ValueError, OSError) as exc:
                        st.error(str(exc))

    # -----------------------------------------------------
    # PROMPT STUDIO
    # -----------------------------------------------------

    with tabs[3]:

        outfits = list_outfits()

        if not outfits:
            st.info("Create an outfit first.")
        else:

            options = {
                f"{item['name']} ({item['id'][:8]})": item
                for item in outfits
            }

            label = st.selectbox(
                "Select outfit",
                list(options.keys()),
                key="prompt_outfit",
            )

            outfit = options[label]

            character = get_character(
                outfit["character_id"]
            )

            prompt = build_outfit_prompt(
                outfit,
                character,
            )

            st.text_area(
                "Generated outfit prompt",
                value=prompt,
                height=400,
                key="outfit_prompt_output",
            )

            st.caption(
                "This is a reusable text prompt. Actual image "
                "generation requires a connected image-generation engine."
            )

    # -----------------------------------------------------
    # IMPORT / EXPORT
    # -----------------------------------------------------

    with tabs[4]:

        st.subheader("Export outfits")

        if st.button("Create outfit export"):

            try:

                destination = export_outfits(
                    APP_ROOT / "exports" / "outfits.json"
                )

                st.download_button(
                    "Download outfits JSON",
                    data=destination.read_bytes(),
                    file_name="outfits.json",
                    mime="application/json",
                )

            except (OSError, ValueError) as exc:
                st.error(str(exc))

        st.divider()

        st.subheader("Import outfits")

        uploaded = st.file_uploader(
            "Upload outfits JSON",
            type=["json"],
            key="outfit_import",
        )

        if uploaded is not None:

            if st.button("Import outfits"):

                try:

                    if len(uploaded.getvalue()) > MAX_FILE_SIZE:
                        raise ValueError("Import file is too large.")

                    with tempfile.TemporaryDirectory() as temp:

                        source = Path(temp) / "outfits.json"

                        source.write_bytes(
                            uploaded.getvalue()
                        )

                        count = import_outfits(source)

                    st.success(
                        f"Imported {count} outfits."
                    )

                    st.rerun()

                except (
                    ValueError,
                    OSError,
                    json.JSONDecodeError,
                ) as exc:
                    st.error(str(exc))


# ---------------------------------------------------------
# BUILT-IN TESTS
# ---------------------------------------------------------

class OutfitManagerTests(unittest.TestCase):

    def setUp(self):

        self.temp_dir = tempfile.TemporaryDirectory()

        self.root = Path(self.temp_dir.name)

        self.database = self.root / "outfits.json"

        self.character_id = "a" * 32

        self.details = {
            "name": "Luxury Black Dress",
            "category": "Luxury",
            "description": "Elegant evening dress",
            "colors": "Black and gold",
            "materials": "Silk",
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_sample(self):

        return create_outfit(
            self.character_id,
            self.details,
            path=self.database,
            validate_character_exists=False,
        )

    def test_create_outfit(self):

        result = self.create_sample()

        self.assertEqual(
            result["name"],
            "Luxury Black Dress",
        )

    def test_get_outfit(self):

        outfit = self.create_sample()

        result = get_outfit(
            outfit["id"],
            self.database,
        )

        self.assertIsNotNone(result)

    def test_list_outfits(self):

        self.create_sample()

        result = list_outfits(path=self.database)

        self.assertEqual(len(result), 1)

    def test_search_outfit(self):

        self.create_sample()

        result = list_outfits(
            search="luxury",
            path=self.database,
        )

        self.assertEqual(len(result), 1)

    def test_category_filter(self):

        self.create_sample()

        result = list_outfits(
            category="Luxury",
            path=self.database,
        )

        self.assertEqual(len(result), 1)

    def test_update_outfit(self):

        outfit = self.create_sample()

        result = update_outfit(
            outfit["id"],
            {"colors": "Red"},
            self.database,
        )

        self.assertEqual(result["colors"], "Red")

    def test_duplicate_outfit(self):

        outfit = self.create_sample()

        duplicate = duplicate_outfit(
            outfit["id"],
            self.database,
            validate_character_exists=False,
        )

        self.assertNotEqual(
            outfit["id"],
            duplicate["id"],
        )

        self.assertEqual(
            duplicate["name"],
            "Luxury Black Dress Copy",
        )

    def test_delete_outfit(self):

        outfit = self.create_sample()

        result = delete_outfit(
            outfit["id"],
            self.database,
        )

        self.assertTrue(result)

        self.assertEqual(
            len(list_outfits(path=self.database)),
            0,
        )

    def test_missing_name(self):

        with self.assertRaises(ValueError):

            create_outfit(
                self.character_id,
                {"name": ""},
                path=self.database,
                validate_character_exists=False,
            )

    def test_invalid_category(self):

        with self.assertRaises(ValueError):

            create_outfit(
                self.character_id,
                {
                    "name": "Test",
                    "category": "Invalid",
                },
                path=self.database,
                validate_character_exists=False,
            )

    def test_invalid_character_id(self):

        with self.assertRaises(ValueError):

            create_outfit(
                "../outside",
                self.details,
                path=self.database,
                validate_character_exists=False,
            )

    def test_build_outfit_prompt(self):

        outfit = self.create_sample()

        prompt = build_outfit_prompt(
            outfit,
            {
                "name": "Sophia",
                "eye_color": "Brown",
                "hair_color": "Black",
            },
        )

        self.assertIn("Sophia", prompt)
        self.assertIn("Black and gold", prompt)
        self.assertIn("Luxury Black Dress", prompt)

    def test_statistics(self):

        self.create_sample()

        stats = get_statistics(self.database)

        self.assertEqual(stats["total_outfits"], 1)

    def test_export_import(self):

        self.create_sample()

        exported = self.root / "export.json"

        export_outfits(
            exported,
            self.database,
        )

        imported = self.root / "imported.json"

        count = import_outfits(
            exported,
            imported,
            validate_character_exists=False,
        )

        self.assertEqual(count, 1)

        self.assertEqual(
            len(list_outfits(path=imported)),
            1,
        )

    def test_delete_missing_outfit(self):

        result = delete_outfit(
            "missing",
            self.database,
        )

        self.assertFalse(result)


def run_tests() -> bool:

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        OutfitManagerTests
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
        description="AI Influencer Studio Outfit Manager"
    )

    parser.add_argument(
        "--test",
        action="store_true",
    )

    args = parser.parse_args()

    if args.test:

        success = run_tests()

        raise SystemExit(
            0 if success else 1
        )

    ensure_directories()

    print("AI Influencer Studio - Outfit Manager")
    print(f"Database: {OUTFIT_FILE}")
    print("Run this module through Streamlit.")
