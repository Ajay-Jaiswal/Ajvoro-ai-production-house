
"""
File 58: modules/image_generation_manager.py

Image Generation Manager
- Prepare image-generation jobs.
- Select character and image settings.
- Build reusable positive and negative prompts.
- Track job status.
- Register locally generated images.
- Preview and export image jobs.
- Optional integration with Character Identity Manager.
- Streamlit is imported only inside render().

This module does NOT run an AI image-generation model.
It manages prompts, settings, jobs and generated image files.
"""

from __future__ import annotations

import json
import uuid
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "outputs" / "image_generation"
GENERATED_DIR = OUTPUT_DIR / "generated"
DATA_FILE = DATA_DIR / "image_generation_jobs.json"

IMAGE_STYLES = [
    "Photorealistic",
    "Hollywood Cinematic",
    "3D CGI",
    "Anime",
    "Digital Art",
    "Fantasy",
    "Sci-Fi",
    "Portrait Photography",
    "Custom",
]

ASPECT_RATIOS = [
    "1:1",
    "3:4",
    "4:3",
    "9:16",
    "16:9",
    "21:9",
]

RESOLUTIONS = [
    "512x512",
    "768x768",
    "1024x1024",
    "1280x720",
    "1920x1080",
    "Custom",
]

JOB_STATUSES = [
    "Draft",
    "Ready",
    "Generating",
    "Completed",
    "Failed",
    "Cancelled",
]


class ImageGenerationError(Exception):
    """Base exception for image generation workflow errors."""


