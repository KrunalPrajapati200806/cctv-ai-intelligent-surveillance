# """
# Evidence/proof-video generator for the CCTV AI surveillance platform.

# Responsibilities
# ----------------

# - Validate the source video.
# - Determine the proof-video time window.
# - Generate an annotated temporary proof video.
# - Convert the temporary video to H.264 MP4.
# - Return evidence metadata.

# This module does NOT:

# - consume Redis messages
# - create incidents
# - publish Redis events
# - perform alert generation
# - perform tracking
# - perform LLM reasoning
# """

# from __future__ import annotations

# import math
# import os
# import threading
# from pathlib import Path
# from typing import Any, Optional

# import cv2
# from ultralytics import YOLO

# from agents.evidence.ffmpeg import convert_to_h264


# # ============================================================
# # PATHS
# # ============================================================

# PROJECT_ROOT = Path(__file__).resolve().parents[2]
# DATA_ROOT = PROJECT_ROOT / "data"

# EVIDENCE_ROOT = DATA_ROOT / "evidence"
# PROOF_DIR = DATA_ROOT / "proof_videos"

# EVIDENCE_ROOT.mkdir(
#     parents=True,
#     exist_ok=True,
# )

# PROOF_DIR.mkdir(
#     parents=True,
#     exist_ok=True,
# )


# # ============================================================
# # ENVIRONMENT HELPERS
# # ============================================================

# def _env_float(
#     name: str,
#     default: float,
#     *,
#     minimum: Optional[float] = None,
# ) -> float:
#     """
#     Read a floating-point environment variable safely.
#     """

#     raw = os.getenv(name)

#     if raw is None or not raw.strip():
#         value = default
#     else:
#         try:
#             value = float(raw)
#         except (TypeError, ValueError):
#             print(
#                 f"[EVIDENCE-GENERATOR] Invalid float for "
#                 f"{name}={raw!r}; using {default}."
#             )
#             value = default

#     if not math.isfinite(value):
#         print(
#             f"[EVIDENCE-GENERATOR] Non-finite value for "
#             f"{name}={raw!r}; using {default}."
#         )
#         value = default

#     if minimum is not None and value < minimum:
#         print(
#             f"[EVIDENCE-GENERATOR] {name}={value} is below "
#             f"minimum {minimum}; using {minimum}."
#         )
#         value = minimum

#     return value


# # ============================================================
# # CONFIGURATION
# # ============================================================

# CONFIDENCE_THRESHOLD = _env_float(
#     "EVIDENCE_CONFIDENCE",
#     0.40,
#     minimum=0.0,
# )

# PRE_EVENT_SECONDS = _env_float(
#     "EVIDENCE_PRE_EVENT_SECONDS",
#     4.0,
#     minimum=0.0,
# )

# POST_EVENT_SECONDS = _env_float(
#     "EVIDENCE_POST_EVENT_SECONDS",
#     6.0,
#     minimum=0.0,
# )

# PROOF_DURATION_SECONDS = _env_float(
#     "EVIDENCE_PROOF_DURATION_SECONDS",
#     10.0,
#     minimum=1.0,
# )

# MODEL_PATH = (
#     os.getenv(
#         "EVIDENCE_YOLO_MODEL",
#         str(PROJECT_ROOT / "yolo11n.pt"),
#     ).strip()
#     or str(PROJECT_ROOT / "yolo11n.pt")
# )


# # ============================================================
# # MODEL
# # ============================================================

# _MODEL: YOLO | None = None
# _MODEL_LOCK = threading.Lock()


# def get_model() -> YOLO:
#     """
#     Lazily load the YOLO model.

#     Model initialization is protected by a lock so multiple
#     threads cannot initialize the global model simultaneously.
#     """

#     global _MODEL

#     if _MODEL is not None:
#         return _MODEL

#     with _MODEL_LOCK:
#         if _MODEL is not None:
#             return _MODEL

#         model_path = Path(
#             MODEL_PATH
#         ).expanduser()

#         if not model_path.is_file():
#             raise FileNotFoundError(
#                 f"Evidence YOLO model was not found: "
#                 f"{model_path}"
#             )

#         print(
#             f"[EVIDENCE-GENERATOR] Loading YOLO model: "
#             f"{model_path}"
#         )

#         _MODEL = YOLO(
#             str(model_path)
#         )

#         print(
#             "[EVIDENCE-GENERATOR] YOLO model loaded."
#         )

#         return _MODEL


# # ============================================================
# # PERSON DETECTION
# # ============================================================

# def detect_people(
#     frame: Any,
# ) -> list[tuple[int, int, int, int, float]]:
#     """
#     Detect people in one frame.

#     Returns
#     -------
#     list[tuple[int, int, int, int, float]]
#         Each detection is:

#         (x1, y1, x2, y2, confidence)
#     """

#     model = get_model()

#     results = model.predict(
#         frame,
#         verbose=False,
#         conf=CONFIDENCE_THRESHOLD,
#         classes=[0],
#     )

#     detections: list[
#         tuple[int, int, int, int, float]
#     ] = []

#     for result in results:
#         boxes = getattr(
#             result,
#             "boxes",
#             None,
#         )

#         if boxes is None:
#             continue

#         for box in boxes:
#             try:
#                 cls_value = float(
#                     box.cls[0].item()
#                 )

#                 confidence = float(
#                     box.conf[0].item()
#                 )

#                 coordinates = (
#                     box.xyxy[0].tolist()
#                 )

#                 if cls_value != 0.0:
#                     continue

#                 if not math.isfinite(
#                     confidence
#                 ):
#                     continue

#                 if len(coordinates) != 4:
#                     continue

#                 x1, y1, x2, y2 = (
#                     int(round(value))
#                     for value in coordinates
#                 )

#                 if x2 <= x1 or y2 <= y1:
#                     continue

#                 detections.append(
#                     (
#                         x1,
#                         y1,
#                         x2,
#                         y2,
#                         confidence,
#                     )
#                 )

