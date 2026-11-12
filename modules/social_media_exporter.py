
"""
Social Media Exporter
File: modules/social_media_exporter.py

Features:
- Social media export presets
- YouTube Shorts, Instagram Reels, TikTok, Facebook Reels
- FFmpeg command generation
- Video export using FFmpeg
- Export history saved in JSON
- File metadata and validation
- Optional Streamlit interface
- Built-in tests that do not require FFmpeg

Note:
This module exports existing videos. It does not generate videos.
"""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
import uuid

from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------
# PATH CONFIGURATION
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs" / "social_media"
TEMP_DIR = BASE_DIR / "temp" / "social_media"

HISTORY_FILE = DATA_DIR / "social_export_history.json"

for folder in (DATA_DIR, OUTPUT_DIR, TEMP_DIR):
    folder.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# PLATFORM PRESETS
# ---------------------------------------------------------

PLATFORM_PRESETS: dict[str, dict[str, Any]] = {
    "YouTube - Standard": {
        "width": 1920,
        "height": 1080,
        "fps": 30,
        "video_bitrate": "8M",
        "audio_bitrate": "192k",
        "max_duration": 3600,
        "aspect_ratio": "16:9",
        "format": "mp4",
    },
    "YouTube Shorts": {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "video_bitrate": "8M",
        "audio_bitrate": "192k",
        "max_duration": 180,
        "aspect_ratio": "9:16",
        "format": "mp4",
    },
    "Instagram Reels": {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "video_bitrate": "8M",
        "audio_bitrate": "192k",
        "max_duration": 180,
        "aspect_ratio": "9:16",
        "format": "mp4",
    },
    "Instagram Feed": {
        "width": 1080,
        "height": 1080,
        "fps": 30,
        "video_bitrate": "6M",
        "audio_bitrate": "192k",
        "max_duration": 180,
        "aspect_ratio": "1:1",
        "format": "mp4",
    },
    "TikTok": {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "video_bitrate": "8M",
        "audio_bitrate": "192k",
        "max_duration": 600,
        "aspect_ratio": "9:16",
        "format": "mp4",
    },
    "Facebook Reels": {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "video_bitrate": "8M",
        "audio_bitrate": "192k",
        "max_duration": 180,
        "aspect_ratio": "9:16",
        "format": "mp4",
    },
    "X Video": {
        "width": 1920,
        "height": 1080,
        "fps": 30,
        "video_bitrate": "8M",
        "audio_bitrate": "192k",
        "max_duration": 140,
        "aspect_ratio": "16:9",
        "format": "mp4",
    },
    "LinkedIn Video": {
        "width": 1920,
        "height": 1080,
        "fps": 30,
        "video_bitrate": "8M",
        "audio_bitrate": "192k",
        "max_duration": 600,
        "aspect_ratio": "16:9",
        "format": "mp4",
    },
}


# ---------------------------------------------------------
# GENERAL HELPERS
# ---------------------------------------------------------

def ensure_directories() -> None:
    """Create required folders safely."""
    for folder in (DATA_DIR, OUTPUT_DIR, TEMP_DIR):
        folder.mkdir(parents=True, exist_ok=True)


def get_preset(platform: str) -> dict[str, Any]:
    """Return a copy of a platform preset."""
    if platform not in PLATFORM_PRESETS:
        raise ValueError(
            f"Unknown platform preset: {platform}. "
            f"Available presets: {', '.join(PLATFORM_PRESETS)}"
        )

    return dict(PLATFORM_PRESETS[platform])


def get_ffmpeg_path() -> str | None:
    """Find FFmpeg executable."""
    return shutil.which("ffmpeg")


def get_ffprobe_path() -> str | None:
    """Find FFprobe executable."""
    return shutil.which("ffprobe")


def validate_input_file(input_path: str | Path) -> Path:
    """Validate an input video path."""
    path = Path(input_path).expanduser()

    if not path.exists():
        raise FileNotFoundError(f"Input video not found: {path}")

    if not path.is_file():
        raise ValueError(f"Input path is not a file: {path}")

    return path.resolve()


def get_safe_filename(filename: str) -> str:
    """Create a safe filename."""
    name = Path(filename).stem

    allowed = []
    for character in name:
        if character.isalnum() or character in ("-", "_"):
            allowed.append(character)
        elif character in (" ", "."):
            allowed.append("_")

    safe_name = "".join(allowed).strip("_")
    return safe_name or "exported_video"


