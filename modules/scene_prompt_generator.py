
"""
AI Influencer Studio
File 55: modules/scene_prompt_generator.py

Local scene prompt generator.

Features:
- Generate image and video prompts from storyboard scenes
- Visual style, lighting, composition and camera controls
- Character consistency instructions
- Negative prompt generation
- Prompt variations
- Save and manage prompt collections
- TXT and JSON exports
- Optional storyboard_manager integration
- Built-in tests

No external AI API is used. Prompts are assembled locally from
scene information and user-selected settings.

Run:
    streamlit run app.py

Test:
    python -m modules.scene_prompt_generator --test
"""

from __future__ import annotations

import argparse
import json
import re
import tempfile
import unittest

from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs" / "scene_prompts"

DATA_FILE = DATA_DIR / "scene_prompts.json"


# ---------------------------------------------------------
# PROMPT PRESETS
# ---------------------------------------------------------

VISUAL_STYLES = {
    "Cinematic Realism": (
        "photorealistic cinematic visuals, realistic materials, "
        "natural proportions, detailed environments"
    ),
    "Hollywood 3D Animation": (
        "high-quality cinematic 3D animation, detailed character "
        "models, realistic textures, expressive visual storytelling"
    ),
    "Anime": (
        "high-quality anime illustration, detailed backgrounds, "
        "expressive character design, cinematic composition"
    ),
    "Fantasy": (
        "epic fantasy visual design, atmospheric environments, "
        "magical details, dramatic cinematic presentation"
    ),
    "Sci-Fi": (
        "futuristic science-fiction environment, advanced technology, "
        "cinematic lighting, detailed futuristic materials"
    ),
    "Documentary": (
        "documentary visual style, natural lighting, realistic "
        "environment, authentic composition"
    ),
    "Fashion Editorial": (
        "premium fashion editorial photography, sophisticated "
        "composition, refined lighting, professional styling"
    ),
    "Custom": "",
}

LIGHTING_STYLES = [
    "Natural daylight",
    "Golden hour",
    "Soft studio lighting",
    "Dramatic cinematic lighting",
    "Low-key lighting",
    "Neon lighting",
    "Moonlight",
    "Volumetric lighting",
    "Backlighting",
    "Custom",
]

CAMERA_SHOTS = [
    "Wide establishing shot",
    "Medium shot",
    "Close-up",
    "Extreme close-up",
    "Over-the-shoulder shot",
    "Tracking shot",
    "Aerial shot",
    "POV shot",
    "Full-body shot",
    "Custom",
]

CAMERA_MOVEMENTS = [
    "Static camera",
    "Slow push-in",
    "Slow pull-back",
    "Pan left",
    "Pan right",
    "Tilt up",
    "Tilt down",
    "Smooth tracking movement",
    "Orbit around subject",
    "Crane movement",
    "Handheld cinematic movement",
    "Custom",
]

COMPOSITIONS = [
    "Centered composition",
    "Rule of thirds",
    "Symmetrical composition",
    "Foreground framing",
    "Deep cinematic composition",
    "Wide environmental composition",
    "Close character-focused composition",
    "Custom",
]

DEFAULT_NEGATIVE_PROMPT = (
    "low quality, blurry, pixelated, distorted anatomy, "
    "extra fingers, missing fingers, extra limbs, malformed hands, "
    "deformed face, inconsistent character appearance, "
    "duplicate subjects, unnatural proportions, text, watermark, "
    "logo, compression artifacts, oversaturated colors"
)


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def make_id(prefix: str = "prompt") -> str:
    return (
        prefix + "_"
        + datetime.now().strftime("%Y%m%d%H%M%S%f")
    )


def clean_text(value: Any, limit: int = 12000) -> str:
    if value is None:
        return ""
    return str(value).strip()[:limit]


def safe_filename(value: str) -> str:
    value = clean_text(value, 120)
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
    value = re.sub(r"\s+", "_", value)
    return value.strip("._") or "scene_prompt"


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_database(path: Path | None = None) -> dict:
    source = path or DATA_FILE

    if not source.exists():
        return {"prompts": []}

    try:
        with source.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            return {"prompts": []}

        prompts = data.get("prompts", [])

        if not isinstance(prompts, list):
            prompts = []

        return {"prompts": prompts}

    except (OSError, json.JSONDecodeError):
        return {"prompts": []}


