# # # # import asyncio
# # # # import json
# # # # import os
# # # # import time
# # # # import uuid
# # # # from datetime import datetime, timezone
# # # # import redis.asyncio as redis


# # # # # ============================================================
# # # # # CONFIG
# # # # # ============================================================

# # # # REDIS_HOST = os.getenv(
# # # #     "REDIS_HOST",
# # # #     "localhost"
# # # # )

# # # # REDIS_PORT = int(
# # # #     os.getenv(
# # # #         "REDIS_PORT",
# # # #         "6379"
# # # #     )
# # # # )

# # # # INPUT_STREAM = "events.tracking"
# # # # OUTPUT_STREAM = "events.behavior"

# # # # GROUP_NAME = "crowd-workers"
# # # # CONSUMER_NAME = "crowd-01"

# # # # CROWD_THRESHOLD = 5

# # # # TRACK_TIMEOUT_SECONDS = 0.8


# # # # # ============================================================
# # # # # STATE
# # # # # ============================================================

# # # # # {
# # # # #     "CAM01": {
# # # # #         "track-1": last_seen_timestamp,
# # # # #         "track-2": last_seen_timestamp
# # # # #     }
# # # # # }

# # # # camera_tracks = {}


# # # # # {
# # # # #     "CAM01": True
# # # # # }

# # # # crowd_active = {}


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
# # # # # REMOVE EXPIRED TRACKS
# # # # # ============================================================

# # # # def remove_expired_tracks(
# # # #     camera_id,
# # # #     now,
# # # # ):

# # # #     tracks = camera_tracks.get(
# # # #         camera_id
# # # #     )

# # # #     if not tracks:

# # # #         return

# # # #     expired_tracks = [

# # # #         track_id

# # # #         for track_id, last_seen
# # # #         in tracks.items()

# # # #         if now - last_seen
# # # #         > TRACK_TIMEOUT_SECONDS

# # # #     ]

# # # #     for track_id in expired_tracks:

# # # #         del tracks[
# # # #             track_id
# # # #         ]

# # # #     if expired_tracks:

# # # #         print(
# # # #             f"Camera {camera_id}: "
# # # #             f"removed "
# # # #             f"{len(expired_tracks)} "
# # # #             f"expired track(s)"
# # # #         )


# # # # # ============================================================
# # # # # GET ACTIVE PERSON COUNT
# # # # # ============================================================

# # # # def get_person_count(
# # # #     camera_id
# # # # ):

# # # #     return len(
# # # #         camera_tracks.get(
# # # #             camera_id,
# # # #             {}
# # # #         )
# # # #     )


# # # # # ============================================================
# # # # # CREATE CROWD EVENT
# # # # # ============================================================

# # # # async def emit_crowd_event(

# # # #     redis_client,

# # # #     camera_id,

# # # #     frame_id,

# # # #     person_count,

# # # # ):

# # # #     # Do not repeatedly emit while
# # # #     # crowd condition remains active.

# # # #     if crowd_active.get(
# # # #         camera_id,
# # # #         False
# # # #     ):

# # # #         return

# # # #     crowd_active[
# # # #         camera_id
# # # #     ] = True

# # # #     active_track_ids = list(

# # # #         camera_tracks.get(
# # # #             camera_id,
# # # #             {}
# # # #         ).keys()

# # # #     )

# # # #     # ========================================================
# # # #     # SEVERITY
# # # #     # ========================================================

# # # #     if person_count >= 10:

# # # #         severity = "critical"

# # # #     elif person_count >= 7:

# # # #         severity = "high"

# # # #     elif person_count >= 5:

# # # #         severity = "medium"

# # # #     else:

# # # #         severity = "low"

# # # #     # ========================================================
# # # #     # CROWD EVENT
# # # #     # ========================================================

# # # #     crowd_event = {

# # # #         "event_id": str(
# # # #             uuid.uuid4()
# # # #         ),

# # # #         "event_type":
# # # #             "crowd.detected",

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

# # # #             "frame_id":
# # # #                 frame_id,

# # # #             "person_count":
# # # #                 person_count,

# # # #             "density":
# # # #                 float(person_count),

# # # #             "threshold":
# # # #                 float(CROWD_THRESHOLD),

# # # #             "severity": severity,

# # # #             "track_ids":
# # # #                 active_track_ids,

# # # #         },

# # # #     }

# # # #     output_id = await redis_client.xadd(

# # # #         OUTPUT_STREAM,

# # # #         {

# # # #             "event":
# # # #                 json.dumps(
# # # #                     crowd_event
# # # #                 )

# # # #         },

# # # #     )

# # # #     print(

# # # #         f"🚨 CROWD DETECTED | "

# # # #         f"Camera: {camera_id} | "

# # # #         f"Count: {person_count} | "

# # # #         f"Threshold: {CROWD_THRESHOLD} | "

# # # #         f"Severity: {severity} | "

# # # #         f"Tracks: {active_track_ids} | "

# # # #         f"Redis ID: {output_id}"

# # # #     )


# # # # # ============================================================
# # # # # UPDATE CROWD STATE
# # # # # ============================================================

# # # # def update_crowd_state(

# # # #     camera_id,

# # # #     person_count,

# # # # ):

# # # #     if person_count < CROWD_THRESHOLD:

# # # #         if crowd_active.get(
# # # #             camera_id,
# # # #             False
# # # #         ):

# # # #             print(

# # # #                 f"✅ Crowd cleared | "

# # # #                 f"Camera: {camera_id} | "

# # # #                 f"Count: {person_count}"

# # # #             )

# # # #         crowd_active[
# # # #             camera_id
# # # #         ] = False


# # # # # ============================================================
# # # # # PROCESS TRACKING EVENT
# # # # # ============================================================

# # # # async def process_tracking_event(
# # # #     redis_client,
# # # #     event,
# # # # ):

# # # #     camera = event.get(
# # # #         "camera",
# # # #         {}
# # # #     )

# # # #     camera_id = camera.get(
# # # #         "camera_id",
# # # #         "unknown"
# # # #     )

# # # #     data = event.get(
# # # #         "data",
# # # #         {}
# # # #     )

# # # #     frame_id = data.get(
# # # #         "frame_id"
# # # #     )

# # # #     tracked_items = data.get(
# # # #         "tracks",
# # # #         []
# # # #     )

# # # #     if not frame_id:

# # # #         print(
# # # #             "Ignoring person.tracked event "
# # # #             "without frame_id"
# # # #         )

# # # #         return

# # # #     if not isinstance(
# # # #         tracked_items,
# # # #         list
# # # #     ):

# # # #         print(
# # # #             "Ignoring person.tracked event "
# # # #             "without valid tracks"
# # # #         )

# # # #         return

# # # #     now = time.time()

# # # #     if camera_id not in camera_tracks:

# # # #         camera_tracks[camera_id] = {}

# # # #     # Every track visible in this frame
# # # #     # is considered active.

# # # #     for tracked_item in tracked_items:

# # # #         track_id = tracked_item.get(
# # # #             "track_id"
# # # #         )

# # # #         if not track_id:
# # # #             continue

# # # #         camera_tracks[camera_id][
# # # #             track_id
# # # #         ] = now

# # # #     # Remove stale tracks.

# # # #     remove_expired_tracks(
# # # #         camera_id,
# # # #         now,
# # # #     )

# # # #     # Count active people.

# # # #     person_count = len(
# # # #         camera_tracks.get(
# # # #             camera_id,
# # # #             {}
# # # #         )
# # # #     )

# # # #     active_track_ids = list(
# # # #         camera_tracks.get(
# # # #             camera_id,
# # # #             {}
# # # #         ).keys()
# # # #     )

# # # #     print(
# # # #         f"Camera {camera_id}: "
# # # #         f"{person_count} active person(s) | "
# # # #         f"Tracks: {active_track_ids}"
# # # #     )
# # # #     # Update crowd state.

# # # #     update_crowd_state(
# # # #         camera_id,
# # # #         person_count,
# # # #     )

# # # #     # Detect crowd.

# # # #     if person_count >= CROWD_THRESHOLD:

# # # #         await emit_crowd_event(
# # # #             redis_client,
# # # #             camera_id,
# # # #             frame_id,
# # # #             person_count,
# # # #         )



# # # # # ============================================================
# # # # # BACKGROUND CLEANUP LOOP
# # # # # ============================================================

# # # # async def cleanup_loop():

# # # #     while True:

# # # #         try:

# # # #             now = time.time()

# # # #             for camera_id in list(
# # # #                 camera_tracks.keys()
# # # #             ):

# # # #                 remove_expired_tracks(
# # # #                     camera_id,
# # # #                     now
# # # #                 )

# # # #                 person_count = (
# # # #                     get_person_count(
# # # #                         camera_id
# # # #                     )
# # # #                 )

# # # #                 update_crowd_state(

# # # #                     camera_id,

# # # #                     person_count,

# # # #                 )

# # # #         except Exception as exc:

# # # #             print(
# # # #                 f"Cleanup error: {exc}"
# # # #             )

# # # #         await asyncio.sleep(1)


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

# # # #     print("=" * 60)

# # # #     print(
# # # #         f"Crowd Agent started: "
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
# # # #         f"Crowd threshold: "
# # # #         f"{CROWD_THRESHOLD}"
# # # #     )

# # # #     print(
# # # #         f"Track timeout: "
# # # #         f"{TRACK_TIMEOUT_SECONDS}s"
# # # #     )

# # # #     print("=" * 60)

# # # #     cleanup_task = asyncio.create_task(
# # # #         cleanup_loop()
# # # #     )

# # # #     try:

# # # #         while True:

# # # #             try:

# # # #                 messages = await redis_client.xreadgroup(

# # # #                     groupname=GROUP_NAME,

# # # #                     consumername=CONSUMER_NAME,

# # # #                     streams={
# # # #                         INPUT_STREAM: ">"
# # # #                     },

# # # #                     count=10,

# # # #                     block=5000,

# # # #                 )

# # # #             except redis.exceptions.TimeoutError:

# # # #                 print(
# # # #                     "Redis read timeout; "
# # # #                     "continuing..."
# # # #                 )

# # # #                 continue

# # # #             if not messages:

# # # #                 continue

# # # #             for stream_name, stream_messages in messages:

# # # #                 for redis_id, fields in stream_messages:

# # # #                     try:

# # # #                         raw_event = fields.get(
# # # #                             "event"
# # # #                         )

# # # #                         if not raw_event:

# # # #                             await redis_client.xack(

# # # #                                 INPUT_STREAM,

# # # #                                 GROUP_NAME,

# # # #                                 redis_id,

# # # #                             )

# # # #                             continue

# # # #                         event = json.loads(
# # # #                             raw_event
# # # #                         )

# # # #                         if event.get(
# # # #                             "event_type"
# # # #                         ) != "person.tracked":

# # # #                             await redis_client.xack(

# # # #                                 INPUT_STREAM,

# # # #                                 GROUP_NAME,

# # # #                                 redis_id,

# # # #                             )

# # # #                             continue

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

# # # #                             f"Invalid JSON in "
# # # #                             f"{redis_id}: "
# # # #                             f"{exc}"

# # # #                         )

# # # #                         await redis_client.xack(

# # # #                             INPUT_STREAM,

# # # #                             GROUP_NAME,

# # # #                             redis_id,

# # # #                         )

# # # #                     except Exception as exc:

# # # #                         print(

# # # #                             f"Error processing "
# # # #                             f"{redis_id}: "
# # # #                             f"{exc}"

# # # #                         )

# # # #     finally:

# # # #         cleanup_task.cancel()

# # # #         await redis_client.aclose()

# # # #         print(
# # # #             "Crowd Agent stopped."
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
# # # import time
# # # import uuid

# # # from shared.agent.base_agent import BaseAgent


# # # class CrowdAgent(BaseAgent):
# # #     """
# # #     Crowd analysis agent.

# # #     Input:
# # #         events.tracking

# # #     Output:
# # #         events.behavior

# # #     Detects:
# # #         - crowd.detected
# # #     """

# # #     def __init__(self):
# # #         super().__init__(
# # #             agent_id=os.getenv(
# # #                 "AGENT_ID",
# # #                 "crowd-01",
# # #             ),
# # #             heartbeat_interval=int(
# # #                 os.getenv(
# # #                     "HEARTBEAT_INTERVAL",
# # #                     "10",
# # #                 )
# # #             ),
# # #         )

# # #         self.input_stream = "events.tracking"
# # #         self.output_stream = "events.behavior"

# # #         self.group_name = os.getenv(
# # #             "CROWD_GROUP",
# # #             "crowd-workers",
# # #         )

# # #         self.consumer_name = os.getenv(
# # #             "CROWD_CONSUMER",
# # #             f"crowd-{uuid.uuid4().hex[:8]}",
# # #         )

# # #         self.crowd_threshold = int(
# # #             os.getenv(
# # #                 "CROWD_THRESHOLD",
# # #                 "5",
# # #             )
# # #         )

# # #         self.track_timeout = float(
# # #             os.getenv(
# # #                 "TRACK_TIMEOUT_SECONDS",
# # #                 "0.8",
# # #             )
# # #         )

# # #         # {
# # #         #     "CAM01": {
# # #         #         "track-1": last_seen,
# # #         #         "track-2": last_seen
# # #         #     }
# # #         # }
# # #         self.camera_tracks = {}

# # #         # {
# # #         #     "CAM01": True
# # #         # }
# # #         self.crowd_active = {}

# # #         self.cleanup_task = None

