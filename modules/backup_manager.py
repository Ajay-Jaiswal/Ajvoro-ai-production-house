
"""
AI Influencer Studio - Backup & Restore Manager
File 19

Features:
- ZIP backups of persistent assets, projects and database
- SQLite-consistent database snapshots
- Backup listing and integrity verification
- Safe, confirmed restore
- ZIP path traversal protection
- Excludes output, temp and backup folders
- Streamlit interface
- Built-in unit tests

Run tests:
    python -m modules.backup_manager --test
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile

from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


APP_ROOT = Path(__file__).resolve().parent.parent

EXCLUDED_DIRS = {
    "output",
    "temp",
    "backups",
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "node_modules",
}

ALLOWED_RESTORE_ROOTS = {
    "assets",
    "projects",
    "database",
}

MANIFEST_NAME = "backup_manifest.json"


def _load_config() -> Any:
    try:
        import config
        return config
    except ImportError:
        return None


def _configured_path(names: tuple[str, ...]) -> Path | None:
    """Find a configured path without requiring a particular config schema."""
    cfg = _load_config()

    if cfg is None:
        return None

    for name in names:
        value = getattr(cfg, name, None)

        if value:
            try:
                path = Path(value).expanduser()
                if not path.is_absolute():
                    path = APP_ROOT / path
                return path.resolve()
            except (TypeError, ValueError, OSError):
                continue

    return None


def get_base_dir() -> Path:
    return (
        _configured_path(
            ("BASE_DIR", "APP_DIR", "PROJECT_ROOT", "ROOT_DIR")
        )
        or APP_ROOT
    )


def get_backup_dir() -> Path:
    configured = _configured_path(
        ("BACKUP_DIR", "BACKUPS_DIR")
    )

    return configured or (get_base_dir() / "backups")


def get_persistent_targets() -> list[Path]:
    """
    Identify persistent folders and database files.

    Only paths inside the application root are included.
    Temporary and generated-output folders are excluded.
    """
    root = get_base_dir()

    candidates = [
        _configured_path(("ASSETS_DIR", "ASSET_DIR")),
        _configured_path(("PROJECTS_DIR", "PROJECT_DIR")),
        _configured_path(("DATABASE_DIR", "DB_DIR")),
        _configured_path(
            ("DB_PATH", "DATABASE_PATH", "SQLITE_DB_PATH")
        ),
        root / "assets",
        root / "projects",
        root / "database",
    ]

    targets = []
    seen = set()

    for candidate in candidates:
        if candidate is None:
            continue

        try:
            path = candidate.resolve()
            path.relative_to(root.resolve())

            if path == root or any(
                part.lower() in EXCLUDED_DIRS
                for part in path.relative_to(root).parts
            ):
                continue

            if not path.exists() or path in seen:
                continue

            seen.add(path)
            targets.append(path)

        except (ValueError, OSError):
            continue

    return targets


def _is_excluded(path: Path) -> bool:
    return any(
        part.lower() in EXCLUDED_DIRS
        for part in path.parts
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def _sqlite_snapshot(source: Path, destination: Path) -> None:
    """Create a consistent SQLite snapshot using SQLite's backup API."""
    source_connection = sqlite3.connect(str(source), timeout=10)
    destination_connection = sqlite3.connect(str(destination))

    try:
        source_connection.backup(destination_connection)
    finally:
        destination_connection.close()
        source_connection.close()


def _collect_files() -> list[Path]:
    files = []

    for target in get_persistent_targets():
        if target.is_file():
            if not _is_excluded(target):
                files.append(target)
            continue

        for path in target.rglob("*"):
            if not path.is_file():
                continue

            if _is_excluded(path):
                continue

            if path.suffix.lower() in {".pyc", ".pyo"}:
                continue

            files.append(path)

    return sorted(set(files))


