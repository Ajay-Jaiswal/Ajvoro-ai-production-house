
"""
AI Influencer Studio
File 43: modules/video_effects.py

Local Cinematic Video Effects Studio.

Features:
- Brightness
- Contrast
- Saturation
- Gamma
- Sharpness
- Blur
- Vignette
- Grayscale
- Vintage look
- Cinematic color presets
- Slow motion and fast motion
- FFmpeg video processing
- Saved effect presets
- Streamlit interface
- Built-in tests

Requirements:
- FFmpeg installed and available in PATH.
- Python standard library only.

Run tests:
    python -m modules.video_effects --test
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import uuid

from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT_DIR / "data"
PRESET_FILE = DATA_DIR / "video_effect_presets.json"

OUTPUT_DIR = ROOT_DIR / "outputs" / "video_effects"
TEMP_DIR = ROOT_DIR / "temp" / "video_effects"


# ---------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------

VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".webm",
    ".m4v",
}

PRESETS = {
    "Original": {
        "brightness": 0.0,
        "contrast": 1.0,
        "saturation": 1.0,
        "gamma": 1.0,
        "sharpness": 0.0,
        "blur": 0.0,
        "vignette": 0.0,
        "grayscale": False,
        "vintage": False,
    },
    "Cinematic Teal Orange": {
        "brightness": 0.02,
        "contrast": 1.12,
        "saturation": 1.18,
        "gamma": 1.0,
        "sharpness": 0.15,
        "blur": 0.0,
        "vignette": 0.25,
        "grayscale": False,
        "vintage": False,
    },
    "Dark Horror": {
        "brightness": -0.08,
        "contrast": 1.25,
        "saturation": 0.72,
        "gamma": 1.15,
        "sharpness": 0.1,
        "blur": 0.0,
        "vignette": 0.65,
        "grayscale": False,
        "vintage": False,
    },
    "Fantasy Blue": {
        "brightness": 0.03,
        "contrast": 1.12,
        "saturation": 1.22,
        "gamma": 0.95,
        "sharpness": 0.2,
        "blur": 0.0,
        "vignette": 0.2,
        "grayscale": False,
        "vintage": False,
    },
    "Vintage Film": {
        "brightness": 0.03,
        "contrast": 0.92,
        "saturation": 0.72,
        "gamma": 1.05,
        "sharpness": 0.0,
        "blur": 0.0,
        "vignette": 0.35,
        "grayscale": False,
        "vintage": True,
    },
    "Black and White": {
        "brightness": 0.0,
        "contrast": 1.1,
        "saturation": 0.0,
        "gamma": 1.0,
        "sharpness": 0.0,
        "blur": 0.0,
        "vignette": 0.15,
        "grayscale": True,
        "vintage": False,
    },
}


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def make_id() -> str:
    return uuid.uuid4().hex[:12]


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)


def validate_video(path: str | Path) -> Path:

    source = Path(path).expanduser().resolve()

    if source.suffix.lower() not in VIDEO_EXTENSIONS:
        raise ValueError(
            f"Unsupported video extension: {source.suffix}"
        )

    if not source.is_file():
        raise FileNotFoundError(source)

    return source


def clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:

    number = float(value)

    return max(
        minimum,
        min(maximum, number),
    )


# ---------------------------------------------------------
# EFFECT VALIDATION
# ---------------------------------------------------------

DEFAULT_EFFECTS = {
    "brightness": 0.0,
    "contrast": 1.0,
    "saturation": 1.0,
    "gamma": 1.0,
    "sharpness": 0.0,
    "blur": 0.0,
    "vignette": 0.0,
    "grayscale": False,
    "vintage": False,
    "speed": 1.0,
}


def validate_effects(
    effects: dict | None = None,
) -> dict:

    effects = effects or {}

    if not isinstance(effects, dict):
        raise ValueError("Effects must be a dictionary.")

    result = dict(DEFAULT_EFFECTS)

    result.update(effects)

    result["brightness"] = clamp(
        result["brightness"],
        -1.0,
        1.0,
    )

    result["contrast"] = clamp(
        result["contrast"],
        0.0,
        3.0,
    )

    result["saturation"] = clamp(
        result["saturation"],
        0.0,
        3.0,
    )

    result["gamma"] = clamp(
        result["gamma"],
        0.1,
        3.0,
    )

    result["sharpness"] = clamp(
        result["sharpness"],
        0.0,
        2.0,
    )

    result["blur"] = clamp(
        result["blur"],
        0.0,
        10.0,
    )

    result["vignette"] = clamp(
        result["vignette"],
        0.0,
        1.0,
    )

    result["speed"] = clamp(
        result["speed"],
        0.25,
        4.0,
    )

    result["grayscale"] = bool(
        result["grayscale"]
    )

    result["vintage"] = bool(
        result["vintage"]
    )

    return result


# ---------------------------------------------------------
# PRESET MANAGEMENT
# ---------------------------------------------------------

def load_presets(
    path: Path | str | None = None,
) -> dict:

    source = Path(path) if path else PRESET_FILE

    if not source.exists():
        return {}

    try:

        data = json.loads(
            source.read_text(encoding="utf-8")
        )

        return data if isinstance(data, dict) else {}

    except (OSError, json.JSONDecodeError):
        return {}


def save_presets(
    presets: dict,
    path: Path | str | None = None,
) -> None:

    destination = Path(path) if path else PRESET_FILE

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = destination.with_name(
        destination.name + ".tmp"
    )

    temporary.write_text(
        json.dumps(
            presets,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    temporary.replace(destination)


def save_custom_preset(
    name: str,
    effects: dict,
    path: Path | str | None = None,
) -> dict:

    preset_name = str(name).strip()

    if not preset_name:
        raise ValueError("Preset name is required.")

    if len(preset_name) > 80:
        raise ValueError("Preset name is too long.")

    if preset_name in PRESETS:
        raise ValueError(
            "Built-in preset names cannot be overwritten."
        )

    presets = load_presets(path)

    preset = {
        "name": preset_name,
        "effects": validate_effects(effects),
        "created_at": now(),
    }

    presets[preset_name] = preset

    save_presets(presets, path)

    return preset


def delete_custom_preset(
    name: str,
    path: Path | str | None = None,
) -> bool:

    if name in PRESETS:
        raise ValueError(
            "Built-in presets cannot be deleted."
        )

    presets = load_presets(path)

    if name not in presets:
        return False

    del presets[name]

    save_presets(presets, path)

    return True


def get_preset(
    name: str,
    path: Path | str | None = None,
) -> dict:

    if name in PRESETS:
        return validate_effects(PRESETS[name])

    presets = load_presets(path)

    if name not in presets:
        raise ValueError("Preset not found.")

    return validate_effects(
        presets[name]["effects"]
    )


# ---------------------------------------------------------
# FILTER GENERATION
# ---------------------------------------------------------

def build_video_filter(
    effects: dict | None = None,
) -> str:

    config = validate_effects(effects)

    filters = []

    brightness = config["brightness"]
    contrast = config["contrast"]
    saturation = config["saturation"]
    gamma = config["gamma"]

    # Color adjustment.
    if (
        brightness != 0
        or contrast != 1
        or saturation != 1
    ):

        filters.append(
            "eq="
            f"brightness={brightness:.4f}:"
            f"contrast={contrast:.4f}:"
            f"saturation={saturation:.4f}"
        )

    # Gamma.
    if gamma != 1:
        filters.append(
            f"eq=gamma={gamma:.4f}"
        )

    # Sharpness.
    if config["sharpness"] > 0:

        amount = config["sharpness"]

        filters.append(
            "unsharp="
            f"5:5:{amount:.3f}:"
            "5:5:0.0"
        )

    # Blur.
    if config["blur"] > 0:

        sigma = config["blur"]

        filters.append(
            f"gblur=sigma={sigma:.3f}"
        )

    # Grayscale.
    if config["grayscale"]:

        filters.append(
            "hue=s=0"
        )

    # Vintage.
    if config["vintage"]:

        filters.append(
            "colorbalance="
            "rs=0.04:gs=0.01:bs=-0.03:"
            "rm=0.03:gm=0.01:bm=-0.02"
        )

    # Vignette.
    if config["vignette"] > 0:

        angle = (
            config["vignette"] * 1.2
        )

        filters.append(
            f"vignette=angle={angle:.4f}"
        )

    return ",".join(filters) if filters else "null"


# ---------------------------------------------------------
# SPEED CONTROL
# ---------------------------------------------------------

def build_speed_filters(
    speed: float,
) -> tuple[str, str]:

    value = clamp(
        speed,
        0.25,
        4.0,
    )

    video_filter = f"setpts={1 / value:.6f}*PTS"

    remaining = value
    audio_filters = []

    while remaining > 2.0:
        audio_filters.append("atempo=2.0")
        remaining /= 2.0

    while remaining < 0.5:
        audio_filters.append("atempo=0.5")
        remaining /= 0.5

    audio_filters.append(
        f"atempo={remaining:.6f}"
    )

    return (
        video_filter,
        ",".join(audio_filters),
    )


# ---------------------------------------------------------
# FFMPEG COMMAND
# ---------------------------------------------------------

def detect_ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


def build_effect_command(
    input_path: str | Path,
    output_path: str | Path,
    effects: dict | None = None,
    preset: str = "veryfast",
    crf: int = 23,
    include_audio: bool = True,
    ffmpeg: str | None = None,
) -> list[str]:

    executable = ffmpeg or detect_ffmpeg()

    if not executable:
        raise RuntimeError("FFmpeg was not found.")

    source = validate_video(input_path)

    target = Path(output_path).expanduser().resolve()

    if target.suffix.lower() != ".mp4":
        raise ValueError(
            "Output file must have an MP4 extension."
        )

    if target == source:
        raise ValueError(
            "Output cannot overwrite the original video."
        )

    allowed_presets = {
        "ultrafast",
        "superfast",
        "veryfast",
        "faster",
        "fast",
        "medium",
        "slow",
    }

    if preset not in allowed_presets:
        raise ValueError("Invalid encoder preset.")

    crf = int(crf)

    if not 0 <= crf <= 51:
        raise ValueError("CRF must be between 0 and 51.")

    config = validate_effects(effects)

    color_filter = build_video_filter(config)

    speed_video, speed_audio = build_speed_filters(
        config["speed"]
    )

    video_filters = []

    if color_filter != "null":
        video_filters.append(color_filter)

    if config["speed"] != 1:
        video_filters.append(speed_video)

    video_filter = ",".join(video_filters) or "null"

    command = [
        executable,
        "-y",
        "-i",
        str(source),
        "-vf",
        video_filter,
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-crf",
        str(crf),
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
    ]

    if include_audio:

        if config["speed"] != 1:

            command.extend([
                "-af",
                speed_audio,
            ])

        command.extend([
            "-c:a",
            "aac",
            "-b:a",
            "192k",
        ])

    else:
        command.append("-an")

    command.append(str(target))

    return command


# ---------------------------------------------------------
# APPLY EFFECTS
# ---------------------------------------------------------

def apply_effects(
    input_path: str | Path,
    output_path: str | Path,
    effects: dict | None = None,
    preset: str = "veryfast",
    crf: int = 23,
    include_audio: bool = True,
) -> dict:

    ensure_directories()

    command = build_effect_command(
        input_path=input_path,
        output_path=output_path,
        effects=effects,
        preset=preset,
        crf=crf,
        include_audio=include_audio,
    )

    target = Path(output_path).expanduser().resolve()

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:

        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=None,
        )

        if process.returncode != 0:

            raise RuntimeError(
                "FFmpeg effect processing failed:\n"
                + process.stderr[-4000:]
            )

        if not target.exists() or target.stat().st_size == 0:

            raise RuntimeError(
                "FFmpeg did not create a valid output file."
            )

        return {
            "success": True,
            "output_path": str(target),
            "size_bytes": target.stat().st_size,
            "effects": validate_effects(effects),
            "created_at": now(),
            "stderr": process.stderr[-2000:],
        }

    except subprocess.TimeoutExpired as exc:

        raise RuntimeError(
            "Video effect processing timed out."
        ) from exc


# ---------------------------------------------------------
# PREVIEW COMMAND
# ---------------------------------------------------------

def build_preview_command(
    input_path: str | Path,
    output_path: str | Path,
    effects: dict | None = None,
    duration: int = 10,
    ffmpeg: str | None = None,
) -> list[str]:

    executable = ffmpeg or detect_ffmpeg()

    if not executable:
        raise RuntimeError("FFmpeg was not found.")

    source = validate_video(input_path)

    target = Path(output_path).expanduser().resolve()

    duration = int(duration)

    if not 1 <= duration <= 60:
        raise ValueError(
            "Preview duration must be between 1 and 60 seconds."
        )

    config = validate_effects(effects)

    video_filter = build_video_filter(config)

    if config["speed"] != 1:

        speed_filter, _ = build_speed_filters(
            config["speed"]
        )

        video_filter = (
            speed_filter
            if video_filter == "null"
            else video_filter + "," + speed_filter
        )

    return [
        executable,
        "-y",
        "-i",
        str(source),
        "-t",
        str(duration),
        "-vf",
        video_filter,
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "32",
        "-pix_fmt",
        "yuv420p",
        str(target),
    ]


# ---------------------------------------------------------
# STREAMLIT UI
# ---------------------------------------------------------

def render(st: Any) -> None:

    ensure_directories()

    st.title("Cinematic Video Effects Studio")

    st.caption(
        "Apply cinematic effects to videos locally with FFmpeg."
    )

    ffmpeg = detect_ffmpeg()

    if ffmpeg:
        st.success("FFmpeg detected.")
    else:
        st.error(
            "FFmpeg not detected. Install FFmpeg before rendering."
        )

    uploaded = st.file_uploader(
        "Upload a video",
        type=[
            "mp4",
            "mov",
            "mkv",
            "avi",
            "webm",
            "m4v",
        ],
    )

    if uploaded is None:
        st.info("Upload a video to start editing.")
        return

    working = TEMP_DIR / (
        "source_" + uuid.uuid4().hex[:10]
    )

    working.mkdir(
        parents=True,
        exist_ok=True,
    )

    source = working / (
        "source" + Path(uploaded.name).suffix.lower()
    )

    source.write_bytes(
        uploaded.getvalue()
    )

    preset_options = (
        list(PRESETS.keys())
        + list(load_presets().keys())
    )

    selected_preset = st.selectbox(
        "Cinematic preset",
        preset_options,
    )

    base_effects = get_preset(selected_preset)

    st.subheader("Color correction")

    col1, col2 = st.columns(2)

    with col1:

        brightness = st.slider(
            "Brightness",
            -1.0,
            1.0,
            float(base_effects["brightness"]),
            0.01,
        )

        contrast = st.slider(
            "Contrast",
            0.0,
            3.0,
            float(base_effects["contrast"]),
            0.05,
        )

        saturation = st.slider(
            "Saturation",
            0.0,
            3.0,
            float(base_effects["saturation"]),
            0.05,
        )

        gamma = st.slider(
            "Gamma",
            0.1,
            3.0,
            float(base_effects["gamma"]),
            0.05,
        )

    with col2:

        sharpness = st.slider(
            "Sharpness",
            0.0,
            2.0,
            float(base_effects["sharpness"]),
            0.05,
        )

        blur = st.slider(
            "Blur",
            0.0,
            10.0,
            float(base_effects["blur"]),
            0.1,
        )

        vignette = st.slider(
            "Vignette",
            0.0,
            1.0,
            float(base_effects["vignette"]),
            0.05,
        )

        speed = st.select_slider(
            "Playback speed",
            options=[
                0.25,
                0.5,
                0.75,
                1.0,
                1.25,
                1.5,
                2.0,
                3.0,
                4.0,
            ],
            value=float(
                base_effects["speed"]
            ),
        )

    grayscale = st.checkbox(
        "Black and white",
        value=base_effects["grayscale"],
    )

    vintage = st.checkbox(
        "Vintage color look",
        value=base_effects["vintage"],
    )

    effects = validate_effects({
        "brightness": brightness,
        "contrast": contrast,
        "saturation": saturation,
        "gamma": gamma,
        "sharpness": sharpness,
        "blur": blur,
        "vignette": vignette,
        "speed": speed,
        "grayscale": grayscale,
        "vintage": vintage,
    })

    st.subheader("Save custom preset")

    with st.expander("Save current effect settings"):

        preset_name = st.text_input(
            "Preset name"
        )

        if st.button("Save Preset"):

            try:

                save_custom_preset(
                    preset_name,
                    effects,
                )

                st.success("Preset saved.")

            except Exception as exc:
                st.error(str(exc))

    st.subheader("Export settings")

    quality = st.selectbox(
        "Encoding quality",
        [
            "CPU Fast",
            "Balanced",
            "High Quality",
        ],
    )

    quality_config = {
        "CPU Fast": ("ultrafast", 28),
        "Balanced": ("veryfast", 23),
        "High Quality": ("medium", 20),
    }

    encoder_preset, crf = quality_config[quality]

    include_audio = st.checkbox(
        "Keep original audio",
        value=True,
    )

    output_name = st.text_input(
        "Output filename",
        value="cinematic_effects.mp4",
    )

    if st.button(
        "Render Video",
        type="primary",
        disabled=not ffmpeg,
    ):

        if Path(output_name).name != output_name:
            st.error("Enter only a filename.")
            return

        if not output_name.lower().endswith(".mp4"):
            output_name += ".mp4"

        target = OUTPUT_DIR / output_name

        try:

            with st.spinner(
                "Applying cinematic effects..."
            ):

                result = apply_effects(
                    input_path=source,
                    output_path=target,
                    effects=effects,
                    preset=encoder_preset,
                    crf=crf,
                    include_audio=include_audio,
                )

            st.success("Video rendered successfully.")

            st.write(
                f"Output: {result['output_path']}"
            )

            with target.open("rb") as file:

                st.download_button(
                    "Download MP4",
                    file.read(),
                    file_name=target.name,
                    mime="video/mp4",
                )

        except Exception as exc:
            st.error(str(exc))

    if st.button("Clean Temporary Upload"):
        shutil.rmtree(
            working,
            ignore_errors=True,
        )
        st.success("Temporary upload cleaned.")


# ---------------------------------------------------------
# BUILT-IN TESTS
# ---------------------------------------------------------

def run_tests() -> bool:

    import unittest

    class VideoEffectsTests(unittest.TestCase):

        def setUp(self):

            self.temp = tempfile.TemporaryDirectory()

            self.root = Path(self.temp.name)

            self.video = self.root / "test.mp4"

            self.video.write_bytes(b"video")

        def tearDown(self):
            self.temp.cleanup()

        def test_default_effects(self):

            config = validate_effects()

            self.assertEqual(
                config["contrast"],
                1.0,
            )

        def test_brightness_clamp(self):

            config = validate_effects({
                "brightness": 5,
            })

            self.assertEqual(
                config["brightness"],
                1.0,
            )

        def test_speed_clamp(self):

            config = validate_effects({
                "speed": 20,
            })

            self.assertEqual(
                config["speed"],
                4.0,
            )

        def test_invalid_effect_type(self):

            with self.assertRaises(ValueError):
                validate_effects("invalid")

        def test_filter_original(self):

            result = build_video_filter()

            self.assertEqual(result, "null")

        def test_filter_grayscale(self):

            result = build_video_filter({
                "grayscale": True,
            })

            self.assertIn(
                "hue=s=0",
                result,
            )

        def test_filter_blur(self):

            result = build_video_filter({
                "blur": 2,
            })

            self.assertIn(
                "gblur",
                result,
            )

        def test_filter_vignette(self):

            result = build_video_filter({
                "vignette": 0.5,
            })

            self.assertIn(
                "vignette",
                result,
            )

        def test_speed_filters(self):

            video_filter, audio_filter = (
                build_speed_filters(2)
            )

            self.assertIn(
                "setpts",
                video_filter,
            )

            self.assertIn(
                "atempo=2",
                audio_filter,
            )

        def test_slow_speed_filters(self):

            _, audio_filter = build_speed_filters(0.25)

            self.assertIn(
                "atempo=0.5",
                audio_filter,
            )

        def test_preset(self):

            result = get_preset(
                "Dark Horror"
            )

            self.assertLess(
                result["brightness"],
                0,
            )

        def test_custom_preset(self):

            preset_path = (
                self.root / "presets.json"
            )

            result = save_custom_preset(
                "My Look",
                {"contrast": 1.5},
                preset_path,
            )

            self.assertEqual(
                result["name"],
                "My Look",
            )

            self.assertEqual(
                get_preset(
                    "My Look",
                    preset_path,
                )["contrast"],
                1.5,
            )

        def test_delete_custom_preset(self):

            preset_path = (
                self.root / "presets.json"
            )

            save_custom_preset(
                "My Look",
                {},
                preset_path,
            )

            self.assertTrue(
                delete_custom_preset(
                    "My Look",
                    preset_path,
                )
            )

        def test_cannot_delete_builtin(self):

            with self.assertRaises(ValueError):
                delete_custom_preset(
                    "Original",
                    self.root / "presets.json",
                )

        def test_video_validation(self):

            self.assertEqual(
                validate_video(self.video),
                self.video.resolve(),
            )

        def test_invalid_video(self):

            bad = self.root / "bad.exe"

            bad.write_bytes(b"bad")

            with self.assertRaises(ValueError):
                validate_video(bad)

        def test_build_command(self):

            command = build_effect_command(
                self.video,
                self.root / "output.mp4",
                {"grayscale": True},
                ffmpeg="ffmpeg",
            )

            self.assertIn(
                "hue=s=0",
                " ".join(command),
            )

            self.assertIn(
                "libx264",
                command,
            )

        def test_prevent_overwrite(self):

            with self.assertRaises(ValueError):

                build_effect_command(
                    self.video,
                    self.video,
                    ffmpeg="ffmpeg",
                )

        def test_preview_command(self):

            command = build_preview_command(
                self.video,
                self.root / "preview.mp4",
                duration=5,
                ffmpeg="ffmpeg",
            )

            self.assertIn(
                "-t",
                command,
            )

            self.assertIn(
                "5",
                command,
            )

        def test_invalid_preview_duration(self):

            with self.assertRaises(ValueError):

                build_preview_command(
                    self.video,
                    self.root / "preview.mp4",
                    duration=100,
                    ffmpeg="ffmpeg",
                )

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        VideoEffectsTests
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

        raise SystemExit(
            0 if success else 1
        )

    print("AI Influencer Studio - Video Effects")

    print(
        "Run tests: "
        "python -m modules.video_effects --test"
    )

    print(
        "FFmpeg:",
        detect_ffmpeg() or "Not installed",
    )
