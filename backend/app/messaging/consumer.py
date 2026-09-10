# # """
# # Reliable Redis Stream consumers and incident persistence.

# # Responsibilities
# # ----------------
# # - Consume canonical alert.created events from events.alerts.
# # - Create/update incidents in SQLite.
# # - Consume canonical evidence.generated/evidence.failed events.
# # - Link evidence results back to incidents.
# # - Validate canonical events before processing.
# # - ACK Redis messages only after successful processing.
# # - Recover pending messages after restart.
# # - Claim stale messages from failed consumers.
# # - Isolate malformed/failed messages.

# # Non-responsibilities
# # --------------------
# # - API-facing stream queries.
# # - Agent supervision.
# # - Camera processing.
# # - Object detection.
# # - Evidence generation.

# # API-facing Redis event queries belong to:
# #     backend.app.messaging.event_consumer

# # Incident Agent entry point:
# #     agents.incident.main
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

# # from backend.app.messaging.redis_client import redis_client
# # from shared.schemas.event_schema import validate_event


# # # ============================================================
# # # CONFIGURATION
# # # ============================================================

# # STREAM_NAME = os.getenv(
# #     "INCIDENT_INPUT_STREAM",
# #     "events.alerts",
# # )

# # GROUP_NAME = os.getenv(
# #     "INCIDENT_GROUP",
# #     "incident-workers",
# # )

# # CONSUMER_NAME = os.getenv(
# #     "INCIDENT_CONSUMER_NAME",
# #     f"incident-{socket.gethostname()}-{uuid.uuid4().hex[:8]}",
# # )

# # DATABASE_PATH = Path(
# #     os.getenv(
# #         "INCIDENT_DATABASE",
# #         "data/incidents.db",
# #     )
# # )

# # SUPPORTED_EVENT_TYPE = "alert.created"


# # # ============================================================
# # # EVIDENCE CONFIGURATION
# # # ============================================================

# # EVIDENCE_STREAM_NAME = os.getenv(
# #     "INCIDENT_EVIDENCE_INPUT_STREAM",
# #     "events.evidence",
# # )

# # EVIDENCE_GROUP_NAME = os.getenv(
# #     "INCIDENT_EVIDENCE_GROUP",
# #     "incident-evidence-workers",
# # )

# # EVIDENCE_CONSUMER_NAME = os.getenv(
# #     "INCIDENT_EVIDENCE_CONSUMER_NAME",
# #     f"incident-evidence-{socket.gethostname()}-{uuid.uuid4().hex[:8]}",
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

# # PENDING_CLAIM_IDLE_MS = int(
# #     os.getenv(
# #         "INCIDENT_PENDING_CLAIM_IDLE_MS",
# #         "30000",
# #     )
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


# # # ============================================================
# # # DATABASE
# # # ============================================================


# # def get_database_connection() -> sqlite3.Connection:
# #     """
# #     Open a SQLite connection configured for concurrent workers.

# #     WAL allows readers and writers to coexist more effectively.
# #     busy_timeout reduces transient 'database is locked' failures.
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
# #     Create or migrate the incidents table.

# #     This function is intentionally synchronous because it is used
# #     from worker threads through asyncio.to_thread().
# #     """

# #     conn = get_database_connection()

# #     try:
# #         conn.execute(
# #             """
# #             CREATE TABLE IF NOT EXISTS incidents (
# #                 incident_id TEXT PRIMARY KEY,
# #                 alert_event_id TEXT UNIQUE NOT NULL,
# #                 alert_type TEXT NOT NULL,
# #                 severity TEXT NOT NULL,

# #                 camera_id TEXT,

# #                 status TEXT NOT NULL DEFAULT 'OPEN',

# #                 trace_id TEXT,
# #                 correlation_id TEXT,

# #                 source_agent_id TEXT,
# #                 source_instance_id TEXT,
# #                 source_hostname TEXT,

# #                 person_count INTEGER,
# #                 threshold REAL,

# #                 frame_id INTEGER,
# #                 frame_timestamp REAL,

# #                 track_ids TEXT,

# #                 message TEXT,

# #                 source_video TEXT,
# #                 video_id TEXT,

# #                 start_time TEXT,
# #                 end_time TEXT,

# #                 evidence_status TEXT
# #                     NOT NULL DEFAULT 'PENDING',

# #                 evidence_type TEXT,
# #                 evidence_event_id TEXT,

# #                 proof_path TEXT,
# #                 proof_filename TEXT,

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

# #         required_columns = {
# #             "camera_id": "TEXT",
# #             "trace_id": "TEXT",
# #             "correlation_id": "TEXT",
# #             "source_agent_id": "TEXT",
# #             "source_instance_id": "TEXT",
# #             "source_hostname": "TEXT",
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
# #             "evidence_status": "TEXT DEFAULT 'PENDING'",
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

# #         for column, definition in required_columns.items():

# #             if column not in columns:

# #                 conn.execute(
# #                     f"""
# #                     ALTER TABLE incidents
# #                     ADD COLUMN {column} {definition}
# #                     """
# #                 )

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

# #     Numeric video-relative timestamps are intentionally not
# #     interpreted here; they are handled separately as durations.
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
# #                 normalized = normalized[:-1] + "+00:00"

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
# #     Determine the wall-clock event time.

# #     Priority:
# #         data.event_timestamp
# #         data.frame_datetime
# #         event.timestamp
# #         current UTC time

# #     Numeric frame_timestamp/event_time values are video-relative
# #     seconds and are therefore NOT converted into wall-clock time.
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

# #     parsed_event_timestamp = parse_timestamp(
# #         event.get("timestamp")
# #     )

# #     if parsed_event_timestamp:
# #         return parsed_event_timestamp

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

# #     if isinstance(value, (list, tuple, set)):

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

# #     Idempotency:
# #         alert_event_id is UNIQUE.

# #     If the same event is received again, the existing incident is
# #     returned instead of creating a duplicate.
# #     """

# #     if not isinstance(event, dict):
# #         raise ValueError(
# #             "Event must be a dictionary"
# #         )

# #     validated_event = validate_event(
# #         event
# #     )

# #     event = validated_event.to_dict()

# #     event_type = event.get(
# #         "event_type"
# #     )

# #     if event_type != SUPPORTED_EVENT_TYPE:
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

# #     if not isinstance(camera, dict):
# #         camera = {}

# #     context = event.get(
# #         "context",
# #         {},
# #     )

# #     if not isinstance(context, dict):
# #         context = {}

# #     data = event.get(
# #         "data",
# #         {},
# #     )

# #     if not isinstance(data, dict):
# #         raise ValueError(
# #             "Alert event data must be an object"
# #         )

# #     source = event.get(
# #         "source",
# #         {},
# #     )

# #     if not isinstance(source, dict):
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
# #         data.get("person_count")
# #     )

# #     threshold = safe_float(
# #         data.get("threshold")
# #     )

# #     frame_id = safe_int(
# #         data.get("frame_id")
# #     )

# #     frame_timestamp = safe_float(
# #         data.get("frame_timestamp")
# #     )

# #     if frame_timestamp is None:
# #         frame_timestamp = safe_float(
# #             data.get("event_time")
# #         )

# #     track_ids = normalize_track_ids(
# #         data.get("track_ids")
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

