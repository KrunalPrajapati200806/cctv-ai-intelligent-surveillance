# # # # import asyncio
# # # # import json
# # # # import os
# # # # import uuid
# # # # from datetime import datetime, timezone

# # # # import redis.asyncio as redis


# # # # # ============================================================
# # # # # CONFIG
# # # # # ============================================================

# # # # REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
# # # # REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# # # # INPUT_STREAM = "events.behavior"
# # # # OUTPUT_STREAM = "events.alerts"

# # # # GROUP_NAME = "alert-workers"
# # # # CONSUMER_NAME = "alert-01"


# # # # # ============================================================
# # # # # REDIS CONSUMER GROUP
# # # # # ============================================================

# # # # async def ensure_consumer_group(redis_client):

# # # #     try:

# # # #         await redis_client.xgroup_create(
# # # #             name=INPUT_STREAM,
# # # #             groupname=GROUP_NAME,
# # # #             id="0",
# # # #             mkstream=True,
# # # #         )

# # # #         print(
# # # #             f"Created consumer group: {GROUP_NAME}"
# # # #         )

# # # #     except redis.ResponseError as exc:

# # # #         if "BUSYGROUP" in str(exc):

# # # #             print(
# # # #                 f"Consumer group already exists: "
# # # #                 f"{GROUP_NAME}"
# # # #             )

# # # #         else:
# # # #             raise


# # # # # ============================================================
# # # # # CREATE ALERT EVENT
# # # # # ============================================================

# # # # async def emit_alert_event(
# # # #     redis_client,
# # # #     behavior_event,
# # # # ):

# # # #     # --------------------------------------------------------
# # # #     # CAMERA
# # # #     # --------------------------------------------------------

# # # #     camera = behavior_event.get(
# # # #         "camera",
# # # #         {},
# # # #     )

# # # #     camera_id = camera.get(
# # # #         "camera_id",
# # # #         "unknown",
# # # #     )

# # # #     # --------------------------------------------------------
# # # #     # DATA
# # # #     # --------------------------------------------------------

# # # #     data = behavior_event.get(
# # # #         "data",
# # # #         {},
# # # #     )

# # # #     if not isinstance(data, dict):
# # # #         data = {}

# # # #     event_type = behavior_event.get(
# # # #         "event_type"
# # # #     )

# # # #     # ========================================================
# # # #     # COMMON VALUES
# # # #     # ========================================================

# # # #     person_count = data.get(
# # # #         "person_count",
# # # #         1,
# # # #     )

# # # #     severity = data.get(
# # # #         "severity",
# # # #         "low",
# # # #     )

# # # #     threshold = data.get(
# # # #         "threshold",
# # # #         0,
# # # #     )

# # # #     frame_id = data.get(
# # # #         "frame_id"
# # # #     )

# # # #     track_ids = data.get(
# # # #         "track_ids",
# # # #         [],
# # # #     )

# # # #     if not isinstance(track_ids, list):
# # # #         track_ids = []

# # # #     alert_type = event_type

# # # #     # ========================================================
# # # #     # CROWD
# # # #     # ========================================================

# # # #     if event_type == "crowd.detected":

# # # #         message = (
# # # #             f"Crowd detected on "
# # # #             f"{camera_id}: "
# # # #             f"{person_count} person(s)"
# # # #         )

# # # #     # ========================================================
# # # #     # LOITERING
# # # #     # ========================================================

# # # #     elif event_type == "loitering.detected":

# # # #         track_id = data.get(
# # # #             "track_id"
# # # #         )

# # # #         duration = data.get(
# # # #             "duration_seconds",
# # # #             0,
# # # #         )

# # # #         person_count = 1

# # # #         if track_id:
# # # #             track_ids = [track_id]

# # # #         message = (
# # # #             f"Possible loitering detected "
# # # #             f"on {camera_id}: "
# # # #             f"person remained for "
# # # #             f"{float(duration):.1f} seconds"
# # # #         )

# # # #     # ========================================================
# # # #     # INTRUSION
# # # #     # ========================================================

# # # #     elif event_type == "intrusion.detected":

# # # #         track_id = data.get(
# # # #             "track_id"
# # # #         )

# # # #         person_count = data.get(
# # # #             "person_count",
# # # #             1,
# # # #         )

# # # #         if track_id:

# # # #             track_ids = [track_id]

# # # #         # Intrusion should normally be high/critical.
# # # #         # Preserve the security agent's severity.

# # # #         if severity not in {
# # # #             "low",
# # # #             "medium",
# # # #             "high",
# # # #             "critical",
# # # #         }:

# # # #             severity = "high"

# # # #         message = (
# # # #             f"Security zone intrusion detected "
# # # #             f"on {camera_id}"
# # # #         )

# # # #         if track_id:

# # # #             message += (
# # # #                 f" | Track={track_id}"
# # # #             )

# # # #     # ========================================================
# # # #     # UNKNOWN
# # # #     # ========================================================

# # # #     else:

# # # #         print(
# # # #             f"Unsupported behavior event: "
# # # #             f"{event_type}"
# # # #         )

# # # #         return

# # # #     # ========================================================
# # # #     # CREATE ALERT
# # # #     # ========================================================

# # # #     alert_event = {

# # # #         "event_id": str(
# # # #             uuid.uuid4()
# # # #         ),

# # # #         "event_type":
# # # #             "alert.created",

# # # #         "version":
# # # #             "1.0",

# # # #         "timestamp":
# # # #             datetime.now(
# # # #                 timezone.utc
# # # #             ).isoformat(),

# # # #         "source": {

# # # #             "agent_id":
# # # #                 CONSUMER_NAME,
# # # #         },

# # # #         "camera": {

# # # #             "camera_id":
# # # #                 camera_id,
# # # #         },

# # # #         "data": {

# # # #             "alert_type":
# # # #                 alert_type,

# # # #             "severity":
# # # #                 severity,

# # # #             "person_count":
# # # #                 person_count,

# # # #             "threshold":
# # # #                 threshold,

# # # #             "frame_id":
# # # #                 frame_id,

# # # #             "track_ids":
# # # #                 track_ids,

# # # #             "message":
# # # #                 message,

# # # #             "source_event_id":
# # # #                 behavior_event.get(
# # # #                     "event_id"
# # # #                 ),
# # # #         },
# # # #     }

# # # #     # ========================================================
# # # #     # PUBLISH
# # # #     # ========================================================

# # # #     output_id = await redis_client.xadd(
# # # #         OUTPUT_STREAM,
# # # #         {
# # # #             "event":
# # # #                 json.dumps(
# # # #                     alert_event
# # # #                 )
# # # #         },
# # # #     )

# # # #     print(
# # # #         f"🚨 ALERT CREATED | "
# # # #         f"Camera={camera_id} | "
# # # #         f"Type={alert_type} | "
# # # #         f"Severity={severity} | "
# # # #         f"Count={person_count} | "
# # # #         f"Redis={output_id}"
# # # #     )


# # # # # ============================================================
# # # # # PROCESS BEHAVIOR EVENT
# # # # # ============================================================

# # # # async def process_behavior_event(
# # # #     redis_client,
# # # #     event,
# # # # ):

# # # #     event_type = event.get(
# # # #         "event_type"
# # # #     )

# # # #     print(
# # # #         f"Received behavior event | "
# # # #         f"Type={event_type}"
# # # #     )

# # # #     # --------------------------------------------------------
# # # #     # ALL SUPPORTED SECURITY EVENTS
# # # #     # --------------------------------------------------------

# # # #     supported_events = {

# # # #         "crowd.detected",

# # # #         "loitering.detected",

# # # #         "intrusion.detected",
# # # #     }

# # # #     if event_type not in supported_events:

# # # #         print(
# # # #             f"Ignoring unsupported event type: "
# # # #             f"{event_type}"
# # # #         )

# # # #         return

# # # #     await emit_alert_event(
# # # #         redis_client,
# # # #         event,
# # # #     )


# # # # # ============================================================
# # # # # MAIN
# # # # # ============================================================

# # # # async def main():

# # # #     redis_client = redis.Redis(

# # # #         host=REDIS_HOST,

# # # #         port=REDIS_PORT,

# # # #         decode_responses=True,

# # # #         socket_connect_timeout=5,

# # # #         socket_timeout=None,
# # # #     )

# # # #     await redis_client.ping()

# # # #     await ensure_consumer_group(
# # # #         redis_client
# # # #     )

# # # #     print("=" * 60)

# # # #     print(
# # # #         f"Alert Agent started: "
# # # #         f"{CONSUMER_NAME}"
# # # #     )

# # # #     print(
# # # #         f"Input stream: "
# # # #         f"{INPUT_STREAM}"
# # # #     )

# # # #     print(
# # # #         f"Output stream: "
# # # #         f"{OUTPUT_STREAM}"
# # # #     )

# # # #     print(
# # # #         "Supported events: "
# # # #         "crowd.detected, "
# # # #         "loitering.detected, "
# # # #         "intrusion.detected"
# # # #     )

# # # #     print("=" * 60)

# # # #     try:

# # # #         while True:

# # # #             try:

# # # #                 messages = (
# # # #                     await redis_client.xreadgroup(

# # # #                         groupname=
# # # #                             GROUP_NAME,

# # # #                         consumername=
# # # #                             CONSUMER_NAME,

# # # #                         streams={
# # # #                             INPUT_STREAM: ">"
# # # #                         },

# # # #                         count=10,

# # # #                         block=5000,
# # # #                     )
# # # #                 )

# # # #             except redis.exceptions.TimeoutError:

# # # #                 print(
# # # #                     "Redis read timeout; "
# # # #                     "continuing..."
# # # #                 )

# # # #                 continue

# # # #             if not messages:
# # # #                 continue

# # # #             for (
# # # #                 stream_name,
# # # #                 stream_messages,
# # # #             ) in messages:

# # # #                 for (
# # # #                     redis_id,
# # # #                     fields,
# # # #                 ) in stream_messages:

# # # #                     try:

# # # #                         raw_event = fields.get(
# # # #                             "event"
# # # #                         )

# # # #                         if not raw_event:

# # # #                             print(
# # # #                                 f"Missing event payload: "
# # # #                                 f"{redis_id}"
# # # #                             )

# # # #                             await redis_client.xack(
# # # #                                 INPUT_STREAM,
# # # #                                 GROUP_NAME,
# # # #                                 redis_id,
# # # #                             )

# # # #                             continue

# # # #                         event = json.loads(
# # # #                             raw_event
# # # #                         )

# # # #                         await process_behavior_event(
# # # #                             redis_client,
# # # #                             event,
# # # #                         )

# # # #                         await redis_client.xack(
# # # #                             INPUT_STREAM,
# # # #                             GROUP_NAME,
# # # #                             redis_id,
# # # #                         )

# # # #                     except json.JSONDecodeError as exc:

