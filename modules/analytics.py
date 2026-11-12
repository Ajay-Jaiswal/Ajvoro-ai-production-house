
"""
AI Influencer Studio
File 18: modules/analytics.py

Lightweight local analytics dashboard.

Integrates optionally with:
- config.py
- database.py
- storage.py
- project_manager.py

Run:
    streamlit run app.py

Test:
    python -m modules.analytics --test
"""

from __future__ import annotations

import argparse
import json
import sqlite3

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


APP_ROOT = Path(__file__).resolve().parent.parent

EXCLUDED_DIRS = {
    "__pycache__", ".git", ".venv", "venv",
    "node_modules", "backups", "temp"
}


# ---------------------------------------------------------
# Configuration and paths
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


def get_paths():
    root = configured_path(
        ("BASE_DIR", "APP_DIR", "PROJECT_ROOT"),
        APP_ROOT
    )

    return {
        "root": root,
        "assets": configured_path(
            ("ASSETS_DIR", "ASSET_DIR"),
            root / "assets"
        ),
        "projects": configured_path(
            ("PROJECTS_DIR", "PROJECT_DIR"),
            root / "projects"
        ),
        "database": configured_path(
            ("DATABASE_DIR", "DB_DIR"),
            root / "database"
        ),
        "output": configured_path(
            ("OUTPUT_DIR", "GENERATED_DIR"),
            root / "output"
        ),
    }


# ---------------------------------------------------------
# File and storage statistics
# ---------------------------------------------------------

def scan_directory(directory: Path) -> dict:
    """Calculate directory size and file statistics."""

    result = {
        "files": 0,
        "folders": 0,
        "size": 0,
        "extensions": Counter(),
        "recent": [],
    }

    if not directory.exists():
        return result

    for path in directory.rglob("*"):
        try:
            if any(part.lower() in EXCLUDED_DIRS for part in path.parts):
                continue

            if path.is_dir():
                result["folders"] += 1
                continue

            if not path.is_file():
                continue

            stat = path.stat()

            result["files"] += 1
            result["size"] += stat.st_size

            extension = path.suffix.lower() or "no extension"
            result["extensions"][extension] += 1

            result["recent"].append({
                "name": path.name,
                "path": str(path),
                "modified": datetime.fromtimestamp(
                    stat.st_mtime
                ),
                "size": stat.st_size,
            })

        except (OSError, PermissionError):
            continue

    result["recent"].sort(
        key=lambda item: item["modified"],
        reverse=True
    )

    return result


def format_size(size: int) -> str:
    value = float(size)

    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.2f} {unit}"
        value /= 1024

    return "0 B"


# ---------------------------------------------------------
# Project analytics
# ---------------------------------------------------------

def read_project_metadata(project_path: Path) -> dict:
    """Read common project metadata JSON files."""

    candidates = [
        project_path / "project.json",
        project_path / "metadata.json",
        project_path / "config.json",
    ]

    for file_path in candidates:
        if file_path.is_file():
            try:
                data = json.loads(
                    file_path.read_text(encoding="utf-8")
                )

                if isinstance(data, dict):
                    return data

            except (OSError, json.JSONDecodeError):
                continue

    return {}


def collect_projects(project_dir: Path) -> list[dict]:
    projects = []

    if not project_dir.exists():
        return projects

    for path in project_dir.iterdir():
        if not path.is_dir():
            continue

        if path.name.lower() in EXCLUDED_DIRS:
            continue

        metadata = read_project_metadata(path)

        status = str(
            metadata.get("status", "Unknown")
        ).strip() or "Unknown"

        projects.append({
            "name": metadata.get("name", path.name),
            "status": status,
            "path": str(path),
            "created": metadata.get(
                "created_at",
                metadata.get("created", "Unknown")
            ),
            "updated": metadata.get(
                "updated_at",
                metadata.get("updated", "Unknown")
            ),
        })

    return projects


# ---------------------------------------------------------
# Character analytics
# ---------------------------------------------------------

def collect_characters(asset_dir: Path) -> list[dict]:
    """Find saved character metadata in common JSON formats."""

    characters = []

    if not asset_dir.exists():
        return characters

    for file_path in asset_dir.rglob("*.json"):
        try:
            if any(
                part.lower() in EXCLUDED_DIRS
                for part in file_path.parts
            ):
                continue

            data = json.loads(
                file_path.read_text(encoding="utf-8")
            )

            if not isinstance(data, dict):
                continue

            # Avoid counting unrelated project metadata.
            is_character = (
                "character" in file_path.parent.name.lower()
                or "character" in file_path.stem.lower()
                or "character_name" in data
                or (
                    "name" in data
                    and any(
                        key in data
                        for key in ("appearance", "personality", "identity")
                    )
                )
            )

            if is_character:
                characters.append({
                    "name": data.get(
                        "name",
                        data.get(
                            "character_name",
                            file_path.stem
                        )
                    ),
                    "path": str(file_path),
                    "updated": datetime.fromtimestamp(
                        file_path.stat().st_mtime
                    ),
                })

        except (OSError, json.JSONDecodeError):
            continue

    return characters


