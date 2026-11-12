
"""
AI Influencer Studio
File 48: modules/content_calendar.py

Local content calendar and publishing planner.

Features:
- Monthly calendar
- Create, edit, delete and duplicate posts
- Platform and status management
- Search and filters
- JSON and CSV export
- Persistent local storage
- Built-in tests

Requirements:
    pip install streamlit

No external API or cloud service required.
"""

from __future__ import annotations

import argparse
import calendar
import csv
import io
import json
import uuid

from datetime import date, datetime, time
from pathlib import Path
from typing import Any


try:
    import streamlit as st
except ImportError:
    st = None


# ---------------------------------------------------------
# Paths and configuration
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
EXPORT_DIR = BASE_DIR / "outputs" / "content_calendar"

DATABASE_FILE = DATA_DIR / "content_calendar.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


PLATFORMS = [
    "YouTube",
    "YouTube Shorts",
    "Instagram",
    "Instagram Reels",
    "TikTok",
    "Facebook",
    "Facebook Reels",
    "X",
    "LinkedIn",
    "Other",
]

STATUSES = [
    "Draft",
    "Planned",
    "Ready",
    "Published",
    "Cancelled",
]

CONTENT_TYPES = [
    "Short Video",
    "Long Video",
    "Reel",
    "Image Post",
    "Carousel",
    "Story",
    "Live Stream",
    "Other",
]


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def generate_id() -> str:
    return uuid.uuid4().hex


def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def safe_filename(value: str) -> str:
    result = "".join(
        char if char.isalnum() or char in "-_"
        else "_"
        for char in str(value)
    )
    return result.strip("_") or "content_calendar"


def parse_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value

    return date.fromisoformat(str(value)[:10])


def parse_time(value: Any) -> time:
    if isinstance(value, time):
        return value

    return time.fromisoformat(str(value))


