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

        # ----------------------------------------------------
        # Per-camera event streams
        # ----------------------------------------------------
        #
        # Each detector owns exactly one camera.
        #
        # Therefore detection events are routed to a
        # camera-specific stream automatically:
        #
        #   CAM01 -> events.detection.CAM01
        #   CAM02 -> events.detection.CAM02
        #   CAM03 -> events.detection.CAM03
        #
        # An explicit DETECTION_OUTPUT_STREAM override is
        # still supported for testing/backward compatibility.

        default_detection_stream = (
            f"events.detection.{self.camera_id}"
        )

        self.detection_stream = os.getenv(
            "DETECTION_OUTPUT_STREAM",
            default_detection_stream,
        ).strip()

        if not self.detection_stream:
            raise ValueError(
                f"DETECTION_OUTPUT_STREAM cannot be empty "
                f"for camera {self.camera_id}."
            )
            
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