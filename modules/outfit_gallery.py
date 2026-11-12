
"""
AI Influencer Studio
File 31: modules/outfit_gallery.py

Purpose:
- Store reference images for saved outfits.
- Link gallery images to outfits and characters.
- Display and manage outfit reference images in Streamlit.
- Keep all files on the local machine.

This module manages reference images only. It does not generate AI images.
"""

from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------
# PATHS AND CONFIGURATION
# ---------------------------------------------------------

try:
    from modules import outfit_manager
except ImportError:
    outfit_manager = None

try:
    from modules import character_consistency
except ImportError:
    character_consistency = None


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
GALLERY_DIR = PROJECT_ROOT / "assets" / "outfit_references"

DATABASE_FILE = DATA_DIR / "outfit_gallery.json"

ALLOWED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}

MAX_IMAGE_SIZE_MB = 15
MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024


# ---------------------------------------------------------
# GENERAL HELPERS
# ---------------------------------------------------------

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_id(value: str) -> str:
    """Convert an ID into a safe folder/file identifier."""
    value = str(value or "").strip()

    if not value:
        raise ValueError("An ID is required.")

    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "_", value)

    if cleaned in {".", ".."}:
        raise ValueError("Invalid ID.")

    return cleaned[:100]


def _safe_filename(filename: str) -> str:
    """Remove unsafe characters from an uploaded filename."""
    name = Path(str(filename or "image")).name
    suffix = Path(name).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(
            "Unsupported image format. Use PNG, JPG, JPEG or WEBP."
        )

    stem = Path(name).stem
    stem = re.sub(r"[^a-zA-Z0-9_-]", "_", stem)
    stem = stem.strip("_") or "reference"

    return f"{stem[:60]}{suffix}"


def _inside_directory(path: Path, root: Path) -> bool:
    """Check that a resolved path stays inside its managed root."""
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def _ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    GALLERY_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# DATABASE
# ---------------------------------------------------------

def load_database(path: Path | str | None = None) -> dict:
    """Load the outfit gallery JSON database."""
    database_path = Path(path) if path else DATABASE_FILE

    if not database_path.exists():
        return {
            "version": 1,
            "updated_at": _now(),
            "outfits": {},
        }

    try:
        with database_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            raise ValueError("Gallery database must be a JSON object.")

        if not isinstance(data.get("outfits"), dict):
            data["outfits"] = {}

        data.setdefault("version", 1)
        data.setdefault("updated_at", _now())

        return data

    except (json.JSONDecodeError, OSError):
        # Do not silently overwrite a damaged database.
        raise RuntimeError(
            f"Could not read gallery database: {database_path}"
        )


def save_database(
    database: dict,
    path: Path | str | None = None,
) -> None:
    """Save gallery data using an atomic temporary file."""
    database_path = Path(path) if path else DATABASE_FILE

    database_path.parent.mkdir(parents=True, exist_ok=True)

    database["version"] = 1
    database["updated_at"] = _now()

    temporary_path = database_path.with_name(
        database_path.name + ".tmp"
    )

    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(database, file, indent=4, ensure_ascii=False)

    temporary_path.replace(database_path)


# ---------------------------------------------------------
# OUTFIT AND CHARACTER VALIDATION
# ---------------------------------------------------------

def _get_outfit(outfit_id: str) -> dict | None:
    if outfit_manager is None:
        raise RuntimeError(
            "outfit_manager.py is not available."
        )

    return outfit_manager.get_outfit(outfit_id)


def _get_character(character_id: str) -> dict | None:
    if not character_id:
        return None

    if character_consistency is None:
        return None

    return character_consistency.get_character(character_id)


def _validate_outfit(outfit_id: str) -> dict:
    outfit_id = str(outfit_id).strip()

    if not outfit_id:
        raise ValueError("Outfit ID is required.")

    outfit = _get_outfit(outfit_id)

    if not outfit:
        raise ValueError(
            f"Outfit '{outfit_id}' was not found."
        )

    return outfit


# ---------------------------------------------------------
# IMAGE STORAGE
# ---------------------------------------------------------