# # #     async def on_start(self):
# # #         """
# # #         Create Redis consumer group and start
# # #         background cleanup.
# # #         """

# # #         try:
# # #             await self.redis_client.xgroup_create(
# # #                 name=self.input_stream,
# # #                 groupname=self.group_name,
# # #                 id="0",
# # #                 mkstream=True,
# # #             )

# # #             print(
# # #                 f"[{self.agent_id}] "
# # #                 f"Created consumer group: "
# # #                 f"{self.group_name}"
# # #             )

# # #         except Exception as error:

# # #             if "BUSYGROUP" not in str(error):
# # #                 raise

# # #         self.cleanup_task = asyncio.create_task(
# # #             self.cleanup_loop()
# # #         )

# # #         print(
# # #             f"[{self.agent_id}] Crowd agent ready."
# # #         )

# # #         print(
# # #             f"[{self.agent_id}] "
# # #             f"Input: {self.input_stream}"
# # #         )

# # #         print(
# # #             f"[{self.agent_id}] "
# # #             f"Output: {self.output_stream}"
# # #         )

# # #         print(
# # #             f"[{self.agent_id}] "
# # #             f"Crowd threshold: "
# # #             f"{self.crowd_threshold}"
# # #         )

# # #         print(
# # #             f"[{self.agent_id}] "
# # #             f"Track timeout: "
# # #             f"{self.track_timeout}s"
# # #         )

# # #         print(
# # #             f"[{self.agent_id}] "
# # #             f"Consumer: {self.consumer_name}"
# # #         )

# # #     async def on_stop(self):
# # #         """
# # #         Gracefully stop cleanup task and clear state.
# # #         """

# # #         if self.cleanup_task:

# # #             self.cleanup_task.cancel()

# # #             try:
# # #                 await self.cleanup_task

# # #             except asyncio.CancelledError:
# # #                 pass

# # #             self.cleanup_task = None

# # #         self.camera_tracks.clear()
# # #         self.crowd_active.clear()

# # #         print(
# # #             f"[{self.agent_id}] "
# # #             f"Crowd state cleared."
# # #         )

# # #     # ========================================================
# # #     # REMOVE EXPIRED TRACKS
# # #     # ========================================================

# # #     def remove_expired_tracks(
# # #         self,
# # #         camera_id,
# # #         now,
# # #     ):
# # #         tracks = self.camera_tracks.get(
# # #             camera_id
# # #         )

# # #         if not tracks:
# # #             return

# # #         expired_tracks = [
# # #             track_id
# # #             for track_id, last_seen
# # #             in tracks.items()
# # #             if now - last_seen
# # #             > self.track_timeout
# # #         ]

# # #         for track_id in expired_tracks:
# # #             del tracks[track_id]

# # #         if expired_tracks:

# # #             print(
# # #                 f"[{self.agent_id}] "
# # #                 f"Camera {camera_id}: "
# # #                 f"removed "
# # #                 f"{len(expired_tracks)} "
# # #                 f"expired track(s)"
# # #             )

# # #     # ========================================================
# # #     # GET ACTIVE PERSON COUNT
# # #     # ========================================================

# # #     def get_person_count(
# # #         self,
# # #         camera_id,
# # #     ):
# # #         return len(
# # #             self.camera_tracks.get(
# # #                 camera_id,
# # #                 {},
# # #             )
# # #         )

# # #     # ========================================================
# # #     # UPDATE CROWD STATE
# # #     # ========================================================

# # #     def update_crowd_state(
# # #         self,
# # #         camera_id,
# # #         person_count,
# # #     ):

# # #         if person_count < self.crowd_threshold:

# # #             if self.crowd_active.get(
# # #                 camera_id,
# # #                 False,
# # #             ):

# # #                 print(
# # #                     f"[{self.agent_id}] "
# # #                     f"Crowd cleared | "
# # #                     f"Camera: {camera_id} | "
# # #                     f"Count: {person_count}"
# # #                 )

# # #             self.crowd_active[
# # #                 camera_id
# # #             ] = False

# # #     # ========================================================
# # #     # EMIT CROWD EVENT
# # #     # ========================================================

# # #     async def emit_crowd_event(
# # #         self,
# # #         camera_id,
# # #         frame_id,
# # #         person_count,
# # #     ):

# # #         # Prevent duplicate crowd events while
# # #         # the crowd condition remains active.

# # #         if self.crowd_active.get(
# # #             camera_id,
# # #             False,
# # #         ):
# # #             return

# # #         self.crowd_active[
# # #             camera_id
# # #         ] = True

# # #         active_track_ids = list(
# # #             self.camera_tracks.get(
# # #                 camera_id,
# # #                 {},
# # #             ).keys()
# # #         )

# # #         # ====================================================
# # #         # SEVERITY
# # #         # ====================================================

# # #         if person_count >= 10:
# # #             severity = "critical"

# # #         elif person_count >= 7:
# # #             severity = "high"

# # #         elif person_count >= 5:
# # #             severity = "medium"

# # #         else:
# # #             severity = "low"

# # #         # ====================================================
# # #         # EVENT
# # #         # ====================================================

# # #         crowd_event = {

# # #             "event_id": str(
# # #                 uuid.uuid4()
# # #             ),

# # #             "event_type":
# # #                 "crowd.detected",

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

# # #                 "frame_id":
# # #                     frame_id,

# # #                 "person_count":
# # #                     person_count,

# # #                 "density":
# # #                     float(person_count),

# # #                 "threshold":
# # #                     float(self.crowd_threshold),

# # #                 "severity":
# # #                     severity,

# # #                 "track_ids":
# # #                     active_track_ids,
# # #             },
# # #         }

# # #         output_id = await self.publish(
# # #             self.output_stream,
# # #             crowd_event,
# # #         )

# # #         print(
# # #             f"CROWD DETECTED | "
# # #             f"Camera={camera_id} | "
# # #             f"Count={person_count} | "
# # #             f"Threshold={self.crowd_threshold} | "
# # #             f"Severity={severity} | "
# # #             f"Tracks={active_track_ids} | "
# # #             f"Redis={output_id}"
# # #         )

# # #     # ========================================================
# # #     # PROCESS TRACKING EVENT
# # #     # ========================================================

# # #     async def process_tracking_event(
# # #         self,
# # #         redis_id,
# # #         event,
# # #     ):

# # #         camera = event.get(
# # #             "camera",
# # #             {},
# # #         )

# # #         camera_id = camera.get(
# # #             "camera_id",
# # #         )

# # #         if not camera_id:
# # #             raise ValueError(
# # #                 "Tracking event missing camera_id"
# # #             )

# # #         data = event.get(
# # #             "data",
# # #             {},
# # #         )

# # #         frame_id = data.get(
# # #             "frame_id"
# # #         )

# # #         tracked_items = data.get(
# # #             "tracks",
# # #             [],
# # #         )

# # #         if not frame_id:
# # #             raise ValueError(
# # #                 "person.tracked event missing frame_id"
# # #             )

# # #         if not isinstance(
# # #             tracked_items,
# # #             list,
# # #         ):
# # #             raise ValueError(
# # #                 "person.tracked tracks must be a list"
# # #             )

# # #         now = time.monotonic()

# # #         if camera_id not in self.camera_tracks:

# # #             self.camera_tracks[
# # #                 camera_id
# # #             ] = {}

# # #         # Every track visible in this frame
# # #         # is considered active.

# # #         for tracked_item in tracked_items:

# # #             if not isinstance(
# # #                 tracked_item,
# # #                 dict,
# # #             ):
# # #                 continue

# # #             track_id = tracked_item.get(
# # #                 "track_id"
# # #             )

# # #             if not track_id:
# # #                 continue

# # #             self.camera_tracks[
# # #                 camera_id
# # #             ][track_id] = now

# # #         # Remove stale tracks.

# # #         self.remove_expired_tracks(
# # #             camera_id,
# # #             now,
# # #         )

# # #         # Count active people.

# # #         person_count = self.get_person_count(
# # #             camera_id
# # #         )

# # #         active_track_ids = list(
# # #             self.camera_tracks.get(
# # #                 camera_id,
# # #                 {},
# # #             ).keys()
# # #         )

# # #         print(
# # #             f"[{self.agent_id}] "
# # #             f"Camera {camera_id}: "
# # #             f"{person_count} active person(s) | "
# # #             f"Tracks: {active_track_ids}"
# # #         )

# # #         # Update crowd state.

# # #         self.update_crowd_state(
# # #             camera_id,
# # #             person_count,
# # #         )

# # #         # Detect crowd.

# # #         if person_count >= self.crowd_threshold:

# # #             await self.emit_crowd_event(
# # #                 camera_id,
# # #                 frame_id,
# # #                 person_count,
# # #             )

# # #     # ========================================================
# # #     # BACKGROUND CLEANUP
# # #     # ========================================================

# # #     async def cleanup_loop(self):

# # #         while self.running:

# # #             try:

# # #                 now = time.monotonic()

# # #                 for camera_id in list(
# # #                     self.camera_tracks.keys()
# # #                 ):

# # #                     self.remove_expired_tracks(
# # #                         camera_id,
# # #                         now,
# # #                     )

# # #                     person_count = (
# # #                         self.get_person_count(
# # #                             camera_id
# # #                         )
# # #                     )

# # #                     self.update_crowd_state(
# # #                         camera_id,
# # #                         person_count,
# # #                     )

# # #             except asyncio.CancelledError:
# # #                 raise

# # #             except Exception as error:

# # #                 # Cleanup failure must NEVER
# # #                 # terminate the Crowd Agent.

# # #                 print(
# # #                     f"[{self.agent_id}] "
# # #                     f"Cleanup error: {error}"
# # #                 )

# # #             await asyncio.sleep(1)

# # #     # ========================================================
# # #     # MAIN PROCESSING LOOP
# # #     # ========================================================

# # #     async def run(self):

# # #         print(
# # #             f"[{self.agent_id}] "
# # #             f"Crowd processing loop started."
# # #         )

# # #         while self.running:

# # #             try:

# # #                 messages = await (
# # #                     self.redis_client.xreadgroup(
# # #                         groupname=self.group_name,
# # #                         consumername=self.consumer_name,
# # #                         streams={
# # #                             self.input_stream: ">"
# # #                         },
# # #                         count=10,
# # #                         block=5000,
# # #                     )
# # #                 )

# # #                 if not messages:
# # #                     continue

# # #                 for _, stream_messages in messages:

# # #                     for redis_id, fields in stream_messages:

# # #                         try:

# # #                             raw_event = fields.get(
# # #                                 "event"
# # #                             )

# # #                             # Invalid Redis message.
# # #                             # ACK and continue.

# # #                             if not raw_event:

# # #                                 await self.redis_client.xack(
# # #                                     self.input_stream,
# # #                                     self.group_name,
# # #                                     redis_id,
# # #                                 )

# # #                                 continue

# # #                             event = json.loads(
# # #                                 raw_event
# # #                             )

# # #                             # Crowd only consumes
# # #                             # person.tracked events.

# # #                             if event.get(
# # #                                 "event_type"
# # #                             ) != "person.tracked":

# # #                                 await self.redis_client.xack(
# # #                                     self.input_stream,
# # #                                     self.group_name,
# # #                                     redis_id,
# # #                                 )

# # #                                 continue

# # #                             await self.process_tracking_event(
# # #                                 redis_id,
# # #                                 event,
# # #                             )

# # #                             # ACK only after
# # #                             # successful processing.

# # #                             await self.redis_client.xack(
# # #                                 self.input_stream,
# # #                                 self.group_name,
# # #                                 redis_id,
# # #                             )

# # #                         except json.JSONDecodeError as error:

# # #                             print(
# # #                                 f"[{self.agent_id}] "
# # #                                 f"Invalid JSON "
# # #                                 f"{redis_id}: "
# # #                                 f"{error}"
# # #                             )

# # #                             # Bad message should not
# # #                             # poison the consumer.

# # #                             await self.redis_client.xack(
# # #                                 self.input_stream,
# # #                                 self.group_name,
# # #                                 redis_id,
# # #                             )

# # #                         except Exception as error:

# # #                             print(
# # #                                 f"[{self.agent_id}] "
# # #                                 f"Message processing error "
# # #                                 f"{redis_id}: "
# # #                                 f"{error}"
# # #                             )

# # #                             # IMPORTANT:
# # #                             # Do NOT ACK unexpected
# # #                             # processing failures.
# # #                             #
# # #                             # Message remains pending
# # #                             # for recovery/retry.

# # #                             continue

# # #             except asyncio.CancelledError:
# # #                 raise

# # #             except Exception as error:

# # #                 print(
# # #                     f"[{self.agent_id}] "
# # #                     f"Crowd loop error: "
# # #                     f"{error}"
# # #                 )

# # #                 # Redis/network/other runtime
# # #                 # failure must not immediately
# # #                 # terminate the entire agent.

# # #                 await asyncio.sleep(2)

# # #         print(
# # #             f"[{self.agent_id}] "
# # #             f"Crowd processing loop stopped."
# # #         )


# # # # ============================================================
# # # # ENTRY POINT
# # # # ============================================================

# # # async def main():

# # #     agent = CrowdAgent()

# # #     await agent.run_forever()


# # # if __name__ == "__main__":

# # #     asyncio.run(main())













# # import asyncio
# # import json
# # import os
# # import uuid
# # from datetime import datetime, timezone
# # from typing import Any, Dict, List, Optional

# # from shared.agent.base_agent import BaseAgent
# # from shared.schemas.event_schema import (
# #     create_event,
# #     validate_event,
# # )


