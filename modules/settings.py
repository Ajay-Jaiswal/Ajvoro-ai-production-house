
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------
# PROJECT PATHS
# ---------------------------------------------------------

MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parent

try:
    import config
except ImportError:
    config = None


def configured_path(attribute: str, fallback: Path) -> Path:
    """Read a path from config.py or use the project default."""
    value = getattr(config, attribute, fallback) if config else fallback
    return Path(value).expanduser().resolve()


BASE_DIR = configured_path("BASE_DIR", PROJECT_ROOT)
ASSETS_DIR = configured_path("ASSETS_DIR", BASE_DIR / "assets")
OUTPUT_DIR = configured_path("OUTPUT_DIR", BASE_DIR / "output")
TEMP_DIR = configured_path("TEMP_DIR", BASE_DIR / "temp")
ENGINES_DIR = configured_path("ENGINES_DIR", BASE_DIR / "engines")

CONFIGURED_MODELS_DIR = (
    getattr(config, "MODELS_DIR", ENGINES_DIR / "models")
    if config else ENGINES_DIR / "models"
)

MODELS_DIR = Path(CONFIGURED_MODELS_DIR).expanduser().resolve()

SETTINGS_FILE = BASE_DIR / "settings.json"


# ---------------------------------------------------------
# SETTINGS DEFAULTS AND VALIDATION
# ---------------------------------------------------------

ALLOWED_RESOLUTIONS = [
    "360p",
    "480p",
    "720p",
    "1080p",
]

MIN_RETENTION_HOURS = 1
MAX_RETENTION_HOURS = 24

DEFAULT_SETTINGS = {
    "cpu_only": True,
    "low_memory_mode": True,
    "preview_resolution": "480p",
    "worker_threads": 2,
    "preview_cache_mb": 128,
    "output_retention_hours": 1,
    "ffmpeg_path": shutil.which("ffmpeg") or "",
    "engines_dir": str(ENGINES_DIR),
    "models_dir": str(MODELS_DIR),
}


class SettingsError(Exception):
    """Raised when settings are invalid or cannot be persisted."""


def is_inside(path: Path, parent: Path) -> bool:
    """Check whether a resolved path is inside another directory."""
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except (ValueError, OSError):
        return False


def normalize_directory(value: Any, setting_name: str) -> str:
    """
    Validate a directory setting.

    Relative paths are resolved inside the project directory.
    Absolute paths may point to external model/engine folders.
    Missing directories are allowed, but are not automatically created.
    """
    if not isinstance(value, str):
        raise SettingsError(f"{setting_name} must be a text path.")

    value = value.strip()

    if not value:
        raise SettingsError(f"{setting_name} cannot be empty.")

    candidate = Path(value).expanduser()

    if not candidate.is_absolute():
        candidate = (BASE_DIR / candidate).resolve()

        if not is_inside(candidate, BASE_DIR):
            raise SettingsError(
                f"{setting_name} cannot use a relative path outside "
                "the project directory."
            )
    else:
        candidate = candidate.resolve()

    if candidate.exists() and not candidate.is_dir():
        raise SettingsError(
            f"{setting_name} points to a file, not a directory."
        )

    return str(candidate)


def normalize_settings(values: dict[str, Any]) -> dict[str, Any]:
    """Merge defaults and validate every supported setting."""
    if not isinstance(values, dict):
        raise SettingsError("Settings data must be a JSON object.")

    result = DEFAULT_SETTINGS.copy()
    result.update({
        key: value
        for key, value in values.items()
        if key in DEFAULT_SETTINGS
    })

    if not isinstance(result["cpu_only"], bool):
        raise SettingsError("CPU-only mode must be True or False.")

    if not isinstance(result["low_memory_mode"], bool):
        raise SettingsError("Low-memory mode must be True or False.")

    resolution = result["preview_resolution"]

    if resolution not in ALLOWED_RESOLUTIONS:
        raise SettingsError(
            f"Invalid preview resolution: {resolution}"
        )

    threads = result["worker_threads"]

    if (
        isinstance(threads, bool)
        or not isinstance(threads, int)
        or not 1 <= threads <= 32
    ):
        raise SettingsError("Worker threads must be between 1 and 32.")

    cache_mb = result["preview_cache_mb"]

    if (
        isinstance(cache_mb, bool)
        or not isinstance(cache_mb, int)
        or not 32 <= cache_mb <= 2048
    ):
        raise SettingsError("Preview cache must be between 32 and 2048 MB.")

    retention = result["output_retention_hours"]

    if (
        isinstance(retention, bool)
        or not isinstance(retention, int)
        or not MIN_RETENTION_HOURS <= retention <= MAX_RETENTION_HOURS
    ):
        raise SettingsError(
            "Output retention must be between 1 and 24 hours."
        )

    ffmpeg_path = result["ffmpeg_path"]

    if not isinstance(ffmpeg_path, str):
        raise SettingsError("FFmpeg path must be text.")

    if len(ffmpeg_path) > 2048:
        raise SettingsError("FFmpeg path is too long.")

    result["ffmpeg_path"] = ffmpeg_path.strip()

    result["engines_dir"] = normalize_directory(
        result["engines_dir"],
        "Engine directory"
    )

    result["models_dir"] = normalize_directory(
        result["models_dir"],
        "Model directory"
    )

    return result


