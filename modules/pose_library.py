
"""
AI Influencer Studio
File 33: modules/pose_library.py

Local pose library for AI influencer characters.

Features:
- Create, edit, duplicate and delete poses.
- Link poses to saved characters.
- Upload local pose reference images.
- Search and filter poses.
- Build reusable AI pose prompts.
- Export pose records as JSON.

Note:
This module prepares prompts and organizes references.
It does not perform actual AI pose generation or motion transfer.
"""

from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------
# OPTIONAL MODULE INTEGRATION
# ---------------------------------------------------------

try:
    from modules import character_consistency
except ImportError:
    character_consistency = None


# ---------------------------------------------------------
# PATHS AND SETTINGS
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
POSE_DIR = PROJECT_ROOT / "assets" / "pose_references"

DATABASE_FILE = DATA_DIR / "pose_library.json"

ALLOWED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}

MAX_IMAGE_SIZE_MB = 15
MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024

POSE_CATEGORIES = [
    "Standing",
    "Walking",
    "Sitting",
    "Running",
    "Portrait",
    "Fashion",
    "Action",
    "Dance",
    "Cinematic",
    "Custom",
]

POSE_FIELDS = [
    "name",
    "category",
    "description",
    "body_position",
    "head_position",
    "arm_position",
    "hand_position",
    "leg_position",
    "facial_expression",
    "camera_angle",
    "camera_distance",
    "lighting",
    "background",
    "visual_style",
    "negative_prompt",
]


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_id(value: str) -> str:
    value = str(value or "").strip()

    if not value:
        raise ValueError("ID is required.")

    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "_", value)

    if cleaned in {".", ".."}:
        raise ValueError("Invalid ID.")

    return cleaned[:100]


def _safe_filename(filename: str) -> str:
    name = Path(str(filename or "reference.png")).name
    extension = Path(name).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(
            "Only PNG, JPG, JPEG and WEBP images are supported."
        )

    stem = re.sub(
        r"[^a-zA-Z0-9_-]",
        "_",
        Path(name).stem,
    ).strip("_") or "reference"

    return f"{stem[:60]}{extension}"


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def _ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    POSE_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# DATABASE
# ---------------------------------------------------------

def load_database(
    path: Path | str | None = None,
) -> dict:
    database_path = Path(path) if path else DATABASE_FILE

    if not database_path.exists():
        return {
            "version": 1,
            "updated_at": _now(),
            "poses": [],
        }

    try:
        with database_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            raise ValueError("Invalid pose database.")

        if not isinstance(data.get("poses"), list):
            data["poses"] = []

        data.setdefault("version", 1)
        data.setdefault("updated_at", _now())

        return data

    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(
            f"Could not read pose database: {exc}"
        ) from exc


def save_database(
    database: dict,
    path: Path | str | None = None,
) -> None:
    database_path = Path(path) if path else DATABASE_FILE
    database_path.parent.mkdir(parents=True, exist_ok=True)

    database["version"] = 1
    database["updated_at"] = _now()

    temporary = database_path.with_name(
        database_path.name + ".tmp"
    )

    with temporary.open("w", encoding="utf-8") as file:
        json.dump(
            database,
            file,
            indent=4,
            ensure_ascii=False,
        )

    temporary.replace(database_path)


# ---------------------------------------------------------
# CHARACTER INTEGRATION
# ---------------------------------------------------------

def list_characters() -> list[dict]:
    if character_consistency is None:
        return []

    try:
        return character_consistency.list_characters()
    except Exception:
        return []


def validate_character(character_id: str) -> bool:
    """Validate a character ID if character module is available."""
    if not character_id:
        return True

    if character_consistency is None:
        return True

    try:
        return bool(
            character_consistency.get_character(character_id)
        )
    except Exception:
        return False


# ---------------------------------------------------------
# POSE VALIDATION AND CRUD
# ---------------------------------------------------------

