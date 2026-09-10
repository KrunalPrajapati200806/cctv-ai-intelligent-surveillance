# # # # import asyncio
# # # # import json
# # # # import os
# # # # import uuid
# # # # from datetime import datetime, timezone

# # # # import redis.asyncio as redis


# # # # # ============================================================
# # # # # CONFIG
# # # # # ============================================================

# # # # REDIS_HOST = os.getenv(
# # # #     "REDIS_HOST",
# # # #     "localhost",
# # # # )

# # # # REDIS_PORT = int(
# # # #     os.getenv(
# # # #         "REDIS_PORT",
# # # #         "6379",
# # # #     )
# # # # )

# # # # INPUT_STREAM = "events.tracking"
# # # # OUTPUT_STREAM = "events.behavior"

# # # # GROUP_NAME = "security-workers"
# # # # CONSUMER_NAME = "security-01"

# # # # # ------------------------------------------------------------
# # # # # Restricted zone
# # # # #
# # # # # A person whose CENTER enters this rectangle will generate
# # # # # an intrusion.detected event.
# # # # #
# # # # # Change these values later according to your camera.
# # # # # ------------------------------------------------------------

# # # # ZONE_X1 = float(
# # # #     os.getenv("ZONE_X1", "50")
# # # # )

# # # # ZONE_Y1 = float(
# # # #     os.getenv("ZONE_Y1", "50")
# # # # )

# # # # ZONE_X2 = float(
# # # #     os.getenv("ZONE_X2", "700")
# # # # )

# # # # ZONE_Y2 = float(
# # # #     os.getenv("ZONE_Y2", "450")
# # # # )

# # # # SECURITY_SEVERITY = os.getenv(
# # # #     "SECURITY_SEVERITY",
# # # #     "high",
# # # # )


# # # # # ============================================================
# # # # # TRACK STATE
# # # # # ============================================================

# # # # # Prevent the same track from generating an intrusion alert
# # # # # on every single frame.
# # # # #
# # # # # Example:
# # # # #
# # # # # track-abc -> already alerted
# # # # #
# # # # # Once the person leaves the zone, the track is removed from
# # # # # this set and can trigger again if they re-enter.
# # # # #
# # # # alerted_tracks = set()


# # # # # ============================================================
# # # # # REDIS CONSUMER GROUP
# # # # # ============================================================

# # # # async def ensure_consumer_group(
# # # #     redis_client,
# # # # ):

# # # #     try:

# # # #         await redis_client.xgroup_create(
# # # #             name=INPUT_STREAM,
# # # #             groupname=GROUP_NAME,
# # # #             id="0",
# # # #             mkstream=True,
# # # #         )

# # # #         print(
# # # #             f"Created consumer group: "
# # # #             f"{GROUP_NAME}"
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
# # # # # CHECK WHETHER POINT IS INSIDE ZONE
# # # # # ============================================================

# # # # def point_inside_zone(
# # # #     x,
# # # #     y,
# # # # ):

# # # #     return (
# # # #         ZONE_X1 <= x <= ZONE_X2
# # # #         and
# # # #         ZONE_Y1 <= y <= ZONE_Y2
# # # #     )


# # # # # ============================================================
# # # # # CREATE INTRUSION EVENT
# # # # # ============================================================

# # # # async def emit_intrusion_event(
# # # #     redis_client,
# # # #     tracking_event,
# # # #     track,
# # # # ):

# # # #     camera = tracking_event.get(
# # # #         "camera",
# # # #         {},
# # # #     )

# # # #     camera_id = camera.get(
# # # #         "camera_id",
# # # #         "unknown",
# # # #     )

# # # #     data = tracking_event.get(
# # # #         "data",
# # # #         {},
# # # #     )

# # # #     track_id = track.get(
# # # #         "track_id",
# # # #     )

# # # #     detection_id = track.get(
# # # #         "detection_id",
# # # #     )

# # # #     bbox = track.get(
# # # #         "bbox",
# # # #         [],
# # # #     )

# # # #     center = track.get(
# # # #         "center",
# # # #         [],
# # # #     )

# # # #     frame_id = data.get(
# # # #         "frame_id",
# # # #     )

# # # #     event = {

# # # #         "event_id": str(
# # # #             uuid.uuid4()
# # # #         ),

# # # #         "event_type":
# # # #             "intrusion.detected",

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

# # # #             "track_id":
# # # #                 track_id,

# # # #             "detection_id":
# # # #                 detection_id,

# # # #             "bbox":
# # # #                 bbox,

# # # #             "center":
# # # #                 center,

# # # #             "frame_id":
# # # #                 frame_id,

# # # #             "severity":
# # # #                 SECURITY_SEVERITY,

# # # #             "zone": {

# # # #                 "x1":
# # # #                     ZONE_X1,

# # # #                 "y1":
# # # #                     ZONE_Y1,

# # # #                 "x2":
# # # #                     ZONE_X2,

# # # #                 "y2":
# # # #                     ZONE_Y2,
# # # #             },

# # # #             "message":
# # # #                 (
# # # #                     f"Person entered "
# # # #                     f"restricted zone on "
# # # #                     f"{camera_id}"
# # # #                 ),

# # # #             "source_event_id":
# # # #                 tracking_event.get(
# # # #                     "event_id"
# # # #                 ),
# # # #         },
# # # #     }

# # # #     redis_id = await redis_client.xadd(
# # # #         OUTPUT_STREAM,
# # # #         {
# # # #             "event":
# # # #                 json.dumps(event)
# # # #         },
# # # #     )

# # # #     print(
# # # #         f"🚨 INTRUSION DETECTED | "
# # # #         f"Camera={camera_id} | "
# # # #         f"Track={track_id} | "
# # # #         f"Severity={SECURITY_SEVERITY} | "
# # # #         f"Redis={redis_id}"
# # # #     )


# # # # # ============================================================
# # # # # PROCESS TRACKING EVENT
# # # # # ============================================================

# # # # async def process_tracking_event(
# # # #     redis_client,
# # # #     event,
# # # # ):

# # # #     # --------------------------------------------------------
# # # #     # Validate event type
# # # #     # --------------------------------------------------------

# # # #     if event.get("event_type") != "person.tracked":

# # # #         print(
# # # #             f"Ignoring event type: "
# # # #             f"{event.get('event_type')}"
# # # #         )

# # # #         return

# # # #     # --------------------------------------------------------
# # # #     # Camera
# # # #     # --------------------------------------------------------

# # # #     camera = event.get(
# # # #         "camera",
# # # #         {},
# # # #     )

# # # #     if not isinstance(camera, dict):

# # # #         print(
# # # #             "Ignoring event with invalid camera."
# # # #         )

# # # #         return

# # # #     camera_id = camera.get(
# # # #         "camera_id",
# # # #         "unknown",
# # # #     )

# # # #     # --------------------------------------------------------
# # # #     # Data
# # # #     # --------------------------------------------------------

# # # #     data = event.get(
# # # #         "data",
# # # #         {},
# # # #     )

# # # #     if not isinstance(data, dict):

# # # #         print(
# # # #             f"Ignoring invalid data | "
# # # #             f"Camera={camera_id}"
# # # #         )

# # # #         return

# # # #     tracks = data.get(
# # # #         "tracks",
# # # #         [],
# # # #     )

# # # #     if not isinstance(tracks, list):

# # # #         print(
# # # #             f"Ignoring invalid tracks | "
# # # #             f"Camera={camera_id}"
# # # #         )

# # # #         return

# # # #     # --------------------------------------------------------
# # # #     # Keep track IDs currently inside the zone.
# # # #     # --------------------------------------------------------

# # # #     currently_inside = set()

# # # #     # --------------------------------------------------------
# # # #     # Check every tracked person
# # # #     # --------------------------------------------------------

# # # #     for track in tracks:

# # # #         if not isinstance(
# # # #             track,
# # # #             dict,
# # # #         ):
# # # #             continue

# # # #         track_id = track.get(
# # # #             "track_id"
# # # #         )

# # # #         if not track_id:
# # # #             continue

# # # #         center = track.get(
# # # #             "center"
# # # #         )

# # # #         # ----------------------------------------------------
# # # #         # Validate center
# # # #         # ----------------------------------------------------

# # # #         if (
# # # #             not isinstance(center, list)
# # # #             or len(center) != 2
# # # #         ):
# # # #             continue

# # # #         try:

# # # #             center_x = float(
# # # #                 center[0]
# # # #             )

# # # #             center_y = float(
# # # #                 center[1]
# # # #             )

# # # #         except (
# # # #             TypeError,
# # # #             ValueError,
# # # #         ):

# # # #             continue

# # # #         # ----------------------------------------------------
# # # #         # Check restricted zone
# # # #         # ----------------------------------------------------

# # # #         inside = point_inside_zone(
# # # #             center_x,
# # # #             center_y,
# # # #         )

# # # #         if inside:

# # # #             currently_inside.add(
# # # #                 track_id
# # # #             )

# # # #             # ------------------------------------------------
# # # #             # Only generate the alert once while the person
# # # #             # remains inside.
# # # #             # ------------------------------------------------

# # # #             if track_id not in alerted_tracks:

# # # #                 await emit_intrusion_event(
# # # #                     redis_client,
# # # #                     event,
# # # #                     track,
# # # #                 )

# # # #                 alerted_tracks.add(
# # # #                     track_id
# # # #                 )

# # # #                 print(
# # # #                     f"Security zone entered | "
# # # #                     f"Camera={camera_id} | "
# # # #                     f"Track={track_id} | "
# # # #                     f"Center=({center_x:.1f}, "
# # # #                     f"{center_y:.1f})"
# # # #                 )

# # # #     # --------------------------------------------------------
# # # #     # Remove tracks that have left the zone.
# # # #     #
# # # #     # This allows the same person to trigger another alert
# # # #     # after leaving and re-entering.
# # # #     # --------------------------------------------------------

# # # #     tracks_to_remove = (
# # # #         alerted_tracks
# # # #         - currently_inside
# # # #     )

# # # #     for track_id in tracks_to_remove:

# # # #         alerted_tracks.discard(
# # # #             track_id
# # # #         )

# # # #         print(
# # # #             f"Security zone exited | "
# # # #             f"Camera={camera_id} | "
# # # #             f"Track={track_id}"
# # # #         )


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

# # # #     await ensure_consumer_group(
# # # #         redis_client
# # # #     )

# # # #     print(
# # # #         "=" * 60
# # # #     )

# # # #     print(
# # # #         f"Security Agent started: "
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
# # # #         f"Restricted zone: "
# # # #         f"({ZONE_X1}, {ZONE_Y1}) -> "
# # # #         f"({ZONE_X2}, {ZONE_Y2})"
# # # #     )

# # # #     print(
# # # #         f"Severity: "
# # # #         f"{SECURITY_SEVERITY}"
# # # #     )

# # # #     print(
# # # #         "=" * 60
# # # #     )

# # # #     try:

# # # #         while True:

# # # #             # =================================================
# # # #             # READ TRACKING EVENTS
# # # #             # =================================================

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

# # # #             # =================================================
# # # #             # PROCESS MESSAGES
# # # #             # =================================================

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
# # # #                                 f"Missing event "
# # # #                                 f"payload | "
# # # #                                 f"Redis={redis_id}"
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

# # # #                         print(
# # # #                             f"Security received | "
# # # #                             f"Type={event.get('event_type')} | "
# # # #                             f"Redis={redis_id}"
# # # #                         )

# # # #                         await process_tracking_event(
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

# # # #                         # Do NOT ACK processing failures.
# # # #                         # Redis keeps the message pending.

# # # #     finally:

# # # #         await redis_client.aclose()

# # # #         print(
# # # #             "Security Agent stopped."
# # # #         )


# # # # # ============================================================
# # # # # ENTRY POINT
# # # # # ============================================================

# # # # if __name__ == "__main__":

# # # #     asyncio.run(
# # # #         main()
# # # #     )











# # # import json
# # # import os
# # # import uuid
# # # from typing import Optional

# # # from shared.agent.base_agent import BaseAgent


# # # # ============================================================
# # # # CONFIG
# # # # ============================================================

# # # INPUT_STREAM = "events.tracking"
# # # OUTPUT_STREAM = "events.behavior"

# # # GROUP_NAME = "security-workers"

# # # DEFAULT_AGENT_ID = os.getenv(
# # #     "SECURITY_AGENT_ID",
# # #     "security-01",
# # # )

# # # # ------------------------------------------------------------
# # # # Restricted zone
# # # # ------------------------------------------------------------

# # # ZONE_X1 = float(
# # #     os.getenv("ZONE_X1", "50")
# # # )

# # # ZONE_Y1 = float(
# # #     os.getenv("ZONE_Y1", "50")
# # # )

# # # ZONE_X2 = float(
# # #     os.getenv("ZONE_X2", "700")
# # # )

# # # ZONE_Y2 = float(
# # #     os.getenv("ZONE_Y2", "450")
# # # )

# # # SECURITY_SEVERITY = os.getenv(
# # #     "SECURITY_SEVERITY",
# # #     "high",
# # # )


# # # # ============================================================
# # # # SECURITY AGENT
# # # # ============================================================

# # # class SecurityAgent(BaseAgent):

# # #     def __init__(
# # #         self,
# # #         agent_id: Optional[str] = None,
# # #     ):
# # #         super().__init__(
# # #             agent_id=agent_id or DEFAULT_AGENT_ID,
# # #         )

# # #         # ----------------------------------------------------
# # #         # Tracks that have already triggered an intrusion
# # #         # while currently inside the zone.
# # #         #
# # #         # Important:
# # #         # This is kept per camera so identical track IDs from
# # #         # different cameras cannot interfere with each other.
# # #         # ----------------------------------------------------

# # #         self.alerted_tracks = {}

# # #         # ----------------------------------------------------
# # #         # Unique Redis consumer name.
# # #         #
# # #         # agent_id identifies the agent.
# # #         # consumer_name identifies this running worker instance.
# # #         # ----------------------------------------------------

# # #         self.consumer_name = (
# # #             f"{self.agent_id}-"
# # #             f"{uuid.uuid4().hex[:8]}"
# # #         )

# # #     # ========================================================
# # #     # STARTUP
# # #     # ========================================================

# # #     async def on_start(self):

# # #         await self.ensure_consumer_group()

# # #         print(
# # #             f"[{self.agent_id}] Security agent ready."
# # #         )

# # #         print(
# # #             f"[{self.agent_id}] "
# # #             f"Input: {INPUT_STREAM}"
# # #         )

# # #         print(
# # #             f"[{self.agent_id}] "
# # #             f"Output: {OUTPUT_STREAM}"
# # #         )

# # #         print(
# # #             f"[{self.agent_id}] "
# # #             f"Consumer: {self.consumer_name}"
# # #         )

# # #         print(
# # #             f"[{self.agent_id}] "
# # #             f"Restricted zone: "
# # #             f"({ZONE_X1}, {ZONE_Y1}) -> "
# # #             f"({ZONE_X2}, {ZONE_Y2})"
# # #         )

# # #         print(
# # #             f"[{self.agent_id}] "
# # #             f"Severity: {SECURITY_SEVERITY}"
# # #         )

# # #     # ========================================================
# # #     # SHUTDOWN
# # #     # ========================================================

