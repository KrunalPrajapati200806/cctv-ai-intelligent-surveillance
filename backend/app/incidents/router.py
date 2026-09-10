"""
Incident API compatibility module.

Canonical implementation lives in backend.api.routes.incidents.
This module re-exports that router so older imports do not fork schema.
"""

from backend.api.routes.incidents import (
    IncidentStatusUpdate,
    ensure_incident_api_database,
    ensure_incidents_table_sync,
    get_connection,
    router,
)

__all__ = [
    "router",
    "IncidentStatusUpdate",
    "get_connection",
    "ensure_incidents_table_sync",
    "ensure_incident_api_database",
]
