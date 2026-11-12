"""Lightweight FFmpeg-based video editor for AI Influencer Studio.

Provides real trim, crop/pad, resize, optional background music and subtitles
when FFmpeg supports the requested filters. It does not provide AI editing,
scene understanding, face tracking, generative effects, or automatic captions.
"""
from __future__ import annotations

import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

import config
import storage

VIDEO_TYPES = {"mp4", "mov", "mkv", "webm", "avi"}
AUDIO_TYPES = {"mp3", "wav", "m4a", "aac", "ogg", "flac"}
ASPECTS = {"16:9": (16, 9), "9:16": (9, 16), "1:1": (1, 1)}
RESOLUTIONS = {"480p": 480, "720p": 720, "1080p": 1080}


def ffmpeg_path() -> str | None:
    """Return the FFmpeg executable if it is available on PATH."""
    return shutil.which("ffmpeg")


def ffprobe_path() -> str | None:
    return shutil.which("ffprobe")


def _safe_asset_dir() -> Path:
    root = Path(config.ASSETS_DIR).resolve() / "video_editor"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _save_upload(upload: Any, allowed: set[str], label: str) -> Path:
    if upload is None:
        raise ValueError(f"Please upload a {label}.")
    suffix = Path(getattr(upload, "name", "")).suffix.lower().lstrip(".")
    if suffix not in allowed:
        raise ValueError(f"Unsupported {label} format: {suffix or 'unknown'}.")
    data = upload.getvalue()
    if not data:
        raise ValueError(f"The {label} file is empty.")
    # Avoid unexpectedly large uploads on low-memory machines.
    if len(data) > 500 * 1024 * 1024:
        raise ValueError(f"{label.title()} upload exceeds the 500 MB limit.")
    destination = _safe_asset_dir() / f"{uuid.uuid4().hex}.{suffix}"
    destination.write_bytes(data)
    return destination


def _probe_duration(path: Path) -> float | None:
    exe = ffprobe_path()
    if not exe:
        return None
    result = subprocess.run(
        [exe, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if result.returncode != 0:
        return None
    try:
        value = float(result.stdout.strip())
        return value if value > 0 else None
    except (TypeError, ValueError):
        return None


def build_ffmpeg_command(
    *, input_video: Path, output_video: Path, start_seconds: float,
    end_seconds: float, aspect: str, resolution: str,
    output_format: str, music_path: Path | None = None,
    subtitle_path: Path | None = None,
) -> list[str]:
    """Build an FFmpeg command; does not execute it."""
    if aspect not in ASPECTS:
        raise ValueError("Choose a supported aspect ratio.")
    if resolution not in RESOLUTIONS:
        raise ValueError("Choose 480p, 720p or 1080p.")
    extension = output_format.lower().lstrip(".")
    if extension not in {"mp4", "mkv", "webm"}:
        raise ValueError("Output format must be MP4, MKV or WEBM.")
    start, end = float(start_seconds), float(end_seconds)
    if start < 0 or end <= start:
        raise ValueError("End time must be greater than a non-negative start time.")

    width_ratio, height_ratio = ASPECTS[aspect]
    height = RESOLUTIONS[resolution]
    width = int(round(height * width_ratio / height_ratio / 2) * 2)
    # Fit the full frame inside the selected canvas, padding rather than
    # cropping away content. This is predictable and avoids destructive crops.
    filters = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease:"
        f"force_divisible_by=2,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1"
    )
    if subtitle_path is not None:
        # The SRT file path is generated internally and escaped for FFmpeg filter syntax.
        sub = str(subtitle_path.resolve()).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
        filters += f",subtitles='{sub}'"

    command = [ffmpeg_path() or "ffmpeg", "-hide_banner", "-y", "-ss", str(start),
               "-i", str(input_video)]
    if music_path is not None:
        command += ["-stream_loop", "-1", "-i", str(music_path)]
    command += ["-t", str(end - start), "-vf", filters]
    if music_path is not None:
        command += ["-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac",
                    "-shortest", "-af", "volume=0.25"]
    else:
        command += ["-map", "0:v:0", "-map", "0:a?", "-c:a", "aac"]
    command += ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
                "-threads", "2", "-pix_fmt", "yuv420p"]
    if extension == "webm":
        # Use VP9 for WebM; keep a small thread count for CPU-only systems.
        command[command.index("libx264")] = "libvpx-vp9"
        command[command.index("-crf") + 1] = "35"
        command[command.index("-pix_fmt"):command.index("-pix_fmt") + 2] = ["-threads", "2"]
    command += [str(output_video)]
    return command


