
"""
File 65: modules/final_workflow_integration.py

AI Influencer Studio - Final Workflow Integration

Features:
- Central workflow dashboard
- Independent module availability checks
- Safe optional imports
- Record count summaries
- Batch generation statistics
- Recent workflow overview
- Independent error handling
- Streamlit dashboard
- Built-in tests

Run:
    python -m modules.final_workflow_integration --test
"""

from __future__ import annotations

import importlib
import json
import tempfile

from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------
# PATH CONFIGURATION
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs" / "workflow_integration"

for folder in (DATA_DIR, OUTPUT_DIR):
    folder.mkdir(parents=True, exist_ok=True)

SNAPSHOT_FILE = DATA_DIR / "workflow_integration.json"


# ---------------------------------------------------------
# MODULE REGISTRY
# ---------------------------------------------------------

MODULE_REGISTRY = {
    "project_manager": {
        "name": "Project Manager",
        "description": "Manage studio projects"
    },
    "analytics": {
        "name": "Analytics",
        "description": "Studio statistics and analytics"
    },
    "character_identity_manager": {
        "name": "Character Identity Manager",
        "description": "Manage character identity profiles"
    },
    "character_reference_library": {
        "name": "Character Reference Library",
        "description": "Manage character reference images"
    },
    "image_generation_manager": {
        "name": "Image Generation Manager",
        "description": "Prepare and track image jobs"
    },
    "video_generation_manager": {
        "name": "Video Generation Manager",
        "description": "Prepare and track video jobs"
    },
    "face_consistency_checker": {
        "name": "Face Consistency Checker",
        "description": "Compare reference and generated images"
    },
    "outfit_consistency_manager": {
        "name": "Outfit Consistency Manager",
        "description": "Manage character outfit continuity"
    },
    "voice_profile_manager": {
        "name": "Voice Profile Manager",
        "description": "Manage voice profiles"
    },
    "lip_sync_manager": {
        "name": "Lip-Sync Manager",
        "description": "Manage lip-sync jobs"
    },
    "batch_generation_manager": {
        "name": "Batch Generation Manager",
        "description": "Manage generation batches"
    },
    "script_writer": {
        "name": "Script Writer",
        "description": "Write and manage scripts"
    },
    "storyboard_manager": {
        "name": "Storyboard Manager",
        "description": "Manage scenes and storyboards"
    },
    "scene_prompt_generator": {
        "name": "Scene Prompt Generator",
        "description": "Create scene prompts"
    }
}