# #         existing = conn.execute(
# #             """
# #             SELECT
# #                 incident_id,
# #                 alert_event_id,
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

# #             existing_incident_id = (
# #                 existing["incident_id"]
# #             )

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
# #                 "camera_id": existing["camera_id"],
# #                 "alert_type": existing["alert_type"],
# #                 "severity": existing["severity"],
# #                 "person_count": person_count,
# #                 "evidence_status": existing[
# #                     "evidence_status"
# #                 ],
# #             }

# #         try:

# #             conn.execute(
# #                 """
# #                 INSERT INTO incidents (
# #                     incident_id,
# #                     alert_event_id,
# #                     alert_type,
# #                     severity,
# #                     camera_id,
# #                     status,
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
# #                     source_video,
# #                     video_id,
# #                     start_time,
# #                     end_time,
# #                     evidence_status,
# #                     created_at,
# #                     updated_at
# #                 )
# #                 VALUES (
# #                     ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
# #                     ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
# #                 )
# #                 """,
# #                 (
# #                     incident_id,
# #                     event_id,
# #                     alert_type,
# #                     severity,
# #                     camera_id,
# #                     DEFAULT_STATUS,
# #                     trace_id,
# #                     correlation_id,
# #                     source_agent_id,
# #                     source_instance_id,
# #                     source_hostname,
# #                     person_count,
# #                     threshold,
# #                     frame_id,
# #                     frame_timestamp,
# #                     json.dumps(
# #                         track_ids
# #                     ),
# #                     message,
# #                     source_video,
# #                     video_id,
# #                     event_time,
# #                     event_time,
# #                     DEFAULT_EVIDENCE_STATUS,
# #                     now,
# #                     now,
# #                 ),
# #             )

# #             conn.commit()

# #         except sqlite3.IntegrityError:

# #             # Another worker may have inserted the same alert
# #             # concurrently. Resolve the winner instead of failing.
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
# #     Apply an evidence.generated/evidence.failed event to an incident.

# #     The incident_id is taken from:
# #         event.context.incident_id

# #     Completed evidence cannot later be downgraded by a stale failed
# #     event.
# #     """

# #     if not isinstance(event, dict):
# #         raise ValueError(
# #             "Evidence event must be a dictionary"
# #         )

# #     validated_event = validate_event(
# #         event
# #     )

# #     event = validated_event.to_dict()

# #     event_type = event.get(
# #         "event_type"
# #     )

# #     if event_type not in SUPPORTED_EVIDENCE_EVENT_TYPES:
# #         raise ValueError(
# #             f"Unsupported evidence event type: {event_type}"
# #         )

# #     context = event.get(
# #         "context",
# #         {},
# #     )

# #     if not isinstance(context, dict):
# #         context = {}

# #     incident_id = context.get(
# #         "incident_id"
# #     )

# #     if not incident_id:
# #         raise ValueError(
# #             "Evidence event is missing context.incident_id"
# #         )

# #     data = event.get(
# #         "data",
# #         {},
# #     )

# #     if not isinstance(data, dict):
# #         raise ValueError(
# #             "Evidence event data must be an object"
# #         )

# #     evidence_event_id = event.get(
# #         "event_id"
# #     )

# #     if not evidence_event_id:
# #         raise ValueError(
# #             "Evidence event is missing event_id"
# #         )

# #     raw_status = str(
# #         data.get(
# #             "status",
# #             "",
# #         )
# #     ).strip().upper()

# #     if event_type == "evidence.generated":

# #         status = (
# #             "COMPLETED"
# #             if raw_status
# #             not in {
# #                 "FAILED",
# #                 "ERROR",
# #             }
# #             else "FAILED"
# #         )

# #     else:

# #         status = "FAILED"

# #     evidence_type = data.get(
# #         "evidence_type"
# #     )

# #     proof_path = data.get(
# #         "proof_path"
# #     )

# #     proof_filename = data.get(
# #         "proof_filename"
# #     )

# #     evidence_duration = safe_float(
# #         data.get("evidence_duration")
# #     )

# #     evidence_reason = data.get(
# #         "reason"
# #     )

# #     if evidence_reason is None:
# #         evidence_reason = data.get(
# #             "error"
# #         )

# #     now = datetime.now(
# #         timezone.utc
# #     ).isoformat()

# #     conn = get_database_connection()

# #     try:

# #         incident = conn.execute(
# #             """
# #             SELECT
# #                 incident_id,
# #                 evidence_status,
# #                 evidence_event_id,
# #                 proof_path,
# #                 proof_filename,
# #                 evidence_duration,
# #                 evidence_reason,
# #                 evidence_updated_at
# #             FROM incidents
# #             WHERE incident_id = ?
# #             """,
# #             (incident_id,),
# #         ).fetchone()

# #         if not incident:
# #             raise ValueError(
# #                 f"Incident not found: {incident_id}"
# #             )

# #         duplicate = conn.execute(
# #             """
# #             SELECT incident_id
# #             FROM incidents
# #             WHERE evidence_event_id = ?
# #             """,
# #             (evidence_event_id,),
# #         ).fetchone()

# #         if duplicate:
# #             return {
# #                 "action": "DUPLICATE",
# #                 "incident_id": incident_id,
# #                 "evidence_event_id": evidence_event_id,
# #                 "evidence_status": incident[
# #                     "evidence_status"
# #                 ],
# #             }

# #         current_status = str(
# #             incident["evidence_status"]
# #             or DEFAULT_EVIDENCE_STATUS
# #         ).upper()

# #         # Never downgrade a completed evidence result.
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

# #         conn.execute(
# #             """
# #             UPDATE incidents
# #             SET
# #                 evidence_status = ?,
# #                 evidence_type = ?,
# #                 evidence_event_id = ?,
# #                 proof_path = ?,
# #                 proof_filename = ?,
# #                 evidence_duration = ?,
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
# #             "proof_path": proof_path,
# #             "proof_filename": proof_filename,
# #         }

# #     finally:
# #         conn.close()


# # # ============================================================
# # # REDIS GROUP MANAGEMENT
# # # ============================================================


# # async def ensure_consumer_group(
# #     stream_name: str = STREAM_NAME,
# #     group_name: str = GROUP_NAME,
# # ) -> None:
# #     """
# #     Ensure a Redis consumer group exists.
# #     """

# #     try:

# #         await redis_client.xgroup_create(
# #             name=stream_name,
# #             groupname=group_name,
# #             id="0",
# #             mkstream=True,
# #         )

# #         print(
# #             f"[INCIDENT] Created consumer group "
# #             f"{group_name} for {stream_name}"
# #         )

# #     except Exception as exc:

# #         if "BUSYGROUP" in str(exc):
# #             return

# #         raise


# # async def ensure_evidence_consumer_group() -> None:
# #     await ensure_consumer_group(
# #         stream_name=EVIDENCE_STREAM_NAME,
# #         group_name=EVIDENCE_GROUP_NAME,
# #     )


# # # ============================================================
# # # ACK
# # # ============================================================


# # async def acknowledge(
# #     redis_id: str,
# # ) -> None:

# #     await redis_client.xack(
# #         STREAM_NAME,
# #         GROUP_NAME,
# #         redis_id,
# #     )


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

# #     if not isinstance(fields, dict):
# #         return {}

# #     normalized: dict[str, Any] = {}

