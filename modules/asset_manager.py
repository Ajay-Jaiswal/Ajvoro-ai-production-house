
"""
AI Influencer Studio
File 25: modules/asset_manager.py

Centralized asset library.

Features:
- Browse images, videos, audio and documents
- Search and filtering
- Persistent asset metadata and tags
- Image previews
- Upload assets
- Safe delete and move operations
- Storage statistics
- Streamlit dashboard
- Built-in tests

Run tests:
    python -m modules.asset_manager --test

Integration:
    from modules import asset_manager
    asset_manager.render(st)
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import shutil
import tempfile
import uuid

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"
}

VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".avi", ".mkv", ".webm"
}

AUDIO_EXTENSIONS = {
    ".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac"
}

DOCUMENT_EXTENSIONS = {
    ".pdf", ".txt", ".md", ".json", ".csv", ".docx", ".xlsx"
}

MAX_UPLOAD_MB = 500


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _configured_folder(setting_key: str, default: str) -> Path:
    """Read a relative folder from settings where available."""
    try:
        from modules.settings_manager import get_setting

        value = get_setting(setting_key, default)

        if isinstance(value, str) and value.strip():
            candidate = Path(value)
            if not candidate.is_absolute():
                return project_root() / candidate

    except Exception:
        pass

    return project_root() / default


def get_managed_roots() -> dict[str, Path]:
    """
    Return the folders managed by this module.

    These folders can be configured in settings_manager.py.
    """
    return {
        "assets": _configured_folder(
            "storage.assets_folder", "assets"
        ),
        "outputs": _configured_folder(
            "storage.outputs_folder", "outputs"
        ),
        "projects": _configured_folder(
            "storage.projects_folder", "projects"
        ),
    }


def ensure_directories() -> None:
    for folder in get_managed_roots().values():
        folder.mkdir(parents=True, exist_ok=True)


def classify_file(path: Path) -> str:
    extension = path.suffix.lower()

    if extension in IMAGE_EXTENSIONS:
        return "image"

    if extension in VIDEO_EXTENSIONS:
        return "video"

    if extension in AUDIO_EXTENSIONS:
        return "audio"

    if extension in DOCUMENT_EXTENSIONS:
        return "document"

    return "other"


def format_size(size: int) -> str:
    value = float(size)

    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.2f} {unit}"
        value /= 1024

    return f"{value:.2f} TB"


def _safe_filename(filename: str) -> str:
    """Remove unsafe characters and directory components."""
    name = Path(str(filename)).name
    name = re.sub(r"[^a-zA-Z0-9._ -]", "_", name)
    name = name.strip(" .")

    if not name:
        name = f"asset_{uuid.uuid4().hex[:8]}"

    return name[:180]


def _is_inside(path: Path, root: Path) -> bool:
    """Check whether a resolved path is inside a managed root."""
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def _validate_managed_file(path: str | Path) -> Path:
    """
    Resolve and validate a file inside a managed directory.

    Symlinks escaping the managed root are rejected.
    """
    candidate = Path(path).resolve(strict=True)

    for root in get_managed_roots().values():
        if _is_inside(candidate, root):
            if not candidate.is_file():
                raise ValueError("The selected path is not a file.")
            return candidate

    raise ValueError("File is outside the managed asset folders.")


def _metadata_path(asset_path: Path) -> Path:
    return asset_path.with_name(
        asset_path.name + ".asset.json"
    )


def load_metadata(asset_path: str | Path) -> dict:
    """Load an asset's sidecar metadata."""
    path = _validate_managed_file(asset_path)
    sidecar = _metadata_path(path)

    if not sidecar.exists():
        return {
            "description": "",
            "tags": [],
            "created_at": "",
        }

    try:
        with sidecar.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            return {
                "description": "",
                "tags": [],
                "created_at": "",
            }

        tags = data.get("tags", [])

        if not isinstance(tags, list):
            tags = []

        return {
            "description": str(data.get("description", "")),
            "tags": [
                str(tag)[:50] for tag in tags[:50]
                if isinstance(tag, str)
            ],
            "created_at": str(data.get("created_at", "")),
        }

    except (OSError, json.JSONDecodeError):
        return {
            "description": "",
            "tags": [],
            "created_at": "",
        }


