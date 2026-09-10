# # # # # # import asyncio
# # # # # # import json
# # # # # # import os
# # # # # # import time
# # # # # # from datetime import datetime, timezone

# # # # # # import redis.asyncio as redis


# # # # # # # ============================================================
# # # # # # # CONFIG
# # # # # # # ============================================================

# # # # # # REDIS_HOST = os.getenv(
# # # # # #     "REDIS_HOST",
# # # # # #     "localhost",
# # # # # # )

# # # # # # REDIS_PORT = int(
# # # # # #     os.getenv(
# # # # # #         "REDIS_PORT",
# # # # # #         "6379",
# # # # # #     )
# # # # # # )

# # # # # # INPUT_STREAM = "events.tracking"

# # # # # # OUTPUT_STREAM = "events.behavior"

# # # # # # GROUP_NAME = "behavior-workers"

# # # # # # CONSUMER_NAME = "behavior-01"

# # # # # # # How long a person must remain active before
# # # # # # # being considered loitering.
# # # # # # LOITERING_THRESHOLD_SECONDS = float(
# # # # # #     os.getenv(
# # # # # #         "LOITERING_THRESHOLD_SECONDS",
# # # # # #         "30",
# # # # # #     )
# # # # # # )

# # # # # # # How long without receiving a track update
# # # # # # # before we consider the person gone.
# # # # # # TRACK_TIMEOUT_SECONDS = float(
# # # # # #     os.getenv(
# # # # # #         "TRACK_TIMEOUT_SECONDS",
# # # # # #         "2.0",
# # # # # #     )
# # # # # # )


# # # # # # # ============================================================
# # # # # # # STATE
# # # # # # # ============================================================

# # # # # # # {
# # # # # # #     camera_id: {
# # # # # # #         track_id: {
# # # # # # #             "first_seen": timestamp,
# # # # # # #             "last_seen": timestamp,
# # # # # # #             "last_event": event
# # # # # # #         }
# # # # # # #     }
# # # # # # # }
# # # # # # #
# # # # # # # This state exists only while the agent is running.

# # # # # # camera_tracks = {}


# # # # # # # ============================================================
# # # # # # # REDIS CONSUMER GROUP
# # # # # # # ============================================================

# # # # # # async def ensure_consumer_group(
# # # # # #     redis_client,
# # # # # # ):

# # # # # #     try:

# # # # # #         await redis_client.xgroup_create(
# # # # # #             name=INPUT_STREAM,
# # # # # #             groupname=GROUP_NAME,
# # # # # #             id="0",
# # # # # #             mkstream=True,
# # # # # #         )

# # # # # #         print(
# # # # # #             f"Created consumer group: "
# # # # # #             f"{GROUP_NAME}"
# # # # # #         )

# # # # # #     except redis.ResponseError as exc:

# # # # # #         if "BUSYGROUP" in str(exc):

# # # # # #             print(
# # # # # #                 f"Consumer group already exists: "
# # # # # #                 f"{GROUP_NAME}"
# # # # # #             )

# # # # # #         else:
# # # # # #             raise


# # # # # # # ============================================================
# # # # # # # GET TRACKS FROM EVENT
# # # # # # # ============================================================

# # # # # # def extract_tracks(event):

# # # # # #     data = event.get(
# # # # # #         "data",
# # # # # #         {},
# # # # # #     )

# # # # # #     tracks = data.get(
# # # # # #         "tracks",
# # # # # #         [],
# # # # # #     )

# # # # # #     return tracks


# # # # # # # ============================================================
# # # # # # # PROCESS TRACKING EVENT
# # # # # # # ============================================================

# # # # # # async def process_tracking_event(
# # # # # #     redis_client,
# # # # # #     event,
# # # # # # ):

# # # # # #     event_type = event.get(
# # # # # #         "event_type"
# # # # # #     )

# # # # # #     if event_type != "person.tracked":

# # # # # #         print(
# # # # # #             f"Ignoring event type: "
# # # # # #             f"{event_type}"
# # # # # #         )

# # # # # #         return

# # # # # #     camera = event.get(
# # # # # #         "camera",
# # # # # #         {},
# # # # # #     )

# # # # # #     camera_id = camera.get(
# # # # # #         "camera_id",
# # # # # #         "unknown",
# # # # # #     )

# # # # # #     tracks = extract_tracks(
# # # # # #         event
# # # # # #     )

# # # # # #     if not tracks:

# # # # # #         return

# # # # # #     now = time.time()

# # # # # #     if camera_id not in camera_tracks:

# # # # # #         camera_tracks[camera_id] = {}

# # # # # #     active_tracks = camera_tracks[
# # # # # #         camera_id
# # # # # #     ]

# # # # # #     # --------------------------------------------------------
# # # # # #     # Update each track
# # # # # #     # --------------------------------------------------------

# # # # # #     for track in tracks:

# # # # # #         track_id = track.get(
# # # # # #             "track_id"
# # # # # #         )

# # # # # #         if not track_id:

# # # # # #             continue

# # # # # #         if track_id not in active_tracks:

# # # # # #             active_tracks[track_id] = {
# # # # # #                 "first_seen": now,
# # # # # #                 "last_seen": now,
# # # # # #                 "last_event": event,
# # # # # #                 "loitering_emitted": False,
# # # # # #             }

# # # # # #         else:

# # # # # #             active_tracks[
# # # # # #                 track_id
# # # # # #             ]["last_seen"] = now

# # # # # #             active_tracks[
# # # # # #                 track_id
# # # # # #             ]["last_event"] = event

# # # # # #     # --------------------------------------------------------
# # # # # #     # Remove expired tracks
# # # # # #     # --------------------------------------------------------

# # # # # #     expired_tracks = []

# # # # # #     for track_id, state in active_tracks.items():

# # # # # #         if (
# # # # # #             now - state["last_seen"]
# # # # # #             > TRACK_TIMEOUT_SECONDS
# # # # # #         ):

# # # # # #             expired_tracks.append(
# # # # # #                 track_id
# # # # # #             )

# # # # # #     for track_id in expired_tracks:

# # # # # #         del active_tracks[
# # # # # #             track_id
# # # # # #         ]

# # # # # #     # --------------------------------------------------------
# # # # # #     # Check loitering
# # # # # #     # --------------------------------------------------------

# # # # # #     for track_id, state in active_tracks.items():

# # # # # #         duration = (
# # # # # #             now
# # # # # #             - state["first_seen"]
# # # # # #         )

# # # # # #         if (
# # # # # #             duration
# # # # # #             >= LOITERING_THRESHOLD_SECONDS
# # # # # #             and not state[
# # # # # #                 "loitering_emitted"
# # # # # #             ]
# # # # # #         ):

# # # # # #             await emit_loitering_event(
# # # # # #                 redis_client=redis_client,
# # # # # #                 camera_id=camera_id,
# # # # # #                 track_id=track_id,
# # # # # #                 duration=duration,
# # # # # #                 source_event=state[
# # # # # #                     "last_event"
# # # # # #                 ],
# # # # # #             )

# # # # # #             state[
# # # # # #                 "loitering_emitted"
# # # # # #             ] = True

# # # # # #     # --------------------------------------------------------
# # # # # #     # Console status
# # # # # #     # --------------------------------------------------------

# # # # # #     print(
# # # # # #         f"Behavior | "
# # # # # #         f"Camera={camera_id} | "
# # # # # #         f"Active tracks={len(active_tracks)}"
# # # # # #     )


# # # # # # # ============================================================
# # # # # # # EMIT LOITERING EVENT
# # # # # # # ============================================================

# # # # # # async def emit_loitering_event(
# # # # # #     redis_client,
# # # # # #     camera_id,
# # # # # #     track_id,
# # # # # #     duration,
# # # # # #     source_event,
# # # # # # ):

# # # # # #     behavior_event = {

# # # # # #         "event_id": (
# # # # # #             __import__("uuid")
# # # # # #             .uuid4()
# # # # # #             .hex
# # # # # #         ),

# # # # # #         "event_type":
# # # # # #             "loitering.detected",

# # # # # #         "version":
# # # # # #             "1.0",

# # # # # #         "timestamp":
# # # # # #             datetime.now(
# # # # # #                 timezone.utc
# # # # # #             ).isoformat(),

# # # # # #         "source": {
# # # # # #             "agent_id":
# # # # # #                 CONSUMER_NAME,
# # # # # #         },

# # # # # #         "camera": {
# # # # # #             "camera_id":
# # # # # #                 camera_id,
# # # # # #         },

# # # # # #         "data": {

# # # # # #             "behavior_type":
# # # # # #                 "loitering",

# # # # # #             "track_id":
# # # # # #                 track_id,

# # # # # #             "duration_seconds":
# # # # # #                 round(
# # # # # #                     duration,
# # # # # #                     2,
# # # # # #                 ),

# # # # # #             "severity":
# # # # # #                 "medium",

# # # # # #             "message":
# # # # # #                 (
# # # # # #                     f"Possible loitering detected "
# # # # # #                     f"on {camera_id}: "
# # # # # #                     f"track {track_id} remained "
# # # # # #                     f"active for "
# # # # # #                     f"{duration:.1f} seconds"
# # # # # #                 ),

# # # # # #             "source_event_id":
# # # # # #                 source_event.get(
# # # # # #                     "event_id"
# # # # # #                 ),
# # # # # #         },
# # # # # #     }

# # # # # #     redis_id = await redis_client.xadd(
# # # # # #         OUTPUT_STREAM,
# # # # # #         {
# # # # # #             "event":
# # # # # #                 json.dumps(
# # # # # #                     behavior_event
# # # # # #                 )
# # # # # #         },
# # # # # #     )

# # # # # #     print(
# # # # # #         f"🚨 LOITERING DETECTED | "
# # # # # #         f"Camera={camera_id} | "
# # # # # #         f"Track={track_id} | "
# # # # # #         f"Duration={duration:.1f}s | "
# # # # # #         f"Severity=medium | "
# # # # # #         f"Redis={redis_id}"
# # # # # #     )


# # # # # # # ============================================================
# # # # # # # MAIN
# # # # # # # ============================================================

# # # # # # async def main():

# # # # # #     redis_client = redis.Redis(
# # # # # #         host=REDIS_HOST,
# # # # # #         port=REDIS_PORT,
# # # # # #         decode_responses=True,
# # # # # #         socket_connect_timeout=5,
# # # # # #         socket_timeout=None,
# # # # # #     )

# # # # # #     await ensure_consumer_group(
# # # # # #         redis_client
# # # # # #     )

# # # # # #     print("=" * 60)

# # # # # #     print(
# # # # # #         f"Behavior Agent started: "
# # # # # #         f"{CONSUMER_NAME}"
# # # # # #     )

# # # # # #     print(
# # # # # #         f"Input stream: "
# # # # # #         f"{INPUT_STREAM}"
# # # # # #     )

# # # # # #     print(
# # # # # #         f"Output stream: "
# # # # # #         f"{OUTPUT_STREAM}"
# # # # # #     )

# # # # # #     print(
# # # # # #         f"Loitering threshold: "
# # # # # #         f"{LOITERING_THRESHOLD_SECONDS}s"
# # # # # #     )

# # # # # #     print(
# # # # # #         f"Track timeout: "
# # # # # #         f"{TRACK_TIMEOUT_SECONDS}s"
# # # # # #     )

# # # # # #     print("=" * 60)

# # # # # #     try:

# # # # # #         while True:

# # # # # #             try:

# # # # # #                 messages = (
# # # # # #                     await redis_client.xreadgroup(
# # # # # #                         groupname=GROUP_NAME,
# # # # # #                         consumername=CONSUMER_NAME,
# # # # # #                         streams={
# # # # # #                             INPUT_STREAM: ">"
# # # # # #                         },
# # # # # #                         count=10,
# # # # # #                         block=5000,
# # # # # #                     )
# # # # # #                 )

# # # # # #             except redis.exceptions.TimeoutError:

# # # # # #                 print(
# # # # # #                     "Redis read timeout; "
# # # # # #                     "continuing..."
# # # # # #                 )

# # # # # #                 continue

# # # # # #             if not messages:

# # # # # #                 continue

# # # # # #             for (
# # # # # #                 stream_name,
# # # # # #                 stream_messages,
# # # # # #             ) in messages:

# # # # # #                 for (
# # # # # #                     redis_id,
# # # # # #                     fields,
# # # # # #                 ) in stream_messages:

# # # # # #                     try:

# # # # # #                         raw_event = fields.get(
# # # # # #                             "event"
# # # # # #                         )

# # # # # #                         if not raw_event:

# # # # # #                             print(
# # # # # #                                 f"Missing event "
# # # # # #                                 f"payload in "
# # # # # #                                 f"{redis_id}"
# # # # # #                             )

# # # # # #                             await redis_client.xack(
# # # # # #                                 INPUT_STREAM,
# # # # # #                                 GROUP_NAME,
# # # # # #                                 redis_id,
# # # # # #                             )

# # # # # #                             continue

# # # # # #                         event = json.loads(
# # # # # #                             raw_event
# # # # # #                         )

# # # # # #                         await process_tracking_event(
# # # # # #                             redis_client,
# # # # # #                             event,
# # # # # #                         )

# # # # # #                         await redis_client.xack(
# # # # # #                             INPUT_STREAM,
# # # # # #                             GROUP_NAME,
# # # # # #                             redis_id,
# # # # # #                         )

# # # # # #                     except json.JSONDecodeError as exc:

# # # # # #                         print(
# # # # # #                             f"Invalid JSON in "
# # # # # #                             f"{redis_id}: "
# # # # # #                             f"{exc}"
# # # # # #                         )

# # # # # #                         await redis_client.xack(
# # # # # #                             INPUT_STREAM,
# # # # # #                             GROUP_NAME,
# # # # # #                             redis_id,
# # # # # #                         )

# # # # # #                     except Exception as exc:

# # # # # #                         print(
# # # # # #                             f"Error processing "
# # # # # #                             f"{redis_id}: "
# # # # # #                             f"{type(exc).__name__}: "
# # # # # #                             f"{exc}"
# # # # # #                         )

# # # # # #                         # Do not ACK.
# # # # # #                         # Redis keeps the message pending.

# # # # # #     finally:

# # # # # #         await redis_client.aclose()

# # # # # #         print(
# # # # # #             "Behavior Agent stopped."
# # # # # #         )


# # # # # # # ============================================================
# # # # # # # ENTRY POINT
# # # # # # # ============================================================

# # # # # # if __name__ == "__main__":

# # # # # #     asyncio.run(
# # # # # #         main()
# # # # # #     )





















# # # # # # import asyncio
# # # # # # import os
# # # # # # import uuid

# # # # # # import cv2
# # # # # # from ultralytics import YOLO

# # # # # # from shared.agent.base_agent import BaseAgent
# # # # # # from shared.schemas.person_detected import PersonDetectedData


# # # # # # class PersonDetectionAgent(BaseAgent):
# # # # # #     """
# # # # # #     YOLO-based person detection agent.

# # # # # #     Camera -> YOLO -> person.detected -> events.detection

# # # # # #     BaseAgent provides:
# # # # # #     - Redis connection
# # # # # #     - Heartbeat
# # # # # #     - Lifecycle management
# # # # # #     - Graceful shutdown
# # # # # #     """

# # # # # #     def __init__(self):
# # # # # #         super().__init__(
# # # # # #             agent_id=os.getenv(
# # # # # #                 "AGENT_ID",
# # # # # #                 "person-detector-01",
# # # # # #             ),
# # # # # #             heartbeat_interval=int(
# # # # # #                 os.getenv(
# # # # # #                     "HEARTBEAT_INTERVAL",
# # # # # #                     "10",
# # # # # #                 )
# # # # # #             ),
# # # # # #         )

# # # # # #         self.camera_id = os.getenv(
# # # # # #             "CAMERA_ID",
# # # # # #             "CAM01",
# # # # # #         )

# # # # # #         self.camera_index = int(
# # # # # #             os.getenv(
# # # # # #                 "CAMERA_INDEX",
# # # # # #                 "0",
# # # # # #             )
# # # # # #         )

# # # # # #         self.model_path = os.getenv(
# # # # # #             "YOLO_MODEL",
# # # # # #             "yolo11n.pt",
# # # # # #         )

# # # # # #         self.confidence = float(
# # # # # #             os.getenv(
# # # # # #                 "YOLO_CONFIDENCE",
# # # # # #                 "0.40",
# # # # # #             )
# # # # # #         )

# # # # # #         self.frame_interval = float(
# # # # # #             os.getenv(
# # # # # #                 "FRAME_INTERVAL",
# # # # # #                 "0.2",
# # # # # #             )
# # # # # #         )

# # # # # #         self.show_camera = (
# # # # # #             os.getenv(
# # # # # #                 "SHOW_CAMERA",
# # # # # #                 "true",
# # # # # #             ).lower()
# # # # # #             == "true"
# # # # # #         )

# # # # # #         self.model = None
# # # # # #         self.cap = None

# # # # # #         self.frame_id = 0

# # # # # #         self.last_alive_log = 0.0

# # # # # #     async def on_start(self):
# # # # # #         print(
# # # # # #             f"[{self.agent_id}] "
# # # # # #             f"Loading YOLO model: {self.model_path}"
# # # # # #         )

# # # # # #         self.model = YOLO(self.model_path)

# # # # # #         print(
# # # # # #             f"[{self.agent_id}] "
# # # # # #             f"YOLO model loaded."
# # # # # #         )

# # # # # #         self.cap = cv2.VideoCapture(
# # # # # #             self.camera_index
# # # # # #         )