# #     for key, value in fields.items():

# #         if isinstance(key, bytes):
# #             key = key.decode(
# #                 "utf-8",
# #                 errors="replace",
# #             )

# #         if isinstance(value, bytes):
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

# #     if isinstance(raw_event, bytes):
# #         raw_event = raw_event.decode(
# #             "utf-8"
# #         )

# #     if isinstance(raw_event, str):

# #         try:
# #             event = json.loads(
# #                 raw_event
# #             )

# #         except json.JSONDecodeError as exc:

# #             raise ValueError(
# #                 f"Invalid event JSON: {exc}"
# #             ) from exc

# #     elif isinstance(raw_event, dict):

# #         event = raw_event

# #     else:

# #         raise ValueError(
# #             "Redis event must be JSON string or object"
# #         )

# #     if not isinstance(event, dict):
# #         raise ValueError(
# #             "Canonical event must be an object"
# #         )

# #     validated = validate_event(
# #         event
# #     )

# #     return validated.to_dict()


# # # ============================================================
# # # ALERT MESSAGE PROCESSING
# # # ============================================================


# # async def process_event(
# #     redis_id: str,
# #     fields: Any,
# # ) -> None:
# #     """
# #     Process one alert Redis message.

# #     Successful processing:
# #         ACK

# #     Processing/database failure:
# #         DO NOT ACK

# #     Invalid permanent canonical payload:
# #         ACK to prevent an infinite poison-message loop.
# #     """

# #     try:

# #         event = parse_event(
# #             fields
# #         )

# #         event_type = event.get(
# #             "event_type"
# #         )

# #         if event_type != SUPPORTED_EVENT_TYPE:

# #             print(
# #                 "[INCIDENT] Unsupported event type; "
# #                 f"ACKing redis_id={redis_id} "
# #                 f"type={event_type}"
# #             )

# #             await acknowledge(
# #                 redis_id
# #             )

# #             return

# #         result = await asyncio.to_thread(
# #             create_incident_sync,
# #             event,
# #         )

# #         print(
# #             "[INCIDENT] "
# #             f"{result.get('action')} | "
# #             f"Incident={result.get('incident_id')} | "
# #             f"Alert={result.get('alert_type')} | "
# #             f"Camera={result.get('camera_id')} | "
# #             f"Severity={result.get('severity')}"
# #         )

# #         await acknowledge(
# #             redis_id
# #         )

# #     except ValueError as exc:

# #         print(
# #             "[INCIDENT] Invalid alert message; "
# #             f"ACKing redis_id={redis_id} | "
# #             f"error={exc}"
# #         )

# #         await acknowledge(
# #             redis_id
# #         )

# #     except asyncio.CancelledError:
# #         raise

# #     except Exception as exc:

# #         print(
# #             "[INCIDENT] Alert processing failed; "
# #             f"redis_id={redis_id} | "
# #             f"{type(exc).__name__}: {exc}"
# #         )

# #         # IMPORTANT:
# #         # No ACK.
# #         #
# #         # Redis retains this message as pending so it can be
# #         # recovered after the failure.
# #         raise


# # # ============================================================
# # # EVIDENCE MESSAGE PROCESSING
# # # ============================================================


# # async def process_evidence_event(
# #     redis_id: str,
# #     fields: Any,
# # ) -> None:
# #     """
# #     Process one evidence Redis message.
# #     """

# #     try:

# #         event = parse_event(
# #             fields
# #         )

# #         event_type = event.get(
# #             "event_type"
# #         )

# #         if (
# #             event_type
# #             not in SUPPORTED_EVIDENCE_EVENT_TYPES
# #         ):

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

# #         # Do not ACK.
# #         raise


# # # ============================================================
# # # PENDING ALERT RECOVERY
# # # ============================================================


# # async def recover_pending_alerts() -> None:
# #     """
# #     Recover messages previously owned by this consumer.
# #     """

# #     while True:

# #         try:

# #             messages = await redis_client.xreadgroup(
# #                 groupname=GROUP_NAME,
# #                 consumername=CONSUMER_NAME,
# #                 streams={
# #                     STREAM_NAME: "0-0",
# #                 },
# #                 count=READ_COUNT,
# #                 block=RECOVERY_BLOCK_MS,
# #             )

# #         except asyncio.CancelledError:
# #             raise

# #         except Exception as exc:

# #             print(
# #                 "[INCIDENT] Pending alert recovery read failed: "
# #                 f"{type(exc).__name__}: {exc}"
# #             )

# #             return

# #         if not messages:
# #             return

# #         processed = False

# #         for (
# #             stream_name,
# #             stream_messages,
# #         ) in messages:

# #             for (
# #                 redis_id,
# #                 fields,
# #             ) in stream_messages:

# #                 processed = True

# #                 try:

# #                     await process_event(
# #                         redis_id,
# #                         fields,
# #                     )

# #                 except Exception as exc:

# #                     print(
# #                         "[INCIDENT] Pending alert still failed: "
# #                         f"redis_id={redis_id} | "
# #                         f"{type(exc).__name__}: {exc}"
# #                     )

# #         if not processed:
# #             return


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
# #                 "[INCIDENT] Pending evidence recovery read failed: "
# #                 f"{type(exc).__name__}: {exc}"
# #             )

# #             return

# #         if not messages:
# #             return

# #         processed = False

# #         for (
# #             stream_name,
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

# #                 except Exception as exc:

# #                     print(
# #                         "[INCIDENT] Pending evidence still failed: "
# #                         f"redis_id={redis_id} | "
# #                         f"{type(exc).__name__}: {exc}"
# #                     )

# #         if not processed:
# #             return


# # # ============================================================
# # # STALE ALERT RECOVERY
# # # ============================================================


# # async def recover_stale_alerts() -> None:
# #     """
# #     Claim stale alert messages from failed Incident Agents.
# #     """

# #     try:

# #         result = await redis_client.xautoclaim(
# #             STREAM_NAME,
# #             GROUP_NAME,
# #             CONSUMER_NAME,
# #             min_idle_time=PENDING_CLAIM_IDLE_MS,
# #             start_id="0-0",
# #             count=READ_COUNT,
# #         )

# #     except asyncio.CancelledError:
# #         raise

# #     except Exception as exc:

# #         print(
# #             "[INCIDENT] Alert XAUTOCLAIM failed: "
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
# #         f"{len(claimed)} stale alert message(s)"
# #     )

# #     for (
# #         redis_id,
# #         fields,
# #     ) in claimed:

# #         try:

# #             await process_event(
# #                 redis_id,
# #                 fields,
# #             )

# #         except Exception as exc:

# #             print(
# #                 "[INCIDENT] Recovered alert failed: "
# #                 f"redis_id={redis_id} | "
# #                 f"{type(exc).__name__}: {exc}"
# #             )


# # # ============================================================
# # # STALE EVIDENCE RECOVERY
# # # ============================================================


# # async def recover_stale_evidence() -> None:
# #     """
# #     Claim stale evidence messages from failed Incident Agents.
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

# #         except Exception as exc:

# #             print(
# #                 "[INCIDENT] Recovered evidence failed: "
# #                 f"redis_id={redis_id} | "
# #                 f"{type(exc).__name__}: {exc}"
# #             )


# # # ============================================================
# # # ALERT CONSUMER LOOP
# # # ============================================================


