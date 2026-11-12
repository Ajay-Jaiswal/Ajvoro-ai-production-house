
"""
File 64: modules/batch_generation_manager.py

AI Influencer Studio - Batch Generation Manager

Features:
- Create multiple generation batches
- Add multiple tasks to a batch
- Support image, video, lip-sync and custom tasks
- Track task status and progress
- Retry failed tasks
- Cancel pending tasks
- Duplicate tasks and batches
- Search and filter batches
- Calculate batch statistics
- Export JSON and CSV reports
- Streamlit interface
- Built-in tests

Run:
    python -m modules.batch_generation_manager --test
"""

from __future__ import annotations

import csv
import json
import tempfile
import uuid

from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------
# PATH CONFIGURATION
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs" / "batch_generation"

DATABASE_FILE = DATA_DIR / "batch_generation.json"

for folder in (DATA_DIR, OUTPUT_DIR):
    folder.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------

TASK_TYPES = {
    "Image Generation",
    "Video Generation",
    "Lip-Sync",
    "Talking Avatar",
    "Motion Control",
    "Custom"
}

TASK_STATUSES = {
    "Pending",
    "Queued",
    "Processing",
    "Completed",
    "Failed",
    "Cancelled"
}

BATCH_STATUSES = {
    "Draft",
    "Queued",
    "Processing",
    "Completed",
    "Partially Failed",
    "Failed",
    "Cancelled"
}


# ---------------------------------------------------------
# GENERAL HELPERS
# ---------------------------------------------------------

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _clean(value: Any, limit: int = 5000) -> str:
    return str(value or "").strip()[:limit]


def _read_database(
    database_path: Path | None = None
) -> dict:
    path = database_path or DATABASE_FILE

    if not path.exists():
        return {"batches": []}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))

        if not isinstance(data, dict):
            return {"batches": []}

        if not isinstance(data.get("batches"), list):
            data["batches"] = []

        return data

    except (OSError, json.JSONDecodeError):
        return {"batches": []}


def _write_database(
    data: dict,
    database_path: Path | None = None
) -> None:
    path = database_path or DATABASE_FILE

    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_suffix(".tmp")

    temporary.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    temporary.replace(path)


def _find_batch(
    data: dict,
    batch_id: str
) -> dict | None:
    return next(
        (
            batch for batch in data["batches"]
            if batch.get("id") == batch_id
        ),
        None
    )


def _find_task(
    batch: dict,
    task_id: str
) -> dict | None:
    return next(
        (
            task for task in batch.get("tasks", [])
            if task.get("id") == task_id
        ),
        None
    )


# ---------------------------------------------------------
# BATCH CREATION
# ---------------------------------------------------------

def create_batch(
    batch_name: str,
    description: str = "",
    project_name: str = "",
    max_parallel_jobs: int = 1,
    database_path: Path | None = None
) -> dict:
    """Create a new generation batch."""

    batch_name = _clean(batch_name, 200)

    if not batch_name:
        raise ValueError("Batch name is required.")

    max_parallel_jobs = int(max_parallel_jobs)

    if not 1 <= max_parallel_jobs <= 10:
        raise ValueError(
            "Parallel jobs must be between 1 and 10."
        )

    data = _read_database(database_path)

    batch = {
        "id": _new_id(),
        "batch_name": batch_name,
        "description": _clean(description),
        "project_name": _clean(project_name, 200),
        "max_parallel_jobs": max_parallel_jobs,
        "status": "Draft",
        "tasks": [],
        "created_at": _now(),
        "updated_at": _now()
    }

    data["batches"].append(batch)

    _write_database(data, database_path)

    return batch


# ---------------------------------------------------------
# ADD TASK
# ---------------------------------------------------------