#             except Exception as error:
#                 print(
#                     "[EVIDENCE-GENERATOR] "
#                     f"Skipping malformed detection: {error}"
#                 )

#     return detections


# # ============================================================
# # DRAWING
# # ============================================================

# def draw_people(
#     frame: Any,
#     people: list[tuple[int, int, int, int, float]],
# ) -> None:
#     """
#     Draw person bounding boxes and confidence values.
#     """

#     for (
#         x1,
#         y1,
#         x2,
#         y2,
#         confidence,
#     ) in people:

#         cv2.rectangle(
#             frame,
#             (x1, y1),
#             (x2, y2),
#             (0, 255, 0),
#             2,
#         )

#         label = (
#             f"Person {confidence:.2f}"
#         )

#         cv2.putText(
#             frame,
#             label,
#             (
#                 x1,
#                 max(20, y1 - 8),
#             ),
#             cv2.FONT_HERSHEY_SIMPLEX,
#             0.55,
#             (0, 255, 0),
#             2,
#             cv2.LINE_AA,
#         )


# # ============================================================
# # EVENT HELPERS
# # ============================================================

# def _safe_event_time(
#     event: dict[str, Any],
# ) -> float:
#     """
#     Extract event time from supported event representations.

#     The returned value must represent seconds relative to the
#     beginning of the source video.
#     """

#     raw_value = event.get(
#         "event_time",
#         event.get(
#             "time",
#             event.get(
#                 "timestamp_seconds",
#                 0.0,
#             ),
#         ),
#     )

#     try:
#         value = float(raw_value)
#     except (
#         TypeError,
#         ValueError,
#     ):
#         return 0.0

#     if not math.isfinite(value):
#         return 0.0

#     return value


# def _safe_event_type(
#     event: dict[str, Any],
# ) -> str:
#     """
#     Extract event type from canonical or legacy fields.
#     """

#     value = event.get(
#         "event_type",
#         event.get(
#             "type",
#             "UNKNOWN_EVENT",
#         ),
#     )

#     text = str(value).strip()

#     return (
#         text
#         or "UNKNOWN_EVENT"
#     )


# def _safe_person_count(
#     event: dict[str, Any],
# ) -> int:
#     """
#     Safely extract the displayed person count.
#     """

#     value = event.get(
#         "after_person_count",
#         event.get(
#             "person_count",
#             0,
#         ),
#     )

#     try:
#         count = int(value)
#     except (
#         TypeError,
#         ValueError,
#     ):
#         return 0

#     return max(
#         0,
#         count,
#     )


# # ============================================================
# # PROOF HEADER
# # ============================================================

# def draw_proof_header(
#     frame: Any,
#     event: dict[str, Any],
# ) -> None:
#     """
#     Draw forensic context at the top of the frame.
#     """

#     height, width = frame.shape[:2]

#     header_height = min(
#         90,
#         max(1, height),
#     )

#     cv2.rectangle(
#         frame,
#         (0, 0),
#         (
#             max(0, width - 1),
#             header_height,
#         ),
#         (0, 0, 0),
#         -1,
#     )

#     event_type = _safe_event_type(
#         event
#     )

#     person_count = _safe_person_count(
#         event
#     )

#     event_time = _safe_event_time(
#         event
#     )

#     camera_id = str(
#         event.get(
#             "camera_id",
#             "UNKNOWN_CAMERA",
#         )
#     ).strip()

#     if not camera_id:
#         camera_id = "UNKNOWN_CAMERA"

#     line_one = (
#         f"EVENT: {event_type} | "
#         f"CAMERA: {camera_id}"
#     )

#     line_two = (
#         f"PERSONS: {person_count} | "
#         f"EVENT TIME: {event_time:.2f}s"
#     )

#     cv2.putText(
#         frame,
#         line_one,
#         (10, 32),
#         cv2.FONT_HERSHEY_SIMPLEX,
#         0.58,
#         (0, 255, 255),
#         2,
#         cv2.LINE_AA,
#     )

#     cv2.putText(
#         frame,
#         line_two,
#         (10, 65),
#         cv2.FONT_HERSHEY_SIMPLEX,
#         0.55,
#         (0, 255, 255),
#         2,
#         cv2.LINE_AA,
#     )


# # ============================================================
# # PROOF WINDOW
# # ============================================================

# def calculate_proof_window(
#     event_time: float,
#     duration: float,
# ) -> tuple[float, float]:
#     """
#     Calculate a bounded proof-video window.

#     Preferred window:

#         event_time - PRE_EVENT_SECONDS
#         through
#         event_time + POST_EVENT_SECONDS

#     The window is then expanded where possible until it reaches
#     PROOF_DURATION_SECONDS.

#     The result is always bounded to:

#         0 <= start <= end <= source duration
#     """

#     if not math.isfinite(
#         event_time
#     ):
#         event_time = 0.0

#     if not math.isfinite(
#         duration
#     ):
#         duration = 0.0

#     duration = max(
#         0.0,
#         duration,
#     )

#     if duration <= 0.0:
#         return 0.0, 0.0

#     event_time = max(
#         0.0,
#         min(
#             event_time,
#             duration,
#         ),
#     )

#     requested_duration = min(
#         PROOF_DURATION_SECONDS,
#         duration,
#     )

#     start = max(
#         0.0,
#         event_time - PRE_EVENT_SECONDS,
#     )

#     end = min(
#         duration,
#         event_time + POST_EVENT_SECONDS,
#     )

#     current_duration = end - start

#     if current_duration < requested_duration:
#         missing = (
#             requested_duration
#             - current_duration
#         )

#         # First expand equally around the event.
#         before = min(
#             missing / 2.0,
#             start,
#         )

#         start -= before
#         missing -= before

#         after = min(
#             missing,
#             duration - end,
#         )

#         end += after
#         missing -= after

#         # If the source boundary prevented equal expansion,
#         # use all remaining space on the other side.
#         if missing > 0.0:
#             before = min(
#                 missing,
#                 start,
#             )

#             start -= before
#             missing -= before

#         if missing > 0.0:
#             after = min(
#                 missing,
#                 duration - end,
#             )