# ---------------------------------------------------------
# VIDEO FILTER
# ---------------------------------------------------------

def build_video_filter(
    preset: dict[str, Any],
    fit_mode: str = "crop",
) -> str:
    """
    Build FFmpeg video filter.

    fit_mode:
        crop  - Fill the complete output frame.
        fit   - Fit the video and add black bars if required.

    Example Shorts filter:
        scale=1080:1920:force_original_aspect_ratio=increase,
        crop=1080:1920,setsar=1,fps=30
    """

    width = int(preset["width"])
    height = int(preset["height"])
    fps = int(preset["fps"])

    if width <= 0 or height <= 0 or fps <= 0:
        raise ValueError("Width, height and FPS must be positive.")

    if fit_mode == "crop":
        filters = [
            (
                f"scale={width}:{height}:"
                "force_original_aspect_ratio=increase"
            ),
            f"crop={width}:{height}",
            "setsar=1",
            f"fps={fps}",
        ]

    elif fit_mode == "fit":
        filters = [
            (
                f"scale={width}:{height}:"
                "force_original_aspect_ratio=decrease"
            ),
            (
                f"pad={width}:{height}:"
                "(ow-iw)/2:(oh-ih)/2:black"
            ),
            "setsar=1",
            f"fps={fps}",
        ]

    else:
        raise ValueError("fit_mode must be either 'crop' or 'fit'.")

    return ",".join(filters)


# ---------------------------------------------------------
# FFMPEG COMMAND BUILDER
# ---------------------------------------------------------

def build_ffmpeg_command(
    input_path: str | Path,
    output_path: str | Path,
    preset: dict[str, Any],
    fit_mode: str = "crop",
    overwrite: bool = True,
) -> list[str]:
    """
    Build an FFmpeg command without executing it.

    The input file must exist.
    FFmpeg itself does not need to be installed to build
    or test this command.
    """

    source = validate_input_file(input_path)
    destination = Path(output_path).expanduser().resolve()

    if source == destination:
        raise ValueError("Input and output paths must be different.")

    destination.parent.mkdir(parents=True, exist_ok=True)

    output_format = str(preset.get("format", "mp4")).lower()

    if output_format != "mp4":
        raise ValueError("This exporter currently supports MP4 only.")

    video_filter = build_video_filter(preset, fit_mode)

    command = [
        "ffmpeg",
        "-hide_banner",
        "-y" if overwrite else "-n",
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-vf",
        video_filter,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-b:v",
        str(preset["video_bitrate"]),
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(preset["fps"]),
        "-c:a",
        "aac",
        "-b:a",
        str(preset["audio_bitrate"]),
        "-movflags",
        "+faststart",
    ]

    max_duration = preset.get("max_duration")

    if max_duration:
        command.extend(["-t", str(int(max_duration))])

    command.append(str(destination))

    return command


# ---------------------------------------------------------
# EXPORT HISTORY
# ---------------------------------------------------------

def load_history() -> list[dict[str, Any]]:
    """Load export history."""
    ensure_directories()

    if not HISTORY_FILE.exists():
        return []

    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_history(history: list[dict[str, Any]]) -> None:
    """Save export history safely."""
    ensure_directories()

    temporary_file = HISTORY_FILE.with_suffix(".tmp")

    temporary_file.write_text(
        json.dumps(history, indent=4, ensure_ascii=False),
        encoding="utf-8",
    )

    temporary_file.replace(HISTORY_FILE)


def add_history_record(record: dict[str, Any]) -> None:
    """Add one export record."""
    history = load_history()
    history.insert(0, record)
    save_history(history)


# ---------------------------------------------------------
# VIDEO METADATA
# ---------------------------------------------------------

def get_video_metadata(
    video_path: str | Path,
) -> dict[str, Any]:
    """Read video metadata through FFprobe."""

    path = validate_input_file(video_path)
    ffprobe = get_ffprobe_path()

    if not ffprobe:
        raise RuntimeError(
            "FFprobe was not found. Install FFmpeg and add it to PATH."
        )

    command = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration,size,format_name",
        "-show_entries",
        "stream=codec_name,width,height,r_frame_rate",
        "-of",
        "json",
        str(path),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "FFprobe failed.")

    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    video_stream = next(
        (item for item in streams if "width" in item),
        {},
    )

    format_data = data.get("format", {})

    return {
        "filename": path.name,
        "duration": float(format_data.get("duration", 0)),
        "size_bytes": int(format_data.get("size", 0)),
        "format": format_data.get("format_name", ""),
        "video_codec": video_stream.get("codec_name", ""),
        "width": video_stream.get("width"),
        "height": video_stream.get("height"),
        "fps": video_stream.get("r_frame_rate", ""),
    }


