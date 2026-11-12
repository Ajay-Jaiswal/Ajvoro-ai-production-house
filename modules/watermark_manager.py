
"""
AI Influencer Studio
File 46: modules/watermark_manager.py

Features:
- Apply Brand Kit logos and watermarks to images
- Apply transparent watermarks to MP4 videos using FFmpeg
- Position, opacity, size and margin controls
- PNG/JPG image export
- MP4 video export
- Load saved profiles from modules.brand_kit
- Preserve original input files
- Built-in tests

Run:
    python -m modules.watermark_manager --test

Streamlit integration:
    from modules import watermark_manager
    pages["Watermark Manager"] = watermark_manager.render
"""

from __future__ import annotations

import argparse
import io
import json
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

try:
    from PIL import Image
except ImportError:
    Image = None


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "outputs" / "watermarked"
TEMP_DIR = BASE_DIR / "temp" / "watermark_manager"

POSITIONS = [
    "top-left",
    "top-right",
    "bottom-left",
    "bottom-right",
    "center",
]

DEFAULT_SETTINGS = {
    "position": "bottom-right",
    "opacity": 65,
    "size_percent": 18,
    "margin": 30,
}


def ensure_directories() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)


def require_pillow() -> None:
    if Image is None:
        raise RuntimeError(
            "Pillow is required. Install it using: "
            "python -m pip install Pillow"
        )


