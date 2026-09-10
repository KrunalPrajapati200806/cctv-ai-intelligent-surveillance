# # import asyncio
# # import json
# # import os
# # import uuid
# # import time

# # import redis.asyncio as redis


# # # ============================================================
# # # CONFIG
# # # ============================================================

# # REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
# # REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# # INPUT_STREAM = "events.detection"
# # OUTPUT_STREAM = "events.tracking"

# # GROUP_NAME = "tracker-workers"
# # CONSUMER_NAME = "tracker-01"

# # BBOX_DISTANCE_THRESHOLD = float(
# #     os.getenv("BBOX_DISTANCE_THRESHOLD", "160")
# # )

# # TRACK_TIMEOUT_SECONDS = float(
# #     os.getenv("TRACK_TIMEOUT_SECONDS", "0.8")
# # )


# # # ============================================================
# # # TRACK STATE
# # # ============================================================

# # tracks = {}


# # # ============================================================
# # # REDIS CONSUMER GROUP
# # # ============================================================

# # async def ensure_consumer_group(redis_client):

# #     try:

# #         await redis_client.xgroup_create(
# #             name=INPUT_STREAM,
# #             groupname=GROUP_NAME,
# #             id="0",
# #             mkstream=True,
# #         )

# #         print(
# #             f"Created consumer group: {GROUP_NAME}"
# #         )

# #     except redis.ResponseError as exc:

# #         if "BUSYGROUP" in str(exc):

# #             print(
# #                 f"Consumer group already exists: "
# #                 f"{GROUP_NAME}"
# #             )

# #         else:
# #             raise


# # # ============================================================
# # # BBOX CENTER
# # # ============================================================

# # def bbox_center(bbox):

# #     x1, y1, x2, y2 = bbox

# #     return (
# #         (x1 + x2) / 2,
# #         (y1 + y2) / 2,
# #     )


# # # ============================================================
# # # BBOX DISTANCE
# # # ============================================================

# # def bbox_distance(bbox1, bbox2):

# #     x1, y1 = bbox_center(bbox1)
# #     x2, y2 = bbox_center(bbox2)

# #     dx = x1 - x2
# #     dy = y1 - y2

# #     return (dx ** 2 + dy ** 2) ** 0.5


# # # ============================================================
# # # REMOVE EXPIRED TRACKS
# # # ============================================================

# # def remove_expired_tracks(camera_id, now):

# #     camera_tracks = tracks.get(camera_id)

# #     if not camera_tracks:
# #         return

# #     expired_track_ids = []

# #     for track_id, track in camera_tracks.items():

# #         age = now - track["last_seen"]

# #         if age > TRACK_TIMEOUT_SECONDS:

# #             expired_track_ids.append(track_id)

# #     for track_id in expired_track_ids:

# #         del camera_tracks[track_id]

# #         print(
# #             f"Expired track: {track_id} | "
# #             f"Camera={camera_id}"
# #         )

# #     if not camera_tracks:

# #         tracks.pop(camera_id, None)


# # # ============================================================
# # # FIND MATCHING TRACK
# # # ============================================================

# # def find_matching_track(camera_id, bbox):

# #     camera_tracks = tracks.get(camera_id, {})

# #     best_track_id = None
# #     best_distance = None

# #     for track_id, track in camera_tracks.items():

# #         distance = bbox_distance(
# #             bbox,
# #             track["bbox"],
# #         )

# #         if distance <= BBOX_DISTANCE_THRESHOLD:

# #             if (
# #                 best_distance is None
# #                 or distance < best_distance
# #             ):

# #                 best_track_id = track_id
# #                 best_distance = distance

# #     return best_track_id


# # # ============================================================
# # # CREATE OR UPDATE TRACK
# # # ============================================================

# # def get_or_create_track(
# #     camera_id,
# #     bbox,
# #     now,
# # ):

# #     # IMPORTANT:
# #     # Never directly assume tracks[camera_id] exists.

# #     camera_tracks = tracks.setdefault(
# #         camera_id,
# #         {},
# #     )

# #     matching_track_id = find_matching_track(
# #         camera_id,
# #         bbox,
# #     )

# #     if matching_track_id:

# #         camera_tracks[
# #             matching_track_id
# #         ]["bbox"] = bbox

# #         camera_tracks[
# #             matching_track_id
# #         ]["last_seen"] = now

# #         return matching_track_id

# #     track_id = f"track-{uuid.uuid4()}"

# #     camera_tracks[track_id] = {
# #         "bbox": bbox,
# #         "last_seen": now,
# #     }

# #     return track_id


# # # ============================================================
# # # PROCESS ONE DETECTION EVENT
# # # ============================================================

# # async def process_detection_event(
# #     redis_client,
# #     event,
# # ):

# #     # --------------------------------------------------------
# #     # CAMERA
# #     # --------------------------------------------------------

# #     camera = event.get("camera")

# #     if not isinstance(camera, dict):

# #         print(
# #             "Ignoring event with invalid camera"
# #         )

# #         return

