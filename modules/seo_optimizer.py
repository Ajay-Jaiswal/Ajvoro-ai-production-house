
"""
AI Influencer Studio
File 50: modules/seo_optimizer.py

Local SEO Optimizer for YouTube and social media.

Features:
- SEO project management
- Title and description builder
- Keyword management
- YouTube tag generation
- Hashtag integration
- SEO checklist score
- Title length analysis
- JSON and TXT export
- Built-in tests

Requirements:
    pip install streamlit

Optional:
    modules.hashtag_research

No paid API or internet connection required.
"""

from __future__ import annotations

import argparse
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
OUTPUT_DIR = BASE_DIR / "outputs" / "seo"

DATABASE_FILE = DATA_DIR / "seo_projects.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


PLATFORMS = [
    "YouTube",
    "YouTube Shorts",
    "Instagram",
    "Instagram Reels",
    "TikTok",
    "Facebook",
    "LinkedIn",
    "X",
]

CONTENT_TYPES = [
    "AI Movie",
    "AI Short Film",
    "AI Reel",
    "Tutorial",
    "Entertainment",
    "Technology",
    "News",
    "Education",
    "Other",
]


# ---------------------------------------------------------
# General utilities
# ---------------------------------------------------------

def generate_id() -> str:
    return uuid.uuid4().hex


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_filename(value: str) -> str:
    cleaned = "".join(
        char if char.isalnum() or char in "-_"
        else "_"
        for char in str(value)
    )
    return cleaned.strip("_") or "seo_project"


def normalize_keywords(
    values: str | list[str],
) -> list[str]:
    """Normalize keywords and remove duplicates."""
    if isinstance(values, str):
        candidates = re.split(r"[,;\n]+", values)
    else:
        candidates = values

    results = []
    seen = set()

    for item in candidates:
        keyword = str(item).strip()

        if not keyword:
            continue

        key = keyword.casefold()

        if key not in seen:
            results.append(keyword)
            seen.add(key)

    return results


def normalize_tags(
    values: str | list[str],
) -> list[str]:
    """Normalize YouTube tags without adding hashtag symbols."""
    if isinstance(values, str):
        candidates = re.split(r"[,;\n]+", values)
    else:
        candidates = values

    results = []
    seen = set()

    for item in candidates:
        tag = str(item).strip().lstrip("#")

        if not tag:
            continue

        key = tag.casefold()

        if key not in seen:
            results.append(tag)
            seen.add(key)

    return results