def add_reference_image(
    outfit_id: str,
    image_bytes: bytes,
    filename: str,
    description: str = "",
    path: Path | str | None = None,
    asset_root: Path | str | None = None,
    validate_outfit: bool = True,
) -> dict:
    """
    Save an uploaded image for an outfit.

    image_bytes:
        Raw bytes from Streamlit file_uploader or another source.

    filename:
        Original uploaded filename.

    path:
        Optional database path, useful for testing.

    asset_root:
        Optional gallery folder, useful for testing.
    """

    outfit_id = str(outfit_id).strip()

    if not outfit_id:
        raise ValueError("Outfit ID is required.")

    if validate_outfit:
        outfit = _validate_outfit(outfit_id)
    else:
        outfit = {}

    if not isinstance(image_bytes, bytes) or not image_bytes:
        raise ValueError("The uploaded image is empty or invalid.")

    if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
        raise ValueError(
            f"Image exceeds the {MAX_IMAGE_SIZE_MB} MB limit."
        )

    safe_name = _safe_filename(filename)

    database_path = Path(path) if path else DATABASE_FILE
    gallery_root = Path(asset_root) if asset_root else GALLERY_DIR

    safe_outfit_id = _safe_id(outfit_id)

    outfit_folder = gallery_root / safe_outfit_id
    outfit_folder.mkdir(parents=True, exist_ok=True)

    if not _inside_directory(outfit_folder, gallery_root):
        raise ValueError("Invalid gallery folder.")

    image_id = uuid.uuid4().hex[:12]
    extension = Path(safe_name).suffix
    stored_name = f"{image_id}{extension}"

    destination = outfit_folder / stored_name

    if not _inside_directory(destination, gallery_root):
        raise ValueError("Invalid image destination.")

    # Save image bytes.
    with destination.open("xb") as file:
        file.write(image_bytes)

    character_id = (
        outfit.get("character_id", "")
        if isinstance(outfit, dict)
        else ""
    )

    record = {
        "id": image_id,
        "outfit_id": outfit_id,
        "character_id": character_id,
        "filename": safe_name,
        "stored_filename": stored_name,
        "relative_path": str(
            destination.relative_to(gallery_root)
        ),
        "description": str(description or "").strip()[:500],
        "size_bytes": len(image_bytes),
        "created_at": _now(),
    }

    try:
        database = load_database(database_path)

        outfit_records = database["outfits"].setdefault(
            outfit_id, []
        )

        outfit_records.append(record)

        save_database(database, database_path)

    except Exception:
        # Remove the newly saved image if database registration fails.
        try:
            destination.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    return record


def list_references(
    outfit_id: str,
    path: Path | str | None = None,
) -> list[dict]:
    """Return all registered images for an outfit."""
    database = load_database(path)

    records = database["outfits"].get(
        str(outfit_id), []
    )

    return [
        record.copy()
        for record in records
        if isinstance(record, dict)
    ]


def get_reference_image_path(
    record: dict,
    asset_root: Path | str | None = None,
) -> Path | None:
    """Resolve a registered image path safely."""
    gallery_root = Path(asset_root) if asset_root else GALLERY_DIR

    relative_path = record.get("relative_path")

    if not relative_path:
        return None

    image_path = gallery_root / relative_path

    if not _inside_directory(image_path, gallery_root):
        return None

    if not image_path.is_file():
        return None

    if image_path.suffix.lower() not in ALLOWED_EXTENSIONS:
        return None

    return image_path


def delete_reference(
    outfit_id: str,
    image_id: str,
    path: Path | str | None = None,
    asset_root: Path | str | None = None,
) -> bool:
    """
    Delete one registered reference image.

    Only files registered in this gallery database can be deleted.
    """
    database_path = Path(path) if path else DATABASE_FILE
    gallery_root = Path(asset_root) if asset_root else GALLERY_DIR

    database = load_database(database_path)

    records = database["outfits"].get(str(outfit_id), [])

    target = next(
        (
            item for item in records
            if item.get("id") == image_id
        ),
        None,
    )

    if target is None:
        return False

    image_path = get_reference_image_path(
        target,
        asset_root=gallery_root,
    )

    # Remove the database record even if the file is already missing.
    database["outfits"][str(outfit_id)] = [
        item for item in records
        if item.get("id") != image_id
    ]

    if not database["outfits"][str(outfit_id)]:
        database["outfits"].pop(str(outfit_id), None)

    save_database(database, database_path)

    if image_path:
        try:
            image_path.unlink(missing_ok=True)
        except OSError:
            # Database record is removed; report failure to clean file.
            return False

    return True


