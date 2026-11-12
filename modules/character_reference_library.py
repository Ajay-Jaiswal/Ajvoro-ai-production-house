
"""
File 57: modules/character_reference_library.py

Character Reference Library
- Organize reference images by character.
- Store image paths, descriptions, tags and reference types.
- Search and filter saved references.
- Import and export reference metadata.
- Uses only Python standard-library packages.
- Streamlit is imported only when render() is called.

Important:
This module organizes reference images. It does not train an AI
model or guarantee that generated images will preserve identity.
"""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
REFERENCE_DIR = ROOT_DIR / "assets" / "character_references"
EXPORT_DIR = ROOT_DIR / "outputs" / "character_references"
DATA_FILE = DATA_DIR / "character_references.json"

REFERENCE_TYPES = [
    "Face",
    "Full Body",
    "Side Profile",
    "Outfit",
    "Expression",
    "Pose",
    "Other",
]


class ReferenceLibraryError(Exception):
    """Base exception for this module."""


def _ensure_directories() -> None:
    for directory in (
        DATA_DIR,
        REFERENCE_DIR,
        EXPORT_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _read_data() -> list[dict[str, Any]]:
    _ensure_directories()

    if not DATA_FILE.exists():
        return []

    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError) as exc:
        raise ReferenceLibraryError(
            f"Could not read reference database: {exc}"
        ) from exc

    if not isinstance(data, list):
        raise ReferenceLibraryError(
            "Reference database must contain a JSON list."
        )

    return [
        item for item in data
        if isinstance(item, dict)
    ]


def _write_data(items: list[dict[str, Any]]) -> None:
    _ensure_directories()

    temporary_file = DATA_FILE.with_suffix(".tmp")

    try:
        with temporary_file.open("w", encoding="utf-8") as file:
            json.dump(
                items,
                file,
                indent=4,
                ensure_ascii=False,
            )

        temporary_file.replace(DATA_FILE)

    except OSError as exc:
        raise ReferenceLibraryError(
            f"Could not save reference database: {exc}"
        ) from exc


def list_references(
    character_name: str | None = None,
) -> list[dict[str, Any]]:
    """Return all references, optionally filtered by character."""

    items = _read_data()

    if character_name:
        target = character_name.strip().casefold()
        items = [
            item for item in items
            if item.get("character_name", "").casefold() == target
        ]

    return sorted(
        items,
        key=lambda item: item.get("created_at", ""),
        reverse=True,
    )


def add_reference(
    character_name: str,
    image_path: str,
    description: str = "",
    reference_type: str = "Face",
    tags: list[str] | None = None,
    copy_image: bool = True,
) -> dict[str, Any]:
    """Register an image as a character reference."""

    character_name = character_name.strip()
    source = Path(image_path).expanduser()

    if not character_name:
        raise ValueError("Character name is required.")

    if not source.exists() or not source.is_file():
        raise FileNotFoundError(
            f"Reference image not found: {source}"
        )

    allowed_types = REFERENCE_TYPES

    if reference_type not in allowed_types:
        raise ValueError(
            f"Reference type must be one of: {allowed_types}"
        )

    _ensure_directories()

    reference_id = uuid.uuid4().hex[:12]
    stored_path = source.resolve()

    if copy_image:
        safe_suffix = source.suffix.lower() or ".img"
        destination = (
            REFERENCE_DIR
            / f"{reference_id}{safe_suffix}"
        )

        try:
            shutil.copy2(source, destination)
        except OSError as exc:
            raise ReferenceLibraryError(
                f"Could not copy reference image: {exc}"
            ) from exc

        stored_path = destination

    clean_tags = []
    for tag in tags or []:
        value = str(tag).strip()
        if value and value.casefold() not in {
            existing.casefold() for existing in clean_tags
        }:
            clean_tags.append(value)

    item = {
        "id": reference_id,
        "character_name": character_name,
        "image_path": str(stored_path),
        "original_path": str(source.resolve()),
        "description": description.strip(),
        "reference_type": reference_type,
        "tags": clean_tags,
        "created_at": _now(),
    }

    items = _read_data()
    items.append(item)
    _write_data(items)

    return item