# #     camera_id = camera.get("camera_id")

# #     if not camera_id:

# #         print(
# #             "Ignoring event without camera_id"
# #         )

# #         return

# #     # --------------------------------------------------------
# #     # DATA
# #     # --------------------------------------------------------

# #     data = event.get("data")

# #     if not isinstance(data, dict):

# #         print(
# #             f"Ignoring event with invalid data | "
# #             f"Camera={camera_id}"
# #         )

# #         return

# #     frame_id = data.get("frame_id")

# #     if not frame_id:

# #         print(
# #             f"Ignoring event without frame_id | "
# #             f"Camera={camera_id}"
# #         )

# #         return

# #     detections = data.get("detections")

# #     if not isinstance(detections, list):

# #         print(
# #             f"Ignoring event with invalid detections | "
# #             f"Camera={camera_id}"
# #         )

# #         return

# #     # --------------------------------------------------------
# #     # TIME
# #     # --------------------------------------------------------

# #     now = time.monotonic()

# #     # --------------------------------------------------------
# #     # REMOVE OLD TRACKS
# #     # --------------------------------------------------------

# #     remove_expired_tracks(
# #         camera_id,
# #         now,
# #     )

# #     # --------------------------------------------------------
# #     # TRACK PEOPLE
# #     # --------------------------------------------------------

# #     tracked_people = []

# #     for detection in detections:

# #         if not isinstance(detection, dict):
# #             continue

# #         detection_id = detection.get(
# #             "detection_id"
# #         )

# #         bbox = detection.get("bbox")

# #         confidence = detection.get(
# #             "confidence"
# #         )

# #         if not detection_id:

# #             print(
# #                 "Skipping detection without "
# #                 "detection_id"
# #             )

# #             continue

# #         if (
# #             not isinstance(bbox, list)
# #             or len(bbox) != 4
# #         ):

# #             print(
# #                 f"Skipping invalid bbox | "
# #                 f"Detection={detection_id}"
# #             )

# #             continue

# #         try:

# #             bbox = [
# #                 float(value)
# #                 for value in bbox
# #             ]

# #         except (
# #             TypeError,
# #             ValueError,
# #         ):

# #             print(
# #                 f"Skipping non-numeric bbox | "
# #                 f"Detection={detection_id}"
# #             )

# #             continue

# #         if not isinstance(
# #             confidence,
# #             (int, float),
# #         ):

# #             print(
# #                 f"Skipping invalid confidence | "
# #                 f"Detection={detection_id}"
# #             )

# #             continue

# #         # ----------------------------------------------------
# #         # TRACK
# #         # ----------------------------------------------------

# #         track_id = get_or_create_track(
# #             camera_id,
# #             bbox,
# #             now,
# #         )

# #         center = bbox_center(bbox)

# #         tracked_people.append(
# #             {
# #                 "track_id": track_id,
# #                 "detection_id": detection_id,
# #                 "bbox": bbox,
# #                 "confidence": float(
# #                     confidence
# #                 ),
# #                 "center": [
# #                     float(center[0]),
# #                     float(center[1]),
# #                 ],
# #             }
# #         )

# #         print(
# #             f"TRACK | "
# #             f"Camera={camera_id} | "
# #             f"Detection={detection_id} | "
# #             f"Track={track_id}"
# #         )

# #     # --------------------------------------------------------
# #     # NO PEOPLE
# #     # --------------------------------------------------------

# #     if not tracked_people:

# #         return

# #     # --------------------------------------------------------
# #     # CREATE TRACKING EVENT
# #     # --------------------------------------------------------

# #     tracked_event = {

# #         "event_id": str(
# #             uuid.uuid4()
# #         ),

# #         "event_type": "person.tracked",

# #         "version": "1.0",

# #         "timestamp": event.get(
# #             "timestamp"
# #         ),

# #         "source": {
# #             "agent_id": CONSUMER_NAME,
# #         },

# #         "camera": {
# #             "camera_id": camera_id,
# #         },

# #         "data": {

# #             "frame_id": frame_id,

# #             "tracks": tracked_people,
# #         },
# #     }

# #     # --------------------------------------------------------
# #     # PUBLISH
# #     # --------------------------------------------------------

# #     output_id = await redis_client.xadd(
# #         OUTPUT_STREAM,
# #         {
# #             "event": json.dumps(
# #                 tracked_event
# #             )
# #         },
# #     )

# #     print(
# #         f"TRACKED EVENT | "
# #         f"Camera={camera_id} | "
# #         f"Persons={len(tracked_people)} | "
# #         f"Redis={output_id}"
# #     )


# # # ============================================================
# # # MAIN
# # # ============================================================

# # async def main():

# #     redis_client = redis.Redis(

# #         host=REDIS_HOST,

# #         port=REDIS_PORT,

# #         decode_responses=True,

# #         socket_connect_timeout=5,

# #         socket_timeout=None,
# #     )

# #     await ensure_consumer_group(
# #         redis_client
# #     )

# #     print("=" * 60)

