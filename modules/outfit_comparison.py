
"""
AI Influencer Studio
File 32: modules/outfit_comparison.py

Purpose:
- Compare up to four saved outfits.
- Display outfit details and reference images.
- Compare character compatibility, colors, materials and styling.
- Export comparison reports as JSON.

This module does not generate or modify AI images.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------
# MODULE INTEGRATION
# ---------------------------------------------------------

try:
    from modules import outfit_manager
except ImportError:
    outfit_manager = None

try:
    from modules import outfit_gallery
except ImportError:
    outfit_gallery = None


# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
COMPARISON_DIR = DATA_DIR / "outfit_comparisons"

DEFAULT_EXPORT_DIR = PROJECT_ROOT / "outputs" / "comparisons"


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item) for item in value)
    return str(value).strip()


def _as_list(value: Any) -> list[str]:
    """Convert a string or collection into a clean list."""
    if value is None:
        return []

    if isinstance(value, str):
        values = value.replace(";", ",").split(",")
    elif isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        values = [value]

    return [
        str(item).strip()
        for item in values
        if str(item).strip()
    ]


def _safe_id(value: str) -> str:
    value = str(value or "").strip()

    if not value:
        raise ValueError("A valid ID is required.")

    cleaned = "".join(
        char if char.isalnum() or char in "_-" else "_"
        for char in value
    )

    return cleaned[:100]


def _ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    COMPARISON_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_EXPORT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# OUTFIT DATA
# ---------------------------------------------------------

def get_all_outfits() -> list[dict]:
    """Load outfits from File 30."""
    if outfit_manager is None:
        raise RuntimeError("outfit_manager.py is unavailable.")

    outfits = outfit_manager.list_outfits()

    return [
        item.copy()
        for item in outfits
        if isinstance(item, dict)
    ]


def get_outfit_details(outfit_id: str) -> dict:
    """Get a saved outfit by its ID."""
    if outfit_manager is None:
        raise RuntimeError("outfit_manager.py is unavailable.")

    outfit = outfit_manager.get_outfit(outfit_id)

    if not outfit:
        raise ValueError(f"Outfit not found: {outfit_id}")

    return outfit.copy()


def get_reference_images(outfit_id: str) -> list[dict]:
    """Get reference images registered by File 31."""
    if outfit_gallery is None:
        return []

    try:
        return outfit_gallery.list_references(outfit_id)
    except Exception:
        return []


# ---------------------------------------------------------
# COMPARISON LOGIC
# ---------------------------------------------------------

COMPARISON_FIELDS = [
    "name",
    "category",
    "description",
    "topwear",
    "bottomwear",
    "footwear",
    "colors",
    "materials",
    "accessories",
    "hairstyle",
    "makeup",
    "season",
    "occasion",
    "visual_style",
    "negative_prompt",
]


def normalize_outfit(outfit: dict) -> dict:
    """Return a consistent comparison-friendly outfit structure."""
    normalized = {}

    for field in COMPARISON_FIELDS:
        value = outfit.get(field, "")

        if field in {
            "colors",
            "materials",
            "accessories",
        }:
            normalized[field] = _as_list(value)
        else:
            normalized[field] = _clean_text(value)

    normalized["id"] = str(outfit.get("id", ""))
    normalized["character_id"] = str(
        outfit.get("character_id", "")
    )

    return normalized


def compare_outfits(outfit_ids: list[str]) -> dict:
    """
    Compare two to four saved outfits.

    Returns a dictionary with outfit details, differences,
    shared properties and character compatibility.
    """
    unique_ids = list(dict.fromkeys(
        str(item).strip()
        for item in outfit_ids
        if str(item).strip()
    ))

    if len(unique_ids) < 2:
        raise ValueError("Select at least two outfits.")

    if len(unique_ids) > 4:
        raise ValueError("You can compare a maximum of four outfits.")

    outfits = [
        normalize_outfit(get_outfit_details(outfit_id))
        for outfit_id in unique_ids
    ]

    # Character compatibility.
    character_ids = {
        item["character_id"]
        for item in outfits
        if item["character_id"]
    }

    same_character = (
        len(character_ids) == 1
        and all(item["character_id"] for item in outfits)
    )

    # Compare each supported field.
    field_comparison = {}

    for field in COMPARISON_FIELDS:
        values = [
            item.get(field, [])
            for item in outfits
        ]

        distinct_values = {
            json.dumps(value, sort_keys=True)
            for value in values
        }

        field_comparison[field] = {
            "values": values,
            "is_same": len(distinct_values) == 1,
            "different_count": len(distinct_values),
        }

    # Common colors and materials.
    color_sets = [
        {value.lower() for value in item["colors"]}
        for item in outfits
    ]

    material_sets = [
        {value.lower() for value in item["materials"]}
        for item in outfits
    ]

    common_colors = (
        sorted(set.intersection(*color_sets))
        if color_sets else []
    )

    common_materials = (
        sorted(set.intersection(*material_sets))
        if material_sets else []
    )

    # Common categories.
    categories = [
        item["category"].lower()
        for item in outfits
        if item["category"]
    ]

    return {
        "comparison_id": uuid.uuid4().hex[:12],
        "created_at": _now(),
        "outfit_count": len(outfits),
        "outfits": outfits,
        "same_character": same_character,
        "character_ids": sorted(character_ids),
        "common_colors": common_colors,
        "common_materials": common_materials,
        "same_category": (
            len(set(categories)) == 1
            and len(categories) == len(outfits)
        ),
        "fields": field_comparison,
    }


# ---------------------------------------------------------
# COMPARISON REPORT
# ---------------------------------------------------------

def build_comparison_report(comparison: dict) -> dict:
    """Create a readable report from a comparison."""
    outfits = comparison.get("outfits", [])

    differences = []
    similarities = []

    for field, result in comparison.get("fields", {}).items():
        if result["is_same"]:
            similarities.append(field)
        else:
            differences.append(field)

    return {
        "comparison_id": comparison.get("comparison_id"),
        "created_at": comparison.get("created_at"),
        "outfit_count": len(outfits),
        "outfit_names": [
            item.get("name") or item.get("id")
            for item in outfits
        ],
        "same_character": comparison.get("same_character"),
        "character_ids": comparison.get("character_ids", []),
        "same_category": comparison.get("same_category"),
        "common_colors": comparison.get("common_colors", []),
        "common_materials": comparison.get("common_materials", []),
        "similar_fields": similarities,
        "different_fields": differences,
    }


# ---------------------------------------------------------
# SAVE AND LOAD COMPARISON HISTORY
# ---------------------------------------------------------

def _history_file(path: Path | str | None = None) -> Path:
    if path:
        return Path(path)

    return COMPARISON_DIR / "history.json"


def load_history(path: Path | str | None = None) -> list[dict]:
    history_path = _history_file(path)

    if not history_path.exists():
        return []

    try:
        with history_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, list):
            raise ValueError("Comparison history must be a list.")

        return data

    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(
            f"Could not load comparison history: {exc}"
        ) from exc


def save_comparison(
    comparison: dict,
    path: Path | str | None = None,
) -> dict:
    """Save a comparison to local JSON history."""
    history_path = _history_file(path)
    history_path.parent.mkdir(parents=True, exist_ok=True)

    history = load_history(history_path)

    record = {
        "comparison": comparison,
        "report": build_comparison_report(comparison),
    }

    history.append(record)

    temporary_path = history_path.with_name(
        history_path.name + ".tmp"
    )

    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(history, file, indent=4, ensure_ascii=False)

    temporary_path.replace(history_path)

    return record


def delete_comparison(
    comparison_id: str,
    path: Path | str | None = None,
) -> bool:
    """Delete a saved comparison from history."""
    history_path = _history_file(path)
    history = load_history(history_path)

    updated = [
        item for item in history
        if item.get("comparison", {}).get("comparison_id")
        != comparison_id
    ]

    if len(updated) == len(history):
        return False

    history_path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = history_path.with_name(
        history_path.name + ".tmp"
    )

    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(updated, file, indent=4, ensure_ascii=False)

    temporary_path.replace(history_path)

    return True


# ---------------------------------------------------------
# EXPORT
# ---------------------------------------------------------

def export_comparison(
    comparison: dict,
    output_dir: Path | str | None = None,
) -> Path:
    """Export a comparison report as JSON."""
    destination_dir = (
        Path(output_dir)
        if output_dir
        else DEFAULT_EXPORT_DIR
    )

    destination_dir.mkdir(parents=True, exist_ok=True)

    comparison_id = _safe_id(
        comparison.get("comparison_id", uuid.uuid4().hex[:12])
    )

    output_path = destination_dir / (
        f"outfit_comparison_{comparison_id}.json"
    )

    payload = {
        "comparison": comparison,
        "report": build_comparison_report(comparison),
    }

    temporary_path = output_path.with_name(
        output_path.name + ".tmp"
    )

    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=4, ensure_ascii=False)

    temporary_path.replace(output_path)

    return output_path


# ---------------------------------------------------------
# STREAMLIT UI
# ---------------------------------------------------------

def render(st: Any) -> None:
    """Render the Outfit Comparison Studio."""
    _ensure_directories()

    st.title("Outfit Comparison Studio")
    st.caption(
        "Compare saved outfits and review their visual design details."
    )

    try:
        outfits = get_all_outfits()
    except Exception as exc:
        st.error(f"Could not load outfits: {exc}")
        return

    if len(outfits) < 2:
        st.info(
            "Create at least two outfits in Outfit Studio "
            "before comparing them."
        )
        return

    outfit_lookup = {}
    labels = []

    for outfit in outfits:
        outfit_id = str(outfit.get("id", ""))

        if not outfit_id:
            continue

        name = outfit.get("name", "Unnamed Outfit")
        label = f"{name} ({outfit_id[:8]})"

        outfit_lookup[label] = outfit_id
        labels.append(label)

    if len(labels) < 2:
        st.warning("Not enough valid outfits to compare.")
        return

    st.subheader("Select outfits")

    selected_labels = st.multiselect(
        "Choose 2–4 outfits",
        options=labels,
        max_selections=4,
        key="outfit_comparison_selection",
    )

    if st.button(
        "Compare Selected Outfits",
        type="primary",
        disabled=len(selected_labels) < 2,
    ):
        selected_ids = [
            outfit_lookup[label]
            for label in selected_labels
        ]

        try:
            comparison = compare_outfits(selected_ids)
            save_comparison(comparison)

            st.session_state[
                "latest_outfit_comparison"
            ] = comparison

            st.success("Comparison completed and saved.")

        except Exception as exc:
            st.error(f"Comparison failed: {exc}")

    comparison = st.session_state.get(
        "latest_outfit_comparison"
    )

    if not comparison:
        st.info("Select outfits and click Compare to begin.")
        return

    st.divider()
    st.subheader("Comparison results")

    if comparison["same_character"]:
        st.success(
            "All selected outfits belong to the same character."
        )
    else:
        st.warning(
            "These outfits are not all linked to the same character."
        )

    if comparison["same_category"]:
        st.info("All selected outfits have the same category.")

    # Side-by-side outfit columns.
    outfit_columns = st.columns(
        len(comparison["outfits"])
    )

    for index, outfit in enumerate(comparison["outfits"]):
        with outfit_columns[index]:
            st.markdown(f"**{outfit.get('name') or 'Outfit'}**")
            st.caption(outfit.get("category", "No category"))

            references = get_reference_images(outfit["id"])

            if references:
                image_path = None

                for reference in references:
                    if outfit_gallery:
                        image_path = (
                            outfit_gallery.get_reference_image_path(
                                reference
                            )
                        )

                    if image_path:
                        break

                if image_path:
                    st.image(
                        str(image_path),
                        use_container_width=True,
                    )
                else:
                    st.caption("Reference image unavailable.")
            else:
                st.caption("No reference images.")

    # Detailed field comparison.
    st.subheader("Design details")

    for field, result in comparison["fields"].items():
        with st.expander(
            f"{field.replace('_', ' ').title()} "
            f"{'— Same' if result['is_same'] else '— Different'}"
        ):
            field_columns = st.columns(
                len(comparison["outfits"])
            )

            for index, value in enumerate(result["values"]):
                with field_columns[index]:
                    outfit_name = (
                        comparison["outfits"][index].get("name")
                        or f"Outfit {index + 1}"
                    )

                    st.markdown(f"**{outfit_name}**")

                    if isinstance(value, list):
                        if value:
                            for item in value:
                                st.write(f"• {item}")
                        else:
                            st.caption("Not specified")
                    else:
                        st.write(value or "Not specified")

    # Similarity summary.
    st.subheader("Shared design elements")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Common colors**")

        if comparison["common_colors"]:
            st.write(", ".join(comparison["common_colors"]))
        else:
            st.caption("No common colors recorded.")

    with col2:
        st.markdown("**Common materials**")

        if comparison["common_materials"]:
            st.write(", ".join(comparison["common_materials"]))
        else:
            st.caption("No common materials recorded.")

    # Export.
    st.divider()
    st.subheader("Export comparison")

    report = build_comparison_report(comparison)

    st.download_button(
        label="Download comparison JSON",
        data=json.dumps(
            {
                "comparison": comparison,
                "report": report,
            },
            indent=4,
            ensure_ascii=False,
        ),
        file_name=(
            f"outfit_comparison_"
            f"{comparison['comparison_id']}.json"
        ),
        mime="application/json",
    )

    if st.button("Export to project folder"):
        try:
            output_path = export_comparison(comparison)
            st.success(f"Exported: {output_path}")
        except Exception as exc:
            st.error(f"Export failed: {exc}")


# ---------------------------------------------------------
# BUILT-IN TESTS
# ---------------------------------------------------------

def run_tests() -> bool:
    import tempfile
    import unittest

    class OutfitComparisonTests(unittest.TestCase):

        def setUp(self):
            self.temp_dir = tempfile.TemporaryDirectory()
            self.root = Path(self.temp_dir.name)

            self.history_path = self.root / "history.json"
            self.export_dir = self.root / "exports"

        def tearDown(self):
            self.temp_dir.cleanup()

        def sample_outfit(
            self,
            outfit_id,
            character_id="character_1",
            colors=None,
        ):
            return {
                "id": outfit_id,
                "character_id": character_id,
                "name": f"Outfit {outfit_id}",
                "category": "Casual",
                "description": "Test outfit",
                "topwear": "Jacket",
                "bottomwear": "Jeans",
                "footwear": "Boots",
                "colors": colors or ["Black", "Blue"],
                "materials": ["Cotton"],
                "accessories": ["Watch"],
                "hairstyle": "Natural",
                "makeup": "Light",
                "season": "Winter",
                "occasion": "Travel",
                "visual_style": "Cinematic",
                "negative_prompt": "",
            }

        def test_normalize_outfit(self):
            outfit = self.sample_outfit("outfit_1")
            result = normalize_outfit(outfit)

            self.assertEqual(result["id"], "outfit_1")
            self.assertEqual(result["colors"], ["Black", "Blue"])

        def test_normalize_string_lists(self):
            outfit = self.sample_outfit("outfit_1")
            outfit["colors"] = "Black, Blue, White"

            result = normalize_outfit(outfit)

            self.assertEqual(
                result["colors"],
                ["Black", "Blue", "White"],
            )

        def test_reject_one_outfit(self):
            with self.assertRaises(ValueError):
                compare_outfits(["outfit_1"])

        def test_reject_more_than_four(self):
            with self.assertRaises(ValueError):
                compare_outfits([
                    "a", "b", "c", "d", "e"
                ])

        def test_reject_duplicate_only_selection(self):
            with self.assertRaises(ValueError):
                compare_outfits(["a", "a"])

        def test_comparison_with_mocked_outfits(self):
            sample_data = {
                "a": self.sample_outfit("a"),
                "b": self.sample_outfit("b"),
            }

            original = get_outfit_details

            try:
                globals()["get_outfit_details"] = (
                    lambda outfit_id: sample_data[outfit_id]
                )

                result = compare_outfits(["a", "b"])

                self.assertEqual(result["outfit_count"], 2)
                self.assertTrue(result["same_character"])
                self.assertTrue(result["same_category"])

            finally:
                globals()["get_outfit_details"] = original

        def test_detect_different_colors(self):
            sample_data = {
                "a": self.sample_outfit(
                    "a",
                    colors=["Black", "Blue"],
                ),
                "b": self.sample_outfit(
                    "b",
                    colors=["Red", "Blue"],
                ),
            }

            original = get_outfit_details

            try:
                globals()["get_outfit_details"] = (
                    lambda outfit_id: sample_data[outfit_id]
                )

                result = compare_outfits(["a", "b"])

                self.assertFalse(
                    result["fields"]["colors"]["is_same"]
                )

                self.assertEqual(
                    result["common_colors"],
                    ["blue"],
                )

            finally:
                globals()["get_outfit_details"] = original

        def test_detect_different_characters(self):
            sample_data = {
                "a": self.sample_outfit(
                    "a",
                    character_id="character_1",
                ),
                "b": self.sample_outfit(
                    "b",
                    character_id="character_2",
                ),
            }

            original = get_outfit_details

            try:
                globals()["get_outfit_details"] = (
                    lambda outfit_id: sample_data[outfit_id]
                )

                result = compare_outfits(["a", "b"])

                self.assertFalse(result["same_character"])

            finally:
                globals()["get_outfit_details"] = original

        def test_build_report(self):
            comparison = {
                "comparison_id": "test123",
                "created_at": _now(),
                "outfits": [
                    {"id": "a", "name": "A"},
                    {"id": "b", "name": "B"},
                ],
                "same_character": True,
                "character_ids": ["character_1"],
                "same_category": True,
                "common_colors": ["black"],
                "common_materials": ["cotton"],
                "fields": {
                    "colors": {
                        "is_same": False,
                    },
                    "category": {
                        "is_same": True,
                    },
                },
            }

            report = build_comparison_report(comparison)

            self.assertEqual(report["outfit_count"], 2)
            self.assertIn("colors", report["different_fields"])
            self.assertIn("category", report["similar_fields"])

        def test_save_and_load_history(self):
            comparison = {
                "comparison_id": "history123",
                "created_at": _now(),
                "outfits": [],
                "fields": {},
            }

            save_comparison(
                comparison,
                path=self.history_path,
            )

            history = load_history(self.history_path)

            self.assertEqual(len(history), 1)
            self.assertEqual(
                history[0]["comparison"]["comparison_id"],
                "history123",
            )

        def test_delete_history(self):
            comparison = {
                "comparison_id": "delete123",
                "created_at": _now(),
                "outfits": [],
                "fields": {},
            }

            save_comparison(
                comparison,
                path=self.history_path,
            )

            deleted = delete_comparison(
                "delete123",
                path=self.history_path,
            )

            self.assertTrue(deleted)
            self.assertEqual(load_history(self.history_path), [])

        def test_export_json(self):
            comparison = {
                "comparison_id": "export123",
                "created_at": _now(),
                "outfits": [],
                "fields": {},
            }

            output = export_comparison(
                comparison,
                output_dir=self.export_dir,
            )

            self.assertTrue(output.exists())

            with output.open("r", encoding="utf-8") as file:
                data = json.load(file)

            self.assertIn("comparison", data)
            self.assertIn("report", data)

        def test_safe_id(self):
            result = _safe_id("outfit/123")

            self.assertNotIn("/", result)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        OutfitComparisonTests
    )

    result = unittest.TextTestRunner(verbosity=2).run(suite)

    return result.wasSuccessful()


# ---------------------------------------------------------
# COMMAND LINE
# ---------------------------------------------------------

if __name__ == "__main__":
    import sys

    if "--test" in sys.argv:
        success = run_tests()
        raise SystemExit(0 if success else 1)

    print("AI Influencer Studio - Outfit Comparison")
    print("Run tests using:")
    print("python -m modules.outfit_comparison --test")