# # # # # #         if not self.cap.isOpened():
# # # # # #             raise RuntimeError(
# # # # # #                 f"Unable to open camera "
# # # # # #                 f"{self.camera_index}"
# # # # # #             )

# # # # # #         print(
# # # # # #             f"[{self.agent_id}] "
# # # # # #             f"Camera opened: "
# # # # # #             f"index={self.camera_index}"
# # # # # #         )

# # # # # #         print(
# # # # # #             f"[{self.agent_id}] "
# # # # # #             f"Camera ID: {self.camera_id}"
# # # # # #         )

# # # # # #     async def on_stop(self):
# # # # # #         if self.cap is not None:
# # # # # #             self.cap.release()
# # # # # #             self.cap = None

# # # # # #         if self.show_camera:
# # # # # #             try:
# # # # # #                 cv2.destroyAllWindows()
# # # # # #             except Exception:
# # # # # #                 pass

# # # # # #         print(
# # # # # #             f"[{self.agent_id}] "
# # # # # #             f"Camera resources released."
# # # # # #         )

# # # # # #     async def run(self):
# # # # # #         if self.model is None:
# # # # # #             raise RuntimeError(
# # # # # #                 "YOLO model is not initialized."
# # # # # #             )

# # # # # #         if self.cap is None:
# # # # # #             raise RuntimeError(
# # # # # #                 "Camera is not initialized."
# # # # # #             )

# # # # # #         print(
# # # # # #             f"[{self.agent_id}] "
# # # # # #             f"Detection loop started."
# # # # # #         )

# # # # # #         loop = asyncio.get_running_loop()

# # # # # #         while self.running:

# # # # # #             try:
# # # # # #                 ret, frame = await loop.run_in_executor(
# # # # # #                     None,
# # # # # #                     self.cap.read,
# # # # # #                 )

# # # # # #                 if not ret or frame is None:

# # # # # #                     print(
# # # # # #                         f"[{self.agent_id}] "
# # # # # #                         f"Camera frame read failed. "
# # # # # #                         f"Attempting reconnect..."
# # # # # #                     )

# # # # # #                     self.cap.release()

# # # # # #                     await asyncio.sleep(1)

# # # # # #                     self.cap = cv2.VideoCapture(
# # # # # #                         self.camera_index
# # # # # #                     )

# # # # # #                     if self.cap.isOpened():
# # # # # #                         print(
# # # # # #                             f"[{self.agent_id}] "
# # # # # #                             f"Camera reconnected."
# # # # # #                         )

# # # # # #                     continue

# # # # # #                 self.frame_id += 1

# # # # # #                 results = await loop.run_in_executor(
# # # # # #                     None,
# # # # # #                     lambda: self.model(
# # # # # #                         frame,
# # # # # #                         conf=self.confidence,
# # # # # #                         classes=[0],
# # # # # #                         verbose=False,
# # # # # #                     ),
# # # # # #                 )

# # # # # #                 detections = []

# # # # # #                 annotated_frame = frame.copy()

# # # # # #                 for result in results:

# # # # # #                     if result.boxes is None:
# # # # # #                         continue

# # # # # #                     boxes = result.boxes

# # # # # #                     for index in range(
# # # # # #                         len(boxes)
# # # # # #                     ):

# # # # # #                         box = boxes[index]

# # # # # #                         xyxy = (
# # # # # #                             box.xyxy[0]
# # # # # #                             .cpu()
# # # # # #                             .tolist()
# # # # # #                         )

# # # # # #                         confidence = float(
# # # # # #                             box.conf[0]
# # # # # #                             .cpu()
# # # # # #                             .item()
# # # # # #                         )

# # # # # #                         detection_id = (
# # # # # #                             f"det-"
# # # # # #                             f"{self.camera_id}-"
# # # # # #                             f"{self.frame_id}-"
# # # # # #                             f"{uuid.uuid4().hex[:8]}"
# # # # # #                         )

# # # # # #                         detections.append(
# # # # # #                             {
# # # # # #                                 "detection_id":
# # # # # #                                     detection_id,
# # # # # #                                 "confidence":
# # # # # #                                     confidence,
# # # # # #                                 "bbox":
# # # # # #                                     [
# # # # # #                                         float(
# # # # # #                                             xyxy[0]
# # # # # #                                         ),
# # # # # #                                         float(
# # # # # #                                             xyxy[1]
# # # # # #                                         ),
# # # # # #                                         float(
# # # # # #                                             xyxy[2]
# # # # # #                                         ),
# # # # # #                                         float(
# # # # # #                                             xyxy[3]
# # # # # #                                         ),
# # # # # #                                     ],
# # # # # #                             }
# # # # # #                         )

# # # # # #                         x1, y1, x2, y2 = map(
# # # # # #                             int,
# # # # # #                             xyxy,
# # # # # #                         )

# # # # # #                         cv2.rectangle(
# # # # # #                             annotated_frame,
# # # # # #                             (x1, y1),
# # # # # #                             (x2, y2),
# # # # # #                             (0, 255, 0),
# # # # # #                             2,
# # # # # #                         )

# # # # # #                         cv2.putText(
# # # # # #                             annotated_frame,
# # # # # #                             f"Person {confidence:.2f}",
# # # # # #                             (x1, max(y1 - 10, 20)),
# # # # # #                             cv2.FONT_HERSHEY_SIMPLEX,
# # # # # #                             0.5,
# # # # # #                             (0, 255, 0),
# # # # # #                             2,
# # # # # #                         )

# # # # # #                 event_data = PersonDetectedData(
# # # # # #                     frame_id=str(
# # # # # #                         self.frame_id
# # # # # #                     ),
# # # # # #                     detections=detections,
# # # # # #                 )

# # # # # #                 event = {
# # # # # #                     "event_id": str(
# # # # # #                         uuid.uuid4()
# # # # # #                     ),
# # # # # #                     "event_type":
# # # # # #                         "person.detected",
# # # # # #                     "version": "1.0",
# # # # # #                     "timestamp":
# # # # # #                         self.now(),
# # # # # #                     "source": {
# # # # # #                         "agent_id":
# # # # # #                             self.agent_id,
# # # # # #                     },
# # # # # #                     "camera": {
# # # # # #                         "camera_id":
# # # # # #                             self.camera_id,
# # # # # #                     },
# # # # # #                     "data":
# # # # # #                         event_data.model_dump(),
# # # # # #                 }

# # # # # #                 redis_id = await self.publish(
# # # # # #                     "events.detection",
# # # # # #                     event,
# # # # # #                 )

# # # # # #                 print(
# # # # # #                     f"DETECTED | "
# # # # # #                     f"Camera={self.camera_id} | "
# # # # # #                     f"Persons={len(detections)} | "
# # # # # #                     f"Redis={redis_id}"
# # # # # #                 )

# # # # # #                 cv2.imwrite(
# # # # # #                     "camera_latest.jpg",
# # # # # #                     annotated_frame,
# # # # # #                 )

# # # # # #                 if self.show_camera:

# # # # # #                     cv2.imshow(
# # # # # #                         "CCTV AI - Person Detection",
# # # # # #                         annotated_frame,
# # # # # #                     )

# # # # # #                     key = cv2.waitKey(1) & 0xFF

# # # # # #                     if key == ord("q"):
# # # # # #                         print(
# # # # # #                             f"[{self.agent_id}] "
# # # # # #                             f"Shutdown requested "
# # # # # #                             f"by operator."
# # # # # #                         )
# # # # # #                         break

# # # # # #                 await asyncio.sleep(
# # # # # #                     self.frame_interval
# # # # # #                 )

# # # # # #             except asyncio.CancelledError:
# # # # # #                 raise

# # # # # #             except Exception as error:

# # # # # #                 print(
# # # # # #                     f"[{self.agent_id}] "
# # # # # #                     f"Detection iteration error: "
# # # # # #                     f"{error}"
# # # # # #                 )

# # # # # #                 # IMPORTANT:
# # # # # #                 # A single bad frame must NOT
# # # # # #                 # terminate the whole agent.
# # # # # #                 await asyncio.sleep(1)

# # # # # #         print(
# # # # # #             f"[{self.agent_id}] "
# # # # # #             f"Detection loop stopped."
# # # # # #         )


# # # # # # async def main():
# # # # # #     agent = PersonDetectionAgent()

# # # # # #     await agent.run_forever()


# # # # # # if __name__ == "__main__":
# # # # # #     asyncio.run(main())















# # # # # import asyncio
# # # # # import json
# # # # # import os
# # # # # import time
# # # # # import uuid

# # # # # from shared.agent.base_agent import BaseAgent


# # # # # class BehaviorAgent(BaseAgent):
# # # # #     """
# # # # #     Behavior analysis agent.

# # # # #     Input:
# # # # #         events.tracking

# # # # #     Output:
# # # # #         events.behavior

# # # # #     Detects:
# # # # #         - person loitering
# # # # #     """

# # # # #     def __init__(self):
# # # # #         super().__init__(
# # # # #             agent_id=os.getenv(
# # # # #                 "AGENT_ID",
# # # # #                 "behavior-01",
# # # # #             ),
# # # # #             heartbeat_interval=int(
# # # # #                 os.getenv(
# # # # #                     "HEARTBEAT_INTERVAL",
# # # # #                     "10",
# # # # #                 ),
# # # # #             ),
# # # # #         )

# # # # #         self.input_stream = "events.tracking"
# # # # #         self.output_stream = "events.behavior"

# # # # #         self.group_name = os.getenv(
# # # # #             "BEHAVIOR_GROUP",
# # # # #             "behavior-workers",
# # # # #         )

# # # # #         self.consumer_name = os.getenv(
# # # # #             "BEHAVIOR_CONSUMER",
# # # # #             f"behavior-{uuid.uuid4().hex[:8]}",
# # # # #         )

# # # # #         self.loitering_threshold = float(
# # # # #             os.getenv(
# # # # #                 "LOITERING_THRESHOLD",
# # # # #                 "30",
# # # # #             ),
# # # # #         )

# # # # #         self.track_timeout = float(
# # # # #             os.getenv(
# # # # #                 "TRACK_TIMEOUT",
# # # # #                 "2",
# # # # #             ),
# # # # #         )

# # # # #         self.track_state = {}

# # # # #     async def on_start(self):
# # # # #         try:
# # # # #             await self.redis_client.xgroup_create(
# # # # #                 self.input_stream,
# # # # #                 self.group_name,
# # # # #                 id="0",
# # # # #                 mkstream=True,
# # # # #             )
# # # # #         except Exception as error:
# # # # #             if "BUSYGROUP" not in str(error):
# # # # #                 raise

# # # # #         print(
# # # # #             f"[{self.agent_id}] Behavior agent ready."
# # # # #         )

# # # # #         print(
# # # # #             f"[{self.agent_id}] "
# # # # #             f"Input: {self.input_stream}"
# # # # #         )

# # # # #         print(
# # # # #             f"[{self.agent_id}] "
# # # # #             f"Output: {self.output_stream}"
# # # # #         )

# # # # #         print(
# # # # #             f"[{self.agent_id}] "
# # # # #             f"Loitering threshold: "
# # # # #             f"{self.loitering_threshold}s"
# # # # #         )

# # # # #     async def on_stop(self):
# # # # #         self.track_state.clear()

# # # # #         print(
# # # # #             f"[{self.agent_id}] "
# # # # #             f"Behavior state cleared."
# # # # #         )

# # # # #     def cleanup_tracks(self):
# # # # #         now = time.monotonic()

# # # # #         stale = []

# # # # #         for key, state in self.track_state.items():
# # # # #             if (
# # # # #                 now - state["last_seen"]
# # # # #                 > self.track_timeout
# # # # #             ):
# # # # #                 stale.append(key)

# # # # #         for key in stale:
# # # # #             del self.track_state[key]

# # # # #     async def process_message(
# # # # #         self,
# # # # #         redis_id,
# # # # #         fields,
# # # # #     ):
# # # # #         raw_event = fields.get("event")

# # # # #         if not raw_event:
# # # # #             await self.redis_client.xack(
# # # # #                 self.input_stream,
# # # # #                 self.group_name,
# # # # #                 redis_id,
# # # # #             )
# # # # #             return

# # # # #         event = json.loads(raw_event)

# # # # #         if event.get("event_type") != "person.tracked":
# # # # #             await self.redis_client.xack(
# # # # #                 self.input_stream,
# # # # #                 self.group_name,
# # # # #                 redis_id,
# # # # #             )
# # # # #             return

# # # # #         camera = event.get(
# # # # #             "camera",
# # # # #             {},
# # # # #         )

# # # # #         data = event.get(
# # # # #             "data",
# # # # #             {},
# # # # #         )

# # # # #         camera_id = camera.get(
# # # # #             "camera_id",
# # # # #             "CAM01",
# # # # #         )

# # # # #         tracks = data.get(
# # # # #             "tracks",
# # # # #             [],
# # # # #         )

# # # # #         now = time.monotonic()

# # # # #         for track in tracks:

# # # # #             track_id = track.get(
# # # # #                 "track_id"
# # # # #             )

# # # # #             if not track_id:
# # # # #                 continue

# # # # #             key = (
# # # # #                 camera_id,
# # # # #                 track_id,
# # # # #             )

# # # # #             if key not in self.track_state:

# # # # #                 self.track_state[key] = {
# # # # #                     "first_seen": now,
# # # # #                     "last_seen": now,
# # # # #                     "loitering_emitted": False,
# # # # #                 }

# # # # #             state = self.track_state[key]

# # # # #             state["last_seen"] = now

# # # # #             duration = (
# # # # #                 now - state["first_seen"]
# # # # #             )

# # # # #             if (
# # # # #                 duration
# # # # #                 >= self.loitering_threshold
# # # # #                 and not state["loitering_emitted"]
# # # # #             ):

# # # # #                 state[
# # # # #                     "loitering_emitted"
# # # # #                 ] = True

# # # # #                 behavior_event = {
# # # # #                     "event_id": str(
# # # # #                         uuid.uuid4()
# # # # #                     ),
# # # # #                     "event_type":
# # # # #                         "loitering.detected",
# # # # #                     "version": "1.0",
# # # # #                     "timestamp":
# # # # #                         self.now(),
# # # # #                     "source": {
# # # # #                         "agent_id":
# # # # #                             self.agent_id,
# # # # #                     },
# # # # #                     "camera": {
# # # # #                         "camera_id":
# # # # #                             camera_id,
# # # # #                     },
# # # # #                     "data": {
# # # # #                         "frame_id": str(
# # # # #                             data.get(
# # # # #                                 "frame_id",
# # # # #                                 redis_id,
# # # # #                             )
# # # # #                         ),
# # # # #                         "track_id":
# # # # #                             track_id,
# # # # #                         "duration_seconds":
# # # # #                             round(
# # # # #                                 duration,
# # # # #                                 2,
# # # # #                             ),
# # # # #                         "threshold_seconds":
# # # # #                             self.loitering_threshold,
# # # # #                         "severity":
# # # # #                             "medium",
# # # # #                     },
# # # # #                 }

# # # # #                 output_id = await self.publish(
# # # # #                     self.output_stream,
# # # # #                     behavior_event,
# # # # #                 )

# # # # #                 print(
# # # # #                     f"LOITERING | "
# # # # #                     f"Camera={camera_id} | "
# # # # #                     f"Track={track_id} | "
# # # # #                     f"Duration={duration:.1f}s | "
# # # # #                     f"Redis={output_id}"
# # # # #                 )

# # # # #         self.cleanup_tracks()

# # # # #         await self.redis_client.xack(
# # # # #             self.input_stream,
# # # # #             self.group_name,
# # # # #             redis_id,
# # # # #         )

# # # # #     async def run(self):

# # # # #         print(
# # # # #             f"[{self.agent_id}] "
# # # # #             f"Behavior loop started."
# # # # #         )

# # # # #         while self.running:

# # # # #             try:

# # # # #                 messages = await (
# # # # #                     self.redis_client.xreadgroup(
# # # # #                         groupname=self.group_name,
# # # # #                         consumername=self.consumer_name,
# # # # #                         streams={
# # # # #                             self.input_stream: ">"
# # # # #                         },
# # # # #                         count=10,
# # # # #                         block=5000,
# # # # #                     )
# # # # #                 )

# # # # #                 if not messages:
# # # # #                     continue

# # # # #                 for _, entries in messages:

# # # # #                     for redis_id, fields in entries:

# # # # #                         try:
# # # # #                             await self.process_message(
# # # # #                                 redis_id,
# # # # #                                 fields,
# # # # #                             )

# # # # #                         except Exception as error:

# # # # #                             print(
# # # # #                                 f"[{self.agent_id}] "
# # # # #                                 f"Message error "
# # # # #                                 f"{redis_id}: "
# # # # #                                 f"{error}"
# # # # #                             )

# # # # #                             # Do not let one bad
# # # # #                             # message kill the agent.
# # # # #                             continue

# # # # #             except asyncio.CancelledError:
# # # # #                 raise

# # # # #             except Exception as error:

# # # # #                 print(
# # # # #                     f"[{self.agent_id}] "
# # # # #                     f"Behavior loop error: "
# # # # #                     f"{error}"
# # # # #                 )

# # # # #                 await asyncio.sleep(2)

# # # # #         print(
# # # # #             f"[{self.agent_id}] "
# # # # #             f"Behavior loop stopped."
# # # # #         )


# # # # # async def main():

# # # # #     agent = BehaviorAgent()

# # # # #     await agent.run_forever()