# ---------------------------------------------------------
# GALLERY SEARCH AND STATISTICS
# ---------------------------------------------------------

def list_gallery_items(
    search: str = "",
    character_id: str = "",
    outfit_id: str = "",
    path: Path | str | None = None,
) -> list[dict]:
    """Return gallery records with optional filters."""
    database = load_database(path)

    search_text = str(search or "").strip().lower()
    results = []

    for current_outfit_id, records in database["outfits"].items():
        if outfit_id and current_outfit_id != outfit_id:
            continue

        for record in records:
            if not isinstance(record, dict):
                continue

            if (
                character_id
                and record.get("character_id") != character_id
            ):
                continue

            searchable = " ".join([
                str(record.get("filename", "")),
                str(record.get("description", "")),
                str(record.get("outfit_id", "")),
                str(record.get("character_id", "")),
            ]).lower()

            if search_text and search_text not in searchable:
                continue

            results.append(record.copy())

    results.sort(
        key=lambda item: item.get("created_at", ""),
        reverse=True,
    )

    return results


def get_statistics(
    path: Path | str | None = None,
    asset_root: Path | str | None = None,
) -> dict:
    """Return gallery storage statistics."""
    records = list_gallery_items(path=path)

    total_bytes = sum(
        int(record.get("size_bytes", 0) or 0)
        for record in records
    )

    outfits = {
        record.get("outfit_id")
        for record in records
        if record.get("outfit_id")
    }

    characters = {
        record.get("character_id")
        for record in records
        if record.get("character_id")
    }

    existing_files = sum(
        1
        for record in records
        if get_reference_image_path(
            record,
            asset_root=asset_root,
        )
    )

    return {
        "total_images": len(records),
        "existing_files": existing_files,
        "missing_files": len(records) - existing_files,
        "total_outfits": len(outfits),
        "total_characters": len(characters),
        "total_size_bytes": total_bytes,
        "total_size_mb": round(
            total_bytes / (1024 * 1024), 2
        ),
    }


# ---------------------------------------------------------
# STREAMLIT USER INTERFACE
# ---------------------------------------------------------

