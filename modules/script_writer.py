
"""
AI Influencer Studio
File 53: modules/script_writer.py

Local Script Writing Studio.

Features:
- Script creation and management
- YouTube, Reels and Shorts templates
- Hook, introduction, scenes and CTA
- Scene-by-scene narration
- Character dialogue
- Script search and editing
- TXT and JSON export
- Streamlit dashboard
- Built-in tests

This module uses local templates.
It does not require an external AI API.
"""

from __future__ import annotations

import argparse
import json
import re
import tempfile
import uuid

from datetime import datetime
from pathlib import Path
from typing import Any


# =========================================================
# PATH CONFIGURATION
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs" / "scripts"

DATABASE_FILE = DATA_DIR / "scripts.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================
# CONSTANTS
# =========================================================

SCRIPT_TYPES = [
    "YouTube Long Video",
    "YouTube Shorts",
    "Instagram Reel",
    "TikTok Video",
    "Advertisement",
    "Storytelling",
    "Documentary",
    "Other",
]

SCRIPT_STATUSES = [
    "Idea",
    "Draft",
    "Review",
    "Approved",
    "Production",
    "Completed",
]

TONE_OPTIONS = [
    "Cinematic",
    "Professional",
    "Funny",
    "Educational",
    "Emotional",
    "Horror",
    "Sci-Fi",
    "Inspirational",
]

LANGUAGES = [
    "English",
    "Hindi",
    "Hinglish",
    "Marathi",
    "Other",
]

DEFAULT_DATABASE = {
    "scripts": [],
    "version": 1,
}


# =========================================================
# HELPERS
# =========================================================

def make_id() -> str:
    return uuid.uuid4().hex


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def clean_text(value: Any, limit: int = 10000) -> str:
    if value is None:
        return ""

    return str(value).strip()[:limit]


def safe_filename(value: str) -> str:
    value = clean_text(value, 100)

    value = re.sub(
        r"[^a-zA-Z0-9_-]+",
        "_",
        value
    )

    return value.strip("_") or "script"


def count_words(text: str) -> int:
    return len(
        re.findall(r"\b[\w'-]+\b", text)
    )


def estimate_speech_duration(
    text: str,
    words_per_minute: int = 130
) -> float:

    words = count_words(text)

    if words_per_minute <= 0:
        return 0.0

    return round(
        words / words_per_minute * 60,
        1
    )


# =========================================================
# DATABASE
# =========================================================

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

        data.setdefault("scripts", [])
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


# =========================================================
# SCENE VALIDATION
# =========================================================

def validate_scene(scene: dict) -> dict:

    title = clean_text(
        scene.get("title", "Untitled Scene"),
        200
    )

    return {
        "id": clean_text(scene.get("id")) or make_id(),
        "title": title or "Untitled Scene",
        "visual": clean_text(
            scene.get("visual"),
            3000
        ),
        "camera": clean_text(
            scene.get("camera"),
            1000
        ),
        "narration": clean_text(
            scene.get("narration"),
            5000
        ),
        "dialogue": clean_text(
            scene.get("dialogue"),
            5000
        ),
        "sound_effects": clean_text(
            scene.get("sound_effects"),
            1000
        ),
        "duration": max(
            1,
            min(
                3600,
                int(scene.get("duration", 10) or 10)
            )
        ),
    }


# =========================================================
# SCRIPT VALIDATION
# =========================================================