def save_database(
    data: dict,
    path: Path | None = None,
) -> None:
    destination = path or DATA_FILE
    destination.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "prompts": data.get("prompts", [])
    }

    temporary = destination.with_suffix(
        destination.suffix + ".tmp"
    )

    with temporary.open("w", encoding="utf-8") as file:
        json.dump(
            payload,
            file,
            indent=2,
            ensure_ascii=False,
        )

    temporary.replace(destination)


# ---------------------------------------------------------
# PROMPT GENERATION
# ---------------------------------------------------------

def resolve_style(
    visual_style: str,
    custom_style: str = "",
) -> str:
    """Return a style description."""

    if visual_style == "Custom":
        return clean_text(custom_style)

    return VISUAL_STYLES.get(
        visual_style,
        VISUAL_STYLES["Cinematic Realism"],
    )


def resolve_option(
    selected: str,
    custom_value: str = "",
) -> str:
    """Resolve a custom or predefined option."""

    if selected == "Custom":
        return clean_text(custom_value)

    return clean_text(selected)


def build_character_consistency(
    character_name: str = "",
    appearance: str = "",
    consistency_notes: str = "",
) -> str:
    """Build character identity instructions."""

    parts = []

    if clean_text(character_name):
        parts.append(
            f"Character identity: {clean_text(character_name)}."
        )

    if clean_text(appearance):
        parts.append(
            "Preserve the following character appearance exactly: "
            + clean_text(appearance)
            + "."
        )

    if clean_text(consistency_notes):
        parts.append(
            "Continuity instructions: "
            + clean_text(consistency_notes)
            + "."
        )

    return " ".join(parts)


def generate_prompt(
    scene_title: str,
    visual_description: str,
    visual_style: str = "Cinematic Realism",
    custom_style: str = "",
    lighting: str = "Dramatic cinematic lighting",
    custom_lighting: str = "",
    camera_shot: str = "Wide establishing shot",
    custom_camera_shot: str = "",
    composition: str = "Rule of thirds",
    custom_composition: str = "",
    character_name: str = "",
    character_appearance: str = "",
    consistency_notes: str = "",
    environment: str = "",
    mood: str = "",
    color_palette: str = "",
    additional_details: str = "",
) -> str:
    """Generate a structured image prompt."""

    description = clean_text(visual_description)

    if not description:
        raise ValueError("Visual description is required.")

    style = resolve_style(visual_style, custom_style)

    lighting_text = resolve_option(
        lighting,
        custom_lighting,
    )

    shot_text = resolve_option(
        camera_shot,
        custom_camera_shot,
    )

    composition_text = resolve_option(
        composition,
        custom_composition,
    )

    character_text = build_character_consistency(
        character_name,
        character_appearance,
        consistency_notes,
    )

    sections = []

    if clean_text(scene_title):
        sections.append(
            f"Scene: {clean_text(scene_title)}."
        )

    sections.append(
        "Visual description: " + description
    )

    if style:
        sections.append("Visual style: " + style)

    if clean_text(environment):
        sections.append(
            "Environment: " + clean_text(environment)
        )

    if character_text:
        sections.append(character_text)

    if lighting_text:
        sections.append(
            "Lighting: " + lighting_text
        )

    if shot_text:
        sections.append(
            "Camera framing: " + shot_text
        )

    if composition_text:
        sections.append(
            "Composition: " + composition_text
        )

    if clean_text(mood):
        sections.append(
            "Emotional atmosphere: " + clean_text(mood)
        )

    if clean_text(color_palette):
        sections.append(
            "Color palette: " + clean_text(color_palette)
        )

    if clean_text(additional_details):
        sections.append(
            "Additional visual details: "
            + clean_text(additional_details)
        )

    sections.append(
        "Maintain coherent anatomy, realistic spatial "
        "relationships, clear subject focus and consistent "
        "visual continuity."
    )

    return "\n\n".join(sections)