def create_backup(name: str | None = None) -> Path:
    """Create an atomic ZIP backup of persistent application data."""
    root = get_base_dir()
    backup_dir = get_backup_dir()

    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    safe_name = "".join(
        c for c in (name or "studio_backup")
        if c.isalnum() or c in ("-", "_")
    ).strip("_-") or "studio_backup"

    destination = backup_dir / f"{safe_name}_{timestamp}.zip"
    temporary_zip = backup_dir / f".{destination.stem}.tmp"

    manifest = {
        "application": "AI Influencer Studio",
        "version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": [],
    }

    try:
        with tempfile.TemporaryDirectory(
            prefix="influencer_backup_"
        ) as temp_dir:

            temp_root = Path(temp_dir)

            with zipfile.ZipFile(
                temporary_zip,
                "w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=4,
            ) as archive:

                for source in _collect_files():
                    relative = source.relative_to(root)

                    if _is_excluded(relative):
                        continue

                    archive_name = (
                        PurePosixPath("persistent")
                        / PurePosixPath(relative.as_posix())
                    )

                    archive_source = source

                    if source.suffix.lower() in {
                        ".db", ".sqlite", ".sqlite3"
                    }:
                        snapshot = (
                            temp_root
                            / f"{len(manifest['files'])}_{source.name}"
                        )

                        try:
                            _sqlite_snapshot(source, snapshot)
                            archive_source = snapshot
                        except sqlite3.Error:
                            # Skip an unavailable database rather than
                            # creating a potentially inconsistent copy.
                            continue

                    archive.write(
                        archive_source,
                        archive_name.as_posix(),
                    )

                    manifest["files"].append({
                        "path": archive_name.as_posix(),
                        "size": archive_source.stat().st_size,
                        "sha256": _sha256(archive_source),
                    })

                archive.writestr(
                    MANIFEST_NAME,
                    json.dumps(manifest, indent=2),
                )

        temporary_zip.replace(destination)

        return destination

    except Exception:
        temporary_zip.unlink(missing_ok=True)
        raise


def list_backups() -> list[dict]:
    """Return backup metadata sorted newest first."""
    backup_dir = get_backup_dir()

    if not backup_dir.exists():
        return []

    results = []

    for path in backup_dir.glob("*.zip"):
        try:
            stat = path.stat()

            results.append({
                "name": path.name,
                "path": path,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(
                    stat.st_mtime
                ),
            })
        except OSError:
            continue

    return sorted(
        results,
        key=lambda item: item["modified"],
        reverse=True,
    )


def verify_backup(backup_path: str | Path) -> tuple[bool, str]:
    """Check ZIP integrity, manifest and archived file hashes."""
    path = Path(backup_path)

    if not path.is_file():
        return False, "Backup file does not exist."

    try:
        with zipfile.ZipFile(path, "r") as archive:
            bad_file = archive.testzip()

            if bad_file:
                return False, f"Corrupt archive entry: {bad_file}"

            names = archive.namelist()

            if MANIFEST_NAME not in names:
                return False, "Backup manifest is missing."

            manifest = json.loads(
                archive.read(MANIFEST_NAME).decode("utf-8")
            )

            for item in manifest.get("files", []):
                name = item.get("path", "")

                if name not in names:
                    return False, f"Missing file: {name}"

                content = archive.read(name)
                digest = hashlib.sha256(content).hexdigest()

                if digest != item.get("sha256"):
                    return False, f"Hash mismatch: {name}"

        return True, "Backup integrity verified successfully."

    except (
        zipfile.BadZipFile,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
    ) as error:
        return False, f"Verification failed: {error}"


def _safe_restore_destination(
    archive_name: str,
    root: Path,
) -> Path | None:
    """Reject absolute paths, traversal and unapproved directories."""
    try:
        relative = PurePosixPath(archive_name)

        if relative.is_absolute():
            return None

        if ".." in relative.parts or not relative.parts:
            return None

        if relative.parts[0] != "persistent":
            return None

        if len(relative.parts) < 2:
            return None

        if relative.parts[1] not in ALLOWED_RESTORE_ROOTS:
            return None

        destination = root.joinpath(*relative.parts[1:]).resolve()

        destination.relative_to(root.resolve())

        return destination

    except (ValueError, OSError):
        return None


