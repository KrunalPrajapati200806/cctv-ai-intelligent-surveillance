# # """
# # Rolling live evidence buffer for the CCTV AI surveillance platform.

# # Responsibilities
# # ----------------
# # - Continuously record successful camera frames.
# # - Store footage as short per-camera MP4 segments.
# # - Maintain a bounded rolling history.
# # - Delete expired segments automatically.
# # - Maintain a lightweight JSON manifest describing segments.
# # - Keep evidence recording isolated from detection/inference failures.

# # This module does NOT:
# # - run YOLO
# # - publish Redis events
# # - create incidents
# # - generate final proof videos
# # - perform LLM reasoning

# # The Evidence Agent can later consume the segment manifest to assemble
# # pre-event + post-event footage around an incident timestamp.
# # """

# # from __future__ import annotations

# # import json
# # import os
# # import time
# # import uuid
# # from collections import deque
# # from datetime import datetime, timezone
# # from pathlib import Path
# # from typing import Any

# # import cv2


# # # ============================================================
# # # HELPERS
# # # ============================================================


# # def parse_positive_float(
# #     name: str,
# #     default: float,
# # ) -> float:
# #     raw = os.getenv(name, str(default))

# #     try:
# #         value = float(raw)
# #     except (TypeError, ValueError):
# #         return default

# #     if value <= 0:
# #         return default

# #     return value


# # def parse_positive_int(
# #     name: str,
# #     default: int,
# # ) -> int:
# #     raw = os.getenv(name, str(default))

# #     try:
# #         value = int(raw)
# #     except (TypeError, ValueError):
# #         return default

# #     if value <= 0:
# #         return default

# #     return value


# # def utc_timestamp() -> str:
# #     return (
# #         datetime.now(timezone.utc)
# #         .isoformat()
# #         .replace("+00:00", "Z")
# #     )


# # def safe_camera_directory_name(
# #     camera_id: str,
# # ) -> str:
# #     allowed = (
# #         "abcdefghijklmnopqrstuvwxyz"
# #         "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
# #         "0123456789"
# #         "-_."
# #     )

# #     result = "".join(
# #         character
# #         if character in allowed
# #         else "_"
# #         for character in str(camera_id)
# #     )

# #     return result[:120] or "camera"


# # # ============================================================
# # # ROLLING EVIDENCE BUFFER
# # # ============================================================


# # class RollingEvidenceBuffer:
# #     """
# #     Per-camera rolling video segment buffer.

# #     Example directory:

# #         data/evidence/
# #             CAM01/
# #                 latest.jpg
# #                 buffer/
# #                     segment_1757234400_001.mp4
# #                     segment_1757234402_002.mp4
# #                     segment_1757234404_003.mp4
# #                     manifest.json

# #     The buffer continuously records short MP4 segments.

# #     Old segments are removed once they fall outside the configured
# #     retention window.
# #     """

# #     def __init__(
# #         self,
# #         camera_id: str,
# #         output_dir: str | Path,
# #         *,
# #         segment_seconds: float | None = None,
# #         retention_seconds: float | None = None,
# #         fps: float | None = None,
# #     ) -> None:
# #         self.camera_id = str(camera_id).strip()

# #         if not self.camera_id:
# #             raise ValueError(
# #                 "camera_id is required for RollingEvidenceBuffer."
# #             )

# #         self.output_dir = Path(output_dir)

# #         self.buffer_dir = (
# #             self.output_dir / "buffer"
# #         )

# #         self.buffer_dir.mkdir(
# #             parents=True,
# #             exist_ok=True,
# #         )

# #         self.manifest_path = (
# #             self.buffer_dir / "manifest.json"
# #         )

# #         self.segment_seconds = (
# #             segment_seconds
# #             if segment_seconds is not None
# #             else parse_positive_float(
# #                 "EVIDENCE_SEGMENT_SECONDS",
# #                 5.0,
# #             )
# #         )

# #         self.retention_seconds = (
# #             retention_seconds
# #             if retention_seconds is not None
# #             else parse_positive_float(
# #                 "EVIDENCE_RETENTION_SECONDS",
# #                 60.0,
# #             )
# #         )

# #         self.fps = (
# #             fps
# #             if fps is not None
# #             else parse_positive_float(
# #                 "EVIDENCE_FPS",
# #                 20.0,
# #             )
# #         )

# #         if self.retention_seconds < self.segment_seconds:
# #             self.retention_seconds = (
# #                 self.segment_seconds * 2
# #             )

# #         self.max_segments = max(
# #             2,
# #             int(
# #                 self.retention_seconds
# #                 / self.segment_seconds
# #             )
# #             + 3,
# #         )

# #         # Current OpenCV writer.
# #         self.writer: cv2.VideoWriter | None = None

# #         # Current segment state.
# #         self.current_segment_path: Path | None = None
# #         self.current_segment_started_at: float | None = None
# #         self.current_segment_started_timestamp: str | None = None
# #         self.current_segment_frame_count = 0
# #         self.current_frame_width = 0
# #         self.current_frame_height = 0

# #         # Segment metadata kept in memory.
# #         self.segments: deque[dict[str, Any]] = deque(
# #             maxlen=max(
# #                 self.max_segments * 2,
# #                 20,
# #             )
# #         )

# #         self.segment_sequence = 0

# #         self.last_frame_timestamp: str | None = None
# #         self.last_frame_epoch: float | None = None

# #         self.enabled = True

# #         self._load_manifest()

# #     # ========================================================
# #     # MANIFEST
# #     # ========================================================

# #     def _load_manifest(self) -> None:
# #         """
# #         Recover the existing manifest after a worker restart.

# #         Invalid, stale, malformed, and zero-byte entries are ignored.
# #         """

# #         self.refresh_manifest()

# #     def _write_manifest(self) -> None:
# #         """
# #         Atomically write the current segment manifest.
# #         """

# #         temp_path: Path | None = None

# #         try:
# #             payload = {
# #                 "camera_id": self.camera_id,
# #                 "updated_at": utc_timestamp(),
# #                 "segment_seconds": self.segment_seconds,
# #                 "retention_seconds": self.retention_seconds,
# #                 "fps": self.fps,
# #                 "segments": list(
# #                     self.segments
# #                 ),
# #             }

# #             temp_path = (
# #                 self.manifest_path.with_name(
# #                     f".manifest."
# #                     f"{uuid.uuid4().hex}"
# #                     f".json"
# #                 )
# #             )

# #             with temp_path.open(
# #                 "w",
# #                 encoding="utf-8",
# #             ) as handle:
# #                 json.dump(
# #                     payload,
# #                     handle,
# #                     indent=2,
# #                 )

# #             os.replace(
# #                 temp_path,
# #                 self.manifest_path,
# #             )

# #         except Exception as error:
# #             print(
# #                 "[EvidenceBuffer] "
# #                 f"Manifest write failed for "
# #                 f"camera={self.camera_id}: "
# #                 f"{type(error).__name__}: {error}"
# #             )

# #             if temp_path is not None:
# #                 try:
# #                     if temp_path.exists():
# #                         temp_path.unlink()
# #                 except Exception:
# #                     pass

# #     # ========================================================
# #     # VIDEO CODEC
# #     # ========================================================

# #     @staticmethod
# #     def _create_writer(
# #         path: Path,
# #         fps: float,
# #         width: int,
# #         height: int,
# #     ) -> cv2.VideoWriter | None:
# #         """
# #         Create an MP4 writer.

# #         mp4v is deliberately used here because it is widely available
# #         through OpenCV on Windows. Final H.264 conversion remains the
# #         responsibility of the Evidence/FFmpeg layer.
# #         """

# #         fourcc = cv2.VideoWriter_fourcc(
# #             *"mp4v"
# #         )

# #         writer = cv2.VideoWriter(
# #             str(path),
# #             fourcc,
# #             float(fps),
# #             (
# #                 int(width),
# #                 int(height),
# #             ),
# #         )

# #         if not writer.isOpened():
# #             try:
# #                 writer.release()
# #             except Exception:
# #                 pass

# #             return None

# #         return writer

# #     # ========================================================
# #     # START SEGMENT
# #     # ========================================================

# #     def _start_segment(
# #         self,
# #         frame,
# #         frame_epoch: float,
# #         frame_timestamp: str,
# #     ) -> bool:
# #         """
# #         Start a new segment using the dimensions of the current frame.
# #         """

# #         height, width = frame.shape[:2]

# #         if width <= 0 or height <= 0:
# #             return False

# #         self.segment_sequence += 1

# #         filename = (
# #             f"segment_"
# #             f"{int(frame_epoch * 1000)}_"
# #             f"{self.segment_sequence}_"
# #             f"{uuid.uuid4().hex[:8]}"
# #             f".mp4"
# #         )

# #         path = (
# #             self.buffer_dir
# #             / filename
# #         )

# #         writer = self._create_writer(
# #             path=path,
# #             fps=self.fps,
# #             width=width,
# #             height=height,
# #         )

# #         if writer is None:
# #             print(
# #                 "[EvidenceBuffer] "
# #                 f"Could not create video writer | "
# #                 f"camera={self.camera_id} | "
# #                 f"path={path}"
# #             )

# #             return False

# #         self.writer = writer

# #         self.current_segment_path = path

# #         self.current_segment_started_at = (
# #             frame_epoch
# #         )

# #         self.current_segment_started_timestamp = (
# #             frame_timestamp
# #         )

# #         self.current_segment_frame_count = 0

# #         self.current_frame_width = width
# #         self.current_frame_height = height

# #         return True

# #     # ========================================================
# #     # FINALIZE SEGMENT
# #     # ========================================================

# #     def _finalize_segment(
# #         self,
# #         end_epoch: float | None = None,
# #         end_timestamp: str | None = None,
# #     ) -> None:
# #         """
# #         Close the current writer and register the segment.
# #         """

# #         writer = self.writer

# #         self.writer = None

# #         path = self.current_segment_path

# #         started_epoch = (
# #             self.current_segment_started_at
# #         )

# #         started_timestamp = (
# #             self.current_segment_started_timestamp
# #         )

# #         frame_count = (
# #             self.current_segment_frame_count
# #         )