def add_task(
    batch_id: str,
    task_name: str,
    task_type: str,
    prompt: str = "",
    character_name: str = "",
    reference_path: str = "",
    settings: dict | None = None,
    database_path: Path | None = None
) -> dict:
    """Add a generation task to an existing batch."""

    task_name = _clean(task_name, 200)

    if not task_name:
        raise ValueError("Task name is required.")

    if task_type not in TASK_TYPES:
        raise ValueError("Unsupported task type.")

    data = _read_database(database_path)
    batch = _find_batch(data, batch_id)

    if not batch:
        raise ValueError("Batch not found.")

    if batch["status"] == "Cancelled":
        raise ValueError("Cannot add tasks to a cancelled batch.")

    task = {
        "id": _new_id(),
        "task_name": task_name,
        "task_type": task_type,
        "prompt": _clean(prompt),
        "character_name": _clean(character_name, 150),
        "reference_path": _clean(reference_path, 1000),
        "settings": settings if isinstance(settings, dict) else {},
        "status": "Pending",
        "progress": 0,
        "attempts": 0,
        "error_message": None,
        "output_path": None,
        "created_at": _now(),
        "updated_at": _now()
    }

    batch["tasks"].append(task)

    batch["status"] = "Draft"
    batch["updated_at"] = _now()

    _write_database(data, database_path)

    return task


# ---------------------------------------------------------
# BATCH RETRIEVAL
# ---------------------------------------------------------

def list_batches(
    status: str | None = None,
    database_path: Path | None = None
) -> list[dict]:
    data = _read_database(database_path)

    batches = data["batches"]

    if status:
        batches = [
            batch for batch in batches
            if batch.get("status") == status
        ]

    return sorted(
        batches,
        key=lambda item: item.get("updated_at", ""),
        reverse=True
    )


def get_batch(
    batch_id: str,
    database_path: Path | None = None
) -> dict | None:
    data = _read_database(database_path)

    return _find_batch(data, batch_id)


def get_task(
    batch_id: str,
    task_id: str,
    database_path: Path | None = None
) -> dict | None:
    batch = get_batch(batch_id, database_path)

    if not batch:
        return None

    return _find_task(batch, task_id)


# ---------------------------------------------------------
# TASK STATUS
# ---------------------------------------------------------

def update_task_status(
    batch_id: str,
    task_id: str,
    status: str,
    progress: int | None = None,
    error_message: str | None = None,
    output_path: str | None = None,
    database_path: Path | None = None
) -> dict:
    """Update one task's status and progress."""

    if status not in TASK_STATUSES:
        raise ValueError("Invalid task status.")

    data = _read_database(database_path)
    batch = _find_batch(data, batch_id)

    if not batch:
        raise ValueError("Batch not found.")

    task = _find_task(batch, task_id)

    if not task:
        raise ValueError("Task not found.")

    if progress is not None:
        progress = int(progress)

        if not 0 <= progress <= 100:
            raise ValueError("Progress must be 0-100.")

    if status == "Completed":
        progress = 100

    if status in ("Pending", "Queued", "Cancelled"):
        progress = 0

    task["status"] = status

    if progress is not None:
        task["progress"] = progress

    task["error_message"] = (
        _clean(error_message, 2000) or None
    )

    if output_path is not None:
        task["output_path"] = _clean(output_path, 1000)

    task["updated_at"] = _now()

    batch["updated_at"] = _now()

    _refresh_batch_status(batch)

    _write_database(data, database_path)

    return task


# ---------------------------------------------------------
# BATCH STATUS CALCULATION
# ---------------------------------------------------------

def _refresh_batch_status(batch: dict) -> str:
    tasks = batch.get("tasks", [])

    if not tasks:
        batch["status"] = "Draft"
        return "Draft"

    statuses = [
        task.get("status")
        for task in tasks
    ]

    if all(status == "Completed" for status in statuses):
        result = "Completed"

    elif all(status == "Cancelled" for status in statuses):
        result = "Cancelled"

    elif all(
        status in ("Completed", "Cancelled")
        for status in statuses
    ):
        result = "Completed"

    elif all(
        status in ("Failed", "Cancelled")
        for status in statuses
    ):
        result = "Failed"

    elif all(
        status in ("Completed", "Failed", "Cancelled")
        for status in statuses
    ):
        result = "Partially Failed"

    elif "Processing" in statuses:
        result = "Processing"

    elif "Queued" in statuses:
        result = "Queued"

    else:
        result = "Draft"

    batch["status"] = result

    return result