def render(st: Any) -> None:
    """Render the Outfit Reference Gallery page."""
    _ensure_directories()

    st.title("Outfit Reference Gallery")
    st.caption(
        "Organize local reference images for your saved AI influencer outfits."
    )

    if outfit_manager is None:
        st.error("outfit_manager.py could not be loaded.")
        return

    try:
        outfits = outfit_manager.list_outfits()
    except Exception as exc:
        st.error(f"Unable to load outfits: {exc}")
        return

    if not outfits:
        st.info(
            "No outfits found. Create an outfit in Outfit Studio first."
        )
        return

    # Build outfit selection labels.
    outfit_options = {}

    for outfit in outfits:
        outfit_id = str(outfit.get("id", ""))

        if not outfit_id:
            continue

        label = outfit.get("name", "Unnamed Outfit")
        outfit_options[f"{label} ({outfit_id[:8]})"] = outfit_id

    if not outfit_options:
        st.warning("No valid outfit records were found.")
        return

    tab_upload, tab_gallery, tab_stats = st.tabs([
        "Upload References",
        "Browse Gallery",
        "Statistics",
    ])

    # -----------------------------------------------------
    # UPLOAD TAB
    # -----------------------------------------------------

    with tab_upload:
        st.subheader("Add outfit reference images")

        selected_label = st.selectbox(
            "Select outfit",
            list(outfit_options.keys()),
            key="outfit_gallery_upload_select",
        )

        selected_outfit_id = outfit_options[selected_label]

        selected_outfit = next(
            (
                item for item in outfits
                if str(item.get("id")) == selected_outfit_id
            ),
            {},
        )

        character_id = selected_outfit.get("character_id", "")

        if character_id:
            st.caption(f"Character ID: {character_id}")

        uploaded_files = st.file_uploader(
            "Upload reference images",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            key="outfit_gallery_upload",
        )

        description = st.text_input(
            "Image description (optional)",
            placeholder="Example: Front view, winter outfit",
        )

        if st.button(
            "Save Reference Images",
            type="primary",
            key="outfit_gallery_save",
        ):
            if not uploaded_files:
                st.warning("Select at least one image.")
            else:
                success_count = 0
                errors = []

                for uploaded in uploaded_files:
                    try:
                        add_reference_image(
                            outfit_id=selected_outfit_id,
                            image_bytes=uploaded.getvalue(),
                            filename=uploaded.name,
                            description=description,
                        )
                        success_count += 1

                    except Exception as exc:
                        errors.append(
                            f"{uploaded.name}: {exc}"
                        )

                if success_count:
                    st.success(
                        f"Saved {success_count} reference image(s)."
                    )

                for error in errors:
                    st.error(error)

    # -----------------------------------------------------
    # GALLERY TAB
    # -----------------------------------------------------

    with tab_gallery:
        st.subheader("Browse outfit references")

        search_text = st.text_input(
            "Search images",
            placeholder="Search filename, outfit ID or description",
            key="outfit_gallery_search",
        )

        filter_label = st.selectbox(
            "Filter by outfit",
            ["All outfits"] + list(outfit_options.keys()),
            key="outfit_gallery_filter",
        )

        filter_outfit_id = (
            ""
            if filter_label == "All outfits"
            else outfit_options[filter_label]
        )

        records = list_gallery_items(
            search=search_text,
            outfit_id=filter_outfit_id,
        )

        if not records:
            st.info("No reference images found.")
        else:
            st.caption(f"{len(records)} image(s) found.")

            columns = st.columns(3)

            for index, record in enumerate(records):
                image_path = get_reference_image_path(record)

                with columns[index % 3]:
                    if image_path:
                        st.image(
                            str(image_path),
                            use_container_width=True,
                        )
                    else:
                        st.warning("Image file is missing.")

                    st.write(
                        f"**{record.get('filename', 'Reference')}**"
                    )

                    st.caption(
                        f"Outfit: {record.get('outfit_id', '')}"
                    )

                    if record.get("description"):
                        st.caption(record["description"])

                    size_mb = (
                        int(record.get("size_bytes", 0))
                        / (1024 * 1024)
                    )

                    st.caption(f"{size_mb:.2f} MB")

                    confirm_key = (
                        f"delete_confirm_{record.get('id')}"
                    )

                    confirmed = st.checkbox(
                        "Confirm deletion",
                        key=confirm_key,
                    )

                    if st.button(
                        "Delete image",
                        key=f"delete_{record.get('id')}",
                        disabled=not confirmed,
                    ):
                        deleted = delete_reference(
                            outfit_id=record.get("outfit_id", ""),
                            image_id=record.get("id", ""),
                        )

                        if deleted:
                            st.success("Reference image deleted.")
                            st.rerun()
                        else:
                            st.error(
                                "Could not fully delete the image."
                            )

    # -----------------------------------------------------
    # STATISTICS TAB
    # -----------------------------------------------------

    with tab_stats:
        st.subheader("Gallery overview")

        stats = get_statistics()

        col1, col2, col3 = st.columns(3)

        col1.metric("Total Images", stats["total_images"])
        col2.metric("Outfits", stats["total_outfits"])
        col3.metric("Characters", stats["total_characters"])

        col4, col5, col6 = st.columns(3)

        col4.metric("Storage Used", f"{stats['total_size_mb']} MB")
        col5.metric("Existing Files", stats["existing_files"])
        col6.metric("Missing Files", stats["missing_files"])

        st.caption(
            "All reference images are stored locally in "
            "assets/outfit_references/."
        )


# ---------------------------------------------------------
# BUILT-IN TESTS
# ---------------------------------------------------------

