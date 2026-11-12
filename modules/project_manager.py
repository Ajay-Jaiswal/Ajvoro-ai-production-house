
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import streamlit as st

try:
    import config
except ImportError:
    config = None


MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parent

ASSETS_DIR = Path(
    getattr(config, "ASSETS_DIR", PROJECT_ROOT / "assets")
).resolve()

PROJECTS_DIR = ASSETS_DIR / "projects"


def ensure_directories():
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)


def safe_project_name(name: str) -> str:
    """Convert a project name into a safe folder name."""
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9_-]+", "_", name)
    name = name.strip("_-")
    return name[:60]


def project_metadata_path(folder: Path) -> Path:
    return folder / "project.json"


def load_project(folder: Path):
    """Load a project only from the approved projects directory."""
    try:
        folder = folder.resolve()
        folder.relative_to(PROJECTS_DIR.resolve())

        metadata = project_metadata_path(folder)

        if not metadata.is_file():
            return None

        data = json.loads(metadata.read_text(encoding="utf-8"))

        if not isinstance(data, dict):
            return None

        data["_folder"] = str(folder)
        return data

    except (OSError, ValueError, json.JSONDecodeError):
        return None


def save_project(folder: Path, data: dict):
    """Save project metadata safely."""
    folder = folder.resolve()
    folder.relative_to(PROJECTS_DIR.resolve())

    metadata = project_metadata_path(folder)

    safe_data = {
        "id": data["id"],
        "name": data["name"],
        "description": data.get("description", ""),
        "project_type": data.get("project_type", "AI Influencer"),
        "status": data.get("status", "Active"),
        "created_at": data["created_at"],
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }

    metadata.write_text(
        json.dumps(safe_data, indent=4),
        encoding="utf-8"
    )


def list_projects():
    """Return valid projects sorted by last update."""
    ensure_directories()
    projects = []

    for folder in PROJECTS_DIR.iterdir():
        if not folder.is_dir():
            continue

        project = load_project(folder)

        if project:
            projects.append(project)

    return sorted(
        projects,
        key=lambda item: item.get("updated_at", ""),
        reverse=True
    )


def create_project(name: str, description: str, project_type: str):
    """Create a new persistent project."""
    ensure_directories()

    clean_name = safe_project_name(name)

    if not clean_name:
        raise ValueError("Enter a valid project name.")

    folder = PROJECTS_DIR / clean_name

    if folder.exists():
        raise ValueError("A project with this name already exists.")

    folder.mkdir(parents=True, exist_ok=False)

    now = datetime.now().isoformat(timespec="seconds")

    data = {
        "id": clean_name,
        "name": name.strip(),
        "description": description.strip(),
        "project_type": project_type,
        "status": "Active",
        "created_at": now,
        "updated_at": now,
    }

    try:
        save_project(folder, data)
    except Exception:
        # Remove only the newly created empty project folder.
        try:
            metadata = project_metadata_path(folder)
            if metadata.exists():
                metadata.unlink()
            folder.rmdir()
        except OSError:
            pass
        raise

    return data


def update_project(project_id: str, name: str,
                   description: str, project_type: str,
                   status: str):
    """Update an existing project's metadata."""
    folder = (PROJECTS_DIR / project_id).resolve()
    folder.relative_to(PROJECTS_DIR.resolve())

    if not folder.is_dir():
        raise FileNotFoundError("Project does not exist.")

    existing = load_project(folder)

    if not existing:
        raise ValueError("Project metadata is invalid.")

    existing["name"] = name.strip()
    existing["description"] = description.strip()
    existing["project_type"] = project_type
    existing["status"] = status

    save_project(folder, existing)


def render_create_project():
    st.subheader("Create New Project")

    with st.form("create_project_form", clear_on_submit=True):
        name = st.text_input(
            "Project name",
            placeholder="My AI Influencer Project"
        )

        description = st.text_area(
            "Project description",
            placeholder="Describe your project..."
        )

        project_type = st.selectbox(
            "Project type",
            [
                "AI Influencer",
                "Talking Avatar",
                "Face Swap",
                "Virtual Outfit",
                "Motion Control",
                "Video Production",
                "Other",
            ]
        )

        submitted = st.form_submit_button(
            "Create Project",
            type="primary"
        )

        if submitted:
            try:
                project = create_project(
                    name,
                    description,
                    project_type
                )

                st.success(
                    f"Project '{project['name']}' created successfully."
                )
                st.rerun()

            except Exception as exc:
                st.error(str(exc))


