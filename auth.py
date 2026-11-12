"""Authentication helpers for AI Influencer Studio.

Passwords are stored only as salted PBKDF2-HMAC-SHA256 hashes.
No plaintext password is written to SQLite or Streamlit session state.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import sqlite3
from typing import Any

import database

# 600,000 iterations is a conservative PBKDF2-HMAC-SHA256 work factor.
PBKDF2_ITERATIONS = 600_000
HASH_ALGORITHM = "pbkdf2_sha256"
SALT_BYTES = 16
KEY_BYTES = 32
MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 1024
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
SESSION_USER_KEY = "auth_user"


def _encode_bytes(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode_bytes(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str) -> str:
    """Return a versioned salted PBKDF2 hash suitable for database storage."""
    if not isinstance(password, str):
        raise TypeError("Password must be a string.")
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must contain {MIN_PASSWORD_LENGTH} to "
            f"{MAX_PASSWORD_LENGTH} characters."
        )

    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt,
        PBKDF2_ITERATIONS, dklen=KEY_BYTES,
    )
    return "$".join((
        HASH_ALGORITHM,
        str(PBKDF2_ITERATIONS),
        _encode_bytes(salt),
        _encode_bytes(digest),
    ))


def verify_password(password: str, encoded_hash: str) -> bool:
    """Verify a password without exposing whether a stored hash is malformed."""
    if not isinstance(password, str) or not isinstance(encoded_hash, str):
        return False

    try:
        algorithm, iterations_text, salt_text, digest_text = encoded_hash.split("$")
        if algorithm != HASH_ALGORITHM:
            return False
        iterations = int(iterations_text)
        # Bound stored parameters to avoid maliciously expensive verification.
        if not 100_000 <= iterations <= 2_000_000:
            return False
        salt = _decode_bytes(salt_text)
        expected = _decode_bytes(digest_text)
        if len(salt) != SALT_BYTES or len(expected) != KEY_BYTES:
            return False

        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt,
            iterations, dklen=len(expected),
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, UnicodeError):
        return False


def _validate_registration(
    username: str, password: str, email: str | None
) -> tuple[str, str | None]:
    normalized_username = username.strip() if isinstance(username, str) else ""
    if not USERNAME_PATTERN.fullmatch(normalized_username):
        raise ValueError(
            "Username must be 3–32 characters and contain only letters, "
            "numbers, dots, underscores, or hyphens."
        )
    if not isinstance(password, str) or not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must contain {MIN_PASSWORD_LENGTH} to "
            f"{MAX_PASSWORD_LENGTH} characters."
        )

    normalized_email = email.strip() if isinstance(email, str) and email.strip() else None
    if normalized_email and not EMAIL_PATTERN.fullmatch(normalized_email):
        raise ValueError("Please provide a valid email address.")
    return normalized_username, normalized_email


def register_user(
    username: str,
    password: str,
    email: str | None = None,
) -> dict[str, Any]:
    """Register an account; returns {ok, message, user_id}.

    Only the password hash is passed to database.create_user.
    """
    try:
        normalized_username, normalized_email = _validate_registration(
            username, password, email
        )
        password_hash = hash_password(password)
        user_id = database.create_user(
            normalized_username,
            password_hash=password_hash,
            email=normalized_email,
        )
        return {"ok": True, "message": "Account created successfully.", "user_id": user_id}
    except ValueError as exc:
        return {"ok": False, "message": str(exc), "user_id": None}
    except sqlite3.IntegrityError:
        return {"ok": False, "message": "Username or email is already registered.", "user_id": None}
    except sqlite3.Error:
        return {"ok": False, "message": "Database error while creating account.", "user_id": None}


def _public_user_record(record: dict[str, Any]) -> dict[str, Any]:
    """Remove sensitive fields before returning a user to the UI."""
    return {
        "id": record["id"],
        "username": record["username"],
        "email": record.get("email"),
        "is_active": bool(record.get("is_active", 0)),
        "created_at": record.get("created_at"),
    }


def login_user(
    username: str,
    password: str,
    session_state: Any | None = None,
) -> dict[str, Any]:
    """Verify credentials and optionally store a safe user record in session."""
    if not isinstance(username, str) or not isinstance(password, str):
        return {"ok": False, "message": "Invalid username or password.", "user": None}

    try:
        record = database.get_user_by_username(username.strip())
    except sqlite3.Error:
        return {"ok": False, "message": "Database error during login.", "user": None}

    # Use a generic error to avoid revealing whether an account exists.
    if not record or not verify_password(password, record.get("password_hash", "")):
        return {"ok": False, "message": "Invalid username or password.", "user": None}
    if not bool(record.get("is_active", 0)):
        return {"ok": False, "message": "This account is disabled.", "user": None}

    public_user = _public_user_record(record)
    if session_state is not None:
        session_state[SESSION_USER_KEY] = public_user

    return {"ok": True, "message": "Login successful.", "user": public_user}


def logout_user(session_state: Any | None = None) -> None:
    """Remove authentication state; never leaves credentials in the session."""
    if session_state is None:
        try:
            import streamlit as st
            session_state = st.session_state
        except Exception:
            return
    session_state.pop(SESSION_USER_KEY, None)


def get_current_user(session_state: Any | None = None) -> dict[str, Any] | None:
    """Return the current safe user record, or None when logged out."""
    if session_state is None:
        try:
            import streamlit as st
            session_state = st.session_state
        except Exception:
            return None
    user = session_state.get(SESSION_USER_KEY)
    return user if isinstance(user, dict) else None


def is_authenticated(session_state: Any | None = None) -> bool:
    """Check whether a valid-looking user record is present in session state."""
    user = get_current_user(session_state)
    return bool(user and user.get("id") and user.get("is_active"))