# # #     async def on_stop(self):

# # #         self.alerted_tracks.clear()

# # #         print(
# # #             f"[{self.agent_id}] "
# # #             f"Security state cleared."
# # #         )

# # #     # ========================================================
# # #     # REDIS CONSUMER GROUP
# # #     # ========================================================

# # #     async def ensure_consumer_group(self):

# # #         if not self.redis_client:
# # #             raise RuntimeError(
# # #                 "Redis client is not initialized."
# # #             )

# # #         try:

# # #             await self.redis_client.xgroup_create(
# # #                 name=INPUT_STREAM,
# # #                 groupname=GROUP_NAME,
# # #                 id="0",
# # #                 mkstream=True,
# # #             )

# # #             print(
# # #                 f"[{self.agent_id}] "
# # #                 f"Created consumer group: "
# # #                 f"{GROUP_NAME}"
# # #             )

# # #         except Exception as exc:

# # #             if "BUSYGROUP" in str(exc):

# # #                 print(
# # #                     f"[{self.agent_id}] "
# # #                     f"Consumer group already exists: "
# # #                     f"{GROUP_NAME}"
# # #                 )

# # #             else:
# # #                 raise

# # #     # ========================================================
# # #     # POINT INSIDE RESTRICTED ZONE
# # #     # ========================================================

# # #     @staticmethod
# # #     def point_inside_zone(
# # #         x: float,
# # #         y: float,
# # #     ) -> bool:

# # #         return (
# # #             ZONE_X1 <= x <= ZONE_X2
# # #             and
# # #             ZONE_Y1 <= y <= ZONE_Y2
# # #         )

# # #     # ========================================================
# # #     # EMIT INTRUSION EVENT
# # #     # ========================================================

# # #     async def emit_intrusion_event(
# # #         self,
# # #         tracking_event: dict,
# # #         track: dict,
# # #     ):

# # #         camera = tracking_event.get(
# # #             "camera",
# # #             {},
# # #         )

# # #         camera_id = camera.get(
# # #             "camera_id",
# # #             "unknown",
# # #         )

# # #         data = tracking_event.get(
# # #             "data",
# # #             {},
# # #         )

# # #         track_id = track.get(
# # #             "track_id",
# # #         )

# # #         detection_id = track.get(
# # #             "detection_id",
# # #         )

# # #         bbox = track.get(
# # #             "bbox",
# # #             [],
# # #         )

# # #         center = track.get(
# # #             "center",
# # #             [],
# # #         )

# # #         frame_id = data.get(
# # #             "frame_id",
# # #         )

# # #         event = {
# # #             "event_id": str(
# # #                 uuid.uuid4()
# # #             ),

# # #             "event_type":
# # #                 "intrusion.detected",

# # #             "version":
# # #                 "1.0",

# # #             "timestamp":
# # #                 self.now(),

# # #             "source": {
# # #                 "agent_id":
# # #                     self.agent_id,
# # #             },

# # #             "camera": {
# # #                 "camera_id":
# # #                     camera_id,
# # #             },

# # #             "data": {

# # #                 "track_id":
# # #                     track_id,

# # #                 "detection_id":
# # #                     detection_id,

# # #                 "bbox":
# # #                     bbox,

# # #                 "center":
# # #                     center,

# # #                 "frame_id":
# # #                     frame_id,

# # #                 "severity":
# # #                     SECURITY_SEVERITY,

# # #                 "zone": {

# # #                     "x1":
# # #                         ZONE_X1,

# # #                     "y1":
# # #                         ZONE_Y1,

# # #                     "x2":
# # #                         ZONE_X2,

# # #                     "y2":
# # #                         ZONE_Y2,
# # #                 },

# # #                 "message":
# # #                     (
# # #                         f"Person entered "
# # #                         f"restricted zone on "
# # #                         f"{camera_id}"
# # #                     ),

# # #                 "source_event_id":
# # #                     tracking_event.get(
# # #                         "event_id"
# # #                     ),
# # #             },
# # #         }

# # #         redis_id = await self.publish(
# # #             OUTPUT_STREAM,
# # #             event,
# # #         )

# # #         print(
# # #             f" INTRUSION DETECTED | "
# # #             f"Camera={camera_id} | "
# # #             f"Track={track_id} | "
# # #             f"Severity={SECURITY_SEVERITY} | "
# # #             f"Redis={redis_id}"
# # #         )

# # #     # ========================================================
# # #     # PROCESS TRACKING EVENT
# # #     # ========================================================

# # #     async def process_tracking_event(
# # #         self,
# # #         event: dict,
# # #     ):

# # #         # ----------------------------------------------------
# # #         # Validate event type
# # #         # ----------------------------------------------------

# # #         if event.get(
# # #             "event_type"
# # #         ) != "person.tracked":

# # #             return

# # #         # ----------------------------------------------------
# # #         # Camera
# # #         # ----------------------------------------------------

# # #         camera = event.get(
# # #             "camera",
# # #             {},
# # #         )

# # #         if not isinstance(
# # #             camera,
# # #             dict,
# # #         ):

# # #             print(
# # #                 f"[{self.agent_id}] "
# # #                 f"Ignoring invalid camera."
# # #             )

# # #             return

# # #         camera_id = camera.get(
# # #             "camera_id",
# # #             "unknown",
# # #         )

# # #         # ----------------------------------------------------
# # #         # Data
# # #         # ----------------------------------------------------

# # #         data = event.get(
# # #             "data",
# # #             {},
# # #         )

# # #         if not isinstance(
# # #             data,
# # #             dict,
# # #         ):

# # #             print(
# # #                 f"[{self.agent_id}] "
# # #                 f"Ignoring invalid data | "
# # #                 f"Camera={camera_id}"
# # #             )

# # #             return

# # #         tracks = data.get(
# # #             "tracks",
# # #             [],
# # #         )

# # #         if not isinstance(
# # #             tracks,
# # #             list,
# # #         ):

# # #             print(
# # #                 f"[{self.agent_id}] "
# # #                 f"Ignoring invalid tracks | "
# # #                 f"Camera={camera_id}"
# # #             )

# # #             return

# # #         # ----------------------------------------------------
# # #         # Create camera-specific alert state.
# # #         #
# # #         # This is important for future multi-camera support.
# # #         # ----------------------------------------------------

# # #         if camera_id not in self.alerted_tracks:

# # #             self.alerted_tracks[camera_id] = set()

# # #         camera_alerted_tracks = (
# # #             self.alerted_tracks[camera_id]
# # #         )

# # #         # ----------------------------------------------------
# # #         # Tracks currently inside zone
# # #         # ----------------------------------------------------

# # #         currently_inside = set()

# # #         # ----------------------------------------------------
# # #         # Process every tracked person
# # #         # ----------------------------------------------------

# # #         for track in tracks:

# # #             if not isinstance(
# # #                 track,
# # #                 dict,
# # #             ):
# # #                 continue

# # #             track_id = track.get(
# # #                 "track_id"
# # #             )

# # #             if not track_id:
# # #                 continue

# # #             center = track.get(
# # #                 "center"
# # #             )

# # #             # ------------------------------------------------
# # #             # Validate center
# # #             # ------------------------------------------------

# # #             if (
# # #                 not isinstance(
# # #                     center,
# # #                     list,
# # #                 )
# # #                 or len(center) != 2
# # #             ):

# # #                 continue

# # #             try:

# # #                 center_x = float(
# # #                     center[0]
# # #                 )

# # #                 center_y = float(
# # #                     center[1]
# # #                 )

# # #             except (
# # #                 TypeError,
# # #                 ValueError,
# # #             ):

# # #                 continue

# # #             # ------------------------------------------------
# # #             # Check restricted zone
# # #             # ------------------------------------------------

# # #             inside = self.point_inside_zone(
# # #                 center_x,
# # #                 center_y,
# # #             )

# # #             if not inside:
# # #                 continue

# # #             currently_inside.add(
# # #                 track_id
# # #             )

# # #             # ------------------------------------------------
# # #             # Generate only one alert while inside.
# # #             # ------------------------------------------------

# # #             if (
# # #                 track_id
# # #                 not in camera_alerted_tracks
# # #             ):

# # #                 await self.emit_intrusion_event(
# # #                     tracking_event=event,
# # #                     track=track,
# # #                 )

# # #                 camera_alerted_tracks.add(
# # #                     track_id
# # #                 )

# # #                 print(
# # #                     f"[{self.agent_id}] "
# # #                     f"Security zone entered | "
# # #                     f"Camera={camera_id} | "
# # #                     f"Track={track_id} | "
# # #                     f"Center=("
# # #                     f"{center_x:.1f}, "
# # #                     f"{center_y:.1f})"
# # #                 )

# # #         # ----------------------------------------------------
# # #         # Remove tracks that left the zone.
# # #         #
# # #         # This allows re-entry to trigger again.
# # #         # ----------------------------------------------------

# # #         tracks_to_remove = (
# # #             camera_alerted_tracks
# # #             - currently_inside
# # #         )

# # #         for track_id in tracks_to_remove:

# # #             camera_alerted_tracks.discard(
# # #                 track_id
# # #             )

# # #             print(
# # #                 f"[{self.agent_id}] "
# # #                 f"Security zone exited | "
# # #                 f"Camera={camera_id} | "
# # #                 f"Track={track_id}"
# # #             )

# # #         # ----------------------------------------------------
# # #         # Remove empty camera state.
# # #         # ----------------------------------------------------

# # #         if not camera_alerted_tracks:

# # #             self.alerted_tracks.pop(
# # #                 camera_id,
# # #                 None,
# # #             )

# # #     # ========================================================
# # #     # MAIN PROCESSING LOOP
# # #     # ========================================================

# # #     async def run(self):

# # #         if not self.redis_client:
# # #             raise RuntimeError(
# # #                 "Redis client is not initialized."
# # #             )

# # #         print(
# # #             f"[{self.agent_id}] "
# # #             f"Security processing loop started."
# # #         )

# # #         while self.running:

# # #             try:

# # #                 messages = (
# # #                     await self.redis_client.xreadgroup(
# # #                         groupname=GROUP_NAME,

# # #                         consumername=
# # #                             self.consumer_name,

# # #                         streams={
# # #                             INPUT_STREAM: ">"
# # #                         },

# # #                         count=10,

# # #                         block=5000,
# # #                     )
# # #                 )

# # #             except Exception as exc:

# # #                 # ------------------------------------------------
# # #                 # Redis failure should not immediately kill the
# # #                 # whole agent.
# # #                 # ------------------------------------------------

# # #                 print(
# # #                     f"[{self.agent_id}] "
# # #                     f"Redis read error: "
# # #                     f"{type(exc).__name__}: {exc}"
# # #                 )

# # #                 await self.sleep(2)

# # #                 continue

# # #             if not messages:
# # #                 continue

# # #             # ------------------------------------------------
# # #             # Process messages independently.
# # #             # ------------------------------------------------

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

# # #                         # ----------------------------------------
# # #                         # Missing event payload
# # #                         # ----------------------------------------

# # #                         if not raw_event:

# # #                             print(
# # #                                 f"[{self.agent_id}] "
# # #                                 f"Missing event payload | "
# # #                                 f"Redis={redis_id}"
# # #                             )

# # #                             await self.redis_client.xack(
# # #                                 INPUT_STREAM,
# # #                                 GROUP_NAME,
# # #                                 redis_id,
# # #                             )

# # #                             continue

# # #                         # ----------------------------------------
# # #                         # Parse JSON
# # #                         # ----------------------------------------

# # #                         event = json.loads(
# # #                             raw_event
# # #                         )

# # #                         print(
# # #                             f"[{self.agent_id}] "
# # #                             f"Security received | "
# # #                             f"Type="
# # #                             f"{event.get('event_type')} | "
# # #                             f"Redis={redis_id}"
# # #                         )

# # #                         # ----------------------------------------
# # #                         # Process this event.
# # #                         #
# # #                         # Failure here is isolated to this
# # #                         # message.
# # #                         # ----------------------------------------

# # #                         await self.process_tracking_event(
# # #                             event
# # #                         )

# # #                         # ----------------------------------------
# # #                         # ACK only after successful processing.
# # #                         # ----------------------------------------

# # #                         await self.redis_client.xack(
# # #                             INPUT_STREAM,
# # #                             GROUP_NAME,
# # #                             redis_id,
# # #                         )

# # #                     except json.JSONDecodeError as exc:

# # #                         # Malformed JSON is a bad message,
# # #                         # not a reason to retry forever.

# # #                         print(
# # #                             f"[{self.agent_id}] "
# # #                             f"Invalid JSON | "
# # #                             f"Redis={redis_id} | "
# # #                             f"Error={exc}"
# # #                         )

# # #                         await self.redis_client.xack(
# # #                             INPUT_STREAM,
# # #                             GROUP_NAME,
# # #                             redis_id,
# # #                         )

# # #                     except Exception as exc:

# # #                         # ------------------------------------------------
# # #                         # IMPORTANT:
# # #                         #
# # #                         # Do NOT ACK unexpected processing failures.
# # #                         #
# # #                         # Redis keeps the message pending so the
# # #                         # monitoring/recovery system can reclaim it.
# # #                         # ------------------------------------------------

# # #                         print(
# # #                             f"[{self.agent_id}] "
# # #                             f"ERROR processing "
# # #                             f"{redis_id} | "
# # #                             f"{type(exc).__name__}: "
# # #                             f"{exc}"
# # #                         )

# # #                         # Continue with the next message.
# # #                         continue


# # # # ============================================================
# # # # ENTRY POINT
# # # # ============================================================

# # # if __name__ == "__main__":

# # #     agent = SecurityAgent()

# # #     try:

# # #         import asyncio

# # #         asyncio.run(
# # #             agent.run_forever()
# # #         )

# # #     except KeyboardInterrupt:

# # #         print(
# # #             "\nSecurity Agent interrupted."
# # #         )
















# # """
# # Security Agent
# # ==============

# # Consumes canonical `person.tracked` events and detects restricted-zone
# # intrusions.

# # Pipeline:

# #     events.tracking
# #           |
# #           v
# #     SecurityAgent
# #           |
# #           v
# #     events.behavior
# #           |
# #           +--> intrusion.detected

# # Design principles:
# # - Canonical event schema
# # - Camera-aware state
# # - Historical-mode timestamp preservation
# # - Trace/correlation/incident propagation
# # - Source-event lineage
# # - Per-message fault isolation
# # - ACK only after successful processing
# # - No silent camera fallback
# # - Same-camera routing/affinity is required for stateful workers

# # NOTE:
# # The current restricted-zone configuration is environment based and therefore
# # still global to this worker. Camera-specific policies will be introduced
# # through the Camera Registry / Policy layer in a later phase.
# # """

# # from __future__ import annotations

# # import json
# # import os
# # import uuid
# # from datetime import datetime, timezone
# # from typing import Any, Optional

# # from shared.agent.base_agent import BaseAgent
# # from shared.schemas.event_schema import create_event, validate_event


# # # ============================================================
# # # CONFIG
# # # ============================================================

# # INPUT_STREAM = os.getenv(
# #     "SECURITY_INPUT_STREAM",
# #     "events.tracking",
# # )

