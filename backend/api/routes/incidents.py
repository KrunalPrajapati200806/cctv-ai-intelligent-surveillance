# """
# Incident API routes.

# Responsibilities:
# - List incidents.
# - Retrieve a single incident.
# - Update incident status.
# - Expose evidence/proof-video information linked to an incident.
# - Provide incident summary statistics.

# Design:
# - SQLite operations run in worker threads so the FastAPI event loop is not blocked.
# - WAL mode improves concurrent read/write behavior.
# - busy_timeout reduces transient "database is locked" failures.
# - Evidence is persisted by the incident consumer and exposed here.
# - Existing endpoint shapes are preserved as much as possible for frontend
#   compatibility.
# """

# from __future__ import annotations

# import asyncio
# import json
# import os
# import sqlite3
# from pathlib import Path
# from typing import Any

# from backend.app.incidents.paths import incident_database_path
# from fastapi import APIRouter, HTTPException, Query
# from pydantic import BaseModel, Field


# router = APIRouter(
#     prefix="/api/incidents",
#     tags=["incidents"],
# )


# # ---------------------------------------------------------------------------
# # Configuration
# # ---------------------------------------------------------------------------

# DATABASE_PATH = incident_database_path()


# # ---------------------------------------------------------------------------
# # Models
# # ---------------------------------------------------------------------------


# class IncidentStatusUpdate(BaseModel):
#     status: str = Field(
#         ...,
#         description="New incident status.",
#     )


# # ---------------------------------------------------------------------------
# # Database helpers
# # ---------------------------------------------------------------------------


# def _ensure_parent_directory() -> None:
#     """
#     Ensure the directory containing the SQLite database exists.
#     """
#     parent = DATABASE_PATH.parent

#     if str(parent) not in ("", "."):
#         parent.mkdir(
#             parents=True,
#             exist_ok=True,
#         )


# def get_connection() -> sqlite3.Connection:
#     """
#     Create a hardened SQLite connection.

#     WAL + busy_timeout allow the API and incident consumer to operate
#     concurrently with fewer transient locking failures.
#     """
#     _ensure_parent_directory()

#     connection = sqlite3.connect(
#         str(DATABASE_PATH),
#         timeout=30.0,
#     )

#     connection.row_factory = sqlite3.Row

#     connection.execute(
#         "PRAGMA journal_mode=WAL"
#     )

#     connection.execute(
#         "PRAGMA busy_timeout=30000"
#     )

#     connection.execute(
#         "PRAGMA foreign_keys=ON"
#     )

#     return connection


# def _table_exists(
#     connection: sqlite3.Connection,
#     table_name: str,
# ) -> bool:
#     row = connection.execute(
#         """
#         SELECT 1
#         FROM sqlite_master
#         WHERE type = 'table'
#           AND name = ?
#         LIMIT 1
#         """,
#         (table_name,),
#     ).fetchone()

#     return row is not None


# def _table_columns(
#     connection: sqlite3.Connection,
#     table_name: str,
# ) -> set[str]:
#     rows = connection.execute(
#         f'PRAGMA table_info("{table_name}")'
#     ).fetchall()

#     return {
#         str(row["name"])
#         for row in rows
#     }


# def ensure_incidents_table_sync() -> None:
#     """
#     Ensure the incidents table exists.

#     The incident consumer normally creates/migrates this table first.
#     Keeping this API-side safeguard makes the route robust when the API
#     starts before the consumer.
#     """
#     connection = get_connection()

#     try:
#         connection.execute(
#             """
#             CREATE TABLE IF NOT EXISTS incidents (
#                 incident_id TEXT PRIMARY KEY,
#                 alert_event_id TEXT,
#                 event_id TEXT,
#                 camera_id TEXT,
#                 event_type TEXT,
#                 alert_type TEXT,
#                 severity TEXT,
#                 mode TEXT,
#                 trace_id TEXT,
#                 correlation_id TEXT,
#                 source_agent_id TEXT,
#                 source_instance_id TEXT,
#                 source_redis_id TEXT,
#                 person_count INTEGER,
#                 threshold INTEGER,
#                 frame_id TEXT,
#                 frame_timestamp TEXT,
#                 track_ids TEXT,
#                 message TEXT,
#                 status TEXT NOT NULL DEFAULT 'OPEN',

