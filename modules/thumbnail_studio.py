
"""
AI Influencer Studio
File 44: modules/thumbnail_studio.py

Features:
- YouTube thumbnail (1280x720) and Shorts cover (1080x1920)
- Background image upload and smart crop
- Title and subtitle text overlays
- Text outline, shadow, alignment and positioning
- Optional transparent logo overlay
- Cinematic, Horror, Fantasy, Tech, News and Minimal presets
- PNG/JPG export
- Persistent thumbnail project metadata
- Built-in tests

Run:
    python -m modules.thumbnail_studio --test

Streamlit integration:
    from modules import thumbnail_studio
    pages["Thumbnail Studio"] = thumbnail_studio.render
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from PIL import (
        Image,
        ImageDraw,
        ImageEnhance,
        ImageFilter,
        ImageFont,
        ImageOps,
    )
except ImportError:
    Image = None
    ImageDraw = None
    ImageEnhance = None
    ImageFilter = None
    ImageFont = None
    ImageOps = None


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs" / "thumbnails"
PROJECTS_FILE = DATA_DIR / "thumbnail_projects.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


PRESETS: dict[str, dict[str, Any]] = {
    "Cinematic": {
        "overlay": 105,
        "brightness": 0.88,
        "contrast": 1.18,
        "saturation": 1.12,
        "title_color": "#FFFFFF",
        "outline_color": "#111111",
        "accent_color": "#F5B642",
        "title_position": "bottom",
        "font_size": 82,
    },
    "Horror": {
        "overlay": 125,
        "brightness": 0.72,
        "contrast": 1.35,
        "saturation": 0.78,
        "title_color": "#FFFFFF",
        "outline_color": "#550000",
        "accent_color": "#E52B2B",
        "title_position": "bottom",
        "font_size": 88,
    },
    "Fantasy": {
        "overlay": 95,
        "brightness": 0.92,
        "contrast": 1.20,
        "saturation": 1.28,
        "title_color": "#FFFFFF",
        "outline_color": "#101B38",
        "accent_color": "#7DDCFF",
        "title_position": "bottom",
        "font_size": 82,
    },
    "Tech": {
        "overlay": 105,
        "brightness": 0.90,
        "contrast": 1.25,
        "saturation": 1.10,
        "title_color": "#FFFFFF",
        "outline_color": "#071B35",
        "accent_color": "#00D9FF",
        "title_position": "bottom",
        "font_size": 78,
    },
    "Breaking News": {
        "overlay": 115,
        "brightness": 0.90,
        "contrast": 1.25,
        "saturation": 1.05,
        "title_color": "#FFFFFF",
        "outline_color": "#181818",
        "accent_color": "#FF2525",
        "title_position": "bottom",
        "font_size": 78,
    },
    "Minimal": {
        "overlay": 65,
        "brightness": 1.0,
        "contrast": 1.05,
        "saturation": 1.0,
        "title_color": "#FFFFFF",
        "outline_color": "#222222",
        "accent_color": "#FFFFFF",
        "title_position": "bottom",
        "font_size": 72,
    },
}


DEFAULT_SETTINGS: dict[str, Any] = {
    "format": "YouTube Thumbnail",
    "width": 1280,
    "height": 720,
    "preset": "Cinematic",
    "title": "YOUR VIDEO TITLE",
    "subtitle": "",
    "accent_label": "",
    "font_size": 82,
    "title_color": "#FFFFFF",
    "outline_color": "#111111",
    "accent_color": "#F5B642",
    "outline_width": 4,
    "shadow": True,
    "shadow_blur": 5,
    "overlay_opacity": 105,
    "brightness": 0.88,
    "contrast": 1.18,
    "saturation": 1.12,
    "title_position": "bottom",
    "alignment": "left",
    "margin": 55,
    "logo_position": "top-right",
    "logo_size": 150,
    "jpeg_quality": 95,
}


def require_pillow() -> None:
    if Image is None:
        raise RuntimeError(
            "Pillow is required. Install it with: "
            "python -m pip install Pillow"
        )


def safe_filename(value: str, fallback: str = "thumbnail") -> str:
    """Convert a string into a safe filename."""
    value = re.sub(r"[^\w.-]+", "_", str(value).strip())
    value = value.strip("._")
    return value[:80] or fallback


def load_projects() -> list[dict[str, Any]]:
    """Load saved thumbnail project metadata."""
    if not PROJECTS_FILE.exists():
        return []

    try:
        data = json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_projects(projects: list[dict[str, Any]]) -> None:
    """Save project metadata atomically."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporary = PROJECTS_FILE.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(projects, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    temporary.replace(PROJECTS_FILE)