# # class CrowdAgent(BaseAgent):
# #     """
# #     Crowd analysis agent.

# #     Input:
# #         events.tracking

# #     Output:
# #         events.behavior

# #     Detects:
# #         - crowd.detected

# #     Important architecture rules:
# #         - Consumes canonical person.tracked events.
# #         - Produces canonical crowd.detected events.
# #         - Preserves upstream event/frame timestamps.
# #         - Preserves mode, trace_id, correlation_id and incident_id.
# #         - Includes source event lineage.
# #         - Keeps crowd state partitioned by camera.
# #         - Does not silently default missing camera IDs.
# #         - One malformed/bad message must not terminate the agent.

# #     IMPORTANT:
# #         This agent is stateful per camera.

# #         Therefore, in a horizontally scaled deployment, all events for the
# #         same camera MUST be routed to the same Crowd worker/partition.

# #         Redis consumer groups alone do not guarantee this affinity.
# #     """

# #     def __init__(self):
# #         super().__init__(
# #             agent_id=os.getenv(
# #                 "AGENT_ID",
# #                 "crowd-01",
# #             ),
# #             heartbeat_interval=int(
# #                 os.getenv(
# #                     "HEARTBEAT_INTERVAL",
# #                     "10",
# #                 )
# #             ),
# #         )

# #         self.input_stream = os.getenv(
# #             "CROWD_INPUT_STREAM",
# #             "events.tracking",
# #         )

# #         self.output_stream = os.getenv(
# #             "CROWD_OUTPUT_STREAM",
# #             "events.behavior",
# #         )

# #         self.group_name = os.getenv(
# #             "CROWD_GROUP",
# #             "crowd-workers",
# #         )

# #         self.consumer_name = os.getenv(
# #             "CROWD_CONSUMER",
# #             f"crowd-{uuid.uuid4().hex[:8]}",
# #         )

# #         self.crowd_threshold = self._positive_int(
# #             os.getenv(
# #                 "CROWD_THRESHOLD",
# #                 "5",
# #             ),
# #             "CROWD_THRESHOLD",
# #         )

# #         self.track_timeout = self._positive_float(
# #             os.getenv(
# #                 "TRACK_TIMEOUT_SECONDS",
# #                 "0.8",
# #             ),
# #             "TRACK_TIMEOUT_SECONDS",
# #         )

# #         # Number of consecutive observations required before a crowd
# #         # condition becomes active.
# #         #
# #         # Default = 1 preserves the old behavior while allowing future
# #         # persistence/hysteresis tuning.
# #         self.activation_observations = self._positive_int(
# #             os.getenv(
# #                 "CROWD_ACTIVATION_OBSERVATIONS",
# #                 "1",
# #             ),
# #             "CROWD_ACTIVATION_OBSERVATIONS",
# #         )

# #         # Optional number of consecutive below-threshold observations
# #         # required before clearing an active crowd.
# #         self.clear_observations = self._positive_int(
# #             os.getenv(
# #                 "CROWD_CLEAR_OBSERVATIONS",
# #                 "1",
# #             ),
# #             "CROWD_CLEAR_OBSERVATIONS",
# #         )

# #         # Per-camera:
# #         #
# #         # {
# #         #     "CAM01": {
# #         #         "track-1": datetime,
# #         #         "track-2": datetime,
# #         #     }
# #         # }
# #         #
# #         # Datetimes are event-time timestamps in UTC.
# #         self.camera_tracks: Dict[str, Dict[str, datetime]] = {}

# #         # Crowd state:
# #         #
# #         # {
# #         #     "CAM01": {
# #         #         "active": False,
# #         #         "above_threshold_observations": 0,
# #         #         "below_threshold_observations": 0,
# #         #         "last_event_timestamp": datetime | None,
# #         #     }
# #         # }
# #         self.crowd_state: Dict[str, Dict[str, Any]] = {}

# #         self.cleanup_task: Optional[asyncio.Task] = None

# #     # ================================================================
# #     # CONFIGURATION HELPERS
# #     # ================================================================

# #     @staticmethod
# #     def _positive_int(
# #         value: str,
# #         name: str,
# #     ) -> int:
# #         try:
# #             parsed = int(value)
# #         except (TypeError, ValueError) as error:
# #             raise ValueError(
# #                 f"{name} must be an integer"
# #             ) from error

# #         if parsed <= 0:
# #             raise ValueError(
# #                 f"{name} must be greater than 0"
# #             )

# #         return parsed

# #     @staticmethod
# #     def _positive_float(
# #         value: str,
# #         name: str,
# #     ) -> float:
# #         try:
# #             parsed = float(value)
# #         except (TypeError, ValueError) as error:
# #             raise ValueError(
# #                 f"{name} must be a number"
# #             ) from error

# #         if parsed <= 0:
# #             raise ValueError(
# #                 f"{name} must be greater than 0"
# #             )

# #         return parsed

# #     # ================================================================
# #     # TIMESTAMP HELPERS
# #     # ================================================================

# #     @staticmethod
# #     def _parse_timestamp(
# #         value: Any,
# #         field_name: str,
# #     ) -> datetime:
# #         """
# #         Parse an ISO timestamp and normalize it to UTC.

# #         Historical mode MUST use the event/frame timestamp rather than
# #         wall-clock/monotonic runtime.
# #         """
# #         if not isinstance(value, str) or not value.strip():
# #             raise ValueError(
# #                 f"{field_name} must be a non-empty ISO timestamp"
# #             )

# #         normalized = value.strip()

# #         if normalized.endswith("Z"):
# #             normalized = normalized[:-1] + "+00:00"

# #         try:
# #             parsed = datetime.fromisoformat(normalized)
# #         except ValueError as error:
# #             raise ValueError(
# #                 f"Invalid {field_name}: {value}"
# #             ) from error

# #         if parsed.tzinfo is None:
# #             parsed = parsed.replace(
# #                 tzinfo=timezone.utc
# #             )

# #         return parsed.astimezone(timezone.utc)

# #     def _event_timestamp(
# #         self,
# #         event: Dict[str, Any],
# #         data: Dict[str, Any],
# #     ) -> datetime:
# #         """
# #         Prefer frame_timestamp because tracking events normally carry
# #         the actual video-frame time.

# #         Fall back to event.timestamp.
# #         """
# #         frame_timestamp = data.get(
# #             "frame_timestamp"
# #         )

# #         if frame_timestamp:
# #             return self._parse_timestamp(
# #                 frame_timestamp,
# #                 "data.frame_timestamp",
# #             )

# #         return self._parse_timestamp(
# #             event.get("timestamp"),
# #             "event.timestamp",
# #         )

# #     # ================================================================
# #     # STATE HELPERS
# #     # ================================================================

# #     def _ensure_camera_state(
# #         self,
# #         camera_id: str,
# #     ) -> None:
# #         if camera_id not in self.camera_tracks:
# #             self.camera_tracks[camera_id] = {}

# #         if camera_id not in self.crowd_state:
# #             self.crowd_state[camera_id] = {
# #                 "active": False,
# #                 "above_threshold_observations": 0,
# #                 "below_threshold_observations": 0,
# #                 "last_event_timestamp": None,
# #             }

# #     def remove_expired_tracks(
# #         self,
# #         camera_id: str,
# #         now: datetime,
# #     ) -> None:
# #         tracks = self.camera_tracks.get(
# #             camera_id
# #         )

# #         if not tracks:
# #             return

# #         expired_tracks = [
# #             track_id
# #             for track_id, last_seen in tracks.items()
# #             if (
# #                 now - last_seen
# #             ).total_seconds()
# #             > self.track_timeout
# #         ]

# #         for track_id in expired_tracks:
# #             del tracks[track_id]

# #         if expired_tracks:
# #             print(
# #                 f"[{self.agent_id}] "
# #                 f"Camera {camera_id}: "
# #                 f"removed "
# #                 f"{len(expired_tracks)} "
# #                 f"expired track(s)"
# #             )

# #     def get_person_count(
# #         self,
# #         camera_id: str,
# #     ) -> int:
# #         return len(
# #             self.camera_tracks.get(
# #                 camera_id,
# #                 {},
# #             )
# #         )

# #     # ================================================================
# #     # SEVERITY
# #     # ================================================================

# #     def calculate_severity(
# #         self,
# #         person_count: int,
# #     ) -> str:
# #         if person_count >= 10:
# #             return "critical"

# #         if person_count >= 7:
# #             return "high"

# #         if person_count >= 5:
# #             return "medium"

# #         return "low"

# #     # ================================================================
# #     # CROWD STATE
# #     # ================================================================

# #     def update_crowd_state(
# #         self,
# #         camera_id: str,
# #         person_count: int,
# #     ) -> Dict[str, Any]:
# #         self._ensure_camera_state(
# #             camera_id
# #         )

# #         state = self.crowd_state[
# #             camera_id
# #         ]

# #         if person_count >= self.crowd_threshold:
# #             state[
# #                 "above_threshold_observations"
# #             ] += 1

# #             state[
# #                 "below_threshold_observations"
# #             ] = 0

# #             if (
# #                 not state["active"]
# #                 and
# #                 state[
# #                     "above_threshold_observations"
# #                 ]
# #                 >= self.activation_observations
# #             ):
# #                 state["active"] = True

# #         else:
# #             state[
# #                 "below_threshold_observations"
# #             ] += 1

# #             state[
# #                 "above_threshold_observations"
# #             ] = 0

# #             if (
# #                 state["active"]
# #                 and
# #                 state[
# #                     "below_threshold_observations"
# #                 ]
# #                 >= self.clear_observations
# #             ):
# #                 state["active"] = False

# #                 print(
# #                     f"[{self.agent_id}] "
# #                     f"Crowd cleared | "
# #                     f"Camera={camera_id} | "
# #                     f"Count={person_count}"
# #                 )

# #         return state

# #     # ================================================================
# #     # BUILD CROWD EVENT
# #     # ================================================================

# #     def build_crowd_event(
# #         self,
# #         source_event: Dict[str, Any],
# #         redis_id: str,
# #         camera_id: str,
# #         frame_id: Any,
# #         frame_timestamp: datetime,
# #         person_count: int,
# #         active_track_ids: List[str],
# #     ) -> Dict[str, Any]:
# #         source = source_event.get(
# #             "source",
# #             {}
# #         )

# #         context = source_event.get(
# #             "context",
# #             {}
# #         )

# #         severity = self.calculate_severity(
# #             person_count
# #         )

# #         event = create_event(
# #             event_type="crowd.detected",
# #             agent_id=self.agent_id,
# #             instance_id=self.instance_id,
# #             hostname=self.hostname,
# #             camera_id=camera_id,
# #             mode=context.get(
# #                 "mode",
# #                 "live",
# #             ),
# #             trace_id=context.get(
# #                 "trace_id"
# #             ),
# #             correlation_id=context.get(
# #                 "correlation_id"
# #             ),
# #             incident_id=context.get(
# #                 "incident_id"
# #             ),
# #             timestamp=frame_timestamp,
# #             data={
# #                 "frame_id": frame_id,
# #                 "frame_timestamp": frame_timestamp.isoformat(),
# #                 "person_count": person_count,

# #                 # IMPORTANT:
# #                 # This is retained for compatibility, but it is NOT
# #                 # physical crowd density. True density requires scene
# #                 # geometry/area calibration.
# #                 "density": float(
# #                     person_count
# #                 ),

# #                 "threshold": self.crowd_threshold,
# #                 "severity": severity,
# #                 "track_ids": active_track_ids,

# #                 # Lineage.
# #                 "source_event_id": source_event.get(
# #                     "event_id"
# #                 ),
# #                 "source_redis_id": redis_id,

# #                 # Useful provenance.
# #                 "source_agent_id": source.get(
# #                     "agent_id"
# #                 ),
# #                 "source_instance_id": source.get(
# #                     "instance_id"
# #                 ),
# #             },
# #         )

# #         return event

# #     # ================================================================
# #     # EMIT CROWD EVENT
# #     # ================================================================

# #     async def emit_crowd_event(
# #         self,
# #         source_event: Dict[str, Any],
# #         redis_id: str,
# #         camera_id: str,
# #         frame_id: Any,
# #         frame_timestamp: datetime,
# #         person_count: int,
# #     ) -> Optional[str]:
# #         self._ensure_camera_state(
# #             camera_id
# #         )

# #         state = self.crowd_state[
# #             camera_id
# #         ]

# #         # Do not emit repeated crowd.detected events while the
# #         # same crowd condition remains active.
# #         #
# #         # The event is emitted only on transition:
# #         # inactive -> active.
# #         if (
# #             state.get("above_threshold_observations", 0)
# #             < self.activation_observations
# #         ):
# #             return None

# #         if state.get(
# #             "event_emitted",
# #             False,
# #         ):
# #             return None

# #         active_track_ids = list(
# #             self.camera_tracks.get(
# #                 camera_id,
# #                 {},
# #             ).keys()
# #         )

# #         crowd_event = self.build_crowd_event(
# #             source_event=source_event,
# #             redis_id=redis_id,
# #             camera_id=camera_id,
# #             frame_id=frame_id,
# #             frame_timestamp=frame_timestamp,
# #             person_count=person_count,
# #             active_track_ids=active_track_ids,
# #         )

# #         # Validate before publishing.
# #         validate_event(
# #             crowd_event
# #         )

# #         # IMPORTANT:
# #         # Do not mark the condition as emitted until Redis publish
# #         # succeeds. Otherwise a publish failure could permanently
# #         # suppress the incident.
# #         output_id = await self.publish(
# #             self.output_stream,
# #             crowd_event,
# #         )

