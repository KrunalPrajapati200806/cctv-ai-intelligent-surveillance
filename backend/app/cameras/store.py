# """Persistent camera configuration storage."""

# from __future__ import annotations

# import json
# import sqlite3
# from datetime import datetime, timezone
# from pathlib import Path
# from typing import Any

# from backend.app.cameras.policy import CameraPolicy
# from backend.app.incidents.paths import incident_database_path


# CAMERA_TABLE = "cameras"


# def _connect(database_path: Path | None = None) -> sqlite3.Connection:
#     path = database_path or incident_database_path()
#     path.parent.mkdir(parents=True, exist_ok=True)
#     connection = sqlite3.connect(str(path), timeout=30)
#     connection.row_factory = sqlite3.Row
#     connection.execute("PRAGMA busy_timeout=30000")
#     return connection


# def ensure_camera_table(database_path: Path | None = None) -> None:
#     connection = _connect(database_path)
#     try:
#         connection.execute(
#             """
#             CREATE TABLE IF NOT EXISTS cameras (
#                 camera_id TEXT PRIMARY KEY,
#                 name TEXT NOT NULL,
#                 source TEXT NOT NULL,
#                 enabled INTEGER NOT NULL DEFAULT 1,
#                 location TEXT NOT NULL DEFAULT 'default',
#                 policy_json TEXT NOT NULL DEFAULT '{}',
#                 status TEXT NOT NULL DEFAULT 'REGISTERED',
#                 created_at TEXT NOT NULL,
#                 updated_at TEXT NOT NULL
#             )
#             """
#         )
#         connection.commit()
#     finally:
#         connection.close()


# def _policy_to_json(policy: CameraPolicy) -> str:
#     restricted_zone = policy.restricted_zone
#     return json.dumps(
#         {
#             "normal_objects": sorted(policy.normal_objects),
#             "restricted_objects": sorted(policy.restricted_objects),
#             "alert_events": sorted(policy.alert_events),
#             "sensitivity": policy.sensitivity,
#             "security_severity": policy.security_severity,
#             "restricted_zone": (
#                 restricted_zone.to_dict()
#                 if restricted_zone is not None
#                 else None
#             ),
#         }
#     )


# def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
#     return {
#         "camera_id": row["camera_id"],
#         "name": row["name"],
#         "source": row["source"],
#         "enabled": bool(row["enabled"]),
#         "location": row["location"],
#         "policy": json.loads(row["policy_json"] or "{}"),
#         "status": row["status"],
#         "created_at": row["created_at"],
#         "updated_at": row["updated_at"],
#     }


# def list_camera_records(database_path: Path | None = None) -> list[dict[str, Any]]:
#     ensure_camera_table(database_path)
#     connection = _connect(database_path)
#     try:
#         rows = connection.execute(
#             "SELECT * FROM cameras ORDER BY camera_id"
#         ).fetchall()
#         return [_row_to_dict(row) for row in rows]
#     finally:
#         connection.close()


# def get_camera_record(
#     camera_id: str,
#     database_path: Path | None = None,
# ) -> dict[str, Any] | None:
#     ensure_camera_table(database_path)
#     connection = _connect(database_path)
#     try:
#         row = connection.execute(
#             "SELECT * FROM cameras WHERE camera_id = ?",
#             (camera_id,),
#         ).fetchone()
#         return _row_to_dict(row) if row else None
#     finally:
#         connection.close()


