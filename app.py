
"""
AI Influencer Studio
File 66: app.py

Fault-Isolated Streamlit Application Launcher

Features:
- Automatically discovers Python modules in modules/
- Loads each module independently
- Isolates import and runtime errors
- Handles missing packages
- Handles missing module files
- Supports module-to-module dependencies
- Shows module-specific errors after navigation
- Logs full tracebacks to logs/app_errors.log
- Provides System Health dashboard
- Provides module search
- Provides refresh and retry
- Provides error log viewer
- Built-in tests

Run:
    streamlit run app.py

Test:
    python app.py --test
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import logging.handlers
import sys
import traceback

from datetime import datetime
from pathlib import Path
from typing import Any


# =========================================================
# 1. PROJECT PATHS
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

MODULES_DIR = BASE_DIR / "modules"
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

ERROR_LOG = LOG_DIR / "app_errors.log"

for folder in (MODULES_DIR, DATA_DIR, LOG_DIR):
    folder.mkdir(parents=True, exist_ok=True)

# Ensure the project root is available for imports.
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


# =========================================================
# 2. LOGGING SYSTEM
# =========================================================

def setup_logger() -> logging.Logger:
    """
    Configure a rotating error log.

    The log file is automatically rotated when it reaches
    approximately 2 MB. Up to 5 backup files are retained.
    """

    logger = logging.getLogger("AIInfluencerStudio")

    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        try:
            handler = logging.handlers.RotatingFileHandler(
                ERROR_LOG,
                maxBytes=2 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8"
            )

            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)s | "
                "%(name)s | %(message)s"
            )

            handler.setFormatter(formatter)
            logger.addHandler(handler)

        except OSError as exc:
            # Keep the application usable even if the log
            # directory cannot be written.
            logger.addHandler(logging.NullHandler())
            print(f"Warning: Could not initialize log file: {exc}")

    return logger


LOGGER = setup_logger()


def log_exception(
    module_name: str,
    stage: str,
    exception: BaseException
) -> None:
    """Log a complete exception traceback."""

    LOGGER.error(
        "Module: %s | Stage: %s | Error: %s",
        module_name,
        stage,
        exception,
        exc_info=(
            type(exception),
            exception,
            exception.__traceback__
        )
    )


# =========================================================
# 3. MODULE CONFIGURATION
# =========================================================

# Add a module's required Python packages here only if
# that module cannot work without those packages.
#
# Example:
# "my_module": ["some_package"]
#
# Python package names are checked using importlib.util.
#
# Most modules should import optional packages only when
# the relevant feature is used.

MODULE_PACKAGE_DEPENDENCIES: dict[str, list[str]] = {
    # Example:
    # "example_module": ["PIL"]
}


# Add dependencies between your own modules here.
#
# Example:
# "video_module": ["character_identity_manager"]
#
# If a required module is missing or fails to import,
# the dependent module will show a dependency error.

MODULE_DEPENDENCIES: dict[str, list[str]] = {
    # Example:
    # "video_module": ["character_identity_manager"]
}


# Known modules that should be present in this project.
# The launcher also discovers additional files automatically.

EXPECTED_MODULES = [
    "analytics",
    "project_manager",
    "character_identity_manager",
    "character_reference_library",
    "image_generation_manager",
    "video_generation_manager",
    "face_consistency_checker",
    "outfit_consistency_manager",
    "voice_profile_manager",
    "lip_sync_manager",
    "batch_generation_manager",
    "final_workflow_integration",
    "script_writer",
    "storyboard_manager",
    "scene_prompt_generator",
    "content_calendar",
    "competitor_analyzer",
    "seo_optimizer",
    "hashtag_research",
    "social_media_exporter",
    "watermark_manager",
    "brand_kit",
    "thumbnail_studio",
    "video_effects",
    "render_queue",
    "video_renderer",
    "subtitle_manager",
    "audio_mixer",
    "transition_manager",
    "timeline_editor",
    "scene_composer",
    "pose_gallery",
    "pose_library",
    "outfit_comparison",
    "outfit_gallery",
    "outfit_manager",
    "character_gallery",
    "character_consistency",
    "prompt_manager",
    "media_preview",
    "asset_manager",
    "activity_logger",
    "notification_manager",
    "settings_manager",
    "workflow_manager",
    "export_manager",
    "backup_manager",
    "talking_avatar",
    "motion_control"
]


# =========================================================
# 4. MODULE NAME HELPERS
# =========================================================

def module_display_name(module_name: str) -> str:
    """Convert a Python filename into a readable name."""

    return module_name.replace("_", " ").title()


def discover_module_names(
    modules_dir: Path | None = None
) -> list[str]:
    """
    Find Python modules inside the modules directory.

    Each module is discovered by filename.
    This function does not import modules.
    """

    root = modules_dir or MODULES_DIR

    if not root.exists():
        return []

    names = []

    try:
        for path in root.glob("*.py"):
            if path.name == "__init__.py":
                continue

            if path.name.startswith("_"):
                continue

            names.append(path.stem)

    except OSError as exc:
        LOGGER.error(
            "Module discovery failed: %s",
            exc,
            exc_info=True
        )

    return sorted(set(names))


def get_all_module_names(
    modules_dir: Path | None = None
) -> list[str]:
    """Combine discovered modules and expected module names."""

    discovered = discover_module_names(modules_dir)

    combined = set(discovered)
    combined.update(EXPECTED_MODULES)

    return sorted(combined)


# =========================================================
# 5. PACKAGE DEPENDENCY CHECK
# =========================================================

def check_package_dependencies(
    module_name: str
) -> list[str]:
    """
    Return a list of missing required packages.

    A missing package affects only the configured module.
    """

    missing = []

    packages = MODULE_PACKAGE_DEPENDENCIES.get(
        module_name,
        []
    )

    for package in packages:
        try:
            spec = importlib.util.find_spec(package)

            if spec is None:
                missing.append(package)

        except (ImportError, ValueError, AttributeError):
            missing.append(package)

    return missing


# =========================================================
# 6. MODULE DEPENDENCY CHECK
# =========================================================

def check_module_dependencies(
    module_name: str,
    module_registry: dict
) -> list[str]:
    """
    Check whether required modules are available.

    Dependencies are explicitly configured in
    MODULE_DEPENDENCIES.
    """

    failures = []

    required_modules = MODULE_DEPENDENCIES.get(
        module_name,
        []
    )

    for dependency in required_modules:
        dependency_info = module_registry.get(dependency)

        if not dependency_info:
            failures.append(
                f"Required module '{dependency}' is missing."
            )
            continue

        if dependency_info.get("status") != "available":
            failures.append(
                f"Required module '{dependency}' "
                f"is unavailable."
            )

    return failures


# =========================================================
# 7. MODULE STATUS REGISTRY
# =========================================================

def create_module_status(
    module_name: str
) -> dict:
    return {
        "name": module_name,
        "display_name": module_display_name(module_name),
        "status": "not_loaded",
        "module_object": None,
        "renderer": None,
        "error": None,
        "error_type": None,
        "stage": None,
        "missing_packages": [],
        "dependency_errors": [],
        "file_exists": False,
        "last_checked": None
    }


def load_one_module(
    module_name: str,
    modules_dir: Path | None = None
) -> dict:
    """
    Load exactly one module.

    Any error is captured and returned as module status.
    """

    root = modules_dir or MODULES_DIR
    file_path = root / f"{module_name}.py"

    result = create_module_status(module_name)

    result["last_checked"] = datetime.now().isoformat(
        timespec="seconds"
    )

    if not file_path.is_file():
        result["status"] = "missing"
        result["stage"] = "discovery"
        result["error"] = (
            f"Module file not found: {file_path}"
        )

        LOGGER.warning(
            "Module file missing: %s",
            file_path
        )

        return result

    result["file_exists"] = True

    missing_packages = check_package_dependencies(
        module_name
    )

    if missing_packages:
        result["status"] = "missing_package"
        result["stage"] = "dependency_check"
        result["missing_packages"] = missing_packages
        result["error"] = (
            "Required package(s) not installed: "
            + ", ".join(missing_packages)
        )

        LOGGER.error(
            "Missing packages for %s: %s",
            module_name,
            missing_packages
        )

        return result

    try:
        module = importlib.import_module(
            f"modules.{module_name}"
        )

        # Refresh the module object when explicitly reloading.
        # Initial import uses the object returned above.

        result["module_object"] = module

        renderer = getattr(module, "render", None)

        if callable(renderer):
            result["renderer"] = renderer
            result["status"] = "available"
        else:
            result["status"] = "utility"
            result["error"] = (
                "This module does not provide a render() "
                "function. It may be a helper or utility module."
            )

    except ModuleNotFoundError as exc:
        result["status"] = "missing_package"
        result["stage"] = "import"
        result["error_type"] = type(exc).__name__
        result["error"] = str(exc)

        if exc.name:
            result["missing_packages"] = [exc.name]

        log_exception(
            module_name,
            "import",
            exc
        )

    except Exception as exc:
        result["status"] = "import_error"
        result["stage"] = "import"
        result["error_type"] = type(exc).__name__
        result["error"] = str(exc)

        log_exception(
            module_name,
            "import",
            exc
        )

    return result


# =========================================================
# 8. LOAD ALL MODULES INDEPENDENTLY
# =========================================================

def load_all_modules(
    modules_dir: Path | None = None
) -> dict:
    """
    Load every discovered or expected module separately.

    One failed module will not stop the loading of others.
    """

    names = get_all_module_names(modules_dir)

    registry = {}

    for module_name in names:
        try:
            registry[module_name] = load_one_module(
                module_name,
                modules_dir
            )

        except Exception as exc:
            result = create_module_status(module_name)

            result["status"] = "launcher_error"
            result["stage"] = "module_loading"
            result["error_type"] = type(exc).__name__
            result["error"] = str(exc)

            registry[module_name] = result

            log_exception(
                module_name,
                "module_loading",
                exc
            )

    # Check inter-module dependencies after initial imports.
    for module_name, result in registry.items():
        if result["status"] not in ("available", "utility"):
            continue

        dependency_errors = check_module_dependencies(
            module_name,
            registry
        )

        if dependency_errors:
            result["status"] = "dependency_error"
            result["dependency_errors"] = dependency_errors
            result["error"] = "; ".join(dependency_errors)
            result["stage"] = "module_dependency"

            LOGGER.error(
                "Dependency error in %s: %s",
                module_name,
                dependency_errors
            )

    return registry


# =========================================================
# 9. SAFE MODULE RELOAD
# =========================================================

def reload_one_module(
    module_name: str,
    registry: dict
) -> dict:
    """
    Reload one module without reloading the entire app.

    Other module statuses remain unchanged.
    """

    importlib.invalidate_caches()

    try:
        module_path = MODULES_DIR / f"{module_name}.py"

        if not module_path.is_file():
            result = create_module_status(module_name)
            result["status"] = "missing"
            result["error"] = "Module file does not exist."
            result["stage"] = "reload"
            registry[module_name] = result
            return result

        full_name = f"modules.{module_name}"

        if full_name in sys.modules:
            try:
                del sys.modules[full_name]
            except Exception:
                pass

        result = load_one_module(module_name)

        registry[module_name] = result

        # Recheck dependent modules.
        for dependent, dependencies in MODULE_DEPENDENCIES.items():
            if module_name not in dependencies:
                continue

            dependent_info = registry.get(dependent)

            if not dependent_info:
                continue

            errors = check_module_dependencies(
                dependent,
                registry
            )

            if errors:
                dependent_info["status"] = "dependency_error"
                dependent_info["dependency_errors"] = errors
                dependent_info["error"] = "; ".join(errors)

        return result

    except Exception as exc:
        result = create_module_status(module_name)

        result["status"] = "reload_error"
        result["stage"] = "reload"
        result["error_type"] = type(exc).__name__
        result["error"] = str(exc)

        registry[module_name] = result

        log_exception(
            module_name,
            "reload",
            exc
        )

        return result


# =========================================================
# 10. MODULE ERROR INFORMATION
# =========================================================

def get_error_guidance(status: dict) -> list[str]:
    """Provide useful troubleshooting instructions."""

    state = status.get("status")
    guidance = []

    if state == "missing":
        guidance.extend([
            "Check whether the Python file exists inside modules/.",
            "Verify that the filename matches the module name.",
            "Create or restore the missing module file."
        ])

    elif state == "missing_package":
        packages = status.get("missing_packages", [])

        if packages:
            guidance.append(
                "Install the missing package(s): "
                + ", ".join(packages)
            )

            for package in packages:
                guidance.append(
                    f"PowerShell: python -m pip install {package}"
                )

        guidance.append(
            "If the package is optional, import it only "
            "inside the feature that needs it."
        )

    elif state == "import_error":
        guidance.extend([
            "Open the error details and check the traceback.",
            "Check syntax errors and incorrect import paths.",
            "Check whether this module imports another broken module.",
            "Run the module's built-in test separately."
        ])

    elif state == "dependency_error":
        guidance.extend([
            "Check the required module names in "
            "MODULE_DEPENDENCIES inside app.py.",
            "Restore or fix the unavailable dependency module.",
            "Reload the dependency and then retry this module."
        ])

    elif state == "runtime_error":
        guidance.extend([
            "The module imported, but its render() function failed.",
            "Check the traceback and the input that caused the error.",
            "Check missing packages, files, data and configuration."
        ])

    elif state == "utility":
        guidance.extend([
            "This module has no Streamlit render() function.",
            "It may be intended to provide functions for other modules."
        ])

    else:
        guidance.append(
            "Check logs/app_errors.log for the full error details."
        )

    return guidance


# =========================================================
# 11. STREAMLIT IMPORT
# =========================================================

def get_streamlit():
    """
    Import Streamlit only when the UI is launched.

    This keeps the built-in Python tests independent
    from Streamlit installation.
    """

    try:
        import streamlit as st
        return st

    except ModuleNotFoundError as exc:
        print(
            "\nStreamlit is not installed.\n"
            "Install it using:\n"
            "python -m pip install streamlit\n"
            "Then run:\n"
            "streamlit run app.py\n"
        )

        raise RuntimeError(
            "Streamlit is required to run the application."
        ) from exc


# =========================================================
# 12. STREAMLIT ERROR DISPLAY
# =========================================================

def display_module_error(
    st,
    module_name: str,
    status: dict
) -> None:
    """Display an error belonging to one module."""

    st.error(
        f"{status.get('display_name', module_name)} "
        "could not be loaded."
    )

    st.markdown("### Error information")

    st.write(
        f"**Module:** `{module_name}`"
    )

    st.write(
        f"**Status:** `{status.get('status')}`"
    )

    st.write(
        f"**Stage:** `{status.get('stage') or 'Unknown'}`"
    )

    st.write(
        f"**Error type:** "
        f"`{status.get('error_type') or 'Not available'}`"
    )

    st.code(
        status.get("error") or "Unknown error",
        language="text"
    )

    dependency_errors = status.get(
        "dependency_errors",
        []
    )

    for error in dependency_errors:
        st.warning(error)

    st.markdown("### How to fix")

    for instruction in get_error_guidance(status):
        st.write(f"- {instruction}")

    st.info(
        "This error belongs to this module. "
        "Other modules can still be used."
    )


# =========================================================
# 13. SYSTEM HEALTH PAGE
# =========================================================

def render_system_health(
    st,
    registry: dict
) -> None:
    st.title("System Health")

    st.caption(
        "Check modules, packages, dependencies and application errors."
    )

    statuses = list(registry.values())

    total = len(statuses)

    available = sum(
        1 for item in statuses
        if item["status"] == "available"
    )

    utilities = sum(
        1 for item in statuses
        if item["status"] == "utility"
    )

    failed = total - available - utilities

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Modules", total)
    col2.metric("Available", available)
    col3.metric("Utility Modules", utilities)
    col4.metric("Unavailable", failed)

    st.divider()

    st.subheader("Module Status")

    for module_name, item in registry.items():
        label = item["display_name"]
        state = item["status"]

        if state == "available":
            st.success(f"{label} — Available")

        elif state == "utility":
            st.info(f"{label} — Utility module")

        else:
            st.error(f"{label} — {state.replace('_', ' ').title()}")

            with st.expander(
                f"View details: {label}"
            ):
                display_module_error(
                    st,
                    module_name,
                    item
                )

    st.divider()

    st.subheader("Configured Dependencies")

    st.write("Python package dependencies:")

    if MODULE_PACKAGE_DEPENDENCIES:
        st.json(MODULE_PACKAGE_DEPENDENCIES)
    else:
        st.info(
            "No additional mandatory package dependencies "
            "are configured in app.py."
        )

    st.write("Module dependencies:")

    if MODULE_DEPENDENCIES:
        st.json(MODULE_DEPENDENCIES)
    else:
        st.info(
            "No mandatory module-to-module dependencies "
            "are configured in app.py."
        )

    st.divider()

    st.subheader("Error Log")

    if ERROR_LOG.exists():
        try:
            log_text = ERROR_LOG.read_text(
                encoding="utf-8",
                errors="replace"
            )

            st.text_area(
                "Recent application log",
                value=log_text[-15000:],
                height=300,
                disabled=True
            )

            st.download_button(
                "Download Error Log",
                data=log_text,
                file_name="app_errors.log",
                mime="text/plain"
            )

        except OSError as exc:
            st.warning(
                f"Could not read error log: {exc}"
            )

    else:
        st.info("No application error log exists yet.")


# =========================================================
# 14. MODULE PAGE
# =========================================================

def render_module_page(
    st,
    module_name: str,
    registry: dict
) -> None:
    """Render one selected module safely."""

    status = registry.get(module_name)

    if status is None:
        st.error("Module status information is unavailable.")
        return

    st.title(status["display_name"])

    st.caption(
        f"Module: modules/{module_name}.py"
    )

    if status["status"] != "available":
        display_module_error(
            st,
            module_name,
            status
        )

        if st.button(
            "Retry This Module",
            key=f"retry_{module_name}"
        ):
            with st.spinner("Reloading module..."):
                result = reload_one_module(
                    module_name,
                    registry
                )

            if result["status"] == "available":
                st.success("Module loaded successfully.")
            else:
                st.error("Module is still unavailable.")

            st.rerun()

        return

    renderer = status.get("renderer")

    if not callable(renderer):
        st.info(
            "This module is available as a Python utility, "
            "but it does not have a Streamlit page."
        )

        st.write(
            "You can use its Python functions from other modules."
        )
        return

    # Each module render is protected independently.
    try:
        renderer()

    except ModuleNotFoundError as exc:
        status["status"] = "runtime_error"
        status["stage"] = "render"
        status["error_type"] = type(exc).__name__
        status["error"] = str(exc)

        if exc.name:
            status["missing_packages"] = [exc.name]

        log_exception(
            module_name,
            "render",
            exc
        )

        st.divider()

        display_module_error(
            st,
            module_name,
            status
        )

    except Exception as exc:
        status["status"] = "runtime_error"
        status["stage"] = "render"
        status["error_type"] = type(exc).__name__
        status["error"] = str(exc)

        log_exception(
            module_name,
            "render",
            exc
        )

        st.divider()

        display_module_error(
            st,
            module_name,
            status
        )


# =========================================================
# 15. MAIN STREAMLIT APPLICATION
# =========================================================

def main() -> None:
    st = get_streamlit()

    st.set_page_config(
        page_title="AI Influencer Studio",
        page_icon="🎬",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Keep the registry in Streamlit session state.
    if "module_registry" not in st.session_state:
        with st.spinner(
            "Discovering and loading studio modules..."
        ):
            st.session_state["module_registry"] = (
                load_all_modules()
            )

    registry = st.session_state["module_registry"]

    # -----------------------------------------------------
    # APP HEADER
    # -----------------------------------------------------

    st.sidebar.title("AI Influencer Studio")

    st.sidebar.caption(
        "Fault-Isolated Modular Application"
    )

    available_count = sum(
        1 for item in registry.values()
        if item["status"] == "available"
    )

    st.sidebar.metric(
        "Available Modules",
        f"{available_count}/{len(registry)}"
    )

    st.sidebar.divider()

    # -----------------------------------------------------
    # NAVIGATION
    # -----------------------------------------------------

    navigation_options = [
        "Dashboard",
        "System Health"
    ]

    navigation_options.extend(
        module_name
        for module_name in registry
    )

    search = st.sidebar.text_input(
        "Search Modules",
        placeholder="Type a module name..."
    )

    if search.strip():
        filtered_options = [
            name for name in navigation_options
            if search.lower() in name.lower()
            or search.lower() in module_display_name(name).lower()
        ]

        if not filtered_options:
            filtered_options = ["Dashboard"]

        navigation_options = filtered_options

    selected_page = st.sidebar.selectbox(
        "Navigate",
        navigation_options,
        format_func=lambda value: (
            value if value in ("Dashboard", "System Health")
            else module_display_name(value)
        )
    )

    # -----------------------------------------------------
    # REFRESH
    # -----------------------------------------------------

    if st.sidebar.button(
        "Refresh All Modules",
        use_container_width=True
    ):
        importlib.invalidate_caches()

        with st.spinner("Refreshing module registry..."):
            st.session_state["module_registry"] = (
                load_all_modules()
            )

        st.rerun()

    st.sidebar.divider()

    st.sidebar.caption(
        "An error in one module should not stop the others."
    )

    # -----------------------------------------------------
    # SELECTED PAGE
    # -----------------------------------------------------

    if selected_page == "Dashboard":
        st.title("AI Influencer Studio")

        st.markdown(
            "### Modular AI Content Production Workspace"
        )

        st.write(
            "Use the sidebar to open individual studio modules."
        )

        statuses = list(registry.values())

        available = sum(
            1 for item in statuses
            if item["status"] == "available"
        )

        unavailable = sum(
            1 for item in statuses
            if item["status"] not in (
                "available",
                "utility"
            )
        )

        utility = sum(
            1 for item in statuses
            if item["status"] == "utility"
        )

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Available Modules",
            available
        )

        col2.metric(
            "Unavailable Modules",
            unavailable
        )

        col3.metric(
            "Utility Modules",
            utility
        )

        st.divider()

        st.subheader("Available Modules")

        for module_name, item in registry.items():
            if item["status"] == "available":
                st.success(
                    f"{item['display_name']} — Ready"
                )

        st.subheader("Modules Requiring Attention")

        problem_modules = [
            (name, item)
            for name, item in registry.items()
            if item["status"] not in (
                "available",
                "utility"
            )
        ]

        if not problem_modules:
            st.success(
                "No module loading errors were detected."
            )

        else:
            for name, item in problem_modules:
                st.warning(
                    f"{item['display_name']} — "
                    f"{item['status'].replace('_', ' ').title()}"
                )

        st.info(
            "Open System Health to inspect errors, "
            "or select a module to retry it."
        )

    elif selected_page == "System Health":
        render_system_health(
            st,
            registry
        )

    else:
        render_module_page(
            st,
            selected_page,
            registry
        )


# =========================================================
# 16. BUILT-IN TESTS
# =========================================================

def run_tests() -> None:
    """
    Run launcher tests without requiring Streamlit.

    These tests use temporary folders and do not modify
    the actual modules directory.
    """

    import tempfile

    print("Running AI Influencer Studio launcher tests...")

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        modules_dir = root / "modules"
        modules_dir.mkdir()

        # Create a simple working module.
        (modules_dir / "working_module.py").write_text(
            "def render():\n"
            "    return 'Working'\n",
            encoding="utf-8"
        )

        # Create a module with no renderer.
        (modules_dir / "utility_module.py").write_text(
            "VALUE = 100\n",
            encoding="utf-8"
        )

        # Create a module with an import error.
        (modules_dir / "broken_module.py").write_text(
            "raise RuntimeError('Test import failure')\n",
            encoding="utf-8"
        )

        # Test discovery.
        discovered = discover_module_names(modules_dir)

        assert "working_module" in discovered
        assert "utility_module" in discovered
        assert "broken_module" in discovered

        # Test working module.
        working = load_one_module(
            "working_module",
            modules_dir
        )

        assert working["status"] == "available"
        assert callable(working["renderer"])

        # Test utility module.
        utility = load_one_module(
            "utility_module",
            modules_dir
        )

        assert utility["status"] == "utility"

        # Test broken module.
        broken = load_one_module(
            "broken_module",
            modules_dir
        )

        assert broken["status"] == "import_error"

        # Test missing module.
        missing = load_one_module(
            "missing_module",
            modules_dir
        )

        assert missing["status"] == "missing"

        # Test complete module registry.
        registry = {}

        for name in discovered:
            registry[name] = load_one_module(
                name,
                modules_dir
            )

        assert registry["working_module"]["status"] == "available"
        assert registry["broken_module"]["status"] == "import_error"

        # Test module dependency failure.
        old_dependencies = dict(MODULE_DEPENDENCIES)

        try:
            MODULE_DEPENDENCIES.clear()

            MODULE_DEPENDENCIES["working_module"] = [
                "missing_module"
            ]

            dependency_errors = check_module_dependencies(
                "working_module",
                registry
            )

            assert len(dependency_errors) == 1

        finally:
            MODULE_DEPENDENCIES.clear()
            MODULE_DEPENDENCIES.update(old_dependencies)

        # Test package dependency detection.
        old_packages = dict(MODULE_PACKAGE_DEPENDENCIES)

        try:
            MODULE_PACKAGE_DEPENDENCIES.clear()

            MODULE_PACKAGE_DEPENDENCIES["working_module"] = [
                "package_that_does_not_exist_12345"
            ]

            missing_packages = check_package_dependencies(
                "working_module"
            )

            assert (
                "package_that_does_not_exist_12345"
                in missing_packages
            )

        finally:
            MODULE_PACKAGE_DEPENDENCIES.clear()
            MODULE_PACKAGE_DEPENDENCIES.update(old_packages)

    print("All launcher tests passed.")


# =========================================================
# 17. APPLICATION ENTRY POINT
# =========================================================

if __name__ == "__main__":

    if "--test" in sys.argv:
        run_tests()

    else:
        try:
            main()

        except Exception as exc:
            log_exception(
                "app",
                "main_application",
                exc
            )

            print("\nAI Influencer Studio could not start.")
            print(f"Error: {exc}")
            print(f"Check the log file: {ERROR_LOG}")

            # Streamlit normally reports its own startup errors.
            # Do not hide the original exception.
            raise