def refresh_batch(
    batch_id: str,
    database_path: Path | None = None
) -> dict:
    data = _read_database(database_path)

    batch = _find_batch(data, batch_id)

    if not batch:
        raise ValueError("Batch not found.")

    _refresh_batch_status(batch)

    batch["updated_at"] = _now()

    _write_database(data, database_path)

    return batch


# ---------------------------------------------------------
# QUEUE MANAGEMENT
# ---------------------------------------------------------

def queue_batch(
    batch_id: str,
    database_path: Path | None = None
) -> dict:
    """Mark pending tasks as queued."""

    data = _read_database(database_path)
    batch = _find_batch(data, batch_id)

    if not batch:
        raise ValueError("Batch not found.")

    if not batch["tasks"]:
        raise ValueError("Batch has no tasks.")

    if batch["status"] == "Cancelled":
        raise ValueError("Cancelled batch cannot be queued.")

    for task in batch["tasks"]:
        if task["status"] in ("Pending", "Failed"):
            task["status"] = "Queued"
            task["progress"] = 0
            task["error_message"] = None
            task["updated_at"] = _now()

    batch["status"] = "Queued"
    batch["updated_at"] = _now()

    _write_database(data, database_path)

    return batch


def get_next_queued_tasks(
    batch_id: str,
    database_path: Path | None = None
) -> list[dict]:
    """
    Return queued tasks up to the batch parallel limit.

    This does not execute any generation engine.
    """

    batch = get_batch(batch_id, database_path)

    if not batch:
        raise ValueError("Batch not found.")

    active_count = sum(
        1 for task in batch["tasks"]
        if task["status"] == "Processing"
    )

    available_slots = max(
        0,
        batch["max_parallel_jobs"] - active_count
    )

    queued = [
        task for task in batch["tasks"]
        if task["status"] == "Queued"
    ]

    return queued[:available_slots]


# ---------------------------------------------------------
# RETRY FAILED TASK
# ---------------------------------------------------------

def retry_failed_task(
    batch_id: str,
    task_id: str,
    database_path: Path | None = None
) -> dict:
    data = _read_database(database_path)

    batch = _find_batch(data, batch_id)

    if not batch:
        raise ValueError("Batch not found.")

    task = _find_task(batch, task_id)

    if not task:
        raise ValueError("Task not found.")

    if task["status"] != "Failed":
        raise ValueError("Only failed tasks can be retried.")

    task["status"] = "Queued"
    task["progress"] = 0
    task["error_message"] = None
    task["attempts"] += 1
    task["updated_at"] = _now()

    batch["status"] = "Queued"
    batch["updated_at"] = _now()

    _write_database(data, database_path)

    return task


# ---------------------------------------------------------
# CANCEL TASK / BATCH
# ---------------------------------------------------------

def cancel_task(
    batch_id: str,
    task_id: str,
    database_path: Path | None = None
) -> dict:
    data = _read_database(database_path)

    batch = _find_batch(data, batch_id)

    if not batch:
        raise ValueError("Batch not found.")

    task = _find_task(batch, task_id)

    if not task:
        raise ValueError("Task not found.")

    if task["status"] in ("Completed", "Failed"):
        raise ValueError(
            "Completed or failed tasks cannot be cancelled."
        )

    task["status"] = "Cancelled"
    task["progress"] = 0
    task["updated_at"] = _now()

    batch["updated_at"] = _now()

    _refresh_batch_status(batch)

    _write_database(data, database_path)

    return task