def save_metadata(
    asset_path: str | Path,
    description: str = "",
    tags: list[str] | None = None,
) -> tuple[bool, str]:
    """Save description and tags beside an asset."""
    try:
        path = _validate_managed_file(asset_path)

        if not isinstance(description, str):
            return False, "Description must be text."

        if tags is None:
            tags = []

        if not isinstance(tags, list):
            return False, "Tags must be a list."

        clean_tags = []

        for tag in tags:
            if not isinstance(tag, str):
                continue

            clean = tag.strip().lower()[:50]

            if clean and clean not in clean_tags:
                clean_tags.append(clean)

        sidecar = _metadata_path(path)

        existing = load_metadata(path)

        data = {
            "description": description.strip()[:2000],
            "tags": clean_tags[:50],
            "created_at": (
                existing.get("created_at")
                or datetime.now(timezone.utc).isoformat()
            ),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        sidecar.parent.mkdir(parents=True, exist_ok=True)

        fd, temp_name = tempfile.mkstemp(
            prefix="asset_metadata_",
            suffix=".tmp",
            dir=str(sidecar.parent),
        )

        temp_path = Path(temp_name)

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=4, ensure_ascii=False)
                file.flush()
                os.fsync(file.fileno())

            os.replace(temp_path, sidecar)

        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)

        return True, "Metadata saved."

    except (OSError, ValueError) as exc:
        return False, str(exc)


def list_assets(
    category: str = "all",
    search: str = "",
    folder: str = "all",
) -> list[dict]:
    """Scan managed folders and return matching assets."""
    results = []
    search = search.strip().lower()

    roots = get_managed_roots()

    for root_name, root in roots.items():
        if folder != "all" and folder != root_name:
            continue

        if not root.exists():
            continue

        for path in root.rglob("*"):
            if not path.is_file():
                continue

            if path.name.endswith(".asset.json"):
                continue

            try:
                safe_path = _validate_managed_file(path)
                stat = safe_path.stat()
            except (OSError, ValueError):
                continue

            file_category = classify_file(safe_path)

            if category != "all" and file_category != category:
                continue

            metadata = load_metadata(safe_path)

            search_text = " ".join([
                safe_path.name,
                metadata["description"],
                " ".join(metadata["tags"]),
                root_name,
            ]).lower()

            if search and search not in search_text:
                continue

            results.append({
                "name": safe_path.name,
                "path": str(safe_path),
                "category": file_category,
                "folder": root_name,
                "size": stat.st_size,
                "size_text": format_size(stat.st_size),
                "extension": safe_path.suffix.lower(),
                "modified": datetime.fromtimestamp(
                    stat.st_mtime,
                    tz=timezone.utc,
                ).isoformat(),
                "description": metadata["description"],
                "tags": metadata["tags"],
                "mime_type": (
                    mimetypes.guess_type(safe_path.name)[0]
                    or "application/octet-stream"
                ),
            })

    results.sort(
        key=lambda item: item["modified"],
        reverse=True,
    )

    return results


def get_statistics() -> dict:
    """Calculate asset counts and storage usage."""
    assets = list_assets()

    stats = {
        "total": len(assets),
        "total_bytes": 0,
        "total_size": "0 B",
        "categories": {},
        "folders": {},
    }

    for item in assets:
        stats["total_bytes"] += item["size"]

        category = item["category"]
        folder = item["folder"]

        stats["categories"][category] = (
            stats["categories"].get(category, 0) + 1
        )

        stats["folders"][folder] = (
            stats["folders"].get(folder, 0) + 1
        )

    stats["total_size"] = format_size(stats["total_bytes"])

    return stats