def generate_video_prompt(
    image_prompt: str,
    duration: int = 8,
    camera_movement: str = "Slow push-in",
    custom_camera_movement: str = "",
    action: str = "",
    motion_intensity: str = "Natural",
    fps: int = 24,
    additional_motion: str = "",
) -> str:
    """Create a video motion prompt from an image prompt."""

    image_prompt = clean_text(image_prompt)

    if not image_prompt:
        raise ValueError("An image prompt is required.")

    duration = max(1, min(int(duration), 3600))
    fps = max(1, min(int(fps), 120))

    movement = resolve_option(
        camera_movement,
        custom_camera_movement,
    )

    sections = [
        "Visual reference:\n" + image_prompt,
        f"Video duration: {duration} seconds.",
        f"Frame rate target: {fps} FPS.",
        f"Camera movement: {movement}.",
        f"Motion intensity: {clean_text(motion_intensity)}.",
    ]

    if clean_text(action):
        sections.append(
            "Subject action: " + clean_text(action)
        )

    if clean_text(additional_motion):
        sections.append(
            "Additional motion instructions: "
            + clean_text(additional_motion)
        )

    sections.append(
        "Use smooth, coherent motion. Preserve the subject's "
        "identity, clothing, proportions and environment throughout "
        "the clip. Avoid sudden scene changes, flickering and "
        "unintended camera jumps."
    )

    return "\n\n".join(sections)


def generate_negative_prompt(
    extra_terms: str = "",
    include_default: bool = True,
) -> str:
    """Build a negative prompt."""

    parts = []

    if include_default:
        parts.append(DEFAULT_NEGATIVE_PROMPT)

    if clean_text(extra_terms):
        parts.append(clean_text(extra_terms))

    return ", ".join(parts)


def generate_variations(
    base_prompt: str,
    variations: int = 3,
) -> list[str]:
    """
    Create deterministic prompt variations.

    These are wording variations, not AI-generated images.
    """

    base_prompt = clean_text(base_prompt)

    if not base_prompt:
        raise ValueError("Base prompt is required.")

    variations = max(1, min(int(variations), 10))

    additions = [
        "Emphasize cinematic depth and environmental details.",
        "Emphasize subject details and visual storytelling.",
        "Emphasize realistic textures and balanced lighting.",
        "Emphasize dramatic composition and atmosphere.",
        "Emphasize natural proportions and scene continuity.",
        "Emphasize foreground and background separation.",
        "Emphasize refined color grading and visual clarity.",
        "Emphasize detailed environment and spatial depth.",
        "Emphasize subtle lighting and realistic materials.",
        "Emphasize professional cinematic framing.",
    ]

    return [
        base_prompt + "\n\nVariation direction: " + additions[index]
        for index in range(variations)
    ]


# ---------------------------------------------------------
# STORYBOARD INTEGRATION
# ---------------------------------------------------------

def get_storyboard_scenes(
    storyboard_id: str,
) -> list[dict]:
    """
    Read scenes from the optional storyboard_manager module.

    This function does not modify storyboard data.
    """

    try:
        from modules import storyboard_manager

        storyboard = storyboard_manager.get_storyboard(
            storyboard_id
        )

        if not storyboard:
            return []

        return sorted(
            storyboard.get("scenes", []),
            key=lambda item: int(item.get("order", 1)),
        )

    except (ImportError, AttributeError, ValueError, TypeError):
        return []


def prompt_from_storyboard_scene(
    scene: dict,
    **settings: Any,
) -> str:
    """Generate a prompt using a storyboard scene."""

    title = scene.get("title", "Untitled Scene")

    description = scene.get("visual_prompt", "")

    if not clean_text(description):
        description = (
            "Create a cinematic scene for "
            + clean_text(title)
        )

    settings.setdefault(
        "environment",
        scene.get("location", ""),
    )

    settings.setdefault(
        "character_name",
        scene.get("characters", ""),
    )

    return generate_prompt(
        scene_title=title,
        visual_description=description,
        **settings,
    )


# ---------------------------------------------------------
# PROMPT COLLECTION MANAGEMENT
# ---------------------------------------------------------

