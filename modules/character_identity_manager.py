
"""
AI Influencer Studio
File 56: modules/character_identity_manager.py

Local Character Identity Manager.

Features:
- Create and manage character identity profiles
- Facial features and physical appearance
- Hair, eyes, skin description and distinctive marks
- Default outfit and alternate outfits
- Personality and voice description
- Identity consistency instructions
- Image and video identity prompts
- Search, duplicate, edit and delete profiles
- JSON and TXT export
- Streamlit interface
- Built-in tests

No cloud APIs or paid AI services.

Run:
    streamlit run app.py

Test:
    python -m modules.character_identity_manager --test
"""

from __future__ import annotations

import argparse
import json
import re
import tempfile
import unittest

from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs" / "character_profiles"

DATA_FILE = DATA_DIR / "character_profiles.json"


# ---------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------

CHARACTER_CATEGORIES = [
    "AI Influencer",
    "Fantasy Character",
    "Sci-Fi Character",
    "Realistic Human",
    "Animated Character",
    "Other",
]

PROFILE_STATUSES = [
    "Active",
    "Draft",
    "Archived",
]


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def make_id(prefix: str = "character") -> str:
    return (
        prefix + "_"
        + datetime.now().strftime("%Y%m%d%H%M%S%f")
    )


def clean_text(value: Any, limit: int = 10000) -> str:
    if value is None:
        return ""
    return str(value).strip()[:limit]


def safe_filename(value: str) -> str:
    value = clean_text(value, 120)
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
    value = re.sub(r"\s+", "_", value)
    return value.strip("._") or "character"


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# STORAGE
# ---------------------------------------------------------

def load_database(path: Path | None = None) -> dict:
    source = path or DATA_FILE

    if not source.exists():
        return {"characters": []}

    try:
        with source.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            return {"characters": []}

        characters = data.get("characters", [])

        if not isinstance(characters, list):
            characters = []

        return {"characters": characters}

    except (OSError, json.JSONDecodeError):
        return {"characters": []}


def save_database(
    data: dict,
    path: Path | None = None,
) -> None:
    destination = path or DATA_FILE
    destination.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "characters": data.get("characters", [])
    }

    temporary = destination.with_suffix(
        destination.suffix + ".tmp"
    )

    with temporary.open("w", encoding="utf-8") as file:
        json.dump(
            payload,
            file,
            indent=2,
            ensure_ascii=False,
        )

    temporary.replace(destination)


# ---------------------------------------------------------
# CHARACTER PROFILE VALIDATION
# ---------------------------------------------------------

def validate_character(data: dict) -> dict:
    """Validate and normalize a character profile."""

    name = clean_text(data.get("name"), 150)

    if not name:
        raise ValueError("Character name is required.")

    category = clean_text(
        data.get("category", "AI Influencer"),
        60,
    )

    if category not in CHARACTER_CATEGORIES:
        category = "Other"

    status = clean_text(
        data.get("status", "Active"),
        30,
    )

    if status not in PROFILE_STATUSES:
        status = "Draft"

    outfits = data.get("outfits", [])

    if not isinstance(outfits, list):
        outfits = []

    clean_outfits = []

    for outfit in outfits:
        if not isinstance(outfit, dict):
            continue

        outfit_name = clean_text(
            outfit.get("name"),
            100,
        )

        if not outfit_name:
            continue

        clean_outfits.append({
            "id": clean_text(
                outfit.get("id") or make_id("outfit"),
                100,
            ),
            "name": outfit_name,
            "description": clean_text(
                outfit.get("description")
            ),
            "is_default": bool(
                outfit.get("is_default", False)
            ),
        })

    return {
        "name": name,
        "category": category,
        "age_description": clean_text(
            data.get("age_description"), 100
        ),
        "gender_presentation": clean_text(
            data.get("gender_presentation"), 100
        ),
        "face_description": clean_text(
            data.get("face_description")
        ),
        "skin_description": clean_text(
            data.get("skin_description")
        ),
        "eye_description": clean_text(
            data.get("eye_description")
        ),
        "hair_description": clean_text(
            data.get("hair_description")
        ),
        "body_description": clean_text(
            data.get("body_description")
        ),
        "distinctive_features": clean_text(
            data.get("distinctive_features")
        ),
        "default_outfit": clean_text(
            data.get("default_outfit")
        ),
        "outfits": clean_outfits,
        "personality": clean_text(
            data.get("personality")
        ),
        "voice_description": clean_text(
            data.get("voice_description")
        ),
        "background_story": clean_text(
            data.get("background_story")
        ),
        "identity_notes": clean_text(
            data.get("identity_notes")
        ),
        "reference_image": clean_text(
            data.get("reference_image"), 1000
        ),
        "status": status,
    }