def validate_settings(
    settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate watermark settings."""
    result = DEFAULT_SETTINGS.copy()
    result.update(settings or {})

    if result["position"] not in POSITIONS:
        raise ValueError("Invalid watermark position.")

    result["opacity"] = max(
        0,
        min(100, int(result["opacity"])),
    )
    result["size_percent"] = max(
        2,
        min(80, int(result["size_percent"])),
    )
    result["margin"] = max(
        0,
        min(1000, int(result["margin"])),
    )

    return result


def open_image(source: bytes | str | Path) -> Image.Image:
    """Load an image from bytes or a filesystem path."""
    require_pillow()

    if isinstance(source, bytes):
        image = Image.open(io.BytesIO(source))
    else:
        image = Image.open(source)

    return image.convert("RGBA")


def resize_watermark(
    watermark: Image.Image,
    base_width: int,
    size_percent: int,
) -> Image.Image:
    """Resize watermark relative to the base image width."""
    target_width = max(
        1,
        int(base_width * size_percent / 100),
    )

    ratio = target_width / max(1, watermark.width)
    target_height = max(1, int(watermark.height * ratio))

    return watermark.resize(
        (target_width, target_height),
        Image.Resampling.LANCZOS,
    )


def apply_opacity(
    watermark: Image.Image,
    opacity: int,
) -> Image.Image:
    """Multiply watermark alpha by the requested opacity."""
    watermark = watermark.convert("RGBA")
    alpha = watermark.getchannel("A")

    multiplier = max(0, min(100, int(opacity))) / 100

    alpha = alpha.point(
        lambda value: int(value * multiplier)
    )

    watermark.putalpha(alpha)
    return watermark


def calculate_position(
    base_size: tuple[int, int],
    watermark_size: tuple[int, int],
    position: str,
    margin: int,
) -> tuple[int, int]:
    """Calculate the watermark's top-left position."""
    base_width, base_height = base_size
    mark_width, mark_height = watermark_size

    if position == "top-left":
        x, y = margin, margin

    elif position == "top-right":
        x, y = base_width - mark_width - margin, margin

    elif position == "bottom-left":
        x, y = margin, base_height - mark_height - margin

    elif position == "bottom-right":
        x = base_width - mark_width - margin
        y = base_height - mark_height - margin

    elif position == "center":
        x = (base_width - mark_width) // 2
        y = (base_height - mark_height) // 2

    else:
        raise ValueError("Unsupported watermark position.")

    x = max(0, min(x, base_width - mark_width))
    y = max(0, min(y, base_height - mark_height))

    return x, y


def apply_watermark_to_image(
    image_source: bytes | str | Path,
    watermark_source: bytes | str | Path,
    settings: dict[str, Any] | None = None,
) -> Image.Image:
    """Return a new image with a watermark applied."""
    require_pillow()

    config = validate_settings(settings)

    base = open_image(image_source)
    watermark = open_image(watermark_source)

    watermark = resize_watermark(
        watermark,
        base.width,
        config["size_percent"],
    )

    watermark = apply_opacity(
        watermark,
        config["opacity"],
    )

    position = calculate_position(
        base.size,
        watermark.size,
        config["position"],
        config["margin"],
    )

    base.alpha_composite(watermark, position)

    return base


def export_watermarked_image(
    image: Image.Image,
    filename: str = "watermarked_image",
    image_format: str = "PNG",
    quality: int = 95,
) -> Path:
    """Save a watermarked image."""
    require_pillow()
    ensure_directories()

    image_format = image_format.upper()

    if image_format not in ("PNG", "JPG", "JPEG"):
        raise ValueError("Supported formats are PNG and JPG.")

    extension = "jpg" if image_format in ("JPG", "JPEG") else "png"

    safe_name = "".join(
        character
        if character.isalnum() or character in "-_"
        else "_"
        for character in Path(filename).stem
    ).strip("_") or "watermarked_image"

    output = OUTPUT_DIR / (
        f"{safe_name}_{uuid.uuid4().hex[:8]}.{extension}"
    )

    if extension == "jpg":
        image.convert("RGB").save(
            output,
            format="JPEG",
            quality=max(50, min(100, int(quality))),
            optimize=True,
        )
    else:
        image.save(output, format="PNG", optimize=True)

    return output


def find_ffmpeg() -> str | None:
    """Find FFmpeg executable."""
    return shutil.which("ffmpeg")


def find_ffprobe() -> str | None:
    """Find FFprobe executable."""
    return shutil.which("ffprobe")


def probe_video(
    video_path: str | Path,
    ffprobe: str | None = None,
) -> dict[str, Any]:
    """Get video dimensions and duration using FFprobe."""
    executable = ffprobe or find_ffprobe()

    if not executable:
        raise RuntimeError(
            "FFprobe was not found. Install FFmpeg and add it to PATH."
        )

    path = Path(video_path)

    if not path.is_file():
        raise FileNotFoundError(f"Video not found: {path}")

    command = [
        executable,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries",
        "stream=width,height:format=duration",
        "-of", "json",
        str(path),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip() or "FFprobe failed."
        )

    try:
        data = json.loads(result.stdout)
        stream = data["streams"][0]
        duration = float(data.get("format", {}).get("duration", 0))

        return {
            "width": int(stream["width"]),
            "height": int(stream["height"]),
            "duration": duration,
        }
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(
            "Could not read video information."
        ) from exc


def build_video_filter(
    video_width: int,
    watermark_width: int,
    settings: dict[str, Any] | None = None,
) -> str:
    """Build the FFmpeg watermark overlay filter."""
    config = validate_settings(settings)

    if video_width <= 0 or watermark_width <= 0:
        raise ValueError("Video and watermark dimensions must be positive.")

    target_width = max(
        1,
        int(video_width * config["size_percent"] / 100),
    )

    opacity = config["opacity"] / 100
    margin = config["margin"]
    position = config["position"]

    if position == "top-left":
        x, y = str(margin), str(margin)

    elif position == "top-right":
        x, y = f"main_w-overlay_w-{margin}", str(margin)

    elif position == "bottom-left":
        x, y = str(margin), f"main_h-overlay_h-{margin}"

    elif position == "bottom-right":
        x = f"main_w-overlay_w-{margin}"
        y = f"main_h-overlay_h-{margin}"

    else:
        x = "(main_w-overlay_w)/2"
        y = "(main_h-overlay_h)/2"

    return (
        f"[1:v]scale={target_width}:-1,"
        f"format=rgba,"
        f"colorchannelmixer=aa={opacity:.3f}[wm];"
        f"[0:v][wm]overlay=x={x}:y={y}:format=auto[v]"
    )


def build_video_command(
    input_path: str | Path,
    watermark_path: str | Path,
    output_path: str | Path,
    video_width: int,
    settings: dict[str, Any] | None = None,
    ffmpeg: str = "ffmpeg",
) -> list[str]:
    """
    Build FFmpeg command for video watermarking.

    The watermark input is looped so it remains visible throughout
    the video. The original audio stream is retained when present.
    """
    input_file = Path(input_path)
    watermark_file = Path(watermark_path)
    output_file = Path(output_path)

    if not input_file.is_file():
        raise FileNotFoundError(input_file)

    if not watermark_file.is_file():
        raise FileNotFoundError(watermark_file)

    if input_file.resolve() == output_file.resolve():
        raise ValueError("Output must not overwrite the original video.")

    if input_file.resolve() == watermark_file.resolve():
        raise ValueError("Video and watermark files must be different.")

    if output_file.suffix.lower() != ".mp4":
        raise ValueError("Video output must use the .mp4 extension.")

    config = validate_settings(settings)

    # Watermark width is measured from the actual watermark image
    # by FFmpeg's scale filter using the target video width.
    filter_complex = build_video_filter(
        video_width,
        1,
        config,
    )

    output_file.parent.mkdir(parents=True, exist_ok=True)

    return [
        ffmpeg,
        "-hide_banner",
        "-y",
        "-i", str(input_file),
        "-loop", "1",
        "-i", str(watermark_file),
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        "-shortest",
        str(output_file),
    ]


def render_watermarked_video(
    input_path: str | Path,
    watermark_path: str | Path,
    output_path: str | Path,
    settings: dict[str, Any] | None = None,
    ffmpeg: str | None = None,
    ffprobe: str | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    """Render a watermarked MP4 video."""
    executable = ffmpeg or find_ffmpeg()

    if not executable:
        raise RuntimeError(
            "FFmpeg was not found. Install FFmpeg and add it to PATH."
        )

    video_info = probe_video(input_path, ffprobe)

    command = build_video_command(
        input_path=input_path,
        watermark_path=watermark_path,
        output_path=output_path,
        video_width=video_info["width"],
        settings=settings,
        ffmpeg=executable,
    )

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr[-3000:] or "FFmpeg rendering failed."
        )

    output = Path(output_path)

    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError("FFmpeg did not produce a valid output file.")

    return {
        "output_path": str(output.resolve()),
        "input_duration": video_info["duration"],
        "video_width": video_info["width"],
        "video_height": video_info["height"],
        "file_size_bytes": output.stat().st_size,
        "settings": validate_settings(settings),
    }


def get_brand_profiles() -> list[dict[str, Any]]:
    """Read saved profiles from File 45."""
    try:
        from modules.brand_kit import load_database
        return load_database()
    except ImportError:
        return []


def get_profile_watermark(
    profile: dict[str, Any],
    asset_type: str = "watermark",
) -> Path | None:
    """Return an existing profile logo or watermark."""
    if asset_type not in ("logo", "watermark"):
        raise ValueError("Asset type must be logo or watermark.")

    asset_path = Path(profile.get(f"{asset_type}_path", ""))

    if asset_path.is_file():
        return asset_path

    return None


def render() -> None:
    """Render the Streamlit Watermark Manager."""
    try:
        import streamlit as st
    except ImportError as exc:
        raise RuntimeError(
            "Streamlit is required. Install it using: "
            "python -m pip install streamlit"
        ) from exc

    ensure_directories()

    st.title("💧 Watermark Manager")
    st.caption(
        "Apply your saved brand identity to images and videos."
    )

    mode = st.radio(
        "Choose operation",
        ["Image Watermark", "Video Watermark"],
        horizontal=True,
    )

    profiles = get_brand_profiles()

    selected_watermark = None

    if profiles:
        profile_options = {
            profile["id"]: profile.get("name", "Untitled")
            for profile in profiles
            if profile.get("id")
        }

        if profile_options:
            selected_id = st.selectbox(
                "Select Brand Kit profile",
                list(profile_options.keys()),
                format_func=lambda value: profile_options[value],
            )

            selected_profile = next(
                (
                    profile
                    for profile in profiles
                    if profile.get("id") == selected_id
                ),
                {},
            )

            asset_choice = st.radio(
                "Brand asset",
                ["Watermark", "Logo", "Upload another image"],
                horizontal=True,
            )

            if asset_choice == "Watermark":
                selected_watermark = get_profile_watermark(
                    selected_profile,
                    "watermark",
                )
            elif asset_choice == "Logo":
                selected_watermark = get_profile_watermark(
                    selected_profile,
                    "logo",
                )

            if asset_choice != "Upload another image":
                if selected_watermark:
                    st.success(
                        f"Using saved asset: {selected_watermark.name}"
                    )
                else:
                    st.warning(
                        "The selected profile does not have this asset. "
                        "Upload another image or add one in Brand Kit."
                    )

    else:
        st.info(
            "No saved Brand Kit profiles found. "
            "You can still upload a watermark manually."
        )

    uploaded_watermark = None

    if selected_watermark is None:
        uploaded_watermark = st.file_uploader(
            "Upload watermark or logo",
            type=["png", "jpg", "jpeg", "webp"],
            key="watermark_asset_upload",
        )

    if selected_watermark is None and uploaded_watermark is None:
        st.info("Choose or upload a watermark to continue.")
        return

    position = st.selectbox(
        "Watermark position",
        POSITIONS,
        index=3,
    )

    opacity = st.slider(
        "Opacity",
        0,
        100,
        65,
    )

    size_percent = st.slider(
        "Watermark size (% of image/video width)",
        2,
        80,
        18,
    )

    margin = st.slider(
        "Margin (pixels)",
        0,
        300,
        30,
    )

    settings = {
        "position": position,
        "opacity": opacity,
        "size_percent": size_percent,
        "margin": margin,
    }

    if mode == "Image Watermark":
        source = st.file_uploader(
            "Upload source image",
            type=["png", "jpg", "jpeg", "webp"],
            key="watermark_source_image",
        )

        export_format = st.selectbox(
            "Export format",
            ["PNG", "JPG"],
        )

        quality = st.slider(
            "JPG quality",
            50,
            100,
            95,
        )

        if source:
            try:
                watermark_source = (
                    selected_watermark
                    if selected_watermark
                    else uploaded_watermark.getvalue()
                )

                result = apply_watermark_to_image(
                    source.getvalue(),
                    watermark_source,
                    settings,
                )

                st.image(
                    result,
                    caption="Watermarked preview",
                    use_container_width=True,
                )

                if st.button(
                    "Export Watermarked Image",
                    type="primary",
                ):
                    output = export_watermarked_image(
                        result,
                        source.name,
                        export_format,
                        quality,
                    )

                    st.success("Image exported.")
                    st.write(f"Output: `{output}`")

                    with open(output, "rb") as file:
                        st.download_button(
                            "Download Image",
                            data=file.read(),
                            file_name=output.name,
                            mime=(
                                "image/png"
                                if output.suffix == ".png"
                                else "image/jpeg"
                            ),
                        )

            except Exception as exc:
                st.error(f"Image watermark failed: {exc}")

    else:
        source = st.file_uploader(
            "Upload source MP4 video",
            type=["mp4"],
            key="watermark_source_video",
        )

        st.warning(
            "Video watermarking re-encodes the video using CPU-based "
            "FFmpeg. Rendering time depends on video length and resolution."
        )

        if source and st.button(
            "Render Watermarked Video",
            type="primary",
        ):
            watermark_source = (
                selected_watermark
                if selected_watermark
                else uploaded_watermark.getvalue()
            )

            try:
                ensure_directories()

                job_id = uuid.uuid4().hex[:10]
                input_path = TEMP_DIR / f"source_{job_id}.mp4"
                watermark_path = TEMP_DIR / f"watermark_{job_id}.png"
                output_path = OUTPUT_DIR / f"video_{job_id}.mp4"

                input_path.write_bytes(source.getvalue())

                if isinstance(watermark_source, Path):
                    shutil.copy2(watermark_source, watermark_path)
                else:
                    watermark_path.write_bytes(watermark_source)

                with st.spinner(
                    "Rendering video watermark. Please wait..."
                ):
                    result = render_watermarked_video(
                        input_path,
                        watermark_path,
                        output_path,
                        settings,
                    )

                st.success("Watermarked video created.")
                st.write(
                    f"Resolution: {result['video_width']} × "
                    f"{result['video_height']}"
                )
                st.write(
                    f"Duration: {result['input_duration']:.2f} seconds"
                )
                st.write(f"Output: `{result['output_path']}`")

                with open(output_path, "rb") as file:
                    st.download_button(
                        "Download Watermarked MP4",
                        data=file.read(),
                        file_name=output_path.name,
                        mime="video/mp4",
                    )

            except subprocess.TimeoutExpired:
                st.error(
                    "Rendering timed out. Try a shorter video."
                )
            except Exception as exc:
                st.error(f"Video watermark failed: {exc}")


# ---------------------------------------------------------------------
# Built-in tests
# ---------------------------------------------------------------------

def run_tests() -> None:
    """Run lightweight unit tests."""
    require_pillow()

    import tempfile

    print("Running Watermark Manager tests...")

    # Validate settings.
    settings = validate_settings({
        "position": "top-left",
        "opacity": 50,
        "size_percent": 20,
        "margin": 10,
    })

    assert settings["position"] == "top-left"
    assert settings["opacity"] == 50

    # Create a test background and transparent watermark.
    base = Image.new("RGBA", (800, 600), (20, 40, 60, 255))
    mark = Image.new("RGBA", (100, 50), (255, 0, 0, 255))

    base_buffer = io.BytesIO()
    mark_buffer = io.BytesIO()

    base.save(base_buffer, format="PNG")
    mark.save(mark_buffer, format="PNG")

    result = apply_watermark_to_image(
        base_buffer.getvalue(),
        mark_buffer.getvalue(),
        settings,
    )

    assert result.size == (800, 600)
    assert result.mode == "RGBA"

    # Check position calculations.
    position = calculate_position(
        (800, 600),
        (100, 50),
        "bottom-right",
        20,
    )

    assert position == (680, 530)

    # Check opacity handling.
    opacity_result = apply_opacity(mark, 50)
    assert opacity_result.getchannel("A").getpixel((50, 25)) == 127

    # Test video filter generation.
    video_filter = build_video_filter(
        1920,
        100,
        {
            "position": "bottom-right",
            "opacity": 50,
            "size_percent": 20,
            "margin": 25,
        },
    )

    assert "colorchannelmixer=aa=0.500" in video_filter
    assert "overlay=" in video_filter
    assert "main_w-overlay_w-25" in video_filter

    # Test command construction with temporary files.
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)

        video = root / "input.mp4"
        watermark = root / "watermark.png"
        output = root / "output.mp4"

        video.write_bytes(b"test video placeholder")
        watermark.write_bytes(b"test watermark placeholder")

        command = build_video_command(
            video,
            watermark,
            output,
            video_width=1920,
            settings=settings,
        )

        assert "-filter_complex" in command
        assert "-map" in command
        assert str(output) in command

        try:
            build_video_command(
                video,
                watermark,
                video,
                video_width=1920,
            )
            raise AssertionError(
                "Input/output collision should have failed."
            )
        except ValueError:
            pass

    print("All Watermark Manager tests passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AI Influencer Studio Watermark Manager"
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
        ensure_directories()
        print("Watermark Manager loaded.")
        print("Run with --test to execute built-in tests.")