# # OUTPUT_STREAM = os.getenv(
# #     "SECURITY_OUTPUT_STREAM",
# #     "events.behavior",
# # )

# # GROUP_NAME = os.getenv(
# #     "SECURITY_GROUP",
# #     "security-workers",
# # )

# # DEFAULT_AGENT_ID = os.getenv(
# #     "SECURITY_AGENT_ID",
# #     "security-01",
# # )

# # CONSUMER_NAME_PREFIX = os.getenv(
# #     "SECURITY_CONSUMER_PREFIX",
# #     DEFAULT_AGENT_ID,
# # )


# # # ============================================================
# # # RESTRICTED ZONE CONFIGURATION
# # # ============================================================

# # def _read_float_env(
# #     name: str,
# #     default: str,
# # ) -> float:
# #     raw_value = os.getenv(name, default)

# #     try:
# #         value = float(raw_value)
# #     except (TypeError, ValueError) as exc:
# #         raise ValueError(
# #             f"{name} must be a valid number. "
# #             f"Received: {raw_value!r}"
# #         ) from exc

# #     if value != value:
# #         raise ValueError(
# #             f"{name} cannot be NaN."
# #         )

# #     if value in (
# #         float("inf"),
# #         float("-inf"),
# #     ):
# #         raise ValueError(
# #             f"{name} must be finite."
# #         )

# #     return value


# # ZONE_X1 = _read_float_env(
# #     "ZONE_X1",
# #     "50",
# # )

# # ZONE_Y1 = _read_float_env(
# #     "ZONE_Y1",
# #     "50",
# # )

# # ZONE_X2 = _read_float_env(
# #     "ZONE_X2",
# #     "700",
# # )

# # ZONE_Y2 = _read_float_env(
# #     "ZONE_Y2",
# #     "450",
# # )

# # SECURITY_SEVERITY = os.getenv(
# #     "SECURITY_SEVERITY",
# #     "high",
# # ).strip().lower()

# # VALID_SEVERITIES = {
# #     "low",
# #     "medium",
# #     "high",
# #     "critical",
# # }


# # # ============================================================
# # # SECURITY AGENT
# # # ============================================================

# # class SecurityAgent(BaseAgent):

# #     def __init__(
# #         self,
# #         agent_id: Optional[str] = None,
# #     ):
# #         super().__init__(
# #             agent_id=agent_id or DEFAULT_AGENT_ID,
# #         )

# #         self._validate_configuration()

# #         # ----------------------------------------------------
# #         # Camera-specific alert state.
# #         #
# #         # Example:
# #         #
# #         # {
# #         #     "CAM01": {"1", "4"},
# #         #     "CAM02": {"2"}
# #         # }
# #         #
# #         # Stateful security workers therefore require
# #         # camera affinity/routing.
# #         # ----------------------------------------------------

# #         self.alerted_tracks: dict[str, set[str]] = {}

# #         # ----------------------------------------------------
# #         # Unique Redis consumer name.
# #         #
# #         # agent_id identifies the logical agent.
# #         # consumer_name identifies this running process.
# #         # ----------------------------------------------------

# #         self.consumer_name = (
# #             f"{CONSUMER_NAME_PREFIX}-"
# #             f"{uuid.uuid4().hex[:8]}"
# #         )

# #     # ========================================================
# #     # CONFIGURATION VALIDATION
# #     # ========================================================

# #     @staticmethod
# #     def _validate_configuration() -> None:

# #         if ZONE_X1 >= ZONE_X2:
# #             raise ValueError(
# #                 "Invalid security zone: "
# #                 "ZONE_X1 must be smaller than ZONE_X2."
# #             )

# #         if ZONE_Y1 >= ZONE_Y2:
# #             raise ValueError(
# #                 "Invalid security zone: "
# #                 "ZONE_Y1 must be smaller than ZONE_Y2."
# #             )

# #         if SECURITY_SEVERITY not in VALID_SEVERITIES:
# #             raise ValueError(
# #                 "SECURITY_SEVERITY must be one of: "
# #                 f"{sorted(VALID_SEVERITIES)}. "
# #                 f"Received: {SECURITY_SEVERITY!r}"
# #             )

# #     # ========================================================
# #     # STARTUP
# #     # ========================================================

# #     async def on_start(self):

# #         await self.ensure_consumer_group()

# #         print(
# #             f"[{self.agent_id}] Security agent ready."
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Instance={self.instance_id}"
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Hostname={self.hostname}"
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Input: {INPUT_STREAM}"
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Output: {OUTPUT_STREAM}"
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Consumer: {self.consumer_name}"
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Restricted zone: "
# #             f"({ZONE_X1}, {ZONE_Y1}) -> "
# #             f"({ZONE_X2}, {ZONE_Y2})"
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Severity: {SECURITY_SEVERITY}"
# #         )

# #     # ========================================================
# #     # SHUTDOWN
# #     # ========================================================

# #     async def on_stop(self):

# #         self.alerted_tracks.clear()

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Security state cleared."
# #         )

# #     # ========================================================
# #     # REDIS CONSUMER GROUP
# #     # ========================================================

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

# #     # ========================================================
# #     # TIMESTAMP PARSER
# #     # ========================================================

# #     @staticmethod
# #     def _parse_timestamp(
# #         value: Any,
# #     ) -> Optional[datetime]:
# #         """
# #         Parse an ISO timestamp and normalize it to UTC.
# #         """

# #         if not isinstance(value, str):
# #             return None

# #         value = value.strip()

# #         if not value:
# #             return None

# #         try:

# #             parsed = datetime.fromisoformat(
# #                 value.replace(
# #                     "Z",
# #                     "+00:00",
# #                 )
# #             )

# #         except ValueError:
# #             return None

# #         if parsed.tzinfo is None:
# #             parsed = parsed.replace(
# #                 tzinfo=timezone.utc
# #             )

# #         return parsed.astimezone(
# #             timezone.utc
# #         )

# #     # ========================================================
# #     # EVENT TIME
# #     # ========================================================

# #     @classmethod
# #     def _get_event_time(
# #         cls,
# #         event: dict,
# #     ) -> datetime:
# #         """
# #         Prefer frame_timestamp because it represents when
# #         the observation actually happened.

# #         Fall back to the canonical event timestamp.
# #         """

# #         data = event.get(
# #             "data"
# #         )

# #         if isinstance(data, dict):

# #             frame_timestamp = (
# #                 cls._parse_timestamp(
# #                     data.get(
# #                         "frame_timestamp"
# #                     )
# #                 )
# #             )

# #             if frame_timestamp is not None:
# #                 return frame_timestamp

# #         event_timestamp = (
# #             cls._parse_timestamp(
# #                 event.get(
# #                     "timestamp"
# #                 )
# #             )
# #         )

# #         if event_timestamp is not None:
# #             return event_timestamp

# #         # Canonical events should always contain a valid
# #         # timestamp. This is defensive only.
# #         return datetime.now(
# #             timezone.utc
# #         )

# #     # ========================================================
# #     # CAMERA ID
# #     # ========================================================

# #     @staticmethod
# #     def _extract_camera_id(
# #         event: dict,
# #     ) -> Optional[str]:

# #         camera = event.get(
# #             "camera"
# #         )

# #         if not isinstance(
# #             camera,
# #             dict,
# #         ):
# #             return None

# #         camera_id = camera.get(
# #             "camera_id"
# #         )

# #         if not isinstance(
# #             camera_id,
# #             str,
# #         ):
# #             return None

# #         camera_id = camera_id.strip()

# #         if not camera_id:
# #             return None

# #         return camera_id

# #     # ========================================================
# #     # POINT INSIDE RESTRICTED ZONE
# #     # ========================================================

# #     @staticmethod
# #     def point_inside_zone(
# #         x: float,
# #         y: float,
# #     ) -> bool:

# #         return (
# #             ZONE_X1 <= x <= ZONE_X2
# #             and
# #             ZONE_Y1 <= y <= ZONE_Y2
# #         )

# #     # ========================================================
# #     # BUILD AND EMIT INTRUSION EVENT
# #     # ========================================================

# #     async def emit_intrusion_event(
# #         self,
# #         tracking_event: dict,
# #         track: dict,
# #         redis_source_id: str,
# #     ) -> str:
# #         """
# #         Build and publish a canonical intrusion.detected
# #         event.
# #         """

# #         camera_id = self._extract_camera_id(
# #             tracking_event
# #         )

# #         if camera_id is None:
# #             raise ValueError(
# #                 "Cannot emit intrusion event without "
# #                 "a valid camera_id."
# #             )

# #         source_event_id = tracking_event.get(
# #             "event_id"
# #         )

# #         if not isinstance(
# #             source_event_id,
# #             str,
# #         ):
# #             raise ValueError(
# #                 "Tracking event is missing event_id."
# #             )

# #         data = tracking_event.get(
# #             "data"
# #         )

# #         if not isinstance(
# #             data,
# #             dict,
# #         ):
# #             raise ValueError(
# #                 "Tracking event data must be an object."
# #             )

# #         track_id = track.get(
# #             "track_id"
# #         )

# #         if track_id is None:
# #             raise ValueError(
# #                 "Track is missing track_id."
# #             )

# #         bbox = track.get(
# #             "bbox",
# #             [],
# #         )

# #         center = track.get(
# #             "center",
# #             [],
# #         )

# #         frame_id = data.get(
# #             "frame_id"
# #         )

# #         frame_timestamp = data.get(
# #             "frame_timestamp"
# #         )

# #         # ----------------------------------------------------
# #         # Context
# #         # ----------------------------------------------------

# #         context = tracking_event.get(
# #             "context",
# #             {},
# #         )

# #         if not isinstance(
# #             context,
# #             dict,
# #         ):
# #             context = {}

# #         mode = context.get(
# #             "mode",
# #             "live",
# #         )

# #         trace_id = context.get(
# #             "trace_id"
# #         )

# #         correlation_id = context.get(
# #             "correlation_id"
# #         )

# #         incident_id = context.get(
# #             "incident_id"
# #         )

# #         # ----------------------------------------------------
# #         # Source timestamp
# #         # ----------------------------------------------------

# #         timestamp = self._get_event_time(
# #             tracking_event
# #         )

# #         # ----------------------------------------------------
# #         # Track information
# #         # ----------------------------------------------------

# #         track_data = {
# #             "track_id": track_id,
# #             "bbox": bbox,
# #             "center": center,
# #         }

# #         optional_track_fields = (
# #             "age",
# #             "match_distance",
# #             "detection_id",
# #             "confidence",
# #         )

# #         for field_name in optional_track_fields:

# #             if field_name in track:

# #                 track_data[field_name] = (
# #                     track[field_name]
# #                 )

# #         # ----------------------------------------------------
# #         # Source information
# #         # ----------------------------------------------------

# #         source = tracking_event.get(
# #             "source",
# #             {},
# #         )

# #         if not isinstance(
# #             source,
# #             dict,
# #         ):
# #             source = {}

# #         # ----------------------------------------------------
# #         # Create canonical event.
# #         # ----------------------------------------------------

# #         event = create_event(
# #             event_type="intrusion.detected",
# #             agent_id=self.agent_id,
# #             instance_id=self.instance_id,
# #             hostname=self.hostname,
# #             camera_id=camera_id,
# #             mode=mode,
# #             trace_id=trace_id,
# #             correlation_id=correlation_id,
# #             incident_id=incident_id,
# #             timestamp=timestamp,
# #             data={
# #                 "track_id": track_id,

# #                 "frame_id": frame_id,

# #                 "frame_timestamp": (
# #                     frame_timestamp
# #                 ),

# #                 "severity": (
# #                     SECURITY_SEVERITY
# #                 ),

# #                 "zone": {
# #                     "x1": ZONE_X1,
# #                     "y1": ZONE_Y1,
# #                     "x2": ZONE_X2,
# #                     "y2": ZONE_Y2,
# #                 },

# #                 "position": {
# #                     "x": (
# #                         center[0]
# #                         if isinstance(
# #                             center,
# #                             (list, tuple),
# #                         )
# #                         and len(center) == 2
# #                         else None
# #                     ),

# #                     "y": (
# #                         center[1]
# #                         if isinstance(
# #                             center,
# #                             (list, tuple),
# #                         )
# #                         and len(center) == 2
# #                         else None
# #                     ),
# #                 },

# #                 "track": track_data,

# #                 "behavior": (
# #                     "restricted_zone_intrusion"
# #                 ),

# #                 "message": (
# #                     "Person entered restricted zone "
# #                     f"on camera {camera_id}."
# #                 ),

# #                 # ------------------------------------------------
# #                 # Event lineage
# #                 # ------------------------------------------------

# #                 "source_event_id": (
# #                     source_event_id
# #                 ),

# #                 "source_redis_id": (
# #                     redis_source_id
# #                 ),

# #                 "source_event_type": (
# #                     tracking_event.get(
# #                         "event_type"
# #                     )
# #                 ),

# #                 "source_agent_id": (
# #                     source.get(
# #                         "agent_id"
# #                     )
# #                 ),

# #                 "source_instance_id": (
# #                     source.get(
# #                         "instance_id"
# #                     )
# #                 ),
# #             },
# #         )

# #         # ----------------------------------------------------
# #         # Validate before publishing.
# #         # ----------------------------------------------------

# #         if not validate_event(
# #             event
# #         ):
# #             raise ValueError(
# #                 "Generated intrusion event failed "
# #                 "canonical event validation."
# #             )

# #         # ----------------------------------------------------
# #         # Publish.
# #         # ----------------------------------------------------

# #         redis_id = await self.publish(
# #             OUTPUT_STREAM,
# #             event,
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"INTRUSION DETECTED | "
# #             f"Camera={camera_id} | "
# #             f"Track={track_id} | "
# #             f"Severity={SECURITY_SEVERITY} | "
# #             f"Redis={redis_id}"
# #         )

# #         return redis_id

# #     # ========================================================
# #     # PROCESS TRACKING EVENT
# #     # ========================================================

# #     async def process_tracking_event(
# #         self,
# #         event: dict,
# #         redis_source_id: str,
# #     ) -> None:

# #         # ----------------------------------------------------
# #         # Only person.tracked events are relevant.
# #         # ----------------------------------------------------

# #         if event.get(
# #             "event_type"
# #         ) != "person.tracked":
# #             return

# #         # ----------------------------------------------------
# #         # Validate source event.
# #         # ----------------------------------------------------

# #         if not validate_event(
# #             event
# #         ):
# #             raise ValueError(
# #                 "Received person.tracked event "
# #                 "failed canonical validation."
# #             )

# #         # ----------------------------------------------------
# #         # Camera.
# #         # ----------------------------------------------------

# #         camera_id = self._extract_camera_id(
# #             event
# #         )

# #         if camera_id is None:

# #             print(
# #                 f"[{self.agent_id}] "
# #                 f"Ignoring person.tracked event "
# #                 f"with invalid camera_id | "
# #                 f"Redis={redis_source_id}"
# #             )

# #             return

# #         # ----------------------------------------------------
# #         # Data.
# #         # ----------------------------------------------------

# #         data = event.get(
# #             "data"
# #         )

# #         if not isinstance(
# #             data,
# #             dict,
# #         ):