def validate_post(post: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a content post."""
    title = str(post.get("title", "")).strip()

    if not title:
        raise ValueError("Post title is required.")

    scheduled_date = parse_date(post.get("scheduled_date"))
    scheduled_time = parse_time(
        post.get("scheduled_time", "12:00")
    )

    platform = str(post.get("platform", "Other")).strip()
    if platform not in PLATFORMS:
        raise ValueError("Invalid platform.")

    status = str(post.get("status", "Draft")).strip()
    if status not in STATUSES:
        raise ValueError("Invalid status.")

    content_type = str(
        post.get("content_type", "Other")
    ).strip()

    if content_type not in CONTENT_TYPES:
        raise ValueError("Invalid content type.")

    return {
        "id": str(post.get("id") or generate_id()),
        "title": title,
        "description": str(post.get("description", "")).strip(),
        "platform": platform,
        "content_type": content_type,
        "scheduled_date": scheduled_date.isoformat(),
        "scheduled_time": scheduled_time.strftime("%H:%M"),
        "status": status,
        "hashtags": str(post.get("hashtags", "")).strip(),
        "caption": str(post.get("caption", "")).strip(),
        "asset_path": str(post.get("asset_path", "")).strip(),
        "notes": str(post.get("notes", "")).strip(),
        "created_at": str(post.get("created_at") or now_iso()),
        "updated_at": now_iso(),
    }


# ---------------------------------------------------------
# Database operations
# ---------------------------------------------------------

def load_posts() -> list[dict[str, Any]]:
    """Load posts from local JSON storage."""
    if not DATABASE_FILE.exists():
        return []

    try:
        data = json.loads(
            DATABASE_FILE.read_text(encoding="utf-8")
        )

        if not isinstance(data, list):
            return []

        valid_posts = []

        for item in data:
            if not isinstance(item, dict):
                continue

            try:
                valid_posts.append(validate_post(item))
            except (ValueError, TypeError):
                continue

        return valid_posts

    except (OSError, json.JSONDecodeError):
        return []


def save_posts(posts: list[dict[str, Any]]) -> None:
    """Save posts atomically to JSON."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    temp_file = DATABASE_FILE.with_suffix(".tmp")

    temp_file.write_text(
        json.dumps(posts, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    temp_file.replace(DATABASE_FILE)


def add_post(post_data: dict[str, Any]) -> dict[str, Any]:
    """Create a new content calendar post."""
    posts = load_posts()

    post = validate_post(post_data)

    if any(item["id"] == post["id"] for item in posts):
        raise ValueError("A post with this ID already exists.")

    posts.append(post)
    save_posts(posts)

    return post


def get_post(post_id: str) -> dict[str, Any] | None:
    """Find a post by ID."""
    for post in load_posts():
        if post["id"] == post_id:
            return post

    return None


def update_post(
    post_id: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    """Update an existing post."""
    posts = load_posts()

    for index, post in enumerate(posts):
        if post["id"] != post_id:
            continue

        merged = dict(post)
        merged.update(updates)
        merged["id"] = post_id

        updated = validate_post(merged)
        posts[index] = updated

        save_posts(posts)
        return updated

    raise ValueError("Post not found.")


def delete_post(post_id: str) -> bool:
    """Delete a post by ID."""
    posts = load_posts()
    remaining = [
        post for post in posts
        if post["id"] != post_id
    ]

    if len(remaining) == len(posts):
        return False

    save_posts(remaining)
    return True


def duplicate_post(post_id: str) -> dict[str, Any]:
    """Duplicate an existing post as a new draft."""
    original = get_post(post_id)

    if original is None:
        raise ValueError("Post not found.")

    duplicate = dict(original)
    duplicate.pop("id", None)

    duplicate["title"] = original["title"] + " (Copy)"
    duplicate["status"] = "Draft"
    duplicate["created_at"] = now_iso()
    duplicate["updated_at"] = now_iso()

    return add_post(duplicate)


# ---------------------------------------------------------
# Query and filtering
# ---------------------------------------------------------

def get_posts_for_date(
    selected_date: date,
) -> list[dict[str, Any]]:
    return [
        post for post in load_posts()
        if post["scheduled_date"] == selected_date.isoformat()
    ]


def get_posts_for_month(
    year: int,
    month: int,
) -> list[dict[str, Any]]:
    return [
        post for post in load_posts()
        if (
            parse_date(post["scheduled_date"]).year == year
            and parse_date(post["scheduled_date"]).month == month
        )
    ]


def search_posts(
    keyword: str = "",
    platform: str = "All",
    status: str = "All",
) -> list[dict[str, Any]]:
    """Search and filter content."""
    posts = load_posts()
    keyword = keyword.strip().lower()

    results = []

    for post in posts:
        if platform != "All" and post["platform"] != platform:
            continue

        if status != "All" and post["status"] != status:
            continue

        searchable = " ".join([
            post["title"],
            post["description"],
            post["caption"],
            post["hashtags"],
            post["notes"],
        ]).lower()

        if keyword and keyword not in searchable:
            continue

        results.append(post)

    return sorted(
        results,
        key=lambda item: (
            item["scheduled_date"],
            item["scheduled_time"],
        ),
    )


# ---------------------------------------------------------
# Statistics
# ---------------------------------------------------------

def get_statistics() -> dict[str, Any]:
    posts = load_posts()

    status_counts = {
        status: sum(
            1 for post in posts
            if post["status"] == status
        )
        for status in STATUSES
    }

    platform_counts = {
        platform: sum(
            1 for post in posts
            if post["platform"] == platform
        )
        for platform in PLATFORMS
    }

    today = date.today()

    upcoming = [
        post for post in posts
        if (
            parse_date(post["scheduled_date"]) >= today
            and post["status"] not in ("Published", "Cancelled")
        )
    ]

    published = status_counts["Published"]

    return {
        "total": len(posts),
        "published": published,
        "upcoming": len(upcoming),
        "drafts": status_counts["Draft"],
        "ready": status_counts["Ready"],
        "planned": status_counts["Planned"],
        "cancelled": status_counts["Cancelled"],
        "status_counts": status_counts,
        "platform_counts": platform_counts,
    }


# ---------------------------------------------------------
# Calendar generation
# ---------------------------------------------------------

def build_month_calendar(
    year: int,
    month: int,
) -> list[list[dict[str, Any]]]:
    """
    Generate a calendar grid.

    Each day contains:
        date
        day
        in_month
        posts
    """
    month_calendar = calendar.Calendar(
        firstweekday=calendar.MONDAY
    )

    posts = get_posts_for_month(year, month)

    posts_by_day: dict[int, list[dict[str, Any]]] = {}

    for post in posts:
        day_number = parse_date(
            post["scheduled_date"]
        ).day

        posts_by_day.setdefault(day_number, []).append(post)

    weeks = []

    for week in month_calendar.monthdatescalendar(year, month):
        week_data = []

        for current_day in week:
            day_posts = (
                posts_by_day.get(current_day.day, [])
                if current_day.month == month
                else []
            )

            week_data.append({
                "date": current_day.isoformat(),
                "day": current_day.day,
                "in_month": current_day.month == month,
                "posts": sorted(
                    day_posts,
                    key=lambda item: item["scheduled_time"],
                ),
            })

        weeks.append(week_data)

    return weeks


# ---------------------------------------------------------
# Export functions
# ---------------------------------------------------------

def export_json(
    output_path: str | Path | None = None,
) -> Path:
    """Export all posts to JSON."""
    path = Path(output_path) if output_path else (
        EXPORT_DIR / "content_calendar.json"
    )

    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(
            load_posts(),
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return path


def export_csv(
    output_path: str | Path | None = None,
) -> Path:
    """Export all posts to CSV."""
    path = Path(output_path) if output_path else (
        EXPORT_DIR / "content_calendar.csv"
    )

    path.parent.mkdir(parents=True, exist_ok=True)

    fields = [
        "id",
        "title",
        "description",
        "platform",
        "content_type",
        "scheduled_date",
        "scheduled_time",
        "status",
        "hashtags",
        "caption",
        "asset_path",
        "notes",
        "created_at",
        "updated_at",
    ]

    with path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fields,
        )

        writer.writeheader()

        for post in load_posts():
            writer.writerow({
                field: post.get(field, "")
                for field in fields
            })

    return path


# ---------------------------------------------------------
# Streamlit helpers
# ---------------------------------------------------------

def _post_editor(
    post: dict[str, Any] | None = None,
    key_prefix: str = "new",
) -> dict[str, Any] | None:
    """Display a reusable post creation/edit form."""
    post = post or {}

    try:
        default_date = parse_date(
            post.get("scheduled_date", date.today().isoformat())
        )
    except ValueError:
        default_date = date.today()

    try:
        default_time = parse_time(
            post.get("scheduled_time", "12:00")
        )
    except ValueError:
        default_time = time(12, 0)

    with st.form(f"content_form_{key_prefix}"):
        title = st.text_input(
            "Post title",
            value=post.get("title", ""),
        )

        description = st.text_area(
            "Description",
            value=post.get("description", ""),
        )

        col1, col2 = st.columns(2)

        with col1:
            platform = st.selectbox(
                "Platform",
                PLATFORMS,
                index=(
                    PLATFORMS.index(post["platform"])
                    if post.get("platform") in PLATFORMS
                    else 0
                ),
            )

            content_type = st.selectbox(
                "Content type",
                CONTENT_TYPES,
                index=(
                    CONTENT_TYPES.index(post["content_type"])
                    if post.get("content_type") in CONTENT_TYPES
                    else 0
                ),
            )

        with col2:
            scheduled_date = st.date_input(
                "Scheduled date",
                value=default_date,
            )

            scheduled_time = st.time_input(
                "Scheduled time",
                value=default_time,
            )

        status = st.selectbox(
            "Status",
            STATUSES,
            index=(
                STATUSES.index(post["status"])
                if post.get("status") in STATUSES
                else 0
            ),
        )

        hashtags = st.text_input(
            "Hashtags",
            value=post.get("hashtags", ""),
            placeholder="#AI #Creator #AIVideo",
        )

        caption = st.text_area(
            "Caption",
            value=post.get("caption", ""),
        )

        asset_path = st.text_input(
            "Asset file path (optional)",
            value=post.get("asset_path", ""),
        )

        notes = st.text_area(
            "Internal notes",
            value=post.get("notes", ""),
        )

        submitted = st.form_submit_button(
            "Save Content",
            type="primary",
            use_container_width=True,
        )

    if not submitted:
        return None

    return {
        "title": title,
        "description": description,
        "platform": platform,
        "content_type": content_type,
        "scheduled_date": scheduled_date.isoformat(),
        "scheduled_time": scheduled_time.strftime("%H:%M"),
        "status": status,
        "hashtags": hashtags,
        "caption": caption,
        "asset_path": asset_path,
        "notes": notes,
    }


def _render_post_details(post: dict[str, Any]) -> None:
    """Show details and management actions for one post."""
    st.markdown(f"**{post['title']}**")

    st.caption(
        f"{post['platform']} · {post['content_type']} · "
        f"{post['scheduled_date']} at {post['scheduled_time']}"
    )

    st.write(f"Status: **{post['status']}**")

    if post.get("description"):
        st.write(post["description"])

    if post.get("caption"):
        st.text_area(
            "Caption",
            value=post["caption"],
            height=100,
            key=f"caption_{post['id']}",
        )

    if post.get("hashtags"):
        st.write(post["hashtags"])

    if post.get("asset_path"):
        asset = Path(post["asset_path"])
        if asset.is_file():
            st.caption(f"Asset available: {asset.name}")
        else:
            st.caption("Asset path is saved, but file is unavailable.")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button(
            "Duplicate",
            key=f"duplicate_{post['id']}",
        ):
            duplicate_post(post["id"])
            st.success("Post duplicated.")
            st.rerun()

    with col2:
        if st.button(
            "Delete",
            key=f"delete_{post['id']}",
        ):
            delete_post(post["id"])
            st.success("Post deleted.")
            st.rerun()

    with col3:
        if st.button(
            "Mark Published",
            key=f"published_{post['id']}",
            disabled=post["status"] == "Published",
        ):
            update_post(
                post["id"],
                {"status": "Published"},
            )
            st.success("Status updated.")
            st.rerun()


# ---------------------------------------------------------
# Main Streamlit interface
# ---------------------------------------------------------

def render() -> None:
    """Render the Content Calendar application."""
    if st is None:
        raise RuntimeError(
            "Install Streamlit: pip install streamlit"
        )

    st.title("Content Calendar")
    st.caption(
        "Plan, organize and track your AI influencer content."
    )

    stats = get_statistics()

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Posts", stats["total"])
    col2.metric("Published", stats["published"])
    col3.metric("Upcoming", stats["upcoming"])
    col4.metric("Drafts", stats["drafts"])

    tab_calendar, tab_create, tab_manage, tab_export = st.tabs([
        "Monthly Calendar",
        "Create Post",
        "Manage Posts",
        "Export",
    ])

    # -----------------------------------------------------
    # Calendar tab
    # -----------------------------------------------------

    with tab_calendar:
        st.subheader("Monthly publishing calendar")

        today = date.today()

        col1, col2 = st.columns(2)

        with col1:
            selected_month = st.selectbox(
                "Month",
                list(range(1, 13)),
                index=today.month - 1,
                format_func=lambda value: calendar.month_name[value],
            )

        with col2:
            selected_year = st.number_input(
                "Year",
                min_value=2000,
                max_value=2100,
                value=today.year,
                step=1,
            )

        st.markdown(
            f"### {calendar.month_name[selected_month]} {selected_year}"
        )

        weeks = build_month_calendar(
            int(selected_year),
            int(selected_month),
        )

        headers = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]

        header_columns = st.columns(7)

        for column, header in zip(header_columns, headers):
            column.markdown(f"**{header[:3]}**")

        for week in weeks:
            columns = st.columns(7)

            for column, day_data in zip(columns, week):
                with column:
                    if not day_data["in_month"]:
                        st.caption(" ")

                    elif day_data["date"] == today.isoformat():
                        st.markdown(
                            f"**<span style='color:#2196F3'>"
                            f"{day_data['day']} · Today</span>**",
                            unsafe_allow_html=True,
                        )

                    else:
                        st.markdown(f"**{day_data['day']}**")

                    for item in day_data["posts"][:3]:
                        status_symbol = {
                            "Draft": "📝",
                            "Planned": "📅",
                            "Ready": "✅",
                            "Published": "🚀",
                            "Cancelled": "❌",
                        }.get(item["status"], "•")

                        st.caption(
                            f"{status_symbol} "
                            f"{item['scheduled_time']} "
                            f"{item['title'][:18]}"
                        )

                    if len(day_data["posts"]) > 3:
                        st.caption(
                            f"+{len(day_data['posts']) - 3} more"
                        )

        st.divider()

        selected_day = st.date_input(
            "View posts for a particular date",
            value=today,
            key="calendar_selected_day",
        )

        day_posts = get_posts_for_date(selected_day)

        st.markdown(
            f"**Posts on {selected_day.strftime('%d %B %Y')}**"
        )

        if not day_posts:
            st.info("No content planned for this date.")
        else:
            for post in day_posts:
                with st.expander(post["title"]):
                    _render_post_details(post)

    # -----------------------------------------------------
    # Create tab
    # -----------------------------------------------------

    with tab_create:
        st.subheader("Create new content")

        form_data = _post_editor(
            key_prefix="create",
        )

        if form_data is not None:
            try:
                post = add_post(form_data)
                st.success(
                    f"Post created successfully: {post['title']}"
                )
                st.rerun()

            except Exception as exc:
                st.error(f"Unable to create post: {exc}")

    # -----------------------------------------------------
    # Manage tab
    # -----------------------------------------------------

    with tab_manage:
        st.subheader("Search and manage content")

        keyword = st.text_input(
            "Search posts",
            placeholder="Search by title, description or hashtag...",
        )

        col1, col2 = st.columns(2)

        with col1:
            selected_platform = st.selectbox(
                "Filter platform",
                ["All"] + PLATFORMS,
            )

        with col2:
            selected_status = st.selectbox(
                "Filter status",
                ["All"] + STATUSES,
            )

        results = search_posts(
            keyword,
            selected_platform,
            selected_status,
        )

        st.caption(f"{len(results)} matching posts")

        for post in results:
            with st.expander(
                f"{post['title']} · {post['scheduled_date']}"
            ):
                _render_post_details(post)

                st.divider()
                st.markdown("**Edit this post**")

                edited_data = _post_editor(
                    post,
                    key_prefix=f"edit_{post['id']}",
                )

                if edited_data is not None:
                    try:
                        update_post(post["id"], edited_data)
                        st.success("Post updated.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Update failed: {exc}")

    # -----------------------------------------------------
    # Export tab
    # -----------------------------------------------------

    with tab_export:
        st.subheader("Export your content calendar")

        all_posts = load_posts()

        if not all_posts:
            st.info("Create some posts before exporting.")
        else:
            st.write(f"Ready to export {len(all_posts)} posts.")

            json_data = json.dumps(
                all_posts,
                indent=2,
                ensure_ascii=False,
            )

            csv_buffer = io.StringIO()

            fields = [
                "id",
                "title",
                "description",
                "platform",
                "content_type",
                "scheduled_date",
                "scheduled_time",
                "status",
                "hashtags",
                "caption",
                "asset_path",
                "notes",
            ]

            writer = csv.DictWriter(
                csv_buffer,
                fieldnames=fields,
            )
            writer.writeheader()

            for post in all_posts:
                writer.writerow({
                    field: post.get(field, "")
                    for field in fields
                })

            col1, col2 = st.columns(2)

            with col1:
                st.download_button(
                    "Download JSON",
                    data=json_data.encode("utf-8"),
                    file_name="content_calendar.json",
                    mime="application/json",
                    use_container_width=True,
                )

            with col2:
                st.download_button(
                    "Download CSV",
                    data=csv_buffer.getvalue().encode("utf-8-sig"),
                    file_name="content_calendar.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

            st.divider()

            st.markdown("**Content status overview**")

            for status, count in stats["status_counts"].items():
                st.write(f"{status}: {count}")


# ---------------------------------------------------------
# Built-in tests
# ---------------------------------------------------------

def run_tests() -> None:
    """Run isolated tests using a temporary database."""
    global DATABASE_FILE

    original_database = DATABASE_FILE
    test_file = DATA_DIR / f"test_calendar_{uuid.uuid4().hex}.json"

    DATABASE_FILE = test_file

    try:
        save_posts([])
        assert load_posts() == []

        post = add_post({
            "title": "Test AI Reel",
            "description": "Testing calendar",
            "platform": "Instagram Reels",
            "content_type": "Reel",
            "scheduled_date": "2026-11-15",
            "scheduled_time": "18:30",
            "status": "Planned",
            "hashtags": "#AI #Creator",
        })

        assert post["title"] == "Test AI Reel"
        assert len(load_posts()) == 1

        found = get_post(post["id"])
        assert found is not None

        updated = update_post(
            post["id"],
            {"status": "Ready"},
        )
        assert updated["status"] == "Ready"

        duplicated = duplicate_post(post["id"])
        assert duplicated["id"] != post["id"]
        assert duplicated["status"] == "Draft"
        assert len(load_posts()) == 2

        filtered = search_posts(
            keyword="AI Reel",
            platform="Instagram Reels",
            status="Ready",
        )
        assert len(filtered) == 1

        month_posts = get_posts_for_month(2026, 11)
        assert len(month_posts) == 2

        grid = build_month_calendar(2026, 11)
        assert len(grid) in (4, 5, 6)
        assert all(len(week) == 7 for week in grid)

        stats = get_statistics()
        assert stats["total"] == 2
        assert stats["ready"] == 1
        assert stats["drafts"] == 1

        assert delete_post(duplicated["id"]) is True
        assert delete_post("missing-id") is False
        assert len(load_posts()) == 1

        try:
            validate_post({
                "title": "",
                "scheduled_date": "2026-11-15",
            })
            raise AssertionError("Empty title should fail.")
        except ValueError:
            pass

        try:
            validate_post({
                "title": "Invalid platform",
                "platform": "Unknown Platform",
                "scheduled_date": "2026-11-15",
            })
            raise AssertionError("Invalid platform should fail.")
        except ValueError:
            pass

        print("All Content Calendar tests passed.")

    finally:
        DATABASE_FILE = original_database
        test_file.unlink(missing_ok=True)


# ---------------------------------------------------------
# Command line entry point
# ---------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AI Influencer Studio Content Calendar"
    )

    parser.add_argument(
        "--test",
        action="store_true",
        help="Run built-in tests.",
    )

    args = parser.parse_args()

    if args.test:
        run_tests()
    else:
        print("Content Calendar module")
        print("Import it into your Streamlit application.")
        print(
            "Run tests with: "
            "python -m modules.content_calendar --test"
        )