# ---------------------------------------------------------
# VIDEO EXPORT
# ---------------------------------------------------------

def export_video(
    input_path: str | Path,
    platform: str,
    output_name: str | None = None,
    fit_mode: str = "crop",
) -> dict[str, Any]:
    """Export a video using the selected platform preset."""

    source = validate_input_file(input_path)
    preset = get_preset(platform)

    if not get_ffmpeg_path():
        raise RuntimeError(
            "FFmpeg is not installed or not available in PATH. "
            "Install FFmpeg and restart PowerShell."
        )

    filename = get_safe_filename(output_name or source.stem)
    destination = OUTPUT_DIR / f"{filename}_{uuid.uuid4().hex[:8]}.mp4"

    command = build_ffmpeg_command(
        source,
        destination,
        preset,
        fit_mode=fit_mode,
    )

    started_at = datetime.now().isoformat(timespec="seconds")

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=3600,
        )

        if result.returncode != 0:
            raise RuntimeError(
                result.stderr[-4000:] or "FFmpeg export failed."
            )

        if not destination.exists() or destination.stat().st_size == 0:
            raise RuntimeError("FFmpeg did not create a valid output file.")

        record = {
            "id": uuid.uuid4().hex,
            "platform": platform,
            "input": str(source),
            "output": str(destination),
            "status": "Completed",
            "started_at": started_at,
            "completed_at": datetime.now().isoformat(timespec="seconds"),
            "output_size_bytes": destination.stat().st_size,
            "error": None,
        }

        add_history_record(record)

        return record

    except Exception as exc:
        record = {
            "id": uuid.uuid4().hex,
            "platform": platform,
            "input": str(source),
            "output": str(destination),
            "status": "Failed",
            "started_at": started_at,
            "completed_at": datetime.now().isoformat(timespec="seconds"),
            "output_size_bytes": 0,
            "error": str(exc),
        }

        add_history_record(record)

        if destination.exists():
            destination.unlink(missing_ok=True)

        raise


# ---------------------------------------------------------
# EXPORT HELPERS
# ---------------------------------------------------------

def get_export_history() -> list[dict[str, Any]]:
    return load_history()


def clear_export_history() -> None:
    save_history([])


def export_history_csv(
    output_path: str | Path | None = None,
) -> Path:
    """Export history to CSV."""

    destination = (
        Path(output_path)
        if output_path
        else OUTPUT_DIR / "social_export_history.csv"
    )

    destination.parent.mkdir(parents=True, exist_ok=True)

    history = load_history()

    fields = [
        "id",
        "platform",
        "input",
        "output",
        "status",
        "started_at",
        "completed_at",
        "output_size_bytes",
        "error",
    ]

    with destination.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(history)

    return destination


def get_export_statistics() -> dict[str, int]:
    """Return export counts."""
    history = load_history()

    return {
        "total": len(history),
        "completed": sum(
            item.get("status") == "Completed" for item in history
        ),
        "failed": sum(
            item.get("status") == "Failed" for item in history
        ),
    }


# ---------------------------------------------------------
# STREAMLIT UI
# ---------------------------------------------------------

