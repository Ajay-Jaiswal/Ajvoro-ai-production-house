
"""
AI Influencer Studio
File 21: modules/workflow_manager.py

Local workflow and task management system.

Features:
- Workflow templates
- Custom workflow creation
- Persistent task queue
- Priority management
- Progress tracking
- Pause / resume / cancel / complete
- Workflow history
- JSON storage
- Streamlit dashboard
- Built-in tests

Run:
    python -m modules.workflow_manager --test
"""

from __future__ import annotations

import argparse
import json
import uuid

from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any


APP_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_DATA_DIR = APP_ROOT / "data"
DEFAULT_STORAGE_FILE = DEFAULT_DATA_DIR / "workflows.json"

LOCK = RLock()

STATUSES = {
    "Pending",
    "Running",
    "Paused",
    "Completed",
    "Cancelled",
    "Failed",
}

PRIORITIES = {
    "Low",
    "Normal",
    "High",
    "Urgent",
}


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

def get_storage_path() -> Path:
    """Resolve workflow storage from config.py when available."""

    try:
        import config

        for key in (
            "WORKFLOW_FILE",
            "WORKFLOW_PATH",
            "WORKFLOWS_FILE",
        ):
            value = getattr(config, key, None)

            if value:
                path = Path(value).expanduser()

                if not path.is_absolute():
                    path = APP_ROOT / path

                return path.resolve()

        for key in ("DATA_DIR", "DATA_PATH"):
            value = getattr(config, key, None)

            if value:
                path = Path(value).expanduser()

                if not path.is_absolute():
                    path = APP_ROOT / path

                return path.resolve() / "workflows.json"

    except ImportError:
        pass

    return DEFAULT_STORAGE_FILE


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------
# Workflow templates
# ---------------------------------------------------------

WORKFLOW_TEMPLATES = {
    "Character Creation": [
        "Define character identity",
        "Prepare character appearance",
        "Save character metadata",
        "Review character consistency",
    ],

    "AI Image Production": [
        "Select saved character",
        "Prepare image prompt",
        "Configure image settings",
        "Generate image using connected engine",
        "Review generated image",
        "Save approved image",
    ],

    "Talking Avatar": [
        "Select character image",
        "Prepare dialogue",
        "Select voice settings",
        "Generate speech using connected TTS",
        "Prepare lip-sync animation",
        "Review and save output",
    ],

    "Motion Control": [
        "Select character reference",
        "Upload motion reference",
        "Configure movement settings",
        "Connect motion generation engine",
        "Review generated motion",
        "Save output",
    ],

    "Video Production": [
        "Prepare storyboard",
        "Collect scene assets",
        "Arrange video timeline",
        "Configure voice and music",
        "Render video using connected engine",
        "Review final video",
        "Export final project",
    ],

    "Social Media Publishing": [
        "Select completed video",
        "Prepare thumbnail",
        "Write title and description",
        "Prepare tags and hashtags",
        "Review publishing package",
        "Publish manually or through a connected service",
    ],
}


# ---------------------------------------------------------
# Storage
# ---------------------------------------------------------

def _empty_store() -> dict:
    return {
        "version": 1,
        "updated_at": now_iso(),
        "tasks": [],
    }


def load_store() -> dict:
    path = get_storage_path()

    with LOCK:
        if not path.exists():
            return _empty_store()

        try:
            data = json.loads(
                path.read_text(encoding="utf-8")
            )

            if not isinstance(data, dict):
                raise ValueError("Invalid workflow data.")

            if not isinstance(data.get("tasks"), list):
                raise ValueError("Invalid task collection.")

            data.setdefault("version", 1)
            data.setdefault("updated_at", now_iso())

            return data

        except (OSError, json.JSONDecodeError, ValueError) as error:
            raise RuntimeError(
                f"Cannot read workflow storage: {error}"
            ) from error