# #     print(
# #         f"Tracker started: {CONSUMER_NAME}"
# #     )

# #     print(
# #         f"Input stream: {INPUT_STREAM}"
# #     )

# #     print(
# #         f"Output stream: {OUTPUT_STREAM}"
# #     )

# #     print(
# #         f"BBOX distance threshold: "
# #         f"{BBOX_DISTANCE_THRESHOLD}"
# #     )

# #     print(
# #         f"Track timeout: "
# #         f"{TRACK_TIMEOUT_SECONDS}s"
# #     )

# #     print("=" * 60)

# #     try:

# #         while True:

# #             try:

# #                 messages = (
# #                     await redis_client.xreadgroup(

# #                         groupname=GROUP_NAME,

# #                         consumername=CONSUMER_NAME,

# #                         streams={
# #                             INPUT_STREAM: ">"
# #                         },

# #                         count=10,

# #                         block=5000,
# #                     )
# #                 )

# #             except redis.exceptions.TimeoutError:

# #                 print(
# #                     "Redis read timeout; "
# #                     "continuing..."
# #                 )

# #                 continue

# #             if not messages:
# #                 continue

# #             for (
# #                 stream_name,
# #                 stream_messages,
# #             ) in messages:

# #                 for (
# #                     redis_id,
# #                     fields,
# #                 ) in stream_messages:

# #                     try:

# #                         raw_event = fields.get(
# #                             "event"
# #                         )

# #                         if not raw_event:

# #                             print(
# #                                 f"Missing event "
# #                                 f"payload: "
# #                                 f"{redis_id}"
# #                             )

# #                             await redis_client.xack(
# #                                 INPUT_STREAM,
# #                                 GROUP_NAME,
# #                                 redis_id,
# #                             )

# #                             continue

# #                         event = json.loads(
# #                             raw_event
# #                         )

# #                         event_type = event.get(
# #                             "event_type"
# #                         )

# #                         if event_type != "person.detected":

# #                             print(
# #                                 f"Ignoring event type: "
# #                                 f"{event_type}"
# #                             )

# #                             await redis_client.xack(
# #                                 INPUT_STREAM,
# #                                 GROUP_NAME,
# #                                 redis_id,
# #                             )

# #                             continue

# #                         await process_detection_event(
# #                             redis_client,
# #                             event,
# #                         )

# #                         await redis_client.xack(
# #                             INPUT_STREAM,
# #                             GROUP_NAME,
# #                             redis_id,
# #                         )

# #                     except json.JSONDecodeError as exc:

# #                         print(
# #                             f"Invalid JSON | "
# #                             f"Redis={redis_id} | "
# #                             f"Error={exc}"
# #                         )

# #                         await redis_client.xack(
# #                             INPUT_STREAM,
# #                             GROUP_NAME,
# #                             redis_id,
# #                         )

# #                     except Exception as exc:

# #                         print(
# #                             f"ERROR processing "
# #                             f"{redis_id} | "
# #                             f"{type(exc).__name__}: "
# #                             f"{exc}"
# #                         )

# #                         # DO NOT ACK.
# #                         #
# #                         # The message remains pending
# #                         # for recovery.

# #     finally:

# #         await redis_client.aclose()

# #         print(
# #             "Tracker stopped."
# #         )


# # # ============================================================
# # # ENTRY POINT
# # # ============================================================

# # if __name__ == "__main__":

# #     asyncio.run(main())




















# import asyncio
# import math
# import os
# import uuid

# from shared.agent.base_agent import BaseAgent
# from shared.schemas.person_tracked import PersonTrackedData


# class PersonTrackerAgent(BaseAgent):
#     """
#     Person tracking agent.

#     events.detection

#     person.tracked

#     events.tracking
#     """

#     def __init__(self):
#         super().__init__(
#             agent_id=os.getenv(
#                 "AGENT_ID",
#                 "tracker-01",
#             ),
#             heartbeat_interval=int(
#                 os.getenv(
#                     "HEARTBEAT_INTERVAL",
#                     "10",
#                 )
#             ),
#         )

#         self.input_stream = "events.detection"
#         self.output_stream = "events.tracking"

#         self.group_name = os.getenv(
#             "TRACKER_GROUP",
#             "tracker-workers",
#         )

#         self.consumer_name = os.getenv(
#             "TRACKER_CONSUMER",
#             f"tracker-{uuid.uuid4().hex[:8]}",
#         )

#         self.distance_threshold = float(
#             os.getenv(
#                 "TRACK_DISTANCE_THRESHOLD",
#                 "160",
#             )
#         )

#         self.track_timeout = float(
#             os.getenv(
#                 "TRACK_TIMEOUT",
#                 "0.8",
#             )
#         )

#         self.tracks = {}

#     async def on_start(self):
#         if not self.redis_client:
#             raise RuntimeError(
#                 "Redis client is not initialized."
#             )

#         try:
#             await self.redis_client.xgroup_create(
#                 self.input_stream,
#                 self.group_name,
#                 id="0",
#                 mkstream=True,
#             )
#         except Exception as error:
#             if "BUSYGROUP" not in str(error):
#                 raise