def render() -> None:
    """Render the Social Media Exporter page."""

    try:
        import streamlit as st
    except ImportError:
        raise RuntimeError(
            "Streamlit is missing. Install it using: pip install streamlit"
        )

    st.title("Social Media Exporter")
    st.caption("Prepare videos for social media platforms using FFmpeg.")

    stats = get_export_statistics()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Exports", stats["total"])
    col2.metric("Completed", stats["completed"])
    col3.metric("Failed", stats["failed"])

    st.divider()

    st.subheader("Export Video")

    uploaded_file = st.file_uploader(
        "Upload a video",
        type=["mp4", "mov", "mkv", "avi", "webm"],
    )

    platform = st.selectbox(
        "Select platform",
        list(PLATFORM_PRESETS.keys()),
    )

    fit_mode = st.radio(
        "Video fitting",
        ["crop", "fit"],
        horizontal=True,
        help="Crop fills the frame. Fit keeps the complete video.",
    )

    output_name = st.text_input(
        "Output filename",
        value="social_media_video",
    )

    preset = get_preset(platform)

    st.info(
        f"Output: {preset['width']} × {preset['height']} | "
        f"{preset['fps']} FPS | {preset['aspect_ratio']} | "
        f"MP4"
    )

    if uploaded_file is not None:
        st.video(uploaded_file)

        if st.button("Export Video", type="primary"):
            input_file = TEMP_DIR / get_safe_filename(uploaded_file.name)
            input_file = input_file.with_suffix(
                Path(uploaded_file.name).suffix or ".mp4"
            )

            try:
                input_file.write_bytes(uploaded_file.getvalue())

                with st.spinner("Exporting video with FFmpeg..."):
                    record = export_video(
                        input_file,
                        platform,
                        output_name,
                        fit_mode,
                    )

                st.success("Video exported successfully.")

                output_file = Path(record["output"])

                st.video(str(output_file))

                st.download_button(
                    "Download exported video",
                    data=output_file.read_bytes(),
                    file_name=output_file.name,
                    mime="video/mp4",
                )

            except Exception as exc:
                st.error(f"Export failed: {exc}")

            finally:
                input_file.unlink(missing_ok=True)

    st.divider()

    st.subheader("Export History")

    history = get_export_history()

    if history:
        st.dataframe(
            history,
            use_container_width=True,
            hide_index=True,
        )

        if st.button("Export History CSV"):
            csv_path = export_history_csv()

            st.download_button(
                "Download CSV",
                data=csv_path.read_bytes(),
                file_name=csv_path.name,
                mime="text/csv",
            )

        if st.button("Clear Export History"):
            clear_export_history()
            st.rerun()
    else:
        st.info("No exports have been recorded yet.")


# ---------------------------------------------------------
# BUILT-IN TESTS
# ---------------------------------------------------------

def run_tests() -> None:
    """Run tests without requiring FFmpeg."""

    print("Running Social Media Exporter tests...")

    # Test 1: Preset
    shorts = get_preset("YouTube Shorts")

    assert shorts["width"] == 1080
    assert shorts["height"] == 1920
    assert shorts["aspect_ratio"] == "9:16"

    # Test 2: Filter
    video_filter = build_video_filter(shorts)

    assert "1080:1920" in video_filter
    assert "crop=1080:1920" in video_filter
    assert "fps=30" in video_filter

    # Test 3: Create a temporary input file.
    test_input = TEMP_DIR / "test_input.mp4"
    test_output = TEMP_DIR / "test_output.mp4"

    test_input.parent.mkdir(parents=True, exist_ok=True)
    test_input.write_bytes(b"test")

    try:
        command = build_ffmpeg_command(
            test_input,
            test_output,
            get_preset("YouTube Shorts"),
        )

        assert command[0] == "ffmpeg"
        assert "libx264" in command
        assert "-vf" in command

        filter_value = command[command.index("-vf") + 1]

        assert "1080:1920" in filter_value
        assert "crop=1080:1920" in filter_value

        assert str(test_input.resolve()) in command
        assert str(test_output.resolve()) in command

    finally:
        test_input.unlink(missing_ok=True)
        test_output.unlink(missing_ok=True)

    # Test 4: Unknown preset
    try:
        get_preset("Unknown Platform")
        raise AssertionError("Unknown preset should raise ValueError.")
    except ValueError:
        pass

    # Test 5: Fit mode
    fit_filter = build_video_filter(shorts, fit_mode="fit")

    assert "pad=1080:1920" in fit_filter

    # Test 6: Invalid fit mode
    try:
        build_video_filter(shorts, fit_mode="invalid")
        raise AssertionError("Invalid fit mode should raise ValueError.")
    except ValueError:
        pass

    # Test 7: Statistics
    statistics = get_export_statistics()

    assert "total" in statistics
    assert "completed" in statistics
    assert "failed" in statistics

    print("All Social Media Exporter tests passed.")


# ---------------------------------------------------------
# COMMAND LINE ENTRY
# ---------------------------------------------------------

if __name__ == "__main__":
    if "--test" in sys.argv:
        run_tests()
    else:
        print("Social Media Exporter")
        print("Run tests: python -m modules.social_media_exporter --test")
        print("Run app: streamlit run app.py")