# # # # # if __name__ == "__main__":
# # # # #     asyncio.run(main())

















# # # # import asyncio
# # # # import json
# # # # import os
# # # # import time
# # # # import uuid

# # # # from shared.agent.base_agent import BaseAgent


# # # # class BehaviorAgent(BaseAgent):
# # # #     """
# # # #     Behavior analysis agent.

# # # #     Input:
# # # #         events.tracking

# # # #     Output:
# # # #         events.behavior

# # # #     Detects:
# # # #         - person loitering
# # # #     """

# # # #     def __init__(self):
# # # #         super().__init__(
# # # #             agent_id=os.getenv(
# # # #                 "AGENT_ID",
# # # #                 "behavior-01",
# # # #             ),
# # # #             heartbeat_interval=int(
# # # #                 os.getenv(
# # # #                     "HEARTBEAT_INTERVAL",
# # # #                     "10",
# # # #                 ),
# # # #             ),
# # # #         )

# # # #         self.input_stream = "events.tracking"

# # # #         self.output_stream = "events.behavior"

# # # #         self.group_name = os.getenv(
# # # #             "BEHAVIOR_GROUP",
# # # #             "behavior-workers",
# # # #         )

# # # #         self.consumer_name = os.getenv(
# # # #             "BEHAVIOR_CONSUMER",
# # # #             f"behavior-{uuid.uuid4().hex[:8]}",
# # # #         )

# # # #         self.loitering_threshold = float(
# # # #             os.getenv(
# # # #                 "LOITERING_THRESHOLD",
# # # #                 "30",
# # # #             ),
# # # #         )

# # # #         self.track_timeout = float(
# # # #             os.getenv(
# # # #                 "TRACK_TIMEOUT",
# # # #                 "2",
# # # #             ),
# # # #         )

# # # #         self.track_state = {}

# # # #     async def on_start(self):
# # # #         try:
# # # #             await self.redis_client.xgroup_create(
# # # #                 self.input_stream,
# # # #                 self.group_name,
# # # #                 id="0",
# # # #                 mkstream=True,
# # # #             )

# # # #         except Exception as error:
# # # #             if "BUSYGROUP" not in str(error):
# # # #                 raise

# # # #         print(
# # # #             f"[{self.agent_id}] Behavior agent ready."
# # # #         )

# # # #         print(
# # # #             f"[{self.agent_id}] "
# # # #             f"Input: {self.input_stream}"
# # # #         )

# # # #         print(
# # # #             f"[{self.agent_id}] "
# # # #             f"Output: {self.output_stream}"
# # # #         )

# # # #         print(
# # # #             f"[{self.agent_id}] "
# # # #             f"Loitering threshold: "
# # # #             f"{self.loitering_threshold}s"
# # # #         )

# # # #     async def on_stop(self):
# # # #         self.track_state.clear()

# # # #         print(
# # # #             f"[{self.agent_id}] "
# # # #             f"Behavior state cleared."
# # # #         )

# # # #     def cleanup_tracks(self):
# # # #         now = time.monotonic()

# # # #         stale = []

# # # #         for key, state in self.track_state.items():
# # # #             if (
# # # #                 now - state["last_seen"]
# # # #                 > self.track_timeout
# # # #             ):
# # # #                 stale.append(key)

# # # #         for key in stale:
# # # #             del self.track_state[key]

# # # #     async def process_message(
# # # #         self,
# # # #         redis_id,
# # # #         fields,
# # # #     ):
# # # #         raw_event = fields.get("event")

# # # #         if not raw_event:
# # # #             await self.redis_client.xack(
# # # #                 self.input_stream,
# # # #                 self.group_name,
# # # #                 redis_id,
# # # #             )
# # # #             return

# # # #         event = json.loads(raw_event)

# # # #         if event.get("event_type") != "person.tracked":
# # # #             await self.redis_client.xack(
# # # #                 self.input_stream,
# # # #                 self.group_name,
# # # #                 redis_id,
# # # #             )
# # # #             return

# # # #         camera = event.get(
# # # #             "camera",
# # # #             {},
# # # #         )

# # # #         data = event.get(
# # # #             "data",
# # # #             {},
# # # #         )

# # # #         camera_id = camera.get(
# # # #             "camera_id",
# # # #             "CAM01",
# # # #         )

# # # #         tracks = data.get(
# # # #             "tracks",
# # # #             [],
# # # #         )

# # # #         now = time.monotonic()

# # # #         for track in tracks:
# # # #             track_id = track.get(
# # # #                 "track_id"
# # # #             )

# # # #             if not track_id:
# # # #                 continue

# # # #             key = (
# # # #                 camera_id,
# # # #                 track_id,
# # # #             )

# # # #             if key not in self.track_state:
# # # #                 self.track_state[key] = {
# # # #                     "first_seen": now,
# # # #                     "last_seen": now,
# # # #                     "loitering_emitted": False,
# # # #                 }

# # # #             state = self.track_state[key]

# # # #             state["last_seen"] = now

# # # #             duration = (
# # # #                 now - state["first_seen"]
# # # #             )

# # # #             if (
# # # #                 duration
# # # #                 >= self.loitering_threshold
# # # #                 and not state["loitering_emitted"]
# # # #             ):
# # # #                 state[
# # # #                     "loitering_emitted"
# # # #                 ] = True

# # # #                 behavior_event = {
# # # #                     "event_id": str(
# # # #                         uuid.uuid4()
# # # #                     ),
# # # #                     "event_type":
# # # #                         "loitering.detected",
# # # #                     "version": "1.0",
# # # #                     "timestamp":
# # # #                         self.now(),
# # # #                     "source": {
# # # #                         "agent_id":
# # # #                             self.agent_id,
# # # #                     },
# # # #                     "camera": {
# # # #                         "camera_id":
# # # #                             camera_id,
# # # #                     },
# # # #                     "data": {
# # # #                         "frame_id": str(
# # # #                             data.get(
# # # #                                 "frame_id",
# # # #                                 redis_id,
# # # #                             )
# # # #                         ),
# # # #                         "track_id":
# # # #                             track_id,
# # # #                         "duration_seconds":
# # # #                             round(
# # # #                                 duration,
# # # #                                 2,
# # # #                             ),
# # # #                         "threshold_seconds":
# # # #                             self.loitering_threshold,
# # # #                         "severity":
# # # #                             "medium",
# # # #                     },
# # # #                 }

# # # #                 output_id = await self.publish(
# # # #                     self.output_stream,
# # # #                     behavior_event,
# # # #                 )

# # # #                 print(
# # # #                     f"LOITERING | "
# # # #                     f"Camera={camera_id} | "
# # # #                     f"Track={track_id} | "
# # # #                     f"Duration={duration:.1f}s | "
# # # #                     f"Redis={output_id}"
# # # #                 )

# # # #         self.cleanup_tracks()

# # # #         await self.redis_client.xack(
# # # #             self.input_stream,
# # # #             self.group_name,
# # # #             redis_id,
# # # #         )

# # # #     async def run(self):
# # # #         print(
# # # #             f"[{self.agent_id}] "
# # # #             f"Behavior loop started."
# # # #         )

# # # #         while self.running:
# # # #             try:
# # # #                 messages = await (
# # # #                     self.redis_client.xreadgroup(
# # # #                         groupname=self.group_name,
# # # #                         consumername=self.consumer_name,
# # # #                         streams={
# # # #                             self.input_stream: ">"
# # # #                         },
# # # #                         count=10,
# # # #                         block=5000,
# # # #                     )
# # # #                 )

# # # #                 if not messages:
# # # #                     continue

# # # #                 for _, entries in messages:
# # # #                     for redis_id, fields in entries:
# # # #                         try:
# # # #                             await self.process_message(
# # # #                                 redis_id,
# # # #                                 fields,
# # # #                             )

# # # #                         except Exception as error:
# # # #                             print(
# # # #                                 f"[{self.agent_id}] "
# # # #                                 f"Message error "
# # # #                                 f"{redis_id}: "
# # # #                                 f"{error}"
# # # #                             )

# # # #                             # Do not let one bad
# # # #                             # message kill the agent.
# # # #                             continue

# # # #             except asyncio.CancelledError:
# # # #                 raise

# # # #             except Exception as error:
# # # #                 print(
# # # #                     f"[{self.agent_id}] "
# # # #                     f"Behavior loop error: "
# # # #                     f"{error}"
# # # #                 )

# # # #                 await asyncio.sleep(2)

# # # #         print(
# # # #             f"[{self.agent_id}] "
# # # #             f"Behavior loop stopped."
# # # #         )


# # # # async def main():
# # # #     agent = BehaviorAgent()

# # # #     await agent.run_forever()


# # # # if __name__ == "__main__":
# # # #     asyncio.run(main())















# # # import asyncio
# # # import json
# # # import os
# # # import uuid
# # # from datetime import datetime, timezone
# # # from typing import Any, Dict, Optional, Tuple

# # # from shared.agent.base_agent import BaseAgent
# # # from shared.schemas.event_schema import create_event, validate_event


# # # class BehaviorAgent(BaseAgent):
# # #     """
# # #     Behavior analysis agent.

# # #     Input:
# # #         events.tracking

# # #     Output:
# # #         events.behavior

# # #     Current detections:
# # #         - person loitering

# # #     Important architecture rule:
# # #         All events for the same camera must be routed to the same
# # #         stateful behavior worker/partition. Otherwise the in-memory
# # #         track state can be split between workers.
# # #     """

# # #     def __init__(self):
# # #         super().__init__(
# # #             agent_id=os.getenv(
# # #                 "AGENT_ID",
# # #                 "behavior-01",
# # #             ),
# # #             heartbeat_interval=int(
# # #                 os.getenv(
# # #                     "HEARTBEAT_INTERVAL",
# # #                     "10",
# # #                 ),
# # #             ),
# # #         )

# # #         self.input_stream = os.getenv(
# # #             "BEHAVIOR_INPUT_STREAM",
# # #             "events.tracking",
# # #         )

# # #         self.output_stream = os.getenv(
# # #             "BEHAVIOR_OUTPUT_STREAM",
# # #             "events.behavior",
# # #         )

# # #         self.group_name = os.getenv(
# # #             "BEHAVIOR_GROUP",
# # #             "behavior-workers",
# # #         )

# # #         self.consumer_name = os.getenv(
# # #             "BEHAVIOR_CONSUMER",
# # #             f"behavior-{uuid.uuid4().hex[:8]}",
# # #         )

# # #         self.loitering_threshold = self._read_positive_float(
# # #             "LOITERING_THRESHOLD",
# # #             30.0,
# # #         )

# # #         self.track_timeout = self._read_positive_float(
# # #             "TRACK_TIMEOUT",
# # #             2.0,
# # #         )

# # #         # Key:
# # #         #     (camera_id, track_id)
# # #         #
# # #         # Value:
# # #         #     {
# # #         #         "first_seen": datetime,
# # #         #         "last_seen": datetime,
# # #         #         "loitering_emitted": bool,
# # #         #     }
# # #         self.track_state: Dict[
# # #             Tuple[str, str],
# # #             Dict[str, Any],
# # #         ] = {}

# # #     @staticmethod
# # #     def _read_positive_float(
# # #         env_name: str,
# # #         default: float,
# # #     ) -> float:
# # #         raw_value = os.getenv(
# # #             env_name,
# # #             str(default),
# # #         )

# # #         try:
# # #             value = float(raw_value)
# # #         except (TypeError, ValueError) as error:
# # #             raise ValueError(
# # #                 f"{env_name} must be a valid number. "
# # #                 f"Received: {raw_value!r}"
# # #             ) from error

# # #         if value <= 0:
# # #             raise ValueError(
# # #                 f"{env_name} must be greater than zero. "
# # #                 f"Received: {value}"
# # #             )

# # #         return value

# # #     @staticmethod
# # #     def _parse_timestamp(
# # #         value: Any,
# # #     ) -> Optional[datetime]:
# # #         """
# # #         Parse an event timestamp into timezone-aware UTC.

# # #         Historical mode depends on actual footage/event timestamps,
# # #         not process/runtime monotonic time.
# # #         """

# # #         if not value:
# # #             return None

# # #         if isinstance(value, datetime):
# # #             parsed = value
# # #         else:
# # #             text = str(value).strip()

# # #             if not text:
# # #                 return None

# # #             if text.endswith("Z"):
# # #                 text = text[:-1] + "+00:00"

# # #             try:
# # #                 parsed = datetime.fromisoformat(text)
# # #             except ValueError:
# # #                 return None

# # #         if parsed.tzinfo is None:
# # #             parsed = parsed.replace(
# # #                 tzinfo=timezone.utc,
# # #             )

# # #         return parsed.astimezone(timezone.utc)

# # #     @staticmethod
# # #     def _event_time(event: Dict[str, Any]) -> Optional[datetime]:
# # #         """
# # #         Determine the timestamp used for behavior calculations.

# # #         Preference:
# # #             1. data.frame_timestamp
# # #             2. event.timestamp
# # #         """

# # #         data = event.get("data")

# # #         if not isinstance(data, dict):
# # #             data = {}

# # #         frame_timestamp = BehaviorAgent._parse_timestamp(
# # #             data.get("frame_timestamp"),
# # #         )

# # #         if frame_timestamp is not None:
# # #             return frame_timestamp

# # #         return BehaviorAgent._parse_timestamp(
# # #             event.get("timestamp"),
# # #         )

# # #     @staticmethod
# # #     def _safe_float(
# # #         value: Any,
# # #     ) -> Optional[float]:
# # #         try:
# # #             if value is None:
# # #                 return None
# # #             return float(value)
# # #         except (TypeError, ValueError):
# # #             return None

# # #     async def on_start(self):
# # #         try:
# # #             await self.redis_client.xgroup_create(
# # #                 self.input_stream,
# # #                 self.group_name,
# # #                 id="0",
# # #                 mkstream=True,
# # #             )
# # #         except Exception as error:
# # #             if "BUSYGROUP" not in str(error):
# # #                 raise

# # #         print(
# # #             f"[{self.agent_id}] Behavior agent ready."
# # #         )

# # #         print(
# # #             f"[{self.agent_id}] "
# # #             f"Instance: {self.instance_id}"
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
# # #             f"Loitering threshold: "
# # #             f"{self.loitering_threshold:.2f}s"
# # #         )

# # #         print(
# # #             f"[{self.agent_id}] "
# # #             f"Track timeout: "
# # #             f"{self.track_timeout:.2f}s"
# # #         )

# # #         print(
# # #             f"[{self.agent_id}] "
# # #             "State model: camera + track_id"
# # #         )

# # #     async def on_stop(self):
# # #         self.track_state.clear()

# # #         print(
# # #             f"[{self.agent_id}] "
# # #             "Behavior state cleared."
# # #         )

# # #     def cleanup_tracks(
# # #         self,
# # #         current_event_time: datetime,
# # #     ):
# # #         """
# # #         Remove tracks that have not been observed recently.

# # #         Uses event timestamps rather than time.monotonic() so that
# # #         Historical Mode behaves according to the footage timeline.
# # #         """

# # #         stale_keys = []

# # #         for key, state in self.track_state.items():
# # #             last_seen = state.get("last_seen")

# # #             if not isinstance(last_seen, datetime):
# # #                 stale_keys.append(key)
# # #                 continue

# # #             age_seconds = (
# # #                 current_event_time - last_seen
# # #             ).total_seconds()

# # #             # If event timestamps arrive slightly out of order,
# # #             # don't delete the state merely because age is negative.
# # #             if (
# # #                 age_seconds >= 0
# # #                 and age_seconds > self.track_timeout
# # #             ):
# # #                 stale_keys.append(key)

# # #         for key in stale_keys:
# # #             self.track_state.pop(
# # #                 key,
# # #                 None,
# # #             )

# # #     def _build_behavior_event(
# # #         self,
# # #         source_event: Dict[str, Any],
# # #         redis_id: str,
# # #         camera_id: str,
# # #         track: Dict[str, Any],
# # #         duration: float,
# # #     ) -> Dict[str, Any]:
# # #         """
# # #         Build canonical loitering.detected event.

# # #         Lineage is preserved through source_event_id and source_redis_id.
# # #         Trace/correlation/incident context is also preserved.
# # #         """

# # #         source_context = source_event.get(
# # #             "context",
# # #             {},
# # #         )

# # #         if not isinstance(source_context, dict):
# # #             source_context = {}

# # #         source_data = source_event.get(
# # #             "data",
# # #             {},
# # #         )

# # #         if not isinstance(source_data, dict):
# # #             source_data = {}

# # #         track_id = str(
# # #             track.get("track_id"),
# # #         )

# # #         frame_id = source_data.get(
# # #             "frame_id",
# # #             redis_id,
# # #         )

# # #         event_time = (
# # #             self._event_time(source_event)
# # #             or datetime.now(timezone.utc)
# # #         )

# # #         behavior_data = {
# # #             "frame_id": str(frame_id),

# # #             "frame_timestamp": (
# # #                 source_data.get("frame_timestamp")
# # #                 or event_time.isoformat()
# # #                 .replace("+00:00", "Z")
# # #             ),

# # #             "track_id": track_id,

# # #             "duration_seconds": round(
# # #                 max(duration, 0.0),
# # #                 2,
# # #             ),

# # #             "threshold_seconds": (
# # #                 self.loitering_threshold
# # #             ),

# # #             "severity": "medium",

# # #             "behavior": "loitering",

# # #             "source_event_id": source_event.get(
# # #                 "event_id",
# # #             ),

# # #             "source_redis_id": redis_id,

