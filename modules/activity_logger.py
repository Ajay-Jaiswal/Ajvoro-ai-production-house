
"""
AI Influencer Studio
File 24: modules/activity_logger.py

Features:
- Persistent activity logging (JSON Lines)
- Activity categories and severity levels
- Search and filtering
- CSV and JSON export
- Log rotation
- Configurable retention
- Streamlit dashboard
- Built-in tests

Run:
    python -m modules.activity_logger --test

Integration:
    from modules import activity_logger
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
import uuid

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


VALID_LEVELS = {
    "info", "success", "warning", "error"
}

VALID_CATEGORIES = {
    "general",
    "project",
    "character",
    "image",
    "video",
    "voice",
    "motion",
    "workflow",
    "storage",
    "system",
    "settings",
    "export",
    "import",
}

MAX_LOG_SIZE_MB = 5
MAX_LOG_FILES = 5
DEFAULT_RETENTION_DAYS = 90


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_log_path() -> Path:
    """Resolve the activity log file location."""
    try:
        import config

        for name in ("ACTIVITY_LOG_FILE", "ACTIVITY_LOG_PATH"):
            value = getattr(config, name, None)
            if value:
                path = Path(value)
                if not path.is_absolute():
                    path = Path(__file__).resolve().parent.parent / path
                return path

        for name in ("DATA_DIR", "DATA_PATH"):
            value = getattr(config, name, None)
            if value:
                folder = Path(value)
                if not folder.is_absolute():
                    folder = Path(__file__).resolve().parent.parent / folder
                return folder / "activity.jsonl"

    except Exception:
        pass

    return (
        Path(__file__).resolve().parent.parent
        / "data"
        / "activity.jsonl"
    )


def _sanitize_metadata(metadata: Any) -> dict:
    """Ensure metadata can be safely serialized to JSON."""
    if metadata is None:
        return {}

    if not isinstance(metadata, dict):
        raise ValueError("Metadata must be a dictionary.")

    try:
        # Round-trip to remove custom Python objects.
        result = json.loads(json.dumps(metadata, ensure_ascii=False))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Metadata is not JSON serializable: {exc}")

    if not isinstance(result, dict):
        raise ValueError("Metadata must be a JSON object.")

    return result


def _make_record(
    action: str,
    description: str,
    category: str,
    level: str,
    metadata: dict | None = None,
) -> dict:
    if not isinstance(action, str) or not action.strip():
        raise ValueError("Action is required.")

    if not isinstance(description, str) or not description.strip():
        raise ValueError("Description is required.")

    if category not in VALID_CATEGORIES:
        raise ValueError("Invalid activity category.")

    if level not in VALID_LEVELS:
        raise ValueError("Invalid activity level.")

    return {
        "id": uuid.uuid4().hex,
        "timestamp": timestamp(),
        "action": action.strip()[:200],
        "description": description.strip()[:2000],
        "category": category,
        "level": level,
        "metadata": _sanitize_metadata(metadata),
    }


def _rotate_logs(path: Path) -> None:
    """Rotate oversized log files."""
    if not path.exists():
        return

    max_size = MAX_LOG_SIZE_MB * 1024 * 1024

    try:
        if path.stat().st_size < max_size:
            return

        oldest = path.with_name(
            f"{path.name}.{MAX_LOG_FILES}"
        )
        oldest.unlink(missing_ok=True)

        for index in range(MAX_LOG_FILES - 1, 0, -1):
            source = path.with_name(f"{path.name}.{index}")
            destination = path.with_name(f"{path.name}.{index + 1}")

            if source.exists():
                os.replace(source, destination)

        os.replace(path, path.with_name(f"{path.name}.1"))

    except OSError:
        # Logging should not crash the main application.
        pass


def log_activity(
    action: str,
    description: str,
    category: str = "general",
    level: str = "info",
    metadata: dict | None = None,
) -> tuple[bool, dict | str]:
    """Append an activity record to the JSONL log."""
    try:
        record = _make_record(
            action=action,
            description=description,
            category=category,
            level=level,
            metadata=metadata,
        )
    except ValueError as exc:
        return False, str(exc)

    path = get_log_path()

    try:
        path.parent.mkdir(parents=True, exist_ok=True)

        _rotate_logs(path)

        with path.open("a", encoding="utf-8") as file:
            file.write(
                json.dumps(record, ensure_ascii=False) + "\n"
            )
            file.flush()

        return True, record

    except OSError as exc:
        return False, str(exc)


def info(action: str, description: str, category="general", metadata=None):
    return log_activity(
        action, description, category, "info", metadata
    )


def success(action: str, description: str, category="general", metadata=None):
    return log_activity(
        action, description, category, "success", metadata
    )


def warning(action: str, description: str, category="general", metadata=None):
    return log_activity(
        action, description, category, "warning", metadata
    )


def error(action: str, description: str, category="general", metadata=None):
    return log_activity(
        action, description, category, "error", metadata
    )


def _read_file(path: Path) -> list[dict]:
    """Read valid JSONL records from one log file."""
    records = []

    if not path.exists():
        return records

    try:
        with path.open("r", encoding="utf-8") as file:
            for line in file:
                try:
                    item = json.loads(line)

                    if isinstance(item, dict) and item.get("id"):
                        records.append(item)

                except json.JSONDecodeError:
                    continue

    except OSError:
        pass

    return records


def _all_log_files() -> list[Path]:
    path = get_log_path()

    files = [path] if path.exists() else []

    for index in range(1, MAX_LOG_FILES + 1):
        rotated = path.with_name(f"{path.name}.{index}")
        if rotated.exists():
            files.append(rotated)

    return files


def list_activities(
    category: str | None = None,
    level: str | None = None,
    search: str = "",
    limit: int | None = 200,
) -> list[dict]:
    """Return matching activities, newest first."""
    records = []

    for path in _all_log_files():
        records.extend(_read_file(path))

    if category and category != "all":
        records = [
            item for item in records
            if item.get("category") == category
        ]

    if level and level != "all":
        records = [
            item for item in records
            if item.get("level") == level
        ]

    search = search.strip().lower()

    if search:
        filtered = []

        for item in records:
            searchable = " ".join([
                str(item.get("action", "")),
                str(item.get("description", "")),
                str(item.get("category", "")),
                json.dumps(item.get("metadata", {}), ensure_ascii=False),
            ]).lower()

            if search in searchable:
                filtered.append(item)

        records = filtered

    records.sort(
        key=lambda item: str(item.get("timestamp", "")),
        reverse=True,
    )

    if limit is not None:
        records = records[:max(0, int(limit))]

    return records


def get_statistics() -> dict:
    records = list_activities(limit=None)

    result = {
        "total": len(records),
        "levels": {},
        "categories": {},
        "today": 0,
        "errors": 0,
        "warnings": 0,
    }

    today = datetime.now(timezone.utc).date()

    for item in records:
        level = item.get("level", "info")
        category = item.get("category", "general")

        result["levels"][level] = (
            result["levels"].get(level, 0) + 1
        )

        result["categories"][category] = (
            result["categories"].get(category, 0) + 1
        )

        if level == "error":
            result["errors"] += 1

        if level == "warning":
            result["warnings"] += 1

        try:
            event_date = datetime.fromisoformat(
                item["timestamp"].replace("Z", "+00:00")
            ).date()

            if event_date == today:
                result["today"] += 1

        except (ValueError, KeyError, TypeError):
            pass

    return result


def export_json(destination: str | Path) -> tuple[bool, str]:
    """Export all available activity records to JSON."""
    destination = Path(destination)

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)

        records = list_activities(limit=None)

        with destination.open("w", encoding="utf-8") as file:
            json.dump(
                records,
                file,
                indent=4,
                ensure_ascii=False,
            )

        return True, str(destination)

    except OSError as exc:
        return False, str(exc)


def export_csv(destination: str | Path) -> tuple[bool, str]:
    """Export activity records to CSV."""
    destination = Path(destination)

    fields = [
        "id",
        "timestamp",
        "action",
        "description",
        "category",
        "level",
        "metadata",
    ]

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)

        records = list_activities(limit=None)

        with destination.open(
            "w",
            encoding="utf-8-sig",
            newline="",
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=fields,
            )
            writer.writeheader()

            for item in records:
                row = dict(item)
                row["metadata"] = json.dumps(
                    row.get("metadata", {}),
                    ensure_ascii=False,
                )
                writer.writerow({
                    key: row.get(key, "")
                    for key in fields
                })

        return True, str(destination)

    except OSError as exc:
        return False, str(exc)


def cleanup_old_logs(
    retention_days: int = DEFAULT_RETENTION_DAYS,
) -> tuple[bool, int | str]:
    """
    Remove old records from the current log file.

    Rotated files are retained unchanged. Use a backup before cleanup
    if you need to preserve older historical records.
    """
    if isinstance(retention_days, bool) or not isinstance(
        retention_days, int
    ):
        return False, "Retention days must be a whole number."

    if not 1 <= retention_days <= 3650:
        return False, "Retention must be between 1 and 3650 days."

    path = get_log_path()

    if not path.exists():
        return True, 0

    cutoff = datetime.now(timezone.utc) - timedelta(
        days=retention_days
    )

    records = _read_file(path)
    retained = []
    removed = 0

    for item in records:
        try:
            event_time = datetime.fromisoformat(
                item["timestamp"].replace("Z", "+00:00")
            )

            if event_time < cutoff:
                removed += 1
            else:
                retained.append(item)

        except (ValueError, KeyError, TypeError):
            # Preserve records with unrecognized timestamps.
            retained.append(item)

    temp_path = None

    try:
        fd, temp_name = tempfile.mkstemp(
            prefix="activity_cleanup_",
            suffix=".tmp",
            dir=str(path.parent),
        )
        temp_path = Path(temp_name)

        with os.fdopen(fd, "w", encoding="utf-8") as file:
            for item in retained:
                file.write(
                    json.dumps(item, ensure_ascii=False) + "\n"
                )

            file.flush()
            os.fsync(file.fileno())

        os.replace(temp_path, path)
        return True, removed

    except OSError as exc:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)

        return False, str(exc)


def render(st) -> None:
    """Render the Streamlit activity dashboard."""
    st.title("Activity Logger")
    st.caption(
        "Search, review and export your AI Influencer Studio activity."
    )

    stats = get_statistics()

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total activities", stats["total"])
    col2.metric("Today", stats["today"])
    col3.metric("Errors", stats["errors"])
    col4.metric("Warnings", stats["warnings"])

    st.divider()

    tab_history, tab_stats, tab_export, tab_maintenance = st.tabs([
        "Activity History",
        "Statistics",
        "Export",
        "Maintenance",
    ])

    with tab_history:
        col1, col2 = st.columns(2)

        with col1:
            category = st.selectbox(
                "Category",
                ["all"] + sorted(VALID_CATEGORIES),
            )

        with col2:
            level = st.selectbox(
                "Severity",
                ["all"] + sorted(VALID_LEVELS),
            )

        search_text = st.text_input(
            "Search activity",
            placeholder="Search action, description or metadata...",
        )

        limit = st.selectbox(
            "Maximum records",
            [50, 100, 200, 500],
            index=2,
        )

        records = list_activities(
            category=category,
            level=level,
            search=search_text,
            limit=limit,
        )

        st.write(f"Found {len(records)} activities.")

        if not records:
            st.info("No matching activities found.")

        icons = {
            "info": "ℹ️",
            "success": "✅",
            "warning": "⚠️",
            "error": "❌",
        }

        for item in records:
            icon = icons.get(item.get("level"), "ℹ️")

            with st.container(border=True):
                st.markdown(
                    f"**{icon} {item.get('action', 'Activity')}**"
                )

                st.write(item.get("description", ""))

                st.caption(
                    f"{item.get('timestamp', '')} | "
                    f"{item.get('category', '')} | "
                    f"{item.get('level', '')}"
                )

                metadata = item.get("metadata", {})

                if metadata:
                    with st.expander("Activity details"):
                        st.json(metadata)

    with tab_stats:
        st.subheader("Severity breakdown")
        st.json(stats["levels"])

        st.subheader("Category breakdown")
        st.json(stats["categories"])

    with tab_export:
        st.subheader("Export activity history")

        json_name = st.text_input(
            "JSON filename",
            "activity_export.json",
        )

        csv_name = st.text_input(
            "CSV filename",
            "activity_export.csv",
        )

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Export JSON", use_container_width=True):
                ok, result = export_json(json_name)

                if ok:
                    st.success(f"Exported: {result}")
                else:
                    st.error(result)

        with col2:
            if st.button("Export CSV", use_container_width=True):
                ok, result = export_csv(csv_name)

                if ok:
                    st.success(f"Exported: {result}")
                else:
                    st.error(result)

    with tab_maintenance:
        st.subheader("Log maintenance")

        retention = st.number_input(
            "Keep records for (days)",
            min_value=1,
            max_value=3650,
            value=DEFAULT_RETENTION_DAYS,
        )

        st.warning(
            "Cleanup permanently removes old records from the current "
            "log file. Export a backup first."
        )

        if st.button("Clean old activity records"):
            ok, result = cleanup_old_logs(int(retention))

            if ok:
                st.success(f"Removed {result} old records.")
                st.rerun()
            else:
                st.error(str(result))


def run_tests() -> bool:
    """Run isolated tests using temporary files."""
    import unittest
    from unittest.mock import patch

    class ActivityLoggerTests(unittest.TestCase):

        def setUp(self):
            self.temp_dir = tempfile.TemporaryDirectory()

            self.log_file = (
                Path(self.temp_dir.name) / "activity.jsonl"
            )

            self.path_patch = patch(
                __name__ + ".get_log_path",
                return_value=self.log_file,
            )
            self.path_patch.start()

        def tearDown(self):
            self.path_patch.stop()
            self.temp_dir.cleanup()

        def test_create_activity(self):
            ok, record = success(
                "Image generated",
                "Test image created.",
                category="image",
            )

            self.assertTrue(ok)
            self.assertEqual(record["level"], "success")

        def test_persistence(self):
            info("Application started", "Studio opened.")
            records = list_activities()

            self.assertEqual(len(records), 1)

        def test_category_filter(self):
            success("Image", "Generated", category="image")
            info("System", "Started", category="system")

            records = list_activities(category="image")

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["category"], "image")

        def test_level_filter(self):
            success("Success", "Done")
            error("Failure", "Failed")

            records = list_activities(level="error")

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["level"], "error")

        def test_search(self):
            info("Project created", "My first project")

            records = list_activities(search="first project")

            self.assertEqual(len(records), 1)

        def test_statistics(self):
            success("Created", "Image", category="image")
            error("Failed", "Video", category="video")

            stats = get_statistics()

            self.assertEqual(stats["total"], 2)
            self.assertEqual(stats["errors"], 1)
            self.assertEqual(stats["levels"]["success"], 1)

        def test_invalid_category(self):
            ok, message = log_activity(
                "Invalid",
                "Test",
                category="unknown",
            )

            self.assertFalse(ok)

        def test_invalid_level(self):
            ok, message = log_activity(
                "Invalid",
                "Test",
                level="unknown",
            )

            self.assertFalse(ok)

        def test_empty_action(self):
            ok, message = log_activity(
                "",
                "Description",
            )

            self.assertFalse(ok)

        def test_metadata_validation(self):
            ok, message = log_activity(
                "Invalid metadata",
                "Test",
                metadata={"object": object()},
            )

            self.assertFalse(ok)

        def test_json_export(self):
            info("Export test", "JSON export")

            destination = (
                Path(self.temp_dir.name) / "export.json"
            )

            ok, result = export_json(destination)

            self.assertTrue(ok, result)
            self.assertTrue(destination.exists())

            data = json.loads(
                destination.read_text(encoding="utf-8")
            )

            self.assertEqual(len(data), 1)

        def test_csv_export(self):
            info("Export test", "CSV export")

            destination = (
                Path(self.temp_dir.name) / "export.csv"
            )

            ok, result = export_csv(destination)

            self.assertTrue(ok, result)
            self.assertTrue(destination.exists())

            with destination.open(
                encoding="utf-8-sig",
                newline="",
            ) as file:
                rows = list(csv.DictReader(file))

            self.assertEqual(len(rows), 1)

        def test_cleanup(self):
            old_record = {
                "id": "old-record",
                "timestamp": "2020-01-01T00:00:00+00:00",
                "action": "Old activity",
                "description": "Old record",
                "category": "general",
                "level": "info",
                "metadata": {},
            }

            self.log_file.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            self.log_file.write_text(
                json.dumps(old_record) + "\n",
                encoding="utf-8",
            )

            ok, removed = cleanup_old_logs(30)

            self.assertTrue(ok)
            self.assertEqual(removed, 1)
            self.assertEqual(len(list_activities()), 0)

        def test_limit(self):
            for index in range(5):
                info(f"Activity {index}", "Test")

            records = list_activities(limit=2)

            self.assertEqual(len(records), 2)

        def test_rotated_log_reading(self):
            info("Current", "Current log")

            rotated = self.log_file.with_name(
                self.log_file.name + ".1"
            )

            old = {
                "id": "rotated-1",
                "timestamp": timestamp(),
                "action": "Rotated activity",
                "description": "Previous log",
                "category": "general",
                "level": "info",
                "metadata": {},
            }

            rotated.write_text(
                json.dumps(old) + "\n",
                encoding="utf-8",
            )

            records = list_activities(limit=None)

            self.assertEqual(len(records), 2)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        ActivityLoggerTests
    )

    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AI Influencer Studio Activity Logger"
    )

    parser.add_argument(
        "--test",
        action="store_true",
        help="Run built-in tests",
    )

    args = parser.parse_args()

    if args.test:
        raise SystemExit(0 if run_tests() else 1)

    print("Activity Logger loaded.")
    print("Run with --test to execute built-in tests.")
