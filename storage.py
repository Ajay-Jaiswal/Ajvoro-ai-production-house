"""Safe temporary-output storage for AI Influencer Studio.

Only files inside OUTPUT_DIR and TEMP_DIR are eligible for expiration.
Persistent folders such as assets/, projects/, and database/ are never scanned.
"""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config

_CLEANUP_LOCK = threading.Lock()
_LAST_CLEANUP_MONOTONIC = 0.0


def _managed_root(root: str | Path) -> Path:
    """Return an absolute managed root, creating it if necessary."""
    path = Path(root).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _is_inside(path: Path, root: Path) -> bool:
    """Check lexical containment without resolving the candidate's symlinks."""
    try:
        return os.path.commonpath((str(path), str(root))) == str(root)
    except (ValueError, OSError):
        return False


def _safe_file_path(
    value: str | Path,
    root: str | Path,
    *,
    must_exist: bool = True,
) -> Path:
    """Validate that a path is a regular, non-symlink file under root."""
    managed_root = _managed_root(root)
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = managed_root / candidate
    candidate = Path(os.path.abspath(candidate))

    if candidate == managed_root or not _is_inside(candidate, managed_root):
        raise ValueError("File must be located inside the managed storage folder.")

    # Reject symlinked parent directories and symlink files. This prevents a
    # path inside output/ from redirecting operations into assets/ or elsewhere.
    relative_parts = candidate.relative_to(managed_root).parts
    current = managed_root
    for part in relative_parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("Symbolic links are not accepted in managed storage.")

    if must_exist:
        if not candidate.exists() or not candidate.is_file():
            raise FileNotFoundError(f"Output file does not exist: {candidate}")
    return candidate


def _iter_regular_files(root: Path):
    """Yield regular files without following symlinked directories or files."""
    if not root.exists():
        return
    for current_dir, dir_names, file_names in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current_dir)
        # Prune symlinked directories so os.walk never descends into them.
        dir_names[:] = [
            name for name in dir_names
            if not (current_path / name).is_symlink()
        ]
        for name in file_names:
            item = current_path / name
            try:
                if item.is_symlink() or not item.is_file():
                    continue
                yield item
            except OSError:
                continue


def register_output(path: str | Path) -> dict[str, Any]:
    """Register a completed output file and return its expiry information.

    The file must already exist inside config.OUTPUT_DIR. Its modification
    time is used as the creation/retention timestamp. Registration does not
    copy or move the file.
    """
    output_path = _safe_file_path(path, config.OUTPUT_DIR, must_exist=True)
    stat = output_path.stat()
    created_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    expires_at = datetime.fromtimestamp(
        stat.st_mtime + config.OUTPUT_TTL_SECONDS, tz=timezone.utc
    )
    return {
        "path": str(output_path),
        "name": output_path.name,
        "size_bytes": stat.st_size,
        "created_at": created_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "remaining_seconds": max(
            0, int(stat.st_mtime + config.OUTPUT_TTL_SECONDS - time.time())
        ),
    }


def list_outputs(*, cleanup: bool = True) -> list[dict[str, Any]]:
    """List unexpired output files, newest first.

    By default this also performs a throttled cleanup check before listing.
    """
    if cleanup:
        maybe_cleanup()

    root = _managed_root(config.OUTPUT_DIR)
    now = time.time()
    results: list[dict[str, Any]] = []
    for path in _iter_regular_files(root):
        try:
            item = register_output(path)
            if now - path.stat().st_mtime < config.OUTPUT_TTL_SECONDS:
                results.append(item)
        except (OSError, ValueError):
            continue
    results.sort(key=lambda item: item["created_at"], reverse=True)
    return results


def delete_output(path: str | Path) -> bool:
    """Delete one file only if it is safely located inside OUTPUT_DIR."""
    output_path = _safe_file_path(path, config.OUTPUT_DIR, must_exist=True)
    output_path.unlink()
    return True


def _clean_one_root(root_value: str | Path, now: float) -> dict[str, Any]:
    root = _managed_root(root_value)
    deleted: list[str] = []
    errors: list[str] = []

    for path in _iter_regular_files(root):
        try:
            age_seconds = now - path.stat().st_mtime
            if age_seconds >= config.OUTPUT_TTL_SECONDS:
                # Revalidate immediately before deletion.
                safe_path = _safe_file_path(path, root, must_exist=True)
                safe_path.unlink()
                deleted.append(str(safe_path))
        except (OSError, ValueError) as exc:
            errors.append(f"{path}: {exc}")

    return {"deleted": deleted, "errors": errors}


def cleanup_expired_outputs(
    *,
    now: float | None = None,
    output_dir: str | Path | None = None,
    temp_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Delete expired files from output/ and temp/ only.

    Optional directory/time arguments are provided for isolated tests. The
    one-hour TTL is shared by generated outputs and temporary processing files.
    Empty directories are left in place; persistent folders are never scanned.
    """
    current_time = time.time() if now is None else float(now)
    output_root = config.OUTPUT_DIR if output_dir is None else output_dir
    temporary_root = config.TEMP_DIR if temp_dir is None else temp_dir

    output_result = _clean_one_root(output_root, current_time)
    temp_result = _clean_one_root(temporary_root, current_time)
    return {
        "deleted_count": len(output_result["deleted"]) + len(temp_result["deleted"]),
        "output": output_result,
        "temp": temp_result,
        "checked_at": datetime.fromtimestamp(
            current_time, tz=timezone.utc
        ).isoformat(),
    }


def maybe_cleanup(*, force: bool = False) -> dict[str, Any] | None:
    """Run cleanup at most once per configured interval while the app is active."""
    global _LAST_CLEANUP_MONOTONIC
    now_monotonic = time.monotonic()

    with _CLEANUP_LOCK:
        due = (
            force
            or _LAST_CLEANUP_MONOTONIC == 0.0
            or now_monotonic - _LAST_CLEANUP_MONOTONIC
            >= config.CLEANUP_INTERVAL_SECONDS
        )
        if not due:
            return None
        _LAST_CLEANUP_MONOTONIC = now_monotonic

    return cleanup_expired_outputs()


def get_storage_summary() -> dict[str, Any]:
    """Return a lightweight summary of current output storage usage."""
    files = list_outputs(cleanup=True)
    return {
        "file_count": len(files),
        "total_size_bytes": sum(item["size_bytes"] for item in files),
        "files": files,
        "ttl_seconds": config.OUTPUT_TTL_SECONDS,
    }
