
"""
File 60: modules/face_consistency_checker.py

Face Consistency Checker

Features:
- Store character reference images.
- Compare reference images with generated images.
- Calculate a lightweight perceptual hash similarity score.
- Save comparison history.
- Search and filter comparisons.
- Export comparison reports.
- Optional Pillow dependency.

IMPORTANT:
This is a basic image similarity utility.
It is NOT facial recognition and cannot verify identity.
"""

from __future__ import annotations

import json
import shutil
import uuid

from datetime import datetime
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT_DIR / "data"
ASSET_DIR = ROOT_DIR / "assets" / "face_consistency"
REFERENCE_DIR = ASSET_DIR / "references"
GENERATED_DIR = ASSET_DIR / "generated"
EXPORT_DIR = ROOT_DIR / "outputs" / "face_consistency"

DATA_FILE = DATA_DIR / "face_consistency_history.json"

SUPPORTED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
}


class FaceConsistencyError(Exception):
    """Base exception for this module."""


def _ensure_directories() -> None:
    for directory in (
        DATA_DIR,
        REFERENCE_DIR,
        GENERATED_DIR,
        EXPORT_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _read_history() -> list[dict[str, Any]]:
    _ensure_directories()

    if not DATA_FILE.exists():
        return []

    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

    except (OSError, json.JSONDecodeError) as exc:
        raise FaceConsistencyError(
            f"Could not read comparison history: {exc}"
        ) from exc

    if not isinstance(data, list):
        raise FaceConsistencyError(
            "Comparison history must be a JSON list."
        )

    return [
        item for item in data
        if isinstance(item, dict)
    ]


def _write_history(
    history: list[dict[str, Any]],
) -> None:
    _ensure_directories()

    temporary = DATA_FILE.with_suffix(".tmp")

    try:
        with temporary.open("w", encoding="utf-8") as file:
            json.dump(
                history,
                file,
                indent=4,
                ensure_ascii=False,
            )

        temporary.replace(DATA_FILE)

    except OSError as exc:
        raise FaceConsistencyError(
            f"Could not save comparison history: {exc}"
        ) from exc


def _validate_image_path(path: str | Path) -> Path:
    image_path = Path(path).expanduser()

    if not image_path.is_file():
        raise FileNotFoundError(
            f"Image file not found: {image_path}"
        )

    if image_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            "Unsupported image format. Supported: "
            + ", ".join(sorted(SUPPORTED_EXTENSIONS))
        )

    return image_path.resolve()


def _get_pillow():
    """Import Pillow only when image analysis is requested."""

    try:
        from PIL import Image, ImageOps
        return Image, ImageOps

    except ImportError as exc:
        raise RuntimeError(
            "Pillow is required for image comparison. "
            "Install it using: pip install Pillow"
        ) from exc


def _calculate_dhash(image_path: str | Path) -> str:
    """
    Calculate a 64-bit difference hash.

    This is a general visual image hash, not a face identity
    embedding or facial recognition algorithm.
    """

    Image, ImageOps = _get_pillow()

    path = _validate_image_path(image_path)

    try:
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source)
            image = image.convert("L")
            image = image.resize((9, 8))

            pixels = list(image.getdata())

    except Exception as exc:
        raise FaceConsistencyError(
            f"Could not process image {path.name}: {exc}"
        ) from exc

    bits = []

    for row in range(8):
        for column in range(8):
            left = pixels[row * 9 + column]
            right = pixels[row * 9 + column + 1]
            bits.append("1" if left > right else "0")

    return "".join(bits)


def _hamming_distance(
    hash_a: str,
    hash_b: str,
) -> int:
    """Count different bits between two hashes."""

    if len(hash_a) != len(hash_b):
        raise ValueError("Hash lengths must match.")

    return sum(
        first != second
        for first, second in zip(hash_a, hash_b)
    )