# # #             "track": {
# # #                 "center": track.get("center"),
# # #                 "bbox": track.get("bbox"),
# # #                 "age": track.get("age"),
# # #                 "match_distance": track.get(
# # #                     "match_distance",
# # #                 ),
# # #             },
# # #         }

# # #         return create_event(
# # #             event_type="loitering.detected",
# # #             agent_id=self.agent_id,
# # #             instance_id=self.instance_id,
# # #             hostname=self.hostname,
# # #             camera_id=camera_id,
# # #             mode=source_context.get(
# # #                 "mode",
# # #                 "live",
# # #             ),
# # #             data=behavior_data,
# # #             trace_id=source_context.get(
# # #                 "trace_id",
# # #             ),
# # #             correlation_id=source_context.get(
# # #                 "correlation_id",
# # #             ),
# # #             incident_id=source_context.get(
# # #                 "incident_id",
# # #             ),
# # #             timestamp=event_time,
# # #         ).to_dict()

# # #     async def process_message(
# # #         self,
# # #         redis_id: str,
# # #         fields: Dict[str, Any],
# # #     ):
# # #         """
# # #         Process exactly one Redis message.

# # #         A malformed message is isolated and ACKed because it cannot
# # #         be processed successfully as a valid tracking event.

# # #         A publish failure is NOT ACKed. This allows the later
# # #         reliability layer to recover the pending message.
# # #         """

# # #         raw_event = fields.get("event")

# # #         if not raw_event:
# # #             print(
# # #                 f"[{self.agent_id}] "
# # #                 f"Skipping message without event: "
# # #                 f"{redis_id}"
# # #             )

# # #             await self.redis_client.xack(
# # #                 self.input_stream,
# # #                 self.group_name,
# # #                 redis_id,
# # #             )
# # #             return

# # #         try:
# # #             event = json.loads(raw_event)
# # #         except (TypeError, json.JSONDecodeError) as error:
# # #             print(
# # #                 f"[{self.agent_id}] "
# # #                 f"Invalid JSON event {redis_id}: "
# # #                 f"{error}"
# # #             )

# # #             await self.redis_client.xack(
# # #                 self.input_stream,
# # #                 self.group_name,
# # #                 redis_id,
# # #             )
# # #             return

# # #         if not isinstance(event, dict):
# # #             print(
# # #                 f"[{self.agent_id}] "
# # #                 f"Event is not an object: "
# # #                 f"{redis_id}"
# # #             )

# # #             await self.redis_client.xack(
# # #                 self.input_stream,
# # #                 self.group_name,
# # #                 redis_id,
# # #             )
# # #             return

# # #         # Canonical event validation.
# # #         if not validate_event(event):
# # #             print(
# # #                 f"[{self.agent_id}] "
# # #                 f"Invalid canonical event: "
# # #                 f"{redis_id}"
# # #             )

# # #             await self.redis_client.xack(
# # #                 self.input_stream,
# # #                 self.group_name,
# # #                 redis_id,
# # #             )
# # #             return

# # #         if event.get("event_type") != "person.tracked":
# # #             await self.redis_client.xack(
# # #                 self.input_stream,
# # #                 self.group_name,
# # #                 redis_id,
# # #             )
# # #             return

# # #         camera = event.get(
# # #             "camera",
# # #         )

# # #         if not isinstance(camera, dict):
# # #             print(
# # #                 f"[{self.agent_id}] "
# # #                 f"Missing camera object: "
# # #                 f"{redis_id}"
# # #             )

# # #             await self.redis_client.xack(
# # #                 self.input_stream,
# # #                 self.group_name,
# # #                 redis_id,
# # #             )
# # #             return

# # #         camera_id = camera.get(
# # #             "camera_id",
# # #         )

# # #         if not isinstance(camera_id, str):
# # #             print(
# # #                 f"[{self.agent_id}] "
# # #                 f"Invalid camera_id: "
# # #                 f"{redis_id}"
# # #             )

# # #             await self.redis_client.xack(
# # #                 self.input_stream,
# # #                 self.group_name,
# # #                 redis_id,
# # #             )
# # #             return

# # #         camera_id = camera_id.strip()

# # #         if not camera_id:
# # #             print(
# # #                 f"[{self.agent_id}] "
# # #                 f"Empty camera_id: "
# # #                 f"{redis_id}"
# # #             )

# # #             await self.redis_client.xack(
# # #                 self.input_stream,
# # #                 self.group_name,
# # #                 redis_id,
# # #             )
# # #             return

# # #         data = event.get(
# # #             "data",
# # #         )

# # #         if not isinstance(data, dict):
# # #             print(
# # #                 f"[{self.agent_id}] "
# # #                 f"Missing tracking data: "
# # #                 f"{redis_id}"
# # #             )

# # #             await self.redis_client.xack(
# # #                 self.input_stream,
# # #                 self.group_name,
# # #                 redis_id,
# # #             )
# # #             return

# # #         tracks = data.get(
# # #             "tracks",
# # #             [],
# # #         )

# # #         if not isinstance(tracks, list):
# # #             print(
# # #                 f"[{self.agent_id}] "
# # #                 f"Invalid tracks payload: "
# # #                 f"{redis_id}"
# # #             )

# # #             await self.redis_client.xack(
# # #                 self.input_stream,
# # #                 self.group_name,
# # #                 redis_id,
# # #             )
# # #             return

# # #         current_event_time = self._event_time(
# # #             event,
# # #         )

# # #         if current_event_time is None:
# # #             print(
# # #                 f"[{self.agent_id}] "
# # #                 f"Missing/invalid event timestamp: "
# # #                 f"{redis_id}"
# # #             )

# # #             await self.redis_client.xack(
# # #                 self.input_stream,
# # #                 self.group_name,
# # #                 redis_id,
# # #             )
# # #             return

# # #         for track in tracks:
# # #             if not isinstance(track, dict):
# # #                 continue

# # #             track_id = track.get(
# # #                 "track_id",
# # #             )

# # #             if track_id is None:
# # #                 continue

# # #             track_id = str(track_id).strip()

# # #             if not track_id:
# # #                 continue

# # #             key = (
# # #                 camera_id,
# # #                 track_id,
# # #             )

# # #             state = self.track_state.get(
# # #                 key,
# # #             )

# # #             if state is None:
# # #                 state = {
# # #                     "first_seen": current_event_time,
# # #                     "last_seen": current_event_time,
# # #                     "loitering_emitted": False,
# # #                 }

# # #                 self.track_state[key] = state

# # #             last_seen = state.get(
# # #                 "last_seen",
# # #             )

# # #             first_seen = state.get(
# # #                 "first_seen",
# # #             )

# # #             if not isinstance(
# # #                 last_seen,
# # #                 datetime,
# # #             ):
# # #                 last_seen = current_event_time
# # #                 state["last_seen"] = current_event_time

# # #             if not isinstance(
# # #                 first_seen,
# # #                 datetime,
# # #             ):
# # #                 first_seen = current_event_time
# # #                 state["first_seen"] = current_event_time

# # #             # Protect against out-of-order timestamps.
# # #             if current_event_time < last_seen:
# # #                 print(
# # #                     f"[{self.agent_id}] "
# # #                     f"Out-of-order event for "
# # #                     f"{camera_id}/{track_id}: "
# # #                     f"{redis_id}"
# # #                 )

# # #                 continue

# # #             state["last_seen"] = current_event_time

# # #             duration = (
# # #                 current_event_time - first_seen
# # #             ).total_seconds()

# # #             if (
# # #                 duration
# # #                 >= self.loitering_threshold
# # #                 and not state["loitering_emitted"]
# # #             ):
# # #                 behavior_event = (
# # #                     self._build_behavior_event(
# # #                         source_event=event,
# # #                         redis_id=redis_id,
# # #                         camera_id=camera_id,
# # #                         track=track,
# # #                         duration=duration,
# # #                     )
# # #                 )

# # #                 # Publish first.
# # #                 #
# # #                 # Only mark loitering as emitted after the publish
# # #                 # succeeds. This prevents a failed publish from
# # #                 # permanently suppressing the event.
# # #                 output_id = await self.publish(
# # #                     self.output_stream,
# # #                     behavior_event,
# # #                 )

# # #                 state[
# # #                     "loitering_emitted"
# # #                 ] = True

# # #                 print(
# # #                     f"LOITERING | "
# # #                     f"Camera={camera_id} | "
# # #                     f"Track={track_id} | "
# # #                     f"Duration={duration:.1f}s | "
# # #                     f"Mode="
# # #                     f"{event.get('context', {}).get('mode', 'live')} | "
# # #                     f"Redis={output_id}"
# # #                 )

# # #         self.cleanup_tracks(
# # #             current_event_time,
# # #         )

# # #         await self.redis_client.xack(
# # #             self.input_stream,
# # #             self.group_name,
# # #             redis_id,
# # #         )

# # #     async def run(self):
# # #         print(
# # #             f"[{self.agent_id}] "
# # #             "Behavior loop started."
# # #         )

# # #         print(
# # #             f"[{self.agent_id}] "
# # #             f"Consumer: {self.consumer_name}"
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

# # #                 for _, entries in messages:
# # #                     for redis_id, fields in entries:
# # #                         try:
# # #                             await self.process_message(
# # #                                 redis_id,
# # #                                 fields,
# # #                             )

# # #                         except asyncio.CancelledError:
# # #                             raise

# # #                         except Exception as error:
# # #                             # Do not allow one message to terminate
# # #                             # the behavior agent.
# # #                             #
# # #                             # IMPORTANT:
# # #                             # The message is intentionally NOT ACKed
# # #                             # here. It remains pending for the future
# # #                             # reliability/recovery layer.
# # #                             print(
# # #                                 f"[{self.agent_id}] "
# # #                                 f"Message error "
# # #                                 f"{redis_id}: "
# # #                                 f"{type(error).__name__}: "
# # #                                 f"{error}"
# # #                             )

# # #                             continue

# # #             except asyncio.CancelledError:
# # #                 raise

# # #             except Exception as error:
# # #                 print(
# # #                     f"[{self.agent_id}] "
# # #                     f"Behavior loop error: "
# # #                     f"{type(error).__name__}: "
# # #                     f"{error}"
# # #                 )

# # #                 await asyncio.sleep(2)

# # #         print(
# # #             f"[{self.agent_id}] "
# # #             "Behavior loop stopped."
# # #         )


# # # async def main():
# # #     agent = BehaviorAgent()
# # #     await agent.run_forever()


# # # if __name__ == "__main__":
# # #     asyncio.run(main())























# # """
# # Behavior Agent
# # ==============

# # Consumes canonical ``person.tracked`` events and detects behavioral
# # patterns such as loitering.

# # Pipeline:

# #     events.tracking
# #           |
# #           v
# #     BehaviorAgent
# #           |
# #           v
# #     events.behavior
# #           |
# #           +--> loitering.detected

# # Design principles:

# # - Canonical event schema
# # - Camera-aware state isolation
# # - Historical-mode timestamp preservation
# # - Trace/correlation/incident propagation
# # - Source-event lineage
# # - Per-message fault isolation
# # - ACK only after successful processing
# # - No silent camera fallback
# # - Same-camera routing/affinity is required for stateful workers

# # Important state rule:

# #     (camera_id, track_id)

# # is the identity of a behavior-tracking state.

# # Cleanup is always restricted to the camera associated with the
# # current event. A timestamp from one camera must never delete state
# # belonging to another camera.

# # Current behavior detections:

# # - person loitering
# # """

# # from __future__ import annotations

# # import asyncio
# # import json
# # import os
# # import uuid
# # from datetime import datetime, timezone
# # from typing import Any, Dict, Optional, Tuple

# # from shared.agent.base_agent import BaseAgent
# # from shared.schemas.event_schema import create_event, validate_event


# # class BehaviorAgent(BaseAgent):
# #     """
# #     Stateful behavior analysis agent.

# #     Input:
# #         events.tracking

# #     Output:
# #         events.behavior

# #     Current detection:
# #         - person loitering

# #     Stateful routing requirement:

# #         All events for the same camera must be routed to the same
# #         behavior worker/partition.

# #     State identity:

# #         (camera_id, track_id)

# #     This prevents track state from being split across workers.
# #     """

# #     def __init__(self):
# #         super().__init__(
# #             agent_id=os.getenv(
# #                 "AGENT_ID",
# #                 "behavior-01",
# #             ),
# #             heartbeat_interval=int(
# #                 os.getenv(
# #                     "HEARTBEAT_INTERVAL",
# #                     "10",
# #                 ),
# #             ),
# #         )

# #         self.input_stream = os.getenv(
# #             "BEHAVIOR_INPUT_STREAM",
# #             "events.tracking",
# #         )

# #         self.output_stream = os.getenv(
# #             "BEHAVIOR_OUTPUT_STREAM",
# #             "events.behavior",
# #         )

# #         self.group_name = os.getenv(
# #             "BEHAVIOR_GROUP",
# #             "behavior-workers",
# #         )

# #         self.consumer_name = os.getenv(
# #             "BEHAVIOR_CONSUMER",
# #             f"behavior-{uuid.uuid4().hex[:8]}",
# #         )

# #         self.loitering_threshold = self._read_positive_float(
# #             "LOITERING_THRESHOLD",
# #             30.0,
# #         )

# #         self.track_timeout = self._read_positive_float(
# #             "TRACK_TIMEOUT",
# #             2.0,
# #         )

# #         # --------------------------------------------------------
# #         # Stateful behavior tracking.
# #         #
# #         # Key:
# #         #     (camera_id, track_id)
# #         #
# #         # Value:
# #         #     {
# #         #         "first_seen": datetime,
# #         #         "last_seen": datetime,
# #         #         "loitering_emitted": bool,
# #         #     }
# #         #
# #         # Camera ID is deliberately part of the key so that two
# #         # cameras can never share the same track state.
# #         # --------------------------------------------------------

# #         self.track_state: Dict[
# #             Tuple[str, str],
# #             Dict[str, Any],
# #         ] = {}

# #     # ============================================================
# #     # CONFIGURATION
# #     # ============================================================

# #     @staticmethod
# #     def _read_positive_float(
# #         env_name: str,
# #         default: float,
# #     ) -> float:
# #         raw_value = os.getenv(
# #             env_name,
# #             str(default),
# #         )

# #         try:
# #             value = float(raw_value)
# #         except (TypeError, ValueError) as error:
# #             raise ValueError(
# #                 f"{env_name} must be a valid number. "
# #                 f"Received: {raw_value!r}"
# #             ) from error

# #         if value <= 0:
# #             raise ValueError(
# #                 f"{env_name} must be greater than zero. "
# #                 f"Received: {value}"
# #             )

# #         if value != value:
# #             raise ValueError(
# #                 f"{env_name} cannot be NaN."
# #             )

# #         if value in (
# #             float("inf"),
# #             float("-inf"),
# #         ):
# #             raise ValueError(
# #                 f"{env_name} must be finite."
# #             )

# #         return value

# #     # ============================================================
# #     # TIMESTAMP PARSING
# #     # ============================================================

# #     @staticmethod
# #     def _parse_timestamp(
# #         value: Any,
# #     ) -> Optional[datetime]:
# #         """
# #         Parse an event timestamp into timezone-aware UTC.

# #         Historical mode depends on actual footage/event timestamps,
# #         not process/runtime monotonic time.
# #         """

# #         if not value:
# #             return None

# #         if isinstance(value, datetime):
# #             parsed = value
# #         else:
# #             text = str(value).strip()

# #             if not text:
# #                 return None

# #             if text.endswith("Z"):
# #                 text = text[:-1] + "+00:00"

# #             try:
# #                 parsed = datetime.fromisoformat(text)
# #             except ValueError:
# #                 return None

# #         if parsed.tzinfo is None:
# #             parsed = parsed.replace(
# #                 tzinfo=timezone.utc,
# #             )

# #         return parsed.astimezone(timezone.utc)

# #     # ============================================================
# #     # EVENT TIME
# #     # ============================================================

# #     @classmethod
# #     def _event_time(
# #         cls,
# #         event: Dict[str, Any],
# #     ) -> Optional[datetime]:
# #         """
# #         Determine the timestamp used for behavior calculations.

# #         Preference:

# #             1. data.frame_timestamp
# #             2. event.timestamp
# #         """

# #         data = event.get("data")

# #         if not isinstance(data, dict):
# #             data = {}

# #         frame_timestamp = cls._parse_timestamp(
# #             data.get("frame_timestamp"),
# #         )

# #         if frame_timestamp is not None:
# #             return frame_timestamp

# #         return cls._parse_timestamp(
# #             event.get("timestamp"),
# #         )

# #     # ============================================================
# #     # STATE CLEANUP
# #     # ============================================================

# #     def cleanup_camera_tracks(
# #         self,
# #         camera_id: str,
# #         current_event_time: datetime,
# #     ) -> None:
# #         """
# #         Remove stale track state for ONE camera only.

# #         This is intentionally camera-scoped.

# #         A timestamp from CAM01 must never remove state belonging
# #         to CAM02.

# #         The cleanup happens BEFORE processing the current event so
# #         that a track returning after a timeout starts a fresh
# #         behavioral observation instead of inheriting an old
# #         loitering duration.
# #         """

# #         stale_keys = []

# #         for key, state in self.track_state.items():
# #             state_camera_id, _track_id = key

# #             if state_camera_id != camera_id:
# #                 continue

# #             last_seen = state.get("last_seen")

# #             if not isinstance(
# #                 last_seen,
# #                 datetime,
# #             ):
# #                 stale_keys.append(key)
# #                 continue