# # # #                         print(
# # # #                             f"Invalid JSON | "
# # # #                             f"Redis={redis_id} | "
# # # #                             f"Error={exc}"
# # # #                         )

# # # #                         await redis_client.xack(
# # # #                             INPUT_STREAM,
# # # #                             GROUP_NAME,
# # # #                             redis_id,
# # # #                         )

# # # #                     except Exception as exc:

# # # #                         print(
# # # #                             f"ERROR processing "
# # # #                             f"{redis_id} | "
# # # #                             f"{type(exc).__name__}: "
# # # #                             f"{exc}"
# # # #                         )

# # # #                         # Do NOT ACK on processing errors.
# # # #                         # Redis will keep the message pending.

# # # #     except KeyboardInterrupt:

# # # #         print(
# # # #             "Alert Agent interrupted."
# # # #         )

# # # #     finally:

# # # #         await redis_client.aclose()

# # # #         print(
# # # #             "Alert Agent stopped."
# # # #         )


# # # # # ============================================================
# # # # # ENTRY POINT
# # # # # ============================================================

# # # # if __name__ == "__main__":

# # # #     asyncio.run(
# # # #         main()
# # # #     )





















# # # import asyncio
# # # import json
# # # import os
# # # import uuid
# # # from datetime import datetime, timezone

# # # import redis.asyncio as redis


# # # # ============================================================
# # # # CONFIG
# # # # ============================================================

# # # REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
# # # REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# # # INPUT_STREAM = "events.behavior"
# # # OUTPUT_STREAM = "events.alerts"

# # # GROUP_NAME = "alert-workers"
# # # CONSUMER_NAME = "alert-01"


# # # # ============================================================
# # # # REDIS CONSUMER GROUP
# # # # ============================================================

# # # async def ensure_consumer_group(redis_client):

# # #     try:

# # #         await redis_client.xgroup_create(
# # #             name=INPUT_STREAM,
# # #             groupname=GROUP_NAME,
# # #             id="0",
# # #             mkstream=True,
# # #         )

# # #         print(
# # #             f"Created consumer group: {GROUP_NAME}"
# # #         )

# # #     except redis.ResponseError as exc:

# # #         if "BUSYGROUP" in str(exc):

# # #             print(
# # #                 f"Consumer group already exists: "
# # #                 f"{GROUP_NAME}"
# # #             )

# # #         else:
# # #             raise


# # # # ============================================================
# # # # CREATE ALERT EVENT
# # # # ============================================================

# # # async def emit_alert_event(
# # #     redis_client,
# # #     behavior_event,
# # # ):

# # #     # --------------------------------------------------------
# # #     # CAMERA
# # #     # --------------------------------------------------------

# # #     camera = behavior_event.get(
# # #         "camera",
# # #         {},
# # #     )

# # #     camera_id = camera.get(
# # #         "camera_id",
# # #         "unknown",
# # #     )

# # #     # --------------------------------------------------------
# # #     # DATA
# # #     # --------------------------------------------------------

# # #     data = behavior_event.get(
# # #         "data",
# # #         {},
# # #     )

# # #     if not isinstance(data, dict):
# # #         data = {}

# # #     event_type = behavior_event.get(
# # #         "event_type"
# # #     )

# # #     # ========================================================
# # #     # COMMON VALUES
# # #     # ========================================================

# # #     person_count = data.get(
# # #         "person_count",
# # #         1,
# # #     )

# # #     severity = data.get(
# # #         "severity",
# # #         "low",
# # #     )

# # #     threshold = data.get(
# # #         "threshold",
# # #         0,
# # #     )

# # #     frame_id = data.get(
# # #         "frame_id"
# # #     )

# # #     track_ids = data.get(
# # #         "track_ids",
# # #         [],
# # #     )

# # #     if not isinstance(track_ids, list):
# # #         track_ids = []

# # #     alert_type = event_type

# # #     # ========================================================
# # #     # CROWD
# # #     # ========================================================

# # #     if event_type == "crowd.detected":

# # #         message = (
# # #             f"Crowd detected on "
# # #             f"{camera_id}: "
# # #             f"{person_count} person(s)"
# # #         )

# # #     # ========================================================
# # #     # LOITERING
# # #     # ========================================================

# # #     elif event_type == "loitering.detected":

# # #         track_id = data.get(
# # #             "track_id"
# # #         )

# # #         duration = data.get(
# # #             "duration_seconds",
# # #             0,
# # #         )

# # #         person_count = 1

# # #         if track_id:
# # #             track_ids = [track_id]

# # #         message = (
# # #             f"Possible loitering detected "
# # #             f"on {camera_id}: "
# # #             f"person remained for "
# # #             f"{float(duration):.1f} seconds"
# # #         )

# # #     # ========================================================
# # #     # INTRUSION
# # #     # ========================================================

# # #     elif event_type == "intrusion.detected":

# # #         track_id = data.get(
# # #             "track_id"
# # #         )

# # #         person_count = data.get(
# # #             "person_count",
# # #             1,
# # #         )

# # #         if track_id:

# # #             track_ids = [track_id]

# # #         # Intrusion should normally be high/critical.
# # #         # Preserve the security agent's severity.

# # #         if severity not in {
# # #             "low",
# # #             "medium",
# # #             "high",
# # #             "critical",
# # #         }:

# # #             severity = "high"

# # #         message = (
# # #             f"Security zone intrusion detected "
# # #             f"on {camera_id}"
# # #         )

# # #         if track_id:

# # #             message += (
# # #                 f" | Track={track_id}"
# # #             )

# # #     # ========================================================
# # #     # UNKNOWN
# # #     # ========================================================

# # #     else:

# # #         print(
# # #             f"Unsupported behavior event: "
# # #             f"{event_type}"
# # #         )

# # #         return

# # #     # ========================================================
# # #     # CREATE ALERT
# # #     # ========================================================

# # #     alert_event = {

# # #         "event_id": str(
# # #             uuid.uuid4()
# # #         ),

# # #         "event_type":
# # #             "alert.created",

# # #         "version":
# # #             "1.0",

# # #         "timestamp":
# # #             datetime.now(
# # #                 timezone.utc
# # #             ).isoformat(),

# # #         "source": {

# # #             "agent_id":
# # #                 CONSUMER_NAME,
# # #         },

# # #         "camera": {

# # #             "camera_id":
# # #                 camera_id,
# # #         },

# # #         "data": {

# # #             "alert_type":
# # #                 alert_type,

# # #             "severity":
# # #                 severity,

# # #             "person_count":
# # #                 person_count,

# # #             "threshold":
# # #                 threshold,

# # #             "frame_id":
# # #                 frame_id,

# # #             "track_ids":
# # #                 track_ids,

# # #             "message":
# # #                 message,

# # #             "source_event_id":
# # #                 behavior_event.get(
# # #                     "event_id"
# # #                 ),
# # #         },
# # #     }

# # #     # ========================================================
# # #     # PUBLISH
# # #     # ========================================================

# # #     output_id = await redis_client.xadd(
# # #         OUTPUT_STREAM,
# # #         {
# # #             "event":
# # #                 json.dumps(
# # #                     alert_event
# # #                 )
# # #         },
# # #     )

# # #     print(
# # #         f"🚨 ALERT CREATED | "
# # #         f"Camera={camera_id} | "
# # #         f"Type={alert_type} | "
# # #         f"Severity={severity} | "
# # #         f"Count={person_count} | "
# # #         f"Redis={output_id}"
# # #     )


# # # # ============================================================
# # # # PROCESS BEHAVIOR EVENT
# # # # ============================================================

# # # async def process_behavior_event(
# # #     redis_client,
# # #     event,
# # # ):

# # #     event_type = event.get(
# # #         "event_type"
# # #     )

# # #     print(
# # #         f"Received behavior event | "
# # #         f"Type={event_type}"
# # #     )

# # #     # --------------------------------------------------------
# # #     # ALL SUPPORTED SECURITY EVENTS
# # #     # --------------------------------------------------------

# # #     supported_events = {

# # #         "crowd.detected",

# # #         "loitering.detected",

# # #         "intrusion.detected",
# # #     }

# # #     if event_type not in supported_events:

# # #         print(
# # #             f"Ignoring unsupported event type: "
# # #             f"{event_type}"
# # #         )

# # #         return

# # #     await emit_alert_event(
# # #         redis_client,
# # #         event,
# # #     )


# # # # ============================================================
# # # # MAIN
# # # # ============================================================

# # # async def main():

# # #     redis_client = redis.Redis(

# # #         host=REDIS_HOST,

# # #         port=REDIS_PORT,

# # #         decode_responses=True,

# # #         socket_connect_timeout=5,

# # #         socket_timeout=None,
# # #     )

# # #     await redis_client.ping()

# # #     await ensure_consumer_group(
# # #         redis_client
# # #     )

# # #     print("=" * 60)

# # #     print(
# # #         f"Alert Agent started: "
# # #         f"{CONSUMER_NAME}"
# # #     )

# # #     print(
# # #         f"Input stream: "
# # #         f"{INPUT_STREAM}"
# # #     )

# # #     print(
# # #         f"Output stream: "
# # #         f"{OUTPUT_STREAM}"
# # #     )

# # #     print(
# # #         "Supported events: "
# # #         "crowd.detected, "
# # #         "loitering.detected, "
# # #         "intrusion.detected"
# # #     )

# # #     print("=" * 60)

# # #     try:

# # #         while True:

# # #             try:

# # #                 messages = (
# # #                     await redis_client.xreadgroup(

# # #                         groupname=
# # #                             GROUP_NAME,

# # #                         consumername=
# # #                             CONSUMER_NAME,

# # #                         streams={
# # #                             INPUT_STREAM: ">"
# # #                         },

# # #                         count=10,

# # #                         block=5000,
# # #                     )
# # #                 )

# # #             except redis.exceptions.TimeoutError:

# # #                 print(
# # #                     "Redis read timeout; "
# # #                     "continuing..."
# # #                 )

# # #                 continue

# # #             if not messages:
# # #                 continue

# # #             for (
# # #                 stream_name,
# # #                 stream_messages,
# # #             ) in messages:

# # #                 for (
# # #                     redis_id,
# # #                     fields,
# # #                 ) in stream_messages:

# # #                     try:

# # #                         raw_event = fields.get(
# # #                             "event"
# # #                         )

# # #                         if not raw_event:

# # #                             print(
# # #                                 f"Missing event payload: "
# # #                                 f"{redis_id}"
# # #                             )

# # #                             await redis_client.xack(
# # #                                 INPUT_STREAM,
# # #                                 GROUP_NAME,
# # #                                 redis_id,
# # #                             )

# # #                             continue

# # #                         event = json.loads(
# # #                             raw_event
# # #                         )

# # #                         await process_behavior_event(
# # #                             redis_client,
# # #                             event,
# # #                         )