def render(app: Any) -> None:
    app.title("Video Editor Studio")
    app.caption("Local FFmpeg editing: trim, resize, aspect ratio, music and subtitles.")
    exe = ffmpeg_path()
    if not exe:
        app.error("FFmpeg was not found on PATH. Install FFmpeg and restart Streamlit to enable editing.")
        app.code("ffmpeg -version", language="powershell")
        app.info("Uploads and workflow preparation are available only after FFmpeg is installed and detected.")
        return
    app.success(f"FFmpeg detected: {exe}")

    video_upload = app.file_uploader("Upload source video", type=sorted(VIDEO_TYPES), key="ve_video")
    if not video_upload:
        app.info("Upload a video to begin.")
        _show_outputs(app)
        return
    try:
        video_path = _save_upload(video_upload, VIDEO_TYPES, "video")
    except ValueError as exc:
        app.error(str(exc))
        return
    app.video(str(video_path))
    duration = _probe_duration(video_path)
    if duration is None:
        app.warning("Could not read video duration with ffprobe. Install FFprobe (normally bundled with FFmpeg).")
        duration = 60.0
    app.caption(f"Detected duration: {duration:.2f} seconds" if _probe_duration(video_path) else "Duration estimate: 60 seconds; verify trim values.")

    c1, c2 = app.columns(2)
    with c1:
        start = app.number_input("Trim start (seconds)", min_value=0.0, max_value=float(duration), value=0.0, step=0.5)
    with c2:
        end = app.number_input("Trim end (seconds)", min_value=0.1, max_value=max(0.1, float(duration)), value=float(duration), step=0.5)
    aspect = app.selectbox("Aspect ratio", list(ASPECTS))
    resolution = app.selectbox("Resolution", list(RESOLUTIONS), index=1)
    output_format = app.selectbox("Output format", ["mp4", "mkv", "webm"])
    music_upload = app.file_uploader("Optional background music", type=sorted(AUDIO_TYPES), key="ve_music")
    music_path = None
    if music_upload:
        try:
            music_path = _save_upload(music_upload, AUDIO_TYPES, "audio")
        except ValueError as exc:
            app.error(str(exc))
            return
        app.audio(music_upload.getvalue())
    subtitle_text = app.text_area("Optional subtitles (displayed for the full trimmed clip)", max_chars=2000,
                                  placeholder="Enter subtitle text...")
    app.caption("Subtitles are burned in using FFmpeg's subtitles filter; this requires an FFmpeg build with libass.")

    if app.button("Render edited video", type="primary", use_container_width=True):
        if end <= start:
            app.error("Trim end must be greater than trim start.")
            return
        subtitle_path = None
        output_path = Path(config.OUTPUT_DIR).resolve() / f"edited_{uuid.uuid4().hex}.{output_format}"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if subtitle_text.strip():
                # SRT timestamps span the entire resulting clip.
                seconds = max(1, int(end - start))
                hh, rem = divmod(seconds, 3600)
                mm, ss = divmod(rem, 60)
                timestamp = f"{hh:02}:{mm:02}:{ss:02},000"
                subtitle_path = Path(config.TEMP_DIR).resolve() / f"subtitle_{uuid.uuid4().hex}.srt"
                subtitle_path.parent.mkdir(parents=True, exist_ok=True)
                safe_text = subtitle_text.strip().replace("\r", " ").replace("\n", " ")
                subtitle_path.write_text(f"1\n00:00:00,000 --> {timestamp}\n{safe_text}\n", encoding="utf-8-sig")
            command = build_ffmpeg_command(
                input_video=video_path, output_video=output_path,
                start_seconds=start, end_seconds=end, aspect=aspect,
                resolution=resolution, output_format=output_format,
                music_path=music_path, subtitle_path=subtitle_path,
            )
            with app.spinner("FFmpeg is rendering your video. CPU rendering may take time..."):
                result = subprocess.run(command, capture_output=True, text=True, timeout=7200, check=False)
            if result.returncode != 0 or not output_path.is_file() or output_path.stat().st_size == 0:
                raise RuntimeError((result.stderr or result.stdout or "FFmpeg failed.")[-3000:])
            registered = storage.register_output(output_path)
            app.success("Video rendered and registered for one-hour retention.")
            app.video(str(output_path))
            app.download_button("Download edited video", output_path.read_bytes(), file_name=output_path.name)
            app.caption(f"Registered output: {registered}")
        except subprocess.TimeoutExpired:
            output_path.unlink(missing_ok=True)
            app.error("Rendering exceeded the two-hour safety limit.")
        except Exception as exc:
            output_path.unlink(missing_ok=True)
            app.error(f"Video rendering failed: {exc}")
        finally:
            if subtitle_path:
                subtitle_path.unlink(missing_ok=True)

    app.warning("This module performs conventional FFmpeg editing only. AI scene detection, face tracking, generative effects, auto-reframing and AI captions are not implemented.")
    _show_outputs(app)


def _show_outputs(app: Any) -> None:
    app.subheader("Recent edited videos")
    try:
        items = [x for x in storage.list_outputs() if Path(x["name"]).name.startswith("edited_")]
        if not items:
            app.info("No edited videos registered yet.")
            return
        for item in items:
            path = Path(item["path"])
            app.caption(f"{item['name']} — expires in {item['remaining_seconds']} seconds")
            if path.is_file():
                app.video(str(path))
    except Exception as exc:
        app.warning(f"Could not list registered outputs: {exc}")
