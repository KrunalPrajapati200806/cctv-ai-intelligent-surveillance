"""Canonical incident database location."""

from __future__ import annotations

import os
from pathlib import Path

# backend/app/incidents/paths.py -> project root
PROJECT_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_INCIDENT_DATABASE = PROJECT_ROOT / "data" / "incidents.db"


def incident_database_path() -> Path:
    """
    Return the single SQLite path used by the API and persistence layer.

    Relative INCIDENT_DATABASE values are resolved from the project root so
    API and agents do not create separate files based on process cwd.
    """
    configured = os.getenv("INCIDENT_DATABASE")

    if not configured:
        return DEFAULT_INCIDENT_DATABASE

    path = Path(configured)

    if not path.is_absolute():
        path = PROJECT_ROOT / path

    return path