#             end += after

#     start = max(
#         0.0,
#         min(
#             start,
#             duration,
#         ),
#     )

#     end = max(
#         start,
#         min(
#             end,
#             duration,
#         ),
#     )

#     return start, end


# # ============================================================
# # VIDEO METADATA
# # ============================================================

# def _get_video_metadata(
#     capture: cv2.VideoCapture,
# ) -> tuple[float, int, int, int, float]:
#     """
#     Read basic video metadata.

#     Returns
#     -------
#     tuple
#         fps, width, height, total_frames, duration
#     """

#     fps = float(
#         capture.get(
#             cv2.CAP_PROP_FPS
#         )
#     )

#     if not math.isfinite(
#         fps
#     ) or fps <= 0.0:
#         fps = 25.0

#     width = int(
#         capture.get(
#             cv2.CAP_PROP_FRAME_WIDTH
#         )
#     )

#     height = int(
#         capture.get(
#             cv2.CAP_PROP_FRAME_HEIGHT
#         )
#     )

#     total_frames = int(
#         capture.get(
#             cv2.CAP_PROP_FRAME_COUNT
#         )
#     )

#     duration = (
#         total_frames / fps
#         if total_frames > 0
#         else 0.0
#     )

#     return (
#         fps,
#         width,
#         height,
#         total_frames,
#         duration,
#     )


# # ============================================================
# # PROOF PATH
# # ============================================================

# def _safe_filename_component(
#     value: str,
# ) -> str:
#     """
#     Convert an arbitrary identifier into a safe filename
#     component.
#     """

#     safe_chars: list[str] = []

#     for char in value:
#         if char.isalnum() or char in {
#             "-",
#             "_",
#             ".",
#         }:
#             safe_chars.append(char)
#         else:
#             safe_chars.append("_")

#     result = "".join(
#         safe_chars
#     ).strip("._")

#     return (
#         result
#         or "unknown"
#     )


# def get_default_proof_path(
#     video_id: str,
# ) -> Path:
#     """
#     Return a safe default proof path.
#     """

#     safe_video_id = (
#         _safe_filename_component(
#             str(video_id)
#         )
#     )

#     return (
#         PROOF_DIR
#         / f"{safe_video_id}_proof.mp4"
#     )


# # ============================================================
# # PROOF GENERATION
# # ============================================================

# def create_proof_video(
#     video_path: Path,
#     proof_path: Path,
#     event: dict[str, Any],
# ) -> dict[str, Any]:
#     """
#     Generate an annotated proof video.

#     Parameters
#     ----------
#     video_path:
#         Source video.

#     proof_path:
#         Final H.264 MP4 output path.

#     event:
#         Generator event dictionary.

#         event_time/time must be relative to the beginning of
#         video_path.

#     Returns
#     -------
#     dict
#         Proof metadata containing:

#         proof_path
#         start_time
#         end_time
#         duration
#         fps
#         width
#         height
#         frames_written
#     """

#     if not isinstance(
#         video_path,
#         Path,
#     ):
#         raise TypeError(
#             "video_path must be a pathlib.Path."
#         )

#     if not isinstance(
#         proof_path,
#         Path,
#     ):
#         raise TypeError(
#             "proof_path must be a pathlib.Path."
#         )

#     if not isinstance(
#         event,
#         dict,
#     ):
#         raise TypeError(
#             "event must be a dictionary."
#         )

#     # --------------------------------------------------------
#     # Validate source
#     # --------------------------------------------------------

#     try:
#         if not video_path.exists():
#             raise FileNotFoundError(
#                 f"Source video does not exist: "
#                 f"{video_path}"
#             )

#         if not video_path.is_file():
#             raise ValueError(
#                 f"Source video is not a file: "
#                 f"{video_path}"
#             )

#         if video_path.stat().st_size <= 0:
#             raise ValueError(
#                 f"Source video is empty: "
#                 f"{video_path}"
#             )

#     except OSError as exc:
#         raise RuntimeError(
#             f"Unable to inspect source video "
#             f"{video_path}: {exc}"
#         ) from exc

#     # --------------------------------------------------------
#     # Prepare output directory
#     # --------------------------------------------------------

#     proof_path.parent.mkdir(
#         parents=True,
#         exist_ok=True,
#     )

#     # Use a process-specific temporary file.
#     raw_path = proof_path.with_name(
#         f"{proof_path.stem}"
#         f"_raw_{os.getpid()}.mp4"
#     )

#     capture = cv2.VideoCapture(
#         str(video_path)
#     )

#     if not capture.isOpened():
#         raise RuntimeError(
#             f"Unable to open source video: "
#             f"{video_path}"
#         )

#     writer: cv2.VideoWriter | None = None

#     written_frames = 0

#     try:
#         # ----------------------------------------------------
#         # Read source metadata
#         # ----------------------------------------------------

#         (
#             fps,
#             width,
#             height,
#             total_frames,
#             source_duration,
#         ) = _get_video_metadata(
#             capture
#         )

#         if width <= 0 or height <= 0:
#             raise RuntimeError(
#                 f"Invalid video dimensions: "
#                 f"{width}x{height}"
#             )

#         if total_frames <= 0:
#             raise RuntimeError(
#                 "Source video contains no readable "
#                 "frame count."
#             )

#         if source_duration <= 0.0:
#             raise RuntimeError(
#                 "Source video duration is invalid."
#             )

#         # ----------------------------------------------------
#         # Calculate proof window
#         # ----------------------------------------------------

#         event_time = _safe_event_time(
#             event
#         )

#         start_time, end_time = (
#             calculate_proof_window(
#                 event_time,
#                 source_duration,
#             )
#         )

#         # ----------------------------------------------------
#         # Convert time to frame range
#         # ----------------------------------------------------

#         start_frame = max(
#             0,
#             int(
#                 math.floor(
#                     start_time * fps
#                 )
#             ),
#         )

#         end_frame_exclusive = min(
#             total_frames,
#             max(
#                 start_frame + 1,
#                 int(
#                     math.ceil(
#                         end_time * fps
#                     )
#                 ),
#             ),
#         )