def update_reference(
    reference_id: str,
    description: str | None = None,
    reference_type: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Update reference metadata."""

    items = _read_data()

    for item in items:
        if item.get("id") != reference_id:
            continue

        if description is not None:
            item["description"] = description.strip()

        if reference_type is not None:
            if reference_type not in REFERENCE_TYPES:
                raise ValueError("Invalid reference type.")
            item["reference_type"] = reference_type

        if tags is not None:
            item["tags"] = list(dict.fromkeys(
                str(tag).strip()
                for tag in tags
                if str(tag).strip()
            ))

        item["updated_at"] = _now()
        _write_data(items)
        return item

    raise ReferenceLibraryError("Reference was not found.")


def delete_reference(
    reference_id: str,
    delete_image: bool = False,
) -> bool:
    """Delete reference metadata and optionally its copied image."""

    items = _read_data()
    target = next(
        (item for item in items if item.get("id") == reference_id),
        None,
    )

    if target is None:
        return False

    items = [
        item for item in items
        if item.get("id") != reference_id
    ]

    _write_data(items)

    if delete_image:
        image = Path(target.get("image_path", ""))

        # Only delete files inside this module's managed folder.
        try:
            resolved_image = image.resolve()
            managed_folder = REFERENCE_DIR.resolve()

            if (
                resolved_image.is_relative_to(managed_folder)
                and resolved_image.is_file()
            ):
                resolved_image.unlink()
        except (OSError, ValueError):
            pass

    return True


def search_references(
    query: str = "",
    reference_type: str = "All",
) -> list[dict[str, Any]]:
    """Search character names, descriptions and tags."""

    items = _read_data()
    query = query.strip().casefold()

    results = []

    for item in items:
        if (
            reference_type != "All"
            and item.get("reference_type") != reference_type
        ):
            continue

        searchable = " ".join([
            item.get("character_name", ""),
            item.get("description", ""),
            item.get("reference_type", ""),
            " ".join(item.get("tags", [])),
        ]).casefold()

        if query and query not in searchable:
            continue

        results.append(item)

    return results


def get_statistics() -> dict[str, int]:
    """Return simple library statistics."""

    items = _read_data()

    characters = {
        item.get("character_name", "")
        for item in items
        if item.get("character_name")
    }

    existing_images = sum(
        1 for item in items
        if Path(item.get("image_path", "")).is_file()
    )

    return {
        "total_references": len(items),
        "total_characters": len(characters),
        "existing_images": existing_images,
        "missing_images": len(items) - existing_images,
    }


def export_library() -> Path:
    """Export all reference metadata to a JSON file."""

    _ensure_directories()

    filename = (
        f"character_references_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    destination = EXPORT_DIR / filename

    payload = {
        "exported_at": _now(),
        "references": _read_data(),
    }

    with destination.open("w", encoding="utf-8") as file:
        json.dump(
            payload,
            file,
            indent=4,
            ensure_ascii=False,
        )

    return destination


def import_library(file_path: str) -> int:
    """Import metadata from a previously exported JSON file."""

    source = Path(file_path).expanduser()

    if not source.is_file():
        raise FileNotFoundError(source)

    with source.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    incoming = (
        payload.get("references", [])
        if isinstance(payload, dict)
        else payload
    )

    if not isinstance(incoming, list):
        raise ValueError("Invalid reference export format.")

    existing = _read_data()
    existing_ids = {
        item.get("id") for item in existing
    }

    imported = 0

    for raw_item in incoming:
        if not isinstance(raw_item, dict):
            continue

        character = str(
            raw_item.get("character_name", "")
        ).strip()

        image_path = str(
            raw_item.get("image_path", "")
        ).strip()

        if not character or not image_path:
            continue

        item = dict(raw_item)

        if not item.get("id") or item["id"] in existing_ids:
            item["id"] = uuid.uuid4().hex[:12]

        item["character_name"] = character
        item["tags"] = item.get("tags", [])
        item["created_at"] = item.get("created_at", _now())

        existing.append(item)
        existing_ids.add(item["id"])
        imported += 1

    _write_data(existing)
    return imported


def render() -> None:
    """Render the Streamlit page. Streamlit is optional until this runs."""

    try:
        import streamlit as st
    except ImportError:
        raise RuntimeError(
            "This module's interface requires Streamlit. "
            "Install it using: pip install streamlit"
        )

    st.title("Character Reference Library")
    st.caption(
        "Organize reference images for your AI characters."
    )

    try:
        stats = get_statistics()

        col1, col2, col3 = st.columns(3)
        col1.metric("References", stats["total_references"])
        col2.metric("Characters", stats["total_characters"])
        col3.metric("Existing images", stats["existing_images"])

        tab_add, tab_library, tab_export = st.tabs([
            "Add Reference",
            "Reference Library",
            "Import / Export",
        ])

        with tab_add:
            st.subheader("Add a character reference")

            character_name = st.text_input(
                "Character name",
                key="reference_character_name",
            )

            uploaded_file = st.file_uploader(
                "Upload reference image",
                type=["png", "jpg", "jpeg", "webp"],
                key="reference_upload",
            )

            description = st.text_area(
                "Description",
                placeholder="Example: Front-facing face reference, neutral expression.",
            )

            reference_type = st.selectbox(
                "Reference type",
                REFERENCE_TYPES,
            )

            tags_text = st.text_input(
                "Tags",
                placeholder="face, hairstyle, costume",
            )

            if st.button(
                "Save Reference",
                type="primary",
            ):
                if not character_name.strip():
                    st.error("Enter a character name.")
                elif uploaded_file is None:
                    st.error("Upload an image first.")
                else:
                    suffix = Path(
                        uploaded_file.name
                    ).suffix.lower() or ".png"

                    temporary_path = (
                        REFERENCE_DIR
                        / f"upload_{uuid.uuid4().hex}{suffix}"
                    )

                    try:
                        _ensure_directories()
                        temporary_path.write_bytes(
                            uploaded_file.getvalue()
                        )

                        item = add_reference(
                            character_name=character_name,
                            image_path=str(temporary_path),
                            description=description,
                            reference_type=reference_type,
                            tags=[
                                tag.strip()
                                for tag in tags_text.split(",")
                                if tag.strip()
                            ],
                            copy_image=True,
                        )

                        st.success(
                            f"Reference saved for "
                            f"{item['character_name']}."
                        )
                        st.rerun()

                    except Exception as exc:
                        st.error(f"Could not save reference: {exc}")

                    finally:
                        try:
                            temporary_path.unlink(missing_ok=True)
                        except OSError:
                            pass

        with tab_library:
            st.subheader("Saved references")

            query = st.text_input(
                "Search references",
                key="reference_search",
            )

            selected_type = st.selectbox(
                "Filter by type",
                ["All"] + REFERENCE_TYPES,
                key="reference_type_filter",
            )

            results = search_references(
                query,
                selected_type,
            )

            if not results:
                st.info("No references found.")
            else:
                for item in results:
                    with st.container(border=True):
                        st.markdown(
                            f"**{item.get('character_name', 'Unnamed')}**"
                        )
                        st.caption(
                            f"{item.get('reference_type', 'Other')} "
                            f"· ID: {item.get('id', '')}"
                        )

                        image_path = Path(
                            item.get("image_path", "")
                        )

                        if image_path.is_file():
                            st.image(
                                str(image_path),
                                width=220,
                            )
                        else:
                            st.warning(
                                "Image file is missing. "
                                "The metadata is still available."
                            )

                        st.write(
                            item.get("description") or "No description."
                        )

                        tags = item.get("tags", [])
                        if tags:
                            st.caption("Tags: " + ", ".join(tags))

                        with st.expander("Edit or delete"):
                            new_description = st.text_area(
                                "Description",
                                value=item.get("description", ""),
                                key=f"desc_{item['id']}",
                            )

                            current_type = item.get(
                                "reference_type",
                                "Face",
                            )

                            new_type = st.selectbox(
                                "Reference type",
                                REFERENCE_TYPES,
                                index=(
                                    REFERENCE_TYPES.index(current_type)
                                    if current_type in REFERENCE_TYPES
                                    else 0
                                ),
                                key=f"type_{item['id']}",
                            )

                            new_tags = st.text_input(
                                "Tags",
                                value=", ".join(tags),
                                key=f"tags_{item['id']}",
                            )

                            if st.button(
                                "Update",
                                key=f"update_{item['id']}",
                            ):
                                update_reference(
                                    item["id"],
                                    description=new_description,
                                    reference_type=new_type,
                                    tags=[
                                        tag.strip()
                                        for tag in new_tags.split(",")
                                        if tag.strip()
                                    ],
                                )
                                st.success("Reference updated.")
                                st.rerun()

                            if st.button(
                                "Delete reference",
                                key=f"delete_{item['id']}",
                            ):
                                delete_reference(
                                    item["id"],
                                    delete_image=True,
                                )
                                st.success("Reference deleted.")
                                st.rerun()

        with tab_export:
            st.subheader("Import and export")

            if st.button("Export reference library"):
                export_path = export_library()

                st.success("Export created.")
                st.download_button(
                    "Download JSON",
                    data=export_path.read_bytes(),
                    file_name=export_path.name,
                    mime="application/json",
                )

            import_file = st.file_uploader(
                "Import a reference JSON export",
                type=["json"],
                key="reference_import",
            )

            if st.button("Import references"):
                if import_file is None:
                    st.warning("Choose a JSON file first.")
                else:
                    temporary_import = (
                        EXPORT_DIR
                        / f"import_{uuid.uuid4().hex}.json"
                    )

                    try:
                        _ensure_directories()
                        temporary_import.write_bytes(
                            import_file.getvalue()
                        )

                        count = import_library(
                            str(temporary_import)
                        )

                        st.success(
                            f"Imported {count} reference records."
                        )
                        st.rerun()

                    except Exception as exc:
                        st.error(f"Import failed: {exc}")

                    finally:
                        temporary_import.unlink(missing_ok=True)

    except Exception as exc:
        st.error(
            "Character Reference Library encountered an error."
        )
        st.exception(exc)


def run_tests() -> None:
    """Run basic built-in tests using a temporary data location."""

    import tempfile

    global DATA_DIR
    global REFERENCE_DIR
    global EXPORT_DIR
    global DATA_FILE

    old_values = (
        DATA_DIR,
        REFERENCE_DIR,
        EXPORT_DIR,
        DATA_FILE,
    )

    try:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)

            DATA_DIR = base / "data"
            REFERENCE_DIR = base / "references"
            EXPORT_DIR = base / "exports"
            DATA_FILE = DATA_DIR / "character_references.json"

            _ensure_directories()

            sample_image = base / "sample.png"
            sample_image.write_bytes(b"test-image-data")

            item = add_reference(
                character_name="Test Character",
                image_path=str(sample_image),
                description="Test face reference",
                reference_type="Face",
                tags=["face", "test"],
            )

            assert item["character_name"] == "Test Character"
            assert len(list_references()) == 1
            assert len(list_references("Test Character")) == 1
            assert len(search_references("test")) == 1

            updated = update_reference(
                item["id"],
                description="Updated description",
                reference_type="Outfit",
            )
            assert updated["description"] == "Updated description"
            assert updated["reference_type"] == "Outfit"

            stats = get_statistics()
            assert stats["total_references"] == 1
            assert stats["total_characters"] == 1

            exported = export_library()
            assert exported.exists()

            assert delete_reference(
                item["id"],
                delete_image=True,
            )
            assert len(list_references()) == 0

            print("All Character Reference Library tests passed.")

    finally:
        (
            DATA_DIR,
            REFERENCE_DIR,
            EXPORT_DIR,
            DATA_FILE,
        ) = old_values


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Character Reference Library"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run built-in tests",
    )

    args = parser.parse_args()

    if args.test:
        run_tests()
    else:
        print("Character Reference Library module")
        print("Run with --test to execute built-in tests.")
