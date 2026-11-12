
"""
File 63: modules/lip_sync_manager.py

AI Influencer Studio - Lip-Sync Manager

Features:
- Create lip-sync projects
- Upload character video and dialogue audio
- Select voice profiles
- Configure sync settings
- Manage lip-sync job status
- Register completed output videos
- Search, duplicate and delete jobs
- Export JSON and CSV
- Streamlit interface
- Built-in tests

Run:
    python -m modules.lip_sync_manager --test
"""

from __future__ import annotations

import csv
import json
import shutil
import tempfile
import uuid

from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------
# PATH CONFIGURATION
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
ASSET_DIR = BASE_DIR / "assets" / "lip_sync"
OUTPUT_DIR = BASE_DIR / "outputs" / "lip_sync"

VIDEO_INPUT_DIR = ASSET_DIR / "videos"
AUDIO_INPUT_DIR = ASSET_DIR / "audio"
GENERATED_DIR = OUTPUT_DIR / "generated"

DATABASE_FILE = DATA_DIR / "lip_sync_jobs.json"

for folder in (
    DATA_DIR,
    VIDEO_INPUT_DIR,
    AUDIO_INPUT_DIR,
    OUTPUT_DIR,
    GENERATED_DIR
):
    folder.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

VALID_STATUSES = {
    "Draft",
    "Queued",
    "Processing",
    "Completed",
    "Failed",
    "Cancelled"
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _clean(value: Any, limit: int = 3000) -> str:
    return str(value or "").strip()[:limit]


def _read_database(
    database_path: Path | None = None
) -> dict:
    path = database_path or DATABASE_FILE

    if not path.exists():
        return {"jobs": []}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))

        if not isinstance(data, dict):
            return {"jobs": []}

        if not isinstance(data.get("jobs"), list):
            data["jobs"] = []

        return data

    except (OSError, json.JSONDecodeError):
        return {"jobs": []}


def _write_database(
    data: dict,
    database_path: Path | None = None
) -> None:
    path = database_path or DATABASE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_suffix(".tmp")

    temporary.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    temporary.replace(path)


def _find_job(data: dict, job_id: str) -> dict | None:
    return next(
        (
            item for item in data["jobs"]
            if item.get("id") == job_id
        ),
        None
    )


# ---------------------------------------------------------
# FILE STORAGE
# ---------------------------------------------------------

def save_media_file(
    source_path: str | Path,
    media_type: str,
    job_id: str,
    destination_dir: Path | None = None
) -> str:
    """Copy an input video or audio file to managed storage."""

    source = Path(source_path)

    if not source.exists() or not source.is_file():
        raise FileNotFoundError("Media file was not found.")

    allowed = {
        "video": {
            ".mp4", ".mov", ".mkv", ".webm", ".avi"
        },
        "audio": {
            ".wav", ".mp3", ".ogg", ".m4a", ".flac"
        }
    }

    if media_type not in allowed:
        raise ValueError("Media type must be video or audio.")

    if source.suffix.lower() not in allowed[media_type]:
        raise ValueError(
            f"Unsupported {media_type} format."
        )

    if destination_dir is None:
        destination_dir = (
            VIDEO_INPUT_DIR
            if media_type == "video"
            else AUDIO_INPUT_DIR
        )

    destination_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    safe_name = "".join(
        char for char in source.name
        if char.isalnum() or char in "._-"
    )[:100]

    destination = destination_dir / (
        f"{job_id}_{safe_name or 'media'}"
    )

    shutil.copy2(source, destination)

    return str(destination)


# ---------------------------------------------------------
# JOB CREATION
# ---------------------------------------------------------