# ---------------------------------------------------------
# CHARACTER CRUD
# ---------------------------------------------------------

def create_character(
    profile: dict,
    database_path: Path | None = None,
) -> dict:
    """Create a new character profile."""

    normalized = validate_character(profile)

    data = load_database(database_path)

    character = {
        "id": make_id(),
        **normalized,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }

    data["characters"].append(character)

    save_database(data, database_path)

    return character


def get_characters(
    database_path: Path | None = None,
) -> list[dict]:
    return load_database(database_path)["characters"]


def get_character(
    character_id: str,
    database_path: Path | None = None,
) -> dict | None:
    for character in get_characters(database_path):
        if character.get("id") == character_id:
            return character

    return None


def update_character(
    character_id: str,
    updates: dict,
    database_path: Path | None = None,
) -> dict:
    """Update an existing character profile."""

    data = load_database(database_path)

    for character in data["characters"]:
        if character.get("id") != character_id:
            continue

        merged = dict(character)
        merged.update(updates)

        normalized = validate_character(merged)

        character.update(normalized)
        character["updated_at"] = now_iso()

        save_database(data, database_path)

        return character

    raise ValueError("Character not found.")


def delete_character(
    character_id: str,
    database_path: Path | None = None,
) -> bool:
    data = load_database(database_path)

    original_count = len(data["characters"])

    data["characters"] = [
        character
        for character in data["characters"]
        if character.get("id") != character_id
    ]

    if len(data["characters"]) == original_count:
        return False

    save_database(data, database_path)
    return True


def duplicate_character(
    character_id: str,
    database_path: Path | None = None,
) -> dict:
    """Duplicate a character profile."""

    original = get_character(
        character_id,
        database_path,
    )

    if not original:
        raise ValueError("Character not found.")

    copied = dict(original)

    copied.pop("id", None)
    copied.pop("created_at", None)
    copied.pop("updated_at", None)

    copied["name"] = original["name"] + " Copy"

    # Give copied outfits independent IDs.
    copied["outfits"] = [
        {
            **outfit,
            "id": make_id("outfit"),
        }
        for outfit in original.get("outfits", [])
    ]

    return create_character(
        copied,
        database_path,
    )


# ---------------------------------------------------------
# OUTFIT MANAGEMENT
# ---------------------------------------------------------

def add_outfit(
    character_id: str,
    outfit_name: str,
    description: str,
    database_path: Path | None = None,
) -> dict:
    """Add an outfit to a character."""

    outfit_name = clean_text(outfit_name, 100)

    if not outfit_name:
        raise ValueError("Outfit name is required.")

    data = load_database(database_path)

    for character in data["characters"]:
        if character.get("id") != character_id:
            continue

        outfits = character.setdefault("outfits", [])

        outfit = {
            "id": make_id("outfit"),
            "name": outfit_name,
            "description": clean_text(description),
            "is_default": False,
        }

        outfits.append(outfit)
        character["updated_at"] = now_iso()

        save_database(data, database_path)

        return outfit

    raise ValueError("Character not found.")


def delete_outfit(
    character_id: str,
    outfit_id: str,
    database_path: Path | None = None,
) -> bool:
    data = load_database(database_path)

    for character in data["characters"]:
        if character.get("id") != character_id:
            continue

        outfits = character.get("outfits", [])
        original_count = len(outfits)

        character["outfits"] = [
            outfit
            for outfit in outfits
            if outfit.get("id") != outfit_id
        ]

        if len(character["outfits"]) == original_count:
            return False

        character["updated_at"] = now_iso()

        save_database(data, database_path)
        return True

    return False


