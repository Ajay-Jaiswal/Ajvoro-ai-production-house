
"""
AI Influencer Studio
File 45: modules/brand_kit.py

Local Brand Kit Manager.

Features:
- Multiple brand profiles
- Logo and watermark asset uploads
- Brand color palette management
- Typography preferences
- Tagline and social links
- Profile import/export as JSON
- Persistent local asset storage
- Built-in tests

Run:
    python -m modules.brand_kit --test

Streamlit integration:
    from modules import brand_kit
    pages["Brand Kit"] = brand_kit.render
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
BRAND_DIR = BASE_DIR / "assets" / "brand_kits"
EXPORT_DIR = BASE_DIR / "outputs" / "brand_kits"
DATABASE_FILE = DATA_DIR / "brand_kits.json"

ALLOWED_IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp"
}

DEFAULT_COLORS = {
    "primary": "#172554",
    "secondary": "#1E293B",
    "accent": "#F59E0B",
    "background": "#FFFFFF",
    "text": "#111827",
}

DEFAULT_PROFILE = {
    "name": "My Brand",
    "description": "",
    "tagline": "",
    "primary_font": "Arial",
    "secondary_font": "Arial",
    "logo_path": "",
    "watermark_path": "",
    "colors": DEFAULT_COLORS.copy(),
    "social_links": {
        "youtube": "",
        "instagram": "",
        "website": "",
        "other": "",
    },
    "watermark_opacity": 65,
    "watermark_position": "bottom-right",
}


def ensure_directories() -> None:
    """Create required storage folders."""
    for folder in (DATA_DIR, BRAND_DIR, EXPORT_DIR):
        folder.mkdir(parents=True, exist_ok=True)


def safe_name(value: str, fallback: str = "brand") -> str:
    """Convert text into a safe filename or folder name."""
    value = re.sub(r"[^\w.-]+", "_", str(value).strip())
    value = value.strip("._")
    return value[:70] or fallback


def validate_hex_color(value: str) -> str:
    """Validate a hexadecimal color and return uppercase form."""
    value = str(value).strip()

    if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ValueError(
            f"Invalid color '{value}'. Use a format such as #FFAA00."
        )

    return value.upper()


def validate_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a brand profile."""
    if not isinstance(profile, dict):
        raise ValueError("Brand profile must be a dictionary.")

    result = DEFAULT_PROFILE.copy()
    result.update(profile)

    name = str(result.get("name", "")).strip()
    if not name:
        raise ValueError("Brand name cannot be empty.")

    result["name"] = name[:100]
    result["description"] = str(result.get("description", ""))[:2000]
    result["tagline"] = str(result.get("tagline", ""))[:300]
    result["primary_font"] = str(result.get("primary_font", "Arial"))[:100]
    result["secondary_font"] = str(
        result.get("secondary_font", "Arial")
    )[:100]

    colors = DEFAULT_COLORS.copy()
    supplied_colors = result.get("colors", {})

    if not isinstance(supplied_colors, dict):
        raise ValueError("Colors must be a dictionary.")

    for key in colors:
        if key in supplied_colors:
            colors[key] = validate_hex_color(supplied_colors[key])

    result["colors"] = colors

    social_defaults = DEFAULT_PROFILE["social_links"].copy()
    supplied_socials = result.get("social_links", {})

    if not isinstance(supplied_socials, dict):
        raise ValueError("Social links must be a dictionary.")

    for key in social_defaults:
        social_defaults[key] = str(
            supplied_socials.get(key, "")
        ).strip()[:500]

    result["social_links"] = social_defaults

    result["watermark_opacity"] = max(
        0,
        min(100, int(result.get("watermark_opacity", 65))),
    )

    allowed_positions = {
        "top-left",
        "top-right",
        "bottom-left",
        "bottom-right",
        "center",
    }

    position = result.get("watermark_position", "bottom-right")
    if position not in allowed_positions:
        position = "bottom-right"

    result["watermark_position"] = position
    result["logo_path"] = str(result.get("logo_path", ""))
    result["watermark_path"] = str(result.get("watermark_path", ""))

    return result