def validate_pose(details: dict) -> dict:
    if not isinstance(details, dict):
        raise ValueError("Pose details must be a dictionary.")

    name = str(details.get("name", "")).strip()

    if not name:
        raise ValueError("Pose name is required.")

    category = str(
        details.get("category", "Custom")
    ).strip()

    if category not in POSE_CATEGORIES:
        category = "Custom"

    cleaned = {
        "name": name[:100],
        "category": category,
    }

    for field in POSE_FIELDS:
        if field in {"name", "category"}:
            continue

        cleaned[field] = str(
            details.get(field, "") or ""
        ).strip()[:2000]

    character_id = str(
        details.get("character_id", "") or ""
    ).strip()

    if character_id and not validate_character(character_id):
        raise ValueError(
            f"Character '{character_id}' was not found."
        )

    cleaned["character_id"] = character_id

    return cleaned


def create_pose(
    details: dict,
    path: Path | str | None = None,
) -> dict:
    database = load_database(path)
    cleaned = validate_pose(details)

    pose = {
        "id": uuid.uuid4().hex[:12],
        **cleaned,
        "reference_images": [],
        "created_at": _now(),
        "updated_at": _now(),
    }

    database["poses"].append(pose)
    save_database(database, path)

    return pose.copy()


def get_pose(
    pose_id: str,
    path: Path | str | None = None,
) -> dict | None:
    database = load_database(path)

    for pose in database["poses"]:
        if pose.get("id") == pose_id:
            return pose.copy()

    return None


def list_poses(
    search: str = "",
    category: str = "",
    character_id: str = "",
    path: Path | str | None = None,
) -> list[dict]:
    database = load_database(path)

    search_text = str(search or "").strip().lower()
    results = []

    for pose in database["poses"]:
        if category and pose.get("category") != category:
            continue

        if (
            character_id
            and pose.get("character_id") != character_id
        ):
            continue

        searchable = " ".join(
            str(pose.get(field, ""))
            for field in POSE_FIELDS
        ).lower()

        if search_text and search_text not in searchable:
            continue

        results.append(pose.copy())

    results.sort(
        key=lambda item: item.get("updated_at", ""),
        reverse=True,
    )

    return results


def update_pose(
    pose_id: str,
    updates: dict,
    path: Path | str | None = None,
) -> dict:
    database = load_database(path)

    for index, pose in enumerate(database["poses"]):
        if pose.get("id") != pose_id:
            continue

        merged = {
            **pose,
            **updates,
        }

        cleaned = validate_pose(merged)

        database["poses"][index] = {
            **pose,
            **cleaned,
            "updated_at": _now(),
        }

        save_database(database, path)

        return database["poses"][index].copy()

    raise ValueError("Pose not found.")


def duplicate_pose(
    pose_id: str,
    new_name: str | None = None,
    path: Path | str | None = None,
) -> dict:
    original = get_pose(pose_id, path)

    if not original:
        raise ValueError("Pose not found.")

    details = {
        field: original.get(field, "")
        for field in POSE_FIELDS
    }

    details["character_id"] = original.get(
        "character_id", ""
    )

    details["name"] = (
        new_name or f"{original['name']} Copy"
    )

    duplicate = create_pose(details, path)

    # Copy registered reference images to a separate pose folder.
    for image in original.get("reference_images", []):
        image_path = get_reference_image_path(image)

        if image_path and image_path.exists():
            try:
                add_reference_image(
                    duplicate["id"],
                    image_path.read_bytes(),
                    image_path.name,
                    path=path,
                )
            except Exception:
                pass

    return get_pose(duplicate["id"], path)


def delete_pose(
    pose_id: str,
    path: Path | str | None = None,
    asset_root: Path | str | None = None,
) -> bool:
    database = load_database(path)

    pose = next(
        (
            item for item in database["poses"]
            if item.get("id") == pose_id
        ),
        None,
    )

    if pose is None:
        return False

    # Remove only registered reference files.
    for image in pose.get("reference_images", []):
        image_path = get_reference_image_path(
            image,
            asset_root=asset_root,
        )

        if image_path:
            try:
                image_path.unlink(missing_ok=True)
            except OSError:
                pass

    database["poses"] = [
        item for item in database["poses"]
        if item.get("id") != pose_id
    ]

    save_database(database, path)

    return True


# ---------------------------------------------------------
# REFERENCE IMAGE MANAGEMENT
# ---------------------------------------------------------