# ---------------------------------------------------------
# CHARACTER IDENTITY PROMPTS
# ---------------------------------------------------------

def generate_identity_description(
    character: dict,
    outfit_id: str | None = None,
) -> str:
    """Build a reusable character identity description."""

    parts = [
        f"Character name: {character.get('name', '')}.",
    ]

    fields = [
        ("Age description", "age_description"),
        ("Gender presentation", "gender_presentation"),
        ("Face", "face_description"),
        ("Skin", "skin_description"),
        ("Eyes", "eye_description"),
        ("Hair", "hair_description"),
        ("Body", "body_description"),
        ("Distinctive features", "distinctive_features"),
    ]

    for label, key in fields:
        value = clean_text(character.get(key))

        if value:
            parts.append(f"{label}: {value}.")

    outfit = None

    if outfit_id:
        outfit = next(
            (
                item
                for item in character.get("outfits", [])
                if item.get("id") == outfit_id
            ),
            None,
        )

    if outfit:
        parts.append(
            "Selected outfit: "
            + outfit.get("name", "")
            + ". "
            + outfit.get("description", "")
        )

    elif clean_text(character.get("default_outfit")):
        parts.append(
            "Default outfit: "
            + character["default_outfit"]
            + "."
        )

    if clean_text(character.get("personality")):
        parts.append(
            "Personality: "
            + character["personality"]
            + "."
        )

    if clean_text(character.get("identity_notes")):
        parts.append(
            "Identity notes: "
            + character["identity_notes"]
            + "."
        )

    return "\n".join(parts)


def generate_identity_lock(
    character: dict,
    outfit_id: str | None = None,
) -> str:
    """Create identity consistency instructions."""

    identity = generate_identity_description(
        character,
        outfit_id,
    )

    return (
        "CHARACTER IDENTITY LOCK\n\n"
        "Use the following description as the fixed identity "
        "reference for this character:\n\n"
        + identity
        + "\n\n"
        "CONSISTENCY REQUIREMENTS:\n"
        "- Preserve the same recognizable face.\n"
        "- Preserve hairstyle, hair color and eye color.\n"
        "- Preserve distinctive facial marks and features.\n"
        "- Preserve body proportions and overall appearance.\n"
        "- Do not randomly change the character's age or identity.\n"
        "- Keep the selected outfit consistent unless a costume "
        "change is explicitly requested.\n"
        "- Maintain visual continuity across shots and scenes.\n"
        "- Do not create duplicate or additional versions "
        "of the character.\n"
    )


def generate_character_image_prompt(
    character: dict,
    scene_description: str,
    outfit_id: str | None = None,
) -> str:
    """Create a scene prompt using a saved character profile."""

    scene_description = clean_text(scene_description)

    if not scene_description:
        raise ValueError("Scene description is required.")

    identity = generate_identity_description(
        character,
        outfit_id,
    )

    return (
        "CHARACTER REFERENCE:\n"
        + identity
        + "\n\nSCENE:\n"
        + scene_description
        + "\n\nVISUAL INSTRUCTIONS:\n"
        "Maintain the exact character identity described above. "
        "Use coherent anatomy, natural proportions, consistent "
        "facial features and a visually consistent outfit. "
        "Place the character naturally within the scene."
    )


def generate_character_video_prompt(
    character: dict,
    action: str,
    duration: int = 8,
    outfit_id: str | None = None,
) -> str:
    """Create a character-focused video prompt."""

    action = clean_text(action)

    if not action:
        raise ValueError("Character action is required.")

    duration = max(1, min(int(duration), 3600))

    identity_lock = generate_identity_lock(
        character,
        outfit_id,
    )

    return (
        identity_lock
        + "\n\nVIDEO ACTION:\n"
        + action
        + f"\n\nDURATION: {duration} seconds.\n"
        "Maintain identity and outfit continuity throughout "
        "the complete clip. Use smooth, natural movement. "
        "Avoid flickering, face morphing and unintended "
        "appearance changes."
    )