def load_database(
    database_file: Path | str = DATABASE_FILE,
) -> list[dict[str, Any]]:
    """Load saved brand profiles."""
    path = Path(database_file)

    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(data, list):
        return []

    valid_profiles = []

    for profile in data:
        if not isinstance(profile, dict):
            continue

        try:
            valid_profiles.append(profile)
        except (ValueError, TypeError):
            continue

    return valid_profiles


def save_database(
    profiles: list[dict[str, Any]],
    database_file: Path | str = DATABASE_FILE,
) -> None:
    """Save profiles atomically."""
    path = Path(database_file)
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(profiles, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    temporary.replace(path)


def get_profile(
    profile_id: str,
    database_file: Path | str = DATABASE_FILE,
) -> dict[str, Any] | None:
    """Find a profile by ID."""
    for profile in load_database(database_file):
        if profile.get("id") == profile_id:
            return profile

    return None


def create_profile(
    name: str,
    description: str = "",
    database_file: Path | str = DATABASE_FILE,
) -> dict[str, Any]:
    """Create a new brand profile."""
    profile = validate_profile({
        "name": name,
        "description": description,
    })

    profile["id"] = str(uuid.uuid4())
    profile["created_at"] = datetime.now().isoformat(timespec="seconds")
    profile["updated_at"] = profile["created_at"]

    profiles = load_database(database_file)
    profiles.insert(0, profile)
    save_database(profiles, database_file)

    return profile


def update_profile(
    profile_id: str,
    updates: dict[str, Any],
    database_file: Path | str = DATABASE_FILE,
) -> dict[str, Any]:
    """Update an existing profile."""
    profiles = load_database(database_file)

    for index, existing in enumerate(profiles):
        if existing.get("id") != profile_id:
            continue

        merged = existing.copy()

        # Merge nested settings instead of replacing them entirely.
        for key, value in updates.items():
            if key in ("colors", "social_links"):
                current = merged.get(key, {})
                if not isinstance(current, dict):
                    current = {}
                if isinstance(value, dict):
                    current.update(value)
                merged[key] = current
            else:
                merged[key] = value

        validated = validate_profile(merged)
        validated["id"] = profile_id
        validated["created_at"] = existing.get("created_at")
        validated["updated_at"] = datetime.now().isoformat(
            timespec="seconds"
        )

        profiles[index] = validated
        save_database(profiles, database_file)

        return validated

    raise KeyError(f"Brand profile not found: {profile_id}")


def delete_profile(
    profile_id: str,
    database_file: Path | str = DATABASE_FILE,
    delete_assets: bool = False,
) -> bool:
    """
    Delete a profile.

    By default, its asset folder is preserved to avoid accidental
    deletion of shared files.
    """
    profiles = load_database(database_file)
    matching = [
        profile for profile in profiles
        if profile.get("id") == profile_id
    ]

    if not matching:
        return False

    updated = [
        profile for profile in profiles
        if profile.get("id") != profile_id
    ]
    save_database(updated, database_file)

    if delete_assets:
        asset_folder = BRAND_DIR / safe_name(profile_id)

        if asset_folder.exists():
            resolved_folder = asset_folder.resolve()
            resolved_root = BRAND_DIR.resolve()

            if resolved_folder.parent == resolved_root:
                shutil.rmtree(resolved_folder)

    return True


def save_brand_asset(
    profile_id: str,
    asset_bytes: bytes,
    original_filename: str,
    asset_type: str = "logo",
) -> Path:
    """Save an uploaded logo or watermark."""
    if asset_type not in ("logo", "watermark"):
        raise ValueError("Asset type must be logo or watermark.")

    if not asset_bytes:
        raise ValueError("Uploaded asset is empty.")

    extension = Path(original_filename).suffix.lower()

    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError(
            "Unsupported image format. Use PNG, JPG, JPEG or WEBP."
        )

    # Verify that the profile ID is a UUID generated by this module.
    try:
        uuid.UUID(profile_id)
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Invalid brand profile ID.")

    folder = BRAND_DIR / safe_name(profile_id)
    folder.mkdir(parents=True, exist_ok=True)

    filename = f"{asset_type}_{uuid.uuid4().hex[:8]}{extension}"
    output_path = folder / filename

    output_path.write_bytes(asset_bytes)

    return output_path.resolve()


def remove_brand_asset(
    profile_id: str,
    asset_type: str,
    database_file: Path | str = DATABASE_FILE,
) -> dict[str, Any]:
    """Remove a logo or watermark reference and its stored file."""
    if asset_type not in ("logo", "watermark"):
        raise ValueError("Asset type must be logo or watermark.")

    profile = get_profile(profile_id, database_file)

    if profile is None:
        raise KeyError("Brand profile not found.")

    field = f"{asset_type}_path"
    stored_path = profile.get(field, "")

    if stored_path:
        path = Path(stored_path).resolve()
        asset_root = BRAND_DIR.resolve()

        if asset_root in path.parents and path.is_file():
            path.unlink()

    return update_profile(
        profile_id,
        {field: ""},
        database_file,
    )


def export_profile(
    profile_id: str,
    export_dir: Path | str = EXPORT_DIR,
    database_file: Path | str = DATABASE_FILE,
) -> Path:
    """Export a profile as a portable JSON file."""
    profile = get_profile(profile_id, database_file)

    if profile is None:
        raise KeyError("Brand profile not found.")

    destination = Path(export_dir)
    destination.mkdir(parents=True, exist_ok=True)

    filename = (
        safe_name(profile["name"])
        + "_"
        + profile_id[:8]
        + ".json"
    )

    output_path = destination / filename
    output_path.write_text(
        json.dumps(profile, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return output_path


def import_profile(
    json_bytes: bytes,
    database_file: Path | str = DATABASE_FILE,
) -> dict[str, Any]:
    """Import a profile from JSON, assigning it a new ID."""
    try:
        imported = json.loads(json_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid brand profile JSON file.") from exc

    if not isinstance(imported, dict):
        raise ValueError("Imported profile must be a JSON object.")

    profile = validate_profile(imported)

    profile["id"] = str(uuid.uuid4())
    profile["created_at"] = datetime.now().isoformat(timespec="seconds")
    profile["updated_at"] = profile["created_at"]

    # Imported asset paths are not copied automatically.
    # Users can upload the original logo and watermark again.
    profile["logo_path"] = ""
    profile["watermark_path"] = ""

    profiles = load_database(database_file)
    profiles.insert(0, profile)
    save_database(profiles, database_file)

    return profile


def get_color_palette(profile: dict[str, Any]) -> dict[str, str]:
    """Return the validated brand color palette."""
    validated = validate_profile(profile)
    return validated["colors"]


def render() -> None:
    """Render the Streamlit Brand Kit Manager."""
    try:
        import streamlit as st
    except ImportError as exc:
        raise RuntimeError(
            "Streamlit is required. Install it with: "
            "python -m pip install streamlit"
        ) from exc

    ensure_directories()

    st.title("🎨 Brand Kit Manager")
    st.caption(
        "Manage reusable logos, colors, typography and channel identity."
    )

    profiles = load_database()

    tab_create, tab_manage, tab_assets, tab_import = st.tabs(
        [
            "Create Brand",
            "Manage Brand",
            "Logo & Watermark",
            "Import / Export",
        ]
    )

    with tab_create:
        st.subheader("Create a new brand profile")

        with st.form("create_brand_form"):
            new_name = st.text_input(
                "Brand or channel name",
                placeholder="Example: AJVORO",
            )
            new_description = st.text_area(
                "Description",
                placeholder="Describe your channel identity...",
            )

            create_clicked = st.form_submit_button(
                "Create Brand Profile",
                type="primary",
            )

        if create_clicked:
            try:
                profile = create_profile(
                    new_name,
                    new_description,
                )
                st.success(
                    f"Created brand profile: {profile['name']}"
                )
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    with tab_manage:
        st.subheader("Manage brand identity")

        if not profiles:
            st.info("Create a brand profile first.")
        else:
            labels = {
                p["id"]: p.get("name", "Untitled")
                for p in profiles
            }

            selected_id = st.selectbox(
                "Select brand",
                list(labels.keys()),
                format_func=lambda value: labels[value],
                key="brand_manage_selection",
            )

            selected = get_profile(selected_id)

            if selected:
                st.markdown("#### Brand information")

                with st.form(f"edit_brand_{selected_id}"):
                    name = st.text_input(
                        "Brand name",
                        value=selected.get("name", ""),
                    )
                    description = st.text_area(
                        "Description",
                        value=selected.get("description", ""),
                    )
                    tagline = st.text_input(
                        "Tagline",
                        value=selected.get("tagline", ""),
                    )

                    st.markdown("#### Brand colors")

                    current_colors = selected.get(
                        "colors",
                        DEFAULT_COLORS,
                    )

                    color_columns = st.columns(2)
                    color_values = {}

                    for index, key in enumerate(DEFAULT_COLORS):
                        with color_columns[index % 2]:
                            color_values[key] = st.color_picker(
                                key.replace("_", " ").title(),
                                current_colors.get(
                                    key,
                                    DEFAULT_COLORS[key],
                                ),
                                key=f"color_{selected_id}_{key}",
                            )

                    st.markdown("#### Typography")

                    primary_font = st.text_input(
                        "Primary font",
                        value=selected.get("primary_font", "Arial"),
                    )
                    secondary_font = st.text_input(
                        "Secondary font",
                        value=selected.get("secondary_font", "Arial"),
                    )

                    save_clicked = st.form_submit_button(
                        "Save Brand Settings",
                        type="primary",
                    )

                if save_clicked:
                    try:
                        update_profile(
                            selected_id,
                            {
                                "name": name,
                                "description": description,
                                "tagline": tagline,
                                "colors": color_values,
                                "primary_font": primary_font,
                                "secondary_font": secondary_font,
                            },
                        )
                        st.success("Brand settings saved.")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

                st.markdown("#### Social links")

                socials = selected.get("social_links", {})

                with st.form(f"socials_{selected_id}"):
                    youtube = st.text_input(
                        "YouTube URL",
                        value=socials.get("youtube", ""),
                    )
                    instagram = st.text_input(
                        "Instagram URL",
                        value=socials.get("instagram", ""),
                    )
                    website = st.text_input(
                        "Website URL",
                        value=socials.get("website", ""),
                    )
                    other = st.text_input(
                        "Other link",
                        value=socials.get("other", ""),
                    )

                    social_save = st.form_submit_button(
                        "Save Social Links"
                    )

                if social_save:
                    try:
                        update_profile(
                            selected_id,
                            {
                                "social_links": {
                                    "youtube": youtube,
                                    "instagram": instagram,
                                    "website": website,
                                    "other": other,
                                }
                            },
                        )
                        st.success("Social links saved.")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

                if st.button(
                    "Delete Brand Profile",
                    key=f"delete_brand_{selected_id}",
                ):
                    st.session_state["confirm_delete_brand"] = selected_id

                if st.session_state.get("confirm_delete_brand") == selected_id:
                    st.warning(
                        "Delete this brand profile? Stored assets are "
                        "preserved by default."
                    )

                    confirm_col, cancel_col = st.columns(2)

                    with confirm_col:
                        if st.button(
                            "Confirm Delete",
                            key=f"confirm_delete_{selected_id}",
                        ):
                            delete_profile(selected_id)
                            st.session_state.pop(
                                "confirm_delete_brand",
                                None,
                            )
                            st.success("Brand profile deleted.")
                            st.rerun()

                    with cancel_col:
                        if st.button(
                            "Cancel",
                            key=f"cancel_delete_{selected_id}",
                        ):
                            st.session_state.pop(
                                "confirm_delete_brand",
                                None,
                            )
                            st.rerun()

    with tab_assets:
        st.subheader("Logo and watermark manager")

        profiles = load_database()

        if not profiles:
            st.info("Create a brand profile before uploading assets.")
        else:
            labels = {
                p["id"]: p.get("name", "Untitled")
                for p in profiles
            }

            selected_id = st.selectbox(
                "Choose brand",
                list(labels.keys()),
                format_func=lambda value: labels[value],
                key="brand_asset_selection",
            )

            selected = get_profile(selected_id)

            if selected:
                logo_upload = st.file_uploader(
                    "Upload brand logo",
                    type=["png", "jpg", "jpeg", "webp"],
                    key="brand_logo_upload",
                )

                if logo_upload and st.button(
                    "Save Logo",
                    key="save_brand_logo",
                ):
                    try:
                        path = save_brand_asset(
                            selected_id,
                            logo_upload.getvalue(),
                            logo_upload.name,
                            "logo",
                        )
                        update_profile(
                            selected_id,
                            {"logo_path": str(path)},
                        )
                        st.success("Logo saved.")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

                logo_path = Path(selected.get("logo_path", ""))

                if logo_path.is_file():
                    st.image(
                        str(logo_path),
                        caption="Current brand logo",
                        width=220,
                    )

                    if st.button(
                        "Remove Logo",
                        key="remove_brand_logo",
                    ):
                        remove_brand_asset(selected_id, "logo")
                        st.success("Logo removed.")
                        st.rerun()

                st.divider()

                watermark_upload = st.file_uploader(
                    "Upload watermark",
                    type=["png", "jpg", "jpeg", "webp"],
                    key="brand_watermark_upload",
                )

                if watermark_upload and st.button(
                    "Save Watermark",
                    key="save_brand_watermark",
                ):
                    try:
                        path = save_brand_asset(
                            selected_id,
                            watermark_upload.getvalue(),
                            watermark_upload.name,
                            "watermark",
                        )
                        update_profile(
                            selected_id,
                            {"watermark_path": str(path)},
                        )
                        st.success("Watermark saved.")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

                watermark_path = Path(
                    selected.get("watermark_path", "")
                )

                if watermark_path.is_file():
                    st.image(
                        str(watermark_path),
                        caption="Current watermark",
                        width=220,
                    )

                    if st.button(
                        "Remove Watermark",
                        key="remove_brand_watermark",
                    ):
                        remove_brand_asset(selected_id, "watermark")
                        st.success("Watermark removed.")
                        st.rerun()

                st.divider()
                st.markdown("#### Watermark settings")

                with st.form(f"watermark_settings_{selected_id}"):
                    opacity = st.slider(
                        "Watermark opacity",
                        0,
                        100,
                        int(selected.get("watermark_opacity", 65)),
                    )

                    position = st.selectbox(
                        "Watermark position",
                        [
                            "top-left",
                            "top-right",
                            "bottom-left",
                            "bottom-right",
                            "center",
                        ],
                        index=[
                            "top-left",
                            "top-right",
                            "bottom-left",
                            "bottom-right",
                            "center",
                        ].index(
                            selected.get(
                                "watermark_position",
                                "bottom-right",
                            )
                        ),
                    )

                    save_watermark_settings = st.form_submit_button(
                        "Save Watermark Settings"
                    )

                if save_watermark_settings:
                    update_profile(
                        selected_id,
                        {
                            "watermark_opacity": opacity,
                            "watermark_position": position,
                        },
                    )
                    st.success("Watermark settings saved.")
                    st.rerun()

    with tab_import:
        st.subheader("Import or export brand profiles")

        profiles = load_database()

        if profiles:
            labels = {
                p["id"]: p.get("name", "Untitled")
                for p in profiles
            }

            export_id = st.selectbox(
                "Select profile to export",
                list(labels.keys()),
                format_func=lambda value: labels[value],
                key="brand_export_selection",
            )

            if st.button("Prepare JSON Export"):
                try:
                    export_path = export_profile(export_id)
                    st.session_state["brand_export_path"] = str(
                        export_path
                    )
                    st.success("Export file prepared.")
                except Exception as exc:
                    st.error(str(exc))

            export_path_value = st.session_state.get(
                "brand_export_path"
            )

            if export_path_value:
                export_path = Path(export_path_value)

                if export_path.is_file():
                    with open(export_path, "rb") as file:
                        st.download_button(
                            "Download Brand Profile JSON",
                            data=file.read(),
                            file_name=export_path.name,
                            mime="application/json",
                        )

        st.divider()
        st.markdown("#### Import a brand profile")

        import_upload = st.file_uploader(
            "Choose a brand profile JSON file",
            type=["json"],
            key="brand_import_upload",
        )

        if import_upload and st.button("Import Brand Profile"):
            try:
                profile = import_profile(import_upload.getvalue())
                st.success(
                    f"Imported brand: {profile['name']}"
                )
                st.info(
                    "Logo and watermark files are not embedded in JSON. "
                    "Upload them again in the Logo & Watermark tab."
                )
                st.rerun()
            except Exception as exc:
                st.error(f"Import failed: {exc}")

    st.divider()
    st.caption(
        "Brand profiles and uploaded assets are stored locally "
        "in your project folder."
    )


# ---------------------------------------------------------------------
# Built-in tests
# ---------------------------------------------------------------------

def run_tests() -> None:
    """Run tests using temporary directories."""
    import tempfile

    print("Running Brand Kit tests...")

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        database_file = root / "data" / "brand_kits.json"

        # Test default profile validation.
        profile = validate_profile({"name": "Test Brand"})
        assert profile["name"] == "Test Brand"
        assert profile["colors"]["primary"] == "#172554"

        # Test invalid colors.
        try:
            validate_hex_color("red")
            raise AssertionError("Invalid color should have failed.")
        except ValueError:
            pass

        # Test create and read.
        created = create_profile(
            "Test Channel",
            "A test description",
            database_file,
        )

        assert created["id"]
        assert get_profile(
            created["id"],
            database_file,
        )["name"] == "Test Channel"

        # Test profile update.
        updated = update_profile(
            created["id"],
            {
                "tagline": "Test tagline",
                "colors": {"accent": "#FF0000"},
                "social_links": {"youtube": "https://example.com"},
            },
            database_file,
        )

        assert updated["tagline"] == "Test tagline"
        assert updated["colors"]["accent"] == "#FF0000"
        assert updated["colors"]["primary"] == "#172554"
        assert updated["social_links"]["youtube"] == (
            "https://example.com"
        )

        # Test export and import.
        export_dir = root / "exports"
        exported = export_profile(
            created["id"],
            export_dir,
            database_file,
        )

        assert exported.exists()

        imported = import_profile(
            exported.read_bytes(),
            database_file,
        )

        assert imported["name"] == "Test Channel"
        assert imported["id"] != created["id"]
        assert imported["logo_path"] == ""

        # Test asset storage with arbitrary image bytes.
        # This tests storage only; image decoding is handled by
        # downstream modules such as Pillow.
        brand_root = root / "brand_assets"
        original_brand_dir = globals()["BRAND_DIR"]

        try:
            globals()["BRAND_DIR"] = brand_root

            asset_path = save_brand_asset(
                created["id"],
                b"test-image-data",
                "logo.png",
                "logo",
            )

            assert asset_path.exists()
            assert asset_path.name.startswith("logo_")
            assert asset_path.suffix == ".png"

        finally:
            globals()["BRAND_DIR"] = original_brand_dir

        # Test database deletion.
        assert delete_profile(
            created["id"],
            database_file,
        ) is True

        assert get_profile(
            created["id"],
            database_file,
        ) is None

        assert delete_profile(
            "missing-profile",
            database_file,
        ) is False

    print("All Brand Kit tests passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AI Influencer Studio Brand Kit Manager"
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
        ensure_directories()
        print("Brand Kit Manager module loaded.")
        print("Run with --test to execute built-in tests.")