# #         self.current_segment_path = None
# #         self.current_segment_started_at = None
# #         self.current_segment_started_timestamp = None
# #         self.current_segment_frame_count = 0

# #         if writer is not None:
# #             try:
# #                 writer.release()
# #             except Exception as error:
# #                 print(
# #                     "[EvidenceBuffer] "
# #                     f"Video writer release failed | "
# #                     f"camera={self.camera_id} | "
# #                     f"error={error}"
# #                 )

# #         if (
# #             path is None
# #             or started_epoch is None
# #             or frame_count <= 0
# #         ):
# #             return

# #         if not path.exists():
# #             return

# #         if end_epoch is None:
# #             end_epoch = (
# #                 started_epoch
# #                 + self.segment_seconds
# #             )

# #         if end_timestamp is None:
# #             end_timestamp = utc_timestamp()

# #         segment = {
# #             "camera_id": self.camera_id,
# #             "path": str(path),
# #             "filename": path.name,
# #             "start_epoch": float(
# #                 started_epoch
# #             ),
# #             "end_epoch": float(
# #                 end_epoch
# #             ),
# #             "start_timestamp": (
# #                 started_timestamp
# #             ),
# #             "end_timestamp": (
# #                 end_timestamp
# #             ),
# #             "frame_count": int(
# #                 frame_count
# #             ),
# #             "fps": float(self.fps),
# #             "width": int(
# #                 self.current_frame_width
# #             ),
# #             "height": int(
# #                 self.current_frame_height
# #             ),
# #             "created_at": utc_timestamp(),
# #         }

# #         self.segments.append(segment)

# #         self._write_manifest()

# #     # ========================================================
# #     # ROTATION
# #     # ========================================================

# #     def _should_rotate_segment(
# #         self,
# #         frame_epoch: float,
# #     ) -> bool:
# #         if (
# #             self.current_segment_started_at
# #             is None
# #         ):
# #             return True

# #         elapsed = (
# #             frame_epoch
# #             - self.current_segment_started_at
# #         )

# #         return elapsed >= self.segment_seconds

# #     # ========================================================
# #     # RETENTION
# #     # ========================================================

# #     def _cleanup_old_segments(
# #         self,
# #         current_epoch: float,
# #     ) -> None:
# #         """
# #         Remove segments outside the rolling retention window.
# #         """

# #         changed = False

# #         cutoff = (
# #             current_epoch
# #             - self.retention_seconds
# #         )

# #         while self.segments:
# #             segment = self.segments[0]

# #             end_epoch = float(
# #                 segment.get(
# #                     "end_epoch",
# #                     0.0,
# #                 )
# #             )

# #             path_value = segment.get(
# #                 "path"
# #             )

# #             if (
# #                 end_epoch >= cutoff
# #                 and len(self.segments)
# #                 <= self.max_segments
# #             ):
# #                 break

# #             self.segments.popleft()

# #             changed = True

# #             if path_value:
# #                 path = Path(
# #                     str(path_value)
# #                 )

# #                 try:
# #                     if path.exists():
# #                         path.unlink()
# #                 except Exception as error:
# #                     print(
# #                         "[EvidenceBuffer] "
# #                         f"Failed deleting old segment | "
# #                         f"camera={self.camera_id} | "
# #                         f"path={path} | "
# #                         f"error={error}"
# #                     )

# #         # Defensive cleanup if an unexpected number
# #         # of segments survived.
# #         while len(self.segments) > self.max_segments:
# #             segment = self.segments.popleft()

# #             changed = True

# #             path_value = segment.get(
# #                 "path"
# #             )

# #             if path_value:
# #                 path = Path(
# #                     str(path_value)
# #                 )

# #                 try:
# #                     if path.exists():
# #                         path.unlink()
# #                 except Exception:
# #                     pass

# #         if changed:
# #             self._write_manifest()

# #     # ========================================================
# #     # WRITE FRAME
# #     # ========================================================

# #     def write(
# #         self,
# #         frame,
# #         *,
# #         timestamp: str | None = None,
# #         epoch: float | None = None,
# #     ) -> bool:
# #         """
# #         Write one successfully captured camera frame.

# #         This method must be called for EVERY successfully captured
# #         frame, not only frames sent to YOLO.

# #         Returns:
# #             True  -> frame accepted by the buffer
# #             False -> buffer could not write the frame
# #         """

# #         if not self.enabled:
# #             return False

# #         try:
# #             if frame is None:
# #                 return False

# #             if not hasattr(
# #                 frame,
# #                 "shape",
# #             ):
# #                 return False

# #             if len(frame.shape) < 2:
# #                 return False

# #             frame_timestamp = (
# #                 timestamp
# #                 if timestamp
# #                 else utc_timestamp()
# #             )

# #             frame_epoch = (
# #                 float(epoch)
# #                 if epoch is not None
# #                 else time.time()
# #             )

# #             height, width = frame.shape[:2]

# #             if width <= 0 or height <= 0:
# #                 return False

# #             # Start or rotate segment.
# #             if (
# #                 self.writer is None
# #                 or self._should_rotate_segment(
# #                     frame_epoch
# #                 )
# #                 or width != self.current_frame_width
# #                 or height != self.current_frame_height
# #             ):
# #                 if self.writer is not None:
# #                     self._finalize_segment(
# #                         end_epoch=frame_epoch,
# #                         end_timestamp=frame_timestamp,
# #                     )

# #                 if not self._start_segment(
# #                     frame=frame,
# #                     frame_epoch=frame_epoch,
# #                     frame_timestamp=frame_timestamp,
# #                 ):
# #                     return False

# #             writer = self.writer

# #             if writer is None:
# #                 return False

# #             # OpenCV VideoWriter expects the same
# #             # dimensions for every frame.
# #             if (
# #                 frame.shape[1]
# #                 != self.current_frame_width
# #                 or frame.shape[0]
# #                 != self.current_frame_height
# #             ):
# #                 return False

# #             writer.write(frame)

# #             self.current_segment_frame_count += 1

# #             self.last_frame_timestamp = (
# #                 frame_timestamp
# #             )

# #             self.last_frame_epoch = (
# #                 frame_epoch
# #             )

# #             self._cleanup_old_segments(
# #                 current_epoch=frame_epoch
# #             )

# #             return True

# #         except Exception as error:
# #             print(
# #                 "[EvidenceBuffer] "
# #                 f"Frame write failed but isolated | "
# #                 f"camera={self.camera_id} | "
# #                 f"type={type(error).__name__} | "
# #                 f"error={error}"
# #             )

# #             return False

# #     # ========================================================
# #     # FORCE ROTATION
# #     # ========================================================

# #     def rotate(self) -> None:
# #         """
# #         Force the current segment to close.
# #         """

# #         try:
# #             if self.writer is not None:
# #                 end_epoch = (
# #                     self.last_frame_epoch
# #                     if self.last_frame_epoch is not None
# #                     else time.time()
# #                 )

# #                 end_timestamp = (
# #                     self.last_frame_timestamp
# #                     if self.last_frame_timestamp is not None
# #                     else utc_timestamp()
# #                 )

# #                 self._finalize_segment(
# #                     end_epoch=end_epoch,
# #                     end_timestamp=end_timestamp,
# #                 )

# #         except Exception as error:
# #             print(
# #                 "[EvidenceBuffer] "
# #                 f"Forced rotation failed | "
# #                 f"camera={self.camera_id} | "
# #                 f"error={error}"
# #             )

# #     # ========================================================
# #     # CLOSE
# #     # ========================================================

# #     def close(self) -> None:
# #         """
# #         Safely close the active segment.

# #         Does not delete the rolling history.
# #         """

# #         try:
# #             self.rotate()
# #         except Exception as error:
# #             print(
# #                 "[EvidenceBuffer] "
# #                 f"Close failed | "
# #                 f"camera={self.camera_id} | "
# #                 f"error={error}"
# #             )

# #     # ========================================================
# #     # GET SEGMENTS
# #     # ========================================================

# #     def refresh_manifest(self) -> int:
# #         """
# #         Refresh the in-memory segment index from manifest.json.

# #         The rolling buffer is normally owned by the detection process, while
# #         the Evidence Agent may keep its own long-lived buffer/manifest view.
# #         Without an explicit refresh, that long-lived view can become stale and
# #         cause valid current segments to be reported as unavailable.

# #         Returns:
# #             Number of valid manifest segments loaded into memory.
# #         """

# #         previous_segments = list(self.segments)

# #         try:
# #             if not self.manifest_path.exists():
# #                 return len(self.segments)

# #             with self.manifest_path.open(
# #                 "r",
# #                 encoding="utf-8",
# #             ) as handle:
# #                 payload = json.load(handle)

# #             if not isinstance(payload, dict):
# #                 return len(self.segments)

# #             stored_segments = payload.get("segments", [])

# #             if not isinstance(stored_segments, list):
# #                 return len(self.segments)

# #             refreshed: list[dict[str, Any]] = []

# #             for segment in stored_segments:
# #                 if not isinstance(segment, dict):
# #                     continue

# #                 path_value = segment.get("path")

# #                 if not path_value:
# #                     continue

# #                 path = Path(str(path_value))

# #                 if not path.is_absolute():
# #                     path = self.buffer_dir / path.name

# #                 if not path.exists():
# #                     continue

# #                 try:
# #                     start_epoch = float(segment.get("start_epoch"))
# #                     end_epoch = float(segment.get("end_epoch"))
# #                 except (TypeError, ValueError):
# #                     continue

# #                 if end_epoch < start_epoch:
# #                     continue

# #                 # A zero-byte file can be the currently active/incomplete
# #                 # segment. It must not be exposed as usable evidence.
# #                 try:
# #                     if path.stat().st_size <= 0:
# #                         continue
# #                 except OSError:
# #                     continue

# #                 refreshed_segment = dict(segment)
# #                 refreshed_segment["path"] = str(path)
# #                 refreshed_segment["start_epoch"] = start_epoch
# #                 refreshed_segment["end_epoch"] = end_epoch
# #                 refreshed.append(refreshed_segment)