def run_tests() -> bool:
    """Run isolated tests using temporary folders."""
    import tempfile
    import unittest
    from unittest.mock import patch

    class OutfitGalleryTests(unittest.TestCase):

        def setUp(self):
            self.temp_dir = tempfile.TemporaryDirectory()
            self.root = Path(self.temp_dir.name)

            self.database_path = self.root / "gallery.json"
            self.asset_root = self.root / "outfit_references"

            self.asset_root.mkdir(parents=True)

        def tearDown(self):
            self.temp_dir.cleanup()

        def test_database_initialization(self):
            data = load_database(self.database_path)

            self.assertIn("outfits", data)
            self.assertEqual(data["outfits"], {})

        def test_save_and_load_database(self):
            data = {
                "version": 1,
                "updated_at": _now(),
                "outfits": {
                    "outfit_1": [],
                },
            }

            save_database(data, self.database_path)
            loaded = load_database(self.database_path)

            self.assertIn("outfit_1", loaded["outfits"])

        def test_safe_filename(self):
            result = _safe_filename("winter look.jpg")

            self.assertTrue(result.endswith(".jpg"))
            self.assertNotIn(" ", result)

        def test_reject_unsupported_extension(self):
            with self.assertRaises(ValueError):
                _safe_filename("malicious.exe")

        def test_reject_empty_image(self):
            with self.assertRaises(ValueError):
                add_reference_image(
                    "outfit_1",
                    b"",
                    "image.png",
                    path=self.database_path,
                    asset_root=self.asset_root,
                    validate_outfit=False,
                )

        def test_add_and_list_reference(self):
            record = add_reference_image(
                outfit_id="outfit_1",
                image_bytes=b"fake-image-data",
                filename="front.png",
                description="Front view",
                path=self.database_path,
                asset_root=self.asset_root,
                validate_outfit=False,
            )

            records = list_references(
                "outfit_1",
                path=self.database_path,
            )

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["id"], record["id"])

        def test_image_path_resolution(self):
            record = add_reference_image(
                outfit_id="outfit_1",
                image_bytes=b"fake-image-data",
                filename="front.png",
                path=self.database_path,
                asset_root=self.asset_root,
                validate_outfit=False,
            )

            image_path = get_reference_image_path(
                record,
                asset_root=self.asset_root,
            )

            self.assertIsNotNone(image_path)
            self.assertTrue(image_path.exists())

        def test_delete_reference(self):
            record = add_reference_image(
                outfit_id="outfit_1",
                image_bytes=b"fake-image-data",
                filename="front.png",
                path=self.database_path,
                asset_root=self.asset_root,
                validate_outfit=False,
            )

            result = delete_reference(
                "outfit_1",
                record["id"],
                path=self.database_path,
                asset_root=self.asset_root,
            )

            self.assertTrue(result)
            self.assertEqual(
                list_references(
                    "outfit_1",
                    path=self.database_path,
                ),
                [],
            )

        def test_search_gallery(self):
            add_reference_image(
                outfit_id="outfit_1",
                image_bytes=b"fake-image-data",
                filename="winter_front.png",
                description="Winter clothing",
                path=self.database_path,
                asset_root=self.asset_root,
                validate_outfit=False,
            )

            results = list_gallery_items(
                search="winter",
                path=self.database_path,
            )

            self.assertEqual(len(results), 1)

        def test_statistics(self):
            add_reference_image(
                outfit_id="outfit_1",
                image_bytes=b"fake-image-data",
                filename="front.png",
                path=self.database_path,
                asset_root=self.asset_root,
                validate_outfit=False,
            )

            stats = get_statistics(
                path=self.database_path,
                asset_root=self.asset_root,
            )

            self.assertEqual(stats["total_images"], 1)
            self.assertEqual(stats["existing_files"], 1)
            self.assertEqual(stats["total_outfits"], 1)

        def test_outfit_validation(self):
            with patch(
                __name__ + "._get_outfit",
                return_value=None,
            ):
                with self.assertRaises(ValueError):
                    _validate_outfit("missing_outfit")

        def test_missing_image_file(self):
            record = {
                "relative_path": "outfit_1/missing.png",
            }

            result = get_reference_image_path(
                record,
                asset_root=self.asset_root,
            )

            self.assertIsNone(result)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        OutfitGalleryTests
    )

    result = unittest.TextTestRunner(verbosity=2).run(suite)

    return result.wasSuccessful()


# ---------------------------------------------------------
# COMMAND LINE TEST RUNNER
# ---------------------------------------------------------

if __name__ == "__main__":
    import sys

    if "--test" in sys.argv:
        success = run_tests()
        raise SystemExit(0 if success else 1)

    print("Outfit Reference Gallery module")
    print("Run tests with:")
    print("python -m modules.outfit_gallery --test")