# ---------------------------------------------------------
# SAFE JSON PERSISTENCE
# ---------------------------------------------------------

def safe_settings_target(settings_file: Path | str) -> Path:
    """Prepare a settings filename without following a file symlink."""
    requested = Path(settings_file).expanduser()

    if not requested.is_absolute():
        requested = BASE_DIR / requested

    if requested.is_symlink():
        raise SettingsError("Refusing to write through a settings symlink.")

    parent = requested.parent.resolve()
    target = parent / requested.name

    if target.exists() and target.is_symlink():
        raise SettingsError("Settings file cannot be a symbolic link.")

    if not target.name:
        raise SettingsError("Invalid settings filename.")

    return target


def load_settings(
    settings_file: Path | str = SETTINGS_FILE
) -> dict[str, Any]:
    """Load saved settings, or return defaults on first launch."""
    target = safe_settings_target(settings_file)

    if not target.exists():
        return normalize_settings(DEFAULT_SETTINGS)

    try:
        raw = json.loads(target.read_text(encoding="utf-8"))

    except json.JSONDecodeError as exc:
        raise SettingsError(
            f"Settings JSON is invalid: {exc}"
        ) from exc

    except OSError as exc:
        raise SettingsError(
            f"Could not read settings: {exc}"
        ) from exc

    return normalize_settings(raw)


def save_settings(
    values: dict[str, Any],
    settings_file: Path | str = SETTINGS_FILE
) -> dict[str, Any]:
    """
    Validate and atomically save settings.

    The temporary file is created beside the destination so os.replace()
    can perform an atomic replacement on the same filesystem.
    """
    validated = normalize_settings(values)
    target = safe_settings_target(settings_file)

    temporary_name = None

    try:
        target.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=target.parent,
            prefix=target.name + ".",
            suffix=".tmp",
            delete=False
        ) as temporary:
            temporary_name = temporary.name

            json.dump(
                validated,
                temporary,
                indent=4,
                ensure_ascii=False
            )

            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())

        os.replace(temporary_name, target)
        temporary_name = None

        return validated

    except (OSError, TypeError, ValueError) as exc:
        raise SettingsError(
            f"Could not save settings: {exc}"
        ) from exc

    finally:
        if temporary_name:
            try:
                Path(temporary_name).unlink(missing_ok=True)
            except OSError:
                pass


def get_output_retention_seconds(
    settings_file: Path | str = SETTINGS_FILE
) -> int:
    """Provide the configured retention duration for storage.py."""
    try:
        values = load_settings(settings_file)
        return values["output_retention_hours"] * 3600
    except (SettingsError, OSError):
        return 3600


# ---------------------------------------------------------
# FFMPEG DETECTION
# ---------------------------------------------------------

def resolve_ffmpeg(executable: str | None = None) -> str | None:
    """
    Find FFmpeg using a configured path or the system PATH.

    No shell command is used.
    """
    candidate = (executable or "").strip()

    if candidate:
        found = shutil.which(candidate)

        if found:
            return str(Path(found).resolve())

        path = Path(candidate).expanduser()

        if path.is_file():
            return str(path.resolve())

    found = shutil.which("ffmpeg")

    if found:
        return str(Path(found).resolve())

    return None


