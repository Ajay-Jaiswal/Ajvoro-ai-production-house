
"""
AI Influencer Studio
File 40: modules/subtitle_manager.py

Professional Subtitle Manager.

Features:
- Subtitle project management
- Subtitle CRUD
- SRT import/export
- WebVTT import/export
- Hindi and multilingual text
- Subtitle styling
- Timestamp validation
- Overlap detection
- Timeline metadata export

This module prepares subtitle data.
It does not burn subtitles into video.
"""

from __future__ import annotations

import json
import re
import uuid

from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT_DIR / "data"
SUBTITLE_DIR = ROOT_DIR / "assets" / "subtitles"
EXPORT_DIR = ROOT_DIR / "outputs" / "subtitles"

DATABASE_FILE = DATA_DIR / "subtitle_projects.json"


# ---------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------

SUPPORTED_FORMATS = ["srt", "vtt"]

POSITIONS = [
    "Bottom Center",
    "Top Center",
    "Middle Center",
    "Bottom Left",
    "Bottom Right",
]

ALIGNMENTS = [
    "left",
    "center",
    "right",
]

FONT_STYLES = [
    "normal",
    "bold",
    "italic",
    "bold italic",
]


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _id() -> str:
    return uuid.uuid4().hex[:12]


def _clean(value: Any, limit: int = 5000) -> str:
    return str(value or "").strip()[:limit]


def _safe_filename(value: str) -> str:
    name = re.sub(
        r"[^a-zA-Z0-9_-]+",
        "_",
        str(value),
    )

    return name.strip("_")[:80] or "subtitle"


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SUBTITLE_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# TIMESTAMP UTILITIES
# ---------------------------------------------------------

def timestamp_to_seconds(value: str) -> float:
    """
    Accepts:
        HH:MM:SS,mmm
        HH:MM:SS.mmm
        MM:SS
        MM:SS.mmm
    """

    value = str(value).strip()

    if not value:
        raise ValueError("Timestamp cannot be empty.")

    parts = value.replace(",", ".").split(":")

    if len(parts) == 2:
        hours = 0
        minutes = int(parts[0])
        seconds = float(parts[1])

    elif len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])

    else:
        raise ValueError("Invalid timestamp format.")

    if hours < 0 or not 0 <= minutes < 60:
        raise ValueError("Invalid timestamp values.")

    if not 0 <= seconds < 60:
        raise ValueError("Invalid seconds value.")

    return hours * 3600 + minutes * 60 + seconds


def seconds_to_timestamp(
    seconds: float,
    vtt: bool = False,
) -> str:

    try:
        seconds = float(seconds)
    except (TypeError, ValueError):
        raise ValueError("Seconds must be numeric.")

    if seconds < 0:
        raise ValueError("Timestamp cannot be negative.")

    milliseconds = round(seconds * 1000)

    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)

    separator = "." if vtt else ","

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{whole_seconds:02d}"
        f"{separator}{milliseconds:03d}"
    )


# ---------------------------------------------------------
# DATABASE
# ---------------------------------------------------------

def load_database(
    path: Path | str | None = None,
) -> dict:

    database_path = Path(path) if path else DATABASE_FILE

    if not database_path.exists():
        return {
            "version": 1,
            "updated_at": _now(),
            "projects": {},
        }

    try:
        with database_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            raise ValueError("Invalid subtitle database.")

        data.setdefault("projects", {})
        data.setdefault("version", 1)

        return data

    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Cannot read subtitle database: {exc}"
        ) from exc


def save_database(
    database: dict,
    path: Path | str | None = None,
) -> None:

    database_path = Path(path) if path else DATABASE_FILE

    database_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    database["version"] = 1
    database["updated_at"] = _now()

    temporary = database_path.with_name(
        database_path.name + ".tmp"
    )

    with temporary.open("w", encoding="utf-8") as file:
        json.dump(
            database,
            file,
            indent=4,
            ensure_ascii=False,
        )

    temporary.replace(database_path)


# ---------------------------------------------------------
# SUBTITLE VALIDATION
# ---------------------------------------------------------

def validate_subtitle(details: dict) -> dict:

    if not isinstance(details, dict):
        raise ValueError("Subtitle must be a dictionary.")

    text = _clean(details.get("text"))

    if not text:
        raise ValueError("Subtitle text is required.")

    try:
        start = float(details.get("start", 0))
        end = float(details.get("end", 0))
    except (TypeError, ValueError):
        raise ValueError("Start and end must be numeric.")

    if start < 0:
        raise ValueError("Start time cannot be negative.")

    if end <= start:
        raise ValueError("End time must be greater than start time.")

    if end - start > 3600:
        raise ValueError("A single subtitle cannot exceed one hour.")

    return {
        "text": text,
        "start": round(start, 3),
        "end": round(end, 3),
        "speaker": _clean(
            details.get("speaker"),
            120,
        ),
        "language": _clean(
            details.get("language", "English"),
            50,
        ),
        "enabled": bool(details.get("enabled", True)),
    }