def save_prompt(
    title: str,
    image_prompt: str,
    negative_prompt: str = "",
    video_prompt: str = "",
    storyboard_id: str = "",
    scene_id: str = "",
    database_path: Path | None = None,
) -> dict:
    """Save a prompt collection locally."""

    title = clean_text(title, 150)

    if not title:
        raise ValueError("Prompt title is required.")

    image_prompt = clean_text(image_prompt)

    if not image_prompt:
        raise ValueError("Image prompt is required.")

    data = load_database(database_path)

    item = {
        "id": make_id(),
        "title": title,
        "image_prompt": image_prompt,
        "negative_prompt": clean_text(negative_prompt),
        "video_prompt": clean_text(video_prompt),
        "storyboard_id": clean_text(storyboard_id),
        "scene_id": clean_text(scene_id),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }

    data["prompts"].append(item)
    save_database(data, database_path)

    return item


def get_prompts(
    database_path: Path | None = None,
) -> list[dict]:
    return load_database(database_path)["prompts"]


def delete_prompt(
    prompt_id: str,
    database_path: Path | None = None,
) -> bool:
    data = load_database(database_path)

    original_count = len(data["prompts"])

    data["prompts"] = [
        item
        for item in data["prompts"]
        if item.get("id") != prompt_id
    ]

    if len(data["prompts"]) == original_count:
        return False

    save_database(data, database_path)
    return True


def search_prompts(
    query: str,
    database_path: Path | None = None,
) -> list[dict]:
    query = clean_text(query).lower()

    if not query:
        return get_prompts(database_path)

    results = []

    for item in get_prompts(database_path):
        searchable = " ".join([
            item.get("title", ""),
            item.get("image_prompt", ""),
            item.get("negative_prompt", ""),
            item.get("video_prompt", ""),
        ]).lower()

        if query in searchable:
            results.append(item)

    return results


# ---------------------------------------------------------
# EXPORTS
# ---------------------------------------------------------

def export_prompt_json(item: dict) -> str:
    return json.dumps(
        item,
        indent=2,
        ensure_ascii=False,
    )


def export_prompt_text(item: dict) -> str:
    return "\n\n".join([
        "TITLE\n" + item.get("title", ""),
        "IMAGE PROMPT\n" + item.get("image_prompt", ""),
        "NEGATIVE PROMPT\n" + item.get("negative_prompt", ""),
        "VIDEO PROMPT\n" + item.get("video_prompt", ""),
    ])


def save_prompt_export(
    item: dict,
    file_format: str = "txt",
) -> Path:
    ensure_directories()

    file_format = file_format.lower()
    title = safe_filename(item.get("title", "prompt"))

    if file_format == "txt":
        content = export_prompt_text(item)
        extension = ".txt"
    elif file_format == "json":
        content = export_prompt_json(item)
        extension = ".json"
    else:
        raise ValueError("Format must be txt or json.")

    destination = OUTPUT_DIR / f"{title}{extension}"

    destination.write_text(
        content,
        encoding="utf-8",
    )

    return destination


# ---------------------------------------------------------
# STREAMLIT UI
# ---------------------------------------------------------