def upload_asset(
    uploaded_file: Any,
    destination: str = "assets",
) -> tuple[bool, str]:
    """
    Save a Streamlit UploadedFile or file-like object.

    The destination must be one of the configured managed folders.
    """
    roots = get_managed_roots()

    if destination not in roots:
        return False, "Invalid destination folder."

    if not hasattr(uploaded_file, "name"):
        return False, "Invalid uploaded file."

    filename = _safe_filename(uploaded_file.name)
    root = roots[destination]

    try:
        root.mkdir(parents=True, exist_ok=True)

        if hasattr(uploaded_file, "getbuffer"):
            content = uploaded_file.getbuffer()
        else:
            content = uploaded_file.read()

        if len(content) > MAX_UPLOAD_MB * 1024 * 1024:
            return False, (
                f"File exceeds the {MAX_UPLOAD_MB} MB upload limit."
            )

        target = root / filename

        # Avoid overwriting existing assets.
        if target.exists():
            stem = target.stem
            suffix = target.suffix
            target = root / (
                f"{stem}_{uuid.uuid4().hex[:8]}{suffix}"
            )

        with target.open("xb") as file:
            file.write(content)

        return True, str(target)

    except (OSError, ValueError) as exc:
        return False, str(exc)


def delete_asset(
    asset_path: str | Path,
    delete_metadata: bool = True,
) -> tuple[bool, str]:
    """Delete a file inside a managed root."""
    try:
        path = _validate_managed_file(asset_path)

        sidecar = _metadata_path(path)

        path.unlink()

        if delete_metadata:
            sidecar.unlink(missing_ok=True)

        return True, "Asset deleted."

    except (OSError, ValueError) as exc:
        return False, str(exc)


def move_asset(
    asset_path: str | Path,
    destination: str,
) -> tuple[bool, str]:
    """Move an asset between managed folders."""
    roots = get_managed_roots()

    if destination not in roots:
        return False, "Invalid destination folder."

    try:
        source = _validate_managed_file(asset_path)
        target_root = roots[destination].resolve()

        if _is_inside(source, target_root):
            return False, "Asset is already in that folder."

        target_root.mkdir(parents=True, exist_ok=True)

        target = target_root / source.name

        if target.exists():
            target = target_root / (
                f"{source.stem}_{uuid.uuid4().hex[:8]}"
                f"{source.suffix}"
            )

        old_sidecar = _metadata_path(source)
        new_sidecar = _metadata_path(target)

        shutil.move(str(source), str(target))

        if old_sidecar.exists():
            shutil.move(str(old_sidecar), str(new_sidecar))

        return True, str(target)

    except (OSError, ValueError) as exc:
        return False, str(exc)