# ---------------------------------------------------------
# STYLE VALIDATION
# ---------------------------------------------------------

def validate_style(style: dict | None = None) -> dict:

    style = style or {}

    position = _clean(
        style.get("position", "Bottom Center")
    )

    if position not in POSITIONS:
        raise ValueError("Invalid subtitle position.")

    alignment = _clean(
        style.get("alignment", "center")
    )

    if alignment not in ALIGNMENTS:
        raise ValueError("Invalid subtitle alignment.")

    font_style = _clean(
        style.get("font_style", "normal")
    )

    if font_style not in FONT_STYLES:
        raise ValueError("Invalid font style.")

    try:
        font_size = int(style.get("font_size", 32))
    except (TypeError, ValueError):
        raise ValueError("Font size must be an integer.")

    if not 8 <= font_size <= 120:
        raise ValueError("Font size must be between 8 and 120.")

    color = _clean(
        style.get("color", "#FFFFFF")
    )

    background_color = _clean(
        style.get("background_color", "#000000")
    )

    color_pattern = r"^#[0-9a-fA-F]{6}$"

    if not re.match(color_pattern, color):
        raise ValueError("Invalid text color.")

    if not re.match(color_pattern, background_color):
        raise ValueError("Invalid background color.")

    try:
        opacity = float(style.get("background_opacity", 0.65))
    except (TypeError, ValueError):
        raise ValueError("Background opacity must be numeric.")

    if not 0 <= opacity <= 1:
        raise ValueError("Background opacity must be between 0 and 1.")

    return {
        "font_family": _clean(
            style.get("font_family", "Arial"),
            100,
        ),
        "font_size": font_size,
        "font_style": font_style,
        "color": color,
        "background_color": background_color,
        "background_opacity": opacity,
        "position": position,
        "alignment": alignment,
        "outline": bool(style.get("outline", True)),
        "shadow": bool(style.get("shadow", True)),
    }


# ---------------------------------------------------------
# PROJECT MANAGEMENT
# ---------------------------------------------------------

def create_project(
    name: str,
    description: str = "",
    language: str = "English",
    path: Path | str | None = None,
) -> dict:

    name = _clean(name, 120)

    if not name:
        raise ValueError("Project name is required.")

    database = load_database(path)

    project_id = _id()

    project = {
        "id": project_id,
        "name": name,
        "description": _clean(description, 2000),
        "language": _clean(language, 50),
        "subtitles": [],
        "style": validate_style(),
        "created_at": _now(),
        "updated_at": _now(),
    }

    database["projects"][project_id] = project

    save_database(database, path)

    return project.copy()


def get_project(
    project_id: str,
    path: Path | str | None = None,
) -> dict | None:

    database = load_database(path)

    project = database["projects"].get(project_id)

    return project.copy() if project else None


def list_projects(
    path: Path | str | None = None,
) -> list[dict]:

    database = load_database(path)

    return [
        project.copy()
        for project in database["projects"].values()
    ]


def update_project(
    project_id: str,
    updates: dict,
    path: Path | str | None = None,
) -> dict:

    database = load_database(path)

    project = database["projects"].get(project_id)

    if not project:
        raise ValueError("Subtitle project not found.")

    if "name" in updates:
        name = _clean(updates["name"], 120)

        if not name:
            raise ValueError("Project name cannot be empty.")

        project["name"] = name

    if "description" in updates:
        project["description"] = _clean(
            updates["description"],
            2000,
        )

    if "language" in updates:
        project["language"] = _clean(
            updates["language"],
            50,
        )

    if "style" in updates:
        project["style"] = validate_style(
            updates["style"]
        )

    project["updated_at"] = _now()

    save_database(database, path)

    return project.copy()


def delete_project(
    project_id: str,
    path: Path | str | None = None,
) -> bool:

    database = load_database(path)

    if project_id not in database["projects"]:
        return False

    del database["projects"][project_id]

    save_database(database, path)

    return True


# ---------------------------------------------------------
# SUBTITLE CRUD
# ---------------------------------------------------------

def add_subtitle(
    project_id: str,
    details: dict,
    path: Path | str | None = None,
) -> dict:

    database = load_database(path)

    project = database["projects"].get(project_id)

    if not project:
        raise ValueError("Subtitle project not found.")

    cleaned = validate_subtitle(details)

    subtitle = {
        "id": _id(),
        **cleaned,
        "created_at": _now(),
        "updated_at": _now(),
    }

    project["subtitles"].append(subtitle)

    project["subtitles"].sort(
        key=lambda item: item["start"]
    )

    project["updated_at"] = _now()

    save_database(database, path)

    return subtitle.copy()