# # async def alert_consumer_loop() -> None:
# #     """
# #     Main alert consumer loop.
# #     """

# #     await ensure_consumer_group()

# #     await recover_pending_alerts()

# #     print(
# #         "[INCIDENT] Alert consumer loop started | "
# #         f"stream={STREAM_NAME} | "
# #         f"group={GROUP_NAME} | "
# #         f"consumer={CONSUMER_NAME}"
# #     )

# #     while True:

# #         await recover_stale_alerts()

# #         try:

# #             messages = await redis_client.xreadgroup(
# #                 groupname=GROUP_NAME,
# #                 consumername=CONSUMER_NAME,
# #                 streams={
# #                     STREAM_NAME: ">",
# #                 },
# #                 count=READ_COUNT,
# #                 block=READ_BLOCK_MS,
# #             )

# #         except asyncio.CancelledError:
# #             raise

# #         except Exception as exc:

# #             print(
# #                 "[INCIDENT] Alert XREADGROUP failed: "
# #                 f"{type(exc).__name__}: {exc}"
# #             )

# #             await asyncio.sleep(2)

# #             continue

# #         if not messages:
# #             continue

# #         for (
# #             stream_name,
# #             stream_messages,
# #         ) in messages:

# #             for (
# #                 redis_id,
# #                 fields,
# #             ) in stream_messages:

# #                 try:

# #                     await process_event(
# #                         redis_id,
# #                         fields,
# #                     )

# #                 except asyncio.CancelledError:
# #                     raise

# #                 except Exception as exc:

# #                     print(
# #                         "[INCIDENT] Alert message remains pending: "
# #                         f"redis_id={redis_id} | "
# #                         f"{type(exc).__name__}: {exc}"
# #                     )


# # # ============================================================
# # # EVIDENCE CONSUMER LOOP
# # # ============================================================


# # async def evidence_consumer_loop() -> None:
# #     """
# #     Main evidence consumer loop.
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

# #             await asyncio.sleep(2)

# #             continue

# #         if not messages:
# #             continue

# #         for (
# #             stream_name,
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
# # # UNIFIED CONSUMER
# # # ============================================================


# # async def consume_events() -> None:
# #     """
# #     Run alert and evidence consumers independently.

# #     A failure in one loop must not terminate the other.
# #     """

# #     ensure_incidents_table()

# #     await ensure_consumer_group()

# #     await ensure_evidence_consumer_group()

# #     alert_task = asyncio.create_task(
# #         alert_consumer_loop(),
# #         name="incident-alert-consumer",
# #     )

# #     evidence_task = asyncio.create_task(
# #         evidence_consumer_loop(),
# #         name="incident-evidence-consumer",
# #     )

# #     tasks = {
# #         alert_task,
# #         evidence_task,
# #     }

# #     print(
# #         "[INCIDENT] Unified consumer service started."
# #     )

# #     try:

# #         while True:

# #             done, _ = await asyncio.wait(
# #                 tasks,
# #                 return_when=asyncio.FIRST_COMPLETED,
# #             )

# #             for task in done:

# #                 try:

# #                     task.result()

# #                 except asyncio.CancelledError:

# #                     if not task.cancelled():
# #                         raise

# #                 except Exception as exc:

# #                     print(
# #                         "[INCIDENT] Background consumer failed: "
# #                         f"{task.get_name()} | "
# #                         f"{type(exc).__name__}: {exc}"
# #                     )

# #                 if task is alert_task:

# #                     print(
# #                         "[INCIDENT] Restarting alert consumer loop."
# #                     )

# #                     alert_task = asyncio.create_task(
# #                         alert_consumer_loop(),
# #                         name="incident-alert-consumer",
# #                     )

# #                     tasks.add(
# #                         alert_task
# #                     )

# #                 elif task is evidence_task:

# #                     print(
# #                         "[INCIDENT] Restarting evidence consumer loop."
# #                     )

# #                     evidence_task = asyncio.create_task(
# #                         evidence_consumer_loop(),
# #                         name="incident-evidence-consumer",
# #                     )

# #                     tasks.add(
# #                         evidence_task
# #                     )

# #                 tasks.discard(
# #                     task
# #                 )

# #     finally:

# #         for task in tasks:
# #             task.cancel()

# #         if tasks:

# #             await asyncio.gather(
# #                 *tasks,
# #                 return_exceptions=True,
# #             )

# #         print(
# #             "[INCIDENT] Unified consumer service stopped."
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
# - Consume canonical alert.created events from events.alerts.
# - Create/update incidents in SQLite.
# - Consume canonical evidence.generated/evidence.failed events.
# - Link evidence results back to incidents.
# - Validate canonical events before processing.
# - ACK Redis messages only after successful processing.
# - Recover pending messages after restart.
# - Claim stale messages from failed consumers.
# - Isolate malformed/failed messages.

# Non-responsibilities
# --------------------
# - API-facing stream queries.
# - Agent supervision.
# - Camera processing.
# - Object detection.
# - Evidence generation.

# API-facing Redis event queries belong to:
#     backend.app.messaging.event_consumer

# Incident Agent entry point:
#     agents.incident.main
# """

# from __future__ import annotations

# import asyncio
# import json
# import os
# import socket
# import sqlite3
# import uuid
# from datetime import datetime, timezone
# from pathlib import Path
# from typing import Any

# from backend.app.messaging.redis_client import redis_client
# from shared.schemas.event_schema import validate_event


# # ============================================================
# # CONFIGURATION
# # ============================================================

# STREAM_NAME = os.getenv(
#     "INCIDENT_INPUT_STREAM",
#     "events.alerts",
# )

# GROUP_NAME = os.getenv(
#     "INCIDENT_GROUP",
#     "incident-workers",
# )

# CONSUMER_NAME = os.getenv(
#     "INCIDENT_CONSUMER_NAME",
#     f"incident-{socket.gethostname()}-{uuid.uuid4().hex[:8]}",
# )

# DATABASE_PATH = Path(
#     os.getenv(
#         "INCIDENT_DATABASE",
#         "data/incidents.db",
#     )
# )

# SUPPORTED_EVENT_TYPE = "alert.created"


# # ============================================================
# # EVIDENCE CONFIGURATION
# # ============================================================

# EVIDENCE_STREAM_NAME = os.getenv(
#     "INCIDENT_EVIDENCE_INPUT_STREAM",
#     "events.evidence",
# )

# EVIDENCE_GROUP_NAME = os.getenv(
#     "INCIDENT_EVIDENCE_GROUP",
#     "incident-evidence-workers",
# )

# EVIDENCE_CONSUMER_NAME = os.getenv(
#     "INCIDENT_EVIDENCE_CONSUMER_NAME",
#     f"incident-evidence-{socket.gethostname()}-{uuid.uuid4().hex[:8]}",
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
#             "30000",
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
# # DATABASE
# # ============================================================


# def get_database_connection() -> sqlite3.Connection:
#     """
#     Open a SQLite connection configured for concurrent workers.

#     WAL allows readers and writers to coexist more effectively.
#     busy_timeout reduces transient database-lock failures.
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

#     This is intentionally synchronous because callers may execute
#     it through asyncio.to_thread().
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
#         #
#         # New nullable columns are used for compatibility with
#         # existing databases. Existing rows therefore remain valid.
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
#         # Backfill missing timestamps safely.
#         # --------------------------------------------------------