#                 evidence_status TEXT NOT NULL DEFAULT 'PENDING',
#                 evidence_type TEXT,
#                 evidence_event_id TEXT,
#                 proof_path TEXT,
#                 proof_filename TEXT,
#                 source_video TEXT,
#                 start_time REAL,
#                 end_time REAL,
#                 evidence_duration REAL,
#                 evidence_reason TEXT,
#                 evidence_updated_at TEXT,

#                 created_at TEXT,
#                 updated_at TEXT
#             )
#             """
#         )

#         existing_columns = _table_columns(
#             connection,
#             "incidents",
#         )

#         required_columns: dict[str, str] = {
#             "alert_event_id": "TEXT",
#             "event_id": "TEXT",
#             "camera_id": "TEXT",
#             "event_type": "TEXT",
#             "alert_type": "TEXT",
#             "severity": "TEXT",
#             "mode": "TEXT",
#             "trace_id": "TEXT",
#             "correlation_id": "TEXT",
#             "source_agent_id": "TEXT",
#             "source_instance_id": "TEXT",
#             "source_redis_id": "TEXT",
#             "person_count": "INTEGER",
#             "threshold": "INTEGER",
#             "frame_id": "TEXT",
#             "frame_timestamp": "TEXT",
#             "track_ids": "TEXT",
#             "message": "TEXT",
#             "status": "TEXT DEFAULT 'OPEN'",
#             "evidence_status": "TEXT DEFAULT 'PENDING'",
#             "evidence_type": "TEXT",
#             "evidence_event_id": "TEXT",
#             "proof_path": "TEXT",
#             "proof_filename": "TEXT",
#             "source_video": "TEXT",
#             "start_time": "REAL",
#             "end_time": "REAL",
#             "evidence_duration": "REAL",
#             "evidence_reason": "TEXT",
#             "evidence_updated_at": "TEXT",
#             "created_at": "TEXT",
#             "updated_at": "TEXT",
#         }

#         for column_name, column_type in required_columns.items():
#             if column_name in existing_columns:
#                 continue

#             connection.execute(
#                 f'ALTER TABLE incidents ADD COLUMN "{column_name}" {column_type}'
#             )

#         connection.execute(
#             """
#             UPDATE incidents
#             SET evidence_status = 'PENDING'
#             WHERE evidence_status IS NULL
#             """
#         )

#         connection.execute(
#             """
#             CREATE INDEX IF NOT EXISTS idx_incidents_camera_id
#             ON incidents(camera_id)
#             """
#         )

#         connection.execute(
#             """
#             CREATE INDEX IF NOT EXISTS idx_incidents_status
#             ON incidents(status)
#             """
#         )

#         connection.execute(
#             """
#             CREATE INDEX IF NOT EXISTS idx_incidents_evidence_status
#             ON incidents(evidence_status)
#             """
#         )

#         connection.execute(
#             """
#             CREATE INDEX IF NOT EXISTS idx_incidents_created_at
#             ON incidents(created_at)
#             """
#         )

#         connection.execute(
#             """
#             CREATE INDEX IF NOT EXISTS idx_incidents_correlation_id
#             ON incidents(correlation_id)
#             """
#         )

#         connection.commit()

#     finally:
#         connection.close()


# # ---------------------------------------------------------------------------
# # Serialization helpers
# # ---------------------------------------------------------------------------


# def _json_loads_if_possible(
#     value: Any,
# ) -> Any:
#     """
#     Decode JSON strings when possible.

#     Non-JSON strings are returned unchanged.
#     """
#     if value is None:
#         return None

#     if not isinstance(value, str):
#         return value

#     value = value.strip()

#     if not value:
#         return value

#     try:
#         return json.loads(value)
#     except (json.JSONDecodeError, TypeError):
#         return value


# def _serialize_evidence(
#     row: sqlite3.Row,
# ) -> dict[str, Any]:
#     """
#     Build the nested evidence representation.
#     """
#     return {
#         "status": row["evidence_status"],
#         "type": row["evidence_type"],
#         "event_id": row["evidence_event_id"],
#         "proof_path": row["proof_path"],
#         "proof_filename": row["proof_filename"],
#         "source_video": row["source_video"],
#         "start_time": row["start_time"],
#         "end_time": row["end_time"],
#         "duration": row["evidence_duration"],
#         "reason": row["evidence_reason"],
#         "updated_at": row["evidence_updated_at"],
#     }


# def serialize_incident(
#     row: sqlite3.Row,
# ) -> dict[str, Any]:
#     """
#     Convert a SQLite incident row into the public API representation.
#     """
#     data = dict(row)