def _ensure_directories() -> None:
    for directory in (
        DATA_DIR,
        OUTPUT_DIR,
        GENERATED_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _read_jobs() -> list[dict[str, Any]]:
    _ensure_directories()

    if not DATA_FILE.exists():
        return []

    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        raise ImageGenerationError(
            f"Could not read image job database: {exc}"
        ) from exc

    if not isinstance(data, list):
        raise ImageGenerationError(
            "Image job database must contain a JSON list."
        )

    return [
        item for item in data
        if isinstance(item, dict)
    ]


def _write_jobs(jobs: list[dict[str, Any]]) -> None:
    _ensure_directories()

    temporary = DATA_FILE.with_suffix(".tmp")

    try:
        with temporary.open("w", encoding="utf-8") as file:
            json.dump(
                jobs,
                file,
                indent=4,
                ensure_ascii=False,
            )

        temporary.replace(DATA_FILE)

    except OSError as exc:
        raise ImageGenerationError(
            f"Could not save image jobs: {exc}"
        ) from exc


def _clean_text(value: str | None) -> str:
    return str(value or "").strip()


def _build_prompt(
    character_name: str,
    character_details: str,
    scene_prompt: str,
    visual_style: str,
    lighting: str,
    camera_angle: str,
    composition: str,
    extra_prompt: str,
) -> str:
    parts = [
        f"Character: {character_name}",
        character_details,
        f"Scene: {scene_prompt}",
        f"Visual style: {visual_style}",
        f"Lighting: {lighting}",
        f"Camera angle: {camera_angle}",
        f"Composition: {composition}",
        extra_prompt,
    ]

    return ", ".join(
        part.strip()
        for part in parts
        if part and part.strip()
    )


def create_job(
    character_name: str,
    scene_prompt: str,
    visual_style: str = "Photorealistic",
    negative_prompt: str = "",
    character_details: str = "",
    lighting: str = "Cinematic lighting",
    camera_angle: str = "Eye-level",
    composition: str = "Medium shot",
    aspect_ratio: str = "16:9",
    resolution: str = "1024x1024",
    custom_resolution: str = "",
    seed: int | None = None,
    steps: int = 25,
    guidance_scale: float = 7.0,
    extra_prompt: str = "",
    notes: str = "",
    status: str = "Draft",
) -> dict[str, Any]:
    """Create and save an image-generation job."""

    character_name = _clean_text(character_name)
    scene_prompt = _clean_text(scene_prompt)

    if not character_name:
        raise ValueError("Character name is required.")

    if not scene_prompt:
        raise ValueError("Scene prompt is required.")

    if visual_style not in IMAGE_STYLES:
        raise ValueError("Invalid visual style.")

    if aspect_ratio not in ASPECT_RATIOS:
        raise ValueError("Invalid aspect ratio.")

    if resolution not in RESOLUTIONS:
        raise ValueError("Invalid resolution.")

    if status not in JOB_STATUSES:
        raise ValueError("Invalid job status.")

    if not 1 <= int(steps) <= 150:
        raise ValueError("Steps must be between 1 and 150.")

    if not 1 <= float(guidance_scale) <= 30:
        raise ValueError(
            "Guidance scale must be between 1 and 30."
        )

    if seed is not None and int(seed) < 0:
        raise ValueError("Seed cannot be negative.")

    final_resolution = (
        _clean_text(custom_resolution)
        if resolution == "Custom"
        else resolution
    )

    if resolution == "Custom" and not final_resolution:
        raise ValueError("Enter a custom resolution.")

    prompt = _build_prompt(
        character_name=character_name,
        character_details=_clean_text(character_details),
        scene_prompt=scene_prompt,
        visual_style=visual_style,
        lighting=_clean_text(lighting),
        camera_angle=_clean_text(camera_angle),
        composition=_clean_text(composition),
        extra_prompt=_clean_text(extra_prompt),
    )

    job = {
        "id": uuid.uuid4().hex[:12],
        "character_name": character_name,
        "scene_prompt": scene_prompt,
        "character_details": _clean_text(character_details),
        "visual_style": visual_style,
        "lighting": _clean_text(lighting),
        "camera_angle": _clean_text(camera_angle),
        "composition": _clean_text(composition),
        "positive_prompt": prompt,
        "negative_prompt": _clean_text(negative_prompt),
        "aspect_ratio": aspect_ratio,
        "resolution": final_resolution,
        "seed": int(seed) if seed is not None else None,
        "steps": int(steps),
        "guidance_scale": float(guidance_scale),
        "extra_prompt": _clean_text(extra_prompt),
        "notes": _clean_text(notes),
        "status": status,
        "generated_image": None,
        "error_message": "",
        "created_at": _now(),
        "updated_at": _now(),
    }

    jobs = _read_jobs()
    jobs.append(job)
    _write_jobs(jobs)

    return job


def list_jobs(
    character_name: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """List jobs with optional filters."""

    jobs = _read_jobs()

    if character_name:
        target = character_name.casefold().strip()
        jobs = [
            job for job in jobs
            if job.get("character_name", "").casefold() == target
        ]

    if status and status != "All":
        jobs = [
            job for job in jobs
            if job.get("status") == status
        ]

    return sorted(
        jobs,
        key=lambda job: job.get("created_at", ""),
        reverse=True,
    )


def get_job(job_id: str) -> dict[str, Any] | None:
    """Get one job by ID."""

    return next(
        (
            job for job in _read_jobs()
            if job.get("id") == job_id
        ),
        None,
    )


def update_job_status(
    job_id: str,
    status: str,
    error_message: str = "",
) -> dict[str, Any]:
    """Update a job's status."""

    if status not in JOB_STATUSES:
        raise ValueError("Invalid job status.")

    jobs = _read_jobs()

    for job in jobs:
        if job.get("id") == job_id:
            job["status"] = status
            job["error_message"] = _clean_text(error_message)
            job["updated_at"] = _now()

            _write_jobs(jobs)
            return job

    raise ImageGenerationError("Image job not found.")


def register_generated_image(
    job_id: str,
    image_path: str,
    copy_image: bool = True,
) -> dict[str, Any]:
    """
    Register an image produced by an external/local generator.

    This function does not generate the image itself.
    """

    source = Path(image_path).expanduser()

    if not source.exists() or not source.is_file():
        raise FileNotFoundError(
            f"Generated image does not exist: {source}"
        )

    extension = source.suffix.lower()

    if extension not in {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".bmp",
    }:
        raise ValueError("Unsupported image file format.")

    jobs = _read_jobs()
    target_job = next(
        (job for job in jobs if job.get("id") == job_id),
        None,
    )

    if target_job is None:
        raise ImageGenerationError("Image job not found.")

    _ensure_directories()

    final_path = source.resolve()

    if copy_image:
        destination = (
            GENERATED_DIR
            / f"{job_id}_{uuid.uuid4().hex[:6]}{extension}"
        )

        try:
            shutil.copy2(source, destination)
        except OSError as exc:
            raise ImageGenerationError(
                f"Could not copy generated image: {exc}"
            ) from exc

        final_path = destination

    target_job["generated_image"] = str(final_path)
    target_job["status"] = "Completed"
    target_job["error_message"] = ""
    target_job["updated_at"] = _now()

    _write_jobs(jobs)

    return target_job


def delete_job(
    job_id: str,
    delete_generated_image: bool = False,
) -> bool:
    """Delete a job and optionally its managed output image."""

    jobs = _read_jobs()

    target = next(
        (job for job in jobs if job.get("id") == job_id),
        None,
    )

    if target is None:
        return False

    remaining = [
        job for job in jobs
        if job.get("id") != job_id
    ]

    _write_jobs(remaining)

    if delete_generated_image:
        image_value = target.get("generated_image")

        if image_value:
            try:
                image_path = Path(image_value).resolve()
                managed_dir = GENERATED_DIR.resolve()

                if (
                    image_path.is_relative_to(managed_dir)
                    and image_path.is_file()
                ):
                    image_path.unlink()
            except (OSError, ValueError):
                pass

    return True


def duplicate_job(job_id: str) -> dict[str, Any]:
    """Duplicate a job as a new draft."""

    original = get_job(job_id)

    if original is None:
        raise ImageGenerationError("Image job not found.")

    duplicate = dict(original)
    duplicate["id"] = uuid.uuid4().hex[:12]
    duplicate["status"] = "Draft"
    duplicate["generated_image"] = None
    duplicate["error_message"] = ""
    duplicate["created_at"] = _now()
    duplicate["updated_at"] = _now()
    duplicate["notes"] = (
        f"Duplicated from job {job_id}. "
        + original.get("notes", "")
    ).strip()

    jobs = _read_jobs()
    jobs.append(duplicate)
    _write_jobs(jobs)

    return duplicate


def get_statistics() -> dict[str, int]:
    """Return job counts."""

    jobs = _read_jobs()

    return {
        "total": len(jobs),
        "draft": sum(
            job.get("status") == "Draft" for job in jobs
        ),
        "ready": sum(
            job.get("status") == "Ready" for job in jobs
        ),
        "completed": sum(
            job.get("status") == "Completed" for job in jobs
        ),
        "failed": sum(
            job.get("status") == "Failed" for job in jobs
        ),
        "with_images": sum(
            bool(job.get("generated_image")) for job in jobs
        ),
    }


def export_jobs() -> Path:
    """Export the image-generation job database."""

    _ensure_directories()

    destination = OUTPUT_DIR / (
        "image_jobs_"
        + datetime.now().strftime("%Y%m%d_%H%M%S")
        + ".json"
    )

    payload = {
        "exported_at": _now(),
        "jobs": _read_jobs(),
    }

    with destination.open("w", encoding="utf-8") as file:
        json.dump(
            payload,
            file,
            indent=4,
            ensure_ascii=False,
        )

    return destination


def get_character_names() -> list[str]:
    """
    Try to retrieve character names from the identity manager.

    Failure to import or read that optional module does not stop
    this module. Users can enter a character name manually.
    """

    try:
        from modules import character_identity_manager

        for function_name in (
            "list_characters",
            "get_all_characters",
        ):
            function = getattr(
                character_identity_manager,
                function_name,
                None,
            )

            if callable(function):
                result = function()

                if isinstance(result, list):
                    names = []

                    for item in result:
                        if isinstance(item, dict):
                            name = (
                                item.get("name")
                                or item.get("character_name")
                            )
                            if name:
                                names.append(str(name))
                        elif isinstance(item, str):
                            names.append(item)

                    if names:
                        return sorted(set(names))

    except Exception:
        pass

    return []


def render() -> None:
    """Render this module's Streamlit interface."""

    try:
        import streamlit as st
    except ImportError:
        raise RuntimeError(
            "Streamlit is required for this page. "
            "Install it with: pip install streamlit"
        )

    st.title("Image Generation Manager")
    st.caption(
        "Prepare, organize and track character image-generation jobs."
    )

    try:
        stats = get_statistics()

        columns = st.columns(4)
        columns[0].metric("Total Jobs", stats["total"])
        columns[1].metric("Drafts", stats["draft"])
        columns[2].metric("Completed", stats["completed"])
        columns[3].metric("Generated Images", stats["with_images"])

        tab_create, tab_jobs, tab_settings = st.tabs([
            "Create Image Job",
            "Manage Jobs",
            "Export",
        ])

        with tab_create:
            st.subheader("Create a new image job")

            known_characters = get_character_names()

            if known_characters:
                character_name = st.selectbox(
                    "Choose saved character",
                    [""] + known_characters,
                )
                manual_character = st.text_input(
                    "Or enter another character name",
                )
                if manual_character.strip():
                    character_name = manual_character.strip()
            else:
                character_name = st.text_input(
                    "Character name",
                    placeholder="Example: Eira",
                )

            character_details = st.text_area(
                "Character identity details",
                placeholder=(
                    "Face, hairstyle, eyes, skin tone, clothing, "
                    "distinctive features and other identity details."
                ),
            )

            scene_prompt = st.text_area(
                "Scene prompt",
                height=130,
                placeholder=(
                    "Describe the scene, environment, action "
                    "and important visual details."
                ),
            )

            extra_prompt = st.text_area(
                "Additional prompt details",
                placeholder="Optional extra visual instructions.",
            )

            negative_prompt = st.text_area(
                "Negative prompt",
                value=(
                    "blurry, low quality, distorted face, "
                    "extra fingers, extra limbs, bad anatomy, "
                    "duplicate character, watermark, text"
                ),
            )

            left, right = st.columns(2)

            with left:
                visual_style = st.selectbox(
                    "Visual style",
                    IMAGE_STYLES,
                )
                lighting = st.selectbox(
                    "Lighting",
                    [
                        "Cinematic lighting",
                        "Soft lighting",
                        "Natural daylight",
                        "Golden hour",
                        "Dramatic shadows",
                        "Neon lighting",
                        "Low-key lighting",
                    ],
                )
                camera_angle = st.selectbox(
                    "Camera angle",
                    [
                        "Eye-level",
                        "Low angle",
                        "High angle",
                        "Bird's-eye view",
                        "Dutch angle",
                        "Close-up",
                    ],
                )

            with right:
                composition = st.selectbox(
                    "Composition",
                    [
                        "Close-up",
                        "Medium shot",
                        "Full body",
                        "Wide shot",
                        "Extreme close-up",
                        "Over-the-shoulder",
                    ],
                )
                aspect_ratio = st.selectbox(
                    "Aspect ratio",
                    ASPECT_RATIOS,
                    index=ASPECT_RATIOS.index("16:9"),
                )
                resolution = st.selectbox(
                    "Resolution",
                    RESOLUTIONS,
                    index=RESOLUTIONS.index("1024x1024"),
                )

            custom_resolution = ""

            if resolution == "Custom":
                custom_resolution = st.text_input(
                    "Custom resolution",
                    placeholder="Example: 1536x1024",
                )

            col_a, col_b, col_c = st.columns(3)

            with col_a:
                steps = st.number_input(
                    "Steps",
                    min_value=1,
                    max_value=150,
                    value=25,
                )

            with col_b:
                guidance_scale = st.number_input(
                    "Guidance scale",
                    min_value=1.0,
                    max_value=30.0,
                    value=7.0,
                    step=0.5,
                )

            with col_c:
                seed_enabled = st.checkbox(
                    "Use fixed seed",
                    value=False,
                )
                seed = st.number_input(
                    "Seed",
                    min_value=0,
                    value=12345,
                    disabled=not seed_enabled,
                )

            notes = st.text_area("Job notes")

            if st.button(
                "Create Image Job",
                type="primary",
                use_container_width=True,
            ):
                try:
                    job = create_job(
                        character_name=character_name,
                        scene_prompt=scene_prompt,
                        visual_style=visual_style,
                        negative_prompt=negative_prompt,
                        character_details=character_details,
                        lighting=lighting,
                        camera_angle=camera_angle,
                        composition=composition,
                        aspect_ratio=aspect_ratio,
                        resolution=resolution,
                        custom_resolution=custom_resolution,
                        seed=int(seed) if seed_enabled else None,
                        steps=int(steps),
                        guidance_scale=float(guidance_scale),
                        extra_prompt=extra_prompt,
                        notes=notes,
                        status="Ready",
                    )

                    st.success(
                        f"Image job created: {job['id']}"
                    )
                    st.code(job["positive_prompt"])

                except Exception as exc:
                    st.error(f"Could not create job: {exc}")

        with tab_jobs:
            st.subheader("Image jobs")

            search_name = st.text_input(
                "Filter by character name",
            )

            status_filter = st.selectbox(
                "Filter by status",
                ["All"] + JOB_STATUSES,
            )

            jobs = list_jobs(
                character_name=search_name or None,
                status=status_filter,
            )

            if not jobs:
                st.info("No image jobs found.")
            else:
                for job in jobs:
                    with st.container(border=True):
                        st.markdown(
                            f"**{job.get('character_name', 'Unknown')}**"
                        )

                        st.caption(
                            f"Job ID: {job.get('id')} · "
                            f"Status: {job.get('status')}"
                        )

                        st.write(job.get("scene_prompt", ""))

                        with st.expander("View prompts and settings"):
                            st.markdown("**Positive prompt**")
                            st.code(
                                job.get("positive_prompt", ""),
                                language=None,
                            )

                            st.markdown("**Negative prompt**")
                            st.code(
                                job.get("negative_prompt", ""),
                                language=None,
                            )

                            st.json({
                                "style": job.get("visual_style"),
                                "resolution": job.get("resolution"),
                                "aspect_ratio": job.get("aspect_ratio"),
                                "steps": job.get("steps"),
                                "guidance_scale": job.get("guidance_scale"),
                                "seed": job.get("seed"),
                            })

                        image_value = job.get("generated_image")

                        if image_value:
                            image_path = Path(image_value)

                            if image_path.is_file():
                                st.image(
                                    str(image_path),
                                    caption="Registered generated image",
                                    width=350,
                                )
                            else:
                                st.warning(
                                    "Registered image file is missing."
                                )

                        job_id = job.get("id")

                        status_col, action_col = st.columns(2)

                        with status_col:
                            new_status = st.selectbox(
                                "Update status",
                                JOB_STATUSES,
                                index=(
                                    JOB_STATUSES.index(job["status"])
                                    if job.get("status") in JOB_STATUSES
                                    else 0
                                ),
                                key=f"status_{job_id}",
                            )

                            if st.button(
                                "Save Status",
                                key=f"save_status_{job_id}",
                            ):
                                update_job_status(
                                    job_id,
                                    new_status,
                                )
                                st.success("Status updated.")
                                st.rerun()

                        with action_col:
                            uploaded_image = st.file_uploader(
                                "Register generated image",
                                type=[
                                    "png",
                                    "jpg",
                                    "jpeg",
                                    "webp",
                                    "bmp",
                                ],
                                key=f"image_{job_id}",
                            )

                            if st.button(
                                "Save Generated Image",
                                key=f"register_{job_id}",
                            ):
                                if uploaded_image is None:
                                    st.warning(
                                        "Upload an image first."
                                    )
                                else:
                                    suffix = (
                                        Path(uploaded_image.name).suffix
                                        or ".png"
                                    )

                                    temporary = (
                                        GENERATED_DIR
                                        / f"upload_{uuid.uuid4().hex}{suffix}"
                                    )

                                    try:
                                        _ensure_directories()
                                        temporary.write_bytes(
                                            uploaded_image.getvalue()
                                        )

                                        register_generated_image(
                                            job_id,
                                            str(temporary),
                                            copy_image=True,
                                        )

                                        st.success(
                                            "Generated image registered."
                                        )
                                        st.rerun()

                                    except Exception as exc:
                                        st.error(str(exc))

                                    finally:
                                        temporary.unlink(missing_ok=True)

                        button_col1, button_col2 = st.columns(2)

                        with button_col1:
                            if st.button(
                                "Duplicate Job",
                                key=f"duplicate_{job_id}",
                            ):
                                duplicate = duplicate_job(job_id)
                                st.success(
                                    f"Created duplicate: {duplicate['id']}"
                                )
                                st.rerun()

                        with button_col2:
                            if st.button(
                                "Delete Job",
                                key=f"delete_{job_id}",
                            ):
                                delete_job(
                                    job_id,
                                    delete_generated_image=True,
                                )
                                st.success("Job deleted.")
                                st.rerun()

        with tab_settings:
            st.subheader("Export image jobs")

            if st.button("Create JSON Export"):
                export_path = export_jobs()

                st.success("Export created.")

                st.download_button(
                    "Download JSON",
                    data=export_path.read_bytes(),
                    file_name=export_path.name,
                    mime="application/json",
                )

            st.info(
                "Image generation is not performed by this module. "
                "Connect a compatible local image engine to execute jobs."
            )

    except Exception as exc:
        st.error(
            "Image Generation Manager encountered an error. "
            "Other application modules should remain available."
        )
        st.exception(exc)


def run_tests() -> None:
    """Run basic tests in temporary directories."""

    import tempfile

    global DATA_DIR
    global OUTPUT_DIR
    global GENERATED_DIR
    global DATA_FILE

    old_values = (
        DATA_DIR,
        OUTPUT_DIR,
        GENERATED_DIR,
        DATA_FILE,
    )

    try:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)

            DATA_DIR = base / "data"
            OUTPUT_DIR = base / "outputs"
            GENERATED_DIR = OUTPUT_DIR / "generated"
            DATA_FILE = DATA_DIR / "image_generation_jobs.json"

            _ensure_directories()

            job = create_job(
                character_name="Test Character",
                scene_prompt="Standing in a snowy forest",
                visual_style="Photorealistic",
                negative_prompt="blurry",
                character_details="Black hair and blue eyes",
                aspect_ratio="16:9",
                resolution="1024x1024",
                steps=25,
                guidance_scale=7.0,
                status="Ready",
            )

            assert job["character_name"] == "Test Character"
            assert "snowy forest" in job["positive_prompt"]
            assert len(list_jobs()) == 1

            fetched = get_job(job["id"])
            assert fetched is not None

            updated = update_job_status(
                job["id"],
                "Generating",
            )
            assert updated["status"] == "Generating"

            duplicate = duplicate_job(job["id"])
            assert duplicate["id"] != job["id"]
            assert duplicate["status"] == "Draft"

            sample_image = base / "generated.png"
            sample_image.write_bytes(b"test-image-data")

            registered = register_generated_image(
                job["id"],
                str(sample_image),
                copy_image=True,
            )

            assert registered["status"] == "Completed"
            assert Path(
                registered["generated_image"]
            ).is_file()

            stats = get_statistics()
            assert stats["total"] == 2
            assert stats["completed"] == 1

            exported = export_jobs()
            assert exported.is_file()

            assert delete_job(
                job["id"],
                delete_generated_image=True,
            )

            assert get_job(job["id"]) is None

            print("All Image Generation Manager tests passed.")

    finally:
        (
            DATA_DIR,
            OUTPUT_DIR,
            GENERATED_DIR,
            DATA_FILE,
        ) = old_values


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Image Generation Manager"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run built-in tests",
    )

    args = parser.parse_args()

    if args.test:
        run_tests()
    else:
        print("Image Generation Manager")
        print("Run with --test to execute built-in tests.")