# #             refreshed.sort(
# #                 key=lambda item: float(
# #                     item.get("start_epoch", 0.0)
# #                 )
# #             )

# #             self.segments.clear()

# #             for segment in refreshed:
# #                 self.segments.append(segment)

# #             return len(self.segments)

# #         except Exception as error:
# #             print(
# #                 "[EvidenceBuffer] "
# #                 f"Manifest refresh failed for "
# #                 f"camera={self.camera_id}: "
# #                 f"{type(error).__name__}: {error}"
# #             )

# #             # Preserve the last known-good in-memory state.
# #             self.segments.clear()
# #             for segment in previous_segments:
# #                 self.segments.append(segment)

# #             return len(self.segments)

# #     def get_segments(
# #         self,
# #     ) -> list[dict[str, Any]]:
# #         """
# #         Return currently retained segments.

# #         Refresh the manifest first so long-lived consumers do not operate
# #         against a stale in-memory snapshot.
# #         """

# #         self.refresh_manifest()

# #         return [
# #             dict(segment)
# #             for segment in self.segments
# #         ]

# #     # ========================================================
# #     # GET SEGMENTS AROUND EVENT
# #     # ========================================================

# #     def get_segments_for_event(
# #         self,
# #         event_epoch: float,
# #         *,
# #         pre_seconds: float = 10.0,
# #         post_seconds: float = 10.0,
# #     ) -> list[dict[str, Any]]:
# #         """
# #         Return retained segments overlapping:

# #             event_epoch - pre_seconds
# #             through
# #             event_epoch + post_seconds

# #         The method does not generate a final proof video.
# #         It only resolves the relevant source segments.
# #         """

# #         # IMPORTANT:
# #         # Evidence Agent and detection worker are separate long-lived
# #         # processes. Reload the manifest before every event lookup so the
# #         # selector sees segments finalized by the detection worker after the
# #         # Evidence Agent started.
# #         self.refresh_manifest()

# #         start_epoch = (
# #             float(event_epoch)
# #             - max(
# #                 0.0,
# #                 float(pre_seconds),
# #             )
# #         )

# #         end_epoch = (
# #             float(event_epoch)
# #             + max(
# #                 0.0,
# #                 float(post_seconds),
# #             )
# #         )

# #         selected: list[dict[str, Any]] = []

# #         for segment in self.segments:
# #             segment_start = float(
# #                 segment.get(
# #                     "start_epoch",
# #                     0.0,
# #                 )
# #             )

# #             segment_end = float(
# #                 segment.get(
# #                     "end_epoch",
# #                     segment_start,
# #                 )
# #             )

# #             if (
# #                 segment_end >= start_epoch
# #                 and segment_start <= end_epoch
# #             ):
# #                 selected.append(
# #                     dict(segment)
# #                 )

# #         return selected

# #     # ========================================================
# #     # STATUS
# #     # ========================================================

# #     def status(self) -> dict[str, Any]:
# #         """
# #         Return operational information useful for monitoring.
# #         """

# #         return {
# #             "camera_id": self.camera_id,
# #             "enabled": self.enabled,
# #             "segment_seconds": self.segment_seconds,
# #             "retention_seconds": self.retention_seconds,
# #             "fps": self.fps,
# #             "segment_count": len(
# #                 self.segments
# #             ),
# #             "latest_segment_start_epoch": (
# #                 float(self.segments[-1]["start_epoch"])
# #                 if self.segments
# #                 and self.segments[-1].get("start_epoch") is not None
# #                 else None
# #             ),
# #             "latest_segment_end_epoch": (
# #                 float(self.segments[-1]["end_epoch"])
# #                 if self.segments
# #                 and self.segments[-1].get("end_epoch") is not None
# #                 else None
# #             ),
# #             "active_segment": (
# #                 str(self.current_segment_path)
# #                 if self.current_segment_path
# #                 else None
# #             ),
# #             "active_frame_count": (
# #                 self.current_segment_frame_count
# #             ),
# #             "last_frame_timestamp": (
# #                 self.last_frame_timestamp
# #             ),
# #             "buffer_directory": str(
# #                 self.buffer_dir
# #             ),
# #             "manifest": str(
# #                 self.manifest_path
# #             ),
# #         }


















# """
# Rolling live evidence buffer for the CCTV AI surveillance platform.

# Responsibilities
# ----------------

# - Continuously record successful camera frames.
# - Store footage as short per-camera MP4 segments.
# - Maintain a bounded rolling history.
# - Delete expired segments automatically.
# - Maintain a lightweight JSON manifest describing segments.
# - Keep evidence recording isolated from detection/inference failures.

# This module does NOT:

# - run YOLO
# - publish Redis events
# - create incidents
# - generate final proof videos
# - perform LLM reasoning

# The Evidence Agent can later consume the segment manifest to assemble
# pre-event + post-event footage around an incident timestamp.

# Important design detail
# -----------------------

# Incoming camera frames are not necessarily delivered at exactly
# EVIDENCE_FPS.

# The rolling buffer therefore uses the incoming frame timestamps as
# wall-clock truth and duplicates the most recent valid frame when the
# incoming frame rate is lower than the configured output FPS.

# This prevents a 5-second wall-clock segment containing only 10-15
# incoming frames from becoming a 0.5-0.75 second MP4.

# The manifest timestamps describe real wall-clock coverage.
# The generated MP4 is therefore kept aligned with that coverage.
# """

# from __future__ import annotations

# import json
# import os
# import time
# import uuid
# from collections import deque
# from datetime import datetime, timezone
# from pathlib import Path
# from typing import Any

# import cv2


# # ============================================================
# # HELPERS
# # ============================================================


# def parse_positive_float(
#     name: str,
#     default: float,
# ) -> float:
#     raw = os.getenv(name, str(default))

#     try:
#         value = float(raw)
#     except (TypeError, ValueError):
#         return default

#     if value <= 0:
#         return default

#     return value


# def utc_timestamp() -> str:
#     return (
#         datetime.now(timezone.utc)
#         .isoformat()
#         .replace("+00:00", "Z")
#     )


# def safe_camera_directory_name(
#     camera_id: str,
# ) -> str:
#     allowed = (
#         "abcdefghijklmnopqrstuvwxyz"
#         "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
#         "0123456789"
#         "-_."
#     )

#     result = "".join(
#         character
#         if character in allowed
#         else "_"
#         for character in str(camera_id)
#     )

#     return result[:120] or "camera"


# # ============================================================
# # ROLLING EVIDENCE BUFFER
# # ============================================================


# class RollingEvidenceBuffer:
#     """
#     Per-camera rolling video segment buffer.

#     Example directory:

#         data/evidence/
#             CAM01/
#                 latest.jpg
#                 buffer/
#                     segment_1757234400_001.mp4
#                     segment_1757234402_002.mp4
#                     segment_1757234404_003.mp4
#                     manifest.json

#     The buffer continuously records short MP4 segments.

#     Old segments are removed once they fall outside the configured
#     retention window.
#     """

#     def __init__(
#         self,
#         camera_id: str,
#         output_dir: str | Path,
#         *,
#         segment_seconds: float | None = None,
#         retention_seconds: float | None = None,
#         fps: float | None = None,
#     ) -> None:

#         self.camera_id = str(camera_id).strip()

#         if not self.camera_id:
#             raise ValueError(
#                 "camera_id is required for RollingEvidenceBuffer."
#             )

#         self.output_dir = Path(output_dir)

#         self.buffer_dir = (
#             self.output_dir / "buffer"
#         )

#         self.buffer_dir.mkdir(
#             parents=True,
#             exist_ok=True,
#         )

#         self.manifest_path = (
#             self.buffer_dir / "manifest.json"
#         )

#         self.segment_seconds = (
#             segment_seconds
#             if segment_seconds is not None
#             else parse_positive_float(
#                 "EVIDENCE_SEGMENT_SECONDS",
#                 5.0,
#             )
#         )

#         self.retention_seconds = (
#             retention_seconds
#             if retention_seconds is not None
#             else parse_positive_float(
#                 "EVIDENCE_RETENTION_SECONDS",
#                 60.0,
#             )
#         )

#         self.fps = (
#             fps
#             if fps is not None
#             else parse_positive_float(
#                 "EVIDENCE_FPS",
#                 20.0,
#             )
#         )

#         if self.retention_seconds < self.segment_seconds:
#             self.retention_seconds = (
#                 self.segment_seconds * 2
#             )

#         self.max_segments = max(
#             2,
#             int(
#                 self.retention_seconds
#                 / self.segment_seconds
#             ) + 3,
#         )

#         # ----------------------------------------------------
#         # Current OpenCV writer
#         # ----------------------------------------------------

#         self.writer: cv2.VideoWriter | None = None

#         # ----------------------------------------------------
#         # Current segment state
#         # ----------------------------------------------------

#         self.current_segment_path: Path | None = None

#         self.current_segment_started_at: float | None = None

#         self.current_segment_started_timestamp: str | None = None

#         self.current_segment_frame_count = 0

#         self.current_frame_width = 0
#         self.current_frame_height = 0

#         # Most recent valid frame written to the current segment.
#         #
#         # This is intentionally kept so that if incoming frames
#         # arrive slower than the configured output FPS, the latest
#         # frame can be repeated to preserve wall-clock duration.
#         self.last_written_frame = None

#         self.last_written_frame_epoch: float | None = None

#         # ----------------------------------------------------
#         # Segment metadata
#         # ----------------------------------------------------

#         self.segments: deque[dict[str, Any]] = deque(
#             maxlen=max(
#                 self.max_segments * 2,
#                 20,
#             )
#         )

#         self.segment_sequence = 0

#         self.last_frame_timestamp: str | None = None
#         self.last_frame_epoch: float | None = None

#         self.enabled = True

#         self._load_manifest()

#     # ========================================================
#     # MANIFEST
#     # ========================================================

#     def _load_manifest(self) -> None:
#         """
#         Recover the existing manifest after a worker restart.

#         Invalid, stale, malformed, and zero-byte entries are ignored.
#         """

#         self.refresh_manifest()

#     def _write_manifest(self) -> None:
#         """
#         Atomically write the current segment manifest.
#         """

