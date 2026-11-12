
"""
AI Influencer Studio
File 42: modules/render_queue.py

Persistent local video render queue.

Features:
- Multiple queued render jobs
- Job priorities
- Pending/running/completed/failed/cancelled states
- Sequential rendering worker
- Job cancellation
- Persistent JSON queue
- Streamlit dashboard
- Integration with video_renderer.py

No cloud services or paid APIs required.

Run tests:
    python -m modules.render_queue --test
"""

from __future__ import annotations

import json
import shutil
import threading
import time
import uuid

from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT_DIR / "data"
QUEUE_FILE = DATA_DIR / "render_queue.json"

OUTPUT_DIR = ROOT_DIR / "outputs" / "rendered_videos"
QUEUE_INPUT_DIR = ROOT_DIR / "temp" / "render_queue"

# ---------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------

STATUSES = {
    "pending",
    "running",
    "completed",
    "failed",
    "cancelled",
}

PRIORITIES = {
    "low": 1,
    "normal": 2,
    "high": 3,
    "urgent": 4,
}

MAX_HISTORY = 300

# ---------------------------------------------------------
# RUNTIME STATE
# ---------------------------------------------------------

_worker_thread: threading.Thread | None = None
_worker_lock = threading.RLock()
_stop_worker = threading.Event()
_cancel_events: dict[str, threading.Event] = {}

# ---------------------------------------------------------
# BASIC HELPERS
# ---------------------------------------------------------

def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def make_id() -> str:
    return uuid.uuid4().hex[:12]


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    QUEUE_INPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_queue(
    path: Path | str | None = None,
) -> list[dict]:

    ensure_directories()

    source = Path(path) if path else QUEUE_FILE

    if not source.exists():
        return []

    try:
        data = json.loads(
            source.read_text(encoding="utf-8")
        )

        if not isinstance(data, list):
            return []

        return [
            item for item in data
            if isinstance(item, dict)
        ]

    except (OSError, json.JSONDecodeError):
        return []