def render(st) -> None:
    """Render the Streamlit asset library."""
    st.title("Asset Manager")
    st.caption(
        "Browse and organize your AI Influencer Studio assets."
    )

    ensure_directories()

    stats = get_statistics()

    c1, c2, c3 = st.columns(3)
    c1.metric("Total assets", stats["total"])
    c2.metric("Storage used", stats["total_size"])
    c3.metric(
        "Asset types",
        len(stats["categories"]),
    )

    st.divider()

    tab_library, tab_upload, tab_manage = st.tabs([
        "Asset Library",
        "Upload",
        "Manage Asset",
    ])

    with tab_library:
        col1, col2 = st.columns(2)

        with col1:
            category = st.selectbox(
                "File type",
                [
                    "all", "image", "video",
                    "audio", "document", "other",
                ],
            )

        with col2:
            folder = st.selectbox(
                "Storage folder",
                ["all", "assets", "outputs", "projects"],
            )

        search = st.text_input(
            "Search assets",
            placeholder="Search filename, description or tag...",
        )

        assets = list_assets(
            category=category,
            search=search,
            folder=folder,
        )

        st.write(f"Found {len(assets)} assets.")

        if not assets:
            st.info("No assets found. Upload a file to get started.")

        for item in assets:
            with st.container(border=True):
                col1, col2 = st.columns([1, 3])

                with col1:
                    if item["category"] == "image":
                        try:
                            st.image(
                                item["path"],
                                use_container_width=True,
                            )
                        except Exception:
                            st.caption("Image preview unavailable.")
                    else:
                        st.markdown(
                            f"**{item['category'].upper()}**"
                        )
                        st.caption(item["extension"])

                with col2:
                    st.markdown(f"**{item['name']}**")
                    st.caption(
                        f"{item['folder']} · {item['size_text']}"
                    )

                    if item["description"]:
                        st.write(item["description"])

                    if item["tags"]:
                        st.write(
                            "Tags: " + ", ".join(item["tags"])
                        )

                    st.caption(item["modified"])

                    with st.expander("Asset details"):
                        st.code(item["path"])
                        st.write("MIME type:", item["mime_type"])

                        if item["category"] == "audio":
                            st.audio(item["path"])

                        if item["category"] == "video":
                            st.video(item["path"])

    with tab_upload:
        st.subheader("Upload new assets")

        uploaded = st.file_uploader(
            "Choose files",
            accept_multiple_files=True,
        )

        destination = st.selectbox(
            "Save to",
            ["assets", "outputs", "projects"],
        )

        if st.button("Upload selected files"):
            if not uploaded:
                st.warning("Select at least one file.")
            else:
                success_count = 0

                for file in uploaded:
                    ok, result = upload_asset(
                        file,
                        destination,
                    )

                    if ok:
                        success_count += 1
                        st.success(f"Uploaded: {Path(result).name}")
                    else:
                        st.error(f"{file.name}: {result}")

                st.info(
                    f"Successfully uploaded {success_count} "
                    f"of {len(uploaded)} files."
                )

    with tab_manage:
        st.subheader("Edit or manage an asset")

        assets = list_assets(limit=None) if False else list_assets()

        if not assets:
            st.info("There are no assets to manage.")
        else:
            asset_options = {
                f"{item['name']} ({item['folder']})": item["path"]
                for item in assets
            }

            selected_label = st.selectbox(
                "Select asset",
                list(asset_options.keys()),
            )

            selected_path = asset_options[selected_label]
            metadata = load_metadata(selected_path)

            description = st.text_area(
                "Description",
                value=metadata["description"],
                max_chars=2000,
            )

            tags_text = st.text_input(
                "Tags (comma separated)",
                value=", ".join(metadata["tags"]),
            )

            if st.button("Save asset metadata"):
                tags = [
                    tag.strip()
                    for tag in tags_text.split(",")
                    if tag.strip()
                ]

                ok, message = save_metadata(
                    selected_path,
                    description,
                    tags,
                )

                if ok:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)

            st.divider()

            move_destination = st.selectbox(
                "Move asset to",
                ["assets", "outputs", "projects"],
            )

            if st.button("Move selected asset"):
                ok, result = move_asset(
                    selected_path,
                    move_destination,
                )

                if ok:
                    st.success(f"Moved to: {result}")
                    st.rerun()
                else:
                    st.error(result)

            st.divider()

            confirm_delete = st.checkbox(
                "I understand this permanently deletes the selected file."
            )

            if st.button(
                "Delete selected asset",
                disabled=not confirm_delete,
            ):
                ok, message = delete_asset(selected_path)

                if ok:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)