#     # Track IDs are stored as JSON by the incident consumer.
#     data["track_ids"] = _json_loads_if_possible(
#         data.get("track_ids")
#     )

#     # Normalize nullable evidence status for older rows/databases.
#     if not data.get("evidence_status"):
#         data["evidence_status"] = "PENDING"

#     # Preserve flat evidence fields for backward compatibility while also
#     # providing a clean nested representation for the frontend.
#     data["evidence"] = _serialize_evidence(row)

#     return data


# # ---------------------------------------------------------------------------
# # Synchronous database operations
# # ---------------------------------------------------------------------------


# def _list_incidents_sync(
#     limit: int,
#     offset: int,
#     status: str | None,
#     camera_id: str | None,
#     severity: str | None,
#     evidence_status: str | None,
# ) -> list[dict[str, Any]]:
#     connection = get_connection()

#     try:
#         where_clauses: list[str] = []
#         parameters: list[Any] = []

#         if status:
#             where_clauses.append("status = ?")
#             parameters.append(status)

#         if camera_id:
#             where_clauses.append("camera_id = ?")
#             parameters.append(camera_id)

#         if severity:
#             where_clauses.append("severity = ?")
#             parameters.append(severity)

#         if evidence_status:
#             where_clauses.append("evidence_status = ?")
#             parameters.append(evidence_status)

#         where_sql = ""

#         if where_clauses:
#             where_sql = (
#                 "WHERE "
#                 + " AND ".join(where_clauses)
#             )

#         rows = connection.execute(
#             f"""
#             SELECT
#                 incident_id,
#                 alert_event_id,
#                 event_id,
#                 camera_id,
#                 event_type,
#                 alert_type,
#                 severity,
#                 mode,
#                 trace_id,
#                 correlation_id,
#                 source_agent_id,
#                 source_instance_id,
#                 source_redis_id,
#                 person_count,
#                 threshold,
#                 frame_id,
#                 frame_timestamp,
#                 track_ids,
#                 message,
#                 status,

#                 evidence_status,
#                 evidence_type,
#                 evidence_event_id,
#                 proof_path,
#                 proof_filename,
#                 source_video,
#                 start_time,
#                 end_time,
#                 evidence_duration,
#                 evidence_reason,
#                 evidence_updated_at,

#                 created_at,
#                 updated_at
#             FROM incidents
#             {where_sql}
#             ORDER BY created_at DESC
#             LIMIT ?
#             OFFSET ?
#             """,
#             (
#                 *parameters,
#                 limit,
#                 offset,
#             ),
#         ).fetchall()

#         return [
#             serialize_incident(row)
#             for row in rows
#         ]

#     finally:
#         connection.close()


# def _get_incident_sync(
#     incident_id: str,
# ) -> dict[str, Any] | None:
#     connection = get_connection()

#     try:
#         row = connection.execute(
#             """
#             SELECT
#                 incident_id,
#                 alert_event_id,
#                 event_id,
#                 camera_id,
#                 event_type,
#                 alert_type,
#                 severity,
#                 mode,
#                 trace_id,
#                 correlation_id,
#                 source_agent_id,
#                 source_instance_id,
#                 source_redis_id,
#                 person_count,
#                 threshold,
#                 frame_id,
#                 frame_timestamp,
#                 track_ids,
#                 message,
#                 status,

#                 evidence_status,
#                 evidence_type,
#                 evidence_event_id,
#                 proof_path,
#                 proof_filename,
#                 source_video,
#                 start_time,
#                 end_time,
#                 evidence_duration,
#                 evidence_reason,
#                 evidence_updated_at,

#                 created_at,
#                 updated_at
#             FROM incidents
#             WHERE incident_id = ?
#             LIMIT 1
#             """,
#             (incident_id,),
#         ).fetchone()

#         if row is None:
#             return None

#         return serialize_incident(row)

#     finally:
#         connection.close()


# def _get_summary_sync() -> dict[str, Any]:
#     connection = get_connection()

#     try:
#         total_row = connection.execute(
#             """
#             SELECT COUNT(*) AS count
#             FROM incidents
#             """
#         ).fetchone()

#         status_rows = connection.execute(
#             """
#             SELECT
#                 status,
#                 COUNT(*) AS count
#             FROM incidents
#             GROUP BY status
#             ORDER BY status
#             """
#         ).fetchall()