def validate_script(data: dict) -> dict:

    title = clean_text(
        data.get("title"),
        200
    )

    if not title:
        raise ValueError("Script title is required.")

    script_type = clean_text(
        data.get("script_type", SCRIPT_TYPES[0])
    )

    if script_type not in SCRIPT_TYPES:
        raise ValueError("Invalid script type.")

    status = clean_text(
        data.get("status", "Idea")
    )

    if status not in SCRIPT_STATUSES:
        raise ValueError("Invalid script status.")

    tone = clean_text(
        data.get("tone", "Cinematic")
    )

    if tone not in TONE_OPTIONS:
        tone = "Cinematic"

    language = clean_text(
        data.get("language", "English")
    )

    if language not in LANGUAGES:
        language = "Other"

    raw_scenes = data.get("scenes", [])

    if not isinstance(raw_scenes, list):
        raise ValueError("Scenes must be a list.")

    scenes = [
        validate_scene(scene)
        for scene in raw_scenes
        if isinstance(scene, dict)
    ]

    return {
        "id": clean_text(data.get("id")) or make_id(),
        "title": title,
        "script_type": script_type,
        "status": status,
        "tone": tone,
        "language": language,
        "target_duration": max(
            1,
            min(
                86400,
                int(data.get("target_duration", 60) or 60)
            )
        ),
        "topic": clean_text(
            data.get("topic"),
            2000
        ),
        "audience": clean_text(
            data.get("audience"),
            1000
        ),
        "hook": clean_text(
            data.get("hook"),
            3000
        ),
        "introduction": clean_text(
            data.get("introduction"),
            3000
        ),
        "main_content": clean_text(
            data.get("main_content"),
            10000
        ),
        "call_to_action": clean_text(
            data.get("call_to_action"),
            3000
        ),
        "scenes": scenes,
        "notes": clean_text(
            data.get("notes"),
            3000
        ),
        "created_at": (
            data.get("created_at") or now_iso()
        ),
        "updated_at": now_iso(),
    }


# =========================================================
# SCRIPT CRUD
# =========================================================

def create_script(data: dict) -> dict:

    database = load_database()

    script = validate_script(data)

    database["scripts"].append(script)

    save_database(database)

    return script


def get_scripts(
    status: str | None = None,
    script_type: str | None = None
) -> list:

    scripts = load_database()["scripts"]

    if status and status != "All":

        scripts = [
            item for item in scripts
            if item["status"] == status
        ]

    if script_type and script_type != "All":

        scripts = [
            item for item in scripts
            if item["script_type"] == script_type
        ]

    return sorted(
        scripts,
        key=lambda item: item["updated_at"],
        reverse=True
    )


def get_script(script_id: str) -> dict | None:

    for script in get_scripts():

        if script["id"] == script_id:
            return script

    return None


def update_script(
    script_id: str,
    updates: dict
) -> dict:

    database = load_database()

    for index, script in enumerate(database["scripts"]):

        if script["id"] == script_id:

            updated_data = {
                **script,
                **updates,
                "id": script_id,
            }

            updated = validate_script(updated_data)

            database["scripts"][index] = updated

            save_database(database)

            return updated

    raise ValueError("Script not found.")


def delete_script(script_id: str) -> bool:

    database = load_database()

    original_count = len(database["scripts"])

    database["scripts"] = [
        item
        for item in database["scripts"]
        if item["id"] != script_id
    ]

    if len(database["scripts"]) == original_count:
        return False

    save_database(database)

    return True


# =========================================================
# SCENE MANAGEMENT
# =========================================================

def add_scene(
    script_id: str,
    scene_data: dict
) -> dict:

    script = get_script(script_id)

    if not script:
        raise ValueError("Script not found.")

    scene = validate_scene(scene_data)

    scenes = list(script["scenes"])
    scenes.append(scene)

    update_script(
        script_id,
        {"scenes": scenes}
    )

    return scene


def update_scene(
    script_id: str,
    scene_id: str,
    updates: dict
) -> dict:

    script = get_script(script_id)

    if not script:
        raise ValueError("Script not found.")

    scenes = list(script["scenes"])

    for index, scene in enumerate(scenes):

        if scene["id"] == scene_id:

            updated = validate_scene({
                **scene,
                **updates,
                "id": scene_id,
            })

            scenes[index] = updated

            update_script(
                script_id,
                {"scenes": scenes}
            )

            return updated

    raise ValueError("Scene not found.")