def count_words(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", str(text)))


# ---------------------------------------------------------
# Database
# ---------------------------------------------------------

def empty_database() -> dict[str, Any]:
    return {
        "projects": [],
        "version": 1,
    }


def load_database() -> dict[str, Any]:
    if not DATABASE_FILE.exists():
        return empty_database()

    try:
        data = json.loads(
            DATABASE_FILE.read_text(encoding="utf-8")
        )

        if not isinstance(data, dict):
            return empty_database()

        projects = data.get("projects", [])

        return {
            "projects": (
                projects if isinstance(projects, list) else []
            ),
            "version": data.get("version", 1),
        }

    except (OSError, json.JSONDecodeError):
        return empty_database()


def save_database(data: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    temp_file = DATABASE_FILE.with_suffix(".tmp")

    temp_file.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    temp_file.replace(DATABASE_FILE)


# ---------------------------------------------------------
# Project validation
# ---------------------------------------------------------

def validate_project(
    data: dict[str, Any],
) -> dict[str, Any]:
    title = str(data.get("title", "")).strip()

    if not title:
        raise ValueError("Project title is required.")

    platform = str(data.get("platform", "YouTube"))

    if platform not in PLATFORMS:
        raise ValueError("Invalid platform.")

    content_type = str(
        data.get("content_type", "Other")
    )

    if content_type not in CONTENT_TYPES:
        content_type = "Other"

    keywords = normalize_keywords(
        data.get("keywords", [])
    )

    tags = normalize_tags(
        data.get("tags", [])
    )

    return {
        "id": str(data.get("id") or generate_id()),
        "title": title,
        "platform": platform,
        "content_type": content_type,
        "primary_keyword": str(
            data.get("primary_keyword", "")
        ).strip(),
        "keywords": keywords,
        "tags": tags,
        "description": str(
            data.get("description", "")
        ).strip(),
        "hashtags": normalize_keywords(
            data.get("hashtags", [])
        ),
        "category": str(
            data.get("category", "")
        ).strip(),
        "target_audience": str(
            data.get("target_audience", "")
        ).strip(),
        "call_to_action": str(
            data.get("call_to_action", "")
        ).strip(),
        "thumbnail_text": str(
            data.get("thumbnail_text", "")
        ).strip(),
        "notes": str(data.get("notes", "")).strip(),
        "created_at": str(
            data.get("created_at") or now_iso()
        ),
        "updated_at": now_iso(),
    }


# ---------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------

def get_projects() -> list[dict[str, Any]]:
    return load_database()["projects"]


def get_project(project_id: str) -> dict[str, Any] | None:
    for project in get_projects():
        if project.get("id") == project_id:
            return project

    return None


def add_project(
    data: dict[str, Any],
) -> dict[str, Any]:
    database = load_database()
    project = validate_project(data)

    if any(
        item["id"] == project["id"]
        for item in database["projects"]
    ):
        raise ValueError("Project ID already exists.")

    database["projects"].append(project)
    save_database(database)

    return project


def update_project(
    project_id: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    database = load_database()

    for index, project in enumerate(database["projects"]):
        if project["id"] != project_id:
            continue

        merged = dict(project)
        merged.update(updates)
        merged["id"] = project_id

        updated = validate_project(merged)
        database["projects"][index] = updated

        save_database(database)
        return updated

    raise ValueError("SEO project not found.")


def delete_project(project_id: str) -> bool:
    database = load_database()

    original_count = len(database["projects"])

    database["projects"] = [
        item for item in database["projects"]
        if item["id"] != project_id
    ]

    if len(database["projects"]) == original_count:
        return False

    save_database(database)
    return True


def duplicate_project(
    project_id: str,
) -> dict[str, Any]:
    project = get_project(project_id)

    if project is None:
        raise ValueError("SEO project not found.")

    duplicate = dict(project)
    duplicate.pop("id", None)

    duplicate["title"] += " (Copy)"
    duplicate["created_at"] = now_iso()

    return add_project(duplicate)


# ---------------------------------------------------------
# SEO title analysis
# ---------------------------------------------------------

def analyze_title(
    title: str,
    primary_keyword: str = "",
) -> dict[str, Any]:
    """Analyze title length and keyword presence."""
    title = str(title).strip()
    length = len(title)

    recommendations = []

    if not title:
        recommendations.append("Add a title.")
    elif length < 20:
        recommendations.append(
            "Consider adding more descriptive context."
        )
    elif length > 70:
        recommendations.append(
            "Consider shortening the title for readability."
        )

    keyword_present = True

    if primary_keyword.strip():
        keyword_present = (
            primary_keyword.casefold() in title.casefold()
        )

        if not keyword_present:
            recommendations.append(
                "Consider including your primary keyword naturally."
            )

    if title and not any(char.isdigit() for char in title):
        recommendations.append(
            "Numbers may be useful when they accurately describe content."
        )

    return {
        "length": length,
        "word_count": count_words(title),
        "keyword_present": keyword_present,
        "recommendations": recommendations,
    }


# ---------------------------------------------------------
# SEO checklist scoring
# ---------------------------------------------------------

def calculate_seo_score(
    project: dict[str, Any],
) -> dict[str, Any]:
    """
    Calculate a transparent checklist score.

    This is not an official platform ranking score.
    Each item contributes equally to the total.
    """
    title = str(project.get("title", "")).strip()
    description = str(
        project.get("description", "")
    ).strip()

    primary_keyword = str(
        project.get("primary_keyword", "")
    ).strip()

    keywords = normalize_keywords(
        project.get("keywords", [])
    )

    tags = normalize_tags(
        project.get("tags", [])
    )

    hashtags = normalize_keywords(
        project.get("hashtags", [])
    )

    checks = {
        "Title is present": bool(title),
        "Title has a readable length": (
            20 <= len(title) <= 70
        ),
        "Primary keyword is present": bool(primary_keyword),
        "Primary keyword appears in title": (
            bool(primary_keyword)
            and primary_keyword.casefold() in title.casefold()
        ),
        "Description is present": bool(description),
        "Description has useful detail": (
            len(description) >= 100
        ),
        "Keywords are added": len(keywords) >= 3,
        "Platform tags are added": len(tags) >= 3,
        "Hashtags are added": len(hashtags) >= 1,
        "Call to action is added": bool(
            str(project.get("call_to_action", "")).strip()
        ),
    }

    passed = sum(checks.values())
    total = len(checks)

    score = round((passed / total) * 100)

    if score >= 90:
        grade = "Excellent checklist completion"
    elif score >= 70:
        grade = "Good checklist completion"
    elif score >= 50:
        grade = "Needs improvement"
    else:
        grade = "Incomplete"

    return {
        "score": score,
        "passed": passed,
        "total": total,
        "grade": grade,
        "checks": checks,
    }


def get_seo_recommendations(
    project: dict[str, Any],
) -> list[str]:
    result = calculate_seo_score(project)
    recommendations = []

    for label, passed in result["checks"].items():
        if not passed:
            recommendations.append(label)

    return recommendations


# ---------------------------------------------------------
# Keyword and tag suggestions
# ---------------------------------------------------------

def suggest_related_keywords(
    primary_keyword: str,
    existing_keywords: list[str] | None = None,
) -> list[str]:
    """
    Build simple keyword variations locally.

    These are brainstorming suggestions, not search-volume data.
    """
    primary = str(primary_keyword).strip()

    if not primary:
        return []

    existing = {
        item.casefold()
        for item in normalize_keywords(existing_keywords or [])
    }

    variations = [
        primary,
        f"{primary} tutorial",
        f"{primary} explained",
        f"{primary} for beginners",
        f"best {primary}",
        f"{primary} tips",
        f"{primary} video",
        f"{primary} 2026",
    ]

    results = []

    for item in variations:
        if item.casefold() not in existing:
            results.append(item)

    return list(dict.fromkeys(results))


def generate_youtube_tags(
    title: str,
    primary_keyword: str,
    keywords: list[str],
    limit: int = 15,
) -> list[str]:
    """Build YouTube tag suggestions from supplied keywords."""
    if limit < 1:
        raise ValueError("Limit must be at least 1.")

    candidates = []

    if primary_keyword.strip():
        candidates.append(primary_keyword.strip())

    candidates.extend(normalize_keywords(keywords))

    title_words = re.findall(
        r"[A-Za-z0-9]+",
        title,
    )

    if title_words:
        candidates.append(" ".join(title_words))

    results = normalize_tags(candidates)

    return results[:limit]


def generate_description(
    *,
    title: str,
    primary_keyword: str,
    introduction: str,
    details: str = "",
    call_to_action: str = "",
    hashtags: list[str] | None = None,
) -> str:
    """Build a structured video description."""
    sections = []

    if introduction.strip():
        sections.append(introduction.strip())

    if details.strip():
        sections.append(details.strip())

    if primary_keyword.strip():
        sections.append(
            f"Main topic: {primary_keyword.strip()}"
        )

    if call_to_action.strip():
        sections.append(call_to_action.strip())

    normalized_hashtags = normalize_tags(
        hashtags or []
    )

    if normalized_hashtags:
        sections.append(
            " ".join("#" + tag for tag in normalized_hashtags)
        )

    return "\n\n".join(sections)


# ---------------------------------------------------------
# Optional hashtag module integration
# ---------------------------------------------------------

def get_saved_hashtags(
    keyword: str = "",
) -> list[str]:
    """
    Try to retrieve tags from File 49.
    Returns an empty list if the module is unavailable.
    """
    try:
        from modules import hashtag_research

        results = hashtag_research.search_hashtags(
            keyword=keyword,
        )

        return [
            item["tag"].lstrip("#")
            for item in results[:20]
        ]

    except (ImportError, AttributeError, OSError, ValueError):
        return []


# ---------------------------------------------------------
# Export
# ---------------------------------------------------------

def export_project_json(
    project_id: str,
    output_path: str | Path | None = None,
) -> Path:
    project = get_project(project_id)

    if project is None:
        raise ValueError("SEO project not found.")

    path = Path(output_path) if output_path else (
        OUTPUT_DIR
        / f"{safe_filename(project['title'])}_{project_id[:8]}.json"
    )

    path.parent.mkdir(parents=True, exist_ok=True)

    report = {
        "project": project,
        "seo_analysis": calculate_seo_score(project),
        "recommendations": get_seo_recommendations(project),
        "exported_at": now_iso(),
    }

    path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return path


def export_project_txt(
    project_id: str,
    output_path: str | Path | None = None,
) -> Path:
    project = get_project(project_id)

    if project is None:
        raise ValueError("SEO project not found.")

    analysis = calculate_seo_score(project)

    content = [
        "SEO OPTIMIZATION REPORT",
        "=" * 35,
        "",
        f"Title: {project['title']}",
        f"Platform: {project['platform']}",
        f"Content type: {project['content_type']}",
        "",
        "DESCRIPTION",
        "-" * 35,
        project["description"],
        "",
        "PRIMARY KEYWORD",
        project["primary_keyword"],
        "",
        "KEYWORDS",
        ", ".join(project["keywords"]),
        "",
        "TAGS",
        ", ".join(project["tags"]),
        "",
        "HASHTAGS",
        " ".join("#" + tag.lstrip("#") for tag in project["hashtags"]),
        "",
        "SEO CHECKLIST",
        f"Score: {analysis['score']}%",
        f"Result: {analysis['grade']}",
        "",
    ]

    for label, passed in analysis["checks"].items():
        content.append(
            f"[{'PASS' if passed else 'TODO'}] {label}"
        )

    path = Path(output_path) if output_path else (
        OUTPUT_DIR
        / f"{safe_filename(project['title'])}_{project_id[:8]}.txt"
    )

    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        "\n".join(content),
        encoding="utf-8",
    )

    return path


# ---------------------------------------------------------
# Streamlit interface
# ---------------------------------------------------------

def render() -> None:
    if st is None:
        raise RuntimeError(
            "Install Streamlit using: pip install streamlit"
        )

    st.title("SEO Optimizer Studio")

    st.caption(
        "Prepare better titles, descriptions, keywords and tags."
    )

    projects = get_projects()

    col1, col2, col3 = st.columns(3)

    col1.metric("Saved SEO Projects", len(projects))

    if projects:
        average_score = round(
            sum(
                calculate_seo_score(item)["score"]
                for item in projects
            ) / len(projects)
        )
    else:
        average_score = 0

    col2.metric("Average Checklist Score", f"{average_score}%")
    col3.metric("Platforms", len(PLATFORMS))

    tab_create, tab_manage, tab_tools = st.tabs([
        "Create SEO Project",
        "Saved Projects",
        "SEO Tools",
    ])

    # -----------------------------------------------------
    # Create project
    # -----------------------------------------------------

    with tab_create:
        st.subheader("Create an SEO project")

        with st.form("seo_project_form"):
            title = st.text_input(
                "Video title",
                placeholder="The Future of AI: A New Era",
            )

            col1, col2 = st.columns(2)

            with col1:
                platform = st.selectbox(
                    "Platform",
                    PLATFORMS,
                )

                content_type = st.selectbox(
                    "Content type",
                    CONTENT_TYPES,
                )

            with col2:
                primary_keyword = st.text_input(
                    "Primary keyword",
                    placeholder="Artificial Intelligence",
                )

                category = st.text_input(
                    "Content category",
                    placeholder="Technology",
                )

            keywords_text = st.text_area(
                "Related keywords",
                placeholder="AI future, AI technology, AI news",
            )

            description = st.text_area(
                "Video description",
                height=180,
            )

            tags_text = st.text_input(
                "Platform tags",
                placeholder="AI, technology, artificial intelligence",
            )

            hashtags_text = st.text_input(
                "Hashtags",
                placeholder="#AI #Technology #Future",
            )

            audience = st.text_input(
                "Target audience",
                placeholder="Technology enthusiasts",
            )

            cta = st.text_input(
                "Call to action",
                placeholder="Subscribe for more videos!",
            )

            thumbnail_text = st.text_input(
                "Thumbnail text",
                placeholder="THE AI REVOLUTION",
            )

            notes = st.text_area("Internal notes")

            submitted = st.form_submit_button(
                "Save SEO Project",
                type="primary",
                use_container_width=True,
            )

        if submitted:
            try:
                project = add_project({
                    "title": title,
                    "platform": platform,
                    "content_type": content_type,
                    "primary_keyword": primary_keyword,
                    "keywords": keywords_text,
                    "description": description,
                    "tags": tags_text,
                    "hashtags": hashtags_text,
                    "category": category,
                    "target_audience": audience,
                    "call_to_action": cta,
                    "thumbnail_text": thumbnail_text,
                    "notes": notes,
                })

                st.success(
                    f"SEO project saved: {project['title']}"
                )
                st.rerun()

            except Exception as exc:
                st.error(f"Unable to save project: {exc}")

    # -----------------------------------------------------
    # Manage projects
    # -----------------------------------------------------

    with tab_manage:
        st.subheader("Saved SEO projects")

        if not projects:
            st.info("No SEO projects saved yet.")

        for project in projects:
            with st.expander(project["title"]):
                analysis = calculate_seo_score(project)

                st.metric(
                    "SEO checklist score",
                    f"{analysis['score']}%",
                    analysis["grade"],
                )

                st.progress(analysis["score"] / 100)

                for label, passed in analysis["checks"].items():
                    st.write(
                        f"{'✅' if passed else '⬜'} {label}"
                    )

                st.markdown("**Description**")
                st.write(project["description"] or "No description.")

                st.markdown("**Keywords**")
                st.write(", ".join(project["keywords"]))

                st.markdown("**Tags**")
                st.write(", ".join(project["tags"]))

                st.markdown("**Recommendations**")

                recommendations = get_seo_recommendations(
                    project
                )

                if recommendations:
                    for item in recommendations:
                        st.write(f"- {item}")
                else:
                    st.success("All checklist items passed.")

                col1, col2, col3 = st.columns(3)

                with col1:
                    if st.button(
                        "Duplicate",
                        key=f"duplicate_{project['id']}",
                    ):
                        duplicate_project(project["id"])
                        st.success("Project duplicated.")
                        st.rerun()

                with col2:
                    if st.button(
                        "Export TXT",
                        key=f"txt_{project['id']}",
                    ):
                        path = export_project_txt(
                            project["id"]
                        )

                        st.download_button(
                            "Download TXT report",
                            data=path.read_bytes(),
                            file_name=path.name,
                            mime="text/plain",
                            key=f"download_txt_{project['id']}",
                        )

                with col3:
                    if st.button(
                        "Delete",
                        key=f"delete_{project['id']}",
                    ):
                        delete_project(project["id"])
                        st.success("Project deleted.")
                        st.rerun()

                st.divider()

                st.markdown("**Edit project**")

                with st.form(f"edit_seo_{project['id']}"):
                    edited_title = st.text_input(
                        "Title",
                        value=project["title"],
                    )

                    edited_keyword = st.text_input(
                        "Primary keyword",
                        value=project["primary_keyword"],
                    )

                    edited_description = st.text_area(
                        "Description",
                        value=project["description"],
                    )

                    edited_keywords = st.text_area(
                        "Keywords",
                        value=", ".join(project["keywords"]),
                    )

                    edited_tags = st.text_input(
                        "Tags",
                        value=", ".join(project["tags"]),
                    )

                    edited_hashtags = st.text_input(
                        "Hashtags",
                        value=", ".join(project["hashtags"]),
                    )

                    edited_cta = st.text_input(
                        "Call to action",
                        value=project["call_to_action"],
                    )

                    save_edit = st.form_submit_button(
                        "Update Project"
                    )

                if save_edit:
                    try:
                        update_project(
                            project["id"],
                            {
                                "title": edited_title,
                                "primary_keyword": edited_keyword,
                                "description": edited_description,
                                "keywords": edited_keywords,
                                "tags": edited_tags,
                                "hashtags": edited_hashtags,
                                "call_to_action": edited_cta,
                            },
                        )

                        st.success("Project updated.")
                        st.rerun()

                    except Exception as exc:
                        st.error(str(exc))

    # -----------------------------------------------------
    # SEO tools
    # -----------------------------------------------------

    with tab_tools:
        st.subheader("Keyword and tag tools")

        tool_keyword = st.text_input(
            "Enter your main topic",
            placeholder="AI Influencer",
        )

        if st.button("Generate Keyword Ideas"):
            suggestions = suggest_related_keywords(
                tool_keyword
            )

            if suggestions:
                st.write(suggestions)
            else:
                st.warning("Enter a keyword first.")

        st.divider()

        st.subheader("Generate YouTube tags")

        tool_title = st.text_input(
            "Video title",
            key="tool_title",
        )

        tool_primary = st.text_input(
            "Primary keyword",
            key="tool_primary",
        )

        tool_keywords = st.text_input(
            "Related keywords",
            key="tool_keywords",
        )

        tag_limit = st.slider(
            "Maximum tags",
            1,
            30,
            15,
        )

        if st.button("Generate Tags"):
            generated_tags = generate_youtube_tags(
                tool_title,
                tool_primary,
                normalize_keywords(tool_keywords),
                tag_limit,
            )

            st.code(", ".join(generated_tags))

        st.divider()

        st.subheader("Title analyzer")

        title_to_analyze = st.text_input(
            "Enter a title",
            key="title_analyzer",
        )

        keyword_to_check = st.text_input(
            "Keyword to check",
            key="title_keyword",
        )

        if st.button("Analyze Title"):
            result = analyze_title(
                title_to_analyze,
                keyword_to_check,
            )

            st.metric("Character count", result["length"])
            st.metric("Word count", result["word_count"])

            st.write(
                "Primary keyword found: "
                + ("Yes" if result["keyword_present"] else "No")
            )

            for recommendation in result["recommendations"]:
                st.write(f"- {recommendation}")


# ---------------------------------------------------------
# Built-in tests
# ---------------------------------------------------------

def run_tests() -> None:
    global DATABASE_FILE

    original_database = DATABASE_FILE

    test_database = (
        DATA_DIR / f"test_seo_{uuid.uuid4().hex}.json"
    )

    DATABASE_FILE = test_database

    try:
        save_database(empty_database())

        assert normalize_keywords(
            "AI, Technology, AI"
        ) == ["AI", "Technology"]

        assert normalize_tags(
            "#AI, #Video, AI"
        ) == ["AI", "Video"]

        assert count_words("AI is changing technology") == 4

        project = add_project({
            "title": "The Future of AI Technology",
            "platform": "YouTube",
            "content_type": "Technology",
            "primary_keyword": "AI Technology",
            "keywords": [
                "AI Technology",
                "Artificial Intelligence",
                "Future of AI",
            ],
            "description": (
                "Discover how AI technology is changing "
                "the future of our world with new innovations."
            ),
            "tags": ["AI", "Technology", "Future"],
            "hashtags": ["AI", "Technology"],
            "call_to_action": "Subscribe for more.",
        })

        assert project["title"] == "The Future of AI Technology"
        assert len(get_projects()) == 1

        found = get_project(project["id"])
        assert found is not None

        analysis = calculate_seo_score(project)

        assert 0 <= analysis["score"] <= 100
        assert analysis["total"] == 10
        assert analysis["passed"] > 0

        title_analysis = analyze_title(
            "The Future of AI Technology",
            "AI Technology",
        )

        assert title_analysis["keyword_present"] is True
        assert title_analysis["length"] > 0

        suggestions = suggest_related_keywords(
            "AI Technology"
        )

        assert "AI Technology" in suggestions
        assert len(suggestions) > 0

        tags = generate_youtube_tags(
            "The Future of AI",
            "AI",
            ["Technology", "Future"],
        )

        assert "AI" in tags
        assert len(tags) <= 15

        description = generate_description(
            title="AI Future",
            primary_keyword="AI",
            introduction="Discover AI.",
            details="Explore new developments.",
            call_to_action="Subscribe.",
            hashtags=["AI", "Technology"],
        )

        assert "Discover AI." in description
        assert "#AI" in description

        duplicated = duplicate_project(project["id"])

        assert duplicated["id"] != project["id"]
        assert duplicated["title"].endswith("(Copy)")

        updated = update_project(
            project["id"],
            {"notes": "Test note"},
        )

        assert updated["notes"] == "Test note"

        assert delete_project(duplicated["id"]) is True
        assert delete_project("missing") is False

        print("All SEO Optimizer tests passed.")

    finally:
        DATABASE_FILE = original_database
        test_database.unlink(missing_ok=True)


# ---------------------------------------------------------
# Command line entry point
# ---------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AI Influencer Studio SEO Optimizer"
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
        print("SEO Optimizer module")
        print("Import into your Streamlit application.")
        print(
            "Run tests with: "
            "python -m modules.seo_optimizer --test"
        )