def save_store(data: dict) -> None:
    """Save JSON atomically to avoid partially written files."""

    path = get_storage_path()

    with LOCK:
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary = path.with_name(
            path.name + ".tmp"
        )

        data["updated_at"] = now_iso()

        try:
            temporary.write_text(
                json.dumps(
                    data,
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            temporary.replace(path)

        except Exception:
            temporary.unlink(missing_ok=True)
            raise


# ---------------------------------------------------------
# Validation
# ---------------------------------------------------------

def validate_text(value: str, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text.")

    value = value.strip()

    if not value:
        raise ValueError(f"{field} is required.")

    if len(value) > 500:
        raise ValueError(f"{field} is too long.")

    return value


def find_task(data: dict, task_id: str) -> dict:
    for task in data["tasks"]:
        if task["id"] == task_id:
            return task

    raise ValueError(f"Task not found: {task_id}")


# ---------------------------------------------------------
# Task creation
# ---------------------------------------------------------

def create_task(
    title: str,
    description: str = "",
    category: str = "Custom",
    priority: str = "Normal",
    steps: list[str] | None = None,
) -> dict:

    title = validate_text(title, "Task title")

    if priority not in PRIORITIES:
        raise ValueError("Invalid priority.")

    if not isinstance(description, str):
        raise ValueError("Description must be text.")

    if len(description) > 2000:
        raise ValueError("Description is too long.")

    if not isinstance(category, str) or len(category) > 100:
        raise ValueError("Invalid category.")

    normalized_steps = []

    for step in steps or []:
        normalized_steps.append(
            validate_text(step, "Workflow step")
        )

    task = {
        "id": uuid.uuid4().hex[:12],
        "title": title,
        "description": description.strip(),
        "category": category.strip() or "Custom",
        "priority": priority,
        "status": "Pending",
        "progress": 0,
        "steps": [
            {
                "id": uuid.uuid4().hex[:8],
                "title": step,
                "completed": False,
            }
            for step in normalized_steps
        ],
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "started_at": None,
        "completed_at": None,
        "history": [
            {
                "event": "Created",
                "timestamp": now_iso(),
            }
        ],
    }

    with LOCK:
        data = load_store()
        data["tasks"].append(task)
        save_store(data)

    return task


def create_from_template(
    template_name: str,
    priority: str = "Normal",
) -> dict:

    if template_name not in WORKFLOW_TEMPLATES:
        raise ValueError("Unknown workflow template.")

    return create_task(
        title=template_name,
        description=f"Workflow generated from {template_name} template.",
        category=template_name,
        priority=priority,
        steps=WORKFLOW_TEMPLATES[template_name],
    )


# ---------------------------------------------------------
# Task updates
# ---------------------------------------------------------

def _record_event(task: dict, event: str) -> None:
    timestamp = now_iso()

    task["updated_at"] = timestamp

    task["history"].append({
        "event": event,
        "timestamp": timestamp,
    })


def update_status(
    task_id: str,
    new_status: str,
) -> dict:

    if new_status not in STATUSES:
        raise ValueError("Invalid task status.")

    with LOCK:
        data = load_store()
        task = find_task(data, task_id)

        current = task["status"]

        allowed = {
            "Pending": {"Running", "Cancelled"},
            "Running": {
                "Paused",
                "Completed",
                "Cancelled",
                "Failed",
            },
            "Paused": {"Running", "Cancelled"},
            "Completed": set(),
            "Cancelled": set(),
            "Failed": {"Pending"},
        }

        if new_status == current:
            return task

        if new_status not in allowed[current]:
            raise ValueError(
                f"Cannot change status from {current} "
                f"to {new_status}."
            )

        task["status"] = new_status

        if new_status == "Running" and not task["started_at"]:
            task["started_at"] = now_iso()

        if new_status == "Completed":
            task["progress"] = 100
            task["completed_at"] = now_iso()

            for step in task["steps"]:
                step["completed"] = True

        if new_status == "Pending":
            task["progress"] = 0
            task["completed_at"] = None

            for step in task["steps"]:
                step["completed"] = False

        _record_event(task, f"Status changed to {new_status}")

        save_store(data)

        return task


def update_progress(
    task_id: str,
    progress: int,
) -> dict:

    if isinstance(progress, bool) or not isinstance(progress, int):
        raise ValueError("Progress must be an integer.")

    if not 0 <= progress <= 100:
        raise ValueError("Progress must be between 0 and 100.")

    with LOCK:
        data = load_store()
        task = find_task(data, task_id)

        if task["status"] not in {"Pending", "Running"}:
            raise ValueError(
                "Progress can only be updated for pending or running tasks."
            )

        if progress == 100:
            task["progress"] = 100
            task["status"] = "Completed"
            task["completed_at"] = now_iso()

            for step in task["steps"]:
                step["completed"] = True

            event = "Task completed"

        else:
            task["progress"] = progress

            if progress > 0 and task["status"] == "Pending":
                task["status"] = "Running"
                task["started_at"] = now_iso()

            event = f"Progress updated to {progress}%"

        _record_event(task, event)
        save_store(data)

        return task


def update_step(
    task_id: str,
    step_id: str,
    completed: bool,
) -> dict:

    if not isinstance(completed, bool):
        raise ValueError("Step completion must be boolean.")

    with LOCK:
        data = load_store()
        task = find_task(data, task_id)

        if task["status"] not in {"Pending", "Running"}:
            raise ValueError("This task cannot be modified.")

        step = next(
            (
                item for item in task["steps"]
                if item["id"] == step_id
            ),
            None,
        )

        if step is None:
            raise ValueError("Workflow step not found.")

        step["completed"] = completed

        total = len(task["steps"])
        completed_count = sum(
            item["completed"] for item in task["steps"]
        )

        task["progress"] = (
            round(completed_count / total * 100)
            if total else 0
        )

        if task["progress"] == 100:
            task["status"] = "Completed"
            task["completed_at"] = now_iso()
            event = "All workflow steps completed"

        else:
            if task["progress"] > 0 and task["status"] == "Pending":
                task["status"] = "Running"
                task["started_at"] = now_iso()

            event = f"Step updated: {step['title']}"

        _record_event(task, event)
        save_store(data)

        return task


def update_priority(
    task_id: str,
    priority: str,
) -> dict:

    if priority not in PRIORITIES:
        raise ValueError("Invalid priority.")

    with LOCK:
        data = load_store()
        task = find_task(data, task_id)

        task["priority"] = priority

        _record_event(task, f"Priority changed to {priority}")
        save_store(data)

        return task


def delete_task(task_id: str) -> bool:
    with LOCK:
        data = load_store()

        original = len(data["tasks"])

        data["tasks"] = [
            task for task in data["tasks"]
            if task["id"] != task_id
        ]

        if len(data["tasks"]) == original:
            return False

        save_store(data)
        return True


# ---------------------------------------------------------
# Queries and analytics
# ---------------------------------------------------------

def list_tasks(
    status: str | None = None,
    category: str | None = None,
) -> list[dict]:

    data = load_store()
    tasks = data["tasks"]

    if status:
        tasks = [
            task for task in tasks
            if task["status"] == status
        ]

    if category:
        tasks = [
            task for task in tasks
            if task["category"] == category
        ]

    priority_order = {
        "Urgent": 0,
        "High": 1,
        "Normal": 2,
        "Low": 3,
    }

    return sorted(
        tasks,
        key=lambda task: (
            priority_order.get(task["priority"], 4),
            task["created_at"],
        ),
    )


def get_statistics() -> dict:
    tasks = list_tasks()

    result = {
        "total": len(tasks),
        "pending": 0,
        "running": 0,
        "paused": 0,
        "completed": 0,
        "cancelled": 0,
        "failed": 0,
        "average_progress": 0,
    }

    for task in tasks:
        key = task["status"].lower()

        if key in result:
            result[key] += 1

    if tasks:
        result["average_progress"] = round(
            sum(task["progress"] for task in tasks)
            / len(tasks)
        )

    return result


def get_history(limit: int = 30) -> list[dict]:
    events = []

    for task in list_tasks():
        for event in task.get("history", []):
            events.append({
                "task": task["title"],
                "task_id": task["id"],
                **event,
            })

    events.sort(
        key=lambda item: item["timestamp"],
        reverse=True,
    )

    return events[:max(0, limit)]


# ---------------------------------------------------------
# Streamlit interface
# ---------------------------------------------------------

def render(st):
    st.title("Workflow Manager")
    st.caption(
        "Organize and track AI Influencer Studio production workflows."
    )

    tab_dashboard, tab_create, tab_details, tab_history = st.tabs([
        "Dashboard",
        "Create Workflow",
        "Manage Tasks",
        "History",
    ])

    # -----------------------------------------------------
    # Dashboard
    # -----------------------------------------------------

    with tab_dashboard:

        stats = get_statistics()

        st.subheader("Workflow Overview")

        columns = st.columns(4)

        columns[0].metric("Total", stats["total"])
        columns[1].metric("Pending", stats["pending"])
        columns[2].metric("Running", stats["running"])
        columns[3].metric("Completed", stats["completed"])

        st.divider()

        columns = st.columns(3)

        columns[0].metric("Paused", stats["paused"])
        columns[1].metric("Failed", stats["failed"])
        columns[2].metric(
            "Average Progress",
            f"{stats['average_progress']}%"
        )

        st.subheader("Task Queue")

        tasks = list_tasks()

        if not tasks:
            st.info("No workflows created yet.")

        for task in tasks[:15]:

            with st.container(border=True):

                st.write(f"**{task['title']}**")

                st.caption(
                    f"{task['category']} · "
                    f"{task['priority']} priority · "
                    f"{task['status']}"
                )

                st.progress(task["progress"] / 100)

                st.caption(
                    f"{task['progress']}% complete"
                )

    # -----------------------------------------------------
    # Create workflow
    # -----------------------------------------------------

    with tab_create:

        st.subheader("Create from Template")

        template_name = st.selectbox(
            "Choose workflow template",
            list(WORKFLOW_TEMPLATES.keys()),
        )

        template_priority = st.selectbox(
            "Template priority",
            list(PRIORITIES),
            index=1,
            key="template_priority",
        )

        st.write("Workflow steps:")

        for index, step in enumerate(
            WORKFLOW_TEMPLATES[template_name],
            start=1,
        ):
            st.write(f"{index}. {step}")

        if st.button(
            "Create Template Workflow",
            type="primary",
            use_container_width=True,
        ):
            try:
                task = create_from_template(
                    template_name,
                    template_priority,
                )

                st.success(
                    f"Created workflow: {task['title']}"
                )

            except Exception as error:
                st.error(str(error))

        st.divider()

        st.subheader("Create Custom Workflow")

        with st.form("custom_workflow_form"):

            title = st.text_input("Workflow title")

            description = st.text_area(
                "Description",
                max_chars=2000,
            )

            category = st.text_input(
                "Category",
                value="Custom",
            )

            priority = st.selectbox(
                "Priority",
                list(PRIORITIES),
            )

            steps_text = st.text_area(
                "Workflow steps",
                placeholder=(
                    "Prepare character\n"
                    "Generate image\n"
                    "Review output\n"
                    "Save final result"
                ),
            )

            submitted = st.form_submit_button(
                "Create Custom Workflow",
                use_container_width=True,
            )

            if submitted:
                try:
                    steps = [
                        line.strip()
                        for line in steps_text.splitlines()
                        if line.strip()
                    ]

                    task = create_task(
                        title=title,
                        description=description,
                        category=category,
                        priority=priority,
                        steps=steps,
                    )

                    st.success(
                        f"Workflow created: {task['title']}"
                    )

                except Exception as error:
                    st.error(str(error))

    # -----------------------------------------------------
    # Manage tasks
    # -----------------------------------------------------

    with tab_details:

        tasks = list_tasks()

        if not tasks:
            st.info("Create a workflow to manage it here.")

        else:

            selected_id = st.selectbox(
                "Select workflow",
                [task["id"] for task in tasks],
                format_func=lambda task_id: next(
                    task["title"]
                    for task in tasks
                    if task["id"] == task_id
                ),
            )

            task = next(
                item for item in tasks
                if item["id"] == selected_id
            )

            st.subheader(task["title"])
            st.write(task["description"])

            st.write(f"Status: **{task['status']}**")
            st.write(f"Priority: **{task['priority']}**")

            st.progress(task["progress"] / 100)

            st.write("Workflow steps")

            for step in task["steps"]:

                checked = st.checkbox(
                    step["title"],
                    value=step["completed"],
                    key=f"step_{task['id']}_{step['id']}",
                    disabled=task["status"] not in {
                        "Pending", "Running"
                    },
                )

                if checked != step["completed"]:
                    try:
                        update_step(
                            task["id"],
                            step["id"],
                            checked,
                        )
                        st.rerun()

                    except Exception as error:
                        st.error(str(error))

            st.divider()

            st.write("Task controls")

            c1, c2, c3 = st.columns(3)

            if c1.button(
                "Start / Resume",
                disabled=task["status"] not in {
                    "Pending", "Paused"
                },
            ):
                update_status(task["id"], "Running")
                st.rerun()

            if c2.button(
                "Pause",
                disabled=task["status"] != "Running",
            ):
                update_status(task["id"], "Paused")
                st.rerun()

            if c3.button(
                "Complete",
                disabled=task["status"] != "Running",
            ):
                update_status(task["id"], "Completed")
                st.rerun()

            new_priority = st.selectbox(
                "Change priority",
                list(PRIORITIES),
                index=list(PRIORITIES).index(
                    task["priority"]
                ),
                key=f"priority_{task['id']}",
            )

            if st.button("Save Priority"):
                update_priority(task["id"], new_priority)
                st.success("Priority updated.")
                st.rerun()

            if task["status"] in {"Pending", "Running", "Paused"}:

                if st.button(
                    "Cancel Workflow",
                    type="secondary",
                ):
                    update_status(task["id"], "Cancelled")
                    st.rerun()

            if task["status"] in {
                "Completed", "Cancelled", "Failed"
            }:

                if st.button("Delete Workflow"):
                    delete_task(task["id"])
                    st.rerun()

            st.caption(
                "Start, pause and complete update workflow tracking "
                "only; they do not execute external AI generation."
            )

    # -----------------------------------------------------
    # History
    # -----------------------------------------------------

    with tab_history:

        st.subheader("Workflow Activity History")

        history = get_history()

        if history:
            st.dataframe(
                [
                    {
                        "Workflow": event["task"],
                        "Event": event["event"],
                        "Timestamp": event["timestamp"],
                    }
                    for event in history
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No workflow history available.")


# ---------------------------------------------------------
# Built-in tests
# ---------------------------------------------------------

def run_tests():
    import tempfile
    import unittest

    from unittest.mock import patch

    class WorkflowManagerTests(unittest.TestCase):

        def setUp(self):

            self.temp = tempfile.TemporaryDirectory()

            self.storage = (
                Path(self.temp.name) / "workflows.json"
            )

            self.patch = patch(
                __name__ + ".get_storage_path",
                return_value=self.storage,
            )

            self.patch.start()

        def tearDown(self):
            self.patch.stop()
            self.temp.cleanup()

        def test_create_task(self):
            task = create_task("Test Workflow")

            self.assertEqual(
                task["status"],
                "Pending",
            )

        def test_persistence(self):
            task = create_task("Persistent Task")

            loaded = list_tasks()

            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0]["id"], task["id"])

        def test_template_creation(self):
            task = create_from_template(
                "Video Production"
            )

            self.assertGreater(len(task["steps"]), 0)

        def test_start_and_pause(self):
            task = create_task("Pause Test")

            update_status(task["id"], "Running")
            result = update_status(task["id"], "Paused")

            self.assertEqual(result["status"], "Paused")

        def test_complete_task(self):
            task = create_task("Complete Test")

            update_status(task["id"], "Running")
            result = update_status(task["id"], "Completed")

            self.assertEqual(result["progress"], 100)

        def test_progress_update(self):
            task = create_task("Progress Test")

            result = update_progress(task["id"], 50)

            self.assertEqual(result["progress"], 50)
            self.assertEqual(result["status"], "Running")

        def test_step_completion(self):
            task = create_task(
                "Step Test",
                steps=["Step A", "Step B"],
            )

            step_id = task["steps"][0]["id"]

            result = update_step(
                task["id"],
                step_id,
                True,
            )

            self.assertEqual(result["progress"], 50)

        def test_priority_update(self):
            task = create_task("Priority Test")

            result = update_priority(
                task["id"],
                "Urgent",
            )

            self.assertEqual(result["priority"], "Urgent")

        def test_cancel_task(self):
            task = create_task("Cancel Test")

            result = update_status(
                task["id"],
                "Cancelled",
            )

            self.assertEqual(result["status"], "Cancelled")

        def test_delete_task(self):
            task = create_task("Delete Test")

            result = delete_task(task["id"])

            self.assertTrue(result)
            self.assertEqual(len(list_tasks()), 0)

        def test_statistics(self):
            task = create_task("Statistics Test")

            update_status(task["id"], "Running")

            stats = get_statistics()

            self.assertEqual(stats["total"], 1)
            self.assertEqual(stats["running"], 1)

        def test_invalid_progress(self):
            task = create_task("Invalid Progress")

            with self.assertRaises(ValueError):
                update_progress(task["id"], 150)

        def test_invalid_transition(self):
            task = create_task("Transition Test")

            with self.assertRaises(ValueError):
                update_status(task["id"], "Completed")

        def test_invalid_template(self):
            with self.assertRaises(ValueError):
                create_from_template("Unknown Template")

        def test_history(self):
            task = create_task("History Test")

            update_status(task["id"], "Running")

            history = get_history()

            self.assertGreaterEqual(len(history), 2)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        WorkflowManagerTests
    )

    result = unittest.TextTestRunner(verbosity=2).run(suite)

    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--test",
        action="store_true",
    )

    args = parser.parse_args()

    if args.test:
        run_tests()
    else:
        print("AI Influencer Studio Workflow Manager")
        print("Run through Streamlit or use:")
        print("python -m modules.workflow_manager --test")