def calculate_similarity(
    reference_path: str,
    generated_path: str,
) -> dict[str, Any]:
    """
    Compare two complete images using difference hashing.

    Returns a heuristic similarity percentage.
    A high score does not mean the same person is present.
    """

    reference = _validate_image_path(reference_path)
    generated = _validate_image_path(generated_path)

    reference_hash = _calculate_dhash(reference)
    generated_hash = _calculate_dhash(generated)

    distance = _hamming_distance(
        reference_hash,
        generated_hash,
    )

    similarity = round(
        (64 - distance) / 64 * 100,
        2,
    )

    Image, ImageOps = _get_pillow()

    with Image.open(reference) as image:
        reference_size = ImageOps.exif_transpose(
            image
        ).size

    with Image.open(generated) as image:
        generated_size = ImageOps.exif_transpose(
            image
        ).size

    return {
        "similarity_score": similarity,
        "hash_distance": distance,
        "hash_bits": 64,
        "reference_dimensions": list(reference_size),
        "generated_dimensions": list(generated_size),
        "same_dimensions": (
            reference_size == generated_size
        ),
        "comparison_method": "64-bit difference hash",
        "interpretation": (
            "General visual similarity only. "
            "Not a facial identity verification."
        ),
    }


def _copy_image(
    source_path: str | Path,
    destination_folder: Path,
    prefix: str,
) -> Path:
    """Copy an image into this module's managed storage."""

    source = _validate_image_path(source_path)
    _ensure_directories()

    destination = (
        destination_folder
        / f"{prefix}_{uuid.uuid4().hex[:10]}{source.suffix.lower()}"
    )

    try:
        shutil.copy2(source, destination)

    except OSError as exc:
        raise FaceConsistencyError(
            f"Could not copy image: {exc}"
        ) from exc

    return destination


def add_reference(
    character_name: str,
    image_path: str,
    description: str = "",
) -> dict[str, Any]:
    """Save a reference image for a character."""

    character_name = str(character_name).strip()

    if not character_name:
        raise ValueError("Character name is required.")

    stored_path = _copy_image(
        image_path,
        REFERENCE_DIR,
        "reference",
    )

    item = {
        "id": uuid.uuid4().hex[:12],
        "character_name": character_name,
        "image_path": str(stored_path),
        "description": str(description).strip(),
        "created_at": _now(),
    }

    # Reference records are stored separately from comparisons.
    references_file = DATA_DIR / "face_references.json"

    if references_file.exists():
        try:
            existing = json.loads(
                references_file.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise FaceConsistencyError(
                f"Could not read reference records: {exc}"
            ) from exc
    else:
        existing = []

    if not isinstance(existing, list):
        raise FaceConsistencyError(
            "Reference database must be a JSON list."
        )

    existing.append(item)

    temporary = references_file.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(existing, indent=4, ensure_ascii=False),
        encoding="utf-8",
    )
    temporary.replace(references_file)

    return item


def list_references(
    character_name: str | None = None,
) -> list[dict[str, Any]]:
    """List stored reference images."""

    _ensure_directories()

    references_file = DATA_DIR / "face_references.json"

    if not references_file.exists():
        return []

    try:
        with references_file.open("r", encoding="utf-8") as file:
            references = json.load(file)

    except (OSError, json.JSONDecodeError) as exc:
        raise FaceConsistencyError(
            f"Could not read reference database: {exc}"
        ) from exc

    if not isinstance(references, list):
        return []

    if character_name:
        target = character_name.strip().casefold()
        references = [
            item for item in references
            if item.get("character_name", "").casefold() == target
        ]

    return sorted(
        references,
        key=lambda item: item.get("created_at", ""),
        reverse=True,
    )


def delete_reference(reference_id: str) -> bool:
    """Delete a reference record and its managed image."""

    references_file = DATA_DIR / "face_references.json"

    references = list_references()

    target = next(
        (
            item for item in references
            if item.get("id") == reference_id
        ),
        None,
    )

    if target is None:
        return False

    remaining = [
        item for item in references
        if item.get("id") != reference_id
    ]

    temporary = references_file.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(remaining, indent=4, ensure_ascii=False),
        encoding="utf-8",
    )
    temporary.replace(references_file)

    image_path = Path(target.get("image_path", ""))

    try:
        resolved = image_path.resolve()
        managed = REFERENCE_DIR.resolve()

        if resolved.is_relative_to(managed) and resolved.is_file():
            resolved.unlink()

    except (OSError, ValueError):
        pass

    return True