# # #                         await redis_client.xack(
# # #                             INPUT_STREAM,
# # #                             GROUP_NAME,
# # #                             redis_id,
# # #                         )

# # #                     except json.JSONDecodeError as exc:

# # #                         print(
# # #                             f"Invalid JSON | "
# # #                             f"Redis={redis_id} | "
# # #                             f"Error={exc}"
# # #                         )

# # #                         await redis_client.xack(
# # #                             INPUT_STREAM,
# # #                             GROUP_NAME,
# # #                             redis_id,
# # #                         )

# # #                     except Exception as exc:

# # #                         print(
# # #                             f"ERROR processing "
# # #                             f"{redis_id} | "
# # #                             f"{type(exc).__name__}: "
# # #                             f"{exc}"
# # #                         )

# # #                         # Do NOT ACK on processing errors.
# # #                         # Redis will keep the message pending.

# # #     except KeyboardInterrupt:

# # #         print(
# # #             "Alert Agent interrupted."
# # #         )

# # #     finally:

# # #         await redis_client.aclose()

# # #         print(
# # #             "Alert Agent stopped."
# # #         )


# # # # ============================================================
# # # # ENTRY POINT
# # # # ============================================================

# # # if __name__ == "__main__":

# # #     asyncio.run(
# # #         main()
# # #     )
































# # import asyncio
# # import json
# # import os
# # import uuid
# # from typing import Optional

# # from shared.agent.base_agent import BaseAgent


# # INPUT_STREAM = "events.behavior"
# # OUTPUT_STREAM = "events.alerts"
# # GROUP_NAME = "alert-workers"
# # DEFAULT_AGENT_ID = "alert-01"

# # READ_COUNT = 10
# # READ_BLOCK_MS = 5000


# # class AlertAgent(BaseAgent):

# #     def __init__(
# #         self,
# #         agent_id: Optional[str] = None,
# #     ):
# #         super().__init__(
# #             agent_id=agent_id
# #         )

# #         # Unique consumer identity.
# #         # This allows multiple Alert Agent instances
# #         # to work independently in the same consumer group.
# #         self.consumer_name = (
# #             f"{self.agent_id}-"
# #             f"{uuid.uuid4().hex[:8]}"
# #         )

# #         self.supported_events = {
# #             "crowd.detected",
# #             "loitering.detected",
# #             "intrusion.detected",
# #         }

# #     # ============================================================
# #     # STARTUP
# #     # ============================================================

# #     async def on_start(self):
# #         await self.ensure_consumer_group()

# #         print(
# #             f"[{self.agent_id}] Alert agent ready."
# #         )
# #         print(
# #             f"[{self.agent_id}] Input: "
# #             f"{INPUT_STREAM}"
# #         )
# #         print(
# #             f"[{self.agent_id}] Output: "
# #             f"{OUTPUT_STREAM}"
# #         )
# #         print(
# #             f"[{self.agent_id}] Consumer group: "
# #             f"{GROUP_NAME}"
# #         )
# #         print(
# #             f"[{self.agent_id}] Consumer: "
# #             f"{self.consumer_name}"
# #         )
# #         print(
# #             f"[{self.agent_id}] Supported events: "
# #             f"crowd.detected, "
# #             f"loitering.detected, "
# #             f"intrusion.detected"
# #         )

# #     # ============================================================
# #     # SHUTDOWN
# #     # ============================================================

# #     async def on_stop(self):
# #         print(
# #             f"[{self.agent_id}] "
# #             f"Alert agent cleanup complete."
# #         )

# #     # ============================================================
# #     # REDIS CONSUMER GROUP
# #     # ============================================================

# #     async def ensure_consumer_group(self):
# #         if not self.redis_client:
# #             raise RuntimeError(
# #                 "Redis client is not initialized."
# #             )

# #         try:
# #             await self.redis_client.xgroup_create(
# #                 name=INPUT_STREAM,
# #                 groupname=GROUP_NAME,
# #                 id="0",
# #                 mkstream=True,
# #             )

# #             print(
# #                 f"[{self.agent_id}] "
# #                 f"Created consumer group: "
# #                 f"{GROUP_NAME}"
# #             )

# #         except Exception as exc:

# #             if "BUSYGROUP" in str(exc):
# #                 print(
# #                     f"[{self.agent_id}] "
# #                     f"Consumer group already exists: "
# #                     f"{GROUP_NAME}"
# #                 )
# #             else:
# #                 raise

# #     # ============================================================
# #     # CREATE ALERT EVENT
# #     # ============================================================

# #     async def emit_alert_event(
# #         self,
# #         behavior_event,
# #     ):
# #         if not self.redis_client:
# #             raise RuntimeError(
# #                 "Redis client is not initialized."
# #             )

# #         # --------------------------------------------------------
# #         # CAMERA
# #         # --------------------------------------------------------

# #         camera = behavior_event.get(
# #             "camera",
# #             {},
# #         )

# #         if not isinstance(camera, dict):
# #             camera = {}

# #         camera_id = camera.get(
# #             "camera_id",
# #             "unknown",
# #         )

# #         # --------------------------------------------------------
# #         # DATA
# #         # --------------------------------------------------------

# #         data = behavior_event.get(
# #             "data",
# #             {},
# #         )

# #         if not isinstance(data, dict):
# #             data = {}

# #         event_type = behavior_event.get(
# #             "event_type"
# #         )

# #         # ========================================================
# #         # COMMON VALUES
# #         # ========================================================

# #         person_count = data.get(
# #             "person_count",
# #             1,
# #         )

# #         severity = data.get(
# #             "severity",
# #             "low",
# #         )

# #         threshold = data.get(
# #             "threshold",
# #             0,
# #         )

# #         frame_id = data.get(
# #             "frame_id"
# #         )

# #         track_ids = data.get(
# #             "track_ids",
# #             [],
# #         )

# #         if not isinstance(track_ids, list):
# #             track_ids = []

# #         alert_type = event_type

# #         # ========================================================
# #         # CROWD
# #         # ========================================================

# #         if event_type == "crowd.detected":

# #             message = (
# #                 f"Crowd detected on "
# #                 f"{camera_id}: "
# #                 f"{person_count} person(s)"
# #             )

# #         # ========================================================
# #         # LOITERING
# #         # ========================================================

# #         elif event_type == "loitering.detected":

# #             track_id = data.get(
# #                 "track_id"
# #             )

# #             duration = data.get(
# #                 "duration_seconds",
# #                 0,
# #             )

# #             person_count = 1

# #             if track_id:
# #                 track_ids = [track_id]

# #             message = (
# #                 f"Possible loitering detected "
# #                 f"on {camera_id}: "
# #                 f"person remained for "
# #                 f"{float(duration):.1f} seconds"
# #             )

# #         # ========================================================
# #         # INTRUSION
# #         # ========================================================

# #         elif event_type == "intrusion.detected":

# #             track_id = data.get(
# #                 "track_id"
# #             )

# #             person_count = data.get(
# #                 "person_count",
# #                 1,
# #             )

# #             if track_id:
# #                 track_ids = [track_id]

# #             # Intrusion should normally be high/critical.
# #             # Preserve Security Agent severity when valid.
# #             if severity not in {
# #                 "low",
# #                 "medium",
# #                 "high",
# #                 "critical",
# #             }:
# #                 severity = "high"

# #             message = (
# #                 f"Security zone intrusion detected "
# #                 f"on {camera_id}"
# #             )

# #             if track_id:
# #                 message += (
# #                     f" | Track={track_id}"
# #                 )

# #         # ========================================================
# #         # UNKNOWN EVENT
# #         # ========================================================

# #         else:

# #             print(
# #                 f"[{self.agent_id}] "
# #                 f"Unsupported behavior event: "
# #                 f"{event_type}"
# #             )

# #             return

# #         # ========================================================
# #         # CREATE ALERT EVENT
# #         # ========================================================

# #         alert_event = {
# #             "event_id": str(
# #                 uuid.uuid4()
# #             ),

# #             "event_type": "alert.created",

# #             "version": "1.0",

# #             "timestamp": self.now(),

# #             "source": {
# #                 "agent_id": self.agent_id,
# #             },

# #             "camera": {
# #                 "camera_id": camera_id,
# #             },

# #             "data": {
# #                 "alert_type": alert_type,

# #                 "severity": severity,

# #                 "person_count": person_count,

# #                 "threshold": threshold,

# #                 "frame_id": frame_id,

# #                 "track_ids": track_ids,

# #                 "message": message,

# #                 "source_event_id":
# #                     behavior_event.get(
# #                         "event_id"
# #                     ),
# #             },
# #         }

# #         # ========================================================
# #         # PUBLISH
# #         # ========================================================

# #         output_id = await self.publish(
# #             OUTPUT_STREAM,
# #             alert_event,
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f" ALERT CREATED | "
# #             f"Camera={camera_id} | "
# #             f"Type={alert_type} | "
# #             f"Severity={severity} | "
# #             f"Count={person_count} | "
# #             f"Redis={output_id}"
# #         )

# #     # ============================================================
# #     # PROCESS BEHAVIOR EVENT
# #     # ============================================================

# #     async def process_behavior_event(
# #         self,
# #         event,
# #     ):
# #         if not isinstance(event, dict):
# #             raise ValueError(
# #                 "Behavior event must be an object."
# #             )

# #         event_type = event.get(
# #             "event_type"
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Received behavior event | "
# #             f"Type={event_type}"
# #         )

# #         # --------------------------------------------------------
# #         # SUPPORTED SECURITY EVENTS
# #         # --------------------------------------------------------

# #         if event_type not in self.supported_events:

# #             print(
# #                 f"[{self.agent_id}] "
# #                 f"Ignoring unsupported event type: "
# #                 f"{event_type}"
# #             )

# #             return

# #         await self.emit_alert_event(
# #             event
# #         )

# #     # ============================================================
# #     # PROCESS REDIS MESSAGE
# #     # ============================================================

# #     async def handle_redis_message(
# #         self,
# #         redis_id,
# #         fields,
# #     ):
# #         try:

# #             raw_event = fields.get(
# #                 "event"
# #             )

# #             # ----------------------------------------------------
# #             # MISSING PAYLOAD
# #             # ----------------------------------------------------

# #             if not raw_event:

# #                 print(
# #                     f"[{self.agent_id}] "
# #                     f"Missing event payload | "
# #                     f"Redis={redis_id}"
# #                 )

# #                 # Bad message is permanently discarded.
# #                 await self.redis_client.xack(
# #                     INPUT_STREAM,
# #                     GROUP_NAME,
# #                     redis_id,
# #                 )

# #                 return

# #             # ----------------------------------------------------
# #             # JSON PARSE
# #             # ----------------------------------------------------

# #             event = json.loads(
# #                 raw_event
# #             )

# #             # ----------------------------------------------------
# #             # VALIDATE OBJECT
# #             # ----------------------------------------------------