#         if (
#             end_frame_exclusive
#             <= start_frame
#         ):
#             raise RuntimeError(
#                 "Calculated proof-video frame "
#                 "range is invalid."
#             )

#         # ----------------------------------------------------
#         # Seek to beginning of proof window
#         # ----------------------------------------------------

#         capture.set(
#             cv2.CAP_PROP_POS_FRAMES,
#             start_frame,
#         )

#         actual_start_frame = int(
#             capture.get(
#                 cv2.CAP_PROP_POS_FRAMES
#             )
#         )

#         if (
#             actual_start_frame
#             != start_frame
#         ):
#             print(
#                 "[EVIDENCE-GENERATOR] Warning: "
#                 "video backend may not have sought "
#                 f"exactly to frame {start_frame}; "
#                 f"reported frame={actual_start_frame}."
#             )

#         # ----------------------------------------------------
#         # Temporary writer
#         # ----------------------------------------------------

#         fourcc = cv2.VideoWriter_fourcc(
#             *"mp4v"
#         )

#         writer = cv2.VideoWriter(
#             str(raw_path),
#             fourcc,
#             fps,
#             (width, height),
#         )

#         if not writer.isOpened():
#             raise RuntimeError(
#                 f"Unable to create temporary "
#                 f"proof video: {raw_path}"
#             )

#         # ----------------------------------------------------
#         # Generate annotated proof video
#         # ----------------------------------------------------

#         current_frame = start_frame

#         while (
#             current_frame
#             < end_frame_exclusive
#         ):
#             success, frame = (
#                 capture.read()
#             )

#             if not success:
#                 print(
#                     "[EVIDENCE-GENERATOR] "
#                     f"Frame read stopped at "
#                     f"{current_frame}; "
#                     "ending proof generation."
#                 )
#                 break

#             people = detect_people(
#                 frame
#             )

#             draw_people(
#                 frame,
#                 people,
#             )

#             proof_event = dict(
#                 event
#             )

#             proof_event[
#                 "after_person_count"
#             ] = len(people)

#             draw_proof_header(
#                 frame,
#                 proof_event,
#             )

#             current_time = (
#                 current_frame / fps
#             )

#             # ------------------------------------------------
#             # Event marker
#             # ------------------------------------------------

#             if abs(
#                 current_time - event_time
#             ) <= 0.5:

#                 marker_top = min(
#                     110,
#                     max(
#                         0,
#                         height - 1,
#                     ),
#                 )

#                 marker_bottom = min(
#                     155,
#                     max(
#                         0,
#                         height - 1,
#                     ),
#                 )

#                 cv2.rectangle(
#                     frame,
#                     (0, marker_top),
#                     (
#                         max(
#                             0,
#                             width - 1,
#                         ),
#                         marker_bottom,
#                     ),
#                     (0, 0, 255),
#                     3,
#                 )

#                 cv2.putText(
#                     frame,
#                     "EVENT",
#                     (
#                         10,
#                         min(
#                             max(
#                                 20,
#                                 height - 10,
#                             ),
#                             marker_top + 32,
#                         ),
#                     ),
#                     cv2.FONT_HERSHEY_SIMPLEX,
#                     0.8,
#                     (0, 0, 255),
#                     2,
#                     cv2.LINE_AA,
#                 )

#             writer.write(
#                 frame
#             )

#             written_frames += 1
#             current_frame += 1

#         if written_frames <= 0:
#             raise RuntimeError(
#                 "No frames were written to "
#                 "the proof video."
#             )

#     finally:
#         # ----------------------------------------------------
#         # Always release OpenCV resources
#         # ----------------------------------------------------

#         if writer is not None:
#             writer.release()

#         capture.release()

#     # --------------------------------------------------------
#     # Validate temporary output
#     # --------------------------------------------------------

#     try:
#         if not raw_path.exists():
#             raise RuntimeError(
#                 f"Temporary proof video was not created: "
#                 f"{raw_path}"
#             )

#         if raw_path.stat().st_size <= 0:
#             raise RuntimeError(
#                 f"Temporary proof video is empty: "
#                 f"{raw_path}"
#             )

#         # ----------------------------------------------------
#         # Convert to H.264 MP4
#         # ----------------------------------------------------

#         convert_to_h264(
#             raw_path,
#             proof_path,
#         )

#         if not proof_path.exists():
#             raise RuntimeError(
#                 f"H.264 proof video was not created: "
#                 f"{proof_path}"
#             )

#         if proof_path.stat().st_size <= 0:
#             raise RuntimeError(
#                 f"H.264 proof video is empty: "
#                 f"{proof_path}"
#             )

#     finally:
#         # ----------------------------------------------------
#         # Always remove temporary raw file
#         # ----------------------------------------------------

#         try:
#             if raw_path.exists():
#                 raw_path.unlink()
#         except OSError as cleanup_error:
#             print(
#                 "[EVIDENCE-GENERATOR] Failed to "
#                 f"remove temporary proof file "
#                 f"{raw_path}: {cleanup_error}"
#             )

#     # --------------------------------------------------------
#     # Metadata
#     # --------------------------------------------------------

#     actual_duration = (
#         written_frames / fps
#     )

#     actual_end_time = min(
#         source_duration,
#         start_time + actual_duration,
#     )

#     return {
#         "proof_path": str(
#             proof_path
#         ),
#         "start_time": float(
#             start_time
#         ),
#         "end_time": float(
#             actual_end_time
#         ),
#         "duration": float(
#             actual_duration
#         ),
#         "fps": float(
#             fps
#         ),
#         "width": int(
#             width
#         ),
#         "height": int(
#             height
#         ),
#         "frames_written": int(
#             written_frames
#         ),
#     }


# # ============================================================
# # PUBLIC API
# # ============================================================

# __all__ = [
#     "calculate_proof_window",
#     "create_proof_video",
#     "detect_people",
#     "draw_people",
#     "draw_proof_header",
#     "get_default_proof_path",
# ]