def add_reference_image(
    pose_id: str,
    image_bytes: bytes,
    filename: str,
    path: Path | str | None = None,
    asset_root: Path | str | None = None,
) -> dict:
    database_path = Path(path) if path else DATABASE_FILE
    gallery_root = Path(asset_root) if asset_root else POSE_DIR

    if not isinstance(image_bytes, bytes) or not image_bytes:
        raise ValueError("Image data is empty.")

    if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
        raise ValueError(
            f"Maximum image size is {MAX_IMAGE_SIZE_MB} MB."
        )

    safe_name = _safe_filename(filename)
    safe_pose_id = _safe_id(pose_id)

    database = load_database(database_path)

    pose = next(
        (
            item for item in database["poses"]
            if item.get("id") == pose_id
        ),
        None,
    )

    if pose is None:
        raise ValueError("Pose not found.")

    pose_folder = gallery_root / safe_pose_id
    pose_folder.mkdir(parents=True, exist_ok=True)

    if not _inside(pose_folder, gallery_root):
        raise ValueError("Invalid pose folder.")

    image_id = uuid.uuid4().hex[:12]
    extension = Path(safe_name).suffix
    stored_name = f"{image_id}{extension}"

    destination = pose_folder / stored_name

    if not _inside(destination, gallery_root):
        raise ValueError("Invalid image destination.")

    with destination.open("xb") as file:
        file.write(image_bytes)

    record = {
        "id": image_id,
        "filename": safe_name,
        "stored_filename": stored_name,
        "relative_path": str(
            destination.relative_to(gallery_root)
        ),
        "size_bytes": len(image_bytes),
        "created_at": _now(),
    }

    try:
        pose.setdefault("reference_images", []).append(record)
        pose["updated_at"] = _now()
        save_database(database, database_path)

    except Exception:
        destination.unlink(missing_ok=True)
        raise

    return record.copy()


def get_reference_image_path(
    record: dict,
    asset_root: Path | str | None = None,
) -> Path | None:
    gallery_root = Path(asset_root) if asset_root else POSE_DIR

    relative_path = record.get("relative_path")

    if not relative_path:
        return None

    image_path = gallery_root / relative_path

    if not _inside(image_path, gallery_root):
        return None

    if not image_path.is_file():
        return None

    if image_path.suffix.lower() not in ALLOWED_EXTENSIONS:
        return None

    return image_path


def delete_reference_image(
    pose_id: str,
    image_id: str,
    path: Path | str | None = None,
    asset_root: Path | str | None = None,
) -> bool:
    database_path = Path(path) if path else DATABASE_FILE
    database = load_database(database_path)

    pose = next(
        (
            item for item in database["poses"]
            if item.get("id") == pose_id
        ),
        None,
    )

    if pose is None:
        return False

    images = pose.get("reference_images", [])

    target = next(
        (
            image for image in images
            if image.get("id") == image_id
        ),
        None,
    )

    if target is None:
        return False

    image_path = get_reference_image_path(
        target,
        asset_root=asset_root,
    )

    pose["reference_images"] = [
        image for image in images
        if image.get("id") != image_id
    ]

    pose["updated_at"] = _now()
    save_database(database, database_path)

    if image_path:
        try:
            image_path.unlink(missing_ok=True)
        except OSError:
            return False

    return True


# ---------------------------------------------------------
# PROMPT BUILDER
# ---------------------------------------------------------

def build_pose_prompt(
    pose_id: str | None = None,
    pose: dict | None = None,
    include_negative: bool = True,
) -> str:
    """Build a reusable text prompt from a saved pose."""
    if pose is None:
        if not pose_id:
            raise ValueError("Provide a pose ID or pose data.")

        pose = get_pose(pose_id)

    if not pose:
        raise ValueError("Pose not found.")

    sections = []

    name = pose.get("name", "Custom Pose")
    sections.append(f"Pose: {name}")

    prompt_fields = [
        ("Category", "category"),
        ("Description", "description"),
        ("Body position", "body_position"),
        ("Head position", "head_position"),
        ("Arm position", "arm_position"),
        ("Hand position", "hand_position"),
        ("Leg position", "leg_position"),
        ("Facial expression", "facial_expression"),
        ("Camera angle", "camera_angle"),
        ("Camera distance", "camera_distance"),
        ("Lighting", "lighting"),
        ("Background", "background"),
        ("Visual style", "visual_style"),
    ]

    for label, field in prompt_fields:
        value = str(pose.get(field, "")).strip()

        if value:
            sections.append(f"{label}: {value}")

    character_id = pose.get("character_id", "")

    if character_id:
        sections.append(
            f"Maintain the identity and appearance of character "
            f"{character_id}."
        )

    if include_negative:
        negative = str(
            pose.get("negative_prompt", "")
        ).strip()

        if negative:
            sections.append(
                f"Negative prompt: {negative}"
            )

    return "\n".join(sections)