def compare_and_save(
    character_name: str,
    reference_path: str,
    generated_path: str,
    notes: str = "",
) -> dict[str, Any]:
    """Compare two images and save the result."""

    character_name = str(character_name).strip()

    if not character_name:
        raise ValueError("Character name is required.")

    reference = _validate_image_path(reference_path)
    generated = _validate_image_path(generated_path)

    result = calculate_similarity(
        str(reference),
        str(generated),
    )

    # Preserve comparison images in managed storage.
    stored_reference = _copy_image(
        reference,
        REFERENCE_DIR,
        "comparison_reference",
    )

    stored_generated = _copy_image(
        generated,
        GENERATED_DIR,
        "comparison_generated",
    )

    record = {
        "id": uuid.uuid4().hex[:12],
        "character_name": character_name,
        "reference_image": str(stored_reference),
        "generated_image": str(stored_generated),
        "similarity_score": result["similarity_score"],
        "hash_distance": result["hash_distance"],
        "hash_bits": result["hash_bits"],
        "reference_dimensions": result["reference_dimensions"],
        "generated_dimensions": result["generated_dimensions"],
        "same_dimensions": result["same_dimensions"],
        "comparison_method": result["comparison_method"],
        "interpretation": result["interpretation"],
        "notes": str(notes).strip(),
        "created_at": _now(),
    }

    history = _read_history()
    history.append(record)
    _write_history(history)

    return record


def list_comparisons(
    character_name: str | None = None,
) -> list[dict[str, Any]]:
    """Return saved comparison records."""

    history = _read_history()

    if character_name:
        target = character_name.strip().casefold()

        history = [
            item for item in history
            if item.get("character_name", "").casefold() == target
        ]

    return sorted(
        history,
        key=lambda item: item.get("created_at", ""),
        reverse=True,
    )


def delete_comparison(
    comparison_id: str,
    delete_images: bool = False,
) -> bool:
    """Delete a comparison record and optionally managed images."""

    history = _read_history()

    target = next(
        (
            item for item in history
            if item.get("id") == comparison_id
        ),
        None,
    )

    if target is None:
        return False

    remaining = [
        item for item in history
        if item.get("id") != comparison_id
    ]

    _write_history(remaining)

    if delete_images:
        for field in (
            "reference_image",
            "generated_image",
        ):
            try:
                path = Path(target.get(field, "")).resolve()

                if (
                    path.is_relative_to(ASSET_DIR.resolve())
                    and path.is_file()
                ):
                    path.unlink()

            except (OSError, ValueError):
                pass

    return True


def get_statistics() -> dict[str, Any]:
    """Calculate comparison statistics."""

    history = _read_history()

    scores = [
        float(item["similarity_score"])
        for item in history
        if isinstance(
            item.get("similarity_score"),
            (int, float),
        )
    ]

    return {
        "total_comparisons": len(history),
        "characters": len({
            item.get("character_name")
            for item in history
            if item.get("character_name")
        }),
        "average_similarity": (
            round(sum(scores) / len(scores), 2)
            if scores else 0
        ),
        "highest_similarity": max(scores) if scores else 0,
        "lowest_similarity": min(scores) if scores else 0,
    }


def export_history() -> Path:
    """Export reference and comparison history."""

    _ensure_directories()

    destination = EXPORT_DIR / (
        "face_consistency_"
        + datetime.now().strftime("%Y%m%d_%H%M%S")
        + ".json"
    )

    payload = {
        "exported_at": _now(),
        "references": list_references(),
        "comparisons": _read_history(),
        "statistics": get_statistics(),
    }

    destination.write_text(
        json.dumps(payload, indent=4, ensure_ascii=False),
        encoding="utf-8",
    )

    return destination


