# # import json

# # from app.messaging.redis_client import redis_client


# # # ============================================================
# # # REDIS STREAMS
# # # ============================================================

# # STREAMS = {
# #     "detection": "events.detection",
# #     "tracking": "events.tracking",
# #     "behavior": "events.behavior",
# # }


# # # ============================================================
# # # CONFIG
# # # ============================================================

# # DEFAULT_COUNT = 20
# # MAX_COUNT = 500


# # # ============================================================
# # # DECODE REDIS VALUE
# # # ============================================================

# # def decode_value(value):
# #     """
# #     Convert Redis byte values to UTF-8 strings.

# #     Works with both:
# #     - bytes
# #     - already-decoded string values
# #     """
# #     if isinstance(value, bytes):
# #         return value.decode("utf-8")

# #     return value


# # # ============================================================
# # # NORMALIZE REDIS FIELDS
# # # ============================================================

# # def normalize_fields(fields):
# #     """
# #     Convert Redis hash/stream fields into normal
# #     Python string key/value pairs.
# #     """
# #     return {
# #         decode_value(key): decode_value(value)
# #         for key, value in fields.items()
# #     }


# # # ============================================================
# # # PARSE EVENT
# # # ============================================================

# # def parse_event(raw_event):
# #     """
# #     Parse the JSON event stored inside the Redis
# #     stream's 'event' field.

# #     Returns:
# #         dict | None
# #     """
# #     if not raw_event:
# #         return None

# #     try:
# #         event = json.loads(raw_event)
# #     except (
# #         json.JSONDecodeError,
# #         TypeError,
# #     ):
# #         return None

# #     if not isinstance(event, dict):
# #         return None

# #     return event


# # # ============================================================
# # # VALIDATE STREAM
# # # ============================================================

# # def validate_stream(stream_name: str) -> str:
# #     """
# #     Accept either:
# #         detection
# #         tracking
# #         behavior

# #     or the actual Redis stream name:
# #         events.detection
# #         events.tracking
# #         events.behavior
# #     """
# #     if stream_name in STREAMS:
# #         return STREAMS[stream_name]

# #     if stream_name in STREAMS.values():
# #         return stream_name

# #     raise ValueError(
# #         "Unknown Redis stream. "
# #         "Use detection, tracking, behavior, "
# #         "events.detection, events.tracking, "
# #         "or events.behavior."
# #     )


# # # ============================================================
# # # GET EVENTS
# # # ============================================================

# # async def get_events(
# #     stream_name: str,
# #     last_id: str = "0-0",
# #     count: int = DEFAULT_COUNT,
# # ):
# #     """
# #     Read historical events from a Redis stream.

# #     Parameters:
# #         stream_name:
# #             Stream alias or actual Redis stream name.

# #         last_id:
# #             Redis stream ID to start reading from.

# #         count:
# #             Maximum number of events to return.

# #     Returns:
# #         [
# #             {
# #                 "redis_id": "...",
# #                 "event": {...}
# #             }
# #         ]
# #     """

# #     stream_name = validate_stream(
# #         stream_name
# #     )

# #     # --------------------------------------------------------
# #     # SANITIZE COUNT
# #     # --------------------------------------------------------

# #     try:
# #         count = int(count)
# #     except (
# #         TypeError,
# #         ValueError,
# #     ):
# #         count = DEFAULT_COUNT

# #     count = max(
# #         1,
# #         min(
# #             count,
# #             MAX_COUNT,
# #         ),
# #     )

# #     # --------------------------------------------------------
# #     # SANITIZE LAST ID
# #     # --------------------------------------------------------

# #     if not last_id:
# #         last_id = "0-0"

# #     last_id = str(last_id)

# #     # --------------------------------------------------------
# #     # READ REDIS STREAM
# #     # --------------------------------------------------------

# #     messages = await redis_client.xrange(
# #         name=stream_name,
# #         min=last_id,
# #         max="+",
# #         count=count,
# #     )

# #     if not messages:
# #         return []

# #     # --------------------------------------------------------
# #     # BUILD RESPONSE
# #     # --------------------------------------------------------

# #     events = []

# #     for message_id, fields in messages:

