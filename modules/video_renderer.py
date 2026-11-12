
"""
AI Influencer Studio
File 41: modules/video_renderer.py

Local FFmpeg Video Rendering Engine.

Features:
- FFmpeg detection
- Video clip concatenation
- Resolution and FPS configuration
- H.264 MP4 rendering
- Audio mixing
- SRT subtitle burning
- CPU-friendly presets
- Render progress reporting
- Render history and error logs

Requirements:
- FFmpeg installed and available in PATH.
- Python standard library only.

Important:
- Video clips are normalized into temporary silent segments.
- Their original audio is not automatically retained.
- External audio tracks can be mixed into the final video.
- Transition metadata is not rendered as visual effects yet.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid

from datetime import datetime
from pathlib import Path
from typing import Any, Callable


# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "outputs" / "rendered_videos"
TEMP_DIR = ROOT_DIR / "temp" / "video_renderer"

HISTORY_FILE = DATA_DIR / "render_history.json"


# ---------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------

SUPPORTED_VIDEO = {
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".webm",
    ".m4v",
}

SUPPORTED_AUDIO = {
    ".mp3",
    ".wav",
    ".aac",
    ".m4a",
    ".ogg",
    ".flac",
}

RESOLUTIONS = {
    "480p": (854, 480),
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "1440p": (2560, 1440),
    "2160p": (3840, 2160),
}

QUALITY_PRESETS = {
    "CPU Fast": {
        "preset": "ultrafast",
        "crf": 28,
    },
    "Balanced": {
        "preset": "veryfast",
        "crf": 23,
    },
    "High Quality": {
        "preset": "medium",
        "crf": 20,
    },
    "Maximum Quality": {
        "preset": "slow",
        "crf": 18,
    },
}

AUDIO_BITRATES = [
    "128k",
    "160k",
    "192k",
    "256k",
    "320k",
]


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _id() -> str:
    return uuid.uuid4().hex[:12]


def _clean(value: Any, limit: int = 1000) -> str:
    return str(value or "").strip()[:limit]


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def validate_video(path: Path | str) -> Path:

    source = Path(path).expanduser().resolve()

    if source.suffix.lower() not in SUPPORTED_VIDEO:
        raise ValueError(
            f"Unsupported video format: {source.suffix}"
        )

    if not source.is_file():
        raise FileNotFoundError(
            f"Video file not found: {source}"
        )

    return source


def validate_audio(path: Path | str) -> Path:

    source = Path(path).expanduser().resolve()

    if source.suffix.lower() not in SUPPORTED_AUDIO:
        raise ValueError(
            f"Unsupported audio format: {source.suffix}"
        )

    if not source.is_file():
        raise FileNotFoundError(
            f"Audio file not found: {source}"
        )

    return source


def validate_resolution(resolution: str) -> tuple[int, int]:

    if resolution not in RESOLUTIONS:
        raise ValueError("Unsupported resolution.")

    return RESOLUTIONS[resolution]


def validate_fps(fps: int | float) -> int:

    try:
        value = int(fps)
    except (TypeError, ValueError):
        raise ValueError("FPS must be an integer.")

    if value not in (24, 25, 30, 50, 60):
        raise ValueError(
            "FPS must be 24, 25, 30, 50 or 60."
        )

    return value


# ---------------------------------------------------------
# FFMPEG DETECTION
# ---------------------------------------------------------

def detect_ffmpeg() -> dict:

    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")

    result = {
        "installed": bool(ffmpeg),
        "ffmpeg_path": ffmpeg,
        "ffprobe_path": ffprobe,
        "version": None,
        "error": None,
    }

    if not ffmpeg:
        result["error"] = (
            "FFmpeg was not found. Install FFmpeg "
            "and add its bin folder to Windows PATH."
        )
        return result

    try:
        process = subprocess.run(
            [ffmpeg, "-version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        first_line = (
            process.stdout.splitlines()[0]
            if process.stdout
            else ""
        )

        result["version"] = first_line

        if process.returncode != 0:
            result["error"] = process.stderr[-1000:]

    except (OSError, subprocess.TimeoutExpired) as exc:
        result["error"] = str(exc)

    return result


def require_ffmpeg() -> str:

    executable = shutil.which("ffmpeg")

    if not executable:
        raise RuntimeError(
            "FFmpeg is not installed or not available in PATH."
        )

    return executable


# ---------------------------------------------------------
# VIDEO INFORMATION
# ---------------------------------------------------------

def probe_media(path: Path | str) -> dict:

    source = Path(path).expanduser().resolve()

    if not source.is_file():
        raise FileNotFoundError(source)

    ffprobe = shutil.which("ffprobe")

    if not ffprobe:
        raise RuntimeError(
            "FFprobe is unavailable. Install FFmpeg with FFprobe."
        )

    command = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration,size,format_name",
        "-show_entries",
        "stream=codec_type,codec_name,width,height,r_frame_rate",
        "-of",
        "json",
        str(source),
    ]

    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    if process.returncode != 0:
        raise RuntimeError(
            process.stderr[-2000:]
        )

    data = json.loads(process.stdout)

    streams = data.get("streams", [])
    format_data = data.get("format", {})

    video_stream = next(
        (
            stream for stream in streams
            if stream.get("codec_type") == "video"
        ),
        {},
    )

    audio_streams = [
        stream for stream in streams
        if stream.get("codec_type") == "audio"
    ]

    return {
        "path": str(source),
        "duration": float(
            format_data.get("duration", 0)
        ),
        "size_bytes": int(
            format_data.get("size", 0)
        ),
        "format": format_data.get("format_name"),
        "video_codec": video_stream.get("codec_name"),
        "width": video_stream.get("width"),
        "height": video_stream.get("height"),
        "fps": video_stream.get("r_frame_rate"),
        "has_audio": bool(audio_streams),
    }


# ---------------------------------------------------------
# RENDER SETTINGS
# ---------------------------------------------------------

def validate_render_settings(settings: dict | None = None) -> dict:

    settings = settings or {}

    resolution = _clean(
        settings.get("resolution", "1080p")
    )

    width, height = validate_resolution(resolution)

    fps = validate_fps(
        settings.get("fps", 24)
    )

    quality = _clean(
        settings.get("quality", "CPU Fast")
    )

    if quality not in QUALITY_PRESETS:
        raise ValueError("Invalid quality preset.")

    audio_bitrate = _clean(
        settings.get("audio_bitrate", "192k")
    )

    if audio_bitrate not in AUDIO_BITRATES:
        raise ValueError("Invalid audio bitrate.")

    return {
        "resolution": resolution,
        "width": width,
        "height": height,
        "fps": fps,
        "quality": quality,
        "video_preset": QUALITY_PRESETS[quality]["preset"],
        "crf": QUALITY_PRESETS[quality]["crf"],
        "audio_bitrate": audio_bitrate,
        "include_audio": bool(
            settings.get("include_audio", True)
        ),
        "burn_subtitles": bool(
            settings.get("burn_subtitles", False)
        ),
        "threads": max(
            1,
            min(
                16,
                int(settings.get("threads", 2)),
            ),
        ),
    }


# ---------------------------------------------------------
# INPUT VALIDATION
# ---------------------------------------------------------

def validate_render_inputs(
    clips: list[str | Path],
    audio_files: list[str | Path] | None = None,
    subtitle_file: str | Path | None = None,
) -> dict:

    if not isinstance(clips, list) or not clips:
        raise ValueError("At least one video clip is required.")

    validated_clips = [
        validate_video(item)
        for item in clips
    ]

    validated_audio = [
        validate_audio(item)
        for item in (audio_files or [])
    ]

    subtitle = None

    if subtitle_file:

        subtitle = Path(
            subtitle_file
        ).expanduser().resolve()

        if not subtitle.is_file():
            raise FileNotFoundError(subtitle)

        if subtitle.suffix.lower() != ".srt":
            raise ValueError(
                "Subtitle burning currently supports SRT only."
            )

    return {
        "clips": validated_clips,
        "audio_files": validated_audio,
        "subtitle_file": subtitle,
    }


# ---------------------------------------------------------
# FILTER HELPERS
# ---------------------------------------------------------

def _subtitle_filter_path(path: Path) -> str:

    """
    Escape path characters for FFmpeg subtitles filter.

    This is a filter argument, not a shell command.
    subprocess is always called with an argument list.
    """

    value = path.resolve().as_posix()

    value = value.replace("\\", "\\\\")
    value = value.replace(":", "\\:")
    value = value.replace("'", "\\'")
    value = value.replace(",", "\\,")

    return value


def _video_filter(
    width: int,
    height: int,
    fps: int,
) -> str:

    return (
        f"scale={width}:{height}:"
        "force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
        "setsar=1,"
        f"fps={fps},"
        "format=yuv420p"
    )


# ---------------------------------------------------------
# BUILD NORMALIZATION COMMAND
# ---------------------------------------------------------

def build_normalize_command(
    input_path: Path | str,
    output_path: Path | str,
    settings: dict,
    ffmpeg: str | None = None,
) -> list[str]:

    executable = ffmpeg or require_ffmpeg()

    source = validate_video(input_path)

    target = Path(output_path)

    config = validate_render_settings(settings)

    video_filter = _video_filter(
        config["width"],
        config["height"],
        config["fps"],
    )

    return [
        executable,
        "-y",
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-vf",
        video_filter,
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        config["video_preset"],
        "-crf",
        str(config["crf"]),
        "-threads",
        str(config["threads"]),
        "-movflags",
        "+faststart",
        str(target),
    ]


# ---------------------------------------------------------
# BUILD CONCAT FILE
# ---------------------------------------------------------

def write_concat_file(
    segment_paths: list[Path | str],
    output_path: Path | str,
) -> Path:

    if not segment_paths:
        raise ValueError("No normalized segments supplied.")

    destination = Path(output_path)
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    lines = []

    for item in segment_paths:

        path = Path(item).resolve()

        if not path.is_file():
            raise FileNotFoundError(path)

        # FFmpeg concat demuxer single-quote escaping.
        escaped = str(path).replace("'", "'\\''")

        lines.append(f"file '{escaped}'")

    destination.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    return destination


# ---------------------------------------------------------
# BUILD FINAL RENDER COMMAND
# ---------------------------------------------------------

def build_final_command(
    video_path: Path | str,
    output_path: Path | str,
    settings: dict,
    audio_files: list[str | Path] | None = None,
    subtitle_file: str | Path | None = None,
    ffmpeg: str | None = None,
) -> list[str]:

    executable = ffmpeg or require_ffmpeg()

    video = Path(video_path).resolve()

    if not video.is_file():
        raise FileNotFoundError(video)

    target = Path(output_path)

    config = validate_render_settings(settings)

    audio = [
        validate_audio(item)
        for item in (audio_files or [])
    ]

    subtitle = None

    if subtitle_file:
        subtitle = Path(subtitle_file).resolve()

        if not subtitle.is_file():
            raise FileNotFoundError(subtitle)

        if subtitle.suffix.lower() != ".srt":
            raise ValueError("Only SRT subtitle files are supported.")

    command = [
        executable,
        "-y",
        "-i",
        str(video),
    ]

    for audio_path in audio:
        command.extend([
            "-i",
            str(audio_path),
        ])

    filters = []
    audio_labels = []

    if config["include_audio"] and audio:

        for index, audio_path in enumerate(audio):

            input_index = index + 1
            label = f"a{index}"

            filters.append(
                f"[{input_index}:a]"
                "aresample=44100,"
                "aformat=sample_fmts=fltp:"
                "sample_rates=44100:"
                "channel_layouts=stereo,"
                f"[{label}]"
            )

            audio_labels.append(
                f"[{label}]"
            )

        if len(audio_labels) == 1:

            filters.append(
                f"{audio_labels[0]}"
                "anull[aout]"
            )

        else:

            inputs = "".join(audio_labels)

            filters.append(
                f"{inputs}"
                f"amix=inputs={len(audio_labels)}:"
                "duration=longest:"
                "dropout_transition=2:"
                "normalize=0,"
                "alimiter=limit=0.95"
                "[aout]"
            )

    video_filter = None

    if subtitle and config["burn_subtitles"]:

        escaped = _subtitle_filter_path(subtitle)

        video_filter = (
            f"subtitles=filename='{escaped}',"
            "format=yuv420p"
        )

    if filters:
        command.extend([
            "-filter_complex",
            ";".join(filters),
        ])

    command.extend([
        "-map",
        "0:v:0",
    ])

    if config["include_audio"] and audio:
        command.extend([
            "-map",
            "[aout]",
        ])
    else:
        command.append("-an")

    if video_filter:
        command.extend([
            "-vf",
            video_filter,
        ])

    command.extend([
        "-c:v",
        "libx264",
        "-preset",
        config["video_preset"],
        "-crf",
        str(config["crf"]),
        "-threads",
        str(config["threads"]),
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
    ])

    if config["include_audio"] and audio:
        command.extend([
            "-c:a",
            "aac",
            "-b:a",
            config["audio_bitrate"],
            "-ar",
            "44100",
        ])

    command.extend([
        "-progress",
        "pipe:1",
        "-nostats",
        str(target),
    ])

    return command


# ---------------------------------------------------------
# PROCESS EXECUTION
# ---------------------------------------------------------

def run_command(
    command: list[str],
    timeout: int | None = None,
) -> dict:

    try:

        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

    except subprocess.TimeoutExpired as exc:

        raise RuntimeError(
            "FFmpeg rendering timed out."
        ) from exc

    except OSError as exc:

        raise RuntimeError(
            f"Could not start FFmpeg: {exc}"
        ) from exc

    if process.returncode != 0:

        raise RuntimeError(
            "FFmpeg command failed:\n"
            + process.stderr[-5000:]
        )

    return {
        "returncode": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }


# ---------------------------------------------------------
# PROGRESS-AWARE EXECUTION
# ---------------------------------------------------------

def run_with_progress(
    command: list[str],
    duration: float = 0,
    progress_callback: Callable[[float], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> dict:

    """
    Run FFmpeg and parse its -progress output.

    The caller may provide a threading.Event to request
    cancellation. Cancellation terminates FFmpeg.
    """

    if not command:
        raise ValueError("FFmpeg command cannot be empty.")

    if duration < 0:
        raise ValueError("Duration cannot be negative.")

    try:

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

    except OSError as exc:
        raise RuntimeError(
            f"Could not start FFmpeg: {exc}"
        ) from exc

    progress = 0.0
    stderr_lines = []

    def read_stderr():
        if process.stderr:
            for line in process.stderr:
                stderr_lines.append(line)

                if len(stderr_lines) > 200:
                    del stderr_lines[:50]

    stderr_thread = threading.Thread(
        target=read_stderr,
        daemon=True,
    )

    stderr_thread.start()

    try:

        if process.stdout:

            for line in process.stdout:

                if cancel_event and cancel_event.is_set():
                    process.terminate()

                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()

                    raise RuntimeError(
                        "Rendering cancelled by user."
                    )

                line = line.strip()

                if line.startswith("out_time_ms="):

                    try:
                        milliseconds = int(
                            line.split("=", 1)[1]
                        )

                        if duration > 0:
                            progress = min(
                                99.0,
                                milliseconds / 1000
                                / duration * 100,
                            )

                            if progress_callback:
                                progress_callback(progress)

                    except ValueError:
                        pass

                elif line.startswith("progress="):
                    if line.endswith("end"):
                        progress = 100.0

                        if progress_callback:
                            progress_callback(100.0)

        return_code = process.wait()

        stderr_thread.join(timeout=2)

        if return_code != 0:

            raise RuntimeError(
                "FFmpeg rendering failed:\n"
                + "".join(stderr_lines)[-5000:]
            )

        return {
            "returncode": return_code,
            "progress": 100.0,
            "stderr": "".join(stderr_lines),
        }

    except Exception:

        if process.poll() is None:
            process.terminate()

            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

        raise


# ---------------------------------------------------------
# RENDER HISTORY
# ---------------------------------------------------------

def load_history(
    path: Path | str | None = None,
) -> list[dict]:

    history_path = Path(path) if path else HISTORY_FILE

    if not history_path.exists():
        return []

    try:

        data = json.loads(
            history_path.read_text(encoding="utf-8")
        )

        if isinstance(data, list):
            return data

        return []

    except (OSError, json.JSONDecodeError):
        return []


def save_history(
    history: list[dict],
    path: Path | str | None = None,
) -> None:

    history_path = Path(path) if path else HISTORY_FILE

    history_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = history_path.with_name(
        history_path.name + ".tmp"
    )

    temporary.write_text(
        json.dumps(
            history,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    temporary.replace(history_path)


def record_render(
    details: dict,
    path: Path | str | None = None,
) -> dict:

    history = load_history(path)

    record = {
        "id": _id(),
        "created_at": _now(),
        **details,
    }

    history.insert(0, record)

    save_history(history[:200], path)

    return record


# ---------------------------------------------------------
# MAIN RENDER PIPELINE
# ---------------------------------------------------------

def render_video(
    clips: list[str | Path],
    output_path: Path | str,
    settings: dict | None = None,
    audio_files: list[str | Path] | None = None,
    subtitle_file: str | Path | None = None,
    progress_callback: Callable[[float], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> dict:

    """
    Normalize video clips and concatenate them.

    The normalized segments are silent.
    Optional external audio files are mixed in the final stage.

    This pipeline currently uses hard cuts between clips.
    """

    ensure_directories()

    config = validate_render_settings(settings)

    inputs = validate_render_inputs(
        clips,
        audio_files,
        subtitle_file,
    )

    if subtitle_file and not config["burn_subtitles"]:
        raise ValueError(
            "Subtitle file supplied but burn_subtitles is disabled."
        )

    target = Path(output_path).expanduser().resolve()

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if target.suffix.lower() != ".mp4":
        raise ValueError("Output filename must end with .mp4.")

    if any(
        source == target
        for source in inputs["clips"] + inputs["audio_files"]
    ):
        raise ValueError(
            "Output path cannot overwrite an input file."
        )

    ffmpeg = require_ffmpeg()

    started = time.time()

    job_id = _id()

    segment_paths = []

    try:

        with tempfile.TemporaryDirectory(
            prefix="render_",
            dir=str(TEMP_DIR),
        ) as temporary_directory:

            working = Path(temporary_directory)

            # Stage 1: Normalize clips.
            for index, clip in enumerate(inputs["clips"]):

                if cancel_event and cancel_event.is_set():
                    raise RuntimeError(
                        "Rendering cancelled by user."
                    )

                segment = working / (
                    f"segment_{index:04d}.mp4"
                )

                command = build_normalize_command(
                    clip,
                    segment,
                    config,
                    ffmpeg,
                )

                run_command(
                    command,
                    timeout=None,
                )

                segment_paths.append(segment)

                if progress_callback:
                    progress_callback(
                        ((index + 1) / len(inputs["clips"])) * 40
                    )

            # Stage 2: Concatenate normalized clips.
            concat_file = write_concat_file(
                segment_paths,
                working / "concat.txt",
            )

            silent_video = working / "combined.mp4"

            concat_command = [
                ffmpeg,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(silent_video),
            ]

            run_command(concat_command)

            if progress_callback:
                progress_callback(50)

            # Stage 3: Determine final video duration.
            duration = 0.0

            if shutil.which("ffprobe"):

                try:
                    info = probe_media(silent_video)
                    duration = info["duration"]
                except Exception:
                    duration = 0.0

            # Stage 4: Final audio/subtitle render.
            final_command = build_final_command(
                silent_video,
                target,
                config,
                inputs["audio_files"],
                inputs["subtitle_file"],
                ffmpeg,
            )

            # Account for the initial clip normalization stage.
            def final_progress(value: float) -> None:
                if progress_callback:
                    progress_callback(
                        50 + value * 0.5
                    )

            result = run_with_progress(
                final_command,
                duration=duration,
                progress_callback=final_progress,
                cancel_event=cancel_event,
            )

        if not target.is_file() or target.stat().st_size == 0:
            raise RuntimeError(
                "FFmpeg completed without producing a valid output file."
            )

        output_info = {
            "output_path": str(target),
            "output_size_bytes": target.stat().st_size,
            "clip_count": len(inputs["clips"]),
            "audio_track_count": len(inputs["audio_files"]),
            "subtitle_burned": bool(
                inputs["subtitle_file"]
                and config["burn_subtitles"]
            ),
            "resolution": config["resolution"],
            "fps": config["fps"],
            "quality": config["quality"],
            "duration": duration,
        }

        record_render({
            "status": "completed",
            "job_id": job_id,
            "duration_seconds": round(
                time.time() - started,
                2,
            ),
            **output_info,
        })

        return {
            "success": True,
            "job_id": job_id,
            **output_info,
            "ffmpeg_stderr": result["stderr"][-2000:],
        }

    except Exception as exc:

        record_render({
            "status": "failed",
            "job_id": job_id,
            "error": str(exc),
            "duration_seconds": round(
                time.time() - started,
                2,
            ),
            "output_path": str(target),
        })

        raise


# ---------------------------------------------------------
# STREAMLIT UI
# ---------------------------------------------------------

def render(st: Any) -> None:

    ensure_directories()

    st.title("Professional Video Renderer")

    st.caption(
        "Render your videos locally using FFmpeg."
    )

    ffmpeg_info = detect_ffmpeg()

    if ffmpeg_info["installed"]:
        st.success(
            f"FFmpeg detected: {ffmpeg_info['version']}"
        )
    else:
        st.error(ffmpeg_info["error"])

        st.info(
            "Install FFmpeg and add its bin folder to PATH, "
            "then restart your terminal."
        )

    tab_render, tab_history, tab_settings = st.tabs([
        "Render Video",
        "Render History",
        "Settings",
    ])

    with tab_render:

        st.subheader("Select video clips")

        uploaded_videos = st.file_uploader(
            "Upload video clips",
            type=[
                "mp4",
                "mov",
                "mkv",
                "avi",
                "webm",
                "m4v",
            ],
            accept_multiple_files=True,
        )

        st.subheader("Audio tracks")

        uploaded_audio = st.file_uploader(
            "Upload background music or voice-over",
            type=[
                "mp3",
                "wav",
                "aac",
                "m4a",
                "ogg",
                "flac",
            ],
            accept_multiple_files=True,
        )

        st.subheader("Subtitle file")

        uploaded_subtitle = st.file_uploader(
            "Upload SRT subtitle file",
            type=["srt"],
        )

        st.subheader("Render configuration")

        col1, col2 = st.columns(2)

        with col1:

            resolution = st.selectbox(
                "Resolution",
                list(RESOLUTIONS.keys()),
                index=2,
            )

            fps = st.selectbox(
                "Frame rate",
                [24, 25, 30, 50, 60],
                index=0,
            )

        with col2:

            quality = st.selectbox(
                "Quality preset",
                list(QUALITY_PRESETS.keys()),
                index=0,
            )

            threads = st.slider(
                "CPU threads",
                1,
                8,
                2,
            )

        include_audio = st.checkbox(
            "Include uploaded audio",
            value=True,
        )

        burn_subtitles = st.checkbox(
            "Burn subtitles into video",
            value=uploaded_subtitle is not None,
            disabled=uploaded_subtitle is None,
        )

        output_name = st.text_input(
            "Output filename",
            value="final_video.mp4",
        )

        st.caption(
            "Clips are joined using hard cuts. "
            "Uploaded audio tracks are mixed together."
        )

        if st.button(
            "Start Rendering",
            type="primary",
            disabled=(
                not ffmpeg_info["installed"]
                or not uploaded_videos
            ),
        ):

            if not output_name.lower().endswith(".mp4"):
                output_name += ".mp4"

            if Path(output_name).name != output_name:
                st.error("Enter a filename only, without a folder path.")

            else:

                try:

                    ensure_directories()

                    job_folder = TEMP_DIR / (
                        "job_" + uuid.uuid4().hex[:10]
                    )

                    job_folder.mkdir(
                        parents=True,
                        exist_ok=False,
                    )

                    video_paths = []
                    audio_paths = []

                    for index, uploaded in enumerate(uploaded_videos):

                        destination = job_folder / (
                            f"video_{index:03d}"
                            + Path(uploaded.name).suffix.lower()
                        )

                        destination.write_bytes(
                            uploaded.getvalue()
                        )

                        video_paths.append(destination)

                    for index, uploaded in enumerate(uploaded_audio):

                        destination = job_folder / (
                            f"audio_{index:03d}"
                            + Path(uploaded.name).suffix.lower()
                        )

                        destination.write_bytes(
                            uploaded.getvalue()
                        )

                        audio_paths.append(destination)

                    subtitle_path = None

                    if uploaded_subtitle:

                        subtitle_path = job_folder / "subtitles.srt"

                        subtitle_path.write_bytes(
                            uploaded_subtitle.getvalue()
                        )

                    output_path = OUTPUT_DIR / output_name

                    settings = {
                        "resolution": resolution,
                        "fps": fps,
                        "quality": quality,
                        "threads": threads,
                        "include_audio": include_audio,
                        "burn_subtitles": burn_subtitles,
                    }

                    progress = st.progress(0)
                    status = st.empty()

                    status.info("Preparing rendering pipeline...")

                    def update_progress(value):
                        progress.progress(
                            min(100, int(value))
                        )

                    try:

                        result = render_video(
                            clips=video_paths,
                            output_path=output_path,
                            settings=settings,
                            audio_files=audio_paths,
                            subtitle_file=subtitle_path,
                            progress_callback=update_progress,
                        )

                        status.success("Video rendering completed.")

                        st.success(
                            f"Output created: {result['output_path']}"
                        )

                        st.json({
                            "resolution": result["resolution"],
                            "fps": result["fps"],
                            "clip_count": result["clip_count"],
                            "audio_track_count": result["audio_track_count"],
                            "size_bytes": result["output_size_bytes"],
                            "duration": result["duration"],
                        })

                        with output_path.open("rb") as file:
                            st.download_button(
                                "Download Rendered MP4",
                                data=file.read(),
                                file_name=output_path.name,
                                mime="video/mp4",
                            )

                    finally:
                        shutil.rmtree(
                            job_folder,
                            ignore_errors=True,
                        )

                except Exception as exc:
                    st.error(
                        f"Rendering failed: {exc}"
                    )

    with tab_history:

        st.subheader("Recent rendering jobs")

        history = load_history()

        if not history:
            st.info("No rendering history available.")

        for item in history[:30]:

            with st.container(border=True):

                st.write(
                    f"**{item.get('status', 'unknown').upper()}**"
                )

                st.caption(
                    item.get("created_at", "")
                )

                if item.get("output_path"):
                    st.text(item["output_path"])

                if item.get("error"):
                    st.error(item["error"])

    with tab_settings:

        st.subheader("Rendering presets")

        for name, preset in QUALITY_PRESETS.items():

            with st.container(border=True):
                st.write(f"**{name}**")
                st.write(
                    f"Encoder preset: {preset['preset']}"
                )
                st.write(
                    f"CRF: {preset['crf']}"
                )

        st.info(
            "For an 8 GB RAM CPU-only computer, start with "
            "480p or 720p and CPU Fast. 1080p rendering "
            "may take significantly longer."
        )


# ---------------------------------------------------------
# BUILT-IN TESTS
# ---------------------------------------------------------

def run_tests() -> bool:

    import unittest

    class VideoRendererTests(unittest.TestCase):

        def setUp(self):
            self.temp = tempfile.TemporaryDirectory()
            self.root = Path(self.temp.name)

        def tearDown(self):
            self.temp.cleanup()

        def make_file(self, name, content=b"test"):
            path = self.root / name
            path.write_bytes(content)
            return path

        def test_resolution(self):

            self.assertEqual(
                validate_resolution("1080p"),
                (1920, 1080),
            )

        def test_invalid_resolution(self):

            with self.assertRaises(ValueError):
                validate_resolution("9000p")

        def test_fps(self):

            self.assertEqual(
                validate_fps(30),
                30,
            )

        def test_invalid_fps(self):

            with self.assertRaises(ValueError):
                validate_fps(15)

        def test_settings(self):

            config = validate_render_settings({
                "resolution": "720p",
                "fps": 30,
                "quality": "CPU Fast",
                "threads": 2,
            })

            self.assertEqual(
                config["width"],
                1280,
            )

        def test_invalid_quality(self):

            with self.assertRaises(ValueError):
                validate_render_settings({
                    "quality": "Invalid",
                })

        def test_validate_video(self):

            video = self.make_file("test.mp4")

            self.assertEqual(
                validate_video(video),
                video.resolve(),
            )

        def test_reject_video_extension(self):

            file = self.make_file("test.exe")

            with self.assertRaises(ValueError):
                validate_video(file)

        def test_validate_audio(self):

            audio = self.make_file("music.mp3")

            self.assertEqual(
                validate_audio(audio),
                audio.resolve(),
            )

        def test_reject_audio_extension(self):

            audio = self.make_file("music.exe")

            with self.assertRaises(ValueError):
                validate_audio(audio)

        def test_concat_file(self):

            first = self.make_file("first.mp4")
            second = self.make_file("second.mp4")

            output = write_concat_file(
                [first, second],
                self.root / "concat.txt",
            )

            content = output.read_text(
                encoding="utf-8"
            )

            self.assertIn("first.mp4", content)
            self.assertIn("second.mp4", content)

        def test_concat_missing_file(self):

            with self.assertRaises(FileNotFoundError):
                write_concat_file(
                    [self.root / "missing.mp4"],
                    self.root / "concat.txt",
                )

        def test_history(self):

            history_path = self.root / "history.json"

            record = record_render(
                {"status": "completed"},
                history_path,
            )

            self.assertEqual(
                record["status"],
                "completed",
            )

            self.assertEqual(
                len(load_history(history_path)),
                1,
            )

        def test_subtitle_filter_path(self):

            subtitle = self.make_file(
                "my subtitle.srt"
            )

            escaped = _subtitle_filter_path(subtitle)

            self.assertIn("my subtitle.srt", escaped)

        def test_normalize_command(self):

            video = self.make_file("test.mp4")

            command = build_normalize_command(
                video,
                self.root / "output.mp4",
                {"resolution": "720p"},
                ffmpeg="ffmpeg",
            )

            self.assertIn("libx264", command)
            self.assertIn("1280", command)

        def test_final_command(self):

            video = self.make_file("combined.mp4")
            audio = self.make_file("music.mp3")

            command = build_final_command(
                video,
                self.root / "final.mp4",
                {"resolution": "720p"},
                audio_files=[audio],
                ffmpeg="ffmpeg",
            )

            self.assertIn("amix=inputs=1", " ".join(command))
            self.assertIn("libx264", command)

        def test_render_inputs(self):

            video = self.make_file("clip.mp4")
            audio = self.make_file("music.mp3")

            inputs = validate_render_inputs(
                [video],
                [audio],
            )

            self.assertEqual(len(inputs["clips"]), 1)
            self.assertEqual(len(inputs["audio_files"]), 1)

        def test_no_clips(self):

            with self.assertRaises(ValueError):
                validate_render_inputs([])

        def test_history_limit(self):

            history_path = self.root / "history.json"

            save_history(
                [{"id": str(i)} for i in range(250)],
                history_path,
            )

            self.assertEqual(
                len(load_history(history_path)),
                250,
            )

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        VideoRendererTests
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

    print("AI Influencer Studio - Video Renderer")
    print("Run tests:")
    print("python -m modules.video_renderer --test")

    info = detect_ffmpeg()

    print("FFmpeg installed:", info["installed"])

    if info["version"]:
        print("Version:", info["version"])