# ---------------------------------------------------------
# SEARCH AND EXPORT
# ---------------------------------------------------------

def search_characters(
    query: str,
    database_path: Path | None = None,
) -> list[dict]:
    query = clean_text(query).lower()

    if not query:
        return get_characters(database_path)

    results = []

    for character in get_characters(database_path):
        searchable = " ".join([
            character.get("name", ""),
            character.get("category", ""),
            character.get("face_description", ""),
            character.get("hair_description", ""),
            character.get("eye_description", ""),
            character.get("personality", ""),
            character.get("background_story", ""),
        ]).lower()

        if query in searchable:
            results.append(character)

    return results


def export_character_json(character: dict) -> str:
    return json.dumps(
        character,
        indent=2,
        ensure_ascii=False,
    )


def export_character_text(character: dict) -> str:
    return (
        "CHARACTER PROFILE\n"
        "=================\n\n"
        + generate_identity_description(character)
        + "\n\nBACKGROUND STORY:\n"
        + character.get("background_story", "")
        + "\n\nVOICE DESCRIPTION:\n"
        + character.get("voice_description", "")
        + "\n\nIDENTITY LOCK:\n"
        + generate_identity_lock(character)
    )


def save_character_export(
    character: dict,
    file_format: str = "json",
) -> Path:
    ensure_directories()

    name = safe_filename(character.get("name", "character"))

    if file_format.lower() == "json":
        content = export_character_json(character)
        extension = ".json"

    elif file_format.lower() == "txt":
        content = export_character_text(character)
        extension = ".txt"

    else:
        raise ValueError("Supported formats are JSON and TXT.")

    destination = OUTPUT_DIR / f"{name}{extension}"

    destination.write_text(
        content,
        encoding="utf-8",
    )

    return destination


# ---------------------------------------------------------
# STREAMLIT UI
# ---------------------------------------------------------

