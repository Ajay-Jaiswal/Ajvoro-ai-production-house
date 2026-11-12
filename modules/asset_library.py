
from __future__ import annotations

import os
import mimetypes
from pathlib import Path
from typing import Optional

import streamlit as st

try:
    import config
except ImportError:
    config = None

try:
    import storage
except ImportError:
    storage = None


MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parent

# Resolve configured directories, with safe project defaults.
ASSETS_DIR = Path(
    getattr(config, "ASSETS_DIR", PROJECT_ROOT / "assets")
).resolve()

OUTPUT_DIR = Path(
    getattr(config, "OUTPUT_DIR", PROJECT_ROOT / "output")
).resolve()

CHARACTERS_DIR = ASSETS_DIR / "characters"
OUTFITS_DIR = ASSETS_DIR / "outfits"
MOTION_DIR = ASSETS_DIR / "motion"
AUDIO_DIR = ASSETS_DIR / "audio"
PROJECTS_DIR = ASSETS_DIR / "projects"

ALLOWED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp",
    ".mp4", ".mov", ".avi", ".mkv",
    ".wav", ".mp3", ".ogg", ".flac",
    ".json", ".txt", ".srt"
}

CATEGORY_DIRECTORIES = {
    "Characters": CHARACTERS_DIR,
    "Outfits": OUTFITS_DIR,
    "Motion References": MOTION_DIR,
    "Audio": AUDIO_DIR,
    "Projects": PROJECTS_DIR,
}


def ensure_directories() -> None:
    """Create persistent asset folders if they do not exist."""
    for directory in CATEGORY_DIRECTORIES.values():
        directory.mkdir(parents=True, exist_ok=True)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def is_inside(path: Path, parent: Path) -> bool:
    """Return True only when path is inside parent."""
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except (ValueError, OSError):
        return False


def detect_category(path: Path) -> str:
    """Determine the asset category from its parent folder."""
    for category, directory in CATEGORY_DIRECTORIES.items():
        if is_inside(path, directory):
            return category

    return "Other"


def format_size(size: int) -> str:
    """Format file size for display."""
    value = float(size)

    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024

    return f"{value:.1f} TB"


def get_file_type(path: Path) -> str:
    """Identify common asset types."""
    extension = path.suffix.lower()

    if extension in {".png", ".jpg", ".jpeg", ".webp"}:
        return "Image"

    if extension in {".mp4", ".mov", ".avi", ".mkv"}:
        return "Video"

    if extension in {".wav", ".mp3", ".ogg", ".flac"}:
        return "Audio"

    if extension in {".json", ".txt", ".srt"}:
        return "Document"

    return "Other"


def scan_assets():
    """Scan persistent folders without modifying their contents."""
    ensure_directories()
    assets = []

    for category, directory in CATEGORY_DIRECTORIES.items():
        try:
            for path in directory.rglob("*"):
                if not path.is_file():
                    continue

                if path.suffix.lower() not in ALLOWED_EXTENSIONS:
                    continue

                try:
                    stat = path.stat()

                    assets.append({
                        "name": path.name,
                        "path": path,
                        "category": category,
                        "type": get_file_type(path),
                        "size": format_size(stat.st_size),
                        "modified": stat.st_mtime,
                    })
                except OSError:
                    continue

        except OSError:
            continue

    return sorted(
        assets,
        key=lambda item: item["modified"],
        reverse=True
    )


def scan_temporary_outputs():
    """
    Get temporary output records through storage.py.

    This function does not independently delete files.
    Expiration and cleanup remain the responsibility of storage.py.
    """
    if storage is None:
        return []

    try:
        return storage.list_outputs()
    except Exception:
        return []


def safe_delete_asset(path: Path) -> tuple[bool, str]:
    """
    Delete only files inside approved persistent asset directories.

    Never deletes output, project root, or arbitrary external paths.
    """
    try:
        resolved = path.resolve()

        approved = any(
            is_inside(resolved, directory)
            for directory in CATEGORY_DIRECTORIES.values()
        )

        if not approved:
            return False, "Deletion blocked: file is outside approved asset folders."

        if not resolved.is_file():
            return False, "File does not exist."

        if resolved.is_symlink():
            return False, "Symbolic links cannot be deleted through this library."

        resolved.unlink()
        return True, "Asset deleted successfully."

    except PermissionError:
        return False, "Permission denied while deleting the asset."

    except OSError as exc:
        return False, f"Could not delete asset: {exc}"


def render_asset_preview(asset: dict) -> None:
    """Display a suitable preview for an asset."""
    path = asset["path"]
    file_type = asset["type"]

    try:
        if file_type == "Image":
            st.image(str(path), use_container_width=True)

        elif file_type == "Video":
            st.video(str(path))

        elif file_type == "Audio":
            st.audio(str(path))

        elif file_type == "Document":
            st.caption("Document asset")

            if path.suffix.lower() in {".txt", ".srt"}:
                try:
                    content = path.read_text(
                        encoding="utf-8",
                        errors="replace"
                    )

                    st.text_area(
                        "File content",
                        value=content[:5000],
                        height=150,
                        disabled=True,
                        key=f"preview_{str(path)}"
                    )
                except OSError:
                    st.warning("Unable to read this document.")

        else:
            st.info("Preview is not supported for this file type.")

    except Exception as exc:
        st.warning(f"Preview unavailable: {exc}")