# #             print(
# #                 f"[{self.agent_id}] "
# #                 f"Ignoring invalid data | "
# #                 f"Camera={camera_id}"
# #             )

# #             return

# #         tracks = data.get(
# #             "tracks",
# #             [],
# #         )

# #         if not isinstance(
# #             tracks,
# #             list,
# #         ):

# #             print(
# #                 f"[{self.agent_id}] "
# #                 f"Ignoring invalid tracks | "
# #                 f"Camera={camera_id}"
# #             )

# #             return

# #         # ----------------------------------------------------
# #         # Camera-specific state.
# #         # ----------------------------------------------------

# #         if camera_id not in self.alerted_tracks:

# #             self.alerted_tracks[
# #                 camera_id
# #             ] = set()

# #         camera_alerted_tracks = (
# #             self.alerted_tracks[
# #                 camera_id
# #             ]
# #         )

# #         # ----------------------------------------------------
# #         # Tracks currently inside zone.
# #         # ----------------------------------------------------

# #         currently_inside: set[str] = set()

# #         # ----------------------------------------------------
# #         # Process every tracked person.
# #         # ----------------------------------------------------

# #         for track in tracks:

# #             if not isinstance(
# #                 track,
# #                 dict,
# #             ):
# #                 continue

# #             track_id = track.get(
# #                 "track_id"
# #             )

# #             if track_id is None:
# #                 continue

# #             # Normalize the track ID for internal state.
# #             track_id = str(
# #                 track_id
# #             ).strip()

# #             if not track_id:
# #                 continue

# #             # ------------------------------------------------
# #             # Center.
# #             # ------------------------------------------------

# #             center = track.get(
# #                 "center"
# #             )

# #             if (
# #                 not isinstance(
# #                     center,
# #                     (list, tuple),
# #                 )
# #                 or len(center) != 2
# #             ):
# #                 continue

# #             try:

# #                 center_x = float(
# #                     center[0]
# #                 )

# #                 center_y = float(
# #                     center[1]
# #                 )

# #             except (
# #                 TypeError,
# #                 ValueError,
# #             ):

# #                 continue

# #             # ------------------------------------------------
# #             # Reject NaN / infinity.
# #             # ------------------------------------------------

# #             if (
# #                 center_x != center_x
# #                 or center_y != center_y
# #                 or center_x in (
# #                     float("inf"),
# #                     float("-inf"),
# #                 )
# #                 or center_y in (
# #                     float("inf"),
# #                     float("-inf"),
# #                 )
# #             ):
# #                 continue

# #             # ------------------------------------------------
# #             # Zone check.
# #             # ------------------------------------------------

# #             inside = self.point_inside_zone(
# #                 center_x,
# #                 center_y,
# #             )

# #             if not inside:
# #                 continue

# #             currently_inside.add(
# #                 track_id
# #             )

# #             # ------------------------------------------------
# #             # Generate only one intrusion event while inside.
# #             # ------------------------------------------------

# #             if track_id not in camera_alerted_tracks:

# #                 await self.emit_intrusion_event(
# #                     tracking_event=event,
# #                     track=track,
# #                     redis_source_id=redis_source_id,
# #                 )

# #                 # IMPORTANT:
# #                 # Mark as alerted only after successful
# #                 # publication.
# #                 camera_alerted_tracks.add(
# #                     track_id
# #                 )

# #                 print(
# #                     f"[{self.agent_id}] "
# #                     f"Security zone entered | "
# #                     f"Camera={camera_id} | "
# #                     f"Track={track_id} | "
# #                     f"Center=("
# #                     f"{center_x:.1f}, "
# #                     f"{center_y:.1f})"
# #                 )

# #         # ----------------------------------------------------
# #         # Remove tracks that left the zone.
# #         #
# #         # This allows re-entry to trigger another event.
# #         # ----------------------------------------------------

# #         tracks_to_remove = (
# #             camera_alerted_tracks
# #             - currently_inside
# #         )

# #         for track_id in tracks_to_remove:

# #             camera_alerted_tracks.discard(
# #                 track_id
# #             )

# #             print(
# #                 f"[{self.agent_id}] "
# #                 f"Security zone exited | "
# #                 f"Camera={camera_id} | "
# #                 f"Track={track_id}"
# #             )

# #         # ----------------------------------------------------
# #         # Remove empty camera state.
# #         # ----------------------------------------------------

# #         if not camera_alerted_tracks:

# #             self.alerted_tracks.pop(
# #                 camera_id,
# #                 None,
# #             )

# #     # ========================================================
# #     # MAIN PROCESSING LOOP
# #     # ========================================================

# #     async def run(self):

# #         if not self.redis_client:
# #             raise RuntimeError(
# #                 "Redis client is not initialized."
# #             )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Security processing loop started."
# #         )

# #         while self.running:

# #             # ------------------------------------------------
# #             # Read from Redis.
# #             # ------------------------------------------------

# #             try:

# #                 messages = (
# #                     await self.redis_client.xreadgroup(
# #                         groupname=GROUP_NAME,
# #                         consumername=(
# #                             self.consumer_name
# #                         ),
# #                         streams={
# #                             INPUT_STREAM: ">"
# #                         },
# #                         count=10,
# #                         block=5000,
# #                     )
# #                 )

# #             except Exception as exc:

# #                 print(
# #                     f"[{self.agent_id}] "
# #                     f"Redis read error: "
# #                     f"{type(exc).__name__}: "
# #                     f"{exc}"
# #                 )

# #                 await self.sleep(
# #                     2
# #                 )

# #                 continue

# #             if not messages:
# #                 continue

# #             # ------------------------------------------------
# #             # Process each Redis message independently.
# #             # ------------------------------------------------

# #             for (
# #                 stream_name,
# #                 stream_messages,
# #             ) in messages:

# #                 for (
# #                     redis_id,
# #                     fields,
# #                 ) in stream_messages:

# #                     try:

# #                         # ------------------------------------
# #                         # Validate Redis fields.
# #                         # ------------------------------------

# #                         if not isinstance(
# #                             fields,
# #                             dict,
# #                         ):

# #                             print(
# #                                 f"[{self.agent_id}] "
# #                                 f"Invalid Redis fields | "
# #                                 f"Redis={redis_id}"
# #                             )

# #                             await self.redis_client.xack(
# #                                 INPUT_STREAM,
# #                                 GROUP_NAME,
# #                                 redis_id,
# #                             )

# #                             continue

# #                         # ------------------------------------
# #                         # Extract event.
# #                         # ------------------------------------

# #                         raw_event = fields.get(
# #                             "event"
# #                         )

# #                         if not raw_event:

# #                             print(
# #                                 f"[{self.agent_id}] "
# #                                 f"Missing event payload | "
# #                                 f"Redis={redis_id}"
# #                             )

# #                             await self.redis_client.xack(
# #                                 INPUT_STREAM,
# #                                 GROUP_NAME,
# #                                 redis_id,
# #                             )

# #                             continue

# #                         # ------------------------------------
# #                         # Parse JSON.
# #                         # ------------------------------------

# #                         event = json.loads(
# #                             raw_event
# #                         )

# #                         if not isinstance(
# #                             event,
# #                             dict,
# #                         ):

# #                             raise ValueError(
# #                                 "Event payload must "
# #                                 "decode to an object."
# #                             )

# #                         # ------------------------------------
# #                         # Extract camera ID safely for logging.
# #                         # ------------------------------------

# #                         received_camera_id = (
# #                             self._extract_camera_id(
# #                                 event
# #                             )
# #                         )

# #                         print(
# #                             f"[{self.agent_id}] "
# #                             f"Security received | "
# #                             f"Type="
# #                             f"{event.get('event_type')} | "
# #                             f"Camera="
# #                             f"{received_camera_id} | "
# #                             f"Redis={redis_id}"
# #                         )

# #                         # ------------------------------------
# #                         # Process event.
# #                         # ------------------------------------

# #                         await self.process_tracking_event(
# #                             event=event,
# #                             redis_source_id=redis_id,
# #                         )

# #                         # ------------------------------------
# #                         # ACK only after successful processing.
# #                         # ------------------------------------

# #                         await self.redis_client.xack(
# #                             INPUT_STREAM,
# #                             GROUP_NAME,
# #                             redis_id,
# #                         )

# #                     except json.JSONDecodeError as exc:

# #                         # ------------------------------------
# #                         # Malformed JSON is a poison message.
# #                         # ------------------------------------

# #                         print(
# #                             f"[{self.agent_id}] "
# #                             f"Invalid JSON | "
# #                             f"Redis={redis_id} | "
# #                             f"Error={exc}"
# #                         )

# #                         await self.redis_client.xack(
# #                             INPUT_STREAM,
# #                             GROUP_NAME,
# #                             redis_id,
# #                         )

# #                     except Exception as exc:

# #                         # ------------------------------------
# #                         # IMPORTANT:
# #                         #
# #                         # Unexpected processing failures are
# #                         # NOT ACKed.
# #                         #
# #                         # Redis keeps the message pending so
# #                         # the reliability layer can reclaim it.
# #                         #
# #                         # The failure is isolated to this
# #                         # message.
# #                         # ------------------------------------

# #                         print(
# #                             f"[{self.agent_id}] "
# #                             f"ERROR processing "
# #                             f"{redis_id} | "
# #                             f"{type(exc).__name__}: "
# #                             f"{exc}"
# #                         )

# #                         continue


# # # ============================================================
# # # ENTRY POINT
# # # ============================================================

# # if __name__ == "__main__":

# #     agent = SecurityAgent()

# #     try:

# #         import asyncio

# #         asyncio.run(
# #             agent.run_forever()
# #         )

# #     except KeyboardInterrupt:

# #         print(
# #             "\nSecurity Agent interrupted."
# #         )




















# """
# Security Agent

# Consumes canonical `person.tracked` events and detects restricted-zone
# intrusions.

# Pipeline:

#     events.tracking
#           |
#           v
#     SecurityAgent
#           |
#           v
#     events.behavior
#           |
#           +--> intrusion.detected

# Architecture:

# - Detection/tracking remains independent from camera policy.
# - Camera-specific security configuration comes from the centralized
#   Camera Registry / Camera Policy layer.
# - Stateful security state is partitioned by camera.
# - Track disappearance uses a grace period before considering a person
#   to have exited a zone.
# - Historical event time is preserved.
# - Canonical event lineage/context is preserved.
# - Redis messages are isolated individually.
# - Messages are ACKed only after successful processing.
# """

# from __future__ import annotations

# import json
# import math
# import os
# import uuid
# from datetime import datetime, timezone
# from typing import Any, Optional

# from shared.agent.base_agent import BaseAgent
# from shared.schemas.event_schema import create_event, validate_event


# # ============================================================
# # CONFIG
# # ============================================================

# INPUT_STREAM = os.getenv(
#     "SECURITY_INPUT_STREAM",
#     "events.tracking",
# )

# OUTPUT_STREAM = os.getenv(
#     "SECURITY_OUTPUT_STREAM",
#     "events.behavior",
# )

# GROUP_NAME = os.getenv(
#     "SECURITY_GROUP",
#     "security-workers",
# )

# DEFAULT_AGENT_ID = os.getenv(
#     "SECURITY_AGENT_ID",
#     "security-01",
# )

# CONSUMER_NAME_PREFIX = os.getenv(
#     "SECURITY_CONSUMER_PREFIX",
#     DEFAULT_AGENT_ID,
# )

# # ------------------------------------------------------------
# # Track-loss protection.
# #
# # A tracked person may disappear temporarily because of:
# #
# # - detector dropout
# # - occlusion
# # - frame loss
# # - tracker recovery
# #
# # Do not immediately interpret one missing observation as
# # a zone exit.
# # ------------------------------------------------------------

# TRACK_LOSS_GRACE_SECONDS = float(
#     os.getenv(
#         "SECURITY_TRACK_LOSS_GRACE_SECONDS",
#         "1.5",
#     )
# )

# if (
#     not math.isfinite(TRACK_LOSS_GRACE_SECONDS)
#     or TRACK_LOSS_GRACE_SECONDS < 0.0
# ):
#     raise ValueError(
#         "SECURITY_TRACK_LOSS_GRACE_SECONDS must be "
#         "a finite number >= 0."
#     )


# # ============================================================
# # OPTIONAL LEGACY GLOBAL CONFIGURATION
# # ============================================================
# #
# # These values are retained only as a backwards-compatible
# # fallback while the centralized CameraPolicy model is being
# # upgraded with restricted-zone configuration.
# #
# # Camera-specific policy takes precedence.
# #
# # Do NOT add camera_id-specific conditionals here.
# # ============================================================

# def _read_float_env(
#     name: str,
#     default: str,
# ) -> float:
#     raw_value = os.getenv(name, default)

#     try:
#         value = float(raw_value)
#     except (TypeError, ValueError) as exc:
#         raise ValueError(
#             f"{name} must be a valid number. "
#             f"Received: {raw_value!r}"
#         ) from exc

#     if not math.isfinite(value):
#         raise ValueError(
#             f"{name} must be finite."
#         )

#     return value


# LEGACY_ZONE_X1 = _read_float_env(
#     "ZONE_X1",
#     "50",
# )

# LEGACY_ZONE_Y1 = _read_float_env(
#     "ZONE_Y1",
#     "50",
# )

# LEGACY_ZONE_X2 = _read_float_env(
#     "ZONE_X2",
#     "700",
# )

# LEGACY_ZONE_Y2 = _read_float_env(
#     "ZONE_Y2",
#     "450",
# )

# LEGACY_SECURITY_SEVERITY = os.getenv(
#     "SECURITY_SEVERITY",
#     "high",
# ).strip().lower()

# VALID_SEVERITIES = {
#     "low",
#     "medium",
#     "high",
#     "critical",
# }


# # ============================================================
# # SECURITY AGENT
# # ============================================================

# class SecurityAgent(BaseAgent):

#     def __init__(
#         self,
#         agent_id: Optional[str] = None,
#     ):
#         super().__init__(
#             agent_id=agent_id or DEFAULT_AGENT_ID,
#         )

#         self._validate_configuration()

#         # ----------------------------------------------------
#         # Camera registry / policy provider.
#         #
#         # Import lazily so the agent remains importable even
#         # when the backend package is unavailable during
#         # isolated unit tests.
#         # ----------------------------------------------------

#         self.camera_registry = None

#         try:
#             from backend.app.cameras.registry import (
#                 CameraRegistry,
#             )

#             self.camera_registry = (
#                 CameraRegistry.from_environment()
#             )

#             print(
#                 f"[{self.agent_id}] "
#                 f"Camera policy registry loaded | "
#                 f"Cameras={self.camera_registry.count()}"
#             )

#         except Exception as exc:
#             # The security worker must remain isolated.
#             #
#             # Legacy environment configuration can still be
#             # used temporarily until CameraPolicy is upgraded.
#             print(
#                 f"[{self.agent_id}] "
#                 f"Camera policy registry unavailable: "
#                 f"{type(exc).__name__}: {exc}"
#             )

#         # ----------------------------------------------------
#         # Camera-specific alert state.
#         #
#         # {
#         #     "CAM01": {"1", "4"},
#         #     "CAM02": {"2"}
#         # }
#         #
#         # A track is kept here only while it is considered
#         # inside the restricted zone.
#         # ----------------------------------------------------

