"""Outfit Studio UI for AI Influencer Studio.

Collects person and garment reference images, stores them persistently,
and prepares an honest preview/workflow. It does not perform virtual try-on.
"""
from __future__ import annotations

import io
import re
import uuid
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError

import config
import storage

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_IMAGE_BYTES = config.MAX_IMAGE_UPLOAD_MB * 1024 * 1024
MAX_IMAGE_DIMENSION = 2048
GARMENT_CATEGORIES = [
    "Top / Shirt", "Trousers / Pants", "Dress", "Jacket / Coat",
    "Traditional wear", "Full outfit", "Shoes", "Accessories", "Other",
]
STYLE_OPTIONS = [
    "Photorealistic", "Cinematic", "Fashion editorial", "Casual",
    "Streetwear", "Traditional", "Formal", "Custom",
]


def _safe_asset_root() -> Path:
    """Create a persistent outfit asset directory under assets/."""
    root = Path(config.ASSETS_DIR).resolve()
    target = (root / "outfits").resolve()
    if target == root or root not in target.parents:
        raise ValueError("Outfit assets must be stored inside assets/.")
    target.mkdir(parents=True, exist_ok=True)
    return target


def _safe_stem(value: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip()).strip("_-")
    return (stem or "outfit")[:40]


def save_reference_image(data: bytes, label: str) -> str:
    """Validate, normalize, and persist an uploaded image under assets/outfits."""
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise ValueError("The uploaded image is empty.")
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError(
            f"Image exceeds the {config.MAX_IMAGE_UPLOAD_MB} MB upload limit."
        )

    try:
        with Image.open(io.BytesIO(data)) as probe:
            if (probe.format or "").upper() not in ALLOWED_FORMATS:
                raise ValueError("Use a JPEG, PNG, or WEBP image.")
            probe.verify()

        with Image.open(io.BytesIO(data)) as source:
            image = ImageOps.exif_transpose(source)
            image.load()
            if image.width < 1 or image.height < 1:
                raise ValueError("Image dimensions are invalid.")
            image.thumbnail(
                (MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION),
                Image.Resampling.LANCZOS,
            )
            if image.mode != "RGB":
                if "A" in image.getbands():
                    rgba = image.convert("RGBA")
                    background = Image.new("RGBA", rgba.size, "white")
                    image = Image.alpha_composite(background, rgba).convert("RGB")
                else:
                    image = image.convert("RGB")

            root = _safe_asset_root()
            filename = f"{_safe_stem(label)}_{uuid.uuid4().hex[:12]}.jpg"
            destination = root / filename
            temporary = root / f".{filename}.tmp"
            try:
                image.save(temporary, format="JPEG", quality=88, optimize=True)
                temporary.replace(destination)
            finally:
                temporary.unlink(missing_ok=True)

            return destination.relative_to(Path(config.BASE_DIR).resolve()).as_posix()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("The file is not a valid supported image.") from exc


def resolve_asset_path(relative_path: str | None) -> Path | None:
    """Resolve a saved reference only if it remains inside assets/."""
    if not relative_path:
        return None
    base = Path(config.BASE_DIR).resolve()
    assets = Path(config.ASSETS_DIR).resolve()
    candidate = (base / relative_path).resolve()
    if assets not in candidate.parents:
        return None
    if candidate.is_symlink() or not candidate.is_file():
        return None
    return candidate


def save_engine_result(data: bytes, extension: str = "jpg") -> dict[str, Any]:
    """Save a real virtual-try-on engine result to expiring output storage."""
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise ValueError("The generated result is empty.")
    suffix = extension.lower().lstrip(".")
    if suffix not in {"jpg", "jpeg", "png", "webp"}:
        raise ValueError("Unsupported outfit output format.")

    output_root = Path(config.OUTPUT_DIR).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    destination = output_root / f"outfit_{uuid.uuid4().hex}.{suffix}"
    with destination.open("xb") as handle:
        handle.write(data)
    try:
        return storage.register_output(destination)
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def _render_saved_assets(app: Any) -> None:
    """Show persistent outfit reference images saved during this session."""
    saved = app.session_state.get("outfit_saved_references", [])
    if not saved:
        app.info("No outfit reference images saved in this session yet.")
        return
    for item in reversed(saved):
        path = resolve_asset_path(item.get("path"))
        if path is None:
            continue
        app.image(str(path), caption=item.get("label", path.name), width=260)
        app.caption(f"Persistent asset: {item['path']}")