# def save_camera_record(
#     camera: Any,
#     *,
#     status: str = "REGISTERED",
#     database_path: Path | None = None,
# ) -> dict[str, Any]:
#     ensure_camera_table(database_path)
#     now = datetime.now(timezone.utc).isoformat()
#     connection = _connect(database_path)
#     try:
#         existing = connection.execute(
#             "SELECT created_at FROM cameras WHERE camera_id = ?",
#             (camera.camera_id,),
#         ).fetchone()
#         created_at = existing["created_at"] if existing else now
#         connection.execute(
#             """
#             INSERT INTO cameras
#                 (camera_id, name, source, enabled, location, policy_json,
#                  status, created_at, updated_at)
#             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
#             ON CONFLICT(camera_id) DO UPDATE SET
#                 name=excluded.name,
#                 source=excluded.source,
#                 enabled=excluded.enabled,
#                 location=excluded.location,
#                 policy_json=excluded.policy_json,
#                 status=excluded.status,
#                 updated_at=excluded.updated_at
#             """,
#             (
#                 camera.camera_id,
#                 camera.name,
#                 camera.source,
#                 int(camera.enabled),
#                 camera.location,
#                 _policy_to_json(camera.policy),
#                 status,
#                 created_at,
#                 now,
#             ),
#         )
#         connection.commit()
#     finally:
#         connection.close()
#     return get_camera_record(camera.camera_id, database_path)  # type: ignore[return-value]


# def delete_camera_record(
#     camera_id: str,
#     database_path: Path | None = None,
# ) -> bool:
#     ensure_camera_table(database_path)
#     connection = _connect(database_path)
#     try:
#         cursor = connection.execute(
#             "DELETE FROM cameras WHERE camera_id = ?",
#             (camera_id,),
#         )
#         connection.commit()
#         return cursor.rowcount > 0
#     finally:
#         connection.close()








"""Persistent camera configuration storage.

This module owns the persistent camera configuration stored in SQLite.

Design goals:
    - Keep camera configuration persistent across process restarts.
    - Be safe for multiple application processes using the same SQLite DB.
    - Keep database access isolated from CameraRegistry.
    - Store camera policy as JSON.
    - Preserve created_at while updating mutable configuration.
    - Provide explicit CRUD operations for future API/supervisor use.
    - Never silently create duplicate camera records.
"""

from __future__ import annotations

import json
import sqlite3

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.cameras.policy import CameraPolicy
from backend.app.incidents.paths import incident_database_path


CAMERA_TABLE = "cameras"

DEFAULT_STATUS = "REGISTERED"
DEFAULT_LOCATION = "default"


def _utc_now() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def _connect(
    database_path: Path | None = None,
) -> sqlite3.Connection:
    """Create a configured SQLite connection.

    A new connection is intentionally created per operation. This keeps
    database connections process-local and avoids sharing SQLite connections
    between workers/threads/processes.

    SQLite connections are configured with:
        - Row objects for named-column access.
        - WAL journal mode for better concurrent read/write behavior.
        - Foreign keys enabled.
        - Busy timeout to tolerate short write contention.
    """

    path = database_path or incident_database_path()

    path = Path(path)
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        str(path),
        timeout=30,
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA busy_timeout = 30000"
    )

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    connection.execute(
        "PRAGMA journal_mode = WAL"
    )

    return connection