#         temp_path: Path | None = None

#         try:
#             payload = {
#                 "camera_id": self.camera_id,
#                 "updated_at": utc_timestamp(),
#                 "segment_seconds": self.segment_seconds,
#                 "retention_seconds": self.retention_seconds,
#                 "fps": self.fps,
#                 "segments": list(self.segments),
#             }

#             temp_path = (
#                 self.manifest_path.with_name(
#                     f".manifest."
#                     f"{uuid.uuid4().hex}"
#                     f".json"
#                 )
#             )

#             with temp_path.open(
#                 "w",
#                 encoding="utf-8",
#             ) as handle:
#                 json.dump(
#                     payload,
#                     handle,
#                     indent=2,
#                 )

#             os.replace(
#                 temp_path,
#                 self.manifest_path,
#             )

#         except Exception as error:

#             print(
#                 "[EvidenceBuffer] "
#                 f"Manifest write failed for "
#                 f"camera={self.camera_id}: "
#                 f"{type(error).__name__}: {error}"
#             )

#             if temp_path is not None:

#                 try:
#                     if temp_path.exists():
#                         temp_path.unlink()
#                 except Exception:
#                     pass

#     # ========================================================
#     # VIDEO CODEC
#     # ========================================================

#     @staticmethod
#     def _create_writer(
#         path: Path,
#         fps: float,
#         width: int,
#         height: int,
#     ) -> cv2.VideoWriter | None:
#         """
#         Create an MP4 writer.

#         mp4v is deliberately used here because it is widely available
#         through OpenCV on Windows.

#         Final H.264 conversion remains the responsibility of the
#         Evidence/FFmpeg layer.
#         """

#         fourcc = cv2.VideoWriter_fourcc(
#             *"mp4v"
#         )

#         writer = cv2.VideoWriter(
#             str(path),
#             fourcc,
#             float(fps),
#             (
#                 int(width),
#                 int(height),
#             ),
#         )

#         if not writer.isOpened():

#             try:
#                 writer.release()
#             except Exception:
#                 pass

#             return None

#         return writer

#     # ========================================================
#     # START SEGMENT
#     # ========================================================

#     def _start_segment(
#         self,
#         frame,
#         frame_epoch: float,
#         frame_timestamp: str,
#     ) -> bool:
#         """
#         Start a new segment using the dimensions of the current frame.
#         """

#         height, width = frame.shape[:2]

#         if width <= 0 or height <= 0:
#             return False

#         self.segment_sequence += 1

#         filename = (
#             f"segment_"
#             f"{int(frame_epoch * 1000)}_"
#             f"{self.segment_sequence}_"
#             f"{uuid.uuid4().hex[:8]}"
#             f".mp4"
#         )

#         path = (
#             self.buffer_dir
#             / filename
#         )

#         writer = self._create_writer(
#             path=path,
#             fps=self.fps,
#             width=width,
#             height=height,
#         )

#         if writer is None:

#             print(
#                 "[EvidenceBuffer] "
#                 f"Could not create video writer | "
#                 f"camera={self.camera_id} | "
#                 f"path={path}"
#             )

#             return False

#         self.writer = writer

#         self.current_segment_path = path

#         self.current_segment_started_at = (
#             frame_epoch
#         )

#         self.current_segment_started_timestamp = (
#             frame_timestamp
#         )

#         self.current_segment_frame_count = 0

#         self.current_frame_width = width
#         self.current_frame_height = height

#         self.last_written_frame = None
#         self.last_written_frame_epoch = None

#         return True

#     # ========================================================
#     # WRITE FRAME TO VIDEO
#     # ========================================================

#     def _write_frame_at_wall_clock(
#         self,
#         frame,
#         frame_epoch: float,
#     ) -> bool:
#         """
#         Write a frame while preserving wall-clock timing.

#         If the incoming camera frame rate is slower than the configured
#         output FPS, duplicate the previous/current frame enough times
#         to keep the generated MP4 aligned with elapsed wall-clock time.

#         Example:

#             configured FPS = 20
#             incoming frame after 0.50 sec

#         Approximately 10 output frames are written, representing
#         that 0.50 second interval.
#         """

#         writer = self.writer

#         if writer is None:
#             return False

#         if (
#             frame.shape[1] != self.current_frame_width
#             or frame.shape[0] != self.current_frame_height
#         ):
#             return False

#         # First frame of the segment.
#         if self.last_written_frame_epoch is None:

#             writer.write(frame)

#             self.current_segment_frame_count += 1

#             self.last_written_frame = frame.copy()

#             self.last_written_frame_epoch = frame_epoch

#             return True

#         elapsed = (
#             frame_epoch
#             - self.last_written_frame_epoch
#         )

#         if elapsed < 0:
#             elapsed = 0.0

#         # Number of output frames representing the elapsed
#         # wall-clock interval.
#         frame_count = max(
#             1,
#             int(
#                 round(
#                     elapsed * self.fps
#                 )
#             ),
#         )

#         # Avoid pathological duplication if a camera timestamp
#         # suddenly jumps forward.
#         max_duplicate_frames = max(
#             int(self.fps * self.segment_seconds * 2),
#             int(self.fps),
#         )

#         frame_count = min(
#             frame_count,
#             max_duplicate_frames,
#         )

#         # Use the most recent valid frame during the interval.
#         #
#         # We write the incoming frame on the final output frame.
#         # Earlier output frames use the previous frame to preserve
#         # temporal continuity.
#         previous_frame = self.last_written_frame

#         if previous_frame is None:
#             previous_frame = frame

#         for index in range(frame_count):

#             if index == frame_count - 1:
#                 output_frame = frame
#             else:
#                 output_frame = previous_frame

#             writer.write(output_frame)

#             self.current_segment_frame_count += 1

#         self.last_written_frame = frame.copy()

#         self.last_written_frame_epoch = frame_epoch

#         return True

#     # ========================================================
#     # FINALIZE SEGMENT
#     # ========================================================

#     def _finalize_segment(
#         self,
#         end_epoch: float | None = None,
#         end_timestamp: str | None = None,
#     ) -> None:
#         """
#         Close the current writer and register the segment.
#         """

#         writer = self.writer

#         self.writer = None

#         path = self.current_segment_path

#         started_epoch = (
#             self.current_segment_started_at
#         )

#         started_timestamp = (
#             self.current_segment_started_timestamp
#         )

#         frame_count = (
#             self.current_segment_frame_count
#         )

#         # IMPORTANT:
#         # Preserve dimensions BEFORE resetting the state.
#         segment_width = (
#             self.current_frame_width
#         )

#         segment_height = (
#             self.current_frame_height
#         )

#         self.current_segment_path = None

#         self.current_segment_started_at = None

#         self.current_segment_started_timestamp = None

#         self.current_segment_frame_count = 0

#         self.current_frame_width = 0
#         self.current_frame_height = 0

#         self.last_written_frame = None
#         self.last_written_frame_epoch = None

#         if writer is not None:

#             try:
#                 writer.release()

#             except Exception as error:

#                 print(
#                     "[EvidenceBuffer] "
#                     f"Video writer release failed | "
#                     f"camera={self.camera_id} | "
#                     f"error={error}"
#                 )

#         if (
#             path is None
#             or started_epoch is None
#             or frame_count <= 0
#         ):
#             return

#         if not path.exists():
#             return

#         if end_epoch is None:

#             end_epoch = (
#                 started_epoch
#                 + self.segment_seconds
#             )

#         if end_timestamp is None:

#             end_timestamp = utc_timestamp()

#         segment = {
#             "camera_id": self.camera_id,
#             "path": str(path),
#             "filename": path.name,
#             "start_epoch": float(
#                 started_epoch
#             ),
#             "end_epoch": float(
#                 end_epoch
#             ),
#             "start_timestamp": (
#                 started_timestamp
#             ),
#             "end_timestamp": (
#                 end_timestamp
#             ),
#             "frame_count": int(
#                 frame_count
#             ),
#             "fps": float(
#                 self.fps
#             ),
#             "width": int(
#                 segment_width
#             ),
#             "height": int(
#                 segment_height
#             ),
#             "created_at": utc_timestamp(),
#         }

#         self.segments.append(segment)

#         self._write_manifest()

#     # ========================================================
#     # ROTATION
#     # ========================================================

#     def _should_rotate_segment(
#         self,
#         frame_epoch: float,
#     ) -> bool:

#         if (
#             self.current_segment_started_at
#             is None
#         ):
#             return True

#         elapsed = (
#             frame_epoch
#             - self.current_segment_started_at
#         )

#         return elapsed >= self.segment_seconds

#     # ========================================================
#     # RETENTION
#     # ========================================================

#     def _cleanup_old_segments(
#         self,
#         current_epoch: float,
#     ) -> None:
#         """
#         Remove segments outside the rolling retention window.
#         """

#         changed = False

#         cutoff = (
#             current_epoch
#             - self.retention_seconds
#         )

#         while self.segments:

#             segment = self.segments[0]

#             end_epoch = float(
#                 segment.get(
#                     "end_epoch",
#                     0.0,
#                 )
#             )

#             path_value = segment.get(
#                 "path"
#             )

#             if (
#                 end_epoch >= cutoff
#                 and len(self.segments)
#                 <= self.max_segments
#             ):
#                 break

#             self.segments.popleft()

#             changed = True

#             if path_value:

#                 path = Path(
#                     str(path_value)
#                 )

#                 try:

#                     if path.exists():
#                         path.unlink()

#                 except Exception as error:

#                     print(
#                         "[EvidenceBuffer] "
#                         f"Failed deleting old segment | "
#                         f"camera={self.camera_id} | "
#                         f"path={path} | "
#                         f"error={error}"
#                     )

#         # Defensive cleanup.
#         while len(self.segments) > self.max_segments:

#             segment = self.segments.popleft()

#             changed = True

#             path_value = segment.get(
#                 "path"
#             )

#             if path_value:

#                 path = Path(
#                     str(path_value)
#                 )

#                 try:

#                     if path.exists():
#                         path.unlink()

#                 except Exception:
#                     pass

#         if changed:
#             self._write_manifest()

#     # ========================================================
#     # WRITE FRAME
#     # ========================================================