# #             age_seconds = (
# #                 current_event_time - last_seen
# #             ).total_seconds()

# #             # Never remove state because of an out-of-order event.
# #             if (
# #                 age_seconds >= 0
# #                 and age_seconds > self.track_timeout
# #             ):
# #                 stale_keys.append(key)

# #         for key in stale_keys:
# #             removed_state = self.track_state.pop(
# #                 key,
# #                 None,
# #             )

# #             if removed_state is not None:
# #                 _, track_id = key

# #                 print(
# #                     f"[{self.agent_id}] "
# #                     f"Track state expired | "
# #                     f"Camera={camera_id} | "
# #                     f"Track={track_id}"
# #                 )

# #     # ============================================================
# #     # BUILD BEHAVIOR EVENT
# #     # ============================================================

# #     def _build_behavior_event(
# #         self,
# #         source_event: Dict[str, Any],
# #         redis_id: str,
# #         camera_id: str,
# #         track: Dict[str, Any],
# #         duration: float,
# #     ) -> Dict[str, Any]:
# #         """
# #         Build canonical loitering.detected event.

# #         Source lineage and execution context are preserved.
# #         """

# #         source_context = source_event.get(
# #             "context",
# #             {},
# #         )

# #         if not isinstance(
# #             source_context,
# #             dict,
# #         ):
# #             source_context = {}

# #         source_data = source_event.get(
# #             "data",
# #             {},
# #         )

# #         if not isinstance(
# #             source_data,
# #             dict,
# #         ):
# #             source_data = {}

# #         track_id = str(
# #             track.get("track_id"),
# #         )

# #         frame_id = source_data.get(
# #             "frame_id",
# #             redis_id,
# #         )

# #         event_time = (
# #             self._event_time(source_event)
# #             or datetime.now(timezone.utc)
# #         )

# #         frame_timestamp = source_data.get(
# #             "frame_timestamp",
# #         )

# #         if not frame_timestamp:
# #             frame_timestamp = (
# #                 event_time
# #                 .isoformat()
# #                 .replace(
# #                     "+00:00",
# #                     "Z",
# #                 )
# #             )

# #         behavior_data = {
# #             "frame_id": str(frame_id),
# #             "frame_timestamp": frame_timestamp,
# #             "track_id": track_id,
# #             "duration_seconds": round(
# #                 max(duration, 0.0),
# #                 2,
# #             ),
# #             "threshold_seconds": (
# #                 self.loitering_threshold
# #             ),
# #             "severity": "medium",
# #             "behavior": "loitering",

# #             # Source lineage.
# #             "source_event_id": source_event.get(
# #                 "event_id",
# #             ),
# #             "source_redis_id": redis_id,

# #             "track": {
# #                 "center": track.get("center"),
# #                 "bbox": track.get("bbox"),
# #                 "age": track.get("age"),
# #                 "match_distance": track.get(
# #                     "match_distance",
# #                 ),
# #             },
# #         }

# #         return create_event(
# #             event_type="loitering.detected",
# #             agent_id=self.agent_id,
# #             instance_id=self.instance_id,
# #             hostname=self.hostname,
# #             camera_id=camera_id,
# #             mode=source_context.get(
# #                 "mode",
# #                 "live",
# #             ),
# #             data=behavior_data,
# #             trace_id=source_context.get(
# #                 "trace_id",
# #             ),
# #             correlation_id=source_context.get(
# #                 "correlation_id",
# #             ),
# #             incident_id=source_context.get(
# #                 "incident_id",
# #             ),
# #             timestamp=event_time,
# #         ).to_dict()

# #     # ============================================================
# #     # STARTUP
# #     # ============================================================

# #     async def on_start(self):
# #         if not self.redis_client:
# #             raise RuntimeError(
# #                 "Redis client is not initialized."
# #             )

# #         try:
# #             await self.redis_client.xgroup_create(
# #                 self.input_stream,
# #                 self.group_name,
# #                 id="0",
# #                 mkstream=True,
# #             )
# #         except Exception as error:
# #             if "BUSYGROUP" not in str(error):
# #                 raise

# #         print(
# #             f"[{self.agent_id}] "
# #             "Behavior agent ready."
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
# #             f"Input: {self.input_stream}"
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Output: {self.output_stream}"
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Consumer: {self.consumer_name}"
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Loitering threshold: "
# #             f"{self.loitering_threshold:.2f}s"
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Track timeout: "
# #             f"{self.track_timeout:.2f}s"
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             "State model: camera + track_id"
# #         )

# #     # ============================================================
# #     # SHUTDOWN
# #     # ============================================================

# #     async def on_stop(self):
# #         self.track_state.clear()

# #         print(
# #             f"[{self.agent_id}] "
# #             "Behavior state cleared."
# #         )

# #     # ============================================================
# #     # PROCESS ONE MESSAGE
# #     # ============================================================

# #     async def process_message(
# #         self,
# #         redis_id: str,
# #         fields: Dict[str, Any],
# #     ):
# #         """
# #         Process exactly one Redis message.

# #         Invalid/poison messages are ACKed because they cannot be
# #         successfully processed.

# #         Processing/publish failures are NOT ACKed, allowing the
# #         reliability layer to reclaim the pending message.
# #         """

# #         if not isinstance(fields, dict):
# #             print(
# #                 f"[{self.agent_id}] "
# #                 f"Invalid Redis fields: "
# #                 f"{redis_id}"
# #             )

# #             await self.redis_client.xack(
# #                 self.input_stream,
# #                 self.group_name,
# #                 redis_id,
# #             )

# #             return

# #         raw_event = fields.get("event")

# #         if not raw_event:
# #             print(
# #                 f"[{self.agent_id}] "
# #                 f"Skipping message without event: "
# #                 f"{redis_id}"
# #             )

# #             await self.redis_client.xack(
# #                 self.input_stream,
# #                 self.group_name,
# #                 redis_id,
# #             )

# #             return

# #         # --------------------------------------------------------
# #         # Parse JSON.
# #         # --------------------------------------------------------

# #         try:
# #             event = json.loads(raw_event)
# #         except (TypeError, json.JSONDecodeError) as error:
# #             print(
# #                 f"[{self.agent_id}] "
# #                 f"Invalid JSON event {redis_id}: "
# #                 f"{error}"
# #             )

# #             await self.redis_client.xack(
# #                 self.input_stream,
# #                 self.group_name,
# #                 redis_id,
# #             )

# #             return

# #         if not isinstance(
# #             event,
# #             dict,
# #         ):
# #             print(
# #                 f"[{self.agent_id}] "
# #                 f"Event is not an object: "
# #                 f"{redis_id}"
# #             )

# #             await self.redis_client.xack(
# #                 self.input_stream,
# #                 self.group_name,
# #                 redis_id,
# #             )

# #             return

# #         # --------------------------------------------------------
# #         # Canonical validation.
# #         # --------------------------------------------------------

# #         if not validate_event(event):
# #             print(
# #                 f"[{self.agent_id}] "
# #                 f"Invalid canonical event: "
# #                 f"{redis_id}"
# #             )

# #             await self.redis_client.xack(
# #                 self.input_stream,
# #                 self.group_name,
# #                 redis_id,
# #             )

# #             return

# #         # --------------------------------------------------------
# #         # Only person.tracked is relevant.
# #         # --------------------------------------------------------

# #         if event.get("event_type") != "person.tracked":
# #             await self.redis_client.xack(
# #                 self.input_stream,
# #                 self.group_name,
# #                 redis_id,
# #             )

# #             return

# #         # --------------------------------------------------------
# #         # Camera validation.
# #         # --------------------------------------------------------

# #         camera = event.get("camera")

# #         if not isinstance(
# #             camera,
# #             dict,
# #         ):
# #             print(
# #                 f"[{self.agent_id}] "
# #                 f"Missing camera object: "
# #                 f"{redis_id}"
# #             )

# #             await self.redis_client.xack(
# #                 self.input_stream,
# #                 self.group_name,
# #                 redis_id,
# #             )

# #             return

# #         camera_id = camera.get(
# #             "camera_id",
# #         )

# #         if not isinstance(
# #             camera_id,
# #             str,
# #         ):
# #             print(
# #                 f"[{self.agent_id}] "
# #                 f"Invalid camera_id: "
# #                 f"{redis_id}"
# #             )

# #             await self.redis_client.xack(
# #                 self.input_stream,
# #                 self.group_name,
# #                 redis_id,
# #             )

# #             return

# #         camera_id = camera_id.strip()

# #         if not camera_id:
# #             print(
# #                 f"[{self.agent_id}] "
# #                 f"Empty camera_id: "
# #                 f"{redis_id}"
# #             )

# #             await self.redis_client.xack(
# #                 self.input_stream,
# #                 self.group_name,
# #                 redis_id,
# #             )

# #             return

# #         # --------------------------------------------------------
# #         # Data validation.
# #         # --------------------------------------------------------

# #         data = event.get("data")

# #         if not isinstance(
# #             data,
# #             dict,
# #         ):
# #             print(
# #                 f"[{self.agent_id}] "
# #                 f"Missing tracking data: "
# #                 f"{redis_id}"
# #             )

# #             await self.redis_client.xack(
# #                 self.input_stream,
# #                 self.group_name,
# #                 redis_id,
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
# #                 f"Invalid tracks payload: "
# #                 f"{redis_id}"
# #             )

# #             await self.redis_client.xack(
# #                 self.input_stream,
# #                 self.group_name,
# #                 redis_id,
# #             )

# #             return

# #         # --------------------------------------------------------
# #         # Event timestamp.
# #         # --------------------------------------------------------

# #         current_event_time = self._event_time(
# #             event,
# #         )

# #         if current_event_time is None:
# #             print(
# #                 f"[{self.agent_id}] "
# #                 f"Missing/invalid event timestamp: "
# #                 f"{redis_id}"
# #             )

# #             await self.redis_client.xack(
# #                 self.input_stream,
# #                 self.group_name,
# #                 redis_id,
# #             )

# #             return

# #         # --------------------------------------------------------
# #         # IMPORTANT:
# #         #
# #         # Clean stale state BEFORE processing this event.
# #         #
# #         # Cleanup is restricted to this camera only.
# #         # --------------------------------------------------------

# #         self.cleanup_camera_tracks(
# #             camera_id=camera_id,
# #             current_event_time=current_event_time,
# #         )

# #         # --------------------------------------------------------
# #         # Process every tracked person.
# #         # --------------------------------------------------------

# #         for track in tracks:
# #             if not isinstance(
# #                 track,
# #                 dict,
# #             ):
# #                 continue

# #             track_id = track.get(
# #                 "track_id",
# #             )

# #             if track_id is None:
# #                 continue

# #             track_id = str(
# #                 track_id,
# #             ).strip()

# #             if not track_id:
# #                 continue

# #             state_key = (
# #                 camera_id,
# #                 track_id,
# #             )

# #             state = self.track_state.get(
# #                 state_key,
# #             )

# #             # ----------------------------------------------------
# #             # New track.
# #             # ----------------------------------------------------

# #             if state is None:
# #                 state = {
# #                     "first_seen": current_event_time,
# #                     "last_seen": current_event_time,
# #                     "loitering_emitted": False,
# #                 }

# #                 self.track_state[
# #                     state_key
# #                 ] = state

# #             last_seen = state.get(
# #                 "last_seen",
# #             )

# #             first_seen = state.get(
# #                 "first_seen",
# #             )

# #             if not isinstance(
# #                 last_seen,
# #                 datetime,
# #             ):
# #                 last_seen = current_event_time

# #                 state["last_seen"] = (
# #                     current_event_time
# #                 )

# #             if not isinstance(
# #                 first_seen,
# #                 datetime,
# #             ):
# #                 first_seen = current_event_time

# #                 state["first_seen"] = (
# #                     current_event_time
# #                 )

# #             # ----------------------------------------------------
# #             # Out-of-order protection.
# #             #
# #             # Do not move state backward in time.
# #             # ----------------------------------------------------

# #             if current_event_time < last_seen:
# #                 print(
# #                     f"[{self.agent_id}] "
# #                     f"Out-of-order event for "
# #                     f"{camera_id}/{track_id}: "
# #                     f"{redis_id}"
# #                 )

# #                 continue

# #             # ----------------------------------------------------
# #             # Update last seen.
# #             # ----------------------------------------------------

# #             state["last_seen"] = (
# #                 current_event_time
# #             )

# #             duration = (
# #                 current_event_time - first_seen
# #             ).total_seconds()

# #             # ----------------------------------------------------
# #             # Loitering threshold.
# #             # ----------------------------------------------------

# #             if (
# #                 duration
# #                 >= self.loitering_threshold
# #                 and not state["loitering_emitted"]
# #             ):
# #                 behavior_event = (
# #                     self._build_behavior_event(
# #                         source_event=event,
# #                         redis_id=redis_id,
# #                         camera_id=camera_id,
# #                         track=track,
# #                         duration=duration,
# #                     )
# #                 )

# #                 # ------------------------------------------------
# #                 # Validate generated event before publishing.
# #                 # ------------------------------------------------

# #                 if not validate_event(
# #                     behavior_event
# #                 ):
# #                     raise ValueError(
# #                         "Generated loitering event "
# #                         "failed canonical validation."
# #                     )

# #                 # ------------------------------------------------
# #                 # Publish FIRST.
# #                 #
# #                 # Only mark the behavior as emitted after
# #                 # successful publication.
# #                 # ------------------------------------------------

# #                 output_id = await self.publish(
# #                     self.output_stream,
# #                     behavior_event,
# #                 )

# #                 state[
# #                     "loitering_emitted"
# #                 ] = True

# #                 print(
# #                     f"[{self.agent_id}] "
# #                     f"LOITERING | "
# #                     f"Camera={camera_id} | "
# #                     f"Track={track_id} | "
# #                     f"Duration={duration:.1f}s | "
# #                     f"Mode="
# #                     f"{event.get('context', {}).get('mode', 'live')} | "
# #                     f"Redis={output_id}"
# #                 )

# #         # --------------------------------------------------------
# #         # ACK only after the entire message has been processed.
# #         # --------------------------------------------------------

# #         await self.redis_client.xack(
# #             self.input_stream,
# #             self.group_name,
# #             redis_id,
# #         )

# #     # ============================================================
# #     # MAIN LOOP
# #     # ============================================================

# #     async def run(self):
# #         if not self.redis_client:
# #             raise RuntimeError(
# #                 "Redis client is not initialized."
# #             )

# #         print(
# #             f"[{self.agent_id}] "
# #             "Behavior loop started."
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Consumer: {self.consumer_name}"
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

# #                 for _stream_name, entries in messages:
# #                     for redis_id, fields in entries:
# #                         try:
# #                             await self.process_message(
# #                                 redis_id,
# #                                 fields,
# #                             )

# #                         except asyncio.CancelledError:
# #                             raise

# #                         except Exception as error:
# #                             # ------------------------------------
# #                             # IMPORTANT:
# #                             #
# #                             # Do NOT ACK unexpected processing
# #                             # failures.
# #                             #
# #                             # The message remains pending and
# #                             # can be reclaimed by the reliability
# #                             # layer.
# #                             #
# #                             # The exception is isolated to this
# #                             # message and must not terminate the
# #                             # behavior worker.
# #                             # ------------------------------------

# #                             print(
# #                                 f"[{self.agent_id}] "
# #                                 f"Message error "
# #                                 f"{redis_id}: "
# #                                 f"{type(error).__name__}: "
# #                                 f"{error}"
# #                             )

# #                             continue

# #             except asyncio.CancelledError:
# #                 raise

# #             except Exception as error:
# #                 # ----------------------------------------------
# #                 # Redis / loop-level failure.
# #                 #
# #                 # Keep the worker alive so the supervisor does
# #                 # not needlessly restart it for a temporary
# #                 # Redis failure.
# #                 # ----------------------------------------------

# #                 print(
# #                     f"[{self.agent_id}] "
# #                     f"Behavior loop error: "
# #                     f"{type(error).__name__}: "
# #                     f"{error}"
# #                 )

# #                 await asyncio.sleep(2)

# #         print(
# #             f"[{self.agent_id}] "
# #             "Behavior loop stopped."
# #         )


# # # ================================================================
# # # ENTRY POINT
# # # ================================================================

# # async def main():
# #     agent = BehaviorAgent()
# #     await agent.run_forever()


# # if __name__ == "__main__":
# #     asyncio.run(main())



































# """
# Behavior Agent

# Consumes canonical ``person.tracked`` events and detects behavioral
# patterns such as loitering.

# Pipeline:

#     events.tracking
#           |
#           v
#     BehaviorAgent
#           |
#           v
#     events.behavior
#           |
#           +--> loitering.detected

# Design principles:

# - Canonical event envelope
# - Camera-aware state isolation
# - Historical-mode timestamp preservation
# - Trace/correlation/incident propagation
# - Source-event lineage
# - Per-message fault isolation
# - ACK only after successful processing
# - No silent camera fallback
# - Stateful processing requires same-camera routing/affinity

# Current behavior detection:

# - person loitering

# Important state identity:

#     (camera_id, track_id)

# A track ID is only meaningful inside its camera context.

# Important reliability rule:

#     Permanent invalid/poison message
#         -> ACK

#     Unexpected processing/publish failure
#         -> DO NOT ACK
#         -> leave message pending for recovery

# The specialized event registry is intentionally not used yet because
# the current Tracker producer and shared person.tracked schema are still
# being aligned. The canonical envelope is validated here, while the
# current tracking payload is structurally validated locally.
# """

# from __future__ import annotations