def get_subtitle(
    project_id: str,
    subtitle_id: str,
    path: Path | str | None = None,
) -> dict | None:

    project = get_project(project_id, path)

    if not project:
        return None

    for subtitle in project["subtitles"]:
        if subtitle["id"] == subtitle_id:
            return subtitle.copy()

    return None


def update_subtitle(
    project_id: str,
    subtitle_id: str,
    updates: dict,
    path: Path | str | None = None,
) -> dict:

    database = load_database(path)

    project = database["projects"].get(project_id)

    if not project:
        raise ValueError("Subtitle project not found.")

    for index, subtitle in enumerate(project["subtitles"]):

        if subtitle["id"] != subtitle_id:
            continue

        cleaned = validate_subtitle({
            **subtitle,
            **updates,
        })

        updated = {
            **subtitle,
            **cleaned,
            "updated_at": _now(),
        }

        project["subtitles"][index] = updated

        project["subtitles"].sort(
            key=lambda item: item["start"]
        )

        project["updated_at"] = _now()

        save_database(database, path)

        return updated.copy()

    raise ValueError("Subtitle not found.")


def delete_subtitle(
    project_id: str,
    subtitle_id: str,
    path: Path | str | None = None,
) -> bool:

    database = load_database(path)

    project = database["projects"].get(project_id)

    if not project:
        return False

    original = len(project["subtitles"])

    project["subtitles"] = [
        subtitle
        for subtitle in project["subtitles"]
        if subtitle["id"] != subtitle_id
    ]

    if len(project["subtitles"]) == original:
        return False

    project["updated_at"] = _now()

    save_database(database, path)

    return True


def bulk_add_subtitles(
    project_id: str,
    subtitles: list[dict],
    path: Path | str | None = None,
) -> list[dict]:

    if not isinstance(subtitles, list):
        raise ValueError("Subtitles must be a list.")

    database = load_database(path)

    project = database["projects"].get(project_id)

    if not project:
        raise ValueError("Subtitle project not found.")

    # Validate all entries before modifying the project.
    cleaned_items = [
        validate_subtitle(item)
        for item in subtitles
    ]

    created = []

    for cleaned in cleaned_items:

        subtitle = {
            "id": _id(),
            **cleaned,
            "created_at": _now(),
            "updated_at": _now(),
        }

        project["subtitles"].append(subtitle)
        created.append(subtitle.copy())

    project["subtitles"].sort(
        key=lambda item: item["start"]
    )

    project["updated_at"] = _now()

    save_database(database, path)

    return created


# ---------------------------------------------------------
# SUBTITLE SEARCH
# ---------------------------------------------------------

def search_subtitles(
    project_id: str,
    query: str,
    path: Path | str | None = None,
) -> list[dict]:

    project = get_project(project_id, path)

    if not project:
        return []

    query = str(query or "").lower().strip()

    if not query:
        return project["subtitles"]

    return [
        subtitle.copy()
        for subtitle in project["subtitles"]
        if query in subtitle["text"].lower()
        or query in subtitle.get("speaker", "").lower()
    ]


# ---------------------------------------------------------
# OVERLAP DETECTION
# ---------------------------------------------------------

def find_overlaps(
    project_id: str,
    path: Path | str | None = None,
) -> list[dict]:

    project = get_project(project_id, path)

    if not project:
        return []

    subtitles = sorted(
        project["subtitles"],
        key=lambda item: item["start"],
    )

    overlaps = []

    for index, current in enumerate(subtitles):

        for following in subtitles[index + 1:]:

            if following["start"] >= current["end"]:
                break

            overlaps.append({
                "first_id": current["id"],
                "second_id": following["id"],
                "first_text": current["text"],
                "second_text": following["text"],
                "overlap_seconds": round(
                    min(
                        current["end"],
                        following["end"],
                    )
                    - following["start"],
                    3,
                ),
            })

    return overlaps


def validate_project(
    project_id: str,
    path: Path | str | None = None,
) -> dict:

    project = get_project(project_id, path)

    if not project:
        raise ValueError("Subtitle project not found.")

    overlaps = find_overlaps(project_id, path)

    empty = [
        item["id"]
        for item in project["subtitles"]
        if not item["text"].strip()
    ]

    invalid = []

    for item in project["subtitles"]:

        if item["end"] <= item["start"]:
            invalid.append(item["id"])

    return {
        "valid": not overlaps and not empty and not invalid,
        "total_subtitles": len(project["subtitles"]),
        "overlaps": overlaps,
        "empty_subtitles": empty,
        "invalid_subtitles": invalid,
    }


# ---------------------------------------------------------
# SRT EXPORT
# ---------------------------------------------------------