#     def write(
#         self,
#         frame,
#         *,
#         timestamp: str | None = None,
#         epoch: float | None = None,
#     ) -> bool:
#         """
#         Write one successfully captured camera frame.

#         This method must be called for EVERY successfully captured
#         frame, not only frames sent to YOLO.

#         Returns:

#             True  -> frame accepted by the buffer
#             False -> buffer could not write the frame
#         """

#         if not self.enabled:
#             return False

#         try:

#             if frame is None:
#                 return False

#             if not hasattr(
#                 frame,
#                 "shape",
#             ):
#                 return False

#             if len(frame.shape) < 2:
#                 return False

#             frame_timestamp = (
#                 timestamp
#                 if timestamp
#                 else utc_timestamp()
#             )

#             frame_epoch = (
#                 float(epoch)
#                 if epoch is not None
#                 else time.time()
#             )

#             height, width = frame.shape[:2]

#             if width <= 0 or height <= 0:
#                 return False

#             # ------------------------------------------------
#             # Start or rotate segment.
#             # ------------------------------------------------

#             if (
#                 self.writer is None
#                 or self._should_rotate_segment(
#                     frame_epoch
#                 )
#                 or width != self.current_frame_width
#                 or height != self.current_frame_height
#             ):

#                 if self.writer is not None:

#                     self._finalize_segment(
#                         end_epoch=frame_epoch,
#                         end_timestamp=frame_timestamp,
#                     )

#                 if not self._start_segment(
#                     frame=frame,
#                     frame_epoch=frame_epoch,
#                     frame_timestamp=frame_timestamp,
#                 ):
#                     return False

#             # ------------------------------------------------
#             # Write frame while preserving wall-clock timing.
#             # ------------------------------------------------

#             if not self._write_frame_at_wall_clock(
#                 frame=frame,
#                 frame_epoch=frame_epoch,
#             ):
#                 return False

#             self.last_frame_timestamp = (
#                 frame_timestamp
#             )

#             self.last_frame_epoch = (
#                 frame_epoch
#             )

#             # ------------------------------------------------
#             # Retention cleanup.
#             # ------------------------------------------------

#             self._cleanup_old_segments(
#                 current_epoch=frame_epoch
#             )

#             return True

#         except Exception as error:

#             print(
#                 "[EvidenceBuffer] "
#                 f"Frame write failed but isolated | "
#                 f"camera={self.camera_id} | "
#                 f"type={type(error).__name__} | "
#                 f"error={error}"
#             )

#             return False

#     # ========================================================
#     # FORCE ROTATION
#     # ========================================================

#     def rotate(self) -> None:
#         """
#         Force the current segment to close.
#         """

#         try:

#             if self.writer is not None:

#                 end_epoch = (
#                     self.last_frame_epoch
#                     if self.last_frame_epoch is not None
#                     else time.time()
#                 )

#                 end_timestamp = (
#                     self.last_frame_timestamp
#                     if self.last_frame_timestamp is not None
#                     else utc_timestamp()
#                 )

#                 self._finalize_segment(
#                     end_epoch=end_epoch,
#                     end_timestamp=end_timestamp,
#                 )

#         except Exception as error:

#             print(
#                 "[EvidenceBuffer] "
#                 f"Forced rotation failed | "
#                 f"camera={self.camera_id} | "
#                 f"error={error}"
#             )

#     # ========================================================
#     # CLOSE
#     # ========================================================

#     def close(self) -> None:
#         """
#         Safely close the active segment.

#         Does not delete the rolling history.
#         """

#         try:
#             self.rotate()

#         except Exception as error:

#             print(
#                 "[EvidenceBuffer] "
#                 f"Close failed | "
#                 f"camera={self.camera_id} | "
#                 f"error={error}"
#             )

#     # ========================================================
#     # GET SEGMENTS
#     # ========================================================

#     def refresh_manifest(self) -> int:
#         """
#         Refresh the in-memory segment index from manifest.json.

#         The rolling buffer is normally owned by the detection process,
#         while the Evidence Agent may keep its own long-lived buffer/
#         manifest view.

#         Without an explicit refresh, that long-lived view can become
#         stale and cause valid current segments to be reported as
#         unavailable.

#         Returns:

#             Number of valid manifest segments loaded into memory.
#         """

#         previous_segments = list(
#             self.segments
#         )

#         try:

#             if not self.manifest_path.exists():
#                 return len(self.segments)

#             with self.manifest_path.open(
#                 "r",
#                 encoding="utf-8",
#             ) as handle:

#                 payload = json.load(handle)

#             if not isinstance(payload, dict):
#                 return len(self.segments)

#             stored_segments = payload.get(
#                 "segments",
#                 []
#             )

#             if not isinstance(
#                 stored_segments,
#                 list,
#             ):
#                 return len(self.segments)

#             refreshed: list[dict[str, Any]] = []

#             for segment in stored_segments:

#                 if not isinstance(
#                     segment,
#                     dict,
#                 ):
#                     continue

#                 path_value = segment.get(
#                     "path"
#                 )

#                 if not path_value:
#                     continue

#                 path = Path(
#                     str(path_value)
#                 )

#                 if not path.is_absolute():

#                     path = (
#                         self.buffer_dir
#                         / path.name
#                     )

#                 if not path.exists():
#                     continue

#                 try:

#                     start_epoch = float(
#                         segment.get(
#                             "start_epoch"
#                         )
#                     )

#                     end_epoch = float(
#                         segment.get(
#                             "end_epoch"
#                         )
#                     )

#                 except (
#                     TypeError,
#                     ValueError,
#                 ):
#                     continue

#                 if end_epoch < start_epoch:
#                     continue

#                 # Reject files too small to be valid evidence.
#                 #
#                 # 44-byte MP4 files previously observed in the
#                 # buffer are incomplete/corrupt files.
#                 try:

#                     if path.stat().st_size <= 1024:
#                         continue

#                 except OSError:
#                     continue

#                 refreshed_segment = dict(
#                     segment
#                 )

#                 refreshed_segment["path"] = str(
#                     path
#                 )

#                 refreshed_segment["start_epoch"] = (
#                     start_epoch
#                 )

#                 refreshed_segment["end_epoch"] = (
#                     end_epoch
#                 )

#                 refreshed.append(
#                     refreshed_segment
#                 )

#             refreshed.sort(
#                 key=lambda item: float(
#                     item.get(
#                         "start_epoch",
#                         0.0,
#                     )
#                 )
#             )

#             self.segments.clear()

#             for segment in refreshed:
#                 self.segments.append(
#                     segment
#                 )

#             return len(self.segments)

#         except Exception as error:

#             print(
#                 "[EvidenceBuffer] "
#                 f"Manifest refresh failed for "
#                 f"camera={self.camera_id}: "
#                 f"{type(error).__name__}: {error}"
#             )

#             # Preserve last known-good state.
#             self.segments.clear()

#             for segment in previous_segments:
#                 self.segments.append(
#                     segment
#                 )

#             return len(self.segments)

#     def get_segments(
#         self,
#     ) -> list[dict[str, Any]]:
#         """
#         Return currently retained segments.

#         Refresh the manifest first so long-lived consumers do not
#         operate against a stale in-memory snapshot.
#         """

#         self.refresh_manifest()

#         return [
#             dict(segment)
#             for segment in self.segments
#         ]

#     # ========================================================
#     # GET SEGMENTS AROUND EVENT
#     # ========================================================

#     def get_segments_for_event(
#         self,
#         event_epoch: float,
#         *,
#         pre_seconds: float = 10.0,
#         post_seconds: float = 10.0,
#     ) -> list[dict[str, Any]]:
#         """
#         Return retained segments overlapping:

#             event_epoch - pre_seconds

#         through:

#             event_epoch + post_seconds

#         The method does not generate a final proof video.
#         It only resolves the relevant source segments.
#         """

#         # Evidence Agent and detection worker are separate
#         # long-lived processes.
#         #
#         # Reload the manifest before every event lookup so the
#         # selector sees segments finalized by the detection worker
#         # after the Evidence Agent started.

#         self.refresh_manifest()

#         start_epoch = (
#             float(event_epoch)
#             - max(
#                 0.0,
#                 float(pre_seconds),
#             )
#         )

#         end_epoch = (
#             float(event_epoch)
#             + max(
#                 0.0,
#                 float(post_seconds),
#             )
#         )

#         selected: list[dict[str, Any]] = []

#         for segment in self.segments:

#             segment_start = float(
#                 segment.get(
#                     "start_epoch",
#                     0.0,
#                 )
#             )

#             segment_end = float(
#                 segment.get(
#                     "end_epoch",
#                     segment_start,
#                 )
#             )

#             if (
#                 segment_end >= start_epoch
#                 and segment_start <= end_epoch
#             ):

#                 selected.append(
#                     dict(segment)
#                 )

#         return selected

#     # ========================================================
#     # STATUS
#     # ========================================================

#     def status(self) -> dict[str, Any]:
#         """
#         Return operational information useful for monitoring.
#         """

#         return {
#             "camera_id": self.camera_id,
#             "enabled": self.enabled,
#             "segment_seconds": self.segment_seconds,
#             "retention_seconds": self.retention_seconds,
#             "fps": self.fps,
#             "segment_count": len(
#                 self.segments
#             ),
#             "latest_segment_start_epoch": (
#                 float(
#                     self.segments[-1][
#                         "start_epoch"
#                     ]
#                 )
#                 if self.segments
#                 and self.segments[-1].get(
#                     "start_epoch"
#                 ) is not None
#                 else None
#             ),
#             "latest_segment_end_epoch": (
#                 float(
#                     self.segments[-1][
#                         "end_epoch"
#                     ]
#                 )
#                 if self.segments
#                 and self.segments[-1].get(
#                     "end_epoch"
#                 ) is not None
#                 else None
#             ),
#             "active_segment": (
#                 str(
#                     self.current_segment_path
#                 )
#                 if self.current_segment_path
#                 else None
#             ),
#             "active_frame_count": (
#                 self.current_segment_frame_count
#             ),
#             "last_frame_timestamp": (
#                 self.last_frame_timestamp
#             ),
#             "buffer_directory": str(
#                 self.buffer_dir
#             ),
#             "manifest": str(
#                 self.manifest_path
#             ),
#         }