def render_project_editor(project):
    st.subheader("Edit Project")

    project_id = project["id"]

    with st.form(f"edit_project_{project_id}"):
        name = st.text_input(
            "Project name",
            value=project.get("name", "")
        )

        description = st.text_area(
            "Description",
            value=project.get("description", "")
        )

        types = [
            "AI Influencer",
            "Talking Avatar",
            "Face Swap",
            "Virtual Outfit",
            "Motion Control",
            "Video Production",
            "Other",
        ]

        current_type = project.get("project_type", "AI Influencer")
        type_index = types.index(current_type) if current_type in types else 0

        project_type = st.selectbox(
            "Project type",
            types,
            index=type_index
        )

        status_options = ["Active", "Paused", "Completed"]
        current_status = project.get("status", "Active")
        status_index = (
            status_options.index(current_status)
            if current_status in status_options else 0
        )

        status = st.selectbox(
            "Status",
            status_options,
            index=status_index
        )

        submitted = st.form_submit_button("Save Changes")

        if submitted:
            try:
                update_project(
                    project_id,
                    name,
                    description,
                    project_type,
                    status
                )
                st.success("Project updated.")
                st.rerun()

            except Exception as exc:
                st.error(str(exc))


def render_project_list():
    st.subheader("Your Projects")

    projects = list_projects()

    search = st.text_input(
        "Search projects",
        placeholder="Enter project name..."
    )

    status_filter = st.selectbox(
        "Filter by status",
        ["All", "Active", "Paused", "Completed"]
    )

    filtered = projects

    if search.strip():
        query = search.strip().lower()
        filtered = [
            p for p in filtered
            if query in p.get("name", "").lower()
        ]

    if status_filter != "All":
        filtered = [
            p for p in filtered
            if p.get("status") == status_filter
        ]

    st.metric("Total projects", len(projects))

    if not filtered:
        st.info("No matching projects found.")
        return

    for project in filtered:
        with st.container(border=True):
            st.markdown(f"### {project.get('name', 'Unnamed Project')}")

            st.write(
                project.get("description") or "No description available."
            )

            col1, col2, col3 = st.columns(3)

            with col1:
                st.caption(
                    f"Type: {project.get('project_type', 'Other')}"
                )

            with col2:
                st.caption(
                    f"Status: {project.get('status', 'Active')}"
                )

            with col3:
                st.caption(
                    f"Updated: {project.get('updated_at', 'Unknown')[:10]}"
                )

            if st.button(
                "Open / Edit Project",
                key=f"open_project_{project['id']}"
            ):
                st.session_state["selected_project_id"] = project["id"]
                st.rerun()


def render_selected_project():
    selected_id = st.session_state.get("selected_project_id")

    if not selected_id:
        return

    folder = (PROJECTS_DIR / selected_id).resolve()

    try:
        folder.relative_to(PROJECTS_DIR.resolve())
    except ValueError:
        st.session_state.pop("selected_project_id", None)
        return

    project = load_project(folder)

    if not project:
        st.warning("Selected project could not be loaded.")
        st.session_state.pop("selected_project_id", None)
        return

    st.divider()
    st.subheader("Selected Project")

    render_project_editor(project)

    st.caption(
        "Project folder: " + str(folder)
    )

    if st.button("Close Project"):
        st.session_state.pop("selected_project_id", None)
        st.rerun()


def render(st):
    ensure_directories()

    st.title("Project Manager")
    st.write(
        "Create, organize, search and manage your AI Influencer Studio projects."
    )

    create_tab, projects_tab = st.tabs([
        "Create Project",
        "My Projects"
    ])

    with create_tab:
        render_create_project()

    with projects_tab:
        render_project_list()

    render_selected_project()

    with st.expander("Project storage information"):
        st.write(
            "Projects are stored permanently in assets/projects. "
            "They are not part of the one-hour temporary output cleanup."
        )


if __name__ == "__main__":
    st.set_page_config(
        page_title="AI Influencer Studio - Project Manager",
        layout="wide"
    )
    render(st)
