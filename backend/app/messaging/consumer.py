# # """
# # Reliable Redis Stream consumers and incident persistence.

# # Responsibilities
# # ----------------

# # - Provide canonical incident database persistence helpers.
# # - Create/update incidents in SQLite.
# # - Consume canonical evidence.generated/evidence.failed events.
# # - Link evidence results back to incidents.
# # - Validate canonical events before processing.
# # - ACK Redis evidence messages only after successful processing.
# # - Recover pending evidence messages after restart.
# # - Claim stale evidence messages from failed consumers.
# # - Isolate malformed/failed evidence messages.

# # Non-responsibilities
# # --------------------

# # - Consuming alert.created events.
# # - Alert -> incident orchestration.
# # - Agent supervision.
# # - Camera processing.
# # - Object detection.
# # - Evidence generation.
# # - API-facing Redis stream queries.

# # Alert -> incident orchestration belongs to:

# #     agents.incident.main

# # API-facing Redis event queries belong to:

# #     backend.app.messaging.event_consumer

# # Evidence generation belongs to:

# #     agents.evidence.main
# # """

# # from __future__ import annotations

# # import asyncio
# # import json
# # import os
# # import socket
# # import sqlite3
# # import uuid
# # from datetime import datetime, timezone
# # from pathlib import Path
# # from typing import Any

# # from backend.app.incidents.paths import incident_database_path
# # from backend.app.messaging.redis_client import redis_client
# # from shared.schemas.event_schema import validate_event


# # # ============================================================
# # # DATABASE CONFIGURATION
# # # ============================================================

# # DATABASE_PATH = incident_database_path()


# # # ============================================================
# # # EVIDENCE STREAM CONFIGURATION
# # # ============================================================

# # EVIDENCE_STREAM_NAME = os.getenv(
# #     "INCIDENT_EVIDENCE_INPUT_STREAM",
# #     "events.evidence",
# # ).strip() or "events.evidence"

# # EVIDENCE_GROUP_NAME = os.getenv(
# #     "INCIDENT_EVIDENCE_GROUP",
# #     "incident-evidence-workers",
# # ).strip() or "incident-evidence-workers"

# # EVIDENCE_CONSUMER_NAME = os.getenv(
# #     "INCIDENT_EVIDENCE_CONSUMER_NAME",
# #     f"incident-evidence-{socket.gethostname()}-{uuid.uuid4().hex[:8]}",
# # ).strip() or (
# #     f"incident-evidence-{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
# # )

# # SUPPORTED_EVIDENCE_EVENT_TYPES = {
# #     "evidence.generated",
# #     "evidence.failed",
# # }


# # # ============================================================
# # # DEFAULTS
# # # ============================================================

# # DEFAULT_STATUS = "OPEN"
# # DEFAULT_EVIDENCE_STATUS = "PENDING"

# # PENDING_CLAIM_IDLE_MS = max(
# #     1000,
# #     int(
# #         os.getenv(
# #             "INCIDENT_PENDING_CLAIM_IDLE_MS",
# #             "120000",
# #         )
# #     ),
# # )

# # READ_COUNT = max(
# #     1,
# #     int(
# #         os.getenv(
# #             "INCIDENT_READ_COUNT",
# #             "10",
# #         )
# #     ),
# # )

# # READ_BLOCK_MS = max(
# #     100,
# #     int(
# #         os.getenv(
# #             "INCIDENT_READ_BLOCK_MS",
# #             "5000",
# #         )
# #     ),
# # )

# # RECOVERY_BLOCK_MS = max(
# #     100,
# #     int(
# #         os.getenv(
# #             "INCIDENT_RECOVERY_BLOCK_MS",
# #             "1000",
# #         )
# #     ),
# # )

# # CONSUMER_RESTART_DELAY_SECONDS = max(
# #     0.1,
# #     float(
# #         os.getenv(
# #             "INCIDENT_CONSUMER_RESTART_DELAY_SECONDS",
# #             "2",
# #         )
# #     ),
# # )


# # # ============================================================
# # # DATABASE
# # # ============================================================


# # def get_database_connection() -> sqlite3.Connection:
# #     """
# #     Open a SQLite connection configured for concurrent workers.

# #     WAL allows readers and writers to coexist more effectively.

# #     busy_timeout reduces transient database-lock failures.
# #     """

# #     DATABASE_PATH.parent.mkdir(
# #         parents=True,
# #         exist_ok=True,
# #     )

# #     conn = sqlite3.connect(
# #         str(DATABASE_PATH),
# #         timeout=10,
# #     )

# #     conn.row_factory = sqlite3.Row

# #     conn.execute(
# #         "PRAGMA journal_mode=WAL"
# #     )

# #     conn.execute(
# #         "PRAGMA busy_timeout=10000"
# #     )

# #     conn.execute(
# #         "PRAGMA foreign_keys=ON"
# #     )

# #     return conn


# # def ensure_incidents_table() -> None:
# #     """
# #     Create or migrate the canonical incidents table.

# #     This function is synchronous intentionally.

# #     Async callers should use:

# #         await asyncio.to_thread(
# #             ensure_incidents_table
# #         )
# #     """

# #     conn = get_database_connection()

# #     try:
# #         conn.execute(
# #             """
# #             CREATE TABLE IF NOT EXISTS incidents (
# #                 incident_id TEXT PRIMARY KEY,
# #                 alert_event_id TEXT UNIQUE NOT NULL,
# #                 event_id TEXT,
# #                 camera_id TEXT,
# #                 event_type TEXT NOT NULL,
# #                 alert_type TEXT NOT NULL,
# #                 severity TEXT NOT NULL,
# #                 mode TEXT,
# #                 trace_id TEXT,
# #                 correlation_id TEXT,
# #                 source_agent_id TEXT,
# #                 source_instance_id TEXT,
# #                 source_hostname TEXT,
# #                 source_redis_id TEXT,
# #                 person_count INTEGER,
# #                 threshold REAL,
# #                 frame_id INTEGER,
# #                 frame_timestamp REAL,
# #                 track_ids TEXT,
# #                 message TEXT,
# #                 status TEXT NOT NULL DEFAULT 'OPEN',
# #                 evidence_status TEXT NOT NULL DEFAULT 'PENDING',
# #                 evidence_type TEXT,
# #                 evidence_event_id TEXT,
# #                 proof_path TEXT,
# #                 proof_filename TEXT,
# #                 source_video TEXT,
# #                 video_id TEXT,
# #                 start_time TEXT,
# #                 end_time TEXT,
# #                 evidence_duration REAL,
# #                 evidence_reason TEXT,
# #                 evidence_updated_at TEXT,
# #                 created_at TEXT NOT NULL,
# #                 updated_at TEXT NOT NULL
# #             )
# #             """
# #         )

# #         columns = {
# #             row["name"]
# #             for row in conn.execute(
# #                 "PRAGMA table_info(incidents)"
# #             ).fetchall()
# #         }

# #         # --------------------------------------------------------
# #         # Safe additive migrations.
# #         # --------------------------------------------------------

# #         migrations: dict[str, str] = {
# #             "event_id": "TEXT",
# #             "camera_id": "TEXT",
# #             "event_type": "TEXT",
# #             "mode": "TEXT",
# #             "trace_id": "TEXT",
# #             "correlation_id": "TEXT",
# #             "source_agent_id": "TEXT",
# #             "source_instance_id": "TEXT",
# #             "source_hostname": "TEXT",
# #             "source_redis_id": "TEXT",
# #             "person_count": "INTEGER",
# #             "threshold": "REAL",
# #             "frame_id": "INTEGER",
# #             "frame_timestamp": "REAL",
# #             "track_ids": "TEXT",
# #             "message": "TEXT",
# #             "source_video": "TEXT",
# #             "video_id": "TEXT",
# #             "start_time": "TEXT",
# #             "end_time": "TEXT",
# #             "evidence_status": "TEXT",
# #             "evidence_type": "TEXT",
# #             "evidence_event_id": "TEXT",
# #             "proof_path": "TEXT",
# #             "proof_filename": "TEXT",
# #             "evidence_duration": "REAL",
# #             "evidence_reason": "TEXT",
# #             "evidence_updated_at": "TEXT",
# #             "created_at": "TEXT",
# #             "updated_at": "TEXT",
# #         }

# #         for column, definition in migrations.items():
# #             if column not in columns:
# #                 conn.execute(
# #                     f"""
# #                     ALTER TABLE incidents
# #                     ADD COLUMN {column} {definition}
# #                     """
# #                 )

# #         # --------------------------------------------------------
# #         # Backfill timestamps.
# #         # --------------------------------------------------------

# #         now = datetime.now(
# #             timezone.utc
# #         ).isoformat()

# #         conn.execute(
# #             """
# #             UPDATE incidents
# #             SET created_at = COALESCE(
# #                 created_at,
# #                 ?
# #             )
# #             WHERE created_at IS NULL
# #             """,
# #             (now,),
# #         )

# #         conn.execute(
# #             """
# #             UPDATE incidents
# #             SET updated_at = COALESCE(
# #                 updated_at,
# #                 created_at,
# #                 ?
# #             )
# #             WHERE updated_at IS NULL
# #             """,
# #             (now,),
# #         )

# #         conn.execute(
# #             """
# #             UPDATE incidents
# #             SET event_type = COALESCE(
# #                 event_type,
# #                 'alert.created'
# #             )
# #             WHERE event_type IS NULL
# #             """
# #         )

# #         conn.execute(
# #             """
# #             UPDATE incidents
# #             SET evidence_status = COALESCE(
# #                 evidence_status,
# #                 ?
# #             )
# #             WHERE evidence_status IS NULL
# #             """,
# #             (DEFAULT_EVIDENCE_STATUS,),
# #         )

# #         # --------------------------------------------------------
# #         # Indexes.
# #         # --------------------------------------------------------

# #         conn.execute(
# #             """
# #             CREATE UNIQUE INDEX IF NOT EXISTS
# #             idx_incidents_alert_event_id
# #             ON incidents(alert_event_id)
# #             """
# #         )

# #         conn.execute(
# #             """
# #             CREATE INDEX IF NOT EXISTS
# #             idx_incidents_event_id
# #             ON incidents(event_id)
# #             """
# #         )

# #         conn.execute(
# #             """
# #             CREATE INDEX IF NOT EXISTS
# #             idx_incidents_camera_id
# #             ON incidents(camera_id)
# #             """
# #         )

# #         conn.execute(
# #             """
# #             CREATE INDEX IF NOT EXISTS
# #             idx_incidents_status
# #             ON incidents(status)
# #             """
# #         )

# #         conn.execute(
# #             """
# #             CREATE INDEX IF NOT EXISTS
# #             idx_incidents_severity
# #             ON incidents(severity)
# #             """
# #         )

# #         conn.execute(
# #             """
# #             CREATE INDEX IF NOT EXISTS
# #             idx_incidents_evidence_status
# #             ON incidents(evidence_status)
# #             """
# #         )

# #         conn.execute(
# #             """
# #             CREATE INDEX IF NOT EXISTS
# #             idx_incidents_start_time
# #             ON incidents(start_time)
# #             """
# #         )

# #         conn.execute(
# #             """
# #             CREATE INDEX IF NOT EXISTS
# #             idx_incidents_trace_id
# #             ON incidents(trace_id)
# #             """
# #         )

# #         conn.execute(
# #             """
# #             CREATE INDEX IF NOT EXISTS
# #             idx_incidents_correlation_id
# #             ON incidents(correlation_id)
# #             """
# #         )

# #         conn.execute(
# #             """
# #             CREATE UNIQUE INDEX IF NOT EXISTS
# #             idx_incidents_evidence_event_id
# #             ON incidents(evidence_event_id)
# #             WHERE evidence_event_id IS NOT NULL
# #             """
# #         )

# #         conn.commit()

# #     finally:
# #         conn.close()


# # # ============================================================
# # # TIMESTAMP HELPERS
# # # ============================================================


# # def parse_timestamp(
# #     value: Any,
# # ) -> str | None:
# #     """
# #     Parse an ISO timestamp and normalize it to UTC.

# #     Numeric values are intentionally not interpreted as
# #     wall-clock timestamps.
# #     """

# #     if value is None:
# #         return None

# #     if isinstance(value, datetime):
# #         dt = value

# #     elif isinstance(value, str):
# #         value = value.strip()

# #         if not value:
# #             return None

# #         try:
# #             normalized = value

# #             if normalized.endswith("Z"):
# #                 normalized = (
# #                     normalized[:-1]
# #                     + "+00:00"
# #                 )

# #             dt = datetime.fromisoformat(
# #                 normalized
# #             )

# #         except ValueError:
# #             return None

# #     else:
# #         return None

# #     if dt.tzinfo is None:
# #         dt = dt.replace(
# #             tzinfo=timezone.utc
# #         )

# #     dt = dt.astimezone(
# #         timezone.utc
# #     )

# #     return dt.isoformat()


# # def get_event_time(
# #     event: dict[str, Any],
# # ) -> str:
# #     """
# #     Determine wall-clock event time.

# #     Priority:

# #         data.event_timestamp
# #         data.frame_datetime
# #         event.timestamp
# #         current UTC time

# #     Numeric frame_timestamp/event_time values are treated
# #     as video-relative values and are not converted to
# #     wall-clock timestamps.
# #     """

# #     data = event.get(
# #         "data",
# #         {},
# #     )

# #     if isinstance(data, dict):
# #         for key in (
# #             "event_timestamp",
# #             "frame_datetime",
# #         ):
# #             parsed = parse_timestamp(
# #                 data.get(key)
# #             )

# #             if parsed:
# #                 return parsed

# #     parsed = parse_timestamp(
# #         event.get("timestamp")
# #     )

# #     if parsed:
# #         return parsed

# #     return datetime.now(
# #         timezone.utc
# #     ).isoformat()


# # # ============================================================
# # # TYPE HELPERS
# # # ============================================================


# # def safe_int(
# #     value: Any,
# # ) -> int | None:

# #     if value is None:
# #         return None

# #     try:
# #         return int(value)

# #     except (
# #         TypeError,
# #         ValueError,
# #     ):
# #         return None


# # def safe_float(
# #     value: Any,
# # ) -> float | None:

# #     if value is None:
# #         return None

# #     try:
# #         return float(value)

# #     except (
# #         TypeError,
# #         ValueError,
# #     ):
# #         return None


# # def normalize_track_ids(
# #     value: Any,
# # ) -> list[str]:

# #     if value is None:
# #         return []

# #     if isinstance(
# #         value,
# #         (
# #             list,
# #             tuple,
# #             set,
# #         ),
# #     ):
# #         return [
# #             str(item)
# #             for item in value
# #             if item is not None
# #         ]

# #     return [str(value)]


# # # ============================================================
# # # INCIDENT CREATION
# # # ============================================================


# # def create_incident_sync(
# #     event: dict[str, Any],
# # ) -> dict[str, Any]:
# #     """
# #     Create an incident from a canonical alert.created event.

# #     This function is called by:

# #         agents.incident.main

# #     It is NOT called by the Redis consumer service.

# #     Idempotency is based on alert_event_id.
# #     """

# #     if not isinstance(event, dict):
# #         raise ValueError(
# #             "Event must be a dictionary"
# #         )

# #     validated_event = validate_event(
# #         event
# #     )

# #     if hasattr(
# #         validated_event,
# #         "to_dict",
# #     ):
# #         event = validated_event.to_dict()

# #     elif hasattr(
# #         validated_event,
# #         "model_dump",
# #     ):
# #         event = validated_event.model_dump(
# #             mode="json"
# #         )

# #     elif isinstance(
# #         validated_event,
# #         dict,
# #     ):
# #         event = validated_event

# #     else:
# #         raise ValueError(
# #             "Validated event has unsupported type"
# #         )

# #     event_type = event.get(
# #         "event_type"
# #     )

# #     if event_type != "alert.created":
# #         raise ValueError(
# #             f"Unsupported event type: {event_type}"
# #         )

# #     event_id = event.get(
# #         "event_id"
# #     )

# #     if not event_id:
# #         raise ValueError(
# #             "Alert event is missing event_id"
# #         )