# import asyncio
# import json
# import math
# import os
# import uuid
# from datetime import datetime, timezone
# from typing import Any, Dict, Optional, Tuple

# from shared.agent.base_agent import BaseAgent
# from shared.schemas.event_schema import create_event, validate_event


# # ============================================================
# # CONFIGURATION
# # ============================================================

# DEFAULT_AGENT_ID = os.getenv(
#     "BEHAVIOR_AGENT_ID",
#     os.getenv("AGENT_ID", "behavior-01"),
# )

# DEFAULT_HEARTBEAT_INTERVAL = int(
#     os.getenv(
#         "HEARTBEAT_INTERVAL",
#         "10",
#     )
# )

# INPUT_STREAM = os.getenv(
#     "BEHAVIOR_INPUT_STREAM",
#     "events.tracking",
# )

# OUTPUT_STREAM = os.getenv(
#     "BEHAVIOR_OUTPUT_STREAM",
#     "events.behavior",
# )

# GROUP_NAME = os.getenv(
#     "BEHAVIOR_GROUP",
#     "behavior-workers",
# )

# CONSUMER_NAME = os.getenv(
#     "BEHAVIOR_CONSUMER",
#     f"behavior-{uuid.uuid4().hex[:8]}",
# )

# LOITERING_THRESHOLD = float(
#     os.getenv(
#         "LOITERING_THRESHOLD",
#         "30.0",
#     )
# )

# TRACK_TIMEOUT = float(
#     os.getenv(
#         "TRACK_TIMEOUT",
#         "2.0",
#     )
# )


# # ============================================================
# # VALIDATE STATIC CONFIGURATION
# # ============================================================

# def _validate_positive_finite(
#     name: str,
#     value: float,
# ) -> float:
#     if not math.isfinite(value):
#         raise ValueError(
#             f"{name} must be finite. "
#             f"Received: {value!r}"
#         )

#     if value <= 0:
#         raise ValueError(
#             f"{name} must be greater than zero. "
#             f"Received: {value!r}"
#         )

#     return value


# _validate_positive_finite(
#     "LOITERING_THRESHOLD",
#     LOITERING_THRESHOLD,
# )

# _validate_positive_finite(
#     "TRACK_TIMEOUT",
#     TRACK_TIMEOUT,
# )


# # ============================================================
# # BEHAVIOR AGENT
# # ============================================================

# class BehaviorAgent(BaseAgent):
#     """
#     Stateful behavior analysis worker.

#     Input:
#         events.tracking

#     Output:
#         events.behavior

#     Current detection:
#         person loitering

#     State identity:
#         (camera_id, track_id)

#     Important:

#     The worker assumes camera affinity is provided by the surrounding
#     routing/supervision topology. Redis consumer groups alone do NOT
#     guarantee that all events for one camera reach the same worker.
#     """

#     def __init__(self):
#         super().__init__(
#             agent_id=DEFAULT_AGENT_ID,
#             heartbeat_interval=DEFAULT_HEARTBEAT_INTERVAL,
#         )

#         self.input_stream = INPUT_STREAM
#         self.output_stream = OUTPUT_STREAM
#         self.group_name = GROUP_NAME
#         self.consumer_name = CONSUMER_NAME

#         self.loitering_threshold = LOITERING_THRESHOLD
#         self.track_timeout = TRACK_TIMEOUT

#         # ----------------------------------------------------
#         # Stateful behavior tracking.
#         #
#         # Key:
#         #     (camera_id, track_id)
#         #
#         # Value:
#         #     {
#         #         "first_seen": datetime,
#         #         "last_seen": datetime,
#         #         "loitering_emitted": bool,
#         #     }
#         # ----------------------------------------------------

#         self.track_state: Dict[
#             Tuple[str, str],
#             Dict[str, Any],
#         ] = {}

#         # ----------------------------------------------------
#         # Per-camera event watermark.
#         #
#         # Prevents an old event from moving camera state
#         # backward in time.
#         # ----------------------------------------------------

#         self.last_event_timestamp: Dict[
#             str,
#             datetime,
#         ] = {}

#     # ========================================================
#     # TIMESTAMP PARSING
#     # ========================================================

#     @staticmethod
#     def _parse_timestamp(
#         value: Any,
#     ) -> Optional[datetime]:
#         """
#         Parse only timezone-aware timestamps.

#         Naive timestamps are rejected rather than silently being
#         interpreted as UTC. This keeps live and historical event
#         semantics deterministic.
#         """

#         if isinstance(value, datetime):
#             parsed = value

#         elif isinstance(value, str):
#             text = value.strip()

#             if not text:
#                 return None

#             if text.endswith("Z"):
#                 text = text[:-1] + "+00:00"

#             try:
#                 parsed = datetime.fromisoformat(text)
#             except ValueError:
#                 return None

#         else:
#             return None

#         if (
#             parsed.tzinfo is None
#             or parsed.utcoffset() is None
#         ):
#             return None

#         return parsed.astimezone(
#             timezone.utc
#         )

#     # ========================================================
#     # EVENT TIME
#     # ========================================================

#     @classmethod
#     def _event_time(
#         cls,
#         event: Dict[str, Any],
#     ) -> Optional[datetime]:
#         """
#         Determine the timestamp used for behavior calculations.

#         Preference:

#         1. data.frame_timestamp
#         2. event.timestamp

#         Never fall back to runtime wall-clock time.
#         """

#         data = event.get("data")

#         if isinstance(data, dict):
#             frame_timestamp = cls._parse_timestamp(
#                 data.get("frame_timestamp")
#             )

#             if frame_timestamp is not None:
#                 return frame_timestamp

#         return cls._parse_timestamp(
#             event.get("timestamp")
#         )

#     # ========================================================
#     # CAMERA ID
#     # ========================================================

#     @staticmethod
#     def _extract_camera_id(
#         event: Dict[str, Any],
#     ) -> Optional[str]:
#         camera = event.get("camera")

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
#     # TRACK VALIDATION
#     # ========================================================

#     @staticmethod
#     def _validate_track(
#         track: Any,
#     ) -> bool:
#         """
#         Validate the currently produced person.tracked structure.

#         The shared specialized schema is not used yet because the
#         Tracker producer and schema are still being aligned.
#         """

#         if not isinstance(
#             track,
#             dict,
#         ):
#             return False

#         track_id = track.get(
#             "track_id"
#         )

#         if not isinstance(
#             track_id,
#             str,
#         ) or not track_id.strip():
#             return False

#         bbox = track.get(
#             "bbox"
#         )

#         if (
#             not isinstance(
#                 bbox,
#                 (list, tuple),
#             )
#             or len(bbox) != 4
#         ):
#             return False

#         try:
#             bbox_values = [
#                 float(value)
#                 for value in bbox
#             ]
#         except (
#             TypeError,
#             ValueError,
#         ):
#             return False

#         if not all(
#             math.isfinite(value)
#             for value in bbox_values
#         ):
#             return False

#         x1, y1, x2, y2 = bbox_values

#         if x2 < x1 or y2 < y1:
#             return False

#         center = track.get(
#             "center"
#         )

#         if (
#             not isinstance(
#                 center,
#                 (list, tuple),
#             )
#             or len(center) != 2
#         ):
#             return False

#         try:
#             center_values = [
#                 float(value)
#                 for value in center
#             ]
#         except (
#             TypeError,
#             ValueError,
#         ):
#             return False

#         if not all(
#             math.isfinite(value)
#             for value in center_values
#         ):
#             return False

#         confidence = track.get(
#             "confidence"
#         )

#         if confidence is not None:
#             try:
#                 confidence_value = float(
#                     confidence
#                 )
#             except (
#                 TypeError,
#                 ValueError,
#             ):
#                 return False

#             if (
#                 not math.isfinite(
#                     confidence_value
#                 )
#                 or not 0.0 <= confidence_value <= 1.0
#             ):
#                 return False

#         return True

#     # ========================================================
#     # TRACKING PAYLOAD VALIDATION
#     # ========================================================

#     @classmethod
#     def _validate_tracking_payload(
#         cls,
#         event: Dict[str, Any],
#     ) -> list[Dict[str, Any]]:
#         """
#         Validate the current Tracker producer payload.

#         Returns:
#             Validated track dictionaries.

#         Raises:
#             ValueError:
#                 If the payload itself is malformed.
#         """

#         data = event.get(
#             "data"
#         )

#         if not isinstance(
#             data,
#             dict,
#         ):
#             raise ValueError(
#                 "person.tracked data must be an object."
#             )

#         frame_id = data.get(
#             "frame_id"
#         )

#         if not isinstance(
#             frame_id,
#             str,
#         ) or not frame_id.strip():
#             raise ValueError(
#                 "person.tracked frame_id must be "
#                 "a non-empty string."
#             )

#         tracks = data.get(
#             "tracks"
#         )

#         if not isinstance(
#             tracks,
#             list,
#         ):
#             raise ValueError(
#                 "person.tracked tracks must be a list."
#             )

#         validated_tracks: list[
#             Dict[str, Any]
#         ] = []

#         for index, track in enumerate(
#             tracks
#         ):
#             if not cls._validate_track(
#                 track
#             ):
#                 raise ValueError(
#                     "Invalid track at index "
#                     f"{index}."
#                 )

#             validated_tracks.append(
#                 track
#             )

#         return validated_tracks

#     # ========================================================
#     # STATE CLEANUP
#     # ========================================================

#     def cleanup_camera_tracks(
#         self,
#         camera_id: str,
#         current_event_time: datetime,
#     ) -> None:
#         """
#         Remove stale state for ONE camera only.

#         A timestamp from one camera can never delete state from
#         another camera.

#         Out-of-order events never cause cleanup because only
#         non-negative ages are considered.
#         """

#         stale_keys: list[
#             Tuple[str, str]
#         ] = []

#         for (
#             state_camera_id,
#             track_id,
#         ), state in self.track_state.items():

#             if state_camera_id != camera_id:
#                 continue

#             last_seen = state.get(
#                 "last_seen"
#             )

#             if not isinstance(
#                 last_seen,
#                 datetime,
#             ):
#                 stale_keys.append(
#                     (
#                         state_camera_id,
#                         track_id,
#                     )
#                 )
#                 continue

#             age_seconds = (
#                 current_event_time
#                 - last_seen
#             ).total_seconds()

#             if (
#                 age_seconds >= 0
#                 and age_seconds > self.track_timeout
#             ):
#                 stale_keys.append(
#                     (
#                         state_camera_id,
#                         track_id,
#                     )
#                 )

#         for key in stale_keys:
#             removed_state = self.track_state.pop(
#                 key,
#                 None,
#             )

#             if removed_state is not None:
#                 _, track_id = key

#                 print(
#                     f"[{self.agent_id}] "
#                     f"Track state expired | "
#                     f"Camera={camera_id} | "
#                     f"Track={track_id}"
#                 )

#     # ========================================================
#     # BUILD BEHAVIOR EVENT
#     # ========================================================

#     def _build_behavior_event(
#         self,
#         source_event: Dict[str, Any],
#         redis_id: str,
#         camera_id: str,
#         track: Dict[str, Any],
#         duration: float,
#         event_time: datetime,
#     ) -> Dict[str, Any]:
#         """
#         Build canonical loitering.detected event.

#         The event timestamp is always derived from the source
#         tracking event. Runtime wall-clock time is never used.
#         """

#         source_context = source_event.get(
#             "context",
#             {},
#         )

#         if not isinstance(
#             source_context,
#             dict,
#         ):
#             source_context = {}

#         source_data = source_event.get(
#             "data",
#             {},
#         )

#         if not isinstance(
#             source_data,
#             dict,
#         ):
#             source_data = {}

#         track_id = str(
#             track.get("track_id")
#         ).strip()

#         frame_id = source_data.get(
#             "frame_id"
#         )

#         if not isinstance(
#             frame_id,
#             str,
#         ) or not frame_id.strip():
#             frame_id = redis_id

#         frame_timestamp = source_data.get(
#             "frame_timestamp"
#         )

#         if not isinstance(
#             frame_timestamp,
#             str,
#         ) or not frame_timestamp.strip():
#             frame_timestamp = (
#                 event_time
#                 .isoformat()
#                 .replace(
#                     "+00:00",
#                     "Z",
#                 )
#             )

#         behavior_data = {
#             "frame_id": frame_id,
#             "frame_timestamp": frame_timestamp,
#             "track_id": track_id,
#             "duration_seconds": round(
#                 max(
#                     duration,
#                     0.0,
#                 ),
#                 2,
#             ),
#             "threshold_seconds": (
#                 self.loitering_threshold
#             ),
#             "severity": "medium",
#             "behavior": "loitering",

#             # Source lineage.
#             "source_event_id": source_event.get(
#                 "event_id"
#             ),
#             "source_redis_id": redis_id,

#             "track": {
#                 "center": track.get(
#                     "center"
#                 ),
#                 "bbox": track.get(
#                     "bbox"
#                 ),
#                 "age": track.get(
#                     "age"
#                 ),
#                 "match_distance": track.get(
#                     "match_distance"
#                 ),
#             },
#         }

#         event = create_event(
#             event_type="loitering.detected",
#             agent_id=self.agent_id,
#             instance_id=self.instance_id,
#             hostname=self.hostname,
#             camera_id=camera_id,
#             mode=source_context.get(
#                 "mode",
#                 "live",
#             ),
#             data=behavior_data,
#             trace_id=source_context.get(
#                 "trace_id"
#             ),
#             correlation_id=source_context.get(
#                 "correlation_id"
#             ),
#             incident_id=source_context.get(
#                 "incident_id"
#             ),
#             timestamp=event_time,
#         )

#         return event.to_dict()

#     # ========================================================
#     # STARTUP
#     # ========================================================

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

#             print(
#                 f"[{self.agent_id}] "
#                 f"Created consumer group: "
#                 f"{self.group_name}"
#             )

#         except Exception as error:
#             if "BUSYGROUP" not in str(error):
#                 raise

#             print(
#                 f"[{self.agent_id}] "
#                 f"Consumer group already exists: "
#                 f"{self.group_name}"
#             )

#         print(
#             f"[{self.agent_id}] "
#             "Behavior agent ready."
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

#         print(
#             f"[{self.agent_id}] "
#             f"Loitering threshold: "
#             f"{self.loitering_threshold:.2f}s"
#         )

#         print(
#             f"[{self.agent_id}] "
#             f"Track timeout: "
#             f"{self.track_timeout:.2f}s"
#         )

#         print(
#             f"[{self.agent_id}] "
#             "State model: camera + track_id"
#         )

#     # ========================================================
#     # SHUTDOWN
#     # ========================================================

#     async def on_stop(self):
#         self.track_state.clear()
#         self.last_event_timestamp.clear()

#         print(
#             f"[{self.agent_id}] "
#             "Behavior state cleared."
#         )

#     # ========================================================
#     # PROCESS ONE MESSAGE
#     # ========================================================

#     async def process_message(
#         self,
#         redis_id: str,
#         fields: Dict[str, Any],
#     ) -> None:
#         """
#         Process exactly one Redis message.

#         Permanent malformed input is ACKed.

#         Unexpected processing or Redis/publish failures are allowed
#         to propagate to the message-level isolation boundary so the
#         message remains pending.
#         """

#         if not isinstance(
#             fields,
#             dict,
#         ):
#             print(
#                 f"[{self.agent_id}] "
#                 f"Invalid Redis fields | "
#                 f"Redis={redis_id}"
#             )

#             await self.redis_client.xack(
#                 self.input_stream,
#                 self.group_name,
#                 redis_id,
#             )
#             return

#         raw_event = fields.get(
#             "event"
#         )

#         if not raw_event:
#             print(
#                 f"[{self.agent_id}] "
#                 f"Missing event payload | "
#                 f"Redis={redis_id}"
#             )

#             await self.redis_client.xack(
#                 self.input_stream,
#                 self.group_name,
#                 redis_id,
#             )
#             return

#         # ----------------------------------------------------
#         # Parse JSON.
#         # ----------------------------------------------------

#         try:
#             event = json.loads(
#                 raw_event
#             )

#         except (
#             TypeError,
#             json.JSONDecodeError,
#         ) as error:

#             print(
#                 f"[{self.agent_id}] "
#                 f"Invalid JSON event | "
#                 f"Redis={redis_id} | "
#                 f"Error={error}"
#             )

#             await self.redis_client.xack(
#                 self.input_stream,
#                 self.group_name,
#                 redis_id,
#             )
#             return

#         if not isinstance(
#             event,
#             dict,
#         ):
#             print(
#                 f"[{self.agent_id}] "
#                 f"Event is not an object | "
#                 f"Redis={redis_id}"
#             )

#             await self.redis_client.xack(
#                 self.input_stream,
#                 self.group_name,
#                 redis_id,
#             )
#             return

#         # ----------------------------------------------------
#         # Canonical envelope validation.
#         #
#         # At this stage validate_event() intentionally validates
#         # the envelope only. Specialized payload validation is
#         # performed below.
#         # ----------------------------------------------------

#         try:
#             validated_event = validate_event(
#                 event
#             )

#         except Exception as error:
#             print(
#                 f"[{self.agent_id}] "
#                 f"Invalid canonical event | "
#                 f"Redis={redis_id} | "
#                 f"Error={error}"
#             )

#             await self.redis_client.xack(
#                 self.input_stream,
#                 self.group_name,
#                 redis_id,
#             )
#             return

#         event = validated_event.to_dict()

#         # ----------------------------------------------------
#         # Only person.tracked is relevant.
#         # ----------------------------------------------------