# #         message_id = decode_value(
# #             message_id
# #         )

# #         normalized_fields = normalize_fields(
# #             fields
# #         )

# #         raw_event = normalized_fields.get(
# #             "event"
# #         )

# #         event = parse_event(
# #             raw_event
# #         )

# #         # ----------------------------------------------------
# #         # Ignore malformed Redis entries.
# #         # ----------------------------------------------------

# #         if event is None:
# #             continue

# #         events.append(
# #             {
# #                 "redis_id": message_id,
# #                 "event": event,
# #             }
# #         )

# #     return events


# # # ============================================================
# # # GET LATEST EVENTS
# # # ============================================================

# # async def get_latest_events(
# #     stream_name: str,
# #     count: int = DEFAULT_COUNT,
# # ):
# #     """
# #     Return the newest events from a Redis stream.
# #     """

# #     stream_name = validate_stream(
# #         stream_name
# #     )

# #     try:
# #         count = int(count)
# #     except (
# #         TypeError,
# #         ValueError,
# #     ):
# #         count = DEFAULT_COUNT

# #     count = max(
# #         1,
# #         min(
# #             count,
# #             MAX_COUNT,
# #         ),
# #     )

# #     messages = await redis_client.xrevrange(
# #         name=stream_name,
# #         max="+",
# #         min="-",
# #         count=count,
# #     )

# #     if not messages:
# #         return []

# #     events = []

# #     for message_id, fields in messages:

# #         message_id = decode_value(
# #             message_id
# #         )

# #         normalized_fields = normalize_fields(
# #             fields
# #         )

# #         raw_event = normalized_fields.get(
# #             "event"
# #         )

# #         event = parse_event(
# #             raw_event
# #         )

# #         if event is None:
# #             continue

# #         events.append(
# #             {
# #                 "redis_id": message_id,
# #                 "event": event,
# #             }
# #         )

# #     return events



























# import asyncio
# import json
# import os
# import socket
# import sqlite3
# import uuid
# from datetime import datetime, timezone
# from pathlib import Path
# from typing import Any

# from app.messaging.redis_client import redis_client
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
# DEFAULT_STATUS = "OPEN"

# try:
#     READ_COUNT = max(
#         1,
#         int(os.getenv("INCIDENT_READ_COUNT", "10")),
#     )
# except (TypeError, ValueError):
#     READ_COUNT = 10

# try:
#     PENDING_CLAIM_IDLE_MS = max(
#         1000,
#         int(
#             os.getenv(
#                 "INCIDENT_PENDING_CLAIM_IDLE_MS",
#                 "30000",
#             )
#         ),
#     )
# except (TypeError, ValueError):
#     PENDING_CLAIM_IDLE_MS = 30000

# try:
#     CLAIM_COUNT = max(
#         1,
#         int(
#             os.getenv(
#                 "INCIDENT_CLAIM_COUNT",
#                 "20",
#             )
#         ),
#     )
# except (TypeError, ValueError):
#     CLAIM_COUNT = 20

# try:
#     PENDING_RECOVERY_INTERVAL_SECONDS = max(
#         1,
#         int(
#             os.getenv(
#                 "INCIDENT_PENDING_RECOVERY_INTERVAL_SECONDS",
#                 "10",
#             )
#         ),
#     )
# except (TypeError, ValueError):
#     PENDING_RECOVERY_INTERVAL_SECONDS = 10


# # ============================================================
# # REDIS VALUE HELPERS
# # ============================================================

# def decode_value(value: Any) -> Any:
#     """Decode Redis bytes into UTF-8 strings."""
#     if isinstance(value, bytes):
#         return value.decode("utf-8")

#     return value


# def normalize_fields(fields: Any) -> dict[str, Any]:
#     """Normalize Redis stream fields into Python strings."""
#     if not isinstance(fields, dict):
#         return {}

#     return {
#         decode_value(key): decode_value(value)
#         for key, value in fields.items()
#     }


# # ============================================================
# # DATABASE
# # ============================================================

# def get_database_connection() -> sqlite3.Connection:
#     """
#     Create a SQLite connection configured for concurrent
#     incident processing.
#     """