#         severity_rows = connection.execute(
#             """
#             SELECT
#                 severity,
#                 COUNT(*) AS count
#             FROM incidents
#             GROUP BY severity
#             ORDER BY severity
#             """
#         ).fetchall()

#         camera_rows = connection.execute(
#             """
#             SELECT
#                 camera_id,
#                 COUNT(*) AS count
#             FROM incidents
#             GROUP BY camera_id
#             ORDER BY camera_id
#             """
#         ).fetchall()

#         evidence_rows = connection.execute(
#             """
#             SELECT
#                 evidence_status,
#                 COUNT(*) AS count
#             FROM incidents
#             GROUP BY evidence_status
#             ORDER BY evidence_status
#             """
#         ).fetchall()

#         return {
#             "total": int(total_row["count"]),
#             "by_status": {
#                 row["status"]: int(row["count"])
#                 for row in status_rows
#                 if row["status"] is not None
#             },
#             "by_severity": {
#                 row["severity"]: int(row["count"])
#                 for row in severity_rows
#                 if row["severity"] is not None
#             },
#             "by_camera": {
#                 row["camera_id"]: int(row["count"])
#                 for row in camera_rows
#                 if row["camera_id"] is not None
#             },
#             "by_evidence_status": {
#                 row["evidence_status"]: int(row["count"])
#                 for row in evidence_rows
#                 if row["evidence_status"] is not None
#             },
#         }

#     finally:
#         connection.close()


# def _update_status_sync(
#     incident_id: str,
#     status: str,
# ) -> dict[str, Any] | None:
#     connection = get_connection()

#     try:
#         cursor = connection.execute(
#             """
#             UPDATE incidents
#             SET
#                 status = ?,
#                 updated_at = CURRENT_TIMESTAMP
#             WHERE incident_id = ?
#             """,
#             (
#                 status,
#                 incident_id,
#             ),
#         )

#         if cursor.rowcount == 0:
#             connection.rollback()
#             return None

#         connection.commit()

#         row = connection.execute(
#             """
#             SELECT
#                 incident_id,
#                 alert_event_id,
#                 event_id,
#                 camera_id,
#                 event_type,
#                 alert_type,
#                 severity,
#                 mode,
#                 trace_id,
#                 correlation_id,
#                 source_agent_id,
#                 source_instance_id,
#                 source_redis_id,
#                 person_count,
#                 threshold,
#                 frame_id,
#                 frame_timestamp,
#                 track_ids,
#                 message,
#                 status,

#                 evidence_status,
#                 evidence_type,
#                 evidence_event_id,
#                 proof_path,
#                 proof_filename,
#                 source_video,
#                 start_time,
#                 end_time,
#                 evidence_duration,
#                 evidence_reason,
#                 evidence_updated_at,

#                 created_at,
#                 updated_at
#             FROM incidents
#             WHERE incident_id = ?
#             LIMIT 1
#             """,
#             (incident_id,),
#         ).fetchone()

#         if row is None:
#             return None

#         return serialize_incident(row)

#     finally:
#         connection.close()


# # ---------------------------------------------------------------------------
# # API endpoints
# # ---------------------------------------------------------------------------


# @router.get("")
# async def list_incidents(
#     limit: int = Query(
#         default=50,
#         ge=1,
#         le=500,
#     ),
#     offset: int = Query(
#         default=0,
#         ge=0,
#     ),
#     status: str | None = Query(
#         default=None,
#     ),
#     camera_id: str | None = Query(
#         default=None,
#     ),
#     severity: str | None = Query(
#         default=None,
#     ),
#     evidence_status: str | None = Query(
#         default=None,
#     ),
# ) -> dict[str, Any]:
#     """
#     List incidents.

#     Optional filters:
#     - status
#     - camera_id
#     - severity
#     - evidence_status
#     """
#     try:
#         incidents = await asyncio.to_thread(
#             _list_incidents_sync,
#             limit,
#             offset,
#             status,
#             camera_id,
#             severity,
#             evidence_status,
#         )

#         return {
#             "incidents": incidents,
#             "count": len(incidents),
#             "limit": limit,
#             "offset": offset,
#         }

#     except sqlite3.Error as exc:
#         raise HTTPException(
#             status_code=503,
#             detail=f"Incident database unavailable: {exc}",
#         ) from exc


# @router.get("/stats/summary")
# async def incident_summary() -> dict[str, Any]:
#     """
#     Return incident statistics.
#     """
#     try:
#         return await asyncio.to_thread(
#             _get_summary_sync,
#         )

