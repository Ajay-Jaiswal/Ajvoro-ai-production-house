
"""
AI Influencer Studio
File 20: modules/export_manager.py

Local ZIP export manager.

Supported exports:
- Individual projects
- Character packages
- Complete asset collections
- Complete project collections

Features:
- JSON export manifest
- SHA256 file checksums
- ZIP integrity validation
- Safe archive paths
- Streamlit export interface
- Built-in unit tests

Run:
    python -m modules.export_manager --test
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
import zipfile

from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable


APP_ROOT = Path(__file__).resolve().parent.parent

EXCLUDED_DIRS = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "temp",
    "backups",
}

MANIFEST_NAME = "export_manifest.json"

EXPORT_DIR_NAME = "exports"


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

def load_config():
    try:
        import config
        return config
    except ImportError:
        return None


def configured_path(names, default=None):
    cfg = load_config()

    if cfg:
        for name in names:
            value = getattr(cfg, name, None)

            if value:
                path = Path(value).expanduser()

                if not path.is_absolute():
                    path = APP_ROOT / path

                return path.resolve()

    return Path(default).resolve() if default else None


def get_root() -> Path:
    return configured_path(
        ("BASE_DIR", "APP_DIR", "PROJECT_ROOT"),
        APP_ROOT
    )


def get_export_dir() -> Path:
    return configured_path(
        ("EXPORT_DIR", "EXPORTS_DIR"),
        get_root() / EXPORT_DIR_NAME
    )


def get_asset_dir() -> Path:
    return configured_path(
        ("ASSETS_DIR", "ASSET_DIR"),
        get_root() / "assets"
    )


def get_project_dir() -> Path:
    return configured_path(
        ("PROJECTS_DIR", "PROJECT_DIR"),
        get_root() / "projects"
    )


# ---------------------------------------------------------
# Utility functions
# ---------------------------------------------------------

def safe_filename(value: str) -> str:
    value = re.sub(
        r"[^a-zA-Z0-9_-]+",
        "_",
        str(value)
    ).strip("_")

    return value[:80] or "export"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def is_excluded(path: Path) -> bool:
    return any(
        part.lower() in EXCLUDED_DIRS
        for part in path.parts
    )


def collect_files(source: Path) -> list[Path]:
    """Collect files while excluding temporary directories."""

    if not source.exists():
        return []

    if source.is_file():
        return [] if is_excluded(source) else [source]

    result = []

    for path in source.rglob("*"):
        try:
            if not path.is_file():
                continue

            if is_excluded(path):
                continue

            result.append(path)

        except OSError:
            continue

    return sorted(result)


def relative_archive_path(path: Path, source: Path) -> str:
    """Create a safe relative ZIP path."""

    relative = (
        path.relative_to(source)
        if source.is_dir()
        else Path(path.name)
    )

    archive_path = PurePosixPath(relative.as_posix())

    if archive_path.is_absolute() or ".." in archive_path.parts:
        raise ValueError("Unsafe archive path detected.")

    return archive_path.as_posix()


# ---------------------------------------------------------
# Project discovery
# ---------------------------------------------------------

def list_projects() -> list[dict]:
    project_dir = get_project_dir()

    if not project_dir.exists():
        return []

    results = []

    for path in sorted(project_dir.iterdir()):
        if not path.is_dir() or is_excluded(path):
            continue

        metadata = {}

        for filename in ("project.json", "metadata.json"):
            metadata_path = path / filename

            if metadata_path.is_file():
                try:
                    metadata = json.loads(
                        metadata_path.read_text(encoding="utf-8")
                    )
                    break
                except (OSError, json.JSONDecodeError):
                    continue

        results.append({
            "name": metadata.get("name", path.name),
            "path": path,
            "status": metadata.get("status", "Unknown"),
        })

    return results


# ---------------------------------------------------------
# Character discovery
# ---------------------------------------------------------

def list_characters() -> list[dict]:
    asset_dir = get_asset_dir()

    if not asset_dir.exists():
        return []

    results = []

    for path in asset_dir.rglob("*.json"):
        if is_excluded(path):
            continue

        try:
            data = json.loads(path.read_text(encoding="utf-8"))

            if not isinstance(data, dict):
                continue

            is_character = (
                "character" in path.stem.lower()
                or "character" in path.parent.name.lower()
                or "character_name" in data
                or (
                    "name" in data
                    and any(
                        key in data
                        for key in (
                            "appearance",
                            "personality",
                            "identity"
                        )
                    )
                )
            )

            if not is_character:
                continue

            results.append({
                "name": data.get(
                    "name",
                    data.get("character_name", path.stem)
                ),
                "path": path,
                "metadata": data,
            })

        except (OSError, json.JSONDecodeError):
            continue

    return results


# ---------------------------------------------------------
# Export engine
# ---------------------------------------------------------

def create_export(
    export_type: str,
    selection: str | None = None,
    custom_name: str | None = None,
) -> Path:
    """
    Create a ZIP export.

    export_type:
        project
        character
        assets
        projects
        all_assets

    selection:
        Project name or character name for individual exports.
    """

    supported_types = {
        "project",
        "character",
        "assets",
        "projects",
        "all_assets",
    }

    if export_type not in supported_types:
        raise ValueError(
            f"Unsupported export type: {export_type}"
        )

    root = get_root()
    export_dir = get_export_dir()

    export_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    sources: list[tuple[Path, str]] = []

    if export_type == "project":
        project = next(
            (
                item for item in list_projects()
                if item["name"] == selection
            ),
            None
        )

        if not project:
            raise ValueError("Selected project was not found.")

        sources.append((
            project["path"],
            f"projects/{project['path'].name}"
        ))

    elif export_type == "character":
        character = next(
            (
                item for item in list_characters()
                if item["name"] == selection
            ),
            None
        )

        if not character:
            raise ValueError("Selected character was not found.")

        # Include character metadata.
        sources.append((
            character["path"],
            f"characters/{character['path'].name}"
        ))

        # Include neighboring files only from its character folder.
        character_folder = character["path"].parent

        if character_folder != get_asset_dir():
            for file in collect_files(character_folder):
                if file == character["path"]:
                    continue

                sources.append((
                    file,
                    f"characters/{character_folder.name}/{file.relative_to(character_folder).as_posix()}"
                ))

    elif export_type == "assets":
        sources.append((
            get_asset_dir(),
            "assets"
        ))

    elif export_type == "all_assets":
        sources.append((
            get_asset_dir(),
            "assets"
        ))

    elif export_type == "projects":
        sources.append((
            get_project_dir(),
            "projects"
        ))

    safe_name = safe_filename(
        custom_name or selection or export_type
    )

    destination = export_dir / (
        f"{safe_name}_{timestamp}.zip"
    )

    temporary_path = export_dir / (
        f".{safe_name}_{timestamp}.tmp"
    )

    manifest = {
        "application": "AI Influencer Studio",
        "export_version": 1,
        "export_type": export_type,
        "name": safe_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": [],
    }

    try:
        with zipfile.ZipFile(
            temporary_path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=4,
        ) as archive:

            for source, archive_prefix in sources:

                if not source.exists():
                    continue

                files = collect_files(source)

                for file in files:

                    if source.is_dir():
                        relative = relative_archive_path(
                            file,
                            source
                        )
                    else:
                        relative = file.name

                    archive_name = (
                        PurePosixPath(archive_prefix)
                        / PurePosixPath(relative)
                    )

                    if (
                        archive_name.is_absolute()
                        or ".." in archive_name.parts
                    ):
                        raise ValueError(
                            "Unsafe export path detected."
                        )

                    archive_name_str = archive_name.as_posix()

                    archive.write(
                        file,
                        archive_name_str
                    )

                    manifest["files"].append({
                        "path": archive_name_str,
                        "size": file.stat().st_size,
                        "sha256": file_hash(file),
                    })

            if not manifest["files"]:
                raise ValueError(
                    "No exportable files found."
                )

            archive.writestr(
                MANIFEST_NAME,
                json.dumps(manifest, indent=2)
            )

        # Atomic publication after successful archive creation.
        temporary_path.replace(destination)

        return destination

    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


# ---------------------------------------------------------
# Export inspection
# ---------------------------------------------------------

def verify_export(export_path: str | Path) -> tuple[bool, str]:
    path = Path(export_path)

    if not path.is_file():
        return False, "Export archive does not exist."

    try:
        with zipfile.ZipFile(path, "r") as archive:

            bad_file = archive.testzip()

            if bad_file:
                return False, f"Corrupt file: {bad_file}"

            names = archive.namelist()

            if MANIFEST_NAME not in names:
                return False, "Export manifest missing."

            manifest = json.loads(
                archive.read(MANIFEST_NAME).decode("utf-8")
            )

            for item in manifest.get("files", []):
                filename = item["path"]

                if filename not in names:
                    return False, f"Missing file: {filename}"

                actual_hash = hashlib.sha256(
                    archive.read(filename)
                ).hexdigest()

                if actual_hash != item["sha256"]:
                    return False, f"Checksum mismatch: {filename}"

        return True, "Export verified successfully."

    except (
        OSError,
        ValueError,
        KeyError,
        zipfile.BadZipFile,
        json.JSONDecodeError,
    ) as error:
        return False, f"Verification failed: {error}"


def list_exports() -> list[dict]:
    export_dir = get_export_dir()

    if not export_dir.exists():
        return []

    results = []

    for path in export_dir.glob("*.zip"):
        try:
            stat = path.stat()

            results.append({
                "name": path.name,
                "path": path,
                "size": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_mtime),
            })

        except OSError:
            continue

    return sorted(
        results,
        key=lambda item: item["created"],
        reverse=True
    )


def format_size(size: int) -> str:
    value = float(size)

    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.2f} {unit}"

        value /= 1024

    return f"{value:.2f} GB"


# ---------------------------------------------------------
# Streamlit interface
# ---------------------------------------------------------

def render(st):
    st.title("Export Manager")
    st.caption(
        "Package your AI characters, projects and assets."
    )

    tab_create, tab_history = st.tabs([
        "Create Export",
        "Export History",
    ])

    with tab_create:

        export_type = st.selectbox(
            "Export category",
            [
                "Individual Project",
                "Individual Character",
                "All Assets",
                "All Projects",
            ]
        )

        type_mapping = {
            "Individual Project": "project",
            "Individual Character": "character",
            "All Assets": "assets",
            "All Projects": "projects",
        }

        internal_type = type_mapping[export_type]

        selection = None

        if internal_type == "project":
            projects = list_projects()

            if projects:
                selection = st.selectbox(
                    "Select project",
                    [item["name"] for item in projects]
                )
            else:
                st.warning("No projects found.")

        elif internal_type == "character":
            characters = list_characters()

            if characters:
                selection = st.selectbox(
                    "Select character",
                    [item["name"] for item in characters]
                )
            else:
                st.warning("No characters found.")

        custom_name = st.text_input(
            "Export package name",
            placeholder="My_AI_Influencer_Package"
        )

        st.info(
            "Exports contain persistent project data and assets. "
            "Temporary files, backups and generated output folders "
            "are excluded."
        )

        can_export = (
            internal_type not in {"project", "character"}
            or selection is not None
        )

        if st.button(
            "Generate Export ZIP",
            type="primary",
            use_container_width=True,
            disabled=not can_export,
        ):
            try:
                with st.spinner("Preparing export package..."):

                    result = create_export(
                        export_type=internal_type,
                        selection=selection,
                        custom_name=custom_name or None,
                    )

                valid, message = verify_export(result)

                if not valid:
                    st.error(message)
                else:
                    st.success("Export generated and verified.")

                    st.write(f"File: `{result.name}`")
                    st.write(
                        f"Size: {format_size(result.stat().st_size)}"
                    )

                    with result.open("rb") as file:
                        st.download_button(
                            "Download ZIP Package",
                            data=file.read(),
                            file_name=result.name,
                            mime="application/zip",
                            use_container_width=True,
                        )

            except Exception as error:
                st.error(f"Export failed: {error}")

    with tab_history:

        exports = list_exports()

        if not exports:
            st.info("No export packages available.")
        else:
            st.dataframe(
                [
                    {
                        "Package": item["name"],
                        "Size": format_size(item["size"]),
                        "Created": item["created"],
                    }
                    for item in exports
                ],
                use_container_width=True,
                hide_index=True,
            )

            selected_export = st.selectbox(
                "Inspect export",
                exports,
                format_func=lambda item: item["name"]
            )

            if st.button("Verify Export Integrity"):
                valid, message = verify_export(
                    selected_export["path"]
                )

                if valid:
                    st.success(message)
                else:
                    st.error(message)

            if selected_export:
                with selected_export["path"].open("rb") as file:
                    st.download_button(
                        "Download Selected Export",
                        data=file.read(),
                        file_name=selected_export["name"],
                        mime="application/zip",
                    )

    st.caption(
        f"Export directory: {get_export_dir()}"
    )


# ---------------------------------------------------------
# Built-in tests
# ---------------------------------------------------------

def run_tests():
    import unittest
    from unittest.mock import patch

    class ExportManagerTests(unittest.TestCase):

        def setUp(self):
            self.temp = tempfile.TemporaryDirectory()
            self.root = Path(self.temp.name)

            self.projects = self.root / "projects"
            self.assets = self.root / "assets"
            self.exports = self.root / "exports"

            self.projects.mkdir()
            self.assets.mkdir()
            self.exports.mkdir()

            self.project = self.projects / "Demo Project"
            self.project.mkdir()

            (self.project / "project.json").write_text(
                json.dumps({
                    "name": "Demo Project",
                    "status": "Completed"
                }),
                encoding="utf-8"
            )

            (self.project / "readme.txt").write_text(
                "Demo project content",
                encoding="utf-8"
            )

            character_dir = self.assets / "characters"
            character_dir.mkdir()

            (character_dir / "character.json").write_text(
                json.dumps({
                    "name": "Demo Character",
                    "appearance": "Test appearance"
                }),
                encoding="utf-8"
            )

            (self.assets / "image.png").write_bytes(
                b"test-image"
            )

            self.patches = [
                patch(__name__ + ".get_root", return_value=self.root),
                patch(__name__ + ".get_export_dir", return_value=self.exports),
                patch(__name__ + ".get_project_dir", return_value=self.projects),
                patch(__name__ + ".get_asset_dir", return_value=self.assets),
            ]

            for item in self.patches:
                item.start()

        def tearDown(self):
            for item in self.patches:
                item.stop()

            self.temp.cleanup()

        def test_project_discovery(self):
            projects = list_projects()
            self.assertEqual(len(projects), 1)
            self.assertEqual(projects[0]["name"], "Demo Project")

        def test_character_discovery(self):
            characters = list_characters()
            self.assertEqual(len(characters), 1)
            self.assertEqual(characters[0]["name"], "Demo Character")

        def test_project_export(self):
            archive = create_export(
                "project",
                selection="Demo Project"
            )
            self.assertTrue(archive.exists())

        def test_character_export(self):
            archive = create_export(
                "character",
                selection="Demo Character"
            )
            self.assertTrue(archive.exists())

        def test_asset_export(self):
            archive = create_export("assets")
            self.assertTrue(archive.exists())

        def test_project_collection_export(self):
            archive = create_export("projects")
            self.assertTrue(archive.exists())

        def test_export_verification(self):
            archive = create_export("assets")
            valid, _ = verify_export(archive)
            self.assertTrue(valid)

        def test_manifest_exists(self):
            archive = create_export("assets")

            with zipfile.ZipFile(archive) as zip_file:
                self.assertIn(
                    MANIFEST_NAME,
                    zip_file.namelist()
                )

        def test_unsafe_path_rejected(self):
            with self.assertRaises(ValueError):
                relative_archive_path(
                    self.root / "outside.txt",
                    self.assets
                )

        def test_unsupported_export_rejected(self):
            with self.assertRaises(ValueError):
                create_export("unknown")

        def test_export_history(self):
            create_export("assets")
            self.assertGreaterEqual(len(list_exports()), 1)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        ExportManagerTests
    )

    result = unittest.TextTestRunner(verbosity=2).run(suite)

    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")

    args = parser.parse_args()

    if args.test:
        run_tests()
    else:
        print("Use this module through the Streamlit application.")
        print("Run tests: python -m modules.export_manager --test")