# #     camera = event.get(
# #         "camera",
# #         {},
# #     )

# #     if not isinstance(
# #         camera,
# #         dict,
# #     ):
# #         camera = {}

# #     context = event.get(
# #         "context",
# #         {},
# #     )

# #     if not isinstance(
# #         context,
# #         dict,
# #     ):
# #         context = {}

# #     data = event.get(
# #         "data",
# #         {},
# #     )

# #     if not isinstance(
# #         data,
# #         dict,
# #     ):
# #         raise ValueError(
# #             "Alert event data must be an object"
# #         )

# #     source = event.get(
# #         "source",
# #         {},
# #     )

# #     if not isinstance(
# #         source,
# #         dict,
# #     ):
# #         source = {}

# #     incident_id = (
# #         context.get("incident_id")
# #         or str(uuid.uuid4())
# #     )

# #     camera_id = camera.get(
# #         "camera_id"
# #     )

# #     alert_type = str(
# #         data.get(
# #             "alert_type",
# #             "unknown",
# #         )
# #     )

# #     severity = str(
# #         data.get(
# #             "severity",
# #             "medium",
# #         )
# #     )

# #     mode = context.get(
# #         "mode"
# #     )

# #     trace_id = context.get(
# #         "trace_id"
# #     )

# #     correlation_id = context.get(
# #         "correlation_id"
# #     )

# #     source_agent_id = source.get(
# #         "agent_id"
# #     )

# #     source_instance_id = source.get(
# #         "instance_id"
# #     )

# #     source_hostname = source.get(
# #         "hostname"
# #     )

# #     person_count = safe_int(
# #         data.get(
# #             "person_count"
# #         )
# #     )

# #     threshold = safe_float(
# #         data.get(
# #             "threshold"
# #         )
# #     )

# #     frame_id = safe_int(
# #         data.get(
# #             "frame_id"
# #         )
# #     )

# #     frame_timestamp = safe_float(
# #         data.get(
# #             "frame_timestamp"
# #         )
# #     )

# #     if frame_timestamp is None:
# #         frame_timestamp = safe_float(
# #             data.get(
# #                 "event_time"
# #             )
# #         )

# #     track_ids = normalize_track_ids(
# #         data.get(
# #             "track_ids"
# #         )
# #     )

# #     message = data.get(
# #         "message"
# #     )

# #     source_video = data.get(
# #         "source_video"
# #     )

# #     video_id = data.get(
# #         "video_id"
# #     )

# #     event_time = get_event_time(
# #         event
# #     )

# #     now = datetime.now(
# #         timezone.utc
# #     ).isoformat()

# #     conn = get_database_connection()

# #     try:

# #         # --------------------------------------------------------
# #         # Idempotency lookup.
# #         # --------------------------------------------------------

# #         existing = conn.execute(
# #             """
# #             SELECT
# #                 incident_id,
# #                 alert_event_id,
# #                 event_id,
# #                 alert_type,
# #                 severity,
# #                 camera_id,
# #                 status,
# #                 evidence_status,
# #                 proof_path,
# #                 evidence_event_id,
# #                 source_video,
# #                 video_id,
# #                 start_time,
# #                 end_time,
# #                 evidence_duration,
# #                 evidence_reason,
# #                 evidence_updated_at,
# #                 created_at,
# #                 updated_at
# #             FROM incidents
# #             WHERE alert_event_id = ?
# #             """,
# #             (event_id,),
# #         ).fetchone()

# #         if existing:

# #             existing_incident_id = existing[
# #                 "incident_id"
# #             ]

# #             conn.execute(
# #                 """
# #                 UPDATE incidents
# #                 SET
# #                     source_video = COALESCE(
# #                         source_video,
# #                         ?
# #                     ),
# #                     video_id = COALESCE(
# #                         video_id,
# #                         ?
# #                     ),
# #                     updated_at = ?
# #                 WHERE incident_id = ?
# #                 """,
# #                 (
# #                     source_video,
# #                     video_id,
# #                     now,
# #                     existing_incident_id,
# #                 ),
# #             )

# #             conn.commit()

# #             return {
# #                 "action": "UPDATED",
# #                 "incident_id": existing_incident_id,
# #                 "alert_event_id": event_id,
# #                 "camera_id": existing[
# #                     "camera_id"
# #                 ],
# #                 "alert_type": existing[
# #                     "alert_type"
# #                 ],
# #                 "severity": existing[
# #                     "severity"
# #                 ],
# #                 "person_count": person_count,
# #                 "evidence_status": existing[
# #                     "evidence_status"
# #                 ],
# #             }

# #         # --------------------------------------------------------
# #         # Insert.
# #         # --------------------------------------------------------

# #         try:

# #             conn.execute(
# #                 """
# #                 INSERT INTO incidents (
# #                     incident_id,
# #                     alert_event_id,
# #                     event_id,
# #                     camera_id,
# #                     event_type,
# #                     alert_type,
# #                     severity,
# #                     mode,
# #                     trace_id,
# #                     correlation_id,
# #                     source_agent_id,
# #                     source_instance_id,
# #                     source_hostname,
# #                     person_count,
# #                     threshold,
# #                     frame_id,
# #                     frame_timestamp,
# #                     track_ids,
# #                     message,
# #                     status,
# #                     evidence_status,
# #                     source_video,
# #                     video_id,
# #                     start_time,
# #                     end_time,
# #                     created_at,
# #                     updated_at
# #                 )
# #                 VALUES (
# #                     ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
# #                     ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
# #                     ?, ?, ?, ?, ?, ?, ?
# #                 )
# #                 """,
# #                 (
# #                     incident_id,
# #                     event_id,
# #                     event_id,
# #                     camera_id,
# #                     event_type,
# #                     alert_type,
# #                     severity,
# #                     mode,
# #                     trace_id,
# #                     correlation_id,
# #                     source_agent_id,
# #                     source_instance_id,
# #                     source_hostname,
# #                     person_count,
# #                     threshold,
# #                     frame_id,
# #                     frame_timestamp,
# #                     json.dumps(track_ids),
# #                     message,
# #                     DEFAULT_STATUS,
# #                     DEFAULT_EVIDENCE_STATUS,
# #                     source_video,
# #                     video_id,
# #                     event_time,
# #                     event_time,
# #                     now,
# #                     now,
# #                 ),
# #             )

# #             conn.commit()

# #         except sqlite3.IntegrityError:

# #             conn.rollback()

# #             existing = conn.execute(
# #                 """
# #                 SELECT
# #                     incident_id,
# #                     alert_event_id,
# #                     alert_type,
# #                     severity,
# #                     camera_id,
# #                     status,
# #                     evidence_status
# #                 FROM incidents
# #                 WHERE alert_event_id = ?
# #                 """,
# #                 (event_id,),
# #             ).fetchone()

# #             if not existing:
# #                 raise

# #             return {
# #                 "action": "UPDATED",
# #                 "incident_id": existing[
# #                     "incident_id"
# #                 ],
# #                 "alert_event_id": event_id,
# #                 "camera_id": existing[
# #                     "camera_id"
# #                 ],
# #                 "alert_type": existing[
# #                     "alert_type"
# #                 ],
# #                 "severity": existing[
# #                     "severity"
# #                 ],
# #                 "person_count": person_count,
# #                 "evidence_status": existing[
# #                     "evidence_status"
# #                 ],
# #             }

# #         return {
# #             "action": "CREATED",
# #             "incident_id": incident_id,
# #             "alert_event_id": event_id,
# #             "camera_id": camera_id,
# #             "alert_type": alert_type,
# #             "severity": severity,
# #             "person_count": person_count,
# #             "evidence_status": DEFAULT_EVIDENCE_STATUS,
# #         }

# #     finally:
# #         conn.close()


# # # ============================================================
# # # EVIDENCE UPDATE
# # # ============================================================



# # def update_evidence_sync(
# #     event: dict[str, Any],
# # ) -> dict[str, Any]:
# #     """
# #     Apply an evidence.generated/evidence.failed event.

# #     The incident_id is taken from:
# #         event.context.incident_id

# #     Persists the complete evidence metadata:
# #         - evidence_status
# #         - evidence_type
# #         - evidence_event_id
# #         - proof_path
# #         - proof_filename
# #         - source_video
# #         - start_time
# #         - end_time
# #         - evidence_duration
# #         - evidence_reason
# #         - evidence_updated_at

# #     A completed evidence result cannot later be downgraded
# #     by a stale failure event.
# #     """

# #     if not isinstance(event, dict):
# #         raise ValueError(
# #             "Evidence event must be a dictionary"
# #         )

# #     validated_event = validate_event(event)

# #     if hasattr(validated_event, "to_dict"):
# #         event = validated_event.to_dict()
# #     elif hasattr(validated_event, "model_dump"):
# #         event = validated_event.model_dump(
# #             mode="json"
# #         )
# #     elif isinstance(validated_event, dict):
# #         event = validated_event
# #     else:
# #         raise ValueError(
# #             "Validated event has unsupported type"
# #         )

# #     event_type = event.get("event_type")

# #     if event_type not in SUPPORTED_EVIDENCE_EVENT_TYPES:
# #         raise ValueError(
# #             f"Unsupported evidence event type: {event_type}"
# #         )

# #     context = event.get("context", {})

# #     if not isinstance(context, dict):
# #         context = {}

# #     incident_id = context.get("incident_id")

# #     if not incident_id:
# #         raise ValueError(
# #             "Evidence event is missing "
# #             "context.incident_id"
# #         )

# #     data = event.get("data", {})

# #     if not isinstance(data, dict):
# #         raise ValueError(
# #             "Evidence event data must be an object"
# #         )

# #     evidence_event_id = event.get("event_id")

# #     if not evidence_event_id:
# #         raise ValueError(
# #             "Evidence event is missing event_id"
# #         )

# #     # --------------------------------------------------------
# #     # Determine final evidence status.
# #     # --------------------------------------------------------

# #     raw_status = str(
# #         data.get("status", "")
# #     ).strip().upper()

# #     if event_type == "evidence.generated":
# #         status = (
# #             "FAILED"
# #             if raw_status in {
# #                 "FAILED",
# #                 "ERROR",
# #             }
# #             else "COMPLETED"
# #         )
# #     else:
# #         status = "FAILED"

# #     # --------------------------------------------------------
# #     # Evidence metadata.
# #     # --------------------------------------------------------

# #     evidence_type = data.get(
# #         "evidence_type"
# #     )

# #     proof_path = data.get(
# #         "proof_path"
# #     )

# #     proof_filename = data.get(
# #         "proof_filename"
# #     )

# #     source_video = data.get(
# #         "source_video"
# #     )

# #     # Evidence generator may emit either:
# #     #
# #     #   duration
# #     #
# #     # or:
# #     #
# #     #   evidence_duration
# #     #
# #     # Support both.

# #     evidence_duration = safe_float(
# #         data.get(
# #             "evidence_duration"
# #         )
# #     )

# #     if evidence_duration is None:
# #         evidence_duration = safe_float(
# #             data.get(
# #                 "duration"
# #             )
# #         )

# #     # --------------------------------------------------------
# #     # Evidence start/end time.
# #     #
# #     # These are allowed to be either:
# #     #   - ISO timestamps
# #     #   - numeric video-relative values
# #     #
# #     # Store them as TEXT because the DB schema defines
# #     # start_time/end_time as TEXT.
# #     # --------------------------------------------------------

# #     start_time = data.get(
# #         "start_time"
# #     )

# #     end_time = data.get(
# #         "end_time"
# #     )

# #     if start_time is not None:
# #         start_time = str(start_time)

# #     if end_time is not None:
# #         end_time = str(end_time)

# #     # --------------------------------------------------------
# #     # Evidence failure reason.
# #     # --------------------------------------------------------

# #     evidence_reason = data.get(
# #         "reason"
# #     )

# #     if evidence_reason is None:
# #         evidence_reason = data.get(
# #             "error"
# #         )

# #     if evidence_reason is not None:
# #         evidence_reason = str(
# #             evidence_reason
# #         )

# #     now = datetime.now(
# #         timezone.utc
# #     ).isoformat()

# #     conn = get_database_connection()

# #     try:
# #         # ----------------------------------------------------
# #         # Explicit transaction.
# #         # ----------------------------------------------------

# #         conn.execute(
# #             "BEGIN IMMEDIATE"
# #         )

# #         incident = conn.execute(
# #             """
# #             SELECT
# #                 incident_id,
# #                 evidence_status,
# #                 evidence_event_id,
# #                 evidence_type,
# #                 proof_path,
# #                 proof_filename,
# #                 source_video,
# #                 start_time,
# #                 end_time,
# #                 evidence_duration,
# #                 evidence_reason,
# #                 evidence_updated_at
# #             FROM incidents
# #             WHERE incident_id = ?
# #             """,
# #             (incident_id,),
# #         ).fetchone()

# #         if not incident:
# #             conn.rollback()
# #             raise ValueError(
# #                 f"Incident not found: {incident_id}"
# #             )

# #         current_status = str(
# #             incident["evidence_status"]
# #             or DEFAULT_EVIDENCE_STATUS
# #         ).upper()

# #         # ----------------------------------------------------
# #         # Same evidence event already applied.
# #         # ----------------------------------------------------

# #         if (
# #             incident["evidence_event_id"]
# #             == evidence_event_id
# #         ):
# #             conn.commit()

# #             return {
# #                 "action": "DUPLICATE",
# #                 "incident_id": incident_id,
# #                 "evidence_event_id": evidence_event_id,
# #                 "evidence_status": current_status,
# #             }

# #         # ----------------------------------------------------
# #         # Never downgrade completed evidence.
# #         # ----------------------------------------------------

# #         if (
# #             current_status == "COMPLETED"
# #             and status == "FAILED"
# #         ):
# #             conn.execute(
# #                 """
# #                 UPDATE incidents
# #                 SET updated_at = ?
# #                 WHERE incident_id = ?
# #                 """,
# #                 (
# #                     now,
# #                     incident_id,
# #                 ),
# #             )

# #             conn.commit()

# #             return {
# #                 "action": "IGNORED_DOWNGRADE",
# #                 "incident_id": incident_id,
# #                 "evidence_event_id": evidence_event_id,
# #                 "evidence_status": current_status,
# #             }

# #         # ----------------------------------------------------
# #         # Apply complete evidence result.
# #         #
# #         # COALESCE preserves useful existing values if an
# #         # incoming event omits optional metadata.
# #         # ----------------------------------------------------

# #         conn.execute(
# #             """
# #             UPDATE incidents
# #             SET
# #                 evidence_status = ?,

# #                 evidence_type = COALESCE(
# #                     ?,
# #                     evidence_type
# #                 ),

# #                 evidence_event_id = ?,

# #                 proof_path = COALESCE(
# #                     ?,
# #                     proof_path
# #                 ),

# #                 proof_filename = COALESCE(
# #                     ?,
# #                     proof_filename
# #                 ),

# #                 source_video = COALESCE(
# #                     ?,
# #                     source_video
# #                 ),

# #                 start_time = COALESCE(
# #                     ?,
# #                     start_time
# #                 ),

# #                 end_time = COALESCE(
# #                     ?,
# #                     end_time
# #                 ),

# #                 evidence_duration = COALESCE(
# #                     ?,
# #                     evidence_duration
# #                 ),

# #                 evidence_reason = ?,

# #                 evidence_updated_at = ?,

# #                 updated_at = ?

# #             WHERE incident_id = ?
# #             """,
# #             (
# #                 status,
# #                 evidence_type,
# #                 evidence_event_id,
# #                 proof_path,
# #                 proof_filename,
# #                 source_video,
# #                 start_time,
# #                 end_time,
# #                 evidence_duration,
# #                 evidence_reason,
# #                 now,
# #                 now,
# #                 incident_id,
# #             ),
# #         )

# #         conn.commit()

# #         return {
# #             "action": "UPDATED",
# #             "incident_id": incident_id,
# #             "evidence_event_id": evidence_event_id,
# #             "evidence_status": status,
# #             "evidence_type": evidence_type,
# #             "proof_path": proof_path,
# #             "proof_filename": proof_filename,
# #             "source_video": source_video,
# #             "start_time": start_time,
# #             "end_time": end_time,
# #             "evidence_duration": evidence_duration,
# #             "evidence_reason": evidence_reason,
# #         }

