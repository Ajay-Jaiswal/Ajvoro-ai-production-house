
"""
File 61: modules/outfit_consistency_manager.py

AI Influencer Studio - Outfit Consistency Manager

Features:
- Create and manage character outfit profiles
- Store clothing, colors, materials, accessories and footwear
- Save outfit reference images
- Assign outfits to scenes
- Detect missing or conflicting scene assignments
- Search, edit, duplicate and delete outfits
- Export outfit data as JSON or CSV
- Streamlit interface
- Built-in tests

Run tests:
    python -m modules.outfit_consistency_manager --test
"""

from __future__ import annotations

import csv
import json
import shutil
import tempfile
import uuid

from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------
# PATH CONFIGURATION
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
ASSET_DIR = BASE_DIR / "assets" / "outfit_consistency"
OUTPUT_DIR = BASE_DIR / "outputs" / "outfit_consistency"

DATABASE_FILE = DATA_DIR / "outfit_consistency.json"

for directory in (DATA_DIR, ASSET_DIR, OUTPUT_DIR):
    directory.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# GENERAL HELPERS
# ---------------------------------------------------------

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _clean(value: Any, limit: int = 5000) -> str:
    return str(value or "").strip()[:limit]


def _read_database(path: Path | None = None) -> dict:
    path = path or DATABASE_FILE

    if not path.exists():
        return {"outfits": [], "assignments": []}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))

        if not isinstance(data, dict):
            return {"outfits": [], "assignments": []}

        data.setdefault("outfits", [])
        data.setdefault("assignments", [])

        if not isinstance(data["outfits"], list):
            data["outfits"] = []

        if not isinstance(data["assignments"], list):
            data["assignments"] = []

        return data

    except (OSError, json.JSONDecodeError):
        return {"outfits": [], "assignments": []}


def _write_database(
    data: dict,
    path: Path | None = None
) -> None:
    path = path or DATABASE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_suffix(path.suffix + ".tmp")

    temporary.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    temporary.replace(path)


def _find_outfit(data: dict, outfit_id: str) -> dict | None:
    return next(
        (
            item for item in data["outfits"]
            if item.get("id") == outfit_id
        ),
        None
    )


def _safe_filename(filename: str) -> str:
    name = Path(filename).name
    allowed = "".join(
        char for char in name
        if char.isalnum() or char in "._-"
    )

    return allowed[:100] or "reference_image"


# ---------------------------------------------------------
# IMAGE STORAGE
# ---------------------------------------------------------

def save_reference_image(
    source_path: str | Path,
    outfit_id: str,
    destination_dir: Path | None = None
) -> str:
    """
    Copy an uploaded reference image into managed storage.

    Returns the saved image path.
    """

    source = Path(source_path)

    if not source.exists() or not source.is_file():
        raise FileNotFoundError("Reference image was not found.")

    allowed_extensions = {
        ".png", ".jpg", ".jpeg", ".webp"
    }

    if source.suffix.lower() not in allowed_extensions:
        raise ValueError("Unsupported image format.")

    destination_dir = destination_dir or ASSET_DIR
    destination_dir.mkdir(parents=True, exist_ok=True)

    filename = (
        f"{outfit_id}_{_safe_filename(source.name)}"
    )

    destination = destination_dir / filename

    shutil.copy2(source, destination)

    return str(destination)


# ---------------------------------------------------------
# OUTFIT CRUD
# ---------------------------------------------------------

