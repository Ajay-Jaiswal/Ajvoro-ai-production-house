
"""
AI Influencer Studio - Competitor Analyzer
File 51: modules/competitor_analyzer.py

Features:
- Save and manage competitor profiles
- Track manually collected social media posts
- Compare views, likes, comments and engagement
- Track posting frequency
- Save content ideas and observations
- Search and filter competitor records
- Export JSON and CSV reports
- Streamlit dashboard
- Built-in tests

This module does not scrape websites or claim to provide live statistics.
All metrics are manually entered by the user.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import uuid

from datetime import datetime, date
from pathlib import Path
from typing import Any


# ---------------------------------------------------------
# PATH CONFIGURATION
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs" / "competitor_analysis"

DATABASE_FILE = DATA_DIR / "competitor_analysis.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------

PLATFORMS = [
    "YouTube",
    "Instagram",
    "TikTok",
    "Facebook",
    "X",
    "Other",
]

CONTENT_TYPES = [
    "Short Video",
    "Long Video",
    "Reel",
    "Image",
    "Carousel",
    "Story",
    "Other",
]

DEFAULT_DATABASE = {
    "competitors": [],
    "posts": [],
    "ideas": [],
    "version": 1,
}


# ---------------------------------------------------------
# GENERAL HELPERS
# ---------------------------------------------------------

def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def make_id() -> str:
    return uuid.uuid4().hex


def clean_text(value: Any, max_length: int = 500) -> str:
    if value is None:
        return ""

    return str(value).strip()[:max_length]


def safe_int(value: Any, default: int = 0) -> int:
    try:
        result = int(value)
        return max(0, result)
    except (TypeError, ValueError, OverflowError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)

        if result < 0:
            return default

        return result

    except (TypeError, ValueError, OverflowError):
        return default


def safe_filename(value: str) -> str:
    value = clean_text(value, 100)

    value = re.sub(
        r"[^a-zA-Z0-9_-]+",
        "_",
        value
    )

    return value.strip("_") or "competitor_report"


def normalize_url(value: str) -> str:
    value = clean_text(value, 1000)

    if not value:
        return ""

    if not value.startswith(("http://", "https://")):
        value = "https://" + value

    return value


def valid_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
        return True
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------
# DATABASE
# ---------------------------------------------------------

def load_database() -> dict:
    if not DATABASE_FILE.exists():
        return DEFAULT_DATABASE.copy()

    try:
        with DATABASE_FILE.open(
            "r",
            encoding="utf-8"
        ) as file:
            data = json.load(file)

        if not isinstance(data, dict):
            return DEFAULT_DATABASE.copy()

        data.setdefault("competitors", [])
        data.setdefault("posts", [])
        data.setdefault("ideas", [])
        data.setdefault("version", 1)

        return data

    except (OSError, json.JSONDecodeError):
        return DEFAULT_DATABASE.copy()


def save_database(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    temporary_file = DATABASE_FILE.with_suffix(".tmp")

    with temporary_file.open(
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            data,
            file,
            indent=4,
            ensure_ascii=False
        )

    temporary_file.replace(DATABASE_FILE)


# ---------------------------------------------------------
# COMPETITOR MANAGEMENT
# ---------------------------------------------------------

def validate_competitor(data: dict) -> dict:
    name = clean_text(data.get("name"), 120)

    if not name:
        raise ValueError("Competitor name is required.")

    platform = clean_text(
        data.get("platform", "YouTube"),
        50
    )

    if platform not in PLATFORMS:
        platform = "Other"

    return {
        "id": clean_text(data.get("id")) or make_id(),
        "name": name,
        "platform": platform,
        "profile_url": normalize_url(
            data.get("profile_url", "")
        ),
        "niche": clean_text(data.get("niche"), 100),
        "description": clean_text(
            data.get("description"),
            1000
        ),
        "followers": safe_int(data.get("followers")),
        "notes": clean_text(data.get("notes"), 2000),
        "created_at": (
            data.get("created_at") or now_iso()
        ),
        "updated_at": now_iso(),
    }


def add_competitor(data: dict) -> dict:
    database = load_database()

    competitor = validate_competitor(data)

    duplicate = any(
        item.get("name", "").lower() == competitor["name"].lower()
        and item.get("platform") == competitor["platform"]
        for item in database["competitors"]
    )

    if duplicate:
        raise ValueError(
            "This competitor already exists on this platform."
        )

    database["competitors"].append(competitor)

    save_database(database)

    return competitor


def get_competitors() -> list:
    return load_database()["competitors"]


def get_competitor(competitor_id: str) -> dict | None:
    for competitor in get_competitors():
        if competitor["id"] == competitor_id:
            return competitor

    return None


def update_competitor(
    competitor_id: str,
    updates: dict
) -> dict:
    database = load_database()

    for index, competitor in enumerate(
        database["competitors"]
    ):
        if competitor["id"] == competitor_id:

            updated_data = {
                **competitor,
                **updates,
                "id": competitor_id,
            }

            updated = validate_competitor(updated_data)

            database["competitors"][index] = updated

            save_database(database)

            return updated

    raise ValueError("Competitor not found.")


def delete_competitor(competitor_id: str) -> bool:
    database = load_database()

    original_count = len(database["competitors"])

    database["competitors"] = [
        item
        for item in database["competitors"]
        if item["id"] != competitor_id
    ]

    if len(database["competitors"]) == original_count:
        return False

    # Remove associated post records.
    database["posts"] = [
        post
        for post in database["posts"]
        if post["competitor_id"] != competitor_id
    ]

    save_database(database)

    return True


# ---------------------------------------------------------
# POST TRACKING
# ---------------------------------------------------------

def validate_post(data: dict) -> dict:
    competitor_id = clean_text(
        data.get("competitor_id"),
        100
    )

    if not get_competitor(competitor_id):
        raise ValueError("Select a valid competitor.")

    title = clean_text(data.get("title"), 200)

    if not title:
        raise ValueError("Post title is required.")

    content_type = clean_text(
        data.get("content_type", "Other"),
        50
    )

    if content_type not in CONTENT_TYPES:
        content_type = "Other"

    post_date = clean_text(
        data.get("published_date"),
        20
    )

    if not post_date:
        post_date = date.today().isoformat()

    if not valid_date(post_date):
        raise ValueError(
            "Published date must use YYYY-MM-DD format."
        )

    return {
        "id": clean_text(data.get("id")) or make_id(),
        "competitor_id": competitor_id,
        "title": title,
        "platform": clean_text(
            data.get("platform", "YouTube"),
            50
        ),
        "content_type": content_type,
        "published_date": post_date,
        "url": normalize_url(data.get("url", "")),
        "views": safe_int(data.get("views")),
        "likes": safe_int(data.get("likes")),
        "comments": safe_int(data.get("comments")),
        "shares": safe_int(data.get("shares")),
        "notes": clean_text(data.get("notes"), 2000),
        "created_at": (
            data.get("created_at") or now_iso()
        ),
        "updated_at": now_iso(),
    }


def add_post(data: dict) -> dict:
    database = load_database()

    post = validate_post(data)

    database["posts"].append(post)

    save_database(database)

    return post


def get_posts(
    competitor_id: str | None = None
) -> list:
    posts = load_database()["posts"]

    if competitor_id:
        posts = [
            post
            for post in posts
            if post["competitor_id"] == competitor_id
        ]

    return sorted(
        posts,
        key=lambda item: item.get("published_date", ""),
        reverse=True
    )


def update_post(post_id: str, updates: dict) -> dict:
    database = load_database()

    for index, post in enumerate(database["posts"]):
        if post["id"] == post_id:

            updated_data = {
                **post,
                **updates,
                "id": post_id,
            }

            updated = validate_post(updated_data)

            database["posts"][index] = updated

            save_database(database)

            return updated

    raise ValueError("Post not found.")


def delete_post(post_id: str) -> bool:
    database = load_database()

    original_count = len(database["posts"])

    database["posts"] = [
        post
        for post in database["posts"]
        if post["id"] != post_id
    ]

    if len(database["posts"]) == original_count:
        return False

    save_database(database)

    return True


# ---------------------------------------------------------
# ENGAGEMENT ANALYTICS
# ---------------------------------------------------------

def calculate_engagement(post: dict) -> float:
    """
    Engagement rate based on views.

    Formula:
    (likes + comments + shares) / views * 100

    This is a simple manually tracked engagement estimate,
    not an official platform analytics metric.
    """

    views = safe_int(post.get("views"))

    if views <= 0:
        return 0.0

    interactions = (
        safe_int(post.get("likes"))
        + safe_int(post.get("comments"))
        + safe_int(post.get("shares"))
    )

    return round(
        interactions / views * 100,
        2
    )


def competitor_statistics(
    competitor_id: str
) -> dict:
    competitor_posts = get_posts(competitor_id)

    total_views = sum(
        safe_int(post.get("views"))
        for post in competitor_posts
    )

    total_likes = sum(
        safe_int(post.get("likes"))
        for post in competitor_posts
    )

    total_comments = sum(
        safe_int(post.get("comments"))
        for post in competitor_posts
    )

    total_shares = sum(
        safe_int(post.get("shares"))
        for post in competitor_posts
    )

    post_count = len(competitor_posts)

    average_views = (
        round(total_views / post_count, 2)
        if post_count else 0
    )

    total_interactions = (
        total_likes + total_comments + total_shares
    )

    engagement_rate = (
        round(total_interactions / total_views * 100, 2)
        if total_views else 0
    )

    return {
        "post_count": post_count,
        "total_views": total_views,
        "average_views": average_views,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "total_shares": total_shares,
        "engagement_rate": engagement_rate,
    }


def compare_competitors() -> list:
    results = []

    for competitor in get_competitors():
        stats = competitor_statistics(
            competitor["id"]
        )

        results.append({
            "competitor_id": competitor["id"],
            "name": competitor["name"],
            "platform": competitor["platform"],
            "niche": competitor["niche"],
            "followers": competitor["followers"],
            **stats,
        })

    return sorted(
        results,
        key=lambda item: item["average_views"],
        reverse=True
    )


def get_top_posts(limit: int = 10) -> list:
    posts = get_posts()

    return sorted(
        posts,
        key=lambda item: (
            safe_int(item.get("views")),
            safe_int(item.get("likes"))
        ),
        reverse=True
    )[:max(1, safe_int(limit, 10))]


# ---------------------------------------------------------
# CONTENT IDEAS
# ---------------------------------------------------------

def add_content_idea(data: dict) -> dict:
    title = clean_text(data.get("title"), 200)

    if not title:
        raise ValueError("Idea title is required.")

    database = load_database()

    idea = {
        "id": make_id(),
        "title": title,
        "competitor_id": clean_text(
            data.get("competitor_id"),
            100
        ),
        "description": clean_text(
            data.get("description"),
            2000
        ),
        "content_type": clean_text(
            data.get("content_type", "Other"),
            50
        ),
        "status": clean_text(
            data.get("status", "Saved"),
            30
        ),
        "created_at": now_iso(),
    }

    database["ideas"].append(idea)

    save_database(database)

    return idea


def get_content_ideas() -> list:
    return sorted(
        load_database()["ideas"],
        key=lambda item: item.get("created_at", ""),
        reverse=True
    )


def delete_content_idea(idea_id: str) -> bool:
    database = load_database()

    original_count = len(database["ideas"])

    database["ideas"] = [
        idea
        for idea in database["ideas"]
        if idea["id"] != idea_id
    ]

    if len(database["ideas"]) == original_count:
        return False

    save_database(database)

    return True


# ---------------------------------------------------------
# SEARCH
# ---------------------------------------------------------

def search_competitors(
    query: str = "",
    platform: str = "All",
    niche: str = "All"
) -> list:

    query = clean_text(query).lower()

    results = []

    for competitor in get_competitors():

        if platform != "All":
            if competitor["platform"] != platform:
                continue

        if niche != "All":
            if competitor["niche"] != niche:
                continue

        searchable = " ".join([
            competitor["name"],
            competitor["platform"],
            competitor["niche"],
            competitor["description"],
            competitor["notes"],
        ]).lower()

        if query and query not in searchable:
            continue

        results.append(competitor)

    return results


# ---------------------------------------------------------
# EXPORT
# ---------------------------------------------------------

def export_json() -> Path:
    database = load_database()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_file = OUTPUT_DIR / "competitor_report.json"

    with output_file.open(
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            database,
            file,
            indent=4,
            ensure_ascii=False
        )

    return output_file


def export_csv() -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_file = OUTPUT_DIR / "competitor_comparison.csv"

    results = compare_competitors()

    fieldnames = [
        "name",
        "platform",
        "niche",
        "followers",
        "post_count",
        "total_views",
        "average_views",
        "total_likes",
        "total_comments",
        "total_shares",
        "engagement_rate",
    ]

    with output_file.open(
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()

        for item in results:
            writer.writerow({
                key: item.get(key, "")
                for key in fieldnames
            })

    return output_file


# ---------------------------------------------------------
# STREAMLIT DASHBOARD
# ---------------------------------------------------------

def render():
    try:
        import streamlit as st
        import pandas as pd
    except ImportError:
        raise RuntimeError(
            "Install dependencies using: "
            "pip install streamlit pandas"
        )

    st.title("🔎 Competitor Analyzer")

    st.caption(
        "Track competitors, compare manually collected "
        "content metrics and discover content opportunities."
    )

    competitors = get_competitors()
    posts = get_posts()
    ideas = get_content_ideas()

    # -----------------------------------------------------
    # OVERVIEW
    # -----------------------------------------------------

    total_views = sum(
        safe_int(post.get("views"))
        for post in posts
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Competitors", len(competitors))
    col2.metric("Tracked Posts", len(posts))
    col3.metric("Total Views", f"{total_views:,}")
    col4.metric("Saved Ideas", len(ideas))

    st.divider()

    # -----------------------------------------------------
    # TABS
    # -----------------------------------------------------

    tabs = st.tabs([
        "Overview",
        "Add Competitor",
        "Track Content",
        "Compare",
        "Content Ideas",
        "Export",
    ])

    # -----------------------------------------------------
    # OVERVIEW TAB
    # -----------------------------------------------------

    with tabs[0]:

        st.subheader("Competitor Directory")

        if not competitors:
            st.info(
                "No competitors added yet. "
                "Add your first competitor to begin."
            )

        else:

            search = st.text_input(
                "Search competitors",
                key="competitor_search"
            )

            available_platforms = [
                "All",
                *PLATFORMS
            ]

            selected_platform = st.selectbox(
                "Platform filter",
                available_platforms,
                key="overview_platform"
            )

            niches = sorted({
                item["niche"]
                for item in competitors
                if item["niche"]
            })

            selected_niche = st.selectbox(
                "Niche filter",
                ["All", *niches],
                key="overview_niche"
            )

            filtered = search_competitors(
                search,
                selected_platform,
                selected_niche
            )

            for competitor in filtered:

                stats = competitor_statistics(
                    competitor["id"]
                )

                with st.expander(
                    f"{competitor['name']} — "
                    f"{competitor['platform']}"
                ):

                    st.write(
                        "**Niche:**",
                        competitor["niche"] or "Not specified"
                    )

                    st.write(
                        "**Profile:**",
                        competitor["profile_url"] or "Not provided"
                    )

                    c1, c2, c3 = st.columns(3)

                    c1.metric(
                        "Followers",
                        f"{competitor['followers']:,}"
                    )

                    c2.metric(
                        "Tracked Posts",
                        stats["post_count"]
                    )

                    c3.metric(
                        "Average Views",
                        f"{stats['average_views']:,.0f}"
                    )

                    st.write(competitor["description"])

                    if st.button(
                        "Delete Competitor",
                        key=f"delete_comp_{competitor['id']}"
                    ):
                        delete_competitor(competitor["id"])
                        st.success("Competitor deleted.")
                        st.rerun()

    # -----------------------------------------------------
    # ADD COMPETITOR TAB
    # -----------------------------------------------------

    with tabs[1]:

        st.subheader("Add New Competitor")

        with st.form("add_competitor_form"):

            name = st.text_input(
                "Competitor name *"
            )

            platform = st.selectbox(
                "Platform",
                PLATFORMS
            )

            profile_url = st.text_input(
                "Profile URL"
            )

            niche = st.text_input(
                "Content niche",
                placeholder="Example: AI movies, gaming, fitness"
            )

            followers = st.number_input(
                "Followers / subscribers",
                min_value=0,
                step=100
            )

            description = st.text_area(
                "Description"
            )

            notes = st.text_area(
                "Research notes"
            )

            submitted = st.form_submit_button(
                "Save Competitor"
            )

            if submitted:

                try:
                    add_competitor({
                        "name": name,
                        "platform": platform,
                        "profile_url": profile_url,
                        "niche": niche,
                        "followers": followers,
                        "description": description,
                        "notes": notes,
                    })

                    st.success("Competitor saved.")
                    st.rerun()

                except ValueError as error:
                    st.error(str(error))

    # -----------------------------------------------------
    # TRACK CONTENT TAB
    # -----------------------------------------------------

    with tabs[2]:

        st.subheader("Track Competitor Content")

        if not competitors:

            st.warning(
                "Add a competitor before tracking content."
            )

        else:

            competitor_options = {
                item["name"] + " (" + item["platform"] + ")":
                item["id"]
                for item in competitors
            }

            with st.form("add_post_form"):

                selected_competitor = st.selectbox(
                    "Competitor",
                    list(competitor_options.keys())
                )

                title = st.text_input("Content title *")

                content_type = st.selectbox(
                    "Content type",
                    CONTENT_TYPES
                )

                published_date = st.date_input(
                    "Published date",
                    value=date.today()
                )

                url = st.text_input("Content URL")

                st.markdown("**Performance metrics**")

                c1, c2 = st.columns(2)

                views = c1.number_input(
                    "Views",
                    min_value=0,
                    step=100
                )

                likes = c2.number_input(
                    "Likes",
                    min_value=0,
                    step=10
                )

                c3, c4 = st.columns(2)

                comments = c3.number_input(
                    "Comments",
                    min_value=0,
                    step=1
                )

                shares = c4.number_input(
                    "Shares",
                    min_value=0,
                    step=1
                )

                notes = st.text_area(
                    "Observations",
                    placeholder=(
                        "Hook, topic, thumbnail style, "
                        "storytelling, audience reaction..."
                    )
                )

                submitted = st.form_submit_button(
                    "Save Content Record"
                )

                if submitted:

                    try:
                        add_post({
                            "competitor_id": competitor_options[
                                selected_competitor
                            ],
                            "title": title,
                            "platform": selected_competitor.split(" (")[1][:-1],
                            "content_type": content_type,
                            "published_date": published_date.isoformat(),
                            "url": url,
                            "views": views,
                            "likes": likes,
                            "comments": comments,
                            "shares": shares,
                            "notes": notes,
                        })

                        st.success("Content record saved.")
                        st.rerun()

                    except ValueError as error:
                        st.error(str(error))

            st.divider()

            st.subheader("Saved Content Records")

            for post in get_posts():

                competitor = get_competitor(
                    post["competitor_id"]
                )

                competitor_name = (
                    competitor["name"]
                    if competitor else "Unknown"
                )

                with st.expander(post["title"]):

                    st.write("Competitor:", competitor_name)
                    st.write("Date:", post["published_date"])
                    st.write("Views:", f"{post['views']:,}")
                    st.write("Likes:", f"{post['likes']:,}")
                    st.write("Comments:", f"{post['comments']:,}")
                    st.write("Shares:", f"{post['shares']:,}")

                    st.metric(
                        "Estimated Engagement Rate",
                        f"{calculate_engagement(post)}%"
                    )

                    st.caption(
                        "Calculated from recorded views and "
                        "interactions; not an official platform metric."
                    )

                    if post["url"]:
                        st.markdown(
                            f"[Open Content]({post['url']})"
                        )

                    if post["notes"]:
                        st.write(post["notes"])

                    if st.button(
                        "Delete Record",
                        key=f"delete_post_{post['id']}"
                    ):
                        delete_post(post["id"])
                        st.success("Record deleted.")
                        st.rerun()

    # -----------------------------------------------------
    # COMPARE TAB
    # -----------------------------------------------------

    with tabs[3]:

        st.subheader("Competitor Performance Comparison")

        comparison = compare_competitors()

        if not comparison:

            st.info("Add competitors to compare them.")

        else:

            df = pd.DataFrame(comparison)

            display_columns = [
                "name",
                "platform",
                "niche",
                "followers",
                "post_count",
                "average_views",
                "engagement_rate",
            ]

            st.dataframe(
                df[display_columns],
                use_container_width=True,
                hide_index=True
            )

            tracked = df[df["post_count"] > 0]

            if not tracked.empty:

                st.subheader("Average Views Comparison")

                chart_data = tracked.set_index(
                    "name"
                )["average_views"]

                st.bar_chart(chart_data)

                st.subheader("Engagement Comparison")

                engagement_data = tracked.set_index(
                    "name"
                )["engagement_rate"]

                st.bar_chart(engagement_data)

            else:
                st.info(
                    "Track at least one post per competitor "
                    "to generate performance charts."
                )

            st.subheader("Top Tracked Posts")

            top_posts = get_top_posts(10)

            if top_posts:

                top_rows = []

                for post in top_posts:

                    competitor = get_competitor(
                        post["competitor_id"]
                    )

                    top_rows.append({
                        "Competitor": (
                            competitor["name"]
                            if competitor else "Unknown"
                        ),
                        "Title": post["title"],
                        "Views": post["views"],
                        "Likes": post["likes"],
                        "Engagement %": calculate_engagement(post),
                    })

                st.dataframe(
                    pd.DataFrame(top_rows),
                    use_container_width=True,
                    hide_index=True
                )

    # -----------------------------------------------------
    # CONTENT IDEAS TAB
    # -----------------------------------------------------

    with tabs[4]:

        st.subheader("Save Content Ideas")

        competitor_choices = {
            "General idea": ""
        }

        competitor_choices.update({
            item["name"]: item["id"]
            for item in competitors
        })

        with st.form("content_idea_form"):

            idea_title = st.text_input(
                "Idea title *"
            )

            idea_competitor = st.selectbox(
                "Inspired by",
                list(competitor_choices.keys())
            )

            idea_type = st.selectbox(
                "Content format",
                CONTENT_TYPES
            )

            idea_description = st.text_area(
                "Your original content approach",
                placeholder=(
                    "Describe how you can adapt this concept "
                    "with your own story, visuals and style."
                )
            )

            submitted = st.form_submit_button(
                "Save Idea"
            )

            if submitted:

                try:
                    add_content_idea({
                        "title": idea_title,
                        "competitor_id": competitor_choices[
                            idea_competitor
                        ],
                        "content_type": idea_type,
                        "description": idea_description,
                    })

                    st.success("Idea saved.")
                    st.rerun()

                except ValueError as error:
                    st.error(str(error))

        st.divider()

        for idea in get_content_ideas():

            with st.expander(idea["title"]):

                st.write(
                    "**Format:**",
                    idea["content_type"]
                )

                st.write(idea["description"])

                if st.button(
                    "Delete Idea",
                    key=f"delete_idea_{idea['id']}"
                ):
                    delete_content_idea(idea["id"])
                    st.rerun()

    # -----------------------------------------------------
    # EXPORT TAB
    # -----------------------------------------------------

    with tabs[5]:

        st.subheader("Export Competitor Research")

        database = load_database()

        json_data = json.dumps(
            database,
            indent=4,
            ensure_ascii=False
        )

        st.download_button(
            "Download Complete JSON Report",
            data=json_data,
            file_name="competitor_analysis.json",
            mime="application/json",
        )

        comparison = compare_competitors()

        if comparison:

            df = pd.DataFrame(comparison)

            csv_data = df.to_csv(
                index=False
            ).encode("utf-8-sig")

            st.download_button(
                "Download Comparison CSV",
                data=csv_data,
                file_name="competitor_comparison.csv",
                mime="text/csv",
            )

        st.caption(
            "Reports contain manually entered information "
            "stored in your local project."
        )


# ---------------------------------------------------------
# BUILT-IN TESTS
# ---------------------------------------------------------

def run_tests():
    import tempfile

    global DATA_DIR
    global DATABASE_FILE
    global OUTPUT_DIR

    original_data_dir = DATA_DIR
    original_database_file = DATABASE_FILE
    original_output_dir = OUTPUT_DIR

    try:

        with tempfile.TemporaryDirectory() as temp:

            temp_path = Path(temp)

            DATA_DIR = temp_path / "data"
            DATABASE_FILE = DATA_DIR / "test.json"
            OUTPUT_DIR = temp_path / "outputs"

            DATA_DIR.mkdir(parents=True, exist_ok=True)

            # Test empty database.
            data = load_database()

            assert data["competitors"] == []
            assert data["posts"] == []

            # Test competitor creation.
            competitor = add_competitor({
                "name": "Demo Creator",
                "platform": "YouTube",
                "niche": "AI Movies",
                "followers": 10000,
            })

            assert competitor["name"] == "Demo Creator"
            assert len(get_competitors()) == 1

            # Test duplicate prevention.
            try:
                add_competitor({
                    "name": "Demo Creator",
                    "platform": "YouTube",
                })
                raise AssertionError(
                    "Duplicate competitor was accepted."
                )
            except ValueError:
                pass

            # Test post creation.
            post = add_post({
                "competitor_id": competitor["id"],
                "title": "AI Movie Trailer",
                "published_date": "2026-01-01",
                "views": 1000,
                "likes": 100,
                "comments": 20,
                "shares": 10,
            })

            assert post["views"] == 1000

            # Test engagement.
            rate = calculate_engagement(post)

            assert rate == 13.0

            # Test statistics.
            stats = competitor_statistics(
                competitor["id"]
            )

            assert stats["post_count"] == 1
            assert stats["total_views"] == 1000
            assert stats["average_views"] == 1000

            # Test comparison.
            comparison = compare_competitors()

            assert len(comparison) == 1
            assert comparison[0]["name"] == "Demo Creator"

            # Test search.
            results = search_competitors(
                query="demo",
                platform="YouTube",
                niche="AI Movies",
            )

            assert len(results) == 1

            # Test content idea.
            idea = add_content_idea({
                "title": "Original AI Fantasy Story",
                "competitor_id": competitor["id"],
                "description": "Create a unique fantasy story.",
            })

            assert idea["title"] == "Original AI Fantasy Story"
            assert len(get_content_ideas()) == 1

            # Test exports.
            json_file = export_json()
            csv_file = export_csv()

            assert json_file.exists()
            assert csv_file.exists()

            # Test post deletion.
            assert delete_post(post["id"]) is True
            assert len(get_posts()) == 0

            # Test idea deletion.
            assert delete_content_idea(idea["id"]) is True
            assert len(get_content_ideas()) == 0

            # Test competitor deletion.
            assert delete_competitor(competitor["id"]) is True
            assert len(get_competitors()) == 0

            print("All competitor analyzer tests passed.")

    finally:

        DATA_DIR = original_data_dir
        DATABASE_FILE = original_database_file
        OUTPUT_DIR = original_output_dir


# ---------------------------------------------------------
# COMMAND LINE
# ---------------------------------------------------------

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="AI Influencer Studio Competitor Analyzer"
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
        try:
            import streamlit
            print(
                "Run the dashboard using: "
                "streamlit run app.py"
            )
        except ImportError:
            print(
                "Install Streamlit: pip install streamlit"
            )
