
"""
AI Influencer Studio
File 27: Professional Prompt Manager

Features:
- Create, edit, duplicate and delete prompts
- Image, video, voice, motion and character categories
- Prompt templates with {{variable}} placeholders
- Search and filter prompt library
- Favorite prompts
- JSON import and export
- Persistent local storage
- Streamlit interface
- Built-in tests

Run tests:
    python -m modules.prompt_manager --test
"""

from __future__ import annotations

import argparse
import json
import re
import tempfile
import unittest
import uuid

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

APP_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROMPT_FILE = APP_ROOT / "data" / "prompts.json"

CATEGORIES = [
    "image",
    "video",
    "voice",
    "motion",
    "character",
    "social_media",
    "general",
]

MAX_PROMPTS = 10000
MAX_PROMPT_LENGTH = 50000
MAX_IMPORT_BYTES = 10 * 1024 * 1024


# ---------------------------------------------------------
# STORAGE
# ---------------------------------------------------------

def get_storage_path(path: str | Path | None = None) -> Path:
    """Return the local prompt database path."""

    if path is not None:
        return Path(path).expanduser().resolve()

    return DEFAULT_PROMPT_FILE.resolve()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_store() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": _now(),
        "prompts": [],
    }


def load_store(
    path: str | Path | None = None,
) -> dict[str, Any]:
    """Load the prompt library safely."""

    storage_path = get_storage_path(path)

    if not storage_path.exists():
        return _empty_store()

    try:
        if storage_path.stat().st_size > MAX_IMPORT_BYTES:
            raise ValueError("Prompt database is too large.")

        data = json.loads(
            storage_path.read_text(encoding="utf-8")
        )

        if not isinstance(data, dict):
            raise ValueError("Invalid prompt database format.")

        prompts = data.get("prompts", [])

        if not isinstance(prompts, list):
            raise ValueError("Invalid prompts collection.")

        valid_prompts = []

        for prompt in prompts:
            if not isinstance(prompt, dict):
                continue

            if not isinstance(prompt.get("id"), str):
                continue

            if not isinstance(prompt.get("title"), str):
                continue

            if not isinstance(prompt.get("content"), str):
                continue

            valid_prompts.append(prompt)

        return {
            "version": 1,
            "updated_at": data.get("updated_at", _now()),
            "prompts": valid_prompts[:MAX_PROMPTS],
        }

    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Prompt database contains invalid JSON: {exc}"
        ) from exc