# #             if not isinstance(event, dict):

# #                 print(
# #                     f"[{self.agent_id}] "
# #                     f"Event payload is not an object | "
# #                     f"Redis={redis_id}"
# #                 )

# #                 await self.redis_client.xack(
# #                     INPUT_STREAM,
# #                     GROUP_NAME,
# #                     redis_id,
# #                 )

# #                 return

# #             # ----------------------------------------------------
# #             # PROCESS
# #             # ----------------------------------------------------

# #             await self.process_behavior_event(
# #                 event
# #             )

# #             # ----------------------------------------------------
# #             # ACK ONLY AFTER SUCCESS
# #             # ----------------------------------------------------

# #             await self.redis_client.xack(
# #                 INPUT_STREAM,
# #                 GROUP_NAME,
# #                 redis_id,
# #             )

# #             print(
# #                 f"[{self.agent_id}] "
# #                 f" ACK {redis_id}"
# #             )

# #         # ========================================================
# #         # INVALID JSON
# #         # ========================================================

# #         except json.JSONDecodeError as exc:

# #             print(
# #                 f"[{self.agent_id}] "
# #                 f"Invalid JSON | "
# #                 f"Redis={redis_id} | "
# #                 f"Error={exc}"
# #             )

# #             # Invalid JSON cannot succeed by retrying.
# #             await self.redis_client.xack(
# #                 INPUT_STREAM,
# #                 GROUP_NAME,
# #                 redis_id,
# #             )

# #         # ========================================================
# #         # PROCESSING ERROR
# #         # ========================================================

# #         except Exception as exc:

# #             print(
# #                 f"[{self.agent_id}] "
# #                 f"Error processing "
# #                 f"{redis_id} | "
# #                 f"{type(exc).__name__}: "
# #                 f"{exc}"
# #             )

# #             # IMPORTANT:
# #             # Do NOT ACK.
# #             #
# #             # Redis keeps this message pending.
# #             # It can later be recovered by a worker.
# #             raise

# #     # ============================================================
# #     # MAIN PROCESSING LOOP
# #     # ============================================================

# #     async def run(self):

# #         if not self.redis_client:
# #             raise RuntimeError(
# #                 "Redis client is not initialized."
# #             )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Alert processing loop started."
# #         )

# #         while self.running:

# #             try:

# #                 messages = (
# #                     await self.redis_client.xreadgroup(
# #                         groupname=GROUP_NAME,

# #                         consumername=self.consumer_name,

# #                         streams={
# #                             INPUT_STREAM: ">"
# #                         },

# #                         count=READ_COUNT,

# #                         block=READ_BLOCK_MS,
# #                     )
# #                 )

# #             except asyncio.CancelledError:
# #                 raise

# #             except Exception as exc:

# #                 # ------------------------------------------------
# #                 # Redis failure must NOT terminate the agent.
# #                 # ------------------------------------------------

# #                 print(
# #                     f"[{self.agent_id}] "
# #                     f"Redis read error | "
# #                     f"{type(exc).__name__}: "
# #                     f"{exc}"
# #                 )

# #                 await self.sleep(2)

# #                 continue

# #             # ----------------------------------------------------
# #             # NO MESSAGE
# #             # ----------------------------------------------------

# #             if not messages:
# #                 continue

# #             # ----------------------------------------------------
# #             # PROCESS EACH MESSAGE INDEPENDENTLY
# #             # ----------------------------------------------------

# #             for stream_name, stream_messages in messages:

# #                 for redis_id, fields in stream_messages:

# #                     try:

# #                         await self.handle_redis_message(
# #                             redis_id,
# #                             fields,
# #                         )

# #                     except asyncio.CancelledError:
# #                         raise

# #                     except Exception as exc:

# #                         # IMPORTANT:
# #                         # A single failed message must NOT
# #                         # terminate the Alert Agent.
# #                         #
# #                         # The message remains pending.
# #                         print(
# #                             f"[{self.agent_id}] "
# #                             f"Message {redis_id} "
# #                             f"left pending for recovery | "
# #                             f"{type(exc).__name__}: "
# #                             f"{exc}"
# #                         )

# #                         continue


# # # ================================================================
# # # ENTRY POINT
# # # ================================================================

# # async def main():

# #     agent = AlertAgent(
# #         agent_id=os.getenv(
# #             "AGENT_ID",
# #             DEFAULT_AGENT_ID,
# #         )
# #     )

# #     await agent.run_forever()


# # if __name__ == "__main__":

# #     asyncio.run(
# #         main()
# #     )




























# """
# Alert Agent
# ===========

# Consumes canonical behavior/security events and converts supported
# events into canonical `alert.created` events.

# Pipeline:

#     crowd.detected

#     loitering.detected ----> AlertAgent ----> alert.created

#     intrusion.detected

# Design principles:
# - Every normal event uses the canonical BaseEvent schema.
# - Input events are validated before processing.
# - Output events are created through create_event().
# - Historical timestamps are preserved.
# - Camera IDs are never silently replaced with a fake/default camera.
# - Trace/correlation/incident context is propagated downstream.
# - Source lineage is preserved.
# - A single malformed/failed message must not terminate the agent.
# - Messages are ACKed only after successful processing.
# - Unsupported event types are safely ACKed because they are not AlertAgent's job.
# - Consumer identity is unique so multiple workers can run safely.
# """

# import asyncio
# import json
# import math
# import os
# import uuid
# from datetime import datetime, timezone
# from typing import Any, Optional

# from shared.agent.base_agent import BaseAgent
# from shared.schemas.event_schema import create_event, validate_event


# # ============================================================================
# # CONFIGURATION
# # ============================================================================

# INPUT_STREAM = os.getenv(
#     "ALERT_INPUT_STREAM",
#     "events.behavior",
# )

# OUTPUT_STREAM = os.getenv(
#     "ALERT_OUTPUT_STREAM",
#     "events.alerts",
# )

# GROUP_NAME = os.getenv(
#     "ALERT_GROUP",
#     "alert-workers",
# )

# DEFAULT_AGENT_ID = os.getenv(
#     "ALERT_AGENT_ID",
#     "alert-01",
# )

# READ_COUNT = 10
# READ_BLOCK_MS = 5000

# VALID_SEVERITIES = {
#     "low",
#     "medium",
#     "high",
#     "critical",
# }


# # ============================================================================
# # HELPERS
# # ============================================================================


# def _safe_float(
#     value: Any,
#     default: float = 0.0,
# ) -> float:
#     """
#     Convert a value to a finite float.

#     Invalid, NaN, and infinite values return the supplied default.
#     """
#     try:
#         result = float(value)

#         if not math.isfinite(result):
#             return default

#         return result

#     except (TypeError, ValueError):
#         return default


# def _safe_int(
#     value: Any,
#     default: int = 0,
# ) -> int:
#     """
#     Convert a value to a safe integer.

#     Invalid values return the supplied default.
#     """
#     try:
#         result = int(value)

#         return result

#     except (TypeError, ValueError):
#         return default


# # ============================================================================
# # ALERT AGENT
# # ============================================================================


# class AlertAgent(BaseAgent):
#     """
#     Converts supported behavioral/security events into alerts.

#     Supported input events:

#         crowd.detected
#         loitering.detected
#         intrusion.detected

#     Output:

#         alert.created
#     """

#     def __init__(
#         self,
#         agent_id: Optional[str] = None,
#     ):
#         super().__init__(
#             agent_id=agent_id,
#         )

#         # ------------------------------------------------------------------
#         # Unique consumer identity.
#         #
#         # Multiple AlertAgent instances may therefore participate in the
#         # same Redis consumer group without sharing the same consumer name.
#         # ------------------------------------------------------------------
#         self.consumer_name = (
#             f"{self.agent_id}-"
#             f"{uuid.uuid4().hex[:8]}"
#         )

#         self.supported_events = {
#             "crowd.detected",
#             "loitering.detected",
#             "intrusion.detected",
#         }

#     # ======================================================================
#     # STARTUP
#     # ======================================================================

#     async def on_start(self):
#         await self.ensure_consumer_group()

#         print(
#             f"[{self.agent_id}] Alert agent ready."
#         )

#         print(
#             f"[{self.agent_id}] "
#             f"Instance={self.instance_id}"
#         )

#         print(
#             f"[{self.agent_id}] "
#             f"Hostname={self.hostname}"
#         )

#         print(
#             f"[{self.agent_id}] "
#             f"Input={INPUT_STREAM}"
#         )

#         print(
#             f"[{self.agent_id}] "
#             f"Output={OUTPUT_STREAM}"
#         )

#         print(
#             f"[{self.agent_id}] "
#             f"ConsumerGroup={GROUP_NAME}"
#         )

#         print(
#             f"[{self.agent_id}] "
#             f"Consumer={self.consumer_name}"
#         )

#         print(
#             f"[{self.agent_id}] "
#             f"Supported events="
#             f"{', '.join(sorted(self.supported_events))}"
#         )

#     # ======================================================================
#     # SHUTDOWN
#     # ======================================================================

#     async def on_stop(self):
#         print(
#             f"[{self.agent_id}] "
#             f"Alert agent cleanup complete."
#         )

#     # ======================================================================
#     # REDIS CONSUMER GROUP
#     # ======================================================================

#     async def ensure_consumer_group(self):
#         if not self.redis_client:
#             raise RuntimeError(
#                 "Redis client is not initialized."
#             )

#         try:
#             await self.redis_client.xgroup_create(
#                 name=INPUT_STREAM,
#                 groupname=GROUP_NAME,
#                 id="0",
#                 mkstream=True,
#             )

#             print(
#                 f"[{self.agent_id}] "
#                 f"Created consumer group: "
#                 f"{GROUP_NAME}"
#             )

#         except Exception as exc:
#             if "BUSYGROUP" in str(exc):
#                 print(
#                     f"[{self.agent_id}] "
#                     f"Consumer group already exists: "
#                     f"{GROUP_NAME}"
#                 )
#             else:
#                 raise

#     # ======================================================================
#     # TIMESTAMP HELPERS
#     # ======================================================================

#     @staticmethod
#     def _parse_timestamp(
#         value: Any,
#     ) -> Optional[datetime]:
#         """
#         Parse an ISO timestamp and normalize it to UTC.

#         Returns None when the value is invalid.
#         """
#         if not isinstance(value, str):
#             return None

#         try:
#             parsed = datetime.fromisoformat(
#                 value.replace(
#                     "Z",
#                     "+00:00",
#                 )
#             )

#         except (TypeError, ValueError):
#             return None

#         if parsed.tzinfo is None:
#             parsed = parsed.replace(
#                 tzinfo=timezone.utc,
#             )

#         return parsed.astimezone(
#             timezone.utc,
#         )

#     def _get_event_time(
#         self,
#         event: dict,
#     ) -> datetime:
#         """
#         Determine the timestamp that should be used for the alert.