def create_job(
    character_name: str,
    project_name: str,
    video_path: str,
    audio_path: str,
    voice_profile_id: str = "",
    sync_mode: str = "Audio Driven",
    quality: str = "Standard",
    face_enhancement: bool = False,
    expression_strength: int = 50,
    lip_sync_strength: int = 75,
    frame_rate: int = 25,
    notes: str = "",
    database_path: Path | None = None
) -> dict:
    """Create a lip-sync job using existing input media."""

    character_name = _clean(character_name, 150)
    project_name = _clean(project_name, 200)

    if not character_name:
        raise ValueError("Character name is required.")

    if not project_name:
        raise ValueError("Project name is required.")

    if not video_path or not Path(video_path).is_file():
        raise FileNotFoundError("Character video is required.")

    if not audio_path or not Path(audio_path).is_file():
        raise FileNotFoundError("Dialogue audio is required.")

    if not 0 <= int(expression_strength) <= 100:
        raise ValueError("Expression strength must be 0-100.")

    if not 0 <= int(lip_sync_strength) <= 100:
        raise ValueError("Lip-sync strength must be 0-100.")

    if int(frame_rate) not in (24, 25, 30, 50, 60):
        raise ValueError("Unsupported frame rate.")

    if sync_mode not in (
        "Audio Driven",
        "Phoneme Guided",
        "Expression Focused"
    ):
        raise ValueError("Invalid synchronization mode.")

    if quality not in ("Draft", "Standard", "High"):
        raise ValueError("Invalid quality setting.")

    data = _read_database(database_path)

    job = {
        "id": _new_id(),
        "character_name": character_name,
        "project_name": project_name,
        "video_path": str(Path(video_path).resolve()),
        "audio_path": str(Path(audio_path).resolve()),
        "voice_profile_id": _clean(
            voice_profile_id, 150
        ),
        "sync_mode": sync_mode,
        "quality": quality,
        "face_enhancement": bool(face_enhancement),
        "expression_strength": int(expression_strength),
        "lip_sync_strength": int(lip_sync_strength),
        "frame_rate": int(frame_rate),
        "notes": _clean(notes),
        "status": "Draft",
        "progress": 0,
        "output_video": None,
        "error_message": None,
        "created_at": _now(),
        "updated_at": _now()
    }

    data["jobs"].append(job)
    _write_database(data, database_path)

    return job


# ---------------------------------------------------------
# JOB RETRIEVAL
# ---------------------------------------------------------

def list_jobs(
    character_name: str | None = None,
    status: str | None = None,
    database_path: Path | None = None
) -> list[dict]:
    data = _read_database(database_path)
    jobs = data["jobs"]

    if character_name:
        target = character_name.strip().lower()

        jobs = [
            job for job in jobs
            if job.get("character_name", "").lower()
            == target
        ]

    if status:
        jobs = [
            job for job in jobs
            if job.get("status") == status
        ]

    return sorted(
        jobs,
        key=lambda item: item.get("updated_at", ""),
        reverse=True
    )


def get_job(
    job_id: str,
    database_path: Path | None = None
) -> dict | None:
    data = _read_database(database_path)
    return _find_job(data, job_id)


# ---------------------------------------------------------
# JOB UPDATE
# ---------------------------------------------------------

def update_job(
    job_id: str,
    database_path: Path | None = None,
    **changes
) -> dict:
    allowed = {
        "project_name",
        "voice_profile_id",
        "sync_mode",
        "quality",
        "face_enhancement",
        "expression_strength",
        "lip_sync_strength",
        "frame_rate",
        "notes"
    }

    data = _read_database(database_path)
    job = _find_job(data, job_id)

    if not job:
        raise ValueError("Lip-sync job not found.")

    for key, value in changes.items():
        if key not in allowed:
            continue

        if key == "expression_strength":
            value = int(value)
            if not 0 <= value <= 100:
                raise ValueError("Expression strength must be 0-100.")

        elif key == "lip_sync_strength":
            value = int(value)
            if not 0 <= value <= 100:
                raise ValueError("Lip-sync strength must be 0-100.")

        elif key == "frame_rate":
            value = int(value)
            if value not in (24, 25, 30, 50, 60):
                raise ValueError("Unsupported frame rate.")

        elif key == "sync_mode":
            if value not in (
                "Audio Driven",
                "Phoneme Guided",
                "Expression Focused"
            ):
                raise ValueError("Invalid sync mode.")

        elif key == "quality":
            if value not in ("Draft", "Standard", "High"):
                raise ValueError("Invalid quality setting.")

        elif key == "face_enhancement":
            value = bool(value)

        else:
            value = _clean(value)

        job[key] = value

    job["updated_at"] = _now()

    _write_database(data, database_path)

    return job


# ---------------------------------------------------------
# JOB STATUS
# ---------------------------------------------------------

def update_job_status(
    job_id: str,
    status: str,
    progress: int | None = None,
    error_message: str | None = None,
    database_path: Path | None = None
) -> dict:
    if status not in VALID_STATUSES:
        raise ValueError("Invalid job status.")

    data = _read_database(database_path)
    job = _find_job(data, job_id)

    if not job:
        raise ValueError("Lip-sync job not found.")

    if progress is not None:
        progress = int(progress)

        if not 0 <= progress <= 100:
            raise ValueError("Progress must be 0-100.")

    if status == "Completed":
        progress = 100

    if status in ("Draft", "Queued"):
        progress = 0

    job["status"] = status

    if progress is not None:
        job["progress"] = progress

    job["error_message"] = _clean(
        error_message, 2000
    ) or None

    job["updated_at"] = _now()

    _write_database(data, database_path)

    return job