#         print(
#             f"[{self.agent_id}] "
#             f"Tracker ready."
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
#             f"Consumer: {self.consumer_name}"
#         )

#     async def on_stop(self):
#         self.tracks.clear()

#         print(
#             f"[{self.agent_id}] "
#             f"Tracker state cleared."
#         )

#     def distance(self, center_a, center_b):
#         return math.sqrt(
#             (center_a[0] - center_b[0]) ** 2
#             + (center_a[1] - center_b[1]) ** 2
#         )

#     def cleanup_tracks(self, camera_id):
#         camera_tracks = self.tracks.get(
#             camera_id,
#             {},
#         )

#         current_time = asyncio.get_running_loop().time()

#         stale_ids = []

#         for track_id, track in camera_tracks.items():
#             if (
#                 current_time - track["last_seen"]
#                 > self.track_timeout
#             ):
#                 stale_ids.append(track_id)

#         for track_id in stale_ids:
#             del camera_tracks[track_id]

#     def update_tracks(
#         self,
#         camera_id,
#         detections,
#     ):
#         if camera_id not in self.tracks:
#             self.tracks[camera_id] = {}

#         camera_tracks = self.tracks[camera_id]

#         current_time = asyncio.get_running_loop().time()

#         matched_track_ids = set()
#         output_tracks = []

#         for detection in detections:

#             detection_id = detection.get(
#                 "detection_id"
#             )

#             bbox = detection.get("bbox")
#             confidence = detection.get(
#                 "confidence"
#             )

#             if not detection_id:
#                 continue

#             if (
#                 not isinstance(bbox, list)
#                 or len(bbox) != 4
#             ):
#                 continue

#             try:
#                 bbox = [
#                     float(value)
#                     for value in bbox
#                 ]

#                 confidence = float(
#                     confidence
#                 )

#             except (
#                 TypeError,
#                 ValueError,
#             ):
#                 continue

#             center = [
#                 (bbox[0] + bbox[2]) / 2,
#                 (bbox[1] + bbox[3]) / 2,
#             ]

#             best_track_id = None
#             best_distance = float("inf")

#             for track_id, track in camera_tracks.items():

#                 if track_id in matched_track_ids:
#                     continue

#                 distance = self.distance(
#                     center,
#                     track["center"],
#                 )

#                 if (
#                     distance
#                     < self.distance_threshold
#                     and distance < best_distance
#                 ):
#                     best_distance = distance
#                     best_track_id = track_id

#             if best_track_id is None:

#                 best_track_id = (
#                     f"track-"
#                     f"{uuid.uuid4().hex}"
#                 )

#                 camera_tracks[
#                     best_track_id
#                 ] = {
#                     "track_id":
#                         best_track_id,
#                     "center":
#                         center,
#                     "bbox":
#                         bbox,
#                     "last_seen":
#                         current_time,
#                 }

#             else:

#                 camera_tracks[
#                     best_track_id
#                 ]["center"] = center

#                 camera_tracks[
#                     best_track_id
#                 ]["bbox"] = bbox

#                 camera_tracks[
#                     best_track_id
#                 ]["last_seen"] = current_time

#             matched_track_ids.add(
#                 best_track_id
#             )

#             output_tracks.append(
#                 {
#                     "track_id":
#                         best_track_id,
#                     "detection_id":
#                         detection_id,
#                     "bbox":
#                         bbox,
#                     "confidence":
#                         confidence,
#                     "center":
#                         center,
#                 }
#             )

#         self.cleanup_tracks(
#             camera_id
#         )

#         return output_tracks

#     async def process_message(
#         self,
#         redis_id,
#         fields,
#     ):
#         try:
#             raw_event = fields.get(
#                 "event"
#             )

#             if not raw_event:
#                 await self.redis_client.xack(
#                     self.input_stream,
#                     self.group_name,
#                     redis_id,
#                 )
#                 return

#             import json

#             event = json.loads(raw_event)

#             if (
#                 event.get("event_type")
#                 != "person.detected"
#             ):
#                 await self.redis_client.xack(
#                     self.input_stream,
#                     self.group_name,
#                     redis_id,
#                 )
#                 return

#             source = event.get(
#                 "source",
#                 {},
#             )

#             camera = event.get(
#                 "camera",
#                 {},
#             )

#             data = event.get(
#                 "data",
#                 {},
#             )

#             camera_id = camera.get(
#                 "camera_id",
#                 "CAM01",
#             )

#             detections = data.get(
#                 "detections",
#                 [],
#             )

#             tracks = self.update_tracks(
#                 camera_id,
#                 detections,
#             )

#             tracked_data = PersonTrackedData(
#                 frame_id=str(
#                     data.get(
#                         "frame_id",
#                         redis_id,
#                     )
#                 ),
#                 tracks=tracks,
#             )