def render() -> None:
    """Display the Streamlit interface."""

    try:
        import streamlit as st

    except ImportError:
        raise RuntimeError(
            "Streamlit is required for this page. "
            "Install it using: pip install streamlit"
        )

    st.title("Face Consistency Checker")

    st.caption(
        "Compare character reference images with generated images "
        "using a lightweight visual similarity method."
    )

    try:
        stats = get_statistics()

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Comparisons",
            stats["total_comparisons"],
        )
        col2.metric(
            "Characters",
            stats["characters"],
        )
        col3.metric(
            "Average visual similarity",
            f"{stats['average_similarity']}%",
        )

        st.warning(
            "The similarity score is based on whole-image visual "
            "patterns. It does not identify faces or verify identity."
        )

        tab_compare, tab_references, tab_history, tab_export = st.tabs([
            "Compare Images",
            "Reference Library",
            "History",
            "Export",
        ])

        with tab_compare:
            st.subheader("Compare character images")

            character_name = st.text_input(
                "Character name",
                key="face_compare_character",
            )

            reference_upload = st.file_uploader(
                "Upload reference image",
                type=["png", "jpg", "jpeg", "webp", "bmp"],
                key="face_reference_upload",
            )

            generated_upload = st.file_uploader(
                "Upload generated image",
                type=["png", "jpg", "jpeg", "webp", "bmp"],
                key="face_generated_upload",
            )

            notes = st.text_area(
                "Comparison notes",
                placeholder="Describe lighting, pose, angle or other differences.",
            )

            if reference_upload is not None:
                st.image(
                    reference_upload,
                    caption="Reference image",
                    width=250,
                )

            if generated_upload is not None:
                st.image(
                    generated_upload,
                    caption="Generated image",
                    width=250,
                )

            if st.button(
                "Compare Images",
                type="primary",
                use_container_width=True,
            ):
                if not character_name.strip():
                    st.error("Enter a character name.")

                elif (
                    reference_upload is None
                    or generated_upload is None
                ):
                    st.error("Upload both images.")

                else:
                    temporary_files = []

                    try:
                        _ensure_directories()

                        reference_temp = (
                            REFERENCE_DIR
                            / f"temp_{uuid.uuid4().hex}.png"
                        )

                        generated_temp = (
                            GENERATED_DIR
                            / f"temp_{uuid.uuid4().hex}.png"
                        )

                        reference_temp.write_bytes(
                            reference_upload.getvalue()
                        )

                        generated_temp.write_bytes(
                            generated_upload.getvalue()
                        )

                        temporary_files.extend([
                            reference_temp,
                            generated_temp,
                        ])

                        result = compare_and_save(
                            character_name=character_name,
                            reference_path=str(reference_temp),
                            generated_path=str(generated_temp),
                            notes=notes,
                        )

                        st.success("Comparison completed.")

                        st.metric(
                            "Visual similarity score",
                            f"{result['similarity_score']}%",
                        )

                        st.write(
                            f"Hash difference: "
                            f"{result['hash_distance']} / 64 bits"
                        )

                        st.write(
                            "Reference dimensions:",
                            result["reference_dimensions"],
                        )

                        st.write(
                            "Generated dimensions:",
                            result["generated_dimensions"],
                        )

                        st.info(result["interpretation"])

                        st.caption(
                            "This score is not an identity verification."
                        )

                    except Exception as exc:
                        st.error(
                            f"Image comparison failed: {exc}"
                        )

                    finally:
                        for temporary in temporary_files:
                            temporary.unlink(missing_ok=True)

        with tab_references:
            st.subheader("Character reference library")

            ref_character = st.text_input(
                "Character name for reference",
                key="face_ref_character",
            )

            ref_upload = st.file_uploader(
                "Upload reference image",
                type=["png", "jpg", "jpeg", "webp", "bmp"],
                key="face_ref_library_upload",
            )

            ref_description = st.text_area(
                "Reference description",
                key="face_ref_description",
            )

            if st.button("Save Reference Image"):
                if not ref_character.strip():
                    st.error("Enter a character name.")

                elif ref_upload is None:
                    st.error("Upload an image.")

                else:
                    try:
                        _ensure_directories()

                        temporary = (
                            REFERENCE_DIR
                            / f"upload_{uuid.uuid4().hex}.png"
                        )

                        temporary.write_bytes(
                            ref_upload.getvalue()
                        )

                        try:
                            item = add_reference(
                                ref_character,
                                str(temporary),
                                ref_description,
                            )
                        finally:
                            temporary.unlink(missing_ok=True)

                        st.success(
                            f"Reference saved: {item['id']}"
                        )
                        st.rerun()

                    except Exception as exc:
                        st.error(str(exc))

            st.divider()

            references = list_references()

            if not references:
                st.info("No saved references yet.")

            for item in references:
                with st.container(border=True):
                    st.markdown(
                        f"**{item.get('character_name', 'Unknown')}**"
                    )

                    image_path = Path(item.get("image_path", ""))

                    if image_path.is_file():
                        st.image(
                            str(image_path),
                            width=220,
                        )
                    else:
                        st.warning("Reference image is missing.")

                    st.caption(item.get("description", ""))

                    if st.button(
                        "Delete Reference",
                        key=f"face_delete_ref_{item['id']}",
                    ):
                        delete_reference(item["id"])
                        st.success("Reference deleted.")
                        st.rerun()

        with tab_history:
            st.subheader("Comparison history")

            history_filter = st.text_input(
                "Filter by character",
                key="face_history_filter",
            )

            history = list_comparisons(
                history_filter or None
            )

            if not history:
                st.info("No comparison records found.")

            for item in history:
                with st.container(border=True):
                    st.markdown(
                        f"**{item.get('character_name', 'Unknown')}**"
                    )

                    st.metric(
                        "Visual similarity",
                        f"{item.get('similarity_score', 0)}%",
                    )

                    left, right = st.columns(2)

                    with left:
                        reference = Path(
                            item.get("reference_image", "")
                        )
                        if reference.is_file():
                            st.image(
                                str(reference),
                                caption="Reference",
                            )

                    with right:
                        generated = Path(
                            item.get("generated_image", "")
                        )
                        if generated.is_file():
                            st.image(
                                str(generated),
                                caption="Generated",
                            )

                    st.caption(
                        f"Comparison ID: {item.get('id')}"
                    )

                    if item.get("notes"):
                        st.write(item["notes"])

                    if st.button(
                        "Delete Comparison",
                        key=f"face_delete_{item['id']}",
                    ):
                        delete_comparison(
                            item["id"],
                            delete_images=True,
                        )
                        st.success("Comparison deleted.")
                        st.rerun()

        with tab_export:
            st.subheader("Export comparison reports")

            if st.button("Create JSON Report"):
                destination = export_history()

                st.success("Report created.")

                st.download_button(
                    "Download Report",
                    data=destination.read_bytes(),
                    file_name=destination.name,
                    mime="application/json",
                )

    except Exception as exc:
        st.error(
            "Face Consistency Checker encountered an error. "
            "Other modules should remain available."
        )
        st.exception(exc)


