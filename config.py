"""Central configuration for AI Influencer Studio.

Designed for Windows 10/11, Python 3.11, and low-memory CPU-only systems.
"""
from __future__ import annotations

import os
from pathlib import Path

# Project root: directory containing app.py and this config.py file.
BASE_DIR = Path(__file__).resolve().parent

# Application identity and UI.
APP_NAME = "AI Influencer Studio"
APP_VERSION = "1.0.0"
DEFAULT_PAGE_LAYOUT = "wide"

# Persistent project folders. Generated outputs and temporary files are TTL-managed;
# user assets, projects, and database files are intentionally preserved.
MODULES_DIR = BASE_DIR / "modules"
ENGINES_DIR = BASE_DIR / "engines"
ASSETS_DIR = BASE_DIR / "assets"
PROJECTS_DIR = BASE_DIR / "projects"
OUTPUT_DIR = BASE_DIR / "output"
TEMP_DIR = BASE_DIR / "temp"
DATABASE_DIR = BASE_DIR / "database"
LOGS_DIR = BASE_DIR / "logs"

# Generated files expire after one hour (3,600 seconds).
OUTPUT_TTL_SECONDS = 60 * 60
# When the Streamlit app is active, check for expired files at most every 5 minutes.
CLEANUP_INTERVAL_SECONDS = 5 * 60

# Low-memory defaults for an 8 GB RAM, CPU-only Windows computer.
MAX_PREVIEW_WIDTH = 768
MAX_PREVIEW_HEIGHT = 768
PREVIEW_JPEG_QUALITY = 82
VIDEO_PREVIEW_MAX_WIDTH = 640
VIDEO_PREVIEW_MAX_HEIGHT = 360
VIDEO_PREVIEW_FPS = 8
VIDEO_PREVIEW_MAX_SECONDS = 15

# Keep uploads bounded. Increase only when required by a specific workflow.
MAX_IMAGE_UPLOAD_MB = 20
MAX_VIDEO_UPLOAD_MB = 200
MAX_AUDIO_UPLOAD_MB = 50

# Conservative processing defaults. Engines can override these for supported models.
DEFAULT_BATCH_SIZE = 1
MAX_CONCURRENT_JOBS = 1
MODEL_CACHE_ENABLED = True
MODEL_CACHE_MAX_ITEMS = 1

# Streamlit server defaults; environment variables can override these values.
SERVER_ADDRESS = os.getenv("AI_STUDIO_SERVER_ADDRESS", "127.0.0.1")
SERVER_PORT = int(os.getenv("AI_STUDIO_SERVER_PORT", "8501"))

# Basic logging configuration.
LOG_FILE = LOGS_DIR / "application.log"
LOG_LEVEL = os.getenv("AI_STUDIO_LOG_LEVEL", "INFO").upper()


def ensure_directories() -> None:
    """Create application folders if they do not already exist."""
    for directory in (
        MODULES_DIR,
        ENGINES_DIR,
        ASSETS_DIR,
        PROJECTS_DIR,
        OUTPUT_DIR,
        TEMP_DIR,
        DATABASE_DIR,
        LOGS_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def get_storage_limits() -> dict[str, int]:
    """Return upload limits in bytes for validation in UI modules."""
    return {
        "image": MAX_IMAGE_UPLOAD_MB * 1024 * 1024,
        "video": MAX_VIDEO_UPLOAD_MB * 1024 * 1024,
        "audio": MAX_AUDIO_UPLOAD_MB * 1024 * 1024,
    }