#     DATABASE_PATH.parent.mkdir(
#         parents=True,
#         exist_ok=True,
#     )

#     connection = sqlite3.connect(
#         str(DATABASE_PATH),
#         timeout=10.0,
#     )

#     connection.row_factory = sqlite3.Row

#     connection.execute(
#         "PRAGMA busy_timeout = 10000"
#     )

#     connection.execute(
#         "PRAGMA journal_mode = WAL"
#     )

#     connection.execute(
#         "PRAGMA foreign_keys = ON"
#     )

#     return connection


# def ensure_incidents_table() -> None:
#     """
#     Create the incidents table and required indexes.

#     This function is intentionally idempotent.
#     """

#     connection = get_database_connection()

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
#                 frame_id INTEGER,

#                 frame_timestamp TEXT,
#                 track_ids TEXT,

#                 message TEXT,

#                 status TEXT,

#                 created_at TEXT,
#                 updated_at TEXT
#             )
#             """
#         )

#         existing_columns = {
#             row["name"]
#             for row in connection.execute(
#                 "PRAGMA table_info(incidents)"
#             ).fetchall()
#         }

#         required_columns = {
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
#             "frame_id": "INTEGER",
#             "frame_timestamp": "TEXT",
#             "track_ids": "TEXT",
#             "message": "TEXT",
#             "status": "TEXT",
#             "created_at": "TEXT",
#             "updated_at": "TEXT",
#         }

#         for column_name, column_type in required_columns.items():
#             if column_name not in existing_columns:
#                 connection.execute(
#                     f"""
#                     ALTER TABLE incidents
#                     ADD COLUMN {column_name} {column_type}
#                     """
#                 )

#         connection.execute(
#             """
#             CREATE UNIQUE INDEX IF NOT EXISTS
#             idx_incidents_alert_event_id
#             ON incidents(alert_event_id)
#             WHERE alert_event_id IS NOT NULL
#             """
#         )

#         connection.execute(
#             """
#             CREATE INDEX IF NOT EXISTS
#             idx_incidents_camera_id
#             ON incidents(camera_id)
#             """
#         )

#         connection.execute(
#             """
#             CREATE INDEX IF NOT EXISTS
#             idx_incidents_status
#             ON incidents(status)
#             """
#         )

#         connection.execute(
#             """
#             CREATE INDEX IF NOT EXISTS
#             idx_incidents_created_at
#             ON incidents(created_at)
#             """
#         )

#         connection.execute(
#             """
#             CREATE INDEX IF NOT EXISTS
#             idx_incidents_correlation_id
#             ON incidents(correlation_id)
#             """
#         )

#         connection.commit()

#     finally:
#         connection.close()


# # ============================================================
# # TIMESTAMP HELPERS
# # ============================================================

# def parse_timestamp(value: Any) -> datetime | None:
#     """Parse an ISO timestamp into timezone-aware UTC datetime."""

#     if not value:
#         return None

#     if isinstance(value, datetime):
#         timestamp = value
#     else:
#         try:
#             timestamp = datetime.fromisoformat(
#                 str(value).replace("Z", "+00:00")
#             )
#         except (TypeError, ValueError):
#             return None

#     if timestamp.tzinfo is None:
#         timestamp = timestamp.replace(
#             tzinfo=timezone.utc
#         )

#     return timestamp.astimezone(timezone.utc)


# def get_event_time(
#     event: Any,
# ) -> datetime:
#     """
#     Prefer frame_timestamp, then event timestamp,
#     then current UTC time.
#     """

#     data = getattr(event, "data", {}) or {}

#     frame_timestamp = parse_timestamp(
#         data.get("frame_timestamp")
#     )

#     if frame_timestamp is not None:
#         return frame_timestamp

#     event_timestamp = parse_timestamp(
#         getattr(event, "timestamp", None)
#     )

#     if event_timestamp is not None:
#         return event_timestamp

#     return datetime.now(timezone.utc)


# # ============================================================
# # DATA NORMALIZATION
# # ============================================================

# def safe_int(value: Any) -> int | None:
#     """Safely convert a value to integer."""

#     if value is None:
#         return None