#         Priority:

#         1. data.frame_timestamp
#         2. event.timestamp
#         3. current UTC time as defensive fallback

#         Historical analysis depends on preserving the original footage
#         timestamp rather than replacing it with processing time.
#         """
#         data = event.get(
#             "data",
#             {},
#         )

#         if isinstance(data, dict):
#             frame_timestamp = self._parse_timestamp(
#                 data.get("frame_timestamp")
#             )

#             if frame_timestamp is not None:
#                 return frame_timestamp

#         event_timestamp = self._parse_timestamp(
#             event.get("timestamp")
#         )

#         if event_timestamp is not None:
#             return event_timestamp

#         return datetime.now(
#             timezone.utc,
#         )

#     # ======================================================================
#     # EVENT FIELD HELPERS
#     # ======================================================================

#     @staticmethod
#     def _extract_camera_id(
#         event: dict,
#     ) -> Optional[str]:
#         """
#         Extract a valid camera ID.

#         Never silently falls back to CAM01/unknown.
#         """
#         camera = event.get(
#             "camera",
#             {},
#         )

#         if not isinstance(camera, dict):
#             return None

#         camera_id = camera.get(
#             "camera_id"
#         )

#         if not isinstance(camera_id, str):
#             return None

#         camera_id = camera_id.strip()

#         if not camera_id:
#             return None

#         return camera_id

#     @staticmethod
#     def _extract_context(
#         event: dict,
#     ) -> dict:
#         context = event.get(
#             "context",
#             {},
#         )

#         if not isinstance(context, dict):
#             return {}

#         return context

#     @staticmethod
#     def _extract_source(
#         event: dict,
#     ) -> dict:
#         source = event.get(
#             "source",
#             {},
#         )

#         if not isinstance(source, dict):
#             return {}

#         return source

#     # ======================================================================
#     # SEVERITY
#     # ======================================================================

#     @staticmethod
#     def _normalize_severity(
#         value: Any,
#         default: str = "medium",
#     ) -> str:
#         if isinstance(value, str):
#             severity = value.strip().lower()

#             if severity in VALID_SEVERITIES:
#                 return severity

#         return default

#     # ======================================================================
#     # ALERT EVENT CREATION
#     # ======================================================================

#     async def emit_alert_event(
#         self,
#         behavior_event: dict,
#         source_redis_id: str,
#     ):
#         """
#         Convert a supported source event into alert.created.

#         The output event is canonical and retains lineage/context from
#         the original event.
#         """
#         if not self.redis_client:
#             raise RuntimeError(
#                 "Redis client is not initialized."
#             )

#         # ------------------------------------------------------------------
#         # Validate source event first.
#         # ------------------------------------------------------------------
#         validate_event(
#             behavior_event,
#         )

#         event_type = behavior_event.get(
#             "event_type"
#         )

#         if event_type not in self.supported_events:
#             return None

#         # ------------------------------------------------------------------
#         # Camera
#         # ------------------------------------------------------------------
#         camera_id = self._extract_camera_id(
#             behavior_event
#         )

#         if camera_id is None:
#             raise ValueError(
#                 "Alert source event has no valid camera_id."
#             )

#         # ------------------------------------------------------------------
#         # Source data
#         # ------------------------------------------------------------------
#         data = behavior_event.get(
#             "data",
#             {},
#         )

#         if not isinstance(data, dict):
#             raise ValueError(
#                 "Alert source event data must be an object."
#             )

#         # ------------------------------------------------------------------
#         # Source context
#         # ------------------------------------------------------------------
#         context = self._extract_context(
#             behavior_event
#         )

#         mode = context.get(
#             "mode",
#             "live",
#         )

#         trace_id = context.get(
#             "trace_id"
#         )

#         correlation_id = context.get(
#             "correlation_id"
#         )

#         incident_id = context.get(
#             "incident_id"
#         )

#         # ------------------------------------------------------------------
#         # Source lineage
#         # ------------------------------------------------------------------
#         source = self._extract_source(
#             behavior_event
#         )

#         source_agent_id = source.get(
#             "agent_id"
#         )

#         source_instance_id = source.get(
#             "instance_id"
#         )

#         # ------------------------------------------------------------------
#         # Common values
#         # ------------------------------------------------------------------
#         severity = self._normalize_severity(
#             data.get("severity"),
#             default="medium",
#         )

#         person_count = _safe_int(
#             data.get("person_count"),
#             default=0,
#         )

#         threshold = _safe_float(
#             data.get("threshold"),
#             default=0.0,
#         )

#         frame_id = data.get(
#             "frame_id"
#         )

#         track_ids = data.get(
#             "track_ids",
#             [],
#         )

#         if not isinstance(track_ids, list):
#             track_ids = []

#         # Normalize track IDs to strings while dropping empty values.
#         normalized_track_ids = []

#         for track_id in track_ids:
#             if track_id is None:
#                 continue

#             track_id_string = str(
#                 track_id
#             ).strip()

#             if track_id_string:
#                 normalized_track_ids.append(
#                     track_id_string
#                 )

#         track_ids = normalized_track_ids

#         alert_type = event_type

#         # ==================================================================
#         # CROWD
#         # ==================================================================

#         if event_type == "crowd.detected":
#             person_count = max(
#                 0,
#                 person_count,
#             )

#             message = (
#                 f"Crowd detected on "
#                 f"{camera_id}: "
#                 f"{person_count} person(s)"
#             )

#         # ==================================================================
#         # LOITERING
#         # ==================================================================

#         elif event_type == "loitering.detected":
#             track_id = data.get(
#                 "track_id"
#             )

#             duration = _safe_float(
#                 data.get("duration_seconds"),
#                 default=0.0,
#             )

#             duration = max(
#                 0.0,
#                 duration,
#             )

#             person_count = 1

#             if track_id is not None:
#                 track_id_string = str(
#                     track_id
#                 ).strip()

#                 if track_id_string:
#                     track_ids = [
#                         track_id_string
#                     ]

#             message = (
#                 f"Possible loitering detected "
#                 f"on {camera_id}: "
#                 f"person remained for "
#                 f"{duration:.1f} seconds"
#             )

#         # ==================================================================
#         # INTRUSION
#         # ==================================================================

#         elif event_type == "intrusion.detected":
#             track_id = data.get(
#                 "track_id"
#             )

#             person_count = _safe_int(
#                 data.get("person_count"),
#                 default=1,
#             )

#             person_count = max(
#                 1,
#                 person_count,
#             )

#             if track_id is not None:
#                 track_id_string = str(
#                     track_id
#                 ).strip()

#                 if track_id_string:
#                     track_ids = [
#                         track_id_string
#                     ]

#             # Security Agent normally supplies high/critical severity.
#             # Preserve valid values, otherwise use high.
#             severity = self._normalize_severity(
#                 data.get("severity"),
#                 default="high",
#             )

#             message = (
#                 f"Security zone intrusion detected "
#                 f"on {camera_id}"
#             )

#             if track_id is not None:
#                 track_id_string = str(
#                     track_id
#                 ).strip()

#                 if track_id_string:
#                     message += (
#                         f" | Track={track_id_string}"
#                     )

#         else:
#             return None

#         # ==================================================================
#         # CREATE CANONICAL ALERT EVENT
#         # ==================================================================

#         alert_data = {
#             "alert_type": alert_type,
#             "severity": severity,
#             "person_count": person_count,
#             "threshold": threshold,
#             "frame_id": frame_id,
#             "track_ids": track_ids,
#             "message": message,

#             # Source lineage.
#             "source_event_id": behavior_event.get(
#                 "event_id"
#             ),
#             "source_redis_id": source_redis_id,
#             "source_event_type": event_type,

#             # Source execution identity.
#             "source_agent_id": source_agent_id,
#             "source_instance_id": source_instance_id,
#         }

#         # Preserve useful source-specific fields without blindly copying
#         # the entire upstream payload.
#         if event_type == "loitering.detected":
#             alert_data["duration_seconds"] = _safe_float(
#                 data.get("duration_seconds"),
#                 default=0.0,
#             )

#             alert_data["behavior"] = data.get(
#                 "behavior",
#                 "loitering",
#             )

#         elif event_type == "crowd.detected":
#             alert_data["behavior"] = data.get(
#                 "behavior",
#                 "crowd_detection",
#             )

#         elif event_type == "intrusion.detected":
#             alert_data["behavior"] = data.get(
#                 "behavior",
#                 "restricted_zone_intrusion",
#             )

#             if "zone" in data:
#                 alert_data["zone"] = data.get(
#                     "zone"
#                 )

#             if "position" in data:
#                 alert_data["position"] = data.get(
#                     "position"
#                 )

#         alert_event = create_event(
#             event_type="alert.created",
#             agent_id=self.agent_id,
#             instance_id=self.instance_id,
#             hostname=self.hostname,
#             camera_id=camera_id,
#             data=alert_data,
#             mode=mode,
#             trace_id=trace_id,
#             correlation_id=correlation_id,
#             incident_id=incident_id,
#             timestamp=self._get_event_time(
#                 behavior_event
#             ),
#         )

#         # Explicit final validation before publishing.
#         validate_event(
#             alert_event
#         )

#         # ------------------------------------------------------------------
#         # Publish.
#         # ------------------------------------------------------------------
#         output_id = await self.publish(
#             OUTPUT_STREAM,
#             alert_event.to_dict(),
#         )

#         print(
#             f"[{self.agent_id}] "
#             f"ALERT CREATED | "
#             f"Camera={camera_id} | "
#             f"Type={alert_type} | "
#             f"Severity={severity} | "
#             f"Count={person_count} | "
#             f"Source={behavior_event.get('event_id')} | "
#             f"Redis={output_id}"
#         )

#         return output_id

#     # ======================================================================
#     # PROCESS SOURCE EVENT
#     # ======================================================================

#     async def process_behavior_event(
#         self,
#         event: dict,
#         source_redis_id: str,
#     ):
#         """
#         Validate and process one source event.

#         Returns:
#             True  -> successfully handled
#             False -> unsupported event safely ignored
#         """
#         if not isinstance(event, dict):
#             raise ValueError(
#                 "Behavior event must be an object."
#             )

#         # ------------------------------------------------------------------
#         # Canonical validation.
#         # ------------------------------------------------------------------
#         validate_event(
#             event
#         )

#         event_type = event.get(
#             "event_type"
#         )

#         camera_id = self._extract_camera_id(
#             event
#         )

#         print(
#             f"[{self.agent_id}] "
#             f"Received behavior event | "
#             f"Type={event_type} | "
#             f"Camera={camera_id} | "
#             f"Redis={source_redis_id}"
#         )