def cancel_batch(
    batch_id: str,
    database_path: Path | None = None
) -> dict:
    data = _read_database(database_path)

    batch = _find_batch(data, batch_id)

    if not batch:
        raise ValueError("Batch not found.")

    for task in batch["tasks"]:
        if task["status"] in (
            "Pending",
            "Queued",
            "Processing"
        ):
            task["status"] = "Cancelled"
            task["progress"] = 0
            task["updated_at"] = _now()

    batch["status"] = "Cancelled"
    batch["updated_at"] = _now()

    _write_database(data, database_path)

    return batch


# ---------------------------------------------------------
# DUPLICATION
# ---------------------------------------------------------

def duplicate_task(
    batch_id: str,
    task_id: str,
    database_path: Path | None = None
) -> dict:
    data = _read_database(database_path)

    batch = _find_batch(data, batch_id)

    if not batch:
        raise ValueError("Batch not found.")

    original = _find_task(batch, task_id)

    if not original:
        raise ValueError("Task not found.")

    duplicate = dict(original)

    duplicate["id"] = _new_id()
    duplicate["task_name"] += " Copy"
    duplicate["status"] = "Pending"
    duplicate["progress"] = 0
    duplicate["attempts"] = 0
    duplicate["error_message"] = None
    duplicate["output_path"] = None
    duplicate["created_at"] = _now()
    duplicate["updated_at"] = _now()

    batch["tasks"].append(duplicate)
    batch["status"] = "Draft"
    batch["updated_at"] = _now()

    _write_database(data, database_path)

    return duplicate


def duplicate_batch(
    batch_id: str,
    database_path: Path | None = None
) -> dict:
    data = _read_database(database_path)

    original = _find_batch(data, batch_id)

    if not original:
        raise ValueError("Batch not found.")

    duplicate = dict(original)

    duplicate["id"] = _new_id()
    duplicate["batch_name"] += " Copy"
    duplicate["status"] = "Draft"
    duplicate["created_at"] = _now()
    duplicate["updated_at"] = _now()

    duplicate["tasks"] = []

    for task in original.get("tasks", []):
        new_task = dict(task)

        new_task["id"] = _new_id()
        new_task["status"] = "Pending"
        new_task["progress"] = 0
        new_task["attempts"] = 0
        new_task["error_message"] = None
        new_task["output_path"] = None
        new_task["created_at"] = _now()
        new_task["updated_at"] = _now()

        duplicate["tasks"].append(new_task)

    data["batches"].append(duplicate)

    _write_database(data, database_path)

    return duplicate


# ---------------------------------------------------------
# DELETE BATCH
# ---------------------------------------------------------

def delete_batch(
    batch_id: str,
    database_path: Path | None = None
) -> bool:
    data = _read_database(database_path)

    original_count = len(data["batches"])

    data["batches"] = [
        batch for batch in data["batches"]
        if batch.get("id") != batch_id
    ]

    if len(data["batches"]) == original_count:
        return False

    _write_database(data, database_path)

    return True


# ---------------------------------------------------------
# SEARCH
# ---------------------------------------------------------

def search_batches(
    query: str,
    database_path: Path | None = None
) -> list[dict]:
    query = _clean(query).lower()

    batches = list_batches(
        database_path=database_path
    )

    if not query:
        return batches

    results = []

    for batch in batches:
        searchable = " ".join([
            batch.get("batch_name", ""),
            batch.get("description", ""),
            batch.get("project_name", ""),
            batch.get("status", "")
        ]).lower()

        task_text = " ".join(
            task.get("task_name", "")
            + " "
            + task.get("task_type", "")
            for task in batch.get("tasks", [])
        ).lower()

        if query in searchable or query in task_text:
            results.append(batch)

    return results


# ---------------------------------------------------------
# STATISTICS
# ---------------------------------------------------------