def export_srt(
    project_id: str,
    output_path: Path | str | None = None,
    path: Path | str | None = None,
) -> Path:

    project = get_project(project_id, path)

    if not project:
        raise ValueError("Subtitle project not found.")

    subtitles = sorted(
        project["subtitles"],
        key=lambda item: item["start"],
    )

    lines = []

    counter = 1

    for subtitle in subtitles:

        if not subtitle["enabled"]:
            continue

        start = seconds_to_timestamp(
            subtitle["start"]
        )

        end = seconds_to_timestamp(
            subtitle["end"]
        )

        lines.extend([
            str(counter),
            f"{start} --> {end}",
            subtitle["text"],
            "",
        ])

        counter += 1

    content = "\n".join(lines)

    if output_path:
        destination = Path(output_path)
    else:
        ensure_directories()

        destination = EXPORT_DIR / (
            _safe_filename(project["name"]) + ".srt"
        )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination.write_text(
        content,
        encoding="utf-8-sig",
    )

    return destination


# ---------------------------------------------------------
# SRT IMPORT
# ---------------------------------------------------------

def parse_srt(content: str) -> list[dict]:

    if not isinstance(content, str):
        raise ValueError("SRT content must be text.")

    content = content.lstrip("\ufeff")

    blocks = re.split(
        r"\r?\n\s*\r?\n",
        content.strip(),
    )

    results = []

    for block in blocks:

        lines = block.splitlines()

        if len(lines) < 2:
            continue

        index = 0

        if lines[0].strip().isdigit():
            index = 1

        if index >= len(lines):
            continue

        match = re.match(
            r"^\s*(\d{2}:\d{2}:\d{2}[,.]\d{1,3})"
            r"\s*-->\s*"
            r"(\d{2}:\d{2}:\d{2}[,.]\d{1,3})",
            lines[index],
        )

        if not match:
            raise ValueError(
                f"Invalid SRT timestamp block: {block[:100]}"
            )

        start = timestamp_to_seconds(match.group(1))
        end = timestamp_to_seconds(match.group(2))

        text = "\n".join(lines[index + 1:]).strip()

        results.append(
            validate_subtitle({
                "start": start,
                "end": end,
                "text": text,
            })
        )

    return results


def import_srt(
    project_id: str,
    source: Path | str,
    replace_existing: bool = False,
    path: Path | str | None = None,
) -> list[dict]:

    source = Path(source)

    if not source.is_file():
        raise FileNotFoundError(source)

    if source.suffix.lower() != ".srt":
        raise ValueError("Please provide an SRT file.")

    content = source.read_text(
        encoding="utf-8-sig"
    )

    parsed = parse_srt(content)

    database = load_database(path)

    project = database["projects"].get(project_id)

    if not project:
        raise ValueError("Subtitle project not found.")

    if replace_existing:
        project["subtitles"] = []

    created = []

    for item in parsed:

        subtitle = {
            "id": _id(),
            **item,
            "speaker": "",
            "language": project["language"],
            "enabled": True,
            "created_at": _now(),
            "updated_at": _now(),
        }

        project["subtitles"].append(subtitle)
        created.append(subtitle.copy())

    project["subtitles"].sort(
        key=lambda item: item["start"]
    )

    project["updated_at"] = _now()

    save_database(database, path)

    return created


# ---------------------------------------------------------
# WEBVTT EXPORT
# ---------------------------------------------------------

def export_vtt(
    project_id: str,
    output_path: Path | str | None = None,
    path: Path | str | None = None,
) -> Path:

    project = get_project(project_id, path)

    if not project:
        raise ValueError("Subtitle project not found.")

    lines = ["WEBVTT", ""]

    subtitles = sorted(
        project["subtitles"],
        key=lambda item: item["start"],
    )

    counter = 1

    for subtitle in subtitles:

        if not subtitle["enabled"]:
            continue

        start = seconds_to_timestamp(
            subtitle["start"],
            vtt=True,
        )

        end = seconds_to_timestamp(
            subtitle["end"],
            vtt=True,
        )

        lines.extend([
            str(counter),
            f"{start} --> {end}",
            subtitle["text"],
            "",
        ])

        counter += 1

    if output_path:
        destination = Path(output_path)
    else:
        ensure_directories()

        destination = EXPORT_DIR / (
            _safe_filename(project["name"]) + ".vtt"
        )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination.write_text(
        "\n".join(lines),
        encoding="utf-8-sig",
    )

    return destination


# ---------------------------------------------------------
# WEBVTT IMPORT
# ---------------------------------------------------------

