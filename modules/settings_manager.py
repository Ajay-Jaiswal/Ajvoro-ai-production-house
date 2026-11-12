
"""
AI Influencer Studio - Settings Manager
File 22: modules/settings_manager.py

Features:
- Persistent JSON settings
- General, AI, video, voice, storage and performance preferences
- Validation and safe defaults
- Import and export settings
- Streamlit settings dashboard
- Built-in tests

Run tests:
    python -m modules.settings_manager --test

Integration:
    from modules import settings_manager
    settings_manager.render(st)
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import tempfile
from pathlib import Path
from typing import Any


DEFAULT_SETTINGS = {
    "general": {
        "studio_name": "AI Influencer Studio",
        "theme": "Dark",
        "language": "English",
        "auto_save": True,
        "confirm_before_delete": True,
    },
    "ai": {
        "generation_mode": "Local",
        "image_quality": "High",
        "image_width": 1024,
        "image_height": 1024,
        "image_format": "PNG",
        "default_image_prompt": "",
        "negative_prompt": "",
        "seed": -1,
    },
    "video": {
        "resolution": "720p",
        "fps": 24,
        "default_duration": 5,
        "format": "MP4",
        "motion_intensity": 50,
    },
    "voice": {
        "language": "English",
        "voice_type": "Female",
        "speed": 1.0,
        "volume": 1.0,
        "emotion": "Neutral",
        "output_format": "WAV",
    },
    "storage": {
        "assets_folder": "assets",
        "projects_folder": "projects",
        "outputs_folder": "outputs",
        "backups_folder": "backups",
        "max_upload_mb": 100,
    },
    "performance": {
        "cpu_workers": 2,
        "max_memory_percent": 75,
        "low_memory_mode": True,
        "clear_temp_on_start": False,
        "prefer_cpu": True,
    },
}


CHOICES = {
    "general.theme": ["Dark", "Light", "System"],
    "general.language": ["English", "Hindi", "Marathi"],
    "ai.generation_mode": ["Local", "Remote", "Manual"],
    "ai.image_quality": ["Draft", "Standard", "High"],
    "ai.image_format": ["PNG", "JPEG", "WEBP"],
    "video.resolution": ["480p", "720p", "1080p"],
    "video.format": ["MP4", "WEBM", "MOV"],
    "voice.language": ["English", "Hindi", "Marathi", "Hinglish"],
    "voice.voice_type": ["Female", "Male", "Neutral"],
    "voice.emotion": [
        "Neutral", "Happy", "Sad", "Angry", "Calm",
        "Excited", "Whispering", "Serious"
    ],
    "voice.output_format": ["WAV", "MP3"],
}


NUMERIC_RULES = {
    "ai.image_width": (256, 4096),
    "ai.image_height": (256, 4096),
    "ai.seed": (-1, 2147483647),
    "video.fps": (12, 60),
    "video.default_duration": (1, 600),
    "video.motion_intensity": (0, 100),
    "voice.speed": (0.5, 2.0),
    "voice.volume": (0.0, 2.0),
    "storage.max_upload_mb": (1, 2048),
    "performance.cpu_workers": (1, 64),
    "performance.max_memory_percent": (10, 95),
}


BOOLEAN_PATHS = {
    "general.auto_save",
    "general.confirm_before_delete",
    "performance.low_memory_mode",
    "performance.clear_temp_on_start",
    "performance.prefer_cpu",
}


STRING_PATHS = {
    "general.studio_name",
    "ai.default_image_prompt",
    "ai.negative_prompt",
    "storage.assets_folder",
    "storage.projects_folder",
    "storage.outputs_folder",
    "storage.backups_folder",
}


def get_settings_path() -> Path:
    """Find the settings file without modifying config.py."""
    try:
        import config

        for name in ("SETTINGS_FILE", "SETTINGS_PATH"):
            value = getattr(config, name, None)
            if value:
                path = Path(value)
                if not path.is_absolute():
                    path = Path(__file__).resolve().parent.parent / path
                return path

        for name in ("DATA_DIR", "DATA_PATH"):
            value = getattr(config, name, None)
            if value:
                folder = Path(value)
                if not folder.is_absolute():
                    folder = Path(__file__).resolve().parent.parent / folder
                return folder / "settings.json"
    except Exception:
        pass

    return Path(__file__).resolve().parent.parent / "data" / "settings.json"


def _deep_merge(base: dict, updates: dict) -> dict:
    """Merge dictionaries while retaining unknown-safe defaults."""
    result = copy.deepcopy(base)

    for key, value in updates.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        elif key in result:
            result[key] = copy.deepcopy(value)

    return result


def _get_nested(data: dict, dotted_path: str) -> Any:
    value = data
    for part in dotted_path.split("."):
        value = value[part]
    return value


def _set_nested(data: dict, dotted_path: str, value: Any) -> None:
    parts = dotted_path.split(".")
    target = data

    for part in parts[:-1]:
        target = target[part]

    target[parts[-1]] = value


def validate_settings(settings: dict) -> tuple[dict, list[str]]:
    """
    Validate known settings and return:
        (validated_settings, error_messages)

    Unknown keys are ignored. Invalid values are replaced with defaults.
    """
    if not isinstance(settings, dict):
        return copy.deepcopy(DEFAULT_SETTINGS), [
            "Settings must be a JSON object."
        ]

    result = copy.deepcopy(DEFAULT_SETTINGS)
    errors = []

    for section, values in settings.items():
        if section not in DEFAULT_SETTINGS:
            continue
        if not isinstance(values, dict):
            errors.append(f"{section}: expected an object.")
            continue

        for key, value in values.items():
            dotted = f"{section}.{key}"

            if dotted not in {
                f"{s}.{k}"
                for s, section_values in DEFAULT_SETTINGS.items()
                for k in section_values
            }:
                continue

            try:
                if dotted in CHOICES:
                    if value not in CHOICES[dotted]:
                        raise ValueError(
                            f"Choose one of: {', '.join(CHOICES[dotted])}"
                        )

                elif dotted in BOOLEAN_PATHS:
                    if not isinstance(value, bool):
                        raise ValueError("Expected true or false.")

                elif dotted in NUMERIC_RULES:
                    minimum, maximum = NUMERIC_RULES[dotted]

                    if isinstance(value, bool) or not isinstance(
                        value, (int, float)
                    ):
                        raise ValueError("Expected a number.")

                    if not minimum <= value <= maximum:
                        raise ValueError(
                            f"Value must be between {minimum} and {maximum}."
                        )

                    if dotted in {
                        "ai.image_width",
                        "ai.image_height",
                        "ai.seed",
                        "video.fps",
                        "video.default_duration",
                        "video.motion_intensity",
                        "storage.max_upload_mb",
                        "performance.cpu_workers",
                        "performance.max_memory_percent",
                    }:
                        if not isinstance(value, int):
                            raise ValueError("Expected a whole number.")

                elif dotted in STRING_PATHS:
                    if not isinstance(value, str):
                        raise ValueError("Expected text.")

                    if dotted.endswith("_folder"):
                        if not value.strip():
                            raise ValueError("Folder name cannot be empty.")
                        if Path(value).is_absolute():
                            raise ValueError(
                                "Use a relative folder path inside the project."
                            )
                        if ".." in Path(value).parts:
                            raise ValueError(
                                "Folder path cannot contain '..'."
                            )

                    if dotted == "general.studio_name" and not value.strip():
                        raise ValueError("Studio name cannot be empty.")

                _set_nested(result, dotted, value)

            except (ValueError, TypeError) as exc:
                errors.append(f"{dotted}: {exc}")

    return result, errors


def load_settings() -> dict:
    """Load settings, creating defaults if the file does not exist."""
    path = get_settings_path()

    if not path.exists():
        settings = copy.deepcopy(DEFAULT_SETTINGS)
        save_settings(settings)
        return settings

    try:
        with path.open("r", encoding="utf-8") as file:
            raw = json.load(file)

        validated, errors = validate_settings(raw)

        # Repair invalid or incomplete settings on disk.
        if errors or validated != raw:
            save_settings(validated)

        return validated

    except (OSError, json.JSONDecodeError, TypeError):
        return copy.deepcopy(DEFAULT_SETTINGS)


def save_settings(settings: dict) -> tuple[bool, list[str]]:
    """Validate and atomically save settings."""
    validated, errors = validate_settings(settings)

    if errors:
        return False, errors

    path = get_settings_path()
    temp_path = None

    try:
        path.parent.mkdir(parents=True, exist_ok=True)

        fd, temp_name = tempfile.mkstemp(
            prefix="settings_",
            suffix=".tmp",
            dir=str(path.parent),
        )
        temp_path = Path(temp_name)

        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(validated, file, indent=4, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())

        os.replace(temp_path, path)
        return True, []

    except OSError as exc:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)
        return False, [str(exc)]


def get_setting(key: str, default: Any = None) -> Any:
    """Read a setting using a dotted key, e.g. 'video.fps'."""
    try:
        settings = load_settings()
        return _get_nested(settings, key)
    except (KeyError, TypeError):
        return default


def update_settings(updates: dict) -> tuple[bool, list[str]]:
    """Update selected settings while preserving other values."""
    current = load_settings()

    if not isinstance(updates, dict):
        return False, ["Updates must be a dictionary."]

    merged = _deep_merge(current, updates)
    return save_settings(merged)


def reset_settings() -> tuple[bool, list[str]]:
    """Restore all settings to their defaults."""
    return save_settings(copy.deepcopy(DEFAULT_SETTINGS))


def export_settings(destination: str | Path) -> tuple[bool, str]:
    """Export settings to a JSON file."""
    destination = Path(destination)

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", encoding="utf-8") as file:
            json.dump(load_settings(), file, indent=4, ensure_ascii=False)
        return True, str(destination)
    except OSError as exc:
        return False, str(exc)


def import_settings(source: str | Path) -> tuple[bool, list[str]]:
    """Import and validate a settings JSON file."""
    try:
        with Path(source).open("r", encoding="utf-8") as file:
            imported = json.load(file)

        if not isinstance(imported, dict):
            return False, ["Imported file must contain a JSON object."]

        # Import only known settings and retain defaults for missing fields.
        validated, errors = validate_settings(imported)
        if errors:
            return False, errors

        return save_settings(validated)

    except (OSError, json.JSONDecodeError) as exc:
        return False, [str(exc)]


def _render_general(st, settings):
    st.subheader("General")
    values = settings["general"]

    values["studio_name"] = st.text_input(
        "Studio name", values["studio_name"]
    )
    values["theme"] = st.selectbox(
        "Theme", CHOICES["general.theme"],
        index=CHOICES["general.theme"].index(values["theme"]),
    )
    values["language"] = st.selectbox(
        "Application language", CHOICES["general.language"],
        index=CHOICES["general.language"].index(values["language"]),
    )
    values["auto_save"] = st.checkbox(
        "Enable auto-save", values["auto_save"]
    )
    values["confirm_before_delete"] = st.checkbox(
        "Confirm before deleting projects and assets",
        values["confirm_before_delete"],
    )


def _render_ai(st, settings):
    st.subheader("AI Generation")
    values = settings["ai"]

    values["generation_mode"] = st.selectbox(
        "Generation mode", CHOICES["ai.generation_mode"],
        index=CHOICES["ai.generation_mode"].index(
            values["generation_mode"]
        ),
    )
    values["image_quality"] = st.selectbox(
        "Default image quality", CHOICES["ai.image_quality"],
        index=CHOICES["ai.image_quality"].index(values["image_quality"]),
    )

    col1, col2 = st.columns(2)
    with col1:
        values["image_width"] = st.number_input(
            "Image width", 256, 4096, values["image_width"], step=64
        )
    with col2:
        values["image_height"] = st.number_input(
            "Image height", 256, 4096, values["image_height"], step=64
        )

    values["image_format"] = st.selectbox(
        "Image format", CHOICES["ai.image_format"],
        index=CHOICES["ai.image_format"].index(values["image_format"]),
    )
    values["seed"] = st.number_input(
        "Seed (-1 means random)", -1, 2147483647,
        values["seed"], step=1,
    )
    values["default_image_prompt"] = st.text_area(
        "Default image prompt", values["default_image_prompt"]
    )
    values["negative_prompt"] = st.text_area(
        "Default negative prompt", values["negative_prompt"]
    )

    st.caption(
        "These are saved preferences. An image-generation module must "
        "read them before they affect actual generation."
    )


def _render_video(st, settings):
    st.subheader("Video Defaults")
    values = settings["video"]

    values["resolution"] = st.selectbox(
        "Default resolution",
        CHOICES["video.resolution"],
        index=CHOICES["video.resolution"].index(values["resolution"]),
    )

    col1, col2 = st.columns(2)
    with col1:
        values["fps"] = st.number_input(
            "Frames per second", 12, 60, values["fps"]
        )
    with col2:
        values["default_duration"] = st.number_input(
            "Default duration (seconds)", 1, 600,
            values["default_duration"],
        )

    values["format"] = st.selectbox(
        "Video format",
        CHOICES["video.format"],
        index=CHOICES["video.format"].index(values["format"]),
    )
    values["motion_intensity"] = st.slider(
        "Default motion intensity", 0, 100,
        values["motion_intensity"],
    )


def _render_voice(st, settings):
    st.subheader("Voice and Language")
    values = settings["voice"]

    for key, label in (
        ("language", "Voice language"),
        ("voice_type", "Voice type"),
        ("emotion", "Default emotion"),
        ("output_format", "Audio output format"),
    ):
        options = CHOICES[f"voice.{key}"]
        values[key] = st.selectbox(
            label, options, index=options.index(values[key])
        )

    values["speed"] = st.slider(
        "Voice speed", 0.5, 2.0, float(values["speed"]), step=0.1
    )
    values["volume"] = st.slider(
        "Voice volume", 0.0, 2.0, float(values["volume"]), step=0.1
    )


def _render_storage(st, settings):
    st.subheader("Storage")
    values = settings["storage"]

    for key, label in (
        ("assets_folder", "Assets folder"),
        ("projects_folder", "Projects folder"),
        ("outputs_folder", "Outputs folder"),
        ("backups_folder", "Backups folder"),
    ):
        values[key] = st.text_input(label, values[key])

    values["max_upload_mb"] = st.number_input(
        "Maximum upload size (MB)", 1, 2048,
        values["max_upload_mb"],
    )

    st.caption(
        "Folder names are stored as relative paths. This module does not "
        "move existing files when you change them."
    )


def _render_performance(st, settings):
    st.subheader("Performance")
    values = settings["performance"]

    values["cpu_workers"] = st.number_input(
        "CPU worker limit", 1, 64, values["cpu_workers"]
    )
    values["max_memory_percent"] = st.slider(
        "Preferred maximum memory usage (%)",
        10, 95, values["max_memory_percent"],
    )
    values["low_memory_mode"] = st.checkbox(
        "Low-memory mode", values["low_memory_mode"]
    )
    values["prefer_cpu"] = st.checkbox(
        "Prefer CPU processing", values["prefer_cpu"]
    )
    values["clear_temp_on_start"] = st.checkbox(
        "Clear temporary files on startup",
        values["clear_temp_on_start"],
    )

    st.info(
        "These settings describe preferences. They do not limit CPU or "
        "RAM by themselves; connect them to your AI processing modules."
    )


def render(st) -> None:
    """Render the Streamlit Settings Manager."""
    st.title("Studio Settings")
    st.caption("Configure your local AI Influencer Studio.")

    settings = load_settings()

    tabs = st.tabs([
        "General", "AI Generation", "Video",
        "Voice", "Storage", "Performance", "Import / Export",
    ])

    with tabs[0]:
        _render_general(st, settings)
    with tabs[1]:
        _render_ai(st, settings)
    with tabs[2]:
        _render_video(st, settings)
    with tabs[3]:
        _render_voice(st, settings)
    with tabs[4]:
        _render_storage(st, settings)
    with tabs[5]:
        _render_performance(st, settings)

    with tabs[6]:
        st.subheader("Settings Backup")
        st.write("Export your settings or restore them from a JSON file.")

        export_name = st.text_input(
            "Export filename", value="studio_settings.json"
        )

        if st.button("Export settings"):
            success, result = export_settings(export_name)
            if success:
                st.success(f"Settings exported to: {result}")
            else:
                st.error(result)

        uploaded = st.file_uploader(
            "Import settings JSON", type=["json"]
        )

        if uploaded is not None and st.button("Import uploaded settings"):
            try:
                data = json.loads(uploaded.getvalue().decode("utf-8"))
                validated, errors = validate_settings(data)

                if errors:
                    st.error("Import rejected: " + "; ".join(errors))
                else:
                    success, save_errors = save_settings(validated)
                    if success:
                        st.success("Settings imported. Reload the page.")
                    else:
                        st.error("; ".join(save_errors))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                st.error(f"Invalid JSON file: {exc}")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Save all settings", type="primary", use_container_width=True):
            success, errors = save_settings(settings)
            if success:
                st.success("Settings saved successfully.")
            else:
                st.error("Could not save: " + "; ".join(errors))

    with col2:
        if st.button("Reset to defaults", use_container_width=True):
            success, errors = reset_settings()
            if success:
                st.success("Settings restored. Reload the page.")
            else:
                st.error("; ".join(errors))


def run_tests() -> bool:
    """Run isolated tests without changing the user's real settings."""
    import unittest
    from unittest.mock import patch

    class SettingsTests(unittest.TestCase):

        def setUp(self):
            self.temp_dir = tempfile.TemporaryDirectory()
            self.settings_file = Path(self.temp_dir.name) / "settings.json"
            self.patch_path = patch(
                __name__ + ".get_settings_path",
                return_value=self.settings_file,
            )
            self.patch_path.start()

        def tearDown(self):
            self.patch_path.stop()
            self.temp_dir.cleanup()

        def test_default_settings(self):
            self.assertEqual(
                load_settings()["general"]["studio_name"],
                "AI Influencer Studio",
            )

        def test_save_and_load(self):
            settings = copy.deepcopy(DEFAULT_SETTINGS)
            settings["general"]["studio_name"] = "Test Studio"

            success, errors = save_settings(settings)
            self.assertTrue(success, errors)
            self.assertEqual(
                load_settings()["general"]["studio_name"],
                "Test Studio",
            )

        def test_update_preserves_other_sections(self):
            success, errors = update_settings({
                "video": {"fps": 30}
            })
            self.assertTrue(success, errors)
            result = load_settings()
            self.assertEqual(result["video"]["fps"], 30)
            self.assertEqual(result["voice"]["language"], "English")

        def test_invalid_choice_rejected(self):
            settings = copy.deepcopy(DEFAULT_SETTINGS)
            settings["general"]["theme"] = "Unknown"
            success, errors = save_settings(settings)
            self.assertFalse(success)
            self.assertTrue(errors)

        def test_invalid_number_rejected(self):
            settings = copy.deepcopy(DEFAULT_SETTINGS)
            settings["video"]["fps"] = 999
            success, errors = save_settings(settings)
            self.assertFalse(success)
            self.assertTrue(errors)

        def test_boolean_type_validation(self):
            settings = copy.deepcopy(DEFAULT_SETTINGS)
            settings["general"]["auto_save"] = "yes"
            success, errors = save_settings(settings)
            self.assertFalse(success)
            self.assertTrue(errors)

        def test_unknown_keys_ignored(self):
            settings = copy.deepcopy(DEFAULT_SETTINGS)
            settings["unknown"] = {"secret": "value"}
            validated, errors = validate_settings(settings)
            self.assertEqual(errors, [])
            self.assertNotIn("unknown", validated)

        def test_reset(self):
            update_settings({"general": {"studio_name": "Changed"}})
            success, errors = reset_settings()
            self.assertTrue(success, errors)
            self.assertEqual(
                load_settings()["general"]["studio_name"],
                "AI Influencer Studio",
            )

        def test_export_and_import(self):
            settings = copy.deepcopy(DEFAULT_SETTINGS)
            settings["general"]["studio_name"] = "Export Test"
            save_settings(settings)

            export_file = Path(self.temp_dir.name) / "export.json"
            success, result = export_settings(export_file)
            self.assertTrue(success, result)

            reset_settings()
            success, errors = import_settings(export_file)
            self.assertTrue(success, errors)
            self.assertEqual(
                load_settings()["general"]["studio_name"],
                "Export Test",
            )

        def test_invalid_folder_traversal(self):
            settings = copy.deepcopy(DEFAULT_SETTINGS)
            settings["storage"]["assets_folder"] = "../outside"
            success, errors = save_settings(settings)
            self.assertFalse(success)
            self.assertTrue(errors)

        def test_invalid_json_fallback(self):
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            self.settings_file.write_text("{invalid", encoding="utf-8")
            result = load_settings()
            self.assertEqual(
                result["general"]["studio_name"],
                "AI Influencer Studio",
            )

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        SettingsTests
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AI Influencer Studio Settings Manager"
    )
    parser.add_argument(
        "--test", action="store_true",
        help="Run built-in tests",
    )
    args = parser.parse_args()

    if args.test:
        raise SystemExit(0 if run_tests() else 1)

    print("Settings Manager module loaded.")
    print("Run with --test to execute built-in tests.")
