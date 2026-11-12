
"""
AI Influencer Studio
File 26: Media Preview Studio

Features:
- Image preview
- Video playback
- Audio playback
- Text and document preview
- File metadata
- Asset filtering and selection
- Safe managed-directory scanning
- Optional integration with asset_manager.py
- Built-in tests

Run tests:
    python -m modules.media_preview --test

Run in Streamlit:
    from modules import media_preview
    media_preview.render(st)
"""

from __future__ import annotations

import argparse
import mimetypes
import os
import tempfile
import unittest

from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

APP_ROOT = Path(__file__).resolve().parent.parent

IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff"
}

VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"
}

AUDIO_EXTENSIONS = {
    ".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac"
}

TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".json", ".log", ".yaml", ".yml"
}

DOCUMENT_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xlsx", ".pptx"
}

PREVIEWABLE_EXTENSIONS = (
    IMAGE_EXTENSIONS
    | VIDEO_EXTENSIONS
    | AUDIO_EXTENSIONS
    | TEXT_EXTENSIONS
    | DOCUMENT_EXTENSIONS
)

MAX_TEXT_PREVIEW_BYTES = 1_000_000
MAX_TEXT_PREVIEW_CHARS = 30_000


# ---------------------------------------------------------
# OPTIONAL ASSET MANAGER INTEGRATION
# ---------------------------------------------------------

try:
    from modules import asset_manager
except ImportError:
    try:
        import asset_manager
    except ImportError:
        asset_manager = None


# ---------------------------------------------------------
# PATH UTILITIES
# ---------------------------------------------------------

def _inside(path: Path, root: Path) -> bool:
    """Return True when path resolves inside root."""

    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError, RuntimeError):
        return False


def _get_roots() -> list[Path]:
    """
    Get managed asset roots from asset_manager.

    Falls back to standard project directories if the
    asset manager is unavailable.
    """

    roots = []

    if asset_manager is not None:
        try:
            configured = asset_manager.get_managed_roots()

            if isinstance(configured, dict):
                values = configured.values()
            elif isinstance(configured, (list, tuple, set)):
                values = configured
            else:
                values = []

            for value in values:
                try:
                    path = Path(value).resolve()
                    if path.exists() and path.is_dir():
                        roots.append(path)
                except (TypeError, ValueError, OSError):
                    continue

        except Exception:
            pass

    if not roots:
        for folder in ("assets", "outputs", "projects"):
            path = APP_ROOT / folder
            if path.exists() and path.is_dir():
                roots.append(path.resolve())

    # Remove duplicates while preserving order.
    unique = []
    seen = set()

    for root in roots:
        key = str(root).casefold()
        if key not in seen:
            unique.append(root)
            seen.add(key)

    return unique


def _validate_path(file_path: str | Path) -> Path:
    """Validate that a file belongs to a managed directory."""

    path = Path(file_path).resolve(strict=True)

    if not path.is_file():
        raise ValueError("Selected path is not a file.")

    roots = _get_roots()

    if not any(_inside(path, root) for root in roots):
        raise ValueError("File is outside the managed asset directories.")

    return path


# ---------------------------------------------------------
# FILE CLASSIFICATION
# ---------------------------------------------------------

def classify_media(file_path: str | Path) -> str:
    """Classify a file by its extension."""

    extension = Path(file_path).suffix.lower()

    if extension in IMAGE_EXTENSIONS:
        return "image"

    if extension in VIDEO_EXTENSIONS:
        return "video"

    if extension in AUDIO_EXTENSIONS:
        return "audio"

    if extension in TEXT_EXTENSIONS:
        return "text"

    if extension in DOCUMENT_EXTENSIONS:
        return "document"

    return "other"


def format_size(size: int) -> str:
    """Convert bytes into a readable size."""

    value = float(size)

    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.2f} {unit}"
        value /= 1024

    return f"{value:.2f} TB"


# ---------------------------------------------------------
# MEDIA DISCOVERY
# ---------------------------------------------------------