# #     except Exception:
# #         conn.rollback()
# #         raise

# #     finally:
# #         conn.close()



# # # ============================================================
# # # REDIS GROUP MANAGEMENT
# # # ============================================================


# # async def ensure_evidence_consumer_group() -> None:
# #     """
# #     Ensure the evidence persistence consumer group exists.
# #     """

# #     try:

# #         await redis_client.xgroup_create(
# #             name=EVIDENCE_STREAM_NAME,
# #             groupname=EVIDENCE_GROUP_NAME,
# #             id="0",
# #             mkstream=True,
# #         )

# #         print(
# #             "[INCIDENT] Created evidence consumer group "
# #             f"{EVIDENCE_GROUP_NAME} for "
# #             f"{EVIDENCE_STREAM_NAME}"
# #         )

# #     except Exception as exc:

# #         if "BUSYGROUP" in str(exc):
# #             return

# #         raise


# # # ============================================================
# # # EVIDENCE ACK
# # # ============================================================


# # async def acknowledge_evidence(
# #     redis_id: str,
# # ) -> None:

# #     await redis_client.xack(
# #         EVIDENCE_STREAM_NAME,
# #         EVIDENCE_GROUP_NAME,
# #         redis_id,
# #     )


# # # ============================================================
# # # EVENT NORMALIZATION
# # # ============================================================


# # def normalize_fields(
# #     fields: Any,
# # ) -> dict[str, Any]:

# #     if not isinstance(
# #         fields,
# #         dict,
# #     ):
# #         return {}

# #     normalized: dict[str, Any] = {}

# #     for key, value in fields.items():

# #         if isinstance(
# #             key,
# #             bytes,
# #         ):
# #             key = key.decode(
# #                 "utf-8",
# #                 errors="replace",
# #             )

# #         if isinstance(
# #             value,
# #             bytes,
# #         ):
# #             value = value.decode(
# #                 "utf-8",
# #                 errors="replace",
# #             )

# #         normalized[key] = value

# #     return normalized


# # def parse_event(
# #     fields: Any,
# # ) -> dict[str, Any]:

# #     normalized = normalize_fields(
# #         fields
# #     )

# #     raw_event = normalized.get(
# #         "event"
# #     )

# #     if raw_event is None:
# #         raise ValueError(
# #             "Redis message missing event field"
# #         )

# #     if isinstance(
# #         raw_event,
# #         bytes,
# #     ):
# #         raw_event = raw_event.decode(
# #             "utf-8",
# #             errors="replace",
# #         )

# #     if isinstance(
# #         raw_event,
# #         str,
# #     ):

# #         try:

# #             event = json.loads(
# #                 raw_event
# #             )

# #         except json.JSONDecodeError as exc:

# #             raise ValueError(
# #                 f"Invalid event JSON: {exc}"
# #             ) from exc

# #     elif isinstance(
# #         raw_event,
# #         dict,
# #     ):

# #         event = raw_event

# #     else:

# #         raise ValueError(
# #             "Redis event must be JSON string or object"
# #         )

# #     if not isinstance(
# #         event,
# #         dict,
# #     ):
# #         raise ValueError(
# #             "Canonical event must be an object"
# #         )

# #     validated = validate_event(
# #         event
# #     )

# #     if hasattr(
# #         validated,
# #         "to_dict",
# #     ):
# #         return validated.to_dict()

# #     if hasattr(
# #         validated,
# #         "model_dump",
# #     ):
# #         return validated.model_dump(
# #             mode="json"
# #         )

# #     if isinstance(
# #         validated,
# #         dict,
# #     ):
# #         return validated

# #     raise ValueError(
# #         "Validated event has unsupported type"
# #     )


# # # ============================================================
# # # EVIDENCE MESSAGE PROCESSING
# # # ============================================================


# # async def process_evidence_event(
# #     redis_id: str,
# #     fields: Any,
# # ) -> None:
# #     """
# #     Process one evidence Redis message.

# #     Permanent invalid payload:
# #         ACK.

# #     Successful update:
# #         ACK.

# #     Retryable processing failure:
# #         NO ACK.
# #     """

# #     try:

# #         event = parse_event(
# #             fields
# #         )

# #         event_type = event.get(
# #             "event_type"
# #         )

# #         if event_type not in SUPPORTED_EVIDENCE_EVENT_TYPES:

# #             print(
# #                 "[INCIDENT] Unsupported evidence event; "
# #                 f"ACKing redis_id={redis_id} "
# #                 f"type={event_type}"
# #             )

# #             await acknowledge_evidence(
# #                 redis_id
# #             )

# #             return

# #         result = await asyncio.to_thread(
# #             update_evidence_sync,
# #             event,
# #         )

# #         print(
# #             "[INCIDENT] Evidence update | "
# #             f"Action={result.get('action')} | "
# #             f"Incident={result.get('incident_id')} | "
# #             f"Status={result.get('evidence_status')}"
# #         )

# #         await acknowledge_evidence(
# #             redis_id
# #         )

# #     except ValueError as exc:

# #         print(
# #             "[INCIDENT] Invalid evidence message; "
# #             f"ACKing redis_id={redis_id} | "
# #             f"error={exc}"
# #         )

# #         await acknowledge_evidence(
# #             redis_id
# #         )

# #     except asyncio.CancelledError:
# #         raise

# #     except Exception as exc:

# #         print(
# #             "[INCIDENT] Evidence processing failed; "
# #             f"redis_id={redis_id} | "
# #             f"{type(exc).__name__}: {exc}"
# #         )

# #         # IMPORTANT:
# #         #
# #         # Do NOT ACK.
# #         #
# #         # Redis retains the message as pending so it can
# #         # be recovered after failure.

# #         raise


# # # ============================================================
# # # PENDING EVIDENCE RECOVERY
# # # ============================================================


# # async def recover_pending_evidence() -> None:
# #     """
# #     Recover evidence messages previously owned by this consumer.
# #     """

# #     while True:

# #         try:

# #             messages = await redis_client.xreadgroup(
# #                 groupname=EVIDENCE_GROUP_NAME,
# #                 consumername=EVIDENCE_CONSUMER_NAME,
# #                 streams={
# #                     EVIDENCE_STREAM_NAME: "0-0",
# #                 },
# #                 count=READ_COUNT,
# #                 block=RECOVERY_BLOCK_MS,
# #             )

# #         except asyncio.CancelledError:
# #             raise

# #         except Exception as exc:

# #             print(
# #                 "[INCIDENT] Pending evidence recovery "
# #                 "read failed: "
# #                 f"{type(exc).__name__}: {exc}"
# #             )

# #             return

# #         if not messages:
# #             return

# #         processed = False

# #         for (
# #             _stream_name,
# #             stream_messages,
# #         ) in messages:

# #             for (
# #                 redis_id,
# #                 fields,
# #             ) in stream_messages:

# #                 processed = True

# #                 try:

# #                     await process_evidence_event(
# #                         redis_id,
# #                         fields,
# #                     )

# #                 except asyncio.CancelledError:
# #                     raise

# #                 except Exception as exc:

# #                     print(
# #                         "[INCIDENT] Pending evidence still failed: "
# #                         f"redis_id={redis_id} | "
# #                         f"{type(exc).__name__}: {exc}"
# #                     )

# #         if not processed:
# #             return


# # # ============================================================
# # # STALE EVIDENCE RECOVERY
# # # ============================================================


# # async def recover_stale_evidence() -> None:
# #     """
# #     Claim stale evidence messages from failed consumers.
# #     """

# #     try:

# #         result = await redis_client.xautoclaim(
# #             EVIDENCE_STREAM_NAME,
# #             EVIDENCE_GROUP_NAME,
# #             EVIDENCE_CONSUMER_NAME,
# #             min_idle_time=PENDING_CLAIM_IDLE_MS,
# #             start_id="0-0",
# #             count=READ_COUNT,
# #         )

# #     except asyncio.CancelledError:
# #         raise

# #     except Exception as exc:

# #         print(
# #             "[INCIDENT] Evidence XAUTOCLAIM failed: "
# #             f"{type(exc).__name__}: {exc}"
# #         )

# #         return

# #     if not result or len(result) < 2:
# #         return

# #     claimed = result[1]

# #     if not claimed:
# #         return

# #     print(
# #         "[INCIDENT] Recovered "
# #         f"{len(claimed)} stale evidence message(s)"
# #     )

# #     for (
# #         redis_id,
# #         fields,
# #     ) in claimed:

# #         try:

# #             await process_evidence_event(
# #                 redis_id,
# #                 fields,
# #             )

# #         except asyncio.CancelledError:
# #             raise

# #         except Exception as exc:

# #             print(
# #                 "[INCIDENT] Recovered evidence failed: "
# #                 f"redis_id={redis_id} | "
# #                 f"{type(exc).__name__}: {exc}"
# #             )


# # # ============================================================
# # # EVIDENCE CONSUMER LOOP
# # # ============================================================


# # async def evidence_consumer_loop() -> None:
# #     """
# #     Main evidence persistence consumer loop.

# #     This consumer owns:

# #         events.evidence

# #     It does NOT consume:

# #         events.alerts
# #     """

# #     await ensure_evidence_consumer_group()

# #     await recover_pending_evidence()

# #     print(
# #         "[INCIDENT] Evidence consumer loop started | "
# #         f"stream={EVIDENCE_STREAM_NAME} | "
# #         f"group={EVIDENCE_GROUP_NAME} | "
# #         f"consumer={EVIDENCE_CONSUMER_NAME}"
# #     )

# #     while True:

# #         await recover_stale_evidence()

# #         try:

# #             messages = await redis_client.xreadgroup(
# #                 groupname=EVIDENCE_GROUP_NAME,
# #                 consumername=EVIDENCE_CONSUMER_NAME,
# #                 streams={
# #                     EVIDENCE_STREAM_NAME: ">",
# #                 },
# #                 count=READ_COUNT,
# #                 block=READ_BLOCK_MS,
# #             )

# #         except asyncio.CancelledError:
# #             raise

# #         except Exception as exc:

# #             print(
# #                 "[INCIDENT] Evidence XREADGROUP failed: "
# #                 f"{type(exc).__name__}: {exc}"
# #             )

# #             await asyncio.sleep(
# #                 CONSUMER_RESTART_DELAY_SECONDS
# #             )

# #             continue

# #         if not messages:
# #             continue

# #         for (
# #             _stream_name,
# #             stream_messages,
# #         ) in messages:

# #             for (
# #                 redis_id,
# #                 fields,
# #             ) in stream_messages:

# #                 try:

# #                     await process_evidence_event(
# #                         redis_id,
# #                         fields,
# #                     )

# #                 except asyncio.CancelledError:
# #                     raise

# #                 except Exception as exc:

# #                     print(
# #                         "[INCIDENT] Evidence message remains pending: "
# #                         f"redis_id={redis_id} | "
# #                         f"{type(exc).__name__}: {exc}"
# #                     )


# # # ============================================================
# # # UNIFIED CONSUMER SERVICE
# # # ============================================================


# # async def consume_events() -> None:
# #     """
# #     Run the evidence persistence consumer.

# #     IMPORTANT ARCHITECTURAL OWNERSHIP:

# #         events.alerts
# #             -> agents.incident.main

# #         events.evidence
# #             -> this module

# #     Therefore this function intentionally does NOT start
# #     an alert consumer.
# #     """

# #     # --------------------------------------------------------
# #     # Database initialization.
# #     # --------------------------------------------------------

# #     await asyncio.to_thread(
# #         ensure_incidents_table
# #     )

# #     # --------------------------------------------------------
# #     # Ensure evidence group.
# #     # --------------------------------------------------------

# #     await ensure_evidence_consumer_group()

# #     # --------------------------------------------------------
# #     # Start evidence persistence consumer.
# #     # --------------------------------------------------------

# #     evidence_task = asyncio.create_task(
# #         evidence_consumer_loop(),
# #         name="incident-evidence-consumer",
# #     )

# #     print(
# #         "[INCIDENT] Evidence persistence service started."
# #     )

# #     try:

# #         await evidence_task

# #     except asyncio.CancelledError:

# #         evidence_task.cancel()

# #         await asyncio.gather(
# #             evidence_task,
# #             return_exceptions=True,
# #         )

# #         raise

# #     except Exception as exc:

# #         print(
# #             "[INCIDENT] Evidence consumer service failed: "
# #             f"{type(exc).__name__}: {exc}"
# #         )

# #         raise

# #     finally:

# #         if not evidence_task.done():
# #             evidence_task.cancel()

# #         await asyncio.gather(
# #             evidence_task,
# #             return_exceptions=True,
# #         )

# #         print(
# #             "[INCIDENT] Evidence persistence service stopped."
# #         )


# # # ============================================================
# # # DIRECT EXECUTION
# # # ============================================================


# # if __name__ == "__main__":
# #     asyncio.run(
# #         consume_events()
# #     )








































# """
# Reliable Redis Stream consumers and incident persistence.

# Responsibilities
# ----------------

# - Provide canonical incident database persistence helpers.
# - Create/update incidents in SQLite.
# - Consume canonical evidence.generated/evidence.failed events.
# - Link evidence results back to incidents.
# - Validate canonical events before processing.
# - ACK Redis evidence messages only after successful processing.
# - Recover pending evidence messages after restart.
# - Claim stale evidence messages from failed consumers.
# - Isolate malformed/failed evidence messages.

# Non-responsibilities
# --------------------

# - Consuming alert.created events.
# - Alert -> incident orchestration.
# - Agent supervision.
# - Camera processing.
# - Object detection.
# - Evidence generation.
# - API-facing Redis stream queries.

# Alert -> incident orchestration belongs to:

#     agents.incident.main

# API-facing Redis event queries belong to:

#     backend.app.messaging.event_consumer

# Evidence generation belongs to:

#     agents.evidence.main
# """

# from __future__ import annotations

# import asyncio
# import json
# import os
# import socket
# import sqlite3
# import uuid
# from datetime import datetime, timezone
# from typing import Any

# from backend.app.incidents.paths import incident_database_path
# from backend.app.messaging.redis_client import redis_client
# from shared.schemas.event_schema import validate_event


# # ============================================================
# # DATABASE CONFIGURATION
# # ============================================================

# DATABASE_PATH = incident_database_path()


# # ============================================================
# # EVIDENCE STREAM CONFIGURATION
# # ============================================================

# EVIDENCE_STREAM_NAME = (
#     os.getenv(
#         "INCIDENT_EVIDENCE_INPUT_STREAM",
#         "events.evidence",
#     ).strip()
#     or "events.evidence"
# )

# EVIDENCE_GROUP_NAME = (
#     os.getenv(
#         "INCIDENT_EVIDENCE_GROUP",
#         "incident-evidence-workers",
#     ).strip()
#     or "incident-evidence-workers"
# )

# EVIDENCE_CONSUMER_NAME = (
#     os.getenv(
#         "INCIDENT_EVIDENCE_CONSUMER_NAME",
#         f"incident-evidence-{socket.gethostname()}-{uuid.uuid4().hex[:8]}",
#     ).strip()
#     or f"incident-evidence-{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
# )

# SUPPORTED_EVIDENCE_EVENT_TYPES = {
#     "evidence.generated",
#     "evidence.failed",
# }


# # ============================================================
# # DEFAULTS
# # ============================================================

# DEFAULT_STATUS = "OPEN"
# DEFAULT_EVIDENCE_STATUS = "PENDING"

# PENDING_CLAIM_IDLE_MS = max(
#     1000,
#     int(
#         os.getenv(
#             "INCIDENT_PENDING_CLAIM_IDLE_MS",
#             "120000",
#         )
#     ),
# )

# READ_COUNT = max(
#     1,
#     int(
#         os.getenv(
#             "INCIDENT_READ_COUNT",
#             "10",
#         )
#     ),
# )

# READ_BLOCK_MS = max(
#     100,
#     int(
#         os.getenv(
#             "INCIDENT_READ_BLOCK_MS",
#             "5000",
#         )
#     ),
# )