def save_store(
    store: dict[str, Any],
    path: str | Path | None = None,
) -> None:
    """Save prompt database using an atomic replacement."""

    if not isinstance(store, dict):
        raise ValueError("Store must be a dictionary.")

    prompts = store.get("prompts")

    if not isinstance(prompts, list):
        raise ValueError("Prompts must be a list.")

    if len(prompts) > MAX_PROMPTS:
        raise ValueError("Prompt limit exceeded.")

    storage_path = get_storage_path(path)
    storage_path.parent.mkdir(parents=True, exist_ok=True)

    store["updated_at"] = _now()

    temporary_path = storage_path.with_name(
        storage_path.name + ".tmp"
    )

    try:
        temporary_path.write_text(
            json.dumps(
                store,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        temporary_path.replace(storage_path)

    except OSError:
        temporary_path.unlink(missing_ok=True)
        raise


# ---------------------------------------------------------
# PROMPT VALIDATION
# ---------------------------------------------------------

def _validate_prompt(
    title: str,
    content: str,
    category: str,
) -> tuple[str, str, str]:

    title = str(title).strip()
    content = str(content).strip()
    category = str(category).strip().lower()

    if not title:
        raise ValueError("Prompt title is required.")

    if len(title) > 200:
        raise ValueError("Prompt title is too long.")

    if not content:
        raise ValueError("Prompt content is required.")

    if len(content) > MAX_PROMPT_LENGTH:
        raise ValueError("Prompt content is too long.")

    if category not in CATEGORIES:
        raise ValueError("Invalid prompt category.")

    return title, content, category


# ---------------------------------------------------------
# CREATE PROMPT
# ---------------------------------------------------------

def create_prompt(
    title: str,
    content: str,
    category: str = "general",
    description: str = "",
    tags: list[str] | None = None,
    favorite: bool = False,
    path: str | Path | None = None,
) -> dict[str, Any]:
    """Create and save a new prompt."""

    title, content, category = _validate_prompt(
        title,
        content,
        category,
    )

    store = load_store(path)

    if len(store["prompts"]) >= MAX_PROMPTS:
        raise ValueError("Prompt library limit reached.")

    normalized_tags = []

    for tag in tags or []:
        tag = str(tag).strip()

        if tag and tag not in normalized_tags:
            normalized_tags.append(tag[:50])

    prompt = {
        "id": uuid.uuid4().hex,
        "title": title,
        "content": content,
        "category": category,
        "description": str(description).strip()[:1000],
        "tags": normalized_tags,
        "favorite": bool(favorite),
        "created_at": _now(),
        "updated_at": _now(),
        "usage_count": 0,
    }

    store["prompts"].append(prompt)
    save_store(store, path)

    return prompt


# ---------------------------------------------------------
# GET PROMPT
# ---------------------------------------------------------

def get_prompt(
    prompt_id: str,
    path: str | Path | None = None,
) -> dict[str, Any] | None:

    store = load_store(path)

    for prompt in store["prompts"]:
        if prompt["id"] == prompt_id:
            return dict(prompt)

    return None


# ---------------------------------------------------------
# LIST PROMPTS
# ---------------------------------------------------------

def list_prompts(
    category: str = "all",
    search: str = "",
    favorites_only: bool = False,
    path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Return filtered prompts."""

    store = load_store(path)

    search = search.strip().casefold()

    results = []

    for prompt in store["prompts"]:

        if category != "all" and prompt.get("category") != category:
            continue

        if favorites_only and not prompt.get("favorite", False):
            continue

        searchable = " ".join([
            prompt.get("title", ""),
            prompt.get("content", ""),
            prompt.get("description", ""),
            " ".join(prompt.get("tags", [])),
        ]).casefold()

        if search and search not in searchable:
            continue

        results.append(dict(prompt))

    return sorted(
        results,
        key=lambda item: item.get("updated_at", ""),
        reverse=True,
    )


# ---------------------------------------------------------
# UPDATE PROMPT
# ---------------------------------------------------------

def update_prompt(
    prompt_id: str,
    path: str | Path | None = None,
    **changes: Any,
) -> dict[str, Any]:

    allowed = {
        "title",
        "content",
        "category",
        "description",
        "tags",
        "favorite",
    }

    unknown = set(changes) - allowed

    if unknown:
        raise ValueError(
            f"Unsupported prompt fields: {', '.join(sorted(unknown))}"
        )

    store = load_store(path)

    for prompt in store["prompts"]:

        if prompt["id"] != prompt_id:
            continue

        updated = dict(prompt)
        updated.update(changes)

        title, content, category = _validate_prompt(
            updated["title"],
            updated["content"],
            updated["category"],
        )

        updated["title"] = title
        updated["content"] = content
        updated["category"] = category
        updated["description"] = str(
            updated.get("description", "")
        ).strip()[:1000]

        updated["tags"] = [
            str(tag).strip()[:50]
            for tag in updated.get("tags", [])
            if str(tag).strip()
        ]

        updated["favorite"] = bool(
            updated.get("favorite", False)
        )

        updated["updated_at"] = _now()

        prompt.clear()
        prompt.update(updated)

        save_store(store, path)

        return dict(prompt)

    raise ValueError("Prompt not found.")


# ---------------------------------------------------------
# DELETE PROMPT
# ---------------------------------------------------------

def delete_prompt(
    prompt_id: str,
    path: str | Path | None = None,
) -> bool:

    store = load_store(path)

    original_count = len(store["prompts"])

    store["prompts"] = [
        prompt for prompt in store["prompts"]
        if prompt["id"] != prompt_id
    ]

    if len(store["prompts"]) == original_count:
        return False

    save_store(store, path)

    return True


# ---------------------------------------------------------
# DUPLICATE PROMPT
# ---------------------------------------------------------

def duplicate_prompt(
    prompt_id: str,
    path: str | Path | None = None,
) -> dict[str, Any]:

    original = get_prompt(prompt_id, path)

    if original is None:
        raise ValueError("Prompt not found.")

    return create_prompt(
        title=f"{original['title']} (Copy)",
        content=original["content"],
        category=original["category"],
        description=original.get("description", ""),
        tags=original.get("tags", []),
        path=path,
    )


# ---------------------------------------------------------
# FAVORITES
# ---------------------------------------------------------

def toggle_favorite(
    prompt_id: str,
    path: str | Path | None = None,
) -> dict[str, Any]:

    prompt = get_prompt(prompt_id, path)

    if prompt is None:
        raise ValueError("Prompt not found.")

    return update_prompt(
        prompt_id,
        path=path,
        favorite=not prompt.get("favorite", False),
    )


# ---------------------------------------------------------
# PROMPT USAGE TRACKING
# ---------------------------------------------------------

def record_usage(
    prompt_id: str,
    path: str | Path | None = None,
) -> dict[str, Any]:

    prompt = get_prompt(prompt_id, path)

    if prompt is None:
        raise ValueError("Prompt not found.")

    return update_prompt(
        prompt_id,
        path=path,
        # Usage count is updated separately below.
    ) if False else _increment_usage(prompt_id, path)


def _increment_usage(
    prompt_id: str,
    path: str | Path | None = None,
) -> dict[str, Any]:

    store = load_store(path)

    for prompt in store["prompts"]:
        if prompt["id"] == prompt_id:
            prompt["usage_count"] = (
                int(prompt.get("usage_count", 0)) + 1
            )
            prompt["updated_at"] = _now()

            save_store(store, path)

            return dict(prompt)

    raise ValueError("Prompt not found.")


# ---------------------------------------------------------
# TEMPLATE VARIABLES
# ---------------------------------------------------------

VARIABLE_PATTERN = re.compile(
    r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}"
)


def extract_variables(content: str) -> list[str]:
    """Find all unique template variables."""

    return list(dict.fromkeys(
        VARIABLE_PATTERN.findall(content)
    ))


def render_template(
    content: str,
    variables: dict[str, Any],
    strict: bool = True,
) -> str:
    """
    Replace variables such as {{character_name}}.

    In strict mode, missing variables raise ValueError.
    """

    required = extract_variables(content)

    if strict:
        missing = [
            name for name in required
            if name not in variables
        ]

        if missing:
            raise ValueError(
                "Missing template variables: "
                + ", ".join(missing)
            )

    def replace(match: re.Match) -> str:
        name = match.group(1)

        if name not in variables:
            return match.group(0)

        return str(variables[name])

    return VARIABLE_PATTERN.sub(replace, content)


# ---------------------------------------------------------
# JSON EXPORT
# ---------------------------------------------------------

def export_prompts(
    output_path: str | Path,
    path: str | Path | None = None,
) -> Path:

    store = load_store(path)

    destination = Path(output_path).expanduser().resolve()

    if destination.suffix.lower() != ".json":
        raise ValueError("Export destination must be a JSON file.")

    destination.parent.mkdir(parents=True, exist_ok=True)

    temporary = destination.with_name(
        destination.name + ".tmp"
    )

    try:
        temporary.write_text(
            json.dumps(
                store,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        temporary.replace(destination)

    except OSError:
        temporary.unlink(missing_ok=True)
        raise

    return destination


# ---------------------------------------------------------
# JSON IMPORT
# ---------------------------------------------------------

def import_prompts(
    input_path: str | Path,
    merge: bool = True,
    path: str | Path | None = None,
) -> int:
    """
    Import prompts from a JSON file.

    merge=True:
        Keep existing prompts and add imported prompts.

    merge=False:
        Replace the existing prompt collection.

    Imported prompt IDs are regenerated to avoid collisions.
    """

    source = Path(input_path).expanduser().resolve()

    if not source.is_file():
        raise FileNotFoundError("Import file not found.")

    if source.stat().st_size > MAX_IMPORT_BYTES:
        raise ValueError("Import file exceeds the size limit.")

    data = json.loads(source.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError("Invalid import format.")

    incoming = data.get("prompts")

    if not isinstance(incoming, list):
        raise ValueError("Import must contain a prompts list.")

    if len(incoming) > MAX_PROMPTS:
        raise ValueError("Too many imported prompts.")

    store = load_store(path)
    existing = store["prompts"] if merge else []

    imported = []

    for item in incoming:

        if not isinstance(item, dict):
            raise ValueError("Invalid prompt entry.")

        title, content, category = _validate_prompt(
            item.get("title", ""),
            item.get("content", ""),
            item.get("category", "general"),
        )

        tags = item.get("tags", [])

        if not isinstance(tags, list):
            raise ValueError("Prompt tags must be a list.")

        imported.append({
            "id": uuid.uuid4().hex,
            "title": title,
            "content": content,
            "category": category,
            "description": str(
                item.get("description", "")
            ).strip()[:1000],
            "tags": [
                str(tag).strip()[:50]
                for tag in tags
                if str(tag).strip()
            ],
            "favorite": bool(item.get("favorite", False)),
            "created_at": _now(),
            "updated_at": _now(),
            "usage_count": 0,
        })

    combined = existing + imported

    if len(combined) > MAX_PROMPTS:
        raise ValueError("Import exceeds prompt library limit.")

    save_store({
        "version": 1,
        "updated_at": _now(),
        "prompts": combined,
    }, path)

    return len(imported)


# ---------------------------------------------------------
# STATISTICS
# ---------------------------------------------------------

def get_statistics(
    path: str | Path | None = None,
) -> dict[str, Any]:

    prompts = list_prompts(path=path)

    categories = {}

    for category in CATEGORIES:
        categories[category] = sum(
            1 for prompt in prompts
            if prompt.get("category") == category
        )

    return {
        "total_prompts": len(prompts),
        "favorites": sum(
            1 for prompt in prompts
            if prompt.get("favorite", False)
        ),
        "total_usage": sum(
            int(prompt.get("usage_count", 0))
            for prompt in prompts
        ),
        "categories": categories,
    }


# ---------------------------------------------------------
# STREAMLIT INTERFACE
# ---------------------------------------------------------

def render(st: Any) -> None:
    """Render the Prompt Manager page."""

    st.title("AI Prompt Manager")

    st.write(
        "Create, organize, reuse, and manage your AI prompts "
        "for every production workflow."
    )

    # Dashboard
    stats = get_statistics()

    col1, col2, col3 = st.columns(3)

    col1.metric("Total prompts", stats["total_prompts"])
    col2.metric("Favorites", stats["favorites"])
    col3.metric("Total usage", stats["total_usage"])

    st.divider()

    tabs = st.tabs([
        "Prompt Library",
        "Create Prompt",
        "Template Builder",
        "Import / Export",
    ])

    # -----------------------------------------------------
    # PROMPT LIBRARY
    # -----------------------------------------------------

    with tabs[0]:

        filter_col, search_col = st.columns([1, 2])

        with filter_col:
            category = st.selectbox(
                "Category",
                ["all"] + CATEGORIES,
                key="prompt_category_filter",
            )

        with search_col:
            search = st.text_input(
                "Search prompts",
                key="prompt_search",
            )

        favorites_only = st.checkbox(
            "Show favorites only"
        )

        prompts = list_prompts(
            category=category,
            search=search,
            favorites_only=favorites_only,
        )

        if not prompts:
            st.info("No prompts found.")
        else:
            options = {
                f"{'★ ' if p.get('favorite') else ''}"
                f"{p['title']} ({p['category']})": p["id"]
                for p in prompts
            }

            selected_label = st.selectbox(
                "Select prompt",
                list(options.keys()),
            )

            selected_id = options[selected_label]
            selected = get_prompt(selected_id)

            if selected:

                st.markdown("### " + selected["title"])

                st.caption(
                    f"Category: {selected['category']} | "
                    f"Used: {selected.get('usage_count', 0)} times"
                )

                st.text_area(
                    "Prompt content",
                    value=selected["content"],
                    height=220,
                    disabled=True,
                    key="selected_prompt_content",
                )

                if selected.get("description"):
                    st.write(selected["description"])

                if selected.get("tags"):
                    st.write(
                        "Tags:",
                        ", ".join(selected["tags"]),
                    )

                col_a, col_b, col_c = st.columns(3)

                with col_a:
                    if st.button(
                        "Copy prompt",
                        use_container_width=True,
                    ):
                        st.code(selected["content"])
                        st.success(
                            "Select and copy the prompt above."
                        )

                with col_b:
                    if st.button(
                        "Toggle favorite",
                        use_container_width=True,
                    ):
                        toggle_favorite(selected_id)
                        st.rerun()

                with col_c:
                    if st.button(
                        "Duplicate",
                        use_container_width=True,
                    ):
                        duplicate_prompt(selected_id)
                        st.success("Prompt duplicated.")
                        st.rerun()

                with st.expander("Edit selected prompt"):

                    edit_title = st.text_input(
                        "Title",
                        value=selected["title"],
                        key="edit_title",
                    )

                    edit_category = st.selectbox(
                        "Category",
                        CATEGORIES,
                        index=CATEGORIES.index(
                            selected["category"]
                        ),
                        key="edit_category",
                    )

                    edit_content = st.text_area(
                        "Content",
                        value=selected["content"],
                        height=200,
                        key="edit_content",
                    )

                    edit_description = st.text_input(
                        "Description",
                        value=selected.get("description", ""),
                        key="edit_description",
                    )

                    if st.button("Save changes"):
                        try:
                            update_prompt(
                                selected_id,
                                title=edit_title,
                                category=edit_category,
                                content=edit_content,
                                description=edit_description,
                            )

                            st.success("Prompt updated.")
                            st.rerun()

                        except ValueError as exc:
                            st.error(str(exc))

                with st.expander("Delete selected prompt"):

                    confirm = st.checkbox(
                        "I confirm that I want to delete this prompt.",
                        key="delete_prompt_confirm",
                    )

                    if st.button(
                        "Delete prompt",
                        disabled=not confirm,
                    ):
                        delete_prompt(selected_id)
                        st.success("Prompt deleted.")
                        st.rerun()

    # -----------------------------------------------------
    # CREATE PROMPT
    # -----------------------------------------------------

    with tabs[1]:

        st.subheader("Create a new prompt")

        with st.form("create_prompt_form"):

            title = st.text_input("Prompt title")

            category = st.selectbox(
                "Prompt category",
                CATEGORIES,
            )

            description = st.text_input(
                "Short description"
            )

            content = st.text_area(
                "Prompt content",
                height=250,
                placeholder=(
                    "Example: Create a cinematic portrait "
                    "of {{character_name}}..."
                ),
            )

            tags_text = st.text_input(
                "Tags",
                placeholder="cinematic, realistic, portrait",
            )

            favorite = st.checkbox("Add to favorites")

            submitted = st.form_submit_button(
                "Save prompt",
                use_container_width=True,
            )

            if submitted:
                try:
                    tags = [
                        tag.strip()
                        for tag in tags_text.split(",")
                        if tag.strip()
                    ]

                    create_prompt(
                        title=title,
                        content=content,
                        category=category,
                        description=description,
                        tags=tags,
                        favorite=favorite,
                    )

                    st.success("Prompt saved successfully.")

                except ValueError as exc:
                    st.error(str(exc))

    # -----------------------------------------------------
    # TEMPLATE BUILDER
    # -----------------------------------------------------

    with tabs[2]:

        st.subheader("Prompt Template Builder")

        templates = list_prompts()

        if not templates:
            st.info("Create a prompt first.")
        else:

            template_options = {
                p["title"]: p
                for p in templates
                if extract_variables(p["content"])
            }

            if not template_options:
                st.info(
                    "No prompts with template variables found. "
                    "Use {{character_name}} or {{scene}} in a prompt."
                )
            else:

                selected_title = st.selectbox(
                    "Choose a template",
                    list(template_options.keys()),
                )

                template = template_options[selected_title]
                variables = extract_variables(
                    template["content"]
                )

                st.write("Required variables:")

                values = {}

                for variable in variables:
                    values[variable] = st.text_input(
                        variable.replace("_", " ").title(),
                        key=f"template_{variable}",
                    )

                if st.button("Generate final prompt"):

                    try:
                        final_prompt = render_template(
                            template["content"],
                            values,
                            strict=True,
                        )

                        record_usage(template["id"])

                        st.markdown("### Generated prompt")
                        st.text_area(
                            "Final result",
                            value=final_prompt,
                            height=250,
                            key="generated_prompt_result",
                        )

                    except ValueError as exc:
                        st.warning(str(exc))

    # -----------------------------------------------------
    # IMPORT / EXPORT
    # -----------------------------------------------------

    with tabs[3]:

        st.subheader("Export prompt library")

        export_name = st.text_input(
            "Export filename",
            value="ai_studio_prompts.json",
        )

        if st.button("Export all prompts"):

            try:
                output = export_prompts(
                    APP_ROOT / "exports" / export_name
                )

                st.success("Export completed.")

                st.download_button(
                    "Download prompt library",
                    data=output.read_bytes(),
                    file_name=output.name,
                    mime="application/json",
                )

            except (ValueError, OSError) as exc:
                st.error(str(exc))

        st.divider()

        st.subheader("Import prompt library")

        uploaded = st.file_uploader(
            "Upload a prompt JSON file",
            type=["json"],
        )

        merge = st.checkbox(
            "Keep existing prompts and merge imported prompts",
            value=True,
        )

        if uploaded is not None:

            if st.button("Import prompts"):

                try:
                    if len(uploaded.getvalue()) > MAX_IMPORT_BYTES:
                        raise ValueError(
                            "Import file exceeds the size limit."
                        )

                    with tempfile.TemporaryDirectory() as temp:
                        temp_path = Path(temp) / "import.json"

                        temp_path.write_bytes(uploaded.getvalue())

                        count = import_prompts(
                            temp_path,
                            merge=merge,
                        )

                    st.success(
                        f"Successfully imported {count} prompts."
                    )

                    st.rerun()

                except (
                    ValueError,
                    OSError,
                    json.JSONDecodeError,
                ) as exc:
                    st.error(str(exc))

    st.divider()

    with st.expander("Prompt category statistics"):
        st.json(stats["categories"])


# ---------------------------------------------------------
# BUILT-IN TESTS
# ---------------------------------------------------------

class PromptManagerTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "prompts.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_sample(self):
        return create_prompt(
            title="Test Image",
            content="Create {{character_name}} in a cinematic scene.",
            category="image",
            tags=["cinematic", "test"],
            path=self.path,
        )

    def test_create_prompt(self):
        prompt = self.create_sample()

        self.assertEqual(prompt["title"], "Test Image")
        self.assertEqual(prompt["category"], "image")

    def test_list_prompts(self):
        self.create_sample()

        results = list_prompts(path=self.path)

        self.assertEqual(len(results), 1)

    def test_get_prompt(self):
        prompt = self.create_sample()

        result = get_prompt(prompt["id"], self.path)

        self.assertIsNotNone(result)

    def test_update_prompt(self):
        prompt = self.create_sample()

        result = update_prompt(
            prompt["id"],
            path=self.path,
            title="Updated Image",
        )

        self.assertEqual(result["title"], "Updated Image")

    def test_delete_prompt(self):
        prompt = self.create_sample()

        result = delete_prompt(prompt["id"], self.path)

        self.assertTrue(result)
        self.assertEqual(len(list_prompts(path=self.path)), 0)

    def test_duplicate_prompt(self):
        prompt = self.create_sample()

        duplicate = duplicate_prompt(prompt["id"], self.path)

        self.assertNotEqual(prompt["id"], duplicate["id"])
        self.assertIn("(Copy)", duplicate["title"])

    def test_favorite_prompt(self):
        prompt = self.create_sample()

        result = toggle_favorite(prompt["id"], self.path)

        self.assertTrue(result["favorite"])

    def test_record_usage(self):
        prompt = self.create_sample()

        result = record_usage(prompt["id"], self.path)

        self.assertEqual(result["usage_count"], 1)

    def test_template_variables(self):
        variables = extract_variables(
            "{{name}} meets {{scene}} and {{name}}"
        )

        self.assertEqual(variables, ["name", "scene"])

    def test_render_template(self):
        result = render_template(
            "Hello {{name}}",
            {"name": "Ajay"},
        )

        self.assertEqual(result, "Hello Ajay")

    def test_missing_template_variable(self):
        with self.assertRaises(ValueError):
            render_template(
                "Hello {{name}}",
                {},
            )

    def test_search_prompts(self):
        self.create_sample()

        results = list_prompts(
            search="cinematic",
            path=self.path,
        )

        self.assertEqual(len(results), 1)

    def test_category_filter(self):
        self.create_sample()

        results = list_prompts(
            category="video",
            path=self.path,
        )

        self.assertEqual(len(results), 0)

    def test_statistics(self):
        self.create_sample()

        stats = get_statistics(self.path)

        self.assertEqual(stats["total_prompts"], 1)
        self.assertEqual(stats["categories"]["image"], 1)

    def test_export_import(self):
        self.create_sample()

        export_path = self.path.parent / "export.json"

        export_prompts(export_path, self.path)

        imported_path = self.path.parent / "imported.json"

        count = import_prompts(
            export_path,
            merge=False,
            path=imported_path,
        )

        self.assertEqual(count, 1)
        self.assertEqual(
            len(list_prompts(path=imported_path)),
            1,
        )

    def test_invalid_category(self):
        with self.assertRaises(ValueError):
            create_prompt(
                "Invalid",
                "Test",
                category="unknown",
                path=self.path,
            )

    def test_empty_title(self):
        with self.assertRaises(ValueError):
            create_prompt(
                "",
                "Test content",
                path=self.path,
            )


def run_tests() -> bool:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        PromptManagerTests
    )

    result = unittest.TextTestRunner(
        verbosity=2
    ).run(suite)

    return result.wasSuccessful()


# ---------------------------------------------------------
# COMMAND LINE
# ---------------------------------------------------------

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="AI Influencer Studio Prompt Manager"
    )

    parser.add_argument(
        "--test",
        action="store_true",
        help="Run built-in tests",
    )

    args = parser.parse_args()

    if args.test:
        success = run_tests()
        raise SystemExit(0 if success else 1)

    print("AI Influencer Studio - Prompt Manager")
    print(f"Storage: {DEFAULT_PROMPT_FILE}")
    print("Run this module through your Streamlit application.")