#         now = datetime.now(timezone.utc).isoformat()

#         conn.execute(
#             """
#             UPDATE incidents
#             SET created_at = COALESCE(created_at, ?)
#             WHERE created_at IS NULL
#             """,
#             (now,),
#         )

#         conn.execute(
#             """
#             UPDATE incidents
#             SET updated_at = COALESCE(updated_at, created_at, ?)
#             WHERE updated_at IS NULL
#             """,
#             (now,),
#         )

#         conn.execute(
#             """
#             UPDATE incidents
#             SET event_type = COALESCE(event_type, ?)
#             WHERE event_type IS NULL
#             """,
#             (SUPPORTED_EVENT_TYPE,),
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
#         # Indexes
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

#         # Evidence event IDs are unique because one Redis event must
#         # never be applied twice to two incidents.
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

#     Numeric values are intentionally not interpreted as wall-clock
#     timestamps.
#     """

#     if value is None:
#         return None

#     if isinstance(value, datetime):
#         dt = value

#     elif isinstance(value, str):
#         value = value.strip()

#         if not value:
#             return None

#         try:
#             normalized = value

#             if normalized.endswith("Z"):
#                 normalized = normalized[:-1] + "+00:00"

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

#     Numeric frame_timestamp/event_time values are treated as
#     video-relative values and are not converted to wall-clock time.
#     """

#     data = event.get(
#         "data",
#         {},
#     )

#     if isinstance(data, dict):
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
#         (list, tuple, set),
#     ):
#         return [
#             str(item)
#             for item in value
#             if item is not None
#         ]

#     return [str(value)]


# # ============================================================
# # INCIDENT CREATION
# # ============================================================


# def create_incident_sync(
#     event: dict[str, Any],
# ) -> dict[str, Any]:
#     """
#     Create an incident from a canonical alert.created event.

#     Idempotency:
#         alert_event_id is UNIQUE.

#     If the same event is received again, the existing incident
#     is returned instead of creating a duplicate.
#     """

#     if not isinstance(event, dict):
#         raise ValueError(
#             "Event must be a dictionary"
#         )

#     validated_event = validate_event(
#         event
#     )

#     event = validated_event.to_dict()

#     event_type = event.get(
#         "event_type"
#     )

#     if event_type != SUPPORTED_EVENT_TYPE:
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

#     if not isinstance(camera, dict):
#         camera = {}

#     context = event.get(
#         "context",
#         {},
#     )

#     if not isinstance(context, dict):
#         context = {}

#     data = event.get(
#         "data",
#         {},
#     )

#     if not isinstance(data, dict):
#         raise ValueError(
#             "Alert event data must be an object"
#         )

#     source = event.get(
#         "source",
#         {},
#     )

#     if not isinstance(source, dict):
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
#         data.get("person_count")
#     )

#     threshold = safe_float(
#         data.get("threshold")
#     )

#     frame_id = safe_int(
#         data.get("frame_id")
#     )

#     frame_timestamp = safe_float(
#         data.get("frame_timestamp")
#     )

#     if frame_timestamp is None:
#         frame_timestamp = safe_float(
#             data.get("event_time")
#         )

#     track_ids = normalize_track_ids(
#         data.get("track_ids")
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
#         # First idempotency lookup.
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
#                 "camera_id": existing["camera_id"],
#                 "alert_type": existing["alert_type"],
#                 "severity": existing["severity"],
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
#             # Another worker may have inserted the same alert
#             # concurrently.
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
#                 # Could be a different constraint violation,
#                 # e.g. incident_id collision.
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

#     Evidence event IDs are unique.

#     A completed evidence result cannot later be downgraded
#     by a stale failure event.
#     """

#     if not isinstance(event, dict):
#         raise ValueError(
#             "Evidence event must be a dictionary"
#         )

#     validated_event = validate_event(
#         event
#     )

#     event = validated_event.to_dict()

#     event_type = event.get(
#         "event_type"
#     )

#     if event_type not in SUPPORTED_EVIDENCE_EVENT_TYPES:
#         raise ValueError(
#             f"Unsupported evidence event type: {event_type}"
#         )

#     context = event.get(
#         "context",
#         {},
#     )

#     if not isinstance(context, dict):
#         context = {}

#     incident_id = context.get(
#         "incident_id"
#     )

#     if not incident_id:
#         raise ValueError(
#             "Evidence event is missing context.incident_id"
#         )

#     data = event.get(
#         "data",
#         {},
#     )

#     if not isinstance(data, dict):
#         raise ValueError(
#             "Evidence event data must be an object"
#         )

#     evidence_event_id = event.get(
#         "event_id"
#     )

#     if not evidence_event_id:
#         raise ValueError(
#             "Evidence event is missing event_id"
#         )

#     raw_status = str(
#         data.get(
#             "status",
#             "",
#         )
#     ).strip().upper()

#     if event_type == "evidence.generated":
#         status = (
#             "FAILED"
#             if raw_status in {
#                 "FAILED",
#                 "ERROR",
#             }
#             else "COMPLETED"
#         )
#     else:
#         status = "FAILED"

#     evidence_type = data.get(
#         "evidence_type"
#     )

#     proof_path = data.get(
#         "proof_path"
#     )

#     proof_filename = data.get(
#         "proof_filename"
#     )

#     evidence_duration = safe_float(
#         data.get("evidence_duration")
#     )

#     evidence_reason = data.get(
#         "reason"
#     )

#     if evidence_reason is None:
#         evidence_reason = data.get(
#             "error"
#         )

#     now = datetime.now(
#         timezone.utc
#     ).isoformat()

#     conn = get_database_connection()

#     try:
#         # --------------------------------------------------------
#         # Begin explicit transaction so the incident lookup,
#         # duplicate check, and update are one atomic operation.
#         # --------------------------------------------------------

#         conn.execute("BEGIN IMMEDIATE")

#         incident = conn.execute(
#             """
#             SELECT
#                 incident_id,
#                 evidence_status,
#                 evidence_event_id,
#                 proof_path,
#                 proof_filename,
#                 evidence_duration,
#                 evidence_reason,
#                 evidence_updated_at
#             FROM incidents
#             WHERE incident_id = ?
#             """,
#             (incident_id,),
#         ).fetchone()

#         if not incident:
#             conn.rollback()

#             raise ValueError(
#                 f"Incident not found: {incident_id}"
#             )

#         current_status = str(
#             incident["evidence_status"]
#             or DEFAULT_EVIDENCE_STATUS
#         ).upper()

#         # --------------------------------------------------------
#         # Same evidence event already applied.
#         # --------------------------------------------------------

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

#         # --------------------------------------------------------
#         # Never downgrade completed evidence.
#         # --------------------------------------------------------

#         if (
#             current_status == "COMPLETED"
#             and status == "FAILED"
#         ):
#             conn.execute(
#                 """
#                 UPDATE incidents
#                 SET updated_at = ?
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

#         # --------------------------------------------------------
#         # Apply evidence result.
#         # --------------------------------------------------------