# RECOVERY_BLOCK_MS = max(
#     100,
#     int(
#         os.getenv(
#             "INCIDENT_RECOVERY_BLOCK_MS",
#             "1000",
#         )
#     ),
# )

# CONSUMER_RESTART_DELAY_SECONDS = max(
#     0.1,
#     float(
#         os.getenv(
#             "INCIDENT_CONSUMER_RESTART_DELAY_SECONDS",
#             "2",
#         )
#     ),
# )


# # ============================================================
# # INTERNAL EXCEPTIONS
# # ============================================================


# class RetryableEvidenceProcessingError(Exception):
#     """
#     Indicates that an evidence message should remain pending.

#     Examples:

#     - Incident has not been persisted yet.
#     - Temporary database problem.
#     - Temporary dependency failure.

#     The Redis message must NOT be ACKed.
#     """


# class PermanentEvidenceMessageError(ValueError):
#     """
#     Indicates that an evidence message is permanently invalid.

#     These messages may safely be ACKed so that malformed data does
#     not poison the consumer indefinitely.
#     """


# # ============================================================
# # DATABASE
# # ============================================================


# def get_database_connection() -> sqlite3.Connection:
#     """
#     Open a SQLite connection configured for concurrent workers.

#     WAL allows readers and writers to coexist more effectively.

#     busy_timeout reduces transient database-lock failures.

#     foreign_keys enables SQLite foreign-key enforcement.
#     """

#     DATABASE_PATH.parent.mkdir(
#         parents=True,
#         exist_ok=True,
#     )

#     conn = sqlite3.connect(
#         str(DATABASE_PATH),
#         timeout=10,
#     )

#     conn.row_factory = sqlite3.Row

#     conn.execute(
#         "PRAGMA journal_mode=WAL"
#     )

#     conn.execute(
#         "PRAGMA busy_timeout=10000"
#     )

#     conn.execute(
#         "PRAGMA foreign_keys=ON"
#     )

#     return conn


# def ensure_incidents_table() -> None:
#     """
#     Create or migrate the canonical incidents table.

#     This function is synchronous intentionally.

#     Async callers should use:

#         await asyncio.to_thread(
#             ensure_incidents_table
#         )
#     """

#     conn = get_database_connection()

#     try:
#         conn.execute(
#             """
#             CREATE TABLE IF NOT EXISTS incidents (
#                 incident_id TEXT PRIMARY KEY,
#                 alert_event_id TEXT UNIQUE NOT NULL,
#                 event_id TEXT,
#                 camera_id TEXT,
#                 event_type TEXT NOT NULL,
#                 alert_type TEXT NOT NULL,
#                 severity TEXT NOT NULL,
#                 mode TEXT,
#                 trace_id TEXT,
#                 correlation_id TEXT,
#                 source_agent_id TEXT,
#                 source_instance_id TEXT,
#                 source_hostname TEXT,
#                 source_redis_id TEXT,
#                 person_count INTEGER,
#                 threshold REAL,
#                 frame_id INTEGER,
#                 frame_timestamp REAL,
#                 track_ids TEXT,
#                 message TEXT,
#                 status TEXT NOT NULL DEFAULT 'OPEN',
#                 evidence_status TEXT NOT NULL DEFAULT 'PENDING',
#                 evidence_type TEXT,
#                 evidence_event_id TEXT,
#                 proof_path TEXT,
#                 proof_filename TEXT,
#                 source_video TEXT,
#                 video_id TEXT,
#                 start_time TEXT,
#                 end_time TEXT,
#                 evidence_duration REAL,
#                 evidence_reason TEXT,
#                 evidence_updated_at TEXT,
#                 created_at TEXT NOT NULL,
#                 updated_at TEXT NOT NULL
#             )
#             """
#         )

#         columns = {
#             row["name"]
#             for row in conn.execute(
#                 "PRAGMA table_info(incidents)"
#             ).fetchall()
#         }

#         # --------------------------------------------------------
#         # Safe additive migrations.
#         # --------------------------------------------------------

#         migrations: dict[str, str] = {
#             "event_id": "TEXT",
#             "camera_id": "TEXT",
#             "event_type": "TEXT",
#             "mode": "TEXT",
#             "trace_id": "TEXT",
#             "correlation_id": "TEXT",
#             "source_agent_id": "TEXT",
#             "source_instance_id": "TEXT",
#             "source_hostname": "TEXT",
#             "source_redis_id": "TEXT",
#             "person_count": "INTEGER",
#             "threshold": "REAL",
#             "frame_id": "INTEGER",
#             "frame_timestamp": "REAL",
#             "track_ids": "TEXT",
#             "message": "TEXT",
#             "source_video": "TEXT",
#             "video_id": "TEXT",
#             "start_time": "TEXT",
#             "end_time": "TEXT",
#             "evidence_status": "TEXT",
#             "evidence_type": "TEXT",
#             "evidence_event_id": "TEXT",
#             "proof_path": "TEXT",
#             "proof_filename": "TEXT",
#             "evidence_duration": "REAL",
#             "evidence_reason": "TEXT",
#             "evidence_updated_at": "TEXT",
#             "created_at": "TEXT",
#             "updated_at": "TEXT",
#         }

#         for column, definition in migrations.items():
#             if column not in columns:
#                 conn.execute(
#                     f"""
#                     ALTER TABLE incidents
#                     ADD COLUMN {column} {definition}
#                     """
#                 )

#         # --------------------------------------------------------
#         # Backfill timestamps.
#         # --------------------------------------------------------

#         now = datetime.now(
#             timezone.utc
#         ).isoformat()

#         conn.execute(
#             """
#             UPDATE incidents
#             SET created_at = COALESCE(
#                 created_at,
#                 ?
#             )
#             WHERE created_at IS NULL
#             """,
#             (now,),
#         )

#         conn.execute(
#             """
#             UPDATE incidents
#             SET updated_at = COALESCE(
#                 updated_at,
#                 created_at,
#                 ?
#             )
#             WHERE updated_at IS NULL
#             """,
#             (now,),
#         )

#         conn.execute(
#             """
#             UPDATE incidents
#             SET event_type = COALESCE(
#                 event_type,
#                 'alert.created'
#             )
#             WHERE event_type IS NULL
#             """
#         )

#         conn.execute(
#             """
#             UPDATE incidents
#             SET evidence_status = COALESCE(
#                 evidence_status,
#                 ?
#             )
#             WHERE evidence_status IS NULL
#             """,
#             (DEFAULT_EVIDENCE_STATUS,),
#         )

#         # --------------------------------------------------------
#         # Indexes.
#         # --------------------------------------------------------

#         conn.execute(
#             """
#             CREATE UNIQUE INDEX IF NOT EXISTS
#             idx_incidents_alert_event_id
#             ON incidents(alert_event_id)
#             """
#         )

#         conn.execute(
#             """
#             CREATE INDEX IF NOT EXISTS
#             idx_incidents_event_id
#             ON incidents(event_id)
#             """
#         )

#         conn.execute(
#             """
#             CREATE INDEX IF NOT EXISTS
#             idx_incidents_camera_id
#             ON incidents(camera_id)
#             """
#         )

#         conn.execute(
#             """
#             CREATE INDEX IF NOT EXISTS
#             idx_incidents_status
#             ON incidents(status)
#             """
#         )

#         conn.execute(
#             """
#             CREATE INDEX IF NOT EXISTS
#             idx_incidents_severity
#             ON incidents(severity)
#             """
#         )

#         conn.execute(
#             """
#             CREATE INDEX IF NOT EXISTS
#             idx_incidents_evidence_status
#             ON incidents(evidence_status)
#             """
#         )

#         conn.execute(
#             """
#             CREATE INDEX IF NOT EXISTS
#             idx_incidents_start_time
#             ON incidents(start_time)
#             """
#         )

#         conn.execute(
#             """
#             CREATE INDEX IF NOT EXISTS
#             idx_incidents_trace_id
#             ON incidents(trace_id)
#             """
#         )

#         conn.execute(
#             """
#             CREATE INDEX IF NOT EXISTS
#             idx_incidents_correlation_id
#             ON incidents(correlation_id)
#             """
#         )

#         conn.execute(
#             """
#             CREATE UNIQUE INDEX IF NOT EXISTS
#             idx_incidents_evidence_event_id
#             ON incidents(evidence_event_id)
#             WHERE evidence_event_id IS NOT NULL
#             """
#         )

#         conn.commit()

#     finally:
#         conn.close()


# # ============================================================
# # TIMESTAMP HELPERS
# # ============================================================


# def parse_timestamp(
#     value: Any,
# ) -> str | None:
#     """
#     Parse an ISO timestamp and normalize it to UTC.

#     Numeric values are intentionally not interpreted as
#     wall-clock timestamps.
#     """

#     if value is None:
#         return None

#     if isinstance(
#         value,
#         datetime,
#     ):
#         dt = value

#     elif isinstance(
#         value,
#         str,
#     ):
#         value = value.strip()

#         if not value:
#             return None

#         try:
#             normalized = value

#             if normalized.endswith("Z"):
#                 normalized = (
#                     normalized[:-1]
#                     + "+00:00"
#                 )

#             dt = datetime.fromisoformat(
#                 normalized
#             )

#         except ValueError:
#             return None

#     else:
#         return None

#     if dt.tzinfo is None:
#         dt = dt.replace(
#             tzinfo=timezone.utc
#         )

#     dt = dt.astimezone(
#         timezone.utc
#     )

#     return dt.isoformat()


# def get_event_time(
#     event: dict[str, Any],
# ) -> str:
#     """
#     Determine wall-clock event time.

#     Priority:

#         data.event_timestamp
#         data.frame_datetime
#         event.timestamp
#         current UTC time

#     Numeric frame_timestamp/event_time values are treated
#     as video-relative values and are not converted to
#     wall-clock timestamps.
#     """

#     data = event.get(
#         "data",
#         {},
#     )

#     if isinstance(
#         data,
#         dict,
#     ):
#         for key in (
#             "event_timestamp",
#             "frame_datetime",
#         ):
#             parsed = parse_timestamp(
#                 data.get(key)
#             )

#             if parsed:
#                 return parsed

#     parsed = parse_timestamp(
#         event.get("timestamp")
#     )

#     if parsed:
#         return parsed

#     return datetime.now(
#         timezone.utc
#     ).isoformat()


# # ============================================================
# # TYPE HELPERS
# # ============================================================


# def safe_int(
#     value: Any,
# ) -> int | None:
#     if value is None:
#         return None

#     try:
#         return int(value)

#     except (
#         TypeError,
#         ValueError,
#     ):
#         return None


# def safe_float(
#     value: Any,
# ) -> float | None:
#     if value is None:
#         return None

#     try:
#         return float(value)

#     except (
#         TypeError,
#         ValueError,
#     ):
#         return None


# def normalize_track_ids(
#     value: Any,
# ) -> list[str]:
#     if value is None:
#         return []

#     if isinstance(
#         value,
#         (
#             list,
#             tuple,
#             set,
#         ),
#     ):
#         return [
#             str(item)
#             for item in value
#             if item is not None
#         ]

#     return [str(value)]


# # ============================================================
# # EVENT VALIDATION / NORMALIZATION
# # ============================================================


# def convert_validated_event(
#     validated_event: Any,
# ) -> dict[str, Any]:
#     """
#     Convert the result of validate_event() into a dictionary.

#     Supports both older/custom validators and Pydantic-style
#     model_dump().
#     """

#     if hasattr(
#         validated_event,
#         "to_dict",
#     ):
#         result = validated_event.to_dict()

#     elif hasattr(
#         validated_event,
#         "model_dump",
#     ):
#         result = validated_event.model_dump(
#             mode="json"
#         )

#     elif isinstance(
#         validated_event,
#         dict,
#     ):
#         result = validated_event

#     else:
#         raise PermanentEvidenceMessageError(
#             "Validated event has unsupported type"
#         )

#     if not isinstance(
#         result,
#         dict,
#     ):
#         raise PermanentEvidenceMessageError(
#             "Validated event is not an object"
#         )

#     return result


# def validate_and_normalize_event(
#     event: Any,
# ) -> dict[str, Any]:
#     """
#     Validate and normalize a canonical event.

#     Validation failures are considered permanent message
#     failures and should be ACKed by the Redis consumer.
#     """

#     if not isinstance(
#         event,
#         dict,
#     ):
#         raise PermanentEvidenceMessageError(
#             "Event must be a dictionary"
#         )

#     try:
#         validated_event = validate_event(
#             event
#         )

#     except Exception as exc:
#         raise PermanentEvidenceMessageError(
#             f"Event validation failed: {exc}"
#         ) from exc

#     return convert_validated_event(
#         validated_event
#     )


# # ============================================================
# # INCIDENT CREATION
# # ============================================================


# def create_incident_sync(
#     event: dict[str, Any],
# ) -> dict[str, Any]:
#     """
#     Create an incident from a canonical alert.created event.

#     This function is called by:

#         agents.incident.main

#     It is NOT called by the Redis evidence consumer service.

#     Idempotency is based on alert_event_id.
#     """

#     if not isinstance(
#         event,
#         dict,
#     ):
#         raise ValueError(
#             "Event must be a dictionary"
#         )

#     event = validate_and_normalize_event(
#         event
#     )

#     event_type = event.get(
#         "event_type"
#     )

#     if event_type != "alert.created":
#         raise ValueError(
#             f"Unsupported event type: {event_type}"
#         )

#     event_id = event.get(
#         "event_id"
#     )

#     if not event_id:
#         raise ValueError(
#             "Alert event is missing event_id"
#         )

#     camera = event.get(
#         "camera",
#         {},
#     )

#     if not isinstance(
#         camera,
#         dict,
#     ):
#         camera = {}

#     context = event.get(
#         "context",
#         {},
#     )

#     if not isinstance(
#         context,
#         dict,
#     ):
#         context = {}

#     data = event.get(
#         "data",
#         {},
#     )

#     if not isinstance(
#         data,
#         dict,
#     ):
#         raise ValueError(
#             "Alert event data must be an object"
#         )

#     source = event.get(
#         "source",
#         {},
#     )

#     if not isinstance(
#         source,
#         dict,
#     ):
#         source = {}

#     incident_id = (
#         context.get("incident_id")
#         or str(uuid.uuid4())
#     )

#     camera_id = camera.get(
#         "camera_id"
#     )

#     alert_type = str(
#         data.get(
#             "alert_type",
#             "unknown",
#         )
#     )

#     severity = str(
#         data.get(
#             "severity",
#             "medium",
#         )
#     )

#     mode = context.get(
#         "mode"
#     )

#     trace_id = context.get(
#         "trace_id"
#     )

#     correlation_id = context.get(
#         "correlation_id"
#     )

#     source_agent_id = source.get(
#         "agent_id"
#     )

#     source_instance_id = source.get(
#         "instance_id"
#     )

#     source_hostname = source.get(
#         "hostname"
#     )

#     person_count = safe_int(
#         data.get(
#             "person_count"
#         )
#     )

#     threshold = safe_float(
#         data.get(
#             "threshold"
#         )
#     )

#     frame_id = safe_int(
#         data.get(
#             "frame_id"
#         )
#     )

#     frame_timestamp = safe_float(
#         data.get(
#             "frame_timestamp"
#         )
#     )

#     if frame_timestamp is None:
#         frame_timestamp = safe_float(
#             data.get(
#                 "event_time"
#             )
#         )

#     track_ids = normalize_track_ids(
#         data.get(
#             "track_ids"
#         )
#     )

#     message = data.get(
#         "message"
#     )

#     source_video = data.get(
#         "source_video"
#     )

#     video_id = data.get(
#         "video_id"
#     )

#     event_time = get_event_time(
#         event
#     )

#     now = datetime.now(
#         timezone.utc
#     ).isoformat()

#     conn = get_database_connection()

#     try:
#         # --------------------------------------------------------
#         # Idempotency lookup.
#         # --------------------------------------------------------

