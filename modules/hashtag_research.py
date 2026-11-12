
"""
AI Influencer Studio
File 49: modules/hashtag_research.py

Local Hashtag Research and Organizer.

Features:
- Hashtag library
- Niche/category management
- Saved hashtag collections
- Platform-specific hashtag sets
- Search and filtering
- Manual usage/performance notes
- Caption builder
- JSON and CSV import/export
- Built-in tests

Requirements:
    pip install streamlit

No paid APIs or cloud services required.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import uuid

from datetime import datetime, timezone
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
OUTPUT_DIR = BASE_DIR / "outputs" / "hashtag_research"

DATABASE_FILE = DATA_DIR / "hashtag_library.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


PLATFORMS = [
    "YouTube",
    "YouTube Shorts",
    "Instagram",
    "Instagram Reels",
    "TikTok",
    "Facebook",
    "X",
    "LinkedIn",
    "General",
]

CATEGORIES = [
    "AI",
    "Technology",
    "Fashion",
    "Beauty",
    "Fitness",
    "Travel",
    "Food",
    "Gaming",
    "Education",
    "Entertainment",
    "Business",
    "Lifestyle",
    "Photography",
    "Movies",
    "Custom",
]


# ---------------------------------------------------------
# Utility functions
# ---------------------------------------------------------

def generate_id() -> str:
    return uuid.uuid4().hex


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_hashtag(value: str) -> str:
    """Normalize a single hashtag."""
    value = str(value).strip()

    if not value:
        raise ValueError("Hashtag cannot be empty.")

    value = value.lstrip("#")
    value = re.sub(r"[^\w]", "", value, flags=re.UNICODE)

    if not value:
        raise ValueError("Hashtag contains no valid characters.")

    return "#" + value


def normalize_hashtags(
    values: str | list[str] | tuple[str, ...],
) -> list[str]:
    """Convert text or a list into unique normalized hashtags."""
    if isinstance(values, str):
        candidates = re.split(r"[\s,;]+", values)
    else:
        candidates = list(values)

    results = []
    seen = set()

    for candidate in candidates:
        candidate = str(candidate).strip()

        if not candidate:
            continue

        try:
            tag = normalize_hashtag(candidate)
        except ValueError:
            continue

        if tag.lower() not in seen:
            results.append(tag)
            seen.add(tag.lower())

    return results


def safe_filename(value: str) -> str:
    cleaned = "".join(
        char if char.isalnum() or char in "-_"
        else "_"
        for char in str(value)
    )
    return cleaned.strip("_") or "hashtags"


# ---------------------------------------------------------
# Database
# ---------------------------------------------------------

def empty_database() -> dict[str, Any]:
    return {
        "hashtags": [],
        "collections": [],
        "version": 1,
    }


def load_database() -> dict[str, Any]:
    """Load local hashtag database."""
    if not DATABASE_FILE.exists():
        return empty_database()

    try:
        data = json.loads(
            DATABASE_FILE.read_text(encoding="utf-8")
        )

        if not isinstance(data, dict):
            return empty_database()

        return {
            "hashtags": (
                data.get("hashtags", [])
                if isinstance(data.get("hashtags"), list)
                else []
            ),
            "collections": (
                data.get("collections", [])
                if isinstance(data.get("collections"), list)
                else []
            ),
            "version": data.get("version", 1),
        }

    except (OSError, json.JSONDecodeError):
        return empty_database()


def save_database(data: dict[str, Any]) -> None:
    """Save database atomically."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    temp_file = DATABASE_FILE.with_suffix(".tmp")

    temp_file.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    temp_file.replace(DATABASE_FILE)


# ---------------------------------------------------------
# Hashtag validation
# ---------------------------------------------------------