def parse_vtt(content: str) -> list[dict]:

    if not isinstance(content, str):
        raise ValueError("VTT content must be text.")

    content = content.lstrip("\ufeff")

    if not content.startswith("WEBVTT"):
        raise ValueError("Invalid WebVTT header.")

    blocks = re.split(
        r"\r?\n\s*\r?\n",
        content.strip(),
    )

    results = []

    for block in blocks[1:]:

        lines = block.splitlines()

        if not lines:
            continue

        index = 0

        if "-->" not in lines[0]:
            index = 1

        if index >= len(lines):
            continue

        match = re.match(
            r"^\s*(\d{2}:\d{2}:\d{2}\.\d{1,3})"
            r"\s*-->\s*"
            r"(\d{2}:\d{2}:\d{2}\.\d{1,3})",
            lines[index],
        )

        if not match:
            raise ValueError("Invalid WebVTT timestamp.")

        results.append(
            validate_subtitle({
                "start": timestamp_to_seconds(match.group(1)),
                "end": timestamp_to_seconds(match.group(2)),
                "text": "\n".join(
                    lines[index + 1:]
                ).strip(),
            })
        )

    return results


def import_vtt(
    project_id: str,
    source: Path | str,
    replace_existing: bool = False,
    path: Path | str | None = None,
) -> list[dict]:

    source = Path(source)

    if not source.is_file():
        raise FileNotFoundError(source)

    if source.suffix.lower() != ".vtt":
        raise ValueError("Please provide a VTT file.")

    parsed = parse_vtt(
        source.read_text(encoding="utf-8-sig")
    )

    database = load_database(path)

    project = database["projects"].get(project_id)

    if not project:
        raise ValueError("Subtitle project not found.")

    if replace_existing:
        project["subtitles"] = []

    created = []

    for item in parsed:

        subtitle = {
            "id": _id(),
            **item,
            "speaker": "",
            "language": project["language"],
            "enabled": True,
            "created_at": _now(),
            "updated_at": _now(),
        }

        project["subtitles"].append(subtitle)
        created.append(subtitle.copy())

    project["subtitles"].sort(
        key=lambda item: item["start"]
    )

    project["updated_at"] = _now()

    save_database(database, path)

    return created


# ---------------------------------------------------------
# TIMELINE EXPORT
# ---------------------------------------------------------

def export_timeline_metadata(
    project_id: str,
    path: Path | str | None = None,
) -> dict:

    project = get_project(project_id, path)

    if not project:
        raise ValueError("Subtitle project not found.")

    return {
        "project_id": project_id,
        "project_name": project["name"],
        "style": project["style"],
        "subtitles": [
            {
                "id": item["id"],
                "start": item["start"],
                "end": item["end"],
                "text": item["text"],
                "enabled": item["enabled"],
            }
            for item in project["subtitles"]
        ],
        "rendering_status": "metadata_only",
    }


# ---------------------------------------------------------
# STATISTICS
# ---------------------------------------------------------

def get_statistics(
    project_id: str,
    path: Path | str | None = None,
) -> dict:

    project = get_project(project_id, path)

    if not project:
        raise ValueError("Subtitle project not found.")

    subtitles = project["subtitles"]

    enabled = [
        item for item in subtitles
        if item["enabled"]
    ]

    total_words = sum(
        len(item["text"].split())
        for item in enabled
    )

    return {
        "total_subtitles": len(subtitles),
        "enabled_subtitles": len(enabled),
        "disabled_subtitles": len(subtitles) - len(enabled),
        "total_words": total_words,
        "total_characters": sum(
            len(item["text"])
            for item in enabled
        ),
        "estimated_duration": max(
            (
                item["end"]
                for item in enabled
            ),
            default=0,
        ),
        "overlaps": len(
            find_overlaps(project_id, path)
        ),
    }


# ---------------------------------------------------------
# STREAMLIT UI
# ---------------------------------------------------------