#         existing = conn.execute(
#             """
#             SELECT
#                 incident_id,
#                 alert_event_id,
#                 event_id,
#                 alert_type,
#                 severity,
#                 camera_id,
#                 status,
#                 evidence_status,
#                 proof_path,
#                 evidence_event_id,
#                 source_video,
#                 video_id,
#                 start_time,
#                 end_time,
#                 evidence_duration,
#                 evidence_reason,
#                 evidence_updated_at,
#                 created_at,
#                 updated_at
#             FROM incidents
#             WHERE alert_event_id = ?
#             """,
#             (event_id,),
#         ).fetchone()

#         if existing:
#             existing_incident_id = existing[
#                 "incident_id"
#             ]

#             conn.execute(
#                 """
#                 UPDATE incidents
#                 SET
#                     source_video = COALESCE(
#                         source_video,
#                         ?
#                     ),
#                     video_id = COALESCE(
#                         video_id,
#                         ?
#                     ),
#                     updated_at = ?
#                 WHERE incident_id = ?
#                 """,
#                 (
#                     source_video,
#                     video_id,
#                     now,
#                     existing_incident_id,
#                 ),
#             )

#             conn.commit()

#             return {
#                 "action": "UPDATED",
#                 "incident_id": existing_incident_id,
#                 "alert_event_id": event_id,
#                 "camera_id": existing[
#                     "camera_id"
#                 ],
#                 "alert_type": existing[
#                     "alert_type"
#                 ],
#                 "severity": existing[
#                     "severity"
#                 ],
#                 "person_count": person_count,
#                 "evidence_status": existing[
#                     "evidence_status"
#                 ],
#             }

#         # --------------------------------------------------------
#         # Insert.
#         # --------------------------------------------------------

#         try:
#             conn.execute(
#                 """
#                 INSERT INTO incidents (
#                     incident_id,
#                     alert_event_id,
#                     event_id,
#                     camera_id,
#                     event_type,
#                     alert_type,
#                     severity,
#                     mode,
#                     trace_id,
#                     correlation_id,
#                     source_agent_id,
#                     source_instance_id,
#                     source_hostname,
#                     person_count,
#                     threshold,
#                     frame_id,
#                     frame_timestamp,
#                     track_ids,
#                     message,
#                     status,
#                     evidence_status,
#                     source_video,
#                     video_id,
#                     start_time,
#                     end_time,
#                     created_at,
#                     updated_at
#                 )
#                 VALUES (
#                     ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
#                     ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
#                     ?, ?, ?, ?, ?, ?, ?
#                 )
#                 """,
#                 (
#                     incident_id,
#                     event_id,
#                     event_id,
#                     camera_id,
#                     event_type,
#                     alert_type,
#                     severity,
#                     mode,
#                     trace_id,
#                     correlation_id,
#                     source_agent_id,
#                     source_instance_id,
#                     source_hostname,
#                     person_count,
#                     threshold,
#                     frame_id,
#                     frame_timestamp,
#                     json.dumps(track_ids),
#                     message,
#                     DEFAULT_STATUS,
#                     DEFAULT_EVIDENCE_STATUS,
#                     source_video,
#                     video_id,
#                     event_time,
#                     event_time,
#                     now,
#                     now,
#                 ),
#             )

#             conn.commit()

#         except sqlite3.IntegrityError:
#             conn.rollback()

#             existing = conn.execute(
#                 """
#                 SELECT
#                     incident_id,
#                     alert_event_id,
#                     alert_type,
#                     severity,
#                     camera_id,
#                     status,
#                     evidence_status
#                 FROM incidents
#                 WHERE alert_event_id = ?
#                 """,
#                 (event_id,),
#             ).fetchone()

#             if not existing:
#                 raise

#             return {
#                 "action": "UPDATED",
#                 "incident_id": existing[
#                     "incident_id"
#                 ],
#                 "alert_event_id": event_id,
#                 "camera_id": existing[
#                     "camera_id"
#                 ],
#                 "alert_type": existing[
#                     "alert_type"
#                 ],
#                 "severity": existing[
#                     "severity"
#                 ],
#                 "person_count": person_count,
#                 "evidence_status": existing[
#                     "evidence_status"
#                 ],
#             }

#         return {
#             "action": "CREATED",
#             "incident_id": incident_id,
#             "alert_event_id": event_id,
#             "camera_id": camera_id,
#             "alert_type": alert_type,
#             "severity": severity,
#             "person_count": person_count,
#             "evidence_status": DEFAULT_EVIDENCE_STATUS,
#         }

#     finally:
#         conn.close()


# # ============================================================
# # EVIDENCE UPDATE
# # ============================================================


# def update_evidence_sync(
#     event: dict[str, Any],
# ) -> dict[str, Any]:
#     """
#     Apply an evidence.generated/evidence.failed event.

#     The incident_id is taken from:

#         event.context.incident_id

#     Persists the complete evidence metadata:

#         - evidence_status
#         - evidence_type
#         - evidence_event_id
#         - proof_path
#         - proof_filename
#         - source_video
#         - start_time
#         - end_time
#         - evidence_duration
#         - evidence_reason
#         - evidence_updated_at

#     A completed evidence result cannot later be downgraded
#     by a stale failure event.

#     IMPORTANT:

#     If the incident does not yet exist, this function raises
#     RetryableEvidenceProcessingError rather than ValueError.

#     This prevents evidence from being ACKed and lost when
#     incident persistence and evidence generation race each other.
#     """

#     if not isinstance(
#         event,
#         dict,
#     ):
#         raise PermanentEvidenceMessageError(
#             "Evidence event must be a dictionary"
#         )

#     event = validate_and_normalize_event(
#         event
#     )

#     event_type = event.get(
#         "event_type"
#     )

#     if event_type not in SUPPORTED_EVIDENCE_EVENT_TYPES:
#         raise PermanentEvidenceMessageError(
#             f"Unsupported evidence event type: {event_type}"
#         )

#     context = event.get(
#         "context",
#         {},
#     )

#     if not isinstance(
#         context,
#         dict,
#     ):
#         context = {}

#     incident_id = context.get(
#         "incident_id"
#     )

#     if not incident_id:
#         raise PermanentEvidenceMessageError(
#             "Evidence event is missing "
#             "context.incident_id"
#         )

#     data = event.get(
#         "data",
#         {},
#     )

#     if not isinstance(
#         data,
#         dict,
#     ):
#         raise PermanentEvidenceMessageError(
#             "Evidence event data must be an object"
#         )

#     evidence_event_id = event.get(
#         "event_id"
#     )

#     if not evidence_event_id:
#         raise PermanentEvidenceMessageError(
#             "Evidence event is missing event_id"
#         )

#     # --------------------------------------------------------
#     # Determine final evidence status.
#     # --------------------------------------------------------

#     raw_status = str(
#         data.get(
#             "status",
#             "",
#         )
#     ).strip().upper()

#     if event_type == "evidence.generated":
#         status = (
#             "FAILED"
#             if raw_status
#             in {
#                 "FAILED",
#                 "ERROR",
#             }
#             else "COMPLETED"
#         )
#     else:
#         status = "FAILED"

#     # --------------------------------------------------------
#     # Evidence metadata.
#     # --------------------------------------------------------

#     evidence_type = data.get(
#         "evidence_type"
#     )

#     proof_path = data.get(
#         "proof_path"
#     )

#     proof_filename = data.get(
#         "proof_filename"
#     )

#     source_video = data.get(
#         "source_video"
#     )

#     evidence_duration = safe_float(
#         data.get(
#             "evidence_duration"
#         )
#     )

#     if evidence_duration is None:
#         evidence_duration = safe_float(
#             data.get(
#                 "duration"
#             )
#         )

#     # --------------------------------------------------------
#     # Evidence start/end time.
#     #
#     # These are allowed to be either:
#     #
#     #   - ISO timestamps
#     #   - numeric video-relative values
#     #
#     # Store them as TEXT because the DB schema defines
#     # start_time/end_time as TEXT.
#     # --------------------------------------------------------

#     start_time = data.get(
#         "start_time"
#     )

#     end_time = data.get(
#         "end_time"
#     )

#     if start_time is not None:
#         start_time = str(start_time)

#     if end_time is not None:
#         end_time = str(end_time)

#     # --------------------------------------------------------
#     # Evidence failure reason.
#     # --------------------------------------------------------

#     evidence_reason = data.get(
#         "reason"
#     )

#     if evidence_reason is None:
#         evidence_reason = data.get(
#             "error"
#         )

#     if evidence_reason is not None:
#         evidence_reason = str(
#             evidence_reason
#         )

#     now = datetime.now(
#         timezone.utc
#     ).isoformat()

#     conn = get_database_connection()

#     try:
#         # ----------------------------------------------------
#         # Explicit transaction.
#         # ----------------------------------------------------

#         conn.execute(
#             "BEGIN IMMEDIATE"
#         )

#         incident = conn.execute(
#             """
#             SELECT
#                 incident_id,
#                 evidence_status,
#                 evidence_event_id,
#                 evidence_type,
#                 proof_path,
#                 proof_filename,
#                 source_video,
#                 start_time,
#                 end_time,
#                 evidence_duration,
#                 evidence_reason,
#                 evidence_updated_at
#             FROM incidents
#             WHERE incident_id = ?
#             """,
#             (incident_id,),
#         ).fetchone()

#         # ----------------------------------------------------
#         # IMPORTANT:
#         #
#         # Incident-not-found is retryable.
#         #
#         # Evidence generation and incident creation may race.
#         # Do not ACK this message yet.
#         # ----------------------------------------------------

#         if not incident:
#             conn.rollback()

#             raise RetryableEvidenceProcessingError(
#                 f"Incident not found yet: {incident_id}"
#             )

#         current_status = str(
#             incident["evidence_status"]
#             or DEFAULT_EVIDENCE_STATUS
#         ).upper()

#         # ----------------------------------------------------
#         # Same evidence event already applied.
#         # ----------------------------------------------------

#         if (
#             incident["evidence_event_id"]
#             == evidence_event_id
#         ):
#             conn.commit()

#             return {
#                 "action": "DUPLICATE",
#                 "incident_id": incident_id,
#                 "evidence_event_id": evidence_event_id,
#                 "evidence_status": current_status,
#             }

#         # ----------------------------------------------------
#         # Never downgrade completed evidence.
#         # ----------------------------------------------------

#         if (
#             current_status == "COMPLETED"
#             and status == "FAILED"
#         ):
#             conn.execute(
#                 """
#                 UPDATE incidents
#                 SET
#                     updated_at = ?
#                 WHERE incident_id = ?
#                 """,
#                 (
#                     now,
#                     incident_id,
#                 ),
#             )

#             conn.commit()

#             return {
#                 "action": "IGNORED_DOWNGRADE",
#                 "incident_id": incident_id,
#                 "evidence_event_id": evidence_event_id,
#                 "evidence_status": current_status,
#             }

#         # ----------------------------------------------------
#         # Apply complete evidence result.
#         #
#         # COALESCE preserves useful existing values if an
#         # incoming event omits optional metadata.
#         # ----------------------------------------------------

#         conn.execute(
#             """
#             UPDATE incidents
#             SET
#                 evidence_status = ?,

#                 evidence_type = COALESCE(
#                     ?,
#                     evidence_type
#                 ),

#                 evidence_event_id = ?,

#                 proof_path = COALESCE(
#                     ?,
#                     proof_path
#                 ),

#                 proof_filename = COALESCE(
#                     ?,
#                     proof_filename
#                 ),

#                 source_video = COALESCE(
#                     ?,
#                     source_video
#                 ),

#                 start_time = COALESCE(
#                     ?,
#                     start_time
#                 ),

#                 end_time = COALESCE(
#                     ?,
#                     end_time
#                 ),

#                 evidence_duration = COALESCE(
#                     ?,
#                     evidence_duration
#                 ),

#                 evidence_reason = ?,

#                 evidence_updated_at = ?,

#                 updated_at = ?

#             WHERE incident_id = ?
#             """,
#             (
#                 status,
#                 evidence_type,
#                 evidence_event_id,
#                 proof_path,
#                 proof_filename,
#                 source_video,
#                 start_time,
#                 end_time,
#                 evidence_duration,
#                 evidence_reason,
#                 now,
#                 now,
#                 incident_id,
#             ),
#         )

#         conn.commit()

#         return {
#             "action": "UPDATED",
#             "incident_id": incident_id,
#             "evidence_event_id": evidence_event_id,
#             "evidence_status": status,
#             "evidence_type": evidence_type,
#             "proof_path": proof_path,
#             "proof_filename": proof_filename,
#             "source_video": source_video,
#             "start_time": start_time,
#             "end_time": end_time,
#             "evidence_duration": evidence_duration,
#             "evidence_reason": evidence_reason,
#         }

#     except RetryableEvidenceProcessingError:
#         conn.rollback()
#         raise

#     except Exception:
#         conn.rollback()
#         raise

#     finally:
#         conn.close()


# # ============================================================
# # REDIS GROUP MANAGEMENT
# # ============================================================


# async def ensure_evidence_consumer_group() -> None:
#     """
#     Ensure the evidence persistence consumer group exists.
#     """

#     try:
#         await redis_client.xgroup_create(
#             name=EVIDENCE_STREAM_NAME,
#             groupname=EVIDENCE_GROUP_NAME,
#             id="0",
#             mkstream=True,
#         )

#         print(
#             "[INCIDENT] Created evidence consumer group "
#             f"{EVIDENCE_GROUP_NAME} for "
#             f"{EVIDENCE_STREAM_NAME}"
#         )

#     except Exception as exc:
#         if "BUSYGROUP" in str(exc):
#             return

#         raise


# # ============================================================
# # EVIDENCE ACK
# # ============================================================


# async def acknowledge_evidence(
#     redis_id: str,
# ) -> None:
#     await redis_client.xack(
#         EVIDENCE_STREAM_NAME,
#         EVIDENCE_GROUP_NAME,
#         redis_id,
#     )


# # ============================================================
# # EVENT NORMALIZATION
# # ============================================================


# def normalize_fields(
#     fields: Any,
# ) -> dict[str, Any]:
#     """
#     Normalize Redis stream field keys and values.

#     Redis clients may return bytes depending on configuration.
#     """

#     if not isinstance(
#         fields,
#         dict,
#     ):
#         return {}

#     normalized: dict[str, Any] = {}

#     for key, value in fields.items():

#         if isinstance(
#             key,
#             bytes,
#         ):
#             key = key.decode(
#                 "utf-8",
#                 errors="replace",
#             )

#         if isinstance(
#             value,
#             bytes,
#         ):
#             value = value.decode(
#                 "utf-8",
#                 errors="replace",
#             )

#         normalized[key] = value

#     return normalized


# def parse_event(
#     fields: Any,
# ) -> dict[str, Any]:
#     """
#     Parse a Redis stream message into a canonical validated event.
#     """

#     normalized = normalize_fields(
#         fields
#     )

#     raw_event = normalized.get(
#         "event"
#     )

#     if raw_event is None:
#         raise PermanentEvidenceMessageError(
#             "Redis message missing event field"
#         )

#     if isinstance(
#         raw_event,
#         bytes,
#     ):
#         raw_event = raw_event.decode(
#             "utf-8",
#             errors="replace",
#         )

#     if isinstance(
#         raw_event,
#         str,
#     ):
#         try:
#             event = json.loads(
#                 raw_event
#             )

#         except json.JSONDecodeError as exc:
#             raise PermanentEvidenceMessageError(
#                 f"Invalid event JSON: {exc}"
#             ) from exc

#     elif isinstance(
#         raw_event,
#         dict,
#     ):
#         event = raw_event

#     else:
#         raise PermanentEvidenceMessageError(
#             "Redis event must be JSON string or object"
#         )

#     if not isinstance(
#         event,
#         dict,
#     ):
#         raise PermanentEvidenceMessageError(
#             "Canonical event must be an object"
#         )

#     return validate_and_normalize_event(
#         event
#     )


# # ============================================================
# # EVIDENCE MESSAGE PROCESSING
# # ============================================================


# async def process_evidence_event(
#     redis_id: str,
#     fields: Any,
# ) -> None:
#     """
#     Process one evidence Redis message.

#     Permanent invalid payload:
#         ACK.

#     Unsupported event type:
#         ACK.