# #         state["event_emitted"] = True
# #         state["last_event_timestamp"] = frame_timestamp

# #         print(
# #             f"[{self.agent_id}] "
# #             f"CROWD DETECTED | "
# #             f"Camera={camera_id} | "
# #             f"Count={person_count} | "
# #             f"Threshold={self.crowd_threshold} | "
# #             f"Severity={crowd_event['data']['severity']} | "
# #             f"Tracks={active_track_ids} | "
# #             f"Redis={output_id}"
# #         )

# #         return output_id

# #     # ================================================================
# #     # PROCESS TRACKING EVENT
# #     # ================================================================

# #     async def process_tracking_event(
# #         self,
# #         redis_id: str,
# #         event: Dict[str, Any],
# #     ) -> None:
# #         # ------------------------------------------------------------
# #         # Canonical event validation
# #         # ------------------------------------------------------------

# #         validate_event(
# #             event
# #         )

# #         if event.get(
# #             "event_type"
# #         ) != "person.tracked":
# #             return

# #         # ------------------------------------------------------------
# #         # Camera
# #         # ------------------------------------------------------------

# #         camera = event.get(
# #             "camera"
# #         )

# #         if not isinstance(
# #             camera,
# #             dict,
# #         ):
# #             raise ValueError(
# #                 "person.tracked event missing camera object"
# #             )

# #         camera_id = camera.get(
# #             "camera_id"
# #         )

# #         if (
# #             not isinstance(
# #                 camera_id,
# #                 str,
# #             )
# #             or not camera_id.strip()
# #         ):
# #             raise ValueError(
# #                 "person.tracked event missing valid camera_id"
# #             )

# #         camera_id = camera_id.strip()

# #         # ------------------------------------------------------------
# #         # Data
# #         # ------------------------------------------------------------

# #         data = event.get(
# #             "data"
# #         )

# #         if not isinstance(
# #             data,
# #             dict,
# #         ):
# #             raise ValueError(
# #                 "person.tracked event data must be an object"
# #             )

# #         if "frame_id" not in data:
# #             raise ValueError(
# #                 "person.tracked event missing frame_id"
# #             )

# #         frame_id = data.get(
# #             "frame_id"
# #         )

# #         tracked_items = data.get(
# #             "tracks",
# #             [],
# #         )

# #         if not isinstance(
# #             tracked_items,
# #             list,
# #         ):
# #             raise ValueError(
# #                 "person.tracked tracks must be a list"
# #             )

# #         # ------------------------------------------------------------
# #         # Event time
# #         # ------------------------------------------------------------

# #         event_timestamp = self._event_timestamp(
# #             event,
# #             data,
# #         )

# #         self._ensure_camera_state(
# #             camera_id
# #         )

# #         # ------------------------------------------------------------
# #         # Update tracks
# #         # ------------------------------------------------------------

# #         for tracked_item in tracked_items:
# #             if not isinstance(
# #                 tracked_item,
# #                 dict,
# #             ):
# #                 continue

# #             track_id = tracked_item.get(
# #                 "track_id"
# #             )

# #             if track_id is None:
# #                 continue

# #             track_id = str(
# #                 track_id
# #             ).strip()

# #             if not track_id:
# #                 continue

# #             self.camera_tracks[
# #                 camera_id
# #             ][track_id] = event_timestamp

# #         # ------------------------------------------------------------
# #         # Remove stale tracks using event time.
# #         #
# #         # This works for both live and historical processing.
# #         # ------------------------------------------------------------

# #         self.remove_expired_tracks(
# #             camera_id,
# #             event_timestamp,
# #         )

# #         person_count = self.get_person_count(
# #             camera_id
# #         )

# #         active_track_ids = list(
# #             self.camera_tracks.get(
# #                 camera_id,
# #                 {},
# #             ).keys()
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Camera={camera_id} | "
# #             f"Time={event_timestamp.isoformat()} | "
# #             f"ActivePersons={person_count} | "
# #             f"Tracks={active_track_ids}"
# #         )

# #         # ------------------------------------------------------------
# #         # Update crowd state
# #         # ------------------------------------------------------------

# #         state = self.update_crowd_state(
# #             camera_id,
# #             person_count,
# #         )

# #         # ------------------------------------------------------------
# #         # Detect crowd transition
# #         # ------------------------------------------------------------

# #         if (
# #             person_count
# #             >= self.crowd_threshold
# #         ):
# #             # Emit only when state has transitioned into the active
# #             # crowd condition.
# #             if (
# #                 state.get("active", False)
# #                 and
# #                 not state.get(
# #                     "event_emitted",
# #                     False,
# #                 )
# #             ):
# #                 await self.emit_crowd_event(
# #                     source_event=event,
# #                     redis_id=redis_id,
# #                     camera_id=camera_id,
# #                     frame_id=frame_id,
# #                     frame_timestamp=event_timestamp,
# #                     person_count=person_count,
# #                 )

# #         else:
# #             # Once the crowd is cleared, allow a future crowd to emit
# #             # another event.
# #             if not state.get(
# #                 "active",
# #                 False,
# #             ):
# #                 state[
# #                     "event_emitted"
# #                 ] = False

# #     # ================================================================
# #     # BACKGROUND CLEANUP
# #     # ================================================================

# #     async def cleanup_loop(self):
# #         """
# #         Runtime cleanup loop.

# #         NOTE:
# #             Cleanup scheduling uses asyncio.sleep(), but expiration
# #             itself uses event timestamps stored in state.

# #             For live mode this normally follows current event time.
# #             Historical processing should primarily be driven by incoming
# #             event timestamps.
# #         """

# #         while self.running:
# #             try:
# #                 # We deliberately do not use time.monotonic() to decide
# #                 # whether a historical track is expired.

# #                 for camera_id in list(
# #                     self.camera_tracks.keys()
# #                 ):
# #                     tracks = self.camera_tracks.get(
# #                         camera_id
# #                     )

# #                     if not tracks:
# #                         continue

# #                     # Find the newest known event timestamp for this
# #                     # camera.
# #                     latest_timestamp = max(
# #                         tracks.values()
# #                     )

# #                     self.remove_expired_tracks(
# #                         camera_id,
# #                         latest_timestamp,
# #                     )

# #                     person_count = (
# #                         self.get_person_count(
# #                             camera_id
# #                         )
# #                     )

# #                     state = self.update_crowd_state(
# #                         camera_id,
# #                         person_count,
# #                     )

# #                     # If a crowd has cleared, allow a future crowd
# #                     # transition to emit again.
# #                     if not state.get(
# #                         "active",
# #                         False,
# #                     ):
# #                         state[
# #                             "event_emitted"
# #                         ] = False

# #             except asyncio.CancelledError:
# #                 raise

# #             except Exception as error:
# #                 # Cleanup failure MUST NOT terminate the Crowd Agent.
# #                 print(
# #                     f"[{self.agent_id}] "
# #                     f"Cleanup error: {error}"
# #                 )

# #             await asyncio.sleep(1)

# #     # ================================================================
# #     # REDIS GROUP
# #     # ================================================================

# #     async def on_start(self):
# #         """
# #         Create Redis consumer group and start cleanup.
# #         """

# #         try:
# #             await self.redis_client.xgroup_create(
# #                 name=self.input_stream,
# #                 groupname=self.group_name,
# #                 id="0",
# #                 mkstream=True,
# #             )

# #             print(
# #                 f"[{self.agent_id}] "
# #                 f"Created consumer group: "
# #                 f"{self.group_name}"
# #             )

# #         except Exception as error:
# #             if "BUSYGROUP" not in str(
# #                 error
# #             ):
# #                 raise

# #         self.cleanup_task = asyncio.create_task(
# #             self.cleanup_loop()
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Crowd agent ready."
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Input: {self.input_stream}"
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Output: {self.output_stream}"
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Crowd threshold: "
# #             f"{self.crowd_threshold}"
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Track timeout: "
# #             f"{self.track_timeout}s"
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Activation observations: "
# #             f"{self.activation_observations}"
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Clear observations: "
# #             f"{self.clear_observations}"
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Instance: {self.instance_id}"
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Hostname: {self.hostname}"
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Consumer: {self.consumer_name}"
# #         )

# #     # ================================================================
# #     # STOP
# #     # ================================================================

# #     async def on_stop(self):
# #         """
# #         Gracefully stop cleanup and clear in-memory state.
# #         """

# #         if self.cleanup_task:
# #             self.cleanup_task.cancel()

# #             try:
# #                 await self.cleanup_task

# #             except asyncio.CancelledError:
# #                 pass

# #             self.cleanup_task = None

# #         self.camera_tracks.clear()
# #         self.crowd_state.clear()

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Crowd state cleared."
# #         )

# #     # ================================================================
# #     # MAIN REDIS LOOP
# #     # ================================================================

# #     async def run(self):
# #         print(
# #             f"[{self.agent_id}] "
# #             f"Crowd processing loop started."
# #         )

# #         while self.running:
# #             try:
# #                 messages = await (
# #                     self.redis_client.xreadgroup(
# #                         groupname=self.group_name,
# #                         consumername=self.consumer_name,
# #                         streams={
# #                             self.input_stream: ">"
# #                         },
# #                         count=10,
# #                         block=5000,
# #                     )
# #                 )

# #                 if not messages:
# #                     continue

# #                 for _, stream_messages in messages:
# #                     for redis_id, fields in stream_messages:

# #                         try:
# #                             raw_event = fields.get(
# #                                 "event"
# #                             )

# #                             # ------------------------------------------------
# #                             # Missing event payload
# #                             # ------------------------------------------------

# #                             if not raw_event:
# #                                 print(
# #                                     f"[{self.agent_id}] "
# #                                     f"Missing event payload "
# #                                     f"for Redis message "
# #                                     f"{redis_id}"
# #                                 )

# #                                 # This is permanently malformed and cannot
# #                                 # be retried successfully.
# #                                 await self.redis_client.xack(
# #                                     self.input_stream,
# #                                     self.group_name,
# #                                     redis_id,
# #                                 )

# #                                 continue

# #                             # ------------------------------------------------
# #                             # JSON
# #                             # ------------------------------------------------

# #                             try:
# #                                 event = json.loads(
# #                                     raw_event
# #                                 )

# #                             except json.JSONDecodeError as error:
# #                                 print(
# #                                     f"[{self.agent_id}] "
# #                                     f"Invalid JSON "
# #                                     f"{redis_id}: "
# #                                     f"{error}"
# #                                 )

# #                                 # Poison message: ACK so it does not
# #                                 # continuously block the consumer.
# #                                 await self.redis_client.xack(
# #                                     self.input_stream,
# #                                     self.group_name,
# #                                     redis_id,
# #                                 )

# #                                 continue

# #                             if not isinstance(
# #                                 event,
# #                                 dict,
# #                             ):
# #                                 print(
# #                                     f"[{self.agent_id}] "
# #                                     f"Event must be a JSON object "
# #                                     f"{redis_id}"
# #                                 )

# #                                 await self.redis_client.xack(
# #                                     self.input_stream,
# #                                     self.group_name,
# #                                     redis_id,
# #                                 )

# #                                 continue

# #                             # ------------------------------------------------
# #                             # Event type filter
# #                             # ------------------------------------------------

# #                             if event.get(
# #                                 "event_type"
# #                             ) != "person.tracked":
# #                                 await self.redis_client.xack(
# #                                     self.input_stream,
# #                                     self.group_name,
# #                                     redis_id,
# #                                 )

# #                                 continue

# #                             # ------------------------------------------------
# #                             # Processing
# #                             # ------------------------------------------------

# #                             await self.process_tracking_event(
# #                                 redis_id,
# #                                 event,
# #                             )

# #                             # ------------------------------------------------
# #                             # ACK ONLY after successful processing.
# #                             # ------------------------------------------------

# #                             await self.redis_client.xack(
# #                                 self.input_stream,
# #                                 self.group_name,
# #                                 redis_id,
# #                             )

# #                         except asyncio.CancelledError:
# #                             raise

# #                         except Exception as error:
# #                             print(
# #                                 f"[{self.agent_id}] "
# #                                 f"Message processing error "
# #                                 f"{redis_id}: "
# #                                 f"{error}"
# #                             )

# #                             # IMPORTANT:
# #                             #
# #                             # Do NOT ACK unexpected processing failures.
# #                             #
# #                             # The message remains pending and will be
# #                             # recovered by the reliability layer that we
# #                             # will add later.
# #                             continue

# #             except asyncio.CancelledError:
# #                 raise

# #             except Exception as error:
# #                 print(
# #                     f"[{self.agent_id}] "
# #                     f"Crowd loop error: "
# #                     f"{error}"
# #                 )

# #                 # Redis/network/runtime failure must not immediately
# #                 # terminate the agent.
# #                 await asyncio.sleep(2)

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Crowd processing loop stopped."
# #         )


# # # ====================================================================
# # # ENTRY POINT
# # # ====================================================================

# # async def main():
# #     agent = CrowdAgent()
# #     await agent.run_forever()


# # if __name__ == "__main__":
# #     asyncio.run(main())























# """
# Crowd Agent
# ===========

# Consumes canonical ``person.tracked`` events and detects crowd conditions.

# Pipeline:

#     events.tracking
#           |
#           v
#       CrowdAgent
#           |
#           v
#     events.behavior
#           |
#           +--> crowd.detected

# Design principles:

