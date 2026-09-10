from __future__ import annotations

from backend.app.incidents.paths import (
    DEFAULT_INCIDENT_DATABASE,
    PROJECT_ROOT,
    incident_database_path,
)


def test_default_incident_database_is_project_root_data() -> None:
    path = incident_database_path()

    assert path == DEFAULT_INCIDENT_DATABASE
    assert path.parent == PROJECT_ROOT / "data"
    assert path.name == "incidents.db"