def render() -> None:
    try:
        import streamlit as st
    except ImportError as exc:
        raise RuntimeError(
            "Install Streamlit using: pip install streamlit"
        ) from exc

    ensure_directories()

    st.title("✨ Scene Prompt Generator")
    st.caption(
        "Build structured image and video prompts from your "
        "storyboard scenes. Runs locally without AI API calls."
    )

    tab_generate, tab_saved = st.tabs([
        "Generate Prompts",
        "Saved Prompts",
    ])

    with tab_generate:
        st.subheader("Scene information")

        storyboard_id = ""
        scene_id = ""
        scene_data = {}

        # Optional storyboard selector
        try:
            from modules import storyboard_manager

            storyboards = storyboard_manager.get_storyboards()

        except (ImportError, AttributeError):
            storyboards = []

        if storyboards:
            use_storyboard = st.checkbox(
                "Import a scene from Storyboard Manager"
            )

            if use_storyboard:
                storyboard_map = {
                    item["id"]: item["title"]
                    for item in storyboards
                }

                storyboard_id = st.selectbox(
                    "Storyboard",
                    list(storyboard_map.keys()),
                    format_func=lambda key: storyboard_map[key],
                )

                scenes = get_storyboard_scenes(storyboard_id)

                if scenes:
                    scene_map = {
                        item["id"]: (
                            f"Scene {item.get('order')}: "
                            f"{item.get('title')}"
                        )
                        for item in scenes
                    }

                    scene_id = st.selectbox(
                        "Scene",
                        list(scene_map.keys()),
                        format_func=lambda key: scene_map[key],
                    )

                    scene_data = next(
                        (
                            item for item in scenes
                            if item["id"] == scene_id
                        ),
                        {},
                    )

                else:
                    st.info("This storyboard has no scenes.")

        default_title = scene_data.get("title", "")
        default_description = scene_data.get("visual_prompt", "")

        scene_title = st.text_input(
            "Scene title",
            value=default_title,
        )

        visual_description = st.text_area(
            "Visual description",
            value=default_description,
            height=150,
            placeholder=(
                "Describe what should appear in the scene..."
            ),
        )

        st.subheader("Visual settings")

        visual_style = st.selectbox(
            "Visual style",
            list(VISUAL_STYLES.keys()),
        )

        custom_style = ""

        if visual_style == "Custom":
            custom_style = st.text_input(
                "Custom visual style"
            )

        lighting = st.selectbox(
            "Lighting",
            LIGHTING_STYLES,
        )

        custom_lighting = ""

        if lighting == "Custom":
            custom_lighting = st.text_input(
                "Custom lighting"
            )

        camera_shot = st.selectbox(
            "Camera shot",
            CAMERA_SHOTS,
        )

        custom_camera_shot = ""

        if camera_shot == "Custom":
            custom_camera_shot = st.text_input(
                "Custom camera shot"
            )

        composition = st.selectbox(
            "Composition",
            COMPOSITIONS,
        )

        custom_composition = ""

        if composition == "Custom":
            custom_composition = st.text_input(
                "Custom composition"
            )

        st.subheader("Character consistency")

        character_name = st.text_input(
            "Character name",
            value=scene_data.get("characters", ""),
        )

        character_appearance = st.text_area(
            "Character appearance",
            placeholder=(
                "Hair, face, clothing, body proportions, "
                "distinctive features..."
            ),
        )

        consistency_notes = st.text_area(
            "Continuity instructions",
            placeholder=(
                "Keep the same face, outfit, hairstyle, "
                "age and character proportions..."
            ),
        )

        st.subheader("Environment and mood")

        environment = st.text_input(
            "Environment",
            value=scene_data.get("location", ""),
        )

        mood = st.text_input(
            "Mood",
            placeholder="Mysterious, joyful, suspenseful...",
        )

        color_palette = st.text_input(
            "Color palette",
            placeholder="Icy blue, charcoal and silver...",
        )

        additional_details = st.text_area(
            "Additional details",
            placeholder="Any other visual instructions...",
        )

        st.divider()
        st.subheader("Negative prompt")

        include_default_negative = st.checkbox(
            "Include default negative prompt",
            value=True,
        )

        extra_negative = st.text_area(
            "Additional negative terms",
            placeholder="Unwanted visual details...",
        )

        negative_prompt = generate_negative_prompt(
            extra_negative,
            include_default_negative,
        )

        with st.expander("Video prompt settings"):
            create_video = st.checkbox(
                "Also create a video prompt",
                value=True,
            )

            video_duration = st.number_input(
                "Duration (seconds)",
                min_value=1,
                max_value=3600,
                value=safe_int(
                    scene_data.get("duration", 8),
                    8,
                ),
            )

            camera_movement = st.selectbox(
                "Camera movement",
                CAMERA_MOVEMENTS,
            )

            custom_camera_movement = ""

            if camera_movement == "Custom":
                custom_camera_movement = st.text_input(
                    "Custom camera movement"
                )

            motion_intensity = st.selectbox(
                "Motion intensity",
                ["Subtle", "Natural", "Dynamic", "High"],
                index=1,
            )

            fps = st.selectbox(
                "Target FPS",
                [24, 25, 30, 50, 60],
                index=0,
            )

            action = st.text_area(
                "Subject action",
                placeholder=(
                    "Character slowly walks toward the camera..."
                ),
            )

            additional_motion = st.text_area(
                "Additional motion instructions"
            )

        generate = st.button(
            "Generate Scene Prompts",
            type="primary",
            use_container_width=True,
        )

        if generate:
            try:
                image_prompt = generate_prompt(
                    scene_title=scene_title,
                    visual_description=visual_description,
                    visual_style=visual_style,
                    custom_style=custom_style,
                    lighting=lighting,
                    custom_lighting=custom_lighting,
                    camera_shot=camera_shot,
                    custom_camera_shot=custom_camera_shot,
                    composition=composition,
                    custom_composition=custom_composition,
                    character_name=character_name,
                    character_appearance=character_appearance,
                    consistency_notes=consistency_notes,
                    environment=environment,
                    mood=mood,
                    color_palette=color_palette,
                    additional_details=additional_details,
                )

                video_prompt = ""

                if create_video:
                    video_prompt = generate_video_prompt(
                        image_prompt=image_prompt,
                        duration=video_duration,
                        camera_movement=camera_movement,
                        custom_camera_movement=custom_camera_movement,
                        action=action,
                        motion_intensity=motion_intensity,
                        fps=fps,
                        additional_motion=additional_motion,
                    )

                st.session_state["scene_prompt_result"] = {
                    "title": scene_title or "Untitled Scene",
                    "image_prompt": image_prompt,
                    "negative_prompt": negative_prompt,
                    "video_prompt": video_prompt,
                    "storyboard_id": storyboard_id,
                    "scene_id": scene_id,
                }

            except ValueError as exc:
                st.error(str(exc))

        result = st.session_state.get("scene_prompt_result")

        if result:
            st.divider()
            st.subheader("Generated prompts")

            st.markdown("**Image prompt**")
            st.code(result["image_prompt"], language="text")

            st.markdown("**Negative prompt**")
            st.code(result["negative_prompt"], language="text")

            if result.get("video_prompt"):
                st.markdown("**Video prompt**")
                st.code(result["video_prompt"], language="text")

            st.download_button(
                "Download prompts as TXT",
                data=export_prompt_text(result),
                file_name=(
                    safe_filename(result["title"]) + ".txt"
                ),
                mime="text/plain",
            )

            st.download_button(
                "Download prompts as JSON",
                data=export_prompt_json(result),
                file_name=(
                    safe_filename(result["title"]) + ".json"
                ),
                mime="application/json",
            )

            if st.button("Save Prompt Collection"):
                saved = save_prompt(
                    title=result["title"],
                    image_prompt=result["image_prompt"],
                    negative_prompt=result["negative_prompt"],
                    video_prompt=result["video_prompt"],
                    storyboard_id=result.get("storyboard_id", ""),
                    scene_id=result.get("scene_id", ""),
                )

                st.success(
                    f"Saved prompt collection: {saved['id']}"
                )

            with st.expander("Create wording variations"):
                variation_count = st.slider(
                    "Number of variations",
                    min_value=1,
                    max_value=10,
                    value=3,
                )

                if st.button("Generate Variations"):
                    variations = generate_variations(
                        result["image_prompt"],
                        variation_count,
                    )

                    for index, variation in enumerate(
                        variations,
                        start=1,
                    ):
                        st.markdown(f"**Variation {index}**")
                        st.code(variation, language="text")

    # -----------------------------------------------------
    # SAVED PROMPTS
    # -----------------------------------------------------

    with tab_saved:
        st.subheader("Saved prompt collections")

        query = st.text_input(
            "Search saved prompts",
            key="saved_prompt_search",
        )

        saved_items = search_prompts(query)

        if not saved_items:
            st.info("No saved prompts found.")

        for item in reversed(saved_items):
            with st.expander(item.get("title", "Untitled")):
                st.caption(
                    "Created: " + item.get("created_at", "")
                )

                st.markdown("**Image prompt**")
                st.code(
                    item.get("image_prompt", ""),
                    language="text",
                )

                st.markdown("**Negative prompt**")
                st.code(
                    item.get("negative_prompt", ""),
                    language="text",
                )

                if item.get("video_prompt"):
                    st.markdown("**Video prompt**")
                    st.code(
                        item.get("video_prompt", ""),
                        language="text",
                    )

                col1, col2 = st.columns(2)

                with col1:
                    st.download_button(
                        "Download TXT",
                        data=export_prompt_text(item),
                        file_name=(
                            safe_filename(item.get("title", "prompt"))
                            + ".txt"
                        ),
                        mime="text/plain",
                        key=f"txt_{item['id']}",
                    )

                with col2:
                    st.download_button(
                        "Download JSON",
                        data=export_prompt_json(item),
                        file_name=(
                            safe_filename(item.get("title", "prompt"))
                            + ".json"
                        ),
                        mime="application/json",
                        key=f"json_{item['id']}",
                    )

                if st.button(
                    "Delete Prompt",
                    key=f"delete_prompt_{item['id']}",
                ):
                    delete_prompt(item["id"])
                    st.success("Prompt deleted.")
                    st.rerun()