def render() -> None:
    try:
        import streamlit as st
    except ImportError as exc:
        raise RuntimeError(
            "Install Streamlit using: pip install streamlit"
        ) from exc

    ensure_directories()

    st.title("🧑 Character Identity Manager")
    st.caption(
        "Build reusable character profiles and preserve "
        "appearance descriptions across your AI scenes."
    )

    tab_create, tab_library, tab_prompts = st.tabs([
        "Create Character",
        "Character Library",
        "Identity Prompts",
    ])

    # -----------------------------------------------------
    # CREATE CHARACTER
    # -----------------------------------------------------

    with tab_create:
        st.subheader("Create character profile")

        with st.form("character_create_form"):

            name = st.text_input(
                "Character name",
                placeholder="Example: Eira",
            )

            category = st.selectbox(
                "Character category",
                CHARACTER_CATEGORIES,
            )

            age_description = st.text_input(
                "Age description",
                placeholder="Example: Adult, approximately 29",
            )

            gender_presentation = st.text_input(
                "Gender presentation",
            )

            st.markdown("#### Physical appearance")

            face_description = st.text_area(
                "Face description",
                placeholder="Face shape, facial structure...",
            )

            skin_description = st.text_input(
                "Skin description",
            )

            eye_description = st.text_input(
                "Eye description",
                placeholder="Eye color, shape and details...",
            )

            hair_description = st.text_area(
                "Hair description",
                placeholder="Hair color, length and hairstyle...",
            )

            body_description = st.text_area(
                "Body description",
                placeholder="General body proportions...",
            )

            distinctive_features = st.text_area(
                "Distinctive features",
                placeholder="Scars, freckles, marks, accessories...",
            )

            st.markdown("#### Clothing")

            default_outfit = st.text_area(
                "Default outfit",
                placeholder="Describe the standard outfit...",
            )

            st.markdown("#### Personality and voice")

            personality = st.text_area(
                "Personality",
            )

            voice_description = st.text_area(
                "Voice description",
                placeholder="Deep male voice, calm female voice...",
            )

            background_story = st.text_area(
                "Background story",
            )

            identity_notes = st.text_area(
                "Identity consistency notes",
                placeholder=(
                    "Keep the same face, hairstyle, clothing "
                    "and distinctive features..."
                ),
            )

            reference_image = st.text_input(
                "Reference image path (optional)",
                placeholder="assets/characters/eira.png",
            )

            submitted = st.form_submit_button(
                "Create Character",
                type="primary",
            )

            if submitted:
                try:
                    character = create_character({
                        "name": name,
                        "category": category,
                        "age_description": age_description,
                        "gender_presentation": gender_presentation,
                        "face_description": face_description,
                        "skin_description": skin_description,
                        "eye_description": eye_description,
                        "hair_description": hair_description,
                        "body_description": body_description,
                        "distinctive_features": distinctive_features,
                        "default_outfit": default_outfit,
                        "personality": personality,
                        "voice_description": voice_description,
                        "background_story": background_story,
                        "identity_notes": identity_notes,
                        "reference_image": reference_image,
                    })

                    st.success(
                        f"Created character: {character['name']}"
                    )
                    st.rerun()

                except ValueError as exc:
                    st.error(str(exc))

    # -----------------------------------------------------
    # CHARACTER LIBRARY
    # -----------------------------------------------------

    with tab_library:
        st.subheader("Saved characters")

        query = st.text_input(
            "Search characters",
            placeholder="Search by name or appearance...",
            key="character_search",
        )

        characters = search_characters(query)

        if not characters:
            st.info("No character profiles found.")

        for character in reversed(characters):
            with st.expander(character["name"]):

                st.write(
                    f"**Category:** {character.get('category')}"
                )

                st.write(
                    f"**Status:** {character.get('status')}"
                )

                st.write(
                    f"**Created:** {character.get('created_at')}"
                )

                st.markdown("#### Identity summary")

                st.code(
                    generate_identity_description(character),
                    language="text",
                )

                st.markdown("#### Manage profile")

                with st.form(
                    f"edit_character_{character['id']}"
                ):
                    edited_name = st.text_input(
                        "Name",
                        value=character.get("name", ""),
                    )

                    edited_face = st.text_area(
                        "Face description",
                        value=character.get("face_description", ""),
                    )

                    edited_hair = st.text_area(
                        "Hair description",
                        value=character.get("hair_description", ""),
                    )

                    edited_eyes = st.text_input(
                        "Eye description",
                        value=character.get("eye_description", ""),
                    )

                    edited_outfit = st.text_area(
                        "Default outfit",
                        value=character.get("default_outfit", ""),
                    )

                    edited_notes = st.text_area(
                        "Identity notes",
                        value=character.get("identity_notes", ""),
                    )

                    edited_status = st.selectbox(
                        "Status",
                        PROFILE_STATUSES,
                        index=(
                            PROFILE_STATUSES.index(
                                character.get("status", "Active")
                            )
                            if character.get("status") in PROFILE_STATUSES
                            else 0
                        ),
                    )

                    save_changes = st.form_submit_button(
                        "Save Profile Changes"
                    )

                    if save_changes:
                        try:
                            update_character(
                                character["id"],
                                {
                                    "name": edited_name,
                                    "face_description": edited_face,
                                    "hair_description": edited_hair,
                                    "eye_description": edited_eyes,
                                    "default_outfit": edited_outfit,
                                    "identity_notes": edited_notes,
                                    "status": edited_status,
                                },
                            )

                            st.success("Character updated.")
                            st.rerun()

                        except ValueError as exc:
                            st.error(str(exc))

                st.markdown("#### Alternate outfits")

                for outfit in character.get("outfits", []):
                    st.write(
                        f"**{outfit['name']}** — "
                        f"{outfit.get('description', '')}"
                    )

                    if st.button(
                        "Delete outfit: " + outfit["name"],
                        key=f"delete_outfit_{outfit['id']}",
                    ):
                        delete_outfit(
                            character["id"],
                            outfit["id"],
                        )
                        st.rerun()

                with st.form(
                    f"add_outfit_{character['id']}"
                ):
                    outfit_name = st.text_input(
                        "New outfit name"
                    )

                    outfit_description = st.text_area(
                        "Outfit description"
                    )

                    add_outfit_button = st.form_submit_button(
                        "Add Outfit"
                    )

                    if add_outfit_button:
                        try:
                            add_outfit(
                                character["id"],
                                outfit_name,
                                outfit_description,
                            )
                            st.success("Outfit added.")
                            st.rerun()

                        except ValueError as exc:
                            st.error(str(exc))

                col1, col2 = st.columns(2)

                with col1:
                    st.download_button(
                        "Download JSON",
                        data=export_character_json(character),
                        file_name=(
                            safe_filename(character["name"]) + ".json"
                        ),
                        mime="application/json",
                        key=f"character_json_{character['id']}",
                    )

                with col2:
                    st.download_button(
                        "Download TXT",
                        data=export_character_text(character),
                        file_name=(
                            safe_filename(character["name"]) + ".txt"
                        ),
                        mime="text/plain",
                        key=f"character_txt_{character['id']}",
                    )

                col_a, col_b = st.columns(2)

                with col_a:
                    if st.button(
                        "Duplicate Character",
                        key=f"duplicate_character_{character['id']}",
                    ):
                        duplicate_character(character["id"])
                        st.success("Character duplicated.")
                        st.rerun()

                with col_b:
                    if st.button(
                        "Delete Character",
                        key=f"delete_character_{character['id']}",
                    ):
                        delete_character(character["id"])
                        st.success("Character deleted.")
                        st.rerun()

    # -----------------------------------------------------
    # IDENTITY PROMPTS
    # -----------------------------------------------------

    with tab_prompts:
        st.subheader("Generate identity instructions")

        characters = get_characters()

        if not characters:
            st.info("Create a character profile first.")

        else:
            character_map = {
                item["id"]: item["name"]
                for item in characters
            }

            selected_id = st.selectbox(
                "Select character",
                list(character_map.keys()),
                format_func=lambda key: character_map[key],
            )

            selected = get_character(selected_id)

            outfits = selected.get("outfits", [])

            outfit_options = {
                "default": "Default outfit"
            }

            for outfit in outfits:
                outfit_options[outfit["id"]] = outfit["name"]

            selected_outfit = st.selectbox(
                "Select outfit",
                list(outfit_options.keys()),
                format_func=lambda key: outfit_options[key],
            )

            outfit_id = (
                None
                if selected_outfit == "default"
                else selected_outfit
            )

            identity_prompt = generate_identity_lock(
                selected,
                outfit_id,
            )

            st.markdown("#### Identity lock prompt")
            st.code(identity_prompt, language="text")

            scene_description = st.text_area(
                "Scene description",
                placeholder=(
                    "A cinematic scene of the character "
                    "walking through a snowy forest..."
                ),
            )

            if st.button("Generate Image Scene Prompt"):
                try:
                    result = generate_character_image_prompt(
                        selected,
                        scene_description,
                        outfit_id,
                    )

                    st.session_state[
                        "character_image_prompt"
                    ] = result

                except ValueError as exc:
                    st.error(str(exc))

            image_result = st.session_state.get(
                "character_image_prompt"
            )

            if image_result:
                st.markdown("#### Image prompt")
                st.code(image_result, language="text")

                st.download_button(
                    "Download Image Prompt",
                    data=image_result,
                    file_name="character_image_prompt.txt",
                    mime="text/plain",
                )

            st.divider()
            st.markdown("#### Video identity prompt")

            action = st.text_area(
                "Character action",
                placeholder=(
                    "The character slowly turns toward "
                    "the camera..."
                ),
            )

            duration = st.number_input(
                "Video duration in seconds",
                min_value=1,
                max_value=3600,
                value=8,
            )

            if st.button("Generate Video Identity Prompt"):
                try:
                    result = generate_character_video_prompt(
                        selected,
                        action,
                        duration,
                        outfit_id,
                    )

                    st.session_state[
                        "character_video_prompt"
                    ] = result

                except ValueError as exc:
                    st.error(str(exc))

            video_result = st.session_state.get(
                "character_video_prompt"
            )

            if video_result:
                st.code(video_result, language="text")

                st.download_button(
                    "Download Video Prompt",
                    data=video_result,
                    file_name="character_video_prompt.txt",
                    mime="text/plain",
                )