def save_queue(
    jobs: list[dict],
    path: Path | str | None = None,
) -> None:

    ensure_directories()

    destination = Path(path) if path else QUEUE_FILE

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = destination.with_name(
        destination.name + ".tmp"
    )

    temporary.write_text(
        json.dumps(
            jobs[-MAX_HISTORY:],
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    temporary.replace(destination)


# ---------------------------------------------------------
# VALIDATION
# ---------------------------------------------------------

def validate_priority(priority: str) -> str:

    value = str(priority).lower().strip()

    if value not in PRIORITIES:
        raise ValueError(
            f"Invalid priority: {priority}"
        )

    return value


def validate_settings(settings: dict | None) -> dict:

    if settings is None:
        settings = {}

    if not isinstance(settings, dict):
        raise ValueError("Settings must be a dictionary.")

    return dict(settings)


def validate_job(job: dict) -> None:

    if not isinstance(job, dict):
        raise ValueError("Invalid render job.")

    if not job.get("id"):
        raise ValueError("Job ID is missing.")

    if job.get("status") not in STATUSES:
        raise ValueError("Invalid job status.")

    if not job.get("clips"):
        raise ValueError("Job requires video clips.")

    if not job.get("output_path"):
        raise ValueError("Output path is missing.")


# ---------------------------------------------------------
# JOB CRUD
# ---------------------------------------------------------

def add_job(
    clips: list[str | Path],
    output_path: str | Path | None = None,
    settings: dict | None = None,
    audio_files: list[str | Path] | None = None,
    subtitle_file: str | Path | None = None,
    priority: str = "normal",
    name: str = "Video Render",
    queue_path: Path | str | None = None,
) -> dict:

    ensure_directories()

    if not clips:
        raise ValueError("At least one video clip is required.")

    priority = validate_priority(priority)
    settings = validate_settings(settings)

    clip_paths = [
        str(Path(item).expanduser().resolve())
        for item in clips
    ]

    audio_paths = [
        str(Path(item).expanduser().resolve())
        for item in (audio_files or [])
    ]

    subtitle_path = (
        str(Path(subtitle_file).expanduser().resolve())
        if subtitle_file else None
    )

    job_id = make_id()

    if output_path is None:
        output_path = OUTPUT_DIR / f"render_{job_id}.mp4"

    target = Path(output_path).expanduser().resolve()

    if target.suffix.lower() != ".mp4":
        raise ValueError("Output must use the .mp4 extension.")

    job = {
        "id": job_id,
        "name": str(name).strip()[:120] or "Video Render",
        "status": "pending",
        "priority": priority,
        "priority_value": PRIORITIES[priority],
        "clips": clip_paths,
        "audio_files": audio_paths,
        "subtitle_file": subtitle_path,
        "output_path": str(target),
        "settings": settings,
        "progress": 0,
        "created_at": now(),
        "started_at": None,
        "completed_at": None,
        "error": None,
        "result": None,
    }

    validate_job(job)

    with _worker_lock:

        jobs = load_queue(queue_path)

        jobs.append(job)

        save_queue(jobs, queue_path)

    return job


def get_job(
    job_id: str,
    queue_path: Path | str | None = None,
) -> dict | None:

    return next(
        (
            job for job in load_queue(queue_path)
            if job.get("id") == job_id
        ),
        None,
    )


def list_jobs(
    status: str | None = None,
    queue_path: Path | str | None = None,
) -> list[dict]:

    jobs = load_queue(queue_path)

    if status:
        if status not in STATUSES:
            raise ValueError("Invalid status.")

        jobs = [
            job for job in jobs
            if job.get("status") == status
        ]

    return sorted(
        jobs,
        key=lambda job: (
            -PRIORITIES.get(
                job.get("priority", "normal"),
                2,
            ),
            job.get("created_at", ""),
        ),
    )


def update_job(
    job_id: str,
    updates: dict,
    queue_path: Path | str | None = None,
) -> dict:

    if not isinstance(updates, dict):
        raise ValueError("Updates must be a dictionary.")

    protected = {
        "id",
        "clips",
        "audio_files",
        "subtitle_file",
        "output_path",
    }

    if protected.intersection(updates):
        raise ValueError(
            "Input files and job ID cannot be changed."
        )

    with _worker_lock:

        jobs = load_queue(queue_path)

        for job in jobs:

            if job.get("id") != job_id:
                continue

            if job.get("status") != "pending":
                raise ValueError(
                    "Only pending jobs can be updated."
                )

            if "priority" in updates:

                priority = validate_priority(
                    updates["priority"]
                )

                job["priority"] = priority
                job["priority_value"] = PRIORITIES[priority]

            if "name" in updates:
                job["name"] = str(
                    updates["name"]
                ).strip()[:120]

            if "settings" in updates:
                job["settings"] = validate_settings(
                    updates["settings"]
                )

            save_queue(jobs, queue_path)

            return job

    raise ValueError("Render job not found.")


# ---------------------------------------------------------
# JOB CONTROL
# ---------------------------------------------------------

def cancel_job(
    job_id: str,
    queue_path: Path | str | None = None,
) -> bool:

    with _worker_lock:

        job = get_job(job_id, queue_path)

        if not job:
            return False

        if job["status"] == "pending":

            jobs = load_queue(queue_path)

            for item in jobs:

                if item["id"] == job_id:
                    item["status"] = "cancelled"
                    item["completed_at"] = now()
                    item["progress"] = 0

            save_queue(jobs, queue_path)

            return True

        if job["status"] == "running":

            event = _cancel_events.get(job_id)

            if event:
                event.set()
                return True

        return False


def retry_job(
    job_id: str,
    queue_path: Path | str | None = None,
) -> dict:

    with _worker_lock:

        jobs = load_queue(queue_path)

        original = next(
            (
                item for item in jobs
                if item.get("id") == job_id
            ),
            None,
        )

        if not original:
            raise ValueError("Job not found.")

        if original["status"] not in {
            "failed",
            "cancelled",
        }:
            raise ValueError(
                "Only failed or cancelled jobs can be retried."
            )

        duplicate = dict(original)

        duplicate["id"] = make_id()
        duplicate["status"] = "pending"
        duplicate["progress"] = 0
        duplicate["created_at"] = now()
        duplicate["started_at"] = None
        duplicate["completed_at"] = None
        duplicate["error"] = None
        duplicate["result"] = None
        duplicate["name"] = (
            str(original.get("name", "Render"))
            + " - Retry"
        )

        jobs.append(duplicate)

        save_queue(jobs, queue_path)

        return duplicate


def clear_finished(
    queue_path: Path | str | None = None,
) -> int:

    with _worker_lock:

        jobs = load_queue(queue_path)

        active = [
            job for job in jobs
            if job.get("status") in {
                "pending",
                "running",
            }
        ]

        removed = len(jobs) - len(active)

        save_queue(active, queue_path)

        return removed


# ---------------------------------------------------------
# WORKER
# ---------------------------------------------------------

def _update_progress(
    job_id: str,
    progress: float,
    queue_path: Path | str | None = None,
) -> None:

    with _worker_lock:

        jobs = load_queue(queue_path)

        for job in jobs:

            if job.get("id") == job_id:

                job["progress"] = max(
                    0,
                    min(100, int(progress)),
                )

                break

        save_queue(jobs, queue_path)


def _mark_job(
    job_id: str,
    status: str,
    error: str | None = None,
    result: dict | None = None,
    queue_path: Path | str | None = None,
) -> None:

    if status not in STATUSES:
        raise ValueError("Invalid job status.")

    with _worker_lock:

        jobs = load_queue(queue_path)

        for job in jobs:

            if job.get("id") != job_id:
                continue

            job["status"] = status
            job["error"] = error
            job["result"] = result

            if status == "running":
                job["started_at"] = now()

            if status in {
                "completed",
                "failed",
                "cancelled",
            }:
                job["completed_at"] = now()

            if status == "completed":
                job["progress"] = 100

            break

        save_queue(jobs, queue_path)


def _next_pending(
    queue_path: Path | str | None = None,
) -> dict | None:

    pending = list_jobs(
        status="pending",
        queue_path=queue_path,
    )

    return pending[0] if pending else None


def process_one_job(
    queue_path: Path | str | None = None,
    renderer: Any = None,
) -> dict | None:

    """
    Process one pending job.

    renderer is injectable for testing.
    """

    if renderer is None:

        from modules.video_renderer import render_video

        renderer = render_video

    with _worker_lock:

        job = _next_pending(queue_path)

        if not job:
            return None

        job_id = job["id"]

        cancel_event = threading.Event()

        _cancel_events[job_id] = cancel_event

        _mark_job(
            job_id,
            "running",
            queue_path=queue_path,
        )

    def progress_callback(value: float):
        _update_progress(
            job_id,
            value,
            queue_path,
        )

    try:

        result = renderer(
            clips=job["clips"],
            output_path=job["output_path"],
            settings=job.get("settings", {}),
            audio_files=job.get("audio_files", []),
            subtitle_file=job.get("subtitle_file"),
            progress_callback=progress_callback,
            cancel_event=cancel_event,
        )

        if cancel_event.is_set():

            _mark_job(
                job_id,
                "cancelled",
                queue_path=queue_path,
            )

        else:

            _mark_job(
                job_id,
                "completed",
                result=result,
                queue_path=queue_path,
            )

    except Exception as exc:

        status = (
            "cancelled"
            if cancel_event.is_set()
            else "failed"
        )

        _mark_job(
            job_id,
            status,
            error=str(exc),
            queue_path=queue_path,
        )

    finally:

        with _worker_lock:
            _cancel_events.pop(job_id, None)

    return get_job(job_id, queue_path)


# ---------------------------------------------------------
# BACKGROUND WORKER
# ---------------------------------------------------------

def _worker_loop(
    idle_sleep: float = 2,
) -> None:

    while not _stop_worker.is_set():

        try:

            job = process_one_job()

            if job is None:
                _stop_worker.wait(idle_sleep)

        except Exception:
            _stop_worker.wait(idle_sleep)


def start_worker() -> bool:

    global _worker_thread

    with _worker_lock:

        if (
            _worker_thread is not None
            and _worker_thread.is_alive()
        ):
            return False

        _stop_worker.clear()

        _worker_thread = threading.Thread(
            target=_worker_loop,
            daemon=True,
            name="AIStudioRenderQueue",
        )

        _worker_thread.start()

        return True


def stop_worker(
    timeout: float = 5,
) -> bool:

    _stop_worker.set()

    thread = _worker_thread

    if thread and thread.is_alive():
        thread.join(timeout=timeout)

    return not (
        thread and thread.is_alive()
    )


def worker_running() -> bool:

    return bool(
        _worker_thread
        and _worker_thread.is_alive()
    )


# ---------------------------------------------------------
# QUEUE STATISTICS
# ---------------------------------------------------------

def get_statistics(
    queue_path: Path | str | None = None,
) -> dict:

    jobs = load_queue(queue_path)

    stats = {
        "total": len(jobs),
        "pending": 0,
        "running": 0,
        "completed": 0,
        "failed": 0,
        "cancelled": 0,
    }

    for job in jobs:

        status = job.get("status")

        if status in stats:
            stats[status] += 1

    return stats


# ---------------------------------------------------------
# STREAMLIT DASHBOARD
# ---------------------------------------------------------

def render(st: Any) -> None:

    ensure_directories()

    st.title("Render Queue Manager")

    st.caption(
        "Manage multiple local video rendering jobs."
    )

    stats = get_statistics()

    columns = st.columns(5)

    for column, key in zip(
        columns,
        [
            "pending",
            "running",
            "completed",
            "failed",
            "cancelled",
        ],
    ):

        column.metric(
            key.title(),
            stats[key],
        )

    worker_status = worker_running()

    if worker_status:
        st.success("Background render worker is running.")
    else:
        st.info("Background render worker is stopped.")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Start Queue Worker"):
            if start_worker():
                st.success("Worker started.")
            else:
                st.info("Worker is already running.")

    with col2:
        if st.button("Stop Queue Worker"):
            if stop_worker():
                st.success("Worker stopped.")
            else:
                st.warning(
                    "Worker is still finishing its current operation."
                )

    with col3:
        if st.button("Refresh Queue"):
            st.rerun()

    st.divider()

    st.subheader("Add a new render job")

    with st.form("add_render_job"):

        clips = st.text_area(
            "Video clip paths (one path per line)",
            placeholder=(
                r"C:\Videos\clip1.mp4" + "\n"
                + r"C:\Videos\clip2.mp4"
            ),
        )

        audio = st.text_area(
            "Optional audio paths (one per line)",
            placeholder=r"C:\Audio\background.mp3",
        )

        subtitle = st.text_input(
            "Optional SRT subtitle path"
        )

        output = st.text_input(
            "Output MP4 path",
            value=str(
                OUTPUT_DIR / "queued_video.mp4"
            ),
        )

        job_name = st.text_input(
            "Job name",
            value="My Video Render",
        )

        priority = st.selectbox(
            "Priority",
            list(PRIORITIES.keys()),
            index=1,
        )

        resolution = st.selectbox(
            "Resolution",
            list(
                ["480p", "720p", "1080p"]
            ),
            index=1,
        )

        fps = st.selectbox(
            "FPS",
            [24, 25, 30, 60],
            index=0,
        )

        quality = st.selectbox(
            "Quality",
            list(
                [
                    "CPU Fast",
                    "Balanced",
                    "High Quality",
                ]
            ),
        )

        submitted = st.form_submit_button(
            "Add to Render Queue",
            type="primary",
        )

        if submitted:

            try:

                clip_list = [
                    line.strip()
                    for line in clips.splitlines()
                    if line.strip()
                ]

                audio_list = [
                    line.strip()
                    for line in audio.splitlines()
                    if line.strip()
                ]

                if not clip_list:
                    raise ValueError(
                        "Enter at least one video path."
                    )

                job = add_job(
                    clips=clip_list,
                    output_path=output,
                    audio_files=audio_list,
                    subtitle_file=subtitle or None,
                    settings={
                        "resolution": resolution,
                        "fps": fps,
                        "quality": quality,
                        "threads": 2,
                        "include_audio": bool(audio_list),
                        "burn_subtitles": bool(subtitle),
                    },
                    priority=priority,
                    name=job_name,
                )

                st.success(
                    f"Job added successfully: {job['id']}"
                )

                st.rerun()

            except Exception as exc:
                st.error(str(exc))

    st.divider()

    st.subheader("Render jobs")

    jobs = list_jobs()

    if not jobs:
        st.info("No render jobs have been added.")
        return

    for job in jobs:

        with st.container(border=True):

            st.write(
                f"**{job.get('name', 'Render Job')}**"
            )

            st.caption(
                f"ID: {job['id']} | "
                f"Priority: {job.get('priority')} | "
                f"Created: {job.get('created_at')}"
            )

            status = job.get("status", "unknown")

            st.write(
                f"Status: **{status.upper()}**"
            )

            if status == "running":
                st.progress(
                    max(
                        0,
                        min(
                            100,
                            int(job.get("progress", 0)),
                        ),
                    )
                )

            st.caption(
                f"Output: {job.get('output_path')}"
            )

            if job.get("error"):
                st.error(job["error"])

            button1, button2 = st.columns(2)

            with button1:

                if status == "pending":

                    if st.button(
                        "Cancel",
                        key=f"cancel_{job['id']}",
                    ):
                        cancel_job(job["id"])
                        st.rerun()

                elif status in {"failed", "cancelled"}:

                    if st.button(
                        "Retry",
                        key=f"retry_{job['id']}",
                    ):
                        retry_job(job["id"])
                        st.rerun()

            with button2:

                if status == "pending":

                    if st.button(
                        "Make Urgent",
                        key=f"urgent_{job['id']}",
                    ):
                        update_job(
                            job["id"],
                            {"priority": "urgent"},
                        )
                        st.rerun()

    st.divider()

    if st.button("Clear Finished Jobs"):

        removed = clear_finished()

        st.success(
            f"Removed {removed} finished jobs."
        )

        st.rerun()


# ---------------------------------------------------------
# BUILT-IN TESTS
# ---------------------------------------------------------

def run_tests() -> bool:

    import tempfile
    import unittest

    class RenderQueueTests(unittest.TestCase):

        def setUp(self):

            self.temp = tempfile.TemporaryDirectory()

            self.root = Path(self.temp.name)

            self.queue_file = (
                self.root / "queue.json"
            )

            self.video = (
                self.root / "clip.mp4"
            )

            self.video.write_bytes(b"video")

        def tearDown(self):
            self.temp.cleanup()

        def test_add_job(self):

            job = add_job(
                [self.video],
                queue_path=self.queue_file,
            )

            self.assertEqual(
                job["status"],
                "pending",
            )

        def test_invalid_priority(self):

            with self.assertRaises(ValueError):
                validate_priority("unknown")

        def test_list_jobs(self):

            add_job(
                [self.video],
                priority="low",
                queue_path=self.queue_file,
            )

            add_job(
                [self.video],
                priority="urgent",
                queue_path=self.queue_file,
            )

            jobs = list_jobs(
                queue_path=self.queue_file
            )

            self.assertEqual(
                jobs[0]["priority"],
                "urgent",
            )

        def test_cancel_pending(self):

            job = add_job(
                [self.video],
                queue_path=self.queue_file,
            )

            self.assertTrue(
                cancel_job(
                    job["id"],
                    self.queue_file,
                )
            )

            self.assertEqual(
                get_job(
                    job["id"],
                    self.queue_file,
                )["status"],
                "cancelled",
            )

        def test_retry_job(self):

            job = add_job(
                [self.video],
                queue_path=self.queue_file,
            )

            jobs = load_queue(self.queue_file)

            jobs[0]["status"] = "failed"

            save_queue(
                jobs,
                self.queue_file,
            )

            retry = retry_job(
                job["id"],
                self.queue_file,
            )

            self.assertNotEqual(
                retry["id"],
                job["id"],
            )

            self.assertEqual(
                retry["status"],
                "pending",
            )

        def test_update_priority(self):

            job = add_job(
                [self.video],
                queue_path=self.queue_file,
            )

            updated = update_job(
                job["id"],
                {"priority": "high"},
                self.queue_file,
            )

            self.assertEqual(
                updated["priority"],
                "high",
            )

        def test_statistics(self):

            add_job(
                [self.video],
                queue_path=self.queue_file,
            )

            stats = get_statistics(
                self.queue_file
            )

            self.assertEqual(
                stats["pending"],
                1,
            )

        def test_clear_finished(self):

            job = add_job(
                [self.video],
                queue_path=self.queue_file,
            )

            jobs = load_queue(self.queue_file)

            jobs[0]["status"] = "completed"

            save_queue(
                jobs,
                self.queue_file,
            )

            removed = clear_finished(
                self.queue_file
            )

            self.assertEqual(removed, 1)

        def test_process_one_job(self):

            job = add_job(
                [self.video],
                queue_path=self.queue_file,
            )

            def fake_renderer(**kwargs):

                callback = kwargs.get(
                    "progress_callback"
                )

                if callback:
                    callback(50)

                return {
                    "success": True,
                    "output_path": kwargs["output_path"],
                }

            result = process_one_job(
                queue_path=self.queue_file,
                renderer=fake_renderer,
            )

            self.assertEqual(
                result["status"],
                "completed",
            )

            self.assertEqual(
                result["progress"],
                100,
            )

        def test_failed_renderer(self):

            job = add_job(
                [self.video],
                queue_path=self.queue_file,
            )

            def fake_renderer(**kwargs):
                raise RuntimeError("Test failure")

            result = process_one_job(
                queue_path=self.queue_file,
                renderer=fake_renderer,
            )

            self.assertEqual(
                result["status"],
                "failed",
            )

            self.assertIn(
                "Test failure",
                result["error"],
            )

        def test_invalid_output(self):

            with self.assertRaises(ValueError):

                add_job(
                    [self.video],
                    output_path=self.root / "output.avi",
                    queue_path=self.queue_file,
                )

        def test_get_missing_job(self):

            self.assertIsNone(
                get_job(
                    "missing",
                    self.queue_file,
                )
            )

        def test_invalid_status_filter(self):

            with self.assertRaises(ValueError):
                list_jobs(
                    status="unknown",
                    queue_path=self.queue_file,
                )

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        RenderQueueTests
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

    print("AI Influencer Studio - Render Queue")
    print(
        "Run tests: "
        "python -m modules.render_queue --test"
    )

    print("Statistics:", get_statistics())