#             tracked_event = {
#                 "event_id": str(
#                     uuid.uuid4()
#                 ),
#                 "event_type":
#                     "person.tracked",
#                 "version": "1.0",
#                 "timestamp":
#                     self.now(),
#                 "source": {
#                     "agent_id":
#                         self.agent_id,
#                 },
#                 "camera": {
#                     "camera_id":
#                         camera_id,
#                 },
#                 "data":
#                     tracked_data.model_dump(),
#             }

#             output_id = await self.publish(
#                 self.output_stream,
#                 tracked_event,
#             )

#             print(
#                 f"TRACKED | "
#                 f"Camera={camera_id} | "
#                 f"Persons={len(tracks)} | "
#                 f"Redis={output_id}"
#             )

#             await self.redis_client.xack(
#                 self.input_stream,
#                 self.group_name,
#                 redis_id,
#             )

#         except asyncio.CancelledError:
#             raise

#         except Exception as error:

#             print(
#                 f"[{self.agent_id}] "
#                 f"Message processing error "
#                 f"for {redis_id}: {error}"
#             )

#             # IMPORTANT:
#             # Do NOT ACK failed messages.
#             #
#             # Redis keeps them pending so they
#             # can be recovered later.
#             raise

#     async def run(self):

#         print(
#             f"[{self.agent_id}] "
#             f"Tracking loop started."
#         )

#         while self.running:

#             try:

#                 messages = await self.redis_client.xreadgroup(
#                     groupname=self.group_name,
#                     consumername=self.consumer_name,
#                     streams={
#                         self.input_stream: ">"
#                     },
#                     count=10,
#                     block=5000,
#                 )

#                 if not messages:
#                     continue

#                 for stream_name, entries in messages:

#                     for redis_id, fields in entries:

#                         try:

#                             await self.process_message(
#                                 redis_id,
#                                 fields,
#                             )

#                         except Exception as error:

#                             print(
#                                 f"[{self.agent_id}] "
#                                 f"Failed message "
#                                 f"{redis_id}: "
#                                 f"{error}"
#                             )

#                             # Continue processing
#                             # other messages.
#                             #
#                             # One bad event must
#                             # NOT terminate tracker.

#             except asyncio.CancelledError:
#                 raise

#             except Exception as error:

#                 print(
#                     f"[{self.agent_id}] "
#                     f"Tracking loop error: "
#                     f"{error}"
#                 )

#                 await asyncio.sleep(2)

#         print(
#             f"[{self.agent_id}] "
#             f"Tracking loop stopped."
#         )


# async def main():
#     agent = PersonTrackerAgent()

#     await agent.run_forever()


# if __name__ == "__main__":
#     asyncio.run(main())














from __future__ import annotations

import asyncio
import json
import math
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from shared.agent.base_agent import BaseAgent
from shared.schemas.event_schema import create_event