#         self.alerted_tracks: dict[str, set[str]] = {}

#         # ----------------------------------------------------
#         # Last observation time for each camera/track.
#         #
#         # Used to prevent a single tracker dropout from
#         # immediately creating an exit + re-entry sequence.
#         # ----------------------------------------------------

#         self.track_last_seen: dict[
#             str,
#             dict[str, datetime],
#         ] = {}

#         # ----------------------------------------------------
#         # Last processed event timestamp for each camera.
#         #
#         # Prevents older historical/out-of-order tracking
#         # events from corrupting state.
#         # ----------------------------------------------------

#         self.last_event_timestamp: dict[
#             str,
#             datetime,
#         ] = {}

#         # ----------------------------------------------------
#         # Unique Redis consumer name.
#         # ----------------------------------------------------

#         self.consumer_name = (
#             f"{CONSUMER_NAME_PREFIX}-"
#             f"{uuid.uuid4().hex[:8]}"
#         )

#     # ========================================================
#     # CONFIGURATION VALIDATION
#     # ========================================================

#     @staticmethod
#     def _validate_configuration() -> None:

#         if LEGACY_ZONE_X1 >= LEGACY_ZONE_X2:
#             raise ValueError(
#                 "Invalid legacy security zone: "
#                 "ZONE_X1 must be smaller than ZONE_X2."
#             )

#         if LEGACY_ZONE_Y1 >= LEGACY_ZONE_Y2:
#             raise ValueError(
#                 "Invalid legacy security zone: "
#                 "ZONE_Y1 must be smaller than ZONE_Y2."
#             )

#         if (
#             LEGACY_SECURITY_SEVERITY
#             not in VALID_SEVERITIES
#         ):
#             raise ValueError(
#                 "SECURITY_SEVERITY must be one of: "
#                 f"{sorted(VALID_SEVERITIES)}. "
#                 f"Received: "
#                 f"{LEGACY_SECURITY_SEVERITY!r}"
#             )

#     # ========================================================
#     # STARTUP
#     # ========================================================

#     async def on_start(self):

#         await self.ensure_consumer_group()

#         print(
#             f"[{self.agent_id}] "
#             f"Security agent ready."
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
#             f"Input: {INPUT_STREAM}"
#         )

#         print(
#             f"[{self.agent_id}] "
#             f"Output: {OUTPUT_STREAM}"
#         )

#         print(
#             f"[{self.agent_id}] "
#             f"Consumer: {self.consumer_name}"
#         )

#         print(
#             f"[{self.agent_id}] "
#             f"Track-loss grace: "
#             f"{TRACK_LOSS_GRACE_SECONDS}s"
#         )

#         print(
#             f"[{self.agent_id}] "
#             f"Camera-specific policy mode enabled."
#         )

#     # ========================================================
#     # SHUTDOWN
#     # ========================================================

#     async def on_stop(self):

#         self.alerted_tracks.clear()
#         self.track_last_seen.clear()
#         self.last_event_timestamp.clear()

#         print(
#             f"[{self.agent_id}] "
#             f"Security state cleared."
#         )

#     # ========================================================
#     # REDIS CONSUMER GROUP
#     # ========================================================

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

#     # ========================================================
#     # TIMESTAMP PARSER
#     # ========================================================

#     @staticmethod
#     def _parse_timestamp(
#         value: Any,
#     ) -> Optional[datetime]:

#         if not isinstance(value, str):
#             return None

#         value = value.strip()

#         if not value:
#             return None

#         try:

#             parsed = datetime.fromisoformat(
#                 value.replace(
#                     "Z",
#                     "+00:00",
#                 )
#             )

#         except ValueError:
#             return None

#         if parsed.tzinfo is None:

#             parsed = parsed.replace(
#                 tzinfo=timezone.utc
#             )

#         return parsed.astimezone(
#             timezone.utc
#         )

#     # ========================================================
#     # EVENT TIME
#     # ========================================================

#     @classmethod
#     def _get_event_time(
#         cls,
#         event: dict,
#     ) -> datetime:

#         data = event.get(
#             "data"
#         )

#         if isinstance(data, dict):

#             frame_timestamp = (
#                 cls._parse_timestamp(
#                     data.get(
#                         "frame_timestamp"
#                     )
#                 )
#             )

#             if frame_timestamp is not None:
#                 return frame_timestamp

#         event_timestamp = (
#             cls._parse_timestamp(
#                 event.get(
#                     "timestamp"
#                 )
#             )
#         )

#         if event_timestamp is not None:
#             return event_timestamp

#         return datetime.now(
#             timezone.utc
#         )

#     # ========================================================
#     # CAMERA ID
#     # ========================================================

#     @staticmethod
#     def _extract_camera_id(
#         event: dict,
#     ) -> Optional[str]:

#         camera = event.get(
#             "camera"
#         )

#         if not isinstance(
#             camera,
#             dict,
#         ):
#             return None

#         camera_id = camera.get(
#             "camera_id"
#         )

#         if not isinstance(
#             camera_id,
#             str,
#         ):
#             return None

#         camera_id = camera_id.strip()

#         if not camera_id:
#             return None

#         return camera_id

#     # ========================================================
#     # CAMERA POLICY
#     # ========================================================

#     def _get_camera_policy(
#         self,
#         camera_id: str,
#     ) -> Optional[Any]:

#         if self.camera_registry is None:
#             return None

#         try:
#             return self.camera_registry.get(
#                 camera_id
#             )
#         except Exception as exc:

#             print(
#                 f"[{self.agent_id}] "
#                 f"Camera policy lookup failed | "
#                 f"Camera={camera_id} | "
#                 f"{type(exc).__name__}: {exc}"
#             )

#             return None

#     # ========================================================
#     # SECURITY ZONE
#     # ========================================================

#     def _get_security_zone(
#         self,
#         camera_id: str,
#     ) -> tuple[float, float, float, float]:

#         camera_config = (
#             self._get_camera_policy(
#                 camera_id
#             )
#         )

#         # ----------------------------------------------------
#         # Future/current CameraPolicy restricted_zone support.
#         #
#         # Expected:
#         #
#         # restricted_zone = {
#         #     "x1": ...,
#         #     "y1": ...,
#         #     "x2": ...,
#         #     "y2": ...
#         # }
#         #
#         # Or a compatible object exposing these attributes.
#         # ----------------------------------------------------

#         if camera_config is not None:

#             policy = getattr(
#                 camera_config,
#                 "policy",
#                 None,
#             )

#             if policy is not None:

#                 zone = getattr(
#                     policy,
#                     "restricted_zone",
#                     None,
#                 )

#                 if zone is not None:

#                     parsed = self._normalize_zone(
#                         zone
#                     )

#                     if parsed is not None:
#                         return parsed

#         # ----------------------------------------------------
#         # Backwards-compatible fallback.
#         #
#         # This fallback exists only while all cameras have not
#         # yet migrated to explicit camera policies.
#         # ----------------------------------------------------

#         return (
#             LEGACY_ZONE_X1,
#             LEGACY_ZONE_Y1,
#             LEGACY_ZONE_X2,
#             LEGACY_ZONE_Y2,
#         )

#     # ========================================================
#     # NORMALIZE ZONE
#     # ========================================================

#     @staticmethod
#     def _normalize_zone(
#         zone: Any,
#     ) -> Optional[
#         tuple[float, float, float, float]
#     ]:

#         try:

#             if isinstance(
#                 zone,
#                 dict,
#             ):

#                 x1 = float(
#                     zone["x1"]
#                 )
#                 y1 = float(
#                     zone["y1"]
#                 )
#                 x2 = float(
#                     zone["x2"]
#                 )
#                 y2 = float(
#                     zone["y2"]
#                 )

#             else:

#                 x1 = float(
#                     getattr(zone, "x1")
#                 )
#                 y1 = float(
#                     getattr(zone, "y1")
#                 )
#                 x2 = float(
#                     getattr(zone, "x2")
#                 )
#                 y2 = float(
#                     getattr(zone, "y2")
#                 )

#         except (
#             KeyError,
#             TypeError,
#             ValueError,
#             AttributeError,
#         ):

#             return None

#         if not all(
#             math.isfinite(value)
#             for value in (
#                 x1,
#                 y1,
#                 x2,
#                 y2,
#             )
#         ):
#             return None

#         if x1 >= x2 or y1 >= y2:
#             return None

#         return (
#             x1,
#             y1,
#             x2,
#             y2,
#         )

#     # ========================================================
#     # SECURITY SEVERITY
#     # ========================================================

#     def _get_security_severity(
#         self,
#         camera_id: str,
#     ) -> str:

#         camera_config = (
#             self._get_camera_policy(
#                 camera_id
#             )
#         )

#         if camera_config is not None:

#             policy = getattr(
#                 camera_config,
#                 "policy",
#                 None,
#             )

#             if policy is not None:

#                 severity = getattr(
#                     policy,
#                     "security_severity",
#                     None,
#                 )

#                 if isinstance(
#                     severity,
#                     str,
#                 ):

#                     severity = (
#                         severity.strip()
#                         .lower()
#                     )

#                     if (
#                         severity
#                         in VALID_SEVERITIES
#                     ):
#                         return severity

#         return LEGACY_SECURITY_SEVERITY

#     # ========================================================
#     # POINT INSIDE RESTRICTED ZONE
#     # ========================================================

#     def point_inside_zone(
#         self,
#         camera_id: str,
#         x: float,
#         y: float,
#     ) -> bool:

#         (
#             x1,
#             y1,
#             x2,
#             y2,
#         ) = self._get_security_zone(
#             camera_id
#         )

#         return (
#             x1 <= x <= x2
#             and
#             y1 <= y <= y2
#         )

#     # ========================================================
#     # REMOVE STALE TRACKS
#     # ========================================================

#     def _cleanup_stale_tracks(
#         self,
#         camera_id: str,
#         event_time: datetime,
#     ) -> None:

#         camera_last_seen = (
#             self.track_last_seen.get(
#                 camera_id
#             )
#         )

#         if not camera_last_seen:
#             return

#         camera_alerted = (
#             self.alerted_tracks.get(
#                 camera_id,
#                 set(),
#             )
#         )

#         stale_tracks = []

#         for track_id, last_seen in (
#             camera_last_seen.items()
#         ):

#             age = (
#                 event_time - last_seen
#             ).total_seconds()

#             if age < 0:
#                 continue

#             if (
#                 age
#                 > TRACK_LOSS_GRACE_SECONDS
#             ):
#                 stale_tracks.append(
#                     track_id
#                 )

#         for track_id in stale_tracks:

#             camera_last_seen.pop(
#                 track_id,
#                 None,
#             )

#             if track_id in camera_alerted:

#                 camera_alerted.discard(
#                     track_id
#                 )

#                 print(
#                     f"[{self.agent_id}] "
#                     f"Security track expired | "
#                     f"Camera={camera_id} | "
#                     f"Track={track_id}"
#                 )

#         if not camera_last_seen:

#             self.track_last_seen.pop(
#                 camera_id,
#                 None,
#             )

#         if not camera_alerted:

#             self.alerted_tracks.pop(
#                 camera_id,
#                 None,
#             )

#     # ========================================================
#     # BUILD AND EMIT INTRUSION EVENT
#     # ========================================================

#     async def emit_intrusion_event(
#         self,
#         tracking_event: dict,
#         track: dict,
#         redis_source_id: str,
#     ) -> str:

#         camera_id = (
#             self._extract_camera_id(
#                 tracking_event
#             )
#         )

#         if camera_id is None:

#             raise ValueError(
#                 "Cannot emit intrusion event "
#                 "without a valid camera_id."
#             )

#         source_event_id = (
#             tracking_event.get(
#                 "event_id"
#             )
#         )

#         if not isinstance(
#             source_event_id,
#             str,
#         ):

#             raise ValueError(
#                 "Tracking event is missing event_id."
#             )

#         data = tracking_event.get(
#             "data"
#         )

#         if not isinstance(
#             data,
#             dict,
#         ):

#             raise ValueError(
#                 "Tracking event data must be an object."
#             )

#         track_id = track.get(
#             "track_id"
#         )

#         if track_id is None:

#             raise ValueError(
#                 "Track is missing track_id."
#             )

#         bbox = track.get(
#             "bbox",
#             [],
#         )

#         center = track.get(
#             "center",
#             [],
#         )

#         frame_id = data.get(
#             "frame_id"
#         )

#         frame_timestamp = data.get(
#             "frame_timestamp"
#         )

#         context = tracking_event.get(
#             "context",
#             {},
#         )

#         if not isinstance(
#             context,
#             dict,
#         ):
#             context = {}

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

#         timestamp = (
#             self._get_event_time(
#                 tracking_event
#             )
#         )

#         (
#             zone_x1,
#             zone_y1,
#             zone_x2,
#             zone_y2,
#         ) = self._get_security_zone(
#             camera_id
#         )

#         severity = (
#             self._get_security_severity(
#                 camera_id
#             )
#         )

#         track_data = {
#             "track_id": track_id,
#             "bbox": bbox,
#             "center": center,
#         }

#         optional_track_fields = (
#             "age",
#             "match_distance",
#             "detection_id",
#             "confidence",
#         )

#         for field_name in (
#             optional_track_fields
#         ):

#             if field_name in track:

#                 track_data[field_name] = (
#                     track[field_name]
#                 )

#         source = tracking_event.get(
#             "source",
#             {},
#         )

#         if not isinstance(
#             source,
#             dict,
#         ):
#             source = {}

#         event = create_event(
#             event_type="intrusion.detected",
#             agent_id=self.agent_id,
#             instance_id=self.instance_id,
#             hostname=self.hostname,
#             camera_id=camera_id,
#             mode=mode,
#             trace_id=trace_id,
#             correlation_id=correlation_id,
#             incident_id=incident_id,
#             timestamp=timestamp,
#             data={
#                 "track_id": track_id,

#                 "frame_id": frame_id,

#                 "frame_timestamp": (
#                     frame_timestamp
#                 ),

#                 "severity": severity,

#                 "zone": {
#                     "x1": zone_x1,
#                     "y1": zone_y1,
#                     "x2": zone_x2,
#                     "y2": zone_y2,
#                 },

#                 "position": {
#                     "x": (
#                         center[0]
#                         if isinstance(
#                             center,
#                             (list, tuple),
#                         )
#                         and len(center) == 2
#                         else None
#                     ),

#                     "y": (
#                         center[1]
#                         if isinstance(
#                             center,
#                             (list, tuple),
#                         )
#                         and len(center) == 2
#                         else None
#                     ),
#                 },

#                 "track": track_data,

#                 "behavior": (
#                     "restricted_zone_intrusion"
#                 ),

#                 "message": (
#                     "Person entered restricted "
#                     f"zone on camera {camera_id}."
#                 ),

#                 # Event lineage.
#                 "source_event_id": (
#                     source_event_id
#                 ),

#                 "source_redis_id": (
#                     redis_source_id
#                 ),

#                 "source_event_type": (
#                     tracking_event.get(
#                         "event_type"
#                     )
#                 ),

#                 "source_agent_id": (
#                     source.get(
#                         "agent_id"
#                     )
#                 ),