#     except sqlite3.Error as exc:
#         raise HTTPException(
#             status_code=503,
#             detail=f"Incident database unavailable: {exc}",
#         ) from exc


# @router.get("/{incident_id}")
# async def get_incident(
#     incident_id: str,
# ) -> dict[str, Any]:
#     """
#     Retrieve a single incident including evidence information.
#     """
#     try:
#         incident = await asyncio.to_thread(
#             _get_incident_sync,
#             incident_id,
#         )

#     except sqlite3.Error as exc:
#         raise HTTPException(
#             status_code=503,
#             detail=f"Incident database unavailable: {exc}",
#         ) from exc

#     if incident is None:
#         raise HTTPException(
#             status_code=404,
#             detail="Incident not found",
#         )

#     return incident


# @router.patch("/{incident_id}/status")
# async def update_incident_status(
#     incident_id: str,
#     payload: IncidentStatusUpdate,
# ) -> dict[str, Any]:
#     """
#     Update an incident status.

#     Allowed statuses:
#     - OPEN
#     - ACKNOWLEDGED
#     - RESOLVED
#     """
#     status = payload.status.strip().upper()

#     allowed_statuses = {
#         "OPEN",
#         "ACKNOWLEDGED",
#         "RESOLVED",
#     }

#     if status not in allowed_statuses:
#         raise HTTPException(
#             status_code=400,
#             detail=(
#                 "Invalid incident status. "
#                 "Allowed values: OPEN, ACKNOWLEDGED, RESOLVED."
#             ),
#         )

#     try:
#         incident = await asyncio.to_thread(
#             _update_status_sync,
#             incident_id,
#             status,
#         )

#     except sqlite3.Error as exc:
#         raise HTTPException(
#             status_code=503,
#             detail=f"Incident database unavailable: {exc}",
#         ) from exc

#     if incident is None:
#         raise HTTPException(
#             status_code=404,
#             detail="Incident not found",
#         )

#     return incident


# # ---------------------------------------------------------------------------
# # Startup safeguard
# # ---------------------------------------------------------------------------


# def ensure_incident_api_database() -> None:
#     """
#     Synchronous startup helper.

#     This can be called by the FastAPI application during startup if desired.
#     It is intentionally separate from route execution.
#     """
#     ensure_incidents_table_sync()


# __all__ = [
#     "router",
#     "IncidentStatusUpdate",
#     "get_connection",
#     "ensure_incidents_table_sync",
#     "ensure_incident_api_database",
# ]


























"""
Incident API routes.

Responsibilities:

- List incidents.
- Retrieve a single incident.
- Update incident status.
- Expose evidence/proof-video information linked to an incident.
- Provide incident summary statistics.

Design:

- SQLite operations run in worker threads so the FastAPI event loop is not blocked.
- WAL mode improves concurrent read/write behavior.
- busy_timeout reduces transient "database is locked" failures.
- Evidence is persisted by the incident consumer and exposed here.
- Existing endpoint shapes are preserved as much as possible for frontend
  compatibility.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any

from backend.app.incidents.paths import incident_database_path
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field


router = APIRouter(
    prefix="/api/incidents",
    tags=["incidents"],
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATABASE_PATH = incident_database_path()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class IncidentStatusUpdate(BaseModel):
    status: str = Field(
        ...,
        description="New incident status.",
    )


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def _ensure_parent_directory() -> None:
    """
    Ensure the directory containing the SQLite database exists.
    """
    parent = DATABASE_PATH.parent

    if str(parent) not in ("", "."):
        parent.mkdir(
            parents=True,
            exist_ok=True,
        )


def get_connection() -> sqlite3.Connection:
    """
    Create a hardened SQLite connection.

    WAL + busy_timeout allow the API and incident consumer to operate
    concurrently with fewer transient locking failures.
    """
    _ensure_parent_directory()

    connection = sqlite3.connect(
        str(DATABASE_PATH),
        timeout=30.0,
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA journal_mode=WAL"
    )

    connection.execute(
        "PRAGMA busy_timeout=30000"
    )

    connection.execute(
        "PRAGMA foreign_keys=ON"
    )

    return connection


def _table_exists(
    connection: sqlite3.Connection,
    table_name: str,
) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        LIMIT 1
        """,
        (table_name,),
    ).fetchone()

    return row is not None