def validate_hashtag(data: dict[str, Any]) -> dict[str, Any]:
    tag = normalize_hashtag(data.get("tag", ""))

    category = str(
        data.get("category", "Custom")
    ).strip()

    if category not in CATEGORIES:
        category = "Custom"

    platforms = data.get("platforms", ["General"])

    if not isinstance(platforms, list):
        platforms = ["General"]

    platforms = [
        platform for platform in platforms
        if platform in PLATFORMS
    ]

    if not platforms:
        platforms = ["General"]

    try:
        usage_count = max(
            0,
            int(data.get("usage_count", 0)),
        )
    except (ValueError, TypeError):
        usage_count = 0

    return {
        "id": str(data.get("id") or generate_id()),
        "tag": tag,
        "category": category,
        "platforms": platforms,
        "niche": str(data.get("niche", "")).strip(),
        "notes": str(data.get("notes", "")).strip(),
        "usage_count": usage_count,
        "performance_notes": str(
            data.get("performance_notes", "")
        ).strip(),
        "created_at": str(
            data.get("created_at") or now_iso()
        ),
        "updated_at": now_iso(),
    }


# ---------------------------------------------------------
# Hashtag CRUD
# ---------------------------------------------------------

def get_all_hashtags() -> list[dict[str, Any]]:
    return load_database()["hashtags"]


def get_hashtag(tag_id: str) -> dict[str, Any] | None:
    for item in get_all_hashtags():
        if item.get("id") == tag_id:
            return item

    return None


def add_hashtag(data: dict[str, Any]) -> dict[str, Any]:
    database = load_database()
    hashtag = validate_hashtag(data)

    duplicate = next(
        (
            item for item in database["hashtags"]
            if item["tag"].lower() == hashtag["tag"].lower()
        ),
        None,
    )

    if duplicate:
        raise ValueError(
            f"{hashtag['tag']} already exists in your library."
        )

    database["hashtags"].append(hashtag)
    save_database(database)

    return hashtag