#                 "source_instance_id": (
#                     source.get(
#                         "instance_id"
#                     )
#                 ),
#             },
#         )

#         if not validate_event(
#             event
#         ):

#             raise ValueError(
#                 "Generated intrusion event failed "
#                 "canonical event validation."
#             )

#         redis_id = await self.publish(
#             OUTPUT_STREAM,
#             event,
#         )

#         print(
#             f"[{self.agent_id}] "
#             f"INTRUSION DETECTED | "
#             f"Camera={camera_id} | "
#             f"Track={track_id} | "
#             f"Severity={severity} | "
#             f"Redis={redis_id}"
#         )

#         return redis_id

#     # ========================================================
#     # PROCESS TRACKING EVENT
#     # ========================================================

#     async def process_tracking_event(
#         self,
#         event: dict,
#         redis_source_id: str,
#     ) -> None:

#         # ----------------------------------------------------
#         # Only person.tracked events are relevant.
#         # ----------------------------------------------------

#         if event.get(
#             "event_type"
#         ) != "person.tracked":

#             return

#         # ----------------------------------------------------
#         # Validate source event.
#         # ----------------------------------------------------

#         if not validate_event(
#             event
#         ):

#             raise ValueError(
#                 "Received person.tracked event "
#                 "failed canonical validation."
#             )

#         # ----------------------------------------------------
#         # Camera.
#         # ----------------------------------------------------

#         camera_id = (
#             self._extract_camera_id(
#                 event
#             )
#         )

#         if camera_id is None:

#             print(
#                 f"[{self.agent_id}] "
#                 f"Ignoring person.tracked event "
#                 f"with invalid camera_id | "
#                 f"Redis={redis_source_id}"
#             )

#             return

#         # ----------------------------------------------------
#         # Event time.
#         # ----------------------------------------------------

#         event_time = (
#             self._get_event_time(
#                 event
#             )
#         )

#         # ----------------------------------------------------
#         # Camera-level ordering protection.
#         # ----------------------------------------------------

#         previous_event_time = (
#             self.last_event_timestamp.get(
#                 camera_id
#             )
#         )

#         if (
#             previous_event_time is not None
#             and event_time < previous_event_time
#         ):

#             print(
#                 f"[{self.agent_id}] "
#                 f"Ignoring out-of-order event | "
#                 f"Camera={camera_id} | "
#                 f"EventTime={event_time.isoformat()} | "
#                 f"LastTime="
#                 f"{previous_event_time.isoformat()} | "
#                 f"Redis={redis_source_id}"
#             )

#             return

#         self.last_event_timestamp[
#             camera_id
#         ] = event_time

#         # ----------------------------------------------------
#         # Data.
#         # ----------------------------------------------------

#         data = event.get(
#             "data"
#         )

#         if not isinstance(
#             data,
#             dict,
#         ):

#             print(
#                 f"[{self.agent_id}] "
#                 f"Ignoring invalid data | "
#                 f"Camera={camera_id}"
#             )

#             return

#         tracks = data.get(
#             "tracks",
#             [],
#         )

#         if not isinstance(
#             tracks,
#             list,
#         ):

#             print(
#                 f"[{self.agent_id}] "
#                 f"Ignoring invalid tracks | "
#                 f"Camera={camera_id}"
#             )

#             return

#         # ----------------------------------------------------
#         # Initialize camera state.
#         # ----------------------------------------------------

#         camera_alerted_tracks = (
#             self.alerted_tracks.setdefault(
#                 camera_id,
#                 set(),
#             )
#         )

#         camera_last_seen = (
#             self.track_last_seen.setdefault(
#                 camera_id,
#                 {},
#             )
#         )

#         currently_inside: set[str] = set()

#         # ----------------------------------------------------
#         # Process current observations.
#         # ----------------------------------------------------

#         for track in tracks:

#             if not isinstance(
#                 track,
#                 dict,
#             ):
#                 continue

#             track_id = track.get(
#                 "track_id"
#             )

#             if track_id is None:
#                 continue

#             track_id = str(
#                 track_id
#             ).strip()

#             if not track_id:
#                 continue

#             center = track.get(
#                 "center"
#             )

#             if (
#                 not isinstance(
#                     center,
#                     (list, tuple),
#                 )
#                 or len(center) != 2
#             ):
#                 continue

#             try:

#                 center_x = float(
#                     center[0]
#                 )

#                 center_y = float(
#                     center[1]
#                 )

#             except (
#                 TypeError,
#                 ValueError,
#             ):
#                 continue

#             if (
#                 not math.isfinite(center_x)
#                 or not math.isfinite(center_y)
#             ):
#                 continue

#             # ------------------------------------------------
#             # Every valid observation refreshes last-seen.
#             # ------------------------------------------------

#             previous_track_time = (
#                 camera_last_seen.get(
#                     track_id
#                 )
#             )

#             if (
#                 previous_track_time is not None
#                 and event_time < previous_track_time
#             ):
#                 continue

#             camera_last_seen[
#                 track_id
#             ] = event_time

#             # ------------------------------------------------
#             # Zone check.
#             # ------------------------------------------------

#             inside = self.point_inside_zone(
#                 camera_id,
#                 center_x,
#                 center_y,
#             )

#             if not inside:
#                 continue

#             currently_inside.add(
#                 track_id
#             )

#             # ------------------------------------------------
#             # Generate only one intrusion event while the
#             # same track remains inside the zone.
#             # ------------------------------------------------

#             if track_id not in camera_alerted_tracks:

#                 await self.emit_intrusion_event(
#                     tracking_event=event,
#                     track=track,
#                     redis_source_id=redis_source_id,
#                 )

#                 # Mark only after successful publication.
#                 camera_alerted_tracks.add(
#                     track_id
#                 )

#                 print(
#                     f"[{self.agent_id}] "
#                     f"Security zone entered | "
#                     f"Camera={camera_id} | "
#                     f"Track={track_id} | "
#                     f"Center=("
#                     f"{center_x:.1f}, "
#                     f"{center_y:.1f})"
#                 )

#         # ----------------------------------------------------
#         # Track-loss cleanup.
#         #
#         # Do NOT immediately clear a track just because it was
#         # absent from one observation.
#         #
#         # This prevents:
#         #
#         # inside → dropout → inside
#         #
#         # from generating duplicate intrusion events.
#         # ----------------------------------------------------

#         self._cleanup_stale_tracks(
#             camera_id=camera_id,
#             event_time=event_time,
#         )

#         # ----------------------------------------------------
#         # Explicit exit detection.
#         #
#         # A track that was observed outside the zone is removed
#         # from alerted state immediately.
#         # ----------------------------------------------------

#         for track in tracks:

#             if not isinstance(
#                 track,
#                 dict,
#             ):
#                 continue

#             track_id = track.get(
#                 "track_id"
#             )

#             if track_id is None:
#                 continue

#             track_id = str(
#                 track_id
#             ).strip()

#             if not track_id:
#                 continue

#             center = track.get(
#                 "center"
#             )

#             if (
#                 not isinstance(
#                     center,
#                     (list, tuple),
#                 )
#                 or len(center) != 2
#             ):
#                 continue

#             try:

#                 center_x = float(
#                     center[0]
#                 )

#                 center_y = float(
#                     center[1]
#                 )

#             except (
#                 TypeError,
#                 ValueError,
#             ):
#                 continue

#             if (
#                 not math.isfinite(center_x)
#                 or not math.isfinite(center_y)
#             ):
#                 continue

#             if self.point_inside_zone(
#                 camera_id,
#                 center_x,
#                 center_y,
#             ):
#                 continue

#             if track_id in camera_alerted_tracks:

#                 camera_alerted_tracks.discard(
#                     track_id
#                 )

#                 print(
#                     f"[{self.agent_id}] "
#                     f"Security zone exited | "
#                     f"Camera={camera_id} | "
#                     f"Track={track_id}"
#                 )

#         # ----------------------------------------------------
#         # Remove empty camera state.
#         # ----------------------------------------------------

#         if not camera_alerted_tracks:

#             self.alerted_tracks.pop(
#                 camera_id,
#                 None,
#             )

#         if not camera_last_seen:

#             self.track_last_seen.pop(
#                 camera_id,
#                 None,
#             )

#     # ========================================================
#     # MAIN PROCESSING LOOP
#     # ========================================================

#     async def run(self):

#         if not self.redis_client:
#             raise RuntimeError(
#                 "Redis client is not initialized."
#             )

#         print(
#             f"[{self.agent_id}] "
#             f"Security processing loop started."
#         )

#         while self.running:

#             # ------------------------------------------------
#             # Read from Redis.
#             # ------------------------------------------------

#             try:

#                 messages = (
#                     await self.redis_client.xreadgroup(
#                         groupname=GROUP_NAME,
#                         consumername=(
#                             self.consumer_name
#                         ),
#                         streams={
#                             INPUT_STREAM: ">"
#                         },
#                         count=10,
#                         block=5000,
#                     )
#                 )

#             except Exception as exc:

#                 print(
#                     f"[{self.agent_id}] "
#                     f"Redis read error: "
#                     f"{type(exc).__name__}: "
#                     f"{exc}"
#                 )

#                 await self.sleep(
#                     2
#                 )

#                 continue

#             if not messages:
#                 continue

#             # ------------------------------------------------
#             # Process each Redis message independently.
#             # ------------------------------------------------

#             for (
#                 stream_name,
#                 stream_messages,
#             ) in messages:

#                 for (
#                     redis_id,
#                     fields,
#                 ) in stream_messages:

#                     try:

#                         # ------------------------------------
#                         # Validate Redis fields.
#                         # ------------------------------------

#                         if not isinstance(
#                             fields,
#                             dict,
#                         ):

#                             print(
#                                 f"[{self.agent_id}] "
#                                 f"Invalid Redis fields | "
#                                 f"Redis={redis_id}"
#                             )

#                             await self.redis_client.xack(
#                                 INPUT_STREAM,
#                                 GROUP_NAME,
#                                 redis_id,
#                             )

#                             continue

#                         # ------------------------------------
#                         # Extract event.
#                         # ------------------------------------

#                         raw_event = fields.get(
#                             "event"
#                         )

#                         if not raw_event:

#                             print(
#                                 f"[{self.agent_id}] "
#                                 f"Missing event payload | "
#                                 f"Redis={redis_id}"
#                             )

#                             await self.redis_client.xack(
#                                 INPUT_STREAM,
#                                 GROUP_NAME,
#                                 redis_id,
#                             )

#                             continue

#                         # ------------------------------------
#                         # Parse JSON.
#                         # ------------------------------------

#                         event = json.loads(
#                             raw_event
#                         )

#                         if not isinstance(
#                             event,
#                             dict,
#                         ):

#                             raise ValueError(
#                                 "Event payload must "
#                                 "decode to an object."
#                             )

#                         # ------------------------------------
#                         # Camera ID for logging.
#                         # ------------------------------------

#                         received_camera_id = (
#                             self._extract_camera_id(
#                                 event
#                             )
#                         )

#                         print(
#                             f"[{self.agent_id}] "
#                             f"Security received | "
#                             f"Type="
#                             f"{event.get('event_type')} | "
#                             f"Camera="
#                             f"{received_camera_id} | "
#                             f"Redis={redis_id}"
#                         )

#                         # ------------------------------------
#                         # Process event.
#                         # ------------------------------------

#                         await self.process_tracking_event(
#                             event=event,
#                             redis_source_id=redis_id,
#                         )

#                         # ------------------------------------
#                         # ACK only after successful processing.
#                         # ------------------------------------

#                         await self.redis_client.xack(
#                             INPUT_STREAM,
#                             GROUP_NAME,
#                             redis_id,
#                         )

#                     except json.JSONDecodeError as exc:

#                         # ------------------------------------
#                         # Malformed JSON is a poison message.
#                         # ------------------------------------

#                         print(
#                             f"[{self.agent_id}] "
#                             f"Invalid JSON | "
#                             f"Redis={redis_id} | "
#                             f"Error={exc}"
#                         )

#                         await self.redis_client.xack(
#                             INPUT_STREAM,
#                             GROUP_NAME,
#                             redis_id,
#                         )

#                     except Exception as exc:

#                         # ------------------------------------
#                         # Unexpected processing failures are
#                         # intentionally NOT ACKed.
#                         #
#                         # Redis keeps the message pending so
#                         # the reliability layer can reclaim it.
#                         #
#                         # Failure is isolated to this message.
#                         # ------------------------------------

#                         print(
#                             f"[{self.agent_id}] "
#                             f"ERROR processing "
#                             f"{redis_id} | "
#                             f"{type(exc).__name__}: "
#                             f"{exc}"
#                         )

#                         continue


# # ============================================================
# # ENTRY POINT
# # ============================================================

# if __name__ == "__main__":

#     agent = SecurityAgent()

#     try:

#         import asyncio

#         asyncio.run(
#             agent.run_forever()
#         )

#     except KeyboardInterrupt:

#         print(
#             "\nSecurity Agent interrupted."
#         )
