#     Successful update:
#         ACK.

#     Retryable processing failure:
#         NO ACK.

#     Unexpected processing failure:
#         NO ACK.
#     """

#     try:
#         event = parse_event(
#             fields
#         )

#         event_type = event.get(
#             "event_type"
#         )

#         if event_type not in SUPPORTED_EVIDENCE_EVENT_TYPES:
#             print(
#                 "[INCIDENT] Unsupported evidence event; "
#                 f"ACKing redis_id={redis_id} "
#                 f"type={event_type}"
#             )

#             await acknowledge_evidence(
#                 redis_id
#             )

#             return

#         result = await asyncio.to_thread(
#             update_evidence_sync,
#             event,
#         )

#         print(
#             "[INCIDENT] Evidence update | "
#             f"Action={result.get('action')} | "
#             f"Incident={result.get('incident_id')} | "
#             f"Status={result.get('evidence_status')}"
#         )

#         await acknowledge_evidence(
#             redis_id
#         )

#     except PermanentEvidenceMessageError as exc:
#         print(
#             "[INCIDENT] Permanent invalid evidence message; "
#             f"ACKing redis_id={redis_id} | "
#             f"error={exc}"
#         )

#         await acknowledge_evidence(
#             redis_id
#         )

#     except RetryableEvidenceProcessingError as exc:
#         print(
#             "[INCIDENT] Retryable evidence processing failure; "
#             f"redis_id={redis_id} | "
#             f"error={exc}"
#         )

#         # IMPORTANT:
#         #
#         # Do NOT ACK.
#         #
#         # Redis retains the message as pending so it can be
#         # retried/recovered later.
#         return

#     except ValueError as exc:
#         # Defensive fallback.
#         #
#         # A ValueError that escapes normal permanent-message
#         # handling is treated as a processing failure rather
#         # than automatically ACKed.
#         #
#         # This is safer for reliability because ACK means:
#         # "the message has been successfully handled."
#         print(
#             "[INCIDENT] Evidence processing ValueError; "
#             f"redis_id={redis_id} | "
#             f"error={exc}"
#         )

#         return

#     except asyncio.CancelledError:
#         raise

#     except Exception as exc:
#         print(
#             "[INCIDENT] Evidence processing failed; "
#             f"redis_id={redis_id} | "
#             f"{type(exc).__name__}: {exc}"
#         )

#         # IMPORTANT:
#         #
#         # Do NOT ACK.
#         #
#         # Redis retains the message as pending so it can be
#         # recovered after failure.
#         return


# # ============================================================
# # PENDING EVIDENCE RECOVERY
# # ============================================================


# async def recover_pending_evidence() -> None:
#     """
#     Recover evidence messages previously owned by this consumer.

#     XREADGROUP with ID 0-0 reads pending messages assigned to
#     this consumer.
#     """

#     while True:
#         try:
#             messages = await redis_client.xreadgroup(
#                 groupname=EVIDENCE_GROUP_NAME,
#                 consumername=EVIDENCE_CONSUMER_NAME,
#                 streams={
#                     EVIDENCE_STREAM_NAME: "0-0",
#                 },
#                 count=READ_COUNT,
#                 block=RECOVERY_BLOCK_MS,
#             )

#         except asyncio.CancelledError:
#             raise

#         except Exception as exc:
#             print(
#                 "[INCIDENT] Pending evidence recovery "
#                 "read failed: "
#                 f"{type(exc).__name__}: {exc}"
#             )

#             return

#         if not messages:
#             return

#         processed = False

#         for (
#             _stream_name,
#             stream_messages,
#         ) in messages:

#             for (
#                 redis_id,
#                 fields,
#             ) in stream_messages:

#                 processed = True

#                 try:
#                     await process_evidence_event(
#                         redis_id,
#                         fields,
#                     )

#                 except asyncio.CancelledError:
#                     raise

#                 except Exception as exc:
#                     print(
#                         "[INCIDENT] Pending evidence still failed: "
#                         f"redis_id={redis_id} | "
#                         f"{type(exc).__name__}: {exc}"
#                     )

#         if not processed:
#             return


# # ============================================================
# # STALE EVIDENCE RECOVERY
# # ============================================================


# async def recover_stale_evidence() -> None:
#     """
#     Claim stale evidence messages from failed consumers.

#     XAUTOCLAIM transfers ownership of messages whose pending
#     idle time exceeds PENDING_CLAIM_IDLE_MS.
#     """

#     try:
#         result = await redis_client.xautoclaim(
#             EVIDENCE_STREAM_NAME,
#             EVIDENCE_GROUP_NAME,
#             EVIDENCE_CONSUMER_NAME,
#             min_idle_time=PENDING_CLAIM_IDLE_MS,
#             start_id="0-0",
#             count=READ_COUNT,
#         )

#     except asyncio.CancelledError:
#         raise

#     except Exception as exc:
#         print(
#             "[INCIDENT] Evidence XAUTOCLAIM failed: "
#             f"{type(exc).__name__}: {exc}"
#         )

#         return

#     if not result or len(result) < 2:
#         return

#     # redis-py returns:
#     #
#     # (
#     #     next_start_id,
#     #     messages,
#     #     deleted_ids,
#     # )
#     #
#     # Older versions may omit deleted_ids, but messages remain
#     # at index 1.

#     claimed = result[1]

#     if not claimed:
#         return

#     print(
#         "[INCIDENT] Recovered "
#         f"{len(claimed)} stale evidence message(s)"
#     )

#     for (
#         redis_id,
#         fields,
#     ) in claimed:

#         try:
#             await process_evidence_event(
#                 redis_id,
#                 fields,
#             )

#         except asyncio.CancelledError:
#             raise

#         except Exception as exc:
#             print(
#                 "[INCIDENT] Recovered evidence failed: "
#                 f"redis_id={redis_id} | "
#                 f"{type(exc).__name__}: {exc}"
#             )


# # ============================================================
# # EVIDENCE CONSUMER LOOP
# # ============================================================


# async def evidence_consumer_loop() -> None:
#     """
#     Main evidence persistence consumer loop.

#     This consumer owns:

#         events.evidence

#     It does NOT consume:

#         events.alerts
#     """

#     await ensure_evidence_consumer_group()

#     await recover_pending_evidence()

#     print(
#         "[INCIDENT] Evidence consumer loop started | "
#         f"stream={EVIDENCE_STREAM_NAME} | "
#         f"group={EVIDENCE_GROUP_NAME} | "
#         f"consumer={EVIDENCE_CONSUMER_NAME}"
#     )

#     while True:

#         # ----------------------------------------------------
#         # Recover stale messages from failed consumers.
#         # ----------------------------------------------------

#         await recover_stale_evidence()

#         # ----------------------------------------------------
#         # Read new evidence messages.
#         # ----------------------------------------------------

#         try:
#             messages = await redis_client.xreadgroup(
#                 groupname=EVIDENCE_GROUP_NAME,
#                 consumername=EVIDENCE_CONSUMER_NAME,
#                 streams={
#                     EVIDENCE_STREAM_NAME: ">",
#                 },
#                 count=READ_COUNT,
#                 block=READ_BLOCK_MS,
#             )

#         except asyncio.CancelledError:
#             raise

#         except Exception as exc:
#             print(
#                 "[INCIDENT] Evidence XREADGROUP failed: "
#                 f"{type(exc).__name__}: {exc}"
#             )

#             await asyncio.sleep(
#                 CONSUMER_RESTART_DELAY_SECONDS
#             )

#             continue

#         if not messages:
#             continue

#         for (
#             _stream_name,
#             stream_messages,
#         ) in messages:

#             for (
#                 redis_id,
#                 fields,
#             ) in stream_messages:

#                 try:
#                     await process_evidence_event(
#                         redis_id,
#                         fields,
#                     )

#                 except asyncio.CancelledError:
#                     raise

#                 except Exception as exc:
#                     print(
#                         "[INCIDENT] Evidence message remains pending: "
#                         f"redis_id={redis_id} | "
#                         f"{type(exc).__name__}: {exc}"
#                     )


# # ============================================================
# # UNIFIED CONSUMER SERVICE
# # ============================================================


# async def consume_events() -> None:
#     """
#     Run the evidence persistence consumer.

#     IMPORTANT ARCHITECTURAL OWNERSHIP:

#         events.alerts
#             -> agents.incident.main

#         events.evidence
#             -> this module

#     Therefore this function intentionally does NOT start
#     an alert consumer.
#     """

#     # --------------------------------------------------------
#     # Database initialization.
#     # --------------------------------------------------------

#     await asyncio.to_thread(
#         ensure_incidents_table
#     )

#     # --------------------------------------------------------
#     # Ensure evidence group.
#     # --------------------------------------------------------

#     await ensure_evidence_consumer_group()

#     # --------------------------------------------------------
#     # Start evidence persistence consumer.
#     # --------------------------------------------------------

#     evidence_task = asyncio.create_task(
#         evidence_consumer_loop(),
#         name="incident-evidence-consumer",
#     )

#     print(
#         "[INCIDENT] Evidence persistence service started."
#     )

#     try:
#         await evidence_task

#     except asyncio.CancelledError:
#         evidence_task.cancel()

#         await asyncio.gather(
#             evidence_task,
#             return_exceptions=True,
#         )

#         raise

#     except Exception as exc:
#         print(
#             "[INCIDENT] Evidence consumer service failed: "
#             f"{type(exc).__name__}: {exc}"
#         )

#         raise

#     finally:
#         if not evidence_task.done():
#             evidence_task.cancel()

#         await asyncio.gather(
#             evidence_task,
#             return_exceptions=True,
#         )

#         print(
#             "[INCIDENT] Evidence persistence service stopped."
#         )


# # ============================================================
# # DIRECT EXECUTION
# # ============================================================


# if __name__ == "__main__":
#     asyncio.run(
#         consume_events()
#     )


