# ---------------------------------------------------------
# BUILT-IN TESTS
# ---------------------------------------------------------

class ScenePromptGeneratorTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_file = (
            Path(self.temp_dir.name) / "test_prompts.json"
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_generate_image_prompt(self):
        result = generate_prompt(
            scene_title="Opening Scene",
            visual_description="A woman walking in a snowy forest",
            visual_style="Cinematic Realism",
            character_name="Eira",
            environment="Snowy forest",
        )

        self.assertIn("Opening Scene", result)
        self.assertIn("Eira", result)
        self.assertIn("snowy forest", result.lower())

    def test_empty_description_rejected(self):
        with self.assertRaises(ValueError):
            generate_prompt(
                scene_title="Empty",
                visual_description="",
            )

    def test_custom_style(self):
        result = generate_prompt(
            scene_title="Custom Test",
            visual_description="A futuristic city",
            visual_style="Custom",
            custom_style="Retro futuristic concept art",
        )

        self.assertIn("Retro futuristic concept art", result)

    def test_video_prompt(self):
        result = generate_video_prompt(
            image_prompt="A character standing in a city",
            duration=10,
            camera_movement="Slow push-in",
            action="The character walks forward",
        )

        self.assertIn("10 seconds", result)
        self.assertIn("Slow push-in", result)
        self.assertIn("walks forward", result)

    def test_negative_prompt(self):
        result = generate_negative_prompt(
            "bad lighting",
            include_default=True,
        )

        self.assertIn("blurry", result)
        self.assertIn("bad lighting", result)

    def test_variations(self):
        results = generate_variations(
            "A cinematic character portrait",
            3,
        )

        self.assertEqual(len(results), 3)
        self.assertIn("Variation direction", results[0])

    def test_save_and_search_prompt(self):
        item = save_prompt(
            title="Test Character",
            image_prompt="A cinematic portrait",
            negative_prompt="blurry",
            database_path=self.test_file,
        )

        results = search_prompts(
            "cinematic",
            self.test_file,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], item["id"])

    def test_delete_prompt(self):
        item = save_prompt(
            title="Delete Test",
            image_prompt="A test image",
            database_path=self.test_file,
        )

        result = delete_prompt(
            item["id"],
            self.test_file,
        )

        self.assertTrue(result)
        self.assertEqual(
            len(get_prompts(self.test_file)),
            0,
        )

    def test_export(self):
        item = {
            "title": "Export Test",
            "image_prompt": "A mountain landscape",
            "negative_prompt": "blurry",
            "video_prompt": "Slow camera movement",
        }

        text = export_prompt_text(item)
        json_text = export_prompt_json(item)

        self.assertIn("mountain landscape", text)
        self.assertIn("Export Test", json_text)

    def test_invalid_export_format(self):
        with self.assertRaises(ValueError):
            save_prompt_export(
                {"title": "Test"},
                "pdf",
            )


# ---------------------------------------------------------
# CLI
# ---------------------------------------------------------

def run_tests() -> bool:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        ScenePromptGeneratorTests
    )

    result = unittest.TextTestRunner(
        verbosity=2
    ).run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Scene Prompt Generator"
    )

    parser.add_argument(
        "--test",
        action="store_true",
        help="Run built-in tests",
    )

    args = parser.parse_args()

    if args.test:
        raise SystemExit(
            0 if run_tests() else 1
        )

    print("Scene Prompt Generator")
    print("Use the module through your Streamlit application.")