# ---------------------------------------------------------
# GENERAL HELPERS
# ---------------------------------------------------------

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None

    try:
        return json.loads(
            path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return None


def save_snapshot(
    snapshot: dict,
    output_path: Path | None = None
) -> Path:
    path = output_path or SNAPSHOT_FILE

    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_suffix(".tmp")

    temporary.write_text(
        json.dumps(
            snapshot,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    temporary.replace(path)

    return path


def load_snapshot(
    input_path: Path | None = None
) -> dict:
    path = input_path or SNAPSHOT_FILE

    data = _read_json(path)

    if isinstance(data, dict):
        return data

    return {
        "created_at": None,
        "modules": {},
        "statistics": {}
    }


# ---------------------------------------------------------
# SAFE MODULE IMPORT
# ---------------------------------------------------------

def load_module_safely(module_name: str) -> dict:
    """
    Import one module independently.

    A failed import must not prevent other modules
    from being inspected.
    """

    result = {
        "module": module_name,
        "available": False,
        "has_renderer": False,
        "module_object": None,
        "error": None
    }

    try:
        module = importlib.import_module(
            f"modules.{module_name}"
        )

        result["available"] = True
        result["has_renderer"] = callable(
            getattr(module, "render", None)
        )
        result["module_object"] = module

    except Exception as exc:
        result["error"] = (
            f"{type(exc).__name__}: {exc}"
        )

    return result


def inspect_modules(
    module_names: list[str] | None = None
) -> dict:
    """
    Check modules one by one.

    The returned dictionary includes failures rather
    than raising an exception for the entire operation.
    """

    names = (
        module_names
        if module_names is not None
        else list(MODULE_REGISTRY.keys())
    )

    results = {}

    for module_name in names:
        try:
            results[module_name] = load_module_safely(
                module_name
            )

        except Exception as exc:
            results[module_name] = {
                "module": module_name,
                "available": False,
                "has_renderer": False,
                "module_object": None,
                "error": str(exc)
            }

    return results


# ---------------------------------------------------------
# SAFE MODULE DATA READING
# ---------------------------------------------------------

MODULE_DATA_FILES = {
    "character_identity_manager": [
        "character_profiles.json"
    ],
    "character_reference_library": [
        "character_references.json"
    ],
    "image_generation_manager": [
        "image_generation_jobs.json"
    ],
    "video_generation_manager": [
        "video_generation_jobs.json"
    ],
    "outfit_consistency_manager": [
        "outfit_consistency.json"
    ],
    "voice_profile_manager": [
        "voice_profiles.json"
    ],
    "lip_sync_manager": [
        "lip_sync_jobs.json"
    ],
    "batch_generation_manager": [
        "batch_generation.json"
    ],
    "script_writer": [
        "scripts.json"
    ],
    "storyboard_manager": [
        "storyboards.json"
    ],
    "scene_prompt_generator": [
        "scene_prompts.json"
    ]
}


def _extract_records(data: Any) -> list:
    """
    Extract a list from common JSON database structures.
    """

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        preferred_keys = (
            "items",
            "records",
            "jobs",
            "profiles",
            "characters",
            "references",
            "outfits",
            "scripts",
            "storyboards",
            "scenes",
            "prompts",
            "batches"
        )

        for key in preferred_keys:
            value = data.get(key)

            if isinstance(value, list):
                return value

    return []


def count_module_records(
    module_name: str,
    data_dir: Path | None = None
) -> dict:
    """
    Count records using known database filenames.

    This function never imports the target module.
    """

    root = data_dir or DATA_DIR

    filenames = MODULE_DATA_FILES.get(
        module_name,
        []
    )

    result = {
        "module": module_name,
        "record_count": 0,
        "database_found": False,
        "database_files": [],
        "errors": []
    }

    for filename in filenames:
        path = root / filename

        if not path.exists():
            continue

        result["database_found"] = True
        result["database_files"].append(filename)

        try:
            data = _read_json(path)

            if data is None:
                result["errors"].append(
                    f"Could not read {filename}"
                )
                continue

            records = _extract_records(data)

            result["record_count"] += len(records)

        except Exception as exc:
            result["errors"].append(
                f"{filename}: {exc}"
            )

    return result


# ---------------------------------------------------------
# MODULE STATUS
# ---------------------------------------------------------

def get_module_status(
    module_names: list[str] | None = None
) -> dict:
    inspected = inspect_modules(module_names)

    results = {}

    for module_name, info in inspected.items():
        metadata = MODULE_REGISTRY.get(
            module_name,
            {}
        )

        results[module_name] = {
            "name": metadata.get(
                "name",
                module_name.replace("_", " ").title()
            ),
            "description": metadata.get(
                "description",
                "Studio module"
            ),
            "available": info["available"],
            "has_renderer": info["has_renderer"],
            "error": info["error"]
        }

    return results


# ---------------------------------------------------------
# WORKFLOW STATISTICS
# ---------------------------------------------------------

def get_workflow_statistics(
    data_dir: Path | None = None
) -> dict:
    root = data_dir or DATA_DIR

    module_names = list(MODULE_REGISTRY.keys())

    counts = {}

    for module_name in module_names:
        try:
            counts[module_name] = count_module_records(
                module_name,
                root
            )

        except Exception as exc:
            counts[module_name] = {
                "module": module_name,
                "record_count": 0,
                "database_found": False,
                "database_files": [],
                "errors": [str(exc)]
            }

    total_records = sum(
        item["record_count"]
        for item in counts.values()
    )

    databases_found = sum(
        1 for item in counts.values()
        if item["database_found"]
    )

    return {
        "total_modules_checked": len(module_names),
        "total_records": total_records,
        "databases_found": databases_found,
        "module_records": counts
    }


# ---------------------------------------------------------
# RECENT WORKFLOW ITEMS
# ---------------------------------------------------------

def get_recent_items(
    data_dir: Path | None = None,
    limit: int = 10
) -> list[dict]:
    """
    Collect records containing common timestamp fields.

    Missing or invalid database files are skipped.
    """

    root = data_dir or DATA_DIR

    recent = []

    for module_name, filenames in MODULE_DATA_FILES.items():
        for filename in filenames:
            path = root / filename

            if not path.exists():
                continue

            try:
                data = _read_json(path)

                if data is None:
                    continue

                records = _extract_records(data)

                for record in records:
                    if not isinstance(record, dict):
                        continue

                    timestamp = (
                        record.get("updated_at")
                        or record.get("created_at")
                        or record.get("timestamp")
                    )

                    if not timestamp:
                        continue

                    recent.append({
                        "module": module_name,
                        "name": (
                            record.get("name")
                            or record.get("title")
                            or record.get("batch_name")
                            or record.get("task_name")
                            or record.get("project_name")
                            or "Unnamed record"
                        ),
                        "status": record.get(
                            "status",
                            "Not specified"
                        ),
                        "timestamp": str(timestamp)
                    })

            except Exception:
                continue

    recent.sort(
        key=lambda item: item["timestamp"],
        reverse=True
    )

    return recent[:max(0, limit)]


# ---------------------------------------------------------
# COMPLETE SYSTEM SNAPSHOT
# ---------------------------------------------------------

def get_system_snapshot(
    data_dir: Path | None = None,
    module_names: list[str] | None = None
) -> dict:
    """
    Build one dashboard snapshot.

    Each section is protected so that an individual
    failure does not break the entire snapshot.
    """

    try:
        module_status = get_module_status(module_names)
    except Exception as exc:
        module_status = {
            "_inspection_error": {
                "available": False,
                "error": str(exc)
            }
        }

    try:
        statistics = get_workflow_statistics(data_dir)
    except Exception as exc:
        statistics = {
            "total_modules_checked": 0,
            "total_records": 0,
            "databases_found": 0,
            "error": str(exc)
        }

    try:
        recent = get_recent_items(data_dir)
    except Exception as exc:
        recent = []

    available = sum(
        1 for item in module_status.values()
        if item.get("available")
    )

    unavailable = len(module_status) - available

    return {
        "created_at": _now(),
        "module_status": module_status,
        "statistics": statistics,
        "recent_items": recent,
        "health": {
            "available_modules": available,
            "unavailable_modules": unavailable,
            "total_modules": len(module_status)
        }
    }


# ---------------------------------------------------------
# EXPORT
# ---------------------------------------------------------

def export_snapshot(
    output_path: Path | None = None
) -> Path:
    snapshot = get_system_snapshot()

    path = output_path or (
        OUTPUT_DIR
        / f"workflow_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )

    return save_snapshot(snapshot, path)


# ---------------------------------------------------------
# STREAMLIT DASHBOARD
# ---------------------------------------------------------

def render() -> None:
    import streamlit as st

    st.title("Final Workflow Integration")

    st.caption(
        "Central overview of your AI Influencer Studio."
    )

    if st.button("Refresh Workflow Dashboard"):
        st.rerun()

    snapshot = get_system_snapshot()

    health = snapshot["health"]
    stats = snapshot["statistics"]

    # -----------------------------------------------------
    # OVERVIEW
    # -----------------------------------------------------

    st.subheader("Studio Overview")

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Available Modules",
        health["available_modules"]
    )

    col2.metric(
        "Unavailable Modules",
        health["unavailable_modules"]
    )

    col3.metric(
        "Saved Records",
        stats.get("total_records", 0)
    )

    st.caption(
        f"Last checked: {snapshot['created_at']}"
    )

    st.divider()

    # -----------------------------------------------------
    # MODULE HEALTH
    # -----------------------------------------------------

    st.subheader("Module Health")

    statuses = snapshot["module_status"]

    for module_name, item in statuses.items():
        name = item.get("name", module_name)

        if item.get("available"):
            if item.get("has_renderer"):
                st.success(f"{name} — Available")
            else:
                st.info(
                    f"{name} — Imported; no page renderer"
                )
        else:
            st.error(
                f"{name} — Unavailable"
            )

            if item.get("error"):
                with st.expander(
                    f"View error: {name}"
                ):
                    st.code(item["error"])

    st.divider()

    # -----------------------------------------------------
    # RECORD BREAKDOWN
    # -----------------------------------------------------

    st.subheader("Saved Data Overview")

    module_records = stats.get(
        "module_records",
        {}
    )

    for module_name, item in module_records.items():
        label = MODULE_REGISTRY.get(
            module_name,
            {}
        ).get(
            "name",
            module_name
        )

        col1, col2 = st.columns([3, 1])

        col1.write(label)
        col2.metric(
            "Records",
            item.get("record_count", 0)
        )

        if item.get("errors"):
            with st.expander(
                f"Data warnings: {label}"
            ):
                for error in item["errors"]:
                    st.warning(error)

    st.divider()

    # -----------------------------------------------------
    # RECENT ACTIVITY
    # -----------------------------------------------------

    st.subheader("Recent Workflow Activity")

    recent = snapshot.get("recent_items", [])

    if not recent:
        st.info(
            "No recent records with timestamps were found."
        )

    else:
        for item in recent:
            module_label = MODULE_REGISTRY.get(
                item["module"],
                {}
            ).get(
                "name",
                item["module"]
            )

            with st.container():
                st.markdown(
                    f"**{item['name']}**"
                )

                st.caption(
                    f"{module_label} | "
                    f"{item['status']} | "
                    f"{item['timestamp']}"
                )

    st.divider()

    # -----------------------------------------------------
    # WORKFLOW GUIDE
    # -----------------------------------------------------

    st.subheader("Recommended Production Workflow")

    workflow_steps = [
        "Create or select a project",
        "Create character identity profiles",
        "Add character reference images",
        "Define character outfits and continuity",
        "Write scripts and create storyboards",
        "Prepare image generation jobs",
        "Prepare video generation jobs",
        "Review visual consistency",
        "Configure voice profiles",
        "Prepare lip-sync jobs",
        "Organize tasks into generation batches",
        "Review and export completed assets"
    ]

    for index, step in enumerate(workflow_steps, start=1):
        st.write(f"{index}. {step}")

    st.caption(
        "These are workflow stages, not proof that "
        "AI generation has actually been performed."
    )

    st.divider()

    # -----------------------------------------------------
    # EXPORT SNAPSHOT
    # -----------------------------------------------------

    st.subheader("Export Workflow Report")

    if st.button("Create Workflow JSON Report"):
        try:
            path = export_snapshot()

            st.download_button(
                "Download Workflow Report",
                data=path.read_bytes(),
                file_name=path.name,
                mime="application/json"
            )

        except Exception as exc:
            st.error(
                f"Could not export report: {exc}"
            )


# ---------------------------------------------------------
# BUILT-IN TESTS
# ---------------------------------------------------------

def run_tests() -> None:
    print("Running Final Workflow Integration tests...")

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)

        # Test JSON helper.
        sample_path = root / "sample.json"

        sample_data = {
            "batches": [
                {
                    "id": "batch-1",
                    "batch_name": "Test Batch",
                    "status": "Completed",
                    "created_at": _now()
                }
            ]
        }

        sample_path.write_text(
            json.dumps(sample_data),
            encoding="utf-8"
        )

        loaded = _read_json(sample_path)

        assert loaded["batches"][0]["id"] == "batch-1"

        # Test record extraction.
        records = _extract_records(sample_data)

        assert len(records) == 1

        # Test empty record extraction.
        assert _extract_records(None) == []

        # Test module record count.
        data_dir = root / "data"
        data_dir.mkdir()

        batch_file = data_dir / "batch_generation.json"

        batch_file.write_text(
            json.dumps(sample_data),
            encoding="utf-8"
        )

        count = count_module_records(
            "batch_generation_manager",
            data_dir
        )

        assert count["database_found"] is True
        assert count["record_count"] == 1

        # Test statistics.
        stats = get_workflow_statistics(data_dir)

        assert stats["total_records"] == 1
        assert stats["databases_found"] == 1

        # Test recent items.
        recent = get_recent_items(data_dir)

        assert len(recent) == 1
        assert recent[0]["name"] == "Test Batch"

        # Test snapshot saving and loading.
        snapshot = {
            "created_at": _now(),
            "modules": {"test": True},
            "statistics": {"records": 1}
        }

        snapshot_path = root / "snapshot.json"

        save_snapshot(snapshot, snapshot_path)

        loaded_snapshot = load_snapshot(snapshot_path)

        assert loaded_snapshot["statistics"]["records"] == 1

        # Test missing snapshot.
        missing = load_snapshot(
            root / "missing.json"
        )

        assert missing["modules"] == {}

        # Test independent missing-module handling.
        missing_module = load_module_safely(
            "module_that_does_not_exist"
        )

        assert missing_module["available"] is False
        assert missing_module["error"] is not None

        # Test status response.
        status = get_module_status([
            "module_that_does_not_exist"
        ])

        assert (
            status["module_that_does_not_exist"]["available"]
            is False
        )

        # Test snapshot construction.
        result = get_system_snapshot(
            data_dir=data_dir,
            module_names=[
                "module_that_does_not_exist"
            ]
        )

        assert result["health"]["total_modules"] == 1
        assert result["health"]["unavailable_modules"] == 1

        # Test export.
        export_path = root / "workflow_export.json"

        exported = export_snapshot(export_path)

        assert exported.exists()

    print(
        "All Final Workflow Integration tests passed."
    )


# ---------------------------------------------------------
# COMMAND LINE
# ---------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Final Workflow Integration"
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
        print("Final Workflow Integration")
        print("Use --test to run built-in tests.")