def _table_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> set[str]:
    rows = connection.execute(
        f'PRAGMA table_info("{table_name}")'
    ).fetchall()

    return {
        str(row["name"])
        for row in rows
    }


def ensure_incidents_table_sync() -> None:
    """
    Ensure the incidents table and evidence-related columns exist.

    The incident consumer normally creates/migrates this table first.
    This API-side safeguard keeps the API resilient when it starts before
    the incident consumer.
    """
    connection = get_connection()

    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS incidents (
                incident_id TEXT PRIMARY KEY,
                alert_event_id TEXT,
                event_id TEXT,
                camera_id TEXT,
                event_type TEXT,
                alert_type TEXT,
                severity TEXT,
                mode TEXT,
                trace_id TEXT,
                correlation_id TEXT,
                source_agent_id TEXT,
                source_instance_id TEXT,
                source_redis_id TEXT,
                person_count INTEGER,
                threshold INTEGER,
                frame_id TEXT,
                frame_timestamp TEXT,
                track_ids TEXT,
                message TEXT,
                status TEXT NOT NULL DEFAULT 'OPEN',

                evidence_status TEXT NOT NULL DEFAULT 'PENDING',
                evidence_type TEXT,
                evidence_event_id TEXT,
                proof_path TEXT,
                proof_filename TEXT,
                source_video TEXT,
                start_time REAL,
                end_time REAL,
                evidence_duration REAL,
                evidence_reason TEXT,
                evidence_updated_at TEXT,

                created_at TEXT,
                updated_at TEXT
            )
            """
        )

        existing_columns = _table_columns(
            connection,
            "incidents",
        )

        required_columns: dict[str, str] = {
            "alert_event_id": "TEXT",
            "event_id": "TEXT",
            "camera_id": "TEXT",
            "event_type": "TEXT",
            "alert_type": "TEXT",
            "severity": "TEXT",
            "mode": "TEXT",
            "trace_id": "TEXT",
            "correlation_id": "TEXT",
            "source_agent_id": "TEXT",
            "source_instance_id": "TEXT",
            "source_redis_id": "TEXT",
            "person_count": "INTEGER",
            "threshold": "INTEGER",
            "frame_id": "TEXT",
            "frame_timestamp": "TEXT",
            "track_ids": "TEXT",
            "message": "TEXT",
            "status": "TEXT DEFAULT 'OPEN'",

            "evidence_status": "TEXT DEFAULT 'PENDING'",
            "evidence_type": "TEXT",
            "evidence_event_id": "TEXT",
            "proof_path": "TEXT",
            "proof_filename": "TEXT",
            "source_video": "TEXT",
            "start_time": "REAL",
            "end_time": "REAL",
            "evidence_duration": "REAL",
            "evidence_reason": "TEXT",
            "evidence_updated_at": "TEXT",

            "created_at": "TEXT",
            "updated_at": "TEXT",
        }

        for column_name, column_type in required_columns.items():
            if column_name in existing_columns:
                continue

            connection.execute(
                f'ALTER TABLE incidents ADD COLUMN "{column_name}" {column_type}'
            )

        connection.execute(
            """
            UPDATE incidents
            SET evidence_status = 'PENDING'
            WHERE evidence_status IS NULL
               OR TRIM(evidence_status) = ''
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_incidents_camera_id
            ON incidents(camera_id)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_incidents_status
            ON incidents(status)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_incidents_evidence_status
            ON incidents(evidence_status)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_incidents_created_at
            ON incidents(created_at)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_incidents_correlation_id
            ON incidents(correlation_id)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_incidents_alert_event_id
            ON incidents(alert_event_id)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_incidents_event_id
            ON incidents(event_id)
            """
        )

        connection.commit()

    finally:
        connection.close()


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


_INCIDENT_SELECT = """
    SELECT
        incident_id,
        alert_event_id,
        event_id,
        camera_id,
        event_type,
        alert_type,
        severity,
        mode,
        trace_id,
        correlation_id,
        source_agent_id,
        source_instance_id,
        source_redis_id,
        person_count,
        threshold,
        frame_id,
        frame_timestamp,
        track_ids,
        message,
        status,

        evidence_status,
        evidence_type,
        evidence_event_id,
        proof_path,
        proof_filename,
        source_video,
        start_time,
        end_time,
        evidence_duration,
        evidence_reason,
        evidence_updated_at,

        created_at,
        updated_at

    FROM incidents