#         # ------------------------------------------------------------------
#         # Unsupported events are not failures.
#         #
#         # This allows the same stream to eventually contain additional
#         # event types without forcing every Alert worker to understand them.
#         # ------------------------------------------------------------------
#         if event_type not in self.supported_events:
#             print(
#                 f"[{self.agent_id}] "
#                 f"Ignoring unsupported event type: "
#                 f"{event_type}"
#             )

#             return False

#         # ------------------------------------------------------------------
#         # Valid camera required for alerts.
#         # ------------------------------------------------------------------
#         if camera_id is None:
#             raise ValueError(
#                 "Supported alert event has no valid camera_id."
#             )

#         await self.emit_alert_event(
#             behavior_event=event,
#             source_redis_id=source_redis_id,
#         )

#         return True

#     # ======================================================================
#     # PROCESS REDIS MESSAGE
#     # ======================================================================

#     async def handle_redis_message(
#         self,
#         redis_id,
#         fields,
#     ):
#         """
#         Process one Redis Stream message.

#         Poison messages are ACKed because retrying them cannot fix malformed
#         JSON or missing payloads.

#         Processing failures are intentionally NOT ACKed. They remain pending
#         so a later recovery mechanism can reclaim them.
#         """
#         if not self.redis_client:
#             raise RuntimeError(
#                 "Redis client is not initialized."
#             )

#         try:
#             # --------------------------------------------------------------
#             # Validate Redis fields.
#             # --------------------------------------------------------------
#             if not isinstance(fields, dict):
#                 print(
#                     f"[{self.agent_id}] "
#                     f"Invalid Redis fields | "
#                     f"Redis={redis_id}"
#                 )

#                 await self.redis_client.xack(
#                     INPUT_STREAM,
#                     GROUP_NAME,
#                     redis_id,
#                 )

#                 return

#             raw_event = fields.get(
#                 "event"
#             )

#             # --------------------------------------------------------------
#             # Missing payload.
#             # --------------------------------------------------------------
#             if not raw_event:
#                 print(
#                     f"[{self.agent_id}] "
#                     f"Missing event payload | "
#                     f"Redis={redis_id}"
#                 )

#                 # Poison message: cannot be repaired by retrying.
#                 await self.redis_client.xack(
#                     INPUT_STREAM,
#                     GROUP_NAME,
#                     redis_id,
#                 )

#                 return

#             # --------------------------------------------------------------
#             # JSON parse.
#             # --------------------------------------------------------------
#             try:
#                 event = json.loads(
#                     raw_event
#                 )

#             except json.JSONDecodeError as exc:
#                 print(
#                     f"[{self.agent_id}] "
#                     f"Invalid JSON | "
#                     f"Redis={redis_id} | "
#                     f"Error={exc}"
#                 )

#                 # Poison message.
#                 await self.redis_client.xack(
#                     INPUT_STREAM,
#                     GROUP_NAME,
#                     redis_id,
#                 )

#                 return

#             # --------------------------------------------------------------
#             # Object validation.
#             # --------------------------------------------------------------
#             if not isinstance(event, dict):
#                 print(
#                     f"[{self.agent_id}] "
#                     f"Event payload is not an object | "
#                     f"Redis={redis_id}"
#                 )

#                 # Poison message.
#                 await self.redis_client.xack(
#                     INPUT_STREAM,
#                     GROUP_NAME,
#                     redis_id,
#                 )

#                 return

#             # --------------------------------------------------------------
#             # Process event.
#             # --------------------------------------------------------------
#             await self.process_behavior_event(
#                 event=event,
#                 source_redis_id=redis_id,
#             )

#             # --------------------------------------------------------------
#             # ACK ONLY AFTER SUCCESS.
#             #
#             # Unsupported valid events also count as successfully handled.
#             # --------------------------------------------------------------
#             await self.redis_client.xack(
#                 INPUT_STREAM,
#                 GROUP_NAME,
#                 redis_id,
#             )

#             print(
#                 f"[{self.agent_id}] "
#                 f"ACK {redis_id}"
#             )

#         except asyncio.CancelledError:
#             raise

#         except Exception as exc:
#             print(
#                 f"[{self.agent_id}] "
#                 f"Error processing {redis_id} | "
#                 f"{type(exc).__name__}: "
#                 f"{exc}"
#             )

#             # --------------------------------------------------------------
#             # IMPORTANT:
#             #
#             # Do NOT ACK processing failures.
#             #
#             # Redis will keep the message pending. A future reliability
#             # layer can reclaim it using XAUTOCLAIM/XCLAIM and retry it.
#             # --------------------------------------------------------------
#             raise

#     # ======================================================================
#     # MAIN PROCESSING LOOP
#     # ======================================================================

#     async def run(self):
#         """
#         Main Redis consumer loop.

#         Redis connection/read failures do not terminate the Alert Agent.
#         Individual message failures do not terminate the Alert Agent.
#         """
#         if not self.redis_client:
#             raise RuntimeError(
#                 "Redis client is not initialized."
#             )

#         print(
#             f"[{self.agent_id}] "
#             f"Alert processing loop started."
#         )

#         while self.running:
#             # --------------------------------------------------------------
#             # Read from Redis.
#             # --------------------------------------------------------------
#             try:
#                 messages = (
#                     await self.redis_client.xreadgroup(
#                         groupname=GROUP_NAME,
#                         consumername=self.consumer_name,
#                         streams={
#                             INPUT_STREAM: ">"
#                         },
#                         count=READ_COUNT,
#                         block=READ_BLOCK_MS,
#                     )
#                 )

#             except asyncio.CancelledError:
#                 raise

#             except Exception as exc:
#                 # Redis failure must not terminate the agent.
#                 print(
#                     f"[{self.agent_id}] "
#                     f"Redis read error | "
#                     f"{type(exc).__name__}: "
#                     f"{exc}"
#                 )

#                 await self.sleep(
#                     2
#                 )

#                 continue

#             # --------------------------------------------------------------
#             # No messages.
#             # --------------------------------------------------------------
#             if not messages:
#                 continue

#             # --------------------------------------------------------------
#             # Process every message independently.
#             # --------------------------------------------------------------
#             for stream_name, stream_messages in messages:
#                 # Defensive stream check.
#                 if stream_name != INPUT_STREAM:
#                     print(
#                         f"[{self.agent_id}] "
#                         f"Unexpected stream received: "
#                         f"{stream_name}"
#                     )

#                 for redis_id, fields in stream_messages:
#                     try:
#                         await self.handle_redis_message(
#                             redis_id=redis_id,
#                             fields=fields,
#                         )

#                     except asyncio.CancelledError:
#                         raise

#                     except Exception as exc:
#                         # --------------------------------------------------
#                         # A single failed message must NOT terminate the
#                         # entire Alert Agent.
#                         #
#                         # The failed Redis message remains pending.
#                         # --------------------------------------------------
#                         print(
#                             f"[{self.agent_id}] "
#                             f"Message {redis_id} "
#                             f"left pending for recovery | "
#                             f"{type(exc).__name__}: "
#                             f"{exc}"
#                         )

#                         continue


# # ============================================================================
# # ENTRY POINT
# # ============================================================================


# async def main():
#     agent = AlertAgent(
#         agent_id=os.getenv(
#             "AGENT_ID",
#             DEFAULT_AGENT_ID,
#         )
#     )

#     await agent.run_forever()


# if __name__ == "__main__":
#     asyncio.run(
#         main()
#     )





























"""
Alert Agent
===========

Consumes canonical behavior/security events and converts supported
events into canonical ``alert.created`` events.

Pipeline:

    crowd.detected
    loitering.detected ----> AlertAgent ----> alert.created
    intrusion.detected

Design principles:

- Every normal event uses the canonical BaseEvent schema.
- Input events are validated before processing.
- Output events are created through create_event().
- Historical timestamps are preserved.
- Naive timestamps are rejected.
- Camera IDs are never silently replaced with a fake/default camera.
- Trace/correlation/incident context is propagated downstream.
- Source lineage is preserved.
- A single malformed/failed message must not terminate the agent.
- Messages are ACKed only after successful processing.
- Unsupported event types are safely ACKed because they are not
  AlertAgent's job.
- Consumer identity is unique so multiple workers can run safely.
- Processing failures are NOT ACKed and remain pending for the
  future shared recovery/DLQ layer.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from shared.agent.base_agent import BaseAgent
from shared.schemas.event_schema import create_event, validate_event


# ============================================================================
# CONFIGURATION
# ============================================================================

INPUT_STREAM = os.getenv(
    "ALERT_INPUT_STREAM",
    "events.behavior",
)

OUTPUT_STREAM = os.getenv(
    "ALERT_OUTPUT_STREAM",
    "events.alerts",
)

GROUP_NAME = os.getenv(
    "ALERT_GROUP",
    "alert-workers",
)

DEFAULT_AGENT_ID = os.getenv(
    "ALERT_AGENT_ID",
    "alert-01",
)

READ_COUNT = 10
READ_BLOCK_MS = 5000

VALID_SEVERITIES = {
    "low",
    "medium",
    "high",
    "critical",
}

SUPPORTED_EVENTS = {
    "crowd.detected",
    "loitering.detected",
    "intrusion.detected",
}


# ============================================================================
# HELPERS
# ============================================================================


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Convert a value to a finite float.

    Invalid, NaN, and infinite values return the supplied default.
    """
    try:
        result = float(value)

        if not math.isfinite(result):
            return default

        return result

    except (TypeError, ValueError):
        return default


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
    """
    Convert a value to an integer.

    Invalid values return the supplied default.
    """
    try:
        return int(value)

    except (TypeError, ValueError):
        return default


# ============================================================================
# ALERT AGENT
# ============================================================================