#     try:
#         return int(value)
#     except (TypeError, ValueError):
#         return None


# def normalize_track_ids(value: Any) -> list[str]:
#     """
#     Normalize track IDs into a JSON-serializable list.
#     """

#     if value is None:
#         return []

#     if isinstance(value, (list, tuple, set)):
#         return [
#             str(track_id)
#             for track_id in value
#             if track_id is not None
#         ]

#     return [str(value)]


# # ============================================================
# # INCIDENT CREATION
# # ============================================================

# def create_incident_sync(
#     event: Any,
#     redis_message_id: str | None = None,
# ) -> str | None:
#     """
#     Persist one alert.created event as an incident.

#     Duplicate alert events are safely ignored using
#     alert_event_id uniqueness.
#     """

#     if getattr(event, "event_type", None) != SUPPORTED_EVENT_TYPE:
#         return None

#     event_id = getattr(event, "event_id", None)

#     source = getattr(event, "source", None)
#     camera = getattr(event, "camera", None)
#     context = getattr(event, "context", None)
#     data = getattr(event, "data", {}) or {}

#     if not event_id:
#         raise ValueError(
#             "alert.created event is missing event_id"
#         )

#     if source is None:
#         raise ValueError(
#             "alert.created event is missing source"
#         )

#     if camera is None:
#         raise ValueError(
#             "alert.created event is missing camera"
#         )

#     if context is None:
#         raise ValueError(
#             "alert.created event is missing context"
#         )

#     mode = getattr(context, "mode", None)

#     if mode not in {"live", "historical"}:
#         raise ValueError(
#             f"Invalid event mode: {mode}"
#         )

#     alert_event_id = event_id

#     source_agent_id = getattr(
#         source,
#         "agent_id",
#         None,
#     )

#     source_instance_id = getattr(
#         source,
#         "instance_id",
#         None,
#     )

#     camera_id = getattr(
#         camera,
#         "camera_id",
#         None,
#     )

#     trace_id = getattr(
#         context,
#         "trace_id",
#         None,
#     )

#     correlation_id = getattr(
#         context,
#         "correlation_id",
#         None,
#     )

#     incident_context_id = getattr(
#         context,
#         "incident_id",
#         None,
#     )

#     alert_type = data.get(
#         "alert_type"
#     )

#     severity = data.get(
#         "severity"
#     )

#     person_count = safe_int(
#         data.get("person_count")
#     )

#     threshold = safe_int(
#         data.get("threshold")
#     )

#     frame_id = safe_int(
#         data.get("frame_id")
#     )

#     frame_timestamp = data.get(
#         "frame_timestamp"
#     )

#     track_ids = normalize_track_ids(
#         data.get("track_ids")
#     )

#     message = data.get(
#         "message"
#     )

#     event_time = get_event_time(event)

#     now = datetime.now(
#         timezone.utc
#     ).isoformat()

#     created_at = event_time.isoformat()

#     incident_id = (
#         incident_context_id
#         or str(uuid.uuid4())
#     )

#     connection = get_database_connection()

#     try:
#         existing = connection.execute(
#             """
#             SELECT incident_id
#             FROM incidents
#             WHERE alert_event_id = ?
#             """,
#             (alert_event_id,),
#         ).fetchone()

#         if existing is not None:
#             return str(
#                 existing["incident_id"]
#             )

#         connection.execute(
#             """
#             INSERT INTO incidents (
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

#                 created_at,
#                 updated_at
#             )
#             VALUES (
#                 ?, ?, ?,
#                 ?, ?, ?, ?,
#                 ?, ?, ?,
#                 ?, ?, ?,
#                 ?, ?, ?,
#                 ?, ?,
#                 ?,
#                 ?,
#                 ?, ?
#             )
#             """,
#             (
#                 incident_id,
#                 alert_event_id,
#                 event_id,

#                 camera_id,
#                 getattr(
#                     event,
#                     "event_type",
#                     None,
#                 ),
#                 alert_type,
#                 severity,

#                 mode,
#                 trace_id,
#                 correlation_id,

#                 source_agent_id,
#                 source_instance_id,
#                 redis_message_id,

#                 person_count,
#                 threshold,
#                 frame_id,