def create_outfit(
    character_name: str,
    outfit_name: str,
    clothing_type: str = "",
    colors: str = "",
    material: str = "",
    accessories: str = "",
    footwear: str = "",
    description: str = "",
    continuity_rules: str = "",
    negative_prompt: str = "",
    tags: list[str] | None = None,
    reference_image: str | None = None,
    database_path: Path | None = None
) -> dict:
    """Create a new outfit profile."""

    character_name = _clean(character_name, 150)
    outfit_name = _clean(outfit_name, 150)

    if not character_name:
        raise ValueError("Character name is required.")

    if not outfit_name:
        raise ValueError("Outfit name is required.")

    data = _read_database(database_path)

    outfit_id = _new_id()

    image_path = None

    if reference_image:
        image_path = save_reference_image(
            reference_image,
            outfit_id
        )

    outfit = {
        "id": outfit_id,
        "character_name": character_name,
        "outfit_name": outfit_name,
        "clothing_type": _clean(clothing_type, 300),
        "colors": _clean(colors, 500),
        "material": _clean(material, 500),
        "accessories": _clean(accessories, 1000),
        "footwear": _clean(footwear, 500),
        "description": _clean(description, 3000),
        "continuity_rules": _clean(
            continuity_rules, 2000
        ),
        "negative_prompt": _clean(
            negative_prompt, 2000
        ),
        "tags": [
            _clean(tag, 100)
            for tag in (tags or [])
            if _clean(tag, 100)
        ],
        "reference_image": image_path,
        "created_at": _now(),
        "updated_at": _now()
    }

    data["outfits"].append(outfit)
    _write_database(data, database_path)

    return outfit


def list_outfits(
    character_name: str | None = None,
    database_path: Path | None = None
) -> list[dict]:
    data = _read_database(database_path)
    outfits = data["outfits"]

    if character_name:
        target = character_name.strip().lower()

        outfits = [
            item for item in outfits
            if item.get("character_name", "").lower()
            == target
        ]

    return sorted(
        outfits,
        key=lambda item: item.get("updated_at", ""),
        reverse=True
    )


def get_outfit(
    outfit_id: str,
    database_path: Path | None = None
) -> dict | None:
    data = _read_database(database_path)
    return _find_outfit(data, outfit_id)


def update_outfit(
    outfit_id: str,
    database_path: Path | None = None,
    **changes
) -> dict:
    allowed_fields = {
        "character_name",
        "outfit_name",
        "clothing_type",
        "colors",
        "material",
        "accessories",
        "footwear",
        "description",
        "continuity_rules",
        "negative_prompt",
        "tags"
    }

    data = _read_database(database_path)
    outfit = _find_outfit(data, outfit_id)

    if not outfit:
        raise ValueError("Outfit not found.")

    for key, value in changes.items():
        if key not in allowed_fields:
            continue

        if key == "tags":
            value = [
                _clean(tag, 100)
                for tag in (value or [])
                if _clean(tag, 100)
            ]
        else:
            value = _clean(value)

        outfit[key] = value

    if not outfit.get("character_name"):
        raise ValueError("Character name cannot be empty.")

    if not outfit.get("outfit_name"):
        raise ValueError("Outfit name cannot be empty.")

    outfit["updated_at"] = _now()

    _write_database(data, database_path)

    return outfit


def duplicate_outfit(
    outfit_id: str,
    database_path: Path | None = None
) -> dict:
    data = _read_database(database_path)
    original = _find_outfit(data, outfit_id)

    if not original:
        raise ValueError("Outfit not found.")

    duplicate = dict(original)
    duplicate["id"] = _new_id()
    duplicate["outfit_name"] = (
        original["outfit_name"] + " Copy"
    )
    duplicate["created_at"] = _now()
    duplicate["updated_at"] = _now()

    # Reference image is shared rather than copied.
    data["outfits"].append(duplicate)

    _write_database(data, database_path)

    return duplicate


def delete_outfit(
    outfit_id: str,
    database_path: Path | None = None
) -> bool:
    data = _read_database(database_path)
    outfit = _find_outfit(data, outfit_id)

    if not outfit:
        return False

    data["outfits"] = [
        item for item in data["outfits"]
        if item.get("id") != outfit_id
    ]

    # Remove scene assignments referencing this outfit.
    data["assignments"] = [
        item for item in data["assignments"]
        if item.get("outfit_id") != outfit_id
    ]

    # Remove its image only if no other outfit uses it.
    image_path = outfit.get("reference_image")

    if image_path:
        still_used = any(
            item.get("reference_image") == image_path
            for item in data["outfits"]
        )

        if not still_used:
            try:
                Path(image_path).unlink(missing_ok=True)
            except OSError:
                pass

    _write_database(data, database_path)

    return True


# ---------------------------------------------------------
# SEARCH
# ---------------------------------------------------------