def probe_ffmpeg(executable: str | None = None) -> dict[str, Any]:
    """Check that FFmpeg launches and return its version line."""
    resolved = resolve_ffmpeg(executable)

    if not resolved:
        return {
            "available": False,
            "path": None,
            "version": None,
            "message": "FFmpeg was not found."
        }

    try:
        result = subprocess.run(
            [resolved, "-version"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
            shell=False
        )

        if result.returncode != 0:
            return {
                "available": False,
                "path": resolved,
                "version": None,
                "message": "FFmpeg was found but its version check failed."
            }

        first_line = (
            result.stdout.strip().splitlines()[0]
            if result.stdout.strip()
            else "FFmpeg version information unavailable."
        )

        return {
            "available": True,
            "path": resolved,
            "version": first_line,
            "message": "FFmpeg is ready."
        }

    except subprocess.TimeoutExpired:
        message = "FFmpeg version check timed out."

    except OSError as exc:
        message = f"Could not execute FFmpeg: {exc}"

    return {
        "available": False,
        "path": resolved,
        "version": None,
        "message": message
    }


# ---------------------------------------------------------
# STORAGE INFORMATION
# ---------------------------------------------------------

def format_bytes(size: int) -> str:
    """Convert bytes into a readable size."""
    value = float(max(0, size))

    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.2f} {unit}"
        value /= 1024

    return f"{value:.2f} TB"


def directory_usage(directory: Path) -> dict[str, Any]:
    """
    Calculate directory usage without loading file contents into memory.

    Symlinks are skipped to avoid following paths outside the directory.
    """
    directory = Path(directory).expanduser()

    total_bytes = 0
    file_count = 0
    error_count = 0

    if not directory.exists() or not directory.is_dir():
        return {
            "exists": False,
            "files": 0,
            "bytes": 0,
            "errors": 0
        }

    for current_root, dir_names, file_names in os.walk(
        directory,
        followlinks=False
    ):
        current = Path(current_root)

        dir_names[:] = [
            name for name in dir_names
            if not (current / name).is_symlink()
        ]

        for filename in file_names:
            path = current / filename

            if path.is_symlink():
                continue

            try:
                if path.is_file():
                    total_bytes += path.stat().st_size
                    file_count += 1
            except OSError:
                error_count += 1

    return {
        "exists": True,
        "files": file_count,
        "bytes": total_bytes,
        "errors": error_count
    }


def get_storage_report() -> dict[str, dict[str, Any]]:
    """Return storage statistics for persistent and temporary folders."""
    return {
        "Persistent assets": directory_usage(ASSETS_DIR),
        "Generated outputs": directory_usage(OUTPUT_DIR),
        "Temporary files": directory_usage(TEMP_DIR),
        "Engine files": directory_usage(ENGINES_DIR),
        "Model files": directory_usage(MODELS_DIR),
    }


# ---------------------------------------------------------
# STREAMLIT HELPERS
# ---------------------------------------------------------

def show_directory_status(st, label: str, value: str) -> None:
    """Display whether a configured directory currently exists."""
    path = Path(value).expanduser()

    if path.is_dir():
        st.success(f"{label}: Directory exists")
    elif path.exists():
        st.error(f"{label}: Path exists but is not a directory")
    else:
        st.warning(
            f"{label}: Directory does not exist yet. "
            "Save the path after creating the folder."
        )

    st.caption(str(path))


def render_ffmpeg_section(st, settings: dict[str, Any]) -> None:
    """Display FFmpeg information and auto-detection."""
    st.subheader("FFmpeg")

    configured = settings.get("ffmpeg_path", "")

    if st.button("Auto-detect FFmpeg", key="settings_detect_ffmpeg"):
        found = resolve_ffmpeg()

        if found:
            updated = settings.copy()
            updated["ffmpeg_path"] = found

            try:
                save_settings(updated)
                st.success("FFmpeg path detected and saved.")
                st.rerun()
            except SettingsError as exc:
                st.error(str(exc))
        else:
            st.warning(
                "FFmpeg was not found in PATH. Install FFmpeg or enter "
                "the full path to ffmpeg.exe."
            )

    probe = probe_ffmpeg(configured)

    if probe["available"]:
        st.success(probe["message"])
        st.caption(probe["version"])
        st.code(probe["path"])
    else:
        st.warning(probe["message"])

    st.caption(
        "Common Windows example: C:\\ffmpeg\\bin\\ffmpeg.exe"
    )