#         if event.get(
#             "event_type"
#         ) != "person.tracked":

#             await self.redis_client.xack(
#                 self.input_stream,
#                 self.group_name,
#                 redis_id,
#             )
#             return

#         # ----------------------------------------------------
#         # Camera validation.
#         # ----------------------------------------------------

#         camera_id = self._extract_camera_id(
#             event
#         )

#         if camera_id is None:
#             print(
#                 f"[{self.agent_id}] "
#                 f"Invalid camera identity | "
#                 f"Redis={redis_id}"
#             )

#             await self.redis_client.xack(
#                 self.input_stream,
#                 self.group_name,
#                 redis_id,
#             )
#             return

#         # ----------------------------------------------------
#         # Event timestamp.
#         # ----------------------------------------------------

#         current_event_time = self._event_time(
#             event
#         )

#         if current_event_time is None:
#             print(
#                 f"[{self.agent_id}] "
#                 f"Missing or invalid timezone-aware "
#                 f"event timestamp | "
#                 f"Camera={camera_id} | "
#                 f"Redis={redis_id}"
#             )

#             await self.redis_client.xack(
#                 self.input_stream,
#                 self.group_name,
#                 redis_id,
#             )
#             return

#         # ----------------------------------------------------
#         # Per-camera ordering protection.
#         #
#         # This prevents an older event from mutating behavior
#         # state after a newer event has already been accepted.
#         # ----------------------------------------------------

#         previous_camera_time = (
#             self.last_event_timestamp.get(
#                 camera_id
#             )
#         )

#         if (
#             previous_camera_time is not None
#             and current_event_time
#             < previous_camera_time
#         ):
#             print(
#                 f"[{self.agent_id}] "
#                 f"Ignoring out-of-order camera event | "
#                 f"Camera={camera_id} | "
#                 f"EventTime="
#                 f"{current_event_time.isoformat()} | "
#                 f"LastTime="
#                 f"{previous_camera_time.isoformat()} | "
#                 f"Redis={redis_id}"
#             )

#             await self.redis_client.xack(
#                 self.input_stream,
#                 self.group_name,
#                 redis_id,
#             )
#             return

#         # ----------------------------------------------------
#         # Validate current tracking payload.
#         # ----------------------------------------------------

#         try:
#             tracks = (
#                 self._validate_tracking_payload(
#                     event
#                 )
#             )

#         except ValueError as error:
#             print(
#                 f"[{self.agent_id}] "
#                 f"Invalid person.tracked payload | "
#                 f"Camera={camera_id} | "
#                 f"Redis={redis_id} | "
#                 f"Error={error}"
#             )

#             await self.redis_client.xack(
#                 self.input_stream,
#                 self.group_name,
#                 redis_id,
#             )
#             return

#         # ----------------------------------------------------
#         # Cleanup only this camera.
#         #
#         # This happens after camera-level ordering validation.
#         # Therefore an old event cannot accidentally perform
#         # cleanup against current state.
#         # ----------------------------------------------------

#         self.cleanup_camera_tracks(
#             camera_id=camera_id,
#             current_event_time=current_event_time,
#         )

#         # ----------------------------------------------------
#         # Process all tracks.
#         # ----------------------------------------------------

#         for track in tracks:

#             track_id = str(
#                 track.get(
#                     "track_id"
#                 )
#             ).strip()

#             state_key = (
#                 camera_id,
#                 track_id,
#             )

#             state = self.track_state.get(
#                 state_key
#             )

#             # ------------------------------------------------
#             # New track.
#             # ------------------------------------------------

#             if state is None:
#                 state = {
#                     "first_seen": (
#                         current_event_time
#                     ),
#                     "last_seen": (
#                         current_event_time
#                     ),
#                     "loitering_emitted": False,
#                 }

#                 self.track_state[
#                     state_key
#                 ] = state

#             first_seen = state.get(
#                 "first_seen"
#             )

#             last_seen = state.get(
#                 "last_seen"
#             )

#             if not isinstance(
#                 first_seen,
#                 datetime,
#             ):
#                 first_seen = (
#                     current_event_time
#                 )
#                 state[
#                     "first_seen"
#                 ] = first_seen

#             if not isinstance(
#                 last_seen,
#                 datetime,
#             ):
#                 last_seen = (
#                     current_event_time
#                 )
#                 state[
#                     "last_seen"
#                 ] = last_seen

#             # ------------------------------------------------
#             # Track-level ordering protection.
#             # ------------------------------------------------

#             if current_event_time < last_seen:
#                 print(
#                     f"[{self.agent_id}] "
#                     f"Ignoring out-of-order track event | "
#                     f"Camera={camera_id} | "
#                     f"Track={track_id} | "
#                     f"Redis={redis_id}"
#                 )
#                 continue

#             # ------------------------------------------------
#             # Update observation time.
#             # ------------------------------------------------

#             state[
#                 "last_seen"
#             ] = current_event_time

#             duration = (
#                 current_event_time
#                 - first_seen
#             ).total_seconds()

#             # Defensive protection against malformed clock
#             # relationships.
#             if duration < 0:
#                 duration = 0.0

#             # ------------------------------------------------
#             # Loitering threshold.
#             # ------------------------------------------------

#             if (
#                 duration
#                 >= self.loitering_threshold
#                 and not state[
#                     "loitering_emitted"
#                 ]
#             ):

#                 behavior_event = (
#                     self._build_behavior_event(
#                         source_event=event,
#                         redis_id=redis_id,
#                         camera_id=camera_id,
#                         track=track,
#                         duration=duration,
#                         event_time=current_event_time,
#                     )
#                 )

#                 # ------------------------------------------------
#                 # Validate generated canonical envelope.
#                 # ------------------------------------------------

#                 try:
#                     validate_event(
#                         behavior_event
#                     )

#                 except Exception as error:
#                     raise ValueError(
#                         "Generated loitering event "
#                         "failed canonical validation."
#                     ) from error

#                 # ------------------------------------------------
#                 # Publish FIRST.
#                 #
#                 # Only after successful publication do we mark
#                 # this behavior as emitted.
#                 # ------------------------------------------------

#                 output_id = await self.publish(
#                     self.output_stream,
#                     behavior_event,
#                 )

#                 state[
#                     "loitering_emitted"
#                 ] = True

#                 print(
#                     f"[{self.agent_id}] "
#                     f"LOITERING | "
#                     f"Camera={camera_id} | "
#                     f"Track={track_id} | "
#                     f"Duration={duration:.1f}s | "
#                     f"Mode="
#                     f"{event.get('context', {}).get('mode', 'live')} | "
#                     f"Redis={output_id}"
#                 )

#         # ----------------------------------------------------
#         # Advance camera watermark only after successful
#         # processing of the complete message.
#         # ----------------------------------------------------

#         self.last_event_timestamp[
#             camera_id
#         ] = current_event_time

#         # ----------------------------------------------------
#         # ACK only after the complete message has succeeded.
#         # ----------------------------------------------------

#         await self.redis_client.xack(
#             self.input_stream,
#             self.group_name,
#             redis_id,
#         )

#     # ========================================================
#     # MAIN LOOP
#     # ========================================================

#     async def run(self):

#         if not self.redis_client:
#             raise RuntimeError(
#                 "Redis client is not initialized."
#             )

#         print(
#             f"[{self.agent_id}] "
#             "Behavior loop started."
#         )

#         print(
#             f"[{self.agent_id}] "
#             f"Consumer: {self.consumer_name}"
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

#                 for (
#                     _stream_name,
#                     entries,
#                 ) in messages:

#                     for (
#                         redis_id,
#                         fields,
#                     ) in entries:

#                         try:
#                             await self.process_message(
#                                 redis_id,
#                                 fields,
#                             )

#                         except asyncio.CancelledError:
#                             raise

#                         except Exception as error:
#                             # --------------------------------
#                             # IMPORTANT:
#                             #
#                             # Do NOT ACK unexpected processing
#                             # failures.
#                             #
#                             # The message remains pending and
#                             # can later be reclaimed by the
#                             # reliability layer.
#                             #
#                             # The failure is isolated to this
#                             # message.
#                             # --------------------------------

#                             print(
#                                 f"[{self.agent_id}] "
#                                 f"Message processing failure | "
#                                 f"Redis={redis_id} | "
#                                 f"{type(error).__name__}: "
#                                 f"{error}"
#                             )

#                             continue

#             except asyncio.CancelledError:
#                 raise

#             except Exception as error:
#                 # --------------------------------------------
#                 # Redis / loop-level failure.
#                 #
#                 # Keep this worker alive for transient Redis
#                 # failures rather than terminating the entire
#                 # worker process.
#                 # --------------------------------------------

#                 print(
#                     f"[{self.agent_id}] "
#                     f"Behavior loop error | "
#                     f"{type(error).__name__}: "
#                     f"{error}"
#                 )

#                 await asyncio.sleep(
#                     2
#                 )

#         print(
#             f"[{self.agent_id}] "
#             "Behavior loop stopped."
#         )


# # ============================================================
# # ENTRY POINT
# # ============================================================

# async def main():
#     agent = BehaviorAgent()
#     await agent.run_forever()


# if __name__ == "__main__":
#     asyncio.run(main())





