def search_outfits(
    query: str,
    database_path: Path | None = None
) -> list[dict]:
    query = _clean(query).lower()

    if not query:
        return list_outfits(database_path=database_path)

    results = []

    for outfit in list_outfits(
        database_path=database_path
    ):
        searchable = " ".join([
            outfit.get("character_name", ""),
            outfit.get("outfit_name", ""),
            outfit.get("clothing_type", ""),
            outfit.get("colors", ""),
            outfit.get("material", ""),
            outfit.get("accessories", ""),
            outfit.get("description", ""),
            " ".join(outfit.get("tags", []))
        ]).lower()

        if query in searchable:
            results.append(outfit)

    return results


# ---------------------------------------------------------
# SCENE ASSIGNMENTS
# ---------------------------------------------------------

def assign_outfit_to_scene(
    outfit_id: str,
    scene_name: str,
    scene_number: str = "",
    notes: str = "",
    database_path: Path | None = None
) -> dict:
    """Assign an outfit to a character scene."""

    data = _read_database(database_path)
    outfit = _find_outfit(data, outfit_id)

    if not outfit:
        raise ValueError("Outfit not found.")

    scene_name = _clean(scene_name, 200)

    if not scene_name:
        raise ValueError("Scene name is required.")

    assignment = {
        "id": _new_id(),
        "outfit_id": outfit_id,
        "character_name": outfit["character_name"],
        "outfit_name": outfit["outfit_name"],
        "scene_name": scene_name,
        "scene_number": _clean(scene_number, 50),
        "notes": _clean(notes, 1000),
        "created_at": _now()
    }

    data["assignments"].append(assignment)
    _write_database(data, database_path)

    return assignment


def list_scene_assignments(
    character_name: str | None = None,
    database_path: Path | None = None
) -> list[dict]:
    data = _read_database(database_path)
    assignments = data["assignments"]

    if character_name:
        target = character_name.strip().lower()

        assignments = [
            item for item in assignments
            if item.get("character_name", "").lower()
            == target
        ]

    return sorted(
        assignments,
        key=lambda item: (
            item.get("scene_number", ""),
            item.get("scene_name", "")
        )
    )


def remove_scene_assignment(
    assignment_id: str,
    database_path: Path | None = None
) -> bool:
    data = _read_database(database_path)

    original_count = len(data["assignments"])

    data["assignments"] = [
        item for item in data["assignments"]
        if item.get("id") != assignment_id
    ]

    if len(data["assignments"]) == original_count:
        return False

    _write_database(data, database_path)

    return True


def check_scene_continuity(
    character_name: str,
    database_path: Path | None = None
) -> dict:
    """
    Check whether a character has multiple outfit profiles
    assigned across scenes.

    This is a metadata-level warning. Different outfits may
    be intentional, so the result is not automatically an error.
    """

    assignments = list_scene_assignments(
        character_name,
        database_path
    )

    grouped = {}

    for assignment in assignments:
        scene = (
            assignment.get("scene_number")
            or assignment.get("scene_name")
        )

        grouped.setdefault(scene, []).append(assignment)

    warnings = []

    for scene, entries in grouped.items():
        outfit_ids = {
            entry.get("outfit_id")
            for entry in entries
        }

        if len(outfit_ids) > 1:
            warnings.append({
                "scene": scene,
                "message": (
                    "Multiple outfit profiles are assigned "
                    "to this character in the same scene."
                )
            })

    return {
        "character_name": character_name,
        "assignment_count": len(assignments),
        "scene_count": len(grouped),
        "warnings": warnings,
        "consistent": len(warnings) == 0
    }


# ---------------------------------------------------------
# STATISTICS
# ---------------------------------------------------------

def get_statistics(
    database_path: Path | None = None
) -> dict:
    data = _read_database(database_path)

    outfits = data["outfits"]
    assignments = data["assignments"]

    characters = {
        item.get("character_name")
        for item in outfits
    }

    return {
        "total_outfits": len(outfits),
        "total_assignments": len(assignments),
        "total_characters": len(characters),
        "characters": sorted(
            name for name in characters if name
        ),
        "outfits_without_reference": sum(
            1 for item in outfits
            if not item.get("reference_image")
        )
    }


# ---------------------------------------------------------
# EXPORT
# ---------------------------------------------------------