def run_tests() -> None:
    """Run built-in tests using temporary directories."""

    import tempfile

    global DATA_DIR
    global ASSET_DIR
    global REFERENCE_DIR
    global GENERATED_DIR
    global EXPORT_DIR
    global DATA_FILE

    old_values = (
        DATA_DIR,
        ASSET_DIR,
        REFERENCE_DIR,
        GENERATED_DIR,
        EXPORT_DIR,
        DATA_FILE,
    )

    try:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)

            DATA_DIR = base / "data"
            ASSET_DIR = base / "assets"
            REFERENCE_DIR = ASSET_DIR / "references"
            GENERATED_DIR = ASSET_DIR / "generated"
            EXPORT_DIR = base / "exports"
            DATA_FILE = DATA_DIR / "face_consistency_history.json"

            _ensure_directories()

            history = _read_history()
            assert history == []

            # Test record storage without requiring Pillow.
            sample_record = {
                "id": "test123",
                "character_name": "Test Character",
                "similarity_score": 85.5,
                "created_at": _now(),
            }

            _write_history([sample_record])

            assert len(_read_history()) == 1
            assert list_comparisons("Test Character")

            stats = get_statistics()
            assert stats["total_comparisons"] == 1
            assert stats["characters"] == 1
            assert stats["average_similarity"] == 85.5

            # Test image hash distance.
            assert _hamming_distance("0000", "0000") == 0
            assert _hamming_distance("0000", "1111") == 4

            # Test missing image handling.
            try:
                _validate_image_path(
                    base / "missing.png"
                )
            except FileNotFoundError:
                pass
            else:
                raise AssertionError(
                    "Missing image should raise FileNotFoundError."
                )

            exported = export_history()
            assert exported.is_file()

            assert delete_comparison("test123")
            assert _read_history() == []

            print(
                "All Face Consistency Checker metadata tests passed."
            )

    finally:
        (
            DATA_DIR,
            ASSET_DIR,
            REFERENCE_DIR,
            GENERATED_DIR,
            EXPORT_DIR,
            DATA_FILE,
        ) = old_values


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Face Consistency Checker"
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
        print("Face Consistency Checker")
        print("Run with --test to execute built-in tests.")