def get_batch_statistics(
    batch_id: str,
    database_path: Path | None = None
) -> dict:
    batch = get_batch(batch_id, database_path)

    if not batch:
        raise ValueError("Batch not found.")

    tasks = batch.get("tasks", [])

    total = len(tasks)

    counts = {
        status: 0 for status in TASK_STATUSES
    }

    for task in tasks:
        status = task.get("status")

        if status in counts:
            counts[status] += 1

    progress = (
        sum(task.get("progress", 0) for task in tasks)
        / total
        if total else 0
    )

    return {
        "batch_id": batch_id,
        "total_tasks": total,
        "completed": counts["Completed"],
        "failed": counts["Failed"],
        "pending": counts["Pending"],
        "queued": counts["Queued"],
        "processing": counts["Processing"],
        "cancelled": counts["Cancelled"],
        "average_progress": round(progress, 2),
        "status_counts": counts
    }


def get_global_statistics(
    database_path: Path | None = None
) -> dict:
    batches = list_batches(
        database_path=database_path
    )

    total_tasks = sum(
        len(batch.get("tasks", []))
        for batch in batches
    )

    completed = sum(
        1
        for batch in batches
        for task in batch.get("tasks", [])
        if task.get("status") == "Completed"
    )

    failed = sum(
        1
        for batch in batches
        for task in batch.get("tasks", [])
        if task.get("status") == "Failed"
    )

    return {
        "total_batches": len(batches),
        "total_tasks": total_tasks,
        "completed_tasks": completed,
        "failed_tasks": failed,
        "completion_percentage": round(
            completed / total_tasks * 100,
            2
        ) if total_tasks else 0
    }


# ---------------------------------------------------------
# EXPORT
# ---------------------------------------------------------