def run_tests() -> bool:
    """Run isolated tests with temporary asset directories."""
    import unittest
    from unittest.mock import patch

    class AssetManagerTests(unittest.TestCase):

        def setUp(self):
            self.temp_dir = tempfile.TemporaryDirectory()
            self.root = Path(self.temp_dir.name)

            self.roots = {
                "assets": self.root / "assets",
                "outputs": self.root / "outputs",
                "projects": self.root / "projects",
            }

            for folder in self.roots.values():
                folder.mkdir(parents=True)

            self.patch_roots = patch(
                __name__ + ".get_managed_roots",
                return_value=self.roots,
            )
            self.patch_roots.start()

        def tearDown(self):
            self.patch_roots.stop()
            self.temp_dir.cleanup()

        def make_file(self, name="test.png", content=b"image"):
            path = self.roots["assets"] / name
            path.write_bytes(content)
            return path

        def test_classify_image(self):
            self.assertEqual(
                classify_file(Path("photo.png")),
                "image",
            )

        def test_classify_video(self):
            self.assertEqual(
                classify_file(Path("movie.mp4")),
                "video",
            )

        def test_classify_audio(self):
            self.assertEqual(
                classify_file(Path("audio.wav")),
                "audio",
            )

        def test_classify_document(self):
            self.assertEqual(
                classify_file(Path("notes.pdf")),
                "document",
            )

        def test_list_assets(self):
            self.make_file()

            result = list_assets()

            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["name"], "test.png")

        def test_search_assets(self):
            path = self.make_file()
            save_metadata(path, "My character image", ["hero"])

            result = list_assets(search="hero")

            self.assertEqual(len(result), 1)

        def test_save_and_load_metadata(self):
            path = self.make_file()

            ok, message = save_metadata(
                path,
                "Character portrait",
                ["character", "portrait"],
            )

            self.assertTrue(ok, message)

            metadata = load_metadata(path)

            self.assertEqual(
                metadata["description"],
                "Character portrait",
            )
            self.assertIn("character", metadata["tags"])

        def test_upload_asset(self):
            class FakeUpload:
                name = "upload.png"

                def getbuffer(self):
                    return b"test-content"

            ok, result = upload_asset(
                FakeUpload(),
                "assets",
            )

            self.assertTrue(ok, result)
            self.assertTrue(Path(result).exists())

        def test_upload_rejects_bad_destination(self):
            class FakeUpload:
                name = "upload.png"

                def getbuffer(self):
                    return b"content"

            ok, message = upload_asset(
                FakeUpload(),
                "unknown",
            )

            self.assertFalse(ok)

        def test_delete_asset(self):
            path = self.make_file()
            save_metadata(path, "Test", ["tag"])

            ok, message = delete_asset(path)

            self.assertTrue(ok, message)
            self.assertFalse(path.exists())
            self.assertFalse(_metadata_path(path).exists())

        def test_move_asset(self):
            path = self.make_file()

            ok, result = move_asset(path, "outputs")

            self.assertTrue(ok, result)
            self.assertTrue(Path(result).exists())
            self.assertFalse(path.exists())

        def test_statistics(self):
            self.make_file("one.png")
            self.make_file("two.png")

            stats = get_statistics()

            self.assertEqual(stats["total"], 2)
            self.assertEqual(stats["categories"]["image"], 2)

        def test_reject_external_file(self):
            external = self.root / "outside.txt"
            external.write_text("outside", encoding="utf-8")

            with self.assertRaises(ValueError):
                _validate_managed_file(external)

        def test_safe_filename(self):
            result = _safe_filename("../../unsafe name?.png")

            self.assertNotIn("/", result)
            self.assertNotIn("?", result)
            self.assertNotIn("..", result)

        def test_move_invalid_destination(self):
            path = self.make_file()

            ok, message = move_asset(path, "unknown")

            self.assertFalse(ok)
            self.assertTrue(path.exists())

        def test_delete_invalid_path(self):
            external = self.root / "external.txt"
            external.write_text("test", encoding="utf-8")

            ok, message = delete_asset(external)

            self.assertFalse(ok)
            self.assertTrue(external.exists())

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        AssetManagerTests
    )

    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AI Influencer Studio Asset Manager"
    )

    parser.add_argument(
        "--test",
        action="store_true",
        help="Run built-in tests",
    )

    args = parser.parse_args()

    if args.test:
        raise SystemExit(0 if run_tests() else 1)

    ensure_directories()
    print("Asset Manager loaded.")
    print("Run with --test to execute built-in tests.")