# ---------------------------------------------------------
# OUTPUT REGISTRATION
# ---------------------------------------------------------

def register_output(
    job_id: str,
    output_video: str | Path,
    database_path: Path | None = None
) -> dict:
    """
    Register an already-generated video.

    This function does not create a video.
    """

    source = Path(output_video)

    if not source.exists() or not source.is_file():
        raise FileNotFoundError("Output video not found.")

    if source.suffix.lower() not in {
        ".mp4", ".mov", ".mkv", ".webm", ".avi"
    }:
        raise ValueError("Unsupported output video format.")

    data = _read_database(database_path)
    job = _find_job(data, job_id)

    if not job:
        raise ValueError("Lip-sync job not found.")

    destination = GENERATED_DIR / (
        f"{job_id}_{source.name}"
    )

    # Avoid copying a file onto itself.
    if source.resolve() != destination.resolve():
        shutil.copy2(source, destination)

    job["output_video"] = str(destination.resolve())
    job["status"] = "Completed"
    job["progress"] = 100
    job["error_message"] = None
    job["updated_at"] = _now()

    _write_database(data, database_path)

    return job


# ---------------------------------------------------------
# DUPLICATE / DELETE
# ---------------------------------------------------------

def duplicate_job(
    job_id: str,
    database_path: Path | None = None
) -> dict:
    data = _read_database(database_path)
    original = _find_job(data, job_id)

    if not original:
        raise ValueError("Lip-sync job not found.")

    duplicate = dict(original)

    duplicate["id"] = _new_id()
    duplicate["project_name"] += " Copy"
    duplicate["status"] = "Draft"
    duplicate["progress"] = 0
    duplicate["output_video"] = None
    duplicate["error_message"] = None
    duplicate["created_at"] = _now()
    duplicate["updated_at"] = _now()

    data["jobs"].append(duplicate)

    _write_database(data, database_path)

    return duplicate


def delete_job(
    job_id: str,
    database_path: Path | None = None
) -> bool:
    data = _read_database(database_path)
    job = _find_job(data, job_id)

    if not job:
        return False

    data["jobs"] = [
        item for item in data["jobs"]
        if item.get("id") != job_id
    ]

    output = job.get("output_video")

    if output:
        # Delete only files inside this module's output folder.
        try:
            output_path = Path(output).resolve()
            output_root = GENERATED_DIR.resolve()

            if output_root in output_path.parents:
                output_path.unlink(missing_ok=True)
        except OSError:
            pass

    _write_database(data, database_path)

    return True


# ---------------------------------------------------------
# SEARCH
# ---------------------------------------------------------

def search_jobs(
    query: str,
    database_path: Path | None = None
) -> list[dict]:
    query = _clean(query).lower()

    if not query:
        return list_jobs(database_path=database_path)

    results = []

    for job in list_jobs(database_path=database_path):
        searchable = " ".join([
            job.get("character_name", ""),
            job.get("project_name", ""),
            job.get("sync_mode", ""),
            job.get("quality", ""),
            job.get("status", ""),
            job.get("notes", "")
        ]).lower()

        if query in searchable:
            results.append(job)

    return results


# ---------------------------------------------------------
# STATISTICS
# ---------------------------------------------------------

def get_statistics(
    database_path: Path | None = None
) -> dict:
    jobs = list_jobs(database_path=database_path)

    status_counts = {
        status: 0 for status in VALID_STATUSES
    }

    for job in jobs:
        status = job.get("status")

        if status in status_counts:
            status_counts[status] += 1

    return {
        "total_jobs": len(jobs),
        "completed": status_counts["Completed"],
        "queued": status_counts["Queued"],
        "processing": status_counts["Processing"],
        "failed": status_counts["Failed"],
        "draft": status_counts["Draft"],
        "status_counts": status_counts
    }


# ---------------------------------------------------------
# EXPORT
# ---------------------------------------------------------