"""
Reliable Redis Stream consumers and incident persistence.

Responsibilities
----------------

- Provide canonical incident database persistence helpers.
- Create/update incidents in SQLite.
- Consume canonical evidence.generated/evidence.failed events.
- Link evidence results back to incidents.
- Validate canonical events before processing.
- ACK Redis evidence messages only after successful processing.
- Recover pending evidence messages after restart.
- Claim stale evidence messages from failed consumers.
- Isolate malformed/failed evidence messages.

Non-responsibilities
--------------------

- Consuming alert.created events.
- Alert -> incident orchestration.
- Agent supervision.
- Camera processing.
- Object detection.
- Evidence generation.
- API-facing Redis stream queries.

Alert -> incident orchestration belongs to:

    agents.incident.main

API-facing Redis event queries belong to:

    backend.app.messaging.event_consumer

Evidence generation belongs to:

    agents.evidence.main
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.app.incidents.paths import incident_database_path
from backend.app.messaging.redis_client import redis_client
from shared.schemas.event_schema import validate_event


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

DATABASE_PATH = incident_database_path()

STREAM_NAME = (
    os.getenv(
        "ALERT_INPUT_STREAM",
        "events.alerts",
    ).strip()
    or "events.alerts"
)

GROUP_NAME = (
    os.getenv(
        "ALERT_CONSUMER_GROUP",
        "incident-workers",
    ).strip()
    or "incident-workers"
)


# ============================================================
# EVIDENCE STREAM CONFIGURATION
# ============================================================

EVIDENCE_STREAM_NAME = (
    os.getenv(
        "INCIDENT_EVIDENCE_INPUT_STREAM",
        "events.evidence",
    ).strip()
    or "events.evidence"
)

EVIDENCE_GROUP_NAME = (
    os.getenv(
        "INCIDENT_EVIDENCE_GROUP",
        "incident-evidence-workers",
    ).strip()
    or "incident-evidence-workers"
)

EVIDENCE_CONSUMER_NAME = (
    os.getenv(
        "INCIDENT_EVIDENCE_CONSUMER_NAME",
        f"incident-evidence-{socket.gethostname()}-{uuid.uuid4().hex[:8]}",
    ).strip()
    or f"incident-evidence-{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
)

SUPPORTED_EVIDENCE_EVENT_TYPES = {
    "evidence.generated",
    "evidence.failed",
}


# ============================================================
# DEFAULTS
# ============================================================

DEFAULT_STATUS = "OPEN"
DEFAULT_EVIDENCE_STATUS = "PENDING"

PENDING_CLAIM_IDLE_MS = max(
    1000,
    int(
        os.getenv(
            "INCIDENT_PENDING_CLAIM_IDLE_MS",
            "120000",
        )
    ),
)

READ_COUNT = max(
    1,
    int(
        os.getenv(
            "INCIDENT_READ_COUNT",
            "10",
        )
    ),
)

READ_BLOCK_MS = max(
    100,
    int(
        os.getenv(
            "INCIDENT_READ_BLOCK_MS",
            "5000",
        )
    ),
)

RECOVERY_BLOCK_MS = max(
    100,
    int(
        os.getenv(
            "INCIDENT_RECOVERY_BLOCK_MS",
            "1000",
        )
    ),
)

CONSUMER_RESTART_DELAY_SECONDS = max(
    0.1,
    float(
        os.getenv(
            "INCIDENT_CONSUMER_RESTART_DELAY_SECONDS",
            "2",
        )
    ),
)


# ============================================================
# INTERNAL EXCEPTIONS
# ============================================================


class RetryableEvidenceProcessingError(Exception):
    """
    Indicates that an evidence message should remain pending.

    Examples:

    - Incident has not been persisted yet.
    - Temporary database problem.
    - Temporary dependency failure.

    The Redis message must NOT be ACKed.
    """


class PermanentEvidenceMessageError(ValueError):
    """
    Indicates that an evidence message is permanently invalid.

    These messages may safely be ACKed so malformed data does
    not poison the consumer indefinitely.
    """


# ============================================================
# DATABASE
# ============================================================


def get_database_connection() -> sqlite3.Connection:
    """
    Open a SQLite connection configured for concurrent workers.

    WAL allows readers and writers to coexist more effectively.
    busy_timeout reduces transient database-lock failures.
    foreign_keys enables SQLite foreign-key enforcement.
    """

    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    conn = sqlite3.connect(
        str(DATABASE_PATH),
        timeout=10,
    )

    conn.row_factory = sqlite3.Row

    conn.execute(
        "PRAGMA journal_mode=WAL"
    )

    conn.execute(
        "PRAGMA busy_timeout=10000"
    )

    conn.execute(
        "PRAGMA foreign_keys=ON"
    )

    return conn


def ensure_incidents_table() -> None:
    """
    Create or migrate the canonical incidents table.

    This function is synchronous intentionally.

    Async callers should use:

        await asyncio.to_thread(
            ensure_incidents_table
        )
    """

    conn = get_database_connection()

    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS incidents (
                incident_id TEXT PRIMARY KEY,
                alert_event_id TEXT UNIQUE NOT NULL,
                event_id TEXT,
                camera_id TEXT,
                event_type TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                mode TEXT,
                trace_id TEXT,
                correlation_id TEXT,
                source_agent_id TEXT,
                source_instance_id TEXT,
                source_hostname TEXT,
                source_redis_id TEXT,
                person_count INTEGER,
                threshold REAL,
                frame_id TEXT,
                frame_timestamp REAL,
                track_ids TEXT,
                message TEXT,
                status TEXT NOT NULL DEFAULT 'OPEN',
                evidence_status TEXT NOT NULL DEFAULT 'PENDING',
                evidence_type TEXT,
                evidence_event_id TEXT,
                proof_path TEXT,
                proof_filename TEXT,
                source_video TEXT,
                video_id TEXT,
                start_time TEXT,
                end_time TEXT,
                evidence_duration REAL,
                evidence_reason TEXT,
                evidence_updated_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(incidents)"
            ).fetchall()
        }

        # --------------------------------------------------------
        # Safe additive migrations.
        # --------------------------------------------------------

        migrations: dict[str, str] = {
            "event_id": "TEXT",
            "camera_id": "TEXT",
            "event_type": "TEXT",
            "mode": "TEXT",
            "trace_id": "TEXT",
            "correlation_id": "TEXT",
            "source_agent_id": "TEXT",
            "source_instance_id": "TEXT",
            "source_hostname": "TEXT",
            "source_redis_id": "TEXT",
            "person_count": "INTEGER",
            "threshold": "REAL",
            "frame_id": "TEXT",
            "frame_timestamp": "REAL",
            "track_ids": "TEXT",
            "message": "TEXT",
            "source_video": "TEXT",
            "video_id": "TEXT",
            "start_time": "TEXT",
            "end_time": "TEXT",
            "evidence_status": "TEXT",
            "evidence_type": "TEXT",
            "evidence_event_id": "TEXT",
            "proof_path": "TEXT",
            "proof_filename": "TEXT",
            "evidence_duration": "REAL",
            "evidence_reason": "TEXT",
            "evidence_updated_at": "TEXT",
            "created_at": "TEXT",
            "updated_at": "TEXT",
        }

        for column, definition in migrations.items():
            if column not in columns:
                conn.execute(
                    f"""
                    ALTER TABLE incidents
                    ADD COLUMN {column} {definition}
                    """
                )

        # --------------------------------------------------------
        # Backfill timestamps.
        # --------------------------------------------------------

        now = datetime.now(
            timezone.utc
        ).isoformat()

        conn.execute(
            """
            UPDATE incidents
            SET created_at = COALESCE(
                created_at,
                ?
            )
            WHERE created_at IS NULL
            """,
            (now,),
        )

        conn.execute(
            """
            UPDATE incidents
            SET updated_at = COALESCE(
                updated_at,
                created_at,
                ?
            )
            WHERE updated_at IS NULL
            """,
            (now,),
        )

        conn.execute(
            """
            UPDATE incidents
            SET event_type = COALESCE(
                event_type,
                'alert.created'
            )
            WHERE event_type IS NULL
            """
        )

        conn.execute(
            """
            UPDATE incidents
            SET evidence_status = COALESCE(
                evidence_status,
                ?
            )
            WHERE evidence_status IS NULL
            """,
            (DEFAULT_EVIDENCE_STATUS,),
        )

        # --------------------------------------------------------
        # Indexes.
        # --------------------------------------------------------

        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_incidents_alert_event_id
            ON incidents(alert_event_id)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_incidents_event_id
            ON incidents(event_id)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_incidents_camera_id
            ON incidents(camera_id)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_incidents_status
            ON incidents(status)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_incidents_severity
            ON incidents(severity)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_incidents_evidence_status
            ON incidents(evidence_status)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_incidents_start_time
            ON incidents(start_time)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_incidents_trace_id
            ON incidents(trace_id)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_incidents_correlation_id
            ON incidents(correlation_id)
            """
        )

        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_incidents_evidence_event_id
            ON incidents(evidence_event_id)
            WHERE evidence_event_id IS NOT NULL
            """
        )

        conn.commit()

    finally:
        conn.close()


# ============================================================
# TIMESTAMP HELPERS
# ============================================================


def parse_timestamp(
    value: Any,
) -> str | None:
    """
    Parse an ISO timestamp and normalize it to UTC.

    Numeric values are intentionally not interpreted as
    wall-clock timestamps.
    """

    if value is None:
        return None

    if isinstance(
        value,
        datetime,
    ):
        dt = value

    elif isinstance(
        value,
        str,
    ):
        value = value.strip()

        if not value:
            return None

        try:
            normalized = value

            if normalized.endswith("Z"):
                normalized = (
                    normalized[:-1]
                    + "+00:00"
                )

            dt = datetime.fromisoformat(
                normalized
            )

        except ValueError:
            return None

    else:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(
            tzinfo=timezone.utc
        )

    dt = dt.astimezone(
        timezone.utc
    )

    return dt.isoformat()


def get_event_time(
    event: dict[str, Any],
) -> str:
    """
    Determine wall-clock event time.

    Priority:

        data.event_timestamp
        data.frame_datetime
        event.timestamp
        current UTC time

    Numeric frame_timestamp/event_time values are treated
    as video-relative values and are not converted to
    wall-clock timestamps.
    """

    data = event.get(
        "data",
        {},
    )

    if isinstance(
        data,
        dict,
    ):
        for key in (
            "event_timestamp",
            "frame_datetime",
        ):
            parsed = parse_timestamp(
                data.get(key)
            )

            if parsed:
                return parsed

    parsed = parse_timestamp(
        event.get("timestamp")
    )

    if parsed:
        return parsed

    return datetime.now(
        timezone.utc
    ).isoformat()


# ============================================================
# TYPE HELPERS
# ============================================================


def safe_int(
    value: Any,
) -> int | None:

    if value is None:
        return None

    try:
        return int(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


def safe_float(
    value: Any,
) -> float | None:

    if value is None:
        return None

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


def normalize_track_ids(
    value: Any,
) -> list[str]:

    if value is None:
        return []

    if isinstance(
        value,
        (
            list,
            tuple,
            set,
        ),
    ):
        return [
            str(item)
            for item in value
            if item is not None
        ]

    return [str(value)]


# ============================================================
# EVENT VALIDATION / NORMALIZATION
# ============================================================


def convert_validated_event(
    validated_event: Any,
) -> dict[str, Any]:
    """
    Convert the result of validate_event() into a dictionary.

    Supports both older/custom validators and Pydantic-style
    model_dump().
    """

    if hasattr(
        validated_event,
        "to_dict",
    ):
        result = validated_event.to_dict()

    elif hasattr(
        validated_event,
        "model_dump",
    ):
        result = validated_event.model_dump(
            mode="json"
        )

    elif isinstance(
        validated_event,
        dict,
    ):
        result = validated_event

    else:
        raise PermanentEvidenceMessageError(
            "Validated event has unsupported type"
        )

    if not isinstance(
        result,
        dict,
    ):
        raise PermanentEvidenceMessageError(
            "Validated event is not an object"
        )

    return result


def validate_and_normalize_event(
    event: Any,
) -> dict[str, Any]:
    """
    Validate and normalize a canonical event.

    Validation failures are considered permanent message
    failures and should be ACKed by the Redis consumer.
    """

    if not isinstance(
        event,
        dict,
    ):
        raise PermanentEvidenceMessageError(
            "Event must be a dictionary"
        )

    try:
        validated_event = validate_event(
            event
        )

    except Exception as exc:
        raise PermanentEvidenceMessageError(
            f"Event validation failed: {exc}"
        ) from exc

    return convert_validated_event(
        validated_event
    )


# ============================================================
# INCIDENT CREATION
# ============================================================


def create_incident_sync(
    event: dict[str, Any],
) -> dict[str, Any]:
    """
    Create an incident from a canonical alert.created event.

    This function is called by:

        agents.incident.main

    It is NOT called by the Redis evidence consumer service.

    Idempotency is based on alert_event_id.
    """

    if not isinstance(
        event,
        dict,
    ):
        raise ValueError(
            "Event must be a dictionary"
        )

    event = validate_and_normalize_event(
        event
    )

    event_type = event.get(
        "event_type"
    )

    if event_type != "alert.created":
        raise ValueError(
            f"Unsupported event type: {event_type}"
        )

    event_id = event.get(
        "event_id"
    )

    if not event_id:
        raise ValueError(
            "Alert event is missing event_id"
        )

    camera = event.get(
        "camera",
        {},
    )

    if not isinstance(
        camera,
        dict,
    ):
        camera = {}

    context = event.get(
        "context",
        {},
    )

    if not isinstance(
        context,
        dict,
    ):
        context = {}

    data = event.get(
        "data",
        {},
    )

    if not isinstance(
        data,
        dict,
    ):
        raise ValueError(
            "Alert event data must be an object"
        )

    source = event.get(
        "source",
        {},
    )

    if not isinstance(
        source,
        dict,
    ):
        source = {}

    incident_id = (
        context.get("incident_id")
        or str(uuid.uuid4())
    )

    camera_id = camera.get(
        "camera_id"
    )

    alert_type = str(
        data.get(
            "alert_type",
            "unknown",
        )
    )

    severity = str(
        data.get(
            "severity",
            "medium",
        )
    )

    mode = context.get(
        "mode"
    )

    trace_id = context.get(
        "trace_id"
    )

    correlation_id = context.get(
        "correlation_id"
    )

    source_agent_id = source.get(
        "agent_id"
    )

    source_instance_id = source.get(
        "instance_id"
    )

    source_hostname = source.get(
        "hostname"
    )

    source_redis_id = source.get(
        "redis_id"
    )

    person_count = safe_int(
        data.get(
            "person_count"
        )
    )

    threshold = safe_float(
        data.get(
            "threshold"
        )
    )

    frame_id_value = data.get("frame_id")
    frame_id = (
        str(frame_id_value)
        if frame_id_value is not None
        else None
    )

    frame_timestamp_value = data.get("frame_timestamp")
    frame_timestamp = (
        str(frame_timestamp_value)
        if frame_timestamp_value is not None
        else None
    )

    if frame_timestamp is None:
        event_time_value = data.get("event_time")
        frame_timestamp = (
            str(event_time_value)
            if event_time_value is not None
            else None
        )

    track_ids = normalize_track_ids(
        data.get(
            "track_ids"
        )
    )

    message = data.get(
        "message"
    )

    source_video = data.get(
        "source_video"
    )

    video_id = data.get(
        "video_id"
    )

    event_time = get_event_time(
        event
    )

    now = datetime.now(
        timezone.utc
    ).isoformat()

    conn = get_database_connection()

    try:
        # --------------------------------------------------------
        # Idempotency lookup.
        # --------------------------------------------------------

        existing = conn.execute(
            """
            SELECT
                incident_id,
                alert_event_id,
                event_id,
                alert_type,
                severity,
                camera_id,
                status,
                evidence_status,
                proof_path,
                evidence_event_id,
                source_video,
                video_id,
                start_time,
                end_time,
                evidence_duration,
                evidence_reason,
                evidence_updated_at,
                created_at,
                updated_at
            FROM incidents
            WHERE alert_event_id = ?
            """,
            (event_id,),
        ).fetchone()

        if existing:
            existing_incident_id = existing[
                "incident_id"
            ]

            conn.execute(
                """
                UPDATE incidents
                SET
                    source_video = COALESCE(
                        source_video,
                        ?
                    ),
                    video_id = COALESCE(
                        video_id,
                        ?
                    ),
                    source_redis_id = COALESCE(
                        source_redis_id,
                        ?
                    ),
                    updated_at = ?
                WHERE incident_id = ?
                """,
                (
                    source_video,
                    video_id,
                    source_redis_id,
                    now,
                    existing_incident_id,
                ),
            )

            conn.commit()

            return {
                "action": "UPDATED",
                "incident_id": existing_incident_id,
                "alert_event_id": event_id,
                "camera_id": existing[
                    "camera_id"
                ],
                "alert_type": existing[
                    "alert_type"
                ],
                "severity": existing[
                    "severity"
                ],
                "person_count": person_count,
                "evidence_status": existing[
                    "evidence_status"
                ],
            }

        # --------------------------------------------------------
        # Insert.
        # --------------------------------------------------------

        try:
            conn.execute(
                """
                INSERT INTO incidents (
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
                    source_hostname,
                    source_redis_id,
                    person_count,
                    threshold,
                    frame_id,
                    frame_timestamp,
                    track_ids,
                    message,
                    status,
                    evidence_status,
                    source_video,
                    video_id,
                    start_time,
                    end_time,
                    created_at,
                    updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    incident_id,
                    event_id,
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
                    source_hostname,
                    source_redis_id,
                    person_count,
                    threshold,
                    frame_id,
                    frame_timestamp,
                    json.dumps(track_ids),
                    message,
                    DEFAULT_STATUS,
                    DEFAULT_EVIDENCE_STATUS,
                    source_video,
                    video_id,
                    event_time,
                    event_time,
                    now,
                    now,
                ),
            )

            conn.commit()

        except sqlite3.IntegrityError:
            conn.rollback()

            existing = conn.execute(
                """
                SELECT
                    incident_id,
                    alert_event_id,
                    alert_type,
                    severity,
                    camera_id,
                    status,
                    evidence_status
                FROM incidents
                WHERE alert_event_id = ?
                """,
                (event_id,),
            ).fetchone()

            if not existing:
                raise

            return {
                "action": "UPDATED",
                "incident_id": existing[
                    "incident_id"
                ],
                "alert_event_id": event_id,
                "camera_id": existing[
                    "camera_id"
                ],
                "alert_type": existing[
                    "alert_type"
                ],
                "severity": existing[
                    "severity"
                ],
                "person_count": person_count,
                "evidence_status": existing[
                    "evidence_status"
                ],
            }

        return {
            "action": "CREATED",
            "incident_id": incident_id,
            "alert_event_id": event_id,
            "camera_id": camera_id,
            "alert_type": alert_type,
            "severity": severity,
            "person_count": person_count,
            "evidence_status": DEFAULT_EVIDENCE_STATUS,
        }

    finally:
        conn.close()


async def create_incident(
    event: dict[str, Any],
) -> dict[str, Any]:
    return await asyncio.to_thread(
        create_incident_sync,
        event,
    )


async def acknowledge(
    redis_id: str,
) -> None:
    await redis_client.xack(
        STREAM_NAME,
        GROUP_NAME,
        redis_id,
    )


async def process_event(
    redis_id: str,
    fields: Any,
) -> None:
    normalized = normalize_fields(fields)
    raw_event = normalized.get("event")

    try:
        if not raw_event:
            raise ValueError("Redis message is missing 'event'.")

        event = json.loads(raw_event)
        event_type = event.get("event_type")

        if event_type != "alert.created":
            await acknowledge(redis_id)
            return

        await create_incident(event)
        await acknowledge(redis_id)

    except json.JSONDecodeError:
        await acknowledge(redis_id)
        return


# ============================================================
# EVIDENCE UPDATE
# ============================================================