def scan_media(
    category: str = "all",
    search: str = "",
    limit: int = 500,
) -> list[dict[str, Any]]:
    """
    Scan managed asset directories.

    Returns file information without reading media contents.
    """

    if limit < 1:
        return []

    results = []
    search = search.strip().casefold()

    for root in _get_roots():

        try:
            files = root.rglob("*")

            for path in files:

                if len(results) >= limit:
                    break

                try:
                    if not path.is_file():
                        continue

                    safe_path = _validate_path(path)

                    media_type = classify_media(safe_path)

                    if category != "all" and media_type != category:
                        continue

                    if search and search not in safe_path.name.casefold():
                        continue

                    stat = safe_path.stat()

                    results.append({
                        "name": safe_path.name,
                        "path": str(safe_path),
                        "type": media_type,
                        "extension": safe_path.suffix.lower(),
                        "size": stat.st_size,
                        "size_display": format_size(stat.st_size),
                        "modified": datetime.fromtimestamp(
                            stat.st_mtime
                        ).strftime("%Y-%m-%d %H:%M:%S"),
                        "mime_type": mimetypes.guess_type(
                            safe_path.name
                        )[0] or "application/octet-stream",
                    })

                except (OSError, ValueError, RuntimeError):
                    continue

        except OSError:
            continue

        if len(results) >= limit:
            break

    results.sort(
        key=lambda item: item["modified"],
        reverse=True
    )

    return results


# ---------------------------------------------------------
# FILE METADATA
# ---------------------------------------------------------

def get_metadata(file_path: str | Path) -> dict[str, Any]:
    """Return metadata for a managed file."""

    path = _validate_path(file_path)
    stat = path.stat()

    metadata = {
        "File name": path.name,
        "File type": classify_media(path),
        "Extension": path.suffix.lower() or "None",
        "File size": format_size(stat.st_size),
        "Size in bytes": stat.st_size,
        "Modified": datetime.fromtimestamp(
            stat.st_mtime
        ).strftime("%Y-%m-%d %H:%M:%S"),
        "MIME type": mimetypes.guess_type(
            path.name
        )[0] or "Unknown",
        "Location": str(path.parent),
    }

    if asset_manager is not None:
        try:
            extra = asset_manager.load_metadata(path)

            if isinstance(extra, dict):
                metadata["Asset metadata"] = extra

        except Exception:
            pass

    return metadata


# ---------------------------------------------------------
# IMAGE PREVIEW
# ---------------------------------------------------------

def preview_image(st: Any, path: Path) -> None:
    """Display an image using Streamlit."""

    st.image(
        str(path),
        caption=path.name,
        use_container_width=True,
    )


# ---------------------------------------------------------
# VIDEO PREVIEW
# ---------------------------------------------------------

def preview_video(st: Any, path: Path) -> None:
    """Play a local video using Streamlit."""

    st.video(str(path))

    st.caption(
        "Video playback uses your browser's supported codecs. "
        "Some formats may need conversion to MP4."
    )


# ---------------------------------------------------------
# AUDIO PREVIEW
# ---------------------------------------------------------

def preview_audio(st: Any, path: Path) -> None:
    """Play local audio using Streamlit."""

    st.audio(str(path))

    st.caption(
        "Audio playback is handled by the browser."
    )


# ---------------------------------------------------------
# TEXT PREVIEW
# ---------------------------------------------------------

def read_text_preview(path: Path) -> str:
    """Read a limited amount of a supported text file."""

    safe_path = _validate_path(path)

    if safe_path.suffix.lower() not in TEXT_EXTENSIONS:
        raise ValueError("Unsupported text preview format.")

    if safe_path.stat().st_size > MAX_TEXT_PREVIEW_BYTES:
        raise ValueError("File is too large for text preview.")

    content = safe_path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    return content[:MAX_TEXT_PREVIEW_CHARS]


def preview_text(st: Any, path: Path) -> None:
    """Display a safe text preview."""

    try:
        content = read_text_preview(path)

        if path.suffix.lower() == ".json":
            st.code(content, language="json")
        elif path.suffix.lower() in {".yaml", ".yml"}:
            st.code(content, language="yaml")
        elif path.suffix.lower() == ".csv":
            st.code(content, language="csv")
        else:
            st.text_area(
                "Document preview",
                value=content,
                height=350,
                disabled=True,
            )

    except (OSError, ValueError) as exc:
        st.warning(str(exc))


# ---------------------------------------------------------
# DOCUMENT PREVIEW
# ---------------------------------------------------------