"""
Evidence/proof-video generator for the CCTV AI surveillance platform.

Responsibilities
----------------

- Validate the source video.
- Determine the proof-video time window.
- Generate an annotated temporary proof video.
- Convert the temporary video to H.264 MP4.
- Return evidence metadata.

This module does NOT:

- consume Redis messages
- create incidents
- publish Redis events
- perform alert generation
- perform tracking
- perform LLM reasoning
"""

from __future__ import annotations

import math
import os
import threading
from pathlib import Path
from typing import Any, Optional

import cv2
from ultralytics import YOLO

from agents.evidence.ffmpeg import convert_to_h264


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "data"
EVIDENCE_ROOT = DATA_ROOT / "evidence"
PROOF_DIR = DATA_ROOT / "proof_videos"

EVIDENCE_ROOT.mkdir(
    parents=True,
    exist_ok=True,
)

PROOF_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# ENVIRONMENT HELPERS
# ============================================================

def _env_float(
    name: str,
    default: float,
    *,
    minimum: Optional[float] = None,
) -> float:
    """
    Read a floating-point environment variable safely.
    """
    raw = os.getenv(name)

    if raw is None or not raw.strip():
        value = default
    else:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            print(
                f"[EVIDENCE-GENERATOR] Invalid float for "
                f"{name}={raw!r}; using {default}."
            )
            value = default

    if not math.isfinite(value):
        print(
            f"[EVIDENCE-GENERATOR] Non-finite value for "
            f"{name}={raw!r}; using {default}."
        )
        value = default

    if minimum is not None and value < minimum:
        print(
            f"[EVIDENCE-GENERATOR] {name}={value} is below "
            f"minimum {minimum}; using {minimum}."
        )
        value = minimum

    return value


def _event_window_seconds(
    event: dict[str, Any],
) -> tuple[float, float]:
    """
    Resolve the requested proof-video pre/post window.

    Priority:

    1. event["evidence_request"]["pre_seconds"]
       event["evidence_request"]["post_seconds"]

    2. event["pre_seconds"]
       event["post_seconds"]

    3. environment configuration

    The Incident Agent normally sends the values through the
    nested evidence_request object.
    """

    evidence_request = event.get(
        "evidence_request"
    )

    if not isinstance(
        evidence_request,
        dict,
    ):
        evidence_request = {}

    raw_pre = evidence_request.get(
        "pre_seconds",
        event.get(
            "pre_seconds",
            None,
        ),
    )

    raw_post = evidence_request.get(
        "post_seconds",
        event.get(
            "post_seconds",
            None,
        ),
    )

    def _parse(
        raw_value: Any,
        fallback: float,
        field_name: str,
    ) -> float:
        if raw_value is None:
            return fallback

        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            print(
                "[EVIDENCE-GENERATOR] Invalid "
                f"{field_name}={raw_value!r}; "
                f"using {fallback}."
            )
            return fallback

        if not math.isfinite(value):
            print(
                "[EVIDENCE-GENERATOR] Non-finite "
                f"{field_name}={raw_value!r}; "
                f"using {fallback}."
            )
            return fallback

        return max(
            0.0,
            value,
        )

    pre_seconds = _parse(
        raw_pre,
        PRE_EVENT_SECONDS,
        "pre_seconds",
    )

    post_seconds = _parse(
        raw_post,
        POST_EVENT_SECONDS,
        "post_seconds",
    )

    return (
        pre_seconds,
        post_seconds,
    )


# ============================================================
# CONFIGURATION
# ============================================================

CONFIDENCE_THRESHOLD = _env_float(
    "EVIDENCE_CONFIDENCE",
    0.40,
    minimum=0.0,
)

# These defaults intentionally match the Incident Agent's
# default evidence request.
#
# The actual per-event values from evidence_request take
# priority inside _event_window_seconds().

PRE_EVENT_SECONDS = _env_float(
    "EVIDENCE_PRE_EVENT_SECONDS",
    10.0,
    minimum=0.0,
)

POST_EVENT_SECONDS = _env_float(
    "EVIDENCE_POST_EVENT_SECONDS",
    10.0,
    minimum=0.0,
)

PROOF_DURATION_SECONDS = _env_float(
    "EVIDENCE_PROOF_DURATION_SECONDS",
    10.0,
    minimum=1.0,
)

MODEL_PATH = (
    os.getenv(
        "EVIDENCE_YOLO_MODEL",
        str(PROJECT_ROOT / "yolo11n.pt"),
    ).strip()
    or str(PROJECT_ROOT / "yolo11n.pt")
)


# ============================================================
# MODEL
# ============================================================

_MODEL: YOLO | None = None
_MODEL_LOCK = threading.Lock()


def get_model() -> YOLO:
    """
    Lazily load the YOLO model.

    Model initialization is protected by a lock so multiple
    threads cannot initialize the global model simultaneously.
    """
    global _MODEL

    if _MODEL is not None:
        return _MODEL

    with _MODEL_LOCK:
        if _MODEL is not None:
            return _MODEL

        model_path = Path(
            MODEL_PATH
        ).expanduser()

        if not model_path.is_file():
            raise FileNotFoundError(
                f"Evidence YOLO model was not found: "
                f"{model_path}"
            )

        print(
            f"[EVIDENCE-GENERATOR] Loading YOLO model: "
            f"{model_path}"
        )

        _MODEL = YOLO(
            str(model_path)
        )

        print(
            "[EVIDENCE-GENERATOR] YOLO model loaded."
        )

        return _MODEL


# ============================================================
# PERSON DETECTION
# ============================================================