def delete_scene(
    script_id: str,
    scene_id: str
) -> bool:

    script = get_script(script_id)

    if not script:
        return False

    scenes = script["scenes"]

    updated_scenes = [
        scene
        for scene in scenes
        if scene["id"] != scene_id
    ]

    if len(updated_scenes) == len(scenes):
        return False

    update_script(
        script_id,
        {"scenes": updated_scenes}
    )

    return True


# =========================================================
# SCRIPT TEMPLATES
# =========================================================

def get_template(
    script_type: str,
    topic: str,
    tone: str = "Cinematic"
) -> dict:

    topic = clean_text(topic, 500)

    if not topic:
        topic = "Your Topic"

    templates = {

        "YouTube Shorts": {
            "hook": (
                f"What if {topic} changed everything? "
                "Watch until the end."
            ),
            "introduction": (
                f"Today, we explore {topic}."
            ),
            "main_content": (
                "Scene 1: Introduce the main idea.\n"
                "Scene 2: Show the biggest challenge.\n"
                "Scene 3: Reveal an unexpected twist."
            ),
            "call_to_action": (
                "Follow for more short videos!"
            ),
        },

        "Instagram Reel": {
            "hook": (
                f"You won't believe what happens with {topic}."
            ),
            "introduction": (
                "Here is the story in a few seconds."
            ),
            "main_content": (
                "Start with a powerful visual.\n"
                "Show the main transformation.\n"
                "Finish with a memorable moment."
            ),
            "call_to_action": (
                "Share this Reel with your friends."
            ),
        },

        "YouTube Long Video": {
            "hook": (
                f"Imagine a world where {topic} "
                "becomes reality."
            ),
            "introduction": (
                "Welcome back. Today we are exploring "
                f"{topic}."
            ),
            "main_content": (
                "Chapter 1: Background and context.\n"
                "Chapter 2: Main story or explanation.\n"
                "Chapter 3: Challenges and discoveries.\n"
                "Chapter 4: Conclusion and key lessons."
            ),
            "call_to_action": (
                "Like, subscribe and share your thoughts "
                "in the comments."
            ),
        },

        "Storytelling": {
            "hook": (
                "Everything changed on the day "
                f"{topic} began."
            ),
            "introduction": (
                "This is a story about courage, "
                "choices and unexpected consequences."
            ),
            "main_content": (
                "Act 1: Introduce the world and characters.\n"
                "Act 2: Introduce the conflict.\n"
                "Act 3: Build tension.\n"
                "Act 4: Reveal the climax.\n"
                "Act 5: Deliver the ending."
            ),
            "call_to_action": (
                "Would you like to see the next chapter?"
            ),
        },

        "Documentary": {
            "hook": (
                f"The truth behind {topic} "
                "is more interesting than you think."
            ),
            "introduction": (
                "In this documentary, we examine "
                f"{topic}."
            ),
            "main_content": (
                "Section 1: Background.\n"
                "Section 2: Evidence and context.\n"
                "Section 3: Important developments.\n"
                "Section 4: Findings and conclusions."
            ),
            "call_to_action": (
                "Subscribe for more documentaries."
            ),
        },

    }

    selected = templates.get(
        script_type,
        templates["YouTube Long Video"]
    )

    return {
        **selected,
        "topic": topic,
        "tone": tone,
        "script_type": script_type,
    }


def apply_template(
    script_id: str,
    script_type: str,
    topic: str,
    tone: str = "Cinematic"
) -> dict:

    template = get_template(
        script_type,
        topic,
        tone
    )

    return update_script(
        script_id,
        {
            "script_type": script_type,
            "topic": topic,
            "tone": tone,
            "hook": template["hook"],
            "introduction": template["introduction"],
            "main_content": template["main_content"],
            "call_to_action": template["call_to_action"],
        }
    )


# =========================================================
# SCRIPT EXPORT
# =========================================================