def preview_document(st: Any, path: Path) -> None:
    """
    Display information for office and PDF documents.

    Full document rendering requires an additional document
    reader. This lightweight module does not install one.
    """

    st.info(
        f"Document detected: {path.name}"
    )

    st.write(
        "This file is available in your managed asset library. "
        "Full PDF or Office document rendering is not enabled "
        "in this lightweight preview module."
    )

    st.caption(
        "Supported document extensions: PDF, DOC, DOCX, XLSX, PPTX."
    )


# ---------------------------------------------------------
# UNIFIED PREVIEW
# ---------------------------------------------------------

def render_preview(
    st: Any,
    file_path: str | Path,
) -> None:
    """Render the appropriate preview for a managed file."""

    try:
        path = _validate_path(file_path)
    except (OSError, ValueError, RuntimeError) as exc:
        st.error(f"Cannot preview this file: {exc}")
        return

    media_type = classify_media(path)

    st.subheader(path.name)

    if media_type == "image":
        preview_image(st, path)

    elif media_type == "video":
        preview_video(st, path)

    elif media_type == "audio":
        preview_audio(st, path)

    elif media_type == "text":
        preview_text(st, path)

    elif media_type == "document":
        preview_document(st, path)

    else:
        st.warning(
            "Preview is not available for this file type."
        )

    st.divider()
    st.markdown("#### File information")

    try:
        metadata = get_metadata(path)

        display_metadata = {
            key: value
            for key, value in metadata.items()
            if key != "Asset metadata"
        }

        st.json(display_metadata)

        if metadata.get("Asset metadata"):
            with st.expander("Additional asset metadata"):
                st.json(metadata["Asset metadata"])

    except (OSError, ValueError, RuntimeError) as exc:
        st.warning(f"Metadata unavailable: {exc}")


# ---------------------------------------------------------
# STREAMLIT MEDIA PREVIEW STUDIO
# ---------------------------------------------------------

def render(st: Any) -> None:
    """Render the Media Preview Studio page."""

    st.title("Media Preview Studio")

    st.write(
        "Browse and preview images, videos, audio files, "
        "and documents stored in your managed project folders."
    )

    roots = _get_roots()

    if not roots:
        st.warning(
            "No managed asset directories were found. "
            "Create your assets, outputs, or projects folders first."
        )
        return

    with st.sidebar:
        st.markdown("### Preview filters")

        category = st.selectbox(
            "Media category",
            [
                "all",
                "image",
                "video",
                "audio",
                "text",
                "document",
                "other",
            ],
        )

        search = st.text_input(
            "Search filename",
            placeholder="Enter filename...",
        )

        limit = st.number_input(
            "Maximum files to scan",
            min_value=10,
            max_value=2000,
            value=500,
            step=50,
        )

    files = scan_media(
        category=category,
        search=search,
        limit=int(limit),
    )

    # Summary
    col1, col2, col3 = st.columns(3)

    col1.metric("Available files", len(files))

    total_size = sum(item["size"] for item in files)
    col2.metric("Total size", format_size(total_size))

    type_count = len(set(item["type"] for item in files))
    col3.metric("Media types", type_count)

    st.divider()

    if not files:
        st.info(
            "No matching files found. Upload assets using "
            "your Asset Manager."
        )
        return

    # File selector
    file_options = {
        (
            f"{item['name']} | {item['type']} | "
            f"{item['size_display']} | {item['modified']}"
        ): item["path"]
        for item in files
    }

    selected_label = st.selectbox(
        "Select a file to preview",
        list(file_options.keys()),
    )

    selected_path = file_options[selected_label]

    st.divider()

    # Preview and details
    preview_col, details_col = st.columns(
        [2, 1],
        gap="large",
    )

    with preview_col:
        render_preview(st, selected_path)

    with details_col:
        st.markdown("### Asset details")

        selected = next(
            item for item in files
            if item["path"] == selected_path
        )

        st.write("**Name:**", selected["name"])
        st.write("**Category:**", selected["type"])
        st.write("**Extension:**", selected["extension"])
        st.write("**Size:**", selected["size_display"])
        st.write("**Modified:**", selected["modified"])

        st.caption(
            "The preview panel does not modify or regenerate "
            "the selected asset."
        )

    # Recent files
    with st.expander("Browse all matching files"):
        rows = [
            {
                "Name": item["name"],
                "Type": item["type"],
                "Size": item["size_display"],
                "Modified": item["modified"],
            }
            for item in files
        ]

        st.dataframe(
            rows,
            use_container_width=True,
            hide_index=True,
        )