#         try:
#             conn.execute(
#                 """
#                 UPDATE incidents
#                 SET
#                     evidence_status = ?,
#                     evidence_type = ?,
#                     evidence_event_id = ?,
#                     proof_path = ?,
#                     proof_filename = ?,
#                     evidence_duration = ?,
#                     evidence_reason = ?,
#                     evidence_updated_at = ?,
#                     updated_at = ?
#                 WHERE incident_id = ?
#                 """,
#                 (
#                     status,
#                     evidence_type,
#                     evidence_event_id,
#                     proof_path,
#                     proof_filename,
#                     evidence_duration,
#                     evidence_reason,
#                     now,
#                     now,
#                     incident_id,
#                 ),
#             )

#             conn.commit()

#         except sqlite3.IntegrityError:
#             conn.rollback()

#             # Another worker may have applied the same evidence event.
#             existing = conn.execute(
#                 """
#                 SELECT
#                     incident_id,
#                     evidence_status
#                 FROM incidents
#                 WHERE evidence_event_id = ?
#                 """,
#                 (evidence_event_id,),
#             ).fetchone()

#             if existing:
#                 return {
#                     "action": "DUPLICATE",
#                     "incident_id": incident_id,
#                     "evidence_event_id": evidence_event_id,
#                     "evidence_status": existing[
#                         "evidence_status"
#                     ],
#                 }

#             raise

#         return {
#             "action": "UPDATED",
#             "incident_id": incident_id,
#             "evidence_event_id": evidence_event_id,
#             "evidence_status": status,
#             "proof_path": proof_path,
#             "proof_filename": proof_filename,
#         }

#     finally:
#         conn.close()


# # ============================================================
# # REDIS GROUP MANAGEMENT
# # ============================================================


# async def ensure_consumer_group(
#     stream_name: str = STREAM_NAME,
#     group_name: str = GROUP_NAME,
# ) -> None:
#     """
#     Ensure a Redis consumer group exists.
#     """

#     try:
#         await redis_client.xgroup_create(
#             name=stream_name,
#             groupname=group_name,
#             id="0",
#             mkstream=True,
#         )

#         print(
#             f"[INCIDENT] Created consumer group "
#             f"{group_name} for {stream_name}"
#         )

#     except Exception as exc:
#         if "BUSYGROUP" in str(exc):
#             return

#         raise


# async def ensure_evidence_consumer_group() -> None:
#     await ensure_consumer_group(
#         stream_name=EVIDENCE_STREAM_NAME,
#         group_name=EVIDENCE_GROUP_NAME,
#     )


# # ============================================================
# # ACK
# # ============================================================


# async def acknowledge(
#     redis_id: str,
# ) -> None:
#     await redis_client.xack(
#         STREAM_NAME,
#         GROUP_NAME,
#         redis_id,
#     )


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
#     if not isinstance(fields, dict):
#         return {}

#     normalized: dict[str, Any] = {}

#     for key, value in fields.items():
#         if isinstance(key, bytes):
#             key = key.decode(
#                 "utf-8",
#                 errors="replace",
#             )

#         if isinstance(value, bytes):
#             value = value.decode(
#                 "utf-8",
#                 errors="replace",
#             )

#         normalized[key] = value

#     return normalized


# def parse_event(
#     fields: Any,
# ) -> dict[str, Any]:
#     normalized = normalize_fields(
#         fields
#     )

#     raw_event = normalized.get(
#         "event"
#     )

#     if raw_event is None:
#         raise ValueError(
#             "Redis message missing event field"
#         )

#     if isinstance(raw_event, bytes):
#         raw_event = raw_event.decode(
#             "utf-8",
#             errors="replace",
#         )

#     if isinstance(raw_event, str):
#         try:
#             event = json.loads(
#                 raw_event
#             )

#         except json.JSONDecodeError as exc:
#             raise ValueError(
#                 f"Invalid event JSON: {exc}"
#             ) from exc

#     elif isinstance(raw_event, dict):
#         event = raw_event

#     else:
#         raise ValueError(
#             "Redis event must be JSON string or object"
#         )

#     if not isinstance(event, dict):
#         raise ValueError(
#             "Canonical event must be an object"
#         )

#     validated = validate_event(
#         event
#     )

#     return validated.to_dict()


# # ============================================================
# # ALERT MESSAGE PROCESSING
# # ============================================================


# async def process_event(
#     redis_id: str,
#     fields: Any,
# ) -> None:
#     """
#     Process one alert Redis message.

#     Permanent invalid/unsupported message:
#         ACK.

#     Successful processing:
#         ACK.

#     Retryable processing/database failure:
#         NO ACK.

#     This preserves at-least-once processing.
#     """

#     try:
#         event = parse_event(
#             fields
#         )

#         event_type = event.get(
#             "event_type"
#         )

#         if event_type != SUPPORTED_EVENT_TYPE:
#             print(
#                 "[INCIDENT] Unsupported event type; "
#                 f"ACKing redis_id={redis_id} "
#                 f"type={event_type}"
#             )

#             await acknowledge(
#                 redis_id
#             )

#             return

#         result = await asyncio.to_thread(
#             create_incident_sync,
#             event,
#         )

#         print(
#             "[INCIDENT] "
#             f"{result.get('action')} | "
#             f"Incident={result.get('incident_id')} | "
#             f"Alert={result.get('alert_type')} | "
#             f"Camera={result.get('camera_id')} | "
#             f"Severity={result.get('severity')}"
#         )

#         await acknowledge(
#             redis_id
#         )

#     except ValueError as exc:
#         # Canonical validation errors and unsupported event types
#         # are permanent from this consumer's perspective.
#         print(
#             "[INCIDENT] Invalid alert message; "
#             f"ACKing redis_id={redis_id} | "
#             f"error={exc}"
#         )

#         await acknowledge(
#             redis_id
#         )

#     except asyncio.CancelledError:
#         raise

#     except Exception as exc:
#         # IMPORTANT:
#         # Do NOT ACK unexpected processing/database failures.
#         #
#         # Redis retains the message as pending so it can be
#         # recovered after failure.
#         print(
#             "[INCIDENT] Alert processing failed; "
#             f"redis_id={redis_id} | "
#             f"{type(exc).__name__}: {exc}"
#         )

#         raise


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

#     Successful update:
#         ACK.

#     Retryable processing failure:
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

#     except ValueError as exc:
#         print(
#             "[INCIDENT] Invalid evidence message; "
#             f"ACKing redis_id={redis_id} | "
#             f"error={exc}"
#         )

#         await acknowledge_evidence(
#             redis_id
#         )

#     except asyncio.CancelledError:
#         raise

#     except Exception as exc:
#         print(
#             "[INCIDENT] Evidence processing failed; "
#             f"redis_id={redis_id} | "
#             f"{type(exc).__name__}: {exc}"
#         )

#         # Do not ACK.
#         raise


# # ============================================================
# # PENDING ALERT RECOVERY
# # ============================================================


# async def recover_pending_alerts() -> None:
#     """
#     Recover messages previously owned by this consumer.

#     Redis ID 0-0 means:
#         messages currently pending for this consumer.

#     It does NOT claim pending messages owned by other consumers.
#     Those are handled by XAUTOCLAIM.
#     """

#     while True:
#         try:
#             messages = await redis_client.xreadgroup(
#                 groupname=GROUP_NAME,
#                 consumername=CONSUMER_NAME,
#                 streams={
#                     STREAM_NAME: "0-0",
#                 },
#                 count=READ_COUNT,
#                 block=RECOVERY_BLOCK_MS,
#             )