def render_storage_section(st, settings: dict[str, Any]) -> None:
    """Show persistent and temporary storage usage."""
    st.subheader("Storage Usage")

    report = get_storage_report()

    columns = st.columns(3)

    visible_items = [
        "Persistent assets",
        "Generated outputs",
        "Temporary files"
    ]

    for index, label in enumerate(visible_items):
        data = report[label]

        with columns[index]:
            st.metric(label, format_bytes(data["bytes"]))
            st.caption(f"{data['files']} files")

    with st.expander("Detailed storage information"):
        for label, data in report.items():
            st.markdown(f"**{label}**")

            if not data["exists"]:
                st.caption("Directory does not exist.")
                continue

            st.write(
                f"Files: {data['files']} | "
                f"Size: {format_bytes(data['bytes'])} | "
                f"Read errors: {data['errors']}"
            )

    retention_seconds = get_output_retention_seconds()

    st.info(
        f"Configured output retention: "
        f"{retention_seconds // 3600} hour(s)."
    )

    st.caption(
        "Changing this setting updates settings.json. For the new value "
        "to control actual file deletion, storage.py must read "
        "get_output_retention_seconds() when performing cleanup."
    )


# ---------------------------------------------------------
# SETTINGS PAGE
# ---------------------------------------------------------

def render(st) -> None:
    """Main entry point called by app.py."""
    st.title("Application Settings")
    st.write(
        "Configure local performance, preview quality, FFmpeg, "
        "model folders and output retention."
    )

    try:
        settings = load_settings()
    except SettingsError as exc:
        st.error(str(exc))
        st.info(
            "Check settings.json. The module will not overwrite a "
            "corrupted settings file automatically."
        )
        return

    st.subheader("Performance Settings")

    with st.form("application_settings_form"):
        cpu_only = st.checkbox(
            "CPU-only mode",
            value=settings["cpu_only"],
            help=(
                "Requests CPU execution from engines that support "
                "this setting. It does not automatically configure "
                "every external AI model."
            )
        )

        low_memory = st.checkbox(
            "Low-memory mode",
            value=settings["low_memory_mode"],
            help=(
                "A preference for modules to use smaller previews, "
                "fewer workers and reduced caching."
            )
        )

        resolution = st.selectbox(
            "Preview resolution",
            ALLOWED_RESOLUTIONS,
            index=ALLOWED_RESOLUTIONS.index(
                settings["preview_resolution"]
            )
        )

        worker_threads = st.number_input(
            "Worker threads",
            min_value=1,
            max_value=32,
            value=settings["worker_threads"],
            step=1,
            help="Use fewer threads on low-memory computers."
        )

        cache_mb = st.number_input(
            "Preview cache limit (MB)",
            min_value=32,
            max_value=2048,
            value=settings["preview_cache_mb"],
            step=32
        )

        st.divider()
        st.subheader("Output Retention")

        retention_hours = st.number_input(
            "Delete generated outputs after (hours)",
            min_value=MIN_RETENTION_HOURS,
            max_value=MAX_RETENTION_HOURS,
            value=settings["output_retention_hours"],
            step=1,
            help=(
                "Default is one hour. This value is persisted locally. "
                "storage.py must read it for cleanup to use it."
            )
        )

        st.divider()
        st.subheader("Engine and Model Directories")

        engines_dir = st.text_input(
            "Engine directory",
            value=settings["engines_dir"]
        )

        models_dir = st.text_input(
            "Model directory",
            value=settings["models_dir"]
        )

        st.divider()
        st.subheader("FFmpeg Configuration")

        ffmpeg_path = st.text_input(
            "FFmpeg executable path",
            value=settings["ffmpeg_path"],
            placeholder="C:\\ffmpeg\\bin\\ffmpeg.exe"
        )

        submitted = st.form_submit_button(
            "Save Settings",
            type="primary"
        )

        if submitted:
            new_settings = {
                "cpu_only": cpu_only,
                "low_memory_mode": low_memory,
                "preview_resolution": resolution,
                "worker_threads": int(worker_threads),
                "preview_cache_mb": int(cache_mb),
                "output_retention_hours": int(retention_hours),
                "engines_dir": engines_dir,
                "models_dir": models_dir,
                "ffmpeg_path": ffmpeg_path,
            }

            try:
                save_settings(new_settings)
                st.success("Settings saved successfully.")
                st.rerun()

            except SettingsError as exc:
                st.error(str(exc))

    st.divider()

    st.subheader("Configured Directory Status")

    col1, col2 = st.columns(2)

    with col1:
        show_directory_status(
            st,
            "Engine directory",
            settings["engines_dir"]
        )

    with col2:
        show_directory_status(
            st,
            "Model directory",
            settings["models_dir"]
        )

    st.divider()

    render_ffmpeg_section(st, settings)

    st.divider()

    render_storage_section(st, settings)

    with st.expander("Settings file location"):
        st.code(str(SETTINGS_FILE))
        st.caption(
            "The settings file is persistent. It is not stored in the "
            "one-hour temporary output directory."
        )