# ---------------------------------------------------------
# BUILT-IN TESTS
# ---------------------------------------------------------

class MediaPreviewTests(unittest.TestCase):

    def test_image_classification(self):
        self.assertEqual(
            classify_media("portrait.png"),
            "image",
        )

    def test_video_classification(self):
        self.assertEqual(
            classify_media("movie.mp4"),
            "video",
        )

    def test_audio_classification(self):
        self.assertEqual(
            classify_media("voice.wav"),
            "audio",
        )

    def test_text_classification(self):
        self.assertEqual(
            classify_media("prompt.txt"),
            "text",
        )

    def test_document_classification(self):
        self.assertEqual(
            classify_media("guide.pdf"),
            "document",
        )

    def test_unknown_classification(self):
        self.assertEqual(
            classify_media("unknown.xyz"),
            "other",
        )

    def test_format_size(self):
        self.assertEqual(
            format_size(1024),
            "1.00 KB",
        )

    def test_format_zero(self):
        self.assertEqual(
            format_size(0),
            "0.00 B",
        )

    def test_text_preview(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            file_path = root / "sample.txt"
            file_path.write_text(
                "Hello AI Studio",
                encoding="utf-8",
            )

            original_roots = _get_roots

            try:
                globals()["_get_roots"] = lambda: [root]

                result = read_text_preview(file_path)

                self.assertEqual(
                    result,
                    "Hello AI Studio",
                )

            finally:
                globals()["_get_roots"] = original_roots

    def test_text_preview_rejects_large_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            file_path = root / "large.txt"

            file_path.write_text(
                "A" * (MAX_TEXT_PREVIEW_BYTES + 1),
                encoding="utf-8",
            )

            original_roots = _get_roots

            try:
                globals()["_get_roots"] = lambda: [root]

                with self.assertRaises(ValueError):
                    read_text_preview(file_path)

            finally:
                globals()["_get_roots"] = original_roots

    def test_rejects_outside_path(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "managed"
            outside = Path(temp) / "outside.txt"

            root.mkdir()
            outside.write_text("Not managed", encoding="utf-8")

            original_roots = _get_roots

            try:
                globals()["_get_roots"] = lambda: [root]

                with self.assertRaises(ValueError):
                    _validate_path(outside)

            finally:
                globals()["_get_roots"] = original_roots

    def test_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            file_path = root / "sample.txt"
            file_path.write_text("metadata test", encoding="utf-8")

            original_roots = _get_roots

            try:
                globals()["_get_roots"] = lambda: [root]

                metadata = get_metadata(file_path)

                self.assertEqual(
                    metadata["File name"],
                    "sample.txt",
                )
                self.assertEqual(
                    metadata["File type"],
                    "text",
                )

            finally:
                globals()["_get_roots"] = original_roots

    def test_scan_media(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()

            (root / "image.png").write_bytes(b"fake-image")
            (root / "notes.txt").write_text(
                "test",
                encoding="utf-8",
            )

            original_roots = _get_roots

            try:
                globals()["_get_roots"] = lambda: [root]

                results = scan_media()

                names = {item["name"] for item in results}

                self.assertIn("image.png", names)
                self.assertIn("notes.txt", names)

            finally:
                globals()["_get_roots"] = original_roots

    def test_scan_category_filter(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()

            (root / "image.png").write_bytes(b"fake-image")
            (root / "notes.txt").write_text(
                "test",
                encoding="utf-8",
            )

            original_roots = _get_roots

            try:
                globals()["_get_roots"] = lambda: [root]

                results = scan_media(category="image")

                self.assertTrue(
                    all(item["type"] == "image" for item in results)
                )

            finally:
                globals()["_get_roots"] = original_roots


def run_tests() -> bool:
    """Execute built-in tests."""

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        MediaPreviewTests
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
        description="AI Influencer Studio Media Preview"
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

    print("Media Preview Studio")
    print("Run the module through your Streamlit application.")