def export_json(
    database_path: Path | None = None,
    output_path: Path | None = None
) -> Path:
    data = _read_database(database_path)

    output_path = output_path or (
        OUTPUT_DIR
        / f"batch_report_{_now().replace(':', '-')}.json"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    return output_path


def export_csv(
    database_path: Path | None = None,
    output_path: Path | None = None
) -> Path:
    batches = list_batches(
        database_path=database_path
    )

    output_path = output_path or (
        OUTPUT_DIR
        / f"batch_tasks_{_now().replace(':', '-')}.csv"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    fields = [
        "batch_id",
        "batch_name",
        "project_name",
        "batch_status",
        "task_id",
        "task_name",
        "task_type",
        "character_name",
        "task_status",
        "progress",
        "attempts",
        "error_message",
        "output_path"
    ]

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fields
        )

        writer.writeheader()

        for batch in batches:
            for task in batch.get("tasks", []):
                writer.writerow({
                    "batch_id": batch["id"],
                    "batch_name": batch["batch_name"],
                    "project_name": batch["project_name"],
                    "batch_status": batch["status"],
                    "task_id": task["id"],
                    "task_name": task["task_name"],
                    "task_type": task["task_type"],
                    "character_name": task["character_name"],
                    "task_status": task["status"],
                    "progress": task["progress"],
                    "attempts": task["attempts"],
                    "error_message": task["error_message"],
                    "output_path": task["output_path"]
                })

    return output_path


# ---------------------------------------------------------
# STREAMLIT INTERFACE
# ---------------------------------------------------------

def render() -> None:
    import streamlit as st

    st.title("Batch Generation Manager")

    st.caption(
        "Organize and monitor multiple AI generation tasks."
    )

    create_tab, manage_tab, queue_tab, reports_tab = st.tabs([
        "Create Batch",
        "Batch Manager",
        "Queue",
        "Reports"
    ])

    # -----------------------------------------------------
    # CREATE BATCH
    # -----------------------------------------------------

    with create_tab:
        st.subheader("Create Generation Batch")

        with st.form("batch_create_form"):

            batch_name = st.text_input(
                "Batch Name",
                placeholder="Example: Eira Episode 1"
            )

            project_name = st.text_input(
                "Project Name",
                placeholder="Example: Fantasy Film"
            )

            description = st.text_area(
                "Description"
            )

            parallel_jobs = st.number_input(
                "Maximum Parallel Jobs",
                min_value=1,
                max_value=10,
                value=1
            )

            submitted = st.form_submit_button(
                "Create Batch",
                type="primary"
            )

            if submitted:
                try:
                    batch = create_batch(
                        batch_name=batch_name,
                        project_name=project_name,
                        description=description,
                        max_parallel_jobs=parallel_jobs
                    )

                    st.success(
                        "Batch created: " + batch["id"]
                    )

                except Exception as exc:
                    st.error(str(exc))

        st.divider()
        st.subheader("Add Task to Existing Batch")

        batches = list_batches()

        if batches:
            batch_options = {
                f"{batch['batch_name']} [{batch['id']}]":
                batch["id"]
                for batch in batches
                if batch["status"] != "Cancelled"
            }

            if batch_options:
                with st.form("batch_add_task_form"):

                    selected_batch = st.selectbox(
                        "Select Batch",
                        list(batch_options.keys())
                    )

                    task_name = st.text_input(
                        "Task Name",
                        placeholder="Example: Generate Scene 01"
                    )

                    task_type = st.selectbox(
                        "Task Type",
                        sorted(TASK_TYPES)
                    )

                    character = st.text_input(
                        "Character Name"
                    )

                    prompt = st.text_area(
                        "Generation Prompt"
                    )

                    reference = st.text_input(
                        "Reference File Path (Optional)"
                    )

                    settings_text = st.text_area(
                        "Additional Settings JSON",
                        value="{}"
                    )

                    add_submitted = st.form_submit_button(
                        "Add Task"
                    )

                    if add_submitted:
                        try:
                            settings = json.loads(settings_text)

                            if not isinstance(settings, dict):
                                raise ValueError(
                                    "Settings must be a JSON object."
                                )

                            task = add_task(
                                batch_id=batch_options[
                                    selected_batch
                                ],
                                task_name=task_name,
                                task_type=task_type,
                                prompt=prompt,
                                character_name=character,
                                reference_path=reference,
                                settings=settings
                            )

                            st.success(
                                "Task added: " + task["id"]
                            )

                        except Exception as exc:
                            st.error(str(exc))

        else:
            st.info("Create a batch first.")

    # -----------------------------------------------------
    # BATCH MANAGER
    # -----------------------------------------------------

    with manage_tab:
        st.subheader("Manage Batches")

        query = st.text_input(
            "Search batches",
            key="batch_search"
        )

        batches = (
            search_batches(query)
            if query
            else list_batches()
        )

        if not batches:
            st.info("No batches found.")

        for batch in batches:
            with st.expander(
                f"{batch['batch_name']} — {batch['status']}"
            ):
                stats = get_batch_statistics(batch["id"])

                col1, col2, col3 = st.columns(3)

                col1.metric(
                    "Tasks",
                    stats["total_tasks"]
                )

                col2.metric(
                    "Completed",
                    stats["completed"]
                )

                col3.metric(
                    "Failed",
                    stats["failed"]
                )

                st.write(
                    f"**Project:** {batch['project_name']}"
                )

                st.write(
                    f"**Description:** {batch['description']}"
                )

                st.write(
                    f"**Parallel Limit:** "
                    f"{batch['max_parallel_jobs']}"
                )

                st.progress(
                    stats["average_progress"] / 100
                )

                st.write(
                    f"Average progress: "
                    f"{stats['average_progress']}%"
                )

                for task in batch["tasks"]:
                    st.markdown(
                        f"**{task['task_name']}** "
                        f"({task['task_type']})"
                    )

                    st.write(
                        f"Status: {task['status']} | "
                        f"Progress: {task['progress']}%"
                    )

                    if task.get("error_message"):
                        st.error(task["error_message"])

                    if task["status"] == "Failed":
                        if st.button(
                            "Retry Task",
                            key=f"retry_{batch['id']}_{task['id']}"
                        ):
                            try:
                                retry_failed_task(
                                    batch["id"],
                                    task["id"]
                                )
                                st.success("Task queued for retry.")
                                st.rerun()

                            except Exception as exc:
                                st.error(str(exc))

                    if task["status"] in (
                        "Pending",
                        "Queued"
                    ):
                        if st.button(
                            "Cancel Task",
                            key=f"cancel_{batch['id']}_{task['id']}"
                        ):
                            cancel_task(
                                batch["id"],
                                task["id"]
                            )
                            st.success("Task cancelled.")
                            st.rerun()

                    if st.button(
                        "Duplicate Task",
                        key=f"duplicate_task_{batch['id']}_{task['id']}"
                    ):
                        duplicate_task(
                            batch["id"],
                            task["id"]
                        )
                        st.success("Task duplicated.")
                        st.rerun()

                st.divider()

                col_a, col_b, col_c = st.columns(3)

                with col_a:
                    if st.button(
                        "Queue Batch",
                        key=f"queue_{batch['id']}"
                    ):
                        try:
                            queue_batch(batch["id"])
                            st.success("Batch queued.")
                            st.rerun()

                        except Exception as exc:
                            st.error(str(exc))

                with col_b:
                    if st.button(
                        "Duplicate Batch",
                        key=f"duplicate_batch_{batch['id']}"
                    ):
                        duplicate_batch(batch["id"])
                        st.success("Batch duplicated.")
                        st.rerun()

                with col_c:
                    if st.button(
                        "Delete Batch",
                        key=f"delete_batch_{batch['id']}"
                    ):
                        st.session_state[
                            "delete_batch_id"
                        ] = batch["id"]

                if st.session_state.get(
                    "delete_batch_id"
                ) == batch["id"]:

                    st.warning(
                        "Confirm deletion of this batch and its task records."
                    )

                    if st.button(
                        "Confirm Delete",
                        key=f"confirm_batch_{batch['id']}"
                    ):
                        delete_batch(batch["id"])

                        st.session_state.pop(
                            "delete_batch_id",
                            None
                        )

                        st.success("Batch deleted.")
                        st.rerun()

    # -----------------------------------------------------
    # QUEUE
    # -----------------------------------------------------

    with queue_tab:
        st.subheader("Generation Queue")

        batches = list_batches()

        if not batches:
            st.info("No batches available.")
        else:
            options = {
                f"{batch['batch_name']} [{batch['id']}]":
                batch["id"]
                for batch in batches
            }

            selected = st.selectbox(
                "Select Batch",
                list(options.keys())
            )

            batch_id = options[selected]
            batch = get_batch(batch_id)

            st.write(
                f"**Batch Status:** {batch['status']}"
            )

            queued_tasks = get_next_queued_tasks(batch_id)

            st.write(
                f"Available task slots: "
                f"{len(queued_tasks)}"
            )

            if queued_tasks:
                st.write("Tasks ready for a generation engine:")

                for task in queued_tasks:
                    st.write(
                        f"- {task['task_name']} "
                        f"({task['task_type']})"
                    )

                st.caption(
                    "These tasks are only listed as ready. "
                    "No generation engine is running."
                )
            else:
                st.info(
                    "No queued tasks are currently available."
                )

            if st.button("Cancel Entire Batch"):
                try:
                    cancel_batch(batch_id)
                    st.success("Batch cancelled.")
                    st.rerun()

                except Exception as exc:
                    st.error(str(exc))

    # -----------------------------------------------------
    # REPORTS
    # -----------------------------------------------------

    with reports_tab:
        st.subheader("Batch Reports")

        stats = get_global_statistics()

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Total Batches",
            stats["total_batches"]
        )

        col2.metric(
            "Total Tasks",
            stats["total_tasks"]
        )

        col3.metric(
            "Completed",
            stats["completed_tasks"]
        )

        st.metric(
            "Completion Rate",
            f"{stats['completion_percentage']}%"
        )

        if st.button("Generate JSON Report"):
            try:
                path = export_json()

                st.download_button(
                    "Download JSON",
                    data=path.read_bytes(),
                    file_name=path.name,
                    mime="application/json"
                )

            except Exception as exc:
                st.error(str(exc))

        if st.button("Generate CSV Report"):
            try:
                path = export_csv()

                st.download_button(
                    "Download CSV",
                    data=path.read_bytes(),
                    file_name=path.name,
                    mime="text/csv"
                )

            except Exception as exc:
                st.error(str(exc))