class AlertAgent(BaseAgent):
    """
    Converts supported behavioral/security events into alert events.

    Supported input events:

        crowd.detected
        loitering.detected
        intrusion.detected

    Output:

        alert.created
    """

    def __init__(
        self,
        agent_id: Optional[str] = None,
    ):
        super().__init__(
            agent_id=agent_id,
        )

        # Unique consumer identity.
        #
        # Multiple AlertAgent instances may participate in the same
        # Redis consumer group without sharing a consumer name.
        self.consumer_name = (
            f"{self.agent_id}-"
            f"{uuid.uuid4().hex[:8]}"
        )

        self.supported_events = set(SUPPORTED_EVENTS)

    # ========================================================================
    # STARTUP
    # ========================================================================

    async def on_start(self):
        await self.ensure_consumer_group()

        print(
            f"[{self.agent_id}] Alert agent ready."
        )

        print(
            f"[{self.agent_id}] "
            f"Instance={self.instance_id}"
        )

        print(
            f"[{self.agent_id}] "
            f"Hostname={self.hostname}"
        )

        print(
            f"[{self.agent_id}] "
            f"Input={INPUT_STREAM}"
        )

        print(
            f"[{self.agent_id}] "
            f"Output={OUTPUT_STREAM}"
        )

        print(
            f"[{self.agent_id}] "
            f"ConsumerGroup={GROUP_NAME}"
        )

        print(
            f"[{self.agent_id}] "
            f"Consumer={self.consumer_name}"
        )

        print(
            f"[{self.agent_id}] "
            f"Supported events="
            f"{', '.join(sorted(self.supported_events))}"
        )

    # ========================================================================
    # SHUTDOWN
    # ========================================================================

    async def on_stop(self):
        print(
            f"[{self.agent_id}] "
            f"Alert agent cleanup complete."
        )

    # ========================================================================
    # REDIS CONSUMER GROUP
    # ========================================================================

    async def ensure_consumer_group(self):
        if not self.redis_client:
            raise RuntimeError(
                "Redis client is not initialized."
            )

        try:
            await self.redis_client.xgroup_create(
                name=INPUT_STREAM,
                groupname=GROUP_NAME,
                id="0",
                mkstream=True,
            )

            print(
                f"[{self.agent_id}] "
                f"Created consumer group: "
                f"{GROUP_NAME}"
            )

        except Exception as exc:
            if "BUSYGROUP" in str(exc):
                print(
                    f"[{self.agent_id}] "
                    f"Consumer group already exists: "
                    f"{GROUP_NAME}"
                )
            else:
                raise

    # ========================================================================
    # TIMESTAMP HELPERS
    # ========================================================================

    @staticmethod
    def _parse_timestamp(
        value: Any,
    ) -> Optional[datetime]:
        """
        Parse an ISO-8601 timestamp.

        Naive timestamps are rejected.

        Returns:
            UTC-aware datetime or None.
        """

        if not isinstance(value, str):
            return None

        try:
            parsed = datetime.fromisoformat(
                value.replace(
                    "Z",
                    "+00:00",
                )
            )

        except (TypeError, ValueError):
            return None

        # Canonical event timestamps must be timezone-aware.
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None

        return parsed.astimezone(
            timezone.utc,
        )

    def _get_event_time(
        self,
        event: dict[str, Any],
    ) -> datetime:
        """
        Determine the timestamp used for alert.created.

        Priority:

        1. data.frame_timestamp
        2. canonical event.timestamp

        There is deliberately NO current-time fallback.

        Historical events must never receive a fabricated processing-time
        timestamp.
        """

        data = event.get(
            "data",
            {},
        )

        if isinstance(data, dict):
            frame_timestamp = self._parse_timestamp(
                data.get("frame_timestamp")
            )

            if frame_timestamp is not None:
                return frame_timestamp

        event_timestamp = self._parse_timestamp(
            event.get("timestamp")
        )

        if event_timestamp is not None:
            return event_timestamp

        raise ValueError(
            "Alert source event has no valid timezone-aware timestamp."
        )

    # ========================================================================
    # EVENT FIELD HELPERS
    # ========================================================================

    @staticmethod
    def _extract_camera_id(
        event: dict[str, Any],
    ) -> Optional[str]:
        """
        Extract a valid camera ID.

        Never silently falls back to CAM01/unknown.
        """

        camera = event.get(
            "camera",
            {},
        )

        if not isinstance(camera, dict):
            return None

        camera_id = camera.get(
            "camera_id"
        )

        if not isinstance(camera_id, str):
            return None

        camera_id = camera_id.strip()

        if not camera_id:
            return None

        return camera_id

    @staticmethod
    def _extract_context(
        event: dict[str, Any],
    ) -> dict[str, Any]:
        context = event.get(
            "context",
            {},
        )

        if not isinstance(context, dict):
            return {}

        return context

    @staticmethod
    def _extract_source(
        event: dict[str, Any],
    ) -> dict[str, Any]:
        source = event.get(
            "source",
            {},
        )

        if not isinstance(source, dict):
            return {}

        return source

    # ========================================================================
    # SEVERITY
    # ========================================================================

    @staticmethod
    def _normalize_severity(
        value: Any,
        default: str,
    ) -> str:
        """
        Normalize severity.

        If no severity is supplied, the caller's explicit default is used.

        If a severity is supplied but invalid, raise ValueError rather than
        silently hiding a malformed upstream event.
        """

        if value is None:
            return default

        if not isinstance(value, str):
            raise ValueError(
                "severity must be a string."
            )

        severity = value.strip().lower()

        if severity not in VALID_SEVERITIES:
            raise ValueError(
                f"Invalid severity: {value!r}"
            )

        return severity

    # ========================================================================
    # TRACK ID NORMALIZATION
    # ========================================================================

    @staticmethod
    def _normalize_track_ids(
        value: Any,
    ) -> list[str]:
        """
        Normalize a list of track IDs.

        None is treated as no track IDs.

        If a non-list value is supplied, reject it instead of silently
        converting malformed structured data.
        """

        if value is None:
            return []

        if not isinstance(value, list):
            raise ValueError(
                "track_ids must be a list."
            )

        normalized: list[str] = []

        for track_id in value:
            if not isinstance(track_id, str):
                raise ValueError(
                    "track_ids must contain strings."
                )

            track_id = track_id.strip()

            if not track_id:
                raise ValueError(
                    "track_ids cannot contain empty values."
                )

            normalized.append(track_id)

        return normalized

    # ========================================================================
    # ALERT EVENT CREATION
    # ========================================================================

    async def emit_alert_event(
        self,
        behavior_event: dict[str, Any],
        source_redis_id: str,
    ):
        """
        Convert a supported source event into alert.created.

        The output event:

        - uses the canonical event envelope
        - preserves event time
        - preserves camera identity
        - preserves trace/correlation/incident context
        - preserves source lineage
        """

        if not self.redis_client:
            raise RuntimeError(
                "Redis client is not initialized."
            )

        # --------------------------------------------------------------------
        # Validate source event envelope.
        # --------------------------------------------------------------------

        validate_event(
            behavior_event
        )

        event_type = behavior_event.get(
            "event_type"
        )

        if event_type not in self.supported_events:
            return None

        # --------------------------------------------------------------------
        # Camera
        # --------------------------------------------------------------------

        camera_id = self._extract_camera_id(
            behavior_event
        )

        if camera_id is None:
            raise ValueError(
                "Alert source event has no valid camera_id."
            )

        # --------------------------------------------------------------------
        # Source data
        # --------------------------------------------------------------------

        data = behavior_event.get(
            "data",
            {},
        )

        if not isinstance(data, dict):
            raise ValueError(
                "Alert source event data must be an object."
            )

        # --------------------------------------------------------------------
        # Source context
        # --------------------------------------------------------------------

        context = self._extract_context(
            behavior_event
        )

        mode = context.get(
            "mode",
            "live",
        )

        if mode not in {"live", "historical"}:
            raise ValueError(
                f"Invalid event mode: {mode!r}"
            )

        trace_id = context.get(
            "trace_id"
        )

        correlation_id = context.get(
            "correlation_id"
        )

        incident_id = context.get(
            "incident_id"
        )

        # --------------------------------------------------------------------
        # Source lineage
        # --------------------------------------------------------------------

        source = self._extract_source(
            behavior_event
        )

        source_agent_id = source.get(
            "agent_id"
        )

        source_instance_id = source.get(
            "instance_id"
        )

        if not isinstance(source_agent_id, str) or not source_agent_id.strip():
            raise ValueError(
                "Alert source event has no valid source.agent_id."
            )

        if (
            not isinstance(source_instance_id, str)
            or not source_instance_id.strip()
        ):
            raise ValueError(
                "Alert source event has no valid source.instance_id."
            )

        # --------------------------------------------------------------------
        # Event time
        # --------------------------------------------------------------------

        event_time = self._get_event_time(
            behavior_event
        )

        # --------------------------------------------------------------------
        # Common fields
        # --------------------------------------------------------------------

        person_count = _safe_int(
            data.get("person_count"),
            default=0,
        )

        person_count = max(
            0,
            person_count,
        )

        threshold = _safe_float(
            data.get("threshold"),
            default=0.0,
        )

        threshold = max(
            0.0,
            threshold,
        )

        frame_id = data.get(
            "frame_id"
        )

        if frame_id is not None:
            if not isinstance(frame_id, str) or not frame_id.strip():
                raise ValueError(
                    "frame_id must be a non-empty string when supplied."
                )

            frame_id = frame_id.strip()

        track_ids = self._normalize_track_ids(
            data.get("track_ids")
        )

        # --------------------------------------------------------------------
        # Event-specific handling
        # --------------------------------------------------------------------

        alert_type = event_type

        # ====================================================================
        # CROWD
        # ====================================================================

        if event_type == "crowd.detected":
            severity = self._normalize_severity(
                data.get("severity"),
                default="medium",
            )

            message = (
                f"Crowd detected on "
                f"{camera_id}: "
                f"{person_count} person(s)"
            )

        # ====================================================================
        # LOITERING
        # ====================================================================

        elif event_type == "loitering.detected":
            severity = self._normalize_severity(
                data.get("severity"),
                default="medium",
            )

            track_id = data.get(
                "track_id"
            )

            if track_id is not None:
                if not isinstance(track_id, str):
                    raise ValueError(
                        "loitering track_id must be a string."
                    )

                track_id = track_id.strip()

                if not track_id:
                    raise ValueError(
                        "loitering track_id cannot be empty."
                    )

                track_ids = [track_id]

            duration = _safe_float(
                data.get("duration_seconds"),
                default=0.0,
            )

            if duration < 0:
                raise ValueError(
                    "duration_seconds cannot be negative."
                )

            person_count = 1

            message = (
                f"Possible loitering detected "
                f"on {camera_id}: "
                f"person remained for "
                f"{duration:.1f} seconds"
            )

        # ====================================================================
        # INTRUSION
        # ====================================================================

        elif event_type == "intrusion.detected":
            severity = self._normalize_severity(
                data.get("severity"),
                default="high",
            )

            track_id = data.get(
                "track_id"
            )

            if track_id is not None:
                if not isinstance(track_id, str):
                    raise ValueError(
                        "intrusion track_id must be a string."
                    )

                track_id = track_id.strip()

                if not track_id:
                    raise ValueError(
                        "intrusion track_id cannot be empty."
                    )

                track_ids = [track_id]

            person_count = _safe_int(
                data.get("person_count"),
                default=1,
            )

            person_count = max(
                1,
                person_count,
            )

            message = (
                f"Security zone intrusion detected "
                f"on {camera_id}"
            )

            if track_id is not None:
                message += (
                    f" | Track={track_id}"
                )

        else:
            return None

        # ====================================================================
        # BUILD ALERT PAYLOAD
        # ====================================================================

        alert_data: dict[str, Any] = {
            "alert_type": alert_type,
            "severity": severity,
            "person_count": person_count,
            "threshold": threshold,
            "frame_id": frame_id,
            "track_ids": track_ids,
            "message": message,

            # Source lineage.
            "source_event_id": behavior_event.get(
                "event_id"
            ),
            "source_redis_id": source_redis_id,
            "source_event_type": event_type,

            # Source execution identity.
            "source_agent_id": source_agent_id,
            "source_instance_id": source_instance_id,
        }

        # --------------------------------------------------------------------
        # Preserve useful source-specific fields.
        #
        # Do NOT blindly copy the upstream payload.
        # --------------------------------------------------------------------

        if event_type == "loitering.detected":
            duration = _safe_float(
                data.get("duration_seconds"),
                default=0.0,
            )

            alert_data["duration_seconds"] = max(
                0.0,
                duration,
            )

            behavior = data.get(
                "behavior",
                "loitering",
            )

            if not isinstance(behavior, str) or not behavior.strip():
                raise ValueError(
                    "loitering behavior must be a non-empty string."
                )

            alert_data["behavior"] = behavior.strip()

        elif event_type == "crowd.detected":
            behavior = data.get(
                "behavior",
                "crowd_detection",
            )

            if not isinstance(behavior, str) or not behavior.strip():
                raise ValueError(
                    "crowd behavior must be a non-empty string."
                )

            alert_data["behavior"] = behavior.strip()

        elif event_type == "intrusion.detected":
            behavior = data.get(
                "behavior",
                "restricted_zone_intrusion",
            )

            if not isinstance(behavior, str) or not behavior.strip():
                raise ValueError(
                    "intrusion behavior must be a non-empty string."
                )

            alert_data["behavior"] = behavior.strip()

            if "zone" in data:
                alert_data["zone"] = data["zone"]

            if "position" in data:
                alert_data["position"] = data["position"]

        # ====================================================================
        # CREATE CANONICAL ALERT EVENT
        # ====================================================================

        alert_event = create_event(
            event_type="alert.created",
            agent_id=self.agent_id,
            instance_id=self.instance_id,
            hostname=self.hostname,
            camera_id=camera_id,
            data=alert_data,
            mode=mode,
            trace_id=trace_id,
            correlation_id=correlation_id,
            incident_id=incident_id,
            timestamp=event_time,
        )

        # Explicit envelope validation.
        #
        # Specialized alert.created validation will be enabled after the
        # alert contract is frozen in shared/schemas.
        validate_event(
            alert_event
        )

        # --------------------------------------------------------------------
        # Publish
        # --------------------------------------------------------------------

        output_id = await self.publish(
            OUTPUT_STREAM,
            alert_event.to_dict(),
        )

        print(
            f"[{self.agent_id}] "
            f"ALERT CREATED | "
            f"Camera={camera_id} | "
            f"Type={alert_type} | "
            f"Severity={severity} | "
            f"Count={person_count} | "
            f"Source={behavior_event.get('event_id')} | "
            f"Redis={output_id}"
        )

        return output_id

    # ========================================================================
    # PROCESS SOURCE EVENT
    # ========================================================================

    async def process_behavior_event(
        self,
        event: dict[str, Any],
        source_redis_id: str,
    ) -> bool:
        """
        Validate and process one source event.

        Returns:

            True  -> successfully handled
            False -> valid but unsupported event type
        """

        if not isinstance(event, dict):
            raise ValueError(
                "Behavior event must be an object."
            )

        # --------------------------------------------------------------------
        # Canonical envelope validation.
        # --------------------------------------------------------------------

        validate_event(
            event
        )

        event_type = event.get(
            "event_type"
        )

        camera_id = self._extract_camera_id(
            event
        )

        print(
            f"[{self.agent_id}] "
            f"Received behavior event | "
            f"Type={event_type} | "
            f"Camera={camera_id} | "
            f"Redis={source_redis_id}"
        )

        # --------------------------------------------------------------------
        # Unsupported events are not failures.
        # --------------------------------------------------------------------

        if event_type not in self.supported_events:
            print(
                f"[{self.agent_id}] "
                f"Ignoring unsupported event type: "
                f"{event_type}"
            )

            return False

        # --------------------------------------------------------------------
        # Supported alerts require a valid camera.
        # --------------------------------------------------------------------

        if camera_id is None:
            raise ValueError(
                "Supported alert event has no valid camera_id."
            )

        await self.emit_alert_event(
            behavior_event=event,
            source_redis_id=source_redis_id,
        )

        return True

    # ========================================================================
    # PROCESS REDIS MESSAGE
    # ========================================================================

    async def handle_redis_message(
        self,
        redis_id: str,
        fields: dict[str, Any],
    ):
        """
        Process one Redis Stream message.

        Permanent poison messages:
            ACK

        Processing/network failures:
            DO NOT ACK

        This preserves the message for future pending-message recovery.
        """

        if not self.redis_client:
            raise RuntimeError(
                "Redis client is not initialized."
            )

        try:
            # --------------------------------------------------------------
            # Validate Redis fields.
            # --------------------------------------------------------------

            if not isinstance(fields, dict):
                print(
                    f"[{self.agent_id}] "
                    f"Invalid Redis fields | "
                    f"Redis={redis_id}"
                )

                await self.redis_client.xack(
                    INPUT_STREAM,
                    GROUP_NAME,
                    redis_id,
                )

                return

            raw_event = fields.get(
                "event"
            )

            # --------------------------------------------------------------
            # Missing payload.
            # --------------------------------------------------------------

            if not raw_event:
                print(
                    f"[{self.agent_id}] "
                    f"Missing event payload | "
                    f"Redis={redis_id}"
                )

                # Permanent poison message.
                await self.redis_client.xack(
                    INPUT_STREAM,
                    GROUP_NAME,
                    redis_id,
                )

                return

            # --------------------------------------------------------------
            # JSON parse.
            # --------------------------------------------------------------

            try:
                event = json.loads(
                    raw_event
                )

            except (json.JSONDecodeError, TypeError) as exc:
                print(
                    f"[{self.agent_id}] "
                    f"Invalid JSON | "
                    f"Redis={redis_id} | "
                    f"Error={exc}"
                )

                # Permanent poison message.
                await self.redis_client.xack(
                    INPUT_STREAM,
                    GROUP_NAME,
                    redis_id,
                )

                return

            # --------------------------------------------------------------
            # Object validation.
            # --------------------------------------------------------------

            if not isinstance(event, dict):
                print(
                    f"[{self.agent_id}] "
                    f"Event payload is not an object | "
                    f"Redis={redis_id}"
                )

                # Permanent poison message.
                await self.redis_client.xack(
                    INPUT_STREAM,
                    GROUP_NAME,
                    redis_id,
                )

                return

            # --------------------------------------------------------------
            # Process event.
            # --------------------------------------------------------------

            await self.process_behavior_event(
                event=event,
                source_redis_id=redis_id,
            )

            # --------------------------------------------------------------
            # ACK ONLY AFTER COMPLETE SUCCESS.
            # --------------------------------------------------------------

            await self.redis_client.xack(
                INPUT_STREAM,
                GROUP_NAME,
                redis_id,
            )

            print(
                f"[{self.agent_id}] "
                f"ACK {redis_id}"
            )

        except asyncio.CancelledError:
            raise

        except ValueError as exc:
            # --------------------------------------------------------------
            # Structural/canonical validation failure.
            #
            # These are currently treated as permanent poison messages.
            #
            # Later, replace this with explicit:
            #     PermanentInvalidEvent
            # and quarantine/DLQ handling.
            # --------------------------------------------------------------

            print(
                f"[{self.agent_id}] "
                f"Invalid event | "
                f"Redis={redis_id} | "
                f"{exc}"
            )

            try:
                await self.redis_client.xack(
                    INPUT_STREAM,
                    GROUP_NAME,
                    redis_id,
                )

                print(
                    f"[{self.agent_id}] "
                    f"ACK invalid event {redis_id}"
                )

            except Exception as ack_exc:
                print(
                    f"[{self.agent_id}] "
                    f"Failed to ACK invalid event "
                    f"{redis_id} | "
                    f"{type(ack_exc).__name__}: "
                    f"{ack_exc}"
                )

                raise

        except Exception as exc:
            # --------------------------------------------------------------
            # Processing failures are NOT ACKed.
            #
            # The Redis message therefore remains pending.
            # --------------------------------------------------------------

            print(
                f"[{self.agent_id}] "
                f"Error processing {redis_id} | "
                f"{type(exc).__name__}: "
                f"{exc}"
            )

            raise

    # ========================================================================
    # MAIN PROCESSING LOOP
    # ========================================================================

    async def run(self):
        """
        Main Redis consumer loop.

        Redis connection/read failures do not terminate the Alert Agent.

        Individual message failures do not terminate the Alert Agent.
        """

        if not self.redis_client:
            raise RuntimeError(
                "Redis client is not initialized."
            )

        print(
            f"[{self.agent_id}] "
            f"Alert processing loop started."
        )

        while self.running:

            # --------------------------------------------------------------
            # Read from Redis.
            # --------------------------------------------------------------

            try:
                messages = await self.redis_client.xreadgroup(
                    groupname=GROUP_NAME,
                    consumername=self.consumer_name,
                    streams={
                        INPUT_STREAM: ">"
                    },
                    count=READ_COUNT,
                    block=READ_BLOCK_MS,
                )

            except asyncio.CancelledError:
                raise

            except Exception as exc:
                # Redis failure must not terminate this worker.
                print(
                    f"[{self.agent_id}] "
                    f"Redis read error | "
                    f"{type(exc).__name__}: "
                    f"{exc}"
                )

                await self.sleep(2)

                continue

            # --------------------------------------------------------------
            # No messages.
            # --------------------------------------------------------------

            if not messages:
                continue

            # --------------------------------------------------------------
            # Process every message independently.
            # --------------------------------------------------------------

            for stream_name, stream_messages in messages:

                # Defensive stream check.
                if stream_name != INPUT_STREAM:
                    print(
                        f"[{self.agent_id}] "
                        f"Unexpected stream received: "
                        f"{stream_name}"
                    )

                    continue

                for redis_id, fields in stream_messages:

                    try:
                        await self.handle_redis_message(
                            redis_id=redis_id,
                            fields=fields,
                        )

                    except asyncio.CancelledError:
                        raise

                    except Exception as exc:
                        # --------------------------------------------------
                        # A single failed message must NOT terminate the
                        # entire Alert Agent.
                        #
                        # The failed Redis message remains pending.
                        # --------------------------------------------------

                        print(
                            f"[{self.agent_id}] "
                            f"Message {redis_id} "
                            f"left pending for recovery | "
                            f"{type(exc).__name__}: "
                            f"{exc}"
                        )

                        continue


# ============================================================================
# ENTRY POINT
# ============================================================================


async def main():
    agent = AlertAgent(
        agent_id=os.getenv(
            "AGENT_ID",
            DEFAULT_AGENT_ID,
        )
    )

    await agent.run_forever()


if __name__ == "__main__":
    asyncio.run(
        main()
    )