def render(app: Any) -> None:
    """Render Outfit Studio inside the main Streamlit application."""
    app.title("Outfit Studio")
    app.caption(
        "Prepare person and clothing references for a virtual try-on workflow. "
        "The current module provides image previews and persistent storage only."
    )

    person_tab, library_tab = app.tabs(["Create Outfit Workflow", "Saved References"])
    with person_tab:
        left, right = app.columns(2)
        with left:
            person_upload = app.file_uploader(
                "Person image", type=["jpg", "jpeg", "png", "webp"],
                key="outfit_person_upload",
                help="Use an image you have permission to process.",
            )
            if person_upload is not None:
                app.image(person_upload, caption="Person reference", use_container_width=True)
        with right:
            garment_upload = app.file_uploader(
                "Clothing reference image", type=["jpg", "jpeg", "png", "webp"],
                key="outfit_garment_upload",
                help="Upload the clothing item or outfit you want to reference.",
            )
            if garment_upload is not None:
                app.image(garment_upload, caption="Clothing reference", use_container_width=True)

        category = app.selectbox("Garment category", GARMENT_CATEGORIES)
        style = app.selectbox("Desired style", STYLE_OPTIONS)
        prompt = app.text_area(
            "Outfit prompt / instructions",
            placeholder=(
                "Describe fit, colors, fabric, details, and how the outfit "
                "should look. This text is saved as workflow input only."
            ),
            height=110,
        )

        app.info(
            "Preview means viewing the two uploaded references side by side. "
            "It does not replace clothing on the person. Real virtual try-on "
            "requires a compatible model and inference engine."
        )

        if app.button("Save Reference Images", type="primary", use_container_width=True):
            if person_upload is None or garment_upload is None:
                app.error("Upload both a person image and a clothing reference image.")
            else:
                saved_items = []
                try:
                    person_path = save_reference_image(
                        person_upload.getvalue(), "person_reference"
                    )
                    saved_items.append({"label": "Person reference", "path": person_path})
                    garment_path = save_reference_image(
                        garment_upload.getvalue(), "garment_reference"
                    )
                    saved_items.append({"label": "Clothing reference", "path": garment_path})
                    app.session_state.setdefault("outfit_saved_references", []).extend(saved_items)
                    app.session_state["outfit_workflow"] = {
                        "person_image": person_path,
                        "garment_image": garment_path,
                        "category": category,
                        "style": style,
                        "prompt": prompt.strip(),
                    }
                    app.success("Reference images saved permanently in assets/outfits/.")
                    app.caption(f"Category: {category} | Style: {style}")
                except (ValueError, OSError) as exc:
                    app.error(str(exc))

        workflow = app.session_state.get("outfit_workflow")
        if workflow:
            app.subheader("Current workflow preview")
            preview_left, preview_right = app.columns(2)
            person_path = resolve_asset_path(workflow.get("person_image"))
            garment_path = resolve_asset_path(workflow.get("garment_image"))
            with preview_left:
                if person_path:
                    app.image(str(person_path), caption="Person", use_container_width=True)
            with preview_right:
                if garment_path:
                    app.image(str(garment_path), caption="Garment", use_container_width=True)
            app.write(f"**Category:** {workflow['category']}")
            app.write(f"**Style:** {workflow['style']}")
            if workflow.get("prompt"):
                app.write(f"**Prompt:** {workflow['prompt']}")
            app.warning(
                "No virtual try-on output has been generated. These are reference previews only."
            )

    with library_tab:
        _render_saved_assets(app)

    app.divider()
    app.subheader("Generated try-on results")
    app.caption("Only actual model-generated results registered in output/ appear here.")
    try:
        results = storage.list_outputs()
        outfit_results = [
            item for item in results
            if Path(item["name"]).name.startswith("outfit_")
        ]
        if not outfit_results:
            app.info("No generated outfit results are available yet.")
        for item in outfit_results:
            result_path = Path(item["path"])
            app.image(str(result_path), use_container_width=True)
            app.caption(
                f"{item['name']} — expires in {item['remaining_seconds']} seconds"
            )
            with result_path.open("rb") as handle:
                app.download_button(
                    "Download result", handle.read(), file_name=item["name"],
                    key=f"outfit_download_{item['name']}",
                )
    except Exception as exc:
        app.error(f"Could not load generated results: {exc}")