# ---------------------------------------------------------
# Database analytics
# ---------------------------------------------------------

def get_database_path() -> Path | None:
    candidates = [
        configured_path(
            ("DB_PATH", "DATABASE_PATH", "SQLITE_DB_PATH")
        ),
        APP_ROOT / "database" / "studio.db",
        APP_ROOT / "database" / "app.db",
        APP_ROOT / "studio.db",
        APP_ROOT / "app.db",
    ]

    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate

    return None


def database_statistics() -> dict:
    """Inspect SQLite tables and row counts without changing data."""

    result = {
        "available": False,
        "tables": {},
        "total_records": 0,
        "error": None,
    }

    database_path = get_database_path()

    if not database_path:
        return result

    connection = None

    try:
        connection = sqlite3.connect(
            f"file:{database_path.as_posix()}?mode=ro",
            uri=True,
            timeout=5
        )

        tables = connection.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            AND name NOT LIKE 'sqlite_%'
        """).fetchall()

        for (table,) in tables:
            # Table names originate from SQLite metadata.
            safe_table = table.replace('"', '""')

            count = connection.execute(
                f'SELECT COUNT(*) FROM "{safe_table}"'
            ).fetchone()[0]

            result["tables"][table] = count
            result["total_records"] += count

        result["available"] = True

    except sqlite3.Error as error:
        result["error"] = str(error)

    finally:
        if connection:
            connection.close()

    return result


# ---------------------------------------------------------
# Complete analytics data
# ---------------------------------------------------------

def collect_analytics() -> dict:
    paths = get_paths()

    assets = scan_directory(paths["assets"])
    projects_storage = scan_directory(paths["projects"])
    outputs = scan_directory(paths["output"])

    projects = collect_projects(paths["projects"])
    characters = collect_characters(paths["assets"])

    combined_extensions = (
        assets["extensions"] +
        projects_storage["extensions"] +
        outputs["extensions"]
    )

    recent_activity = sorted(
        assets["recent"]
        + projects_storage["recent"]
        + outputs["recent"],
        key=lambda item: item["modified"],
        reverse=True
    )[:20]

    statuses = Counter(
        project["status"] for project in projects
    )

    return {
        "characters": characters,
        "total_characters": len(characters),

        "projects": projects,
        "total_projects": len(projects),
        "project_status": dict(statuses),

        "assets": assets,
        "total_assets": assets["files"],

        "outputs": outputs,
        "total_outputs": outputs["files"],

        "storage": {
            "assets": assets["size"],
            "projects": projects_storage["size"],
            "outputs": outputs["size"],
            "total": (
                assets["size"]
                + projects_storage["size"]
                + outputs["size"]
            ),
        },

        "file_types": dict(combined_extensions),

        "recent_activity": recent_activity,

        "database": database_statistics(),

        "generated_at": datetime.now(),
    }


# ---------------------------------------------------------
# Streamlit dashboard
# ---------------------------------------------------------

def render(st):
    st.title("AI Influencer Studio Analytics")
    st.caption("Local project, character and asset analytics")

    if st.button("Refresh Analytics", use_container_width=True):
        st.rerun()

    try:
        data = collect_analytics()

    except Exception as error:
        st.error(f"Analytics error: {error}")
        return

    st.markdown("### Studio Overview")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Characters", data["total_characters"])
    c2.metric("Projects", data["total_projects"])
    c3.metric("Assets", data["total_assets"])
    c4.metric("Generated Outputs", data["total_outputs"])

    st.divider()

    st.markdown("### Storage Overview")

    storage = data["storage"]

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Total Storage", format_size(storage["total"]))
    c2.metric("Assets", format_size(storage["assets"]))
    c3.metric("Projects", format_size(storage["projects"]))
    c4.metric("Outputs", format_size(storage["outputs"]))

    st.divider()

    st.markdown("### Project Status")

    if data["project_status"]:
        import pandas as pd

        status_df = pd.DataFrame(
            list(data["project_status"].items()),
            columns=["Status", "Projects"]
        )

        st.bar_chart(
            status_df.set_index("Status")
        )
    else:
        st.info("No project data available.")

    st.markdown("### File Type Breakdown")

    if data["file_types"]:
        import pandas as pd

        type_df = pd.DataFrame(
            list(data["file_types"].items()),
            columns=["File Type", "Count"]
        ).sort_values("Count", ascending=False)

        st.bar_chart(
            type_df.set_index("File Type")
        )
    else:
        st.info("No files found.")

    st.divider()

    st.markdown("### Saved Characters")

    if data["characters"]:
        st.dataframe(
            [
                {
                    "Character": item["name"],
                    "Last Updated": item["updated"],
                    "Location": item["path"],
                }
                for item in data["characters"]
            ],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No character metadata detected.")

    st.markdown("### Projects")

    if data["projects"]:
        st.dataframe(
            [
                {
                    "Project": item["name"],
                    "Status": item["status"],
                    "Created": item["created"],
                    "Updated": item["updated"],
                }
                for item in data["projects"]
            ],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No saved projects detected.")

    st.divider()

    st.markdown("### Recent Activity")

    if data["recent_activity"]:
        st.dataframe(
            [
                {
                    "File": item["name"],
                    "Modified": item["modified"],
                    "Size": format_size(item["size"]),
                    "Location": item["path"],
                }
                for item in data["recent_activity"]
            ],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No recent file activity found.")

    st.divider()

    st.markdown("### Database Statistics")

    db = data["database"]

    if db["available"]:
        st.metric("Total Database Records", db["total_records"])

        st.dataframe(
            [
                {"Table": name, "Records": count}
                for name, count in db["tables"].items()
            ],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No accessible SQLite database detected.")

        if db["error"]:
            st.caption(db["error"])

    st.caption(
        f"Last refreshed: {data['generated_at']:%Y-%m-%d %H:%M:%S}"
    )


# ---------------------------------------------------------
# Built-in tests
# ---------------------------------------------------------

def run_tests():
    import tempfile
    import unittest
    from unittest.mock import patch

    class AnalyticsTests(unittest.TestCase):

        def setUp(self):
            self.temp = tempfile.TemporaryDirectory()
            self.root = Path(self.temp.name)

            self.assets = self.root / "assets"
            self.projects = self.root / "projects"
            self.output = self.root / "output"
            self.database = self.root / "database"

            for directory in (
                self.assets,
                self.projects,
                self.output,
                self.database
            ):
                directory.mkdir(parents=True)

            self.character_dir = self.assets / "characters"
            self.character_dir.mkdir()

            (self.character_dir / "character.json").write_text(
                json.dumps({
                    "name": "Test Avatar",
                    "appearance": "Fictional character"
                }),
                encoding="utf-8"
            )

            project = self.projects / "Test Project"
            project.mkdir()

            (project / "project.json").write_text(
                json.dumps({
                    "name": "Test Project",
                    "status": "Completed"
                }),
                encoding="utf-8"
            )

            (self.assets / "image.png").write_bytes(b"test-image")
            (self.output / "video.mp4").write_bytes(b"test-video")

            self.db_path = self.database / "studio.db"

            connection = sqlite3.connect(self.db_path)
            connection.execute(
                "CREATE TABLE characters (id INTEGER PRIMARY KEY)"
            )
            connection.execute(
                "INSERT INTO characters DEFAULT VALUES"
            )
            connection.commit()
            connection.close()

            self.patches = [
                patch(
                    __name__ + ".get_paths",
                    return_value={
                        "root": self.root,
                        "assets": self.assets,
                        "projects": self.projects,
                        "output": self.output,
                        "database": self.database,
                    }
                ),
                patch(
                    __name__ + ".get_database_path",
                    return_value=self.db_path
                )
            ]

            for item in self.patches:
                item.start()

        def tearDown(self):
            for item in self.patches:
                item.stop()

            self.temp.cleanup()

        def test_directory_scan(self):
            result = scan_directory(self.assets)
            self.assertGreater(result["files"], 0)

        def test_storage_size(self):
            result = scan_directory(self.assets)
            self.assertGreater(result["size"], 0)

        def test_project_collection(self):
            result = collect_projects(self.projects)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["status"], "Completed")

        def test_character_collection(self):
            result = collect_characters(self.assets)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["name"], "Test Avatar")

        def test_database_statistics(self):
            result = database_statistics()
            self.assertTrue(result["available"])
            self.assertEqual(result["total_records"], 1)

        def test_format_size(self):
            self.assertEqual(format_size(1024), "1.00 KB")

        def test_analytics_structure(self):
            result = collect_analytics()
            self.assertIn("total_projects", result)
            self.assertIn("total_characters", result)
            self.assertIn("storage", result)
            self.assertIn("database", result)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        AnalyticsTests
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
        print("Use analytics through the Streamlit application.")
        print("Test: python -m modules.analytics --test")