# ---------------------------------------------------------
# BUILT-IN TESTS
# ---------------------------------------------------------

def run_tests() -> None:
    print("Running Batch Generation Manager tests...")

    with tempfile.TemporaryDirectory() as temp:
        database = Path(temp) / "test_batches.json"

        # Create batch.
        batch = create_batch(
            batch_name="Test Batch",
            project_name="Test Project",
            max_parallel_jobs=2,
            database_path=database
        )

        assert batch["status"] == "Draft"

        # Add tasks.
        task1 = add_task(
            batch_id=batch["id"],
            task_name="Generate Image",
            task_type="Image Generation",
            prompt="A fantasy character",
            database_path=database
        )

        task2 = add_task(
            batch_id=batch["id"],
            task_name="Generate Video",
            task_type="Video Generation",
            database_path=database
        )

        assert len(
            get_batch(batch["id"], database)["tasks"]
        ) == 2

        # Queue batch.
        queue_batch(batch["id"], database)

        queued = get_next_queued_tasks(
            batch["id"],
            database
        )

        assert len(queued) == 2

        # Start one task.
        update_task_status(
            batch["id"],
            task1["id"],
            "Processing",
            40,
            database_path=database
        )

        next_tasks = get_next_queued_tasks(
            batch["id"],
            database
        )

        assert len(next_tasks) == 1

        # Complete first task.
        update_task_status(
            batch["id"],
            task1["id"],
            "Completed",
            database_path=database
        )

        # Fail second task.
        update_task_status(
            batch["id"],
            task2["id"],
            "Failed",
            30,
            error_message="Test failure",
            database_path=database
        )

        # Check batch status.
        refreshed = refresh_batch(
            batch["id"],
            database
        )

        assert refreshed["status"] == "Partially Failed"

        # Retry failed task.
        retry_failed_task(
            batch["id"],
            task2["id"],
            database
        )

        retried = get_task(
            batch["id"],
            task2["id"],
            database
        )

        assert retried["status"] == "Queued"
        assert retried["attempts"] == 1

        # Duplicate task.
        duplicate = duplicate_task(
            batch["id"],
            task1["id"],
            database
        )

        assert duplicate["id"] != task1["id"]

        # Duplicate batch.
        duplicate_batch_result = duplicate_batch(
            batch["id"],
            database
        )

        assert duplicate_batch_result["id"] != batch["id"]
        assert len(duplicate_batch_result["tasks"]) == 3

        # Search.
        results = search_batches(
            "Test Project",
            database
        )

        assert len(results) == 2

        # Statistics.
        stats = get_batch_statistics(
            batch["id"],
            database
        )

        assert stats["total_tasks"] == 3

        global_stats = get_global_statistics(database)

        assert global_stats["total_batches"] == 2

        # Cancel task.
        cancel_task(
            batch["id"],
            duplicate["id"],
            database
        )

        # Export.
        json_path = Path(temp) / "export.json"
        csv_path = Path(temp) / "export.csv"

        export_json(database, json_path)
        export_csv(database, csv_path)

        assert json_path.exists()
        assert csv_path.exists()

        # Delete.
        assert delete_batch(
            batch["id"],
            database
        )

        assert get_batch(
            batch["id"],
            database
        ) is None

        # Validation.
        try:
            create_batch(
                batch_name="Invalid Batch",
                max_parallel_jobs=20,
                database_path=database
            )
            raise AssertionError(
                "Invalid parallel limit was accepted."
            )

        except ValueError:
            pass

    print("All Batch Generation Manager tests passed.")


# ---------------------------------------------------------
# COMMAND LINE
# ---------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Batch Generation Manager"
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
        print("Batch Generation Manager")
        print("Use --test to run built-in tests.")