def update_evidence_sync(
    event: dict[str, Any],
) -> dict[str, Any]:
    """
    Apply an evidence.generated/evidence.failed event.

    The incident_id is taken from:

        event.context.incident_id

    A completed evidence result cannot later be downgraded
    by a stale failure event.

    If the incident does not yet exist, this function raises
    RetryableEvidenceProcessingError rather than ValueError.

    This prevents evidence from being ACKed and lost when
    incident persistence and evidence generation race each other.
    """

    if not isinstance(
        event,
        dict,
    ):
        raise PermanentEvidenceMessageError(
            "Evidence event must be a dictionary"
        )

    # Event has already been validated by parse_event().
    event_type = event.get(
        "event_type"
    )

    if event_type not in SUPPORTED_EVIDENCE_EVENT_TYPES:
        raise PermanentEvidenceMessageError(
            f"Unsupported evidence event type: {event_type}"
        )

    context = event.get(
        "context",
        {},
    )

    if not isinstance(
        context,
        dict,
    ):
        context = {}

    incident_id = context.get(
        "incident_id"
    )

    if not incident_id:
        raise PermanentEvidenceMessageError(
            "Evidence event is missing "
            "context.incident_id"
        )

    data = event.get(
        "data",
        {},
    )

    if not isinstance(
        data,
        dict,
    ):
        raise PermanentEvidenceMessageError(
            "Evidence event data must be an object"
        )

    evidence_event_id = event.get(
        "event_id"
    )

    if not evidence_event_id:
        raise PermanentEvidenceMessageError(
            "Evidence event is missing event_id"
        )

    # --------------------------------------------------------
    # Determine final evidence status.
    # --------------------------------------------------------

    raw_status = str(
        data.get(
            "status",
            "",
        )
    ).strip().upper()

    if event_type == "evidence.generated":
        status = (
            "FAILED"
            if raw_status
            in {
                "FAILED",
                "ERROR",
            }
            else "COMPLETED"
        )
    else:
        status = "FAILED"

    # --------------------------------------------------------
    # Evidence metadata.
    # --------------------------------------------------------

    evidence_type = data.get(
        "evidence_type"
    )

    proof_path = data.get(
        "proof_path"
    )

    proof_filename = data.get(
        "proof_filename"
    )

    source_video = data.get(
        "source_video"
    )

    video_id = data.get(
        "video_id"
    )

    evidence_duration = safe_float(
        data.get(
            "evidence_duration"
        )
    )

    if evidence_duration is None:
        evidence_duration = safe_float(
            data.get(
                "duration"
            )
        )

    start_time = data.get(
        "start_time"
    )

    end_time = data.get(
        "end_time"
    )

    if start_time is not None:
        start_time = str(start_time)

    if end_time is not None:
        end_time = str(end_time)

    evidence_reason = data.get(
        "reason"
    )

    if evidence_reason is None:
        evidence_reason = data.get(
            "error"
        )

    if evidence_reason is not None:
        evidence_reason = str(
            evidence_reason
        )

    now = datetime.now(
        timezone.utc
    ).isoformat()

    conn = get_database_connection()

    try:
        # ----------------------------------------------------
        # Explicit transaction.
        # ----------------------------------------------------

        conn.execute(
            "BEGIN IMMEDIATE"
        )

        incident = conn.execute(
            """
            SELECT
                incident_id,
                evidence_status,
                evidence_event_id,
                evidence_type,
                proof_path,
                proof_filename,
                source_video,
                video_id,
                start_time,
                end_time,
                evidence_duration,
                evidence_reason,
                evidence_updated_at
            FROM incidents
            WHERE incident_id = ?
            """,
            (incident_id,),
        ).fetchone()

        # ----------------------------------------------------
        # Incident-not-found is retryable.
        # ----------------------------------------------------

        if not incident:
            conn.rollback()

            raise RetryableEvidenceProcessingError(
                f"Incident not found yet: {incident_id}"
            )

        current_status = str(
            incident["evidence_status"]
            or DEFAULT_EVIDENCE_STATUS
        ).upper()

        # ----------------------------------------------------
        # Same evidence event already applied.
        # ----------------------------------------------------

        if (
            incident["evidence_event_id"]
            == evidence_event_id
        ):
            conn.commit()

            return {
                "action": "DUPLICATE",
                "incident_id": incident_id,
                "evidence_event_id": evidence_event_id,
                "evidence_status": current_status,
            }

        # ----------------------------------------------------
        # Never downgrade completed evidence.
        # ----------------------------------------------------

        if (
            current_status == "COMPLETED"
            and status == "FAILED"
        ):
            conn.execute(
                """
                UPDATE incidents
                SET
                    updated_at = ?
                WHERE incident_id = ?
                """,
                (
                    now,
                    incident_id,
                ),
            )

            conn.commit()

            return {
                "action": "IGNORED_DOWNGRADE",
                "incident_id": incident_id,
                "evidence_event_id": evidence_event_id,
                "evidence_status": current_status,
            }

        # ----------------------------------------------------
        # Apply complete evidence result.
        # ----------------------------------------------------

        conn.execute(
            """
            UPDATE incidents
            SET
                evidence_status = ?,

                evidence_type = COALESCE(
                    ?,
                    evidence_type
                ),

                evidence_event_id = ?,

                proof_path = COALESCE(
                    ?,
                    proof_path
                ),

                proof_filename = COALESCE(
                    ?,
                    proof_filename
                ),

                source_video = COALESCE(
                    ?,
                    source_video
                ),

                video_id = COALESCE(
                    ?,
                    video_id
                ),

                start_time = COALESCE(
                    ?,
                    start_time
                ),

                end_time = COALESCE(
                    ?,
                    end_time
                ),

                evidence_duration = COALESCE(
                    ?,
                    evidence_duration
                ),

                evidence_reason = ?,

                evidence_updated_at = ?,

                updated_at = ?

            WHERE incident_id = ?
            """,
            (
                status,
                evidence_type,
                evidence_event_id,
                proof_path,
                proof_filename,
                source_video,
                video_id,
                start_time,
                end_time,
                evidence_duration,
                evidence_reason,
                now,
                now,
                incident_id,
            ),
        )

        conn.commit()

        return {
            "action": "UPDATED",
            "incident_id": incident_id,
            "evidence_event_id": evidence_event_id,
            "evidence_status": status,
            "evidence_type": evidence_type,
            "proof_path": proof_path,
            "proof_filename": proof_filename,
            "source_video": source_video,
            "video_id": video_id,
            "start_time": start_time,
            "end_time": end_time,
            "evidence_duration": evidence_duration,
            "evidence_reason": evidence_reason,
        }

    except RetryableEvidenceProcessingError:
        conn.rollback()
        raise

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# ============================================================
# REDIS GROUP MANAGEMENT
# ============================================================


async def ensure_evidence_consumer_group() -> None:
    """
    Ensure the evidence persistence consumer group exists.
    """

    try:
        await redis_client.xgroup_create(
            name=EVIDENCE_STREAM_NAME,
            groupname=EVIDENCE_GROUP_NAME,
            id="0-0",
            mkstream=True,
        )

        print(
            "[INCIDENT] Created evidence consumer group "
            f"{EVIDENCE_GROUP_NAME} for "
            f"{EVIDENCE_STREAM_NAME}"
        )

    except Exception as exc:
        if "BUSYGROUP" in str(exc):
            return

        raise


# ============================================================
# EVIDENCE ACK
# ============================================================


async def acknowledge_evidence(
    redis_id: str,
) -> None:
    """
    ACK only after successful processing or permanent rejection.
    """

    await redis_client.xack(
        EVIDENCE_STREAM_NAME,
        EVIDENCE_GROUP_NAME,
        redis_id,
    )


# ============================================================
# EVENT NORMALIZATION
# ============================================================


def normalize_fields(
    fields: Any,
) -> dict[str, Any]:
    """
    Normalize Redis stream field keys and values.

    Redis clients may return bytes depending on configuration.
    """

    if not isinstance(
        fields,
        dict,
    ):
        return {}

    normalized: dict[str, Any] = {}

    for key, value in fields.items():

        if isinstance(
            key,
            bytes,
        ):
            key = key.decode(
                "utf-8",
                errors="replace",
            )

        if isinstance(
            value,
            bytes,
        ):
            value = value.decode(
                "utf-8",
                errors="replace",
            )

        normalized[key] = value

    return normalized


def parse_event(
    fields: Any,
) -> dict[str, Any]:
    """
    Parse and validate a Redis stream message.

    Validation happens exactly once on the Redis-consumer path.
    """

    normalized = normalize_fields(
        fields
    )

    raw_event = normalized.get(
        "event"
    )

    if raw_event is None:
        raise PermanentEvidenceMessageError(
            "Redis message missing event field"
        )

    if isinstance(
        raw_event,
        bytes,
    ):
        raw_event = raw_event.decode(
            "utf-8",
            errors="replace",
        )

    if isinstance(
        raw_event,
        str,
    ):
        try:
            event = json.loads(
                raw_event
            )

        except json.JSONDecodeError as exc:
            raise PermanentEvidenceMessageError(
                f"Invalid event JSON: {exc}"
            ) from exc

    elif isinstance(
        raw_event,
        dict,
    ):
        event = raw_event

    else:
        raise PermanentEvidenceMessageError(
            "Redis event must be JSON string or object"
        )

    if not isinstance(
        event,
        dict,
    ):
        raise PermanentEvidenceMessageError(
            "Canonical event must be an object"
        )

    return validate_and_normalize_event(
        event
    )


# ============================================================
# EVIDENCE MESSAGE PROCESSING
# ============================================================


async def process_evidence_event(
    redis_id: str,
    fields: Any,
) -> None:
    """
    Process one evidence Redis message.

    Permanent invalid payload:
        ACK.

    Unsupported event type:
        ACK.

    Successful update:
        ACK.

    Retryable processing failure:
        NO ACK.

    Unexpected processing failure:
        NO ACK.
    """

    try:
        event = parse_event(
            fields
        )

        event_type = event.get(
            "event_type"
        )

        if event_type not in SUPPORTED_EVIDENCE_EVENT_TYPES:
            print(
                "[INCIDENT] Unsupported evidence event; "
                f"ACKing redis_id={redis_id} "
                f"type={event_type}"
            )

            await acknowledge_evidence(
                redis_id
            )

            return

        result = await asyncio.to_thread(
            update_evidence_sync,
            event,
        )

        print(
            "[INCIDENT] Evidence update | "
            f"Action={result.get('action')} | "
            f"Incident={result.get('incident_id')} | "
            f"Status={result.get('evidence_status')}"
        )

        await acknowledge_evidence(
            redis_id
        )

    except PermanentEvidenceMessageError as exc:

        print(
            "[INCIDENT] Permanent invalid evidence message; "
            f"ACKing redis_id={redis_id} | "
            f"error={exc}"
        )

        await acknowledge_evidence(
            redis_id
        )

    except RetryableEvidenceProcessingError as exc:

        print(
            "[INCIDENT] Retryable evidence processing failure; "
            f"redis_id={redis_id} | "
            f"error={exc}"
        )

        # DO NOT ACK.
        #
        # Redis keeps the message pending so it can be retried
        # or claimed by another healthy consumer.

        return

    except asyncio.CancelledError:
        raise

    except Exception as exc:

        print(
            "[INCIDENT] Evidence processing failed; "
            f"redis_id={redis_id} | "
            f"{type(exc).__name__}: {exc}"
        )

        # DO NOT ACK.
        #
        # Unexpected failures remain pending for recovery.

        return


# ============================================================
# PENDING EVIDENCE RECOVERY
# ============================================================


async def recover_pending_evidence() -> None:
    """
    Recover evidence messages previously owned by THIS consumer.

    XREADGROUP with ID 0-0 reads pending messages assigned to
    this consumer.

    Once this consumer's own pending entries are exhausted,
    the function returns.

    Redis consumer-group semantics intentionally keep unacked
    messages in the Pending Entries List (PEL).
    """

    while True:

        try:
            messages = await redis_client.xreadgroup(
                groupname=EVIDENCE_GROUP_NAME,
                consumername=EVIDENCE_CONSUMER_NAME,
                streams={
                    EVIDENCE_STREAM_NAME: "0-0",
                },
                count=READ_COUNT,
                block=RECOVERY_BLOCK_MS,
            )

        except asyncio.CancelledError:
            raise

        except Exception as exc:

            print(
                "[INCIDENT] Pending evidence recovery "
                "read failed: "
                f"{type(exc).__name__}: {exc}"
            )

            return

        if not messages:
            return

        processed = False

        for (
            _stream_name,
            stream_messages,
        ) in messages:

            for (
                redis_id,
                fields,
            ) in stream_messages:

                processed = True

                try:
                    await process_evidence_event(
                        redis_id,
                        fields,
                    )

                except asyncio.CancelledError:
                    raise

                except Exception as exc:

                    print(
                        "[INCIDENT] Pending evidence still failed: "
                        f"redis_id={redis_id} | "
                        f"{type(exc).__name__}: {exc}"
                    )

        if not processed:
            return


# ============================================================
# STALE EVIDENCE RECOVERY
# ============================================================


async def recover_stale_evidence() -> None:
    """
    Claim stale evidence messages from failed consumers.

    IMPORTANT:

    XAUTOCLAIM returns a cursor. We must continue scanning using
    that cursor until the scan reaches 0-0, otherwise a large
    Pending Entries List may not be fully examined.

    The messages are then processed by this healthy consumer.
    """

    cursor = "0-0"

    while True:

        try:
            result = await redis_client.xautoclaim(
                EVIDENCE_STREAM_NAME,
                EVIDENCE_GROUP_NAME,
                EVIDENCE_CONSUMER_NAME,
                min_idle_time=PENDING_CLAIM_IDLE_MS,
                start_id=cursor,
                count=READ_COUNT,
            )

        except asyncio.CancelledError:
            raise

        except Exception as exc:

            print(
                "[INCIDENT] Evidence XAUTOCLAIM failed: "
                f"{type(exc).__name__}: {exc}"
            )

            return

        if not result or len(result) < 2:
            return

        next_cursor = result[0]
        claimed = result[1]

        if claimed:
            print(
                "[INCIDENT] Recovered "
                f"{len(claimed)} stale evidence message(s)"
            )

            for (
                redis_id,
                fields,
            ) in claimed:

                try:
                    await process_evidence_event(
                        redis_id,
                        fields,
                    )

                except asyncio.CancelledError:
                    raise

                except Exception as exc:

                    print(
                        "[INCIDENT] Recovered evidence failed: "
                        f"redis_id={redis_id} | "
                        f"{type(exc).__name__}: {exc}"
                    )

        # Redis signals that the scan is complete by returning
        # 0-0 as the next cursor.
        if next_cursor in (
            "0-0",
            b"0-0",
        ):
            return

        cursor = next_cursor


# ============================================================
# EVIDENCE CONSUMER LOOP
# ============================================================


async def evidence_consumer_loop() -> None:
    """
    Main evidence persistence consumer loop.

    This consumer owns:

        events.evidence

    It does NOT consume:

        events.alerts
    """

    await ensure_evidence_consumer_group()

    # Recover messages that were pending under this consumer
    # before a previous process shutdown/restart.
    await recover_pending_evidence()

    print(
        "[INCIDENT] Evidence consumer loop started | "
        f"stream={EVIDENCE_STREAM_NAME} | "
        f"group={EVIDENCE_GROUP_NAME} | "
        f"consumer={EVIDENCE_CONSUMER_NAME}"
    )

    while True:

        # ----------------------------------------------------
        # Recover stale messages from failed consumers.
        # ----------------------------------------------------

        await recover_stale_evidence()

        # ----------------------------------------------------
        # Read new evidence messages.
        # ----------------------------------------------------

        try:
            messages = await redis_client.xreadgroup(
                groupname=EVIDENCE_GROUP_NAME,
                consumername=EVIDENCE_CONSUMER_NAME,
                streams={
                    EVIDENCE_STREAM_NAME: ">",
                },
                count=READ_COUNT,
                block=READ_BLOCK_MS,
            )

        except asyncio.CancelledError:
            raise

        except Exception as exc:

            print(
                "[INCIDENT] Evidence XREADGROUP failed: "
                f"{type(exc).__name__}: {exc}"
            )

            await asyncio.sleep(
                CONSUMER_RESTART_DELAY_SECONDS
            )

            continue

        if not messages:
            continue

        for (
            _stream_name,
            stream_messages,
        ) in messages:

            for (
                redis_id,
                fields,
            ) in stream_messages:

                try:
                    await process_evidence_event(
                        redis_id,
                        fields,
                    )

                except asyncio.CancelledError:
                    raise

                except Exception as exc:

                    print(
                        "[INCIDENT] Evidence message remains pending: "
                        f"redis_id={redis_id} | "
                        f"{type(exc).__name__}: {exc}"
                    )


# ============================================================
# UNIFIED CONSUMER SERVICE
# ============================================================


async def consume_events() -> None:
    """
    Run the evidence persistence consumer.

    IMPORTANT ARCHITECTURAL OWNERSHIP:

        events.alerts
            -> agents.incident.main

        events.evidence
            -> this module

    Therefore this function intentionally does NOT start
    an alert consumer.
    """

    # --------------------------------------------------------
    # Database initialization.
    # --------------------------------------------------------

    await asyncio.to_thread(
        ensure_incidents_table
    )

    # --------------------------------------------------------
    # Ensure evidence group.
    # --------------------------------------------------------

    await ensure_evidence_consumer_group()

    # --------------------------------------------------------
    # Start evidence persistence consumer.
    # --------------------------------------------------------

    evidence_task = asyncio.create_task(
        evidence_consumer_loop(),
        name="incident-evidence-consumer",
    )

    print(
        "[INCIDENT] Evidence persistence service started."
    )

    try:
        await evidence_task

    except asyncio.CancelledError:

        evidence_task.cancel()

        await asyncio.gather(
            evidence_task,
            return_exceptions=True,
        )

        raise

    except Exception as exc:

        print(
            "[INCIDENT] Evidence consumer service failed: "
            f"{type(exc).__name__}: {exc}"
        )

        raise

    finally:

        if not evidence_task.done():
            evidence_task.cancel()

        await asyncio.gather(
            evidence_task,
            return_exceptions=True,
        )

        print(
            "[INCIDENT] Evidence persistence service stopped."
        )


# ============================================================
# DIRECT EXECUTION
# ============================================================


if __name__ == "__main__":
    asyncio.run(
        consume_events()
    )