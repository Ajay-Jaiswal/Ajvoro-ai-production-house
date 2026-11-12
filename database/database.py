"""Lightweight persistent SQLite database for AI Influencer Studio.

Persistent records only: users, characters, projects, and app metadata.
Generated media belongs in output/ or temp/ and is NOT stored as BLOBs here.
Recommended runtime: Python 3.11+ (standard library only).
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import config

SCHEMA_VERSION = 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _database_path() -> Path:
    """Resolve the configured database file and ensure its parent exists."""
    config.ensure_directories()
    path = Path(config.DATABASE_DIR) / "studio.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Yield a configured connection and always close it afterwards.

    Transactions are intentionally controlled by the caller. Use
    transaction() for writes that should commit or roll back automatically.
    """
    connection = sqlite3.connect(
        str(_database_path()),
        timeout=10.0,
        isolation_level="DEFERRED",
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    try:
        yield connection
    finally:
        connection.close()


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """Open a connection; commit on success and roll back on exceptions."""
    with get_connection() as connection:
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise


def init_db() -> Path:
    """Create/update the schema and return the persistent database path."""
    database_path = _database_path()
    with get_connection() as connection:
        # WAL improves concurrent reader behaviour for this small local app.
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                email TEXT COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS characters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                image_path TEXT,
                settings_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                project_path TEXT,
                settings_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS app_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_characters_user_id
                ON characters(user_id);
            CREATE INDEX IF NOT EXISTS idx_projects_user_id
                ON projects(user_id);
            CREATE INDEX IF NOT EXISTS idx_projects_updated_at
                ON projects(updated_at);
            """
        )
        connection.execute(
            """INSERT INTO app_metadata (key, value, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET
                   value = excluded.value,
                   updated_at = excluded.updated_at""",
            ("schema_version", str(SCHEMA_VERSION), _utc_now()),
        )
        connection.commit()
    return database_path


def create_user(
    username: str,
    password_hash: str,
    email: str | None = None,
) -> int:
    """Create a user. Pass a securely generated password hash, never plaintext."""
    username = username.strip()
    if not username:
        raise ValueError("Username cannot be empty.")
    if not password_hash:
        raise ValueError("A password hash is required.")

    now = _utc_now()
    with transaction() as connection:
        cursor = connection.execute(
            """INSERT INTO users
               (username, email, password_hash, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (username, email.strip() if email else None, password_hash, now, now),
        )
        return int(cursor.lastrowid)


def get_user_by_username(username: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM users WHERE username = ?", (username.strip(),)
        ).fetchone()
        return dict(row) if row else None


def create_character(
    name: str,
    *,
    user_id: int | None = None,
    description: str = "",
    image_path: str | None = None,
    settings: dict[str, Any] | None = None,
) -> int:
    """Save character metadata; image_path should reference persistent assets/."""
    name = name.strip()
    if not name:
        raise ValueError("Character name cannot be empty.")
    settings_json = json.dumps(settings or {}, ensure_ascii=False)
    now = _utc_now()
    with transaction() as connection:
        cursor = connection.execute(
            """INSERT INTO characters
               (user_id, name, description, image_path, settings_json,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, name, description, image_path, settings_json, now, now),
        )
        return int(cursor.lastrowid)


def list_characters(user_id: int | None = None) -> list[dict[str, Any]]:
    query = "SELECT * FROM characters"
    parameters: tuple[Any, ...] = ()
    if user_id is not None:
        query += " WHERE user_id = ?"
        parameters = (user_id,)
    query += " ORDER BY updated_at DESC, id DESC"
    with get_connection() as connection:
        rows = connection.execute(query, parameters).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["settings"] = json.loads(item.pop("settings_json"))
            result.append(item)
        return result


def create_project(
    name: str,
    *,
    user_id: int | None = None,
    description: str = "",
    project_path: str | None = None,
    settings: dict[str, Any] | None = None,
) -> int:
    """Save project metadata; project_path should reference persistent projects/."""
    name = name.strip()
    if not name:
        raise ValueError("Project name cannot be empty.")
    settings_json = json.dumps(settings or {}, ensure_ascii=False)
    now = _utc_now()
    with transaction() as connection:
        cursor = connection.execute(
            """INSERT INTO projects
               (user_id, name, description, project_path, settings_json,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, name, description, project_path, settings_json, now, now),
        )
        return int(cursor.lastrowid)


def list_projects(user_id: int | None = None) -> list[dict[str, Any]]:
    query = "SELECT * FROM projects"
    parameters: tuple[Any, ...] = ()
    if user_id is not None:
        query += " WHERE user_id = ?"
        parameters = (user_id,)
    query += " ORDER BY updated_at DESC, id DESC"
    with get_connection() as connection:
        rows = connection.execute(query, parameters).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["settings"] = json.loads(item.pop("settings_json"))
            result.append(item)
        return result


def set_metadata(key: str, value: Any) -> None:
    """Store application metadata as JSON (not generated media)."""
    key = key.strip()
    if not key:
        raise ValueError("Metadata key cannot be empty.")
    serialized = json.dumps(value, ensure_ascii=False)
    with transaction() as connection:
        connection.execute(
            """INSERT INTO app_metadata (key, value, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET
                   value = excluded.value,
                   updated_at = excluded.updated_at""",
            (key, serialized, _utc_now()),
        )


def get_metadata(key: str, default: Any = None) -> Any:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT value FROM app_metadata WHERE key = ?", (key,)
        ).fetchone()
        return json.loads(row["value"]) if row else default


# Initialize the persistent database when this module is first imported.
DATABASE_PATH = init_db()