#                 frame_timestamp,
#                 json.dumps(
#                     track_ids
#                 ),

#                 message,

#                 DEFAULT_STATUS,

#                 created_at,
#                 now,
#             ),
#         )

#         connection.commit()

#         return incident_id

#     except sqlite3.IntegrityError:
#         connection.rollback()

#         existing = connection.execute(
#             """
#             SELECT incident_id
#             FROM incidents
#             WHERE alert_event_id = ?
#             """,
#             (alert_event_id,),
#         ).fetchone()

#         if existing is not None:
#             return str(
#                 existing["incident_id"]
#             )

#         raise

#     finally:
#         connection.close()


# async def create_incident(
#     event: Any,
#     redis_message_id: str | None = None,
# ) -> str | None:
#     """
#     Async wrapper around synchronous SQLite persistence.
#     """

#     return await asyncio.to_thread(
#         create_incident_sync,
#         event,
#         redis_message_id,
#     )


# # ============================================================
# # REDIS CONSUMER GROUP
# # ============================================================

# async def ensure_consumer_group() -> None:
#     """
#     Ensure the incident consumer group exists.

#     MKSTREAM allows the group to be created even when
#     events.alerts does not yet exist.
#     """

#     try:
#         await redis_client.xgroup_create(
#             name=STREAM_NAME,
#             groupname=GROUP_NAME,
#             id="0-0",
#             mkstream=True,
#         )

#         print(
#             f"[INCIDENT] Consumer group created: "
#             f"{GROUP_NAME}"
#         )

#     except Exception as exc:
#         message = str(exc).lower()

#         if (
#             "busygroup" in message
#             or "consumer group name already exists" in message
#         ):
#             return

#         raise


# # ============================================================
# # ACKNOWLEDGEMENT
# # ============================================================

# async def acknowledge(
#     redis_message_id: str,
# ) -> None:
#     """Acknowledge a successfully processed message."""

#     await redis_client.xack(
#         STREAM_NAME,
#         GROUP_NAME,
#         redis_message_id,
#     )


# # ============================================================
# # EVENT PROCESSING
# # ============================================================

# async def process_event(
#     redis_message_id: Any,
#     fields: Any,
# ) -> None:
#     """
#     Process one Redis stream message.

#     Important reliability rule:

#         ACK only after successful processing.

#     Unexpected database/application errors are re-raised,
#     leaving the Redis message pending for recovery.
#     """

#     redis_message_id = decode_value(
#         redis_message_id
#     )

#     normalized_fields = normalize_fields(
#         fields
#     )

#     raw_event = normalized_fields.get(
#         "event"
#     )

#     if not raw_event:
#         print(
#             f"[INCIDENT] Missing event field; "
#             f"ACK poison message {redis_message_id}"
#         )

#         await acknowledge(
#             redis_message_id
#         )

#         return

#     try:
#         if isinstance(raw_event, str):
#             event_dict = json.loads(
#                 raw_event
#             )
#         elif isinstance(raw_event, dict):
#             event_dict = raw_event
#         else:
#             raise ValueError(
#                 "event field must be JSON string or dict"
#             )

#     except (
#         json.JSONDecodeError,
#         TypeError,
#         ValueError,
#     ) as exc:
#         print(
#             f"[INCIDENT] Invalid JSON event "
#             f"{redis_message_id}: {exc}"
#         )

#         await acknowledge(
#             redis_message_id
#         )

#         return

#     if not isinstance(
#         event_dict,
#         dict,
#     ):
#         print(
#             f"[INCIDENT] Event is not an object; "
#             f"ACK {redis_message_id}"
#         )

#         await acknowledge(
#             redis_message_id
#         )

#         return

#     try:
#         event = validate_event(
#             event_dict
#         )

#     except Exception as exc:
#         print(
#             f"[INCIDENT] Canonical event validation "
#             f"failed for {redis_message_id}: {exc}"
#         )

#         await acknowledge(
#             redis_message_id
#         )

#         return

#     if (
#         getattr(
#             event,
#             "event_type",
#             None,
#         )
#         != SUPPORTED_EVENT_TYPE
#     ):
#         print(
#             f"[INCIDENT] Ignoring unsupported event "
#             f"type={getattr(event, 'event_type', None)} "
#             f"redis_id={redis_message_id}"
#         )