# ---------------------------------------------------------
# BUILT-IN TESTS
# ---------------------------------------------------------

class CharacterIdentityTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_file = (
            Path(self.temp_dir.name) / "characters.json"
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_test_character(self):
        return create_character(
            {
                "name": "Eira",
                "category": "Fantasy Character",
                "face_description": "Oval face",
                "eye_description": "Gray-blue eyes",
                "hair_description": "Two dark brown braids",
                "default_outfit": "Dark blue dress",
                "identity_notes": "Keep facial scar consistent",
            },
            self.test_file,
        )

    def test_create_character(self):
        character = self.create_test_character()

        self.assertEqual(character["name"], "Eira")
        self.assertEqual(len(get_characters(self.test_file)), 1)

    def test_empty_name_rejected(self):
        with self.assertRaises(ValueError):
            create_character(
                {"name": ""},
                self.test_file,
            )

    def test_update_character(self):
        character = self.create_test_character()

        updated = update_character(
            character["id"],
            {"eye_description": "Bright blue eyes"},
            self.test_file,
        )

        self.assertEqual(
            updated["eye_description"],
            "Bright blue eyes",
        )

    def test_delete_character(self):
        character = self.create_test_character()

        self.assertTrue(
            delete_character(
                character["id"],
                self.test_file,
            )
        )

        self.assertEqual(
            len(get_characters(self.test_file)),
            0,
        )

    def test_duplicate_character(self):
        original = self.create_test_character()

        duplicate = duplicate_character(
            original["id"],
            self.test_file,
        )

        self.assertNotEqual(
            original["id"],
            duplicate["id"],
        )

        self.assertEqual(
            len(get_characters(self.test_file)),
            2,
        )

    def test_add_and_delete_outfit(self):
        character = self.create_test_character()

        outfit = add_outfit(
            character["id"],
            "Winter Outfit",
            "White winter coat",
            self.test_file,
        )

        updated = get_character(
            character["id"],
            self.test_file,
        )

        self.assertEqual(len(updated["outfits"]), 1)

        self.assertTrue(
            delete_outfit(
                character["id"],
                outfit["id"],
                self.test_file,
            )
        )

    def test_identity_lock(self):
        character = self.create_test_character()

        prompt = generate_identity_lock(character)

        self.assertIn("Eira", prompt)
        self.assertIn("gray-blue eyes", prompt)
        self.assertIn("CONSISTENCY REQUIREMENTS", prompt)

    def test_image_prompt(self):
        character = self.create_test_character()

        prompt = generate_character_image_prompt(
            character,
            "Walking through a snowy forest",
        )

        self.assertIn("Eira", prompt)
        self.assertIn("snowy forest", prompt)

    def test_video_prompt(self):
        character = self.create_test_character()

        prompt = generate_character_video_prompt(
            character,
            "Slowly turning toward the camera",
            duration=10,
        )

        self.assertIn("10 seconds", prompt)
        self.assertIn("turning toward the camera", prompt)

    def test_empty_scene_rejected(self):
        character = self.create_test_character()

        with self.assertRaises(ValueError):
            generate_character_image_prompt(
                character,
                "",
            )

    def test_export(self):
        character = self.create_test_character()

        self.assertIn(
            "Eira",
            export_character_json(character),
        )

        self.assertIn(
            "IDENTITY LOCK",
            export_character_text(character),
        )

    def test_search(self):
        self.create_test_character()

        results = search_characters(
            "braids",
            self.test_file,
        )

        self.assertEqual(len(results), 1)


# ---------------------------------------------------------
# COMMAND LINE
# ---------------------------------------------------------

def run_tests() -> bool:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        CharacterIdentityTests
    )

    result = unittest.TextTestRunner(
        verbosity=2
    ).run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Character Identity Manager"
    )

    parser.add_argument(
        "--test",
        action="store_true",
        help="Run built-in tests",
    )

    args = parser.parse_args()

    if args.test:
        raise SystemExit(
            0 if run_tests() else 1
        )

    print("Character Identity Manager")
    print("Register this module in your Streamlit application.")
