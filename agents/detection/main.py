# # # # # # # # # import asyncio
# # # # # # # # # import json
# # # # # # # # # import os
# # # # # # # # # import uuid
# # # # # # # # # import time
# # # # # # # # # from datetime import datetime, timezone

# # # # # # # # # import cv2
# # # # # # # # # import redis.asyncio as redis
# # # # # # # # # from ultralytics import YOLO

# # # # # # # # # from shared.schemas.person_detected import PersonDetectedData


# # # # # # # # # # ============================================================
# # # # # # # # # # CONFIG
# # # # # # # # # # ============================================================

# # # # # # # # # REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
# # # # # # # # # REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# # # # # # # # # OUTPUT_STREAM = "events.detection"

# # # # # # # # # AGENT_ID = "person-detector-01"
# # # # # # # # # CAMERA_ID = "CAM01"

# # # # # # # # # CAMERA_INDEX = int(
# # # # # # # # #     os.getenv("CAMERA_INDEX", "0")
# # # # # # # # # )

# # # # # # # # # FRAME_INTERVAL_SECONDS = float(
# # # # # # # # #     os.getenv("FRAME_INTERVAL_SECONDS", "0.2")
# # # # # # # # # )

# # # # # # # # # MODEL_NAME = os.getenv(
# # # # # # # # #     "YOLO_MODEL",
# # # # # # # # #     "yolo11n.pt",
# # # # # # # # # )

# # # # # # # # # PERSON_CLASS_ID = 0

# # # # # # # # # CONFIDENCE_THRESHOLD = float(
# # # # # # # # #     os.getenv("CONFIDENCE_THRESHOLD", "0.40")
# # # # # # # # # )

# # # # # # # # # SHOW_CAMERA = (
# # # # # # # # #     os.getenv("SHOW_CAMERA", "true").lower() == "true"
# # # # # # # # # )

# # # # # # # # # HEARTBEAT_INTERVAL_SECONDS = 10


# # # # # # # # # # ============================================================
# # # # # # # # # # CAMERA FRAME PATH
# # # # # # # # # # ============================================================

# # # # # # # # # # Project root:
# # # # # # # # # # cctv-ai-intelligent-surveillance/

# # # # # # # # # PROJECT_ROOT = os.path.abspath(
# # # # # # # # #     os.path.join(
# # # # # # # # #         os.path.dirname(__file__),
# # # # # # # # #         "..",
# # # # # # # # #         "..",
# # # # # # # # #     )
# # # # # # # # # )

# # # # # # # # # # Shared frame used by FastAPI

# # # # # # # # # CAMERA_FRAME = os.path.join(
# # # # # # # # #     PROJECT_ROOT,
# # # # # # # # #     "camera_latest.jpg",
# # # # # # # # # )

# # # # # # # # # print(
# # # # # # # # #     f"Camera frame path: {CAMERA_FRAME}"
# # # # # # # # # )


# # # # # # # # # # ============================================================
# # # # # # # # # # LOAD YOLO
# # # # # # # # # # ============================================================

# # # # # # # # # print(
# # # # # # # # #     f"Loading YOLO model: {MODEL_NAME}"
# # # # # # # # # )

# # # # # # # # # model = YOLO(MODEL_NAME)

# # # # # # # # # print(
# # # # # # # # #     "YOLO model loaded successfully."
# # # # # # # # # )


# # # # # # # # # # ============================================================
# # # # # # # # # # CREATE DETECTION EVENT
# # # # # # # # # # ============================================================

# # # # # # # # # def create_detection_event(frame):

# # # # # # # # #     frame_id = str(uuid.uuid4())

# # # # # # # # #     results = model(
# # # # # # # # #         frame,
# # # # # # # # #         verbose=False,
# # # # # # # # #         conf=CONFIDENCE_THRESHOLD,
# # # # # # # # #     )

# # # # # # # # #     detections = []

# # # # # # # # #     for result in results:

# # # # # # # # #         if result.boxes is None:
# # # # # # # # #             continue

# # # # # # # # #         for box in result.boxes:

# # # # # # # # #             class_id = int(
# # # # # # # # #                 box.cls[0].item()
# # # # # # # # #             )

# # # # # # # # #             confidence = float(
# # # # # # # # #                 box.conf[0].item()
# # # # # # # # #             )

# # # # # # # # #             # ------------------------------------------------
# # # # # # # # #             # Only detect people
# # # # # # # # #             # ------------------------------------------------

# # # # # # # # #             if class_id != PERSON_CLASS_ID:
# # # # # # # # #                 continue

# # # # # # # # #             x1, y1, x2, y2 = (
# # # # # # # # #                 box.xyxy[0].tolist()
# # # # # # # # #             )

# # # # # # # # #             detection = {
# # # # # # # # #                 "detection_id": str(
# # # # # # # # #                     uuid.uuid4()
# # # # # # # # #                 ),
# # # # # # # # #                 "confidence": confidence,
# # # # # # # # #                 "bbox": [
# # # # # # # # #                     float(x1),
# # # # # # # # #                     float(y1),
# # # # # # # # #                     float(x2),
# # # # # # # # #                     float(y2),
# # # # # # # # #                 ],
# # # # # # # # #             }

# # # # # # # # #             detections.append(
# # # # # # # # #                 detection
# # # # # # # # #             )

# # # # # # # # #     event = {
# # # # # # # # #         "event_id": str(uuid.uuid4()),

# # # # # # # # #         "event_type": "person.detected",

# # # # # # # # #         "version": "1.0",

# # # # # # # # #         "timestamp": datetime.now(
# # # # # # # # #             timezone.utc
# # # # # # # # #         ).isoformat(),

# # # # # # # # #         "source": {
# # # # # # # # #             "agent_id": AGENT_ID,
# # # # # # # # #         },

# # # # # # # # #         "camera": {
# # # # # # # # #             "camera_id": CAMERA_ID,
# # # # # # # # #         },

# # # # # # # # #         "data": {
# # # # # # # # #             "frame_id": frame_id,
# # # # # # # # #             "detections": detections,
# # # # # # # # #         },
# # # # # # # # #     }

# # # # # # # # #     return event


# # # # # # # # # # ============================================================
# # # # # # # # # # DRAW DETECTIONS
# # # # # # # # # # ============================================================

# # # # # # # # # def draw_detections(
# # # # # # # # #     frame,
# # # # # # # # #     event,
# # # # # # # # # ):

# # # # # # # # #     detections = (
# # # # # # # # #         event["data"]["detections"]
# # # # # # # # #     )

# # # # # # # # #     for detection in detections:

# # # # # # # # #         x1, y1, x2, y2 = map(
# # # # # # # # #             int,
# # # # # # # # #             detection["bbox"],
# # # # # # # # #         )

# # # # # # # # #         confidence = (
# # # # # # # # #             detection["confidence"]
# # # # # # # # #         )

# # # # # # # # #         cv2.rectangle(
# # # # # # # # #             frame,
# # # # # # # # #             (x1, y1),
# # # # # # # # #             (x2, y2),
# # # # # # # # #             (0, 255, 0),
# # # # # # # # #             2,
# # # # # # # # #         )

# # # # # # # # #         label = (
# # # # # # # # #             f"Person {confidence:.2f}"
# # # # # # # # #         )

# # # # # # # # #         cv2.putText(
# # # # # # # # #             frame,
# # # # # # # # #             label,
# # # # # # # # #             (
# # # # # # # # #                 x1,
# # # # # # # # #                 max(y1 - 10, 20),
# # # # # # # # #             ),
# # # # # # # # #             cv2.FONT_HERSHEY_SIMPLEX,
# # # # # # # # #             0.6,
# # # # # # # # #             (0, 255, 0),
# # # # # # # # #             2,
# # # # # # # # #         )

# # # # # # # # #     # --------------------------------------------------------
# # # # # # # # #     # Camera label
# # # # # # # # #     # --------------------------------------------------------

# # # # # # # # #     cv2.putText(
# # # # # # # # #         frame,
# # # # # # # # #         CAMERA_ID,
# # # # # # # # #         (20, 35),
# # # # # # # # #         cv2.FONT_HERSHEY_SIMPLEX,
# # # # # # # # #         1,
# # # # # # # # #         (0, 255, 0),
# # # # # # # # #         2,
# # # # # # # # #     )

# # # # # # # # #     # --------------------------------------------------------
# # # # # # # # #     # Person count
# # # # # # # # #     # --------------------------------------------------------

# # # # # # # # #     count = len(detections)

# # # # # # # # #     cv2.putText(
# # # # # # # # #         frame,
# # # # # # # # #         f"People: {count}",
# # # # # # # # #         (20, 70),
# # # # # # # # #         cv2.FONT_HERSHEY_SIMPLEX,
# # # # # # # # #         0.8,
# # # # # # # # #         (0, 255, 255),
# # # # # # # # #         2,
# # # # # # # # #     )

# # # # # # # # #     return frame


# # # # # # # # # # ============================================================
# # # # # # # # # # OPEN CAMERA
# # # # # # # # # # ============================================================

# # # # # # # # # def open_camera():

# # # # # # # # #     camera = cv2.VideoCapture(
# # # # # # # # #         CAMERA_INDEX
# # # # # # # # #     )

# # # # # # # # #     if not camera.isOpened():

# # # # # # # # #         camera.release()

# # # # # # # # #         return None

# # # # # # # # #     # --------------------------------------------------------
# # # # # # # # #     # Keep camera buffer small.
# # # # # # # # #     #
# # # # # # # # #     # This helps prevent processing old frames.
# # # # # # # # #     # --------------------------------------------------------

# # # # # # # # #     try:
# # # # # # # # #         camera.set(
# # # # # # # # #             cv2.CAP_PROP_BUFFERSIZE,
# # # # # # # # #             1,
# # # # # # # # #         )
# # # # # # # # #     except Exception:
# # # # # # # # #         pass

# # # # # # # # #     return camera


# # # # # # # # # # ============================================================
# # # # # # # # # # MAIN
# # # # # # # # # # ============================================================

# # # # # # # # # async def main():

# # # # # # # # #     print()
# # # # # # # # #     print(
# # # # # # # # #         "=========================================="
# # # # # # # # #     )
# # # # # # # # #     print(
# # # # # # # # #         "Person Detection Agent"
# # # # # # # # #     )
# # # # # # # # #     print(
# # # # # # # # #         "=========================================="
# # # # # # # # #     )

# # # # # # # # #     print(
# # # # # # # # #         f"Agent: {AGENT_ID}"
# # # # # # # # #     )

# # # # # # # # #     print(
# # # # # # # # #         f"Camera: {CAMERA_ID}"
# # # # # # # # #     )

# # # # # # # # #     print(
# # # # # # # # #         f"Camera index: {CAMERA_INDEX}"
# # # # # # # # #     )

# # # # # # # # #     print(
# # # # # # # # #         f"Redis: "
# # # # # # # # #         f"{REDIS_HOST}:{REDIS_PORT}"
# # # # # # # # #     )

# # # # # # # # #     print(
# # # # # # # # #         f"Output stream: "
# # # # # # # # #         f"{OUTPUT_STREAM}"
# # # # # # # # #     )

# # # # # # # # #     print(
# # # # # # # # #         f"Confidence threshold: "
# # # # # # # # #         f"{CONFIDENCE_THRESHOLD}"
# # # # # # # # #     )

# # # # # # # # #     print(
# # # # # # # # #         f"Frame interval: "
# # # # # # # # #         f"{FRAME_INTERVAL_SECONDS}"
# # # # # # # # #     )

# # # # # # # # #     print(
# # # # # # # # #         f"Show camera: "
# # # # # # # # #         f"{SHOW_CAMERA}"
# # # # # # # # #     )

# # # # # # # # #     print(
# # # # # # # # #         f"Heartbeat interval: "
# # # # # # # # #         f"{HEARTBEAT_INTERVAL_SECONDS}s"
# # # # # # # # #     )

# # # # # # # # #     print(
# # # # # # # # #         f"Camera frame: "
# # # # # # # # #         f"{CAMERA_FRAME}"
# # # # # # # # #     )

# # # # # # # # #     print(
# # # # # # # # #         "=========================================="
# # # # # # # # #     )
# # # # # # # # #     print()

# # # # # # # # #     # ========================================================
# # # # # # # # #     # OPEN CAMERA
# # # # # # # # #     # ========================================================

# # # # # # # # #     camera = open_camera()

# # # # # # # # #     if camera is None:

# # # # # # # # #         print(
# # # # # # # # #             f"ERROR: Could not open camera "
# # # # # # # # #             f"index {CAMERA_INDEX}"
# # # # # # # # #         )

# # # # # # # # #         return

# # # # # # # # #     print(
# # # # # # # # #         "Camera opened successfully."
# # # # # # # # #     )

# # # # # # # # #     # ========================================================
# # # # # # # # #     # REDIS
# # # # # # # # #     # ========================================================

# # # # # # # # #     redis_client = redis.Redis(
# # # # # # # # #         host=REDIS_HOST,
# # # # # # # # #         port=REDIS_PORT,
# # # # # # # # #         decode_responses=True,
# # # # # # # # #         socket_connect_timeout=5,
# # # # # # # # #         socket_timeout=None,
# # # # # # # # #     )

# # # # # # # # #     last_heartbeat = time.monotonic()

# # # # # # # # #     try:

# # # # # # # # #         await redis_client.ping()

# # # # # # # # #         print(
# # # # # # # # #             "Redis connection successful."
# # # # # # # # #         )

# # # # # # # # #         # ====================================================
# # # # # # # # #         # DETECTION LOOP
# # # # # # # # #         # ====================================================

# # # # # # # # #         while True:

# # # # # # # # #             # ------------------------------------------------
# # # # # # # # #             # READ CAMERA FRAME
# # # # # # # # #             # ------------------------------------------------

# # # # # # # # #             success, frame = camera.read()

# # # # # # # # #             if not success or frame is None:

# # # # # # # # #                 print(
# # # # # # # # #                     "WARNING: Could not read "
# # # # # # # # #                     "camera frame."
# # # # # # # # #                 )

# # # # # # # # #                 print(
# # # # # # # # #                     "Attempting camera reconnect..."
# # # # # # # # #                 )

# # # # # # # # #                 camera.release()

# # # # # # # # #                 await asyncio.sleep(1)

# # # # # # # # #                 camera = open_camera()

# # # # # # # # #                 if camera is None:

# # # # # # # # #                     print(
# # # # # # # # #                         f"WARNING: Could not reopen "
# # # # # # # # #                         f"camera index "
# # # # # # # # #                         f"{CAMERA_INDEX}"
# # # # # # # # #                     )

# # # # # # # # #                     await asyncio.sleep(2)

# # # # # # # # #                     continue

# # # # # # # # #                 print(
# # # # # # # # #                     "Camera reconnected successfully."
# # # # # # # # #                 )

# # # # # # # # #                 continue

# # # # # # # # #             # ------------------------------------------------
# # # # # # # # #             # HEARTBEAT
# # # # # # # # #             # ------------------------------------------------

# # # # # # # # #             current_time = (
# # # # # # # # #                 time.monotonic()
# # # # # # # # #             )

# # # # # # # # #             if (
# # # # # # # # #                 current_time
# # # # # # # # #                 - last_heartbeat
# # # # # # # # #                 >= HEARTBEAT_INTERVAL_SECONDS
# # # # # # # # #             ):

# # # # # # # # #                 print(
# # # # # # # # #                     f"DETECTOR ALIVE | "
# # # # # # # # #                     f"Camera={CAMERA_ID} | "
# # # # # # # # #                     f"Frame="
# # # # # # # # #                     f"{frame.shape[1]}x"
# # # # # # # # #                     f"{frame.shape[0]}"
# # # # # # # # #                 )

# # # # # # # # #                 last_heartbeat = (
# # # # # # # # #                     current_time
# # # # # # # # #                 )

# # # # # # # # #             # ------------------------------------------------
# # # # # # # # #             # YOLO DETECTION
# # # # # # # # #             # ------------------------------------------------

# # # # # # # # #             event = create_detection_event(
# # # # # # # # #                 frame
# # # # # # # # #             )

# # # # # # # # #             # ------------------------------------------------
# # # # # # # # #             # VALIDATE EVENT
# # # # # # # # #             # ------------------------------------------------

# # # # # # # # #             PersonDetectedData.model_validate(
# # # # # # # # #                 event["data"]
# # # # # # # # #             )

# # # # # # # # #             # ------------------------------------------------
# # # # # # # # #             # PUBLISH TO REDIS
# # # # # # # # #             # ------------------------------------------------

# # # # # # # # #             redis_id = (
# # # # # # # # #                 await redis_client.xadd(
# # # # # # # # #                     OUTPUT_STREAM,
# # # # # # # # #                     {
# # # # # # # # #                         "event": json.dumps(
# # # # # # # # #                             event
# # # # # # # # #                         )
# # # # # # # # #                     },
# # # # # # # # #                 )
# # # # # # # # #             )

# # # # # # # # #             person_count = len(
# # # # # # # # #                 event["data"]["detections"]
# # # # # # # # #             )

# # # # # # # # #             print(
# # # # # # # # #                 f"DETECTED | "
# # # # # # # # #                 f"Camera={CAMERA_ID} | "
# # # # # # # # #                 f"Persons={person_count} | "
# # # # # # # # #                 f"Redis={redis_id}"
# # # # # # # # #             )

# # # # # # # # #             # ------------------------------------------------
# # # # # # # # #             # DRAW DETECTIONS
# # # # # # # # #             # ------------------------------------------------

# # # # # # # # #             display_frame = (
# # # # # # # # #                 draw_detections(
# # # # # # # # #                     frame,
# # # # # # # # #                     event,
# # # # # # # # #                 )
# # # # # # # # #             )

# # # # # # # # #             # ------------------------------------------------
# # # # # # # # #             # SAVE LATEST FRAME
# # # # # # # # #             # ------------------------------------------------

# # # # # # # # #             saved = cv2.imwrite(
# # # # # # # # #                 CAMERA_FRAME,
# # # # # # # # #                 display_frame,
# # # # # # # # #             )

# # # # # # # # #             if not saved:

# # # # # # # # #                 print(
# # # # # # # # #                     "ERROR: Could not save "
# # # # # # # # #                     f"camera frame: "
# # # # # # # # #                     f"{CAMERA_FRAME}"
# # # # # # # # #                 )

# # # # # # # # #             # ------------------------------------------------
# # # # # # # # #             # DISPLAY LOCAL CAMERA
# # # # # # # # #             # ------------------------------------------------

# # # # # # # # #             if SHOW_CAMERA:

# # # # # # # # #                 cv2.imshow(
# # # # # # # # #                     "CCTV AI - CAM01",
# # # # # # # # #                     display_frame,
# # # # # # # # #                 )

# # # # # # # # #                 key = (
# # # # # # # # #                     cv2.waitKey(1)
# # # # # # # # #                     & 0xFF
# # # # # # # # #                 )

# # # # # # # # #                 if key == ord("q"):

# # # # # # # # #                     print(
# # # # # # # # #                         "Q pressed. "
# # # # # # # # #                         "Stopping detection agent."
# # # # # # # # #                     )

# # # # # # # # #                     break

# # # # # # # # #             # ------------------------------------------------
# # # # # # # # #             # CONTROL LOOP SPEED
# # # # # # # # #             # ------------------------------------------------

# # # # # # # # #             await asyncio.sleep(
# # # # # # # # #                 FRAME_INTERVAL_SECONDS
# # # # # # # # #             )

# # # # # # # # #     except KeyboardInterrupt:

# # # # # # # # #         print(
# # # # # # # # #             "Detection agent interrupted."
# # # # # # # # #         )

# # # # # # # # #     except Exception as e:

# # # # # # # # #         print()

# # # # # # # # #         print(
# # # # # # # # #             "ERROR: Detection agent "
# # # # # # # # #             "stopped because of an exception."
# # # # # # # # #         )

# # # # # # # # #         print(
# # # # # # # # #             f"{type(e).__name__}: {e}"
# # # # # # # # #         )

# # # # # # # # #     finally:

# # # # # # # # #         # ====================================================
# # # # # # # # #         # CLEANUP
# # # # # # # # #         # ====================================================

# # # # # # # # #         if camera is not None:

# # # # # # # # #             camera.release()

# # # # # # # # #         cv2.destroyAllWindows()

# # # # # # # # #         await redis_client.aclose()

# # # # # # # # #         print()

# # # # # # # # #         print(
# # # # # # # # #             "Person Detection Agent stopped."
# # # # # # # # #         )


# # # # # # # # # # ============================================================
# # # # # # # # # # ENTRY POINT
# # # # # # # # # # ============================================================

# # # # # # # # # if __name__ == "__main__":

# # # # # # # # #     asyncio.run(main())












# # # # # # # # import asyncio
# # # # # # # # import os
# # # # # # # # import uuid

# # # # # # # # import cv2
# # # # # # # # from ultralytics import YOLO

# # # # # # # # from shared.agent.base_agent import BaseAgent
# # # # # # # # from shared.schemas.person_detected import PersonDetectedData


# # # # # # # # class PersonDetectionAgent(BaseAgent):
# # # # # # # #     """
# # # # # # # #     YOLO-based person detection agent.

# # # # # # # #     Camera -> YOLO -> person.detected -> events.detection

# # # # # # # #     BaseAgent provides:
# # # # # # # #     - Redis connection
# # # # # # # #     - Heartbeat
# # # # # # # #     - Lifecycle management
# # # # # # # #     - Graceful shutdown
# # # # # # # #     """

# # # # # # # #     def __init__(self):
# # # # # # # #         super().__init__(
# # # # # # # #             agent_id=os.getenv(
# # # # # # # #                 "AGENT_ID",
# # # # # # # #                 "person-detector-01",
# # # # # # # #             ),
# # # # # # # #             heartbeat_interval=int(
# # # # # # # #                 os.getenv(
# # # # # # # #                     "HEARTBEAT_INTERVAL",
# # # # # # # #                     "10",
# # # # # # # #                 )
# # # # # # # #             ),
# # # # # # # #         )

# # # # # # # #         self.camera_id = os.getenv(
# # # # # # # #             "CAMERA_ID",
# # # # # # # #             "CAM01",
# # # # # # # #         )

# # # # # # # #         self.camera_index = int(
# # # # # # # #             os.getenv(
# # # # # # # #                 "CAMERA_INDEX",
# # # # # # # #                 "0",
# # # # # # # #             )
# # # # # # # #         )

# # # # # # # #         self.model_path = os.getenv(
# # # # # # # #             "YOLO_MODEL",
# # # # # # # #             "yolo11n.pt",
# # # # # # # #         )

# # # # # # # #         self.confidence = float(
# # # # # # # #             os.getenv(
# # # # # # # #                 "YOLO_CONFIDENCE",
# # # # # # # #                 "0.40",
# # # # # # # #             )
# # # # # # # #         )

# # # # # # # #         self.frame_interval = float(
# # # # # # # #             os.getenv(
# # # # # # # #                 "FRAME_INTERVAL",
# # # # # # # #                 "0.2",
# # # # # # # #             )
# # # # # # # #         )

# # # # # # # #         self.show_camera = (
# # # # # # # #             os.getenv(
# # # # # # # #                 "SHOW_CAMERA",
# # # # # # # #                 "true",
# # # # # # # #             ).lower()
# # # # # # # #             == "true"
# # # # # # # #         )

# # # # # # # #         self.model = None
# # # # # # # #         self.cap = None

# # # # # # # #         self.frame_id = 0

# # # # # # # #         self.last_alive_log = 0.0

# # # # # # # #     async def on_start(self):
# # # # # # # #         print(
# # # # # # # #             f"[{self.agent_id}] "
# # # # # # # #             f"Loading YOLO model: {self.model_path}"
# # # # # # # #         )

# # # # # # # #         self.model = YOLO(self.model_path)

# # # # # # # #         print(
# # # # # # # #             f"[{self.agent_id}] "
# # # # # # # #             f"YOLO model loaded."
# # # # # # # #         )

# # # # # # # #         self.cap = cv2.VideoCapture(
# # # # # # # #             self.camera_index
# # # # # # # #         )

# # # # # # # #         if not self.cap.isOpened():
# # # # # # # #             raise RuntimeError(
# # # # # # # #                 f"Unable to open camera "
# # # # # # # #                 f"{self.camera_index}"
# # # # # # # #             )

# # # # # # # #         print(
# # # # # # # #             f"[{self.agent_id}] "
# # # # # # # #             f"Camera opened: "
# # # # # # # #             f"index={self.camera_index}"
# # # # # # # #         )

# # # # # # # #         print(
# # # # # # # #             f"[{self.agent_id}] "
# # # # # # # #             f"Camera ID: {self.camera_id}"
# # # # # # # #         )

# # # # # # # #     async def on_stop(self):
# # # # # # # #         if self.cap is not None:
# # # # # # # #             self.cap.release()
# # # # # # # #             self.cap = None

# # # # # # # #         if self.show_camera:
# # # # # # # #             try:
# # # # # # # #                 cv2.destroyAllWindows()
# # # # # # # #             except Exception:
# # # # # # # #                 pass

# # # # # # # #         print(
# # # # # # # #             f"[{self.agent_id}] "
# # # # # # # #             f"Camera resources released."
# # # # # # # #         )

# # # # # # # #     async def run(self):
# # # # # # # #         if self.model is None:
# # # # # # # #             raise RuntimeError(
# # # # # # # #                 "YOLO model is not initialized."
# # # # # # # #             )

# # # # # # # #         if self.cap is None:
# # # # # # # #             raise RuntimeError(
# # # # # # # #                 "Camera is not initialized."
# # # # # # # #             )

# # # # # # # #         print(
# # # # # # # #             f"[{self.agent_id}] "
# # # # # # # #             f"Detection loop started."
# # # # # # # #         )

# # # # # # # #         loop = asyncio.get_running_loop()

# # # # # # # #         while self.running:

# # # # # # # #             try:
# # # # # # # #                 ret, frame = await loop.run_in_executor(
# # # # # # # #                     None,
# # # # # # # #                     self.cap.read,
# # # # # # # #                 )

# # # # # # # #                 if not ret or frame is None:

# # # # # # # #                     print(
# # # # # # # #                         f"[{self.agent_id}] "
# # # # # # # #                         f"Camera frame read failed. "
# # # # # # # #                         f"Attempting reconnect..."
# # # # # # # #                     )

# # # # # # # #                     self.cap.release()

# # # # # # # #                     await asyncio.sleep(1)

# # # # # # # #                     self.cap = cv2.VideoCapture(
# # # # # # # #                         self.camera_index
# # # # # # # #                     )

# # # # # # # #                     if self.cap.isOpened():
# # # # # # # #                         print(
# # # # # # # #                             f"[{self.agent_id}] "
# # # # # # # #                             f"Camera reconnected."
# # # # # # # #                         )

# # # # # # # #                     continue

# # # # # # # #                 self.frame_id += 1

# # # # # # # #                 results = await loop.run_in_executor(
# # # # # # # #                     None,
# # # # # # # #                     lambda: self.model(
# # # # # # # #                         frame,
# # # # # # # #                         conf=self.confidence,
# # # # # # # #                         classes=[0],
# # # # # # # #                         verbose=False,
# # # # # # # #                     ),
# # # # # # # #                 )

# # # # # # # #                 detections = []

# # # # # # # #                 annotated_frame = frame.copy()

# # # # # # # #                 for result in results:

# # # # # # # #                     if result.boxes is None:
# # # # # # # #                         continue

# # # # # # # #                     boxes = result.boxes

# # # # # # # #                     for index in range(
# # # # # # # #                         len(boxes)
# # # # # # # #                     ):

# # # # # # # #                         box = boxes[index]

# # # # # # # #                         xyxy = (
# # # # # # # #                             box.xyxy[0]
# # # # # # # #                             .cpu()
# # # # # # # #                             .tolist()
# # # # # # # #                         )

# # # # # # # #                         confidence = float(
# # # # # # # #                             box.conf[0]
# # # # # # # #                             .cpu()
# # # # # # # #                             .item()
# # # # # # # #                         )

# # # # # # # #                         detection_id = (
# # # # # # # #                             f"det-"
# # # # # # # #                             f"{self.camera_id}-"
# # # # # # # #                             f"{self.frame_id}-"
# # # # # # # #                             f"{uuid.uuid4().hex[:8]}"
# # # # # # # #                         )

# # # # # # # #                         detections.append(
# # # # # # # #                             {
# # # # # # # #                                 "detection_id":
# # # # # # # #                                     detection_id,
# # # # # # # #                                 "confidence":
# # # # # # # #                                     confidence,
# # # # # # # #                                 "bbox":
# # # # # # # #                                     [
# # # # # # # #                                         float(
# # # # # # # #                                             xyxy[0]
# # # # # # # #                                         ),
# # # # # # # #                                         float(
# # # # # # # #                                             xyxy[1]
# # # # # # # #                                         ),
# # # # # # # #                                         float(
# # # # # # # #                                             xyxy[2]
# # # # # # # #                                         ),
# # # # # # # #                                         float(
# # # # # # # #                                             xyxy[3]
# # # # # # # #                                         ),
# # # # # # # #                                     ],
# # # # # # # #                             }
# # # # # # # #                         )

# # # # # # # #                         x1, y1, x2, y2 = map(
# # # # # # # #                             int,
# # # # # # # #                             xyxy,
# # # # # # # #                         )

# # # # # # # #                         cv2.rectangle(
# # # # # # # #                             annotated_frame,
# # # # # # # #                             (x1, y1),
# # # # # # # #                             (x2, y2),
# # # # # # # #                             (0, 255, 0),
# # # # # # # #                             2,
# # # # # # # #                         )

# # # # # # # #                         cv2.putText(
# # # # # # # #                             annotated_frame,
# # # # # # # #                             f"Person {confidence:.2f}",
# # # # # # # #                             (x1, max(y1 - 10, 20)),
# # # # # # # #                             cv2.FONT_HERSHEY_SIMPLEX,
# # # # # # # #                             0.5,
# # # # # # # #                             (0, 255, 0),
# # # # # # # #                             2,
# # # # # # # #                         )

# # # # # # # #                 event_data = PersonDetectedData(
# # # # # # # #                     frame_id=str(
# # # # # # # #                         self.frame_id
# # # # # # # #                     ),
# # # # # # # #                     detections=detections,
# # # # # # # #                 )

# # # # # # # #                 event = {
# # # # # # # #                     "event_id": str(
# # # # # # # #                         uuid.uuid4()
# # # # # # # #                     ),
# # # # # # # #                     "event_type":
# # # # # # # #                         "person.detected",
# # # # # # # #                     "version": "1.0",
# # # # # # # #                     "timestamp":
# # # # # # # #                         self.now(),
# # # # # # # #                     "source": {
# # # # # # # #                         "agent_id":
# # # # # # # #                             self.agent_id,
# # # # # # # #                     },
# # # # # # # #                     "camera": {
# # # # # # # #                         "camera_id":
# # # # # # # #                             self.camera_id,
# # # # # # # #                     },
# # # # # # # #                     "data":
# # # # # # # #                         event_data.model_dump(),
# # # # # # # #                 }

# # # # # # # #                 redis_id = await self.publish(
# # # # # # # #                     "events.detection",
# # # # # # # #                     event,
# # # # # # # #                 )

# # # # # # # #                 print(
# # # # # # # #                     f"DETECTED | "
# # # # # # # #                     f"Camera={self.camera_id} | "
# # # # # # # #                     f"Persons={len(detections)} | "
# # # # # # # #                     f"Redis={redis_id}"
# # # # # # # #                 )

# # # # # # # #                 cv2.imwrite(
# # # # # # # #                     "camera_latest.jpg",
# # # # # # # #                     annotated_frame,
# # # # # # # #                 )

# # # # # # # #                 if self.show_camera:

# # # # # # # #                     cv2.imshow(
# # # # # # # #                         "CCTV AI - Person Detection",
# # # # # # # #                         annotated_frame,
# # # # # # # #                     )

# # # # # # # #                     key = cv2.waitKey(1) & 0xFF

# # # # # # # #                     if key == ord("q"):
# # # # # # # #                         print(
# # # # # # # #                             f"[{self.agent_id}] "
# # # # # # # #                             f"Shutdown requested "
# # # # # # # #                             f"by operator."
# # # # # # # #                         )
# # # # # # # #                         break

# # # # # # # #                 await asyncio.sleep(
# # # # # # # #                     self.frame_interval
# # # # # # # #                 )

# # # # # # # #             except asyncio.CancelledError:
# # # # # # # #                 raise

# # # # # # # #             except Exception as error:

# # # # # # # #                 print(
# # # # # # # #                     f"[{self.agent_id}] "
# # # # # # # #                     f"Detection iteration error: "
# # # # # # # #                     f"{error}"
# # # # # # # #                 )

# # # # # # # #                 # IMPORTANT:
# # # # # # # #                 # A single bad frame must NOT
# # # # # # # #                 # terminate the whole agent.
# # # # # # # #                 await asyncio.sleep(1)

# # # # # # # #         print(
# # # # # # # #             f"[{self.agent_id}] "
# # # # # # # #             f"Detection loop stopped."
# # # # # # # #         )


# # # # # # # # async def main():
# # # # # # # #     agent = PersonDetectionAgent()

# # # # # # # #     await agent.run_forever()


# # # # # # # # if __name__ == "__main__":
# # # # # # # #     asyncio.run(main())

































# # # # # # # import asyncio
# # # # # # # import os
# # # # # # # import uuid
# # # # # # # from pathlib import Path
# # # # # # # from typing import Union

# # # # # # # import cv2
# # # # # # # from ultralytics import YOLO

# # # # # # # from shared.agent.base_agent import BaseAgent
# # # # # # # from shared.schemas.person_detected import PersonDetectedData


# # # # # # # class PersonDetectionAgent(BaseAgent):
# # # # # # #     """
# # # # # # #     Single-camera YOLO person detection worker.

# # # # # # #     Supported camera sources:
# # # # # # #         1. webcam
# # # # # # #         2. video file
# # # # # # #         3. RTSP
# # # # # # #         4. HTTP/HTTPS stream

# # # # # # #     Architecture:

# # # # # # #         Camera
# # # # # # #            ↓
# # # # # # #         OpenCV
# # # # # # #            ↓
# # # # # # #         YOLO
# # # # # # #            ↓
# # # # # # #         person.detected
# # # # # # #            ↓
# # # # # # #         Redis events.detection

# # # # # # #     IMPORTANT:
# # # # # # #         One process should handle ONE camera.

# # # # # # #         This provides fault isolation:

# # # # # # #             CAM01 worker crashes
# # # # # # #                     ↓
# # # # # # #             CAM01 restarts

# # # # # # #             CAM02/CAM03/... remain unaffected.

# # # # # # #     Environment variables:

# # # # # # #         AGENT_ID
# # # # # # #         CAMERA_ID

# # # # # # #         CAMERA_SOURCE_TYPE
# # # # # # #             webcam
# # # # # # #             file
# # # # # # #             rtsp
# # # # # # #             http

# # # # # # #         CAMERA_SOURCE

# # # # # # #         CAMERA_INDEX
# # # # # # #             Backward-compatible webcam configuration.

# # # # # # #         YOLO_MODEL
# # # # # # #         YOLO_CONFIDENCE
# # # # # # #         FRAME_INTERVAL
# # # # # # #         SHOW_CAMERA
# # # # # # #         EVIDENCE_DIR
# # # # # # #     """

# # # # # # #     def __init__(self):
# # # # # # #         super().__init__(
# # # # # # #             agent_id=os.getenv(
# # # # # # #                 "AGENT_ID",
# # # # # # #                 "person-detector-01",
# # # # # # #             ),
# # # # # # #             heartbeat_interval=int(
# # # # # # #                 os.getenv(
# # # # # # #                     "HEARTBEAT_INTERVAL",
# # # # # # #                     "10",
# # # # # # #                 )
# # # # # # #             ),
# # # # # # #         )

# # # # # # #         # -------------------------------------------------
# # # # # # #         # Camera identity
# # # # # # #         # -------------------------------------------------

# # # # # # #         self.camera_id = os.getenv(
# # # # # # #             "CAMERA_ID",
# # # # # # #             "CAM01",
# # # # # # #         ).strip()

# # # # # # #         if not self.camera_id:
# # # # # # #             raise ValueError(
# # # # # # #                 "CAMERA_ID cannot be empty."
# # # # # # #             )

# # # # # # #         # -------------------------------------------------
# # # # # # #         # Camera source
# # # # # # #         # -------------------------------------------------

# # # # # # #         self.source_type = os.getenv(
# # # # # # #             "CAMERA_SOURCE_TYPE",
# # # # # # #             "",
# # # # # # #         ).strip().lower()

# # # # # # #         self.source = os.getenv(
# # # # # # #             "CAMERA_SOURCE",
# # # # # # #             "",
# # # # # # #         ).strip()

# # # # # # #         # -------------------------------------------------
# # # # # # #         # Backward compatibility
# # # # # # #         #
# # # # # # #         # Existing setup:
# # # # # # #         #
# # # # # # #         # CAMERA_INDEX=0
# # # # # # #         #
# # # # # # #         # continues to work.
# # # # # # #         # -------------------------------------------------

# # # # # # #         if not self.source_type:
# # # # # # #             self.source_type = "webcam"

# # # # # # #         if not self.source:
# # # # # # #             self.source = os.getenv(
# # # # # # #                 "CAMERA_INDEX",
# # # # # # #                 "0",
# # # # # # #             ).strip()

# # # # # # #         # -------------------------------------------------
# # # # # # #         # Normalize webcam source
# # # # # # #         # -------------------------------------------------

# # # # # # #         if self.source_type == "webcam":
# # # # # # #             try:
# # # # # # #                 self.source = int(self.source)
# # # # # # #             except ValueError as error:
# # # # # # #                 raise ValueError(
# # # # # # #                     "For CAMERA_SOURCE_TYPE=webcam, "
# # # # # # #                     "CAMERA_SOURCE must be an integer "
# # # # # # #                     "camera index such as 0 or 1."
# # # # # # #                 ) from error

# # # # # # #         elif self.source_type in {
# # # # # # #             "file",
# # # # # # #             "rtsp",
# # # # # # #             "http",
# # # # # # #             "https",
# # # # # # #         }:
# # # # # # #             if not self.source:
# # # # # # #                 raise ValueError(
# # # # # # #                     f"CAMERA_SOURCE is required for "
# # # # # # #                     f"source type '{self.source_type}'."
# # # # # # #                 )

# # # # # # #         else:
# # # # # # #             raise ValueError(
# # # # # # #                 "Unsupported CAMERA_SOURCE_TYPE: "
# # # # # # #                 f"{self.source_type}. "
# # # # # # #                 "Supported values: webcam, file, rtsp, http, https."
# # # # # # #             )

# # # # # # #         # -------------------------------------------------
# # # # # # #         # YOLO configuration
# # # # # # #         # -------------------------------------------------

# # # # # # #         self.model_path = os.getenv(
# # # # # # #             "YOLO_MODEL",
# # # # # # #             "yolo11n.pt",
# # # # # # #         )

# # # # # # #         self.confidence = float(
# # # # # # #             os.getenv(
# # # # # # #                 "YOLO_CONFIDENCE",
# # # # # # #                 "0.40",
# # # # # # #             )
# # # # # # #         )

# # # # # # #         if not 0.0 < self.confidence <= 1.0:
# # # # # # #             raise ValueError(
# # # # # # #                 "YOLO_CONFIDENCE must be between 0 and 1."
# # # # # # #             )

# # # # # # #         # -------------------------------------------------
# # # # # # #         # Processing configuration
# # # # # # #         # -------------------------------------------------

# # # # # # #         self.frame_interval = float(
# # # # # # #             os.getenv(
# # # # # # #                 "FRAME_INTERVAL",
# # # # # # #                 "0.2",
# # # # # # #             )
# # # # # # #         )

# # # # # # #         if self.frame_interval < 0:
# # # # # # #             raise ValueError(
# # # # # # #                 "FRAME_INTERVAL cannot be negative."
# # # # # # #             )

# # # # # # #         # -------------------------------------------------
# # # # # # #         # Display configuration
# # # # # # #         #
# # # # # # #         # Default is FALSE because production systems
# # # # # # #         # should not open a GUI window for every camera.
# # # # # # #         # -------------------------------------------------

# # # # # # #         self.show_camera = (
# # # # # # #             os.getenv(
# # # # # # #                 "SHOW_CAMERA",
# # # # # # #                 "false",
# # # # # # #             ).strip().lower()
# # # # # # #             == "true"
# # # # # # #         )

# # # # # # #         # -------------------------------------------------
# # # # # # #         # Evidence configuration
# # # # # # #         #
# # # # # # #         # Every camera gets its own directory.
# # # # # # #         #
# # # # # # #         # This prevents:
# # # # # # #         #
# # # # # # #         # CAM01 -> camera_latest.jpg
# # # # # # #         # CAM02 -> camera_latest.jpg
# # # # # # #         #
# # # # # # #         # from overwriting each other.
# # # # # # #         # -------------------------------------------------

# # # # # # #         self.evidence_dir = Path(
# # # # # # #             os.getenv(
# # # # # # #                 "EVIDENCE_DIR",
# # # # # # #                 "data/evidence",
# # # # # # #             )
# # # # # # #         )

# # # # # # #         self.camera_evidence_dir = (
# # # # # # #             self.evidence_dir / self.camera_id
# # # # # # #         )

# # # # # # #         self.camera_latest_path = (
# # # # # # #             self.camera_evidence_dir
# # # # # # #             / "latest.jpg"
# # # # # # #         )

# # # # # # #         # -------------------------------------------------
# # # # # # #         # Runtime state
# # # # # # #         # -------------------------------------------------

# # # # # # #         self.model = None
# # # # # # #         self.cap = None

# # # # # # #         self.frame_id = 0

# # # # # # #         self.last_alive_log = 0.0

# # # # # # #         self.reconnect_delay = float(
# # # # # # #             os.getenv(
# # # # # # #                 "CAMERA_RECONNECT_DELAY",
# # # # # # #                 "1",
# # # # # # #             )
# # # # # # #         )

# # # # # # #         self.max_reconnect_delay = float(
# # # # # # #             os.getenv(
# # # # # # #                 "CAMERA_MAX_RECONNECT_DELAY",
# # # # # # #                 "10",
# # # # # # #             )
# # # # # # #         )

# # # # # # #     # =====================================================
# # # # # # #     # Camera helpers
# # # # # # #     # =====================================================

# # # # # # #     def _get_cv_source(self) -> Union[int, str]:
# # # # # # #         """
# # # # # # #         Convert configured camera source into the value
# # # # # # #         expected by cv2.VideoCapture().
# # # # # # #         """

# # # # # # #         if self.source_type == "webcam":
# # # # # # #             return int(self.source)

# # # # # # #         return str(self.source)

# # # # # # #     def _open_camera(self) -> bool:
# # # # # # #         """
# # # # # # #         Open the configured camera/stream.

# # # # # # #         Returns:
# # # # # # #             True  -> successfully opened
# # # # # # #             False -> failed
# # # # # # #         """

# # # # # # #         source = self._get_cv_source()

# # # # # # #         print(
# # # # # # #             f"[{self.agent_id}] "
# # # # # # #             f"Opening camera source..."
# # # # # # #         )

# # # # # # #         print(
# # # # # # #             f"[{self.agent_id}] "
# # # # # # #             f"Source type: {self.source_type}"
# # # # # # #         )

# # # # # # #         print(
# # # # # # #             f"[{self.agent_id}] "
# # # # # # #             f"Source: {source}"
# # # # # # #         )

# # # # # # #         try:
# # # # # # #             self.cap = cv2.VideoCapture(
# # # # # # #                 source
# # # # # # #             )

# # # # # # #             if not self.cap.isOpened():
# # # # # # #                 self.cap.release()
# # # # # # #                 self.cap = None

# # # # # # #                 print(
# # # # # # #                     f"[{self.agent_id}] "
# # # # # # #                     f"Unable to open camera source."
# # # # # # #                 )

# # # # # # #                 return False

# # # # # # #             print(
# # # # # # #                 f"[{self.agent_id}] "
# # # # # # #                 f"Camera source opened successfully."
# # # # # # #             )

# # # # # # #             return True

# # # # # # #         except Exception as error:
# # # # # # #             print(
# # # # # # #                 f"[{self.agent_id}] "
# # # # # # #                 f"Camera open error: {error}"
# # # # # # #             )

# # # # # # #             if self.cap is not None:
# # # # # # #                 try:
# # # # # # #                     self.cap.release()
# # # # # # #                 except Exception:
# # # # # # #                     pass

# # # # # # #             self.cap = None

# # # # # # #             return False

# # # # # # #     async def _reconnect_camera(self):
# # # # # # #         """
# # # # # # #         Reconnect the camera without terminating the agent.

# # # # # # #         The worker remains alive while the camera is unavailable.
# # # # # # #         """

# # # # # # #         if self.cap is not None:
# # # # # # #             try:
# # # # # # #                 self.cap.release()
# # # # # # #             except Exception:
# # # # # # #                 pass

# # # # # # #             self.cap = None

# # # # # # #         delay = self.reconnect_delay

# # # # # # #         while self.running:

# # # # # # #             print(
# # # # # # #                 f"[{self.agent_id}] "
# # # # # # #                 f"Camera reconnect attempt "
# # # # # # #                 f"in {delay:.1f}s..."
# # # # # # #             )

# # # # # # #             await asyncio.sleep(delay)

# # # # # # #             if not self.running:
# # # # # # #                 return False

# # # # # # #             if self._open_camera():
# # # # # # #                 print(
# # # # # # #                     f"[{self.agent_id}] "
# # # # # # #                     f"Camera reconnected successfully."
# # # # # # #                 )

# # # # # # #                 return True

# # # # # # #             delay = min(
# # # # # # #                 delay * 2,
# # # # # # #                 self.max_reconnect_delay,
# # # # # # #             )

# # # # # # #         return False

# # # # # # #     # =====================================================
# # # # # # #     # Agent lifecycle
# # # # # # #     # =====================================================

# # # # # # #     async def on_start(self):
# # # # # # #         print(
# # # # # # #             f"[{self.agent_id}] "
# # # # # # #             f"Loading YOLO model: {self.model_path}"
# # # # # # #         )

# # # # # # #         self.model = YOLO(
# # # # # # #             self.model_path
# # # # # # #         )

# # # # # # #         print(
# # # # # # #             f"[{self.agent_id}] "
# # # # # # #             f"YOLO model loaded."
# # # # # # #         )

# # # # # # #         # -------------------------------------------------
# # # # # # #         # Prepare per-camera evidence directory
# # # # # # #         # -------------------------------------------------

# # # # # # #         self.camera_evidence_dir.mkdir(
# # # # # # #             parents=True,
# # # # # # #             exist_ok=True,
# # # # # # #         )

# # # # # # #         # -------------------------------------------------
# # # # # # #         # Open camera
# # # # # # #         # -------------------------------------------------

# # # # # # #         if not self._open_camera():
# # # # # # #             raise RuntimeError(
# # # # # # #                 f"Unable to open camera source "
# # # # # # #                 f"for camera '{self.camera_id}'."
# # # # # # #             )

# # # # # # #         print(
# # # # # # #             f"[{self.agent_id}] "
# # # # # # #             f"Camera ID: {self.camera_id}"
# # # # # # #         )

# # # # # # #         print(
# # # # # # #             f"[{self.agent_id}] "
# # # # # # #             f"Source type: {self.source_type}"
# # # # # # #         )

# # # # # # #         print(
# # # # # # #             f"[{self.agent_id}] "
# # # # # # #             f"Evidence: {self.camera_latest_path}"
# # # # # # #         )

# # # # # # #     async def on_stop(self):
# # # # # # #         if self.cap is not None:

# # # # # # #             try:
# # # # # # #                 self.cap.release()
# # # # # # #             except Exception as error:
# # # # # # #                 print(
# # # # # # #                     f"[{self.agent_id}] "
# # # # # # #                     f"Camera release error: {error}"
# # # # # # #                 )

# # # # # # #             self.cap = None

# # # # # # #         if self.show_camera:

# # # # # # #             try:
# # # # # # #                 cv2.destroyAllWindows()
# # # # # # #             except Exception:
# # # # # # #                 pass

# # # # # # #         print(
# # # # # # #             f"[{self.agent_id}] "
# # # # # # #             f"Camera resources released."
# # # # # # #         )

# # # # # # #     # =====================================================
# # # # # # #     # Detection
# # # # # # #     # =====================================================

# # # # # # #     async def _run_detection(
# # # # # # #         self,
# # # # # # #         frame,
# # # # # # #         loop,
# # # # # # #     ):
# # # # # # #         """
# # # # # # #         Run YOLO inference outside the asyncio event loop.
# # # # # # #         """

# # # # # # #         return await loop.run_in_executor(
# # # # # # #             None,
# # # # # # #             lambda: self.model(
# # # # # # #                 frame,
# # # # # # #                 conf=self.confidence,
# # # # # # #                 classes=[0],
# # # # # # #                 verbose=False,
# # # # # # #             ),
# # # # # # #         )

# # # # # # #     def _build_detections(
# # # # # # #         self,
# # # # # # #         results,
# # # # # # #         annotated_frame,
# # # # # # #     ):
# # # # # # #         """
# # # # # # #         Convert YOLO results into the project's
# # # # # # #         existing detection event structure.
# # # # # # #         """

# # # # # # #         detections = []

# # # # # # #         for result in results:

# # # # # # #             if result.boxes is None:
# # # # # # #                 continue

# # # # # # #             boxes = result.boxes

# # # # # # #             for index in range(
# # # # # # #                 len(boxes)
# # # # # # #             ):

# # # # # # #                 box = boxes[index]

# # # # # # #                 xyxy = (
# # # # # # #                     box.xyxy[0]
# # # # # # #                     .cpu()
# # # # # # #                     .tolist()
# # # # # # #                 )

# # # # # # #                 confidence = float(
# # # # # # #                     box.conf[0]
# # # # # # #                     .cpu()
# # # # # # #                     .item()
# # # # # # #                 )

# # # # # # #                 detection_id = (
# # # # # # #                     f"det-"
# # # # # # #                     f"{self.camera_id}-"
# # # # # # #                     f"{self.frame_id}-"
# # # # # # #                     f"{uuid.uuid4().hex[:8]}"
# # # # # # #                 )

# # # # # # #                 detections.append(
# # # # # # #                     {
# # # # # # #                         "detection_id":
# # # # # # #                             detection_id,
# # # # # # #                         "confidence":
# # # # # # #                             confidence,
# # # # # # #                         "bbox":
# # # # # # #                             [
# # # # # # #                                 float(
# # # # # # #                                     xyxy[0]
# # # # # # #                                 ),
# # # # # # #                                 float(
# # # # # # #                                     xyxy[1]
# # # # # # #                                 ),
# # # # # # #                                 float(
# # # # # # #                                     xyxy[2]
# # # # # # #                                 ),
# # # # # # #                                 float(
# # # # # # #                                     xyxy[3]
# # # # # # #                                 ),
# # # # # # #                             ],
# # # # # # #                     }
# # # # # # #                 )

# # # # # # #                 # -------------------------------------------------
# # # # # # #                 # Annotation
# # # # # # #                 # -------------------------------------------------

# # # # # # #                 x1, y1, x2, y2 = map(
# # # # # # #                     int,
# # # # # # #                     xyxy,
# # # # # # #                 )

# # # # # # #                 cv2.rectangle(
# # # # # # #                     annotated_frame,
# # # # # # #                     (x1, y1),
# # # # # # #                     (x2, y2),
# # # # # # #                     (0, 255, 0),
# # # # # # #                     2,
# # # # # # #                 )

# # # # # # #                 cv2.putText(
# # # # # # #                     annotated_frame,
# # # # # # #                     f"Person {confidence:.2f}",
# # # # # # #                     (
# # # # # # #                         x1,
# # # # # # #                         max(
# # # # # # #                             y1 - 10,
# # # # # # #                             20,
# # # # # # #                         ),
# # # # # # #                     ),
# # # # # # #                     cv2.FONT_HERSHEY_SIMPLEX,
# # # # # # #                     0.5,
# # # # # # #                     (0, 255, 0),
# # # # # # #                     2,
# # # # # # #                 )

# # # # # # #         return detections

# # # # # # #     async def _publish_detection_event(
# # # # # # #         self,
# # # # # # #         detections,
# # # # # # #     ):
# # # # # # #         """
# # # # # # #         Publish the existing person.detected event.

# # # # # # #         IMPORTANT:
# # # # # # #         Event structure remains compatible with the
# # # # # # #         existing downstream pipeline.
# # # # # # #         """

# # # # # # #         event_data = PersonDetectedData(
# # # # # # #             frame_id=str(
# # # # # # #                 self.frame_id
# # # # # # #             ),
# # # # # # #             detections=detections,
# # # # # # #         )

# # # # # # #         event = {
# # # # # # #             "event_id": str(
# # # # # # #                 uuid.uuid4()
# # # # # # #             ),
# # # # # # #             "event_type":
# # # # # # #                 "person.detected",
# # # # # # #             "version": "1.0",
# # # # # # #             "timestamp":
# # # # # # #                 self.now(),
# # # # # # #             "source": {
# # # # # # #                 "agent_id":
# # # # # # #                     self.agent_id,
# # # # # # #             },
# # # # # # #             "camera": {
# # # # # # #                 "camera_id":
# # # # # # #                     self.camera_id,
# # # # # # #             },
# # # # # # #             "data":
# # # # # # #                 event_data.model_dump(),
# # # # # # #         }

# # # # # # #         redis_id = await self.publish(
# # # # # # #             "events.detection",
# # # # # # #             event,
# # # # # # #         )

# # # # # # #         return redis_id

# # # # # # #     # =====================================================
# # # # # # #     # Main loop
# # # # # # #     # =====================================================

# # # # # # #     async def run(self):

# # # # # # #         if self.model is None:
# # # # # # #             raise RuntimeError(
# # # # # # #                 "YOLO model is not initialized."
# # # # # # #             )

# # # # # # #         if self.cap is None:
# # # # # # #             raise RuntimeError(
# # # # # # #                 "Camera is not initialized."
# # # # # # #             )

# # # # # # #         print(
# # # # # # #             f"[{self.agent_id}] "
# # # # # # #             f"Detection loop started."
# # # # # # #         )

# # # # # # #         loop = asyncio.get_running_loop()

# # # # # # #         while self.running:

# # # # # # #             try:

# # # # # # #                 # -------------------------------------------------
# # # # # # #                 # Make sure camera is available
# # # # # # #                 # -------------------------------------------------

# # # # # # #                 if self.cap is None:
# # # # # # #                     reconnected = (
# # # # # # #                         await self._reconnect_camera()
# # # # # # #                     )

# # # # # # #                     if not reconnected:
# # # # # # #                         break

# # # # # # #                 # -------------------------------------------------
# # # # # # #                 # Read frame
# # # # # # #                 # -------------------------------------------------

# # # # # # #                 ret, frame = (
# # # # # # #                     await loop.run_in_executor(
# # # # # # #                         None,
# # # # # # #                         self.cap.read,
# # # # # # #                     )
# # # # # # #                 )

# # # # # # #                 if not ret or frame is None:

# # # # # # #                     print(
# # # # # # #                         f"[{self.agent_id}] "
# # # # # # #                         f"Camera frame read failed."
# # # # # # #                     )

# # # # # # #                     reconnected = (
# # # # # # #                         await self._reconnect_camera()
# # # # # # #                     )

# # # # # # #                     if not reconnected:
# # # # # # #                         break

# # # # # # #                     continue

# # # # # # #                 # -------------------------------------------------
# # # # # # #                 # Increment frame counter
# # # # # # #                 # -------------------------------------------------

# # # # # # #                 self.frame_id += 1

# # # # # # #                 # -------------------------------------------------
# # # # # # #                 # YOLO inference
# # # # # # #                 # -------------------------------------------------

# # # # # # #                 results = await self._run_detection(
# # # # # # #                     frame,
# # # # # # #                     loop,
# # # # # # #                 )

# # # # # # #                 # -------------------------------------------------
# # # # # # #                 # Build detection results
# # # # # # #                 # -------------------------------------------------

# # # # # # #                 annotated_frame = frame.copy()

# # # # # # #                 detections = (
# # # # # # #                     self._build_detections(
# # # # # # #                         results,
# # # # # # #                         annotated_frame,
# # # # # # #                     )
# # # # # # #                 )

# # # # # # #                 # -------------------------------------------------
# # # # # # #                 # Publish event
# # # # # # #                 # -------------------------------------------------

# # # # # # #                 redis_id = (
# # # # # # #                     await self._publish_detection_event(
# # # # # # #                         detections
# # # # # # #                     )
# # # # # # #                 )

# # # # # # #                 print(
# # # # # # #                     f"DETECTED | "
# # # # # # #                     f"Camera={self.camera_id} | "
# # # # # # #                     f"Persons={len(detections)} | "
# # # # # # #                     f"Redis={redis_id}"
# # # # # # #                 )

# # # # # # #                 # -------------------------------------------------
# # # # # # #                 # Save latest frame
# # # # # # #                 #
# # # # # # #                 # Per-camera path:
# # # # # # #                 #
# # # # # # #                 # data/evidence/CAM01/latest.jpg
# # # # # # #                 # data/evidence/CAM02/latest.jpg
# # # # # # #                 # -------------------------------------------------

# # # # # # #                 try:

# # # # # # #                     cv2.imwrite(
# # # # # # #                         str(
# # # # # # #                             self.camera_latest_path
# # # # # # #                         ),
# # # # # # #                         annotated_frame,
# # # # # # #                     )

# # # # # # #                 except Exception as error:

# # # # # # #                     print(
# # # # # # #                         f"[{self.agent_id}] "
# # # # # # #                         f"Evidence frame write error: "
# # # # # # #                         f"{error}"
# # # # # # #                     )

# # # # # # #                 # -------------------------------------------------
# # # # # # #                 # Optional local display
# # # # # # #                 # -------------------------------------------------

# # # # # # #                 if self.show_camera:

# # # # # # #                     cv2.imshow(
# # # # # # #                         f"CCTV AI - "
# # # # # # #                         f"{self.camera_id}",
# # # # # # #                         annotated_frame,
# # # # # # #                     )

# # # # # # #                     key = (
# # # # # # #                         cv2.waitKey(1)
# # # # # # #                         & 0xFF
# # # # # # #                     )

# # # # # # #                     if key == ord("q"):

# # # # # # #                         print(
# # # # # # #                             f"[{self.agent_id}] "
# # # # # # #                             f"Shutdown requested "
# # # # # # #                             f"by operator."
# # # # # # #                         )

# # # # # # #                         break

# # # # # # #                 # -------------------------------------------------
# # # # # # #                 # Processing interval
# # # # # # #                 # -------------------------------------------------

# # # # # # #                 await asyncio.sleep(
# # # # # # #                     self.frame_interval
# # # # # # #                 )

# # # # # # #             except asyncio.CancelledError:
# # # # # # #                 raise

# # # # # # #             except Exception as error:

# # # # # # #                 # -------------------------------------------------
# # # # # # #                 # IMPORTANT FAULT ISOLATION
# # # # # # #                 #
# # # # # # #                 # A single bad frame, YOLO error,
# # # # # # #                 # evidence error, or event error must
# # # # # # #                 # NOT terminate the worker.
# # # # # # #                 #
# # # # # # #                 # The worker only terminates when its
# # # # # # #                 # process itself fails or shutdown is
# # # # # # #                 # requested.
# # # # # # #                 # -------------------------------------------------

# # # # # # #                 print(
# # # # # # #                     f"[{self.agent_id}] "
# # # # # # #                     f"Detection iteration error: "
# # # # # # #                     f"{error}"
# # # # # # #                 )

# # # # # # #                 await asyncio.sleep(1)

# # # # # # #         print(
# # # # # # #             f"[{self.agent_id}] "
# # # # # # #             f"Detection loop stopped."
# # # # # # #         )


# # # # # # # # =============================================================
# # # # # # # # Entry point
# # # # # # # # =============================================================

# # # # # # # async def main():

# # # # # # #     agent = PersonDetectionAgent()

# # # # # # #     await agent.run_forever()


# # # # # # # if __name__ == "__main__":
# # # # # # #     asyncio.run(main())







































# # # # # # from __future__ import annotations

# # # # # # import asyncio
# # # # # # import os
# # # # # # import socket
# # # # # # import time
# # # # # # import uuid
# # # # # # from pathlib import Path
# # # # # # from typing import Union

# # # # # # import cv2
# # # # # # from ultralytics import YOLO

# # # # # # from shared.agent.base_agent import BaseAgent
# # # # # # from shared.schemas.event_schema import create_event


# # # # # # class PersonDetectionAgent(BaseAgent):
# # # # # #     """
# # # # # #     Single-camera YOLO person detection worker.

# # # # # #     Architecture:

# # # # # #         Camera / RTSP / HTTP / File
# # # # # #                     ↓
# # # # # #                OpenCV
# # # # # #                     ↓
# # # # # #                  YOLO
# # # # # #                     ↓
# # # # # #             person.detected
# # # # # #                     ↓
# # # # # #            events.detection

# # # # # #     IMPORTANT:

# # # # # #         One detector process handles ONE camera.

# # # # # #         This provides fault isolation:

# # # # # #             CAM01 detector crashes
# # # # # #                     ↓
# # # # # #             CAM01 worker restarts

# # # # # #             CAM02 / CAM03 / ... remain unaffected.

# # # # # #     Supported camera sources:

# # # # # #         webcam
# # # # # #         file
# # # # # #         rtsp
# # # # # #         http
# # # # # #         https

# # # # # #     Environment variables:

# # # # # #         AGENT_ID
# # # # # #         CAMERA_ID

# # # # # #         CAMERA_SOURCE_TYPE
# # # # # #             webcam
# # # # # #             file
# # # # # #             rtsp
# # # # # #             http
# # # # # #             https

# # # # # #         CAMERA_SOURCE
# # # # # #         CAMERA_INDEX

# # # # # #         YOLO_MODEL
# # # # # #         YOLO_CONFIDENCE

# # # # # #         FRAME_INTERVAL

# # # # # #         SHOW_CAMERA

# # # # # #         EVIDENCE_DIR

# # # # # #         CAMERA_RECONNECT_DELAY
# # # # # #         CAMERA_MAX_RECONNECT_DELAY

# # # # # #         HEARTBEAT_INTERVAL
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

# # # # # #         # =====================================================
# # # # # #         # Camera identity
# # # # # #         # =====================================================

# # # # # #         self.camera_id = os.getenv(
# # # # # #             "CAMERA_ID",
# # # # # #             "CAM01",
# # # # # #         ).strip()

# # # # # #         if not self.camera_id:
# # # # # #             raise ValueError(
# # # # # #                 "CAMERA_ID cannot be empty."
# # # # # #             )

# # # # # #         # =====================================================
# # # # # #         # Camera source configuration
# # # # # #         # =====================================================

# # # # # #         self.source_type = os.getenv(
# # # # # #             "CAMERA_SOURCE_TYPE",
# # # # # #             "",
# # # # # #         ).strip().lower()

# # # # # #         self.source = os.getenv(
# # # # # #             "CAMERA_SOURCE",
# # # # # #             "",
# # # # # #         ).strip()

# # # # # #         # Backward-compatible webcam configuration.
# # # # # #         if not self.source_type:
# # # # # #             self.source_type = "webcam"

# # # # # #         if not self.source:
# # # # # #             self.source = os.getenv(
# # # # # #                 "CAMERA_INDEX",
# # # # # #                 "0",
# # # # # #             ).strip()

# # # # # #         # =====================================================
# # # # # #         # Normalize / validate camera source
# # # # # #         # =====================================================

# # # # # #         if self.source_type == "webcam":
# # # # # #             try:
# # # # # #                 self.source = int(self.source)
# # # # # #             except ValueError as error:
# # # # # #                 raise ValueError(
# # # # # #                     "For CAMERA_SOURCE_TYPE=webcam, "
# # # # # #                     "CAMERA_SOURCE must be an integer "
# # # # # #                     "camera index such as 0 or 1."
# # # # # #                 ) from error

# # # # # #         elif self.source_type in {
# # # # # #             "file",
# # # # # #             "rtsp",
# # # # # #             "http",
# # # # # #             "https",
# # # # # #         }:
# # # # # #             if not self.source:
# # # # # #                 raise ValueError(
# # # # # #                     "CAMERA_SOURCE is required for "
# # # # # #                     f"source type '{self.source_type}'."
# # # # # #                 )

# # # # # #         else:
# # # # # #             raise ValueError(
# # # # # #                 "Unsupported CAMERA_SOURCE_TYPE: "
# # # # # #                 f"{self.source_type}. "
# # # # # #                 "Supported values: webcam, file, rtsp, http, https."
# # # # # #             )

# # # # # #         # =====================================================
# # # # # #         # YOLO configuration
# # # # # #         # =====================================================

# # # # # #         self.model_path = os.getenv(
# # # # # #             "YOLO_MODEL",
# # # # # #             "yolo11n.pt",
# # # # # #         ).strip()

# # # # # #         if not self.model_path:
# # # # # #             raise ValueError(
# # # # # #                 "YOLO_MODEL cannot be empty."
# # # # # #             )

# # # # # #         try:
# # # # # #             self.confidence = float(
# # # # # #                 os.getenv(
# # # # # #                     "YOLO_CONFIDENCE",
# # # # # #                     "0.40",
# # # # # #                 )
# # # # # #             )
# # # # # #         except ValueError as error:
# # # # # #             raise ValueError(
# # # # # #                 "YOLO_CONFIDENCE must be a valid number."
# # # # # #             ) from error

# # # # # #         if not 0.0 < self.confidence <= 1.0:
# # # # # #             raise ValueError(
# # # # # #                 "YOLO_CONFIDENCE must be between 0 and 1."
# # # # # #             )

# # # # # #         # =====================================================
# # # # # #         # Processing configuration
# # # # # #         # =====================================================

# # # # # #         try:
# # # # # #             self.frame_interval = float(
# # # # # #                 os.getenv(
# # # # # #                     "FRAME_INTERVAL",
# # # # # #                     "0.2",
# # # # # #                 )
# # # # # #             )
# # # # # #         except ValueError as error:
# # # # # #             raise ValueError(
# # # # # #                 "FRAME_INTERVAL must be a valid number."
# # # # # #             ) from error

# # # # # #         if self.frame_interval < 0:
# # # # # #             raise ValueError(
# # # # # #                 "FRAME_INTERVAL cannot be negative."
# # # # # #             )

# # # # # #         # =====================================================
# # # # # #         # Display configuration
# # # # # #         # =====================================================

# # # # # #         self.show_camera = (
# # # # # #             os.getenv(
# # # # # #                 "SHOW_CAMERA",
# # # # # #                 "false",
# # # # # #             ).strip().lower()
# # # # # #             == "true"
# # # # # #         )

# # # # # #         # =====================================================
# # # # # #         # Evidence configuration
# # # # # #         # =====================================================

# # # # # #         self.evidence_dir = Path(
# # # # # #             os.getenv(
# # # # # #                 "EVIDENCE_DIR",
# # # # # #                 "data/evidence",
# # # # # #             )
# # # # # #         )

# # # # # #         self.camera_evidence_dir = (
# # # # # #             self.evidence_dir / self.camera_id
# # # # # #         )

# # # # # #         self.camera_latest_path = (
# # # # # #             self.camera_evidence_dir / "latest.jpg"
# # # # # #         )

# # # # # #         # Temporary file used for atomic latest-frame replacement.
# # # # # #         self.camera_latest_temp_path = (
# # # # # #             self.camera_evidence_dir
# # # # # #             / ".latest.tmp.jpg"
# # # # # #         )

# # # # # #         # =====================================================
# # # # # #         # Runtime state
# # # # # #         # =====================================================

# # # # # #         self.model = None
# # # # # #         self.cap = None

# # # # # #         self.frame_id = 0

# # # # # #         self.hostname = socket.gethostname()

# # # # # #         self.last_frame_timestamp = None

# # # # # #         # =====================================================
# # # # # #         # Camera reconnect configuration
# # # # # #         # =====================================================

# # # # # #         try:
# # # # # #             self.reconnect_delay = float(
# # # # # #                 os.getenv(
# # # # # #                     "CAMERA_RECONNECT_DELAY",
# # # # # #                     "1",
# # # # # #                 )
# # # # # #             )

# # # # # #             self.max_reconnect_delay = float(
# # # # # #                 os.getenv(
# # # # # #                     "CAMERA_MAX_RECONNECT_DELAY",
# # # # # #                     "10",
# # # # # #                 )
# # # # # #             )
# # # # # #         except ValueError as error:
# # # # # #             raise ValueError(
# # # # # #                 "Camera reconnect delays must be valid numbers."
# # # # # #             ) from error

# # # # # #         if self.reconnect_delay <= 0:
# # # # # #             raise ValueError(
# # # # # #                 "CAMERA_RECONNECT_DELAY must be greater than 0."
# # # # # #             )

# # # # # #         if self.max_reconnect_delay < self.reconnect_delay:
# # # # # #             raise ValueError(
# # # # # #                 "CAMERA_MAX_RECONNECT_DELAY must be greater than "
# # # # # #                 "or equal to CAMERA_RECONNECT_DELAY."
# # # # # #             )

# # # # # #     # =========================================================
# # # # # #     # Camera helpers
# # # # # #     # =========================================================

# # # # # #     def _get_cv_source(self) -> Union[int, str]:
# # # # # #         """
# # # # # #         Convert configured camera source into the value
# # # # # #         expected by cv2.VideoCapture().
# # # # # #         """

# # # # # #         if self.source_type == "webcam":
# # # # # #             return int(self.source)

# # # # # #         return str(self.source)

# # # # # #     def _open_camera(self) -> bool:
# # # # # #         """
# # # # # #         Open the configured camera/stream.

# # # # # #         Returns:

# # # # # #             True  -> successfully opened
# # # # # #             False -> failed
# # # # # #         """

# # # # # #         source = self._get_cv_source()

# # # # # #         print(
# # # # # #             f"[{self.agent_id}] "
# # # # # #             f"Opening camera source..."
# # # # # #         )

# # # # # #         print(
# # # # # #             f"[{self.agent_id}] "
# # # # # #             f"Camera ID: {self.camera_id}"
# # # # # #         )

# # # # # #         print(
# # # # # #             f"[{self.agent_id}] "
# # # # # #             f"Source type: {self.source_type}"
# # # # # #         )

# # # # # #         print(
# # # # # #             f"[{self.agent_id}] "
# # # # # #             f"Source: {source}"
# # # # # #         )

# # # # # #         try:
# # # # # #             self.cap = cv2.VideoCapture(source)

# # # # # #             if not self.cap.isOpened():
# # # # # #                 try:
# # # # # #                     self.cap.release()
# # # # # #                 except Exception:
# # # # # #                     pass

# # # # # #                 self.cap = None

# # # # # #                 print(
# # # # # #                     f"[{self.agent_id}] "
# # # # # #                     f"Unable to open camera source."
# # # # # #                 )

# # # # # #                 return False

# # # # # #             print(
# # # # # #                 f"[{self.agent_id}] "
# # # # # #                 f"Camera source opened successfully."
# # # # # #             )

# # # # # #             return True

# # # # # #         except Exception as error:
# # # # # #             print(
# # # # # #                 f"[{self.agent_id}] "
# # # # # #                 f"Camera open error: {error}"
# # # # # #             )

# # # # # #             if self.cap is not None:
# # # # # #                 try:
# # # # # #                     self.cap.release()
# # # # # #                 except Exception:
# # # # # #                     pass

# # # # # #             self.cap = None

# # # # # #             return False

# # # # # #     async def _reconnect_camera(self) -> bool:
# # # # # #         """
# # # # # #         Reconnect the camera without terminating the agent.

# # # # # #         The worker remains alive while the camera is unavailable.
# # # # # #         """

# # # # # #         if self.cap is not None:
# # # # # #             try:
# # # # # #                 self.cap.release()
# # # # # #             except Exception:
# # # # # #                 pass

# # # # # #             self.cap = None

# # # # # #         delay = self.reconnect_delay

# # # # # #         while self.running:
# # # # # #             print(
# # # # # #                 f"[{self.agent_id}] "
# # # # # #                 f"Camera reconnect attempt "
# # # # # #                 f"in {delay:.1f}s..."
# # # # # #             )

# # # # # #             await asyncio.sleep(delay)

# # # # # #             if not self.running:
# # # # # #                 return False

# # # # # #             if self._open_camera():
# # # # # #                 print(
# # # # # #                     f"[{self.agent_id}] "
# # # # # #                     f"Camera reconnected successfully."
# # # # # #                 )

# # # # # #                 return True

# # # # # #             delay = min(
# # # # # #                 delay * 2,
# # # # # #                 self.max_reconnect_delay,
# # # # # #             )

# # # # # #         return False

# # # # # #     # =========================================================
# # # # # #     # Agent lifecycle
# # # # # #     # =========================================================

# # # # # #     async def on_start(self):
# # # # # #         print(
# # # # # #             f"[{self.agent_id}] "
# # # # # #             f"Loading YOLO model: {self.model_path}"
# # # # # #         )

# # # # # #         self.model = YOLO(
# # # # # #             self.model_path
# # # # # #         )

# # # # # #         print(
# # # # # #             f"[{self.agent_id}] "
# # # # # #             f"YOLO model loaded successfully."
# # # # # #         )

# # # # # #         # -----------------------------------------------------
# # # # # #         # Prepare per-camera evidence directory
# # # # # #         # -----------------------------------------------------

# # # # # #         self.camera_evidence_dir.mkdir(
# # # # # #             parents=True,
# # # # # #             exist_ok=True,
# # # # # #         )

# # # # # #         # -----------------------------------------------------
# # # # # #         # Open camera
# # # # # #         # -----------------------------------------------------

# # # # # #         if not self._open_camera():
# # # # # #             raise RuntimeError(
# # # # # #                 f"Unable to open camera source "
# # # # # #                 f"for camera '{self.camera_id}'."
# # # # # #             )

# # # # # #         print(
# # # # # #             f"[{self.agent_id}] "
# # # # # #             f"Camera ID: {self.camera_id}"
# # # # # #         )

# # # # # #         print(
# # # # # #             f"[{self.agent_id}] "
# # # # # #             f"Source type: {self.source_type}"
# # # # # #         )

# # # # # #         print(
# # # # # #             f"[{self.agent_id}] "
# # # # # #             f"Evidence: {self.camera_latest_path}"
# # # # # #         )

# # # # # #     async def on_stop(self):
# # # # # #         if self.cap is not None:
# # # # # #             try:
# # # # # #                 self.cap.release()
# # # # # #             except Exception as error:
# # # # # #                 print(
# # # # # #                     f"[{self.agent_id}] "
# # # # # #                     f"Camera release error: {error}"
# # # # # #                 )

# # # # # #             self.cap = None

# # # # # #         if self.show_camera:
# # # # # #             try:
# # # # # #                 cv2.destroyAllWindows()
# # # # # #             except Exception:
# # # # # #                 pass

# # # # # #         # Remove temporary evidence file if it exists.
# # # # # #         try:
# # # # # #             if self.camera_latest_temp_path.exists():
# # # # # #                 self.camera_latest_temp_path.unlink()
# # # # # #         except Exception:
# # # # # #             pass

# # # # # #         print(
# # # # # #             f"[{self.agent_id}] "
# # # # # #             f"Camera resources released."
# # # # # #         )

# # # # # #     # =========================================================
# # # # # #     # Detection
# # # # # #     # =========================================================

# # # # # #     async def _run_detection(
# # # # # #         self,
# # # # # #         frame,
# # # # # #         loop,
# # # # # #     ):
# # # # # #         """
# # # # # #         Run YOLO inference outside the asyncio event loop.
# # # # # #         """

# # # # # #         return await loop.run_in_executor(
# # # # # #             None,
# # # # # #             lambda: self.model(
# # # # # #                 frame,
# # # # # #                 conf=self.confidence,
# # # # # #                 classes=[0],  # COCO class 0 = person
# # # # # #                 verbose=False,
# # # # # #             ),
# # # # # #         )

# # # # # #     def _build_detections(
# # # # # #         self,
# # # # # #         results,
# # # # # #         annotated_frame,
# # # # # #     ) -> list[dict]:
# # # # # #         """
# # # # # #         Convert YOLO results into normalized detection data.

# # # # # #         The canonical event envelope is created separately.
# # # # # #         """

# # # # # #         detections = []

# # # # # #         for result in results:
# # # # # #             if result.boxes is None:
# # # # # #                 continue

# # # # # #             boxes = result.boxes

# # # # # #             for index in range(len(boxes)):
# # # # # #                 box = boxes[index]

# # # # # #                 xyxy = (
# # # # # #                     box.xyxy[0]
# # # # # #                     .cpu()
# # # # # #                     .tolist()
# # # # # #                 )

# # # # # #                 confidence = float(
# # # # # #                     box.conf[0]
# # # # # #                     .cpu()
# # # # # #                     .item()
# # # # # #                 )

# # # # # #                 detection_id = (
# # # # # #                     f"det-"
# # # # # #                     f"{self.camera_id}-"
# # # # # #                     f"{self.frame_id}-"
# # # # # #                     f"{uuid.uuid4().hex[:8]}"
# # # # # #                 )

# # # # # #                 x1 = float(xyxy[0])
# # # # # #                 y1 = float(xyxy[1])
# # # # # #                 x2 = float(xyxy[2])
# # # # # #                 y2 = float(xyxy[3])

# # # # # #                 detections.append(
# # # # # #                     {
# # # # # #                         "detection_id": detection_id,
# # # # # #                         "class": "person",
# # # # # #                         "class_id": 0,
# # # # # #                         "confidence": confidence,
# # # # # #                         "bbox": [
# # # # # #                             x1,
# # # # # #                             y1,
# # # # # #                             x2,
# # # # # #                             y2,
# # # # # #                         ],
# # # # # #                     }
# # # # # #                 )

# # # # # #                 # -------------------------------------------------
# # # # # #                 # Annotation
# # # # # #                 # -------------------------------------------------

# # # # # #                 draw_x1 = int(x1)
# # # # # #                 draw_y1 = int(y1)
# # # # # #                 draw_x2 = int(x2)
# # # # # #                 draw_y2 = int(y2)

# # # # # #                 cv2.rectangle(
# # # # # #                     annotated_frame,
# # # # # #                     (draw_x1, draw_y1),
# # # # # #                     (draw_x2, draw_y2),
# # # # # #                     (0, 255, 0),
# # # # # #                     2,
# # # # # #                 )

# # # # # #                 cv2.putText(
# # # # # #                     annotated_frame,
# # # # # #                     f"Person {confidence:.2f}",
# # # # # #                     (
# # # # # #                         draw_x1,
# # # # # #                         max(draw_y1 - 10, 20),
# # # # # #                     ),
# # # # # #                     cv2.FONT_HERSHEY_SIMPLEX,
# # # # # #                     0.5,
# # # # # #                     (0, 255, 0),
# # # # # #                     2,
# # # # # #                 )

# # # # # #         return detections

# # # # # #     # =========================================================
# # # # # #     # Event publishing
# # # # # #     # =========================================================

# # # # # #     async def _publish_detection_event(
# # # # # #         self,
# # # # # #         detections: list[dict],
# # # # # #         frame_timestamp,
# # # # # #     ):
# # # # # #         """
# # # # # #         Create and publish the canonical person.detected event.

# # # # # #         Canonical structure:

# # # # # #             event_id
# # # # # #             event_type
# # # # # #             version
# # # # # #             timestamp
# # # # # #             source
# # # # # #             camera
# # # # # #             context
# # # # # #             data

# # # # # #         The event is validated by BaseAgent.publish().
# # # # # #         """

# # # # # #         event = create_event(
# # # # # #             event_type="person.detected",
# # # # # #             agent_id=self.agent_id,
# # # # # #             instance_id=self.instance_id,
# # # # # #             hostname=self.hostname,
# # # # # #             camera_id=self.camera_id,
# # # # # #             mode="live",
# # # # # #             timestamp=frame_timestamp,
# # # # # #             data={
# # # # # #                 "frame_id": self.frame_id,
# # # # # #                 "frame_timestamp": frame_timestamp.isoformat(),
# # # # # #                 "detection_count": len(detections),
# # # # # #                 "model": self.model_path,
# # # # # #                 "confidence_threshold": self.confidence,
# # # # # #                 "detections": detections,
# # # # # #             },
# # # # # #         )

# # # # # #         redis_id = await self.publish(
# # # # # #             "events.detection",
# # # # # #             event,
# # # # # #         )

# # # # # #         return redis_id, event

# # # # # #     # =========================================================
# # # # # #     # Evidence
# # # # # #     # =========================================================

# # # # # #     def _save_latest_frame(
# # # # # #         self,
# # # # # #         annotated_frame,
# # # # # #     ) -> bool:
# # # # # #         """
# # # # # #         Save the latest annotated frame atomically.

# # # # # #         Writing to a temporary file first prevents readers from
# # # # # #         observing a partially-written JPEG.
# # # # # #         """

# # # # # #         try:
# # # # # #             success = cv2.imwrite(
# # # # # #                 str(self.camera_latest_temp_path),
# # # # # #                 annotated_frame,
# # # # # #             )

# # # # # #             if not success:
# # # # # #                 print(
# # # # # #                     f"[{self.agent_id}] "
# # # # # #                     f"Failed to encode latest evidence frame."
# # # # # #                 )

# # # # # #                 return False

# # # # # #             os.replace(
# # # # # #                 self.camera_latest_temp_path,
# # # # # #                 self.camera_latest_path,
# # # # # #             )

# # # # # #             return True

# # # # # #         except Exception as error:
# # # # # #             print(
# # # # # #                 f"[{self.agent_id}] "
# # # # # #                 f"Evidence frame write error: {error}"
# # # # # #             )

# # # # # #             try:
# # # # # #                 if self.camera_latest_temp_path.exists():
# # # # # #                     self.camera_latest_temp_path.unlink()
# # # # # #             except Exception:
# # # # # #                 pass

# # # # # #             return False

# # # # # #     # =========================================================
# # # # # #     # Main processing loop
# # # # # #     # =========================================================

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
# # # # # #             iteration_started = time.monotonic()

# # # # # #             try:
# # # # # #                 # =================================================
# # # # # #                 # Ensure camera is available
# # # # # #                 # =================================================

# # # # # #                 if self.cap is None:
# # # # # #                     reconnected = (
# # # # # #                         await self._reconnect_camera()
# # # # # #                     )

# # # # # #                     if not reconnected:
# # # # # #                         break

# # # # # #                 # =================================================
# # # # # #                 # Read frame
# # # # # #                 # =================================================

# # # # # #                 ret, frame = await loop.run_in_executor(
# # # # # #                     None,
# # # # # #                     self.cap.read,
# # # # # #                 )

# # # # # #                 if not ret or frame is None:
# # # # # #                     print(
# # # # # #                         f"[{self.agent_id}] "
# # # # # #                         f"Camera frame read failed."
# # # # # #                     )

# # # # # #                     reconnected = (
# # # # # #                         await self._reconnect_camera()
# # # # # #                     )

# # # # # #                     if not reconnected:
# # # # # #                         break

# # # # # #                     continue

# # # # # #                 # =================================================
# # # # # #                 # Frame metadata
# # # # # #                 # =================================================

# # # # # #                 self.frame_id += 1

# # # # # #                 frame_timestamp = (
# # # # # #                     self.now()
# # # # # #                 )

# # # # # #                 self.last_frame_timestamp = (
# # # # # #                     frame_timestamp
# # # # # #                 )

# # # # # #                 # =================================================
# # # # # #                 # YOLO inference
# # # # # #                 # =================================================

# # # # # #                 results = await self._run_detection(
# # # # # #                     frame,
# # # # # #                     loop,
# # # # # #                 )

# # # # # #                 # =================================================
# # # # # #                 # Build detections
# # # # # #                 # =================================================

# # # # # #                 annotated_frame = frame.copy()

# # # # # #                 detections = (
# # # # # #                     self._build_detections(
# # # # # #                         results,
# # # # # #                         annotated_frame,
# # # # # #                     )
# # # # # #                 )

# # # # # #                 # =================================================
# # # # # #                 # Publish canonical event
# # # # # #                 # =================================================

# # # # # #                 redis_id, event = (
# # # # # #                     await self._publish_detection_event(
# # # # # #                         detections,
# # # # # #                         frame_timestamp,
# # # # # #                     )
# # # # # #                 )

# # # # # #                 print(
# # # # # #                     f"DETECTED | "
# # # # # #                     f"Camera={self.camera_id} | "
# # # # # #                     f"Frame={self.frame_id} | "
# # # # # #                     f"Persons={len(detections)} | "
# # # # # #                     f"Redis={redis_id} | "
# # # # # #                     f"Event={event.event_id}"
# # # # # #                 )

# # # # # #                 # =================================================
# # # # # #                 # Save latest evidence frame
# # # # # #                 # =================================================

# # # # # #                 self._save_latest_frame(
# # # # # #                     annotated_frame
# # # # # #                 )

# # # # # #                 # =================================================
# # # # # #                 # Optional local display
# # # # # #                 # =================================================

# # # # # #                 if self.show_camera:
# # # # # #                     cv2.imshow(
# # # # # #                         f"CCTV AI - {self.camera_id}",
# # # # # #                         annotated_frame,
# # # # # #                     )

# # # # # #                     key = (
# # # # # #                         cv2.waitKey(1)
# # # # # #                         & 0xFF
# # # # # #                     )

# # # # # #                     if key == ord("q"):
# # # # # #                         print(
# # # # # #                             f"[{self.agent_id}] "
# # # # # #                             f"Shutdown requested "
# # # # # #                             f"by operator."
# # # # # #                         )

# # # # # #                         break

# # # # # #                 # =================================================
# # # # # #                 # Processing interval
# # # # # #                 # =================================================

# # # # # #                 elapsed = (
# # # # # #                     time.monotonic()
# # # # # #                     - iteration_started
# # # # # #                 )

# # # # # #                 sleep_time = max(
# # # # # #                     0.0,
# # # # # #                     self.frame_interval - elapsed,
# # # # # #                 )

# # # # # #                 if sleep_time > 0:
# # # # # #                     await asyncio.sleep(
# # # # # #                         sleep_time
# # # # # #                     )

# # # # # #             except asyncio.CancelledError:
# # # # # #                 raise

# # # # # #             except Exception as error:
# # # # # #                 # =================================================
# # # # # #                 # FAULT ISOLATION
# # # # # #                 #
# # # # # #                 # A single bad frame, YOLO inference failure,
# # # # # #                 # evidence failure, or event-processing failure
# # # # # #                 # must NOT terminate this camera worker.
# # # # # #                 #
# # # # # #                 # Other camera workers are separate processes.
# # # # # #                 # =================================================

# # # # # #                 print(
# # # # # #                     f"[{self.agent_id}] "
# # # # # #                     f"Detection iteration error: "
# # # # # #                     f"{type(error).__name__}: {error}"
# # # # # #                 )

# # # # # #                 await asyncio.sleep(1)

# # # # # #         print(
# # # # # #             f"[{self.agent_id}] "
# # # # # #             f"Detection loop stopped."
# # # # # #         )


# # # # # # # =============================================================
# # # # # # # Entry point
# # # # # # # =============================================================

# # # # # # async def main():
# # # # # #     agent = PersonDetectionAgent()

# # # # # #     await agent.run_forever()


# # # # # # if __name__ == "__main__":
# # # # # #     asyncio.run(main())









# # # # # from __future__ import annotations

# # # # # import asyncio
# # # # # import math
# # # # # import os
# # # # # import socket
# # # # # import time
# # # # # import uuid
# # # # # from pathlib import Path
# # # # # from typing import Any, Union

# # # # # import cv2
# # # # # from ultralytics import YOLO

# # # # # from shared.agent.base_agent import BaseAgent
# # # # # from shared.schemas.event_schema import create_event


# # # # # class PersonDetectionAgent(BaseAgent):
# # # # #     """
# # # # #     Single-camera YOLO person detection worker.

# # # # #     Architecture:

# # # # #         Camera / RTSP / HTTP / File
# # # # #                     ↓
# # # # #                OpenCV
# # # # #                     ↓
# # # # #                   YOLO
# # # # #                     ↓
# # # # #              person.detected
# # # # #                     ↓
# # # # #            events.detection

# # # # #     IMPORTANT:
# # # # #         One detector process handles ONE camera.

# # # # #     Fault isolation:

# # # # #         CAM01 detector failure
# # # # #                     ↓
# # # # #              CAM01 worker
# # # # #                recovers/restarts

# # # # #         CAM02 / CAM03 / ...
# # # # #              remain unaffected.

# # # # #     Camera availability is NOT considered an agent-startup
# # # # #     requirement. A temporary camera outage must not terminate
# # # # #     this worker. The worker remains alive and repeatedly attempts
# # # # #     reconnection.

# # # # #     Supported source types:

# # # # #         webcam
# # # # #         file
# # # # #         rtsp
# # # # #         http
# # # # #         https
# # # # #     """

# # # # #     SUPPORTED_SOURCE_TYPES = {
# # # # #         "webcam",
# # # # #         "file",
# # # # #         "rtsp",
# # # # #         "http",
# # # # #         "https",
# # # # #     }

# # # # #     def __init__(self):
# # # # #         super().__init__(
# # # # #             agent_id=os.getenv(
# # # # #                 "AGENT_ID",
# # # # #                 "person-detector-01",
# # # # #             ).strip(),
# # # # #             heartbeat_interval=self._read_positive_int_env(
# # # # #                 "HEARTBEAT_INTERVAL",
# # # # #                 10,
# # # # #             ),
# # # # #         )

# # # # #         # =====================================================
# # # # #         # Camera identity
# # # # #         # =====================================================

# # # # #         self.camera_id = os.getenv(
# # # # #             "CAMERA_ID",
# # # # #             "",
# # # # #         ).strip()

# # # # #         if not self.camera_id:
# # # # #             raise ValueError(
# # # # #                 "CAMERA_ID is required. "
# # # # #                 "Do not rely on a default camera ID in a "
# # # # #                 "multi-camera deployment."
# # # # #             )

# # # # #         # =====================================================
# # # # #         # Camera source
# # # # #         # =====================================================

# # # # #         self.source_type = os.getenv(
# # # # #             "CAMERA_SOURCE_TYPE",
# # # # #             "webcam",
# # # # #         ).strip().lower()

# # # # #         self.source = os.getenv(
# # # # #             "CAMERA_SOURCE",
# # # # #             "",
# # # # #         ).strip()

# # # # #         # Backward-compatible webcam configuration.
# # # # #         if not self.source:
# # # # #             self.source = os.getenv(
# # # # #                 "CAMERA_INDEX",
# # # # #                 "0",
# # # # #             ).strip()

# # # # #         self._validate_source_configuration()

# # # # #         # =====================================================
# # # # #         # YOLO configuration
# # # # #         # =====================================================

# # # # #         self.model_path = os.getenv(
# # # # #             "YOLO_MODEL",
# # # # #             "yolo11n.pt",
# # # # #         ).strip()

# # # # #         if not self.model_path:
# # # # #             raise ValueError(
# # # # #                 "YOLO_MODEL cannot be empty."
# # # # #             )

# # # # #         self.confidence = self._read_float_env(
# # # # #             "YOLO_CONFIDENCE",
# # # # #             0.40,
# # # # #         )

# # # # #         if not 0.0 < self.confidence <= 1.0:
# # # # #             raise ValueError(
# # # # #                 "YOLO_CONFIDENCE must be greater than 0 "
# # # # #                 "and less than or equal to 1."
# # # # #             )

# # # # #         # =====================================================
# # # # #         # Processing configuration
# # # # #         # =====================================================

# # # # #         self.frame_interval = self._read_float_env(
# # # # #             "FRAME_INTERVAL",
# # # # #             0.2,
# # # # #         )

# # # # #         if self.frame_interval < 0:
# # # # #             raise ValueError(
# # # # #                 "FRAME_INTERVAL cannot be negative."
# # # # #             )

# # # # #         # =====================================================
# # # # #         # Display configuration
# # # # #         # =====================================================

# # # # #         self.show_camera = (
# # # # #             os.getenv(
# # # # #                 "SHOW_CAMERA",
# # # # #                 "false",
# # # # #             ).strip().lower()
# # # # #             == "true"
# # # # #         )

# # # # #         # =====================================================
# # # # #         # Evidence configuration
# # # # #         # =====================================================

# # # # #         self.evidence_dir = Path(
# # # # #             os.getenv(
# # # # #                 "EVIDENCE_DIR",
# # # # #                 "data/evidence",
# # # # #             )
# # # # #         )

# # # # #         self.camera_evidence_dir = (
# # # # #             self.evidence_dir / self.camera_id
# # # # #         )

# # # # #         self.camera_latest_path = (
# # # # #             self.camera_evidence_dir / "latest.jpg"
# # # # #         )

# # # # #         self.camera_latest_temp_path = (
# # # # #             self.camera_evidence_dir / ".latest.tmp.jpg"
# # # # #         )

# # # # #         # =====================================================
# # # # #         # Reconnect configuration
# # # # #         # =====================================================

# # # # #         self.reconnect_delay = self._read_positive_float_env(
# # # # #             "CAMERA_RECONNECT_DELAY",
# # # # #             1.0,
# # # # #         )

# # # # #         self.max_reconnect_delay = self._read_positive_float_env(
# # # # #             "CAMERA_MAX_RECONNECT_DELAY",
# # # # #             10.0,
# # # # #         )

# # # # #         if self.max_reconnect_delay < self.reconnect_delay:
# # # # #             raise ValueError(
# # # # #                 "CAMERA_MAX_RECONNECT_DELAY must be greater than "
# # # # #                 "or equal to CAMERA_RECONNECT_DELAY."
# # # # #             )

# # # # #         # =====================================================
# # # # #         # Runtime state
# # # # #         # =====================================================

# # # # #         self.model: YOLO | None = None
# # # # #         self.cap: cv2.VideoCapture | None = None

# # # # #         self.frame_id = 0
# # # # #         self.last_frame_timestamp = None

# # # # #         self.hostname = socket.gethostname()

# # # # #     # =========================================================
# # # # #     # Configuration helpers
# # # # #     # =========================================================

# # # # #     @staticmethod
# # # # #     def _read_positive_int_env(
# # # # #         name: str,
# # # # #         default: int,
# # # # #     ) -> int:
# # # # #         raw = os.getenv(name, str(default)).strip()

# # # # #         try:
# # # # #             value = int(raw)
# # # # #         except ValueError as exc:
# # # # #             raise ValueError(
# # # # #                 f"{name} must be a valid integer."
# # # # #             ) from exc

# # # # #         if value <= 0:
# # # # #             raise ValueError(
# # # # #                 f"{name} must be greater than 0."
# # # # #             )

# # # # #         return value

# # # # #     @staticmethod
# # # # #     def _read_float_env(
# # # # #         name: str,
# # # # #         default: float,
# # # # #     ) -> float:
# # # # #         raw = os.getenv(name, str(default)).strip()

# # # # #         try:
# # # # #             value = float(raw)
# # # # #         except ValueError as exc:
# # # # #             raise ValueError(
# # # # #                 f"{name} must be a valid number."
# # # # #             ) from exc

# # # # #         if not math.isfinite(value):
# # # # #             raise ValueError(
# # # # #                 f"{name} must be a finite number."
# # # # #             )

# # # # #         return value

# # # # #     @classmethod
# # # # #     def _read_positive_float_env(
# # # # #         cls,
# # # # #         name: str,
# # # # #         default: float,
# # # # #     ) -> float:
# # # # #         value = cls._read_float_env(name, default)

# # # # #         if value <= 0:
# # # # #             raise ValueError(
# # # # #                 f"{name} must be greater than 0."
# # # # #             )

# # # # #         return value

# # # # #     def _validate_source_configuration(self) -> None:
# # # # #         if self.source_type not in self.SUPPORTED_SOURCE_TYPES:
# # # # #             raise ValueError(
# # # # #                 "Unsupported CAMERA_SOURCE_TYPE: "
# # # # #                 f"{self.source_type}. "
# # # # #                 "Supported values: webcam, file, rtsp, http, https."
# # # # #             )

# # # # #         if not self.source:
# # # # #             raise ValueError(
# # # # #                 "CAMERA_SOURCE cannot be empty."
# # # # #             )

# # # # #         if self.source_type == "webcam":
# # # # #             try:
# # # # #                 int(self.source)
# # # # #             except ValueError as exc:
# # # # #                 raise ValueError(
# # # # #                     "For CAMERA_SOURCE_TYPE=webcam, "
# # # # #                     "CAMERA_SOURCE must be an integer camera "
# # # # #                     "index such as 0 or 1."
# # # # #                 ) from exc

# # # # #     # =========================================================
# # # # #     # Camera helpers
# # # # #     # =========================================================

# # # # #     def _get_cv_source(self) -> Union[int, str]:
# # # # #         if self.source_type == "webcam":
# # # # #             return int(self.source)

# # # # #         return self.source

# # # # #     def _release_camera(self) -> None:
# # # # #         camera = self.cap
# # # # #         self.cap = None

# # # # #         if camera is not None:
# # # # #             try:
# # # # #                 camera.release()
# # # # #             except Exception as exc:
# # # # #                 print(
# # # # #                     f"[{self.agent_id}] "
# # # # #                     f"Camera release error: {exc}"
# # # # #                 )

# # # # #     def _open_camera(self) -> bool:
# # # # #         """
# # # # #         Attempt to open the configured source.

# # # # #         IMPORTANT:
# # # # #             Failure here is NOT fatal to the worker.
# # # # #             The caller decides whether to retry.
# # # # #         """

# # # # #         self._release_camera()

# # # # #         source = self._get_cv_source()

# # # # #         print(
# # # # #             f"[{self.agent_id}] "
# # # # #             f"Opening camera source | "
# # # # #             f"Camera={self.camera_id} | "
# # # # #             f"Type={self.source_type} | "
# # # # #             f"Source={source}"
# # # # #         )

# # # # #         try:
# # # # #             capture = cv2.VideoCapture(source)

# # # # #             if not capture.isOpened():
# # # # #                 try:
# # # # #                     capture.release()
# # # # #                 except Exception:
# # # # #                     pass

# # # # #                 print(
# # # # #                     f"[{self.agent_id}] "
# # # # #                     f"Camera source unavailable | "
# # # # #                     f"Camera={self.camera_id}"
# # # # #                 )

# # # # #                 return False

# # # # #             self.cap = capture

# # # # #             print(
# # # # #                 f"[{self.agent_id}] "
# # # # #                 f"Camera source opened successfully | "
# # # # #                 f"Camera={self.camera_id}"
# # # # #             )

# # # # #             return True

# # # # #         except Exception as exc:
# # # # #             print(
# # # # #                 f"[{self.agent_id}] "
# # # # #                 f"Camera open error | "
# # # # #                 f"Camera={self.camera_id} | "
# # # # #                 f"Error={type(exc).__name__}: {exc}"
# # # # #             )

# # # # #             self._release_camera()

# # # # #             return False

# # # # #     async def _reconnect_camera(self) -> bool:
# # # # #         """
# # # # #         Keep the worker alive while the camera is unavailable.

# # # # #         Exponential backoff prevents a failed camera from
# # # # #         generating an aggressive reconnect loop.
# # # # #         """

# # # # #         self._release_camera()

# # # # #         delay = self.reconnect_delay

# # # # #         while self.running:
# # # # #             print(
# # # # #                 f"[{self.agent_id}] "
# # # # #                 f"Camera unavailable | "
# # # # #                 f"Camera={self.camera_id} | "
# # # # #                 f"Next reconnect in {delay:.1f}s"
# # # # #             )

# # # # #             await asyncio.sleep(delay)

# # # # #             if not self.running:
# # # # #                 return False

# # # # #             if self._open_camera():
# # # # #                 print(
# # # # #                     f"[{self.agent_id}] "
# # # # #                     f"Camera reconnected | "
# # # # #                     f"Camera={self.camera_id}"
# # # # #                 )
# # # # #                 return True

# # # # #             delay = min(
# # # # #                 delay * 2.0,
# # # # #                 self.max_reconnect_delay,
# # # # #             )

# # # # #         return False

# # # # #     # =========================================================
# # # # #     # Lifecycle
# # # # #     # =========================================================

# # # # #     async def on_start(self):
# # # # #         print(
# # # # #             f"[{self.agent_id}] "
# # # # #             f"Starting person detector | "
# # # # #             f"Instance={self.instance_id} | "
# # # # #             f"Hostname={self.hostname}"
# # # # #         )

# # # # #         # -----------------------------------------------------
# # # # #         # Model loading is fatal.
# # # # #         # Without YOLO this worker cannot perform its job.
# # # # #         # -----------------------------------------------------

# # # # #         print(
# # # # #             f"[{self.agent_id}] "
# # # # #             f"Loading YOLO model: {self.model_path}"
# # # # #         )

# # # # #         self.model = YOLO(self.model_path)

# # # # #         print(
# # # # #             f"[{self.agent_id}] "
# # # # #             f"YOLO model loaded successfully."
# # # # #         )

# # # # #         # -----------------------------------------------------
# # # # #         # Evidence directory
# # # # #         # -----------------------------------------------------

# # # # #         self.camera_evidence_dir.mkdir(
# # # # #             parents=True,
# # # # #             exist_ok=True,
# # # # #         )

# # # # #         # -----------------------------------------------------
# # # # #         # Camera opening is intentionally NOT fatal.
# # # # #         #
# # # # #         # A camera may be temporarily offline when the worker
# # # # #         # starts. run() will reconnect continuously.
# # # # #         # -----------------------------------------------------

# # # # #         if not self._open_camera():
# # # # #             print(
# # # # #                 f"[{self.agent_id}] "
# # # # #                 f"Camera is currently unavailable. "
# # # # #                 f"Worker will remain alive and retry."
# # # # #             )

# # # # #         print(
# # # # #             f"[{self.agent_id}] "
# # # # #             f"Camera={self.camera_id} | "
# # # # #             f"SourceType={self.source_type} | "
# # # # #             f"Evidence={self.camera_latest_path}"
# # # # #         )

# # # # #     async def on_stop(self):
# # # # #         self._release_camera()

# # # # #         if self.show_camera:
# # # # #             try:
# # # # #                 cv2.destroyAllWindows()
# # # # #             except Exception:
# # # # #                 pass

# # # # #         try:
# # # # #             if self.camera_latest_temp_path.exists():
# # # # #                 self.camera_latest_temp_path.unlink()
# # # # #         except Exception:
# # # # #             pass

# # # # #         print(
# # # # #             f"[{self.agent_id}] "
# # # # #             f"Camera resources released | "
# # # # #             f"Camera={self.camera_id}"
# # # # #         )

# # # # #     # =========================================================
# # # # #     # Detection
# # # # #     # =========================================================

# # # # #     async def _run_detection(
# # # # #         self,
# # # # #         frame: Any,
# # # # #         loop: asyncio.AbstractEventLoop,
# # # # #     ):
# # # # #         if self.model is None:
# # # # #             raise RuntimeError(
# # # # #                 "YOLO model is not initialized."
# # # # #             )

# # # # #         return await loop.run_in_executor(
# # # # #             None,
# # # # #             lambda: self.model(
# # # # #                 frame,
# # # # #                 conf=self.confidence,
# # # # #                 classes=[0],
# # # # #                 verbose=False,
# # # # #             ),
# # # # #         )

# # # # #     def _build_detections(
# # # # #         self,
# # # # #         results,
# # # # #         annotated_frame,
# # # # #     ) -> list[dict]:
# # # # #         detections: list[dict] = []

# # # # #         for result in results:
# # # # #             if result.boxes is None:
# # # # #                 continue

# # # # #             boxes = result.boxes

# # # # #             for index in range(len(boxes)):
# # # # #                 box = boxes[index]

# # # # #                 xyxy = (
# # # # #                     box.xyxy[0]
# # # # #                     .cpu()
# # # # #                     .tolist()
# # # # #                 )

# # # # #                 confidence = float(
# # # # #                     box.conf[0]
# # # # #                     .cpu()
# # # # #                     .item()
# # # # #                 )

# # # # #                 if not math.isfinite(confidence):
# # # # #                     continue

# # # # #                 x1 = float(xyxy[0])
# # # # #                 y1 = float(xyxy[1])
# # # # #                 x2 = float(xyxy[2])
# # # # #                 y2 = float(xyxy[3])

# # # # #                 coordinates = (
# # # # #                     x1,
# # # # #                     y1,
# # # # #                     x2,
# # # # #                     y2,
# # # # #                 )

# # # # #                 if not all(
# # # # #                     math.isfinite(value)
# # # # #                     for value in coordinates
# # # # #                 ):
# # # # #                     continue

# # # # #                 detection_id = (
# # # # #                     f"det-{self.camera_id}-"
# # # # #                     f"{self.frame_id}-"
# # # # #                     f"{uuid.uuid4().hex[:8]}"
# # # # #                 )

# # # # #                 detections.append(
# # # # #                     {
# # # # #                         "detection_id": detection_id,
# # # # #                         "class": "person",
# # # # #                         "class_id": 0,
# # # # #                         "confidence": confidence,
# # # # #                         "bbox": [
# # # # #                             x1,
# # # # #                             y1,
# # # # #                             x2,
# # # # #                             y2,
# # # # #                         ],
# # # # #                     }
# # # # #                 )

# # # # #                 # -------------------------------------------------
# # # # #                 # Annotation
# # # # #                 # -------------------------------------------------

# # # # #                 draw_x1 = int(x1)
# # # # #                 draw_y1 = int(y1)
# # # # #                 draw_x2 = int(x2)
# # # # #                 draw_y2 = int(y2)

# # # # #                 cv2.rectangle(
# # # # #                     annotated_frame,
# # # # #                     (draw_x1, draw_y1),
# # # # #                     (draw_x2, draw_y2),
# # # # #                     (0, 255, 0),
# # # # #                     2,
# # # # #                 )

# # # # #                 cv2.putText(
# # # # #                     annotated_frame,
# # # # #                     f"Person {confidence:.2f}",
# # # # #                     (
# # # # #                         draw_x1,
# # # # #                         max(draw_y1 - 10, 20),
# # # # #                     ),
# # # # #                     cv2.FONT_HERSHEY_SIMPLEX,
# # # # #                     0.5,
# # # # #                     (0, 255, 0),
# # # # #                     2,
# # # # #                 )

# # # # #         return detections

# # # # #     # =========================================================
# # # # #     # Event publishing
# # # # #     # =========================================================

# # # # #     async def _publish_detection_event(
# # # # #         self,
# # # # #         detections: list[dict],
# # # # #         frame_timestamp,
# # # # #     ):
# # # # #         event = create_event(
# # # # #             event_type="person.detected",
# # # # #             agent_id=self.agent_id,
# # # # #             instance_id=self.instance_id,
# # # # #             hostname=self.hostname,
# # # # #             camera_id=self.camera_id,
# # # # #             mode="live",
# # # # #             timestamp=frame_timestamp,
# # # # #             data={
# # # # #                 "frame_id": self.frame_id,
# # # # #                 "frame_timestamp": frame_timestamp.isoformat(),
# # # # #                 "detection_count": len(detections),
# # # # #                 "model": self.model_path,
# # # # #                 "confidence_threshold": self.confidence,
# # # # #                 "detections": detections,
# # # # #             },
# # # # #         )

# # # # #         redis_id = await self.publish(
# # # # #             "events.detection",
# # # # #             event,
# # # # #         )

# # # # #         return redis_id, event

# # # # #     # =========================================================
# # # # #     # Evidence
# # # # #     # =========================================================

# # # # #     def _save_latest_frame(
# # # # #         self,
# # # # #         annotated_frame,
# # # # #     ) -> bool:
# # # # #         """
# # # # #         Atomically replace latest.jpg.

# # # # #         Readers never see a partially-written JPEG.
# # # # #         """

# # # # #         try:
# # # # #             success = cv2.imwrite(
# # # # #                 str(self.camera_latest_temp_path),
# # # # #                 annotated_frame,
# # # # #             )

# # # # #             if not success:
# # # # #                 print(
# # # # #                     f"[{self.agent_id}] "
# # # # #                     f"Failed to encode latest frame | "
# # # # #                     f"Camera={self.camera_id}"
# # # # #                 )
# # # # #                 return False

# # # # #             os.replace(
# # # # #                 self.camera_latest_temp_path,
# # # # #                 self.camera_latest_path,
# # # # #             )

# # # # #             return True

# # # # #         except Exception as exc:
# # # # #             print(
# # # # #                 f"[{self.agent_id}] "
# # # # #                 f"Evidence frame write error | "
# # # # #                 f"Camera={self.camera_id} | "
# # # # #                 f"Error={type(exc).__name__}: {exc}"
# # # # #             )

# # # # #             try:
# # # # #                 if self.camera_latest_temp_path.exists():
# # # # #                     self.camera_latest_temp_path.unlink()
# # # # #             except Exception:
# # # # #                 pass

# # # # #             return False

# # # # #     # =========================================================
# # # # #     # Main processing loop
# # # # #     # =========================================================

# # # # #     async def run(self):
# # # # #         if self.model is None:
# # # # #             raise RuntimeError(
# # # # #                 "YOLO model is not initialized."
# # # # #             )

# # # # #         print(
# # # # #             f"[{self.agent_id}] "
# # # # #             f"Detection loop started | "
# # # # #             f"Camera={self.camera_id}"
# # # # #         )

# # # # #         loop = asyncio.get_running_loop()

# # # # #         while self.running:
# # # # #             iteration_started = time.monotonic()

# # # # #             try:
# # # # #                 # -------------------------------------------------
# # # # #                 # Camera unavailable
# # # # #                 # -------------------------------------------------

# # # # #                 if self.cap is None:
# # # # #                     connected = await self._reconnect_camera()

# # # # #                     if not connected:
# # # # #                         break

# # # # #                 # -------------------------------------------------
# # # # #                 # Read frame
# # # # #                 # -------------------------------------------------

# # # # #                 camera = self.cap

# # # # #                 if camera is None:
# # # # #                     continue

# # # # #                 ret, frame = await loop.run_in_executor(
# # # # #                     None,
# # # # #                     camera.read,
# # # # #                 )

# # # # #                 if not ret or frame is None:
# # # # #                     print(
# # # # #                         f"[{self.agent_id}] "
# # # # #                         f"Camera frame read failed | "
# # # # #                         f"Camera={self.camera_id}"
# # # # #                     )

# # # # #                     await self._reconnect_camera()
# # # # #                     continue

# # # # #                 # -------------------------------------------------
# # # # #                 # Frame metadata
# # # # #                 # -------------------------------------------------

# # # # #                 self.frame_id += 1

# # # # #                 frame_timestamp = self.now()

# # # # #                 self.last_frame_timestamp = (
# # # # #                     frame_timestamp
# # # # #                 )

# # # # #                 # -------------------------------------------------
# # # # #                 # YOLO inference
# # # # #                 # -------------------------------------------------

# # # # #                 results = await self._run_detection(
# # # # #                     frame,
# # # # #                     loop,
# # # # #                 )

# # # # #                 # -------------------------------------------------
# # # # #                 # Build detection data
# # # # #                 # -------------------------------------------------

# # # # #                 annotated_frame = frame.copy()

# # # # #                 detections = self._build_detections(
# # # # #                     results,
# # # # #                     annotated_frame,
# # # # #                 )

# # # # #                 # -------------------------------------------------
# # # # #                 # Publish canonical event
# # # # #                 # -------------------------------------------------

# # # # #                 redis_id, event = (
# # # # #                     await self._publish_detection_event(
# # # # #                         detections,
# # # # #                         frame_timestamp,
# # # # #                     )
# # # # #                 )

# # # # #                 print(
# # # # #                     f"DETECTED | "
# # # # #                     f"Camera={self.camera_id} | "
# # # # #                     f"Frame={self.frame_id} | "
# # # # #                     f"Persons={len(detections)} | "
# # # # #                     f"Redis={redis_id} | "
# # # # #                     f"Event={event.event_id}"
# # # # #                 )

# # # # #                 # -------------------------------------------------
# # # # #                 # Latest evidence
# # # # #                 # -------------------------------------------------

# # # # #                 self._save_latest_frame(
# # # # #                     annotated_frame
# # # # #                 )

# # # # #                 # -------------------------------------------------
# # # # #                 # Optional local display
# # # # #                 # -------------------------------------------------

# # # # #                 if self.show_camera:
# # # # #                     cv2.imshow(
# # # # #                         f"CCTV AI - {self.camera_id}",
# # # # #                         annotated_frame,
# # # # #                     )

# # # # #                     key = cv2.waitKey(1) & 0xFF

# # # # #                     if key == ord("q"):
# # # # #                         print(
# # # # #                             f"[{self.agent_id}] "
# # # # #                             f"Shutdown requested by operator."
# # # # #                         )
# # # # #                         break

# # # # #                 # -------------------------------------------------
# # # # #                 # Processing interval
# # # # #                 # -------------------------------------------------

# # # # #                 elapsed = (
# # # # #                     time.monotonic()
# # # # #                     - iteration_started
# # # # #                 )

# # # # #                 sleep_time = max(
# # # # #                     0.0,
# # # # #                     self.frame_interval - elapsed,
# # # # #                 )

# # # # #                 if sleep_time > 0:
# # # # #                     await asyncio.sleep(sleep_time)

# # # # #             except asyncio.CancelledError:
# # # # #                 raise

# # # # #             except Exception as exc:
# # # # #                 # =================================================
# # # # #                 # CAMERA WORKER FAULT ISOLATION
# # # # #                 #
# # # # #                 # A single frame, inference, Redis publish,
# # # # #                 # evidence, or processing failure must not kill
# # # # #                 # this worker.
# # # # #                 #
# # # # #                 # Other camera workers are separate processes.
# # # # #                 # =================================================

# # # # #                 print(
# # # # #                     f"[{self.agent_id}] "
# # # # #                     f"Detection iteration error | "
# # # # #                     f"Camera={self.camera_id} | "
# # # # #                     f"Error={type(exc).__name__}: {exc}"
# # # # #                 )

# # # # #                 await asyncio.sleep(1.0)

# # # # #         print(
# # # # #             f"[{self.agent_id}] "
# # # # #             f"Detection loop stopped | "
# # # # #             f"Camera={self.camera_id}"
# # # # #         )


# # # # # # =============================================================
# # # # # # Entry point
# # # # # # =============================================================

# # # # # async def main():
# # # # #     agent = PersonDetectionAgent()
# # # # #     await agent.run_forever()


# # # # # if __name__ == "__main__":
# # # # #     asyncio.run(main())



















# # # # import asyncio
# # # # import os
# # # # import socket
# # # # import time
# # # # import uuid
# # # # from pathlib import Path
# # # # from typing import Any

# # # # import cv2
# # # # from ultralytics import YOLO

# # # # from shared.agent.base_agent import BaseAgent
# # # # from shared.schemas.event_schema import create_event


# # # # # ============================================================
# # # # # PATHS
# # # # # ============================================================

# # # # PROJECT_ROOT = Path(__file__).resolve().parents[2]

# # # # EVIDENCE_ROOT = (
# # # #     PROJECT_ROOT
# # # #     / "data"
# # # #     / "evidence"
# # # # )

# # # # EVIDENCE_ROOT.mkdir(
# # # #     parents=True,
# # # #     exist_ok=True,
# # # # )


# # # # # ============================================================
# # # # # HELPERS
# # # # # ============================================================

# # # # def parse_bool(value: str, default: bool = False) -> bool:
# # # #     value = str(value).strip().lower()

# # # #     if value in {"1", "true", "yes", "y", "on"}:
# # # #         return True

# # # #     if value in {"0", "false", "no", "n", "off"}:
# # # #         return False

# # # #     return default


# # # # def parse_positive_float(
# # # #     name: str,
# # # #     default: float,
# # # # ) -> float:
# # # #     raw = os.getenv(name, str(default))

# # # #     try:
# # # #         value = float(raw)
# # # #     except (TypeError, ValueError):
# # # #         return default

# # # #     if value <= 0:
# # # #         return default

# # # #     return value


# # # # def parse_non_negative_float(
# # # #     name: str,
# # # #     default: float,
# # # # ) -> float:
# # # #     raw = os.getenv(name, str(default))

# # # #     try:
# # # #         value = float(raw)
# # # #     except (TypeError, ValueError):
# # # #         return default

# # # #     if value < 0:
# # # #         return default

# # # #     return value


# # # # def parse_class_filter(
# # # #     raw_value: str,
# # # # ) -> list[int] | None:
# # # #     """
# # # #     Parse YOLO class filter.

# # # #     Examples:

# # # #         YOLO_CLASSES=0,2,3,5,7
# # # #         YOLO_CLASSES=0
# # # #         YOLO_CLASSES=all

# # # #     None means all model classes.
# # # #     """

# # # #     value = str(raw_value).strip().lower()

# # # #     if not value or value == "all":
# # # #         return None

# # # #     classes: list[int] = []

# # # #     for item in value.split(","):
# # # #         item = item.strip()

# # # #         if not item:
# # # #             continue

# # # #         try:
# # # #             class_id = int(item)
# # # #         except ValueError:
# # # #             print(
# # # #                 f"[DetectionAgent] "
# # # #                 f"Ignoring invalid YOLO class: {item}"
# # # #             )
# # # #             continue

# # # #         if class_id < 0:
# # # #             continue

# # # #         classes.append(class_id)

# # # #     if not classes:
# # # #         return None

# # # #     return sorted(set(classes))


# # # # def utc_timestamp() -> str:
# # # #     """
# # # #     Return a timezone-aware UTC timestamp.

# # # #     BaseEvent will also normalize timestamps, but keeping a
# # # #     canonical timestamp inside event data is useful for evidence
# # # #     and downstream processing.
# # # #     """

# # # #     from datetime import datetime, timezone

# # # #     return (
# # # #         datetime.now(timezone.utc)
# # # #         .isoformat()
# # # #         .replace("+00:00", "Z")
# # # #     )


# # # # # ============================================================
# # # # # DETECTION AGENT
# # # # # ============================================================

# # # # class DetectionAgent(BaseAgent):
# # # #     """
# # # #     Generalized CCTV object-detection worker.

# # # #     Responsibilities:

# # # #         Camera / RTSP
# # # #             ↓
# # # #         OpenCV frame capture
# # # #             ↓
# # # #         YOLO inference
# # # #             ↓
# # # #         Structured detections
# # # #             ↓
# # # #         Canonical events

# # # #     Current YOLO event outputs:

# # # #         person.detected
# # # #         vehicle.detected
# # # #         object.detected

# # # #     Person detections are deliberately kept compatible with the
# # # #     existing tracker pipeline.

# # # #     IMPORTANT:

# # # #         This worker is NOT responsible for:

# # # #         - person tracking
# # # #         - fall detection
# # # #         - fight detection
# # # #         - loitering
# # # #         - crowd intelligence
# # # #         - restricted-zone logic
# # # #         - incident correlation
# # # #         - evidence generation
# # # #         - LLM reasoning

# # # #     Those remain separate capabilities/agents so failures stay
# # # #     isolated.
# # # #     """

# # # #     # COCO classes commonly useful for CCTV.
# # # #     #
# # # #     # 0 = person
# # # #     # 2 = car
# # # #     # 3 = motorcycle
# # # #     # 5 = bus
# # # #     # 7 = truck
# # # #     DEFAULT_CLASSES = "0,2,3,5,7"

# # # #     PERSON_CLASS_ID = 0

# # # #     VEHICLE_CLASS_IDS = {
# # # #         2,  # car
# # # #         3,  # motorcycle
# # # #         5,  # bus
# # # #         7,  # truck
# # # #     }

# # # #     def __init__(self):
# # # #         super().__init__(
# # # #             agent_id=os.getenv(
# # # #                 "AGENT_ID",
# # # #                 "person-detector-01",
# # # #             ),
# # # #             heartbeat_interval=int(
# # # #                 os.getenv(
# # # #                     "HEARTBEAT_INTERVAL",
# # # #                     "10",
# # # #                 )
# # # #             ),
# # # #         )

# # # #         # --------------------------------------------------------
# # # #         # Camera identity
# # # #         # --------------------------------------------------------

# # # #         self.camera_id = os.getenv(
# # # #             "CAMERA_ID",
# # # #             "",
# # # #         ).strip()

# # # #         if not self.camera_id:
# # # #             raise ValueError(
# # # #                 "CAMERA_ID is required. "
# # # #                 "Do not silently default to CAM01."
# # # #             )

# # # #         # --------------------------------------------------------
# # # #         # Camera source
# # # #         # --------------------------------------------------------

# # # #         self.camera_source = os.getenv(
# # # #             "CAMERA_SOURCE",
# # # #             "",
# # # #         ).strip()

# # # #         # Backwards compatibility with the old webcam setup.
# # # #         if not self.camera_source:
# # # #             self.camera_source = os.getenv(
# # # #                 "CAMERA_INDEX",
# # # #                 "0",
# # # #             ).strip()

# # # #         # --------------------------------------------------------
# # # #         # YOLO configuration
# # # #         # --------------------------------------------------------

# # # #         self.model_path = os.getenv(
# # # #             "YOLO_MODEL",
# # # #             str(
# # # #                 PROJECT_ROOT
# # # #                 / "yolo11n.pt"
# # # #             ),
# # # #         ).strip()

# # # #         self.confidence = parse_positive_float(
# # # #             "YOLO_CONFIDENCE",
# # # #             0.40,
# # # #         )

# # # #         self.iou = parse_positive_float(
# # # #             "YOLO_IOU",
# # # #             0.45,
# # # #         )

# # # #         # Default is person + common vehicles.
# # # #         #
# # # #         # Set:
# # # #         #
# # # #         #     YOLO_CLASSES=all
# # # #         #
# # # #         # if you want all classes available in the loaded YOLO model.
# # # #         self.class_filter = parse_class_filter(
# # # #             os.getenv(
# # # #                 "YOLO_CLASSES",
# # # #                 self.DEFAULT_CLASSES,
# # # #             )
# # # #         )

# # # #         # --------------------------------------------------------
# # # #         # Frame processing
# # # #         # --------------------------------------------------------

# # # #         self.frame_interval = parse_non_negative_float(
# # # #             "FRAME_INTERVAL",
# # # #             0.20,
# # # #         )

# # # #         self.inference_interval = parse_non_negative_float(
# # # #             "INFERENCE_INTERVAL",
# # # #             0.0,
# # # #         )

# # # #         self.show_camera = parse_bool(
# # # #             os.getenv(
# # # #                 "SHOW_CAMERA",
# # # #                 "true",
# # # #             ),
# # # #             default=True,
# # # #         )

# # # #         # --------------------------------------------------------
# # # #         # Camera reconnect configuration
# # # #         # --------------------------------------------------------

# # # #         self.reconnect_initial_delay = parse_positive_float(
# # # #             "CAMERA_RECONNECT_INITIAL_DELAY",
# # # #             1.0,
# # # #         )

# # # #         self.reconnect_max_delay = parse_positive_float(
# # # #             "CAMERA_RECONNECT_MAX_DELAY",
# # # #             30.0,
# # # #         )

# # # #         self.read_failure_before_reconnect = max(
# # # #             1,
# # # #             int(
# # # #                 os.getenv(
# # # #                     "CAMERA_READ_FAILURE_THRESHOLD",
# # # #                     "3",
# # # #                 )
# # # #             ),
# # # #         )

# # # #         # --------------------------------------------------------
# # # #         # Event configuration
# # # #         # --------------------------------------------------------

# # # #         self.detection_stream = os.getenv(
# # # #             "DETECTION_OUTPUT_STREAM",
# # # #             "events.detection",
# # # #         ).strip()

# # # #         self.vehicle_stream = os.getenv(
# # # #             "VEHICLE_OUTPUT_STREAM",
# # # #             "events.vehicle",
# # # #         ).strip()

# # # #         self.object_stream = os.getenv(
# # # #             "OBJECT_OUTPUT_STREAM",
# # # #             "events.objects",
# # # #         ).strip()

# # # #         # --------------------------------------------------------
# # # #         # Runtime state
# # # #         # --------------------------------------------------------

# # # #         self.model: YOLO | None = None
# # # #         self.cap: cv2.VideoCapture | None = None

# # # #         self.frame_id = 0

# # # #         self.last_inference_time = 0.0
# # # #         self.last_frame_time = 0.0

# # # #         self.read_failures = 0

# # # #         self.reconnect_delay = (
# # # #             self.reconnect_initial_delay
# # # #         )

# # # #         self.last_alive_log = 0.0

# # # #         # --------------------------------------------------------
# # # #         # Evidence
# # # #         # --------------------------------------------------------

# # # #         self.camera_evidence_dir = (
# # # #             EVIDENCE_ROOT
# # # #             / self._safe_camera_directory_name(
# # # #                 self.camera_id
# # # #             )
# # # #         )

# # # #         self.camera_evidence_dir.mkdir(
# # # #             parents=True,
# # # #             exist_ok=True,
# # # #         )

# # # #         self.latest_frame_path = (
# # # #             self.camera_evidence_dir
# # # #             / "latest.jpg"
# # # #         )

# # # #         # Preserve compatibility with the existing frontend/
# # # #         # single-camera prototype.
# # # #         self.legacy_latest_frame_path = (
# # # #             PROJECT_ROOT
# # # #             / "camera_latest.jpg"
# # # #         )

# # # #         # --------------------------------------------------------
# # # #         # Model class metadata
# # # #         # --------------------------------------------------------

# # # #         self.class_names: dict[int, str] = {}

# # # #     # ============================================================
# # # #     # CAMERA DIRECTORY
# # # #     # ============================================================

# # # #     @staticmethod
# # # #     def _safe_camera_directory_name(
# # # #         camera_id: str,
# # # #     ) -> str:
# # # #         """
# # # #         Convert camera ID into a filesystem-safe directory name.
# # # #         """

# # # #         allowed = (
# # # #             "abcdefghijklmnopqrstuvwxyz"
# # # #             "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
# # # #             "0123456789"
# # # #             "-_."
# # # #         )

# # # #         result = "".join(
# # # #             character
# # # #             if character in allowed
# # # #             else "_"
# # # #             for character in camera_id
# # # #         )

# # # #         return result[:120] or "camera"

# # # #     # ============================================================
# # # #     # START
# # # #     # ============================================================

# # # #     async def on_start(self):
# # # #         print(
# # # #             f"[{self.agent_id}] "
# # # #             f"Starting generalized detection worker."
# # # #         )

# # # #         print(
# # # #             f"[{self.agent_id}] "
# # # #             f"Camera ID: {self.camera_id}"
# # # #         )

# # # #         print(
# # # #             f"[{self.agent_id}] "
# # # #             f"Camera source: {self.camera_source}"
# # # #         )

# # # #         print(
# # # #             f"[{self.agent_id}] "
# # # #             f"YOLO model: {self.model_path}"
# # # #         )

# # # #         if self.class_filter is None:
# # # #             print(
# # # #                 f"[{self.agent_id}] "
# # # #                 f"YOLO classes: ALL"
# # # #             )
# # # #         else:
# # # #             print(
# # # #                 f"[{self.agent_id}] "
# # # #                 f"YOLO classes: {self.class_filter}"
# # # #             )

# # # #         # --------------------------------------------------------
# # # #         # Lazy model loading
# # # #         # --------------------------------------------------------
# # # #         #
# # # #         # The model is loaded by this worker, not at module import.
# # # #         # Therefore importing this module cannot crash the API/control
# # # #         # plane simply because the model is missing.
# # # #         # --------------------------------------------------------

# # # #         self.model = YOLO(
# # # #             self.model_path
# # # #         )

# # # #         self._load_class_names()

# # # #         print(
# # # #             f"[{self.agent_id}] "
# # # #             f"YOLO model loaded successfully."
# # # #         )

# # # #         # --------------------------------------------------------
# # # #         # Camera is best-effort.
# # # #         #
# # # #         # A camera being offline MUST NOT make this worker crash.
# # # #         # The worker stays alive and reconnects.
# # # #         # --------------------------------------------------------

# # # #         opened = await self._open_camera()

# # # #         if opened:
# # # #             print(
# # # #                 f"[{self.agent_id}] "
# # # #                 f"Camera opened successfully."
# # # #             )
# # # #         else:
# # # #             print(
# # # #                 f"[{self.agent_id}] "
# # # #                 f"Camera is currently unavailable. "
# # # #                 f"Worker will remain alive and retry."
# # # #             )

# # # #     # ============================================================
# # # #     # LOAD CLASS NAMES
# # # #     # ============================================================

# # # #     def _load_class_names(self):
# # # #         if self.model is None:
# # # #             return

# # # #         names = getattr(
# # # #             self.model,
# # # #             "names",
# # # #             {},
# # # #         )

# # # #         if isinstance(names, dict):
# # # #             self.class_names = {
# # # #                 int(key): str(value)
# # # #                 for key, value in names.items()
# # # #             }

# # # #         elif isinstance(names, list):
# # # #             self.class_names = {
# # # #                 index: str(value)
# # # #                 for index, value in enumerate(names)
# # # #             }

# # # #         else:
# # # #             self.class_names = {}

# # # #     # ============================================================
# # # #     # CAMERA OPEN
# # # #     # ============================================================

# # # #     async def _open_camera(self) -> bool:
# # # #         loop = asyncio.get_running_loop()

# # # #         old_cap = self.cap

# # # #         if old_cap is not None:
# # # #             try:
# # # #                 await loop.run_in_executor(
# # # #                     None,
# # # #                     old_cap.release,
# # # #                 )
# # # #             except Exception:
# # # #                 pass

# # # #             self.cap = None

# # # #         source = self._normalize_camera_source(
# # # #             self.camera_source
# # # #         )

# # # #         try:
# # # #             cap = await loop.run_in_executor(
# # # #                 None,
# # # #                 cv2.VideoCapture,
# # # #                 source,
# # # #             )

# # # #             if cap is None:
# # # #                 return False

# # # #             is_opened = await loop.run_in_executor(
# # # #                 None,
# # # #                 cap.isOpened,
# # # #             )

# # # #             if not is_opened:
# # # #                 await loop.run_in_executor(
# # # #                     None,
# # # #                     cap.release,
# # # #                 )

# # # #                 return False

# # # #             # Small buffer helps reduce latency for live CCTV.
# # # #             try:
# # # #                 await loop.run_in_executor(
# # # #                     None,
# # # #                     lambda: cap.set(
# # # #                         cv2.CAP_PROP_BUFFERSIZE,
# # # #                         1,
# # # #                     ),
# # # #                 )
# # # #             except Exception:
# # # #                 pass

# # # #             self.cap = cap
# # # #             self.read_failures = 0
# # # #             self.reconnect_delay = (
# # # #                 self.reconnect_initial_delay
# # # #             )

# # # #             return True

# # # #         except Exception as error:
# # # #             print(
# # # #                 f"[{self.agent_id}] "
# # # #                 f"Camera open error: {error}"
# # # #             )

# # # #             return False

# # # #     # ============================================================
# # # #     # CAMERA SOURCE NORMALIZATION
# # # #     # ============================================================

# # # #     @staticmethod
# # # #     def _normalize_camera_source(
# # # #         source: str,
# # # #     ) -> str | int:
# # # #         """
# # # #         Convert numeric webcam source to int.

# # # #         RTSP/HTTP/file paths remain strings.
# # # #         """

# # # #         value = str(source).strip()

# # # #         if (
# # # #             value.isdigit()
# # # #             and not value.startswith("0x")
# # # #         ):
# # # #             try:
# # # #                 return int(value)
# # # #             except ValueError:
# # # #                 pass

# # # #         return value

# # # #     # ============================================================
# # # #     # CAMERA RECONNECT
# # # #     # ============================================================

# # # #     async def _reconnect_camera(self):
# # # #         print(
# # # #             f"[{self.agent_id}] "
# # # #             f"Camera reconnect scheduled in "
# # # #             f"{self.reconnect_delay:.1f}s."
# # # #         )

# # # #         await asyncio.sleep(
# # # #             self.reconnect_delay
# # # #         )

# # # #         if not self.running:
# # # #             return

# # # #         opened = await self._open_camera()

# # # #         if opened:
# # # #             print(
# # # #                 f"[{self.agent_id}] "
# # # #                 f"Camera reconnected: "
# # # #                 f"{self.camera_id}"
# # # #             )

# # # #             self.reconnect_delay = (
# # # #                 self.reconnect_initial_delay
# # # #             )

# # # #         else:
# # # #             self.reconnect_delay = min(
# # # #                 self.reconnect_delay * 2,
# # # #                 self.reconnect_max_delay,
# # # #             )

# # # #     # ============================================================
# # # #     # STOP
# # # #     # ============================================================

# # # #     async def on_stop(self):
# # # #         loop = asyncio.get_running_loop()

# # # #         if self.cap is not None:
# # # #             try:
# # # #                 await loop.run_in_executor(
# # # #                     None,
# # # #                     self.cap.release,
# # # #                 )
# # # #             except Exception:
# # # #                 pass

# # # #             self.cap = None

# # # #         if self.show_camera:
# # # #             try:
# # # #                 cv2.destroyAllWindows()
# # # #             except Exception:
# # # #                 pass

# # # #         print(
# # # #             f"[{self.agent_id}] "
# # # #             f"Detection worker stopped."
# # # #         )

# # # #     # ============================================================
# # # #     # INFERENCE
# # # #     # ============================================================

# # # #     def _run_yolo(
# # # #         self,
# # # #         frame,
# # # #     ):
# # # #         if self.model is None:
# # # #             raise RuntimeError(
# # # #                 "YOLO model is not initialized."
# # # #             )

# # # #         return self.model(
# # # #             frame,
# # # #             conf=self.confidence,
# # # #             iou=self.iou,
# # # #             classes=self.class_filter,
# # # #             verbose=False,
# # # #         )

# # # #     # ============================================================
# # # #     # EXTRACT DETECTIONS
# # # #     # ============================================================

# # # #     def _extract_detections(
# # # #         self,
# # # #         results,
# # # #     ) -> list[dict[str, Any]]:
# # # #         detections: list[dict[str, Any]] = []

# # # #         for result in results:
# # # #             if result.boxes is None:
# # # #                 continue

# # # #             boxes = result.boxes

# # # #             for index in range(
# # # #                 len(boxes)
# # # #             ):
# # # #                 box = boxes[index]

# # # #                 xyxy = (
# # # #                     box.xyxy[0]
# # # #                     .cpu()
# # # #                     .tolist()
# # # #                 )

# # # #                 confidence = float(
# # # #                     box.conf[0]
# # # #                     .cpu()
# # # #                     .item()
# # # #                 )

# # # #                 class_id = int(
# # # #                     box.cls[0]
# # # #                     .cpu()
# # # #                     .item()
# # # #                 )

# # # #                 class_name = self.class_names.get(
# # # #                     class_id,
# # # #                     f"class_{class_id}",
# # # #                 )

# # # #                 detection_id = (
# # # #                     f"det-"
# # # #                     f"{self.camera_id}-"
# # # #                     f"{self.frame_id}-"
# # # #                     f"{uuid.uuid4().hex[:8]}"
# # # #                 )

# # # #                 x1 = float(xyxy[0])
# # # #                 y1 = float(xyxy[1])
# # # #                 x2 = float(xyxy[2])
# # # #                 y2 = float(xyxy[3])

# # # #                 detections.append(
# # # #                     {
# # # #                         "detection_id": detection_id,
# # # #                         "class_id": class_id,
# # # #                         "class_name": class_name,
# # # #                         "confidence": confidence,
# # # #                         "bbox": [
# # # #                             x1,
# # # #                             y1,
# # # #                             x2,
# # # #                             y2,
# # # #                         ],
# # # #                     }
# # # #                 )

# # # #         return detections

# # # #     # ============================================================
# # # #     # SPLIT DETECTIONS
# # # #     # ============================================================

# # # #     @staticmethod
# # # #     def _split_detections(
# # # #         detections: list[dict[str, Any]],
# # # #     ):
# # # #         people: list[dict[str, Any]] = []
# # # #         vehicles: list[dict[str, Any]] = []

# # # #         for detection in detections:
# # # #             class_id = int(
# # # #                 detection["class_id"]
# # # #             )

# # # #             if class_id == DetectionAgent.PERSON_CLASS_ID:
# # # #                 people.append(detection)

# # # #             if class_id in DetectionAgent.VEHICLE_CLASS_IDS:
# # # #                 vehicles.append(detection)

# # # #         return people, vehicles

# # # #     # ============================================================
# # # #     # EVENT PUBLISHING
# # # #     # ============================================================

# # # #     async def _publish_event(
# # # #         self,
# # # #         stream: str,
# # # #         event_type: str,
# # # #         data: dict[str, Any],
# # # #         trace_id: str | None = None,
# # # #         correlation_id: str | None = None,
# # # #         incident_id: str | None = None,
# # # #     ):
# # # #         event = create_event(
# # # #             event_type=event_type,
# # # #             agent_id=self.agent_id,
# # # #             instance_id=self.instance_id,
# # # #             hostname=self.hostname,
# # # #             camera_id=self.camera_id,
# # # #             mode="live",
# # # #             trace_id=trace_id,
# # # #             correlation_id=correlation_id,
# # # #             incident_id=incident_id,
# # # #             data=data,
# # # #         )

# # # #         return await self.publish(
# # # #             stream,
# # # #             event.to_dict(),
# # # #         )

# # # #     # ============================================================
# # # #     # PERSON EVENT
# # # #     # ============================================================

# # # #     async def _publish_person_event(
# # # #         self,
# # # #         people: list[dict[str, Any]],
# # # #         frame_timestamp: str,
# # # #     ):
# # # #         """
# # # #         Preserve the event contract expected by the current
# # # #         person tracker.

# # # #         We publish even when people == [].

# # # #         This is important because downstream stateful workers
# # # #         need empty observations to know that a person is no
# # # #         longer visible.
# # # #         """

# # # #         data = {
# # # #             "frame_id": str(
# # # #                 self.frame_id
# # # #             ),
# # # #             "frame_timestamp": frame_timestamp,
# # # #             "detection_count": len(people),
# # # #             "count": len(people),
# # # #             "detections": people,
# # # #             "model": self.model_path,
# # # #             "confidence_threshold": self.confidence,
# # # #         }

# # # #         redis_id = await self._publish_event(
# # # #             stream=self.detection_stream,
# # # #             event_type="person.detected",
# # # #             data=data,
# # # #         )

# # # #         return redis_id

# # # #     # ============================================================
# # # #     # VEHICLE EVENT
# # # #     # ============================================================

# # # #     async def _publish_vehicle_event(
# # # #         self,
# # # #         vehicles: list[dict[str, Any]],
# # # #         frame_timestamp: str,
# # # #     ):
# # # #         """
# # # #         Vehicle events are kept separate from person events.

# # # #         Future vehicle-specific agents can consume
# # # #         events.vehicle without modifying the person pipeline.
# # # #         """

# # # #         data = {
# # # #             "frame_id": str(
# # # #                 self.frame_id
# # # #             ),
# # # #             "frame_timestamp": frame_timestamp,
# # # #             "vehicle_count": len(vehicles),
# # # #             "count": len(vehicles),
# # # #             "vehicles": vehicles,
# # # #             "model": self.model_path,
# # # #             "confidence_threshold": self.confidence,
# # # #         }

# # # #         return await self._publish_event(
# # # #             stream=self.vehicle_stream,
# # # #             event_type="vehicle.detected",
# # # #             data=data,
# # # #         )

# # # #     # ============================================================
# # # #     # GENERIC OBJECT EVENT
# # # #     # ============================================================

# # # #     async def _publish_object_event(
# # # #         self,
# # # #         detections: list[dict[str, Any]],
# # # #         frame_timestamp: str,
# # # #     ):
# # # #         """
# # # #         Generic object event.

# # # #         This gives the future platform a common perception stream
# # # #         without forcing every new object type into the person
# # # #         pipeline.

# # # #         Example:

# # # #             person
# # # #             car
# # # #             motorcycle
# # # #             bus
# # # #             truck

# # # #         Specialized events such as fire.detected and fall.detected
# # # #         will later come from specialized models/agents.
# # # #         """

# # # #         data = {
# # # #             "frame_id": str(
# # # #                 self.frame_id
# # # #             ),
# # # #             "frame_timestamp": frame_timestamp,
# # # #             "object_count": len(detections),
# # # #             "count": len(detections),
# # # #             "detections": detections,
# # # #             "model": self.model_path,
# # # #             "confidence_threshold": self.confidence,
# # # #         }

# # # #         return await self._publish_event(
# # # #             stream=self.object_stream,
# # # #             event_type="object.detected",
# # # #             data=data,
# # # #         )

# # # #     # ============================================================
# # # #     # ANNOTATION
# # # #     # ============================================================

# # # #     def _annotate_frame(
# # # #         self,
# # # #         frame,
# # # #         detections: list[dict[str, Any]],
# # # #     ):
# # # #         annotated_frame = frame.copy()

# # # #         for detection in detections:
# # # #             bbox = detection["bbox"]

# # # #             x1 = int(bbox[0])
# # # #             y1 = int(bbox[1])
# # # #             x2 = int(bbox[2])
# # # #             y2 = int(bbox[3])

# # # #             confidence = float(
# # # #                 detection["confidence"]
# # # #             )

# # # #             class_id = int(
# # # #                 detection["class_id"]
# # # #             )

# # # #             class_name = str(
# # # #                 detection["class_name"]
# # # #             )

# # # #             # Person uses the familiar green annotation.
# # # #             if class_id == self.PERSON_CLASS_ID:
# # # #                 label = (
# # # #                     f"Person "
# # # #                     f"{confidence:.2f}"
# # # #                 )

# # # #             elif class_id in self.VEHICLE_CLASS_IDS:
# # # #                 label = (
# # # #                     f"{class_name} "
# # # #                     f"{confidence:.2f}"
# # # #                 )

# # # #             else:
# # # #                 label = (
# # # #                     f"{class_name} "
# # # #                     f"{confidence:.2f}"
# # # #                 )

# # # #             cv2.rectangle(
# # # #                 annotated_frame,
# # # #                 (x1, y1),
# # # #                 (x2, y2),
# # # #                 (0, 255, 0),
# # # #                 2,
# # # #             )

# # # #             cv2.putText(
# # # #                 annotated_frame,
# # # #                 label,
# # # #                 (
# # # #                     x1,
# # # #                     max(
# # # #                         y1 - 10,
# # # #                         20,
# # # #                     ),
# # # #                 ),
# # # #                 cv2.FONT_HERSHEY_SIMPLEX,
# # # #                 0.5,
# # # #                 (0, 255, 0),
# # # #                 2,
# # # #             )

# # # #         # Camera / frame information.
# # # #         cv2.putText(
# # # #             annotated_frame,
# # # #             (
# # # #                 f"Camera: {self.camera_id} | "
# # # #                 f"Frame: {self.frame_id} | "
# # # #                 f"Objects: {len(detections)}"
# # # #             ),
# # # #             (10, 25),
# # # #             cv2.FONT_HERSHEY_SIMPLEX,
# # # #             0.6,
# # # #             (255, 255, 255),
# # # #             2,
# # # #         )

# # # #         return annotated_frame

# # # #     # ============================================================
# # # #     # ATOMIC IMAGE WRITE
# # # #     # ============================================================

# # # #     def _write_latest_frame(
# # # #         self,
# # # #         frame,
# # # #     ):
# # # #         """
# # # #         Write the latest frame atomically.

# # # #         Readers never intentionally see a half-written JPEG.
# # # #         """

# # # #         targets = [
# # # #             self.latest_frame_path,
# # # #             self.legacy_latest_frame_path,
# # # #         ]

# # # #         for target in targets:
# # # #             try:
# # # #                 target.parent.mkdir(
# # # #                     parents=True,
# # # #                     exist_ok=True,
# # # #                 )

# # # #                 temp_path = target.with_name(
# # # #                     f".{target.stem}."
# # # #                     f"{uuid.uuid4().hex}"
# # # #                     f"{target.suffix}"
# # # #                 )

# # # #                 success = cv2.imwrite(
# # # #                     str(temp_path),
# # # #                     frame,
# # # #                 )

# # # #                 if not success:
# # # #                     raise RuntimeError(
# # # #                         f"cv2.imwrite failed for "
# # # #                         f"{target}"
# # # #                     )

# # # #                 os.replace(
# # # #                     temp_path,
# # # #                     target,
# # # #                 )

# # # #             except Exception as error:
# # # #                 print(
# # # #                     f"[{self.agent_id}] "
# # # #                     f"Latest-frame write failed "
# # # #                     f"for {target}: {error}"
# # # #                 )

# # # #                 try:
# # # #                     if temp_path.exists():
# # # #                         temp_path.unlink()
# # # #                 except Exception:
# # # #                     pass

# # # #     # ============================================================
# # # #     # DISPLAY
# # # #     # ============================================================

# # # #     def _display_frame(
# # # #         self,
# # # #         frame,
# # # #     ) -> bool:
# # # #         """
# # # #         Returns False when the operator requests shutdown.
# # # #         """

# # # #         if not self.show_camera:
# # # #             return True

# # # #         try:
# # # #             window_name = (
# # # #                 f"CCTV AI - "
# # # #                 f"{self.camera_id}"
# # # #             )

# # # #             cv2.imshow(
# # # #                 window_name,
# # # #                 frame,
# # # #             )

# # # #             key = (
# # # #                 cv2.waitKey(1)
# # # #                 & 0xFF
# # # #             )

# # # #             if key == ord("q"):
# # # #                 print(
# # # #                     f"[{self.agent_id}] "
# # # #                     f"Shutdown requested "
# # # #                     f"by operator."
# # # #                 )

# # # #                 return False

# # # #         except Exception as error:
# # # #             # Display failure must never terminate the detector.
# # # #             print(
# # # #                 f"[{self.agent_id}] "
# # # #                 f"Display error isolated: {error}"
# # # #             )

# # # #         return True

# # # #     # ============================================================
# # # #     # MAIN LOOP
# # # #     # ============================================================

# # # #     async def run(self):
# # # #         if self.model is None:
# # # #             raise RuntimeError(
# # # #                 "YOLO model is not initialized."
# # # #             )

# # # #         print(
# # # #             f"[{self.agent_id}] "
# # # #             f"Generalized detection loop started."
# # # #         )

# # # #         loop = asyncio.get_running_loop()

# # # #         while self.running:
# # # #             try:
# # # #                 # ------------------------------------------------
# # # #                 # Camera unavailable
# # # #                 # ------------------------------------------------

# # # #                 if self.cap is None:
# # # #                     await self._reconnect_camera()
# # # #                     continue

# # # #                 # ------------------------------------------------
# # # #                 # Read frame
# # # #                 # ------------------------------------------------

# # # #                 ret, frame = await loop.run_in_executor(
# # # #                     None,
# # # #                     self.cap.read,
# # # #                 )

# # # #                 if not ret or frame is None:
# # # #                     self.read_failures += 1

# # # #                     print(
# # # #                         f"[{self.agent_id}] "
# # # #                         f"Camera frame read failed "
# # # #                         f"({self.read_failures}/"
# # # #                         f"{self.read_failure_before_reconnect})."
# # # #                     )

# # # #                     if (
# # # #                         self.read_failures
# # # #                         >= self.read_failure_before_reconnect
# # # #                     ):
# # # #                         try:
# # # #                             await loop.run_in_executor(
# # # #                                 None,
# # # #                                 self.cap.release,
# # # #                             )
# # # #                         except Exception:
# # # #                             pass

# # # #                         self.cap = None
# # # #                         self.read_failures = 0

# # # #                     await asyncio.sleep(
# # # #                         min(
# # # #                             self.reconnect_delay,
# # # #                             2.0,
# # # #                         )
# # # #                     )

# # # #                     continue

# # # #                 # Successful read.
# # # #                 self.read_failures = 0
# # # #                 self.last_frame_time = time.monotonic()

# # # #                 self.frame_id += 1

# # # #                 # ------------------------------------------------
# # # #                 # Optional frame throttling
# # # #                 # ------------------------------------------------

# # # #                 if self.inference_interval > 0:
# # # #                     now = time.monotonic()

# # # #                     elapsed = (
# # # #                         now
# # # #                         - self.last_inference_time
# # # #                     )

# # # #                     if elapsed < self.inference_interval:
# # # #                         if not self._display_frame(frame):
# # # #                             break

# # # #                         await asyncio.sleep(
# # # #                             max(
# # # #                                 0.0,
# # # #                                 self.frame_interval,
# # # #                             )
# # # #                         )

# # # #                         continue

# # # #                 self.last_inference_time = (
# # # #                     time.monotonic()
# # # #                 )

# # # #                 # ------------------------------------------------
# # # #                 # Frame timestamp
# # # #                 # ------------------------------------------------

# # # #                 frame_timestamp = utc_timestamp()

# # # #                 # ------------------------------------------------
# # # #                 # YOLO inference
# # # #                 # ------------------------------------------------

# # # #                 results = await loop.run_in_executor(
# # # #                     None,
# # # #                     self._run_yolo,
# # # #                     frame,
# # # #                 )

# # # #                 # ------------------------------------------------
# # # #                 # Extract detections
# # # #                 # ------------------------------------------------

# # # #                 detections = (
# # # #                     self._extract_detections(
# # # #                         results
# # # #                     )
# # # #                 )

# # # #                 people, vehicles = (
# # # #                     self._split_detections(
# # # #                         detections
# # # #                     )
# # # #                 )

# # # #                 # ------------------------------------------------
# # # #                 # Annotate
# # # #                 # ------------------------------------------------

# # # #                 annotated_frame = (
# # # #                     self._annotate_frame(
# # # #                         frame,
# # # #                         detections,
# # # #                     )
# # # #                 )

# # # #                 # ------------------------------------------------
# # # #                 # Publish person event
# # # #                 # ------------------------------------------------

# # # #                 person_redis_id = (
# # # #                     await self._publish_person_event(
# # # #                         people,
# # # #                         frame_timestamp,
# # # #                     )
# # # #                 )

# # # #                 # ------------------------------------------------
# # # #                 # Publish vehicle event
# # # #                 # ------------------------------------------------

# # # #                 vehicle_redis_id = (
# # # #                     await self._publish_vehicle_event(
# # # #                         vehicles,
# # # #                         frame_timestamp,
# # # #                     )
# # # #                 )

# # # #                 # ------------------------------------------------
# # # #                 # Publish generic object event
# # # #                 # ------------------------------------------------

# # # #                 object_redis_id = (
# # # #                     await self._publish_object_event(
# # # #                         detections,
# # # #                         frame_timestamp,
# # # #                     )
# # # #                 )

# # # #                 # ------------------------------------------------
# # # #                 # Evidence/latest frame
# # # #                 # ------------------------------------------------

# # # #                 self._write_latest_frame(
# # # #                     annotated_frame
# # # #                 )

# # # #                 # ------------------------------------------------
# # # #                 # Logging
# # # #                 # ------------------------------------------------

# # # #                 print(
# # # #                     f"DETECTED | "
# # # #                     f"Camera={self.camera_id} | "
# # # #                     f"Frame={self.frame_id} | "
# # # #                     f"Persons={len(people)} | "
# # # #                     f"Vehicles={len(vehicles)} | "
# # # #                     f"Objects={len(detections)} | "
# # # #                     f"PersonRedis={person_redis_id} | "
# # # #                     f"VehicleRedis={vehicle_redis_id} | "
# # # #                     f"ObjectRedis={object_redis_id}"
# # # #                 )

# # # #                 # ------------------------------------------------
# # # #                 # Display
# # # #                 # ------------------------------------------------

# # # #                 if not self._display_frame(
# # # #                     annotated_frame
# # # #                 ):
# # # #                     break

# # # #                 # ------------------------------------------------
# # # #                 # Frame pacing
# # # #                 # ------------------------------------------------

# # # #                 if self.frame_interval > 0:
# # # #                     await asyncio.sleep(
# # # #                         self.frame_interval
# # # #                     )

# # # #             # ====================================================
# # # #             # SHUTDOWN
# # # #             # ====================================================

# # # #             except asyncio.CancelledError:
# # # #                 raise

# # # #             # ====================================================
# # # #             # INDIVIDUAL ITERATION FAILURE
# # # #             # ====================================================

# # # #             except Exception as error:
# # # #                 """
# # # #                 CRITICAL FAULT-ISOLATION RULE:

# # # #                 One failed frame, YOLO inference, Redis publish,
# # # #                 annotation, evidence write, or other iteration
# # # #                 must NOT terminate the camera worker.

# # # #                 BaseAgent/supervisor can still recover the whole
# # # #                 worker if a truly fatal condition occurs.
# # # #                 """

# # # #                 print(
# # # #                     f"[{self.agent_id}] "
# # # #                     f"Detection iteration error isolated: "
# # # #                     f"{type(error).__name__}: {error}"
# # # #                 )

# # # #                 await asyncio.sleep(
# # # #                     1.0
# # # #                 )

# # # #         print(
# # # #             f"[{self.agent_id}] "
# # # #             f"Detection loop stopped."
# # # #         )


# # # # # ============================================================
# # # # # MAIN
# # # # # ============================================================

# # # # async def main():
# # # #     agent = DetectionAgent()

# # # #     await agent.run_forever()


# # # # if __name__ == "__main__":
# # # #     asyncio.run(main())






























# # # import asyncio
# # # import os
# # # import socket
# # # import time
# # # import uuid
# # # from datetime import datetime, timezone
# # # from pathlib import Path
# # # from typing import Any

# # # import cv2
# # # from ultralytics import YOLO

# # # from shared.agent.base_agent import BaseAgent
# # # from shared.schemas.event_schema import create_event


# # # # ============================================================
# # # # PATHS
# # # # ============================================================

# # # PROJECT_ROOT = Path(__file__).resolve().parents[2]

# # # EVIDENCE_ROOT = PROJECT_ROOT / "data" / "evidence"
# # # EVIDENCE_ROOT.mkdir(
# # #     parents=True,
# # #     exist_ok=True,
# # # )


# # # # ============================================================
# # # # HELPERS
# # # # ============================================================

# # # def parse_bool(
# # #     value: str,
# # #     default: bool = False,
# # # ) -> bool:
# # #     value = str(value).strip().lower()

# # #     if value in {"1", "true", "yes", "y", "on"}:
# # #         return True

# # #     if value in {"0", "false", "no", "n", "off"}:
# # #         return False

# # #     return default


# # # def parse_positive_float(
# # #     name: str,
# # #     default: float,
# # # ) -> float:
# # #     raw = os.getenv(name, str(default))

# # #     try:
# # #         value = float(raw)
# # #     except (TypeError, ValueError):
# # #         return default

# # #     if value <= 0:
# # #         return default

# # #     return value


# # # def parse_non_negative_float(
# # #     name: str,
# # #     default: float,
# # # ) -> float:
# # #     raw = os.getenv(name, str(default))

# # #     try:
# # #         value = float(raw)
# # #     except (TypeError, ValueError):
# # #         return default

# # #     if value < 0:
# # #         return default

# # #     return value


# # # def parse_positive_int(
# # #     name: str,
# # #     default: int,
# # # ) -> int:
# # #     raw = os.getenv(name, str(default))

# # #     try:
# # #         value = int(raw)
# # #     except (TypeError, ValueError):
# # #         return default

# # #     if value <= 0:
# # #         return default

# # #     return value


# # # def parse_class_filter(
# # #     raw_value: str,
# # # ) -> list[int] | None:
# # #     """
# # #     Parse YOLO class filter.

# # #     Examples:
# # #         YOLO_CLASSES=0,2,3,5,7
# # #         YOLO_CLASSES=0
# # #         YOLO_CLASSES=all

# # #     None means all model classes.
# # #     """

# # #     value = str(raw_value).strip().lower()

# # #     if not value or value == "all":
# # #         return None

# # #     classes: list[int] = []

# # #     for item in value.split(","):
# # #         item = item.strip()

# # #         if not item:
# # #             continue

# # #         try:
# # #             class_id = int(item)
# # #         except ValueError:
# # #             print(
# # #                 "[DetectionAgent] "
# # #                 f"Ignoring invalid YOLO class: {item}"
# # #             )
# # #             continue

# # #         if class_id < 0:
# # #             continue

# # #         classes.append(class_id)

# # #     if not classes:
# # #         return None

# # #     return sorted(set(classes))


# # # def utc_timestamp() -> str:
# # #     """
# # #     Return canonical timezone-aware UTC timestamp.
# # #     """

# # #     return (
# # #         datetime.now(timezone.utc)
# # #         .isoformat()
# # #         .replace("+00:00", "Z")
# # #     )


# # # # ============================================================
# # # # DETECTION AGENT
# # # # ============================================================

# # # class DetectionAgent(BaseAgent):
# # #     """
# # #     Per-camera CCTV object-detection worker.

# # #     Architecture:

# # #         Camera / RTSP
# # #               ↓
# # #         OpenCV capture
# # #               ↓
# # #         YOLO inference
# # #               ↓
# # #         Structured detections
# # #               ↓
# # #         Canonical events

# # #     IMPORTANT:

# # #     One DetectionAgent instance MUST belong to exactly one camera.

# # #     Camera identity is immutable for the lifetime of this worker.

# # #     This worker is NOT responsible for:

# # #         - tracking
# # #         - cross-camera identity
# # #         - fall detection
# # #         - fight detection
# # #         - loitering
# # #         - crowd intelligence
# # #         - restricted-zone logic
# # #         - incident correlation
# # #         - evidence generation
# # #         - LLM reasoning

# # #     Those capabilities remain isolated downstream.
# # #     """

# # #     # COCO classes commonly useful for CCTV.
# # #     #
# # #     # 0 = person
# # #     # 2 = car
# # #     # 3 = motorcycle
# # #     # 5 = bus
# # #     # 7 = truck

# # #     DEFAULT_CLASSES = "0,2,3,5,7"

# # #     PERSON_CLASS_ID = 0

# # #     VEHICLE_CLASS_IDS = {
# # #         2,  # car
# # #         3,  # motorcycle
# # #         5,  # bus
# # #         7,  # truck
# # #     }

# # #     # ========================================================
# # #     # INIT
# # #     # ========================================================

# # #     def __init__(self):
# # #         super().__init__(
# # #             agent_id=os.getenv(
# # #                 "AGENT_ID",
# # #                 "person-detector-01",
# # #             ),
# # #             heartbeat_interval=parse_positive_int(
# # #                 "HEARTBEAT_INTERVAL",
# # #                 10,
# # #             ),
# # #         )

# # #         # ----------------------------------------------------
# # #         # Immutable camera identity
# # #         # ----------------------------------------------------

# # #         self.camera_id = os.getenv(
# # #             "CAMERA_ID",
# # #             "",
# # #         ).strip()

# # #         if not self.camera_id:
# # #             raise ValueError(
# # #                 "CAMERA_ID is required. "
# # #                 "Detection workers must never silently "
# # #                 "default to CAM01."
# # #             )

# # #         # Capture the original identity once.
# # #         #
# # #         # This gives us a strong invariant:
# # #         #
# # #         #     _camera_identity == camera_id
# # #         #
# # #         # and allows us to detect accidental mutation.

# # #         self._camera_identity = self.camera_id

# # #         # ----------------------------------------------------
# # #         # Camera metadata
# # #         # ----------------------------------------------------

# # #         self.camera_name = os.getenv(
# # #             "CAMERA_NAME",
# # #             self.camera_id,
# # #         ).strip()

# # #         self.camera_location = os.getenv(
# # #             "CAMERA_LOCATION",
# # #             "default",
# # #         ).strip()

# # #         # ----------------------------------------------------
# # #         # Camera source
# # #         # ----------------------------------------------------

# # #         self.camera_source = os.getenv(
# # #             "CAMERA_SOURCE",
# # #             "",
# # #         ).strip()

# # #         # Backward compatibility.
# # #         if not self.camera_source:
# # #             self.camera_source = os.getenv(
# # #                 "CAMERA_INDEX",
# # #                 "0",
# # #             ).strip()

# # #         if not self.camera_source:
# # #             raise ValueError(
# # #                 f"CAMERA_SOURCE is required for "
# # #                 f"{self.camera_id}."
# # #             )

# # #         # Capture immutable source too.
# # #         self._camera_source_identity = self.camera_source

# # #         # ----------------------------------------------------
# # #         # YOLO configuration
# # #         # ----------------------------------------------------

# # #         self.model_path = os.getenv(
# # #             "YOLO_MODEL",
# # #             str(
# # #                 PROJECT_ROOT / "yolo11n.pt"
# # #             ),
# # #         ).strip()

# # #         self.confidence = parse_positive_float(
# # #             "YOLO_CONFIDENCE",
# # #             0.40,
# # #         )

# # #         self.iou = parse_positive_float(
# # #             "YOLO_IOU",
# # #             0.45,
# # #         )

# # #         self.class_filter = parse_class_filter(
# # #             os.getenv(
# # #                 "YOLO_CLASSES",
# # #                 self.DEFAULT_CLASSES,
# # #             )
# # #         )

# # #         # ----------------------------------------------------
# # #         # Frame processing
# # #         # ----------------------------------------------------

# # #         self.frame_interval = parse_non_negative_float(
# # #             "FRAME_INTERVAL",
# # #             0.20,
# # #         )

# # #         self.inference_interval = parse_non_negative_float(
# # #             "INFERENCE_INTERVAL",
# # #             0.0,
# # #         )

# # #         self.show_camera = parse_bool(
# # #             os.getenv(
# # #                 "SHOW_CAMERA",
# # #                 "true",
# # #             ),
# # #             default=True,
# # #         )

# # #         # ----------------------------------------------------
# # #         # Camera reconnect configuration
# # #         # ----------------------------------------------------

# # #         self.reconnect_initial_delay = parse_positive_float(
# # #             "CAMERA_RECONNECT_INITIAL_DELAY",
# # #             1.0,
# # #         )

# # #         self.reconnect_max_delay = parse_positive_float(
# # #             "CAMERA_RECONNECT_MAX_DELAY",
# # #             30.0,
# # #         )

# # #         self.read_failure_before_reconnect = max(
# # #             1,
# # #             parse_positive_int(
# # #                 "CAMERA_READ_FAILURE_THRESHOLD",
# # #                 3,
# # #             ),
# # #         )

# # #         # ----------------------------------------------------
# # #         # Event streams
# # #         # ----------------------------------------------------

# # #         self.detection_stream = os.getenv(
# # #             "DETECTION_OUTPUT_STREAM",
# # #             "events.detection",
# # #         ).strip()

# # #         self.vehicle_stream = os.getenv(
# # #             "VEHICLE_OUTPUT_STREAM",
# # #             "events.vehicle",
# # #         ).strip()

# # #         self.object_stream = os.getenv(
# # #             "OBJECT_OUTPUT_STREAM",
# # #             "events.objects",
# # #         ).strip()

# # #         # ----------------------------------------------------
# # #         # Runtime state
# # #         # ----------------------------------------------------

# # #         self.model: YOLO | None = None

# # #         self.cap: cv2.VideoCapture | None = None

# # #         self.frame_id = 0

# # #         self.last_inference_time = 0.0

# # #         self.last_frame_time = 0.0

# # #         self.read_failures = 0

# # #         self.reconnect_delay = (
# # #             self.reconnect_initial_delay
# # #         )

# # #         self.last_alive_log = 0.0

# # #         self.reconnect_in_progress = False

# # #         # ----------------------------------------------------
# # #         # Evidence
# # #         # ----------------------------------------------------

# # #         # Every camera gets its own directory.
# # #         #
# # #         # Example:
# # #         #
# # #         # data/evidence/
# # #         #   CAM01/
# # #         #   CAM02/
# # #         #   CAM03/

# # #         self.camera_evidence_dir = (
# # #             EVIDENCE_ROOT
# # #             / self._safe_camera_directory_name(
# # #                 self.camera_id
# # #             )
# # #         )

# # #         self.camera_evidence_dir.mkdir(
# # #             parents=True,
# # #             exist_ok=True,
# # #         )

# # #         self.latest_frame_path = (
# # #             self.camera_evidence_dir
# # #             / "latest.jpg"
# # #         )

# # #         # IMPORTANT:
# # #         #
# # #         # Do NOT write camera_latest.jpg here.
# # #         #
# # #         # That old global file causes:
# # #         #
# # #         # CAM01 → camera_latest.jpg
# # #         # CAM02 → camera_latest.jpg
# # #         #
# # #         # and therefore destroys camera isolation.
# # #         #
# # #         # The frontend should eventually consume:
# # #         #
# # #         # data/evidence/<camera_id>/latest.jpg

# # #         # ----------------------------------------------------
# # #         # Model class metadata
# # #         # ----------------------------------------------------

# # #         self.class_names: dict[int, str] = {}

# # #     # ============================================================
# # #     # CAMERA DIRECTORY
# # #     # ============================================================

# # #     @staticmethod
# # #     def _safe_camera_directory_name(
# # #         camera_id: str,
# # #     ) -> str:
# # #         """
# # #         Convert camera ID into filesystem-safe directory name.
# # #         """

# # #         allowed = (
# # #             "abcdefghijklmnopqrstuvwxyz"
# # #             "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
# # #             "0123456789"
# # #             "-_."
# # #         )

# # #         result = "".join(
# # #             character
# # #             if character in allowed
# # #             else "_"
# # #             for character in camera_id
# # #         )

# # #         return result[:120] or "camera"

# # #     # ============================================================
# # #     # IDENTITY VALIDATION
# # #     # ============================================================

# # #     def _validate_camera_identity(self) -> None:
# # #         """
# # #         Ensure camera identity has not changed.

# # #         A detector worker is permanently bound to one camera.
# # #         """

# # #         if self.camera_id != self._camera_identity:
# # #             raise RuntimeError(
# # #                 "CAMERA ID MUTATION DETECTED: "
# # #                 f"original={self._camera_identity}, "
# # #                 f"current={self.camera_id}"
# # #             )

# # #         if self.camera_source != self._camera_source_identity:
# # #             raise RuntimeError(
# # #                 "CAMERA SOURCE MUTATION DETECTED: "
# # #                 f"original={self._camera_source_identity}, "
# # #                 f"current={self.camera_source}"
# # #             )

# # #     # ============================================================
# # #     # START
# # #     # ============================================================

# # #     async def on_start(self):
# # #         self._validate_camera_identity()

# # #         print(
# # #             f"[{self.agent_id}] "
# # #             "Starting per-camera detection worker."
# # #         )

# # #         print(
# # #             f"[{self.agent_id}] "
# # #             f"Camera ID: {self.camera_id}"
# # #         )

# # #         print(
# # #             f"[{self.agent_id}] "
# # #             f"Camera name: {self.camera_name}"
# # #         )

# # #         print(
# # #             f"[{self.agent_id}] "
# # #             f"Camera location: {self.camera_location}"
# # #         )

# # #         print(
# # #             f"[{self.agent_id}] "
# # #             f"Camera source: {self.camera_source}"
# # #         )

# # #         print(
# # #             f"[{self.agent_id}] "
# # #             f"Evidence directory: "
# # #             f"{self.camera_evidence_dir}"
# # #         )

# # #         print(
# # #             f"[{self.agent_id}] "
# # #             f"YOLO model: {self.model_path}"
# # #         )

# # #         if self.class_filter is None:
# # #             print(
# # #                 f"[{self.agent_id}] "
# # #                 "YOLO classes: ALL"
# # #             )
# # #         else:
# # #             print(
# # #                 f"[{self.agent_id}] "
# # #                 f"YOLO classes: {self.class_filter}"
# # #             )

# # #         # ----------------------------------------------------
# # #         # Lazy model loading
# # #         # ----------------------------------------------------

# # #         try:
# # #             self.model = YOLO(
# # #                 self.model_path
# # #             )

# # #             self._load_class_names()

# # #             print(
# # #                 f"[{self.agent_id}] "
# # #                 "YOLO model loaded successfully."
# # #             )

# # #         except Exception as error:
# # #             print(
# # #                 f"[{self.agent_id}] "
# # #                 "YOLO model loading failed: "
# # #                 f"{type(error).__name__}: {error}"
# # #             )

# # #             # Model loading is a worker-level failure.
# # #             #
# # #             # We intentionally allow BaseAgent/supervisor
# # #             # to handle the process lifecycle instead of
# # #             # crashing the entire platform.

# # #             raise

# # #         # ----------------------------------------------------
# # #         # Camera is best effort.
# # #         # ----------------------------------------------------

# # #         opened = await self._open_camera()

# # #         if opened:
# # #             print(
# # #                 f"[{self.agent_id}] "
# # #                 f"Camera opened successfully: "
# # #                 f"camera_id={self.camera_id}, "
# # #                 f"source={self.camera_source}"
# # #             )
# # #         else:
# # #             print(
# # #                 f"[{self.agent_id}] "
# # #                 f"Camera unavailable: "
# # #                 f"camera_id={self.camera_id}, "
# # #                 f"source={self.camera_source}. "
# # #                 "Worker remains alive and will retry."
# # #             )

# # #     # ============================================================
# # #     # LOAD CLASS NAMES
# # #     # ============================================================

# # #     def _load_class_names(self):
# # #         if self.model is None:
# # #             return

# # #         names = getattr(
# # #             self.model,
# # #             "names",
# # #             {},
# # #         )

# # #         if isinstance(names, dict):
# # #             self.class_names = {
# # #                 int(key): str(value)
# # #                 for key, value in names.items()
# # #             }

# # #         elif isinstance(names, list):
# # #             self.class_names = {
# # #                 index: str(value)
# # #                 for index, value in enumerate(names)
# # #             }

# # #         else:
# # #             self.class_names = {}

# # #     # ============================================================
# # #     # CAMERA OPEN
# # #     # ============================================================

# # #     async def _open_camera(self) -> bool:
# # #         """
# # #         Open ONLY this worker's configured camera source.

# # #         This function never changes:
# # #             self.camera_id
# # #             self.camera_source
# # #         """

# # #         self._validate_camera_identity()

# # #         loop = asyncio.get_running_loop()

# # #         # ----------------------------------------------------
# # #         # Release previous capture
# # #         # ----------------------------------------------------

# # #         old_cap = self.cap

# # #         if old_cap is not None:
# # #             try:
# # #                 await loop.run_in_executor(
# # #                     None,
# # #                     old_cap.release,
# # #                 )
# # #             except Exception as error:
# # #                 print(
# # #                     f"[{self.agent_id}] "
# # #                     f"Previous camera release error "
# # #                     f"isolated: {error}"
# # #                 )

# # #             self.cap = None

# # #         # ----------------------------------------------------
# # #         # Normalize source
# # #         # ----------------------------------------------------

# # #         source = self._normalize_camera_source(
# # #             self.camera_source
# # #         )

# # #         print(
# # #             f"[{self.agent_id}] "
# # #             f"Opening camera: "
# # #             f"camera_id={self.camera_id}, "
# # #             f"source={self.camera_source}"
# # #         )

# # #         # ----------------------------------------------------
# # #         # Open capture
# # #         # ----------------------------------------------------

# # #         try:
# # #             cap = await loop.run_in_executor(
# # #                 None,
# # #                 cv2.VideoCapture,
# # #                 source,
# # #             )

# # #             if cap is None:
# # #                 print(
# # #                     f"[{self.agent_id}] "
# # #                     "cv2.VideoCapture returned None."
# # #                 )
# # #                 return False

# # #             is_opened = await loop.run_in_executor(
# # #                 None,
# # #                 cap.isOpened,
# # #             )

# # #             if not is_opened:
# # #                 print(
# # #                     f"[{self.agent_id}] "
# # #                     f"Camera failed to open: "
# # #                     f"camera_id={self.camera_id}, "
# # #                     f"source={self.camera_source}"
# # #                 )

# # #                 try:
# # #                     await loop.run_in_executor(
# # #                         None,
# # #                         cap.release,
# # #                     )
# # #                 except Exception:
# # #                     pass

# # #                 return False

# # #             # ------------------------------------------------
# # #             # Low-latency buffer
# # #             # ------------------------------------------------

# # #             try:
# # #                 await loop.run_in_executor(
# # #                     None,
# # #                     lambda: cap.set(
# # #                         cv2.CAP_PROP_BUFFERSIZE,
# # #                         1,
# # #                     ),
# # #                 )
# # #             except Exception as error:
# # #                 print(
# # #                     f"[{self.agent_id}] "
# # #                     "Camera buffer configuration "
# # #                     f"failed but isolated: {error}"
# # #                 )

# # #             # ------------------------------------------------
# # #             # Assign capture ONLY after successful open.
# # #             # ------------------------------------------------

# # #             self.cap = cap

# # #             self.read_failures = 0

# # #             self.reconnect_delay = (
# # #                 self.reconnect_initial_delay
# # #             )

# # #             return True

# # #         except Exception as error:
# # #             print(
# # #                 f"[{self.agent_id}] "
# # #                 f"Camera open error isolated: "
# # #                 f"{type(error).__name__}: {error}"
# # #             )

# # #             return False

# # #     # ============================================================
# # #     # CAMERA SOURCE NORMALIZATION
# # #     # ============================================================

# # #     @staticmethod
# # #     def _normalize_camera_source(
# # #         source: str,
# # #     ) -> str | int:
# # #         """
# # #         Convert numeric webcam source to int.

# # #         Examples:

# # #             "0"  → 0
# # #             "1"  → 1
# # #             "rtsp://..." → string
# # #             "video.mp4" → string
# # #         """

# # #         value = str(source).strip()

# # #         if (
# # #             value.isdigit()
# # #             and not value.startswith("0x")
# # #         ):
# # #             try:
# # #                 return int(value)
# # #             except ValueError:
# # #                 pass

# # #         return value

# # #     # ============================================================
# # #     # CAMERA RECONNECT
# # #     # ============================================================

# # #     async def _reconnect_camera(self):
# # #         """
# # #         Reconnect ONLY this worker's camera.

# # #         No other camera state is touched.
# # #         """

# # #         self._validate_camera_identity()

# # #         if self.reconnect_in_progress:
# # #             return

# # #         self.reconnect_in_progress = True

# # #         try:
# # #             current_camera_id = self.camera_id
# # #             current_source = self.camera_source

# # #             print(
# # #                 f"[{self.agent_id}] "
# # #                 f"Camera reconnect scheduled: "
# # #                 f"camera_id={current_camera_id}, "
# # #                 f"source={current_source}, "
# # #                 f"delay={self.reconnect_delay:.1f}s"
# # #             )

# # #             await asyncio.sleep(
# # #                 self.reconnect_delay
# # #             )

# # #             if not self.running:
# # #                 return

# # #             # Verify identity again after sleep.
# # #             self._validate_camera_identity()

# # #             opened = await self._open_camera()

# # #             if opened:
# # #                 print(
# # #                     f"[{self.agent_id}] "
# # #                     f"Camera reconnected successfully: "
# # #                     f"camera_id={self.camera_id}, "
# # #                     f"source={self.camera_source}"
# # #                 )

# # #                 self.reconnect_delay = (
# # #                     self.reconnect_initial_delay
# # #                 )

# # #             else:
# # #                 self.reconnect_delay = min(
# # #                     self.reconnect_delay * 2,
# # #                     self.reconnect_max_delay,
# # #                 )

# # #                 print(
# # #                     f"[{self.agent_id}] "
# # #                     f"Camera reconnect failed: "
# # #                     f"camera_id={self.camera_id}, "
# # #                     f"source={self.camera_source}, "
# # #                     f"next_delay={self.reconnect_delay:.1f}s"
# # #                 )

# # #         finally:
# # #             self.reconnect_in_progress = False

# # #     # ============================================================
# # #     # STOP
# # #     # ============================================================

# # #     async def on_stop(self):
# # #         loop = asyncio.get_running_loop()

# # #         cap = self.cap

# # #         self.cap = None

# # #         if cap is not None:
# # #             try:
# # #                 await loop.run_in_executor(
# # #                     None,
# # #                     cap.release,
# # #                 )
# # #             except Exception as error:
# # #                 print(
# # #                     f"[{self.agent_id}] "
# # #                     f"Camera release error isolated: "
# # #                     f"{error}"
# # #                 )

# # #         if self.show_camera:
# # #             try:
# # #                 window_name = (
# # #                     f"CCTV AI - {self.camera_id}"
# # #                 )

# # #                 cv2.destroyWindow(
# # #                     window_name
# # #                 )

# # #             except Exception:
# # #                 # Some OpenCV backends do not support
# # #                 # destroyWindow reliably.
# # #                 pass

# # #             try:
# # #                 cv2.destroyAllWindows()
# # #             except Exception:
# # #                 pass

# # #         print(
# # #             f"[{self.agent_id}] "
# # #             f"Detection worker stopped: "
# # #             f"camera_id={self.camera_id}"
# # #         )

# # #     # ============================================================
# # #     # INFERENCE
# # #     # ============================================================

# # #     def _run_yolo(
# # #         self,
# # #         frame,
# # #     ):
# # #         if self.model is None:
# # #             raise RuntimeError(
# # #                 "YOLO model is not initialized."
# # #             )

# # #         return self.model(
# # #             frame,
# # #             conf=self.confidence,
# # #             iou=self.iou,
# # #             classes=self.class_filter,
# # #             verbose=False,
# # #         )

# # #     # ============================================================
# # #     # EXTRACT DETECTIONS
# # #     # ============================================================

# # #     def _extract_detections(
# # #         self,
# # #         results,
# # #     ) -> list[dict[str, Any]]:
# # #         detections: list[dict[str, Any]] = []

# # #         for result in results:
# # #             if result.boxes is None:
# # #                 continue

# # #             boxes = result.boxes

# # #             for index in range(len(boxes)):
# # #                 box = boxes[index]

# # #                 xyxy = (
# # #                     box.xyxy[0]
# # #                     .cpu()
# # #                     .tolist()
# # #                 )

# # #                 confidence = float(
# # #                     box.conf[0]
# # #                     .cpu()
# # #                     .item()
# # #                 )

# # #                 class_id = int(
# # #                     box.cls[0]
# # #                     .cpu()
# # #                     .item()
# # #                 )

# # #                 class_name = self.class_names.get(
# # #                     class_id,
# # #                     f"class_{class_id}",
# # #                 )

# # #                 detection_id = (
# # #                     f"det-"
# # #                     f"{self.camera_id}-"
# # #                     f"{self.frame_id}-"
# # #                     f"{uuid.uuid4().hex[:8]}"
# # #                 )

# # #                 x1 = float(xyxy[0])
# # #                 y1 = float(xyxy[1])
# # #                 x2 = float(xyxy[2])
# # #                 y2 = float(xyxy[3])

# # #                 detections.append(
# # #                     {
# # #                         "detection_id": detection_id,
# # #                         "class_id": class_id,
# # #                         "class_name": class_name,
# # #                         "confidence": confidence,
# # #                         "bbox": [
# # #                             x1,
# # #                             y1,
# # #                             x2,
# # #                             y2,
# # #                         ],
# # #                     }
# # #                 )

# # #         return detections

# # #     # ============================================================
# # #     # SPLIT DETECTIONS
# # #     # ============================================================

# # #     @staticmethod
# # #     def _split_detections(
# # #         detections: list[dict[str, Any]],
# # #     ):
# # #         people: list[dict[str, Any]] = []

# # #         vehicles: list[dict[str, Any]] = []

# # #         for detection in detections:
# # #             class_id = int(
# # #                 detection["class_id"]
# # #             )

# # #             if class_id == DetectionAgent.PERSON_CLASS_ID:
# # #                 people.append(detection)

# # #             if class_id in DetectionAgent.VEHICLE_CLASS_IDS:
# # #                 vehicles.append(detection)

# # #         return people, vehicles

# # #     # ============================================================
# # #     # EVENT PUBLISHING
# # #     # ============================================================

# # #     async def _publish_event(
# # #         self,
# # #         stream: str,
# # #         event_type: str,
# # #         data: dict[str, Any],
# # #         trace_id: str | None = None,
# # #         correlation_id: str | None = None,
# # #         incident_id: str | None = None,
# # #     ):
# # #         self._validate_camera_identity()

# # #         event = create_event(
# # #             event_type=event_type,
# # #             agent_id=self.agent_id,
# # #             instance_id=self.instance_id,
# # #             hostname=self.hostname,
# # #             camera_id=self.camera_id,
# # #             mode="live",
# # #             trace_id=trace_id,
# # #             correlation_id=correlation_id,
# # #             incident_id=incident_id,
# # #             data=data,
# # #         )

# # #         return await self.publish(
# # #             stream,
# # #             event.to_dict(),
# # #         )

# # #     # ============================================================
# # #     # PERSON EVENT
# # #     # ============================================================

# # #     async def _publish_person_event(
# # #         self,
# # #         people: list[dict[str, Any]],
# # #         frame_timestamp: str,
# # #     ):
# # #         """
# # #         Preserve the event contract expected by tracker.

# # #         Empty person observations are intentionally published.
# # #         """

# # #         data = {
# # #             "frame_id": str(
# # #                 self.frame_id
# # #             ),
# # #             "frame_timestamp": frame_timestamp,
# # #             "detection_count": len(people),
# # #             "count": len(people),
# # #             "detections": people,
# # #             "model": self.model_path,
# # #             "confidence_threshold": self.confidence,
# # #         }

# # #         return await self._publish_event(
# # #             stream=self.detection_stream,
# # #             event_type="person.detected",
# # #             data=data,
# # #         )

# # #     # ============================================================
# # #     # VEHICLE EVENT
# # #     # ============================================================

# # #     async def _publish_vehicle_event(
# # #         self,
# # #         vehicles: list[dict[str, Any]],
# # #         frame_timestamp: str,
# # #     ):
# # #         data = {
# # #             "frame_id": str(
# # #                 self.frame_id
# # #             ),
# # #             "frame_timestamp": frame_timestamp,
# # #             "vehicle_count": len(vehicles),
# # #             "count": len(vehicles),
# # #             "vehicles": vehicles,
# # #             "model": self.model_path,
# # #             "confidence_threshold": self.confidence,
# # #         }

# # #         return await self._publish_event(
# # #             stream=self.vehicle_stream,
# # #             event_type="vehicle.detected",
# # #             data=data,
# # #         )

# # #     # ============================================================
# # #     # GENERIC OBJECT EVENT
# # #     # ============================================================

# # #     async def _publish_object_event(
# # #         self,
# # #         detections: list[dict[str, Any]],
# # #         frame_timestamp: str,
# # #     ):
# # #         data = {
# # #             "frame_id": str(
# # #                 self.frame_id
# # #             ),
# # #             "frame_timestamp": frame_timestamp,
# # #             "object_count": len(detections),
# # #             "count": len(detections),
# # #             "detections": detections,
# # #             "model": self.model_path,
# # #             "confidence_threshold": self.confidence,
# # #         }

# # #         return await self._publish_event(
# # #             stream=self.object_stream,
# # #             event_type="object.detected",
# # #             data=data,
# # #         )

# # #     # ============================================================
# # #     # ANNOTATION
# # #     # ============================================================

# # #     def _annotate_frame(
# # #         self,
# # #         frame,
# # #         detections: list[dict[str, Any]],
# # #     ):
# # #         annotated_frame = frame.copy()

# # #         for detection in detections:
# # #             bbox = detection["bbox"]

# # #             x1 = int(bbox[0])
# # #             y1 = int(bbox[1])
# # #             x2 = int(bbox[2])
# # #             y2 = int(bbox[3])

# # #             confidence = float(
# # #                 detection["confidence"]
# # #             )

# # #             class_id = int(
# # #                 detection["class_id"]
# # #             )

# # #             class_name = str(
# # #                 detection["class_name"]
# # #             )

# # #             if class_id == self.PERSON_CLASS_ID:
# # #                 label = (
# # #                     f"Person "
# # #                     f"{confidence:.2f}"
# # #                 )

# # #             else:
# # #                 label = (
# # #                     f"{class_name} "
# # #                     f"{confidence:.2f}"
# # #                 )

# # #             cv2.rectangle(
# # #                 annotated_frame,
# # #                 (x1, y1),
# # #                 (x2, y2),
# # #                 (0, 255, 0),
# # #                 2,
# # #             )

# # #             cv2.putText(
# # #                 annotated_frame,
# # #                 label,
# # #                 (
# # #                     x1,
# # #                     max(
# # #                         y1 - 10,
# # #                         20,
# # #                     ),
# # #                 ),
# # #                 cv2.FONT_HERSHEY_SIMPLEX,
# # #                 0.5,
# # #                 (0, 255, 0),
# # #                 2,
# # #             )

# # #         # ----------------------------------------------------
# # #         # Camera metadata
# # #         # ----------------------------------------------------

# # #         cv2.putText(
# # #             annotated_frame,
# # #             (
# # #                 f"Camera: {self.camera_id} | "
# # #                 f"Frame: {self.frame_id} | "
# # #                 f"Objects: {len(detections)}"
# # #             ),
# # #             (10, 25),
# # #             cv2.FONT_HERSHEY_SIMPLEX,
# # #             0.6,
# # #             (255, 255, 255),
# # #             2,
# # #         )

# # #         return annotated_frame

# # #     # ============================================================
# # #     # ATOMIC IMAGE WRITE
# # #     # ============================================================

# # #     def _write_latest_frame(
# # #         self,
# # #         frame,
# # #     ):
# # #         """
# # #         Write only to this camera's evidence directory.

# # #         Example:

# # #             data/evidence/CAM01/latest.jpg
# # #             data/evidence/CAM02/latest.jpg

# # #         Atomic replace prevents readers from seeing a
# # #         partially-written JPEG.
# # #         """

# # #         target = self.latest_frame_path

# # #         temp_path: Path | None = None

# # #         try:
# # #             target.parent.mkdir(
# # #                 parents=True,
# # #                 exist_ok=True,
# # #             )

# # #             temp_path = target.with_name(
# # #                 f".{target.stem}."
# # #                 f"{uuid.uuid4().hex}"
# # #                 f"{target.suffix}"
# # #             )

# # #             success = cv2.imwrite(
# # #                 str(temp_path),
# # #                 frame,
# # #             )

# # #             if not success:
# # #                 raise RuntimeError(
# # #                     "cv2.imwrite returned False"
# # #                 )

# # #             os.replace(
# # #                 temp_path,
# # #                 target,
# # #             )

# # #         except Exception as error:
# # #             print(
# # #                 f"[{self.agent_id}] "
# # #                 f"Latest-frame write failed: "
# # #                 f"camera_id={self.camera_id}, "
# # #                 f"target={target}, "
# # #                 f"error={error}"
# # #             )

# # #             if temp_path is not None:
# # #                 try:
# # #                     if temp_path.exists():
# # #                         temp_path.unlink()
# # #                 except Exception:
# # #                     pass

# # #     # ============================================================
# # #     # DISPLAY
# # #     # ============================================================

# # #     def _display_frame(
# # #         self,
# # #         frame,
# # #     ) -> bool:
# # #         """
# # #         Returns False when operator requests shutdown.
# # #         """

# # #         if not self.show_camera:
# # #             return True

# # #         try:
# # #             window_name = (
# # #                 f"CCTV AI - "
# # #                 f"{self.camera_id}"
# # #             )

# # #             cv2.imshow(
# # #                 window_name,
# # #                 frame,
# # #             )

# # #             key = (
# # #                 cv2.waitKey(1)
# # #                 & 0xFF
# # #             )

# # #             if key == ord("q"):
# # #                 print(
# # #                     f"[{self.agent_id}] "
# # #                     f"Shutdown requested by operator: "
# # #                     f"camera_id={self.camera_id}"
# # #                 )

# # #                 return False

# # #         except Exception as error:
# # #             # Display failure must never terminate
# # #             # the detector worker.

# # #             print(
# # #                 f"[{self.agent_id}] "
# # #                 f"Display error isolated: "
# # #                 f"camera_id={self.camera_id}, "
# # #                 f"error={error}"
# # #             )

# # #         return True

# # #     # ============================================================
# # #     # MAIN LOOP
# # #     # ============================================================

# # #     async def run(self):
# # #         if self.model is None:
# # #             raise RuntimeError(
# # #                 "YOLO model is not initialized."
# # #             )

# # #         self._validate_camera_identity()

# # #         print(
# # #             f"[{self.agent_id}] "
# # #             f"Detection loop started: "
# # #             f"camera_id={self.camera_id}, "
# # #             f"source={self.camera_source}"
# # #         )

# # #         loop = asyncio.get_running_loop()

# # #         while self.running:

# # #             try:
# # #                 # ------------------------------------------------
# # #                 # Identity protection
# # #                 # ------------------------------------------------

# # #                 self._validate_camera_identity()

# # #                 # ------------------------------------------------
# # #                 # Camera unavailable
# # #                 # ------------------------------------------------

# # #                 if self.cap is None:
# # #                     await self._reconnect_camera()
# # #                     continue

# # #                 # ------------------------------------------------
# # #                 # Read frame
# # #                 # ------------------------------------------------

# # #                 cap = self.cap

# # #                 ret, frame = await loop.run_in_executor(
# # #                     None,
# # #                     cap.read,
# # #                 )

# # #                 # If another operation replaced the capture
# # #                 # while this read was executing, ignore the result.
# # #                 if cap is not self.cap:
# # #                     continue

# # #                 if not ret or frame is None:
# # #                     self.read_failures += 1

# # #                     print(
# # #                         f"[{self.agent_id}] "
# # #                         f"Camera frame read failed "
# # #                         f"({self.read_failures}/"
# # #                         f"{self.read_failure_before_reconnect}) | "
# # #                         f"camera_id={self.camera_id}"
# # #                     )

# # #                     if (
# # #                         self.read_failures
# # #                         >= self.read_failure_before_reconnect
# # #                     ):
# # #                         failed_cap = self.cap

# # #                         self.cap = None

# # #                         if failed_cap is not None:
# # #                             try:
# # #                                 await loop.run_in_executor(
# # #                                     None,
# # #                                     failed_cap.release,
# # #                                 )
# # #                             except Exception as error:
# # #                                 print(
# # #                                     f"[{self.agent_id}] "
# # #                                     "Failed camera release "
# # #                                     f"isolated: {error}"
# # #                                 )

# # #                         self.read_failures = 0

# # #                     await asyncio.sleep(
# # #                         min(
# # #                             self.reconnect_delay,
# # #                             2.0,
# # #                         )
# # #                     )

# # #                     continue

# # #                 # ------------------------------------------------
# # #                 # Successful frame
# # #                 # ------------------------------------------------

# # #                 self.read_failures = 0

# # #                 self.last_frame_time = (
# # #                     time.monotonic()
# # #                 )

# # #                 self.frame_id += 1

# # #                 # ------------------------------------------------
# # #                 # Optional inference throttling
# # #                 # ------------------------------------------------

# # #                 if self.inference_interval > 0:
# # #                     now = time.monotonic()

# # #                     elapsed = (
# # #                         now
# # #                         - self.last_inference_time
# # #                     )

# # #                     if (
# # #                         elapsed
# # #                         < self.inference_interval
# # #                     ):
# # #                         if not self._display_frame(
# # #                             frame
# # #                         ):
# # #                             break

# # #                         await asyncio.sleep(
# # #                             max(
# # #                                 0.0,
# # #                                 self.frame_interval,
# # #                             )
# # #                         )

# # #                         continue

# # #                 self.last_inference_time = (
# # #                     time.monotonic()
# # #                 )

# # #                 # ------------------------------------------------
# # #                 # Frame timestamp
# # #                 # ------------------------------------------------

# # #                 frame_timestamp = utc_timestamp()

# # #                 # ------------------------------------------------
# # #                 # YOLO inference
# # #                 # ------------------------------------------------

# # #                 results = await loop.run_in_executor(
# # #                     None,
# # #                     self._run_yolo,
# # #                     frame,
# # #                 )

# # #                 # ------------------------------------------------
# # #                 # Extract detections
# # #                 # ------------------------------------------------

# # #                 detections = (
# # #                     self._extract_detections(
# # #                         results
# # #                     )
# # #                 )

# # #                 people, vehicles = (
# # #                     self._split_detections(
# # #                         detections
# # #                     )
# # #                 )

# # #                 # ------------------------------------------------
# # #                 # Annotation
# # #                 # ------------------------------------------------

# # #                 annotated_frame = (
# # #                     self._annotate_frame(
# # #                         frame,
# # #                         detections,
# # #                     )
# # #                 )

# # #                 # ------------------------------------------------
# # #                 # Publish person event
# # #                 # ------------------------------------------------

# # #                 person_redis_id = (
# # #                     await self._publish_person_event(
# # #                         people,
# # #                         frame_timestamp,
# # #                     )
# # #                 )

# # #                 # ------------------------------------------------
# # #                 # Publish vehicle event
# # #                 # ------------------------------------------------

# # #                 vehicle_redis_id = (
# # #                     await self._publish_vehicle_event(
# # #                         vehicles,
# # #                         frame_timestamp,
# # #                     )
# # #                 )

# # #                 # ------------------------------------------------
# # #                 # Publish generic object event
# # #                 # ------------------------------------------------

# # #                 object_redis_id = (
# # #                     await self._publish_object_event(
# # #                         detections,
# # #                         frame_timestamp,
# # #                     )
# # #                 )

# # #                 # ------------------------------------------------
# # #                 # Camera-specific latest frame
# # #                 # ------------------------------------------------

# # #                 self._write_latest_frame(
# # #                     annotated_frame
# # #                 )

# # #                 # ------------------------------------------------
# # #                 # Logging
# # #                 # ------------------------------------------------

# # #                 print(
# # #                     f"DETECTED | "
# # #                     f"Agent={self.agent_id} | "
# # #                     f"Camera={self.camera_id} | "
# # #                     f"Frame={self.frame_id} | "
# # #                     f"Persons={len(people)} | "
# # #                     f"Vehicles={len(vehicles)} | "
# # #                     f"Objects={len(detections)} | "
# # #                     f"PersonRedis={person_redis_id} | "
# # #                     f"VehicleRedis={vehicle_redis_id} | "
# # #                     f"ObjectRedis={object_redis_id}"
# # #                 )

# # #                 # ------------------------------------------------
# # #                 # Display
# # #                 # ------------------------------------------------

# # #                 if not self._display_frame(
# # #                     annotated_frame
# # #                 ):
# # #                     break

# # #                 # ------------------------------------------------
# # #                 # Frame pacing
# # #                 # ------------------------------------------------

# # #                 if self.frame_interval > 0:
# # #                     await asyncio.sleep(
# # #                         self.frame_interval
# # #                     )

# # #             # ====================================================
# # #             # SHUTDOWN
# # #             # ====================================================

# # #             except asyncio.CancelledError:
# # #                 raise

# # #             # ====================================================
# # #             # INDIVIDUAL ITERATION FAILURE
# # #             # ====================================================

# # #             except Exception as error:
# # #                 """
# # #                 CRITICAL FAULT-ISOLATION RULE:

# # #                 A single frame, inference, Redis publish,
# # #                 annotation, evidence write, or other iteration
# # #                 failure must NOT terminate this camera worker.

# # #                 The supervisor may still restart this worker
# # #                 if the process itself becomes unhealthy.
# # #                 """

# # #                 print(
# # #                     f"[{self.agent_id}] "
# # #                     f"Detection iteration error isolated | "
# # #                     f"camera_id={self.camera_id} | "
# # #                     f"type={type(error).__name__} | "
# # #                     f"error={error}"
# # #                 )

# # #                 await asyncio.sleep(
# # #                     1.0
# # #                 )

# # #         print(
# # #             f"[{self.agent_id}] "
# # #             f"Detection loop stopped | "
# # #             f"camera_id={self.camera_id}"
# # #         )


# # # # ============================================================
# # # # MAIN
# # # # ============================================================

# # # async def main():
# # #     agent = DetectionAgent()
# # #     await agent.run_forever()


# # # if __name__ == "__main__":
# # #     asyncio.run(main())




# # """
# # Per-camera CCTV Detection Agent.

# # Responsibilities
# # ----------------
# # - Capture frames from exactly one configured camera.
# # - Run YOLO object detection.
# # - Publish structured detection events.
# # - Maintain a camera-specific latest.jpg.
# # - Maintain a bounded rolling evidence buffer.

# # This worker does NOT:
# # - perform tracking
# # - perform cross-camera ReID
# # - perform behavior reasoning
# # - generate incidents
# # - generate final proof videos
# # - perform LLM reasoning

# # All downstream intelligence remains isolated.
# # """

# # from __future__ import annotations

# # import asyncio
# # import os
# # import time
# # import uuid
# # from datetime import datetime, timezone
# # from pathlib import Path
# # from typing import Any

# # import cv2
# # from ultralytics import YOLO

# # from agents.detection.evidence_buffer import (
# #     RollingEvidenceBuffer,
# # )

# # from shared.agent.base_agent import BaseAgent
# # from shared.schemas.event_schema import create_event


# # # ============================================================
# # # PATHS
# # # ============================================================

# # PROJECT_ROOT = Path(
# #     __file__
# # ).resolve().parents[2]

# # EVIDENCE_ROOT = (
# #     PROJECT_ROOT
# #     / "data"
# #     / "evidence"
# # )

# # EVIDENCE_ROOT.mkdir(
# #     parents=True,
# #     exist_ok=True,
# # )


# # # ============================================================
# # # HELPERS
# # # ============================================================


# # def parse_bool(
# #     value: str,
# #     default: bool = False,
# # ) -> bool:
# #     value = str(
# #         value
# #     ).strip().lower()

# #     if value in {
# #         "1",
# #         "true",
# #         "yes",
# #         "y",
# #         "on",
# #     }:
# #         return True

# #     if value in {
# #         "0",
# #         "false",
# #         "no",
# #         "n",
# #         "off",
# #     }:
# #         return False

# #     return default


# # def parse_positive_float(
# #     name: str,
# #     default: float,
# # ) -> float:
# #     raw = os.getenv(
# #         name,
# #         str(default),
# #     )

# #     try:
# #         value = float(raw)
# #     except (
# #         TypeError,
# #         ValueError,
# #     ):
# #         return default

# #     if value <= 0:
# #         return default

# #     return value


# # def parse_non_negative_float(
# #     name: str,
# #     default: float,
# # ) -> float:
# #     raw = os.getenv(
# #         name,
# #         str(default),
# #     )

# #     try:
# #         value = float(raw)
# #     except (
# #         TypeError,
# #         ValueError,
# #     ):
# #         return default

# #     if value < 0:
# #         return default

# #     return value


# # def parse_positive_int(
# #     name: str,
# #     default: int,
# # ) -> int:
# #     raw = os.getenv(
# #         name,
# #         str(default),
# #     )

# #     try:
# #         value = int(raw)
# #     except (
# #         TypeError,
# #         ValueError,
# #     ):
# #         return default

# #     if value <= 0:
# #         return default

# #     return value


# # def parse_class_filter(
# #     raw_value: str,
# # ) -> list[int] | None:
# #     """
# #     Parse YOLO class filter.

# #     Examples:

# #         YOLO_CLASSES=0,2,3,5,7
# #         YOLO_CLASSES=0
# #         YOLO_CLASSES=all

# #     None means all model classes.
# #     """

# #     value = str(
# #         raw_value
# #     ).strip().lower()

# #     if not value or value == "all":
# #         return None

# #     classes: list[int] = []

# #     for item in value.split(","):
# #         item = item.strip()

# #         if not item:
# #             continue

# #         try:
# #             class_id = int(item)
# #         except ValueError:
# #             print(
# #                 "[DetectionAgent] "
# #                 f"Ignoring invalid YOLO class: "
# #                 f"{item}"
# #             )
# #             continue

# #         if class_id < 0:
# #             continue

# #         classes.append(
# #             class_id
# #         )

# #     if not classes:
# #         return None

# #     return sorted(
# #         set(classes)
# #     )


# # def utc_timestamp() -> str:
# #     """
# #     Return canonical timezone-aware UTC timestamp.
# #     """

# #     return (
# #         datetime.now(
# #             timezone.utc
# #         )
# #         .isoformat()
# #         .replace(
# #             "+00:00",
# #             "Z",
# #         )
# #     )


# # # ============================================================
# # # DETECTION AGENT
# # # ============================================================


# # class DetectionAgent(BaseAgent):
# #     """
# #     Per-camera CCTV object-detection worker.

# #     One DetectionAgent instance MUST belong to exactly one camera.
# #     """

# #     # COCO classes commonly useful for CCTV.
# #     #
# #     # 0 = person
# #     # 2 = car
# #     # 3 = motorcycle
# #     # 5 = bus
# #     # 7 = truck

# #     DEFAULT_CLASSES = (
# #         "0,2,3,5,7"
# #     )

# #     PERSON_CLASS_ID = 0

# #     VEHICLE_CLASS_IDS = {
# #         2,  # car
# #         3,  # motorcycle
# #         5,  # bus
# #         7,  # truck
# #     }

# #     # ========================================================
# #     # INIT
# #     # ========================================================

# #     def __init__(self):

# #         super().__init__(
# #             agent_id=os.getenv(
# #                 "AGENT_ID",
# #                 "person-detector-01",
# #             ),
# #             heartbeat_interval=parse_positive_int(
# #                 "HEARTBEAT_INTERVAL",
# #                 10,
# #             ),
# #         )

# #         # ----------------------------------------------------
# #         # Immutable camera identity
# #         # ----------------------------------------------------

# #         self.camera_id = os.getenv(
# #             "CAMERA_ID",
# #             "",
# #         ).strip()

# #         if not self.camera_id:
# #             raise ValueError(
# #                 "CAMERA_ID is required. "
# #                 "Detection workers must never "
# #                 "silently default to CAM01."
# #             )

# #         self._camera_identity = (
# #             self.camera_id
# #         )

# #         # ----------------------------------------------------
# #         # Camera metadata
# #         # ----------------------------------------------------

# #         self.camera_name = os.getenv(
# #             "CAMERA_NAME",
# #             self.camera_id,
# #         ).strip()

# #         self.camera_location = os.getenv(
# #             "CAMERA_LOCATION",
# #             "default",
# #         ).strip()

# #         # ----------------------------------------------------
# #         # Camera source
# #         # ----------------------------------------------------

# #         self.camera_source = os.getenv(
# #             "CAMERA_SOURCE",
# #             "",
# #         ).strip()

# #         # Backward compatibility.
# #         if not self.camera_source:
# #             self.camera_source = os.getenv(
# #                 "CAMERA_INDEX",
# #                 "0",
# #             ).strip()

# #         if not self.camera_source:
# #             raise ValueError(
# #                 f"CAMERA_SOURCE is required "
# #                 f"for {self.camera_id}."
# #             )

# #         self._camera_source_identity = (
# #             self.camera_source
# #         )

# #         # ----------------------------------------------------
# #         # YOLO configuration
# #         # ----------------------------------------------------

# #         self.model_path = os.getenv(
# #             "YOLO_MODEL",
# #             str(
# #                 PROJECT_ROOT
# #                 / "yolo11n.pt"
# #             ),
# #         ).strip()

# #         self.confidence = (
# #             parse_positive_float(
# #                 "YOLO_CONFIDENCE",
# #                 0.40,
# #             )
# #         )

# #         self.iou = (
# #             parse_positive_float(
# #                 "YOLO_IOU",
# #                 0.45,
# #             )
# #         )

# #         self.class_filter = (
# #             parse_class_filter(
# #                 os.getenv(
# #                     "YOLO_CLASSES",
# #                     self.DEFAULT_CLASSES,
# #                 )
# #             )
# #         )

# #         # ----------------------------------------------------
# #         # Frame processing
# #         # ----------------------------------------------------

# #         self.frame_interval = (
# #             parse_non_negative_float(
# #                 "FRAME_INTERVAL",
# #                 0.20,
# #             )
# #         )

# #         self.inference_interval = (
# #             parse_non_negative_float(
# #                 "INFERENCE_INTERVAL",
# #                 0.0,
# #             )
# #         )

# #         self.show_camera = parse_bool(
# #             os.getenv(
# #                 "SHOW_CAMERA",
# #                 "true",
# #             ),
# #             default=True,
# #         )

# #         # ----------------------------------------------------
# #         # Camera reconnect configuration
# #         # ----------------------------------------------------

# #         self.reconnect_initial_delay = (
# #             parse_positive_float(
# #                 "CAMERA_RECONNECT_INITIAL_DELAY",
# #                 1.0,
# #             )
# #         )

# #         self.reconnect_max_delay = (
# #             parse_positive_float(
# #                 "CAMERA_RECONNECT_MAX_DELAY",
# #                 30.0,
# #             )
# #         )

# #         self.read_failure_before_reconnect = max(
# #             1,
# #             parse_positive_int(
# #                 "CAMERA_READ_FAILURE_THRESHOLD",
# #                 3,
# #             ),
# #         )

# #         # ----------------------------------------------------
# #         # Event streams
# #         # ----------------------------------------------------

# #         self.detection_stream = os.getenv(
# #             "DETECTION_OUTPUT_STREAM",
# #             "events.detection",
# #         ).strip()

# #         self.vehicle_stream = os.getenv(
# #             "VEHICLE_OUTPUT_STREAM",
# #             "events.vehicle",
# #         ).strip()

# #         self.object_stream = os.getenv(
# #             "OBJECT_OUTPUT_STREAM",
# #             "events.objects",
# #         ).strip()

# #         # ----------------------------------------------------
# #         # Runtime state
# #         # ----------------------------------------------------

# #         self.model: YOLO | None = None

# #         self.cap: cv2.VideoCapture | None = None

# #         self.frame_id = 0

# #         self.last_inference_time = 0.0

# #         self.last_frame_time = 0.0

# #         self.read_failures = 0

# #         self.reconnect_delay = (
# #             self.reconnect_initial_delay
# #         )

# #         self.reconnect_in_progress = False

# #         # ----------------------------------------------------
# #         # Evidence
# #         # ----------------------------------------------------

# #         self.camera_evidence_dir = (
# #             EVIDENCE_ROOT
# #             / self._safe_camera_directory_name(
# #                 self.camera_id
# #             )
# #         )

# #         self.camera_evidence_dir.mkdir(
# #             parents=True,
# #             exist_ok=True,
# #         )

# #         self.latest_frame_path = (
# #             self.camera_evidence_dir
# #             / "latest.jpg"
# #         )

# #         # ----------------------------------------------------
# #         # Rolling evidence buffer
# #         # ----------------------------------------------------

# #         self.evidence_buffer = (
# #             RollingEvidenceBuffer(
# #                 camera_id=self.camera_id,
# #                 output_dir=self.camera_evidence_dir,
# #                 segment_seconds=parse_positive_float(
# #                     "EVIDENCE_SEGMENT_SECONDS",
# #                     5.0,
# #                 ),
# #                 retention_seconds=parse_positive_float(
# #                     "EVIDENCE_RETENTION_SECONDS",
# #                     60.0,
# #                 ),
# #                 fps=parse_positive_float(
# #                     "EVIDENCE_FPS",
# #                     20.0,
# #                 ),
# #             )
# #         )

# #         # ----------------------------------------------------
# #         # Model class metadata
# #         # ----------------------------------------------------

# #         self.class_names: dict[
# #             int,
# #             str,
# #         ] = {}

# #     # ========================================================
# #     # CAMERA DIRECTORY
# #     # ========================================================

# #     @staticmethod
# #     def _safe_camera_directory_name(
# #         camera_id: str,
# #     ) -> str:

# #         allowed = (
# #             "abcdefghijklmnopqrstuvwxyz"
# #             "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
# #             "0123456789"
# #             "-_."
# #         )

# #         result = "".join(
# #             character
# #             if character in allowed
# #             else "_"
# #             for character in camera_id
# #         )

# #         return (
# #             result[:120]
# #             or "camera"
# #         )

# #     # ========================================================
# #     # IDENTITY VALIDATION
# #     # ========================================================

# #     def _validate_camera_identity(
# #         self,
# #     ) -> None:

# #         if (
# #             self.camera_id
# #             != self._camera_identity
# #         ):
# #             raise RuntimeError(
# #                 "CAMERA ID MUTATION DETECTED: "
# #                 f"original={self._camera_identity}, "
# #                 f"current={self.camera_id}"
# #             )

# #         if (
# #             self.camera_source
# #             != self._camera_source_identity
# #         ):
# #             raise RuntimeError(
# #                 "CAMERA SOURCE MUTATION DETECTED: "
# #                 f"original={self._camera_source_identity}, "
# #                 f"current={self.camera_source}"
# #             )

# #     # ========================================================
# #     # START
# #     # ========================================================

# #     async def on_start(
# #         self,
# #     ):

# #         self._validate_camera_identity()

# #         print(
# #             f"[{self.agent_id}] "
# #             "Starting per-camera detection worker."
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Camera ID: {self.camera_id}"
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Camera name: {self.camera_name}"
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Camera location: {self.camera_location}"
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Camera source: {self.camera_source}"
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Evidence directory: "
# #             f"{self.camera_evidence_dir}"
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Evidence buffer: "
# #             f"{self.evidence_buffer.buffer_dir}"
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Evidence segment: "
# #             f"{self.evidence_buffer.segment_seconds:.1f}s"
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"Evidence retention: "
# #             f"{self.evidence_buffer.retention_seconds:.1f}s"
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             f"YOLO model: {self.model_path}"
# #         )

# #         if self.class_filter is None:
# #             print(
# #                 f"[{self.agent_id}] "
# #                 "YOLO classes: ALL"
# #             )
# #         else:
# #             print(
# #                 f"[{self.agent_id}] "
# #                 f"YOLO classes: "
# #                 f"{self.class_filter}"
# #             )

# #         # ----------------------------------------------------
# #         # Lazy model loading
# #         # ----------------------------------------------------

# #         try:
# #             self.model = YOLO(
# #                 self.model_path
# #             )

# #             self._load_class_names()

# #             print(
# #                 f"[{self.agent_id}] "
# #                 "YOLO model loaded successfully."
# #             )

# #         except Exception as error:

# #             print(
# #                 f"[{self.agent_id}] "
# #                 "YOLO model loading failed: "
# #                 f"{type(error).__name__}: "
# #                 f"{error}"
# #             )

# #             raise

# #         # ----------------------------------------------------
# #         # Camera is best effort
# #         # ----------------------------------------------------

# #         opened = await self._open_camera()

# #         if opened:

# #             print(
# #                 f"[{self.agent_id}] "
# #                 "Camera opened successfully: "
# #                 f"camera_id={self.camera_id}, "
# #                 f"source={self.camera_source}"
# #             )

# #         else:

# #             print(
# #                 f"[{self.agent_id}] "
# #                 "Camera unavailable: "
# #                 f"camera_id={self.camera_id}, "
# #                 f"source={self.camera_source}. "
# #                 "Worker remains alive and will retry."
# #             )

# #     # ========================================================
# #     # LOAD CLASS NAMES
# #     # ========================================================

# #     def _load_class_names(
# #         self,
# #     ) -> None:

# #         if self.model is None:
# #             return

# #         names = getattr(
# #             self.model,
# #             "names",
# #             {},
# #         )

# #         if isinstance(
# #             names,
# #             dict,
# #         ):

# #             self.class_names = {
# #                 int(key): str(value)
# #                 for key, value in names.items()
# #             }

# #         elif isinstance(
# #             names,
# #             list,
# #         ):

# #             self.class_names = {
# #                 index: str(value)
# #                 for index, value
# #                 in enumerate(names)
# #             }

# #         else:

# #             self.class_names = {}

# #     # ========================================================
# #     # CAMERA OPEN
# #     # ========================================================

# #     async def _open_camera(
# #         self,
# #     ) -> bool:

# #         self._validate_camera_identity()

# #         loop = (
# #             asyncio.get_running_loop()
# #         )

# #         # ----------------------------------------------------
# #         # Release previous capture
# #         # ----------------------------------------------------

# #         old_cap = self.cap

# #         if old_cap is not None:

# #             try:

# #                 await loop.run_in_executor(
# #                     None,
# #                     old_cap.release,
# #                 )

# #             except Exception as error:

# #                 print(
# #                     f"[{self.agent_id}] "
# #                     "Previous camera release "
# #                     f"error isolated: {error}"
# #                 )

# #             self.cap = None

# #         # ----------------------------------------------------
# #         # Normalize source
# #         # ----------------------------------------------------

# #         source = (
# #             self._normalize_camera_source(
# #                 self.camera_source
# #             )
# #         )

# #         print(
# #             f"[{self.agent_id}] "
# #             "Opening camera: "
# #             f"camera_id={self.camera_id}, "
# #             f"source={self.camera_source}"
# #         )

# #         # ----------------------------------------------------
# #         # Open capture
# #         # ----------------------------------------------------

# #         try:

# #             cap = await loop.run_in_executor(
# #                 None,
# #                 cv2.VideoCapture,
# #                 source,
# #             )

# #             if cap is None:

# #                 print(
# #                     f"[{self.agent_id}] "
# #                     "cv2.VideoCapture returned None."
# #                 )

# #                 return False

# #             is_opened = (
# #                 await loop.run_in_executor(
# #                     None,
# #                     cap.isOpened,
# #                 )
# #             )

# #             if not is_opened:

# #                 print(
# #                     f"[{self.agent_id}] "
# #                     "Camera failed to open: "
# #                     f"camera_id={self.camera_id}, "
# #                     f"source={self.camera_source}"
# #                 )

# #                 try:

# #                     await loop.run_in_executor(
# #                         None,
# #                         cap.release,
# #                     )

# #                 except Exception:
# #                     pass

# #                 return False

# #             # ------------------------------------------------
# #             # Low-latency buffer
# #             # ------------------------------------------------

# #             try:

# #                 await loop.run_in_executor(
# #                     None,
# #                     lambda: cap.set(
# #                         cv2.CAP_PROP_BUFFERSIZE,
# #                         1,
# #                     ),
# #                 )

# #             except Exception as error:

# #                 print(
# #                     f"[{self.agent_id}] "
# #                     "Camera buffer configuration "
# #                     f"failed but isolated: {error}"
# #                 )

# #             # ------------------------------------------------
# #             # Assign capture only after successful open
# #             # ------------------------------------------------

# #             self.cap = cap

# #             self.read_failures = 0

# #             self.reconnect_delay = (
# #                 self.reconnect_initial_delay
# #             )

# #             return True

# #         except Exception as error:

# #             print(
# #                 f"[{self.agent_id}] "
# #                 "Camera open error isolated: "
# #                 f"{type(error).__name__}: "
# #                 f"{error}"
# #             )

# #             return False

# #     # ========================================================
# #     # CAMERA SOURCE NORMALIZATION
# #     # ========================================================

# #     @staticmethod
# #     def _normalize_camera_source(
# #         source: str,
# #     ) -> str | int:

# #         value = str(
# #             source
# #         ).strip()

# #         if (
# #             value.isdigit()
# #             and not value.startswith("0x")
# #         ):

# #             try:
# #                 return int(value)
# #             except ValueError:
# #                 pass

# #         return value

# #     # ========================================================
# #     # CAMERA RECONNECT
# #     # ========================================================

# #     async def _reconnect_camera(
# #         self,
# #     ) -> None:

# #         self._validate_camera_identity()

# #         if self.reconnect_in_progress:
# #             return

# #         self.reconnect_in_progress = True

# #         try:

# #             print(
# #                 f"[{self.agent_id}] "
# #                 "Camera reconnect scheduled: "
# #                 f"camera_id={self.camera_id}, "
# #                 f"source={self.camera_source}, "
# #                 f"delay={self.reconnect_delay:.1f}s"
# #             )

# #             await asyncio.sleep(
# #                 self.reconnect_delay
# #             )

# #             if not self.running:
# #                 return

# #             self._validate_camera_identity()

# #             opened = await self._open_camera()

# #             if opened:

# #                 print(
# #                     f"[{self.agent_id}] "
# #                     "Camera reconnected successfully: "
# #                     f"camera_id={self.camera_id}, "
# #                     f"source={self.camera_source}"
# #                 )

# #                 self.reconnect_delay = (
# #                     self.reconnect_initial_delay
# #                 )

# #             else:

# #                 self.reconnect_delay = min(
# #                     self.reconnect_delay * 2,
# #                     self.reconnect_max_delay,
# #                 )

# #                 print(
# #                     f"[{self.agent_id}] "
# #                     "Camera reconnect failed: "
# #                     f"camera_id={self.camera_id}, "
# #                     f"source={self.camera_source}, "
# #                     f"next_delay="
# #                     f"{self.reconnect_delay:.1f}s"
# #                 )

# #         finally:

# #             self.reconnect_in_progress = False

# #     # ========================================================
# #     # STOP
# #     # ========================================================

# #     async def on_stop(
# #         self,
# #     ):

# #         loop = (
# #             asyncio.get_running_loop()
# #         )

# #         # ----------------------------------------------------
# #         # Close evidence buffer first
# #         # ----------------------------------------------------

# #         try:

# #             self.evidence_buffer.close()

# #         except Exception as error:

# #             print(
# #                 f"[{self.agent_id}] "
# #                 "Evidence buffer close failed "
# #                 f"but isolated: {error}"
# #             )

# #         # ----------------------------------------------------
# #         # Release camera
# #         # ----------------------------------------------------

# #         cap = self.cap

# #         self.cap = None

# #         if cap is not None:

# #             try:

# #                 await loop.run_in_executor(
# #                     None,
# #                     cap.release,
# #                 )

# #             except Exception as error:

# #                 print(
# #                     f"[{self.agent_id}] "
# #                     "Camera release error isolated: "
# #                     f"{error}"
# #                 )

# #         # ----------------------------------------------------
# #         # Close OpenCV window
# #         # ----------------------------------------------------

# #         if self.show_camera:

# #             try:

# #                 cv2.destroyWindow(
# #                     f"CCTV AI - {self.camera_id}"
# #                 )

# #             except Exception:
# #                 pass

# #             try:

# #                 cv2.destroyAllWindows()

# #             except Exception:
# #                 pass

# #         print(
# #             f"[{self.agent_id}] "
# #             "Detection worker stopped: "
# #             f"camera_id={self.camera_id}"
# #         )

# #     # ========================================================
# #     # INFERENCE
# #     # ========================================================

# #     def _run_yolo(
# #         self,
# #         frame,
# #     ):

# #         if self.model is None:

# #             raise RuntimeError(
# #                 "YOLO model is not initialized."
# #             )

# #         return self.model(
# #             frame,
# #             conf=self.confidence,
# #             iou=self.iou,
# #             classes=self.class_filter,
# #             verbose=False,
# #         )

# #     # ========================================================
# #     # EXTRACT DETECTIONS
# #     # ========================================================

# #     def _extract_detections(
# #         self,
# #         results,
# #     ) -> list[dict[str, Any]]:

# #         detections: list[
# #             dict[str, Any]
# #         ] = []

# #         for result in results:

# #             if result.boxes is None:
# #                 continue

# #             boxes = result.boxes

# #             for index in range(
# #                 len(boxes)
# #             ):

# #                 box = boxes[index]

# #                 xyxy = (
# #                     box.xyxy[0]
# #                     .cpu()
# #                     .tolist()
# #                 )

# #                 confidence = float(
# #                     box.conf[0]
# #                     .cpu()
# #                     .item()
# #                 )

# #                 class_id = int(
# #                     box.cls[0]
# #                     .cpu()
# #                     .item()
# #                 )

# #                 class_name = (
# #                     self.class_names.get(
# #                         class_id,
# #                         f"class_{class_id}",
# #                     )
# #                 )

# #                 detection_id = (
# #                     f"det-"
# #                     f"{self.camera_id}-"
# #                     f"{self.frame_id}-"
# #                     f"{uuid.uuid4().hex[:8]}"
# #                 )

# #                 x1 = float(
# #                     xyxy[0]
# #                 )

# #                 y1 = float(
# #                     xyxy[1]
# #                 )

# #                 x2 = float(
# #                     xyxy[2]
# #                 )

# #                 y2 = float(
# #                     xyxy[3]
# #                 )

# #                 detections.append(
# #                     {
# #                         "detection_id": detection_id,
# #                         "class_id": class_id,
# #                         "class_name": class_name,
# #                         "confidence": confidence,
# #                         "bbox": [
# #                             x1,
# #                             y1,
# #                             x2,
# #                             y2,
# #                         ],
# #                     }
# #                 )

# #         return detections

# #     # ========================================================
# #     # SPLIT DETECTIONS
# #     # ========================================================

# #     @staticmethod
# #     def _split_detections(
# #         detections: list[
# #             dict[str, Any]
# #         ],
# #     ):

# #         people: list[
# #             dict[str, Any]
# #         ] = []

# #         vehicles: list[
# #             dict[str, Any]
# #         ] = []

# #         for detection in detections:

# #             class_id = int(
# #                 detection[
# #                     "class_id"
# #                 ]
# #             )

# #             if (
# #                 class_id
# #                 == DetectionAgent.PERSON_CLASS_ID
# #             ):

# #                 people.append(
# #                     detection
# #                 )

# #             if (
# #                 class_id
# #                 in DetectionAgent.VEHICLE_CLASS_IDS
# #             ):

# #                 vehicles.append(
# #                     detection
# #                 )

# #         return people, vehicles

# #     # ========================================================
# #     # EVENT PUBLISHING
# #     # ========================================================

# #     async def _publish_event(
# #         self,
# #         stream: str,
# #         event_type: str,
# #         data: dict[str, Any],
# #         trace_id: str | None = None,
# #         correlation_id: str | None = None,
# #         incident_id: str | None = None,
# #     ):

# #         self._validate_camera_identity()

# #         event = create_event(
# #             event_type=event_type,
# #             agent_id=self.agent_id,
# #             instance_id=self.instance_id,
# #             hostname=self.hostname,
# #             camera_id=self.camera_id,
# #             mode="live",
# #             trace_id=trace_id,
# #             correlation_id=correlation_id,
# #             incident_id=incident_id,
# #             data=data,
# #         )

# #         return await self.publish(
# #             stream,
# #             event.to_dict(),
# #         )

# #     # ========================================================
# #     # PERSON EVENT
# #     # ========================================================

# #     async def _publish_person_event(
# #         self,
# #         people: list[
# #             dict[str, Any]
# #         ],
# #         frame_timestamp: str,
# #     ):

# #         data = {
# #             "frame_id": str(
# #                 self.frame_id
# #             ),
# #             "frame_timestamp": (
# #                 frame_timestamp
# #             ),
# #             "detection_count": len(
# #                 people
# #             ),
# #             "count": len(
# #                 people
# #             ),
# #             "detections": people,
# #             "model": self.model_path,
# #             "confidence_threshold": (
# #                 self.confidence
# #             ),
# #         }

# #         return await self._publish_event(
# #             stream=self.detection_stream,
# #             event_type="person.detected",
# #             data=data,
# #         )

# #     # ========================================================
# #     # VEHICLE EVENT
# #     # ========================================================

# #     async def _publish_vehicle_event(
# #         self,
# #         vehicles: list[
# #             dict[str, Any]
# #         ],
# #         frame_timestamp: str,
# #     ):

# #         data = {
# #             "frame_id": str(
# #                 self.frame_id
# #             ),
# #             "frame_timestamp": (
# #                 frame_timestamp
# #             ),
# #             "vehicle_count": len(
# #                 vehicles
# #             ),
# #             "count": len(
# #                 vehicles
# #             ),
# #             "vehicles": vehicles,
# #             "model": self.model_path,
# #             "confidence_threshold": (
# #                 self.confidence
# #             ),
# #         }

# #         return await self._publish_event(
# #             stream=self.vehicle_stream,
# #             event_type="vehicle.detected",
# #             data=data,
# #         )

# #     # ========================================================
# #     # GENERIC OBJECT EVENT
# #     # ========================================================

# #     async def _publish_object_event(
# #         self,
# #         detections: list[
# #             dict[str, Any]
# #         ],
# #         frame_timestamp: str,
# #     ):

# #         data = {
# #             "frame_id": str(
# #                 self.frame_id
# #             ),
# #             "frame_timestamp": (
# #                 frame_timestamp
# #             ),
# #             "object_count": len(
# #                 detections
# #             ),
# #             "count": len(
# #                 detections
# #             ),
# #             "detections": detections,
# #             "model": self.model_path,
# #             "confidence_threshold": (
# #                 self.confidence
# #             ),
# #         }

# #         return await self._publish_event(
# #             stream=self.object_stream,
# #             event_type="object.detected",
# #             data=data,
# #         )

# #     # ========================================================
# #     # ANNOTATION
# #     # ========================================================

# #     def _annotate_frame(
# #         self,
# #         frame,
# #         detections: list[
# #             dict[str, Any]
# #         ],
# #     ):

# #         annotated_frame = (
# #             frame.copy()
# #         )

# #         for detection in detections:

# #             bbox = detection[
# #                 "bbox"
# #             ]

# #             x1 = int(
# #                 bbox[0]
# #             )

# #             y1 = int(
# #                 bbox[1]
# #             )

# #             x2 = int(
# #                 bbox[2]
# #             )

# #             y2 = int(
# #                 bbox[3]
# #             )

# #             confidence = float(
# #                 detection[
# #                     "confidence"
# #                 ]
# #             )

# #             class_id = int(
# #                 detection[
# #                     "class_id"
# #                 ]
# #             )

# #             class_name = str(
# #                 detection[
# #                     "class_name"
# #                 ]
# #             )

# #             if (
# #                 class_id
# #                 == self.PERSON_CLASS_ID
# #             ):

# #                 label = (
# #                     f"Person "
# #                     f"{confidence:.2f}"
# #                 )

# #             else:

# #                 label = (
# #                     f"{class_name} "
# #                     f"{confidence:.2f}"
# #                 )

# #             cv2.rectangle(
# #                 annotated_frame,
# #                 (x1, y1),
# #                 (x2, y2),
# #                 (0, 255, 0),
# #                 2,
# #             )

# #             cv2.putText(
# #                 annotated_frame,
# #                 label,
# #                 (
# #                     x1,
# #                     max(
# #                         y1 - 10,
# #                         20,
# #                     ),
# #                 ),
# #                 cv2.FONT_HERSHEY_SIMPLEX,
# #                 0.5,
# #                 (0, 255, 0),
# #                 2,
# #             )

# #         cv2.putText(
# #             annotated_frame,
# #             (
# #                 f"Camera: "
# #                 f"{self.camera_id} | "
# #                 f"Frame: "
# #                 f"{self.frame_id} | "
# #                 f"Objects: "
# #                 f"{len(detections)}"
# #             ),
# #             (10, 25),
# #             cv2.FONT_HERSHEY_SIMPLEX,
# #             0.6,
# #             (255, 255, 255),
# #             2,
# #         )

# #         return annotated_frame

# #     # ========================================================
# #     # ATOMIC IMAGE WRITE
# #     # ========================================================

# #     def _write_latest_frame(
# #         self,
# #         frame,
# #     ):

# #         target = (
# #             self.latest_frame_path
# #         )

# #         temp_path: Path | None = None

# #         try:

# #             target.parent.mkdir(
# #                 parents=True,
# #                 exist_ok=True,
# #             )

# #             temp_path = (
# #                 target.with_name(
# #                     f".{target.stem}."
# #                     f"{uuid.uuid4().hex}"
# #                     f"{target.suffix}"
# #                 )
# #             )

# #             success = cv2.imwrite(
# #                 str(temp_path),
# #                 frame,
# #             )

# #             if not success:

# #                 raise RuntimeError(
# #                     "cv2.imwrite returned False"
# #                 )

# #             os.replace(
# #                 temp_path,
# #                 target,
# #             )

# #         except Exception as error:

# #             print(
# #                 f"[{self.agent_id}] "
# #                 "Latest-frame write failed: "
# #                 f"camera_id={self.camera_id}, "
# #                 f"target={target}, "
# #                 f"error={error}"
# #             )

# #             if (
# #                 temp_path is not None
# #             ):

# #                 try:

# #                     if temp_path.exists():
# #                         temp_path.unlink()

# #                 except Exception:
# #                     pass

# #     # ========================================================
# #     # DISPLAY
# #     # ========================================================

# #     def _display_frame(
# #         self,
# #         frame,
# #     ) -> bool:

# #         if not self.show_camera:
# #             return True

# #         try:

# #             window_name = (
# #                 f"CCTV AI - "
# #                 f"{self.camera_id}"
# #             )

# #             cv2.imshow(
# #                 window_name,
# #                 frame,
# #             )

# #             key = (
# #                 cv2.waitKey(1)
# #                 & 0xFF
# #             )

# #             if key == ord("q"):

# #                 print(
# #                     f"[{self.agent_id}] "
# #                     "Shutdown requested by operator: "
# #                     f"camera_id={self.camera_id}"
# #                 )

# #                 return False

# #         except Exception as error:

# #             print(
# #                 f"[{self.agent_id}] "
# #                 "Display error isolated: "
# #                 f"camera_id={self.camera_id}, "
# #                 f"error={error}"
# #             )

# #         return True

# #     # ========================================================
# #     # MAIN LOOP
# #     # ========================================================

# #     async def run(
# #         self,
# #     ):

# #         if self.model is None:

# #             raise RuntimeError(
# #                 "YOLO model is not initialized."
# #             )

# #         self._validate_camera_identity()

# #         print(
# #             f"[{self.agent_id}] "
# #             "Detection loop started: "
# #             f"camera_id={self.camera_id}, "
# #             f"source={self.camera_source}"
# #         )

# #         loop = (
# #             asyncio.get_running_loop()
# #         )

# #         while self.running:

# #             try:

# #                 # ------------------------------------------------
# #                 # Identity protection
# #                 # ------------------------------------------------

# #                 self._validate_camera_identity()

# #                 # ------------------------------------------------
# #                 # Camera unavailable
# #                 # ------------------------------------------------

# #                 if self.cap is None:

# #                     await self._reconnect_camera()

# #                     continue

# #                 # ------------------------------------------------
# #                 # Read frame
# #                 # ------------------------------------------------

# #                 cap = self.cap

# #                 ret, frame = (
# #                     await loop.run_in_executor(
# #                         None,
# #                         cap.read,
# #                     )
# #                 )

# #                 # If another operation replaced
# #                 # the capture while read was executing,
# #                 # ignore the result.

# #                 if cap is not self.cap:
# #                     continue

# #                 # ------------------------------------------------
# #                 # Read failure
# #                 # ------------------------------------------------

# #                 if (
# #                     not ret
# #                     or frame is None
# #                 ):

# #                     self.read_failures += 1

# #                     print(
# #                         f"[{self.agent_id}] "
# #                         "Camera frame read failed "
# #                         f"({self.read_failures}/"
# #                         f"{self.read_failure_before_reconnect}) | "
# #                         f"camera_id={self.camera_id}"
# #                     )

# #                     if (
# #                         self.read_failures
# #                         >= self.read_failure_before_reconnect
# #                     ):

# #                         failed_cap = (
# #                             self.cap
# #                         )

# #                         self.cap = None

# #                         if failed_cap is not None:

# #                             try:

# #                                 await loop.run_in_executor(
# #                                     None,
# #                                     failed_cap.release,
# #                                 )

# #                             except Exception as error:

# #                                 print(
# #                                     f"[{self.agent_id}] "
# #                                     "Failed camera release "
# #                                     f"isolated: {error}"
# #                                 )

# #                         # Close the current evidence
# #                         # segment cleanly.

# #                         try:

# #                             self.evidence_buffer.rotate()

# #                         except Exception as error:

# #                             print(
# #                                 f"[{self.agent_id}] "
# #                                 "Evidence buffer rotation "
# #                                 f"failed but isolated: {error}"
# #                             )

# #                         self.read_failures = 0

# #                     await asyncio.sleep(
# #                         min(
# #                             self.reconnect_delay,
# #                             2.0,
# #                         )
# #                     )

# #                     continue

# #                 # ------------------------------------------------
# #                 # Successful frame
# #                 # ------------------------------------------------

# #                 self.read_failures = 0

# #                 self.last_frame_time = (
# #                     time.monotonic()
# #                 )

# #                 self.frame_id += 1

# #                 # IMPORTANT:
# #                 #
# #                 # Capture the timestamp immediately after
# #                 # successful frame acquisition.
# #                 #
# #                 # This timestamp represents the camera frame,
# #                 # not the later YOLO inference completion time.

# #                 frame_timestamp = (
# #                     utc_timestamp()
# #                 )

# #                 frame_epoch = (
# #                     time.time()
# #                 )

# #                 # ------------------------------------------------
# #                 # ROLLING EVIDENCE BUFFER
# #                 # ------------------------------------------------
# #                 #
# #                 # This happens BEFORE inference throttling.
# #                 #
# #                 # Therefore the evidence buffer continues recording
# #                 # even when YOLO inference is intentionally throttled.

# #                 try:

# #                     buffer_written = (
# #                         self.evidence_buffer.write(
# #                             frame,
# #                             timestamp=frame_timestamp,
# #                             epoch=frame_epoch,
# #                         )
# #                     )

# #                     if not buffer_written:

# #                         print(
# #                             f"[{self.agent_id}] "
# #                             "Evidence buffer did not accept "
# #                             f"frame={self.frame_id} | "
# #                             f"camera_id={self.camera_id}"
# #                         )

# #                 except Exception as error:

# #                     # CRITICAL:
# #                     #
# #                     # Evidence recording failure must never
# #                     # terminate detection.

# #                     print(
# #                         f"[{self.agent_id}] "
# #                         "Evidence buffer error isolated | "
# #                         f"camera_id={self.camera_id} | "
# #                         f"type={type(error).__name__} | "
# #                         f"error={error}"
# #                     )

# #                 # ------------------------------------------------
# #                 # Optional inference throttling
# #                 # ------------------------------------------------

# #                 if (
# #                     self.inference_interval > 0
# #                 ):

# #                     now = time.monotonic()

# #                     elapsed = (
# #                         now
# #                         - self.last_inference_time
# #                     )

# #                     if (
# #                         elapsed
# #                         < self.inference_interval
# #                     ):

# #                         if not self._display_frame(
# #                             frame
# #                         ):

# #                             break

# #                         if (
# #                             self.frame_interval
# #                             > 0
# #                         ):

# #                             await asyncio.sleep(
# #                                 self.frame_interval
# #                             )

# #                         continue

# #                 self.last_inference_time = (
# #                     time.monotonic()
# #                 )

# #                 # ------------------------------------------------
# #                 # YOLO inference
# #                 # ------------------------------------------------

# #                 results = (
# #                     await loop.run_in_executor(
# #                         None,
# #                         self._run_yolo,
# #                         frame,
# #                     )
# #                 )

# #                 # ------------------------------------------------
# #                 # Extract detections
# #                 # ------------------------------------------------

# #                 detections = (
# #                     self._extract_detections(
# #                         results
# #                     )
# #                 )

# #                 people, vehicles = (
# #                     self._split_detections(
# #                         detections
# #                     )
# #                 )

# #                 # ------------------------------------------------
# #                 # Annotation
# #                 # ------------------------------------------------

# #                 annotated_frame = (
# #                     self._annotate_frame(
# #                         frame,
# #                         detections,
# #                     )
# #                 )

# #                 # ------------------------------------------------
# #                 # Publish person event
# #                 # ------------------------------------------------

# #                 person_redis_id = (
# #                     await self._publish_person_event(
# #                         people,
# #                         frame_timestamp,
# #                     )
# #                 )

# #                 # ------------------------------------------------
# #                 # Publish vehicle event
# #                 # ------------------------------------------------

# #                 vehicle_redis_id = (
# #                     await self._publish_vehicle_event(
# #                         vehicles,
# #                         frame_timestamp,
# #                     )
# #                 )

# #                 # ------------------------------------------------
# #                 # Publish generic object event
# #                 # ------------------------------------------------

# #                 object_redis_id = (
# #                     await self._publish_object_event(
# #                         detections,
# #                         frame_timestamp,
# #                     )
# #                 )

# #                 # ------------------------------------------------
# #                 # Camera-specific latest frame
# #                 # ------------------------------------------------

# #                 self._write_latest_frame(
# #                     annotated_frame
# #                 )

# #                 # ------------------------------------------------
# #                 # Logging
# #                 # ------------------------------------------------

# #                 print(
# #                     "DETECTED | "
# #                     f"Agent={self.agent_id} | "
# #                     f"Camera={self.camera_id} | "
# #                     f"Frame={self.frame_id} | "
# #                     f"Persons={len(people)} | "
# #                     f"Vehicles={len(vehicles)} | "
# #                     f"Objects={len(detections)} | "
# #                     f"PersonRedis={person_redis_id} | "
# #                     f"VehicleRedis={vehicle_redis_id} | "
# #                     f"ObjectRedis={object_redis_id}"
# #                 )

# #                 # ------------------------------------------------
# #                 # Display
# #                 # ------------------------------------------------

# #                 if not self._display_frame(
# #                     annotated_frame
# #                 ):

# #                     break

# #                 # ------------------------------------------------
# #                 # Frame pacing
# #                 # ------------------------------------------------

# #                 if (
# #                     self.frame_interval
# #                     > 0
# #                 ):

# #                     await asyncio.sleep(
# #                         self.frame_interval
# #                     )

# #             # ====================================================
# #             # SHUTDOWN
# #             # ====================================================

# #             except asyncio.CancelledError:

# #                 raise

# #             # ====================================================
# #             # INDIVIDUAL ITERATION FAILURE
# #             # ====================================================

# #             except Exception as error:

# #                 """
# #                 CRITICAL FAULT-ISOLATION RULE:

# #                 A single frame, inference, Redis publish,
# #                 annotation, evidence write, or other iteration
# #                 failure must NOT terminate this camera worker.
# #                 """

# #                 print(
# #                     f"[{self.agent_id}] "
# #                     "Detection iteration error isolated | "
# #                     f"camera_id={self.camera_id} | "
# #                     f"type={type(error).__name__} | "
# #                     f"error={error}"
# #                 )

# #                 await asyncio.sleep(
# #                     1.0
# #                 )

# #         print(
# #             f"[{self.agent_id}] "
# #             "Detection loop stopped | "
# #             f"camera_id={self.camera_id}"
# #         )


# # # ============================================================
# # # MAIN
# # # ============================================================


# # async def main():

# #     agent = DetectionAgent()

# #     await agent.run_forever()


# # if __name__ == "__main__":

# #     asyncio.run(
# #         main()
# #     )














# """
# Per-camera CCTV Detection Agent.

# Responsibilities
# ----------------

# - Capture frames from exactly one configured camera.
# - Run YOLO object detection.
# - Publish structured detection events.
# - Maintain a camera-specific latest.jpg.
# - Maintain a bounded rolling evidence buffer.

# This worker does NOT:

# - perform tracking
# - perform cross-camera ReID
# - perform behavior reasoning
# - generate incidents
# - generate final proof videos
# - perform LLM reasoning

# All downstream intelligence remains isolated.
# """

# from __future__ import annotations

# import asyncio
# import os
# import time
# import uuid
# from datetime import datetime, timezone
# from pathlib import Path
# from typing import Any

# import cv2
# from ultralytics import YOLO

# from agents.detection.evidence_buffer import RollingEvidenceBuffer
# from shared.agent.base_agent import BaseAgent
# from shared.schemas.event_schema import create_event


# # ============================================================
# # PATHS
# # ============================================================

# PROJECT_ROOT = Path(__file__).resolve().parents[2]

# EVIDENCE_ROOT = PROJECT_ROOT / "data" / "evidence"

# EVIDENCE_ROOT.mkdir(
#     parents=True,
#     exist_ok=True,
# )


# # ============================================================
# # HELPERS
# # ============================================================


# def parse_bool(
#     value: str,
#     default: bool = False,
# ) -> bool:
#     value = str(value).strip().lower()

#     if value in {
#         "1",
#         "true",
#         "yes",
#         "y",
#         "on",
#     }:
#         return True

#     if value in {
#         "0",
#         "false",
#         "no",
#         "n",
#         "off",
#     }:
#         return False

#     return default


# def parse_positive_float(
#     name: str,
#     default: float,
# ) -> float:
#     raw = os.getenv(
#         name,
#         str(default),
#     )

#     try:
#         value = float(raw)
#     except (
#         TypeError,
#         ValueError,
#     ):
#         return default

#     if value <= 0:
#         return default

#     return value


# def parse_non_negative_float(
#     name: str,
#     default: float,
# ) -> float:
#     raw = os.getenv(
#         name,
#         str(default),
#     )

#     try:
#         value = float(raw)
#     except (
#         TypeError,
#         ValueError,
#     ):
#         return default

#     if value < 0:
#         return default

#     return value


# def parse_positive_int(
#     name: str,
#     default: int,
# ) -> int:
#     raw = os.getenv(
#         name,
#         str(default),
#     )

#     try:
#         value = int(raw)
#     except (
#         TypeError,
#         ValueError,
#     ):
#         return default

#     if value <= 0:
#         return default

#     return value


# def parse_class_filter(
#     raw_value: str,
# ) -> list[int] | None:
#     """
#     Parse YOLO class filter.

#     Examples:

#         YOLO_CLASSES=0,2,3,5,7
#         YOLO_CLASSES=0
#         YOLO_CLASSES=all

#     None means all model classes.
#     """

#     value = str(raw_value).strip().lower()

#     if not value or value == "all":
#         return None

#     classes: list[int] = []

#     for item in value.split(","):
#         item = item.strip()

#         if not item:
#             continue

#         try:
#             class_id = int(item)
#         except ValueError:
#             print(
#                 "[DetectionAgent] "
#                 f"Ignoring invalid YOLO class: {item}"
#             )
#             continue

#         if class_id < 0:
#             continue

#         classes.append(class_id)

#     if not classes:
#         return None

#     return sorted(set(classes))


# def utc_timestamp() -> str:
#     """
#     Return canonical timezone-aware UTC timestamp.
#     """

#     return (
#         datetime.now(timezone.utc)
#         .isoformat()
#         .replace("+00:00", "Z")
#     )


# # ============================================================
# # DETECTION AGENT
# # ============================================================


# class DetectionAgent(BaseAgent):
#     """
#     Per-camera CCTV object-detection worker.

#     One DetectionAgent instance MUST belong to exactly one camera.
#     """

#     # COCO classes commonly useful for CCTV.
#     #
#     # 0 = person
#     # 2 = car
#     # 3 = motorcycle
#     # 5 = bus
#     # 7 = truck

#     DEFAULT_CLASSES = "0,2,3,5,7"

#     PERSON_CLASS_ID = 0

#     VEHICLE_CLASS_IDS = {
#         2,  # car
#         3,  # motorcycle
#         5,  # bus
#         7,  # truck
#     }

#     # ========================================================
#     # INIT
#     # ========================================================

#     def __init__(self):
#         super().__init__(
#             agent_id=os.getenv(
#                 "AGENT_ID",
#                 "person-detector-01",
#             ),
#             heartbeat_interval=parse_positive_int(
#                 "HEARTBEAT_INTERVAL",
#                 10,
#             ),
#         )

#         # ----------------------------------------------------
#         # Immutable camera identity
#         # ----------------------------------------------------

#         self.camera_id = os.getenv(
#             "CAMERA_ID",
#             "",
#         ).strip()

#         if not self.camera_id:
#             raise ValueError(
#                 "CAMERA_ID is required. "
#                 "Detection workers must never "
#                 "silently default to CAM01."
#             )

#         self._camera_identity = self.camera_id

#         # ----------------------------------------------------
#         # Camera metadata
#         # ----------------------------------------------------

#         self.camera_name = os.getenv(
#             "CAMERA_NAME",
#             self.camera_id,
#         ).strip()

#         self.camera_location = os.getenv(
#             "CAMERA_LOCATION",
#             "default",
#         ).strip()

#         # ----------------------------------------------------
#         # Camera source
#         # ----------------------------------------------------

#         self.camera_source = os.getenv(
#             "CAMERA_SOURCE",
#             "",
#         ).strip()

#         # Backward compatibility.
#         if not self.camera_source:
#             self.camera_source = os.getenv(
#                 "CAMERA_INDEX",
#                 "0",
#             ).strip()

#         if not self.camera_source:
#             raise ValueError(
#                 f"CAMERA_SOURCE is required "
#                 f"for {self.camera_id}."
#             )

#         self._camera_source_identity = self.camera_source

#         # ----------------------------------------------------
#         # YOLO configuration
#         # ----------------------------------------------------

#         self.model_path = os.getenv(
#             "YOLO_MODEL",
#             str(
#                 PROJECT_ROOT / "yolo11n.pt"
#             ),
#         ).strip()

#         self.confidence = parse_positive_float(
#             "YOLO_CONFIDENCE",
#             0.40,
#         )

#         self.iou = parse_positive_float(
#             "YOLO_IOU",
#             0.45,
#         )

#         self.class_filter = parse_class_filter(
#             os.getenv(
#                 "YOLO_CLASSES",
#                 self.DEFAULT_CLASSES,
#             )
#         )

#         # ----------------------------------------------------
#         # Frame processing
#         # ----------------------------------------------------

#         self.frame_interval = parse_non_negative_float(
#             "FRAME_INTERVAL",
#             0.20,
#         )

#         self.inference_interval = parse_non_negative_float(
#             "INFERENCE_INTERVAL",
#             0.0,
#         )

#         self.show_camera = parse_bool(
#             os.getenv(
#                 "SHOW_CAMERA",
#                 "true",
#             ),
#             default=True,
#         )

#         # ----------------------------------------------------
#         # Camera reconnect configuration
#         # ----------------------------------------------------

#         self.reconnect_initial_delay = parse_positive_float(
#             "CAMERA_RECONNECT_INITIAL_DELAY",
#             1.0,
#         )

#         self.reconnect_max_delay = parse_positive_float(
#             "CAMERA_RECONNECT_MAX_DELAY",
#             30.0,
#         )

#         self.read_failure_before_reconnect = max(
#             1,
#             parse_positive_int(
#                 "CAMERA_READ_FAILURE_THRESHOLD",
#                 3,
#             ),
#         )

#         # ----------------------------------------------------
#         # Event streams
#         # ----------------------------------------------------

#         self.detection_stream = os.getenv(
#             "DETECTION_OUTPUT_STREAM",
#             "events.detection",
#         ).strip()

#         self.vehicle_stream = os.getenv(
#             "VEHICLE_OUTPUT_STREAM",
#             "events.vehicle",
#         ).strip()

#         self.object_stream = os.getenv(
#             "OBJECT_OUTPUT_STREAM",
#             "events.objects",
#         ).strip()

#         # ----------------------------------------------------
#         # Runtime state
#         # ----------------------------------------------------

#         self.model: YOLO | None = None

#         self.cap: cv2.VideoCapture | None = None

#         self.frame_id = 0

#         self.last_inference_time = 0.0

#         self.last_frame_time = 0.0

#         self.read_failures = 0

#         self.reconnect_delay = (
#             self.reconnect_initial_delay
#         )

#         self.reconnect_in_progress = False

#         # ----------------------------------------------------
#         # Camera evidence directory
#         # ----------------------------------------------------

#         self.camera_evidence_dir = (
#             EVIDENCE_ROOT
#             / self._safe_camera_directory_name(
#                 self.camera_id
#             )
#         )

#         self.camera_evidence_dir.mkdir(
#             parents=True,
#             exist_ok=True,
#         )

#         self.latest_frame_path = (
#             self.camera_evidence_dir
#             / "latest.jpg"
#         )

#         # ----------------------------------------------------
#         # Rolling evidence configuration
#         # ----------------------------------------------------

#         self.evidence_segment_seconds = (
#             parse_positive_float(
#                 "EVIDENCE_SEGMENT_SECONDS",
#                 5.0,
#             )
#         )

#         self.evidence_retention_seconds = (
#             parse_positive_float(
#                 "EVIDENCE_RETENTION_SECONDS",
#                 60.0,
#             )
#         )

#         self.evidence_fps = parse_positive_float(
#             "EVIDENCE_FPS",
#             20.0,
#         )

#         # ----------------------------------------------------
#         # Rolling evidence buffer
#         #
#         # IMPORTANT:
#         #
#         # The buffer belongs to this camera worker.
#         #
#         # Detection/inference failure must never terminate
#         # the camera worker merely because evidence recording
#         # has a problem.
#         # ----------------------------------------------------

#         self.evidence_buffer: RollingEvidenceBuffer | None = None

#         self.evidence_buffer_enabled = True

#         self._initialize_evidence_buffer()

#         # ----------------------------------------------------
#         # Model class metadata
#         # ----------------------------------------------------

#         self.class_names: dict[int, str] = {}

#     # ========================================================
#     # CAMERA DIRECTORY
#     # ========================================================

#     @staticmethod
#     def _safe_camera_directory_name(
#         camera_id: str,
#     ) -> str:
#         allowed = (
#             "abcdefghijklmnopqrstuvwxyz"
#             "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
#             "0123456789"
#             "-_."
#         )

#         result = "".join(
#             character
#             if character in allowed
#             else "_"
#             for character in camera_id
#         )

#         return (
#             result[:120]
#             or "camera"
#         )

#     # ========================================================
#     # EVIDENCE BUFFER INITIALIZATION
#     # ========================================================

#     def _initialize_evidence_buffer(self) -> None:
#         """
#         Initialize the per-camera rolling evidence buffer.

#         A buffer initialization failure is isolated from the
#         detection worker. Detection may continue without
#         evidence rather than allowing one subsystem failure
#         to terminate the camera worker.
#         """

#         try:
#             self.evidence_buffer = RollingEvidenceBuffer(
#                 camera_id=self.camera_id,
#                 output_dir=self.camera_evidence_dir,
#                 segment_seconds=self.evidence_segment_seconds,
#                 retention_seconds=self.evidence_retention_seconds,
#                 fps=self.evidence_fps,
#             )

#             self.evidence_buffer_enabled = True

#             print(
#                 f"[{self.agent_id}] "
#                 "Rolling evidence buffer initialized | "
#                 f"camera_id={self.camera_id} | "
#                 f"directory={self.evidence_buffer.buffer_dir} | "
#                 f"segment={self.evidence_buffer.segment_seconds:.1f}s | "
#                 f"retention={self.evidence_buffer.retention_seconds:.1f}s | "
#                 f"fps={self.evidence_buffer.fps:.1f}"
#             )

#         except Exception as error:
#             self.evidence_buffer = None
#             self.evidence_buffer_enabled = False

#             print(
#                 f"[{self.agent_id}] "
#                 "Rolling evidence buffer initialization failed "
#                 "but detection remains active | "
#                 f"camera_id={self.camera_id} | "
#                 f"type={type(error).__name__} | "
#                 f"error={error}"
#             )

#     # ========================================================
#     # IDENTITY VALIDATION
#     # ========================================================

#     def _validate_camera_identity(
#         self,
#     ) -> None:
#         if self.camera_id != self._camera_identity:
#             raise RuntimeError(
#                 "CAMERA ID MUTATION DETECTED: "
#                 f"original={self._camera_identity}, "
#                 f"current={self.camera_id}"
#             )

#         if (
#             self.camera_source
#             != self._camera_source_identity
#         ):
#             raise RuntimeError(
#                 "CAMERA SOURCE MUTATION DETECTED: "
#                 f"original={self._camera_source_identity}, "
#                 f"current={self.camera_source}"
#             )

#     # ========================================================
#     # START
#     # ========================================================

#     async def on_start(
#         self,
#     ):
#         self._validate_camera_identity()

#         print(
#             f"[{self.agent_id}] "
#             "Starting per-camera detection worker."
#         )

#         print(
#             f"[{self.agent_id}] "
#             f"Camera ID: {self.camera_id}"
#         )

#         print(
#             f"[{self.agent_id}] "
#             f"Camera name: {self.camera_name}"
#         )

#         print(
#             f"[{self.agent_id}] "
#             f"Camera location: {self.camera_location}"
#         )

#         print(
#             f"[{self.agent_id}] "
#             f"Camera source: {self.camera_source}"
#         )

#         print(
#             f"[{self.agent_id}] "
#             f"Evidence directory: "
#             f"{self.camera_evidence_dir}"
#         )

#         if self.evidence_buffer is not None:
#             print(
#                 f"[{self.agent_id}] "
#                 "Evidence buffer: "
#                 f"{self.evidence_buffer.buffer_dir}"
#             )

#             print(
#                 f"[{self.agent_id}] "
#                 "Evidence segment: "
#                 f"{self.evidence_buffer.segment_seconds:.1f}s"
#             )

#             print(
#                 f"[{self.agent_id}] "
#                 "Evidence retention: "
#                 f"{self.evidence_buffer.retention_seconds:.1f}s"
#             )

#             print(
#                 f"[{self.agent_id}] "
#                 "Evidence FPS: "
#                 f"{self.evidence_buffer.fps:.1f}"
#             )

#         else:
#             print(
#                 f"[{self.agent_id}] "
#                 "Evidence buffer is DISABLED."
#             )

#         print(
#             f"[{self.agent_id}] "
#             f"YOLO model: {self.model_path}"
#         )

#         if self.class_filter is None:
#             print(
#                 f"[{self.agent_id}] "
#                 "YOLO classes: ALL"
#             )
#         else:
#             print(
#                 f"[{self.agent_id}] "
#                 f"YOLO classes: {self.class_filter}"
#             )

#         # ----------------------------------------------------
#         # Lazy model loading
#         # ----------------------------------------------------

#         try:
#             self.model = YOLO(
#                 self.model_path
#             )

#             self._load_class_names()

#             print(
#                 f"[{self.agent_id}] "
#                 "YOLO model loaded successfully."
#             )

#         except Exception as error:
#             print(
#                 f"[{self.agent_id}] "
#                 "YOLO model loading failed: "
#                 f"{type(error).__name__}: "
#                 f"{error}"
#             )
#             raise

#         # ----------------------------------------------------
#         # Camera is best effort
#         # ----------------------------------------------------

#         opened = await self._open_camera()

#         if opened:
#             print(
#                 f"[{self.agent_id}] "
#                 "Camera opened successfully: "
#                 f"camera_id={self.camera_id}, "
#                 f"source={self.camera_source}"
#             )
#         else:
#             print(
#                 f"[{self.agent_id}] "
#                 "Camera unavailable: "
#                 f"camera_id={self.camera_id}, "
#                 f"source={self.camera_source}. "
#                 "Worker remains alive and will retry."
#             )

#     # ========================================================
#     # LOAD CLASS NAMES
#     # ========================================================

#     def _load_class_names(
#         self,
#     ) -> None:
#         if self.model is None:
#             return

#         names = getattr(
#             self.model,
#             "names",
#             {},
#         )

#         if isinstance(
#             names,
#             dict,
#         ):
#             self.class_names = {
#                 int(key): str(value)
#                 for key, value in names.items()
#             }

#         elif isinstance(
#             names,
#             list,
#         ):
#             self.class_names = {
#                 index: str(value)
#                 for index, value in enumerate(names)
#             }

#         else:
#             self.class_names = {}

#     # ========================================================
#     # CAMERA OPEN
#     # ========================================================

#     async def _open_camera(
#         self,
#     ) -> bool:
#         self._validate_camera_identity()

#         loop = asyncio.get_running_loop()

#         # ----------------------------------------------------
#         # Release previous capture
#         # ----------------------------------------------------

#         old_cap = self.cap

#         if old_cap is not None:
#             try:
#                 await loop.run_in_executor(
#                     None,
#                     old_cap.release,
#                 )
#             except Exception as error:
#                 print(
#                     f"[{self.agent_id}] "
#                     "Previous camera release "
#                     f"error isolated: {error}"
#                 )

#             self.cap = None

#         # ----------------------------------------------------
#         # Normalize source
#         # ----------------------------------------------------

#         source = self._normalize_camera_source(
#             self.camera_source
#         )

#         print(
#             f"[{self.agent_id}] "
#             "Opening camera: "
#             f"camera_id={self.camera_id}, "
#             f"source={self.camera_source}"
#         )

#         # ----------------------------------------------------
#         # Open capture
#         # ----------------------------------------------------

#         cap: cv2.VideoCapture | None = None

#         try:
#             cap = await loop.run_in_executor(
#                 None,
#                 cv2.VideoCapture,
#                 source,
#             )

#             if cap is None:
#                 print(
#                     f"[{self.agent_id}] "
#                     "cv2.VideoCapture returned None."
#                 )
#                 return False

#             is_opened = await loop.run_in_executor(
#                 None,
#                 cap.isOpened,
#             )

#             if not is_opened:
#                 print(
#                     f"[{self.agent_id}] "
#                     "Camera failed to open: "
#                     f"camera_id={self.camera_id}, "
#                     f"source={self.camera_source}"
#                 )

#                 try:
#                     await loop.run_in_executor(
#                         None,
#                         cap.release,
#                     )
#                 except Exception:
#                     pass

#                 return False

#             # ------------------------------------------------
#             # Low-latency buffer
#             # ------------------------------------------------

#             try:
#                 await loop.run_in_executor(
#                     None,
#                     lambda: cap.set(
#                         cv2.CAP_PROP_BUFFERSIZE,
#                         1,
#                     ),
#                 )
#             except Exception as error:
#                 print(
#                     f"[{self.agent_id}] "
#                     "Camera buffer configuration "
#                     f"failed but isolated: {error}"
#                 )

#             # ------------------------------------------------
#             # Assign capture only after successful open
#             # ------------------------------------------------

#             self.cap = cap

#             self.read_failures = 0

#             self.reconnect_delay = (
#                 self.reconnect_initial_delay
#             )

#             return True

#         except Exception as error:
#             print(
#                 f"[{self.agent_id}] "
#                 "Camera open error isolated: "
#                 f"{type(error).__name__}: "
#                 f"{error}"
#             )

#             if cap is not None:
#                 try:
#                     await loop.run_in_executor(
#                         None,
#                         cap.release,
#                     )
#                 except Exception:
#                     pass

#             return False

#     # ========================================================
#     # CAMERA SOURCE NORMALIZATION
#     # ========================================================

#     @staticmethod
#     def _normalize_camera_source(
#         source: str,
#     ) -> str | int:
#         value = str(source).strip()

#         if (
#             value.isdigit()
#             and not value.startswith("0x")
#         ):
#             try:
#                 return int(value)
#             except ValueError:
#                 pass

#         return value

#     # ========================================================
#     # CAMERA RECONNECT
#     # ========================================================

#     async def _reconnect_camera(
#         self,
#     ) -> None:
#         self._validate_camera_identity()

#         if self.reconnect_in_progress:
#             return

#         self.reconnect_in_progress = True

#         try:
#             print(
#                 f"[{self.agent_id}] "
#                 "Camera reconnect scheduled: "
#                 f"camera_id={self.camera_id}, "
#                 f"source={self.camera_source}, "
#                 f"delay={self.reconnect_delay:.1f}s"
#             )

#             await asyncio.sleep(
#                 self.reconnect_delay
#             )

#             if not self.running:
#                 return

#             self._validate_camera_identity()

#             opened = await self._open_camera()

#             if opened:
#                 print(
#                     f"[{self.agent_id}] "
#                     "Camera reconnected successfully: "
#                     f"camera_id={self.camera_id}, "
#                     f"source={self.camera_source}"
#                 )

#                 self.reconnect_delay = (
#                     self.reconnect_initial_delay
#                 )

#             else:
#                 self.reconnect_delay = min(
#                     self.reconnect_delay * 2,
#                     self.reconnect_max_delay,
#                 )

#                 print(
#                     f"[{self.agent_id}] "
#                     "Camera reconnect failed: "
#                     f"camera_id={self.camera_id}, "
#                     f"source={self.camera_source}, "
#                     f"next_delay="
#                     f"{self.reconnect_delay:.1f}s"
#                 )

#         finally:
#             self.reconnect_in_progress = False

#     # ========================================================
#     # STOP
#     # ========================================================

#     async def on_stop(
#         self,
#     ):
#         loop = asyncio.get_running_loop()

#         # ----------------------------------------------------
#         # Close evidence buffer first
#         #
#         # This finalizes the active segment so the last
#         # captured evidence becomes visible in manifest.json.
#         # ----------------------------------------------------

#         buffer_instance = self.evidence_buffer

#         self.evidence_buffer = None

#         if buffer_instance is not None:
#             try:
#                 buffer_instance.close()

#                 print(
#                     f"[{self.agent_id}] "
#                     "Evidence buffer closed successfully | "
#                     f"camera_id={self.camera_id}"
#                 )

#             except Exception as error:
#                 print(
#                     f"[{self.agent_id}] "
#                     "Evidence buffer close failed "
#                     f"but isolated | "
#                     f"camera_id={self.camera_id} | "
#                     f"error={error}"
#                 )

#         # ----------------------------------------------------
#         # Release camera
#         # ----------------------------------------------------

#         cap = self.cap

#         self.cap = None

#         if cap is not None:
#             try:
#                 await loop.run_in_executor(
#                     None,
#                     cap.release,
#                 )
#             except Exception as error:
#                 print(
#                     f"[{self.agent_id}] "
#                     "Camera release error isolated: "
#                     f"{error}"
#                 )

#         # ----------------------------------------------------
#         # Close OpenCV window
#         # ----------------------------------------------------

#         if self.show_camera:
#             try:
#                 cv2.destroyWindow(
#                     f"CCTV AI - {self.camera_id}"
#                 )
#             except Exception:
#                 pass

#             try:
#                 cv2.destroyAllWindows()
#             except Exception:
#                 pass

#         print(
#             f"[{self.agent_id}] "
#             "Detection worker stopped: "
#             f"camera_id={self.camera_id}"
#         )

#     # ========================================================
#     # INFERENCE
#     # ========================================================

#     def _run_yolo(
#         self,
#         frame,
#     ):
#         if self.model is None:
#             raise RuntimeError(
#                 "YOLO model is not initialized."
#             )

#         return self.model(
#             frame,
#             conf=self.confidence,
#             iou=self.iou,
#             classes=self.class_filter,
#             verbose=False,
#         )

#     # ========================================================
#     # EXTRACT DETECTIONS
#     # ========================================================

#     def _extract_detections(
#         self,
#         results,
#     ) -> list[dict[str, Any]]:
#         detections: list[dict[str, Any]] = []

#         for result in results:
#             if result.boxes is None:
#                 continue

#             boxes = result.boxes

#             for index in range(len(boxes)):
#                 box = boxes[index]

#                 xyxy = (
#                     box.xyxy[0]
#                     .cpu()
#                     .tolist()
#                 )

#                 confidence = float(
#                     box.conf[0]
#                     .cpu()
#                     .item()
#                 )

#                 class_id = int(
#                     box.cls[0]
#                     .cpu()
#                     .item()
#                 )

#                 class_name = self.class_names.get(
#                     class_id,
#                     f"class_{class_id}",
#                 )

#                 detection_id = (
#                     f"det-"
#                     f"{self.camera_id}-"
#                     f"{self.frame_id}-"
#                     f"{uuid.uuid4().hex[:8]}"
#                 )

#                 x1 = float(xyxy[0])
#                 y1 = float(xyxy[1])
#                 x2 = float(xyxy[2])
#                 y2 = float(xyxy[3])

#                 detections.append(
#                     {
#                         "detection_id": detection_id,
#                         "class_id": class_id,
#                         "class_name": class_name,
#                         "confidence": confidence,
#                         "bbox": [
#                             x1,
#                             y1,
#                             x2,
#                             y2,
#                         ],
#                     }
#                 )

#         return detections

#     # ========================================================
#     # SPLIT DETECTIONS
#     # ========================================================

#     @staticmethod
#     def _split_detections(
#         detections: list[dict[str, Any]],
#     ):
#         people: list[dict[str, Any]] = []

#         vehicles: list[dict[str, Any]] = []

#         for detection in detections:
#             class_id = int(
#                 detection["class_id"]
#             )

#             if class_id == DetectionAgent.PERSON_CLASS_ID:
#                 people.append(detection)

#             if class_id in DetectionAgent.VEHICLE_CLASS_IDS:
#                 vehicles.append(detection)

#         return people, vehicles

#     # ========================================================
#     # EVENT PUBLISHING
#     # ========================================================

#     async def _publish_event(
#         self,
#         stream: str,
#         event_type: str,
#         data: dict[str, Any],
#         trace_id: str | None = None,
#         correlation_id: str | None = None,
#         incident_id: str | None = None,
#     ):
#         self._validate_camera_identity()

#         event = create_event(
#             event_type=event_type,
#             agent_id=self.agent_id,
#             instance_id=self.instance_id,
#             hostname=self.hostname,
#             camera_id=self.camera_id,
#             mode="live",
#             trace_id=trace_id,
#             correlation_id=correlation_id,
#             incident_id=incident_id,
#             data=data,
#         )

#         return await self.publish(
#             stream,
#             event.to_dict(),
#         )

#     # ========================================================
#     # PERSON EVENT
#     # ========================================================

#     async def _publish_person_event(
#         self,
#         people: list[dict[str, Any]],
#         frame_timestamp: str,
#     ):
#         data = {
#             "frame_id": str(
#                 self.frame_id
#             ),
#             "frame_timestamp": frame_timestamp,
#             "detection_count": len(people),
#             "count": len(people),
#             "detections": people,
#             "model": self.model_path,
#             "confidence_threshold": self.confidence,
#         }

#         return await self._publish_event(
#             stream=self.detection_stream,
#             event_type="person.detected",
#             data=data,
#         )

#     # ========================================================
#     # VEHICLE EVENT
#     # ========================================================

#     async def _publish_vehicle_event(
#         self,
#         vehicles: list[dict[str, Any]],
#         frame_timestamp: str,
#     ):
#         data = {
#             "frame_id": str(
#                 self.frame_id
#             ),
#             "frame_timestamp": frame_timestamp,
#             "vehicle_count": len(vehicles),
#             "count": len(vehicles),
#             "vehicles": vehicles,
#             "model": self.model_path,
#             "confidence_threshold": self.confidence,
#         }

#         return await self._publish_event(
#             stream=self.vehicle_stream,
#             event_type="vehicle.detected",
#             data=data,
#         )

#     # ========================================================
#     # GENERIC OBJECT EVENT
#     # ========================================================

#     async def _publish_object_event(
#         self,
#         detections: list[dict[str, Any]],
#         frame_timestamp: str,
#     ):
#         data = {
#             "frame_id": str(
#                 self.frame_id
#             ),
#             "frame_timestamp": frame_timestamp,
#             "object_count": len(detections),
#             "count": len(detections),
#             "detections": detections,
#             "model": self.model_path,
#             "confidence_threshold": self.confidence,
#         }

#         return await self._publish_event(
#             stream=self.object_stream,
#             event_type="object.detected",
#             data=data,
#         )

#     # ========================================================
#     # ANNOTATION
#     # ========================================================

#     def _annotate_frame(
#         self,
#         frame,
#         detections: list[dict[str, Any]],
#     ):
#         annotated_frame = frame.copy()

#         for detection in detections:
#             bbox = detection["bbox"]

#             x1 = int(bbox[0])
#             y1 = int(bbox[1])
#             x2 = int(bbox[2])
#             y2 = int(bbox[3])

#             confidence = float(
#                 detection["confidence"]
#             )

#             class_id = int(
#                 detection["class_id"]
#             )

#             class_name = str(
#                 detection["class_name"]
#             )

#             if class_id == self.PERSON_CLASS_ID:
#                 label = (
#                     f"Person "
#                     f"{confidence:.2f}"
#                 )
#             else:
#                 label = (
#                     f"{class_name} "
#                     f"{confidence:.2f}"
#                 )

#             cv2.rectangle(
#                 annotated_frame,
#                 (x1, y1),
#                 (x2, y2),
#                 (0, 255, 0),
#                 2,
#             )

#             cv2.putText(
#                 annotated_frame,
#                 label,
#                 (
#                     x1,
#                     max(
#                         y1 - 10,
#                         20,
#                     ),
#                 ),
#                 cv2.FONT_HERSHEY_SIMPLEX,
#                 0.5,
#                 (0, 255, 0),
#                 2,
#             )

#         cv2.putText(
#             annotated_frame,
#             (
#                 f"Camera: "
#                 f"{self.camera_id} | "
#                 f"Frame: "
#                 f"{self.frame_id} | "
#                 f"Objects: "
#                 f"{len(detections)}"
#             ),
#             (10, 25),
#             cv2.FONT_HERSHEY_SIMPLEX,
#             0.6,
#             (255, 255, 255),
#             2,
#         )

#         return annotated_frame

#     # ========================================================
#     # ATOMIC IMAGE WRITE
#     # ========================================================

#     def _write_latest_frame(
#         self,
#         frame,
#     ):
#         target = self.latest_frame_path

#         temp_path: Path | None = None

#         try:
#             target.parent.mkdir(
#                 parents=True,
#                 exist_ok=True,
#             )

#             temp_path = target.with_name(
#                 f".{target.stem}."
#                 f"{uuid.uuid4().hex}"
#                 f"{target.suffix}"
#             )

#             success = cv2.imwrite(
#                 str(temp_path),
#                 frame,
#             )

#             if not success:
#                 raise RuntimeError(
#                     "cv2.imwrite returned False"
#                 )

#             os.replace(
#                 temp_path,
#                 target,
#             )

#         except Exception as error:
#             print(
#                 f"[{self.agent_id}] "
#                 "Latest-frame write failed: "
#                 f"camera_id={self.camera_id}, "
#                 f"target={target}, "
#                 f"error={error}"
#             )

#             if temp_path is not None:
#                 try:
#                     if temp_path.exists():
#                         temp_path.unlink()
#                 except Exception:
#                     pass

#     # ========================================================
#     # DISPLAY
#     # ========================================================

#     def _display_frame(
#         self,
#         frame,
#     ) -> bool:
#         if not self.show_camera:
#             return True

#         try:
#             window_name = (
#                 f"CCTV AI - "
#                 f"{self.camera_id}"
#             )

#             cv2.imshow(
#                 window_name,
#                 frame,
#             )

#             key = (
#                 cv2.waitKey(1)
#                 & 0xFF
#             )

#             if key == ord("q"):
#                 print(
#                     f"[{self.agent_id}] "
#                     "Shutdown requested by operator: "
#                     f"camera_id={self.camera_id}"
#                 )

#                 return False

#         except Exception as error:
#             print(
#                 f"[{self.agent_id}] "
#                 "Display error isolated: "
#                 f"camera_id={self.camera_id}, "
#                 f"error={error}"
#             )

#         return True

#     # ========================================================
#     # ROLLING BUFFER WRITE
#     # ========================================================

#     def _write_evidence_frame(
#         self,
#         frame,
#         frame_timestamp: str,
#         frame_epoch: float,
#     ) -> bool:
#         """
#         Write one successfully captured frame into the
#         per-camera rolling evidence buffer.

#         This function is intentionally isolated from detection.

#         Returns:
#             True  -> frame accepted by evidence buffer.
#             False -> evidence buffer unavailable/rejected.

#         IMPORTANT:
#             A False result NEVER means that detection should stop.
#         """

#         buffer_instance = self.evidence_buffer

#         if (
#             not self.evidence_buffer_enabled
#             or buffer_instance is None
#         ):
#             return False

#         try:
#             accepted = buffer_instance.write(
#                 frame,
#                 timestamp=frame_timestamp,
#                 epoch=frame_epoch,
#             )

#             if not accepted:
#                 print(
#                     f"[{self.agent_id}] "
#                     "Evidence buffer rejected frame | "
#                     f"camera_id={self.camera_id} | "
#                     f"frame={self.frame_id}"
#                 )

#             return bool(accepted)

#         except Exception as error:
#             print(
#                 f"[{self.agent_id}] "
#                 "Evidence buffer write failed but "
#                 "detection remains active | "
#                 f"camera_id={self.camera_id} | "
#                 f"frame={self.frame_id} | "
#                 f"type={type(error).__name__} | "
#                 f"error={error}"
#             )

#             return False

#     # ========================================================
#     # BUFFER STATUS LOGGING
#     # ========================================================

#     def _log_buffer_status(
#         self,
#     ) -> None:
#         """
#         Lightweight diagnostic helper.

#         This is intentionally not called for every frame.
#         """

#         buffer_instance = self.evidence_buffer

#         if buffer_instance is None:
#             return

#         try:
#             status = buffer_instance.status()

#             print(
#                 f"[{self.agent_id}] "
#                 "Evidence buffer status | "
#                 f"camera_id={self.camera_id} | "
#                 f"segments={status.get('segment_count')} | "
#                 f"frames={status.get('frame_count')} | "
#                 f"active={status.get('active')} | "
#                 f"directory={status.get('buffer_dir')}"
#             )

#         except Exception as error:
#             print(
#                 f"[{self.agent_id}] "
#                 "Evidence buffer status check "
#                 f"failed but isolated | "
#                 f"camera_id={self.camera_id} | "
#                 f"error={error}"
#             )

#     # ========================================================
#     # MAIN LOOP
#     # ========================================================

#     async def run(
#         self,
#     ):
#         if self.model is None:
#             raise RuntimeError(
#                 "YOLO model is not initialized."
#             )

#         self._validate_camera_identity()

#         print(
#             f"[{self.agent_id}] "
#             "Detection loop started: "
#             f"camera_id={self.camera_id}, "
#             f"source={self.camera_source}"
#         )

#         loop = asyncio.get_running_loop()

#         # Diagnostic timer.
#         last_buffer_status_log = 0.0

#         while self.running:
#             try:
#                 # ------------------------------------------------
#                 # Identity protection
#                 # ------------------------------------------------

#                 self._validate_camera_identity()

#                 # ------------------------------------------------
#                 # Camera unavailable
#                 # ------------------------------------------------

#                 if self.cap is None:
#                     await self._reconnect_camera()
#                     continue

#                 # ------------------------------------------------
#                 # Read frame
#                 # ------------------------------------------------

#                 cap = self.cap

#                 ret, frame = await loop.run_in_executor(
#                     None,
#                     cap.read,
#                 )

#                 # If another operation replaced the capture
#                 # while read was executing, ignore the result.
#                 if cap is not self.cap:
#                     continue

#                 # ------------------------------------------------
#                 # Read failure
#                 # ------------------------------------------------

#                 if (
#                     not ret
#                     or frame is None
#                 ):
#                     self.read_failures += 1

#                     print(
#                         f"[{self.agent_id}] "
#                         "Camera frame read failed "
#                         f"({self.read_failures}/"
#                         f"{self.read_failure_before_reconnect}) | "
#                         f"camera_id={self.camera_id}"
#                     )

#                     if (
#                         self.read_failures
#                         >= self.read_failure_before_reconnect
#                     ):
#                         failed_cap = self.cap

#                         self.cap = None

#                         if failed_cap is not None:
#                             try:
#                                 await loop.run_in_executor(
#                                     None,
#                                     failed_cap.release,
#                                 )
#                             except Exception as error:
#                                 print(
#                                     f"[{self.agent_id}] "
#                                     "Failed camera release "
#                                     f"isolated: {error}"
#                                 )

#                         # Close the current evidence segment
#                         # cleanly. The rolling buffer itself
#                         # remains usable after reconnect.
#                         buffer_instance = self.evidence_buffer

#                         if buffer_instance is not None:
#                             try:
#                                 buffer_instance.rotate()
#                             except Exception as error:
#                                 print(
#                                     f"[{self.agent_id}] "
#                                     "Evidence buffer rotation "
#                                     f"failed but isolated | "
#                                     f"camera_id={self.camera_id} | "
#                                     f"error={error}"
#                                 )

#                         self.read_failures = 0

#                     await asyncio.sleep(
#                         min(
#                             self.reconnect_delay,
#                             2.0,
#                         )
#                     )

#                     continue

#                 # ------------------------------------------------
#                 # Successful frame
#                 # ------------------------------------------------

#                 self.read_failures = 0

#                 self.last_frame_time = (
#                     time.monotonic()
#                 )

#                 self.frame_id += 1

#                 # IMPORTANT:
#                 #
#                 # Capture timestamp immediately after successful
#                 # frame acquisition.
#                 #
#                 # This represents the camera frame time, not the
#                 # later YOLO inference completion time.

#                 frame_timestamp = utc_timestamp()

#                 frame_epoch = time.time()

#                 # ------------------------------------------------
#                 # ROLLING EVIDENCE BUFFER
#                 # ------------------------------------------------
#                 #
#                 # THIS MUST REMAIN BEFORE INFERENCE THROTTLING.
#                 #
#                 # The camera evidence stream must continue recording
#                 # even when YOLO inference is intentionally throttled.
#                 # ------------------------------------------------

#                 self._write_evidence_frame(
#                     frame=frame,
#                     frame_timestamp=frame_timestamp,
#                     frame_epoch=frame_epoch,
#                 )

#                 # ------------------------------------------------
#                 # Periodic buffer diagnostics
#                 # ------------------------------------------------

#                 now_monotonic = time.monotonic()

#                 if (
#                     now_monotonic
#                     - last_buffer_status_log
#                     >= 10.0
#                 ):
#                     self._log_buffer_status()

#                     last_buffer_status_log = (
#                         now_monotonic
#                     )

#                 # ------------------------------------------------
#                 # Optional inference throttling
#                 # ------------------------------------------------

#                 if self.inference_interval > 0:
#                     now = time.monotonic()

#                     elapsed = (
#                         now
#                         - self.last_inference_time
#                     )

#                     if (
#                         elapsed
#                         < self.inference_interval
#                     ):
#                         if not self._display_frame(
#                             frame
#                         ):
#                             break

#                         if self.frame_interval > 0:
#                             await asyncio.sleep(
#                                 self.frame_interval
#                             )

#                         continue

#                 self.last_inference_time = (
#                     time.monotonic()
#                 )

#                 # ------------------------------------------------
#                 # YOLO inference
#                 # ------------------------------------------------

#                 results = await loop.run_in_executor(
#                     None,
#                     self._run_yolo,
#                     frame,
#                 )

#                 # ------------------------------------------------
#                 # Extract detections
#                 # ------------------------------------------------

#                 detections = (
#                     self._extract_detections(
#                         results
#                     )
#                 )

#                 people, vehicles = (
#                     self._split_detections(
#                         detections
#                     )
#                 )

#                 # ------------------------------------------------
#                 # Annotation
#                 # ------------------------------------------------

#                 annotated_frame = (
#                     self._annotate_frame(
#                         frame,
#                         detections,
#                     )
#                 )

#                 # ------------------------------------------------
#                 # Publish person event
#                 # ------------------------------------------------

#                 person_redis_id = (
#                     await self._publish_person_event(
#                         people,
#                         frame_timestamp,
#                     )
#                 )

#                 # ------------------------------------------------
#                 # Publish vehicle event
#                 # ------------------------------------------------

#                 vehicle_redis_id = (
#                     await self._publish_vehicle_event(
#                         vehicles,
#                         frame_timestamp,
#                     )
#                 )

#                 # ------------------------------------------------
#                 # Publish generic object event
#                 # ------------------------------------------------

#                 object_redis_id = (
#                     await self._publish_object_event(
#                         detections,
#                         frame_timestamp,
#                     )
#                 )

#                 # ------------------------------------------------
#                 # Camera-specific latest frame
#                 # ------------------------------------------------

#                 self._write_latest_frame(
#                     annotated_frame
#                 )

#                 # ------------------------------------------------
#                 # Logging
#                 # ------------------------------------------------

#                 print(
#                     "DETECTED | "
#                     f"Agent={self.agent_id} | "
#                     f"Camera={self.camera_id} | "
#                     f"Frame={self.frame_id} | "
#                     f"Persons={len(people)} | "
#                     f"Vehicles={len(vehicles)} | "
#                     f"Objects={len(detections)} | "
#                     f"PersonRedis={person_redis_id} | "
#                     f"VehicleRedis={vehicle_redis_id} | "
#                     f"ObjectRedis={object_redis_id}"
#                 )

#                 # ------------------------------------------------
#                 # Display
#                 # ------------------------------------------------

#                 if not self._display_frame(
#                     annotated_frame
#                 ):
#                     break

#                 # ------------------------------------------------
#                 # Frame pacing
#                 # ------------------------------------------------

#                 if self.frame_interval > 0:
#                     await asyncio.sleep(
#                         self.frame_interval
#                     )

#             # ====================================================
#             # SHUTDOWN
#             # ====================================================

#             except asyncio.CancelledError:
#                 raise

#             # ====================================================
#             # INDIVIDUAL ITERATION FAILURE
#             # ====================================================

#             except Exception as error:
#                 """
#                 CRITICAL FAULT-ISOLATION RULE:

#                 A single frame, inference, Redis publish,
#                 annotation, evidence write, or other iteration
#                 failure must NOT terminate this camera worker.
#                 """

#                 print(
#                     f"[{self.agent_id}] "
#                     "Detection iteration error isolated | "
#                     f"camera_id={self.camera_id} | "
#                     f"type={type(error).__name__} | "
#                     f"error={error}"
#                 )

#                 await asyncio.sleep(
#                     1.0
#                 )

#         print(
#             f"[{self.agent_id}] "
#             "Detection loop stopped | "
#             f"camera_id={self.camera_id}"
#         )


# # ============================================================
# # MAIN
# # ============================================================


# async def main():
#     agent = DetectionAgent()

#     await agent.run_forever()


# if __name__ == "__main__":
#     asyncio.run(
#         main()
#     )













"""
Per-camera CCTV Detection Agent.

Responsibilities
----------------

- Capture frames from exactly one configured camera.
- Maintain a camera-specific latest.jpg.
- Maintain a bounded rolling evidence buffer.
- Run YOLO object detection on the latest available frame.
- Publish structured detection events.

This worker does NOT:

- perform tracking
- perform cross-camera ReID
- perform behavior reasoning
- generate incidents
- generate final proof videos
- perform LLM reasoning

All downstream intelligence remains isolated.

Important architecture rule
----------------------------

Camera capture and rolling evidence recording are independent
from YOLO inference.

The camera capture loop MUST NOT wait for:

- YOLO inference
- Redis publishing
- annotation
- display
- downstream processing

This prevents inference latency from creating gaps in the
rolling evidence buffer.
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
from ultralytics import YOLO

from agents.detection.evidence_buffer import RollingEvidenceBuffer
from shared.agent.base_agent import BaseAgent
from shared.schemas.event_schema import create_event


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

EVIDENCE_ROOT = PROJECT_ROOT / "data" / "evidence"
EVIDENCE_ROOT.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# HELPERS
# ============================================================


def parse_bool(
    value: str,
    default: bool = False,
) -> bool:
    value = str(value).strip().lower()

    if value in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }:
        return True

    if value in {
        "0",
        "false",
        "no",
        "n",
        "off",
    }:
        return False

    return default


def parse_positive_float(
    name: str,
    default: float,
) -> float:
    raw = os.getenv(
        name,
        str(default),
    )

    try:
        value = float(raw)
    except (
        TypeError,
        ValueError,
    ):
        return default

    if value <= 0:
        return default

    return value


def parse_non_negative_float(
    name: str,
    default: float,
) -> float:
    raw = os.getenv(
        name,
        str(default),
    )

    try:
        value = float(raw)
    except (
        TypeError,
        ValueError,
    ):
        return default

    if value < 0:
        return default

    return value


def parse_positive_int(
    name: str,
    default: int,
) -> int:
    raw = os.getenv(
        name,
        str(default),
    )

    try:
        value = int(raw)
    except (
        TypeError,
        ValueError,
    ):
        return default

    if value <= 0:
        return default

    return value


def parse_class_filter(
    raw_value: str,
) -> list[int] | None:
    """
    Parse YOLO class filter.

    Examples:
        YOLO_CLASSES=0,2,3,5,7
        YOLO_CLASSES=0
        YOLO_CLASSES=all

    None means all model classes.
    """

    value = str(raw_value).strip().lower()

    if not value or value == "all":
        return None

    classes: list[int] = []

    for item in value.split(","):
        item = item.strip()

        if not item:
            continue

        try:
            class_id = int(item)
        except ValueError:
            print(
                "[DetectionAgent] "
                f"Ignoring invalid YOLO class: {item}"
            )
            continue

        if class_id < 0:
            continue

        classes.append(class_id)

    if not classes:
        return None

    return sorted(set(classes))


def utc_timestamp() -> str:
    """
    Return canonical timezone-aware UTC timestamp.
    """

    return (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


# ============================================================
# DETECTION AGENT
# ============================================================


class DetectionAgent(BaseAgent):
    """
    Per-camera CCTV object-detection worker.

    One DetectionAgent instance MUST belong to exactly one camera.

    Capture/evidence recording is separated from YOLO inference.
    """

    # COCO classes commonly useful for CCTV.
    #
    # 0 = person
    # 2 = car
    # 3 = motorcycle
    # 5 = bus
    # 7 = truck

    DEFAULT_CLASSES = "0,2,3,5,7"

    PERSON_CLASS_ID = 0

    VEHICLE_CLASS_IDS = {
        2,  # car
        3,  # motorcycle
        5,  # bus
        7,  # truck
    }

    # ========================================================
    # INIT
    # ========================================================

    def __init__(self):
        super().__init__(
            agent_id=os.getenv(
                "AGENT_ID",
                "person-detector-01",
            ),
            heartbeat_interval=parse_positive_int(
                "HEARTBEAT_INTERVAL",
                10,
            ),
        )

        # ----------------------------------------------------
        # Immutable camera identity
        # ----------------------------------------------------

        self.camera_id = os.getenv(
            "CAMERA_ID",
            "",
        ).strip()

        if not self.camera_id:
            raise ValueError(
                "CAMERA_ID is required. "
                "Detection workers must never "
                "silently default to CAM01."
            )

        self._camera_identity = self.camera_id

        # ----------------------------------------------------
        # Camera metadata
        # ----------------------------------------------------

        self.camera_name = os.getenv(
            "CAMERA_NAME",
            self.camera_id,
        ).strip()

        self.camera_location = os.getenv(
            "CAMERA_LOCATION",
            "default",
        ).strip()

        # ----------------------------------------------------
        # Camera source
        # ----------------------------------------------------

        self.camera_source = os.getenv(
            "CAMERA_SOURCE",
            "",
        ).strip()

        # Backward compatibility.
        if not self.camera_source:
            self.camera_source = os.getenv(
                "CAMERA_INDEX",
                "0",
            ).strip()

        if not self.camera_source:
            raise ValueError(
                f"CAMERA_SOURCE is required "
                f"for {self.camera_id}."
            )

        self._camera_source_identity = self.camera_source

        # ----------------------------------------------------
        # YOLO configuration
        # ----------------------------------------------------

        self.model_path = os.getenv(
            "YOLO_MODEL",
            str(
                PROJECT_ROOT / "yolo11n.pt"
            ),
        ).strip()

        self.confidence = parse_positive_float(
            "YOLO_CONFIDENCE",
            0.40,
        )

        self.iou = parse_positive_float(
            "YOLO_IOU",
            0.45,
        )

        self.class_filter = parse_class_filter(
            os.getenv(
                "YOLO_CLASSES",
                self.DEFAULT_CLASSES,
            )
        )

        # ----------------------------------------------------
        # Frame processing
        # ----------------------------------------------------

        # This is now ONLY inference/display pacing.
        #
        # It MUST NOT control camera capture.
        self.frame_interval = parse_non_negative_float(
            "FRAME_INTERVAL",
            0.20,
        )

        self.inference_interval = parse_non_negative_float(
            "INFERENCE_INTERVAL",
            0.0,
        )

        self.show_camera = parse_bool(
            os.getenv(
                "SHOW_CAMERA",
                "true",
            ),
            default=True,
        )

        # ----------------------------------------------------
        # Camera reconnect configuration
        # ----------------------------------------------------

        self.reconnect_initial_delay = parse_positive_float(
            "CAMERA_RECONNECT_INITIAL_DELAY",
            1.0,
        )

        self.reconnect_max_delay = parse_positive_float(
            "CAMERA_RECONNECT_MAX_DELAY",
            30.0,
        )

        self.read_failure_before_reconnect = max(
            1,
            parse_positive_int(
                "CAMERA_READ_FAILURE_THRESHOLD",
                3,
            ),
        )

        # ----------------------------------------------------
        # Event streams
        # ----------------------------------------------------

        self.detection_stream = os.getenv(
            "DETECTION_OUTPUT_STREAM",
            "events.detection",
        ).strip()

        self.vehicle_stream = os.getenv(
            "VEHICLE_OUTPUT_STREAM",
            "events.vehicle",
        ).strip()

        self.object_stream = os.getenv(
            "OBJECT_OUTPUT_STREAM",
            "events.objects",
        ).strip()

        # ----------------------------------------------------
        # Runtime state
        # ----------------------------------------------------

        self.model: YOLO | None = None

        self.cap: cv2.VideoCapture | None = None

        self.frame_id = 0

        self.last_inference_time = 0.0
        self.last_frame_time = 0.0

        self.read_failures = 0

        self.reconnect_delay = (
            self.reconnect_initial_delay
        )

        self.reconnect_in_progress = False

        # ----------------------------------------------------
        # Camera evidence directory
        # ----------------------------------------------------

        self.camera_evidence_dir = (
            EVIDENCE_ROOT
            / self._safe_camera_directory_name(
                self.camera_id
            )
        )

        self.camera_evidence_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.latest_frame_path = (
            self.camera_evidence_dir
            / "latest.jpg"
        )

        # ----------------------------------------------------
        # Rolling evidence configuration
        # ----------------------------------------------------

        self.evidence_segment_seconds = (
            parse_positive_float(
                "EVIDENCE_SEGMENT_SECONDS",
                5.0,
            )
        )

        self.evidence_retention_seconds = (
            parse_positive_float(
                "EVIDENCE_RETENTION_SECONDS",
                60.0,
            )
        )

        self.evidence_fps = parse_positive_float(
            "EVIDENCE_FPS",
            20.0,
        )

        # ----------------------------------------------------
        # Rolling evidence buffer
        # ----------------------------------------------------

        self.evidence_buffer: RollingEvidenceBuffer | None = None

        self.evidence_buffer_enabled = True

        self._initialize_evidence_buffer()

        # ----------------------------------------------------
        # Model class metadata
        # ----------------------------------------------------

        self.class_names: dict[int, str] = {}

        # ----------------------------------------------------
        # Capture / inference decoupling
        # ----------------------------------------------------

        # Only the newest frame is required for inference.
        #
        # Evidence recording receives EVERY successfully
        # captured frame independently.
        self.latest_capture_queue: asyncio.Queue[
            tuple[Any, str, float, int]
        ] = asyncio.Queue(
            maxsize=1
        )

        self.capture_task: asyncio.Task | None = None

        self.capture_stop_event = asyncio.Event()

    # ========================================================
    # CAMERA DIRECTORY
    # ========================================================

    @staticmethod
    def _safe_camera_directory_name(
        camera_id: str,
    ) -> str:
        allowed = (
            "abcdefghijklmnopqrstuvwxyz"
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "0123456789"
            "-_."
        )

        result = "".join(
            character
            if character in allowed
            else "_"
            for character in camera_id
        )

        return (
            result[:120]
            or "camera"
        )

    # ========================================================
    # EVIDENCE BUFFER INITIALIZATION
    # ========================================================

    def _initialize_evidence_buffer(self) -> None:
        """
        Initialize the per-camera rolling evidence buffer.

        A buffer initialization failure is isolated from the
        detection worker.
        """

        try:
            self.evidence_buffer = RollingEvidenceBuffer(
                camera_id=self.camera_id,
                output_dir=self.camera_evidence_dir,
                segment_seconds=self.evidence_segment_seconds,
                retention_seconds=self.evidence_retention_seconds,
                fps=self.evidence_fps,
            )

            self.evidence_buffer_enabled = True

            print(
                f"[{self.agent_id}] "
                "Rolling evidence buffer initialized | "
                f"camera_id={self.camera_id} | "
                f"directory={self.evidence_buffer.buffer_dir} | "
                f"segment={self.evidence_buffer.segment_seconds:.1f}s | "
                f"retention={self.evidence_buffer.retention_seconds:.1f}s | "
                f"fps={self.evidence_buffer.fps:.1f}"
            )

        except Exception as error:
            self.evidence_buffer = None
            self.evidence_buffer_enabled = False

            print(
                f"[{self.agent_id}] "
                "Rolling evidence buffer initialization failed "
                "but detection remains active | "
                f"camera_id={self.camera_id} | "
                f"type={type(error).__name__} | "
                f"error={error}"
            )

    # ========================================================
    # IDENTITY VALIDATION
    # ========================================================

    def _validate_camera_identity(
        self,
    ) -> None:

        if self.camera_id != self._camera_identity:
            raise RuntimeError(
                "CAMERA ID MUTATION DETECTED: "
                f"original={self._camera_identity}, "
                f"current={self.camera_id}"
            )

        if (
            self.camera_source
            != self._camera_source_identity
        ):
            raise RuntimeError(
                "CAMERA SOURCE MUTATION DETECTED: "
                f"original={self._camera_source_identity}, "
                f"current={self.camera_source}"
            )

    # ========================================================
    # START
    # ========================================================

    async def on_start(
        self,
    ):
        self._validate_camera_identity()

        print(
            f"[{self.agent_id}] "
            "Starting per-camera detection worker."
        )

        print(
            f"[{self.agent_id}] "
            f"Camera ID: {self.camera_id}"
        )

        print(
            f"[{self.agent_id}] "
            f"Camera name: {self.camera_name}"
        )

        print(
            f"[{self.agent_id}] "
            f"Camera location: {self.camera_location}"
        )

        print(
            f"[{self.agent_id}] "
            f"Camera source: {self.camera_source}"
        )

        print(
            f"[{self.agent_id}] "
            f"Evidence directory: "
            f"{self.camera_evidence_dir}"
        )

        if self.evidence_buffer is not None:

            print(
                f"[{self.agent_id}] "
                "Evidence buffer: "
                f"{self.evidence_buffer.buffer_dir}"
            )

            print(
                f"[{self.agent_id}] "
                "Evidence segment: "
                f"{self.evidence_buffer.segment_seconds:.1f}s"
            )

            print(
                f"[{self.agent_id}] "
                "Evidence retention: "
                f"{self.evidence_buffer.retention_seconds:.1f}s"
            )

            print(
                f"[{self.agent_id}] "
                "Evidence FPS: "
                f"{self.evidence_buffer.fps:.1f}"
            )

        else:

            print(
                f"[{self.agent_id}] "
                "Evidence buffer is DISABLED."
            )

        print(
            f"[{self.agent_id}] "
            f"YOLO model: {self.model_path}"
        )

        if self.class_filter is None:

            print(
                f"[{self.agent_id}] "
                "YOLO classes: ALL"
            )

        else:

            print(
                f"[{self.agent_id}] "
                f"YOLO classes: {self.class_filter}"
            )

        # ----------------------------------------------------
        # Lazy model loading
        # ----------------------------------------------------

        try:

            self.model = YOLO(
                self.model_path
            )

            self._load_class_names()

            print(
                f"[{self.agent_id}] "
                "YOLO model loaded successfully."
            )

        except Exception as error:

            print(
                f"[{self.agent_id}] "
                "YOLO model loading failed: "
                f"{type(error).__name__}: "
                f"{error}"
            )

            raise

        # ----------------------------------------------------
        # Camera best effort
        # ----------------------------------------------------

        opened = await self._open_camera()

        if opened:

            print(
                f"[{self.agent_id}] "
                "Camera opened successfully: "
                f"camera_id={self.camera_id}, "
                f"source={self.camera_source}"
            )

        else:

            print(
                f"[{self.agent_id}] "
                "Camera unavailable: "
                f"camera_id={self.camera_id}, "
                f"source={self.camera_source}. "
                "Worker remains alive and will retry."
            )

    # ========================================================
    # LOAD CLASS NAMES
    # ========================================================

    def _load_class_names(
        self,
    ) -> None:

        if self.model is None:
            return

        names = getattr(
            self.model,
            "names",
            {},
        )

        if isinstance(
            names,
            dict,
        ):

            self.class_names = {
                int(key): str(value)
                for key, value in names.items()
            }

        elif isinstance(
            names,
            list,
        ):

            self.class_names = {
                index: str(value)
                for index, value in enumerate(names)
            }

        else:

            self.class_names = {}

    # ========================================================
    # CAMERA OPEN
    # ========================================================

    async def _open_camera(
        self,
    ) -> bool:

        self._validate_camera_identity()

        loop = asyncio.get_running_loop()

        # ----------------------------------------------------
        # Release previous capture
        # ----------------------------------------------------

        old_cap = self.cap

        if old_cap is not None:

            try:

                await loop.run_in_executor(
                    None,
                    old_cap.release,
                )

            except Exception as error:

                print(
                    f"[{self.agent_id}] "
                    "Previous camera release "
                    f"error isolated: {error}"
                )

            self.cap = None

        # ----------------------------------------------------
        # Normalize source
        # ----------------------------------------------------

        source = self._normalize_camera_source(
            self.camera_source
        )

        print(
            f"[{self.agent_id}] "
            "Opening camera: "
            f"camera_id={self.camera_id}, "
            f"source={self.camera_source}"
        )

        cap: cv2.VideoCapture | None = None

        try:

            cap = await loop.run_in_executor(
                None,
                cv2.VideoCapture,
                source,
            )

            if cap is None:

                print(
                    f"[{self.agent_id}] "
                    "cv2.VideoCapture returned None."
                )

                return False

            is_opened = await loop.run_in_executor(
                None,
                cap.isOpened,
            )

            if not is_opened:

                print(
                    f"[{self.agent_id}] "
                    "Camera failed to open: "
                    f"camera_id={self.camera_id}, "
                    f"source={self.camera_source}"
                )

                try:

                    await loop.run_in_executor(
                        None,
                        cap.release,
                    )

                except Exception:
                    pass

                return False

            # ------------------------------------------------
            # Low-latency buffer
            # ------------------------------------------------

            try:

                await loop.run_in_executor(
                    None,
                    lambda: cap.set(
                        cv2.CAP_PROP_BUFFERSIZE,
                        1,
                    ),
                )

            except Exception as error:

                print(
                    f"[{self.agent_id}] "
                    "Camera buffer configuration "
                    f"failed but isolated: {error}"
                )

            # ------------------------------------------------
            # Assign only after successful open
            # ------------------------------------------------

            self.cap = cap

            self.read_failures = 0

            self.reconnect_delay = (
                self.reconnect_initial_delay
            )

            return True

        except Exception as error:

            print(
                f"[{self.agent_id}] "
                "Camera open error isolated: "
                f"{type(error).__name__}: "
                f"{error}"
            )

            if cap is not None:

                try:

                    await loop.run_in_executor(
                        None,
                        cap.release,
                    )

                except Exception:
                    pass

            return False

    # ========================================================
    # CAMERA SOURCE NORMALIZATION
    # ========================================================

    @staticmethod
    def _normalize_camera_source(
        source: str,
    ) -> str | int:

        value = str(source).strip()

        if (
            value.isdigit()
            and not value.startswith("0x")
        ):

            try:
                return int(value)

            except ValueError:
                pass

        return value

    # ========================================================
    # CAMERA RECONNECT
    # ========================================================

    async def _reconnect_camera(
        self,
    ) -> None:

        self._validate_camera_identity()

        if self.reconnect_in_progress:
            return

        self.reconnect_in_progress = True

        try:

            print(
                f"[{self.agent_id}] "
                "Camera reconnect scheduled: "
                f"camera_id={self.camera_id}, "
                f"source={self.camera_source}, "
                f"delay={self.reconnect_delay:.1f}s"
            )

            await asyncio.sleep(
                self.reconnect_delay
            )

            if not self.running:
                return

            self._validate_camera_identity()

            opened = await self._open_camera()

            if opened:

                print(
                    f"[{self.agent_id}] "
                    "Camera reconnected successfully: "
                    f"camera_id={self.camera_id}, "
                    f"source={self.camera_source}"
                )

                self.reconnect_delay = (
                    self.reconnect_initial_delay
                )

            else:

                self.reconnect_delay = min(
                    self.reconnect_delay * 2,
                    self.reconnect_max_delay,
                )

                print(
                    f"[{self.agent_id}] "
                    "Camera reconnect failed: "
                    f"camera_id={self.camera_id}, "
                    f"source={self.camera_source}, "
                    f"next_delay="
                    f"{self.reconnect_delay:.1f}s"
                )

        finally:

            self.reconnect_in_progress = False

    # ========================================================
    # STOP
    # ========================================================

    async def on_stop(
        self,
    ):

        self.capture_stop_event.set()

        # ----------------------------------------------------
        # Stop capture task
        # ----------------------------------------------------

        capture_task = self.capture_task

        self.capture_task = None

        if capture_task is not None:

            if (
                not capture_task.done()
                and capture_task is not asyncio.current_task()
            ):

                capture_task.cancel()

                try:
                    await capture_task

                except asyncio.CancelledError:
                    pass

                except Exception as error:

                    print(
                        f"[{self.agent_id}] "
                        "Capture task shutdown error "
                        f"isolated: {error}"
                    )

        # ----------------------------------------------------
        # Close evidence buffer
        # ----------------------------------------------------

        buffer_instance = self.evidence_buffer

        self.evidence_buffer = None

        if buffer_instance is not None:

            try:

                buffer_instance.close()

                print(
                    f"[{self.agent_id}] "
                    "Evidence buffer closed successfully | "
                    f"camera_id={self.camera_id}"
                )

            except Exception as error:

                print(
                    f"[{self.agent_id}] "
                    "Evidence buffer close failed "
                    "but isolated | "
                    f"camera_id={self.camera_id} | "
                    f"error={error}"
                )

        # ----------------------------------------------------
        # Release camera
        # ----------------------------------------------------

        loop = asyncio.get_running_loop()

        cap = self.cap

        self.cap = None

        if cap is not None:

            try:

                await loop.run_in_executor(
                    None,
                    cap.release,
                )

            except Exception as error:

                print(
                    f"[{self.agent_id}] "
                    "Camera release error isolated: "
                    f"{error}"
                )

        # ----------------------------------------------------
        # Close OpenCV window
        # ----------------------------------------------------

        if self.show_camera:

            try:

                cv2.destroyWindow(
                    f"CCTV AI - {self.camera_id}"
                )

            except Exception:
                pass

            try:

                cv2.destroyAllWindows()

            except Exception:
                pass

        print(
            f"[{self.agent_id}] "
            "Detection worker stopped: "
            f"camera_id={self.camera_id}"
        )

    # ========================================================
    # INFERENCE
    # ========================================================

    def _run_yolo(
        self,
        frame,
    ):

        if self.model is None:
            raise RuntimeError(
                "YOLO model is not initialized."
            )

        return self.model(
            frame,
            conf=self.confidence,
            iou=self.iou,
            classes=self.class_filter,
            verbose=False,
        )

    # ========================================================
    # EXTRACT DETECTIONS
    # ========================================================

    def _extract_detections(
        self,
        results,
    ) -> list[dict[str, Any]]:

        detections: list[dict[str, Any]] = []

        for result in results:

            if result.boxes is None:
                continue

            boxes = result.boxes

            for index in range(len(boxes)):

                box = boxes[index]

                xyxy = (
                    box.xyxy[0]
                    .cpu()
                    .tolist()
                )

                confidence = float(
                    box.conf[0]
                    .cpu()
                    .item()
                )

                class_id = int(
                    box.cls[0]
                    .cpu()
                    .item()
                )

                class_name = self.class_names.get(
                    class_id,
                    f"class_{class_id}",
                )

                detection_id = (
                    f"det-"
                    f"{self.camera_id}-"
                    f"{self.frame_id}-"
                    f"{uuid.uuid4().hex[:8]}"
                )

                x1 = float(xyxy[0])
                y1 = float(xyxy[1])
                x2 = float(xyxy[2])
                y2 = float(xyxy[3])

                detections.append(
                    {
                        "detection_id": detection_id,
                        "class_id": class_id,
                        "class_name": class_name,
                        "confidence": confidence,
                        "bbox": [
                            x1,
                            y1,
                            x2,
                            y2,
                        ],
                    }
                )

        return detections

    # ========================================================
    # SPLIT DETECTIONS
    # ========================================================

    @staticmethod
    def _split_detections(
        detections: list[dict[str, Any]],
    ):

        people: list[dict[str, Any]] = []
        vehicles: list[dict[str, Any]] = []

        for detection in detections:

            class_id = int(
                detection["class_id"]
            )

            if class_id == DetectionAgent.PERSON_CLASS_ID:
                people.append(detection)

            if class_id in DetectionAgent.VEHICLE_CLASS_IDS:
                vehicles.append(detection)

        return people, vehicles

    # ========================================================
    # EVENT PUBLISHING
    # ========================================================

    async def _publish_event(
        self,
        stream: str,
        event_type: str,
        data: dict[str, Any],
        trace_id: str | None = None,
        correlation_id: str | None = None,
        incident_id: str | None = None,
    ):

        self._validate_camera_identity()

        event = create_event(
            event_type=event_type,
            agent_id=self.agent_id,
            instance_id=self.instance_id,
            hostname=self.hostname,
            camera_id=self.camera_id,
            mode="live",
            trace_id=trace_id,
            correlation_id=correlation_id,
            incident_id=incident_id,
            data=data,
        )

        return await self.publish(
            stream,
            event.to_dict(),
        )

    # ========================================================
    # PERSON EVENT
    # ========================================================

    async def _publish_person_event(
        self,
        people: list[dict[str, Any]],
        frame_timestamp: str,
    ):

        data = {
            "frame_id": str(
                self.frame_id
            ),
            "frame_timestamp": frame_timestamp,
            "detection_count": len(people),
            "count": len(people),
            "detections": people,
            "model": self.model_path,
            "confidence_threshold": self.confidence,
        }

        return await self._publish_event(
            stream=self.detection_stream,
            event_type="person.detected",
            data=data,
        )

    # ========================================================
    # VEHICLE EVENT
    # ========================================================

    async def _publish_vehicle_event(
        self,
        vehicles: list[dict[str, Any]],
        frame_timestamp: str,
    ):

        data = {
            "frame_id": str(
                self.frame_id
            ),
            "frame_timestamp": frame_timestamp,
            "vehicle_count": len(vehicles),
            "count": len(vehicles),
            "vehicles": vehicles,
            "model": self.model_path,
            "confidence_threshold": self.confidence,
        }

        return await self._publish_event(
            stream=self.vehicle_stream,
            event_type="vehicle.detected",
            data=data,
        )

    # ========================================================
    # GENERIC OBJECT EVENT
    # ========================================================

    async def _publish_object_event(
        self,
        detections: list[dict[str, Any]],
        frame_timestamp: str,
    ):

        data = {
            "frame_id": str(
                self.frame_id
            ),
            "frame_timestamp": frame_timestamp,
            "object_count": len(detections),
            "count": len(detections),
            "detections": detections,
            "model": self.model_path,
            "confidence_threshold": self.confidence,
        }

        return await self._publish_event(
            stream=self.object_stream,
            event_type="object.detected",
            data=data,
        )

    # ========================================================
    # ANNOTATION
    # ========================================================

    def _annotate_frame(
        self,
        frame,
        detections: list[dict[str, Any]],
    ):

        annotated_frame = frame.copy()

        for detection in detections:

            bbox = detection["bbox"]

            x1 = int(bbox[0])
            y1 = int(bbox[1])
            x2 = int(bbox[2])
            y2 = int(bbox[3])

            confidence = float(
                detection["confidence"]
            )

            class_id = int(
                detection["class_id"]
            )

            class_name = str(
                detection["class_name"]
            )

            if class_id == self.PERSON_CLASS_ID:

                label = (
                    f"Person "
                    f"{confidence:.2f}"
                )

            else:

                label = (
                    f"{class_name} "
                    f"{confidence:.2f}"
                )

            cv2.rectangle(
                annotated_frame,
                (x1, y1),
                (x2, y2),
                (0, 255, 0),
                2,
            )

            cv2.putText(
                annotated_frame,
                label,
                (
                    x1,
                    max(
                        y1 - 10,
                        20,
                    ),
                ),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2,
            )

        cv2.putText(
            annotated_frame,
            (
                f"Camera: "
                f"{self.camera_id} | "
                f"Frame: "
                f"{self.frame_id} | "
                f"Objects: "
                f"{len(detections)}"
            ),
            (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
        )

        return annotated_frame

    # ========================================================
    # ATOMIC IMAGE WRITE
    # ========================================================

    def _write_latest_frame(
        self,
        frame,
    ):

        target = self.latest_frame_path

        temp_path: Path | None = None

        try:

            target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            temp_path = target.with_name(
                f".{target.stem}."
                f"{uuid.uuid4().hex}"
                f"{target.suffix}"
            )

            success = cv2.imwrite(
                str(temp_path),
                frame,
            )

            if not success:

                raise RuntimeError(
                    "cv2.imwrite returned False"
                )

            os.replace(
                temp_path,
                target,
            )

        except Exception as error:

            print(
                f"[{self.agent_id}] "
                "Latest-frame write failed: "
                f"camera_id={self.camera_id}, "
                f"target={target}, "
                f"error={error}"
            )

            if temp_path is not None:

                try:

                    if temp_path.exists():
                        temp_path.unlink()

                except Exception:
                    pass

    # ========================================================
    # DISPLAY
    # ========================================================

    def _display_frame(
        self,
        frame,
    ) -> bool:

        if not self.show_camera:
            return True

        try:

            window_name = (
                f"CCTV AI - "
                f"{self.camera_id}"
            )

            cv2.imshow(
                window_name,
                frame,
            )

            key = (
                cv2.waitKey(1)
                & 0xFF
            )

            if key == ord("q"):

                print(
                    f"[{self.agent_id}] "
                    "Shutdown requested by operator: "
                    f"camera_id={self.camera_id}"
                )

                return False

        except Exception as error:

            print(
                f"[{self.agent_id}] "
                "Display error isolated: "
                f"camera_id={self.camera_id}, "
                f"error={error}"
            )

        return True

    # ========================================================
    # ROLLING BUFFER WRITE
    # ========================================================

    def _write_evidence_frame(
        self,
        frame,
        frame_timestamp: str,
        frame_epoch: float,
    ) -> bool:

        """
        Write EVERY successfully captured frame into the
        per-camera rolling evidence buffer.

        This method is called by the dedicated camera capture
        loop and therefore does not wait for YOLO inference.
        """

        buffer_instance = self.evidence_buffer

        if (
            not self.evidence_buffer_enabled
            or buffer_instance is None
        ):
            return False

        try:

            accepted = buffer_instance.write(
                frame,
                timestamp=frame_timestamp,
                epoch=frame_epoch,
            )

            if not accepted:

                print(
                    f"[{self.agent_id}] "
                    "Evidence buffer rejected frame | "
                    f"camera_id={self.camera_id} | "
                    f"frame={self.frame_id}"
                )

            return bool(accepted)

        except Exception as error:

            print(
                f"[{self.agent_id}] "
                "Evidence buffer write failed but "
                "detection remains active | "
                f"camera_id={self.camera_id} | "
                f"frame={self.frame_id} | "
                f"type={type(error).__name__} | "
                f"error={error}"
            )

            return False

    # ========================================================
    # BUFFER STATUS LOGGING
    # ========================================================

    def _log_buffer_status(
        self,
    ) -> None:

        buffer_instance = self.evidence_buffer

        if buffer_instance is None:
            return

        try:

            status = buffer_instance.status()

            print(
                f"[{self.agent_id}] "
                "Evidence buffer status | "
                f"camera_id={self.camera_id} | "
                f"segments={status.get('segment_count')} | "
                f"frames={status.get('frame_count')} | "
                f"active={status.get('active')} | "
                f"directory={status.get('buffer_dir')}"
            )

        except Exception as error:

            print(
                f"[{self.agent_id}] "
                "Evidence buffer status check "
                f"failed but isolated | "
                f"camera_id={self.camera_id} | "
                f"error={error}"
            )

    # ========================================================
    # QUEUE LATEST FRAME
    # ========================================================

    async def _queue_latest_frame(
        self,
        frame,
        frame_timestamp: str,
        frame_epoch: float,
        captured_frame_id: int,
    ) -> None:

        """
        Keep only the newest frame for inference.

        The camera/evidence path never waits for inference.
        """

        item = (
            frame,
            frame_timestamp,
            frame_epoch,
            captured_frame_id,
        )

        try:

            self.latest_capture_queue.put_nowait(
                item
            )

        except asyncio.QueueFull:

            try:
                self.latest_capture_queue.get_nowait()

            except asyncio.QueueEmpty:
                pass

            try:

                self.latest_capture_queue.put_nowait(
                    item
                )

            except asyncio.QueueFull:

                # Another consumer may have inserted the
                # latest frame. Dropping this inference frame
                # is acceptable because evidence already has it.
                pass

    # ========================================================
    # CAMERA CAPTURE LOOP
    # ========================================================

    async def _capture_loop(
        self,
    ) -> None:

        """
        Dedicated camera acquisition loop.

        CRITICAL:

        This loop owns the camera read path and rolling
        evidence recording.

        It does NOT run YOLO.

        It does NOT publish Redis detection events.

        It does NOT wait for inference.

        It does NOT wait for latest.jpg.

        It does NOT wait for display.

        Therefore camera evidence remains continuous even
        when inference is slow.
        """

        loop = asyncio.get_running_loop()

        last_buffer_status_log = time.monotonic()

        while (
            self.running
            and not self.capture_stop_event.is_set()
        ):

            try:

                self._validate_camera_identity()

                # ------------------------------------------------
                # Camera unavailable
                # ------------------------------------------------

                if self.cap is None:

                    await self._reconnect_camera()

                    continue

                cap = self.cap

                # ------------------------------------------------
                # Capture frame
                # ------------------------------------------------

                ret, frame = await loop.run_in_executor(
                    None,
                    cap.read,
                )

                # If another operation replaced the capture,
                # ignore this result.
                if cap is not self.cap:
                    continue

                # ------------------------------------------------
                # Read failure
                # ------------------------------------------------

                if (
                    not ret
                    or frame is None
                ):

                    self.read_failures += 1

                    print(
                        f"[{self.agent_id}] "
                        "Camera frame read failed "
                        f"({self.read_failures}/"
                        f"{self.read_failure_before_reconnect}) | "
                        f"camera_id={self.camera_id}"
                    )

                    if (
                        self.read_failures
                        >= self.read_failure_before_reconnect
                    ):

                        failed_cap = self.cap

                        self.cap = None

                        if failed_cap is not None:

                            try:

                                await loop.run_in_executor(
                                    None,
                                    failed_cap.release,
                                )

                            except Exception as error:

                                print(
                                    f"[{self.agent_id}] "
                                    "Failed camera release "
                                    f"isolated: {error}"
                                )

                        # Close current evidence segment cleanly.
                        buffer_instance = self.evidence_buffer

                        if buffer_instance is not None:

                            try:

                                buffer_instance.rotate()

                            except Exception as error:

                                print(
                                    f"[{self.agent_id}] "
                                    "Evidence buffer rotation "
                                    f"failed but isolated | "
                                    f"camera_id={self.camera_id} | "
                                    f"error={error}"
                                )

                        self.read_failures = 0

                    await asyncio.sleep(
                        min(
                            self.reconnect_delay,
                            2.0,
                        )
                    )

                    continue

                # ------------------------------------------------
                # Successful capture
                # ------------------------------------------------

                self.read_failures = 0

                self.last_frame_time = (
                    time.monotonic()
                )

                self.frame_id += 1

                captured_frame_id = self.frame_id

                # Capture timestamp immediately after acquisition.
                frame_timestamp = utc_timestamp()

                frame_epoch = time.time()

                # ------------------------------------------------
                # ROLLING EVIDENCE
                # ------------------------------------------------
                #
                # This happens immediately after capture.
                #
                # It is completely independent of YOLO.
                # ------------------------------------------------

                self._write_evidence_frame(
                    frame=frame,
                    frame_timestamp=frame_timestamp,
                    frame_epoch=frame_epoch,
                )

                # ------------------------------------------------
                # Send newest frame to inference queue
                # ------------------------------------------------

                await self._queue_latest_frame(
                    frame=frame,
                    frame_timestamp=frame_timestamp,
                    frame_epoch=frame_epoch,
                    captured_frame_id=captured_frame_id,
                )

                # ------------------------------------------------
                # Periodic buffer diagnostics
                # ------------------------------------------------

                now_monotonic = time.monotonic()

                if (
                    now_monotonic
                    - last_buffer_status_log
                    >= 10.0
                ):

                    self._log_buffer_status()

                    last_buffer_status_log = (
                        now_monotonic
                    )

            except asyncio.CancelledError:
                raise

            except Exception as error:

                print(
                    f"[{self.agent_id}] "
                    "Camera capture iteration error isolated | "
                    f"camera_id={self.camera_id} | "
                    f"type={type(error).__name__} | "
                    f"error={error}"
                )

                await asyncio.sleep(
                    0.2
                )

        print(
            f"[{self.agent_id}] "
            "Camera capture loop stopped | "
            f"camera_id={self.camera_id}"
        )

    # ========================================================
    # INFERENCE FRAME PROCESSING
    # ========================================================

    async def _process_inference_frame(
        self,
        frame,
        frame_timestamp: str,
        frame_epoch: float,
        captured_frame_id: int,
    ) -> bool:

        """
        Process one latest available frame through YOLO.

        Evidence recording has already happened in the
        independent capture loop.
        """

        loop = asyncio.get_running_loop()

        # ----------------------------------------------------
        # Optional inference throttling
        # ----------------------------------------------------

        if self.inference_interval > 0:

            now = time.monotonic()

            elapsed = (
                now
                - self.last_inference_time
            )

            if (
                elapsed
                < self.inference_interval
            ):

                if not self._display_frame(
                    frame
                ):
                    return False

                return True

        self.last_inference_time = (
            time.monotonic()
        )

        # ----------------------------------------------------
        # YOLO inference
        # ----------------------------------------------------

        results = await loop.run_in_executor(
            None,
            self._run_yolo,
            frame,
        )

        # ----------------------------------------------------
        # Extract detections
        # ----------------------------------------------------

        detections = (
            self._extract_detections(
                results
            )
        )

        people, vehicles = (
            self._split_detections(
                detections
            )
        )

        # ----------------------------------------------------
        # Annotation
        # ----------------------------------------------------

        annotated_frame = (
            self._annotate_frame(
                frame,
                detections,
            )
        )

        # ----------------------------------------------------
        # Publish person event
        # ----------------------------------------------------

        person_redis_id = (
            await self._publish_person_event(
                people,
                frame_timestamp,
            )
        )

        # ----------------------------------------------------
        # Publish vehicle event
        # ----------------------------------------------------

        vehicle_redis_id = (
            await self._publish_vehicle_event(
                vehicles,
                frame_timestamp,
            )
        )

        # ----------------------------------------------------
        # Publish generic object event
        # ----------------------------------------------------

        object_redis_id = (
            await self._publish_object_event(
                detections,
                frame_timestamp,
            )
        )

        # ----------------------------------------------------
        # Camera-specific latest frame
        # ----------------------------------------------------

        self._write_latest_frame(
            annotated_frame
        )

        # ----------------------------------------------------
        # Logging
        # ----------------------------------------------------

        print(
            "DETECTED | "
            f"Agent={self.agent_id} | "
            f"Camera={self.camera_id} | "
            f"CapturedFrame={captured_frame_id} | "
            f"Persons={len(people)} | "
            f"Vehicles={len(vehicles)} | "
            f"Objects={len(detections)} | "
            f"PersonRedis={person_redis_id} | "
            f"VehicleRedis={vehicle_redis_id} | "
            f"ObjectRedis={object_redis_id}"
        )

        # ----------------------------------------------------
        # Display
        # ----------------------------------------------------

        if not self._display_frame(
            annotated_frame
        ):
            return False

        # ----------------------------------------------------
        # Inference pacing
        # ----------------------------------------------------

        if self.frame_interval > 0:

            await asyncio.sleep(
                self.frame_interval
            )

        return True

    # ========================================================
    # MAIN LOOP
    # ========================================================

    async def run(
        self,
    ):

        if self.model is None:
            raise RuntimeError(
                "YOLO model is not initialized."
            )

        self._validate_camera_identity()

        print(
            f"[{self.agent_id}] "
            "Detection loop started: "
            f"camera_id={self.camera_id}, "
            f"source={self.camera_source}"
        )

        # ----------------------------------------------------
        # Start independent capture/evidence loop
        # ----------------------------------------------------

        self.capture_stop_event.clear()

        self.capture_task = asyncio.create_task(
            self._capture_loop(),
            name=(
                f"capture-{self.camera_id}"
            ),
        )

        try:

            # ------------------------------------------------
            # Inference loop
            # ------------------------------------------------

            while self.running:

                try:

                    self._validate_camera_identity()

                    frame, frame_timestamp, frame_epoch, captured_frame_id = (
                        await asyncio.wait_for(
                            self.latest_capture_queue.get(),
                            timeout=1.0,
                        )
                    )

                    keep_running = (
                        await self._process_inference_frame(
                            frame=frame,
                            frame_timestamp=frame_timestamp,
                            frame_epoch=frame_epoch,
                            captured_frame_id=captured_frame_id,
                        )
                    )

                    if not keep_running:
                        break

                except asyncio.TimeoutError:

                    # Camera capture continues independently.
                    continue

                except asyncio.CancelledError:
                    raise

                except Exception as error:

                    """
                    CRITICAL FAULT-ISOLATION RULE:

                    A single inference, Redis publish,
                    annotation, display, or processing failure
                    must NOT terminate this camera worker.

                    The capture/evidence loop remains independent.
                    """

                    print(
                        f"[{self.agent_id}] "
                        "Detection iteration error isolated | "
                        f"camera_id={self.camera_id} | "
                        f"type={type(error).__name__} | "
                        f"error={error}"
                    )

                    await asyncio.sleep(
                        0.2
                    )

        finally:

            # ------------------------------------------------
            # Stop capture loop
            # ------------------------------------------------

            self.capture_stop_event.set()

            capture_task = self.capture_task

            self.capture_task = None

            if capture_task is not None:

                if not capture_task.done():

                    capture_task.cancel()

                    try:

                        await capture_task

                    except asyncio.CancelledError:
                        pass

                    except Exception as error:

                        print(
                            f"[{self.agent_id}] "
                            "Capture task finalization "
                            f"error isolated: {error}"
                        )

        print(
            f"[{self.agent_id}] "
            "Detection loop stopped | "
            f"camera_id={self.camera_id}"
        )


# ============================================================
# MAIN
# ============================================================


async def main():

    agent = DetectionAgent()

    await agent.run_forever()


if __name__ == "__main__":

    asyncio.run(
        main()
    )