def detect_people(
    frame: Any,
) -> list[tuple[int, int, int, int, float]]:
    """
    Detect people in one frame.

    Returns
    -------
    list[tuple[int, int, int, int, float]]
        Each detection is:

        (x1, y1, x2, y2, confidence)
    """
    model = get_model()

    results = model.predict(
        frame,
        verbose=False,
        conf=CONFIDENCE_THRESHOLD,
        classes=[0],
    )

    detections: list[
        tuple[int, int, int, int, float]
    ] = []

    for result in results:
        boxes = getattr(
            result,
            "boxes",
            None,
        )

        if boxes is None:
            continue

        for box in boxes:
            try:
                cls_value = float(
                    box.cls[0].item()
                )

                confidence = float(
                    box.conf[0].item()
                )

                coordinates = (
                    box.xyxy[0].tolist()
                )

                if cls_value != 0.0:
                    continue

                if not math.isfinite(
                    confidence
                ):
                    continue

                if len(coordinates) != 4:
                    continue

                x1, y1, x2, y2 = (
                    int(round(value))
                    for value in coordinates
                )

                if x2 <= x1 or y2 <= y1:
                    continue

                detections.append(
                    (
                        x1,
                        y1,
                        x2,
                        y2,
                        confidence,
                    )
                )

            except Exception as error:
                print(
                    "[EVIDENCE-GENERATOR] "
                    f"Skipping malformed detection: {error}"
                )

    return detections


# ============================================================
# DRAWING
# ============================================================