# ---------------------------------------------------------
# STATISTICS AND EXPORT
# ---------------------------------------------------------

def get_statistics(
    path: Path | str | None = None,
) -> dict:
    poses = list_poses(path=path)

    categories = {}

    total_images = 0

    for pose in poses:
        category = pose.get("category", "Custom")

        categories[category] = (
            categories.get(category, 0) + 1
        )

        total_images += len(
            pose.get("reference_images", [])
        )

    return {
        "total_poses": len(poses),
        "total_reference_images": total_images,
        "linked_characters": len({
            pose.get("character_id")
            for pose in poses
            if pose.get("character_id")
        }),
        "categories": categories,
    }


def export_poses(
    output_path: Path | str,
    path: Path | str | None = None,
) -> Path:
    """Export all pose metadata to a JSON file."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    database = load_database(path)

    temporary = output.with_name(output.name + ".tmp")

    with temporary.open("w", encoding="utf-8") as file:
        json.dump(
            database,
            file,
            indent=4,
            ensure_ascii=False,
        )

    temporary.replace(output)

    return output


# ---------------------------------------------------------
# STREAMLIT UI
# ---------------------------------------------------------

def render(st: Any) -> None:
    _ensure_directories()

    st.title("Pose Library")
    st.caption(
        "Create, organize and reuse character poses and reference images."
    )

    tab_create, tab_library, tab_stats = st.tabs([
        "Create Pose",
        "Pose Collection",
        "Statistics",
    ])

    # -----------------------------------------------------
    # CREATE POSE
    # -----------------------------------------------------

    with tab_create:
        st.subheader("Create a new pose")

        characters = list_characters()

        character_options = {
            "No character linked": ""
        }

        for character in characters:
            character_id = str(character.get("id", ""))

            if character_id:
                name = character.get("name", "Character")
                character_options[
                    f"{name} ({character_id[:8]})"
                ] = character_id

        with st.form("pose_create_form"):
            name = st.text_input(
                "Pose name",
                placeholder="Example: Heroic standing pose",
            )

            category = st.selectbox(
                "Category",
                POSE_CATEGORIES,
            )

            character_label = st.selectbox(
                "Link character",
                list(character_options.keys()),
            )

            description = st.text_area(
                "Pose description",
                placeholder="Describe the overall pose...",
            )

            col1, col2 = st.columns(2)

            with col1:
                body_position = st.text_input("Body position")
                head_position = st.text_input("Head position")
                arm_position = st.text_input("Arm position")
                hand_position = st.text_input("Hand position")
                leg_position = st.text_input("Leg position")
                facial_expression = st.text_input(
                    "Facial expression"
                )

            with col2:
                camera_angle = st.text_input("Camera angle")
                camera_distance = st.text_input("Camera distance")
                lighting = st.text_input("Lighting")
                background = st.text_input("Background")
                visual_style = st.text_input("Visual style")

            negative_prompt = st.text_area(
                "Negative prompt",
                placeholder="Example: distorted hands, extra fingers...",
            )

            submitted = st.form_submit_button(
                "Create Pose",
                type="primary",
            )

        if submitted:
            try:
                pose = create_pose({
                    "name": name,
                    "category": category,
                    "character_id": character_options[
                        character_label
                    ],
                    "description": description,
                    "body_position": body_position,
                    "head_position": head_position,
                    "arm_position": arm_position,
                    "hand_position": hand_position,
                    "leg_position": leg_position,
                    "facial_expression": facial_expression,
                    "camera_angle": camera_angle,
                    "camera_distance": camera_distance,
                    "lighting": lighting,
                    "background": background,
                    "visual_style": visual_style,
                    "negative_prompt": negative_prompt,
                })

                st.success(
                    f"Pose created successfully: {pose['name']}"
                )

            except Exception as exc:
                st.error(f"Could not create pose: {exc}")

        st.divider()
        st.subheader("Upload pose reference")

        poses = list_poses()

        if poses:
            pose_options = {
                f"{pose['name']} ({pose['id'][:8]})": pose["id"]
                for pose in poses
            }

            selected_pose_label = st.selectbox(
                "Select pose",
                list(pose_options.keys()),
                key="pose_upload_select",
            )

            selected_pose_id = pose_options[
                selected_pose_label
            ]

            uploaded = st.file_uploader(
                "Upload pose reference image",
                type=["png", "jpg", "jpeg", "webp"],
                key="pose_reference_upload",
            )

            if st.button(
                "Save Pose Reference",
                key="pose_save_reference",
            ):
                if uploaded is None:
                    st.warning("Please upload an image.")
                else:
                    try:
                        add_reference_image(
                            selected_pose_id,
                            uploaded.getvalue(),
                            uploaded.name,
                        )

                        st.success("Pose reference saved.")

                    except Exception as exc:
                        st.error(str(exc))
        else:
            st.info("Create a pose before uploading its reference.")

    # -----------------------------------------------------
    # POSE COLLECTION
    # -----------------------------------------------------

    with tab_library:
        st.subheader("Saved poses")

        search = st.text_input(
            "Search poses",
            placeholder="Search by name or description",
            key="pose_search",
        )

        category_filter = st.selectbox(
            "Filter category",
            ["All"] + POSE_CATEGORIES,
        )

        character_filter_options = {
            "All characters": ""
        }

        for character in characters:
            character_id = str(character.get("id", ""))

            if character_id:
                character_filter_options[
                    character.get("name", character_id)
                ] = character_id

        character_filter_label = st.selectbox(
            "Filter character",
            list(character_filter_options.keys()),
        )

        results = list_poses(
            search=search,
            category=(
                "" if category_filter == "All"
                else category_filter
            ),
            character_id=character_filter_options[
                character_filter_label
            ],
        )

        if not results:
            st.info("No matching poses found.")

        for pose in results:
            with st.expander(
                f"{pose['name']} — {pose['category']}"
            ):
                st.write(
                    pose.get("description") or "No description."
                )

                images = pose.get("reference_images", [])

                if images:
                    image_columns = st.columns(3)

                    for index, record in enumerate(images):
                        image_path = get_reference_image_path(record)

                        if image_path:
                            with image_columns[index % 3]:
                                st.image(
                                    str(image_path),
                                    use_container_width=True,
                                )
                else:
                    st.caption("No reference images.")

                prompt = build_pose_prompt(pose=pose)

                st.text_area(
                    "Reusable pose prompt",
                    value=prompt,
                    height=180,
                    key=f"pose_prompt_{pose['id']}",
                )

                st.download_button(
                    "Download pose prompt",
                    data=prompt,
                    file_name=f"pose_{pose['id']}.txt",
                    mime="text/plain",
                    key=f"pose_download_{pose['id']}",
                )

                st.divider()
                st.markdown("**Edit pose**")

                with st.form(
                    f"edit_pose_{pose['id']}"
                ):
                    edit_name = st.text_input(
                        "Name",
                        value=pose.get("name", ""),
                    )

                    edit_description = st.text_area(
                        "Description",
                        value=pose.get("description", ""),
                    )

                    edit_category = st.selectbox(
                        "Category",
                        POSE_CATEGORIES,
                        index=(
                            POSE_CATEGORIES.index(
                                pose["category"]
                            )
                            if pose.get("category") in POSE_CATEGORIES
                            else POSE_CATEGORIES.index("Custom")
                        ),
                    )

                    edit_body = st.text_input(
                        "Body position",
                        value=pose.get("body_position", ""),
                    )

                    edit_camera = st.text_input(
                        "Camera angle",
                        value=pose.get("camera_angle", ""),
                    )

                    edit_style = st.text_input(
                        "Visual style",
                        value=pose.get("visual_style", ""),
                    )

                    edit_negative = st.text_area(
                        "Negative prompt",
                        value=pose.get("negative_prompt", ""),
                    )

                    save_edit = st.form_submit_button(
                        "Save Changes"
                    )

                if save_edit:
                    try:
                        update_pose(
                            pose["id"],
                            {
                                "name": edit_name,
                                "description": edit_description,
                                "category": edit_category,
                                "body_position": edit_body,
                                "camera_angle": edit_camera,
                                "visual_style": edit_style,
                                "negative_prompt": edit_negative,
                            },
                        )

                        st.success("Pose updated.")
                        st.rerun()

                    except Exception as exc:
                        st.error(str(exc))

                col_a, col_b = st.columns(2)

                with col_a:
                    if st.button(
                        "Duplicate Pose",
                        key=f"duplicate_{pose['id']}",
                    ):
                        try:
                            duplicate_pose(pose["id"])
                            st.success("Pose duplicated.")
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))

                with col_b:
                    confirm = st.checkbox(
                        "Confirm deletion",
                        key=f"confirm_delete_{pose['id']}",
                    )

                    if st.button(
                        "Delete Pose",
                        key=f"delete_{pose['id']}",
                        disabled=not confirm,
                    ):
                        if delete_pose(pose["id"]):
                            st.success("Pose deleted.")
                            st.rerun()
                        else:
                            st.error("Pose could not be deleted.")

        st.divider()

        if st.button("Export All Poses"):
            try:
                output = export_poses(
                    DEFAULT_EXPORT_DIR / "pose_library.json"
                )

                st.success(f"Exported to {output}")

            except Exception as exc:
                st.error(str(exc))

    # -----------------------------------------------------
    # STATISTICS
    # -----------------------------------------------------

    with tab_stats:
        st.subheader("Pose Library Statistics")

        stats = get_statistics()

        col1, col2, col3 = st.columns(3)

        col1.metric("Total Poses", stats["total_poses"])
        col2.metric(
            "Reference Images",
            stats["total_reference_images"],
        )
        col3.metric(
            "Linked Characters",
            stats["linked_characters"],
        )

        st.markdown("**Category breakdown**")

        if stats["categories"]:
            for category, count in stats["categories"].items():
                st.write(f"- {category}: {count}")
        else:
            st.info("No saved poses yet.")


# ---------------------------------------------------------
# BUILT-IN TESTS
# ---------------------------------------------------------

def run_tests() -> bool:
    import tempfile
    import unittest

    class PoseLibraryTests(unittest.TestCase):

        def setUp(self):
            self.temp = tempfile.TemporaryDirectory()
            self.root = Path(self.temp.name)
            self.database = self.root / "poses.json"
            self.assets = self.root / "pose_references"

            self.assets.mkdir(parents=True)

        def tearDown(self):
            self.temp.cleanup()

        def sample_pose(self):
            return {
                "name": "Heroic Pose",
                "category": "Cinematic",
                "description": "Standing confidently",
                "body_position": "Upright",
                "head_position": "Slightly raised",
                "arm_position": "Arms relaxed",
                "hand_position": "Open hands",
                "leg_position": "Feet apart",
                "facial_expression": "Confident",
                "camera_angle": "Low angle",
                "camera_distance": "Full body",
                "lighting": "Dramatic",
                "background": "Studio",
                "visual_style": "Realistic",
                "negative_prompt": "Extra fingers",
            }

        def test_empty_database(self):
            data = load_database(self.database)
            self.assertEqual(data["poses"], [])

        def test_save_and_load(self):
            data = load_database(self.database)
            data["poses"].append({"id": "test"})
            save_database(data, self.database)

            loaded = load_database(self.database)
            self.assertEqual(len(loaded["poses"]), 1)

        def test_create_pose(self):
            pose = create_pose(
                self.sample_pose(),
                self.database,
            )

            self.assertTrue(pose["id"])
            self.assertEqual(pose["name"], "Heroic Pose")

        def test_missing_name_rejected(self):
            with self.assertRaises(ValueError):
                create_pose(
                    {"category": "Cinematic"},
                    self.database,
                )

        def test_get_pose(self):
            pose = create_pose(
                self.sample_pose(),
                self.database,
            )

            result = get_pose(pose["id"], self.database)

            self.assertEqual(result["id"], pose["id"])

        def test_search_pose(self):
            create_pose(
                self.sample_pose(),
                self.database,
            )

            results = list_poses(
                search="heroic",
                path=self.database,
            )

            self.assertEqual(len(results), 1)

        def test_category_filter(self):
            create_pose(
                self.sample_pose(),
                self.database,
            )

            results = list_poses(
                category="Cinematic",
                path=self.database,
            )

            self.assertEqual(len(results), 1)

        def test_update_pose(self):
            pose = create_pose(
                self.sample_pose(),
                self.database,
            )

            updated = update_pose(
                pose["id"],
                {"name": "Updated Pose"},
                self.database,
            )

            self.assertEqual(updated["name"], "Updated Pose")

        def test_duplicate_pose(self):
            pose = create_pose(
                self.sample_pose(),
                self.database,
            )

            duplicate = duplicate_pose(
                pose["id"],
                path=self.database,
            )

            self.assertNotEqual(
                pose["id"],
                duplicate["id"],
            )

        def test_delete_pose(self):
            pose = create_pose(
                self.sample_pose(),
                self.database,
            )

            result = delete_pose(
                pose["id"],
                path=self.database,
                asset_root=self.assets,
            )

            self.assertTrue(result)
            self.assertIsNone(
                get_pose(pose["id"], self.database)
            )

        def test_reference_upload(self):
            pose = create_pose(
                self.sample_pose(),
                self.database,
            )

            image = add_reference_image(
                pose["id"],
                b"sample-image-bytes",
                "reference.png",
                path=self.database,
                asset_root=self.assets,
            )

            self.assertTrue(image["id"])

            saved_pose = get_pose(
                pose["id"],
                self.database,
            )

            self.assertEqual(
                len(saved_pose["reference_images"]),
                1,
            )

        def test_invalid_extension(self):
            with self.assertRaises(ValueError):
                add_reference_image(
                    "pose_1",
                    b"image-data",
                    "file.exe",
                    path=self.database,
                    asset_root=self.assets,
                )

        def test_delete_reference(self):
            pose = create_pose(
                self.sample_pose(),
                self.database,
            )

            image = add_reference_image(
                pose["id"],
                b"sample-image-bytes",
                "reference.png",
                path=self.database,
                asset_root=self.assets,
            )

            result = delete_reference_image(
                pose["id"],
                image["id"],
                path=self.database,
                asset_root=self.assets,
            )

            self.assertTrue(result)

        def test_prompt_builder(self):
            pose = self.sample_pose()

            prompt = build_pose_prompt(pose=pose)

            self.assertIn("Heroic Pose", prompt)
            self.assertIn("Low angle", prompt)
            self.assertIn("Extra fingers", prompt)

        def test_statistics(self):
            create_pose(
                self.sample_pose(),
                self.database,
            )

            stats = get_statistics(self.database)

            self.assertEqual(stats["total_poses"], 1)
            self.assertEqual(
                stats["categories"]["Cinematic"],
                1,
            )

        def test_export(self):
            create_pose(
                self.sample_pose(),
                self.database,
            )

            output = self.root / "export.json"

            export_poses(
                output,
                path=self.database,
            )

            self.assertTrue(output.exists())

            with output.open("r", encoding="utf-8") as file:
                data = json.load(file)

            self.assertEqual(len(data["poses"]), 1)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        PoseLibraryTests
    )

    result = unittest.TextTestRunner(verbosity=2).run(suite)

    return result.wasSuccessful()


# ---------------------------------------------------------
# COMMAND LINE TEST RUNNER
# ---------------------------------------------------------

if __name__ == "__main__":
    import sys

    if "--test" in sys.argv:
        success = run_tests()
        raise SystemExit(0 if success else 1)

    print("AI Influencer Studio - Pose Library")
    print("Run tests using:")
    print("python -m modules.pose_library --test")