def restore_backup(
    backup_path: str | Path,
    confirmed: bool = False,
) -> tuple[bool, str]:
    """
    Restore persistent data from a verified backup.

    Existing files may be overwritten. Callers must explicitly confirm.
    """
    if not confirmed:
        return False, "Explicit restore confirmation is required."

    valid, message = verify_backup(backup_path)

    if not valid:
        return False, message

    root = get_base_dir()
    restored = 0

    try:
        with zipfile.ZipFile(backup_path, "r") as archive:

            manifest = json.loads(
                archive.read(MANIFEST_NAME).decode("utf-8")
            )

            for item in manifest.get("files", []):
                name = item.get("path", "")
                destination = _safe_restore_destination(name, root)

                if destination is None:
                    return False, f"Unsafe archive path rejected: {name}"

                destination.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                with archive.open(name, "r") as source:
                    with destination.open("wb") as target:
                        shutil.copyfileobj(source, target)

                restored += 1

        return True, f"Successfully restored {restored} files."

    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        return False, f"Restore failed: {error}"


def format_size(size: int) -> str:
    """Human-readable file size."""
    value = float(size)

    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.2f} {unit}"
        value /= 1024

    return f"{value:.2f} GB"


def render(st) -> None:
    """Render the Backup & Restore Streamlit page."""
    st.title("Backup & Restore Manager")
    st.caption(
        "Protect your AI Influencer Studio projects, assets and database."
    )

    tab_backup, tab_restore, tab_info = st.tabs([
        "Create Backup",
        "Restore Backup",
        "Backup Information",
    ])

    with tab_backup:
        st.subheader("Create a new backup")

        backup_name = st.text_input(
            "Backup name",
            value="studio_backup",
            max_chars=50,
        )

        targets = get_persistent_targets()

        st.write("Persistent data sources:")

        if targets:
            for target in targets:
                st.write(f"- `{target}`")
        else:
            st.warning("No persistent data folders found yet.")

        if st.button(
            "Create ZIP Backup",
            type="primary",
            use_container_width=True,
        ):
            try:
                with st.spinner("Creating backup..."):
                    result = create_backup(backup_name)

                st.success("Backup created successfully.")
                st.code(str(result))
                st.write(
                    f"Backup size: {format_size(result.stat().st_size)}"
                )

            except Exception as error:
                st.error(f"Backup creation failed: {error}")

    with tab_restore:
        st.subheader("Available backups")

        backups = list_backups()

        if not backups:
            st.info("No backups found.")
        else:
            selected = st.selectbox(
                "Select backup",
                backups,
                format_func=lambda item: item["name"],
            )

            if selected:
                st.write(f"Size: {format_size(selected['size'])}")
                st.write(
                    f"Created: {selected['modified'].strftime('%Y-%m-%d %H:%M:%S')}"
                )

                if st.button("Verify Selected Backup"):
                    valid, message = verify_backup(selected["path"])

                    if valid:
                        st.success(message)
                    else:
                        st.error(message)

                st.warning(
                    "Restoring may overwrite existing project, asset "
                    "and database files. Create a current backup first."
                )

                confirmation = st.text_input(
                    'Type RESTORE to confirm',
                    key="backup_restore_confirmation",
                )

                if st.button(
                    "Restore Selected Backup",
                    type="primary",
                    disabled=confirmation != "RESTORE",
                ):
                    try:
                        with st.spinner("Restoring data..."):
                            success, message = restore_backup(
                                selected["path"],
                                confirmed=True,
                            )

                        if success:
                            st.success(message)
                            st.info(
                                "Restart the application if database "
                                "or project data was restored."
                            )
                        else:
                            st.error(message)

                    except Exception as error:
                        st.error(f"Restore failed: {error}")

    with tab_info:
        st.subheader("Backup statistics")

        backups = list_backups()

        total_size = sum(
            item["size"] for item in backups
        )

        col1, col2, col3 = st.columns(3)

        col1.metric("Total Backups", len(backups))
        col2.metric("Total Size", format_size(total_size))
        col3.metric(
            "Latest Backup",
            backups[0]["modified"].strftime("%d %b %Y")
            if backups else "Not available",
        )

        st.markdown("### Backup policies")

        st.write("- Assets and projects are included.")
        st.write("- Database files receive SQLite snapshots.")
        st.write("- Temporary files are excluded.")
        st.write("- Generated output videos are excluded.")
        st.write("- Existing data can be overwritten during restore.")

        st.markdown("### Backup location")
        st.code(str(get_backup_dir()))