#         await acknowledge(
#             redis_message_id
#         )

#         return

#     print(
#         "[INCIDENT] Processing alert: "
#         f"event_id={event.event_id} "
#         f"camera={event.camera.camera_id} "
#         f"mode={event.context.mode} "
#         f"redis_id={redis_message_id}"
#     )

#     try:
#         incident_id = await create_incident(
#             event,
#             redis_message_id,
#         )

#         await acknowledge(
#             redis_message_id
#         )

#         print(
#             "[INCIDENT] Processed successfully: "
#             f"incident_id={incident_id} "
#             f"event_id={event.event_id}"
#         )

#     except asyncio.CancelledError:
#         raise

#     except Exception as exc:
#         print(
#             "[INCIDENT] Processing failed; "
#             f"message remains pending. "
#             f"redis_id={redis_message_id} "
#             f"error={exc}"
#         )

#         raise


# # ============================================================
# # PENDING MESSAGE RECOVERY
# # ============================================================

# async def recover_pending_messages() -> int:
#     """
#     Recover stale pending messages using XAUTOCLAIM.

#     Each recovered message is processed independently so
#     one bad message cannot terminate recovery of others.
#     """

#     recovered_count = 0

#     try:
#         result = await redis_client.xautoclaim(
#             name=STREAM_NAME,
#             groupname=GROUP_NAME,
#             consumername=CONSUMER_NAME,
#             min_idle_time=PENDING_CLAIM_IDLE_MS,
#             start_id="0-0",
#             count=CLAIM_COUNT,
#         )

#     except (
#         asyncio.CancelledError
#     ):
#         raise

#     except Exception as exc:
#         print(
#             f"[INCIDENT] Pending recovery Redis error: "
#             f"{exc}"
#         )

#         return 0

#     if not result:
#         return 0

#     try:
#         messages = result[1]
#     except (
#         IndexError,
#         TypeError,
#     ):
#         return 0

#     for message_id, fields in messages:
#         try:
#             await process_event(
#                 message_id,
#                 fields,
#             )

#             recovered_count += 1

#         except asyncio.CancelledError:
#             raise

#         except Exception as exc:
#             print(
#                 "[INCIDENT] Recovered message processing "
#                 f"failed; isolated message. "
#                 f"id={decode_value(message_id)} "
#                 f"error={exc}"
#             )

#     return recovered_count


# async def pending_recovery_loop() -> None:
#     """
#     Periodically recover stale pending messages.
#     """

#     while True:
#         try:
#             await recover_pending_messages()

#         except asyncio.CancelledError:
#             raise

#         except Exception as exc:
#             print(
#                 f"[INCIDENT] Pending recovery loop error: "
#                 f"{exc}"
#             )

#         await asyncio.sleep(
#             PENDING_RECOVERY_INTERVAL_SECONDS
#         )


# # ============================================================
# # MAIN CONSUMER
# # ============================================================

# async def consume_events() -> None:
#     """
#     Durable incident consumer.

#     Flow:

#         events.alerts
#              ↓
#         consumer group
#              ↓
#         canonical validation
#              ↓
#         alert.created filtering
#              ↓
#         SQLite incident persistence
#              ↓
#         ACK

#     Failed processing remains pending and can be
#     automatically recovered.
#     """

#     await asyncio.to_thread(
#         ensure_incidents_table
#     )

#     await ensure_consumer_group()

#     print(
#         "[INCIDENT] Consumer started: "
#         f"stream={STREAM_NAME} "
#         f"group={GROUP_NAME} "
#         f"consumer={CONSUMER_NAME}"
#     )

#     recovery_task = asyncio.create_task(
#         pending_recovery_loop()
#     )

#     try:
#         while True:
#             try:
#                 messages = await redis_client.xreadgroup(
#                     groupname=GROUP_NAME,
#                     consumername=CONSUMER_NAME,
#                     streams={
#                         STREAM_NAME: ">"
#                     },
#                     count=READ_COUNT,
#                     block=5000,
#                 )