# - Canonical event schema
# - Camera-scoped state isolation
# - Historical-mode timestamp correctness
# - Out-of-order event protection
# - No runtime/background mutation of event-time state
# - Trace/correlation/incident propagation
# - Source-event lineage
# - Per-message fault isolation
# - ACK only after successful processing
# - No silent camera fallback
# - Same-camera routing/affinity required for stateful workers

# Important:

# Crowd state is driven ONLY by incoming tracking observations.

# A background asyncio task must never fabricate new observations by
# calling update_crowd_state(). This is especially important for
# historical processing, where wall-clock time has no relationship to
# the footage timeline.
# """

# from __future__ import annotations

# import asyncio
# import json
# import math
# import os
# import uuid
# from datetime import datetime, timezone
# from typing import Any, Dict, List, Optional

# from shared.agent.base_agent import BaseAgent
# from shared.schemas.event_schema import create_event, validate_event


# class CrowdAgent(BaseAgent):
#     """
#     Stateful crowd analysis agent.

#     Input:
#         events.tracking

#     Output:
#         events.behavior

#     Detection:
#         - crowd.detected

#     State is partitioned by camera_id.
#     """

#     def __init__(self):
#         super().__init__(
#             agent_id=os.getenv(
#                 "AGENT_ID",
#                 "crowd-01",
#             ),
#             heartbeat_interval=int(
#                 os.getenv(
#                     "HEARTBEAT_INTERVAL",
#                     "10",
#                 ),
#             ),
#         )

#         self.input_stream = os.getenv(
#             "CROWD_INPUT_STREAM",
#             "events.tracking",
#         )

#         self.output_stream = os.getenv(
#             "CROWD_OUTPUT_STREAM",
#             "events.behavior",
#         )

#         self.group_name = os.getenv(
#             "CROWD_GROUP",
#             "crowd-workers",
#         )

#         self.consumer_name = os.getenv(
#             "CROWD_CONSUMER",
#             f"crowd-{uuid.uuid4().hex[:8]}",
#         )

#         self.crowd_threshold = self._positive_int(
#             os.getenv(
#                 "CROWD_THRESHOLD",
#                 "5",
#             ),
#             "CROWD_THRESHOLD",
#         )

#         self.track_timeout = self._positive_float(
#             os.getenv(
#                 "TRACK_TIMEOUT_SECONDS",
#                 "0.8",
#             ),
#             "TRACK_TIMEOUT_SECONDS",
#         )

#         self.activation_observations = self._positive_int(
#             os.getenv(
#                 "CROWD_ACTIVATION_OBSERVATIONS",
#                 "1",
#             ),
#             "CROWD_ACTIVATION_OBSERVATIONS",
#         )

#         self.clear_observations = self._positive_int(
#             os.getenv(
#                 "CROWD_CLEAR_OBSERVATIONS",
#                 "1",
#             ),
#             "CROWD_CLEAR_OBSERVATIONS",
#         )

#         # ------------------------------------------------------------
#         # Camera-scoped track state
#         #
#         # {
#         #     "CAM01": {
#         #         "track-1": datetime(...),
#         #         "track-2": datetime(...),
#         #     }
#         # }
#         # ------------------------------------------------------------

#         self.camera_tracks: Dict[
#             str,
#             Dict[str, datetime],
#         ] = {}

#         # ------------------------------------------------------------
#         # Camera-scoped crowd state
#         #
#         # {
#         #     "CAM01": {
#         #         "active": False,
#         #         "above_threshold_observations": 0,
#         #         "below_threshold_observations": 0,
#         #         "event_emitted": False,
#         #         "last_event_timestamp": datetime | None,
#         #     }
#         # }
#         # ------------------------------------------------------------

#         self.crowd_state: Dict[
#             str,
#             Dict[str, Any],
#         ] = {}

#     # ================================================================
#     # CONFIGURATION
#     # ================================================================

#     @staticmethod
#     def _positive_int(
#         value: str,
#         name: str,
#     ) -> int:
#         try:
#             parsed = int(value)
#         except (TypeError, ValueError) as error:
#             raise ValueError(
#                 f"{name} must be an integer"
#             ) from error

#         if parsed <= 0:
#             raise ValueError(
#                 f"{name} must be greater than 0"
#             )

#         return parsed

#     @staticmethod
#     def _positive_float(
#         value: str,
#         name: str,
#     ) -> float:
#         try:
#             parsed = float(value)
#         except (TypeError, ValueError) as error:
#             raise ValueError(
#                 f"{name} must be a number"
#             ) from error

#         if parsed <= 0:
#             raise ValueError(
#                 f"{name} must be greater than 0"
#             )

#         if not math.isfinite(parsed):
#             raise ValueError(
#                 f"{name} must be finite"
#             )

#         return parsed

#     # ================================================================
#     # TIMESTAMP
#     # ================================================================

#     @staticmethod
#     def _parse_timestamp(
#         value: Any,
#         field_name: str,
#     ) -> datetime:
#         """
#         Parse ISO timestamp and normalize to UTC.
#         """

#         if not isinstance(
#             value,
#             str,
#         ) or not value.strip():
#             raise ValueError(
#                 f"{field_name} must be a non-empty ISO timestamp"
#             )

#         normalized = value.strip()

#         if normalized.endswith("Z"):
#             normalized = (
#                 normalized[:-1] + "+00:00"
#             )

#         try:
#             parsed = datetime.fromisoformat(
#                 normalized
#             )
#         except ValueError as error:
#             raise ValueError(
#                 f"Invalid {field_name}: {value}"
#             ) from error

#         if parsed.tzinfo is None:
#             parsed = parsed.replace(
#                 tzinfo=timezone.utc
#             )

#         return parsed.astimezone(
#             timezone.utc
#         )

#     def _event_timestamp(
#         self,
#         event: Dict[str, Any],
#         data: Dict[str, Any],
#     ) -> datetime:
#         """
#         Prefer frame timestamp because it represents the actual
#         video-frame time.

#         Fallback:
#             event.timestamp
#         """

#         frame_timestamp = data.get(
#             "frame_timestamp"
#         )

#         if frame_timestamp:
#             return self._parse_timestamp(
#                 frame_timestamp,
#                 "data.frame_timestamp",
#             )

#         return self._parse_timestamp(
#             event.get("timestamp"),
#             "event.timestamp",
#         )

#     # ================================================================
#     # CAMERA STATE
#     # ================================================================

#     def _ensure_camera_state(
#         self,
#         camera_id: str,
#     ) -> None:
#         if camera_id not in self.camera_tracks:
#             self.camera_tracks[camera_id] = {}

#         if camera_id not in self.crowd_state:
#             self.crowd_state[camera_id] = {
#                 "active": False,
#                 "above_threshold_observations": 0,
#                 "below_threshold_observations": 0,
#                 "event_emitted": False,
#                 "last_event_timestamp": None,
#             }

#     # ================================================================
#     # TRACK CLEANUP
#     # ================================================================

#     def remove_expired_tracks(
#         self,
#         camera_id: str,
#         event_timestamp: datetime,
#     ) -> None:
#         """
#         Remove tracks that have not appeared within track_timeout.

#         IMPORTANT:

#         This function is called only when a NEW tracking observation
#         arrives.

#         It does not use wall-clock time.

#         Therefore it works correctly for both live and historical
#         processing.
#         """

#         tracks = self.camera_tracks.get(
#             camera_id
#         )

#         if not tracks:
#             return

#         expired_tracks: List[str] = []

#         for track_id, last_seen in tracks.items():
#             age = (
#                 event_timestamp - last_seen
#             ).total_seconds()

#             # If an older event arrives, do not treat it as evidence
#             # that the track disappeared.
#             if age < 0:
#                 continue

#             if age > self.track_timeout:
#                 expired_tracks.append(
#                     track_id
#                 )

#         for track_id in expired_tracks:
#             tracks.pop(
#                 track_id,
#                 None,
#             )

#         if expired_tracks:
#             print(
#                 f"[{self.agent_id}] "
#                 f"Expired tracks | "
#                 f"Camera={camera_id} | "
#                 f"Count={len(expired_tracks)}"
#             )

#     def get_person_count(
#         self,
#         camera_id: str,
#     ) -> int:
#         return len(
#             self.camera_tracks.get(
#                 camera_id,
#                 {},
#             )
#         )

#     # ================================================================
#     # SEVERITY
#     # ================================================================

#     def calculate_severity(
#         self,
#         person_count: int,
#     ) -> str:
#         if person_count >= 10:
#             return "critical"

#         if person_count >= 7:
#             return "high"

#         if person_count >= 5:
#             return "medium"

#         return "low"

#     # ================================================================
#     # CROWD STATE
#     # ================================================================

#     def update_crowd_state(
#         self,
#         camera_id: str,
#         person_count: int,
#     ) -> Dict[str, Any]:
#         """
#         Update crowd state using exactly ONE incoming observation.

#         This function must never be called from a periodic cleanup
#         task because each call represents a new observation.
#         """

#         self._ensure_camera_state(
#             camera_id
#         )

#         state = self.crowd_state[
#             camera_id
#         ]

#         if person_count >= self.crowd_threshold:
#             state[
#                 "above_threshold_observations"
#             ] += 1

#             state[
#                 "below_threshold_observations"
#             ] = 0

#             if (
#                 not state["active"]
#                 and state[
#                     "above_threshold_observations"
#                 ]
#                 >= self.activation_observations
#             ):
#                 state["active"] = True

#                 print(
#                     f"[{self.agent_id}] "
#                     f"Crowd condition ACTIVE | "
#                     f"Camera={camera_id} | "
#                     f"Count={person_count}"
#                 )

#         else:
#             state[
#                 "below_threshold_observations"
#             ] += 1

#             state[
#                 "above_threshold_observations"
#             ] = 0

#             if (
#                 state["active"]
#                 and state[
#                     "below_threshold_observations"
#                 ]
#                 >= self.clear_observations
#             ):
#                 state["active"] = False

#                 print(
#                     f"[{self.agent_id}] "
#                     f"Crowd condition CLEARED | "
#                     f"Camera={camera_id} | "
#                     f"Count={person_count}"
#                 )

#         return state

#     # ================================================================
#     # CROWD EVENT
#     # ================================================================

#     def build_crowd_event(
#         self,
#         source_event: Dict[str, Any],
#         redis_id: str,
#         camera_id: str,
#         frame_id: Any,
#         frame_timestamp: datetime,
#         person_count: int,
#         active_track_ids: List[str],
#     ) -> Dict[str, Any]:
#         source = source_event.get(
#             "source",
#             {},
#         )

#         context = source_event.get(
#             "context",
#             {},
#         )

#         if not isinstance(
#             source,
#             dict,
#         ):
#             source = {}

#         if not isinstance(
#             context,
#             dict,
#         ):
#             context = {}

#         severity = self.calculate_severity(
#             person_count
#         )

#         frame_timestamp_text = (
#             frame_timestamp.isoformat()
#         )

#         event = create_event(
#             event_type="crowd.detected",
#             agent_id=self.agent_id,
#             instance_id=self.instance_id,
#             hostname=self.hostname,
#             camera_id=camera_id,
#             mode=context.get(
#                 "mode",
#                 "live",
#             ),
#             trace_id=context.get(
#                 "trace_id"
#             ),
#             correlation_id=context.get(
#                 "correlation_id"
#             ),
#             incident_id=context.get(
#                 "incident_id"
#             ),
#             timestamp=frame_timestamp,
#             data={
#                 "frame_id": frame_id,
#                 "frame_timestamp": frame_timestamp_text,
#                 "person_count": person_count,

#                 # Compatibility field.
#                 #
#                 # This is NOT physical crowd density.
#                 # True density requires scene geometry/calibration.
#                 "density": float(
#                     person_count
#                 ),

#                 "threshold": self.crowd_threshold,
#                 "severity": severity,
#                 "track_ids": active_track_ids,

#                 # Source lineage.
#                 "source_event_id": source_event.get(
#                     "event_id"
#                 ),
#                 "source_redis_id": redis_id,

#                 # Provenance.
#                 "source_agent_id": source.get(
#                     "agent_id"
#                 ),
#                 "source_instance_id": source.get(
#                     "instance_id"
#                 ),
#             },
#         )

#         if not validate_event(event):
#             raise ValueError(
#                 "Generated crowd.detected event "
#                 "failed canonical validation."
#             )

#         return event

#     # ================================================================
#     # EMIT
#     # ================================================================

#     async def emit_crowd_event(
#         self,
#         source_event: Dict[str, Any],
#         redis_id: str,
#         camera_id: str,
#         frame_id: Any,
#         frame_timestamp: datetime,
#         person_count: int,
#     ) -> Optional[str]:
#         """
#         Emit exactly one crowd.detected event for the current
#         active crowd condition.

#         The event_emitted flag is updated ONLY after Redis publish
#         succeeds.
#         """

#         self._ensure_camera_state(
#             camera_id
#         )

#         state = self.crowd_state[
#             camera_id
#         ]

#         if not state.get(
#             "active",
#             False,
#         ):
#             return None

#         if state.get(
#             "event_emitted",
#             False,
#         ):
#             return None

#         active_track_ids = list(
#             self.camera_tracks.get(
#                 camera_id,
#                 {},
#             ).keys()
#         )

#         crowd_event = self.build_crowd_event(
#             source_event=source_event,
#             redis_id=redis_id,
#             camera_id=camera_id,
#             frame_id=frame_id,
#             frame_timestamp=frame_timestamp,
#             person_count=person_count,
#             active_track_ids=active_track_ids,
#         )