# ---------------------------------------------------------
# Built-in tests
# ---------------------------------------------------------

def run_tests() -> None:
    """Run isolated backup and restore tests."""
    import unittest
    from unittest.mock import patch

    class BackupManagerTests(unittest.TestCase):

        def setUp(self):
            self.temp = tempfile.TemporaryDirectory()
            self.root = Path(self.temp.name)

            self.assets = self.root / "assets"
            self.projects = self.root / "projects"
            self.database = self.root / "database"
            self.output = self.root / "output"
            self.temp_dir = self.root / "temp"
            self.backups = self.root / "backups"

            for folder in (
                self.assets,
                self.projects,
                self.database,
                self.output,
                self.temp_dir,
                self.backups,
            ):
                folder.mkdir(parents=True)

            (self.assets / "character.txt").write_text(
                "Test character",
                encoding="utf-8",
            )

            (self.projects / "project.json").write_text(
                '{"name": "Test Project"}',
                encoding="utf-8",
            )

            (self.output / "video.mp4").write_text(
                "Generated output",
                encoding="utf-8",
            )

            self.database_file = self.database / "test.db"

            connection = sqlite3.connect(self.database_file)
            connection.execute(
                "CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)"
            )
            connection.execute(
                "INSERT INTO test(value) VALUES ('backup-test')"
            )
            connection.commit()
            connection.close()

            self.patches = [
                patch(
                    __name__ + ".get_base_dir",
                    return_value=self.root,
                ),
                patch(
                    __name__ + ".get_backup_dir",
                    return_value=self.backups,
                ),
                patch(
                    __name__ + ".get_persistent_targets",
                    return_value=[
                        self.assets,
                        self.projects,
                        self.database,
                        self.output,
                        self.temp_dir,
                    ],
                ),
            ]

            for item in self.patches:
                item.start()

        def tearDown(self):
            for item in self.patches:
                item.stop()

            self.temp.cleanup()

        def test_backup_creation(self):
            backup = create_backup()
            self.assertTrue(backup.exists())

        def test_backup_verification(self):
            backup = create_backup()
            valid, _ = verify_backup(backup)
            self.assertTrue(valid)

        def test_temporary_output_excluded(self):
            backup = create_backup()

            with zipfile.ZipFile(backup) as archive:
                names = archive.namelist()

            self.assertFalse(
                any("/output/" in name for name in names)
            )
            self.assertFalse(
                any("/temp/" in name for name in names)
            )

        def test_sqlite_snapshot(self):
            backup = create_backup()

            with zipfile.ZipFile(backup) as archive:
                database_name = (
                    "persistent/database/test.db"
                )
                content = archive.read(database_name)

            snapshot = self.root / "snapshot.db"
            snapshot.write_bytes(content)

            connection = sqlite3.connect(snapshot)

            result = connection.execute(
                "SELECT value FROM test"
            ).fetchone()

            connection.close()

            self.assertEqual(result[0], "backup-test")

        def test_restore_requires_confirmation(self):
            backup = create_backup()

            success, _ = restore_backup(
                backup,
                confirmed=False,
            )

            self.assertFalse(success)

        def test_restore_data(self):
            backup = create_backup()

            (self.assets / "character.txt").write_text(
                "Changed",
                encoding="utf-8",
            )

            success, _ = restore_backup(
                backup,
                confirmed=True,
            )

            self.assertTrue(success)

            content = (
                self.assets / "character.txt"
            ).read_text(encoding="utf-8")

            self.assertEqual(content, "Test character")

        def test_path_traversal_rejected(self):
            result = _safe_restore_destination(
                "persistent/assets/../../outside.txt",
                self.root,
            )

            self.assertIsNone(result)

        def test_invalid_archive(self):
            invalid = self.backups / "invalid.zip"
            invalid.write_text("not a zip", encoding="utf-8")

            valid, _ = verify_backup(invalid)

            self.assertFalse(valid)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        BackupManagerTests
    )

    result = unittest.TextTestRunner(verbosity=2).run(suite)

    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AI Influencer Studio Backup Manager"
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
        print("Use this module through the Streamlit application.")
        print("Run tests: python -m modules.backup_manager --test")