#             except asyncio.CancelledError:
#                 raise

#             except Exception as exc:
#                 print(
#                     f"[INCIDENT] Redis read error: "
#                     f"{exc}"
#                 )

#                 await asyncio.sleep(2)

#                 continue

#             if not messages:
#                 continue

#             for stream_name, stream_messages in messages:
#                 for message_id, fields in stream_messages:

#                     try:
#                         await process_event(
#                             message_id,
#                             fields,
#                         )

#                     except asyncio.CancelledError:
#                         raise

#                     except Exception as exc:
#                         print(
#                             "[INCIDENT] Message processing "
#                             f"failed but consumer continues. "
#                             f"id={decode_value(message_id)} "
#                             f"error={exc}"
#                         )

#     finally:
#         recovery_task.cancel()

#         try:
#             await recovery_task

#         except asyncio.CancelledError:
#             pass

#         except Exception as exc:
#             print(
#                 f"[INCIDENT] Recovery task shutdown error: "
#                 f"{exc}"
#             )


# # ============================================================
# # ENTRY POINT
# # ============================================================

# def main() -> None:
#     """Run the incident consumer."""

#     asyncio.run(
#         consume_events()
#     )


# if __name__ == "__main__":
#     main()
















"""
Generic Redis event-stream query helpers.

This module is intentionally separate from the Incident Agent consumer.

Responsibilities:
    - Read historical/latest events from Redis Streams.
    - Decode Redis byte values.
    - Normalize stream fields.
    - Parse canonical event JSON.
    - Validate canonical events.
    - Provide lightweight API-facing stream queries.

Non-responsibilities:
    - Creating incidents.
    - Updating incidents.
    - Evidence generation.
    - Incident recovery.
    - Agent supervision.
    - Running background consumers.

Incident processing belongs to:
    backend.app.messaging.consumer
"""

from __future__ import annotations

import json
from typing import Any

from backend.app.messaging.redis_client import redis_client
from shared.schemas.event_schema import validate_event


# ============================================================
# STREAM CONFIGURATION
# ============================================================

STREAMS: dict[str, str] = {
    "detection": "events.detection",
    "tracking": "events.tracking",
    "behavior": "events.behavior",
}


# ============================================================
# REDIS VALUE HELPERS
# ============================================================

def decode_value(value: Any) -> Any:
    """
    Decode Redis bytes into UTF-8 strings.

    Non-byte values are returned unchanged.
    """
    if isinstance(value, bytes):
        return value.decode("utf-8")

    return value


def normalize_fields(fields: Any) -> dict[str, Any]:
    """
    Normalize Redis stream fields into a Python dictionary.

    Redis clients may return byte keys and byte values.
    """
    if not isinstance(fields, dict):
        return {}

    return {
        decode_value(key): decode_value(value)
        for key, value in fields.items()
    }


# ============================================================
# EVENT PARSING
# ============================================================

def parse_event(fields: Any) -> dict[str, Any] | None:
    """
    Parse a Redis stream message into a canonical event dictionary.

    Expected Redis format:

        {
            "event": "<JSON>"
        }

    A dictionary event is also accepted for compatibility.

    Invalid events return None rather than raising so that one
    malformed event cannot break API-level event retrieval.
    """
    normalized_fields = normalize_fields(fields)

    raw_event = normalized_fields.get("event")

    if raw_event is None:
        return None

    try:
        if isinstance(raw_event, str):
            event = json.loads(raw_event)

        elif isinstance(raw_event, dict):
            event = raw_event

        else:
            return None

    except (
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ):
        return None

    if not isinstance(event, dict):
        return None

    try:
        validated_event = validate_event(event)
    except Exception:
        return None

    return validated_event.to_dict()


# ============================================================
# STREAM VALIDATION
# ============================================================

def validate_stream(stream_name: str) -> str:
    """
    Validate that an API-requested stream belongs to the
    known application streams.

    Raises:
        ValueError: if the stream is not registered.
    """
    if not isinstance(stream_name, str):
        raise ValueError("stream_name must be a string")

    normalized = stream_name.strip()

    if not normalized:
        raise ValueError("stream_name cannot be empty")

    if normalized not in STREAMS.values():
        raise ValueError(
            f"Unsupported event stream: {normalized}"
        )

    return normalized