def update_hashtag(
    tag_id: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    database = load_database()

    for index, item in enumerate(database["hashtags"]):
        if item["id"] != tag_id:
            continue

        merged = dict(item)
        merged.update(updates)
        merged["id"] = tag_id

        updated = validate_hashtag(merged)

        for other in database["hashtags"]:
            if (
                other["id"] != tag_id
                and other["tag"].lower() == updated["tag"].lower()
            ):
                raise ValueError("This hashtag already exists.")

        database["hashtags"][index] = updated
        save_database(database)

        return updated

    raise ValueError("Hashtag not found.")


def delete_hashtag(tag_id: str) -> bool:
    database = load_database()

    original_count = len(database["hashtags"])

    database["hashtags"] = [
        item for item in database["hashtags"]
        if item["id"] != tag_id
    ]

    if len(database["hashtags"]) == original_count:
        return False

    # Remove the deleted hashtag from all saved collections.
    deleted_tag = None

    # Find collection references by ID and remove them.
    for collection in database["collections"]:
        collection["hashtag_ids"] = [
            item_id for item_id in collection.get("hashtag_ids", [])
            if item_id != tag_id
        ]

    save_database(database)
    return True


def record_hashtag_usage(tag_id: str) -> dict[str, Any]:
    item = get_hashtag(tag_id)

    if item is None:
        raise ValueError("Hashtag not found.")

    return update_hashtag(
        tag_id,
        {"usage_count": item.get("usage_count", 0) + 1},
    )


# ---------------------------------------------------------
# Hashtag search and filtering
# ---------------------------------------------------------

def search_hashtags(
    keyword: str = "",
    category: str = "All",
    platform: str = "All",
) -> list[dict[str, Any]]:
    keyword = keyword.strip().lower()

    results = []

    for item in get_all_hashtags():
        if category != "All" and item["category"] != category:
            continue

        if (
            platform != "All"
            and platform not in item["platforms"]
            and "General" not in item["platforms"]
        ):
            continue

        searchable = " ".join([
            item["tag"],
            item["category"],
            item["niche"],
            item["notes"],
            item["performance_notes"],
        ]).lower()

        if keyword and keyword not in searchable:
            continue

        results.append(item)

    return sorted(
        results,
        key=lambda item: (
            -item["usage_count"],
            item["tag"].lower(),
        ),
    )


def get_category_statistics() -> dict[str, int]:
    results = {category: 0 for category in CATEGORIES}

    for item in get_all_hashtags():
        category = item["category"]
        results[category] = results.get(category, 0) + 1

    return results


# ---------------------------------------------------------
# Collections
# ---------------------------------------------------------

def create_collection(
    name: str,
    hashtag_ids: list[str],
    platform: str = "General",
    description: str = "",
) -> dict[str, Any]:
    name = str(name).strip()

    if not name:
        raise ValueError("Collection name is required.")

    if platform not in PLATFORMS:
        raise ValueError("Invalid platform.")

    database = load_database()

    valid_ids = {
        item["id"] for item in database["hashtags"]
    }

    unique_ids = list(dict.fromkeys(
        item_id for item_id in hashtag_ids
        if item_id in valid_ids
    ))

    collection = {
        "id": generate_id(),
        "name": name,
        "platform": platform,
        "description": str(description).strip(),
        "hashtag_ids": unique_ids,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }

    database["collections"].append(collection)
    save_database(database)

    return collection


def get_collections() -> list[dict[str, Any]]:
    return load_database()["collections"]


def get_collection_hashtags(
    collection_id: str,
) -> list[dict[str, Any]]:
    database = load_database()

    collection = next(
        (
            item for item in database["collections"]
            if item["id"] == collection_id
        ),
        None,
    )

    if collection is None:
        raise ValueError("Collection not found.")

    id_set = set(collection.get("hashtag_ids", []))

    return [
        item for item in database["hashtags"]
        if item["id"] in id_set
    ]


def delete_collection(collection_id: str) -> bool:
    database = load_database()

    original_count = len(database["collections"])

    database["collections"] = [
        item for item in database["collections"]
        if item["id"] != collection_id
    ]

    if len(database["collections"]) == original_count:
        return False

    save_database(database)
    return True


# ---------------------------------------------------------
# Hashtag generation
# ---------------------------------------------------------

def generate_hashtag_set(
    keyword: str,
    category: str = "All",
    platform: str = "All",
    limit: int = 15,
) -> list[str]:
    """
    Generate a set from saved hashtags.

    This uses local library matches, not live trend data.
    """
    if limit < 1:
        raise ValueError("Limit must be at least 1.")

    results = search_hashtags(
        keyword=keyword,
        category=category,
        platform=platform,
    )

    return [
        item["tag"]
        for item in results[:limit]
    ]


def build_caption(
    caption: str,
    hashtags: list[str],
    *,
    include_line_break: bool = True,
) -> str:
    """Combine a caption with a unique hashtag list."""
    normalized = normalize_hashtags(hashtags)

    caption = str(caption).strip()

    if not normalized:
        return caption

    separator = "\n\n" if include_line_break else " "

    if caption:
        return caption + separator + " ".join(normalized)

    return " ".join(normalized)


def generate_caption_from_collection(
    caption: str,
    collection_id: str,
) -> str:
    items = get_collection_hashtags(collection_id)

    return build_caption(
        caption,
        [item["tag"] for item in items],
    )


# ---------------------------------------------------------
# Import and export
# ---------------------------------------------------------

def export_json(
    output_path: str | Path | None = None,
) -> Path:
    path = Path(output_path) if output_path else (
        OUTPUT_DIR / "hashtag_library.json"
    )

    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(
            load_database(),
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return path


def export_csv(
    output_path: str | Path | None = None,
) -> Path:
    path = Path(output_path) if output_path else (
        OUTPUT_DIR / "hashtag_library.csv"
    )

    path.parent.mkdir(parents=True, exist_ok=True)

    fields = [
        "id",
        "tag",
        "category",
        "platforms",
        "niche",
        "notes",
        "usage_count",
        "performance_notes",
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

        for item in get_all_hashtags():
            row = dict(item)
            row["platforms"] = ", ".join(item["platforms"])

            writer.writerow({
                field: row.get(field, "")
                for field in fields
            })

    return path


def import_json_data(
    raw_data: str | bytes,
    *,
    merge: bool = True,
) -> dict[str, int]:
    """Import a hashtag database from JSON."""
    if isinstance(raw_data, bytes):
        raw_data = raw_data.decode("utf-8")

    imported = json.loads(raw_data)

    if not isinstance(imported, dict):
        raise ValueError("JSON must contain a database object.")

    incoming_tags = imported.get("hashtags", [])
    incoming_collections = imported.get("collections", [])

    if not isinstance(incoming_tags, list):
        raise ValueError("Hashtags must be a list.")

    if not isinstance(incoming_collections, list):
        raise ValueError("Collections must be a list.")

    database = load_database() if merge else empty_database()

    existing_tags = {
        item["tag"].lower()
        for item in database["hashtags"]
    }

    added = 0
    skipped = 0

    id_mapping: dict[str, str] = {}

    for raw_tag in incoming_tags:
        if not isinstance(raw_tag, dict):
            skipped += 1
            continue

        try:
            tag = validate_hashtag(raw_tag)
        except (ValueError, TypeError):
            skipped += 1
            continue

        if tag["tag"].lower() in existing_tags:
            skipped += 1
            continue

        old_id = str(raw_tag.get("id", ""))
        tag["id"] = generate_id()

        if old_id:
            id_mapping[old_id] = tag["id"]

        database["hashtags"].append(tag)
        existing_tags.add(tag["tag"].lower())
        added += 1

    imported_collections = 0

    for raw_collection in incoming_collections:
        if not isinstance(raw_collection, dict):
            continue

        old_ids = raw_collection.get("hashtag_ids", [])

        if not isinstance(old_ids, list):
            old_ids = []

        mapped_ids = [
            id_mapping[item_id]
            for item_id in old_ids
            if item_id in id_mapping
        ]

        collection = {
            "id": generate_id(),
            "name": str(
                raw_collection.get("name", "Imported Collection")
            ).strip() or "Imported Collection",
            "platform": (
                raw_collection.get("platform")
                if raw_collection.get("platform") in PLATFORMS
                else "General"
            ),
            "description": str(
                raw_collection.get("description", "")
            ),
            "hashtag_ids": mapped_ids,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }

        database["collections"].append(collection)
        imported_collections += 1

    save_database(database)

    return {
        "added_hashtags": added,
        "skipped_hashtags": skipped,
        "imported_collections": imported_collections,
    }


# ---------------------------------------------------------
# Streamlit interface
# ---------------------------------------------------------

def render() -> None:
    if st is None:
        raise RuntimeError(
            "Streamlit is required: pip install streamlit"
        )

    st.title("Hashtag Research Studio")

    st.caption(
        "Build and organize reusable hashtag sets for your content."
    )

    all_tags = get_all_hashtags()
    collections = get_collections()

    col1, col2, col3 = st.columns(3)

    col1.metric("Saved Hashtags", len(all_tags))
    col2.metric("Collections", len(collections))
    col3.metric(
        "Total Usage",
        sum(item["usage_count"] for item in all_tags),
    )

    tab_library, tab_add, tab_collections, tab_caption, tab_import = (
        st.tabs([
            "Hashtag Library",
            "Add Hashtag",
            "Collections",
            "Caption Builder",
            "Import / Export",
        ])
    )

    # -----------------------------------------------------
    # Library
    # -----------------------------------------------------

    with tab_library:
        st.subheader("Your hashtag library")

        keyword = st.text_input(
            "Search hashtags",
            placeholder="Search AI, fashion, travel...",
        )

        col1, col2 = st.columns(2)

        with col1:
            category = st.selectbox(
                "Category",
                ["All"] + CATEGORIES,
            )

        with col2:
            platform = st.selectbox(
                "Platform",
                ["All"] + PLATFORMS,
            )

        results = search_hashtags(
            keyword,
            category,
            platform,
        )

        st.caption(f"{len(results)} hashtags found")

        for item in results:
            with st.expander(
                f"{item['tag']} · {item['category']}"
            ):
                st.write(
                    f"Platforms: {', '.join(item['platforms'])}"
                )
                st.write(f"Niche: {item['niche'] or 'Not set'}")
                st.write(f"Usage count: {item['usage_count']}")

                if item["notes"]:
                    st.write(item["notes"])

                if item["performance_notes"]:
                    st.caption(
                        f"Performance notes: {item['performance_notes']}"
                    )

                col1, col2 = st.columns(2)

                with col1:
                    if st.button(
                        "Record Usage",
                        key=f"use_{item['id']}",
                    ):
                        record_hashtag_usage(item["id"])
                        st.success("Usage recorded.")
                        st.rerun()

                with col2:
                    if st.button(
                        "Delete",
                        key=f"delete_tag_{item['id']}",
                    ):
                        delete_hashtag(item["id"])
                        st.success("Hashtag deleted.")
                        st.rerun()

    # -----------------------------------------------------
    # Add hashtag
    # -----------------------------------------------------

    with tab_add:
        st.subheader("Add a hashtag")

        with st.form("add_hashtag_form"):
            tag_input = st.text_input(
                "Hashtag",
                placeholder="#AIInfluencer",
            )

            selected_category = st.selectbox(
                "Category",
                CATEGORIES,
            )

            niche = st.text_input(
                "Niche",
                placeholder="AI movies, cinematic reels...",
            )

            selected_platforms = st.multiselect(
                "Suitable platforms",
                PLATFORMS,
                default=["General"],
            )

            notes = st.text_area("Notes")

            performance_notes = st.text_area(
                "Manual performance notes",
                placeholder="Add your own observations...",
            )

            submitted = st.form_submit_button(
                "Save Hashtag",
                type="primary",
                use_container_width=True,
            )

        if submitted:
            try:
                item = add_hashtag({
                    "tag": tag_input,
                    "category": selected_category,
                    "niche": niche,
                    "platforms": selected_platforms,
                    "notes": notes,
                    "performance_notes": performance_notes,
                })

                st.success(f"Saved {item['tag']}.")
                st.rerun()

            except Exception as exc:
                st.error(f"Unable to save hashtag: {exc}")

        st.divider()
        st.subheader("Quick add multiple hashtags")

        bulk_text = st.text_area(
            "Enter hashtags separated by spaces or commas",
            placeholder="#AI #AIVideo #AIInfluencer",
        )

        bulk_category = st.selectbox(
            "Bulk category",
            CATEGORIES,
            key="bulk_category",
        )

        if st.button("Add All Hashtags"):
            tags = normalize_hashtags(bulk_text)

            added = 0
            skipped = 0

            for tag in tags:
                try:
                    add_hashtag({
                        "tag": tag,
                        "category": bulk_category,
                        "platforms": ["General"],
                    })
                    added += 1
                except ValueError:
                    skipped += 1

            st.success(
                f"Added: {added} | Skipped: {skipped}"
            )
            st.rerun()

    # -----------------------------------------------------
    # Collections
    # -----------------------------------------------------

    with tab_collections:
        st.subheader("Saved hashtag collections")

        if all_tags:
            with st.form("create_collection_form"):
                collection_name = st.text_input(
                    "Collection name",
                    placeholder="My AI Reels Hashtags",
                )

                collection_platform = st.selectbox(
                    "Platform",
                    PLATFORMS,
                    key="collection_platform",
                )

                collection_description = st.text_area(
                    "Description"
                )

                tag_options = {
                    item["tag"]: item["id"]
                    for item in all_tags
                }

                selected_tags = st.multiselect(
                    "Select hashtags",
                    list(tag_options.keys()),
                )

                save_collection = st.form_submit_button(
                    "Create Collection",
                    type="primary",
                )

            if save_collection:
                try:
                    create_collection(
                        collection_name,
                        [tag_options[tag] for tag in selected_tags],
                        collection_platform,
                        collection_description,
                    )
                    st.success("Collection created.")
                    st.rerun()

                except Exception as exc:
                    st.error(str(exc))

        else:
            st.info("Add hashtags before creating collections.")

        st.divider()

        for collection in get_collections():
            with st.expander(collection["name"]):
                st.write(
                    f"Platform: {collection['platform']}"
                )
                st.write(collection["description"])

                items = get_collection_hashtags(
                    collection["id"]
                )

                st.write(
                    " ".join(item["tag"] for item in items)
                    or "No hashtags in this collection."
                )

                if st.button(
                    "Copy-ready hashtag set",
                    key=f"collection_copy_{collection['id']}",
                ):
                    st.code(
                        " ".join(item["tag"] for item in items)
                    )

                if st.button(
                    "Delete Collection",
                    key=f"collection_delete_{collection['id']}",
                ):
                    delete_collection(collection["id"])
                    st.success("Collection deleted.")
                    st.rerun()

    # -----------------------------------------------------
    # Caption builder
    # -----------------------------------------------------

    with tab_caption:
        st.subheader("Caption and hashtag builder")

        caption_text = st.text_area(
            "Write your caption",
            height=150,
        )

        source_type = st.radio(
            "Hashtag source",
            ["Generate from library", "Saved collection", "Manual"],
            horizontal=True,
        )

        chosen_tags: list[str] = []

        if source_type == "Generate from library":
            keyword = st.text_input(
                "Keyword or niche",
                placeholder="AI cinematic fantasy",
            )

            col1, col2 = st.columns(2)

            with col1:
                category = st.selectbox(
                    "Category",
                    ["All"] + CATEGORIES,
                    key="caption_category",
                )

            with col2:
                platform = st.selectbox(
                    "Platform",
                    ["All"] + PLATFORMS,
                    key="caption_platform",
                )

            limit = st.slider(
                "Maximum hashtags",
                min_value=1,
                max_value=30,
                value=15,
            )

            chosen_tags = generate_hashtag_set(
                keyword,
                category,
                platform,
                limit,
            )

        elif source_type == "Saved collection":
            current_collections = get_collections()

            if current_collections:
                collection_map = {
                    item["name"]: item["id"]
                    for item in current_collections
                }

                chosen_collection = st.selectbox(
                    "Select collection",
                    list(collection_map.keys()),
                )

                chosen_tags = [
                    item["tag"]
                    for item in get_collection_hashtags(
                        collection_map[chosen_collection]
                    )
                ]
            else:
                st.info("No saved collections available.")

        else:
            manual_tags = st.text_input(
                "Enter hashtags",
                placeholder="#AI #Creator #AIVideo",
            )
            chosen_tags = normalize_hashtags(manual_tags)

        st.markdown("**Selected hashtags**")

        st.write(" ".join(chosen_tags) or "No matching hashtags found.")

        generated_caption = build_caption(
            caption_text,
            chosen_tags,
        )

        st.markdown("**Generated caption**")

        st.text_area(
            "Copy your final caption",
            value=generated_caption,
            height=200,
            key="generated_caption_output",
        )

        st.download_button(
            "Download Caption TXT",
            data=generated_caption.encode("utf-8"),
            file_name="social_caption.txt",
            mime="text/plain",
        )

    # -----------------------------------------------------
    # Import and export
    # -----------------------------------------------------

    with tab_import:
        st.subheader("Import and export hashtag library")

        database = load_database()

        json_data = json.dumps(
            database,
            indent=2,
            ensure_ascii=False,
        )

        csv_buffer = io.StringIO()

        writer = csv.DictWriter(
            csv_buffer,
            fieldnames=[
                "tag",
                "category",
                "platforms",
                "niche",
                "notes",
                "usage_count",
                "performance_notes",
            ],
        )

        writer.writeheader()

        for item in database["hashtags"]:
            writer.writerow({
                "tag": item["tag"],
                "category": item["category"],
                "platforms": ", ".join(item["platforms"]),
                "niche": item["niche"],
                "notes": item["notes"],
                "usage_count": item["usage_count"],
                "performance_notes": item["performance_notes"],
            })

        col1, col2 = st.columns(2)

        with col1:
            st.download_button(
                "Download JSON",
                data=json_data.encode("utf-8"),
                file_name="hashtag_library.json",
                mime="application/json",
            )

        with col2:
            st.download_button(
                "Download CSV",
                data=csv_buffer.getvalue().encode("utf-8-sig"),
                file_name="hashtag_library.csv",
                mime="text/csv",
            )

        st.divider()

        st.subheader("Import JSON backup")

        uploaded = st.file_uploader(
            "Choose hashtag JSON file",
            type=["json"],
            key="hashtag_import_file",
        )

        merge = st.checkbox(
            "Merge with existing library",
            value=True,
        )

        if st.button(
            "Import JSON",
            disabled=uploaded is None,
        ):
            try:
                result = import_json_data(
                    uploaded.getvalue(),
                    merge=merge,
                )

                st.success(
                    f"Imported {result['added_hashtags']} hashtags. "
                    f"Skipped {result['skipped_hashtags']} duplicates "
                    f"or invalid records."
                )
                st.rerun()

            except Exception as exc:
                st.error(f"Import failed: {exc}")


# ---------------------------------------------------------
# Built-in tests
# ---------------------------------------------------------

def run_tests() -> None:
    global DATABASE_FILE

    original_database = DATABASE_FILE
    test_database = (
        DATA_DIR / f"test_hashtags_{uuid.uuid4().hex}.json"
    )

    DATABASE_FILE = test_database

    try:
        save_database(empty_database())

        assert normalize_hashtag(" AI Video ") == "#AIVideo"

        assert normalize_hashtags(
            "#AI #Video, #AI"
        ) == ["#AI", "#Video"]

        first = add_hashtag({
            "tag": "#AIInfluencer",
            "category": "AI",
            "platforms": ["YouTube", "Instagram"],
            "niche": "AI creators",
        })

        second = add_hashtag({
            "tag": "#Cinematic",
            "category": "Movies",
            "platforms": ["YouTube"],
        })

        assert len(get_all_hashtags()) == 2

        try:
            add_hashtag({"tag": "#AIInfluencer"})
            raise AssertionError("Duplicate hashtag should fail.")
        except ValueError:
            pass

        updated = update_hashtag(
            first["id"],
            {"notes": "Test note"},
        )
        assert updated["notes"] == "Test note"

        used = record_hashtag_usage(first["id"])
        assert used["usage_count"] == 1

        results = search_hashtags(
            keyword="AI",
            category="AI",
            platform="Instagram",
        )
        assert len(results) == 1

        collection = create_collection(
            "AI Collection",
            [first["id"], second["id"]],
            platform="Instagram",
        )

        collection_items = get_collection_hashtags(
            collection["id"]
        )
        assert len(collection_items) == 2

        caption = build_caption(
            "Welcome to my AI channel",
            ["#AI", "#Creator", "#AI"],
        )

        assert caption.count("#AI") == 1
        assert "#Creator" in caption

        generated = generate_hashtag_set(
            "AI",
            category="AI",
            platform="Instagram",
        )
        assert "#AIInfluencer" in generated

        stats = get_category_statistics()
        assert stats["AI"] == 1
        assert stats["Movies"] == 1

        backup = json.dumps(load_database())

        test_import_file = (
            DATA_DIR / f"test_import_{uuid.uuid4().hex}.json"
        )

        test_import_file.write_text(
            backup,
            encoding="utf-8",
        )

        try:
            imported = import_json_data(
                test_import_file.read_text(encoding="utf-8"),
                merge=True,
            )
            assert imported["added_hashtags"] == 0
            assert imported["skipped_hashtags"] == 2
        finally:
            test_import_file.unlink(missing_ok=True)

        assert delete_hashtag(first["id"]) is True

        # Deleting a hashtag must also remove it from collections.
        remaining = get_collection_hashtags(collection["id"])
        assert all(item["id"] != first["id"] for item in remaining)

        assert delete_collection(collection["id"]) is True

        print("All Hashtag Research tests passed.")

    finally:
        DATABASE_FILE = original_database
        test_database.unlink(missing_ok=True)


# ---------------------------------------------------------
# Command line entry point
# ---------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AI Influencer Studio Hashtag Research"
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
        print("Hashtag Research module")
        print("Import into your Streamlit application.")
        print(
            "Run tests with: "
            "python -m modules.hashtag_research --test"
        )