"""


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _json_loads_if_possible(
    value: Any,
) -> Any:
    """
    Decode JSON strings when possible.

    Non-JSON strings are returned unchanged.
    """
    if value is None:
        return None

    if not isinstance(value, str):
        return value

    value = value.strip()

    if not value:
        return value

    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


def _serialize_evidence(
    row: sqlite3.Row,
) -> dict[str, Any]:
    """
    Build the nested evidence representation.

    Evidence fields are intentionally exposed using a stable API shape.
    """
    evidence_status = row["evidence_status"]

    if not evidence_status:
        evidence_status = "PENDING"

    return {
        "status": evidence_status,
        "type": row["evidence_type"],
        "event_id": row["evidence_event_id"],
        "proof_path": row["proof_path"],
        "proof_filename": row["proof_filename"],
        "source_video": row["source_video"],
        "start_time": row["start_time"],
        "end_time": row["end_time"],
        "duration": row["evidence_duration"],
        "reason": row["evidence_reason"],
        "updated_at": row["evidence_updated_at"],
    }


def serialize_incident(
    row: sqlite3.Row,
) -> dict[str, Any]:
    """
    Convert a SQLite incident row into the public API representation.
    """
    data = dict(row)

    data["track_ids"] = _json_loads_if_possible(
        data.get("track_ids")
    )

    if not data.get("evidence_status"):
        data["evidence_status"] = "PENDING"

    data["evidence"] = _serialize_evidence(
        row
    )

    return data


# ---------------------------------------------------------------------------
# Synchronous database operations
# ---------------------------------------------------------------------------


def _list_incidents_sync(
    limit: int,
    offset: int,
    status: str | None,
    camera_id: str | None,
    severity: str | None,
    evidence_status: str | None,
) -> list[dict[str, Any]]:
    """
    List incidents with optional filters.
    """
    ensure_incidents_table_sync()

    connection = get_connection()

    try:
        where_clauses: list[str] = []
        parameters: list[Any] = []

        if status:
            where_clauses.append(
                "status = ?"
            )
            parameters.append(status)

        if camera_id:
            where_clauses.append(
                "camera_id = ?"
            )
            parameters.append(camera_id)

        if severity:
            where_clauses.append(
                "severity = ?"
            )
            parameters.append(severity)

        if evidence_status:
            where_clauses.append(
                "evidence_status = ?"
            )
            parameters.append(evidence_status)

        where_sql = ""

        if where_clauses:
            where_sql = (
                "WHERE "
                + " AND ".join(where_clauses)
            )

        rows = connection.execute(
            f"""
            {_INCIDENT_SELECT}
            {where_sql}
            ORDER BY
                CASE
                    WHEN created_at IS NULL THEN 1
                    ELSE 0
                END,
                created_at DESC
            LIMIT ?
            OFFSET ?
            """,
            (
                *parameters,
                limit,
                offset,
            ),
        ).fetchall()

        return [
            serialize_incident(row)
            for row in rows
        ]

    finally:
        connection.close()


def _get_incident_sync(
    incident_id: str,
) -> dict[str, Any] | None:
    """
    Retrieve a single incident.
    """
    ensure_incidents_table_sync()

    connection = get_connection()

    try:
        row = connection.execute(
            f"""
            {_INCIDENT_SELECT}
            WHERE incident_id = ?
            LIMIT 1
            """,
            (incident_id,),
        ).fetchone()

        if row is None:
            return None

        return serialize_incident(
            row
        )

    finally:
        connection.close()


def _get_summary_sync() -> dict[str, Any]:
    """
    Return incident summary statistics.
    """
    ensure_incidents_table_sync()

    connection = get_connection()

    try:
        total_row = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM incidents
            """
        ).fetchone()

        status_rows = connection.execute(
            """
            SELECT
                status,
                COUNT(*) AS count
            FROM incidents
            GROUP BY status
            ORDER BY status
            """
        ).fetchall()

        severity_rows = connection.execute(
            """
            SELECT
                severity,
                COUNT(*) AS count
            FROM incidents
            GROUP BY severity
            ORDER BY severity
            """
        ).fetchall()

        camera_rows = connection.execute(
            """
            SELECT
                camera_id,
                COUNT(*) AS count
            FROM incidents
            GROUP BY camera_id
            ORDER BY camera_id
            """
        ).fetchall()

        evidence_rows = connection.execute(
            """
            SELECT
                evidence_status,
                COUNT(*) AS count
            FROM incidents
            GROUP BY evidence_status
            ORDER BY evidence_status
            """
        ).fetchall()

        return {
            "total": int(
                total_row["count"]
            ),
            "by_status": {
                row["status"]: int(
                    row["count"]
                )
                for row in status_rows
                if row["status"] is not None
            },
            "by_severity": {
                row["severity"]: int(
                    row["count"]
                )
                for row in severity_rows
                if row["severity"] is not None
            },
            "by_camera": {
                row["camera_id"]: int(
                    row["count"]
                )
                for row in camera_rows
                if row["camera_id"] is not None
            },
            "by_evidence_status": {
                row["evidence_status"]: int(
                    row["count"]
                )
                for row in evidence_rows
                if row["evidence_status"] is not None
            },
        }

    finally:
        connection.close()


