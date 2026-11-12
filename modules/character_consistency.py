
"""
AI Influencer Studio
File 28: Character Consistency Manager

Features:
- Create reusable character profiles
- Save facial and physical descriptions
- Save hairstyles, eye color, skin tone and outfits
- Store reference images in the local project
- Generate reusable character identity prompts
- Character search and filtering
- Edit, duplicate and delete profiles
- JSON import and export
- Streamlit interface
- Built-in tests

Run tests:
    python -m modules.character_consistency --test

Integration:
    from modules import character_consistency
    character_consistency.render(st)
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
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
CHARACTER_DIR = APP_ROOT / "assets" / "characters"

DATABASE_FILE = DATA_DIR / "characters.json"

MAX_CHARACTERS = 5000
MAX_TEXT_LENGTH = 5000
MAX_IMPORT_BYTES = 10 * 1024 * 1024

IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}

CHARACTER_FIELDS = [
    "name",
    "age_description",
    "gender_description",
    "skin_tone",
    "face_shape",
    "eye_color",
    "eyebrows",
    "nose",
    "lips",
    "hair_style",
    "hair_color",
    "body_type",
    "height_description",
    "distinctive_features",
    "default_outfit",
    "personality",
    "voice_description",
    "visual_style",
    "negative_prompt",
]


# ---------------------------------------------------------
# GENERAL UTILITIES
# ---------------------------------------------------------

def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CHARACTER_DIR.mkdir(parents=True, exist_ok=True)


def clean_text(value: Any, max_length: int = MAX_TEXT_LENGTH) -> str:
    """Normalize and validate text fields."""

    if value is None:
        return ""

    result = str(value).strip()

    if len(result) > max_length:
        raise ValueError(
            f"Text exceeds maximum length of {max_length} characters."
        )

    return result


def safe_character_name(name: str) -> str:
    """Create a filesystem-safe character name."""

    cleaned = re.sub(
        r"[^a-zA-Z0-9_-]+",
        "_",
        name.strip(),
    )

    cleaned = cleaned.strip("_")

    return cleaned[:60] or "character"


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError, RuntimeError):
        return False


# ---------------------------------------------------------
# DATABASE
# ---------------------------------------------------------

def get_database_path(
    path: str | Path | None = None,
) -> Path:

    return (
        Path(path).expanduser().resolve()
        if path is not None
        else DATABASE_FILE.resolve()
    )


def empty_database() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": now(),
        "characters": [],
    }


def load_database(
    path: str | Path | None = None,
) -> dict[str, Any]:

    database_path = get_database_path(path)

    if not database_path.exists():
        return empty_database()

    if database_path.stat().st_size > MAX_IMPORT_BYTES:
        raise ValueError("Character database is too large.")

    try:
        data = json.loads(
            database_path.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as exc:
        raise ValueError("Character database has invalid JSON.") from exc

    if not isinstance(data, dict):
        raise ValueError("Invalid character database.")

    characters = data.get("characters", [])

    if not isinstance(characters, list):
        raise ValueError("Invalid characters collection.")

    valid = []

    for character in characters:
        if not isinstance(character, dict):
            continue

        if not isinstance(character.get("id"), str):
            continue

        if not isinstance(character.get("name"), str):
            continue

        valid.append(character)

    return {
        "version": 1,
        "updated_at": data.get("updated_at", now()),
        "characters": valid[:MAX_CHARACTERS],
    }


def save_database(
    database: dict[str, Any],
    path: str | Path | None = None,
) -> None:

    if not isinstance(database, dict):
        raise ValueError("Database must be a dictionary.")

    characters = database.get("characters")

    if not isinstance(characters, list):
        raise ValueError("Characters must be a list.")

    if len(characters) > MAX_CHARACTERS:
        raise ValueError("Character limit exceeded.")

    database_path = get_database_path(path)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    database["updated_at"] = now()

    temp_path = database_path.with_name(
        database_path.name + ".tmp"
    )

    try:
        temp_path.write_text(
            json.dumps(
                database,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        temp_path.replace(database_path)

    except OSError:
        temp_path.unlink(missing_ok=True)
        raise


# ---------------------------------------------------------
# CHARACTER VALIDATION
# ---------------------------------------------------------

def validate_character(
    details: dict[str, Any],
) -> dict[str, Any]:

    if not isinstance(details, dict):
        raise ValueError("Character details must be a dictionary.")

    unknown = set(details) - set(CHARACTER_FIELDS)

    if unknown:
        raise ValueError(
            "Unsupported character fields: "
            + ", ".join(sorted(unknown))
        )

    result = {}

    for field in CHARACTER_FIELDS:
        result[field] = clean_text(
            details.get(field, "")
        )

    if not result["name"]:
        raise ValueError("Character name is required.")

    return result


# ---------------------------------------------------------
# CHARACTER STORAGE DIRECTORY
# ---------------------------------------------------------

def get_character_directory(
    character_id: str,
    root: str | Path | None = None,
) -> Path:

    if not re.fullmatch(r"[a-f0-9]{32}", character_id):
        raise ValueError("Invalid character ID.")

    base = (
        Path(root).expanduser().resolve()
        if root is not None
        else CHARACTER_DIR.resolve()
    )

    destination = (base / character_id).resolve()

    if not _inside(destination, base):
        raise ValueError("Invalid character directory.")

    return destination


# ---------------------------------------------------------
# CREATE CHARACTER
# ---------------------------------------------------------

def create_character(
    details: dict[str, Any],
    reference_images: list[str | Path] | None = None,
    path: str | Path | None = None,
    asset_root: str | Path | None = None,
) -> dict[str, Any]:

    profile = validate_character(details)

    database = load_database(path)

    if len(database["characters"]) >= MAX_CHARACTERS:
        raise ValueError("Character limit reached.")

    character_id = uuid.uuid4().hex

    character = {
        "id": character_id,
        **profile,
        "reference_images": [],
        "created_at": now(),
        "updated_at": now(),
    }

    # Validate and copy all reference files before registering them.
    references = []

    for image_path in reference_images or []:

        source = Path(image_path).expanduser().resolve(strict=True)

        if not source.is_file():
            raise ValueError("Reference image is not a file.")

        if source.suffix.lower() not in IMAGE_EXTENSIONS:
            raise ValueError(
                f"Unsupported reference image: {source.name}"
            )

        references.append(source)

    if references:

        folder = get_character_directory(
            character_id,
            asset_root,
        )

        folder.mkdir(parents=True, exist_ok=True)

        copied = []

        try:
            for index, source in enumerate(references, start=1):

                filename = (
                    f"reference_{index}{source.suffix.lower()}"
                )

                destination = folder / filename

                shutil.copy2(source, destination)

                copied.append(str(destination))

            character["reference_images"] = copied

        except OSError:
            shutil.rmtree(folder, ignore_errors=True)
            raise

    database["characters"].append(character)

    try:
        save_database(database, path)
    except Exception:
        if references:
            folder = get_character_directory(
                character_id,
                asset_root,
            )
            shutil.rmtree(folder, ignore_errors=True)
        raise

    return dict(character)


# ---------------------------------------------------------
# GET CHARACTER
# ---------------------------------------------------------

def get_character(
    character_id: str,
    path: str | Path | None = None,
) -> dict[str, Any] | None:

    database = load_database(path)

    for character in database["characters"]:
        if character["id"] == character_id:
            return dict(character)

    return None


# ---------------------------------------------------------
# LIST CHARACTERS
# ---------------------------------------------------------

def list_characters(
    search: str = "",
    path: str | Path | None = None,
) -> list[dict[str, Any]]:

    database = load_database(path)
    search = search.strip().casefold()

    results = []

    for character in database["characters"]:

        searchable = " ".join(
            str(character.get(field, ""))
            for field in CHARACTER_FIELDS
        ).casefold()

        if search and search not in searchable:
            continue

        results.append(dict(character))

    return sorted(
        results,
        key=lambda item: item.get("updated_at", ""),
        reverse=True,
    )


# ---------------------------------------------------------
# UPDATE CHARACTER
# ---------------------------------------------------------

def update_character(
    character_id: str,
    changes: dict[str, Any],
    path: str | Path | None = None,
) -> dict[str, Any]:

    if not isinstance(changes, dict):
        raise ValueError("Changes must be a dictionary.")

    database = load_database(path)

    for character in database["characters"]:

        if character["id"] != character_id:
            continue

        details = {
            field: character.get(field, "")
            for field in CHARACTER_FIELDS
        }

        details.update(changes)

        validated = validate_character(details)

        character.update(validated)
        character["updated_at"] = now()

        save_database(database, path)

        return dict(character)

    raise ValueError("Character not found.")


# ---------------------------------------------------------
# DUPLICATE CHARACTER
# ---------------------------------------------------------

def duplicate_character(
    character_id: str,
    path: str | Path | None = None,
) -> dict[str, Any]:

    original = get_character(character_id, path)

    if original is None:
        raise ValueError("Character not found.")

    details = {
        field: original.get(field, "")
        for field in CHARACTER_FIELDS
    }

    details["name"] += " Copy"

    # The duplicate gets its own profile and reference directory.
    # Reference images are deliberately not copied automatically.
    return create_character(
        details,
        path=path,
    )


# ---------------------------------------------------------
# DELETE CHARACTER
# ---------------------------------------------------------

def delete_character(
    character_id: str,
    path: str | Path | None = None,
    asset_root: str | Path | None = None,
    delete_references: bool = False,
) -> bool:

    database = load_database(path)

    character = next(
        (
            item for item in database["characters"]
            if item["id"] == character_id
        ),
        None,
    )

    if character is None:
        return False

    database["characters"] = [
        item for item in database["characters"]
        if item["id"] != character_id
    ]

    save_database(database, path)

    if delete_references:
        folder = get_character_directory(
            character_id,
            asset_root,
        )
        shutil.rmtree(folder, ignore_errors=True)

    return True


# ---------------------------------------------------------
# CHARACTER CONSISTENCY PROMPT
# ---------------------------------------------------------

def build_identity_prompt(
    character: dict[str, Any],
) -> str:
    """
    Build a reusable character identity description.

    This produces text for downstream generation engines.
    It does not guarantee visual identity without a compatible
    image-generation model and reference-image workflow.
    """

    if not isinstance(character, dict):
        raise ValueError("Character must be a dictionary.")

    name = clean_text(character.get("name"))

    if not name:
        raise ValueError("Character name is required.")

    descriptions = [
        ("Age", "age_description"),
        ("Appearance", "gender_description"),
        ("Skin tone", "skin_tone"),
        ("Face shape", "face_shape"),
        ("Eyes", "eye_color"),
        ("Eyebrows", "eyebrows"),
        ("Nose", "nose"),
        ("Lips", "lips"),
        ("Hair style", "hair_style"),
        ("Hair color", "hair_color"),
        ("Body type", "body_type"),
        ("Height", "height_description"),
        ("Distinctive features", "distinctive_features"),
        ("Default outfit", "default_outfit"),
        ("Personality", "personality"),
        ("Voice", "voice_description"),
        ("Visual style", "visual_style"),
    ]

    lines = [
        f"CHARACTER IDENTITY: {name}",
        "",
        "Maintain the following visual identity consistently:",
    ]

    for label, field in descriptions:
        value = clean_text(character.get(field, ""))

        if value:
            lines.append(f"- {label}: {value}")

    lines.extend([
        "",
        "CONSISTENCY RULES:",
        "- Preserve the same facial identity.",
        "- Preserve eye color and hairstyle.",
        "- Maintain distinctive facial features.",
        "- Keep body proportions consistent.",
        "- Do not randomly change the character's age.",
        "- Maintain continuity across scenes.",
        "- Change clothing only when the scene requires it.",
        "- Use reference images when supported by the AI model.",
    ])

    negative = clean_text(
        character.get("negative_prompt", "")
    )

    if negative:
        lines.extend([
            "",
            "NEGATIVE PROMPT:",
            negative,
        ])

    return "\n".join(lines)


# ---------------------------------------------------------
# CHARACTER STATISTICS
# ---------------------------------------------------------

def get_statistics(
    path: str | Path | None = None,
) -> dict[str, Any]:

    characters = list_characters(path=path)

    return {
        "total_characters": len(characters),
        "with_reference_images": sum(
            bool(item.get("reference_images"))
            for item in characters
        ),
        "without_reference_images": sum(
            not item.get("reference_images")
            for item in characters
        ),
    }


# ---------------------------------------------------------
# JSON EXPORT
# ---------------------------------------------------------

def export_characters(
    output_path: str | Path,
    path: str | Path | None = None,
) -> Path:

    database = load_database(path)

    destination = Path(output_path).expanduser().resolve()

    if destination.suffix.lower() != ".json":
        raise ValueError("Export file must use .json extension.")

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
# JSON IMPORT
# ---------------------------------------------------------

def import_characters(
    input_path: str | Path,
    path: str | Path | None = None,
) -> int:

    source = Path(input_path).expanduser().resolve()

    if not source.is_file():
        raise FileNotFoundError("Import file not found.")

    if source.stat().st_size > MAX_IMPORT_BYTES:
        raise ValueError("Import file is too large.")

    data = json.loads(
        source.read_text(encoding="utf-8")
    )

    if not isinstance(data, dict):
        raise ValueError("Invalid import file.")

    incoming = data.get("characters")

    if not isinstance(incoming, list):
        raise ValueError("Invalid characters collection.")

    if len(incoming) > MAX_CHARACTERS:
        raise ValueError("Too many imported characters.")

    database = load_database(path)
    existing = database["characters"]

    if len(existing) + len(incoming) > MAX_CHARACTERS:
        raise ValueError("Character limit exceeded.")

    imported = []

    for item in incoming:

        if not isinstance(item, dict):
            raise ValueError("Invalid character entry.")

        details = {
            field: item.get(field, "")
            for field in CHARACTER_FIELDS
        }

        validated = validate_character(details)

        imported.append({
            "id": uuid.uuid4().hex,
            **validated,
            # Reference paths from another computer are not trusted.
            "reference_images": [],
            "created_at": now(),
            "updated_at": now(),
        })

    database["characters"] = existing + imported

    save_database(database, path)

    return len(imported)


# ---------------------------------------------------------
# STREAMLIT INTERFACE
# ---------------------------------------------------------

def render(st: Any) -> None:
    """Render Character Consistency Manager."""

    ensure_directories()

    st.title("Character Consistency Manager")

    st.write(
        "Create reusable character identities for your "
        "AI image, video, and storytelling workflows."
    )

    stats = get_statistics()

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Characters",
        stats["total_characters"],
    )

    col2.metric(
        "With references",
        stats["with_reference_images"],
    )

    col3.metric(
        "Without references",
        stats["without_reference_images"],
    )

    st.divider()

    tabs = st.tabs([
        "Character Library",
        "Create Character",
        "Identity Prompt",
        "Import / Export",
    ])

    # -----------------------------------------------------
    # CHARACTER LIBRARY
    # -----------------------------------------------------

    with tabs[0]:

        search = st.text_input(
            "Search characters",
            key="character_search",
        )

        characters = list_characters(search=search)

        if not characters:
            st.info("No saved characters found.")
        else:

            options = {
                f"{item['name']} | {item['id'][:8]}": item["id"]
                for item in characters
            }

            label = st.selectbox(
                "Select character",
                list(options.keys()),
            )

            selected_id = options[label]
            selected = get_character(selected_id)

            if selected:

                st.subheader(selected["name"])

                reference_images = selected.get(
                    "reference_images",
                    [],
                )

                for image_path in reference_images:

                    path = Path(image_path)

                    if path.is_file():
                        st.image(
                            str(path),
                            caption=path.name,
                            width=250,
                        )

                with st.expander("View character identity"):
                    for field in CHARACTER_FIELDS:
                        value = selected.get(field, "")

                        if value:
                            st.write(
                                f"**{field.replace('_', ' ').title()}:** "
                                f"{value}"
                            )

                with st.expander("Edit character"):

                    updated = {}

                    for field in CHARACTER_FIELDS:

                        current_value = selected.get(field, "")

                        if field == "name":
                            updated[field] = st.text_input(
                                "Character name",
                                value=current_value,
                                key=f"edit_{field}",
                            )
                        else:
                            updated[field] = st.text_area(
                                field.replace("_", " ").title(),
                                value=current_value,
                                key=f"edit_{field}",
                                height=70,
                            )

                    if st.button("Save character changes"):

                        try:
                            update_character(
                                selected_id,
                                updated,
                            )

                            st.success("Character updated.")
                            st.rerun()

                        except ValueError as exc:
                            st.error(str(exc))

                if st.button(
                    "Duplicate character",
                    key="duplicate_character",
                ):
                    duplicate_character(selected_id)
                    st.success("Character duplicated.")
                    st.rerun()

                with st.expander("Delete character"):

                    delete_refs = st.checkbox(
                        "Also delete its stored reference images.",
                        key="delete_character_refs",
                    )

                    confirm = st.checkbox(
                        "I confirm character deletion.",
                        key="confirm_character_delete",
                    )

                    if st.button(
                        "Delete selected character",
                        disabled=not confirm,
                    ):

                        delete_character(
                            selected_id,
                            delete_references=delete_refs,
                        )

                        st.success("Character deleted.")
                        st.rerun()

    # -----------------------------------------------------
    # CREATE CHARACTER
    # -----------------------------------------------------

    with tabs[1]:

        st.subheader("Create a character profile")

        with st.form("character_creation_form"):

            details = {}

            details["name"] = st.text_input(
                "Character name",
                placeholder="Example: Sophia",
            )

            details["age_description"] = st.text_input(
                "Age description",
                placeholder="Example: Adult, approximately 25",
            )

            details["gender_description"] = st.text_input(
                "Appearance description",
                placeholder="Example: Feminine appearance",
            )

            details["skin_tone"] = st.text_input(
                "Skin tone",
                placeholder="Example: Warm medium complexion",
            )

            details["face_shape"] = st.text_input(
                "Face shape",
                placeholder="Example: Oval face",
            )

            details["eye_color"] = st.text_input(
                "Eye color",
                placeholder="Example: Dark brown",
            )

            details["eyebrows"] = st.text_input("Eyebrows")
            details["nose"] = st.text_input("Nose")
            details["lips"] = st.text_input("Lips")

            details["hair_style"] = st.text_input(
                "Hair style",
                placeholder="Example: Long wavy hair",
            )

            details["hair_color"] = st.text_input(
                "Hair color",
                placeholder="Example: Natural black",
            )

            details["body_type"] = st.text_input("Body type")
            details["height_description"] = st.text_input(
                "Height description"
            )

            details["distinctive_features"] = st.text_area(
                "Distinctive features",
                placeholder="Scars, freckles, facial marks...",
            )

            details["default_outfit"] = st.text_area(
                "Default outfit",
                placeholder="Describe the default clothing...",
            )

            details["personality"] = st.text_area(
                "Personality"
            )

            details["voice_description"] = st.text_area(
                "Voice description"
            )

            details["visual_style"] = st.text_input(
                "Visual style",
                value="Photorealistic cinematic style",
            )

            details["negative_prompt"] = st.text_area(
                "Negative prompt",
                placeholder="Different face, inconsistent eyes...",
            )

            reference_files = st.file_uploader(
                "Upload reference images",
                type=["png", "jpg", "jpeg", "webp"],
                accept_multiple_files=True,
            )

            submitted = st.form_submit_button(
                "Save character",
                use_container_width=True,
            )

            if submitted:

                try:
                    ensure_directories()

                    temporary_sources = []

                    with tempfile.TemporaryDirectory() as temp:
                        for index, uploaded in enumerate(
                            reference_files or []
                        ):

                            if uploaded.size > 20 * 1024 * 1024:
                                raise ValueError(
                                    "Each reference image must be "
                                    "20 MB or smaller."
                                )

                            temp_path = (
                                Path(temp)
                                / f"reference_{index}"
                                f"{Path(uploaded.name).suffix.lower()}"
                            )

                            temp_path.write_bytes(
                                uploaded.getvalue()
                            )

                            temporary_sources.append(temp_path)

                        character = create_character(
                            details,
                            reference_images=temporary_sources,
                        )

                    st.success(
                        f"Character '{character['name']}' saved."
                    )

                except (ValueError, OSError) as exc:
                    st.error(str(exc))

    # -----------------------------------------------------
    # IDENTITY PROMPT
    # -----------------------------------------------------

    with tabs[2]:

        st.subheader("Generate a reusable identity prompt")

        characters = list_characters()

        if not characters:
            st.info("Create a character first.")
        else:

            options = {
                item["name"]: item
                for item in characters
            }

            selected_name = st.selectbox(
                "Choose character",
                list(options.keys()),
            )

            selected = options[selected_name]

            identity_prompt = build_identity_prompt(selected)

            st.text_area(
                "Character identity prompt",
                value=identity_prompt,
                height=400,
                key="identity_prompt_output",
            )

            st.caption(
                "Use this text in your image and video generation "
                "workflows. Attach the saved reference images when "
                "your generation engine supports reference conditioning."
            )

    # -----------------------------------------------------
    # IMPORT / EXPORT
    # -----------------------------------------------------

    with tabs[3]:

        st.subheader("Export character profiles")

        if st.button("Export all character profiles"):

            try:
                output = export_characters(
                    APP_ROOT / "exports" / "characters.json"
                )

                st.download_button(
                    "Download character profiles",
                    data=output.read_bytes(),
                    file_name="characters.json",
                    mime="application/json",
                )

                st.success("Character export created.")

            except (OSError, ValueError) as exc:
                st.error(str(exc))

        st.divider()

        st.subheader("Import character profiles")

        uploaded = st.file_uploader(
            "Select character JSON",
            type=["json"],
            key="character_import",
        )

        if uploaded is not None:

            if st.button("Import character profiles"):

                try:
                    if len(uploaded.getvalue()) > MAX_IMPORT_BYTES:
                        raise ValueError("Import file is too large.")

                    with tempfile.TemporaryDirectory() as temp:

                        import_path = Path(temp) / "characters.json"

                        import_path.write_bytes(
                            uploaded.getvalue()
                        )

                        count = import_characters(import_path)

                    st.success(
                        f"Imported {count} character profiles."
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

class CharacterConsistencyTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

        self.root = Path(self.temp_dir.name)

        self.database = self.root / "characters.json"
        self.assets = self.root / "character_assets"

    def tearDown(self):
        self.temp_dir.cleanup()

    def sample_details(self):
        return {
            "name": "Sophia",
            "age_description": "Adult, approximately 25",
            "eye_color": "Brown",
            "hair_color": "Black",
            "hair_style": "Long wavy hair",
        }

    def create_sample(self):
        return create_character(
            self.sample_details(),
            path=self.database,
            asset_root=self.assets,
        )

    def test_create_character(self):
        character = self.create_sample()

        self.assertEqual(character["name"], "Sophia")

    def test_get_character(self):
        character = self.create_sample()

        result = get_character(
            character["id"],
            self.database,
        )

        self.assertIsNotNone(result)

    def test_list_characters(self):
        self.create_sample()

        result = list_characters(path=self.database)

        self.assertEqual(len(result), 1)

    def test_search_character(self):
        self.create_sample()

        result = list_characters(
            search="sophia",
            path=self.database,
        )

        self.assertEqual(len(result), 1)

    def test_update_character(self):
        character = self.create_sample()

        result = update_character(
            character["id"],
            {"eye_color": "Blue"},
            self.database,
        )

        self.assertEqual(result["eye_color"], "Blue")

    def test_duplicate_character(self):
        character = self.create_sample()

        duplicate = duplicate_character(
            character["id"],
            self.database,
        )

        self.assertNotEqual(
            character["id"],
            duplicate["id"],
        )

        self.assertEqual(
            duplicate["name"],
            "Sophia Copy",
        )

    def test_delete_character(self):
        character = self.create_sample()

        result = delete_character(
            character["id"],
            path=self.database,
            asset_root=self.assets,
        )

        self.assertTrue(result)

        self.assertEqual(
            len(list_characters(path=self.database)),
            0,
        )

    def test_required_name(self):
        with self.assertRaises(ValueError):
            create_character(
                {"name": ""},
                path=self.database,
            )

    def test_invalid_fields(self):
        with self.assertRaises(ValueError):
            create_character(
                {
                    "name": "Test",
                    "unknown": "value",
                },
                path=self.database,
            )

    def test_identity_prompt(self):
        character = self.create_sample()

        prompt = build_identity_prompt(character)

        self.assertIn("Sophia", prompt)
        self.assertIn("Brown", prompt)
        self.assertIn("CONSISTENCY RULES", prompt)

    def test_statistics(self):
        self.create_sample()

        stats = get_statistics(self.database)

        self.assertEqual(stats["total_characters"], 1)
        self.assertEqual(stats["without_reference_images"], 1)

    def test_export_import(self):
        self.create_sample()

        export_path = self.root / "export.json"

        export_characters(
            export_path,
            self.database,
        )

        imported_database = self.root / "imported.json"

        count = import_characters(
            export_path,
            imported_database,
        )

        self.assertEqual(count, 1)

        self.assertEqual(
            len(list_characters(path=imported_database)),
            1,
        )

    def test_reference_image_copy(self):
        source = self.root / "reference.png"
        source.write_bytes(b"test-image-data")

        character = create_character(
            self.sample_details(),
            reference_images=[source],
            path=self.database,
            asset_root=self.assets,
        )

        references = character["reference_images"]

        self.assertEqual(len(references), 1)
        self.assertTrue(Path(references[0]).is_file())

    def test_reject_invalid_reference(self):
        source = self.root / "reference.exe"
        source.write_bytes(b"not-an-image")

        with self.assertRaises(ValueError):
            create_character(
                self.sample_details(),
                reference_images=[source],
                path=self.database,
                asset_root=self.assets,
            )

    def test_safe_character_directory(self):
        with self.assertRaises(ValueError):
            get_character_directory(
                "../outside",
                self.assets,
            )


def run_tests() -> bool:

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        CharacterConsistencyTests
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
        description="AI Influencer Character Consistency Manager"
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

    print("AI Influencer Studio - Character Consistency Manager")
    print(f"Database: {DATABASE_FILE}")
    print(f"Characters: {CHARACTER_DIR}")
    print("Run this module through Streamlit.")