#         except asyncio.CancelledError:
#             raise

#         except Exception as exc:
#             print(
#                 "[INCIDENT] Pending alert recovery read failed: "
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
#                     await process_event(
#                         redis_id,
#                         fields,
#                     )

#                 except asyncio.CancelledError:
#                     raise

#                 except Exception as exc:
#                     print(
#                         "[INCIDENT] Pending alert still failed: "
#                         f"redis_id={redis_id} | "
#                         f"{type(exc).__name__}: {exc}"
#                     )

#         if not processed:
#             return


# # ============================================================
# # PENDING EVIDENCE RECOVERY
# # ============================================================


# async def recover_pending_evidence() -> None:
#     """
#     Recover evidence messages previously owned by this consumer.
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
#                 "[INCIDENT] Pending evidence recovery read failed: "
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
# # STALE ALERT RECOVERY
# # ============================================================


# async def recover_stale_alerts() -> None:
#     """
#     Claim stale alert messages from failed Incident consumers.
#     """

#     try:
#         result = await redis_client.xautoclaim(
#             STREAM_NAME,
#             GROUP_NAME,
#             CONSUMER_NAME,
#             min_idle_time=PENDING_CLAIM_IDLE_MS,
#             start_id="0-0",
#             count=READ_COUNT,
#         )

#     except asyncio.CancelledError:
#         raise

#     except Exception as exc:
#         print(
#             "[INCIDENT] Alert XAUTOCLAIM failed: "
#             f"{type(exc).__name__}: {exc}"
#         )

#         return

#     if not result or len(result) < 2:
#         return

#     claimed = result[1]

#     if not claimed:
#         return

#     print(
#         "[INCIDENT] Recovered "
#         f"{len(claimed)} stale alert message(s)"
#     )

#     for (
#         redis_id,
#         fields,
#     ) in claimed:

#         try:
#             await process_event(
#                 redis_id,
#                 fields,
#             )

#         except asyncio.CancelledError:
#             raise

#         except Exception as exc:
#             print(
#                 "[INCIDENT] Recovered alert failed: "
#                 f"redis_id={redis_id} | "
#                 f"{type(exc).__name__}: {exc}"
#             )


# # ============================================================
# # STALE EVIDENCE RECOVERY
# # ============================================================


# async def recover_stale_evidence() -> None:
#     """
#     Claim stale evidence messages from failed Incident consumers.
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
# # ALERT CONSUMER LOOP
# # ============================================================


# async def alert_consumer_loop() -> None:
#     """
#     Main alert consumer loop.
#     """

#     await ensure_consumer_group()

#     await recover_pending_alerts()

#     print(
#         "[INCIDENT] Alert consumer loop started | "
#         f"stream={STREAM_NAME} | "
#         f"group={GROUP_NAME} | "
#         f"consumer={CONSUMER_NAME}"
#     )

#     while True:
#         await recover_stale_alerts()

#         try:
#             messages = await redis_client.xreadgroup(
#                 groupname=GROUP_NAME,
#                 consumername=CONSUMER_NAME,
#                 streams={
#                     STREAM_NAME: ">",
#                 },
#                 count=READ_COUNT,
#                 block=READ_BLOCK_MS,
#             )

#         except asyncio.CancelledError:
#             raise

#         except Exception as exc:
#             print(
#                 "[INCIDENT] Alert XREADGROUP failed: "
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
#                     await process_event(
#                         redis_id,
#                         fields,
#                     )

#                 except asyncio.CancelledError:
#                     raise

#                 except Exception as exc:
#                     print(
#                         "[INCIDENT] Alert message remains pending: "
#                         f"redis_id={redis_id} | "
#                         f"{type(exc).__name__}: {exc}"
#                     )


# # ============================================================
# # EVIDENCE CONSUMER LOOP
# # ============================================================


# async def evidence_consumer_loop() -> None:
#     """
#     Main evidence consumer loop.
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
#         await recover_stale_evidence()

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
# # UNIFIED CONSUMER
# # ============================================================


# async def consume_events() -> None:
#     """
#     Run alert and evidence consumers independently.

#     A failure in one loop must not terminate the other.
#     """

#     # Database initialization happens before consumers start.
#     #
#     # This is synchronous because it is a startup operation.
#     # It does not run continuously inside the event loop.
#     await asyncio.to_thread(
#         ensure_incidents_table
#     )

#     await ensure_consumer_group()

#     await ensure_evidence_consumer_group()

#     alert_task = asyncio.create_task(
#         alert_consumer_loop(),
#         name="incident-alert-consumer",
#     )

#     evidence_task = asyncio.create_task(
#         evidence_consumer_loop(),
#         name="incident-evidence-consumer",
#     )

#     tasks: set[asyncio.Task[Any]] = {
#         alert_task,
#         evidence_task,
#     }

#     print(
#         "[INCIDENT] Unified consumer service started."
#     )

#     try:
#         while True:
#             done, _ = await asyncio.wait(
#                 tasks,
#                 return_when=asyncio.FIRST_COMPLETED,
#             )

#             for task in done:
#                 try:
#                     task.result()

#                 except asyncio.CancelledError:
#                     if not task.cancelled():
#                         raise

#                 except Exception as exc:
#                     print(
#                         "[INCIDENT] Background consumer failed: "
#                         f"{task.get_name()} | "
#                         f"{type(exc).__name__}: {exc}"
#                     )

#                 # ------------------------------------------------
#                 # Replace only the failed/completed task.
#                 # The other consumer continues untouched.
#                 # ------------------------------------------------

#                 if task is alert_task:
#                     print(
#                         "[INCIDENT] Restarting alert consumer loop."
#                     )

#                     alert_task = asyncio.create_task(
#                         alert_consumer_loop(),
#                         name="incident-alert-consumer",
#                     )

#                     tasks.add(
#                         alert_task
#                     )

#                 elif task is evidence_task:
#                     print(
#                         "[INCIDENT] Restarting evidence consumer loop."
#                     )

#                     evidence_task = asyncio.create_task(
#                         evidence_consumer_loop(),
#                         name="incident-evidence-consumer",
#                     )

#                     tasks.add(
#                         evidence_task
#                     )

#                 tasks.discard(
#                     task
#                 )

#                 # Prevent an immediate restart storm if the newly
#                 # created consumer repeatedly fails during startup.
#                 await asyncio.sleep(
#                     CONSUMER_RESTART_DELAY_SECONDS
#                 )

#     finally:
#         for task in tasks:
#             task.cancel()

#         if tasks:
#             await asyncio.gather(
#                 *tasks,
#                 return_exceptions=True,
#             )

#         print(
#             "[INCIDENT] Unified consumer service stopped."
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
from pathlib import Path
from typing import Any

from backend.app.incidents.paths import incident_database_path
from backend.app.messaging.redis_client import redis_client
from shared.schemas.event_schema import validate_event


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

DATABASE_PATH = incident_database_path()


# ============================================================
# EVIDENCE STREAM CONFIGURATION
# ============================================================

EVIDENCE_STREAM_NAME = os.getenv(
    "INCIDENT_EVIDENCE_INPUT_STREAM",
    "events.evidence",
).strip() or "events.evidence"