def register_project(
    name: str,
    output_path: str | Path,
    settings: dict[str, Any],
) -> dict[str, Any]:
    """Register a generated thumbnail in the project history."""
    output = Path(output_path).resolve()

    if not output.exists():
        raise FileNotFoundError(f"Thumbnail output not found: {output}")

    record = {
        "id": str(uuid.uuid4()),
        "name": name.strip() or "Untitled Thumbnail",
        "output_path": str(output),
        "format": settings.get("format", "Custom"),
        "width": settings.get("width"),
        "height": settings.get("height"),
        "preset": settings.get("preset", "Cinematic"),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "settings": settings.copy(),
    }

    projects = load_projects()
    projects.insert(0, record)
    save_projects(projects)

    return record


def validate_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize thumbnail settings."""
    result = DEFAULT_SETTINGS.copy()
    result.update(settings or {})

    result["width"] = int(result["width"])
    result["height"] = int(result["height"])

    if not 64 <= result["width"] <= 4096:
        raise ValueError("Width must be between 64 and 4096 pixels.")

    if not 64 <= result["height"] <= 4096:
        raise ValueError("Height must be between 64 and 4096 pixels.")

    result["font_size"] = max(10, min(400, int(result["font_size"])))
    result["outline_width"] = max(
        0, min(30, int(result["outline_width"]))
    )
    result["margin"] = max(0, min(500, int(result["margin"])))
    result["overlay_opacity"] = max(
        0, min(230, int(result["overlay_opacity"]))
    )
    result["shadow_blur"] = max(
        0, min(30, int(result["shadow_blur"]))
    )
    result["logo_size"] = max(20, min(1000, int(result["logo_size"])))
    result["jpeg_quality"] = max(
        50, min(100, int(result["jpeg_quality"]))
    )

    for key in ("brightness", "contrast", "saturation"):
        result[key] = max(0.1, min(2.5, float(result[key])))

    if result["preset"] not in PRESETS:
        result["preset"] = "Cinematic"

    if result["alignment"] not in ("left", "center", "right"):
        result["alignment"] = "left"

    if result["title_position"] not in ("top", "center", "bottom"):
        result["title_position"] = "bottom"

    if result["logo_position"] not in (
        "top-left",
        "top-right",
        "bottom-left",
        "bottom-right",
    ):
        result["logo_position"] = "top-right"

    return result


def open_image(source: bytes | str | Path) -> Image.Image:
    """Open an image from bytes or a filesystem path."""
    require_pillow()

    if isinstance(source, bytes):
        image = Image.open(io.BytesIO(source))
    else:
        image = Image.open(source)

    return ImageOps.exif_transpose(image).convert("RGBA")


def find_windows_font() -> str | None:
    """Find a commonly available Windows font."""
    candidates = [
        Path(os.environ.get("WINDIR", r"C:\Windows"))
        / "Fonts"
        / "impact.ttf",
        Path(os.environ.get("WINDIR", r"C:\Windows"))
        / "Fonts"
        / "arialbd.ttf",
        Path(os.environ.get("WINDIR", r"C:\Windows"))
        / "Fonts"
        / "segoeuib.ttf",
    ]

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    return None


def load_font(font_size: int, font_path: str | None = None):
    """Load a font, falling back to Pillow's built-in font."""
    require_pillow()

    candidates = []

    if font_path:
        candidates.append(Path(font_path))

    windows_font = find_windows_font()
    if windows_font:
        candidates.append(Path(windows_font))

    for candidate in candidates:
        try:
            if candidate.exists():
                return ImageFont.truetype(str(candidate), font_size)
        except OSError:
            continue

    return ImageFont.load_default()


def wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font,
    max_width: int,
) -> list[str]:
    """Wrap text into lines that fit the available width."""
    words = str(text).split()

    if not words:
        return []

    lines = []
    current = words[0]

    for word in words[1:]:
        candidate = f"{current} {word}"
        box = draw.textbbox((0, 0), candidate, font=font)

        if box[2] - box[0] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word

    lines.append(current)
    return lines


def apply_image_adjustments(
    image: Image.Image,
    settings: dict[str, Any],
) -> Image.Image:
    """Apply brightness, contrast and saturation."""
    require_pillow()

    rgb = image.convert("RGB")

    rgb = ImageEnhance.Brightness(rgb).enhance(
        settings["brightness"]
    )
    rgb = ImageEnhance.Contrast(rgb).enhance(
        settings["contrast"]
    )
    rgb = ImageEnhance.Color(rgb).enhance(
        settings["saturation"]
    )

    return rgb.convert("RGBA")


def add_bottom_overlay(
    image: Image.Image,
    opacity: int,
    position: str = "bottom",
) -> Image.Image:
    """Add a soft dark gradient to improve text readability."""
    require_pillow()

    if opacity <= 0:
        return image

    width, height = image.size
    gradient = Image.new("RGBA", (1, height), (0, 0, 0, 0))
    pixels = []

    for y in range(height):
        if position == "top":
            progress = 1.0 - (y / max(1, height - 1))
        elif position == "center":
            distance = abs((y / max(1, height - 1)) - 0.5)
            progress = max(0.0, 1.0 - distance * 2.5)
        else:
            progress = y / max(1, height - 1)

        alpha = int(opacity * (progress ** 1.5))
        pixels.append((0, 0, 0, alpha))

    gradient.putdata(pixels)
    gradient = gradient.resize((width, height))
    return Image.alpha_composite(image.convert("RGBA"), gradient)


def draw_text_block(
    image: Image.Image,
    text: str,
    font,
    color: str,
    outline_color: str,
    outline_width: int,
    shadow: bool,
    shadow_blur: int,
    alignment: str,
    position: str,
    margin: int,
    max_width: int | None = None,
    vertical_offset: int = 0,
) -> Image.Image:
    """Draw wrapped text with optional outline and shadow."""
    require_pillow()

    if not text.strip():
        return image

    width, height = image.size
    max_width = max_width or (width - margin * 2)

    draw = ImageDraw.Draw(image)
    lines = wrap_text(draw, text, font, max_width)

    line_boxes = [
        draw.textbbox((0, 0), line, font=font, stroke_width=outline_width)
        for line in lines
    ]

    line_heights = [
        max(1, box[3] - box[1]) for box in line_boxes
    ]

    line_spacing = max(5, int(font.size * 0.16))
    total_height = sum(line_heights) + line_spacing * max(0, len(lines) - 1)

    if position == "top":
        y = margin + vertical_offset
    elif position == "center":
        y = (height - total_height) // 2 + vertical_offset
    else:
        y = height - total_height - margin + vertical_offset

    y = max(margin, min(y, height - total_height - margin))

    shadow_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_layer)
    main_draw = ImageDraw.Draw(image)

    for line, line_height in zip(lines, line_heights):
        text_box = main_draw.textbbox(
            (0, 0),
            line,
            font=font,
            stroke_width=outline_width,
        )
        text_width = text_box[2] - text_box[0]

        if alignment == "center":
            x = (width - text_width) // 2
        elif alignment == "right":
            x = width - margin - text_width
        else:
            x = margin

        if shadow:
            shadow_draw.text(
                (x + 4, y + 5),
                line,
                font=font,
                fill=(0, 0, 0, 220),
                stroke_width=outline_width,
                stroke_fill=(0, 0, 0, 220),
            )

        main_draw.text(
            (x, y),
            line,
            font=font,
            fill=color,
            stroke_width=outline_width,
            stroke_fill=outline_color,
        )

        y += line_height + line_spacing

    if shadow:
        if shadow_blur:
            shadow_layer = shadow_layer.filter(
                ImageFilter.GaussianBlur(shadow_blur)
            )
        image = Image.alpha_composite(image, shadow_layer)

        # Redraw the main text after the shadow layer.
        main_draw = ImageDraw.Draw(image)
        y = max(
            margin,
            min(
                (
                    margin + vertical_offset
                    if position == "top"
                    else (
                        (height - total_height) // 2 + vertical_offset
                        if position == "center"
                        else height - total_height - margin + vertical_offset
                    )
                ),
                height - total_height - margin,
            ),
        )

        for line, line_height in zip(lines, line_heights):
            text_box = main_draw.textbbox(
                (0, 0),
                line,
                font=font,
                stroke_width=outline_width,
            )
            text_width = text_box[2] - text_box[0]

            if alignment == "center":
                x = (width - text_width) // 2
            elif alignment == "right":
                x = width - margin - text_width
            else:
                x = margin

            main_draw.text(
                (x, y),
                line,
                font=font,
                fill=color,
                stroke_width=outline_width,
                stroke_fill=outline_color,
            )
            y += line_height + line_spacing

    return image