def format_script(script: dict) -> str:

    lines = []

    lines.append("=" * 60)
    lines.append(script["title"].upper())
    lines.append("=" * 60)

    lines.append(
        f"Type: {script['script_type']}"
    )

    lines.append(
        f"Language: {script['language']}"
    )

    lines.append(
        f"Tone: {script['tone']}"
    )

    lines.append(
        f"Target Duration: {script['target_duration']} seconds"
    )

    lines.append("")

    lines.append("TOPIC")
    lines.append(script["topic"])
    lines.append("")

    lines.append("HOOK")
    lines.append(script["hook"])
    lines.append("")

    lines.append("INTRODUCTION")
    lines.append(script["introduction"])
    lines.append("")

    lines.append("MAIN CONTENT")
    lines.append(script["main_content"])
    lines.append("")

    lines.append("SCENES")

    for index, scene in enumerate(
        script["scenes"],
        start=1
    ):

        lines.append("")
        lines.append(
            f"SCENE {index}: {scene['title']}"
        )

        lines.append(
            f"Duration: {scene['duration']} seconds"
        )

        lines.append(
            f"Visual: {scene['visual']}"
        )

        lines.append(
            f"Camera: {scene['camera']}"
        )

        lines.append(
            f"Narration: {scene['narration']}"
        )

        lines.append(
            f"Dialogue: {scene['dialogue']}"
        )

        lines.append(
            f"Sound Effects: {scene['sound_effects']}"
        )

    lines.append("")
    lines.append("CALL TO ACTION")
    lines.append(script["call_to_action"])

    lines.append("")
    lines.append("NOTES")
    lines.append(script["notes"])

    return "\n".join(lines)


def export_script_txt(script_id: str) -> Path:

    script = get_script(script_id)

    if not script:
        raise ValueError("Script not found.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_file = OUTPUT_DIR / (
        safe_filename(script["title"]) + ".txt"
    )

    output_file.write_text(
        format_script(script),
        encoding="utf-8"
    )

    return output_file