def export_json(
    database_path: Path | None = None,
    output_path: Path | None = None
) -> Path:
    data = _read_database(database_path)

    output_path = output_path or (
        OUTPUT_DIR / f"lip_sync_{_now().replace(':', '-')}.json"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    return output_path


def export_csv(
    database_path: Path | None = None,
    output_path: Path | None = None
) -> Path:
    jobs = list_jobs(database_path=database_path)

    output_path = output_path or (
        OUTPUT_DIR / f"lip_sync_{_now().replace(':', '-')}.csv"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    fields = [
        "id",
        "character_name",
        "project_name",
        "video_path",
        "audio_path",
        "voice_profile_id",
        "sync_mode",
        "quality",
        "face_enhancement",
        "expression_strength",
        "lip_sync_strength",
        "frame_rate",
        "status",
        "progress",
        "output_video",
        "error_message",
        "created_at",
        "updated_at"
    ]

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fields,
            extrasaction="ignore"
        )

        writer.writeheader()
        writer.writerows(jobs)

    return output_path


# ---------------------------------------------------------
# STREAMLIT UI
# ---------------------------------------------------------

def render() -> None:
    import streamlit as st

    st.title("Lip-Sync Manager")

    st.caption(
        "Prepare, organize and track AI character lip-sync jobs."
    )

    create_tab, jobs_tab, output_tab = st.tabs([
        "Create Job",
        "Job Manager",
        "Output Registration"
    ])

    # -----------------------------------------------------
    # CREATE JOB
    # -----------------------------------------------------

    with create_tab:
        st.subheader("Create Lip-Sync Job")

        with st.form("lip_sync_create_form"):

            character = st.text_input(
                "Character Name",
                placeholder="Example: Eira"
            )

            project = st.text_input(
                "Project Name",
                placeholder="Example: Eira Dialogue Scene 01"
            )

            video_upload = st.file_uploader(
                "Character Video",
                type=["mp4", "mov", "mkv", "webm", "avi"],
                key="lip_video_upload"
            )

            audio_upload = st.file_uploader(
                "Dialogue Audio",
                type=["wav", "mp3", "ogg", "m4a", "flac"],
                key="lip_audio_upload"
            )

            voice_profile_id = st.text_input(
                "Voice Profile ID (Optional)"
            )

            sync_mode = st.selectbox(
                "Synchronization Mode",
                [
                    "Audio Driven",
                    "Phoneme Guided",
                    "Expression Focused"
                ]
            )

            quality = st.selectbox(
                "Processing Quality",
                ["Draft", "Standard", "High"]
            )

            face_enhancement = st.checkbox(
                "Enable Face Enhancement",
                value=False
            )

            expression_strength = st.slider(
                "Expression Strength",
                0,
                100,
                50
            )

            lip_strength = st.slider(
                "Lip-Sync Strength",
                0,
                100,
                75
            )

            frame_rate = st.selectbox(
                "Frame Rate",
                [24, 25, 30, 50, 60],
                index=1
            )

            notes = st.text_area(
                "Additional Notes"
            )

            submitted = st.form_submit_button(
                "Create Lip-Sync Job",
                type="primary"
            )

            if submitted:
                video_path = None
                audio_path = None

                try:
                    if not video_upload or not audio_upload:
                        raise ValueError(
                            "Upload both a character video "
                            "and dialogue audio."
                        )

                    temporary_id = _new_id()

                    video_temp = (
                        VIDEO_INPUT_DIR
                        / f"{temporary_id}_{Path(video_upload.name).name}"
                    )

                    audio_temp = (
                        AUDIO_INPUT_DIR
                        / f"{temporary_id}_{Path(audio_upload.name).name}"
                    )

                    video_temp.write_bytes(
                        video_upload.getvalue()
                    )

                    audio_temp.write_bytes(
                        audio_upload.getvalue()
                    )

                    job = create_job(
                        character_name=character,
                        project_name=project,
                        video_path=str(video_temp),
                        audio_path=str(audio_temp),
                        voice_profile_id=voice_profile_id,
                        sync_mode=sync_mode,
                        quality=quality,
                        face_enhancement=face_enhancement,
                        expression_strength=expression_strength,
                        lip_sync_strength=lip_strength,
                        frame_rate=frame_rate,
                        notes=notes
                    )

                    st.success(
                        "Lip-sync job created: " + job["id"]
                    )

                    st.info(
                        "Job saved as Draft. No AI processing "
                        "has started."
                    )

                except Exception as exc:
                    st.error(f"Could not create job: {exc}")

    # -----------------------------------------------------
    # JOB MANAGER
    # -----------------------------------------------------

    with jobs_tab:
        st.subheader("Lip-Sync Job Manager")

        stats = get_statistics()

        col1, col2, col3, col4 = st.columns(4)

        col1.metric("Total", stats["total_jobs"])
        col2.metric("Completed", stats["completed"])
        col3.metric("Queued", stats["queued"])
        col4.metric("Failed", stats["failed"])

        query = st.text_input(
            "Search jobs",
            key="lip_sync_search"
        )

        jobs = (
            search_jobs(query)
            if query
            else list_jobs()
        )

        status_filter = st.selectbox(
            "Filter by Status",
            ["All"] + sorted(VALID_STATUSES)
        )

        if status_filter != "All":
            jobs = [
                job for job in jobs
                if job["status"] == status_filter
            ]

        if not jobs:
            st.info("No lip-sync jobs found.")

        for job in jobs:
            with st.expander(
                f"{job['character_name']} — "
                f"{job['project_name']} "
                f"({job['status']})"
            ):
                st.write("**Job ID:**", job["id"])
                st.write("**Sync Mode:**", job["sync_mode"])
                st.write("**Quality:**", job["quality"])
                st.write("**Frame Rate:**", job["frame_rate"])
                st.write("**Progress:**", f"{job['progress']}%")

                st.progress(
                    max(0, min(100, job["progress"])) / 100
                )

                st.write(
                    "**Input Video:**",
                    Path(job["video_path"]).name
                )

                st.write(
                    "**Input Audio:**",
                    Path(job["audio_path"]).name
                )

                if job.get("error_message"):
                    st.error(job["error_message"])

                with st.form(
                    f"job_status_form_{job['id']}"
                ):
                    new_status = st.selectbox(
                        "Update Status",
                        sorted(VALID_STATUSES),
                        index=sorted(VALID_STATUSES).index(
                            job["status"]
                        ),
                        key=f"status_{job['id']}"
                    )

                    new_progress = st.slider(
                        "Progress",
                        0,
                        100,
                        int(job["progress"]),
                        key=f"progress_{job['id']}"
                    )

                    error_message = st.text_input(
                        "Error Message",
                        value=job.get("error_message") or "",
                        key=f"error_{job['id']}"
                    )

                    update_button = st.form_submit_button(
                        "Update Job"
                    )

                    if update_button:
                        try:
                            update_job_status(
                                job["id"],
                                new_status,
                                new_progress,
                                error_message or None
                            )

                            st.success("Job updated.")
                            st.rerun()

                        except Exception as exc:
                            st.error(str(exc))

                col_a, col_b = st.columns(2)

                with col_a:
                    if st.button(
                        "Duplicate Job",
                        key=f"duplicate_lip_{job['id']}"
                    ):
                        duplicate_job(job["id"])
                        st.success("Job duplicated.")
                        st.rerun()

                with col_b:
                    if st.button(
                        "Delete Job",
                        key=f"delete_lip_{job['id']}"
                    ):
                        st.session_state[
                            "delete_lip_job"
                        ] = job["id"]

                if st.session_state.get(
                    "delete_lip_job"
                ) == job["id"]:

                    st.warning(
                        "Confirm deletion of this job."
                    )

                    if st.button(
                        "Confirm Delete",
                        key=f"confirm_lip_{job['id']}"
                    ):
                        delete_job(job["id"])

                        st.session_state.pop(
                            "delete_lip_job",
                            None
                        )

                        st.success("Job deleted.")
                        st.rerun()

    # -----------------------------------------------------
    # OUTPUT REGISTRATION
    # -----------------------------------------------------

    with output_tab:
        st.subheader("Register Generated Lip-Sync Video")

        draft_jobs = [
            job for job in list_jobs()
            if job["status"] != "Completed"
        ]

        if not draft_jobs:
            st.info("No unfinished jobs available.")
        else:
            job_options = {
                (
                    f"{job['character_name']} — "
                    f"{job['project_name']} [{job['id']}]"
                ): job["id"]
                for job in draft_jobs
            }

            selected = st.selectbox(
                "Select Job",
                list(job_options.keys())
            )

            output_upload = st.file_uploader(
                "Upload Completed Video",
                type=["mp4", "mov", "mkv", "webm", "avi"],
                key="lip_output_upload"
            )

            if st.button("Register Completed Video"):
                try:
                    if not output_upload:
                        raise ValueError(
                            "Please upload a completed video."
                        )

                    temp_output = (
                        GENERATED_DIR
                        / f"upload_{uuid.uuid4().hex}_{Path(output_upload.name).name}"
                    )

                    temp_output.write_bytes(
                        output_upload.getvalue()
                    )

                    result = register_output(
                        job_options[selected],
                        temp_output
                    )

                    st.success(
                        "Output registered for job "
                        + result["id"]
                    )

                except Exception as exc:
                    st.error(str(exc))

        st.divider()

        completed_jobs = [
            job for job in list_jobs()
            if job["status"] == "Completed"
            and job.get("output_video")
        ]

        for job in completed_jobs:
            st.write(
                f"**{job['project_name']}** — "
                f"{job['character_name']}"
            )

            output = Path(job["output_video"])

            if output.is_file():
                st.video(str(output))

    # -----------------------------------------------------
    # EXPORT
    # -----------------------------------------------------

    st.divider()
    st.subheader("Export Lip-Sync Records")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Export JSON"):
            try:
                path = export_json()

                st.download_button(
                    "Download JSON",
                    data=path.read_bytes(),
                    file_name=path.name,
                    mime="application/json"
                )

            except Exception as exc:
                st.error(str(exc))

    with col2:
        if st.button("Export CSV"):
            try:
                path = export_csv()

                st.download_button(
                    "Download CSV",
                    data=path.read_bytes(),
                    file_name=path.name,
                    mime="text/csv"
                )

            except Exception as exc:
                st.error(str(exc))


# ---------------------------------------------------------
# BUILT-IN TESTS
# ---------------------------------------------------------

def run_tests() -> None:
    print("Running Lip-Sync Manager tests...")

    with tempfile.TemporaryDirectory() as temp:
        temp_dir = Path(temp)

        database = temp_dir / "test_jobs.json"

        video = temp_dir / "input.mp4"
        audio = temp_dir / "input.wav"

        video.write_bytes(b"fake video data")
        audio.write_bytes(b"fake audio data")

        # Create job.
        job = create_job(
            character_name="Eira",
            project_name="Eira Scene 01",
            video_path=str(video),
            audio_path=str(audio),
            sync_mode="Audio Driven",
            quality="Standard",
            expression_strength=60,
            lip_sync_strength=80,
            frame_rate=25,
            database_path=database
        )

        assert job["character_name"] == "Eira"
        assert job["status"] == "Draft"

        # Retrieve.
        found = get_job(job["id"], database)
        assert found is not None

        # Update settings.
        update_job(
            job["id"],
            database_path=database,
            lip_sync_strength=90,
            quality="High"
        )

        updated = get_job(job["id"], database)

        assert updated["lip_sync_strength"] == 90
        assert updated["quality"] == "High"

        # Status update.
        update_job_status(
            job["id"],
            "Processing",
            40,
            database_path=database
        )

        processing = get_job(job["id"], database)

        assert processing["status"] == "Processing"
        assert processing["progress"] == 40

        # Search.
        results = search_jobs("Eira", database)
        assert len(results) == 1

        # Duplicate.
        duplicate = duplicate_job(
            job["id"],
            database
        )

        assert duplicate["id"] != job["id"]
        assert duplicate["status"] == "Draft"

        # Register output.
        generated = temp_dir / "result.mp4"
        generated.write_bytes(b"generated video data")

        result = register_output(
            job["id"],
            generated,
            database
        )

        assert result["status"] == "Completed"
        assert result["progress"] == 100
        assert Path(result["output_video"]).exists()

        # Statistics.
        stats = get_statistics(database)

        assert stats["total_jobs"] == 2
        assert stats["completed"] == 1

        # Export.
        json_path = temp_dir / "export.json"
        csv_path = temp_dir / "export.csv"

        export_json(database, json_path)
        export_csv(database, csv_path)

        assert json_path.exists()
        assert csv_path.exists()

        # Delete.
        assert delete_job(job["id"], database)
        assert get_job(job["id"], database) is None

        # Validation.
        try:
            update_job_status(
                duplicate["id"],
                "Unknown",
                database_path=database
            )
            raise AssertionError("Invalid status was accepted.")

        except ValueError:
            pass

    print("All Lip-Sync Manager tests passed.")


# ---------------------------------------------------------
# COMMAND LINE
# ---------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Lip-Sync Manager"
    )

    parser.add_argument(
        "--test",
        action="store_true",
        help="Run built-in tests"
    )

    args = parser.parse_args()

    if args.test:
        run_tests()
    else:
        print("Lip-Sync Manager")
        print("Run with --test to execute built-in tests.")