"""
Behavior Agent

Consumes canonical ``person.tracked`` events and detects behavioral
patterns such as loitering.

Pipeline:

    events.tracking
          |
          v
    BehaviorAgent
          |
          v
    events.behavior
          |
          +--> loitering.detected

Design principles:

- Canonical event envelope
- Camera-aware state isolation
- Historical-mode timestamp preservation
- Trace/correlation/incident propagation
- Source-event lineage
- Per-message fault isolation
- ACK only after successful processing
- No silent camera fallback
- Stateful processing requires same-camera routing/affinity

Current behavior detection:

- person loitering

Important state identity:

    (camera_id, track_id)

A track ID is only meaningful inside its camera context.

Important reliability rule:

    Permanent invalid/poison message
        -> ACK

    Unexpected processing/publish failure
        -> DO NOT ACK
        -> leave message pending for recovery

IMPORTANT VALIDATION DESIGN:

The shared ``validate_event()`` function validates both:

1. the canonical BaseEvent envelope, and
2. a specialized payload when the event type is registered.

The current Tracker producer payload and the registered
``person.tracked`` specialized schema are not aligned yet.

Therefore this agent intentionally performs:

    BaseEvent.model_validate(...)
        +
    local person.tracked payload validation

instead of calling ``validate_event()`` for incoming
``person.tracked`` messages.

Generated ``loitering.detected`` events ARE validated with the
full ``validate_event()`` function because their producer and
specialized schema are expected to be aligned.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from shared.agent.base_agent import BaseAgent
from shared.schemas.event_schema import (
    BaseEvent,
    create_event,
    validate_event,
)


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_AGENT_ID = os.getenv(
    "BEHAVIOR_AGENT_ID",
    os.getenv("AGENT_ID", "behavior-01"),
)

DEFAULT_HEARTBEAT_INTERVAL = int(
    os.getenv(
        "HEARTBEAT_INTERVAL",
        "10",
    )
)

INPUT_STREAM = os.getenv(
    "BEHAVIOR_INPUT_STREAM",
    "events.tracking",
)

OUTPUT_STREAM = os.getenv(
    "BEHAVIOR_OUTPUT_STREAM",
    "events.behavior",
)

GROUP_NAME = os.getenv(
    "BEHAVIOR_GROUP",
    "behavior-workers",
)

CONSUMER_NAME = os.getenv(
    "BEHAVIOR_CONSUMER",
    f"behavior-{uuid.uuid4().hex[:8]}",
)

LOITERING_THRESHOLD = float(
    os.getenv(
        "LOITERING_THRESHOLD",
        "30.0",
    )
)

TRACK_TIMEOUT = float(
    os.getenv(
        "TRACK_TIMEOUT",
        "2.0",
    )
)


# ============================================================
# VALIDATE STATIC CONFIGURATION
# ============================================================

def _validate_positive_finite(
    name: str,
    value: float,
) -> float:
    """
    Validate a positive finite numeric configuration value.
    """

    if not math.isfinite(value):
        raise ValueError(
            f"{name} must be finite. "
            f"Received: {value!r}"
        )

    if value <= 0:
        raise ValueError(
            f"{name} must be greater than zero. "
            f"Received: {value!r}"
        )

    return value


_validate_positive_finite(
    "LOITERING_THRESHOLD",
    LOITERING_THRESHOLD,
)

_validate_positive_finite(
    "TRACK_TIMEOUT",
    TRACK_TIMEOUT,
)


# ============================================================
# BEHAVIOR AGENT
# ============================================================

class BehaviorAgent(BaseAgent):
    """
    Stateful behavior analysis worker.

    Input:
        events.tracking

    Output:
        events.behavior

    Current detection:
        person loitering

    State identity:
        (camera_id, track_id)

    Important:

    The worker assumes camera affinity is provided by the surrounding
    routing/supervision topology. Redis consumer groups alone do NOT
    guarantee that all events for one camera reach the same worker.
    """

    def __init__(self):
        super().__init__(
            agent_id=DEFAULT_AGENT_ID,
            heartbeat_interval=DEFAULT_HEARTBEAT_INTERVAL,
        )

        self.input_stream = INPUT_STREAM
        self.output_stream = OUTPUT_STREAM
        self.group_name = GROUP_NAME
        self.consumer_name = CONSUMER_NAME

        self.loitering_threshold = LOITERING_THRESHOLD
        self.track_timeout = TRACK_TIMEOUT

        # ----------------------------------------------------
        # Stateful behavior tracking.
        #
        # Key:
        #     (camera_id, track_id)
        #
        # Value:
        #     {
        #         "first_seen": datetime,
        #         "last_seen": datetime,
        #         "loitering_emitted": bool,
        #     }
        # ----------------------------------------------------

        self.track_state: Dict[
            Tuple[str, str],
            Dict[str, Any],
        ] = {}

        # ----------------------------------------------------
        # Per-camera event watermark.
        #
        # Prevents an old event from moving camera state
        # backward in time.
        # ----------------------------------------------------

        self.last_event_timestamp: Dict[
            str,
            datetime,
        ] = {}

    # ========================================================
    # TIMESTAMP PARSING
    # ========================================================

    @staticmethod
    def _parse_timestamp(
        value: Any,
    ) -> Optional[datetime]:
        """
        Parse only timezone-aware timestamps.

        Naive timestamps are rejected rather than silently being
        interpreted as UTC. This keeps live and historical event
        semantics deterministic.
        """

        if isinstance(value, datetime):
            parsed = value

        elif isinstance(value, str):
            text = value.strip()

            if not text:
                return None

            if text.endswith("Z"):
                text = text[:-1] + "+00:00"

            try:
                parsed = datetime.fromisoformat(text)

            except ValueError:
                return None

        else:
            return None

        if (
            parsed.tzinfo is None
            or parsed.utcoffset() is None
        ):
            return None

        return parsed.astimezone(
            timezone.utc
        )

    # ========================================================
    # EVENT TIME
    # ========================================================

    @classmethod
    def _event_time(
        cls,
        event: Dict[str, Any],
    ) -> Optional[datetime]:
        """
        Determine the timestamp used for behavior calculations.

        Preference:

        1. data.frame_timestamp
        2. event.timestamp

        Never fall back to runtime wall-clock time.
        """

        data = event.get("data")

        if isinstance(data, dict):
            frame_timestamp = cls._parse_timestamp(
                data.get("frame_timestamp")
            )

            if frame_timestamp is not None:
                return frame_timestamp

        return cls._parse_timestamp(
            event.get("timestamp")
        )

    # ========================================================
    # CAMERA ID
    # ========================================================

    @staticmethod
    def _extract_camera_id(
        event: Dict[str, Any],
    ) -> Optional[str]:
        """
        Extract and validate the canonical camera identity.
        """

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
    # TRACK VALIDATION
    # ========================================================

    @staticmethod
    def _validate_track(
        track: Any,
    ) -> bool:
        """
        Validate the currently produced person.tracked structure.

        This is intentionally local.

        The registered specialized person.tracked schema currently
        rejects producer fields such as:

            source_event_id
            source_redis_id
            frame_timestamp
            detection_count
            track_count
            tracker

        Therefore this worker does not route incoming person.tracked
        events through the specialized registry validation.
        """

        if not isinstance(
            track,
            dict,
        ):
            return False

        track_id = track.get(
            "track_id"
        )

        if not isinstance(
            track_id,
            str,
        ) or not track_id.strip():
            return False

        bbox = track.get(
            "bbox"
        )

        if (
            not isinstance(
                bbox,
                (list, tuple),
            )
            or len(bbox) != 4
        ):
            return False

        try:
            bbox_values = [
                float(value)
                for value in bbox
            ]

        except (
            TypeError,
            ValueError,
        ):
            return False

        if not all(
            math.isfinite(value)
            for value in bbox_values
        ):
            return False

        x1, y1, x2, y2 = bbox_values

        if x2 < x1 or y2 < y1:
            return False

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
            return False

        try:
            center_values = [
                float(value)
                for value in center
            ]

        except (
            TypeError,
            ValueError,
        ):
            return False

        if not all(
            math.isfinite(value)
            for value in center_values
        ):
            return False

        confidence = track.get(
            "confidence"
        )

        if confidence is not None:
            try:
                confidence_value = float(
                    confidence
                )

            except (
                TypeError,
                ValueError,
            ):
                return False

            if (
                not math.isfinite(
                    confidence_value
                )
                or not 0.0 <= confidence_value <= 1.0
            ):
                return False

        return True

    # ========================================================
    # TRACKING PAYLOAD VALIDATION
    # ========================================================

    @classmethod
    def _validate_tracking_payload(
        cls,
        event: Dict[str, Any],
    ) -> list[Dict[str, Any]]:
        """
        Validate the current Tracker producer payload.

        Returns:
            Validated track dictionaries.

        Raises:
            ValueError:
                If the payload itself is malformed.
        """

        data = event.get(
            "data"
        )

        if not isinstance(
            data,
            dict,
        ):
            raise ValueError(
                "person.tracked data must be an object."
            )

        frame_id = data.get(
            "frame_id"
        )

        if not isinstance(
            frame_id,
            str,
        ) or not frame_id.strip():
            raise ValueError(
                "person.tracked frame_id must be "
                "a non-empty string."
            )

        tracks = data.get(
            "tracks"
        )

        if not isinstance(
            tracks,
            list,
        ):
            raise ValueError(
                "person.tracked tracks must be a list."
            )

        validated_tracks: list[
            Dict[str, Any]
        ] = []

        for index, track in enumerate(
            tracks
        ):
            if not cls._validate_track(
                track
            ):
                raise ValueError(
                    "Invalid track at index "
                    f"{index}."
                )

            validated_tracks.append(
                track
            )

        return validated_tracks

    # ========================================================
    # INCOMING CANONICAL ENVELOPE VALIDATION
    # ========================================================

    @staticmethod
    def _validate_canonical_envelope(
        event: Dict[str, Any],
    ) -> BaseEvent:
        """
        Validate ONLY the canonical BaseEvent envelope.

        Do NOT call validate_event() here.

        validate_event() additionally invokes the specialized event
        registry. The current person.tracked producer payload is not
        compatible with that specialized schema yet.

        BaseEvent.model_validate() validates:

        - event_id
        - event_type
        - version
        - timestamp
        - source
        - camera
        - context
        - data container

        The contents of data are validated separately by the local
        person.tracked validator.
        """

        return BaseEvent.model_validate(
            event
        )

    # ========================================================
    # STATE CLEANUP
    # ========================================================

    def cleanup_camera_tracks(
        self,
        camera_id: str,
        current_event_time: datetime,
    ) -> None:
        """
        Remove stale state for ONE camera only.

        A timestamp from one camera can never delete state from
        another camera.

        Out-of-order events never cause cleanup because only
        non-negative ages are considered.
        """

        stale_keys: list[
            Tuple[str, str]
        ] = []

        for (
            state_camera_id,
            track_id,
        ), state in self.track_state.items():

            if state_camera_id != camera_id:
                continue

            last_seen = state.get(
                "last_seen"
            )

            if not isinstance(
                last_seen,
                datetime,
            ):
                stale_keys.append(
                    (
                        state_camera_id,
                        track_id,
                    )
                )
                continue

            age_seconds = (
                current_event_time
                - last_seen
            ).total_seconds()

            if (
                age_seconds >= 0
                and age_seconds > self.track_timeout
            ):
                stale_keys.append(
                    (
                        state_camera_id,
                        track_id,
                    )
                )

        for key in stale_keys:
            removed_state = self.track_state.pop(
                key,
                None,
            )

            if removed_state is not None:
                _, track_id = key

                print(
                    f"[{self.agent_id}] "
                    f"Track state expired | "
                    f"Camera={camera_id} | "
                    f"Track={track_id}"
                )

    # ========================================================
    # BUILD BEHAVIOR EVENT
    # ========================================================

    def _build_behavior_event(
        self,
        source_event: Dict[str, Any],
        redis_id: str,
        camera_id: str,
        track: Dict[str, Any],
        duration: float,
        event_time: datetime,
    ) -> Dict[str, Any]:
        """
        Build canonical loitering.detected event.

        The event timestamp is always derived from the source
        tracking event. Runtime wall-clock time is never used.
        """

        source_context = source_event.get(
            "context",
            {},
        )

        if not isinstance(
            source_context,
            dict,
        ):
            source_context = {}

        source_data = source_event.get(
            "data",
            {},
        )

        if not isinstance(
            source_data,
            dict,
        ):
            source_data = {}

        track_id = str(
            track.get("track_id")
        ).strip()

        frame_id = source_data.get(
            "frame_id"
        )

        if not isinstance(
            frame_id,
            str,
        ) or not frame_id.strip():
            frame_id = redis_id

        frame_timestamp = source_data.get(
            "frame_timestamp"
        )

        if not isinstance(
            frame_timestamp,
            str,
        ) or not frame_timestamp.strip():
            frame_timestamp = (
                event_time
                .isoformat()
                .replace(
                    "+00:00",
                    "Z",
                )
            )

        behavior_data = {
            "frame_id": frame_id,
            "frame_timestamp": frame_timestamp,
            "track_id": track_id,
            "duration_seconds": round(
                max(
                    duration,
                    0.0,
                ),
                2,
            ),
            "threshold_seconds": (
                self.loitering_threshold
            ),
            "severity": "medium",
            "behavior": "loitering",

            # Source lineage.
            "source_event_id": source_event.get(
                "event_id"
            ),
            "source_redis_id": redis_id,

            "track": {
                "center": track.get(
                    "center"
                ),
                "bbox": track.get(
                    "bbox"
                ),
                "age": track.get(
                    "age"
                ),
                "match_distance": track.get(
                    "match_distance"
                ),
            },
        }

        event = create_event(
            event_type="loitering.detected",
            agent_id=self.agent_id,
            instance_id=self.instance_id,
            hostname=self.hostname,
            camera_id=camera_id,
            mode=source_context.get(
                "mode",
                "live",
            ),
            data=behavior_data,
            trace_id=source_context.get(
                "trace_id"
            ),
            correlation_id=source_context.get(
                "correlation_id"
            ),
            incident_id=source_context.get(
                "incident_id"
            ),
            timestamp=event_time,
        )

        return event.to_dict()

    # ========================================================
    # STARTUP
    # ========================================================

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
                f"Consumer group already exists: "
                f"{self.group_name}"
            )

        print(
            f"[{self.agent_id}] "
            "Behavior agent ready."
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
            f"Input: {self.input_stream}"
        )

        print(
            f"[{self.agent_id}] "
            f"Output: {self.output_stream}"
        )

        print(
            f"[{self.agent_id}] "
            f"Consumer: {self.consumer_name}"
        )

        print(
            f"[{self.agent_id}] "
            f"Loitering threshold: "
            f"{self.loitering_threshold:.2f}s"
        )

        print(
            f"[{self.agent_id}] "
            f"Track timeout: "
            f"{self.track_timeout:.2f}s"
        )

        print(
            f"[{self.agent_id}] "
            "State model: camera + track_id"
        )

    # ========================================================
    # SHUTDOWN
    # ========================================================

    async def on_stop(self):
        self.track_state.clear()
        self.last_event_timestamp.clear()

        print(
            f"[{self.agent_id}] "
            "Behavior state cleared."
        )

    # ========================================================
    # PROCESS ONE MESSAGE
    # ========================================================

    async def process_message(
        self,
        redis_id: str,
        fields: Dict[str, Any],
    ) -> None:
        """
        Process exactly one Redis message.

        Permanent malformed input is ACKed.

        Unexpected processing or Redis/publish failures are allowed
        to propagate to the message-level isolation boundary so the
        message remains pending.
        """

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
                self.input_stream,
                self.group_name,
                redis_id,
            )
            return

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
                self.input_stream,
                self.group_name,
                redis_id,
            )
            return

        # ----------------------------------------------------
        # Parse JSON.
        # ----------------------------------------------------

        try:
            event = json.loads(
                raw_event
            )

        except (
            TypeError,
            json.JSONDecodeError,
        ) as error:

            print(
                f"[{self.agent_id}] "
                f"Invalid JSON event | "
                f"Redis={redis_id} | "
                f"Error={error}"
            )

            await self.redis_client.xack(
                self.input_stream,
                self.group_name,
                redis_id,
            )
            return

        if not isinstance(
            event,
            dict,
        ):
            print(
                f"[{self.agent_id}] "
                f"Event is not an object | "
                f"Redis={redis_id}"
            )

            await self.redis_client.xack(
                self.input_stream,
                self.group_name,
                redis_id,
            )
            return

        # ----------------------------------------------------
        # Identify event type BEFORE validation.
        #
        # This lets the Behavior Agent decide whether the event
        # should use the envelope-only validation path.
        # ----------------------------------------------------

        event_type = event.get(
            "event_type"
        )

        if not isinstance(
            event_type,
            str,
        ) or not event_type.strip():
            print(
                f"[{self.agent_id}] "
                f"Missing event_type | "
                f"Redis={redis_id}"
            )

            await self.redis_client.xack(
                self.input_stream,
                self.group_name,
                redis_id,
            )
            return

        event_type = event_type.strip()

        # ----------------------------------------------------
        # Canonical envelope validation.
        #
        # IMPORTANT:
        #
        # Do NOT use validate_event(event) here for person.tracked.
        #
        # validate_event() invokes the specialized registry and
        # currently rejects the Tracker producer's payload.
        #
        # BaseEvent.model_validate() validates the canonical
        # envelope without invoking the specialized registry.
        # ----------------------------------------------------

        try:
            validated_event = (
                self._validate_canonical_envelope(
                    event
                )
            )

        except Exception as error:
            print(
                f"[{self.agent_id}] "
                f"Invalid canonical event | "
                f"Redis={redis_id} | "
                f"Error={error}"
            )

            await self.redis_client.xack(
                self.input_stream,
                self.group_name,
                redis_id,
            )
            return

        event = validated_event.to_dict()

        # ----------------------------------------------------
        # Only person.tracked is relevant.
        #
        # Other event types are permanent non-work for this
        # consumer and can be safely ACKed.
        # ----------------------------------------------------

        if event.get(
            "event_type"
        ) != "person.tracked":

            await self.redis_client.xack(
                self.input_stream,
                self.group_name,
                redis_id,
            )
            return

        # ----------------------------------------------------
        # Camera validation.
        # ----------------------------------------------------

        camera_id = self._extract_camera_id(
            event
        )

        if camera_id is None:
            print(
                f"[{self.agent_id}] "
                f"Invalid camera identity | "
                f"Redis={redis_id}"
            )

            await self.redis_client.xack(
                self.input_stream,
                self.group_name,
                redis_id,
            )
            return

        # ----------------------------------------------------
        # Event timestamp.
        # ----------------------------------------------------

        current_event_time = self._event_time(
            event
        )

        if current_event_time is None:
            print(
                f"[{self.agent_id}] "
                f"Missing or invalid timezone-aware "
                f"event timestamp | "
                f"Camera={camera_id} | "
                f"Redis={redis_id}"
            )

            await self.redis_client.xack(
                self.input_stream,
                self.group_name,
                redis_id,
            )
            return

        # ----------------------------------------------------
        # Per-camera ordering protection.
        #
        # This prevents an older event from mutating behavior
        # state after a newer event has already been accepted.
        # ----------------------------------------------------

        previous_camera_time = (
            self.last_event_timestamp.get(
                camera_id
            )
        )

        if (
            previous_camera_time is not None
            and current_event_time
            < previous_camera_time
        ):
            print(
                f"[{self.agent_id}] "
                f"Ignoring out-of-order camera event | "
                f"Camera={camera_id} | "
                f"EventTime="
                f"{current_event_time.isoformat()} | "
                f"LastTime="
                f"{previous_camera_time.isoformat()} | "
                f"Redis={redis_id}"
            )

            await self.redis_client.xack(
                self.input_stream,
                self.group_name,
                redis_id,
            )
            return

        # ----------------------------------------------------
        # Validate current tracking payload.
        # ----------------------------------------------------

        try:
            tracks = (
                self._validate_tracking_payload(
                    event
                )
            )

        except ValueError as error:
            print(
                f"[{self.agent_id}] "
                f"Invalid person.tracked payload | "
                f"Camera={camera_id} | "
                f"Redis={redis_id} | "
                f"Error={error}"
            )

            await self.redis_client.xack(
                self.input_stream,
                self.group_name,
                redis_id,
            )
            return

        # ----------------------------------------------------
        # Cleanup only this camera.
        #
        # This happens after camera-level ordering validation.
        # Therefore an old event cannot accidentally perform
        # cleanup against current state.
        # ----------------------------------------------------

        self.cleanup_camera_tracks(
            camera_id=camera_id,
            current_event_time=current_event_time,
        )

        # ----------------------------------------------------
        # Process all tracks.
        # ----------------------------------------------------

        for track in tracks:

            track_id = str(
                track.get(
                    "track_id"
                )
            ).strip()

            state_key = (
                camera_id,
                track_id,
            )

            state = self.track_state.get(
                state_key
            )

            # ------------------------------------------------
            # New track.
            # ------------------------------------------------

            if state is None:
                state = {
                    "first_seen": (
                        current_event_time
                    ),
                    "last_seen": (
                        current_event_time
                    ),
                    "loitering_emitted": False,
                }

                self.track_state[
                    state_key
                ] = state

            first_seen = state.get(
                "first_seen"
            )

            last_seen = state.get(
                "last_seen"
            )

            if not isinstance(
                first_seen,
                datetime,
            ):
                first_seen = (
                    current_event_time
                )
                state[
                    "first_seen"
                ] = first_seen

            if not isinstance(
                last_seen,
                datetime,
            ):
                last_seen = (
                    current_event_time
                )
                state[
                    "last_seen"
                ] = last_seen

            # ------------------------------------------------
            # Track-level ordering protection.
            # ------------------------------------------------

            if current_event_time < last_seen:
                print(
                    f"[{self.agent_id}] "
                    f"Ignoring out-of-order track event | "
                    f"Camera={camera_id} | "
                    f"Track={track_id} | "
                    f"Redis={redis_id}"
                )
                continue

            # ------------------------------------------------
            # Update observation time.
            # ------------------------------------------------

            state[
                "last_seen"
            ] = current_event_time

            duration = (
                current_event_time
                - first_seen
            ).total_seconds()

            # Defensive protection against malformed clock
            # relationships.
            if duration < 0:
                duration = 0.0

            # ------------------------------------------------
            # Loitering threshold.
            # ------------------------------------------------

            if (
                duration
                >= self.loitering_threshold
                and not state[
                    "loitering_emitted"
                ]
            ):

                behavior_event = (
                    self._build_behavior_event(
                        source_event=event,
                        redis_id=redis_id,
                        camera_id=camera_id,
                        track=track,
                        duration=duration,
                        event_time=current_event_time,
                    )
                )

                # ------------------------------------------------
                # Validate generated event.
                #
                # Here we intentionally use the FULL validation
                # path because loitering.detected should conform
                # to its registered specialized schema.
                # ------------------------------------------------

                try:
                    validate_event(
                        behavior_event
                    )

                except Exception as error:
                    raise ValueError(
                        "Generated loitering event "
                        "failed canonical/specialized "
                        "validation."
                    ) from error

                # ------------------------------------------------
                # Publish FIRST.
                #
                # Only after successful publication do we mark
                # this behavior as emitted.
                # ------------------------------------------------

                output_id = await self.publish(
                    self.output_stream,
                    behavior_event,
                )

                state[
                    "loitering_emitted"
                ] = True

                print(
                    f"[{self.agent_id}] "
                    f"LOITERING | "
                    f"Camera={camera_id} | "
                    f"Track={track_id} | "
                    f"Duration={duration:.1f}s | "
                    f"Mode="
                    f"{event.get('context', {}).get('mode', 'live')} | "
                    f"Redis={output_id}"
                )

        # ----------------------------------------------------
        # Advance camera watermark only after successful
        # processing of the complete message.
        # ----------------------------------------------------

        self.last_event_timestamp[
            camera_id
        ] = current_event_time

        # ----------------------------------------------------
        # ACK only after the complete message has succeeded.
        # ----------------------------------------------------

        await self.redis_client.xack(
            self.input_stream,
            self.group_name,
            redis_id,
        )

    # ========================================================
    # MAIN LOOP
    # ========================================================

    async def run(self):

        if not self.redis_client:
            raise RuntimeError(
                "Redis client is not initialized."
            )

        print(
            f"[{self.agent_id}] "
            "Behavior loop started."
        )

        print(
            f"[{self.agent_id}] "
            f"Consumer: {self.consumer_name}"
        )

        while self.running:

            try:
                messages = await (
                    self.redis_client.xreadgroup(
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
                    _stream_name,
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
                            # --------------------------------
                            # IMPORTANT:
                            #
                            # Do NOT ACK unexpected processing
                            # failures.
                            #
                            # The message remains pending and
                            # can later be reclaimed by the
                            # reliability layer.
                            #
                            # The failure is isolated to this
                            # message.
                            # --------------------------------

                            print(
                                f"[{self.agent_id}] "
                                f"Message processing failure | "
                                f"Redis={redis_id} | "
                                f"{type(error).__name__}: "
                                f"{error}"
                            )

                            continue

            except asyncio.CancelledError:
                raise

            except Exception as error:
                # --------------------------------------------
                # Redis / loop-level failure.
                #
                # Keep this worker alive for transient Redis
                # failures rather than terminating the entire
                # worker process.
                # --------------------------------------------

                print(
                    f"[{self.agent_id}] "
                    f"Behavior loop error | "
                    f"{type(error).__name__}: "
                    f"{error}"
                )

                await asyncio.sleep(
                    2
                )

        print(
            f"[{self.agent_id}] "
            "Behavior loop stopped."
        )


# ============================================================
# ENTRY POINT
# ============================================================

async def main():
    agent = BehaviorAgent()
    await agent.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