#         output_id = await self.publish(
#             self.output_stream,
#             crowd_event,
#         )

#         # IMPORTANT:
#         #
#         # Only mark emitted after Redis publish succeeds.
#         state["event_emitted"] = True
#         state[
#             "last_event_timestamp"
#         ] = frame_timestamp

#         print(
#             f"[{self.agent_id}] "
#             f"CROWD DETECTED | "
#             f"Camera={camera_id} | "
#             f"Count={person_count} | "
#             f"Threshold={self.crowd_threshold} | "
#             f"Severity={crowd_event['data']['severity']} | "
#             f"Tracks={active_track_ids} | "
#             f"Redis={output_id}"
#         )

#         return output_id

#     # ================================================================
#     # PROCESS TRACKING EVENT
#     # ================================================================

#     async def process_tracking_event(
#         self,
#         redis_id: str,
#         event: Dict[str, Any],
#     ) -> None:
#         """
#         Process one canonical person.tracked event.

#         State mutation is camera-scoped and event-time ordered.
#         """

#         if not validate_event(event):
#             raise ValueError(
#                 "Received event failed canonical validation."
#             )

#         if event.get(
#             "event_type"
#         ) != "person.tracked":
#             return

#         # ------------------------------------------------------------
#         # Camera
#         # ------------------------------------------------------------

#         camera = event.get(
#             "camera"
#         )

#         if not isinstance(
#             camera,
#             dict,
#         ):
#             raise ValueError(
#                 "person.tracked event missing camera object"
#             )

#         camera_id = camera.get(
#             "camera_id"
#         )

#         if (
#             not isinstance(
#                 camera_id,
#                 str,
#             )
#             or not camera_id.strip()
#         ):
#             raise ValueError(
#                 "person.tracked event missing valid camera_id"
#             )

#         camera_id = camera_id.strip()

#         # ------------------------------------------------------------
#         # Data
#         # ------------------------------------------------------------

#         data = event.get(
#             "data"
#         )

#         if not isinstance(
#             data,
#             dict,
#         ):
#             raise ValueError(
#                 "person.tracked event data must be an object"
#             )

#         if "frame_id" not in data:
#             raise ValueError(
#                 "person.tracked event missing frame_id"
#             )

#         frame_id = data.get(
#             "frame_id"
#         )

#         tracked_items = data.get(
#             "tracks",
#             [],
#         )

#         if not isinstance(
#             tracked_items,
#             list,
#         ):
#             raise ValueError(
#                 "person.tracked tracks must be a list"
#             )

#         # ------------------------------------------------------------
#         # Event timestamp
#         # ------------------------------------------------------------

#         event_timestamp = self._event_timestamp(
#             event,
#             data,
#         )

#         self._ensure_camera_state(
#             camera_id
#         )

#         state = self.crowd_state[
#             camera_id
#         ]

#         # ------------------------------------------------------------
#         # Out-of-order protection
#         # ------------------------------------------------------------

#         last_camera_timestamp = state.get(
#             "last_event_timestamp"
#         )

#         if (
#             isinstance(
#                 last_camera_timestamp,
#                 datetime,
#             )
#             and event_timestamp
#             < last_camera_timestamp
#         ):
#             print(
#                 f"[{self.agent_id}] "
#                 f"Ignoring out-of-order event | "
#                 f"Camera={camera_id} | "
#                 f"EventTime={event_timestamp.isoformat()} | "
#                 f"LastTime={last_camera_timestamp.isoformat()} | "
#                 f"Redis={redis_id}"
#             )

#             return

#         # ------------------------------------------------------------
#         # First remove tracks that disappeared before this observation.
#         # ------------------------------------------------------------

#         self.remove_expired_tracks(
#             camera_id=camera_id,
#             event_timestamp=event_timestamp,
#         )

#         # ------------------------------------------------------------
#         # Update current tracks.
#         # ------------------------------------------------------------

#         camera_tracks = self.camera_tracks[
#             camera_id
#         ]

#         for tracked_item in tracked_items:
#             if not isinstance(
#                 tracked_item,
#                 dict,
#             ):
#                 continue

#             track_id = tracked_item.get(
#                 "track_id"
#             )

#             if track_id is None:
#                 continue

#             track_id = str(
#                 track_id
#             ).strip()

#             if not track_id:
#                 continue

#             previous_timestamp = camera_tracks.get(
#                 track_id
#             )

#             # Never move a track backward in time.
#             if (
#                 previous_timestamp is not None
#                 and event_timestamp
#                 < previous_timestamp
#             ):
#                 continue

#             camera_tracks[
#                 track_id
#             ] = event_timestamp

#         # ------------------------------------------------------------
#         # Current camera state
#         # ------------------------------------------------------------

#         person_count = self.get_person_count(
#             camera_id
#         )

#         active_track_ids = list(
#             camera_tracks.keys()
#         )

#         print(
#             f"[{self.agent_id}] "
#             f"Camera={camera_id} | "
#             f"Time={event_timestamp.isoformat()} | "
#             f"ActivePersons={person_count} | "
#             f"Tracks={active_track_ids}"
#         )

#         # ------------------------------------------------------------
#         # One observation -> one state update.
#         # ------------------------------------------------------------

#         state = self.update_crowd_state(
#             camera_id=camera_id,
#             person_count=person_count,
#         )

#         # The camera's latest processed event timestamp advances only
#         # after the event has been accepted as current.
#         state[
#             "last_event_timestamp"
#         ] = event_timestamp

#         # ------------------------------------------------------------
#         # Crowd activation
#         # ------------------------------------------------------------

#         if (
#             person_count
#             >= self.crowd_threshold
#             and state.get(
#                 "active",
#                 False,
#             )
#             and not state.get(
#                 "event_emitted",
#                 False,
#             )
#         ):
#             await self.emit_crowd_event(
#                 source_event=event,
#                 redis_id=redis_id,
#                 camera_id=camera_id,
#                 frame_id=frame_id,
#                 frame_timestamp=event_timestamp,
#                 person_count=person_count,
#             )

#         # ------------------------------------------------------------
#         # Crowd cleared -> future crowd may emit again.
#         # ------------------------------------------------------------

#         elif not state.get(
#             "active",
#             False,
#         ):
#             state[
#                 "event_emitted"
#             ] = False

#     # ================================================================
#     # REDIS GROUP
#     # ================================================================

#     async def on_start(self):
#         """
#         Create Redis consumer group.

#         No background state-mutating cleanup task is started.

#         Event-time state is updated only when an actual tracking
#         observation arrives.
#         """

#         try:
#             await self.redis_client.xgroup_create(
#                 name=self.input_stream,
#                 groupname=self.group_name,
#                 id="0",
#                 mkstream=True,
#             )

#             print(
#                 f"[{self.agent_id}] "
#                 f"Created consumer group: "
#                 f"{self.group_name}"
#             )

#         except Exception as error:
#             if "BUSYGROUP" not in str(
#                 error
#             ):
#                 raise

#         print(
#             f"[{self.agent_id}] "
#             f"Crowd agent ready."
#         )

#         print(
#             f"[{self.agent_id}] "
#             f"Input: {self.input_stream}"
#         )

#         print(
#             f"[{self.agent_id}] "
#             f"Output: {self.output_stream}"
#         )

#         print(
#             f"[{self.agent_id}] "
#             f"Crowd threshold: "
#             f"{self.crowd_threshold}"
#         )

#         print(
#             f"[{self.agent_id}] "
#             f"Track timeout: "
#             f"{self.track_timeout}s"
#         )

#         print(
#             f"[{self.agent_id}] "
#             f"Activation observations: "
#             f"{self.activation_observations}"
#         )

#         print(
#             f"[{self.agent_id}] "
#             f"Clear observations: "
#             f"{self.clear_observations}"
#         )

#         print(
#             f"[{self.agent_id}] "
#             f"Instance: {self.instance_id}"
#         )

#         print(
#             f"[{self.agent_id}] "
#             f"Hostname: {self.hostname}"
#         )

#         print(
#             f"[{self.agent_id}] "
#             f"Consumer: {self.consumer_name}"
#         )

#     # ================================================================
#     # STOP
#     # ================================================================

#     async def on_stop(self):
#         """
#         Clear in-memory state on graceful shutdown.
#         """

#         self.camera_tracks.clear()
#         self.crowd_state.clear()

#         print(
#             f"[{self.agent_id}] "
#             f"Crowd state cleared."
#         )

#     # ================================================================
#     # MAIN REDIS LOOP
#     # ================================================================

#     async def run(self):
#         print(
#             f"[{self.agent_id}] "
#             f"Crowd processing loop started."
#         )

#         while self.running:
#             try:
#                 messages = await (
#                     self.redis_client.xreadgroup(
#                         groupname=self.group_name,
#                         consumername=self.consumer_name,
#                         streams={
#                             self.input_stream: ">"
#                         },
#                         count=10,
#                         block=5000,
#                     )
#                 )

#                 if not messages:
#                     continue

#                 for _, stream_messages in messages:
#                     for redis_id, fields in stream_messages:
#                         try:
#                             # ------------------------------------------------
#                             # Redis fields
#                             # ------------------------------------------------

#                             if not isinstance(
#                                 fields,
#                                 dict,
#                             ):
#                                 print(
#                                     f"[{self.agent_id}] "
#                                     f"Invalid Redis fields | "
#                                     f"Redis={redis_id}"
#                                 )

#                                 await self.redis_client.xack(
#                                     self.input_stream,
#                                     self.group_name,
#                                     redis_id,
#                                 )

#                                 continue

#                             raw_event = fields.get(
#                                 "event"
#                             )

#                             # ------------------------------------------------
#                             # Missing payload
#                             # ------------------------------------------------

#                             if not raw_event:
#                                 print(
#                                     f"[{self.agent_id}] "
#                                     f"Missing event payload | "
#                                     f"Redis={redis_id}"
#                                 )

#                                 await self.redis_client.xack(
#                                     self.input_stream,
#                                     self.group_name,
#                                     redis_id,
#                                 )

#                                 continue

#                             # ------------------------------------------------
#                             # JSON
#                             # ------------------------------------------------

#                             try:
#                                 event = json.loads(
#                                     raw_event
#                                 )
#                             except (
#                                 TypeError,
#                                 json.JSONDecodeError,
#                             ) as error:
#                                 print(
#                                     f"[{self.agent_id}] "
#                                     f"Invalid JSON | "
#                                     f"Redis={redis_id} | "
#                                     f"Error={error}"
#                                 )

#                                 # Permanent poison message.
#                                 await self.redis_client.xack(
#                                     self.input_stream,
#                                     self.group_name,
#                                     redis_id,
#                                 )

#                                 continue

#                             if not isinstance(
#                                 event,
#                                 dict,
#                             ):
#                                 print(
#                                     f"[{self.agent_id}] "
#                                     f"Event must be JSON object | "
#                                     f"Redis={redis_id}"
#                                 )

#                                 await self.redis_client.xack(
#                                     self.input_stream,
#                                     self.group_name,
#                                     redis_id,
#                                 )

#                                 continue

#                             # ------------------------------------------------
#                             # Event type
#                             # ------------------------------------------------

#                             if event.get(
#                                 "event_type"
#                             ) != "person.tracked":
#                                 await self.redis_client.xack(
#                                     self.input_stream,
#                                     self.group_name,
#                                     redis_id,
#                                 )

#                                 continue

#                             # ------------------------------------------------
#                             # Processing
#                             # ------------------------------------------------

#                             await self.process_tracking_event(
#                                 redis_id=redis_id,
#                                 event=event,
#                             )

#                             # ------------------------------------------------
#                             # ACK only after successful processing.
#                             # ------------------------------------------------

#                             await self.redis_client.xack(
#                                 self.input_stream,
#                                 self.group_name,
#                                 redis_id,
#                             )

#                         except asyncio.CancelledError:
#                             raise

#                         except Exception as error:
#                             print(
#                                 f"[{self.agent_id}] "
#                                 f"Message processing error | "
#                                 f"Redis={redis_id} | "
#                                 f"{type(error).__name__}: "
#                                 f"{error}"
#                             )

#                             # IMPORTANT:
#                             #
#                             # Do NOT ACK unexpected processing failures.
#                             #
#                             # The message remains pending and can be
#                             # recovered by the Redis reliability layer.

#                             continue

#             except asyncio.CancelledError:
#                 raise

#             except Exception as error:
#                 print(
#                     f"[{self.agent_id}] "
#                     f"Crowd loop error | "
#                     f"{type(error).__name__}: "
#                     f"{error}"
#                 )

#                 # Redis/network failure must not terminate the worker.
#                 await asyncio.sleep(2)

#         print(
#             f"[{self.agent_id}] "
#             f"Crowd processing loop stopped."
#         )


# # ====================================================================
# # ENTRY POINT
# # ====================================================================

# async def main():
#     agent = CrowdAgent()
#     await agent.run_forever()


# if __name__ == "__main__":
#     asyncio.run(main())
