def ensure_camera_table(
    database_path: Path | None = None,
) -> None:
    """Create the camera table if it does not already exist."""

    connection = _connect(database_path)

    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS cameras (
                camera_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                source TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                location TEXT NOT NULL DEFAULT 'default',
                policy_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'REGISTERED',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_cameras_enabled
            ON cameras(enabled)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_cameras_status
            ON cameras(status)
            """
        )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def _normalize_camera_id(
    camera_id: str,
) -> str:
    """Normalize and validate a camera ID."""

    if not isinstance(camera_id, str):
        raise ValueError(
            "camera_id must be a string"
        )

    normalized = camera_id.strip()

    if not normalized:
        raise ValueError(
            "camera_id cannot be empty"
        )

    return normalized


def _normalize_status(
    status: str,
) -> str:
    """Normalize a persisted runtime/configuration status."""

    if not isinstance(status, str):
        raise ValueError(
            "status must be a string"
        )

    normalized = status.strip().upper()

    if not normalized:
        return DEFAULT_STATUS

    return normalized


def _normalize_location(
    location: str,
) -> str:
    """Normalize a camera location."""

    if not isinstance(location, str):
        raise ValueError(
            "location must be a string"
        )

    normalized = location.strip()

    return normalized or DEFAULT_LOCATION


def _policy_to_json(
    policy: CameraPolicy,
) -> str:
    """Serialize CameraPolicy into stable JSON."""

    if not isinstance(policy, CameraPolicy):
        raise TypeError(
            "policy must be a CameraPolicy instance"
        )

    restricted_zone = policy.restricted_zone

    payload = {
        "normal_objects": sorted(
            policy.normal_objects
        ),
        "restricted_objects": sorted(
            policy.restricted_objects
        ),
        "alert_events": sorted(
            policy.alert_events
        ),
        "sensitivity": policy.sensitivity,
        "security_severity": policy.security_severity,
        "restricted_zone": (
            restricted_zone.to_dict()
            if restricted_zone is not None
            else None
        ),
    }

    return json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    )


def _policy_from_json(
    value: str | None,
) -> dict[str, Any]:
    """Deserialize policy JSON safely.

    The registry is responsible for converting this dictionary back into
    CameraPolicy because that parsing/validation logic already lives there.
    """

    if not value:
        return {}

    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        # Do not crash the entire application because one persisted policy
        # record contains malformed JSON. Return an empty policy payload and
        # let the registry's validation/default handling take over.
        return {}

    if not isinstance(payload, dict):
        return {}

    return payload


def _row_to_dict(
    row: sqlite3.Row,
) -> dict[str, Any]:
    """Convert a SQLite row into the public camera record format."""

    return {
        "camera_id": row["camera_id"],
        "name": row["name"],
        "source": row["source"],
        "enabled": bool(row["enabled"]),
        "location": row["location"],
        "policy": _policy_from_json(
            row["policy_json"]
        ),
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_camera_records(
    database_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Return all persisted camera records."""

    ensure_camera_table(database_path)

    connection = _connect(database_path)

    try:
        rows = connection.execute(
            """
            SELECT
                camera_id,
                name,
                source,
                enabled,
                location,
                policy_json,
                status,
                created_at,
                updated_at
            FROM cameras
            ORDER BY camera_id
            """
        ).fetchall()

        return [
            _row_to_dict(row)
            for row in rows
        ]

    finally:
        connection.close()


def get_camera_record(
    camera_id: str,
    database_path: Path | None = None,
) -> dict[str, Any] | None:
    """Return one persisted camera record."""

    normalized_id = _normalize_camera_id(
        camera_id
    )

    ensure_camera_table(database_path)

    connection = _connect(database_path)

    try:
        row = connection.execute(
            """
            SELECT
                camera_id,
                name,
                source,
                enabled,
                location,
                policy_json,
                status,
                created_at,
                updated_at
            FROM cameras
            WHERE camera_id = ?
            """,
            (normalized_id,),
        ).fetchone()

        if row is None:
            return None

        return _row_to_dict(row)

    finally:
        connection.close()


def camera_exists(
    camera_id: str,
    database_path: Path | None = None,
) -> bool:
    """Return True if a camera exists."""

    normalized_id = _normalize_camera_id(
        camera_id
    )

    ensure_camera_table(database_path)

    connection = _connect(database_path)

    try:
        row = connection.execute(
            """
            SELECT 1
            FROM cameras
            WHERE camera_id = ?
            LIMIT 1
            """,
            (normalized_id,),
        ).fetchone()

        return row is not None

    finally:
        connection.close()


def save_camera_record(
    camera: Any,
    *,
    status: str = DEFAULT_STATUS,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Create or update a persisted camera configuration.

    The operation is intentionally an UPSERT.

    camera must expose:
        camera_id
        name
        source
        enabled
        location
        policy

    created_at is preserved when updating an existing camera.
    updated_at is refreshed on every save.
    """

    if camera is None:
        raise ValueError(
            "camera cannot be None"
        )

    camera_id = _normalize_camera_id(
        camera.camera_id
    )

    if not isinstance(camera.name, str):
        raise ValueError(
            f"Camera name must be a string: {camera_id}"
        )

    name = camera.name.strip() or camera_id

    if not isinstance(camera.source, str):
        raise ValueError(
            f"Camera source must be a string: {camera_id}"
        )

    source = camera.source.strip()

    if not source:
        raise ValueError(
            f"Camera source cannot be empty: {camera_id}"
        )

    enabled = bool(camera.enabled)

    location = _normalize_location(
        camera.location
    )

    normalized_status = _normalize_status(
        status
    )

    policy_json = _policy_to_json(
        camera.policy
    )

    ensure_camera_table(database_path)

    now = _utc_now()

    connection = _connect(database_path)

    try:
        existing = connection.execute(
            """
            SELECT created_at
            FROM cameras
            WHERE camera_id = ?
            """,
            (camera_id,),
        ).fetchone()

        created_at = (
            existing["created_at"]
            if existing is not None
            else now
        )

        connection.execute(
            """
            INSERT INTO cameras (
                camera_id,
                name,
                source,
                enabled,
                location,
                policy_json,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(camera_id)
            DO UPDATE SET
                name = excluded.name,
                source = excluded.source,
                enabled = excluded.enabled,
                location = excluded.location,
                policy_json = excluded.policy_json,
                status = excluded.status,
                updated_at = excluded.updated_at
            """,
            (
                camera_id,
                name,
                source,
                int(enabled),
                location,
                policy_json,
                normalized_status,
                created_at,
                now,
            ),
        )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    record = get_camera_record(
        camera_id,
        database_path,
    )

    if record is None:
        raise RuntimeError(
            "Camera was saved but could not be "
            f"read back: {camera_id}"
        )

    return record


def update_camera_status(
    camera_id: str,
    status: str,
    database_path: Path | None = None,
) -> dict[str, Any] | None:
    """Update only the persisted camera status.

    This is useful for supervisor/runtime state synchronization without
    rewriting the complete camera configuration.
    """

    normalized_id = _normalize_camera_id(
        camera_id
    )

    normalized_status = _normalize_status(
        status
    )

    ensure_camera_table(database_path)

    now = _utc_now()

    connection = _connect(database_path)

    try:
        cursor = connection.execute(
            """
            UPDATE cameras
            SET
                status = ?,
                updated_at = ?
            WHERE camera_id = ?
            """,
            (
                normalized_status,
                now,
                normalized_id,
            ),
        )

        connection.commit()

        if cursor.rowcount == 0:
            return None

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    return get_camera_record(
        normalized_id,
        database_path,
    )


def delete_camera_record(
    camera_id: str,
    database_path: Path | None = None,
) -> bool:
    """Delete a persisted camera configuration."""

    normalized_id = _normalize_camera_id(
        camera_id
    )

    ensure_camera_table(database_path)

    connection = _connect(database_path)

    try:
        cursor = connection.execute(
            """
            DELETE FROM cameras
            WHERE camera_id = ?
            """,
            (normalized_id,),
        )

        connection.commit()

        return cursor.rowcount > 0

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def clear_camera_records(
    database_path: Path | None = None,
) -> int:
    """Delete all persisted camera configurations.

    Intended for development/test reset operations.

    Returns:
        Number of deleted cameras.
    """

    ensure_camera_table(database_path)

    connection = _connect(database_path)

    try:
        cursor = connection.execute(
            "DELETE FROM cameras"
        )

        connection.commit()

        return cursor.rowcount

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


__all__ = [
    "CAMERA_TABLE",
    "DEFAULT_STATUS",
    "DEFAULT_LOCATION",
    "ensure_camera_table",
    "list_camera_records",
    "get_camera_record",
    "camera_exists",
    "save_camera_record",
    "update_camera_status",
    "delete_camera_record",
    "clear_camera_records",
]