def _update_status_sync(
    incident_id: str,
    status: str,
) -> dict[str, Any] | None:
    """
    Update incident status and return the updated incident.
    """
    ensure_incidents_table_sync()

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            UPDATE incidents
            SET
                status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE incident_id = ?
            """,
            (
                status,
                incident_id,
            ),
        )

        if cursor.rowcount == 0:
            connection.rollback()
            return None

        connection.commit()

        row = connection.execute(
            f"""
            {_INCIDENT_SELECT}
            WHERE incident_id = ?
            LIMIT 1
            """,
            (incident_id,),
        ).fetchone()

        if row is None:
            return None

        return serialize_incident(
            row
        )

    finally:
        connection.close()


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_incidents(
    limit: int = Query(
        default=50,
        ge=1,
        le=500,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    status: str | None = Query(
        default=None,
    ),
    camera_id: str | None = Query(
        default=None,
    ),
    severity: str | None = Query(
        default=None,
    ),
    evidence_status: str | None = Query(
        default=None,
    ),
) -> dict[str, Any]:
    """
    List incidents.

    Optional filters:

    - status
    - camera_id
    - severity
    - evidence_status
    """
    try:
        incidents = await asyncio.to_thread(
            _list_incidents_sync,
            limit,
            offset,
            status,
            camera_id,
            severity,
            evidence_status,
        )

        return {
            "incidents": incidents,
            "count": len(incidents),
            "limit": limit,
            "offset": offset,
        }

    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Incident database unavailable: {exc}",
        ) from exc


@router.get("/stats/summary")
async def incident_summary() -> dict[str, Any]:
    """
    Return incident statistics.
    """
    try:
        return await asyncio.to_thread(
            _get_summary_sync,
        )

    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Incident database unavailable: {exc}",
        ) from exc


@router.get("/{incident_id}")
async def get_incident(
    incident_id: str,
) -> dict[str, Any]:
    """
    Retrieve a single incident including evidence information.
    """
    try:
        incident = await asyncio.to_thread(
            _get_incident_sync,
            incident_id,
        )

    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Incident database unavailable: {exc}",
        ) from exc

    if incident is None:
        raise HTTPException(
            status_code=404,
            detail="Incident not found",
        )

    return incident


@router.patch("/{incident_id}/status")
async def update_incident_status(
    incident_id: str,
    payload: IncidentStatusUpdate,
) -> dict[str, Any]:
    """
    Update an incident status.

    Allowed statuses:

    - OPEN
    - ACKNOWLEDGED
    - RESOLVED
    """
    status = payload.status.strip().upper()

    allowed_statuses = {
        "OPEN",
        "ACKNOWLEDGED",
        "RESOLVED",
    }

    if status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid incident status. "
                "Allowed values: OPEN, ACKNOWLEDGED, RESOLVED."
            ),
        )

    try:
        incident = await asyncio.to_thread(
            _update_status_sync,
            incident_id,
            status,
        )

    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Incident database unavailable: {exc}",
        ) from exc

    if incident is None:
        raise HTTPException(
            status_code=404,
            detail="Incident not found",
        )

    return incident


# ---------------------------------------------------------------------------
# Startup safeguard
# ---------------------------------------------------------------------------


def ensure_incident_api_database() -> None:
    """
    Synchronous startup helper.

    This can be called by the FastAPI application during startup.
    The route-level database operations also call the schema safeguard,
    so the API remains robust when started independently.
    """
    ensure_incidents_table_sync()


__all__ = [
    "router",
    "IncidentStatusUpdate",
    "get_connection",
    "ensure_incidents_table_sync",
    "ensure_incident_api_database",
]