# ---------------------------------------------------------
# SELF-TESTS
# ---------------------------------------------------------

class SettingsModuleTests(unittest.TestCase):
    """Tests for persistence, validation and path safety."""

    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.test_root = Path(self.temp_directory.name)
        self.test_file = self.test_root / "test_settings.json"

    def tearDown(self):
        self.temp_directory.cleanup()

    def test_default_settings(self):
        values = normalize_settings({})
        self.assertEqual(values["output_retention_hours"], 1)
        self.assertTrue(values["cpu_only"])
        self.assertTrue(values["low_memory_mode"])

    def test_save_and_load(self):
        values = DEFAULT_SETTINGS.copy()
        values["output_retention_hours"] = 3
        values["preview_resolution"] = "720p"

        save_settings(values, self.test_file)
        loaded = load_settings(self.test_file)

        self.assertEqual(loaded["output_retention_hours"], 3)
        self.assertEqual(loaded["preview_resolution"], "720p")

    def test_retention_seconds(self):
        values = DEFAULT_SETTINGS.copy()
        values["output_retention_hours"] = 2

        save_settings(values, self.test_file)

        self.assertEqual(
            get_output_retention_seconds(self.test_file),
            7200
        )

    def test_invalid_retention_rejected(self):
        values = DEFAULT_SETTINGS.copy()
        values["output_retention_hours"] = 100

        with self.assertRaises(SettingsError):
            normalize_settings(values)

    def test_invalid_resolution_rejected(self):
        values = DEFAULT_SETTINGS.copy()
        values["preview_resolution"] = "12K"

        with self.assertRaises(SettingsError):
            normalize_settings(values)

    def test_invalid_worker_threads_rejected(self):
        values = DEFAULT_SETTINGS.copy()
        values["worker_threads"] = 0

        with self.assertRaises(SettingsError):
            normalize_settings(values)

    def test_invalid_boolean_rejected(self):
        values = DEFAULT_SETTINGS.copy()
        values["cpu_only"] = "yes"

        with self.assertRaises(SettingsError):
            normalize_settings(values)

    def test_relative_path_traversal_rejected(self):
        values = DEFAULT_SETTINGS.copy()
        values["engines_dir"] = "../../outside_project"

        with self.assertRaises(SettingsError):
            normalize_settings(values)

    def test_corrupted_json_rejected(self):
        self.test_file.write_text(
            "{invalid json",
            encoding="utf-8"
        )

        with self.assertRaises(SettingsError):
            load_settings(self.test_file)

    def test_directory_usage(self):
        sample = self.test_root / "sample.txt"
        sample.write_text("hello", encoding="utf-8")

        report = directory_usage(self.test_root)

        self.assertTrue(report["exists"])
        self.assertEqual(report["files"], 1)
        self.assertEqual(report["bytes"], 5)


def run_self_tests() -> bool:
    """Run all built-in tests and return success/failure."""
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        SettingsModuleTests
    )

    result = unittest.TextTestRunner(verbosity=2).run(suite)

    return result.wasSuccessful()


# ---------------------------------------------------------
# OPTIONAL STANDALONE EXECUTION
# ---------------------------------------------------------

if __name__ == "__main__":
    if "--self-test" in sys.argv:
        success = run_self_tests()
        sys.exit(0 if success else 1)

    try:
        import streamlit as st

        st.set_page_config(
            page_title="AI Influencer Studio - Settings",
            layout="wide"
        )

        render(st)

    except ImportError:
        print("Streamlit is not installed.")
        print("Install it with: pip install streamlit")
        sys.exit(1)