"""
Crowd Agent

Consumes canonical ``person.tracked`` events and detects crowd conditions.

Pipeline:

    events.tracking
          |
          v
      CrowdAgent
          |
          v
    events.behavior
          |
          +--> crowd.detected

Design principles:
- Canonical event envelope
- Camera-scoped state isolation
- Historical-mode timestamp correctness
- Out-of-order event protection
- No runtime/background mutation of event-time state
- Trace/correlation/incident propagation
- Source-event lineage
- Per-message fault isolation
- ACK only after successful processing
- No silent camera fallback
- Same-camera routing/affinity required for stateful workers

Important:
Crowd state is driven ONLY by incoming tracking observations.

A background asyncio task must never fabricate observations by calling
update_crowd_state(). This is especially important for historical processing,
where wall-clock time has no relationship to the footage timeline.

NOTE:
Redis consumer groups do not inherently guarantee camera affinity. The
deployment topology must eventually partition/rout events so all events for
one camera are processed by the same state owner.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from shared.agent.base_agent import BaseAgent
from shared.schemas.event_schema import create_event, validate_event


class CrowdAgent(BaseAgent):
    """
    Stateful crowd analysis agent.

    Input:
        events.tracking

    Output:
        events.behavior

    Detection:
        crowd.detected

    State is partitioned by camera_id.

    This worker must eventually receive all events for a given camera
    through the same state owner.
    """

    INPUT_EVENT_TYPE = "person.tracked"
    OUTPUT_EVENT_TYPE = "crowd.detected"

    def __init__(self):
        super().__init__(
            agent_id=os.getenv("AGENT_ID", "crowd-01"),
            heartbeat_interval=int(
                os.getenv("HEARTBEAT_INTERVAL", "10")
            ),
        )

        self.input_stream = os.getenv(
            "CROWD_INPUT_STREAM",
            "events.tracking",
        )

        self.output_stream = os.getenv(
            "CROWD_OUTPUT_STREAM",
            "events.behavior",
        )

        self.group_name = os.getenv(
            "CROWD_GROUP",
            "crowd-workers",
        )

        self.consumer_name = os.getenv(
            "CROWD_CONSUMER",
            f"crowd-{uuid.uuid4().hex[:8]}",
        )

        self.crowd_threshold = self._positive_int(
            os.getenv("CROWD_THRESHOLD", "5"),
            "CROWD_THRESHOLD",
        )

        self.track_timeout = self._positive_float(
            os.getenv("TRACK_TIMEOUT_SECONDS", "0.8"),
            "TRACK_TIMEOUT_SECONDS",
        )

        self.activation_observations = self._positive_int(
            os.getenv(
                "CROWD_ACTIVATION_OBSERVATIONS",
                "1",
            ),
            "CROWD_ACTIVATION_OBSERVATIONS",
        )

        self.clear_observations = self._positive_int(
            os.getenv(
                "CROWD_CLEAR_OBSERVATIONS",
                "1",
            ),
            "CROWD_CLEAR_OBSERVATIONS",
        )

        # ------------------------------------------------------------
        # Camera-scoped track state
        #
        # {
        #     "CAM01": {
        #         "track-1": datetime(...),
        #         "track-2": datetime(...),
        #     }
        # }
        #
        # ------------------------------------------------------------

        self.camera_tracks: Dict[
            str,
            Dict[str, datetime],
        ] = {}

        # ------------------------------------------------------------
        # Camera-scoped crowd state
        #
        # {
        #     "CAM01": {
        #         "active": False,
        #         "above_threshold_observations": 0,
        #         "below_threshold_observations": 0,
        #         "event_emitted": False,
        #         "last_processed_timestamp": datetime | None,
        #         "last_event_timestamp": datetime | None,
        #     }
        # }
        #
        # last_processed_timestamp:
        #     Last accepted tracking observation for this camera.
        #
        # last_event_timestamp:
        #     Timestamp associated with the last emitted crowd event.
        #
        # Keeping these separate avoids coupling event emission with
        # event ordering.
        # ------------------------------------------------------------

        self.crowd_state: Dict[
            str,
            Dict[str, Any],
        ] = {}

    # ================================================================
    # CONFIGURATION
    # ================================================================

    @staticmethod
    def _positive_int(
        value: str,
        name: str,
    ) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"{name} must be an integer"
            ) from error

        if parsed <= 0:
            raise ValueError(
                f"{name} must be greater than 0"
            )

        return parsed

    @staticmethod
    def _positive_float(
        value: str,
        name: str,
    ) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"{name} must be a number"
            ) from error

        if parsed <= 0:
            raise ValueError(
                f"{name} must be greater than 0"
            )

        if not math.isfinite(parsed):
            raise ValueError(
                f"{name} must be finite"
            )

        return parsed

    # ================================================================
    # TIMESTAMP
    # ================================================================

    @staticmethod
    def _parse_timestamp(
        value: Any,
        field_name: str,
    ) -> datetime:
        """
        Parse an ISO timestamp and normalize it to UTC.

        Naive timestamps are rejected.

        The canonical event schema requires timezone-aware timestamps.
        Silently treating a naive timestamp as UTC can corrupt historical
        event ordering, so this agent deliberately rejects it.
        """

        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"{field_name} must be a non-empty ISO timestamp"
            )

        normalized = value.strip()

        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"

        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as error:
            raise ValueError(
                f"Invalid {field_name}: {value}"
            ) from error

        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError(
                f"{field_name} must be timezone-aware"
            )

        return parsed.astimezone(timezone.utc)

    def _event_timestamp(
        self,
        event: Dict[str, Any],
        data: Dict[str, Any],
    ) -> datetime:
        """
        Determine the timestamp representing the tracking observation.

        Prefer data.frame_timestamp because it represents the source
        frame's processing/observation time.

        Fall back to the canonical event timestamp.
        """

        frame_timestamp = data.get("frame_timestamp")

        if frame_timestamp is not None:
            return self._parse_timestamp(
                frame_timestamp,
                "data.frame_timestamp",
            )

        return self._parse_timestamp(
            event.get("timestamp"),
            "event.timestamp",
        )

    # ================================================================
    # CAMERA STATE
    # ================================================================

    def _ensure_camera_state(
        self,
        camera_id: str,
    ) -> None:
        """
        Create state for a camera without affecting any other camera.
        """

        if camera_id not in self.camera_tracks:
            self.camera_tracks[camera_id] = {}

        if camera_id not in self.crowd_state:
            self.crowd_state[camera_id] = {
                "active": False,
                "above_threshold_observations": 0,
                "below_threshold_observations": 0,
                "event_emitted": False,
                "last_processed_timestamp": None,
                "last_event_timestamp": None,
            }

    # ================================================================
    # TRACK CLEANUP
    # ================================================================

    def remove_expired_tracks(
        self,
        camera_id: str,
        event_timestamp: datetime,
    ) -> None:
        """
        Remove tracks that have not appeared within track_timeout.

        This function is called ONLY when a new tracking observation
        arrives.

        It uses event time, never wall-clock time.

        Therefore it works for:
        - live streams
        - historical footage
        - replayed footage
        """

        tracks = self.camera_tracks.get(camera_id)

        if not tracks:
            return

        expired_tracks: List[str] = []

        for track_id, last_seen in list(tracks.items()):
            age = (
                event_timestamp - last_seen
            ).total_seconds()

            # An older observation must never cause a track to expire.
            if age < 0:
                continue

            if age > self.track_timeout:
                expired_tracks.append(track_id)

        for track_id in expired_tracks:
            tracks.pop(track_id, None)

        if expired_tracks:
            print(
                f"[{self.agent_id}] "
                f"Expired tracks | "
                f"Camera={camera_id} | "
                f"Count={len(expired_tracks)}"
            )

    def get_person_count(
        self,
        camera_id: str,
    ) -> int:
        """
        Return the number of currently active tracks for one camera.
        """

        return len(
            self.camera_tracks.get(
                camera_id,
                {},
            )
        )

    # ================================================================
    # SEVERITY
    # ================================================================

    def calculate_severity(
        self,
        person_count: int,
    ) -> str:
        """
        Convert person count into crowd severity.

        These thresholds are currently configuration-independent
        MVP defaults and can later become camera-policy driven.
        """

        if person_count >= 10:
            return "critical"

        if person_count >= 7:
            return "high"

        if person_count >= 5:
            return "medium"

        return "low"

    # ================================================================
    # CROWD STATE
    # ================================================================

    def update_crowd_state(
        self,
        camera_id: str,
        person_count: int,
    ) -> Dict[str, Any]:
        """
        Update crowd state using exactly ONE accepted observation.

        This function must NEVER be called by a periodic cleanup task.
        Each invocation represents an actual tracking observation.
        """

        if person_count < 0:
            raise ValueError(
                "person_count cannot be negative"
            )

        self._ensure_camera_state(camera_id)

        state = self.crowd_state[camera_id]

        if person_count >= self.crowd_threshold:
            state["above_threshold_observations"] += 1
            state["below_threshold_observations"] = 0

            if (
                not state["active"]
                and state["above_threshold_observations"]
                >= self.activation_observations
            ):
                state["active"] = True

                print(
                    f"[{self.agent_id}] "
                    f"Crowd condition ACTIVE | "
                    f"Camera={camera_id} | "
                    f"Count={person_count}"
                )

        else:
            state["below_threshold_observations"] += 1
            state["above_threshold_observations"] = 0

            if (
                state["active"]
                and state["below_threshold_observations"]
                >= self.clear_observations
            ):
                state["active"] = False

                print(
                    f"[{self.agent_id}] "
                    f"Crowd condition CLEARED | "
                    f"Camera={camera_id} | "
                    f"Count={person_count}"
                )

        return state

    # ================================================================
    # EVENT BUILDING
    # ================================================================

    def build_crowd_event(
        self,
        source_event: Dict[str, Any],
        redis_id: str,
        camera_id: str,
        frame_id: Any,
        frame_timestamp: datetime,
        person_count: int,
        active_track_ids: List[str],
    ) -> Dict[str, Any]:
        """
        Build one canonical crowd.detected event.

        The specialized payload registry is intentionally not invoked
        here yet because the project's person/tracked and crowd
        contracts are still being aligned with all producers.
        """

        source = source_event.get("source", {})
        context = source_event.get("context", {})

        if not isinstance(source, dict):
            source = {}

        if not isinstance(context, dict):
            context = {}

        mode = context.get("mode", "live")

        if mode not in {"live", "historical"}:
            raise ValueError(
                f"Invalid event context mode: {mode!r}"
            )

        trace_id = context.get("trace_id")

        if not isinstance(trace_id, str) or not trace_id.strip():
            raise ValueError(
                "Source event context.trace_id is required"
            )

        severity = self.calculate_severity(
            person_count
        )

        frame_timestamp_text = (
            frame_timestamp.isoformat()
        )

        event = create_event(
            event_type=self.OUTPUT_EVENT_TYPE,
            agent_id=self.agent_id,
            instance_id=self.instance_id,
            hostname=self.hostname,
            camera_id=camera_id,
            mode=mode,
            trace_id=trace_id,
            correlation_id=context.get(
                "correlation_id"
            ),
            incident_id=context.get(
                "incident_id"
            ),
            timestamp=frame_timestamp,
            data={
                "frame_id": frame_id,
                "frame_timestamp": frame_timestamp_text,
                "person_count": person_count,

                # Compatibility field.
                #
                # This is NOT physical crowd density.
                # Physical density requires scene geometry,
                # calibration and/or an occupied-area estimate.
                "density": float(person_count),

                "threshold": self.crowd_threshold,
                "severity": severity,
                "track_ids": active_track_ids,

                # Source lineage.
                "source_event_id": source_event.get(
                    "event_id"
                ),
                "source_redis_id": redis_id,

                # Provenance.
                "source_agent_id": source.get(
                    "agent_id"
                ),
                "source_instance_id": source.get(
                    "instance_id"
                ),
            },
        )

        # Validate the canonical envelope.
        #
        # Specialized payload validation will be enabled once all
        # event contracts are aligned with their actual producers.
        validate_event(event)

        return event

    # ================================================================
    # EMIT
    # ================================================================

    async def emit_crowd_event(
        self,
        source_event: Dict[str, Any],
        redis_id: str,
        camera_id: str,
        frame_id: Any,
        frame_timestamp: datetime,
        person_count: int,
    ) -> Optional[str]:
        """
        Emit exactly one crowd.detected event for the current
        active crowd condition.

        event_emitted is changed ONLY after Redis publish succeeds.
        """

        self._ensure_camera_state(camera_id)

        state = self.crowd_state[camera_id]

        if not state.get("active", False):
            return None

        if state.get("event_emitted", False):
            return None

        active_track_ids = list(
            self.camera_tracks.get(
                camera_id,
                {},
            ).keys()
        )

        crowd_event = self.build_crowd_event(
            source_event=source_event,
            redis_id=redis_id,
            camera_id=camera_id,
            frame_id=frame_id,
            frame_timestamp=frame_timestamp,
            person_count=person_count,
            active_track_ids=active_track_ids,
        )

        # If publish fails, this exception propagates.
        #
        # The state remains event_emitted=False, allowing the pending
        # source message to be retried without permanently losing the
        # crowd event.
        output_id = await self.publish(
            self.output_stream,
            crowd_event,
        )

        # Mark emitted ONLY after successful Redis publish.
        state["event_emitted"] = True
        state["last_event_timestamp"] = frame_timestamp

        print(
            f"[{self.agent_id}] "
            f"CROWD DETECTED | "
            f"Camera={camera_id} | "
            f"Count={person_count} | "
            f"Threshold={self.crowd_threshold} | "
            f"Severity={crowd_event['data']['severity']} | "
            f"Tracks={active_track_ids} | "
            f"Redis={output_id}"
        )

        return output_id

    # ================================================================
    # TRACKING EVENT VALIDATION
    # ================================================================

    @staticmethod
    def _validate_tracking_payload(
        data: Dict[str, Any],
    ) -> None:
        """
        Validate the currently produced person.tracked payload.

        The current Tracker emits:
            frame_id
            frame_timestamp
            tracks[]

        Each track contains at minimum:
            track_id
            detection_id
            bbox
            confidence
            center

        Additional Tracker fields are allowed because the canonical
        specialized contract is still being aligned with producers.
        """

        if "frame_id" not in data:
            raise ValueError(
                "person.tracked event missing frame_id"
            )

        tracks = data.get("tracks", [])

        if not isinstance(tracks, list):
            raise ValueError(
                "person.tracked tracks must be a list"
            )

        for index, track in enumerate(tracks):
            if not isinstance(track, dict):
                raise ValueError(
                    f"Track at index {index} must be an object"
                )

            track_id = track.get("track_id")

            if (
                not isinstance(track_id, str)
                or not track_id.strip()
            ):
                raise ValueError(
                    f"Track at index {index} has invalid track_id"
                )

            bbox = track.get("bbox")

            if (
                not isinstance(bbox, list)
                or len(bbox) != 4
            ):
                raise ValueError(
                    f"Track {track_id!r} must contain "
                    f"a 4-value bbox"
                )

            for value in bbox:
                if (
                    not isinstance(value, (int, float))
                    or isinstance(value, bool)
                    or not math.isfinite(float(value))
                ):
                    raise ValueError(
                        f"Track {track_id!r} contains "
                        f"invalid bbox values"
                    )

            confidence = track.get("confidence")

            if (
                not isinstance(confidence, (int, float))
                or isinstance(confidence, bool)
                or not math.isfinite(float(confidence))
                or not 0 <= float(confidence) <= 1
            ):
                raise ValueError(
                    f"Track {track_id!r} has invalid confidence"
                )

            center = track.get("center")

            if (
                not isinstance(center, list)
                or len(center) != 2
            ):
                raise ValueError(
                    f"Track {track_id!r} must contain "
                    f"a 2-value center"
                )

            for value in center:
                if (
                    not isinstance(value, (int, float))
                    or isinstance(value, bool)
                    or not math.isfinite(float(value))
                ):
                    raise ValueError(
                        f"Track {track_id!r} contains "
                        f"invalid center values"
                    )

    # ================================================================
    # PROCESS TRACKING EVENT
    # ================================================================

    async def process_tracking_event(
        self,
        redis_id: str,
        event: Dict[str, Any],
    ) -> None:
        """
        Process one canonical person.tracked event.

        State mutation is camera-scoped and event-time ordered.
        """

        # Envelope validation.
        validate_event(event)

        if event.get("event_type") != self.INPUT_EVENT_TYPE:
            return

        # ------------------------------------------------------------
        # Camera
        # ------------------------------------------------------------

        camera = event.get("camera")

        if not isinstance(camera, dict):
            raise ValueError(
                "person.tracked event missing camera object"
            )

        camera_id = camera.get("camera_id")

        if (
            not isinstance(camera_id, str)
            or not camera_id.strip()
        ):
            raise ValueError(
                "person.tracked event missing valid camera_id"
            )

        camera_id = camera_id.strip()

        # ------------------------------------------------------------
        # Data
        # ------------------------------------------------------------

        data = event.get("data")

        if not isinstance(data, dict):
            raise ValueError(
                "person.tracked event data must be an object"
            )

        self._validate_tracking_payload(data)

        frame_id = data.get("frame_id")

        # ------------------------------------------------------------
        # Event timestamp
        # ------------------------------------------------------------

        event_timestamp = self._event_timestamp(
            event,
            data,
        )

        self._ensure_camera_state(camera_id)

        state = self.crowd_state[camera_id]

        # ------------------------------------------------------------
        # Out-of-order protection
        # ------------------------------------------------------------

        last_processed_timestamp = state.get(
            "last_processed_timestamp"
        )

        if (
            isinstance(
                last_processed_timestamp,
                datetime,
            )
            and event_timestamp < last_processed_timestamp
        ):
            print(
                f"[{self.agent_id}] "
                f"Ignoring out-of-order event | "
                f"Camera={camera_id} | "
                f"EventTime={event_timestamp.isoformat()} | "
                f"LastTime="
                f"{last_processed_timestamp.isoformat()} | "
                f"Redis={redis_id}"
            )

            # This is not a processing failure.
            # The event is valid but obsolete for this state owner.
            return

        # ------------------------------------------------------------
        # Remove tracks that disappeared before this observation.
        # ------------------------------------------------------------

        self.remove_expired_tracks(
            camera_id=camera_id,
            event_timestamp=event_timestamp,
        )

        # ------------------------------------------------------------
        # Update current tracks.
        # ------------------------------------------------------------

        camera_tracks = self.camera_tracks[camera_id]

        tracked_items = data.get(
            "tracks",
            [],
        )

        for tracked_item in tracked_items:
            track_id = str(
                tracked_item["track_id"]
            ).strip()

            previous_timestamp = camera_tracks.get(
                track_id
            )

            # Never move an individual track backward in time.
            if (
                previous_timestamp is not None
                and event_timestamp < previous_timestamp
            ):
                continue

            camera_tracks[track_id] = event_timestamp

        # ------------------------------------------------------------
        # Current camera state
        # ------------------------------------------------------------

        person_count = self.get_person_count(
            camera_id
        )

        active_track_ids = list(
            camera_tracks.keys()
        )

        print(
            f"[{self.agent_id}] "
            f"Camera={camera_id} | "
            f"Time={event_timestamp.isoformat()} | "
            f"ActivePersons={person_count} | "
            f"Tracks={active_track_ids}"
        )

        # ------------------------------------------------------------
        # One accepted observation -> one state update.
        # ------------------------------------------------------------

        state = self.update_crowd_state(
            camera_id=camera_id,
            person_count=person_count,
        )

        # Advance event-time cursor only after the observation has
        # successfully passed validation and state processing.
        state["last_processed_timestamp"] = event_timestamp

        # ------------------------------------------------------------
        # Crowd activation
        # ------------------------------------------------------------

        if (
            person_count >= self.crowd_threshold
            and state.get("active", False)
            and not state.get("event_emitted", False)
        ):
            await self.emit_crowd_event(
                source_event=event,
                redis_id=redis_id,
                camera_id=camera_id,
                frame_id=frame_id,
                frame_timestamp=event_timestamp,
                person_count=person_count,
            )

        # ------------------------------------------------------------
        # Crowd cleared
        #
        # Once inactive, the next future crowd condition is allowed
        # to emit another crowd.detected event.
        # ------------------------------------------------------------

        elif not state.get("active", False):
            state["event_emitted"] = False

    # ================================================================
    # REDIS GROUP
    # ================================================================

    async def on_start(self):
        """
        Create the Redis consumer group.

        No background task mutates event-time state.
        """

        try:
            await self.redis_client.xgroup_create(
                name=self.input_stream,
                groupname=self.group_name,
                id="0",
                mkstream=True,
            )

            print(
                f"[{self.agent_id}] "
                f"Created consumer group: "
                f"{self.group_name}"
            )

        except Exception as error:
            if "BUSYGROUP" not in str(error):
                raise

        print(
            f"[{self.agent_id}] "
            f"Crowd agent ready."
        )

        print(
            f"[{self.agent_id}] "
            f"Input: {self.input_stream}"
        )

        print(
            f"[{self.agent_id}] "
            f"Output: {self.output_stream}"
        )

        print(
            f"[{self.agent_id}] "
            f"Crowd threshold: "
            f"{self.crowd_threshold}"
        )

        print(
            f"[{self.agent_id}] "
            f"Track timeout: "
            f"{self.track_timeout}s"
        )

        print(
            f"[{self.agent_id}] "
            f"Activation observations: "
            f"{self.activation_observations}"
        )

        print(
            f"[{self.agent_id}] "
            f"Clear observations: "
            f"{self.clear_observations}"
        )

        print(
            f"[{self.agent_id}] "
            f"Instance: {self.instance_id}"
        )

        print(
            f"[{self.agent_id}] "
            f"Hostname: {self.hostname}"
        )

        print(
            f"[{self.agent_id}] "
            f"Consumer: {self.consumer_name}"
        )

    # ================================================================
    # STOP
    # ================================================================

    async def on_stop(self):
        """
        Clear in-memory state on graceful shutdown.

        State is intentionally not persisted here yet.
        Persistent/checkpointed state can be added later if required.
        """

        self.camera_tracks.clear()
        self.crowd_state.clear()

        print(
            f"[{self.agent_id}] "
            f"Crowd state cleared."
        )

    # ================================================================
    # REDIS MESSAGE ACK
    # ================================================================

    async def _ack(
        self,
        redis_id: str,
    ) -> None:
        """
        ACK one message.

        ACK failures are allowed to propagate because an ACK failure
        means Redis still considers the message pending.
        """

        await self.redis_client.xack(
            self.input_stream,
            self.group_name,
            redis_id,
        )

    # ================================================================
    # MAIN REDIS LOOP
    # ================================================================

    async def run(self):
        """
        Consume new tracking events.

        Reliability semantics:

        Permanent poison message:
            ACK it so it does not block the worker forever.

        Successful processing:
            ACK it.

        Unexpected processing failure:
            DO NOT ACK.
            Message remains pending for recovery.

        Redis/network failure:
            Keep the worker alive and retry.
        """

        print(
            f"[{self.agent_id}] "
            f"Crowd processing loop started."
        )

        while self.running:
            try:
                messages = await self.redis_client.xreadgroup(
                    groupname=self.group_name,
                    consumername=self.consumer_name,
                    streams={
                        self.input_stream: ">"
                    },
                    count=10,
                    block=5000,
                )

                if not messages:
                    continue

                for _, stream_messages in messages:
                    for redis_id, fields in stream_messages:
                        try:
                            # ------------------------------------------------
                            # Redis fields
                            # ------------------------------------------------

                            if not isinstance(fields, dict):
                                print(
                                    f"[{self.agent_id}] "
                                    f"Invalid Redis fields | "
                                    f"Redis={redis_id}"
                                )

                                await self._ack(redis_id)
                                continue

                            raw_event = fields.get("event")

                            # ------------------------------------------------
                            # Missing payload
                            # ------------------------------------------------

                            if not raw_event:
                                print(
                                    f"[{self.agent_id}] "
                                    f"Missing event payload | "
                                    f"Redis={redis_id}"
                                )

                                # Permanent poison message.
                                await self._ack(redis_id)
                                continue

                            # ------------------------------------------------
                            # JSON
                            # ------------------------------------------------

                            try:
                                event = json.loads(raw_event)

                            except (
                                TypeError,
                                json.JSONDecodeError,
                            ) as error:
                                print(
                                    f"[{self.agent_id}] "
                                    f"Invalid JSON | "
                                    f"Redis={redis_id} | "
                                    f"Error={error}"
                                )

                                # Permanent poison message.
                                await self._ack(redis_id)
                                continue

                            if not isinstance(event, dict):
                                print(
                                    f"[{self.agent_id}] "
                                    f"Event must be JSON object | "
                                    f"Redis={redis_id}"
                                )

                                # Permanent poison message.
                                await self._ack(redis_id)
                                continue

                            # ------------------------------------------------
                            # Event type
                            # ------------------------------------------------

                            if (
                                event.get("event_type")
                                != self.INPUT_EVENT_TYPE
                            ):
                                # The stream may eventually contain other
                                # tracking events. They are not this
                                # consumer's responsibility.
                                await self._ack(redis_id)
                                continue

                            # ------------------------------------------------
                            # Processing
                            # ------------------------------------------------

                            await self.process_tracking_event(
                                redis_id=redis_id,
                                event=event,
                            )

                            # ------------------------------------------------
                            # ACK only after successful processing.
                            # ------------------------------------------------

                            await self._ack(redis_id)

                        except asyncio.CancelledError:
                            raise

                        except ValueError as error:
                            # ------------------------------------------------
                            # ValueError here represents a permanently
                            # malformed/invalid event according to the
                            # current CrowdAgent contract.
                            #
                            # ACK prevents a poison message from being
                            # retried forever.
                            # ------------------------------------------------

                            print(
                                f"[{self.agent_id}] "
                                f"Permanent event validation error | "
                                f"Redis={redis_id} | "
                                f"{type(error).__name__}: "
                                f"{error}"
                            )

                            try:
                                await self._ack(redis_id)
                            except Exception as ack_error:
                                print(
                                    f"[{self.agent_id}] "
                                    f"ACK failed after permanent "
                                    f"validation error | "
                                    f"Redis={redis_id} | "
                                    f"{type(ack_error).__name__}: "
                                    f"{ack_error}"
                                )

                        except Exception as error:
                            print(
                                f"[{self.agent_id}] "
                                f"Message processing error | "
                                f"Redis={redis_id} | "
                                f"{type(error).__name__}: "
                                f"{error}"
                            )

                            # IMPORTANT:
                            #
                            # Do NOT ACK unexpected processing failures.
                            #
                            # The message remains pending and can later
                            # be recovered by the Redis reliability layer.
                            continue

            except asyncio.CancelledError:
                raise

            except Exception as error:
                print(
                    f"[{self.agent_id}] "
                    f"Crowd loop error | "
                    f"{type(error).__name__}: "
                    f"{error}"
                )

                # Redis/network failure must not terminate this worker.
                await asyncio.sleep(2)

        print(
            f"[{self.agent_id}] "
            f"Crowd processing loop stopped."
        )


# ====================================================================
# ENTRY POINT
# ====================================================================

async def main():
    agent = CrowdAgent()
    await agent.run_forever()


if __name__ == "__main__":
    asyncio.run(main())