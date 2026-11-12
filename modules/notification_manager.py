
"""
AI Influencer Studio
File 23: modules/notification_manager.py

Local notification center:
- Success, info, warning and error notifications
- Persistent JSON notification history
- Read/unread tracking
- Notification filtering
- Delete and clear notifications
- Workflow event notifications
- Streamlit dashboard
- Built-in tests

Run:
    python -m modules.notification_manager --test

Integration:
    from modules import notification_manager
    notification_manager.render(st)
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import uuid

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MAX_NOTIFICATIONS = 500

VALID_TYPES = {
    "success",
    "info",
    "warning",
    "error",
}

VALID_CATEGORIES = {
    "general",
    "workflow",
    "character",
    "image",
    "video",
    "voice",
    "motion",
    "storage",
    "system",
}


def current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_notification_path() -> Path:
    """Resolve the notification JSON file."""
    try:
        import config

        for name in (
            "NOTIFICATION_FILE",
            "NOTIFICATION_PATH",
        ):
            value = getattr(config, name, None)
            if value:
                path = Path(value)
                if not path.is_absolute():
                    path = (
                        Path(__file__).resolve().parent.parent / path
                    )
                return path

        for name in ("DATA_DIR", "DATA_PATH"):
            value = getattr(config, name, None)
            if value:
                folder = Path(value)
                if not folder.is_absolute():
                    folder = (
                        Path(__file__).resolve().parent.parent / folder
                    )
                return folder / "notifications.json"

    except Exception:
        pass

    return (
        Path(__file__).resolve().parent.parent
        / "data"
        / "notifications.json"
    )


def _empty_store() -> dict:
    return {
        "version": 1,
        "notifications": [],
    }


def _normalize_store(data: Any) -> dict:
    """Validate the notification store structure."""
    if not isinstance(data, dict):
        return _empty_store()

    notifications = data.get("notifications", [])

    if not isinstance(notifications, list):
        return _empty_store()

    valid = []

    for item in notifications:
        if not isinstance(item, dict):
            continue

        if not isinstance(item.get("id"), str):
            continue

        if not isinstance(item.get("title"), str):
            continue

        if not isinstance(item.get("message"), str):
            continue

        item_type = item.get("type", "info")
        category = item.get("category", "general")

        if item_type not in VALID_TYPES:
            item_type = "info"

        if category not in VALID_CATEGORIES:
            category = "general"

        valid.append({
            "id": item["id"],
            "title": item["title"][:200],
            "message": item["message"][:2000],
            "type": item_type,
            "category": category,
            "created_at": str(item.get("created_at", "")),
            "read": bool(item.get("read", False)),
            "metadata": (
                item.get("metadata")
                if isinstance(item.get("metadata"), dict)
                else {}
            ),
        })

    return {
        "version": 1,
        "notifications": valid[-MAX_NOTIFICATIONS:],
    }


def load_store() -> dict:
    """Load notification history."""
    path = get_notification_path()

    if not path.exists():
        return _empty_store()

    try:
        with path.open("r", encoding="utf-8") as file:
            return _normalize_store(json.load(file))
    except (OSError, json.JSONDecodeError):
        return _empty_store()


def save_store(store: dict) -> tuple[bool, str]:
    """Atomically save notification history."""
    path = get_notification_path()
    temp_path = None

    try:
        path.parent.mkdir(parents=True, exist_ok=True)

        normalized = _normalize_store(store)

        fd, temp_name = tempfile.mkstemp(
            prefix="notifications_",
            suffix=".tmp",
            dir=str(path.parent),
        )
        temp_path = Path(temp_name)

        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(
                normalized,
                file,
                indent=4,
                ensure_ascii=False,
            )
            file.flush()
            os.fsync(file.fileno())

        os.replace(temp_path, path)
        return True, "Saved"

    except OSError as exc:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)

        return False, str(exc)


def create_notification(
    title: str,
    message: str,
    notification_type: str = "info",
    category: str = "general",
    metadata: dict | None = None,
) -> tuple[bool, dict | str]:
    """Create and persist a notification."""
    if not isinstance(title, str) or not title.strip():
        return False, "Notification title is required."

    if not isinstance(message, str) or not message.strip():
        return False, "Notification message is required."

    if notification_type not in VALID_TYPES:
        return False, "Invalid notification type."

    if category not in VALID_CATEGORIES:
        return False, "Invalid notification category."

    if metadata is not None and not isinstance(metadata, dict):
        return False, "Metadata must be a dictionary."

    notification = {
        "id": uuid.uuid4().hex,
        "title": title.strip()[:200],
        "message": message.strip()[:2000],
        "type": notification_type,
        "category": category,
        "created_at": current_timestamp(),
        "read": False,
        "metadata": metadata or {},
    }

    store = load_store()
    store["notifications"].append(notification)
    store["notifications"] = (
        store["notifications"][-MAX_NOTIFICATIONS:]
    )

    success, error = save_store(store)

    if not success:
        return False, error

    return True, notification


def success(title: str, message: str, category="general"):
    return create_notification(
        title, message, "success", category
    )


def info(title: str, message: str, category="general"):
    return create_notification(
        title, message, "info", category
    )


def warning(title: str, message: str, category="general"):
    return create_notification(
        title, message, "warning", category
    )


def error(title: str, message: str, category="general"):
    return create_notification(
        title, message, "error", category
    )


def list_notifications(
    category: str | None = None,
    unread_only: bool = False,
    limit: int | None = None,
) -> list[dict]:
    """Return newest notifications first."""
    notifications = load_store()["notifications"]

    if category and category != "all":
        notifications = [
            item for item in notifications
            if item["category"] == category
        ]

    if unread_only:
        notifications = [
            item for item in notifications
            if not item["read"]
        ]

    notifications = list(reversed(notifications))

    if limit is not None:
        limit = max(0, int(limit))
        notifications = notifications[:limit]

    return notifications


def unread_count() -> int:
    return sum(
        1 for item in load_store()["notifications"]
        if not item["read"]
    )


def mark_as_read(notification_id: str) -> tuple[bool, str]:
    store = load_store()

    for item in store["notifications"]:
        if item["id"] == notification_id:
            item["read"] = True
            return save_store(store)

    return False, "Notification not found."


def mark_all_as_read() -> tuple[bool, str]:
    store = load_store()

    for item in store["notifications"]:
        item["read"] = True

    return save_store(store)


def delete_notification(notification_id: str) -> tuple[bool, str]:
    store = load_store()
    original_count = len(store["notifications"])

    store["notifications"] = [
        item for item in store["notifications"]
        if item["id"] != notification_id
    ]

    if len(store["notifications"]) == original_count:
        return False, "Notification not found."

    return save_store(store)


def clear_notifications(
    unread_only: bool = False,
) -> tuple[bool, str]:
    store = load_store()

    if unread_only:
        store["notifications"] = [
            item for item in store["notifications"]
            if item["read"]
        ]
    else:
        store["notifications"] = []

    return save_store(store)


def get_statistics() -> dict:
    notifications = load_store()["notifications"]

    stats = {
        "total": len(notifications),
        "unread": 0,
        "read": 0,
        "types": {},
        "categories": {},
    }

    for item in notifications:
        if item["read"]:
            stats["read"] += 1
        else:
            stats["unread"] += 1

        item_type = item["type"]
        category = item["category"]

        stats["types"][item_type] = (
            stats["types"].get(item_type, 0) + 1
        )

        stats["categories"][category] = (
            stats["categories"].get(category, 0) + 1
        )

    return stats


def notify_workflow_event(
    task_title: str,
    event: str,
    details: str = "",
) -> tuple[bool, dict | str]:
    """Create a notification for a workflow lifecycle event."""
    event = event.lower().strip()

    event_config = {
        "completed": (
            "Workflow completed",
            "success",
            "Your workflow finished successfully.",
        ),
        "failed": (
            "Workflow failed",
            "error",
            "Your workflow encountered an error.",
        ),
        "paused": (
            "Workflow paused",
            "warning",
            "Your workflow has been paused.",
        ),
        "started": (
            "Workflow started",
            "info",
            "Your workflow has started.",
        ),
        "cancelled": (
            "Workflow cancelled",
            "warning",
            "Your workflow was cancelled.",
        ),
    }

    if event not in event_config:
        return False, "Unsupported workflow event."

    title, item_type, default_message = event_config[event]

    message = f"{task_title}: {default_message}"

    if details:
        message += f" Details: {details}"

    return create_notification(
        title=title,
        message=message,
        notification_type=item_type,
        category="workflow",
        metadata={
            "task_title": task_title,
            "event": event,
        },
    )


def render(st) -> None:
    """Render the Streamlit notification center."""
    st.title("Notification Center")
    st.caption("View studio alerts, workflow updates and activity.")

    stats = get_statistics()

    col1, col2, col3 = st.columns(3)

    col1.metric("Total notifications", stats["total"])
    col2.metric("Unread", stats["unread"])
    col3.metric("Read", stats["read"])

    st.divider()

    tab_inbox, tab_stats = st.tabs([
        "Inbox",
        "Statistics",
    ])

    with tab_inbox:
        filter_col, status_col = st.columns(2)

        with filter_col:
            category = st.selectbox(
                "Category",
                ["all"] + sorted(VALID_CATEGORIES),
            )

        with status_col:
            status = st.selectbox(
                "Status",
                ["All", "Unread", "Read"],
            )

        notifications = list_notifications(
            category=category,
            unread_only=(status == "Unread"),
        )

        if status == "Read":
            notifications = [
                item for item in notifications
                if item["read"]
            ]

        action_col1, action_col2 = st.columns(2)

        with action_col1:
            if st.button("Mark all as read"):
                ok, message = mark_all_as_read()
                if ok:
                    st.success("All notifications marked as read.")
                    st.rerun()
                else:
                    st.error(message)

        with action_col2:
            if st.button("Clear all notifications"):
                ok, message = clear_notifications()
                if ok:
                    st.success("Notification history cleared.")
                    st.rerun()
                else:
                    st.error(message)

        st.divider()

        if not notifications:
            st.info("No notifications found.")
        else:
            icons = {
                "success": "✅",
                "info": "ℹ️",
                "warning": "⚠️",
                "error": "❌",
            }

            for item in notifications:
                with st.container(border=True):
                    header_col, status_col = st.columns([4, 1])

                    with header_col:
                        st.markdown(
                            f"**{icons[item['type']]} "
                            f"{item['title']}**"
                        )

                    with status_col:
                        st.caption(
                            "Read" if item["read"] else "Unread"
                        )

                    st.write(item["message"])

                    st.caption(
                        f"Category: {item['category']} | "
                        f"Date: {item['created_at']}"
                    )

                    if item["metadata"]:
                        with st.expander("Additional information"):
                            st.json(item["metadata"])

                    button_col1, button_col2 = st.columns(2)

                    with button_col1:
                        if not item["read"]:
                            if st.button(
                                "Mark as read",
                                key=f"read_{item['id']}",
                            ):
                                mark_as_read(item["id"])
                                st.rerun()

                    with button_col2:
                        if st.button(
                            "Delete",
                            key=f"delete_{item['id']}",
                        ):
                            delete_notification(item["id"])
                            st.rerun()

    with tab_stats:
        st.subheader("Notification breakdown")

        if stats["types"]:
            st.write("By notification type")
            st.json(stats["types"])

        if stats["categories"]:
            st.write("By category")
            st.json(stats["categories"])


def run_tests() -> bool:
    """Run isolated tests without changing real user data."""
    import unittest
    from unittest.mock import patch

    class NotificationTests(unittest.TestCase):

        def setUp(self):
            self.temp_dir = tempfile.TemporaryDirectory()
            self.test_path = (
                Path(self.temp_dir.name) / "notifications.json"
            )

            self.path_patch = patch(
                __name__ + ".get_notification_path",
                return_value=self.test_path,
            )
            self.path_patch.start()

        def tearDown(self):
            self.path_patch.stop()
            self.temp_dir.cleanup()

        def test_create_notification(self):
            ok, item = success(
                "Test success",
                "Test message",
            )
            self.assertTrue(ok)
            self.assertEqual(item["type"], "success")

        def test_persistence(self):
            success("Saved", "Persistent message")
            self.assertEqual(len(list_notifications()), 1)

        def test_unread_count(self):
            success("One", "First")
            info("Two", "Second")
            self.assertEqual(unread_count(), 2)

        def test_mark_as_read(self):
            ok, item = info("Read test", "Message")
            self.assertTrue(ok)

            ok, message = mark_as_read(item["id"])
            self.assertTrue(ok, message)
            self.assertEqual(unread_count(), 0)

        def test_mark_all_as_read(self):
            success("A", "First")
            warning("B", "Second")

            ok, message = mark_all_as_read()
            self.assertTrue(ok, message)
            self.assertEqual(unread_count(), 0)

        def test_delete_notification(self):
            ok, item = info("Delete", "Message")
            self.assertTrue(ok)

            ok, message = delete_notification(item["id"])
            self.assertTrue(ok, message)
            self.assertEqual(len(list_notifications()), 0)

        def test_clear_notifications(self):
            success("A", "First")
            info("B", "Second")

            ok, message = clear_notifications()
            self.assertTrue(ok, message)
            self.assertEqual(len(list_notifications()), 0)

        def test_filter_by_category(self):
            success("Image", "Generated", category="image")
            info("System", "Started", category="system")

            results = list_notifications(category="image")
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["category"], "image")

        def test_workflow_completed(self):
            ok, item = notify_workflow_event(
                "Video generation",
                "completed",
            )
            self.assertTrue(ok)
            self.assertEqual(item["category"], "workflow")
            self.assertEqual(item["type"], "success")

        def test_invalid_type_rejected(self):
            ok, message = create_notification(
                "Invalid",
                "Message",
                notification_type="unknown",
            )
            self.assertFalse(ok)

        def test_invalid_category_rejected(self):
            ok, message = create_notification(
                "Invalid",
                "Message",
                category="unknown",
            )
            self.assertFalse(ok)

        def test_empty_title_rejected(self):
            ok, message = create_notification(
                "",
                "Message",
            )
            self.assertFalse(ok)

        def test_max_notification_limit(self):
            store = _empty_store()

            for index in range(MAX_NOTIFICATIONS + 10):
                store["notifications"].append({
                    "id": str(index),
                    "title": f"Title {index}",
                    "message": "Message",
                    "type": "info",
                    "category": "general",
                    "created_at": current_timestamp(),
                    "read": False,
                    "metadata": {},
                })

            normalized = _normalize_store(store)
            self.assertEqual(
                len(normalized["notifications"]),
                MAX_NOTIFICATIONS,
            )

        def test_statistics(self):
            success("Success", "Message")
            error("Error", "Message")

            stats = get_statistics()
            self.assertEqual(stats["total"], 2)
            self.assertEqual(stats["unread"], 2)
            self.assertEqual(stats["types"]["success"], 1)
            self.assertEqual(stats["types"]["error"], 1)

        def test_missing_notification(self):
            ok, message = mark_as_read("not-existing")
            self.assertFalse(ok)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        NotificationTests
    )

    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AI Influencer Studio Notification Manager"
    )

    parser.add_argument(
        "--test",
        action="store_true",
        help="Run built-in tests",
    )

    args = parser.parse_args()

    if args.test:
        raise SystemExit(0 if run_tests() else 1)

    print("Notification Manager loaded.")
    print("Run with --test to execute built-in tests.")