def export_all_json() -> Path:

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_file = OUTPUT_DIR / "all_scripts.json"

    output_file.write_text(
        json.dumps(
            load_database(),
            indent=4,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    return output_file


# =========================================================
# SCRIPT ANALYTICS
# =========================================================

def get_script_statistics() -> dict:

    scripts = get_scripts()

    total_scenes = sum(
        len(script["scenes"])
        for script in scripts
    )

    total_words = sum(
        count_words(script["hook"])
        + count_words(script["introduction"])
        + count_words(script["main_content"])
        + count_words(script["call_to_action"])
        for script in scripts
    )

    status_counts = {
        status: 0
        for status in SCRIPT_STATUSES
    }

    for script in scripts:
        status_counts[script["status"]] += 1

    return {
        "total_scripts": len(scripts),
        "total_scenes": total_scenes,
        "total_words": total_words,
        "status_counts": status_counts,
    }


def search_scripts(query: str) -> list:

    query = clean_text(query).lower()

    if not query:
        return get_scripts()

    results = []

    for script in get_scripts():

        searchable = " ".join([
            script["title"],
            script["topic"],
            script["script_type"],
            script["tone"],
            script["hook"],
            script["main_content"],
        ]).lower()

        if query in searchable:
            results.append(script)

    return results


# =========================================================
# STREAMLIT UI
# =========================================================

def render():

    try:
        import streamlit as st

    except ImportError:
        raise RuntimeError(
            "Install Streamlit: pip install streamlit"
        )

    st.title("✍️ Script Writer Studio")

    st.caption(
        "Create scripts, organize scenes and prepare "
        "content for production."
    )

    stats = get_script_statistics()

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Total Scripts",
        stats["total_scripts"]
    )

    c2.metric(
        "Total Scenes",
        stats["total_scenes"]
    )

    c3.metric(
        "Total Words",
        stats["total_words"]
    )

    tabs = st.tabs([
        "Create Script",
        "My Scripts",
        "Scene Editor",
        "Templates",
        "Export",
    ])

    # -----------------------------------------------------
    # CREATE SCRIPT
    # -----------------------------------------------------

    with tabs[0]:

        st.subheader("Create New Script")

        with st.form("create_script_form"):

            title = st.text_input(
                "Script title *"
            )

            topic = st.text_area(
                "Video topic"
            )

            script_type = st.selectbox(
                "Script type",
                SCRIPT_TYPES
            )

            tone = st.selectbox(
                "Tone",
                TONE_OPTIONS
            )

            language = st.selectbox(
                "Language",
                LANGUAGES
            )

            target_duration = st.number_input(
                "Target duration (seconds)",
                min_value=1,
                max_value=86400,
                value=60
            )

            audience = st.text_input(
                "Target audience"
            )

            submitted = st.form_submit_button(
                "Create Script"
            )

            if submitted:

                try:

                    script = create_script({
                        "title": title,
                        "topic": topic,
                        "script_type": script_type,
                        "tone": tone,
                        "language": language,
                        "target_duration": target_duration,
                        "audience": audience,
                        "status": "Draft",
                    })

                    st.success(
                        f"Created script: {script['title']}"
                    )

                    st.rerun()

                except ValueError as error:

                    st.error(str(error))

    # -----------------------------------------------------
    # MY SCRIPTS
    # -----------------------------------------------------

    with tabs[1]:

        st.subheader("Saved Scripts")

        query = st.text_input(
            "Search scripts"
        )

        for script in search_scripts(query):

            with st.expander(script["title"]):

                st.write(
                    f"**Type:** {script['script_type']}"
                )

                st.write(
                    f"**Status:** {script['status']}"
                )

                st.write(
                    f"**Topic:** {script['topic']}"
                )

                new_status = st.selectbox(
                    "Change status",
                    SCRIPT_STATUSES,
                    index=SCRIPT_STATUSES.index(
                        script["status"]
                    ),
                    key=f"script_status_{script['id']}"
                )

                if st.button(
                    "Update Status",
                    key=f"script_update_{script['id']}"
                ):

                    update_script(
                        script["id"],
                        {"status": new_status}
                    )

                    st.success("Status updated.")
                    st.rerun()

                st.text_area(
                    "Hook",
                    value=script["hook"],
                    key=f"hook_view_{script['id']}",
                    disabled=True
                )

                if st.button(
                    "Delete Script",
                    key=f"script_delete_{script['id']}"
                ):

                    delete_script(script["id"])

                    st.success("Script deleted.")
                    st.rerun()

    # -----------------------------------------------------
    # SCENE EDITOR
    # -----------------------------------------------------

    with tabs[2]:

        st.subheader("Scene-by-Scene Editor")

        scripts = get_scripts()

        if not scripts:

            st.info("Create a script first.")

        else:

            options = {
                script["title"]: script["id"]
                for script in scripts
            }

            selected_title = st.selectbox(
                "Select script",
                list(options.keys())
            )

            selected_id = options[selected_title]

            script = get_script(selected_id)

            st.markdown("**Main Script Sections**")

            with st.form("main_script_editor"):

                hook = st.text_area(
                    "Hook",
                    value=script["hook"]
                )

                introduction = st.text_area(
                    "Introduction",
                    value=script["introduction"]
                )

                main_content = st.text_area(
                    "Main content",
                    value=script["main_content"],
                    height=200
                )

                cta = st.text_area(
                    "Call to action",
                    value=script["call_to_action"]
                )

                submitted = st.form_submit_button(
                    "Save Script Sections"
                )

                if submitted:

                    update_script(
                        selected_id,
                        {
                            "hook": hook,
                            "introduction": introduction,
                            "main_content": main_content,
                            "call_to_action": cta,
                        }
                    )

                    st.success("Script sections saved.")
                    st.rerun()

            st.divider()

            st.subheader("Add Scene")

            with st.form("add_scene_form"):

                scene_title = st.text_input(
                    "Scene title"
                )

                visual = st.text_area(
                    "Visual description"
                )

                camera = st.text_input(
                    "Camera direction"
                )

                narration = st.text_area(
                    "Narration"
                )

                dialogue = st.text_area(
                    "Character dialogue"
                )

                sound_effects = st.text_input(
                    "Sound effects"
                )

                duration = st.number_input(
                    "Scene duration in seconds",
                    min_value=1,
                    max_value=3600,
                    value=10
                )

                submitted = st.form_submit_button(
                    "Add Scene"
                )

                if submitted:

                    try:

                        add_scene(
                            selected_id,
                            {
                                "title": scene_title,
                                "visual": visual,
                                "camera": camera,
                                "narration": narration,
                                "dialogue": dialogue,
                                "sound_effects": sound_effects,
                                "duration": duration,
                            }
                        )

                        st.success("Scene added.")
                        st.rerun()

                    except ValueError as error:

                        st.error(str(error))

            st.divider()

            st.subheader("Existing Scenes")

            script = get_script(selected_id)

            for index, scene in enumerate(
                script["scenes"],
                start=1
            ):

                with st.expander(
                    f"Scene {index}: {scene['title']}"
                ):

                    st.write(
                        "**Visual:**",
                        scene["visual"]
                    )

                    st.write(
                        "**Camera:**",
                        scene["camera"]
                    )

                    st.write(
                        "**Narration:**",
                        scene["narration"]
                    )

                    st.write(
                        "**Dialogue:**",
                        scene["dialogue"]
                    )

                    st.write(
                        "**Duration:**",
                        scene["duration"],
                        "seconds"
                    )

                    if st.button(
                        "Delete Scene",
                        key=f"delete_scene_{scene['id']}"
                    ):

                        delete_scene(
                            selected_id,
                            scene["id"]
                        )

                        st.success("Scene deleted.")
                        st.rerun()

    # -----------------------------------------------------
    # TEMPLATES
    # -----------------------------------------------------

    with tabs[3]:

        st.subheader("Script Templates")

        template_type = st.selectbox(
            "Choose template",
            SCRIPT_TYPES
        )

        template_topic = st.text_input(
            "Enter topic",
            value="AI Future Technology"
        )

        template_tone = st.selectbox(
            "Choose tone",
            TONE_OPTIONS,
            key="template_tone"
        )

        if st.button("Generate Template Preview"):

            template = get_template(
                template_type,
                template_topic,
                template_tone
            )

            st.markdown("**Hook**")
            st.write(template["hook"])

            st.markdown("**Introduction**")
            st.write(template["introduction"])

            st.markdown("**Main Content**")
            st.write(template["main_content"])

            st.markdown("**Call to Action**")
            st.write(template["call_to_action"])

            st.caption(
                "This is a template preview, not AI-generated "
                "or fact-checked content."
            )

        st.divider()

        scripts = get_scripts()

        if scripts:

            selected = st.selectbox(
                "Apply template to existing script",
                {
                    script["title"]: script["id"]
                    for script in scripts
                },
                key="apply_template_script"
            )

            if st.button("Apply Template"):

                try:

                    apply_template(
                        selected,
                        template_type,
                        template_topic,
                        template_tone
                    )

                    st.success("Template applied.")
                    st.rerun()

                except ValueError as error:

                    st.error(str(error))

    # -----------------------------------------------------
    # EXPORT
    # -----------------------------------------------------

    with tabs[4]:

        st.subheader("Export Scripts")

        scripts = get_scripts()

        if not scripts:

            st.info("No scripts available.")

        else:

            selected_script = st.selectbox(
                "Choose script to export",
                {
                    script["title"]: script["id"]
                    for script in scripts
                },
                key="export_script"
            )

            script = get_script(selected_script)

            st.download_button(
                "Download TXT Script",
                data=format_script(script),
                file_name=(
                    safe_filename(script["title"]) + ".txt"
                ),
                mime="text/plain"
            )

            json_data = json.dumps(
                script,
                indent=4,
                ensure_ascii=False
            )

            st.download_button(
                "Download Script JSON",
                data=json_data,
                file_name=(
                    safe_filename(script["title"]) + ".json"
                ),
                mime="application/json"
            )

            st.divider()

            all_scripts = json.dumps(
                load_database(),
                indent=4,
                ensure_ascii=False
            )

            st.download_button(
                "Download All Scripts",
                data=all_scripts,
                file_name="all_scripts.json",
                mime="application/json"
            )

            word_total = (
                count_words(script["hook"])
                + count_words(script["introduction"])
                + count_words(script["main_content"])
                + count_words(script["call_to_action"])
            )

            estimated_duration = estimate_speech_duration(
                script["hook"]
                + " "
                + script["introduction"]
                + " "
                + script["main_content"]
                + " "
                + script["call_to_action"]
            )

            st.metric(
                "Estimated narration duration",
                f"{estimated_duration} seconds"
            )

            st.caption(
                f"Approximate word count: {word_total}. "
                "Actual duration depends on speaking speed."
            )


# =========================================================
# BUILT-IN TESTS
# =========================================================

def run_tests():

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
            DATABASE_FILE = DATA_DIR / "scripts.json"
            OUTPUT_DIR = temp_path / "outputs"

            DATA_DIR.mkdir(
                parents=True,
                exist_ok=True
            )

            # Database test.
            database = load_database()

            assert database["scripts"] == []

            # Create script.
            script = create_script({
                "title": "AI Future War",
                "topic": "Artificial Intelligence",
                "script_type": "YouTube Shorts",
                "tone": "Sci-Fi",
                "language": "English",
                "target_duration": 60,
                "status": "Draft",
            })

            assert script["title"] == "AI Future War"

            # Retrieve script.
            assert get_script(script["id"]) is not None

            # Template test.
            template = get_template(
                "YouTube Shorts",
                "AI Future"
            )

            assert template["hook"]
            assert template["introduction"]

            # Apply template.
            updated = apply_template(
                script["id"],
                "YouTube Shorts",
                "AI Future"
            )

            assert updated["hook"]

            # Add scene.
            scene = add_scene(
                script["id"],
                {
                    "title": "Opening Scene",
                    "visual": "A futuristic city.",
                    "camera": "Wide cinematic shot.",
                    "narration": "The future is here.",
                    "dialogue": "Welcome to the future.",
                    "duration": 10,
                }
            )

            assert len(
                get_script(script["id"])["scenes"]
            ) == 1

            # Update scene.
            updated_scene = update_scene(
                script["id"],
                scene["id"],
                {
                    "title": "Updated Opening"
                }
            )

            assert updated_scene["title"] == "Updated Opening"

            # Statistics.
            stats = get_script_statistics()

            assert stats["total_scripts"] == 1
            assert stats["total_scenes"] == 1

            # Search.
            results = search_scripts("AI Future")

            assert len(results) == 1

            # Script formatting.
            formatted = format_script(
                get_script(script["id"])
            )

            assert "AI FUTURE WAR" in formatted

            # Word count.
            assert count_words("Hello world") == 2

            # Duration.
            assert estimate_speech_duration(
                "one two three four"
            ) > 0

            # Export.
            txt_file = export_script_txt(
                script["id"]
            )

            json_file = export_all_json()

            assert txt_file.exists()
            assert json_file.exists()

            # Delete scene.
            assert delete_scene(
                script["id"],
                scene["id"]
            )

            # Delete script.
            assert delete_script(script["id"])

            assert get_scripts() == []

            print("All script writer tests passed.")

    finally:

        DATA_DIR = original_data_dir
        DATABASE_FILE = original_database_file
        OUTPUT_DIR = original_output_dir


# =========================================================
# COMMAND LINE
# =========================================================

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="AI Influencer Studio Script Writer"
    )

    parser.add_argument(
        "--test",
        action="store_true"
    )

    args = parser.parse_args()

    if args.test:

        run_tests()

    else:

        print(
            "Run the application using: "
            "streamlit run app.py"
        )