def add_accent_label(
    image: Image.Image,
    label: str,
    accent_color: str,
    font,
    margin: int,
) -> Image.Image:
    """Draw a small colored label near the top-left."""
    if not label.strip():
        return image

    draw = ImageDraw.Draw(image)
    width, height = image.size

    x = margin
    y = margin
    padding_x = max(12, font.size // 4)
    padding_y = max(8, font.size // 8)

    box = draw.textbbox((0, 0), label, font=font)
    text_width = box[2] - box[0]
    text_height = box[3] - box[1]

    rect = (
        x,
        y,
        min(width - margin, x + text_width + padding_x * 2),
        min(height - margin, y + text_height + padding_y * 2),
    )

    draw.rounded_rectangle(
        rect,
        radius=max(4, font.size // 5),
        fill=accent_color,
    )

    draw.text(
        (x + padding_x, y + padding_y),
        label,
        font=font,
        fill="#FFFFFF",
    )

    return image


def add_logo(
    image: Image.Image,
    logo_source: bytes | str | Path,
    position: str,
    max_size: int,
    margin: int,
) -> Image.Image:
    """Add a transparent logo while preserving its aspect ratio."""
    require_pillow()

    logo = open_image(logo_source)
    logo.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

    width, height = image.size
    logo_width, logo_height = logo.size

    if position == "top-left":
        x, y = margin, margin
    elif position == "top-right":
        x, y = width - logo_width - margin, margin
    elif position == "bottom-left":
        x, y = margin, height - logo_height - margin
    else:
        x, y = width - logo_width - margin, height - logo_height - margin

    x = max(0, min(x, width - logo_width))
    y = max(0, min(y, height - logo_height))

    image.alpha_composite(logo, (x, y))
    return image


def create_thumbnail(
    background_source: bytes | str | Path,
    settings: dict[str, Any] | None = None,
    logo_source: bytes | str | Path | None = None,
    font_path: str | None = None,
) -> Image.Image:
    """
    Generate a thumbnail and return a Pillow image.

    background_source:
        Image bytes or a local image path.

    settings:
        Optional thumbnail configuration.

    logo_source:
        Optional transparent PNG or other supported image.
    """
    require_pillow()

    config = validate_settings(settings or {})
    width = config["width"]
    height = config["height"]

    background = open_image(background_source)

    # Fill the requested canvas while preserving the image aspect ratio.
    background = ImageOps.fit(
        background,
        (width, height),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )

    background = apply_image_adjustments(background, config)

    background = add_bottom_overlay(
        background,
        config["overlay_opacity"],
        config["title_position"],
    )

    title_font = load_font(config["font_size"], font_path)
    subtitle_font = load_font(
        max(12, int(config["font_size"] * 0.36)),
        font_path,
    )
    label_font = load_font(
        max(12, int(config["font_size"] * 0.25)),
        font_path,
    )

    # Draw the main title.
    background = draw_text_block(
        background,
        config["title"],
        title_font,
        config["title_color"],
        config["outline_color"],
        config["outline_width"],
        config["shadow"],
        config["shadow_blur"],
        config["alignment"],
        config["title_position"],
        config["margin"],
        vertical_offset=0,
    )

    # Draw subtitle below the title area.
    if config["subtitle"].strip():
        subtitle_position = (
            "bottom"
            if config["title_position"] == "bottom"
            else "top"
        )

        subtitle_offset = (
            int(config["font_size"] * 1.8)
            if config["title_position"] == "bottom"
            else int(config["font_size"] * 1.8)
        )

        background = draw_text_block(
            background,
            config["subtitle"],
            subtitle_font,
            config["title_color"],
            config["outline_color"],
            max(1, config["outline_width"] // 2),
            config["shadow"],
            max(0, config["shadow_blur"] // 2),
            config["alignment"],
            subtitle_position,
            config["margin"],
            vertical_offset=(
                -subtitle_offset
                if subtitle_position == "bottom"
                else subtitle_offset
            ),
        )

    background = add_accent_label(
        background,
        config["accent_label"],
        config["accent_color"],
        label_font,
        config["margin"],
    )

    if logo_source:
        background = add_logo(
            background,
            logo_source,
            config["logo_position"],
            config["logo_size"],
            config["margin"],
        )

    return background.convert("RGB")


def export_thumbnail(
    image: Image.Image,
    filename: str,
    image_format: str = "PNG",
    quality: int = 95,
) -> Path:
    """Export a generated thumbnail to the output folder."""
    require_pillow()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    image_format = image_format.upper()
    if image_format not in ("PNG", "JPEG", "JPG"):
        raise ValueError("Only PNG and JPG export are supported.")

    extension = "jpg" if image_format in ("JPEG", "JPG") else "png"
    name = safe_filename(Path(filename).stem)
    output_path = OUTPUT_DIR / f"{name}_{uuid.uuid4().hex[:8]}.{extension}"

    if extension == "jpg":
        image.convert("RGB").save(
            output_path,
            format="JPEG",
            quality=max(50, min(100, int(quality))),
            optimize=True,
        )
    else:
        image.save(output_path, format="PNG", optimize=True)

    return output_path


def delete_project(project_id: str) -> bool:
    """Delete a project record. The exported image is kept."""
    projects = load_projects()
    updated = [p for p in projects if p.get("id") != project_id]

    if len(updated) == len(projects):
        return False

    save_projects(updated)
    return True


def render() -> None:
    """Render the Streamlit Thumbnail Studio page."""
    try:
        import streamlit as st
    except ImportError as exc:
        raise RuntimeError(
            "Streamlit is required. Install it with: "
            "python -m pip install streamlit"
        ) from exc

    st.title("🎬 Thumbnail Studio")
    st.caption(
        "Create cinematic YouTube thumbnails and vertical Shorts covers "
        "using local image processing."
    )

    if Image is None:
        st.error(
            "Pillow is not installed. Run: "
            "`python -m pip install Pillow`"
        )
        return

    format_choice = st.selectbox(
        "Thumbnail format",
        ["YouTube Thumbnail", "YouTube Shorts Cover", "Custom"],
    )

    if format_choice == "YouTube Thumbnail":
        width, height = 1280, 720
    elif format_choice == "YouTube Shorts Cover":
        width, height = 1080, 1920
    else:
        custom_col1, custom_col2 = st.columns(2)
        with custom_col1:
            width = st.number_input(
                "Width",
                min_value=64,
                max_value=4096,
                value=1280,
                step=16,
            )
        with custom_col2:
            height = st.number_input(
                "Height",
                min_value=64,
                max_value=4096,
                value=720,
                step=16,
            )

    background_upload = st.file_uploader(
        "Upload background image",
        type=["png", "jpg", "jpeg", "webp"],
        key="thumbnail_background",
    )

    if not background_upload:
        st.info("Upload a background image to begin.")
        st.markdown("### Example thumbnail styles")
        st.write(
            "- Cinematic: dramatic movie-style presentation\n"
            "- Horror: dark, high-contrast visuals\n"
            "- Fantasy: vivid fantasy colors\n"
            "- Tech: modern technology and AI visuals\n"
            "- Breaking News: bold news presentation\n"
            "- Minimal: clean text-focused design"
        )
        return

    left, right = st.columns([1, 1])

    with left:
        project_name = st.text_input(
            "Project name",
            value="My Thumbnail",
        )

        preset = st.selectbox(
            "Design preset",
            list(PRESETS.keys()),
        )

        preset_settings = PRESETS[preset]

        title = st.text_area(
            "Main title",
            value="YOUR VIDEO TITLE",
            height=90,
        )

        subtitle = st.text_input("Subtitle", value="")
        accent_label = st.text_input(
            "Small accent label",
            value="",
            help="Example: NEW VIDEO, AI FUTURE, EPISODE 01",
        )

        st.markdown("#### Text design")

        font_size = st.slider(
            "Title font size",
            20,
            180,
            int(preset_settings["font_size"]),
        )

        title_color = st.color_picker(
            "Title color",
            preset_settings["title_color"],
        )

        outline_color = st.color_picker(
            "Outline color",
            preset_settings["outline_color"],
        )

        accent_color = st.color_picker(
            "Accent color",
            preset_settings["accent_color"],
        )

        outline_width = st.slider(
            "Outline thickness",
            0,
            15,
            4,
        )

        alignment = st.selectbox(
            "Text alignment",
            ["left", "center", "right"],
        )

        title_position = st.selectbox(
            "Title position",
            ["top", "center", "bottom"],
            index=(
                ["top", "center", "bottom"].index(
                    preset_settings["title_position"]
                )
            ),
        )

        shadow = st.checkbox("Enable text shadow", value=True)
        shadow_blur = st.slider("Shadow blur", 0, 20, 5)
        margin = st.slider("Text margin", 10, 200, 55)

        st.markdown("#### Image adjustments")

        brightness = st.slider(
            "Brightness",
            0.1,
            2.5,
            float(preset_settings["brightness"]),
            0.05,
        )

        contrast = st.slider(
            "Contrast",
            0.1,
            2.5,
            float(preset_settings["contrast"]),
            0.05,
        )

        saturation = st.slider(
            "Saturation",
            0.1,
            2.5,
            float(preset_settings["saturation"]),
            0.05,
        )

        overlay_opacity = st.slider(
            "Dark gradient overlay",
            0,
            230,
            int(preset_settings["overlay"]),
        )

        st.markdown("#### Branding")

        logo_upload = st.file_uploader(
            "Optional logo",
            type=["png", "jpg", "jpeg", "webp"],
            key="thumbnail_logo",
        )

        logo_position = st.selectbox(
            "Logo position",
            [
                "top-left",
                "top-right",
                "bottom-left",
                "bottom-right",
            ],
        )

        logo_size = st.slider(
            "Logo maximum size",
            30,
            400,
            150,
        )

        st.markdown("#### Export")

        export_format = st.selectbox("Image format", ["PNG", "JPG"])
        jpeg_quality = st.slider("JPG quality", 50, 100, 95)

        font_path = st.text_input(
            "Optional custom font path",
            value="",
            help=(
                "Example: C:\\Windows\\Fonts\\arialbd.ttf. "
                "Leave empty to use an available default font."
            ),
        )

    settings = {
        "format": format_choice,
        "width": int(width),
        "height": int(height),
        "preset": preset,
        "title": title,
        "subtitle": subtitle,
        "accent_label": accent_label,
        "font_size": font_size,
        "title_color": title_color,
        "outline_color": outline_color,
        "accent_color": accent_color,
        "outline_width": outline_width,
        "shadow": shadow,
        "shadow_blur": shadow_blur,
        "overlay_opacity": overlay_opacity,
        "brightness": brightness,
        "contrast": contrast,
        "saturation": saturation,
        "title_position": title_position,
        "alignment": alignment,
        "margin": margin,
        "logo_position": logo_position,
        "logo_size": logo_size,
        "jpeg_quality": jpeg_quality,
    }

    try:
        preview = create_thumbnail(
            background_upload.getvalue(),
            settings=settings,
            logo_source=(
                logo_upload.getvalue() if logo_upload else None
            ),
            font_path=font_path.strip() or None,
        )
    except Exception as exc:
        st.error(f"Could not create preview: {exc}")
        return

    with right:
        st.markdown("### Live preview")
        st.image(
            preview,
            caption=f"{width} × {height} pixels",
            use_container_width=True,
        )

        st.caption(
            "Preview is generated locally. No external AI service is used."
        )

        if st.button(
            "Generate and save thumbnail",
            type="primary",
            use_container_width=True,
        ):
            try:
                output_path = export_thumbnail(
                    preview,
                    project_name,
                    export_format,
                    jpeg_quality,
                )

                record = register_project(
                    project_name,
                    output_path,
                    settings,
                )

                st.success("Thumbnail saved successfully.")
                st.write(f"Saved file: `{output_path}`")
                st.write(f"Project ID: `{record['id']}`")

                with open(output_path, "rb") as file:
                    st.download_button(
                        "Download thumbnail",
                        data=file.read(),
                        file_name=output_path.name,
                        mime=(
                            "image/png"
                            if output_path.suffix == ".png"
                            else "image/jpeg"
                        ),
                    )

            except Exception as exc:
                st.error(f"Export failed: {exc}")

    st.divider()
    st.markdown("### Saved thumbnail projects")

    projects = load_projects()

    if not projects:
        st.info("No saved thumbnail projects yet.")
        return

    for project in projects[:20]:
        with st.expander(
            f"{project.get('name', 'Untitled')} — "
            f"{project.get('created_at', '')}"
        ):
            st.write(
                f"Preset: {project.get('preset', 'Unknown')}"
            )
            st.write(
                f"Dimensions: {project.get('width')} × "
                f"{project.get('height')}"
            )

            output_path = Path(project.get("output_path", ""))

            if output_path.exists():
                st.image(
                    str(output_path),
                    use_container_width=True,
                )

                try:
                    with open(output_path, "rb") as file:
                        st.download_button(
                            "Download saved thumbnail",
                            data=file.read(),
                            file_name=output_path.name,
                            key=f"download_{project['id']}",
                        )
                except OSError:
                    st.warning("Could not read the saved thumbnail.")
            else:
                st.warning("The exported image file is missing.")

            if st.button(
                "Delete project record",
                key=f"delete_{project['id']}",
            ):
                delete_project(project["id"])
                st.rerun()


# ---------------------------------------------------------------------
# Built-in tests
# ---------------------------------------------------------------------

def run_tests() -> None:
    """Run lightweight tests without Streamlit."""
    require_pillow()

    import tempfile

    print("Running Thumbnail Studio tests...")

    # Test settings validation.
    config = validate_settings({
        "width": 640,
        "height": 360,
        "preset": "Horror",
    })
    assert config["width"] == 640
    assert config["height"] == 360
    assert config["preset"] == "Horror"

    # Test filename safety.
    assert "/" not in safe_filename("../test thumbnail")
    assert safe_filename("") == "thumbnail"

    # Test image creation and resizing.
    background = Image.new(
        "RGB",
        (800, 600),
        color=(35, 55, 85),
    )

    image_bytes = io.BytesIO()
    background.save(image_bytes, format="PNG")

    settings = {
        "width": 640,
        "height": 360,
        "title": "TEST THUMBNAIL",
        "subtitle": "Built-in test",
        "accent_label": "TEST",
        "font_size": 45,
        "preset": "Cinematic",
    }

    result = create_thumbnail(
        image_bytes.getvalue(),
        settings=settings,
    )

    assert result.size == (640, 360)
    assert result.mode == "RGB"

    # Test export to a temporary folder.
    with tempfile.TemporaryDirectory() as temporary_dir:
        original_output_dir = OUTPUT_DIR

        try:
            # Replace the module output path only during this test.
            globals()["OUTPUT_DIR"] = Path(temporary_dir)

            output_path = export_thumbnail(
                result,
                "test thumbnail",
                "PNG",
            )

            assert output_path.exists()
            assert output_path.suffix == ".png"

            reopened = Image.open(output_path)
            assert reopened.size == (640, 360)

            jpg_path = export_thumbnail(
                result,
                "test thumbnail jpg",
                "JPG",
                quality=90,
            )

            assert jpg_path.exists()
            assert jpg_path.suffix == ".jpg"

        finally:
            globals()["OUTPUT_DIR"] = original_output_dir

    # Test text wrapping.
    test_draw = ImageDraw.Draw(Image.new("RGB", (400, 200)))
    test_font = load_font(24)
    lines = wrap_text(test_draw, "This is a thumbnail text test", test_font, 150)
    assert len(lines) >= 1

    print("All Thumbnail Studio tests passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AI Influencer Studio Thumbnail Studio"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run built-in tests",
    )
    args = parser.parse_args()

    if args.test:
        run_tests()
    else:
        print("Thumbnail Studio module loaded.")
        print("Run with --test to execute built-in tests.")