def export_json(
    database_path: Path | None = None,
    output_path: Path | None = None
) -> Path:
    data = _read_database(database_path)

    output_path = output_path or (
        OUTPUT_DIR / f"outfits_{_now().replace(':', '-')}.json"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    return output_path


def export_csv(
    database_path: Path | None = None,
    output_path: Path | None = None
) -> Path:
    outfits = list_outfits(database_path=database_path)

    output_path = output_path or (
        OUTPUT_DIR / f"outfits_{_now().replace(':', '-')}.csv"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    fields = [
        "id",
        "character_name",
        "outfit_name",
        "clothing_type",
        "colors",
        "material",
        "accessories",
        "footwear",
        "description",
        "continuity_rules",
        "negative_prompt",
        "reference_image",
        "created_at",
        "updated_at"
    ]

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fields,
            extrasaction="ignore"
        )

        writer.writeheader()

        for outfit in outfits:
            writer.writerow(outfit)

    return output_path


# ---------------------------------------------------------
# PROMPT HELPER
# ---------------------------------------------------------

def build_outfit_prompt(
    outfit_id: str,
    database_path: Path | None = None
) -> str:
    """Build a reusable outfit continuity prompt."""

    outfit = get_outfit(outfit_id, database_path)

    if not outfit:
        raise ValueError("Outfit not found.")

    sections = [
        f"Character: {outfit['character_name']}",
        f"Outfit: {outfit['outfit_name']}",
        f"Clothing: {outfit.get('clothing_type', '')}",
        f"Colors: {outfit.get('colors', '')}",
        f"Material: {outfit.get('material', '')}",
        f"Accessories: {outfit.get('accessories', '')}",
        f"Footwear: {outfit.get('footwear', '')}",
        f"Description: {outfit.get('description', '')}",
        (
            "Continuity rules: "
            + outfit.get("continuity_rules", "")
        )
    ]

    if outfit.get("negative_prompt"):
        sections.append(
            "Avoid: " + outfit["negative_prompt"]
        )

    return "\n".join(
        section for section in sections
        if section.split(":", 1)[-1].strip()
    )


# ---------------------------------------------------------
# STREAMLIT UI
# ---------------------------------------------------------

def render() -> None:
    """Render the Outfit Consistency Manager page."""

    import streamlit as st

    st.title("Outfit Consistency Manager")
    st.caption(
        "Manage character clothing, reference images "
        "and scene-by-scene outfit continuity."
    )

    tab_create, tab_library, tab_scenes, tab_export = (
        st.tabs([
            "Create Outfit",
            "Outfit Library",
            "Scene Assignments",
            "Export"
        ])
    )

    # -----------------------------------------------------
    # CREATE
    # -----------------------------------------------------

    with tab_create:
        st.subheader("Create an Outfit Profile")

        with st.form("create_outfit_form"):

            character = st.text_input(
                "Character Name",
                placeholder="Example: Eira"
            )

            outfit_name = st.text_input(
                "Outfit Name",
                placeholder="Example: Winter Battle Outfit"
            )

            clothing_type = st.text_input(
                "Clothing Type",
                placeholder="Dark blue winter dress"
            )

            colors = st.text_input(
                "Colors",
                placeholder="Dark blue, charcoal, silver"
            )

            material = st.text_input(
                "Material",
                placeholder="Leather, wool, metal"
            )

            accessories = st.text_area(
                "Accessories",
                placeholder="Silver pendant, leather belt"
            )

            footwear = st.text_input(
                "Footwear",
                placeholder="Black leather boots"
            )

            description = st.text_area(
                "Full Outfit Description"
            )

            continuity_rules = st.text_area(
                "Continuity Rules",
                placeholder=(
                    "Keep the same colors, pendant, "
                    "sleeve design and cloak in every scene."
                )
            )

            negative_prompt = st.text_area(
                "Negative Prompt",
                placeholder=(
                    "No color changes, no missing accessories, "
                    "no different clothing design."
                )
            )

            tags_text = st.text_input(
                "Tags",
                placeholder="winter, battle, fantasy"
            )

            uploaded_image = st.file_uploader(
                "Upload Outfit Reference Image",
                type=["png", "jpg", "jpeg", "webp"],
                key="outfit_reference_upload"
            )

            submitted = st.form_submit_button(
                "Save Outfit",
                type="primary"
            )

            if submitted:
                try:
                    image_path = None

                    if uploaded_image:
                        temporary_dir = (
                            ASSET_DIR / "uploads"
                        )
                        temporary_dir.mkdir(
                            parents=True,
                            exist_ok=True
                        )

                        temporary_path = (
                            temporary_dir
                            / _safe_filename(
                                uploaded_image.name
                            )
                        )

                        temporary_path.write_bytes(
                            uploaded_image.getvalue()
                        )

                        image_path = str(temporary_path)

                    outfit = create_outfit(
                        character_name=character,
                        outfit_name=outfit_name,
                        clothing_type=clothing_type,
                        colors=colors,
                        material=material,
                        accessories=accessories,
                        footwear=footwear,
                        description=description,
                        continuity_rules=continuity_rules,
                        negative_prompt=negative_prompt,
                        tags=[
                            tag.strip()
                            for tag in tags_text.split(",")
                            if tag.strip()
                        ],
                        reference_image=image_path
                    )

                    st.success(
                        f"Outfit saved: {outfit['outfit_name']}"
                    )

                except Exception as exc:
                    st.error(f"Could not save outfit: {exc}")

    # -----------------------------------------------------
    # LIBRARY
    # -----------------------------------------------------

    with tab_library:
        st.subheader("Saved Outfit Profiles")

        search = st.text_input(
            "Search outfits",
            placeholder="Search character, color or clothing"
        )

        outfits = (
            search_outfits(search)
            if search
            else list_outfits()
        )

        stats = get_statistics()

        col1, col2, col3 = st.columns(3)

        col1.metric("Outfits", stats["total_outfits"])
        col2.metric("Characters", stats["total_characters"])
        col3.metric(
            "Scene Assignments",
            stats["total_assignments"]
        )

        if not outfits:
            st.info("No outfit profiles found.")

        for outfit in outfits:
            with st.expander(
                f"{outfit['character_name']} — "
                f"{outfit['outfit_name']}"
            ):
                st.write(
                    "**Clothing:**",
                    outfit.get("clothing_type", "-")
                )

                st.write(
                    "**Colors:**",
                    outfit.get("colors", "-")
                )

                st.write(
                    "**Material:**",
                    outfit.get("material", "-")
                )

                st.write(
                    "**Accessories:**",
                    outfit.get("accessories", "-")
                )

                st.write(
                    "**Footwear:**",
                    outfit.get("footwear", "-")
                )

                st.write(
                    "**Description:**",
                    outfit.get("description", "-")
                )

                st.write(
                    "**Continuity Rules:**",
                    outfit.get("continuity_rules", "-")
                )

                image_path = outfit.get("reference_image")

                if image_path and Path(image_path).is_file():
                    st.image(
                        image_path,
                        caption="Outfit Reference",
                        width=300
                    )

                prompt = build_outfit_prompt(outfit["id"])

                st.text_area(
                    "Generated Outfit Prompt",
                    value=prompt,
                    height=180,
                    key=f"prompt_{outfit['id']}"
                )

                st.download_button(
                    "Download Outfit Prompt",
                    data=prompt,
                    file_name=(
                        f"{outfit['outfit_name']}.txt"
                    ),
                    mime="text/plain",
                    key=f"download_{outfit['id']}"
                )

                with st.form(
                    f"edit_outfit_{outfit['id']}"
                ):
                    st.caption("Quick edit")

                    new_name = st.text_input(
                        "Outfit Name",
                        value=outfit["outfit_name"],
                        key=f"name_{outfit['id']}"
                    )

                    new_colors = st.text_input(
                        "Colors",
                        value=outfit.get("colors", ""),
                        key=f"colors_{outfit['id']}"
                    )

                    new_description = st.text_area(
                        "Description",
                        value=outfit.get("description", ""),
                        key=f"description_{outfit['id']}"
                    )

                    edit_submitted = st.form_submit_button(
                        "Update Outfit"
                    )

                    if edit_submitted:
                        try:
                            update_outfit(
                                outfit["id"],
                                outfit_name=new_name,
                                colors=new_colors,
                                description=new_description
                            )
                            st.success("Outfit updated.")
                            st.rerun()

                        except Exception as exc:
                            st.error(str(exc))

                col_a, col_b = st.columns(2)

                with col_a:
                    if st.button(
                        "Duplicate",
                        key=f"duplicate_{outfit['id']}"
                    ):
                        try:
                            duplicate_outfit(outfit["id"])
                            st.success("Outfit duplicated.")
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))

                with col_b:
                    if st.button(
                        "Delete",
                        key=f"delete_{outfit['id']}"
                    ):
                        st.session_state[
                            "confirm_delete_outfit"
                        ] = outfit["id"]

                if st.session_state.get(
                    "confirm_delete_outfit"
                ) == outfit["id"]:

                    st.warning(
                        "Are you sure you want to delete this outfit?"
                    )

                    if st.button(
                        "Confirm Delete",
                        key=f"confirm_{outfit['id']}"
                    ):
                        delete_outfit(outfit["id"])

                        st.session_state.pop(
                            "confirm_delete_outfit",
                            None
                        )

                        st.success("Outfit deleted.")
                        st.rerun()

    # -----------------------------------------------------
    # SCENE ASSIGNMENTS
    # -----------------------------------------------------

    with tab_scenes:
        st.subheader("Assign Outfits to Scenes")

        outfits = list_outfits()

        if not outfits:
            st.info(
                "Create an outfit profile before assigning scenes."
            )
        else:
            outfit_options = {
                (
                    f"{item['character_name']} — "
                    f"{item['outfit_name']}"
                ): item["id"]
                for item in outfits
            }

            with st.form("scene_assignment_form"):

                selected_label = st.selectbox(
                    "Select Outfit",
                    list(outfit_options.keys())
                )

                scene_name = st.text_input(
                    "Scene Name",
                    placeholder="Example: Frozen Castle Scene"
                )

                scene_number = st.text_input(
                    "Scene Number",
                    placeholder="Example: 01"
                )

                notes = st.text_area(
                    "Assignment Notes"
                )

                assign_submitted = st.form_submit_button(
                    "Assign Outfit"
                )

                if assign_submitted:
                    try:
                        assignment = assign_outfit_to_scene(
                            outfit_id=outfit_options[
                                selected_label
                            ],
                            scene_name=scene_name,
                            scene_number=scene_number,
                            notes=notes
                        )

                        st.success(
                            "Outfit assigned to scene: "
                            + assignment["scene_name"]
                        )

                    except Exception as exc:
                        st.error(str(exc))

        st.divider()
        st.subheader("Existing Scene Assignments")

        characters = get_statistics()["characters"]

        selected_character = st.selectbox(
            "Filter by Character",
            ["All Characters"] + characters
        )

        assignments = list_scene_assignments(
            None if selected_character == "All Characters"
            else selected_character
        )

        for assignment in assignments:
            with st.expander(
                f"Scene {assignment.get('scene_number') or '-'} "
                f"— {assignment['scene_name']}"
            ):
                st.write(
                    f"**Character:** "
                    f"{assignment['character_name']}"
                )

                st.write(
                    f"**Outfit:** {assignment['outfit_name']}"
                )

                st.write(
                    f"**Notes:** {assignment.get('notes', '-')}"
                )

                if st.button(
                    "Remove Assignment",
                    key=f"remove_assignment_{assignment['id']}"
                ):
                    remove_scene_assignment(
                        assignment["id"]
                    )
                    st.success("Assignment removed.")
                    st.rerun()

        st.divider()
        st.subheader("Continuity Check")

        if characters:
            check_character = st.selectbox(
                "Choose Character for Check",
                characters,
                key="continuity_character"
            )

            if st.button("Check Outfit Continuity"):
                result = check_scene_continuity(
                    check_character
                )

                st.write(
                    f"Scenes checked: {result['scene_count']}"
                )

                st.write(
                    f"Assignments: {result['assignment_count']}"
                )

                if result["consistent"]:
                    st.success(
                        "No conflicting outfit assignments found."
                    )
                else:
                    st.warning(
                        "Potential outfit assignment conflicts found."
                    )

                    for warning in result["warnings"]:
                        st.write(
                            f"- Scene {warning['scene']}: "
                            f"{warning['message']}"
                        )

                st.caption(
                    "This checks metadata assignments, not visual "
                    "similarity between images."
                )

    # -----------------------------------------------------
    # EXPORT
    # -----------------------------------------------------

    with tab_export:
        st.subheader("Export Outfit Data")

        st.write(
            "Export your outfit profiles for backups "
            "or use in other project modules."
        )

        if st.button("Generate JSON Export"):
            try:
                path = export_json()
                st.success(f"JSON exported: {path}")

                st.download_button(
                    "Download JSON",
                    data=path.read_bytes(),
                    file_name=path.name,
                    mime="application/json"
                )

            except Exception as exc:
                st.error(str(exc))

        if st.button("Generate CSV Export"):
            try:
                path = export_csv()
                st.success(f"CSV exported: {path}")

                st.download_button(
                    "Download CSV",
                    data=path.read_bytes(),
                    file_name=path.name,
                    mime="text/csv"
                )

            except Exception as exc:
                st.error(str(exc))