"""
Rolling live evidence buffer for the CCTV AI surveillance platform.

Responsibilities
----------------

- Continuously record successfully captured camera frames.
- Store footage as short per-camera MP4 segments.
- Maintain a bounded rolling history.
- Delete expired segments automatically.
- Maintain a lightweight JSON manifest describing finalized segments.
- Keep evidence recording isolated from detection/inference failures.

This module does NOT:

- run YOLO
- publish Redis events
- create incidents
- generate final proof videos
- perform LLM reasoning

The Evidence Agent can later consume the segment manifest to assemble
pre-event + post-event footage around an incident timestamp.

Timing design
-------------

Incoming camera frames are not necessarily delivered at exactly
EVIDENCE_FPS.

The buffer therefore treats incoming frame timestamps as wall-clock
truth and creates a constant-FPS MP4 representation of that timeline.

When the incoming frame rate is lower than EVIDENCE_FPS, the most recent
valid frame is duplicated as necessary.

Importantly, when a segment is finalized, it is padded to its intended
wall-clock boundary using the most recent valid frame. This prevents a
5-second wall-clock segment containing only one or two incoming frames
from becoming a 0.05-0.10 second MP4.

The manifest describes the intended wall-clock coverage of each
finalized segment.

Only finalized segments are written to manifest.json. The currently
open segment is never advertised as available evidence.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2


# ============================================================
# HELPERS
# ============================================================


def parse_positive_float(
    name: str,
    default: float,
) -> float:
    """Read a positive floating-point environment variable."""

    raw = os.getenv(name, str(default))

    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default

    if value <= 0:
        return default

    return value


def utc_timestamp() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""

    return (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def safe_camera_directory_name(
    camera_id: str,
) -> str:
    """
    Convert a camera identifier into a filesystem-safe directory name.

    Kept for compatibility with callers that may use this helper.
    """

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
        for character in str(camera_id)
    )

    return result[:120] or "camera"


# ============================================================
# ROLLING EVIDENCE BUFFER
# ============================================================


class RollingEvidenceBuffer:
    """
    Per-camera rolling video segment buffer.

    Example:

        data/evidence/
            CAM01/
                buffer/
                    segment_....mp4
                    segment_....mp4
                    manifest.json

    The buffer continuously creates short MP4 segments.

    Old finalized segments are removed once they fall outside the
    configured rolling retention window.

    Thread/process ownership
    ------------------------

    One RollingEvidenceBuffer instance should be owned by one writer
    process/thread.

    Other processes, such as the Evidence Agent, should create their own
    read-only instance and call get_segments() /
    get_segments_for_event(). Those methods refresh manifest.json before
    reading it.
    """

    def __init__(
        self,
        camera_id: str,
        output_dir: str | Path,
        *,
        segment_seconds: float | None = None,
        retention_seconds: float | None = None,
        fps: float | None = None,
    ) -> None:

        self.camera_id = str(camera_id).strip()

        if not self.camera_id:
            raise ValueError(
                "camera_id is required for RollingEvidenceBuffer."
            )

        self.output_dir = Path(output_dir)

        self.buffer_dir = (
            self.output_dir / "buffer"
        )

        self.buffer_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.manifest_path = (
            self.buffer_dir / "manifest.json"
        )

        self.segment_seconds = (
            float(segment_seconds)
            if segment_seconds is not None
            else parse_positive_float(
                "EVIDENCE_SEGMENT_SECONDS",
                5.0,
            )
        )

        self.retention_seconds = (
            float(retention_seconds)
            if retention_seconds is not None
            else parse_positive_float(
                "EVIDENCE_RETENTION_SECONDS",
                60.0,
            )
        )

        self.fps = (
            float(fps)
            if fps is not None
            else parse_positive_float(
                "EVIDENCE_FPS",
                20.0,
            )
        )

        if self.segment_seconds <= 0:
            self.segment_seconds = 5.0

        if self.retention_seconds <= 0:
            self.retention_seconds = 60.0

        if self.fps <= 0:
            self.fps = 20.0

        # Retention must be able to contain at least two segments.
        if self.retention_seconds < self.segment_seconds:
            self.retention_seconds = (
                self.segment_seconds * 2.0
            )

        # This is a safety bound, not the primary retention mechanism.
        self.max_segments = max(
            2,
            int(
                self.retention_seconds
                / self.segment_seconds
            ) + 3,
        )

        # ----------------------------------------------------
        # Current OpenCV writer
        # ----------------------------------------------------

        self.writer: cv2.VideoWriter | None = None

        # ----------------------------------------------------
        # Current segment state
        # ----------------------------------------------------

        self.current_segment_path: Path | None = None

        self.current_segment_started_at: float | None = None

        self.current_segment_started_timestamp: str | None = None

        self.current_segment_frame_count = 0

        self.current_frame_width = 0
        self.current_frame_height = 0

        # Most recent frame available for temporal padding.
        self.last_written_frame = None

        self.last_written_frame_epoch: float | None = None

        # ----------------------------------------------------
        # Segment metadata
        # ----------------------------------------------------

        # Do NOT use deque(maxlen=...) here.
        #
        # A maxlen deque silently removes entries when it fills up,
        # which would make it impossible to reliably delete the
        # corresponding MP4 file.
        self.segments: deque[dict[str, Any]] = deque()

        self.segment_sequence = 0

        self.last_frame_timestamp: str | None = None
        self.last_frame_epoch: float | None = None

        self.enabled = True

        self._load_manifest()

    # ========================================================
    # MANIFEST
    # ========================================================

    def _load_manifest(self) -> None:
        """Recover the existing manifest after a worker restart."""

        self.refresh_manifest()

    def _write_manifest(self) -> None:
        """
        Atomically write the current finalized-segment manifest.
        """

        temp_path: Path | None = None

        try:
            payload = {
                "camera_id": self.camera_id,
                "updated_at": utc_timestamp(),
                "segment_seconds": self.segment_seconds,
                "retention_seconds": self.retention_seconds,
                "fps": self.fps,
                "segments": list(self.segments),
            }

            temp_path = self.manifest_path.with_name(
                f".manifest.{uuid.uuid4().hex}.json"
            )

            with temp_path.open(
                "w",
                encoding="utf-8",
            ) as handle:
                json.dump(
                    payload,
                    handle,
                    indent=2,
                )

                handle.flush()

                try:
                    os.fsync(handle.fileno())
                except OSError:
                    # fsync is best-effort on some filesystems.
                    pass

            os.replace(
                temp_path,
                self.manifest_path,
            )

        except Exception as error:

            print(
                "[EvidenceBuffer] "
                f"Manifest write failed | "
                f"camera={self.camera_id} | "
                f"type={type(error).__name__} | "
                f"error={error}"
            )

            if temp_path is not None:

                try:
                    if temp_path.exists():
                        temp_path.unlink()
                except Exception:
                    pass

    # ========================================================
    # VIDEO CODEC
    # ========================================================

    @staticmethod
    def _create_writer(
        path: Path,
        fps: float,
        width: int,
        height: int,
    ) -> cv2.VideoWriter | None:
        """
        Create an MP4 writer.

        mp4v is intentionally used because it is widely available
        through OpenCV on Windows.

        Final H.264 conversion remains the responsibility of the
        Evidence/FFmpeg layer.
        """

        fourcc = cv2.VideoWriter_fourcc(
            *"mp4v"
        )

        writer = cv2.VideoWriter(
            str(path),
            fourcc,
            float(fps),
            (
                int(width),
                int(height),
            ),
        )

        if not writer.isOpened():

            try:
                writer.release()
            except Exception:
                pass

            return None

        return writer

    # ========================================================
    # START SEGMENT
    # ========================================================

    def _start_segment(
        self,
        frame,
        frame_epoch: float,
        frame_timestamp: str,
    ) -> bool:
        """Start a new segment using the current frame dimensions."""

        height, width = frame.shape[:2]

        if width <= 0 or height <= 0:
            return False

        self.segment_sequence += 1

        filename = (
            f"segment_"
            f"{int(frame_epoch * 1000)}_"
            f"{self.segment_sequence}_"
            f"{uuid.uuid4().hex[:8]}"
            f".mp4"
        )

        path = (
            self.buffer_dir
            / filename
        )

        writer = self._create_writer(
            path=path,
            fps=self.fps,
            width=width,
            height=height,
        )

        if writer is None:

            print(
                "[EvidenceBuffer] "
                f"Could not create video writer | "
                f"camera={self.camera_id} | "
                f"path={path}"
            )

            return False

        self.writer = writer

        self.current_segment_path = path

        self.current_segment_started_at = (
            frame_epoch
        )

        self.current_segment_started_timestamp = (
            frame_timestamp
        )

        self.current_segment_frame_count = 0

        self.current_frame_width = width
        self.current_frame_height = height

        self.last_written_frame = None
        self.last_written_frame_epoch = None

        return True

    # ========================================================
    # WRITE FRAME
    # ========================================================

    def _write_output_frame(
        self,
        frame,
    ) -> bool:
        """Write one frame to the active writer."""

        if self.writer is None:
            return False

        if (
            frame.shape[1] != self.current_frame_width
            or frame.shape[0] != self.current_frame_height
        ):
            return False

        try:

            self.writer.write(frame)

            self.current_segment_frame_count += 1

            return True

        except Exception as error:

            print(
                "[EvidenceBuffer] "
                f"Video frame write failed | "
                f"camera={self.camera_id} | "
                f"type={type(error).__name__} | "
                f"error={error}"
            )

            return False

    def _write_frame_at_wall_clock(
        self,
        frame,
        frame_epoch: float,
    ) -> bool:
        """
        Write the incoming frame while preserving elapsed wall-clock time.

        If frames arrive slower than EVIDENCE_FPS, the previous frame is
        duplicated for the elapsed interval and the new frame is written
        at the end of that interval.

        Example:

            EVIDENCE_FPS = 20
            incoming interval = 0.5 sec

        Approximately 10 encoded frames are produced.
        """

        if self.writer is None:
            return False

        if (
            frame.shape[1] != self.current_frame_width
            or frame.shape[0] != self.current_frame_height
        ):
            return False

        # First frame of a segment.
        if self.last_written_frame_epoch is None:

            if not self._write_output_frame(frame):
                return False

            self.last_written_frame = frame.copy()

            self.last_written_frame_epoch = frame_epoch

            return True

        elapsed = (
            frame_epoch
            - self.last_written_frame_epoch
        )

        if elapsed < 0:
            elapsed = 0.0

        frame_count = max(
            1,
            int(
                round(
                    elapsed * self.fps
                )
            ),
        )

        # Prevent a broken camera timestamp from causing millions of
        # duplicate frames.
        max_duplicate_frames = max(
            int(
                self.fps
                * self.segment_seconds
                * 2
            ),
            int(self.fps),
            1,
        )

        frame_count = min(
            frame_count,
            max_duplicate_frames,
        )

        previous_frame = self.last_written_frame

        if previous_frame is None:
            previous_frame = frame

        for index in range(frame_count):

            output_frame = (
                frame
                if index == frame_count - 1
                else previous_frame
            )

            if not self._write_output_frame(
                output_frame
            ):
                return False

        self.last_written_frame = frame.copy()

        self.last_written_frame_epoch = frame_epoch

        return True

    # ========================================================
    # PAD ACTIVE SEGMENT
    # ========================================================

    def _pad_active_segment_to_duration(
        self,
        target_duration: float,
    ) -> None:
        """
        Pad the active segment to a target wall-clock duration.

        This is critical when incoming frames are sparse.

        Example:

            segment = 5 seconds
            camera gives only one frame

        The MP4 must still contain approximately:

            5 * EVIDENCE_FPS

        encoded frames.

        The most recent valid frame is repeated.
        """

        if self.writer is None:
            return

        if self.last_written_frame is None:
            return

        target_frames = max(
            1,
            int(
                round(
                    max(
                        0.0,
                        target_duration,
                    )
                    * self.fps
                )
            ),
        )

        missing_frames = (
            target_frames
            - self.current_segment_frame_count
        )

        if missing_frames <= 0:
            return

        for _ in range(missing_frames):

            if not self._write_output_frame(
                self.last_written_frame
            ):
                break

    # ========================================================
    # FINALIZE SEGMENT
    # ========================================================

    def _finalize_segment(
        self,
        end_epoch: float | None = None,
        end_timestamp: str | None = None,
    ) -> None:
        """
        Close the current writer and register the finalized segment.

        The active segment is padded to its intended wall-clock duration
        whenever possible.

        IMPORTANT:

        The finalized segment is added to manifest.json only AFTER the
        VideoWriter has been released successfully enough for the file
        to exist on disk.
        """

        writer = self.writer

        path = self.current_segment_path

        started_epoch = (
            self.current_segment_started_at
        )

        started_timestamp = (
            self.current_segment_started_timestamp
        )

        frame_count_before_release = (
            self.current_segment_frame_count
        )

        segment_width = (
            self.current_frame_width
        )

        segment_height = (
            self.current_frame_height
        )

        # ----------------------------------------------------
        # Determine intended end time.
        # ----------------------------------------------------

        if (
            started_epoch is not None
            and end_epoch is None
        ):
            end_epoch = (
                started_epoch
                + self.segment_seconds
            )

        if (
            started_epoch is not None
            and end_epoch is not None
            and end_epoch < started_epoch
        ):
            end_epoch = started_epoch

        if end_timestamp is None:

            if (
                end_epoch is not None
                and started_epoch is not None
            ):

                end_timestamp = (
                    datetime.fromtimestamp(
                        end_epoch,
                        tz=timezone.utc,
                    )
                    .isoformat()
                    .replace(
                        "+00:00",
                        "Z",
                    )
                )

            else:
                end_timestamp = utc_timestamp()

        # ----------------------------------------------------
        # Pad before releasing writer.
        # ----------------------------------------------------

        if (
            writer is not None
            and started_epoch is not None
            and end_epoch is not None
        ):

            target_duration = max(
                0.0,
                end_epoch
                - started_epoch,
            )

            try:
                self._pad_active_segment_to_duration(
                    target_duration
                )
            except Exception as error:

                print(
                    "[EvidenceBuffer] "
                    f"Segment padding failed | "
                    f"camera={self.camera_id} | "
                    f"type={type(error).__name__} | "
                    f"error={error}"
                )

        final_frame_count = (
            self.current_segment_frame_count
        )

        # ----------------------------------------------------
        # Release writer.
        # ----------------------------------------------------

        self.writer = None

        if writer is not None:

            try:
                writer.release()

            except Exception as error:

                print(
                    "[EvidenceBuffer] "
                    f"Video writer release failed | "
                    f"camera={self.camera_id} | "
                    f"error={error}"
                )

        # ----------------------------------------------------
        # Reset active state.
        # ----------------------------------------------------

        self.current_segment_path = None

        self.current_segment_started_at = None

        self.current_segment_started_timestamp = None

        self.current_segment_frame_count = 0

        self.current_frame_width = 0
        self.current_frame_height = 0

        self.last_written_frame = None
        self.last_written_frame_epoch = None

        # ----------------------------------------------------
        # Validate finalized file.
        # ----------------------------------------------------

        if (
            path is None
            or started_epoch is None
            or final_frame_count <= 0
        ):
            return

        if not path.exists():
            print(
                "[EvidenceBuffer] "
                f"Finalized segment file missing | "
                f"camera={self.camera_id} | "
                f"path={path}"
            )
            return

        try:
            file_size = path.stat().st_size
        except OSError:
            return

        # Reject tiny/incomplete files.
        if file_size <= 1024:

            print(
                "[EvidenceBuffer] "
                f"Rejecting tiny segment | "
                f"camera={self.camera_id} | "
                f"path={path} | "
                f"size={file_size}"
            )

            return

        # ----------------------------------------------------
        # Register finalized segment.
        # ----------------------------------------------------

        if end_epoch is None:

            end_epoch = (
                started_epoch
                + self.segment_seconds
            )

        if end_timestamp is None:

            end_timestamp = (
                datetime.fromtimestamp(
                    end_epoch,
                    tz=timezone.utc,
                )
                .isoformat()
                .replace(
                    "+00:00",
                    "Z",
                )
            )

        segment = {
            "camera_id": self.camera_id,
            "path": str(path),
            "filename": path.name,
            "start_epoch": float(
                started_epoch
            ),
            "end_epoch": float(
                end_epoch
            ),
            "start_timestamp": (
                started_timestamp
            ),
            "end_timestamp": (
                end_timestamp
            ),
            "frame_count": int(
                final_frame_count
            ),
            "fps": float(
                self.fps
            ),
            "width": int(
                segment_width
            ),
            "height": int(
                segment_height
            ),
            "file_size_bytes": int(
                file_size
            ),
            "created_at": utc_timestamp(),
        }

        self.segments.append(segment)

        self._write_manifest()

    # ========================================================
    # ROTATION
    # ========================================================

    def _should_rotate_segment(
        self,
        frame_epoch: float,
    ) -> bool:
        """Return True when the active segment reached its duration."""

        if self.current_segment_started_at is None:
            return True

        elapsed = (
            frame_epoch
            - self.current_segment_started_at
        )

        return elapsed >= self.segment_seconds

    # ========================================================
    # RETENTION
    # ========================================================

    def _delete_segment_file(
        self,
        segment: dict[str, Any],
    ) -> bool:
        """Delete a finalized segment file."""

        path_value = segment.get("path")

        if not path_value:
            return True

        path = Path(
            str(path_value)
        )

        try:

            if path.exists():
                path.unlink()

            return True

        except Exception as error:

            print(
                "[EvidenceBuffer] "
                f"Failed deleting old segment | "
                f"camera={self.camera_id} | "
                f"path={path} | "
                f"type={type(error).__name__} | "
                f"error={error}"
            )

            return False

    def _cleanup_old_segments(
        self,
        current_epoch: float,
    ) -> None:
        """
        Remove finalized segments outside the rolling retention window.

        Files are removed only after their metadata has been selected
        for eviction.

        If deletion fails, the metadata entry is retained so the system
        does not falsely claim that the file was removed.
        """

        changed = False

        cutoff = (
            current_epoch
            - self.retention_seconds
        )

        # ----------------------------------------------------
        # Time-based retention.
        # ----------------------------------------------------

        while self.segments:

            segment = self.segments[0]

            end_epoch = float(
                segment.get(
                    "end_epoch",
                    0.0,
                )
            )

            if end_epoch >= cutoff:
                break

            if not self._delete_segment_file(
                segment
            ):
                break

            self.segments.popleft()

            changed = True

        # ----------------------------------------------------
        # Defensive count bound.
        #
        # This should rarely be reached, but protects against
        # unexpected metadata accumulation.
        # ----------------------------------------------------

        while len(self.segments) > self.max_segments:

            segment = self.segments[0]

            if not self._delete_segment_file(
                segment
            ):
                break

            self.segments.popleft()

            changed = True

        if changed:
            self._write_manifest()

    # ========================================================
    # WRITE FRAME
    # ========================================================

    def write(
        self,
        frame,
        *,
        timestamp: str | None = None,
        epoch: float | None = None,
    ) -> bool:
        """
        Write one successfully captured camera frame.

        This should be called for EVERY successfully captured frame,
        not only frames sent to YOLO.

        Returns:

            True  -> frame accepted by the buffer
            False -> buffer could not write the frame
        """

        if not self.enabled:
            return False

        try:

            if frame is None:
                return False

            if not hasattr(
                frame,
                "shape",
            ):
                return False

            if len(frame.shape) < 2:
                return False

            frame_timestamp = (
                timestamp
                if timestamp
                else utc_timestamp()
            )

            frame_epoch = (
                float(epoch)
                if epoch is not None
                else time.time()
            )

            if not (
                frame_epoch == frame_epoch
            ):
                # NaN guard.
                return False

            height, width = frame.shape[:2]

            if width <= 0 or height <= 0:
                return False

            # ------------------------------------------------
            # Start or rotate segment.
            # ------------------------------------------------

            needs_new_segment = (
                self.writer is None
                or self._should_rotate_segment(
                    frame_epoch
                )
                or width != self.current_frame_width
                or height != self.current_frame_height
            )

            if needs_new_segment:

                if self.writer is not None:

                    # IMPORTANT:
                    #
                    # The previous segment is finalized at its own
                    # configured wall-clock boundary rather than using
                    # the new frame timestamp as its nominal end.
                    segment_end_epoch = (
                        self.current_segment_started_at
                        + self.segment_seconds
                        if self.current_segment_started_at
                        is not None
                        else frame_epoch
                    )

                    segment_end_timestamp = (
                        datetime.fromtimestamp(
                            segment_end_epoch,
                            tz=timezone.utc,
                        )
                        .isoformat()
                        .replace(
                            "+00:00",
                            "Z",
                        )
                    )

                    self._finalize_segment(
                        end_epoch=segment_end_epoch,
                        end_timestamp=segment_end_timestamp,
                    )

                if not self._start_segment(
                    frame=frame,
                    frame_epoch=frame_epoch,
                    frame_timestamp=frame_timestamp,
                ):
                    return False

            # ------------------------------------------------
            # Write frame using wall-clock timing.
            # ------------------------------------------------

            if not self._write_frame_at_wall_clock(
                frame=frame,
                frame_epoch=frame_epoch,
            ):
                return False

            self.last_frame_timestamp = (
                frame_timestamp
            )

            self.last_frame_epoch = (
                frame_epoch
            )

            # ------------------------------------------------
            # Retention cleanup.
            # ------------------------------------------------

            self._cleanup_old_segments(
                current_epoch=frame_epoch
            )

            return True

        except Exception as error:

            print(
                "[EvidenceBuffer] "
                f"Frame write failed but isolated | "
                f"camera={self.camera_id} | "
                f"type={type(error).__name__} | "
                f"error={error}"
            )

            return False

    # ========================================================
    # FORCE ROTATION
    # ========================================================

    def rotate(self) -> None:
        """
        Force the current segment to close.

        The active segment is padded to its configured duration when
        possible.
        """

        try:

            if self.writer is not None:

                if self.current_segment_started_at is not None:

                    end_epoch = (
                        self.current_segment_started_at
                        + self.segment_seconds
                    )

                    end_timestamp = (
                        datetime.fromtimestamp(
                            end_epoch,
                            tz=timezone.utc,
                        )
                        .isoformat()
                        .replace(
                            "+00:00",
                            "Z",
                        )
                    )

                else:

                    end_epoch = (
                        self.last_frame_epoch
                        if self.last_frame_epoch is not None
                        else time.time()
                    )

                    end_timestamp = (
                        datetime.fromtimestamp(
                            end_epoch,
                            tz=timezone.utc,
                        )
                        .isoformat()
                        .replace(
                            "+00:00",
                            "Z",
                        )
                    )

                self._finalize_segment(
                    end_epoch=end_epoch,
                    end_timestamp=end_timestamp,
                )

        except Exception as error:

            print(
                "[EvidenceBuffer] "
                f"Forced rotation failed | "
                f"camera={self.camera_id} | "
                f"type={type(error).__name__} | "
                f"error={error}"
            )

    # ========================================================
    # CLOSE
    # ========================================================

    def close(self) -> None:
        """
        Safely close the active segment.

        Existing rolling history is intentionally preserved.
        """

        try:

            self.rotate()

        except Exception as error:

            print(
                "[EvidenceBuffer] "
                f"Close failed | "
                f"camera={self.camera_id} | "
                f"type={type(error).__name__} | "
                f"error={error}"
            )

    # ========================================================
    # MANIFEST REFRESH
    # ========================================================

    def refresh_manifest(self) -> int:
        """
        Refresh the in-memory segment index from manifest.json.

        This is important because the Detection Agent and Evidence Agent
        can be separate long-lived processes.

        Returns:

            Number of valid manifest segments currently loaded.
        """

        previous_segments = list(
            self.segments
        )

        try:

            if not self.manifest_path.exists():
                return len(self.segments)

            with self.manifest_path.open(
                "r",
                encoding="utf-8",
            ) as handle:

                payload = json.load(handle)

            if not isinstance(
                payload,
                dict,
            ):
                return len(self.segments)

            stored_segments = payload.get(
                "segments",
                [],
            )

            if not isinstance(
                stored_segments,
                list,
            ):
                return len(self.segments)

            refreshed: list[dict[str, Any]] = []

            for segment in stored_segments:

                if not isinstance(
                    segment,
                    dict,
                ):
                    continue

                path_value = segment.get(
                    "path"
                )

                if not path_value:
                    continue

                path = Path(
                    str(path_value)
                )

                # Older manifests may contain relative paths.
                if not path.is_absolute():

                    path = (
                        self.buffer_dir
                        / path.name
                    )

                if not path.exists():
                    continue

                try:

                    start_epoch = float(
                        segment.get(
                            "start_epoch"
                        )
                    )

                    end_epoch = float(
                        segment.get(
                            "end_epoch"
                        )
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    continue

                if end_epoch < start_epoch:
                    continue

                try:

                    file_size = path.stat().st_size

                except OSError:
                    continue

                # Reject zero-byte/tiny incomplete files.
                if file_size <= 1024:
                    continue

                refreshed_segment = dict(
                    segment
                )

                refreshed_segment["path"] = (
                    str(path)
                )

                refreshed_segment["start_epoch"] = (
                    start_epoch
                )

                refreshed_segment["end_epoch"] = (
                    end_epoch
                )

                refreshed_segment["file_size_bytes"] = (
                    int(file_size)
                )

                refreshed.append(
                    refreshed_segment
                )

            refreshed.sort(
                key=lambda item: float(
                    item.get(
                        "start_epoch",
                        0.0,
                    )
                )
            )

            self.segments.clear()

            for segment in refreshed:
                self.segments.append(
                    segment
                )

            # Keep the in-memory safety bound.
            #
            # Unlike the previous maxlen deque, this does not silently
            # delete metadata. We explicitly remove the oldest metadata
            # and corresponding file if necessary.
            while len(self.segments) > self.max_segments:

                segment = self.segments.popleft()

                self._delete_segment_file(
                    segment
                )

            return len(self.segments)

        except Exception as error:

            print(
                "[EvidenceBuffer] "
                f"Manifest refresh failed | "
                f"camera={self.camera_id} | "
                f"type={type(error).__name__} | "
                f"error={error}"
            )

            # Preserve last known-good state.
            self.segments.clear()

            for segment in previous_segments:
                self.segments.append(
                    segment
                )

            return len(self.segments)

    # ========================================================
    # GET SEGMENTS
    # ========================================================

    def get_segments(
        self,
    ) -> list[dict[str, Any]]:
        """
        Return currently retained finalized segments.

        Refreshes manifest.json first so a long-lived Evidence Agent
        does not operate on a stale in-memory snapshot.
        """

        self.refresh_manifest()

        return [
            dict(segment)
            for segment in self.segments
        ]

    # ========================================================
    # GET SEGMENTS AROUND EVENT
    # ========================================================

    def get_segments_for_event(
        self,
        event_epoch: float,
        *,
        pre_seconds: float = 10.0,
        post_seconds: float = 10.0,
    ) -> list[dict[str, Any]]:
        """
        Return finalized retained segments overlapping:

            event_epoch - pre_seconds

        through:

            event_epoch + post_seconds

        This method only resolves source segments.

        It does NOT generate a final proof video.
        """

        # Detection and Evidence can be separate processes.
        #
        # Reload the manifest immediately before lookup so newly
        # finalized segments are visible.

        self.refresh_manifest()

        try:
            event_epoch = float(
                event_epoch
            )
        except (
            TypeError,
            ValueError,
        ):
            return []

        start_epoch = (
            event_epoch
            - max(
                0.0,
                float(pre_seconds),
            )
        )

        end_epoch = (
            event_epoch
            + max(
                0.0,
                float(post_seconds),
            )
        )

        selected: list[dict[str, Any]] = []

        for segment in self.segments:

            try:

                segment_start = float(
                    segment.get(
                        "start_epoch",
                        0.0,
                    )
                )

                segment_end = float(
                    segment.get(
                        "end_epoch",
                        segment_start,
                    )
                )

            except (
                TypeError,
                ValueError,
            ):
                continue

            # Standard interval-overlap test.
            if (
                segment_end >= start_epoch
                and segment_start <= end_epoch
            ):

                selected.append(
                    dict(segment)
                )

        selected.sort(
            key=lambda item: float(
                item.get(
                    "start_epoch",
                    0.0,
                )
            )
        )

        return selected

    # ========================================================
    # STATUS
    # ========================================================

    def status(self) -> dict[str, Any]:
        """
        Return operational information useful for monitoring.
        """

        latest_segment = (
            self.segments[-1]
            if self.segments
            else None
        )

        return {
            "camera_id": self.camera_id,
            "enabled": self.enabled,
            "segment_seconds": self.segment_seconds,
            "retention_seconds": self.retention_seconds,
            "fps": self.fps,
            "max_segments": self.max_segments,
            "segment_count": len(
                self.segments
            ),
            "latest_segment_start_epoch": (
                float(
                    latest_segment[
                        "start_epoch"
                    ]
                )
                if latest_segment
                and latest_segment.get(
                    "start_epoch"
                ) is not None
                else None
            ),
            "latest_segment_end_epoch": (
                float(
                    latest_segment[
                        "end_epoch"
                    ]
                )
                if latest_segment
                and latest_segment.get(
                    "end_epoch"
                ) is not None
                else None
            ),
            "active_segment": (
                str(
                    self.current_segment_path
                )
                if self.current_segment_path
                else None
            ),
            "active_frame_count": (
                self.current_segment_frame_count
            ),
            "last_frame_timestamp": (
                self.last_frame_timestamp
            ),
            "last_frame_epoch": (
                self.last_frame_epoch
            ),
            "buffer_directory": str(
                self.buffer_dir
            ),
            "manifest": str(
                self.manifest_path
            ),
        }