def render_asset_card(asset: dict, index: int) -> None:
    """Render one asset with metadata and deletion controls."""
    path = asset["path"]

    with st.container(border=True):
        st.markdown(f"**{asset['name']}**")

        st.caption(
            f"{asset['category']} | "
            f"{asset['type']} | "
            f"{asset['size']}"
        )

        render_asset_preview(asset)

        confirm_key = f"confirm_delete_{index}"

        if st.checkbox(
            "Confirm deletion",
            key=confirm_key
        ):
            if st.button(
                "Delete asset",
                key=f"delete_{index}",
                type="secondary"
            ):
                success, message = safe_delete_asset(path)

                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)


def render_persistent_assets() -> None:
    """Render searchable persistent asset library."""
    assets = scan_assets()

    st.subheader("Persistent Asset Library")
    st.caption(
        "These files remain stored until you explicitly delete them."
    )

    search = st.text_input(
        "Search assets",
        placeholder="Search by filename..."
    )

    categories = ["All"] + list(CATEGORY_DIRECTORIES.keys())

    selected_category = st.selectbox(
        "Category",
        categories
    )

    file_types = [
        "All",
        "Image",
        "Video",
        "Audio",
        "Document"
    ]

    selected_type = st.selectbox(
        "File type",
        file_types
    )

    filtered = assets

    if search.strip():
        query = search.strip().lower()

        filtered = [
            item for item in filtered
            if query in item["name"].lower()
        ]

    if selected_category != "All":
        filtered = [
            item for item in filtered
            if item["category"] == selected_category
        ]

    if selected_type != "All":
        filtered = [
            item for item in filtered
            if item["type"] == selected_type
        ]

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Total assets", len(assets))

    with col2:
        st.metric("Filtered assets", len(filtered))

    if not filtered:
        st.info("No assets found. Upload assets from the relevant studio.")
        return

    for index, asset in enumerate(filtered):
        render_asset_card(asset, index)


def render_temporary_outputs() -> None:
    """Show temporary generated outputs registered in storage.py."""
    st.subheader("Temporary Generated Outputs")

    st.caption(
        "Outputs are managed by storage.py and expire after one hour "
        "according to its retention policy."
    )

    outputs = scan_temporary_outputs()

    if not outputs:
        st.info("No registered temporary outputs found.")
        return

    for index, output in enumerate(outputs):
        name = output.get("name", "Generated output")
        path_value = output.get("path")
        remaining = output.get("remaining_seconds")

        with st.container(border=True):
            st.markdown(f"**{name}**")

            if remaining is not None:
                minutes = max(0, int(remaining) // 60)
                st.caption(f"Approximate time remaining: {minutes} minutes")

            if path_value:
                path = Path(path_value)

                if path.is_file():
                    file_type = get_file_type(path)

                    if file_type == "Image":
                        st.image(str(path), use_container_width=True)
                    elif file_type == "Video":
                        st.video(str(path))
                    elif file_type == "Audio":
                        st.audio(str(path))

                    try:
                        with open(path, "rb") as file:
                            st.download_button(
                                "Download output",
                                data=file.read(),
                                file_name=path.name,
                                key=f"download_output_{index}"
                            )
                    except OSError:
                        st.warning("Unable to open this output file.")
                else:
                    st.caption("Output file is no longer available.")


def render_storage_information() -> None:
    """Explain storage separation."""
    with st.expander("Storage and retention information"):
        st.markdown(
            """
            **Persistent assets**
            - Character reference images
            - Outfit reference images
            - Motion reference files
            - Audio assets
            - Project files

            These are not automatically deleted.

            **Temporary outputs**
            - Generated previews
            - Rendered results
            - Temporary processing files

            These are managed by `storage.py` and its one-hour
            retention policy.

            Cleanup runs according to the storage module's schedule.
            It may not run while the application is closed.
            """
        )


def render(st) -> None:
    """Streamlit module entry point used by app.py."""
    ensure_directories()

    st.title("Asset Library")
    st.write(
        "Manage your saved characters, outfits, motion references, "
        "audio assets, projects and temporary generated outputs."
    )

    persistent_tab, output_tab = st.tabs([
        "Persistent Assets",
        "Temporary Outputs"
    ])

    with persistent_tab:
        render_persistent_assets()

    with output_tab:
        render_temporary_outputs()

    render_storage_information()


if __name__ == "__main__":
    st.set_page_config(
        page_title="AI Influencer Studio - Asset Library",
        layout="wide"
    )

    render(st)