# ---------------------------------------------------------
# BUILT-IN TESTS
# ---------------------------------------------------------

def run_tests() -> None:
    print("Running Outfit Consistency Manager tests...")

    with tempfile.TemporaryDirectory() as temp:
        database = Path(temp) / "test_outfits.json"

        # Test outfit creation.
        outfit = create_outfit(
            character_name="Eira",
            outfit_name="Winter Outfit",
            clothing_type="Winter dress",
            colors="Blue and silver",
            material="Wool",
            accessories="Silver pendant",
            footwear="Leather boots",
            continuity_rules="Keep pendant visible.",
            database_path=database
        )

        assert outfit["character_name"] == "Eira"
        assert outfit["outfit_name"] == "Winter Outfit"

        # Test retrieval.
        found = get_outfit(
            outfit["id"],
            database
        )

        assert found is not None

        # Test update.
        update_outfit(
            outfit["id"],
            database_path=database,
            colors="Dark blue and silver"
        )

        updated = get_outfit(
            outfit["id"],
            database
        )

        assert updated["colors"] == "Dark blue and silver"

        # Test search.
        results = search_outfits(
            "Eira",
            database
        )

        assert len(results) == 1

        # Test duplication.
        duplicate = duplicate_outfit(
            outfit["id"],
            database
        )

        assert duplicate["id"] != outfit["id"]

        # Test scene assignment.
        assignment = assign_outfit_to_scene(
            outfit_id=outfit["id"],
            scene_name="Frozen Castle",
            scene_number="01",
            database_path=database
        )

        assert assignment["outfit_id"] == outfit["id"]

        assignments = list_scene_assignments(
            "Eira",
            database
        )

        assert len(assignments) == 1

        # Test continuity check.
        result = check_scene_continuity(
            "Eira",
            database
        )

        assert result["consistent"] is True

        # Test statistics.
        stats = get_statistics(database)

        assert stats["total_outfits"] == 2
        assert stats["total_assignments"] == 1

        # Test prompt creation.
        prompt = build_outfit_prompt(
            outfit["id"],
            database
        )

        assert "Eira" in prompt
        assert "Winter Outfit" in prompt

        # Test scene removal.
        assert remove_scene_assignment(
            assignment["id"],
            database
        ) is True

        assert len(
            list_scene_assignments(
                "Eira",
                database
            )
        ) == 0

        # Test deletion.
        assert delete_outfit(
            outfit["id"],
            database
        ) is True

        assert get_outfit(
            outfit["id"],
            database
        ) is None

        # Test exports.
        json_path = Path(temp) / "export.json"
        csv_path = Path(temp) / "export.csv"

        export_json(database, json_path)
        export_csv(database, csv_path)

        assert json_path.exists()
        assert csv_path.exists()

    print("All Outfit Consistency Manager tests passed.")


# ---------------------------------------------------------
# COMMAND LINE
# ---------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Outfit Consistency Manager"
    )

    parser.add_argument(
        "--test",
        action="store_true",
        help="Run built-in tests"
    )

    args = parser.parse_args()

    if args.test:
        run_tests()
    else:
        print("Outfit Consistency Manager")
        print("Run tests using: --test")
        print("Launch the UI through your Streamlit app.")