def render(st: Any) -> None:

    ensure_directories()

    st.title("Professional Subtitle Manager")

    st.caption(
        "Create, edit, import and export subtitles "
        "for your cinematic videos."
    )

    tab_projects, tab_editor, tab_import, tab_export = st.tabs([
        "Projects",
        "Subtitle Editor",
        "Import",
        "Export",
    ])

    # -----------------------------------------------------
    # PROJECTS
    # -----------------------------------------------------

    with tab_projects:

        st.subheader("Create subtitle project")

        with st.form("create_subtitle_project"):

            name = st.text_input(
                "Project name",
                placeholder="Episode 01 Subtitles",
            )

            description = st.text_area(
                "Description",
            )

            language = st.selectbox(
                "Language",
                [
                    "English",
                    "Hindi",
                    "Hinglish",
                    "Marathi",
                    "Other",
                ],
            )

            submitted = st.form_submit_button(
                "Create Project"
            )

        if submitted:

            try:
                project = create_project(
                    name,
                    description,
                    language,
                )

                st.success(
                    f"Created project: {project['name']}"
                )

            except Exception as exc:
                st.error(str(exc))

        projects = list_projects()

        st.subheader("Saved projects")

        for project in projects:

            with st.container(border=True):

                st.write(f"**{project['name']}**")

                st.caption(
                    f"{project['language']} | "
                    f"{len(project['subtitles'])} subtitles"
                )

                if st.button(
                    "Delete Project",
                    key=f"delete_project_{project['id']}",
                ):

                    delete_project(project["id"])

                    st.success("Project deleted.")

                    st.rerun()

    projects = list_projects()

    project_options = {
        project["name"] + " (" + project["id"][:8] + ")":
        project["id"]
        for project in projects
    }

    selected_project_id = None

    if project_options:

        selected_label = st.selectbox(
            "Select subtitle project",
            list(project_options.keys()),
            key="selected_subtitle_project",
        )

        selected_project_id = project_options[selected_label]

    # -----------------------------------------------------
    # EDITOR
    # -----------------------------------------------------

    with tab_editor:

        if not selected_project_id:

            st.info("Create a subtitle project first.")

        else:

            project = get_project(selected_project_id)

            st.subheader("Add subtitle")

            with st.form("add_subtitle_form"):

                text = st.text_area(
                    "Subtitle text",
                    placeholder="Enter dialogue or narration...",
                )

                col1, col2 = st.columns(2)

                with col1:
                    start = st.number_input(
                        "Start time (seconds)",
                        min_value=0.0,
                        value=0.0,
                        step=0.1,
                    )

                with col2:
                    end = st.number_input(
                        "End time (seconds)",
                        min_value=0.1,
                        value=3.0,
                        step=0.1,
                    )

                speaker = st.text_input(
                    "Speaker",
                )

                submitted = st.form_submit_button(
                    "Add Subtitle"
                )

            if submitted:

                try:
                    add_subtitle(
                        selected_project_id,
                        {
                            "text": text,
                            "start": start,
                            "end": end,
                            "speaker": speaker,
                            "language": project["language"],
                        },
                    )

                    st.success("Subtitle added.")

                    st.rerun()

                except Exception as exc:
                    st.error(str(exc))

            st.divider()

            st.subheader("Subtitle list")

            for index, subtitle in enumerate(
                project["subtitles"]
            ):

                with st.container(border=True):

                    st.write(
                        f"**{index + 1}. {subtitle['text']}**"
                    )

                    st.caption(
                        f"{seconds_to_timestamp(subtitle['start'])}"
                        f" → "
                        f"{seconds_to_timestamp(subtitle['end'])}"
                    )

                    with st.expander("Edit subtitle"):

                        new_text = st.text_area(
                            "Text",
                            value=subtitle["text"],
                            key=f"text_{subtitle['id']}",
                        )

                        new_start = st.number_input(
                            "Start",
                            value=float(subtitle["start"]),
                            min_value=0.0,
                            key=f"start_{subtitle['id']}",
                        )

                        new_end = st.number_input(
                            "End",
                            value=float(subtitle["end"]),
                            min_value=0.0,
                            key=f"end_{subtitle['id']}",
                        )

                        if st.button(
                            "Save Changes",
                            key=f"save_{subtitle['id']}",
                        ):

                            try:
                                update_subtitle(
                                    selected_project_id,
                                    subtitle["id"],
                                    {
                                        "text": new_text,
                                        "start": new_start,
                                        "end": new_end,
                                    },
                                )

                                st.success("Subtitle updated.")

                                st.rerun()

                            except Exception as exc:
                                st.error(str(exc))

                    if st.button(
                        "Delete Subtitle",
                        key=f"delete_sub_{subtitle['id']}",
                    ):

                        delete_subtitle(
                            selected_project_id,
                            subtitle["id"],
                        )

                        st.rerun()

            st.divider()

            st.subheader("Subtitle style")

            style = project["style"]

            with st.form("subtitle_style_form"):

                font_family = st.text_input(
                    "Font family",
                    value=style["font_family"],
                )

                font_size = st.slider(
                    "Font size",
                    8,
                    120,
                    style["font_size"],
                )

                font_style = st.selectbox(
                    "Font style",
                    FONT_STYLES,
                    index=FONT_STYLES.index(
                        style["font_style"]
                    ),
                )

                color = st.color_picker(
                    "Text color",
                    style["color"],
                )

                background_color = st.color_picker(
                    "Background color",
                    style["background_color"],
                )

                opacity = st.slider(
                    "Background opacity",
                    0.0,
                    1.0,
                    float(style["background_opacity"]),
                )

                position = st.selectbox(
                    "Position",
                    POSITIONS,
                    index=POSITIONS.index(
                        style["position"]
                    ),
                )

                alignment = st.selectbox(
                    "Alignment",
                    ALIGNMENTS,
                    index=ALIGNMENTS.index(
                        style["alignment"]
                    ),
                )

                outline = st.checkbox(
                    "Enable outline",
                    value=style["outline"],
                )

                shadow = st.checkbox(
                    "Enable shadow",
                    value=style["shadow"],
                )

                save_style = st.form_submit_button(
                    "Save Subtitle Style"
                )

            if save_style:

                try:
                    update_project(
                        selected_project_id,
                        {
                            "style": {
                                "font_family": font_family,
                                "font_size": font_size,
                                "font_style": font_style,
                                "color": color,
                                "background_color": background_color,
                                "background_opacity": opacity,
                                "position": position,
                                "alignment": alignment,
                                "outline": outline,
                                "shadow": shadow,
                            }
                        },
                    )

                    st.success("Subtitle style saved.")

                except Exception as exc:
                    st.error(str(exc))

            st.divider()

            validation = validate_project(
                selected_project_id
            )

            if validation["valid"]:
                st.success("Subtitle validation passed.")
            else:
                st.warning(
                    f"Found {len(validation['overlaps'])} overlapping subtitle pairs."
                )

                for overlap in validation["overlaps"]:
                    st.write(
                        f"{overlap['first_text']} overlaps with "
                        f"{overlap['second_text']}"
                    )

    # -----------------------------------------------------
    # IMPORT
    # -----------------------------------------------------

    with tab_import:

        if not selected_project_id:

            st.info("Create a subtitle project first.")

        else:

            uploaded = st.file_uploader(
                "Upload SRT or VTT",
                type=["srt", "vtt"],
            )

            replace_existing = st.checkbox(
                "Replace existing subtitles",
                value=False,
            )

            if st.button(
                "Import Subtitle File",
                disabled=uploaded is None,
            ):

                try:

                    suffix = Path(uploaded.name).suffix.lower()

                    if suffix not in [".srt", ".vtt"]:
                        raise ValueError(
                            "Only SRT and VTT files are supported."
                        )

                    temporary = (
                        SUBTITLE_DIR
                        / (
                            "upload_"
                            + uuid.uuid4().hex
                            + suffix
                        )
                    )

                    temporary.write_bytes(
                        uploaded.getvalue()
                    )

                    try:
                        if suffix == ".srt":
                            imported = import_srt(
                                selected_project_id,
                                temporary,
                                replace_existing,
                            )
                        else:
                            imported = import_vtt(
                                selected_project_id,
                                temporary,
                                replace_existing,
                            )
                    finally:
                        temporary.unlink(missing_ok=True)

                    st.success(
                        f"Imported {len(imported)} subtitles."
                    )

                    st.rerun()

                except Exception as exc:
                    st.error(str(exc))

    # -----------------------------------------------------
    # EXPORT
    # -----------------------------------------------------

    with tab_export:

        if not selected_project_id:

            st.info("Create a subtitle project first.")

        else:

            stats = get_statistics(
                selected_project_id
            )

            col1, col2, col3 = st.columns(3)

            col1.metric(
                "Subtitles",
                stats["total_subtitles"],
            )

            col2.metric(
                "Words",
                stats["total_words"],
            )

            col3.metric(
                "Overlaps",
                stats["overlaps"],
            )

            export_format = st.selectbox(
                "Export format",
                ["SRT", "WebVTT"],
            )

            if st.button(
                "Generate Subtitle File",
                type="primary",
            ):

                try:

                    if export_format == "SRT":
                        output = export_srt(
                            selected_project_id
                        )
                    else:
                        output = export_vtt(
                            selected_project_id
                        )

                    with output.open("rb") as file:

                        st.download_button(
                            "Download Subtitle File",
                            data=file.read(),
                            file_name=output.name,
                            mime="text/plain",
                        )

                except Exception as exc:
                    st.error(str(exc))

            st.divider()

            if st.button("Show Subtitle Statistics"):
                st.json(stats)