EVIDENCE_GROUP_NAME = os.getenv(
    "INCIDENT_EVIDENCE_GROUP",
    "incident-evidence-workers",
).strip() or "incident-evidence-workers"

EVIDENCE_CONSUMER_NAME = os.getenv(
    "INCIDENT_EVIDENCE_CONSUMER_NAME",
    f"incident-evidence-{socket.gethostname()}-{uuid.uuid4().hex[:8]}",
).strip() or (
    f"incident-evidence-{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
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
# DATABASE
# ============================================================


def get_database_connection() -> sqlite3.Connection:
    """
    Open a SQLite connection configured for concurrent workers.

    WAL allows readers and writers to coexist more effectively.

    busy_timeout reduces transient database-lock failures.
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
                frame_id INTEGER,
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
            "frame_id": "INTEGER",
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

    if isinstance(value, datetime):
        dt = value

    elif isinstance(value, str):
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

    if isinstance(data, dict):
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
# INCIDENT CREATION
# ============================================================


def create_incident_sync(
    event: dict[str, Any],
) -> dict[str, Any]:
    """
    Create an incident from a canonical alert.created event.

    This function is called by:

        agents.incident.main

    It is NOT called by the Redis consumer service.

    Idempotency is based on alert_event_id.
    """

    if not isinstance(event, dict):
        raise ValueError(
            "Event must be a dictionary"
        )

    validated_event = validate_event(
        event
    )

    if hasattr(
        validated_event,
        "to_dict",
    ):
        event = validated_event.to_dict()

    elif hasattr(
        validated_event,
        "model_dump",
    ):
        event = validated_event.model_dump(
            mode="json"
        )

    elif isinstance(
        validated_event,
        dict,
    ):
        event = validated_event

    else:
        raise ValueError(
            "Validated event has unsupported type"
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

    frame_id = safe_int(
        data.get(
            "frame_id"
        )
    )

    frame_timestamp = safe_float(
        data.get(
            "frame_timestamp"
        )
    )

    if frame_timestamp is None:
        frame_timestamp = safe_float(
            data.get(
                "event_time"
            )
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
                    updated_at = ?
                WHERE incident_id = ?
                """,
                (
                    source_video,
                    video_id,
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
                    ?, ?, ?, ?, ?, ?, ?
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

    Persists the complete evidence metadata:
        - evidence_status
        - evidence_type
        - evidence_event_id
        - proof_path
        - proof_filename
        - source_video
        - start_time
        - end_time
        - evidence_duration
        - evidence_reason
        - evidence_updated_at

    A completed evidence result cannot later be downgraded
    by a stale failure event.
    """

    if not isinstance(event, dict):
        raise ValueError(
            "Evidence event must be a dictionary"
        )

    validated_event = validate_event(event)

    if hasattr(validated_event, "to_dict"):
        event = validated_event.to_dict()
    elif hasattr(validated_event, "model_dump"):
        event = validated_event.model_dump(
            mode="json"
        )
    elif isinstance(validated_event, dict):
        event = validated_event
    else:
        raise ValueError(
            "Validated event has unsupported type"
        )

    event_type = event.get("event_type")

    if event_type not in SUPPORTED_EVIDENCE_EVENT_TYPES:
        raise ValueError(
            f"Unsupported evidence event type: {event_type}"
        )

    context = event.get("context", {})

    if not isinstance(context, dict):
        context = {}

    incident_id = context.get("incident_id")

    if not incident_id:
        raise ValueError(
            "Evidence event is missing "
            "context.incident_id"
        )

    data = event.get("data", {})

    if not isinstance(data, dict):
        raise ValueError(
            "Evidence event data must be an object"
        )

    evidence_event_id = event.get("event_id")

    if not evidence_event_id:
        raise ValueError(
            "Evidence event is missing event_id"
        )

    # --------------------------------------------------------
    # Determine final evidence status.
    # --------------------------------------------------------

    raw_status = str(
        data.get("status", "")
    ).strip().upper()

    if event_type == "evidence.generated":
        status = (
            "FAILED"
            if raw_status in {
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

    # Evidence generator may emit either:
    #
    #   duration
    #
    # or:
    #
    #   evidence_duration
    #
    # Support both.

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

    # --------------------------------------------------------
    # Evidence start/end time.
    #
    # These are allowed to be either:
    #   - ISO timestamps
    #   - numeric video-relative values
    #
    # Store them as TEXT because the DB schema defines
    # start_time/end_time as TEXT.
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Evidence failure reason.
    # --------------------------------------------------------

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

        if not incident:
            conn.rollback()
            raise ValueError(
                f"Incident not found: {incident_id}"
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
                SET updated_at = ?
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
        #
        # COALESCE preserves useful existing values if an
        # incoming event omits optional metadata.
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
            "start_time": start_time,
            "end_time": end_time,
            "evidence_duration": evidence_duration,
            "evidence_reason": evidence_reason,
        }

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
            id="0",
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

    normalized = normalize_fields(
        fields
    )

    raw_event = normalized.get(
        "event"
    )

    if raw_event is None:
        raise ValueError(
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

            raise ValueError(
                f"Invalid event JSON: {exc}"
            ) from exc

    elif isinstance(
        raw_event,
        dict,
    ):

        event = raw_event

    else:

        raise ValueError(
            "Redis event must be JSON string or object"
        )

    if not isinstance(
        event,
        dict,
    ):
        raise ValueError(
            "Canonical event must be an object"
        )

    validated = validate_event(
        event
    )

    if hasattr(
        validated,
        "to_dict",
    ):
        return validated.to_dict()

    if hasattr(
        validated,
        "model_dump",
    ):
        return validated.model_dump(
            mode="json"
        )

    if isinstance(
        validated,
        dict,
    ):
        return validated

    raise ValueError(
        "Validated event has unsupported type"
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

    Successful update:
        ACK.

    Retryable processing failure:
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

    except ValueError as exc:

        print(
            "[INCIDENT] Invalid evidence message; "
            f"ACKing redis_id={redis_id} | "
            f"error={exc}"
        )

        await acknowledge_evidence(
            redis_id
        )

    except asyncio.CancelledError:
        raise

    except Exception as exc:

        print(
            "[INCIDENT] Evidence processing failed; "
            f"redis_id={redis_id} | "
            f"{type(exc).__name__}: {exc}"
        )

        # IMPORTANT:
        #
        # Do NOT ACK.
        #
        # Redis retains the message as pending so it can
        # be recovered after failure.

        raise


# ============================================================
# PENDING EVIDENCE RECOVERY
# ============================================================


async def recover_pending_evidence() -> None:
    """
    Recover evidence messages previously owned by this consumer.
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
    """

    try:

        result = await redis_client.xautoclaim(
            EVIDENCE_STREAM_NAME,
            EVIDENCE_GROUP_NAME,
            EVIDENCE_CONSUMER_NAME,
            min_idle_time=PENDING_CLAIM_IDLE_MS,
            start_id="0-0",
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

    claimed = result[1]

    if not claimed:
        return

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

    await recover_pending_evidence()

    print(
        "[INCIDENT] Evidence consumer loop started | "
        f"stream={EVIDENCE_STREAM_NAME} | "
        f"group={EVIDENCE_GROUP_NAME} | "
        f"consumer={EVIDENCE_CONSUMER_NAME}"
    )

    while True:

        await recover_stale_evidence()

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