# ============================================================
# EVENT RETRIEVAL
# ============================================================

async def get_events(
    stream_name: str,
    last_id: str = "0-0",
    count: int = 20,
) -> list[dict[str, Any]]:
    """
    Retrieve events from a Redis stream.

    Args:
        stream_name:
            One of the registered application streams.

        last_id:
            Redis stream ID from which to read.
            Example: "0-0".

        count:
            Maximum number of events to retrieve.

    Returns:
        A list of validated canonical event dictionaries.

    Notes:
        Invalid/malformed events are skipped rather than allowing
        one bad stream entry to break the entire API request.
    """
    stream_name = validate_stream(stream_name)

    try:
        count = int(count)
    except (TypeError, ValueError):
        count = 20

    count = max(1, min(count, 100))

    if not isinstance(last_id, str) or not last_id.strip():
        last_id = "0-0"

    try:
        messages = await redis_client.xrange(
            name=stream_name,
            min=last_id,
            count=count,
        )
    except Exception as exc:
        print(
            "[EVENT_CONSUMER] Redis read error: "
            f"stream={stream_name} "
            f"error={exc}"
        )
        return []

    events: list[dict[str, Any]] = []

    for redis_message_id, fields in messages:
        try:
            event = parse_event(fields)

            if event is None:
                continue

            event["_redis_id"] = decode_value(
                redis_message_id
            )

            events.append(event)

        except Exception as exc:
            print(
                "[EVENT_CONSUMER] Event parsing failed; "
                f"stream={stream_name} "
                f"redis_id={decode_value(redis_message_id)} "
                f"error={exc}"
            )

    return events


# ============================================================
# LATEST EVENTS
# ============================================================

async def get_latest_events(
    stream_name: str,
    count: int = 20,
) -> list[dict[str, Any]]:
    """
    Retrieve the latest validated events from a Redis stream.

    Uses XREVRANGE so the newest events are returned first.
    """
    stream_name = validate_stream(stream_name)

    try:
        count = int(count)
    except (TypeError, ValueError):
        count = 20

    count = max(1, min(count, 100))

    try:
        messages = await redis_client.xrevrange(
            name=stream_name,
            max="+",
            min="-",
            count=count,
        )
    except Exception as exc:
        print(
            "[EVENT_CONSUMER] Redis latest-events error: "
            f"stream={stream_name} "
            f"error={exc}"
        )
        return []

    events: list[dict[str, Any]] = []

    for redis_message_id, fields in messages:
        try:
            event = parse_event(fields)

            if event is None:
                continue

            event["_redis_id"] = decode_value(
                redis_message_id
            )

            events.append(event)

        except Exception as exc:
            print(
                "[EVENT_CONSUMER] Latest event parsing failed; "
                f"stream={stream_name} "
                f"redis_id={decode_value(redis_message_id)} "
                f"error={exc}"
            )

    return events


# ============================================================
# STREAM-SPECIFIC HELPERS
# ============================================================

async def get_detection_events(
    last_id: str = "0-0",
    count: int = 20,
) -> list[dict[str, Any]]:
    """
    Retrieve validated detection events.
    """
    return await get_events(
        STREAMS["detection"],
        last_id,
        count,
    )


async def get_tracking_events(
    last_id: str = "0-0",
    count: int = 20,
) -> list[dict[str, Any]]:
    """
    Retrieve validated tracking events.
    """
    return await get_events(
        STREAMS["tracking"],
        last_id,
        count,
    )


async def get_behavior_events(
    last_id: str = "0-0",
    count: int = 20,
) -> list[dict[str, Any]]:
    """
    Retrieve validated behavior events.
    """
    return await get_events(
        STREAMS["behavior"],
        last_id,
        count,
    )


# ============================================================
# PUBLIC API
# ============================================================

__all__ = [
    "STREAMS",
    "decode_value",
    "normalize_fields",
    "parse_event",
    "validate_stream",
    "get_events",
    "get_latest_events",
    "get_detection_events",
    "get_tracking_events",
    "get_behavior_events",
]