# ---------------------------------------------------------
# BUILT-IN TESTS
# ---------------------------------------------------------

def run_tests() -> bool:

    import tempfile
    import unittest

    class SubtitleTests(unittest.TestCase):

        def setUp(self):

            self.temp = tempfile.TemporaryDirectory()
            self.root = Path(self.temp.name)
            self.database = self.root / "subtitles.json"

            self.project = create_project(
                "Test Subtitle Project",
                language="English",
                path=self.database,
            )

        def tearDown(self):
            self.temp.cleanup()

        def sample(self):
            return {
                "text": "Hello world",
                "start": 1,
                "end": 3,
                "language": "English",
            }

        def test_timestamp_conversion(self):

            seconds = timestamp_to_seconds(
                "00:01:30,500"
            )

            self.assertEqual(seconds, 90.5)

            timestamp = seconds_to_timestamp(90.5)

            self.assertEqual(
                timestamp,
                "00:01:30,500",
            )

        def test_create_project(self):

            self.assertEqual(
                self.project["name"],
                "Test Subtitle Project",
            )

        def test_add_subtitle(self):

            subtitle = add_subtitle(
                self.project["id"],
                self.sample(),
                self.database,
            )

            self.assertEqual(
                subtitle["text"],
                "Hello world",
            )

        def test_update_subtitle(self):

            subtitle = add_subtitle(
                self.project["id"],
                self.sample(),
                self.database,
            )

            updated = update_subtitle(
                self.project["id"],
                subtitle["id"],
                {"text": "Updated"},
                self.database,
            )

            self.assertEqual(
                updated["text"],
                "Updated",
            )

        def test_delete_subtitle(self):

            subtitle = add_subtitle(
                self.project["id"],
                self.sample(),
                self.database,
            )

            self.assertTrue(
                delete_subtitle(
                    self.project["id"],
                    subtitle["id"],
                    self.database,
                )
            )

        def test_invalid_timestamp(self):

            with self.assertRaises(ValueError):
                timestamp_to_seconds("invalid")

        def test_invalid_subtitle(self):

            data = self.sample()
            data["end"] = 0

            with self.assertRaises(ValueError):
                validate_subtitle(data)

        def test_style_validation(self):

            style = validate_style({
                "font_size": 48,
                "color": "#FF0000",
            })

            self.assertEqual(
                style["font_size"],
                48,
            )

        def test_invalid_style(self):

            with self.assertRaises(ValueError):
                validate_style({
                    "font_size": 200,
                })

        def test_overlap_detection(self):

            add_subtitle(
                self.project["id"],
                {
                    "text": "First",
                    "start": 0,
                    "end": 3,
                },
                self.database,
            )

            add_subtitle(
                self.project["id"],
                {
                    "text": "Second",
                    "start": 2,
                    "end": 4,
                },
                self.database,
            )

            overlaps = find_overlaps(
                self.project["id"],
                self.database,
            )

            self.assertEqual(len(overlaps), 1)

        def test_srt_parse(self):

            content = (
                "1\n"
                "00:00:01,000 --> 00:00:03,000\n"
                "Hello world\n"
            )

            results = parse_srt(content)

            self.assertEqual(
                results[0]["text"],
                "Hello world",
            )

        def test_srt_export(self):

            add_subtitle(
                self.project["id"],
                self.sample(),
                self.database,
            )

            output = export_srt(
                self.project["id"],
                self.root / "test.srt",
                self.database,
            )

            self.assertTrue(output.exists())

            self.assertIn(
                "Hello world",
                output.read_text(encoding="utf-8-sig"),
            )

        def test_vtt_parse(self):

            content = (
                "WEBVTT\n\n"
                "1\n"
                "00:00:01.000 --> 00:00:03.000\n"
                "Hello VTT\n"
            )

            results = parse_vtt(content)

            self.assertEqual(
                results[0]["text"],
                "Hello VTT",
            )

        def test_vtt_export(self):

            add_subtitle(
                self.project["id"],
                self.sample(),
                self.database,
            )

            output = export_vtt(
                self.project["id"],
                self.root / "test.vtt",
                self.database,
            )

            self.assertTrue(output.exists())

            self.assertIn(
                "WEBVTT",
                output.read_text(encoding="utf-8-sig"),
            )

        def test_statistics(self):

            add_subtitle(
                self.project["id"],
                self.sample(),
                self.database,
            )

            stats = get_statistics(
                self.project["id"],
                self.database,
            )

            self.assertEqual(
                stats["total_subtitles"],
                1,
            )

            self.assertEqual(
                stats["total_words"],
                2,
            )

        def test_delete_project(self):

            self.assertTrue(
                delete_project(
                    self.project["id"],
                    self.database,
                )
            )

        def test_bulk_add_is_validated_before_writing(self):

            items = [
                {
                    "text": "Valid",
                    "start": 0,
                    "end": 1,
                },
                {
                    "text": "",
                    "start": 1,
                    "end": 2,
                },
            ]

            with self.assertRaises(ValueError):
                bulk_add_subtitles(
                    self.project["id"],
                    items,
                    self.database,
                )

            project = get_project(
                self.project["id"],
                self.database,
            )

            self.assertEqual(
                len(project["subtitles"]),
                0,
            )

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        SubtitleTests
    )

    result = unittest.TextTestRunner(
        verbosity=2
    ).run(suite)

    return result.wasSuccessful()


# ---------------------------------------------------------
# COMMAND LINE
# ---------------------------------------------------------

if __name__ == "__main__":

    import sys

    if "--test" in sys.argv:
        success = run_tests()
        raise SystemExit(0 if success else 1)

    print("AI Influencer Studio - Subtitle Manager")
    print("Run tests:")
    print("python -m modules.subtitle_manager --test")