class PersonTrackerAgent(BaseAgent):
    """
    Stateful person-tracking worker.

    Pipeline:

        events.detection
              |
              | person.detected
              v
        PersonTrackerAgent
              |
              | person.tracked
              v
        events.tracking

    IMPORTANT:

        Tracking state is maintained per camera.

        Therefore, in production, all events belonging to the
        same camera MUST be routed to the same tracker worker/
        partition. A generic Redis consumer group can otherwise
        distribute events from one camera across multiple workers
        and break tracking continuity.

    Current tracker implementation:

        Center-distance nearest-neighbour tracker.

    This is intentionally kept behind a simple internal interface
    so it can later be replaced by ByteTrack / BoT-SORT without
    changing the event contract.
    """

    INPUT_STREAM = "events.detection"
    OUTPUT_STREAM = "events.tracking"

    INPUT_EVENT_TYPE = "person.detected"
    OUTPUT_EVENT_TYPE = "person.tracked"

    def __init__(self):
        super().__init__(
            agent_id=os.getenv(
                "AGENT_ID",
                "tracker-01",
            ),
            heartbeat_interval=int(
                os.getenv(
                    "HEARTBEAT_INTERVAL",
                    "10",
                )
            ),
        )

        self.input_stream = self.INPUT_STREAM
        self.output_stream = self.OUTPUT_STREAM

        self.group_name = os.getenv(
            "TRACKER_GROUP",
            "tracker-workers",
        ).strip()

        self.consumer_name = os.getenv(
            "TRACKER_CONSUMER",
            f"tracker-{uuid.uuid4().hex[:8]}",
        ).strip()

        try:
            self.distance_threshold = float(
                os.getenv(
                    "TRACK_DISTANCE_THRESHOLD",
                    "160",
                )
            )
        except ValueError as error:
            raise ValueError(
                "TRACK_DISTANCE_THRESHOLD must be a valid number."
            ) from error

        if self.distance_threshold <= 0:
            raise ValueError(
                "TRACK_DISTANCE_THRESHOLD must be greater than 0."
            )

        try:
            self.track_timeout = float(
                os.getenv(
                    "TRACK_TIMEOUT",
                    "0.8",
                )
            )
        except ValueError as error:
            raise ValueError(
                "TRACK_TIMEOUT must be a valid number."
            ) from error

        if self.track_timeout <= 0:
            raise ValueError(
                "TRACK_TIMEOUT must be greater than 0."
            )

        # ---------------------------------------------------------
        # Per-camera tracking state.
        #
        # {
        #     camera_id: {
        #         track_id: {
        #             center: [x, y],
        #             bbox: [x1, y1, x2, y2],
        #             last_seen_event_time: datetime,
        #             last_seen_runtime: float,
        #             age: int,
        #         }
        #     }
        # }
        # ---------------------------------------------------------

        self.tracks: dict[
            str,
            dict[str, dict[str, Any]],
        ] = {}

        print(
            f"[{self.agent_id}] "
            f"Initialized tracker."
        )

        print(
            f"[{self.agent_id}] "
            f"Consumer: {self.consumer_name}"
        )

        print(
            f"[{self.agent_id}] "
            f"Group: {self.group_name}"
        )

    # =========================================================
    # Lifecycle
    # =========================================================

    async def on_start(self):
        if not self.redis_client:
            raise RuntimeError(
                "Redis client is not initialized."
            )

        try:
            await self.redis_client.xgroup_create(
                self.input_stream,
                self.group_name,
                id="0",
                mkstream=True,
            )

        except Exception as error:
            if "BUSYGROUP" not in str(error):
                raise

        print(
            f"[{self.agent_id}] "
            f"Tracker ready."
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
            f"Camera-affine state tracking enabled."
        )

    async def on_stop(self):
        self.tracks.clear()

        print(
            f"[{self.agent_id}] "
            f"Tracker state cleared."
        )

    # =========================================================
    # Geometry
    # =========================================================

    @staticmethod
    def distance(
        center_a: list[float],
        center_b: list[float],
    ) -> float:
        return math.sqrt(
            (center_a[0] - center_b[0]) ** 2
            + (center_a[1] - center_b[1]) ** 2
        )

    @staticmethod
    def bbox_center(
        bbox: list[float],
    ) -> list[float]:
        return [
            (bbox[0] + bbox[2]) / 2.0,
            (bbox[1] + bbox[3]) / 2.0,
        ]

    # =========================================================
    # Timestamp handling
    # =========================================================

    @staticmethod
    def _parse_timestamp(
        value: Any,
    ) -> datetime | None:
        """
        Parse an event timestamp into timezone-aware UTC.

        The tracker must use event time rather than process/runtime
        time so that historical footage remains temporally correct.
        """

        if isinstance(value, datetime):
            timestamp = value

        elif isinstance(value, str):
            text = value.strip()

            if not text:
                return None

            try:
                timestamp = datetime.fromisoformat(
                    text.replace(
                        "Z",
                        "+00:00",
                    )
                )
            except ValueError:
                return None

        else:
            return None

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(
                tzinfo=timezone.utc
            )

        return timestamp.astimezone(
            timezone.utc
        )

    # =========================================================
    # Track cleanup
    # =========================================================

    def cleanup_tracks(
        self,
        camera_id: str,
        event_timestamp: datetime,
    ):
        """
        Remove tracks that have not been seen within TRACK_TIMEOUT.

        Uses event timestamps rather than asyncio monotonic time.

        This is important for:

            live mode
            historical mode
            replay
            deterministic testing
        """

        camera_tracks = self.tracks.get(
            camera_id
        )

        if not camera_tracks:
            return

        stale_ids: list[str] = []

        for track_id, track in camera_tracks.items():
            last_seen = track.get(
                "last_seen_event_time"
            )

            if not isinstance(
                last_seen,
                datetime,
            ):
                stale_ids.append(track_id)
                continue

            elapsed = (
                event_timestamp - last_seen
            ).total_seconds()

            # If events arrive out of chronological order,
            # do not delete a track merely because the current
            # event timestamp is older.
            if elapsed >= self.track_timeout:
                stale_ids.append(track_id)

        for track_id in stale_ids:
            camera_tracks.pop(
                track_id,
                None,
            )

        if not camera_tracks:
            self.tracks.pop(
                camera_id,
                None,
            )

    # =========================================================
    # Tracking
    # =========================================================

    def update_tracks(
        self,
        camera_id: str,
        detections: list[dict[str, Any]],
        event_timestamp: datetime,
    ) -> list[dict[str, Any]]:
        """
        Update tracks for one camera.

        IMPORTANT:

            This function assumes all events for camera_id are
            processed by the same tracker worker.

        The matching strategy is:

            detection -> nearest unmatched existing track

        If no track is close enough, a new track is created.
        """

        if camera_id not in self.tracks:
            self.tracks[camera_id] = {}

        camera_tracks = self.tracks[camera_id]

        self.cleanup_tracks(
            camera_id,
            event_timestamp,
        )

        camera_tracks = self.tracks.setdefault(
            camera_id,
            {},
        )

        matched_track_ids: set[str] = set()

        output_tracks: list[dict[str, Any]] = []

        for detection in detections:
            if not isinstance(
                detection,
                dict,
            ):
                continue

            detection_id = detection.get(
                "detection_id"
            )

            bbox = detection.get(
                "bbox"
            )

            confidence = detection.get(
                "confidence"
            )

            if not detection_id:
                continue

            if (
                not isinstance(
                    bbox,
                    list,
                )
                or len(bbox) != 4
            ):
                continue

            try:
                bbox = [
                    float(value)
                    for value in bbox
                ]

                confidence = float(
                    confidence
                )

            except (
                TypeError,
                ValueError,
            ):
                continue

            x1, y1, x2, y2 = bbox

            if x2 < x1 or y2 < y1:
                continue

            center = self.bbox_center(
                bbox
            )

            best_track_id: str | None = None
            best_distance = float("inf")

            for (
                track_id,
                track,
            ) in camera_tracks.items():

                if track_id in matched_track_ids:
                    continue

                previous_center = track.get(
                    "center"
                )

                if (
                    not isinstance(
                        previous_center,
                        list,
                    )
                    or len(previous_center) != 2
                ):
                    continue

                candidate_distance = self.distance(
                    center,
                    previous_center,
                )

                if (
                    candidate_distance
                    <= self.distance_threshold
                    and candidate_distance
                    < best_distance
                ):
                    best_distance = candidate_distance
                    best_track_id = track_id

            # -------------------------------------------------
            # Create new track
            # -------------------------------------------------

            if best_track_id is None:
                best_track_id = (
                    f"track-"
                    f"{uuid.uuid4().hex}"
                )

                camera_tracks[
                    best_track_id
                ] = {
                    "track_id": best_track_id,
                    "center": center,
                    "bbox": bbox,
                    "last_seen_event_time": (
                        event_timestamp
                    ),
                    "age": 1,
                }

            # -------------------------------------------------
            # Update existing track
            # -------------------------------------------------

            else:
                track = camera_tracks[
                    best_track_id
                ]

                track["center"] = center
                track["bbox"] = bbox
                track[
                    "last_seen_event_time"
                ] = event_timestamp

                track["age"] = (
                    int(
                        track.get(
                            "age",
                            0,
                        )
                    )
                    + 1
                )

            matched_track_ids.add(
                best_track_id
            )

            output_tracks.append(
                {
                    "track_id": best_track_id,
                    "detection_id": detection_id,
                    "class": detection.get(
                        "class",
                        "person",
                    ),
                    "class_id": detection.get(
                        "class_id",
                        0,
                    ),
                    "bbox": bbox,
                    "confidence": confidence,
                    "center": center,
                    "match_distance": (
                        None
                        if best_distance == float("inf")
                        else best_distance
                    ),
                    "age": camera_tracks[
                        best_track_id
                    ]["age"],
                }
            )

        return output_tracks

    # =========================================================
    # Event validation
    # =========================================================

    @staticmethod
    def _extract_event(
        raw_event: str,
    ) -> dict[str, Any]:
        try:
            event = json.loads(
                raw_event
            )
        except json.JSONDecodeError as error:
            raise ValueError(
                f"Invalid event JSON: {error}"
            ) from error

        if not isinstance(
            event,
            dict,
        ):
            raise ValueError(
                "Event must be a JSON object."
            )

        return event

    @staticmethod
    def _require_camera_id(
        event: dict[str, Any],
    ) -> str:
        camera = event.get(
            "camera"
        )

        if not isinstance(
            camera,
            dict,
        ):
            raise ValueError(
                "Event is missing camera object."
            )

        camera_id = camera.get(
            "camera_id"
        )

        if not isinstance(
            camera_id,
            str,
        ):
            raise ValueError(
                "Event is missing camera.camera_id."
            )

        camera_id = camera_id.strip()

        if not camera_id:
            raise ValueError(
                "camera.camera_id cannot be empty."
            )

        return camera_id

    # =========================================================
    # Message processing
    # =========================================================

    async def process_message(
        self,
        redis_id: str,
        fields: dict[str, Any],
    ):
        try:
            raw_event = fields.get(
                "event"
            )

            if not raw_event:
                raise ValueError(
                    "Redis message is missing 'event' field."
                )

            event = self._extract_event(
                raw_event
            )

            event_type = event.get(
                "event_type"
            )

            if event_type != self.INPUT_EVENT_TYPE:
                # This worker only owns person.detected.
                await self.redis_client.xack(
                    self.input_stream,
                    self.group_name,
                    redis_id,
                )

                return

            # -------------------------------------------------
            # Required canonical event structures
            # -------------------------------------------------

            source = event.get(
                "source"
            )

            context = event.get(
                "context"
            )

            data = event.get(
                "data"
            )

            if not isinstance(
                source,
                dict,
            ):
                raise ValueError(
                    "Input event is missing source."
                )

            if not isinstance(
                context,
                dict,
            ):
                raise ValueError(
                    "Input event is missing context."
                )

            if not isinstance(
                data,
                dict,
            ):
                raise ValueError(
                    "Input event is missing data."
                )

            camera_id = self._require_camera_id(
                event
            )

            # -------------------------------------------------
            # Preserve event time
            # -------------------------------------------------

            event_timestamp = self._parse_timestamp(
                event.get("timestamp")
            )

            if event_timestamp is None:
                raise ValueError(
                    "Input event contains an invalid timestamp."
                )

            # -------------------------------------------------
            # Extract detections
            # -------------------------------------------------

            detections = data.get(
                "detections",
                [],
            )

            if not isinstance(
                detections,
                list,
            ):
                raise ValueError(
                    "data.detections must be a list."
                )

            # -------------------------------------------------
            # Update camera-local tracking state
            # -------------------------------------------------

            tracks = self.update_tracks(
                camera_id=camera_id,
                detections=detections,
                event_timestamp=event_timestamp,
            )

            # -------------------------------------------------
            # Preserve lineage
            # -------------------------------------------------

            source_event_id = event.get(
                "event_id"
            )

            if not source_event_id:
                raise ValueError(
                    "Input event is missing event_id."
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

            mode = context.get(
                "mode",
                "live",
            )

            if mode not in {
                "live",
                "historical",
            }:
                raise ValueError(
                    f"Unsupported event mode: {mode}"
                )

            # -------------------------------------------------
            # Build canonical tracking event
            # -------------------------------------------------

            tracked_event = create_event(
                event_type=self.OUTPUT_EVENT_TYPE,
                agent_id=self.agent_id,
                instance_id=self.instance_id,
                hostname=self.hostname,
                camera_id=camera_id,
                mode=mode,
                timestamp=event_timestamp,
                trace_id=trace_id,
                correlation_id=correlation_id,
                incident_id=incident_id,
                data={
                    "source_event_id": source_event_id,
                    "source_redis_id": redis_id,
                    "frame_id": data.get(
                        "frame_id"
                    ),
                    "frame_timestamp": data.get(
                        "frame_timestamp"
                    ),
                    "detection_count": len(
                        detections
                    ),
                    "track_count": len(
                        tracks
                    ),
                    "tracks": tracks,
                    "tracker": {
                        "type": "center-distance",
                        "distance_threshold": (
                            self.distance_threshold
                        ),
                        "track_timeout": (
                            self.track_timeout
                        ),
                    },
                },
            )

            # -------------------------------------------------
            # Publish downstream event
            # -------------------------------------------------

            output_id = await self.publish(
                self.output_stream,
                tracked_event,
            )

            print(
                f"TRACKED | "
                f"Camera={camera_id} | "
                f"Frame={data.get('frame_id')} | "
                f"Persons={len(tracks)} | "
                f"Redis={output_id} | "
                f"Event={tracked_event.event_id}"
            )

            # -------------------------------------------------
            # ACK only after successful publish
            # -------------------------------------------------

            await self.redis_client.xack(
                self.input_stream,
                self.group_name,
                redis_id,
            )

        except asyncio.CancelledError:
            raise

        except Exception as error:
            print(
                f"[{self.agent_id}] "
                f"Message processing error "
                f"for {redis_id}: "
                f"{type(error).__name__}: {error}"
            )

            # IMPORTANT:
            #
            # Do NOT ACK failed messages.
            #
            # Redis keeps them pending so the future reliability
            # layer can recover/retry/DLQ them.
            #
            # The exception is deliberately re-raised so the
            # current message remains unacknowledged.
            raise

    # =========================================================
    # Main consumer loop
    # =========================================================

    async def run(self):
        if not self.redis_client:
            raise RuntimeError(
                "Redis client is not initialized."
            )

        print(
            f"[{self.agent_id}] "
            f"Tracking loop started."
        )

        while self.running:
            try:
                messages = (
                    await self.redis_client.xreadgroup(
                        groupname=self.group_name,
                        consumername=self.consumer_name,
                        streams={
                            self.input_stream: ">"
                        },
                        count=10,
                        block=5000,
                    )
                )

                if not messages:
                    continue

                for (
                    stream_name,
                    entries,
                ) in messages:

                    for (
                        redis_id,
                        fields,
                    ) in entries:

                        try:
                            await self.process_message(
                                redis_id,
                                fields,
                            )

                        except asyncio.CancelledError:
                            raise

                        except Exception as error:
                            print(
                                f"[{self.agent_id}] "
                                f"Failed message "
                                f"{redis_id}: "
                                f"{type(error).__name__}: "
                                f"{error}"
                            )

                            # One bad event must not terminate
                            # the tracker process.
                            #
                            # The message remains pending because
                            # process_message did not ACK it.

                            continue

            except asyncio.CancelledError:
                raise

            except Exception as error:
                print(
                    f"[{self.agent_id}] "
                    f"Tracking loop error: "
                    f"{type(error).__name__}: "
                    f"{error}"
                )

                # Redis/network failure should not immediately
                # crash the entire worker. Give Redis a moment
                # before retrying.
                await asyncio.sleep(2)

        print(
            f"[{self.agent_id}] "
            f"Tracking loop stopped."
        )


async def main():
    agent = PersonTrackerAgent()

    await agent.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