"""
Security Agent

Consumes canonical `person.tracked` events and detects restricted-zone
intrusions.

Pipeline:

    events.tracking
          |
          v
    SecurityAgent
          |
          v
    events.behavior
          |
          +--> intrusion.detected

Architecture:

- Detection/tracking remains independent from camera policy.
- Camera-specific security configuration comes from the centralized
  Camera Registry / Camera Policy layer.
- Stateful security state is partitioned by camera.
- Track disappearance uses a grace period before considering a person
  to have exited a zone.
- Historical event time is preserved.
- Canonical event lineage/context is preserved.
- Redis messages are isolated individually.
- Messages are ACKed only after successful processing.
- Security policy failures never silently become security alerts.
- Legacy global-zone configuration is disabled by default and is only
  available through explicit compatibility mode.
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


# ============================================================
# CONFIG
# ============================================================

INPUT_STREAM = os.getenv(
    "SECURITY_INPUT_STREAM",
    "events.tracking",
)

OUTPUT_STREAM = os.getenv(
    "SECURITY_OUTPUT_STREAM",
    "events.behavior",
)

GROUP_NAME = os.getenv(
    "SECURITY_GROUP",
    "security-workers",
)

DEFAULT_AGENT_ID = os.getenv(
    "SECURITY_AGENT_ID",
    "security-01",
)

CONSUMER_NAME_PREFIX = os.getenv(
    "SECURITY_CONSUMER_PREFIX",
    DEFAULT_AGENT_ID,
)


# ------------------------------------------------------------
# Track-loss protection.
#
# A tracked person may disappear temporarily because of:
#
# - detector dropout
# - occlusion
# - frame loss
# - tracker recovery
#
# Do not immediately interpret one missing observation as
# a zone exit.
# ------------------------------------------------------------

TRACK_LOSS_GRACE_SECONDS = float(
    os.getenv(
        "SECURITY_TRACK_LOSS_GRACE_SECONDS",
        "1.5",
    )
)

if (
    not math.isfinite(TRACK_LOSS_GRACE_SECONDS)
    or TRACK_LOSS_GRACE_SECONDS < 0.0
):
    raise ValueError(
        "SECURITY_TRACK_LOSS_GRACE_SECONDS must be "
        "a finite number >= 0."
    )


# ============================================================
# OPTIONAL LEGACY GLOBAL CONFIGURATION
# ============================================================
#
# Legacy global security-zone configuration is retained only
# for backwards compatibility with older tests/deployments.
#
# IMPORTANT:
#
# This is intentionally DISABLED by default.
#
# A camera without an explicit CameraPolicy restricted zone
# must NOT automatically inherit a global security zone.
#
# Enable only temporarily with:
#
# SECURITY_LEGACY_ZONE_FALLBACK_ENABLED=true
#
# ============================================================

SECURITY_LEGACY_ZONE_FALLBACK_ENABLED = (
    os.getenv(
        "SECURITY_LEGACY_ZONE_FALLBACK_ENABLED",
        "false",
    ).strip().lower()
    in {
        "1",
        "true",
        "yes",
        "on",
    }
)


def _read_float_env(
    name: str,
    default: str,
) -> float:
    raw_value = os.getenv(
        name,
        default,
    )

    try:
        value = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{name} must be a valid number. "
            f"Received: {raw_value!r}"
        ) from exc

    if not math.isfinite(value):
        raise ValueError(
            f"{name} must be finite."
        )

    return value


LEGACY_ZONE_X1 = _read_float_env(
    "ZONE_X1",
    "50",
)

LEGACY_ZONE_Y1 = _read_float_env(
    "ZONE_Y1",
    "50",
)

LEGACY_ZONE_X2 = _read_float_env(
    "ZONE_X2",
    "700",
)

LEGACY_ZONE_Y2 = _read_float_env(
    "ZONE_Y2",
    "450",
)

LEGACY_SECURITY_SEVERITY = os.getenv(
    "SECURITY_SEVERITY",
    "high",
).strip().lower()

VALID_SEVERITIES = {
    "low",
    "medium",
    "high",
    "critical",
}


# ============================================================
# SECURITY AGENT
# ============================================================

class SecurityAgent(BaseAgent):

    def __init__(
        self,
        agent_id: Optional[str] = None,
    ):
        super().__init__(
            agent_id=agent_id or DEFAULT_AGENT_ID,
        )

        self._validate_configuration()

        # ----------------------------------------------------
        # Camera registry / policy provider.
        #
        # Import lazily so the agent remains importable even
        # when the backend package is unavailable during
        # isolated unit tests.
        # ----------------------------------------------------

        self.camera_registry = None

        try:
            from backend.app.cameras.registry import (
                CameraRegistry,
            )

            self.camera_registry = (
                CameraRegistry.from_environment()
            )

            print(
                f"[{self.agent_id}] "
                f"Camera policy registry loaded | "
                f"Cameras={self.camera_registry.count()}"
            )

        except Exception as exc:
            # Security must fail closed.
            #
            # A missing policy registry must NOT silently turn
            # into a global security zone.
            self.camera_registry = None

            print(
                f"[{self.agent_id}] "
                f"Camera policy registry unavailable | "
                f"{type(exc).__name__}: {exc}"
            )

            if SECURITY_LEGACY_ZONE_FALLBACK_ENABLED:
                print(
                    f"[{self.agent_id}] "
                    f"WARNING: legacy security-zone fallback "
                    f"is explicitly enabled."
                )

        # ----------------------------------------------------
        # Camera-specific alert state.
        #
        # {
        #     "CAM01": {"1", "4"},
        #     "CAM02": {"2"}
        # }
        #
        # A track is kept here only while it is considered
        # inside the restricted zone.
        # ----------------------------------------------------

        self.alerted_tracks: dict[
            str,
            set[str],
        ] = {}

        # ----------------------------------------------------
        # Last observation time for each camera/track.
        #
        # Used to prevent a single tracker dropout from
        # immediately creating an exit + re-entry sequence.
        # ----------------------------------------------------

        self.track_last_seen: dict[
            str,
            dict[str, datetime],
        ] = {}

        # ----------------------------------------------------
        # Last processed event timestamp for each camera.
        #
        # Prevents older historical/out-of-order tracking
        # events from corrupting state.
        # ----------------------------------------------------

        self.last_event_timestamp: dict[
            str,
            datetime,
        ] = {}

        # ----------------------------------------------------
        # Unique Redis consumer name.
        # ----------------------------------------------------

        self.consumer_name = (
            f"{CONSUMER_NAME_PREFIX}-"
            f"{uuid.uuid4().hex[:8]}"
        )

    # ========================================================
    # CONFIGURATION VALIDATION
    # ========================================================

    @staticmethod
    def _validate_configuration() -> None:

        if not SECURITY_LEGACY_ZONE_FALLBACK_ENABLED:
            return

        if LEGACY_ZONE_X1 >= LEGACY_ZONE_X2:
            raise ValueError(
                "Invalid legacy security zone: "
                "ZONE_X1 must be smaller than ZONE_X2."
            )

        if LEGACY_ZONE_Y1 >= LEGACY_ZONE_Y2:
            raise ValueError(
                "Invalid legacy security zone: "
                "ZONE_Y1 must be smaller than ZONE_Y2."
            )

        if (
            LEGACY_SECURITY_SEVERITY
            not in VALID_SEVERITIES
        ):
            raise ValueError(
                "SECURITY_SEVERITY must be one of: "
                f"{sorted(VALID_SEVERITIES)}. "
                f"Received: "
                f"{LEGACY_SECURITY_SEVERITY!r}"
            )

    # ========================================================
    # STARTUP
    # ========================================================

    async def on_start(self):
        await self.ensure_consumer_group()

        print(
            f"[{self.agent_id}] "
            f"Security agent ready."
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
            f"Input: {INPUT_STREAM}"
        )

        print(
            f"[{self.agent_id}] "
            f"Output: {OUTPUT_STREAM}"
        )

        print(
            f"[{self.agent_id}] "
            f"Consumer: {self.consumer_name}"
        )

        print(
            f"[{self.agent_id}] "
            f"Track-loss grace: "
            f"{TRACK_LOSS_GRACE_SECONDS}s"
        )

        print(
            f"[{self.agent_id}] "
            f"Legacy zone fallback: "
            f"{SECURITY_LEGACY_ZONE_FALLBACK_ENABLED}"
        )

        print(
            f"[{self.agent_id}] "
            f"Camera-specific policy mode enabled."
        )

    # ========================================================
    # SHUTDOWN
    # ========================================================

    async def on_stop(self):
        self.alerted_tracks.clear()
        self.track_last_seen.clear()
        self.last_event_timestamp.clear()

        print(
            f"[{self.agent_id}] "
            f"Security state cleared."
        )

    # ========================================================
    # REDIS CONSUMER GROUP
    # ========================================================

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

    # ========================================================
    # TIMESTAMP PARSER
    # ========================================================

    @staticmethod
    def _parse_timestamp(
        value: Any,
    ) -> Optional[datetime]:

        if not isinstance(value, str):
            return None

        value = value.strip()

        if not value:
            return None

        try:
            parsed = datetime.fromisoformat(
                value.replace(
                    "Z",
                    "+00:00",
                )
            )
        except ValueError:
            return None

        # Canonical events require timezone-aware timestamps.
        #
        # Do NOT silently convert a naive timestamp here.
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None

        return parsed.astimezone(
            timezone.utc
        )

    # ========================================================
    # EVENT TIME
    # ========================================================

    @classmethod
    def _get_event_time(
        cls,
        event: dict,
    ) -> datetime:

        data = event.get("data")

        if isinstance(data, dict):
            frame_timestamp = cls._parse_timestamp(
                data.get("frame_timestamp")
            )

            if frame_timestamp is not None:
                return frame_timestamp

        event_timestamp = cls._parse_timestamp(
            event.get("timestamp")
        )

        if event_timestamp is not None:
            return event_timestamp

        # This should normally be unreachable after canonical
        # event validation.
        raise ValueError(
            "Event does not contain a valid timezone-aware "
            "timestamp."
        )

    # ========================================================
    # CAMERA ID
    # ========================================================

    @staticmethod
    def _extract_camera_id(
        event: dict,
    ) -> Optional[str]:

        camera = event.get("camera")

        if not isinstance(
            camera,
            dict,
        ):
            return None

        camera_id = camera.get(
            "camera_id"
        )

        if not isinstance(
            camera_id,
            str,
        ):
            return None

        camera_id = camera_id.strip()

        if not camera_id:
            return None

        return camera_id

    # ========================================================
    # CAMERA POLICY
    # ========================================================

    def _get_camera_config(
        self,
        camera_id: str,
    ) -> Optional[Any]:

        if self.camera_registry is None:
            return None

        try:
            return self.camera_registry.get(
                camera_id
            )

        except Exception as exc:
            print(
                f"[{self.agent_id}] "
                f"Camera policy lookup failed | "
                f"Camera={camera_id} | "
                f"{type(exc).__name__}: {exc}"
            )

            return None

    # ========================================================
    # SECURITY ZONE
    # ========================================================

    def _get_security_zone(
        self,
        camera_id: str,
        camera_config: Optional[Any] = None,
    ) -> Optional[
        tuple[float, float, float, float]
    ]:

        if camera_config is None:
            camera_config = self._get_camera_config(
                camera_id
            )

        # ----------------------------------------------------
        # Explicit camera policy has priority.
        # ----------------------------------------------------

        if camera_config is not None:

            policy = getattr(
                camera_config,
                "policy",
                None,
            )

            if policy is not None:

                zone = getattr(
                    policy,
                    "restricted_zone",
                    None,
                )

                if zone is not None:
                    parsed = self._normalize_zone(
                        zone
                    )

                    if parsed is None:
                        print(
                            f"[{self.agent_id}] "
                            f"Invalid restricted zone "
                            f"configuration | "
                            f"Camera={camera_id}"
                        )

                    return parsed

                # Explicitly configured camera with no
                # restricted zone means security-zone
                # intrusion detection is disabled for it.
                return None

            # Known camera without usable policy.
            print(
                f"[{self.agent_id}] "
                f"Camera has no usable security policy | "
                f"Camera={camera_id}"
            )

            return None

        # ----------------------------------------------------
        # Registry unavailable / camera unknown.
        #
        # Fail closed unless legacy compatibility mode was
        # explicitly enabled.
        # ----------------------------------------------------

        if SECURITY_LEGACY_ZONE_FALLBACK_ENABLED:
            return (
                LEGACY_ZONE_X1,
                LEGACY_ZONE_Y1,
                LEGACY_ZONE_X2,
                LEGACY_ZONE_Y2,
            )

        return None

    # ========================================================
    # NORMALIZE ZONE
    # ========================================================

    @staticmethod
    def _normalize_zone(
        zone: Any,
    ) -> Optional[
        tuple[float, float, float, float]
    ]:

        try:
            if isinstance(
                zone,
                dict,
            ):
                x1 = float(zone["x1"])
                y1 = float(zone["y1"])
                x2 = float(zone["x2"])
                y2 = float(zone["y2"])

            else:
                x1 = float(
                    getattr(zone, "x1")
                )
                y1 = float(
                    getattr(zone, "y1")
                )
                x2 = float(
                    getattr(zone, "x2")
                )
                y2 = float(
                    getattr(zone, "y2")
                )

        except (
            KeyError,
            TypeError,
            ValueError,
            AttributeError,
        ):
            return None

        if not all(
            math.isfinite(value)
            for value in (
                x1,
                y1,
                x2,
                y2,
            )
        ):
            return None

        if x1 >= x2 or y1 >= y2:
            return None

        return (
            x1,
            y1,
            x2,
            y2,
        )

    # ========================================================
    # SECURITY SEVERITY
    # ========================================================

    def _get_security_severity(
        self,
        camera_id: str,
        camera_config: Optional[Any] = None,
    ) -> Optional[str]:

        if camera_config is None:
            camera_config = self._get_camera_config(
                camera_id
            )

        if camera_config is not None:

            policy = getattr(
                camera_config,
                "policy",
                None,
            )

            if policy is not None:

                severity = getattr(
                    policy,
                    "security_severity",
                    None,
                )

                if isinstance(
                    severity,
                    str,
                ):
                    severity = (
                        severity.strip()
                        .lower()
                    )

                    if (
                        severity
                        in VALID_SEVERITIES
                    ):
                        return severity

                print(
                    f"[{self.agent_id}] "
                    f"Invalid security severity | "
                    f"Camera={camera_id}"
                )

                return None

            return None

        if SECURITY_LEGACY_ZONE_FALLBACK_ENABLED:
            return LEGACY_SECURITY_SEVERITY

        return None

    # ========================================================
    # POINT INSIDE RESTRICTED ZONE
    # ========================================================

    @staticmethod
    def _point_inside_zone(
        zone: tuple[
            float,
            float,
            float,
            float,
        ],
        x: float,
        y: float,
    ) -> bool:

        (
            x1,
            y1,
            x2,
            y2,
        ) = zone

        return (
            x1 <= x <= x2
            and
            y1 <= y <= y2
        )

    # ========================================================
    # REMOVE STALE TRACKS
    # ========================================================

    def _cleanup_stale_tracks(
        self,
        camera_id: str,
        event_time: datetime,
    ) -> None:

        camera_last_seen = (
            self.track_last_seen.get(
                camera_id
            )
        )

        if not camera_last_seen:
            return

        camera_alerted = (
            self.alerted_tracks.get(
                camera_id,
                set(),
            )
        )

        stale_tracks: list[str] = []

        for (
            track_id,
            last_seen,
        ) in camera_last_seen.items():

            age = (
                event_time - last_seen
            ).total_seconds()

            if age < 0:
                continue

            if (
                age
                > TRACK_LOSS_GRACE_SECONDS
            ):
                stale_tracks.append(
                    track_id
                )

        for track_id in stale_tracks:

            camera_last_seen.pop(
                track_id,
                None,
            )

            if track_id in camera_alerted:

                camera_alerted.discard(
                    track_id
                )

                print(
                    f"[{self.agent_id}] "
                    f"Security track expired | "
                    f"Camera={camera_id} | "
                    f"Track={track_id}"
                )

        if not camera_last_seen:
            self.track_last_seen.pop(
                camera_id,
                None,
            )

        if not camera_alerted:
            self.alerted_tracks.pop(
                camera_id,
                None,
            )

    # ========================================================
    # BUILD AND EMIT INTRUSION EVENT
    # ========================================================

    async def emit_intrusion_event(
        self,
        tracking_event: dict,
        track: dict,
        redis_source_id: str,
        camera_config: Optional[Any] = None,
    ) -> str:

        camera_id = self._extract_camera_id(
            tracking_event
        )

        if camera_id is None:
            raise ValueError(
                "Cannot emit intrusion event "
                "without a valid camera_id."
            )

        source_event_id = tracking_event.get(
            "event_id"
        )

        if not isinstance(
            source_event_id,
            str,
        ):
            raise ValueError(
                "Tracking event is missing event_id."
            )

        data = tracking_event.get(
            "data"
        )

        if not isinstance(
            data,
            dict,
        ):
            raise ValueError(
                "Tracking event data must be an object."
            )

        track_id = track.get(
            "track_id"
        )

        if track_id is None:
            raise ValueError(
                "Track is missing track_id."
            )

        track_id = str(track_id).strip()

        if not track_id:
            raise ValueError(
                "Track contains an empty track_id."
            )

        bbox = track.get(
            "bbox",
            [],
        )

        center = track.get(
            "center",
            [],
        )

        frame_id = data.get(
            "frame_id"
        )

        frame_timestamp = data.get(
            "frame_timestamp"
        )

        context = tracking_event.get(
            "context",
            {},
        )

        if not isinstance(
            context,
            dict,
        ):
            raise ValueError(
                "Tracking event context must be an object."
            )

        mode = context.get(
            "mode",
            "live",
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

        timestamp = self._get_event_time(
            tracking_event
        )

        zone = self._get_security_zone(
            camera_id=camera_id,
            camera_config=camera_config,
        )

        if zone is None:
            raise ValueError(
                f"No valid restricted security zone "
                f"configured for camera {camera_id}."
            )

        severity = self._get_security_severity(
            camera_id=camera_id,
            camera_config=camera_config,
        )

        if severity is None:
            raise ValueError(
                f"No valid security severity "
                f"configured for camera {camera_id}."
            )

        (
            zone_x1,
            zone_y1,
            zone_x2,
            zone_y2,
        ) = zone

        track_data = {
            "track_id": track_id,
            "bbox": bbox,
            "center": center,
        }

        optional_track_fields = (
            "age",
            "match_distance",
            "detection_id",
            "confidence",
        )

        for field_name in optional_track_fields:

            if field_name in track:

                track_data[field_name] = (
                    track[field_name]
                )

        source = tracking_event.get(
            "source",
            {},
        )

        if not isinstance(
            source,
            dict,
        ):
            raise ValueError(
                "Tracking event source must be an object."
            )

        position_x: Optional[float] = None
        position_y: Optional[float] = None

        if (
            isinstance(
                center,
                (list, tuple),
            )
            and len(center) == 2
        ):
            try:
                position_x = float(
                    center[0]
                )
                position_y = float(
                    center[1]
                )
            except (
                TypeError,
                ValueError,
            ):
                position_x = None
                position_y = None

        event = create_event(
            event_type="intrusion.detected",
            agent_id=self.agent_id,
            instance_id=self.instance_id,
            hostname=self.hostname,
            camera_id=camera_id,
            mode=mode,
            trace_id=trace_id,
            correlation_id=correlation_id,
            incident_id=incident_id,
            timestamp=timestamp,
            data={
                "track_id": track_id,
                "frame_id": frame_id,
                "frame_timestamp": frame_timestamp,
                "severity": severity,
                "zone": {
                    "x1": zone_x1,
                    "y1": zone_y1,
                    "x2": zone_x2,
                    "y2": zone_y2,
                },
                "position": {
                    "x": position_x,
                    "y": position_y,
                },
                "track": track_data,
                "behavior": (
                    "restricted_zone_intrusion"
                ),
                "message": (
                    "Person entered restricted "
                    f"zone on camera {camera_id}."
                ),

                # ------------------------------------------------
                # Event lineage.
                # ------------------------------------------------

                "source_event_id": (
                    source_event_id
                ),

                "source_redis_id": (
                    redis_source_id
                ),

                "source_event_type": (
                    tracking_event.get(
                        "event_type"
                    )
                ),

                "source_agent_id": (
                    source.get(
                        "agent_id"
                    )
                ),

                "source_instance_id": (
                    source.get(
                        "instance_id"
                    )
                ),
            },
        )

        # Current canonical envelope validation.
        #
        # Specialized intrusion validation will be added after
        # the final event-contract registry is frozen.
        if not validate_event(event):
            raise ValueError(
                "Generated intrusion event failed "
                "canonical event validation."
            )

        redis_id = await self.publish(
            OUTPUT_STREAM,
            event,
        )

        print(
            f"[{self.agent_id}] "
            f"INTRUSION DETECTED | "
            f"Camera={camera_id} | "
            f"Track={track_id} | "
            f"Severity={severity} | "
            f"Redis={redis_id}"
        )

        return redis_id

    # ========================================================
    # PROCESS TRACKING EVENT
    # ========================================================

    async def process_tracking_event(
        self,
        event: dict,
        redis_source_id: str,
    ) -> None:

        # ----------------------------------------------------
        # Only person.tracked events are relevant.
        # ----------------------------------------------------

        if event.get(
            "event_type"
        ) != "person.tracked":
            return

        # ----------------------------------------------------
        # Validate source event envelope.
        #
        # NOTE:
        # validate_registered_event() is intentionally not used
        # yet because the current PersonTrackedData schema and
        # actual Tracker producer contract are still being
        # reconciled.
        # ----------------------------------------------------

        if not validate_event(
            event
        ):
            raise ValueError(
                "Received person.tracked event "
                "failed canonical validation."
            )

        # ----------------------------------------------------
        # Camera.
        # ----------------------------------------------------

        camera_id = self._extract_camera_id(
            event
        )

        if camera_id is None:
            raise ValueError(
                "person.tracked event has no valid camera_id."
            )

        # ----------------------------------------------------
        # Camera policy.
        #
        # Security fails closed:
        #
        # known camera + explicit restricted zone
        #     -> evaluate
        #
        # known camera + no restricted zone
        #     -> no security alert
        #
        # unknown camera / unavailable registry
        #     -> no security alert unless explicit legacy mode
        # ----------------------------------------------------

        camera_config = self._get_camera_config(
            camera_id
        )

        zone = self._get_security_zone(
            camera_id=camera_id,
            camera_config=camera_config,
        )

        if zone is None:
            return

        severity = self._get_security_severity(
            camera_id=camera_id,
            camera_config=camera_config,
        )

        if severity is None:
            print(
                f"[{self.agent_id}] "
                f"Security policy has no valid severity | "
                f"Camera={camera_id}"
            )
            return

        # ----------------------------------------------------
        # Event time.
        # ----------------------------------------------------

        event_time = self._get_event_time(
            event
        )

        # ----------------------------------------------------
        # Camera-level ordering protection.
        # ----------------------------------------------------

        previous_event_time = (
            self.last_event_timestamp.get(
                camera_id
            )
        )

        if (
            previous_event_time is not None
            and event_time < previous_event_time
        ):
            print(
                f"[{self.agent_id}] "
                f"Ignoring out-of-order event | "
                f"Camera={camera_id} | "
                f"EventTime={event_time.isoformat()} | "
                f"LastTime="
                f"{previous_event_time.isoformat()} | "
                f"Redis={redis_source_id}"
            )
            return

        # ----------------------------------------------------
        # Data.
        # ----------------------------------------------------

        data = event.get(
            "data"
        )

        if not isinstance(
            data,
            dict,
        ):
            raise ValueError(
                "person.tracked event data must be an object."
            )

        tracks = data.get(
            "tracks",
            [],
        )

        if not isinstance(
            tracks,
            list,
        ):
            raise ValueError(
                "person.tracked event tracks must be a list."
            )

        # ----------------------------------------------------
        # The event has passed the relevant structural checks,
        # so update the camera event watermark.
        # ----------------------------------------------------

        self.last_event_timestamp[
            camera_id
        ] = event_time

        # ----------------------------------------------------
        # Initialize camera state.
        # ----------------------------------------------------

        camera_alerted_tracks = (
            self.alerted_tracks.setdefault(
                camera_id,
                set(),
            )
        )

        camera_last_seen = (
            self.track_last_seen.setdefault(
                camera_id,
                {},
            )
        )

        # ----------------------------------------------------
        # Process current observations.
        # ----------------------------------------------------

        for track in tracks:

            if not isinstance(
                track,
                dict,
            ):
                continue

            track_id = track.get(
                "track_id"
            )

            if track_id is None:
                continue

            track_id = str(
                track_id
            ).strip()

            if not track_id:
                continue

            center = track.get(
                "center"
            )

            if (
                not isinstance(
                    center,
                    (list, tuple),
                )
                or len(center) != 2
            ):
                continue

            try:
                center_x = float(
                    center[0]
                )
                center_y = float(
                    center[1]
                )

            except (
                TypeError,
                ValueError,
            ):
                continue

            if (
                not math.isfinite(center_x)
                or not math.isfinite(center_y)
            ):
                continue

            # ------------------------------------------------
            # Prevent an older observation for the same track
            # from moving its last-seen timestamp backwards.
            # ------------------------------------------------

            previous_track_time = (
                camera_last_seen.get(
                    track_id
                )
            )

            if (
                previous_track_time is not None
                and event_time < previous_track_time
            ):
                continue

            camera_last_seen[
                track_id
            ] = event_time

            # ------------------------------------------------
            # Zone check.
            # ------------------------------------------------

            inside = self._point_inside_zone(
                zone,
                center_x,
                center_y,
            )

            # ------------------------------------------------
            # Explicit exit:
            #
            # If the tracker explicitly observes the person
            # outside the restricted zone, clear the alert
            # state immediately.
            # ------------------------------------------------

            if not inside:

                if (
                    track_id
                    in camera_alerted_tracks
                ):
                    camera_alerted_tracks.discard(
                        track_id
                    )

                    print(
                        f"[{self.agent_id}] "
                        f"Security zone exited | "
                        f"Camera={camera_id} | "
                        f"Track={track_id}"
                    )

                continue

            # ------------------------------------------------
            # Person is inside the restricted zone.
            # ------------------------------------------------

            # Generate only one intrusion event while the same
            # track remains inside the zone.

            if (
                track_id
                not in camera_alerted_tracks
            ):

                await self.emit_intrusion_event(
                    tracking_event=event,
                    track=track,
                    redis_source_id=redis_source_id,
                    camera_config=camera_config,
                )

                # Mark only AFTER successful publication.
                #
                # If publication fails, this remains unmarked
                # and the Redis message remains pending.
                camera_alerted_tracks.add(
                    track_id
                )

                print(
                    f"[{self.agent_id}] "
                    f"Security zone entered | "
                    f"Camera={camera_id} | "
                    f"Track={track_id} | "
                    f"Center=("
                    f"{center_x:.1f}, "
                    f"{center_y:.1f}) | "
                    f"Severity={severity}"
                )

        # ----------------------------------------------------
        # Track-loss cleanup.
        #
        # Do NOT immediately clear a track just because it was
        # absent from one observation.
        #
        # This prevents:
        #
        # inside -> dropout -> inside
        #
        # from generating duplicate intrusion events.
        # ----------------------------------------------------

        self._cleanup_stale_tracks(
            camera_id=camera_id,
            event_time=event_time,
        )

        # ----------------------------------------------------
        # Remove empty camera state.
        # ----------------------------------------------------

        if not camera_alerted_tracks:
            self.alerted_tracks.pop(
                camera_id,
                None,
            )

        if not camera_last_seen:
            self.track_last_seen.pop(
                camera_id,
                None,
            )

    # ========================================================
    # MAIN PROCESSING LOOP
    # ========================================================

    async def run(self):

        if not self.redis_client:
            raise RuntimeError(
                "Redis client is not initialized."
            )

        print(
            f"[{self.agent_id}] "
            f"Security processing loop started."
        )

        while self.running:

            # ------------------------------------------------
            # Read from Redis.
            # ------------------------------------------------

            try:
                messages = (
                    await self.redis_client.xreadgroup(
                        groupname=GROUP_NAME,
                        consumername=(
                            self.consumer_name
                        ),
                        streams={
                            INPUT_STREAM: ">"
                        },
                        count=10,
                        block=5000,
                    )
                )

            except asyncio.CancelledError:
                raise

            except Exception as exc:
                print(
                    f"[{self.agent_id}] "
                    f"Redis read error: "
                    f"{type(exc).__name__}: "
                    f"{exc}"
                )

                await self.sleep(
                    2
                )

                continue

            if not messages:
                continue

            # ------------------------------------------------
            # Process each Redis message independently.
            # ------------------------------------------------

            for (
                stream_name,
                stream_messages,
            ) in messages:

                for (
                    redis_id,
                    fields,
                ) in stream_messages:

                    try:

                        # ------------------------------------
                        # Validate Redis fields.
                        # ------------------------------------

                        if not isinstance(
                            fields,
                            dict,
                        ):
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

                            continue

                        # ------------------------------------
                        # Extract event.
                        # ------------------------------------

                        raw_event = fields.get(
                            "event"
                        )

                        if not raw_event:
                            print(
                                f"[{self.agent_id}] "
                                f"Missing event payload | "
                                f"Redis={redis_id}"
                            )

                            await self.redis_client.xack(
                                INPUT_STREAM,
                                GROUP_NAME,
                                redis_id,
                            )

                            continue

                        # ------------------------------------
                        # Parse JSON.
                        # ------------------------------------

                        event = json.loads(
                            raw_event
                        )

                        if not isinstance(
                            event,
                            dict,
                        ):
                            raise ValueError(
                                "Event payload must "
                                "decode to an object."
                            )

                        # ------------------------------------
                        # Camera ID for logging.
                        # ------------------------------------

                        received_camera_id = (
                            self._extract_camera_id(
                                event
                            )
                        )

                        print(
                            f"[{self.agent_id}] "
                            f"Security received | "
                            f"Type="
                            f"{event.get('event_type')} | "
                            f"Camera="
                            f"{received_camera_id} | "
                            f"Redis={redis_id}"
                        )

                        # ------------------------------------
                        # Process event.
                        # ------------------------------------

                        await self.process_tracking_event(
                            event=event,
                            redis_source_id=redis_id,
                        )

                        # ------------------------------------
                        # ACK only after successful processing.
                        # ------------------------------------

                        await self.redis_client.xack(
                            INPUT_STREAM,
                            GROUP_NAME,
                            redis_id,
                        )

                    except asyncio.CancelledError:
                        raise

                    except json.JSONDecodeError as exc:
                        # ------------------------------------
                        # Malformed JSON is a permanent
                        # poison message.
                        # ------------------------------------

                        print(
                            f"[{self.agent_id}] "
                            f"Invalid JSON | "
                            f"Redis={redis_id} | "
                            f"Error={exc}"
                        )

                        await self.redis_client.xack(
                            INPUT_STREAM,
                            GROUP_NAME,
                            redis_id,
                        )

                    except ValueError as exc:
                        # ------------------------------------
                        # Structurally invalid/permanent event.
                        #
                        # Current MVP behavior:
                        # ACK after logging so one poison event
                        # cannot block the consumer.
                        #
                        # Final architecture should route these
                        # into a DLQ/quarantine stream instead.
                        # ------------------------------------

                        print(
                            f"[{self.agent_id}] "
                            f"Invalid security event | "
                            f"Redis={redis_id} | "
                            f"Error={exc}"
                        )

                        await self.redis_client.xack(
                            INPUT_STREAM,
                            GROUP_NAME,
                            redis_id,
                        )

                    except Exception as exc:
                        # ------------------------------------
                        # Unexpected processing failures are
                        # intentionally NOT ACKed.
                        #
                        # Redis keeps the message pending so
                        # the reliability/recovery layer can
                        # reclaim it.
                        #
                        # Failure is isolated to this message.
                        # ------------------------------------

                        print(
                            f"[{self.agent_id}] "
                            f"ERROR processing "
                            f"{redis_id} | "
                            f"{type(exc).__name__}: "
                            f"{exc}"
                        )

                        continue


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    agent = SecurityAgent()

    try:
        asyncio.run(
            agent.run_forever()
        )

    except KeyboardInterrupt:
        print(
            "\nSecurity Agent interrupted."
        )