def draw_people(
    frame: Any,
    people: list[tuple[int, int, int, int, float]],
) -> None:
    """
    Draw person bounding boxes and confidence values.
    """
    for (
        x1,
        y1,
        x2,
        y2,
        confidence,
    ) in people:
        cv2.rectangle(
            frame,
            (x1, y1),
            (x2, y2),
            (0, 255, 0),
            2,
        )

        label = (
            f"Person {confidence:.2f}"
        )

        cv2.putText(
            frame,
            label,
            (
                x1,
                max(
                    20,
                    y1 - 8,
                ),
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )


# ============================================================
# EVENT HELPERS
# ============================================================

def _safe_event_time(
    event: dict[str, Any],
) -> float:
    """
    Extract event time from supported event representations.

    The returned value MUST represent seconds relative to the
    beginning of the source video.
    """
    raw_value = event.get(
        "event_time",
        event.get(
            "time",
            event.get(
                "timestamp_seconds",
                0.0,
            ),
        ),
    )

    try:
        value = float(raw_value)
    except (
        TypeError,
        ValueError,
    ):
        return 0.0

    if not math.isfinite(value):
        return 0.0

    return value


def _safe_event_type(
    event: dict[str, Any],
) -> str:
    """
    Extract event type from canonical or legacy fields.
    """
    value = event.get(
        "event_type",
        event.get(
            "type",
            "UNKNOWN_EVENT",
        ),
    )

    text = str(value).strip()

    return (
        text
        or "UNKNOWN_EVENT"
    )


def _safe_person_count(
    event: dict[str, Any],
) -> int:
    """
    Safely extract the displayed person count.
    """
    value = event.get(
        "after_person_count",
        event.get(
            "person_count",
            0,
        ),
    )

    try:
        count = int(value)
    except (
        TypeError,
        ValueError,
    ):
        return 0

    return max(
        0,
        count,
    )


# ============================================================
# PROOF HEADER
# ============================================================

def draw_proof_header(
    frame: Any,
    event: dict[str, Any],
) -> None:
    """
    Draw forensic context at the top of the frame.
    """
    height, width = frame.shape[:2]

    header_height = min(
        90,
        max(
            1,
            height,
        ),
    )

    cv2.rectangle(
        frame,
        (0, 0),
        (
            max(
                0,
                width - 1,
            ),
            header_height,
        ),
        (0, 0, 0),
        -1,
    )

    event_type = _safe_event_type(
        event
    )

    person_count = _safe_person_count(
        event
    )

    event_time = _safe_event_time(
        event
    )

    camera_id = str(
        event.get(
            "camera_id",
            "UNKNOWN_CAMERA",
        )
    ).strip()

    if not camera_id:
        camera_id = "UNKNOWN_CAMERA"

    line_one = (
        f"EVENT: {event_type} | "
        f"CAMERA: {camera_id}"
    )

    line_two = (
        f"PERSONS: {person_count} | "
        f"EVENT TIME: {event_time:.2f}s"
    )

    cv2.putText(
        frame,
        line_one,
        (10, 32),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.58,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )

    cv2.putText(
        frame,
        line_two,
        (10, 65),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )


# ============================================================
# PROOF WINDOW
# ============================================================

def calculate_proof_window(
    event_time: float,
    duration: float,
    *,
    pre_seconds: Optional[float] = None,
    post_seconds: Optional[float] = None,
) -> tuple[float, float]:
    """
    Calculate a bounded proof-video window.

    Preferred window:

        event_time - pre_seconds
        through
        event_time + post_seconds

    The window is then expanded where possible until it reaches
    PROOF_DURATION_SECONDS.

    The result is always bounded to:

        0 <= start <= end <= source duration

    Parameters
    ----------
    event_time:
        Event time in seconds relative to the beginning of the
        source video.

    duration:
        Total source-video duration.

    pre_seconds:
        Requested footage before the event.

        If None, PRE_EVENT_SECONDS is used.

    post_seconds:
        Requested footage after the event.

        If None, POST_EVENT_SECONDS is used.
    """

    if pre_seconds is None:
        pre_seconds = PRE_EVENT_SECONDS

    if post_seconds is None:
        post_seconds = POST_EVENT_SECONDS

    if not math.isfinite(pre_seconds):
        pre_seconds = PRE_EVENT_SECONDS

    if not math.isfinite(post_seconds):
        post_seconds = POST_EVENT_SECONDS

    pre_seconds = max(
        0.0,
        pre_seconds,
    )

    post_seconds = max(
        0.0,
        post_seconds,
    )

    if not math.isfinite(event_time):
        event_time = 0.0

    if not math.isfinite(duration):
        duration = 0.0

    duration = max(
        0.0,
        duration,
    )

    if duration <= 0.0:
        return 0.0, 0.0

    event_time = max(
        0.0,
        min(
            event_time,
            duration,
        ),
    )

    requested_duration = min(
        PROOF_DURATION_SECONDS,
        duration,
    )

    start = max(
        0.0,
        event_time - pre_seconds,
    )

    end = min(
        duration,
        event_time + post_seconds,
    )

    current_duration = end - start

    if current_duration < requested_duration:
        missing = (
            requested_duration
            - current_duration
        )

        # First expand equally around the event.
        before = min(
            missing / 2.0,
            start,
        )

        start -= before
        missing -= before

        after = min(
            missing,
            duration - end,
        )

        end += after
        missing -= after

        # If the source boundary prevented equal expansion,
        # use remaining space on the other side.
        if missing > 0.0:
            before = min(
                missing,
                start,
            )

            start -= before
            missing -= before

        if missing > 0.0:
            after = min(
                missing,
                duration - end,
            )

            end += after

    start = max(
        0.0,
        min(
            start,
            duration,
        ),
    )

    end = max(
        start,
        min(
            end,
            duration,
        ),
    )

    return (
        start,
        end,
    )


# ============================================================
# VIDEO METADATA
# ============================================================

def _get_video_metadata(
    capture: cv2.VideoCapture,
) -> tuple[float, int, int, int, float]:
    """
    Read basic video metadata.

    Returns
    -------
    tuple
        fps,
        width,
        height,
        total_frames,
        duration
    """
    fps = float(
        capture.get(
            cv2.CAP_PROP_FPS
        )
    )

    if not math.isfinite(
        fps
    ) or fps <= 0.0:
        fps = 25.0

    width = int(
        capture.get(
            cv2.CAP_PROP_FRAME_WIDTH
        )
    )

    height = int(
        capture.get(
            cv2.CAP_PROP_FRAME_HEIGHT
        )
    )

    total_frames = int(
        capture.get(
            cv2.CAP_PROP_FRAME_COUNT
        )
    )

    duration = (
        total_frames / fps
        if total_frames > 0
        else 0.0
    )

    return (
        fps,
        width,
        height,
        total_frames,
        duration,
    )


# ============================================================
# PROOF PATH
# ============================================================

def _safe_filename_component(
    value: str,
) -> str:
    """
    Convert an arbitrary identifier into a safe filename
    component.
    """
    safe_chars: list[str] = []

    for char in value:
        if char.isalnum() or char in {
            "-",
            "_",
            ".",
        }:
            safe_chars.append(char)
        else:
            safe_chars.append("_")

    result = "".join(
        safe_chars
    ).strip("._")

    return (
        result
        or "unknown"
    )


def get_default_proof_path(
    video_id: str,
) -> Path:
    """
    Return a safe default proof path.
    """
    safe_video_id = (
        _safe_filename_component(
            str(video_id)
        )
    )

    return (
        PROOF_DIR
        / f"{safe_video_id}_proof.mp4"
    )


# ============================================================
# PROOF GENERATION
# ============================================================

def create_proof_video(
    video_path: Path,
    proof_path: Path,
    event: dict[str, Any],
) -> dict[str, Any]:
    """
    Generate an annotated proof video.

    Parameters
    ----------
    video_path:
        Source video.

    proof_path:
        Final H.264 MP4 output path.

    event:
        Generator event dictionary.

        event_time/time MUST be relative to the beginning of
        video_path.

        Optional evidence_request values:

            evidence_request.pre_seconds
            evidence_request.post_seconds

        These values control the requested proof window.

    Returns
    -------
    dict
        Proof metadata containing:

        proof_path
        start_time
        end_time
        duration
        fps
        width
        height
        frames_written
        event_time
        pre_seconds
        post_seconds
    """

    if not isinstance(
        video_path,
        Path,
    ):
        raise TypeError(
            "video_path must be a pathlib.Path."
        )

    if not isinstance(
        proof_path,
        Path,
    ):
        raise TypeError(
            "proof_path must be a pathlib.Path."
        )

    if not isinstance(
        event,
        dict,
    ):
        raise TypeError(
            "event must be a dictionary."
        )

    # --------------------------------------------------------
    # Resolve requested evidence window
    # --------------------------------------------------------

    pre_seconds, post_seconds = (
        _event_window_seconds(
            event
        )
    )

    # --------------------------------------------------------
    # Validate source
    # --------------------------------------------------------

    try:
        if not video_path.exists():
            raise FileNotFoundError(
                f"Source video does not exist: "
                f"{video_path}"
            )

        if not video_path.is_file():
            raise ValueError(
                f"Source video is not a file: "
                f"{video_path}"
            )

        if video_path.stat().st_size <= 0:
            raise ValueError(
                f"Source video is empty: "
                f"{video_path}"
            )

    except OSError as exc:
        raise RuntimeError(
            f"Unable to inspect source video "
            f"{video_path}: {exc}"
        ) from exc

    # --------------------------------------------------------
    # Prepare output directory
    # --------------------------------------------------------

    proof_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Use a process-specific temporary file.
    raw_path = proof_path.with_name(
        f"{proof_path.stem}"
        f"_raw_{os.getpid()}.mp4"
    )

    capture = cv2.VideoCapture(
        str(video_path)
    )

    if not capture.isOpened():
        raise RuntimeError(
            f"Unable to open source video: "
            f"{video_path}"
        )

    writer: cv2.VideoWriter | None = None
    written_frames = 0

    try:
        # ----------------------------------------------------
        # Read source metadata
        # ----------------------------------------------------

        (
            fps,
            width,
            height,
            total_frames,
            source_duration,
        ) = _get_video_metadata(
            capture
        )

        if width <= 0 or height <= 0:
            raise RuntimeError(
                f"Invalid video dimensions: "
                f"{width}x{height}"
            )

        if total_frames <= 0:
            raise RuntimeError(
                "Source video contains no readable "
                "frame count."
            )

        if source_duration <= 0.0:
            raise RuntimeError(
                "Source video duration is invalid."
            )

        # ----------------------------------------------------
        # Calculate proof window
        # ----------------------------------------------------

        event_time = _safe_event_time(
            event
        )

        start_time, end_time = (
            calculate_proof_window(
                event_time,
                source_duration,
                pre_seconds=pre_seconds,
                post_seconds=post_seconds,
            )
        )

        print(
            "[EVIDENCE-GENERATOR] Proof window "
            f"event_time={event_time:.3f}s "
            f"pre={pre_seconds:.3f}s "
            f"post={post_seconds:.3f}s "
            f"start={start_time:.3f}s "
            f"end={end_time:.3f}s "
            f"duration={end_time - start_time:.3f}s"
        )

        # ----------------------------------------------------
        # Convert time to frame range
        # ----------------------------------------------------

        start_frame = max(
            0,
            int(
                math.floor(
                    start_time * fps
                )
            ),
        )

        end_frame_exclusive = min(
            total_frames,
            max(
                start_frame + 1,
                int(
                    math.ceil(
                        end_time * fps
                    )
                ),
            ),
        )

        if (
            end_frame_exclusive
            <= start_frame
        ):
            raise RuntimeError(
                "Calculated proof-video frame "
                "range is invalid."
            )

        # ----------------------------------------------------
        # Seek to beginning of proof window
        # ----------------------------------------------------

        capture.set(
            cv2.CAP_PROP_POS_FRAMES,
            start_frame,
        )

        actual_start_frame = int(
            capture.get(
                cv2.CAP_PROP_POS_FRAMES
            )
        )

        if (
            actual_start_frame
            != start_frame
        ):
            print(
                "[EVIDENCE-GENERATOR] Warning: "
                "video backend may not have sought "
                f"exactly to frame {start_frame}; "
                f"reported frame={actual_start_frame}."
            )

        # ----------------------------------------------------
        # Temporary writer
        # ----------------------------------------------------

        fourcc = cv2.VideoWriter_fourcc(
            *"mp4v"
        )

        writer = cv2.VideoWriter(
            str(raw_path),
            fourcc,
            fps,
            (width, height),
        )

        if not writer.isOpened():
            raise RuntimeError(
                f"Unable to create temporary "
                f"proof video: {raw_path}"
            )

        # ----------------------------------------------------
        # Generate annotated proof video
        # ----------------------------------------------------

        current_frame = start_frame

        while (
            current_frame
            < end_frame_exclusive
        ):
            success, frame = (
                capture.read()
            )

            if not success:
                print(
                    "[EVIDENCE-GENERATOR] "
                    f"Frame read stopped at "
                    f"{current_frame}; "
                    "ending proof generation."
                )
                break

            people = detect_people(
                frame
            )

            draw_people(
                frame,
                people,
            )

            proof_event = dict(
                event
            )

            proof_event[
                "after_person_count"
            ] = len(people)

            draw_proof_header(
                frame,
                proof_event,
            )

            current_time = (
                current_frame / fps
            )

            # ------------------------------------------------
            # Event marker
            # ------------------------------------------------

            if abs(
                current_time - event_time
            ) <= 0.5:
                marker_top = min(
                    110,
                    max(
                        0,
                        height - 1,
                    ),
                )

                marker_bottom = min(
                    155,
                    max(
                        0,
                        height - 1,
                    ),
                )

                cv2.rectangle(
                    frame,
                    (0, marker_top),
                    (
                        max(
                            0,
                            width - 1,
                        ),
                        marker_bottom,
                    ),
                    (0, 0, 255),
                    3,
                )

                cv2.putText(
                    frame,
                    "EVENT",
                    (
                        10,
                        min(
                            max(
                                20,
                                height - 10,
                            ),
                            marker_top + 32,
                        ),
                    ),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 0, 255),
                    2,
                    cv2.LINE_AA,
                )

            writer.write(
                frame
            )

            written_frames += 1
            current_frame += 1

        if written_frames <= 0:
            raise RuntimeError(
                "No frames were written to "
                "the proof video."
            )

    finally:
        # ----------------------------------------------------
        # Always release OpenCV resources
        # ----------------------------------------------------

        if writer is not None:
            writer.release()

        capture.release()

    # --------------------------------------------------------
    # Validate temporary output
    # --------------------------------------------------------

    try:
        if not raw_path.exists():
            raise RuntimeError(
                f"Temporary proof video was not created: "
                f"{raw_path}"
            )

        if raw_path.stat().st_size <= 0:
            raise RuntimeError(
                f"Temporary proof video is empty: "
                f"{raw_path}"
            )

        # ----------------------------------------------------
        # Convert to H.264 MP4
        # ----------------------------------------------------

        convert_to_h264(
            raw_path,
            proof_path,
        )

        if not proof_path.exists():
            raise RuntimeError(
                f"H.264 proof video was not created: "
                f"{proof_path}"
            )

        if proof_path.stat().st_size <= 0:
            raise RuntimeError(
                f"H.264 proof video is empty: "
                f"{proof_path}"
            )

    finally:
        # ----------------------------------------------------
        # Always remove temporary raw file
        # ----------------------------------------------------

        try:
            if raw_path.exists():
                raw_path.unlink()

        except OSError as cleanup_error:
            print(
                "[EVIDENCE-GENERATOR] Failed to "
                f"remove temporary proof file "
                f"{raw_path}: {cleanup_error}"
            )

    # --------------------------------------------------------
    # Metadata
    # --------------------------------------------------------

    actual_duration = (
        written_frames / fps
    )

    actual_end_time = min(
        source_duration,
        start_time + actual_duration,
    )

    return {
        "proof_path": str(
            proof_path
        ),
        "start_time": float(
            start_time
        ),
        "end_time": float(
            actual_end_time
        ),
        "duration": float(
            actual_duration
        ),
        "fps": float(
            fps
        ),
        "width": int(
            width
        ),
        "height": int(
            height
        ),
        "frames_written": int(
            written_frames
        ),
        "event_time": float(
            event_time
        ),
        "pre_seconds": float(
            pre_seconds
        ),
        "post_seconds": float(
            post_seconds
        ),
    }


# ============================================================
# PUBLIC API
# ============================================================

__all__ = [
    "calculate_proof_window",
    "create_proof_video",
    "detect_people",
    "draw_people",
    "draw_proof_header",
    "get_default_proof_path",
]
