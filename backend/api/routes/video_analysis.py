# from pathlib import Path
# import os
# import shutil
# import subprocess
# import uuid

# import cv2

# from fastapi import (
#     APIRouter,
#     BackgroundTasks,
#     HTTPException,
#     UploadFile,
#     File,
# )
# from fastapi.responses import FileResponse
# from ultralytics import YOLO


# # ============================================================
# # ROUTER
# # ============================================================

# router = APIRouter(
#     prefix="/api/video-analysis",
#     tags=["video-analysis"],
# )


# # ============================================================
# # PATHS
# # ============================================================

# PROJECT_ROOT = Path(__file__).resolve().parents[3]

# UPLOAD_DIR = (
#     PROJECT_ROOT
#     / "data"
#     / "recorded_videos"
# )

# PROOF_DIR = (
#     PROJECT_ROOT
#     / "data"
#     / "proof_videos"
# )

# UPLOAD_DIR.mkdir(
#     parents=True,
#     exist_ok=True,
# )

# PROOF_DIR.mkdir(
#     parents=True,
#     exist_ok=True,
# )


# # ============================================================
# # FFMPEG
# # ============================================================

# FFMPEG_BIN = (
#     os.getenv("FFMPEG_BIN")
#     or shutil.which("ffmpeg")
# )


# def require_ffmpeg() -> str:
#     if not FFMPEG_BIN:
#         raise RuntimeError(
#             "FFmpeg was not found. "
#             "Make sure ffmpeg is in PATH or "
#             "set FFMPEG_BIN to ffmpeg.exe."
#         )

#     return FFMPEG_BIN


# # ============================================================
# # CONFIG
# # ============================================================

# ALLOWED_VIDEO_TYPES = {
#     "video/mp4",
#     "video/avi",
#     "video/x-msvideo",
#     "video/mov",
#     "video/quicktime",
#     "video/webm",
# }

# ALLOWED_EXTENSIONS = {
#     ".mp4",
#     ".avi",
#     ".mov",
#     ".webm",
# }

# CONFIDENCE_THRESHOLD = 0.40


# # ============================================================
# # UNUSUAL EVENT CONFIG
# # ============================================================

# UNUSUAL_PERSON_COUNT = 4
# UNUSUAL_PERSON_CHANGE = 2
# UNUSUAL_CONFIRMATION_FRAMES = 5

# # Process every Nth frame during the first analysis pass.
# ANALYSIS_FRAME_SKIP = 3


# # ============================================================
# # PROOF CONFIG
# # ============================================================

# PRE_EVENT_SECONDS = 4.0
# POST_EVENT_SECONDS = 6.0
# PROOF_DURATION_SECONDS = 10.0


# # ============================================================
# # YOLO MODEL
# # ============================================================

# print(
#     "Loading YOLO model for recorded-video analysis..."
# )

# MODEL = YOLO(
#     "yolo11n.pt"
# )

# print(
#     "Recorded-video YOLO model loaded successfully."
# )


# # ============================================================
# # ANALYSIS JOB STATE
# # ============================================================

# analysis_jobs = {}


# # ============================================================
# # FIND VIDEO
# # ============================================================

# def find_video(
#     video_id: str,
# ) -> Path | None:

#     video_files = list(
#         UPLOAD_DIR.glob(
#             f"{video_id}.*"
#         )
#     )

#     if not video_files:
#         return None

#     return video_files[0]


# # ============================================================
# # DETECT PEOPLE
# # ============================================================
# #
# # IMPORTANT:
# # We intentionally use MODEL.predict() here instead of
# # MODEL.track(..., persist=True).
# #
# # This application currently needs person counts, not persistent
# # track IDs. Using tracking state across separate analysis/proof
# # passes can cause stale tracker state.
# #
# # If persistent IDs are required later, create a dedicated
# # tracker/model instance for each video-analysis session.
# # ============================================================

# def detect_people(frame):
#     results = MODEL.predict(
#         frame,
#         verbose=False,
#         conf=CONFIDENCE_THRESHOLD,
#         classes=[0],
#     )

#     people = []

#     for result in results:

#         if result.boxes is None:
#             continue

#         for box in result.boxes:

#             class_id = int(
#                 box.cls[0].item()
#             )

#             if class_id != 0:
#                 continue

#             confidence = float(
#                 box.conf[0].item()
#             )

#             x1, y1, x2, y2 = map(
#                 int,
#                 box.xyxy[0].tolist(),
#             )

#             people.append(
#                 {
#                     "bbox": [
#                         x1,
#                         y1,
#                         x2,
#                         y2,
#                     ],
#                     "confidence": confidence,
#                 }
#             )

#     return people


# # ============================================================
# # DRAW PEOPLE
# # ============================================================

# def draw_people(
#     frame,
#     people,
# ):

#     for person in people:

#         x1, y1, x2, y2 = (
#             person["bbox"]
#         )

#         confidence = (
#             person["confidence"]
#         )

#         cv2.rectangle(
#             frame,
#             (x1, y1),
#             (x2, y2),
#             (0, 255, 0),
#             2,
#         )

#         cv2.putText(
#             frame,
#             f"Person {confidence:.2f}",
#             (
#                 x1,
#                 max(y1 - 10, 20),
#             ),
#             cv2.FONT_HERSHEY_SIMPLEX,
#             0.6,
#             (0, 255, 0),
#             2,
#         )


# # ============================================================
# # DRAW PROOF HEADER
# # ============================================================

# def draw_proof_header(
#     frame,
#     event,
# ):

#     height, width = frame.shape[:2]

#     cv2.rectangle(
#         frame,
#         (0, 0),
#         (width, 125),
#         (0, 0, 0),
#         -1,
#     )

#     cv2.putText(
#         frame,
#         "AI SURVEILLANCE PROOF",
#         (20, 32),
#         cv2.FONT_HERSHEY_SIMPLEX,
#         0.75,
#         (0, 255, 255),
#         2,
#     )

#     cv2.putText(
#         frame,
#         f"Event: {event['type']}",
#         (20, 62),
#         cv2.FONT_HERSHEY_SIMPLEX,
#         0.55,
#         (0, 255, 255),
#         2,
#     )

#     cv2.putText(
#         frame,
#         f"People: {event['after_person_count']}",
#         (20, 88),
#         cv2.FONT_HERSHEY_SIMPLEX,
#         0.55,
#         (0, 255, 255),
#         2,
#     )

#     cv2.putText(
#         frame,
#         f"Event time: {event['time']:.2f}s",
#         (20, 114),
#         cv2.FONT_HERSHEY_SIMPLEX,
#         0.50,
#         (0, 255, 255),
#         2,
#     )


# # ============================================================
# # FIND UNUSUAL EVENT
# # ============================================================

# def find_unusual_event(
#     frame_counts,
#     fps,
#     duration,
# ):

#     if not frame_counts:

#         return {
#             "time": 0.0,
#             "type": "NO_EVENT",
#             "score": 0,
#             "before_person_count": 0,
#             "after_person_count": 0,
#             "change": 0,
#         }

#     best_event = {
#         "time": 0.0,
#         "type": "NO_STRONG_EVENT",
#         "score": 0,
#         "before_person_count": 0,
#         "after_person_count": 0,
#         "change": 0,
#     }

#     previous_count = (
#         frame_counts[0]["person_count"]
#     )

#     consecutive_unusual = 0

#     for index in range(
#         1,
#         len(frame_counts),
#     ):

#         current = frame_counts[index]

#         current_count = (
#             current["person_count"]
#         )

#         change = (
#             current_count
#             - previous_count
#         )

#         absolute_change = abs(change)

#         unusual = (
#             absolute_change
#             >= UNUSUAL_PERSON_CHANGE
#             and (
#                 current_count
#                 >= UNUSUAL_PERSON_COUNT
#                 or previous_count
#                 >= UNUSUAL_PERSON_COUNT
#             )
#         )

#         if unusual:
#             consecutive_unusual += 1
#         else:
#             consecutive_unusual = 0

#         if unusual:

#             score = absolute_change

#             if (
#                 consecutive_unusual
#                 >= UNUSUAL_CONFIRMATION_FRAMES
#             ):
#                 score += 1

#             if score > best_event["score"]:

#                 event_type = (
#                     "SUDDEN_PERSON_INCREASE"
#                     if change > 0
#                     else "SUDDEN_PERSON_DECREASE"
#                 )

#                 best_event = {
#                     "time": current["time"],
#                     "type": event_type,
#                     "score": score,
#                     "before_person_count": (
#                         previous_count
#                     ),
#                     "after_person_count": (
#                         current_count
#                     ),
#                     "change": change,
#                 }

#         previous_count = current_count

#     best_event["time"] = max(
#         0.0,
#         min(
#             best_event["time"],
#             max(0.0, duration),
#         ),
#     )

#     return best_event


# # ============================================================
# # CONVERT PROOF TO H264
# # ============================================================

# def convert_proof_to_h264(
#     raw_path: Path,
#     final_path: Path,
# ):

#     ffmpeg = require_ffmpeg()

#     temp_h264 = (
#         final_path.with_name(
#             f"{final_path.stem}_h264_tmp.mp4"
#         )
#     )

#     command = [
#         ffmpeg,
#         "-y",
#         "-hide_banner",
#         "-loglevel",
#         "error",
#         "-i",
#         str(raw_path),
#         "-an",
#         "-c:v",
#         "libx264",
#         "-preset",
#         "fast",
#         "-crf",
#         "23",
#         "-pix_fmt",
#         "yuv420p",
#         "-profile:v",
#         "main",
#         "-level:v",
#         "3.0",
#         "-movflags",
#         "+faststart",
#         str(temp_h264),
#     ]

#     try:

#         subprocess.run(
#             command,
#             check=True,
#             capture_output=True,
#             text=True,
#         )

#         if (
#             not temp_h264.exists()
#             or temp_h264.stat().st_size == 0
#         ):
#             raise RuntimeError(
#                 "FFmpeg completed but "
#                 "did not create a valid H.264 file."
#             )

#         os.replace(
#             temp_h264,
#             final_path,
#         )

#     except subprocess.CalledProcessError as exc:

#         stderr = (
#             exc.stderr or ""
#         ).strip()

#         raise RuntimeError(
#             "FFmpeg H.264 conversion failed"
#             + (
#                 f": {stderr}"
#                 if stderr
#                 else "."
#             )
#         ) from exc

#     finally:

#         if temp_h264.exists():

#             try:
#                 temp_h264.unlink()
#             except OSError:
#                 pass


# # ============================================================
# # CREATE PROOF VIDEO
# # ============================================================

# def create_proof_video(
#     video_path,
#     proof_path,
#     event,
# ):

#     capture = cv2.VideoCapture(
#         str(video_path)
#     )

#     if not capture.isOpened():

#         raise RuntimeError(
#             "Could not open video for proof generation"
#         )

#     fps = capture.get(
#         cv2.CAP_PROP_FPS
#     )

#     if not fps or fps <= 0:
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
#         else 0
#     )

#     if width <= 0 or height <= 0:

#         capture.release()

#         raise RuntimeError(
#             "Invalid video dimensions"
#         )

#     event_time = event["time"]

#     start_time = max(
#         0.0,
#         event_time - PRE_EVENT_SECONDS,
#     )

#     end_time = min(
#         duration,
#         event_time + POST_EVENT_SECONDS,
#     )

#     current_duration = (
#         end_time - start_time
#     )

#     # Try to create a full 10-second proof window
#     # whenever the source video is long enough.
#     if (
#         current_duration
#         < PROOF_DURATION_SECONDS
#     ):

#         missing = (
#             PROOF_DURATION_SECONDS
#             - current_duration
#         )

#         extra_before = min(
#             missing,
#             start_time,
#         )

#         start_time -= extra_before
#         missing -= extra_before

#         extra_after = min(
#             missing,
#             duration - end_time,
#         )

#         end_time += extra_after

#     start_frame = max(
#         0,
#         int(start_time * fps),
#     )

#     end_frame = min(
#         max(0, total_frames - 1),
#         int(end_time * fps),
#     )

#     capture.set(
#         cv2.CAP_PROP_POS_FRAMES,
#         start_frame,
#     )

#     raw_path = (
#         proof_path.with_name(
#             f"{proof_path.stem}_raw.mp4"
#         )
#     )

#     fourcc = cv2.VideoWriter_fourcc(
#         *"mp4v"
#     )

#     writer = cv2.VideoWriter(
#         str(raw_path),
#         fourcc,
#         fps,
#         (width, height),
#     )

#     if not writer.isOpened():

#         capture.release()

#         raise RuntimeError(
#             "Could not create temporary proof video"
#         )

#     frame_number = start_frame

#     try:

#         while frame_number <= end_frame:

#             success, frame = (
#                 capture.read()
#             )

#             if not success:
#                 break

#             current_time = (
#                 frame_number / fps
#             )

#             people = detect_people(
#                 frame
#             )

#             draw_people(
#                 frame,
#                 people,
#             )

#             proof_event = {
#                 **event,
#                 "time": event["time"],
#                 "after_person_count": len(
#                     people
#                 ),
#             }

#             draw_proof_header(
#                 frame,
#                 proof_event,
#             )

#             if (
#                 abs(
#                     current_time
#                     - event_time
#                 )
#                 <= 0.5
#             ):

#                 cv2.rectangle(
#                     frame,
#                     (0, 125),
#                     (width, 160),
#                     (0, 0, 255),
#                     -1,
#                 )

#                 cv2.putText(
#                     frame,
#                     "<<< UNUSUAL EVENT >>>",
#                     (20, 150),
#                     cv2.FONT_HERSHEY_SIMPLEX,
#                     0.65,
#                     (255, 255, 255),
#                     2,
#                 )

#             writer.write(frame)

#             frame_number += 1

#     finally:

#         writer.release()
#         capture.release()

#     try:

#         convert_proof_to_h264(
#             raw_path,
#             proof_path,
#         )

#     finally:

#         if raw_path.exists():

#             try:
#                 raw_path.unlink()
#             except OSError:
#                 pass

#     actual_duration = (
#         max(
#             0,
#             end_frame - start_frame + 1,
#         )
#         / fps
#     )

#     return {
#         "start_time": start_time,
#         "end_time": end_time,
#         "duration": actual_duration,
#     }


# # ============================================================
# # BACKGROUND VIDEO ANALYSIS
# # ============================================================

# def process_recorded_video(
#     video_id: str,
#     video_path: str,
# ):

#     capture = None

#     try:

#         analysis_jobs[video_id] = {
#             "status": "PROCESSING",
#             "video_id": video_id,
#             "progress": 0,
#             "message": "Video analysis started",
#         }

#         input_path = Path(
#             video_path
#         )

#         if not input_path.exists():

#             raise FileNotFoundError(
#                 f"Video not found: {input_path}"
#             )

#         capture = cv2.VideoCapture(
#             str(input_path)
#         )

#         if not capture.isOpened():

#             raise RuntimeError(
#                 "Could not open recorded video"
#             )

#         fps = capture.get(
#             cv2.CAP_PROP_FPS
#         )

#         if not fps or fps <= 0:
#             fps = 25.0

#         total_frames = int(
#             capture.get(
#                 cv2.CAP_PROP_FRAME_COUNT
#             )
#         )

#         duration = (
#             total_frames / fps
#             if total_frames > 0
#             else 0
#         )

#         frame_count = 0
#         processed_frames = 0
#         detected_frames = 0
#         total_person_detections = 0

#         frame_counts = []

#         while True:

#             success, frame = (
#                 capture.read()
#             )

#             if not success:
#                 break

#             frame_count += 1

#             if (
#                 frame_count
#                 % ANALYSIS_FRAME_SKIP
#                 != 0
#             ):
#                 continue

#             processed_frames += 1

#             people = detect_people(
#                 frame
#             )

#             person_count = len(
#                 people
#             )

#             if person_count > 0:

#                 detected_frames += 1

#                 total_person_detections += (
#                     person_count
#                 )

#             current_time = (
#                 frame_count / fps
#             )

#             frame_counts.append(
#                 {
#                     "frame": frame_count,
#                     "time": current_time,
#                     "person_count": person_count,
#                 }
#             )

#             if total_frames > 0:

#                 progress = int(
#                     (
#                         frame_count
#                         / total_frames
#                     )
#                     * 100
#                 )

#                 progress = max(
#                     0,
#                     min(99, progress),
#                 )

#             else:
#                 progress = 0

#             analysis_jobs[video_id] = {
#                 "status": "PROCESSING",
#                 "video_id": video_id,
#                 "progress": progress,
#                 "message": (
#                     "Analyzing recorded video"
#                 ),
#                 "total_frames": total_frames,
#                 "processed_frames": processed_frames,
#                 "frames_with_people": detected_frames,
#                 "total_person_detections": (
#                     total_person_detections
#                 ),
#             }

#         capture.release()
#         capture = None

#         event = find_unusual_event(
#             frame_counts,
#             fps,
#             duration,
#         )

#         proof_path = (
#             PROOF_DIR
#             / f"{video_id}_proof.mp4"
#         )

#         proof_window = create_proof_video(
#             input_path,
#             proof_path,
#             event,
#         )

#         analysis_jobs[video_id] = {
#             "status": "COMPLETED",
#             "video_id": video_id,
#             "progress": 100,
#             "message": (
#                 "Video analysis completed"
#             ),

#             "total_frames": total_frames,

#             "processed_frames": (
#                 processed_frames
#             ),

#             "frames_with_people": (
#                 detected_frames
#             ),

#             "total_person_detections": (
#                 total_person_detections
#             ),

#             "event": {
#                 "type": event["type"],
#                 "time": event["time"],
#                 "score": event["score"],

#                 "before_person_count": (
#                     event[
#                         "before_person_count"
#                     ]
#                 ),

#                 "after_person_count": (
#                     event[
#                         "after_person_count"
#                     ]
#                 ),

#                 "change": event["change"],
#             },

#             "proof_video": (
#                 f"/api/video-analysis/"
#                 f"{video_id}/proof"
#             ),

#             "proof_duration": (
#                 proof_window["duration"]
#             ),

#             "proof_start_time": (
#                 proof_window["start_time"]
#             ),

#             "proof_end_time": (
#                 proof_window["end_time"]
#             ),
#         }

#     except Exception as exc:

#         print(
#             f"Video analysis failed for "
#             f"{video_id}: {exc}"
#         )

#         analysis_jobs[video_id] = {
#             "status": "FAILED",
#             "video_id": video_id,
#             "progress": 0,
#             "message": (
#                 "Video analysis failed"
#             ),
#             "error": str(exc),
#         }

#     finally:

#         if capture is not None:
#             capture.release()


# # ============================================================
# # UPLOAD RECORDED VIDEO
# # ============================================================

# @router.post("/upload")
# async def upload_recorded_video(
#     file: UploadFile = File(...),
# ):

#     if not file.filename:

#         raise HTTPException(
#             status_code=400,
#             detail="Video filename is required",
#         )

#     original_name = Path(
#         file.filename
#     ).name

#     extension = Path(
#         original_name
#     ).suffix.lower()

#     if extension not in ALLOWED_EXTENSIONS:

#         raise HTTPException(
#             status_code=400,
#             detail=(
#                 "Unsupported video format. "
#                 "Use MP4, AVI, MOV, or WEBM."
#             ),
#         )

#     if (
#         file.content_type
#         and file.content_type
#         not in ALLOWED_VIDEO_TYPES
#     ):

#         raise HTTPException(
#             status_code=400,
#             detail=(
#                 "Unsupported video MIME type."
#             ),
#         )

#     video_id = str(
#         uuid.uuid4()
#     )

#     video_path = (
#         UPLOAD_DIR
#         / f"{video_id}{extension}"
#     )

#     try:

#         with video_path.open(
#             "wb"
#         ) as output:

#             while True:

#                 chunk = await file.read(
#                     1024 * 1024
#                 )

#                 if not chunk:
#                     break

#                 output.write(chunk)

#     finally:

#         await file.close()

#     return {
#         "video_id": video_id,
#         "filename": original_name,
#         "status": "UPLOADED",
#     }


# # ============================================================
# # START ANALYSIS
# # ============================================================

# @router.post("/{video_id}/analyze")
# async def analyze_recorded_video(
#     video_id: str,
#     background_tasks: BackgroundTasks,
# ):

#     video_path = find_video(
#         video_id
#     )

#     if video_path is None:

#         raise HTTPException(
#             status_code=404,
#             detail="Recorded video not found",
#         )

#     existing_job = (
#         analysis_jobs.get(video_id)
#     )

#     if existing_job:

#         existing_status = (
#             existing_job.get("status")
#         )

#         if existing_status == "PROCESSING":

#             return {
#                 "video_id": video_id,
#                 "status": "ALREADY_PROCESSING",
#                 "message": (
#                     "Video analysis is already running"
#                 ),
#             }

#         if existing_status == "QUEUED":

#             return {
#                 "video_id": video_id,
#                 "status": "ALREADY_QUEUED",
#                 "message": (
#                     "Video analysis is already queued"
#                 ),
#             }

#         if existing_status == "COMPLETED":

#             return {
#                 "video_id": video_id,
#                 "status": "ALREADY_COMPLETED",
#                 "message": (
#                     "Video has already been analyzed"
#                 ),
#             }

#     analysis_jobs[video_id] = {
#         "status": "QUEUED",
#         "video_id": video_id,
#         "progress": 0,
#         "message": (
#             "Video analysis queued"
#         ),
#     }

#     background_tasks.add_task(
#         process_recorded_video,
#         video_id,
#         str(video_path),
#     )

#     return {
#         "video_id": video_id,
#         "status": "ANALYSIS_STARTED",
#         "message": (
#             "Video analysis started in the background"
#         ),
#         "status_url": (
#             f"/api/video-analysis/"
#             f"{video_id}/analysis"
#         ),
#         "proof_url": (
#             f"/api/video-analysis/"
#             f"{video_id}/proof"
#         ),
#     }


# # ============================================================
# # GET ANALYSIS STATUS
# # ============================================================

# @router.get("/{video_id}/analysis")
# async def get_analysis_status(
#     video_id: str,
# ):

#     job = analysis_jobs.get(
#         video_id
#     )

#     if not job:

#         raise HTTPException(
#             status_code=404,
#             detail="Analysis job not found",
#         )

#     return job


# # ============================================================
# # GET PROOF VIDEO
# # ============================================================

# @router.get("/{video_id}/proof")
# async def get_proof_video(
#     video_id: str,
# ):

#     proof_path = (
#         PROOF_DIR
#         / f"{video_id}_proof.mp4"
#     )

#     if not proof_path.exists():

#         job = analysis_jobs.get(
#             video_id
#         )

#         if job and job.get("status") in {
#             "QUEUED",
#             "PROCESSING",
#         }:

#             raise HTTPException(
#                 status_code=202,
#                 detail=(
#                     "Proof video is still "
#                     "being generated"
#                 ),
#             )

#         raise HTTPException(
#             status_code=404,
#             detail="Proof video not found",
#         )

#     return FileResponse(
#         path=str(proof_path),
#         media_type="video/mp4",
#         filename=(
#             f"{video_id}_proof.mp4"
#         ),
#         content_disposition_type="inline",
#         headers={
#             "Accept-Ranges": "bytes",
#             "Cache-Control": (
#                 "no-cache, "
#                 "no-store, "
#                 "must-revalidate"
#             ),
#             "Pragma": "no-cache",
#             "Expires": "0",
#         },
#     )












from __future__ import annotations

import asyncio
import json
import math
import os
import shutil
import subprocess
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
from fastapi import (
    APIRouter,
    HTTPException,
    UploadFile,
    File,
)
from fastapi.responses import FileResponse
from ultralytics import YOLO


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/api/video-analysis",
    tags=["video-analysis"],
)


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[3]

UPLOAD_DIR = (
    PROJECT_ROOT
    / "data"
    / "recorded_videos"
)

PROOF_DIR = (
    PROJECT_ROOT
    / "data"
    / "proof_videos"
)

JOB_DIR = (
    PROJECT_ROOT
    / "data"
    / "historical_jobs"
)

UPLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

PROOF_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

JOB_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# FFMPEG
# ============================================================

FFMPEG_BIN = (
    os.getenv("FFMPEG_BIN")
    or shutil.which("ffmpeg")
)


def require_ffmpeg() -> str:
    if not FFMPEG_BIN:
        raise RuntimeError(
            "FFmpeg was not found. "
            "Make sure ffmpeg is in PATH or set "
            "FFMPEG_BIN to ffmpeg.exe."
        )

    return FFMPEG_BIN


# ============================================================
# CONFIGURATION
# ============================================================

ALLOWED_EXTENSIONS = {
    ".mp4",
    ".avi",
    ".mov",
    ".webm",
    ".mkv",
}

ALLOWED_VIDEO_TYPES = {
    "video/mp4",
    "video/avi",
    "video/x-msvideo",
    "video/mov",
    "video/quicktime",
    "video/webm",
    "video/x-matroska",
    "",
}

CONFIDENCE_THRESHOLD = float(
    os.getenv(
        "HISTORICAL_CONFIDENCE",
        "0.40",
    )
)

ANALYSIS_FRAME_SKIP = max(
    1,
    int(
        os.getenv(
            "HISTORICAL_FRAME_SKIP",
            "3",
        )
    ),
)

UNUSUAL_PERSON_COUNT = max(
    1,
    int(
        os.getenv(
            "HISTORICAL_UNUSUAL_PERSON_COUNT",
            "4",
        )
    ),
)

UNUSUAL_PERSON_CHANGE = max(
    1,
    int(
        os.getenv(
            "HISTORICAL_UNUSUAL_PERSON_CHANGE",
            "2",
        )
    ),
)

UNUSUAL_CONFIRMATION_FRAMES = max(
    1,
    int(
        os.getenv(
            "HISTORICAL_CONFIRMATION_FRAMES",
            "5",
        )
    ),
)

PRE_EVENT_SECONDS = max(
    0.0,
    float(
        os.getenv(
            "HISTORICAL_PRE_EVENT_SECONDS",
            "4",
        )
    ),
)

POST_EVENT_SECONDS = max(
    0.0,
    float(
        os.getenv(
            "HISTORICAL_POST_EVENT_SECONDS",
            "6",
        )
    ),
)

PROOF_DURATION_SECONDS = max(
    1.0,
    float(
        os.getenv(
            "HISTORICAL_PROOF_DURATION_SECONDS",
            "10",
        )
    ),
)

MAX_UPLOAD_SIZE_BYTES = max(
    1,
    int(
        os.getenv(
            "HISTORICAL_MAX_UPLOAD_BYTES",
            str(2 * 1024 * 1024 * 1024),
        )
    ),
)

MAX_CONCURRENT_HISTORICAL_JOBS = max(
    1,
    int(
        os.getenv(
            "HISTORICAL_MAX_CONCURRENT_JOBS",
            "1",
        )
    ),
)


# ============================================================
# MODEL
# ============================================================

MODEL_PATH = os.getenv(
    "HISTORICAL_YOLO_MODEL",
    "yolo11n.pt",
).strip()

if not MODEL_PATH:
    MODEL_PATH = "yolo11n.pt"


_MODEL: YOLO | None = None
_MODEL_LOCK = threading.Lock()


def get_model() -> YOLO:
    """
    Lazy model initialization.

    The FastAPI application can start even if the model cannot
    currently be loaded. The failure is isolated to the
    historical-analysis job.
    """

    global _MODEL

    if _MODEL is not None:
        return _MODEL

    with _MODEL_LOCK:
        if _MODEL is None:
            print(
                "[HistoricalAnalysis] "
                f"Loading YOLO model: {MODEL_PATH}"
            )

            _MODEL = YOLO(MODEL_PATH)

            print(
                "[HistoricalAnalysis] "
                "YOLO model loaded successfully."
            )

    return _MODEL


# ============================================================
# JOB EXECUTOR
# ============================================================

JOB_EXECUTOR = ThreadPoolExecutor(
    max_workers=MAX_CONCURRENT_HISTORICAL_JOBS,
    thread_name_prefix="historical-analysis",
)


# ============================================================
# IN-PROCESS LOCK
# ============================================================

JOB_STATE_LOCK = threading.Lock()


# ============================================================
# JOB STATE
# ============================================================

analysis_jobs: dict[str, dict[str, Any]] = {}


# ============================================================
# TIME HELPERS
# ============================================================

def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


# ============================================================
# JOB PERSISTENCE
# ============================================================

def job_path(video_id: str) -> Path:
    return JOB_DIR / f"{video_id}.json"


def save_job(job: dict[str, Any]) -> None:
    """
    Atomically persist historical-analysis state.

    This protects job metadata from disappearing merely because
    FastAPI's in-memory dictionary is recreated.
    """

    video_id = str(job["video_id"])

    path = job_path(video_id)
    temp_path = path.with_suffix(".tmp")

    payload = dict(job)
    payload["updated_at"] = utc_now_iso()

    try:
        with temp_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                payload,
                file,
                indent=2,
                ensure_ascii=False,
            )

        os.replace(
            temp_path,
            path,
        )

    except Exception as exc:
        print(
            "[HistoricalAnalysis] "
            f"Could not persist job {video_id}: "
            f"{type(exc).__name__}: {exc}"
        )

        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception:
            pass


def update_job(
    video_id: str,
    **updates,
) -> dict[str, Any]:
    with JOB_STATE_LOCK:
        existing = analysis_jobs.get(
            video_id,
            {
                "video_id": video_id,
            },
        )

        existing.update(updates)
        existing["updated_at"] = utc_now_iso()

        analysis_jobs[video_id] = dict(existing)

        save_job(existing)

        return dict(existing)


def load_job(video_id: str) -> dict[str, Any] | None:
    with JOB_STATE_LOCK:
        existing = analysis_jobs.get(video_id)

        if existing is not None:
            return dict(existing)

    path = job_path(video_id)

    if not path.exists():
        return None

    try:
        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            job = json.load(file)

        if not isinstance(job, dict):
            return None

        with JOB_STATE_LOCK:
            analysis_jobs[video_id] = dict(job)

        return dict(job)

    except Exception as exc:
        print(
            "[HistoricalAnalysis] "
            f"Could not read job {video_id}: "
            f"{type(exc).__name__}: {exc}"
        )

        return None


# ============================================================
# VIDEO DISCOVERY
# ============================================================

def find_video(
    video_id: str,
) -> Path | None:

    if not video_id:
        return None

    for path in UPLOAD_DIR.glob(
        f"{video_id}.*"
    ):
        if path.is_file():
            return path

    return None


# ============================================================
# SAFE FILE VALIDATION
# ============================================================

def validate_video_file(
    path: Path,
) -> None:

    if not path.exists():
        raise FileNotFoundError(
            f"Video not found: {path}"
        )

    if not path.is_file():
        raise RuntimeError(
            "Uploaded video path is not a file."
        )

    if path.stat().st_size <= 0:
        raise RuntimeError(
            "Uploaded video is empty."
        )


# ============================================================
# DETECT PEOPLE
# ============================================================

def detect_people(
    frame,
) -> list[dict]:

    model = get_model()

    results = model.predict(
        frame,
        verbose=False,
        conf=CONFIDENCE_THRESHOLD,
        classes=[0],
    )

    people: list[dict] = []

    for result in results:
        if result.boxes is None:
            continue

        for box in result.boxes:
            class_id = int(
                box.cls[0].item()
            )

            if class_id != 0:
                continue

            confidence = float(
                box.conf[0].item()
            )

            if not math.isfinite(confidence):
                continue

            coordinates = [
                float(value)
                for value in box.xyxy[0]
                .tolist()
            ]

            if len(coordinates) != 4:
                continue

            if not all(
                math.isfinite(value)
                for value in coordinates
            ):
                continue

            x1, y1, x2, y2 = coordinates

            people.append(
                {
                    "bbox": [
                        x1,
                        y1,
                        x2,
                        y2,
                    ],
                    "confidence": confidence,
                }
            )

    return people


# ============================================================
# DRAW PEOPLE
# ============================================================

def draw_people(
    frame,
    people: list[dict],
) -> None:

    for person in people:
        x1, y1, x2, y2 = map(
            int,
            person["bbox"],
        )

        confidence = float(
            person["confidence"]
        )

        cv2.rectangle(
            frame,
            (x1, y1),
            (x2, y2),
            (0, 255, 0),
            2,
        )

        cv2.putText(
            frame,
            f"Person {confidence:.2f}",
            (
                x1,
                max(y1 - 10, 20),
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
        )


# ============================================================
# PROOF HEADER
# ============================================================

def draw_proof_header(
    frame,
    event: dict[str, Any],
) -> None:

    height, width = frame.shape[:2]

    header_height = min(
        125,
        max(1, height),
    )

    cv2.rectangle(
        frame,
        (0, 0),
        (width, header_height),
        (0, 0, 0),
        -1,
    )

    cv2.putText(
        frame,
        "AI SURVEILLANCE PROOF",
        (20, 32),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        (0, 255, 255),
        2,
    )

    cv2.putText(
        frame,
        f"Event: {event['type']}",
        (20, 62),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 255, 255),
        2,
    )

    cv2.putText(
        frame,
        f"People: {event['after_person_count']}",
        (20, 88),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 255, 255),
        2,
    )

    cv2.putText(
        frame,
        f"Event time: {event['time']:.2f}s",
        (20, 114),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.50,
        (0, 255, 255),
        2,
    )


# ============================================================
# FIND UNUSUAL EVENT
# ============================================================

def find_unusual_event(
    frame_counts: list[dict],
    fps: float,
    duration: float,
) -> dict[str, Any]:

    if not frame_counts:
        return {
            "time": 0.0,
            "type": "NO_EVENT",
            "score": 0,
            "before_person_count": 0,
            "after_person_count": 0,
            "change": 0,
        }

    best_event = {
        "time": 0.0,
        "type": "NO_STRONG_EVENT",
        "score": 0,
        "before_person_count": 0,
        "after_person_count": 0,
        "change": 0,
    }

    previous_count = int(
        frame_counts[0]["person_count"]
    )

    consecutive_unusual = 0

    for current in frame_counts[1:]:
        current_count = int(
            current["person_count"]
        )

        change = (
            current_count
            - previous_count
        )

        absolute_change = abs(change)

        unusual = (
            absolute_change
            >= UNUSUAL_PERSON_CHANGE
            and (
                current_count
                >= UNUSUAL_PERSON_COUNT
                or previous_count
                >= UNUSUAL_PERSON_COUNT
            )
        )

        if unusual:
            consecutive_unusual += 1
        else:
            consecutive_unusual = 0

        if unusual:
            score = absolute_change

            if (
                consecutive_unusual
                >= UNUSUAL_CONFIRMATION_FRAMES
            ):
                score += 1

            if score > best_event["score"]:
                event_type = (
                    "SUDDEN_PERSON_INCREASE"
                    if change > 0
                    else "SUDDEN_PERSON_DECREASE"
                )

                best_event = {
                    "time": float(
                        current["time"]
                    ),
                    "type": event_type,
                    "score": score,
                    "before_person_count": (
                        previous_count
                    ),
                    "after_person_count": (
                        current_count
                    ),
                    "change": change,
                }

        previous_count = current_count

    best_event["time"] = max(
        0.0,
        min(
            float(best_event["time"]),
            max(0.0, float(duration)),
        ),
    )

    return best_event


# ============================================================
# FFMPEG H264 CONVERSION
# ============================================================

def convert_proof_to_h264(
    raw_path: Path,
    final_path: Path,
) -> None:

    ffmpeg = require_ffmpeg()

    temp_h264 = final_path.with_name(
        f"{final_path.stem}_h264_tmp.mp4"
    )

    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(raw_path),
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-profile:v",
        "main",
        "-level:v",
        "3.0",
        "-movflags",
        "+faststart",
        str(temp_h264),
    ]

    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )

        if (
            not temp_h264.exists()
            or temp_h264.stat().st_size == 0
        ):
            raise RuntimeError(
                "FFmpeg completed but did not create "
                "a valid H.264 file."
            )

        os.replace(
            temp_h264,
            final_path,
        )

    except subprocess.CalledProcessError as exc:
        stderr = (
            exc.stderr or ""
        ).strip()

        raise RuntimeError(
            "FFmpeg H.264 conversion failed"
            + (
                f": {stderr}"
                if stderr
                else "."
            )
        ) from exc

    finally:
        if temp_h264.exists():
            try:
                temp_h264.unlink()
            except OSError:
                pass


# ============================================================
# CREATE PROOF VIDEO
# ============================================================

def create_proof_video(
    video_path: Path,
    proof_path: Path,
    event: dict[str, Any],
) -> dict[str, float]:

    capture = cv2.VideoCapture(
        str(video_path)
    )

    if not capture.isOpened():
        raise RuntimeError(
            "Could not open video for proof generation."
        )

    fps = capture.get(
        cv2.CAP_PROP_FPS
    )

    if not fps or fps <= 0:
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

    if width <= 0 or height <= 0:
        capture.release()

        raise RuntimeError(
            "Invalid video dimensions."
        )

    event_time = float(
        event["time"]
    )

    start_time = max(
        0.0,
        event_time - PRE_EVENT_SECONDS,
    )

    end_time = min(
        duration,
        event_time + POST_EVENT_SECONDS,
    )

    current_duration = (
        end_time - start_time
    )

    # Try to obtain the configured proof duration
    # by expanding around the event.
    if (
        current_duration
        < PROOF_DURATION_SECONDS
    ):
        missing = (
            PROOF_DURATION_SECONDS
            - current_duration
        )

        extra_before = min(
            missing,
            start_time,
        )

        start_time -= extra_before
        missing -= extra_before

        extra_after = min(
            missing,
            duration - end_time,
        )

        end_time += extra_after

    start_frame = max(
        0,
        int(start_time * fps),
    )

    end_frame = min(
        max(0, total_frames - 1),
        int(end_time * fps),
    )

    capture.set(
        cv2.CAP_PROP_POS_FRAMES,
        start_frame,
    )

    raw_path = proof_path.with_name(
        f"{proof_path.stem}_raw.mp4"
    )

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
        capture.release()

        raise RuntimeError(
            "Could not create temporary proof video."
        )

    frame_number = start_frame

    try:
        while frame_number <= end_frame:
            success, frame = capture.read()

            if not success:
                break

            current_time = (
                frame_number / fps
            )

            people = detect_people(
                frame
            )

            draw_people(
                frame,
                people,
            )

            proof_event = {
                **event,
                "after_person_count": len(
                    people
                ),
            }

            draw_proof_header(
                frame,
                proof_event,
            )

            if (
                abs(
                    current_time
                    - event_time
                )
                <= 0.5
            ):
                marker_top = min(
                    125,
                    max(0, height - 1),
                )

                marker_bottom = min(
                    160,
                    max(0, height - 1),
                )

                if marker_bottom > marker_top:
                    cv2.rectangle(
                        frame,
                        (0, marker_top),
                        (
                            width,
                            marker_bottom,
                        ),
                        (0, 0, 255),
                        -1,
                    )

                cv2.putText(
                    frame,
                    "<<< UNUSUAL EVENT >>>",
                    (20, min(150, max(20, height - 5))),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (255, 255, 255),
                    2,
                )

            writer.write(frame)

            frame_number += 1

    finally:
        writer.release()
        capture.release()

    try:
        convert_proof_to_h264(
            raw_path,
            proof_path,
        )

    finally:
        if raw_path.exists():
            try:
                raw_path.unlink()
            except OSError:
                pass

    actual_frames = max(
        0,
        end_frame - start_frame + 1,
    )

    actual_duration = (
        actual_frames / fps
    )

    return {
        "start_time": start_time,
        "end_time": end_time,
        "duration": actual_duration,
    }


# ============================================================
# HISTORICAL VIDEO ANALYSIS
# ============================================================

def process_recorded_video(
    video_id: str,
    video_path: str,
) -> None:

    capture = None

    try:
        update_job(
            video_id,
            status="PROCESSING",
            progress=0,
            message="Video analysis started.",
            started_at=utc_now_iso(),
        )

        input_path = Path(video_path)

        validate_video_file(
            input_path
        )

        # -----------------------------------------------------
        # Open source video
        # -----------------------------------------------------

        capture = cv2.VideoCapture(
            str(input_path)
        )

        if not capture.isOpened():
            raise RuntimeError(
                "Could not open recorded video."
            )

        fps = capture.get(
            cv2.CAP_PROP_FPS
        )

        if not fps or fps <= 0:
            fps = 25.0

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

        frame_count = 0
        processed_frames = 0
        detected_frames = 0
        total_person_detections = 0

        # -----------------------------------------------------
        # Important:
        #
        # Do NOT store every analyzed frame forever.
        #
        # Keep only the sampled person-count observations
        # needed for the current anomaly detector.
        #
        # This is still an in-memory list, but its size is
        # proportional to sampled frames rather than every
        # source frame.
        # -----------------------------------------------------

        frame_counts: list[dict] = []

        while True:
            success, frame = capture.read()

            if not success:
                break

            frame_count += 1

            if (
                frame_count
                % ANALYSIS_FRAME_SKIP
                != 0
            ):
                continue

            processed_frames += 1

            people = detect_people(
                frame
            )

            person_count = len(
                people
            )

            if person_count > 0:
                detected_frames += 1
                total_person_detections += (
                    person_count
                )

            current_time = (
                frame_count / fps
            )

            frame_counts.append(
                {
                    "frame": frame_count,
                    "time": current_time,
                    "person_count": person_count,
                }
            )

            if total_frames > 0:
                progress = int(
                    (
                        frame_count
                        / total_frames
                    )
                    * 100
                )

                progress = max(
                    0,
                    min(95, progress),
                )
            else:
                progress = 0

            update_job(
                video_id,
                status="PROCESSING",
                progress=progress,
                message="Analyzing recorded video.",
                total_frames=total_frames,
                processed_frames=processed_frames,
                frames_with_people=detected_frames,
                total_person_detections=(
                    total_person_detections
                ),
            )

        capture.release()
        capture = None

        # -----------------------------------------------------
        # Find unusual event
        # -----------------------------------------------------

        event = find_unusual_event(
            frame_counts,
            fps,
            duration,
        )

        # -----------------------------------------------------
        # NO EVENT
        #
        # Do not waste another full YOLO pass creating a proof
        # video when there is no detected unusual event.
        # -----------------------------------------------------

        if event["type"] in {
            "NO_EVENT",
            "NO_STRONG_EVENT",
        }:
            update_job(
                video_id,
                status="COMPLETED",
                progress=100,
                message=(
                    "Video analysis completed. "
                    "No strong unusual event was detected."
                ),
                total_frames=total_frames,
                processed_frames=processed_frames,
                frames_with_people=detected_frames,
                total_person_detections=(
                    total_person_detections
                ),
                event={
                    "type": event["type"],
                    "time": event["time"],
                    "score": event["score"],
                    "before_person_count": (
                        event[
                            "before_person_count"
                        ]
                    ),
                    "after_person_count": (
                        event[
                            "after_person_count"
                        ]
                    ),
                    "change": event["change"],
                },
                proof_video=None,
                proof_duration=0,
                proof_start_time=None,
                proof_end_time=None,
                completed_at=utc_now_iso(),
            )

            return

        # -----------------------------------------------------
        # Create proof
        # -----------------------------------------------------

        proof_path = (
            PROOF_DIR
            / f"{video_id}_proof.mp4"
        )

        update_job(
            video_id,
            status="GENERATING_PROOF",
            progress=96,
            message="Generating evidence proof video.",
        )

        proof_window = create_proof_video(
            input_path,
            proof_path,
            event,
        )

        # -----------------------------------------------------
        # Completed
        # -----------------------------------------------------

        update_job(
            video_id,
            status="COMPLETED",
            progress=100,
            message="Video analysis completed.",
            total_frames=total_frames,
            processed_frames=processed_frames,
            frames_with_people=detected_frames,
            total_person_detections=(
                total_person_detections
            ),
            event={
                "type": event["type"],
                "time": event["time"],
                "score": event["score"],
                "before_person_count": (
                    event[
                        "before_person_count"
                    ]
                ),
                "after_person_count": (
                    event[
                        "after_person_count"
                    ]
                ),
                "change": event["change"],
            },
            proof_video=(
                f"/api/video-analysis/"
                f"{video_id}/proof"
            ),
            proof_duration=(
                proof_window["duration"]
            ),
            proof_start_time=(
                proof_window["start_time"]
            ),
            proof_end_time=(
                proof_window["end_time"]
            ),
            completed_at=utc_now_iso(),
        )

    except Exception as exc:
        print(
            "[HistoricalAnalysis] "
            f"Analysis failed | "
            f"Video={video_id} | "
            f"Error={type(exc).__name__}: {exc}"
        )

        update_job(
            video_id,
            status="FAILED",
            progress=0,
            message="Video analysis failed.",
            error=str(exc),
            failed_at=utc_now_iso(),
        )

    finally:
        if capture is not None:
            try:
                capture.release()
            except Exception:
                pass


# ============================================================
# START JOB
# ============================================================

def submit_historical_job(
    video_id: str,
    video_path: Path,
) -> None:

    JOB_EXECUTOR.submit(
        process_recorded_video,
        video_id,
        str(video_path),
    )


# ============================================================
# UPLOAD RECORDED VIDEO
# ============================================================

@router.post("/upload")
async def upload_recorded_video(
    file: UploadFile = File(...),
):
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Video filename is required.",
        )

    original_name = Path(
        file.filename
    ).name

    extension = Path(
        original_name
    ).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported video format. "
                "Use MP4, AVI, MOV, WEBM, or MKV."
            ),
        )

    content_type = (
        file.content_type or ""
    ).lower()

    if content_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported video MIME type.",
        )

    video_id = str(
        uuid.uuid4()
    )

    final_path = (
        UPLOAD_DIR
        / f"{video_id}{extension}"
    )

    temp_path = (
        UPLOAD_DIR
        / f".{video_id}.uploading"
    )

    total_bytes = 0

    try:
        with temp_path.open(
            "wb"
        ) as output:

            while True:
                chunk = await file.read(
                    1024 * 1024
                )

                if not chunk:
                    break

                total_bytes += len(chunk)

                if (
                    total_bytes
                    > MAX_UPLOAD_SIZE_BYTES
                ):
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            "Video file is too large. "
                            f"Maximum allowed size is "
                            f"{MAX_UPLOAD_SIZE_BYTES} bytes."
                        ),
                    )

                output.write(chunk)

        if total_bytes <= 0:
            raise HTTPException(
                status_code=400,
                detail="Uploaded video is empty.",
            )

        os.replace(
            temp_path,
            final_path,
        )

    except HTTPException:
        raise

    except Exception as exc:
        print(
            "[HistoricalAnalysis] "
            f"Upload failed: "
            f"{type(exc).__name__}: {exc}"
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to save uploaded video.",
        ) from exc

    finally:
        await file.close()

        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception:
            pass

    return {
        "video_id": video_id,
        "filename": original_name,
        "status": "UPLOADED",
        "size_bytes": total_bytes,
    }


# ============================================================
# START ANALYSIS
# ============================================================

@router.post("/{video_id}/analyze")
async def analyze_recorded_video(
    video_id: str,
):
    video_path = find_video(
        video_id
    )

    if video_path is None:
        raise HTTPException(
            status_code=404,
            detail="Recorded video not found.",
        )

    existing_job = load_job(
        video_id
    )

    if existing_job:
        existing_status = existing_job.get(
            "status"
        )

        if existing_status in {
            "QUEUED",
            "PROCESSING",
            "GENERATING_PROOF",
        }:
            return {
                "video_id": video_id,
                "status": "ALREADY_PROCESSING",
                "message": (
                    "Video analysis is already "
                    "queued or running."
                ),
                "status_url": (
                    f"/api/video-analysis/"
                    f"{video_id}/analysis"
                ),
            }

        if existing_status == "COMPLETED":
            return {
                "video_id": video_id,
                "status": "ALREADY_COMPLETED",
                "message": (
                    "Video has already been analyzed."
                ),
                "status_url": (
                    f"/api/video-analysis/"
                    f"{video_id}/analysis"
                ),
            }

    update_job(
        video_id,
        status="QUEUED",
        progress=0,
        message="Video analysis queued.",
        queued_at=utc_now_iso(),

    )

    try:
        submit_historical_job(
            video_id,
            video_path,
        )

    except Exception as exc:
        update_job(
            video_id,
            status="FAILED",
            progress=0,
            message="Unable to queue analysis.",
            error=str(exc),
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to queue video analysis.",
        ) from exc

    return {
        "video_id": video_id,
        "status": "ANALYSIS_STARTED",
        "message": (
            "Video analysis started in the background."
        ),
        "status_url": (
            f"/api/video-analysis/"
            f"{video_id}/analysis"
        ),
        "proof_url": (
            f"/api/video-analysis/"
            f"{video_id}/proof"
        ),
    }


# ============================================================
# GET ANALYSIS STATUS
# ============================================================

@router.get("/{video_id}/analysis")
async def get_analysis_status(
    video_id: str,
):
    job = load_job(
        video_id
    )

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Analysis job not found.",
        )

    return job


# ============================================================
# GET PROOF VIDEO
# ============================================================

@router.get("/{video_id}/proof")
async def get_proof_video(
    video_id: str,
):
    proof_path = (
        PROOF_DIR
        / f"{video_id}_proof.mp4"
    )

    if not proof_path.exists():
        job = load_job(
            video_id
        )

        if job and job.get("status") in {
            "QUEUED",
            "PROCESSING",
            "GENERATING_PROOF",
        }:
            raise HTTPException(
                status_code=202,
                detail=(
                    "Proof video is still "
                    "being generated."
                ),
            )

        if job and job.get("status") == "COMPLETED":
            raise HTTPException(
                status_code=404,
                detail=(
                    "No proof video was generated "
                    "because no strong unusual event "
                    "was detected."
                ),
            )

        raise HTTPException(
            status_code=404,
            detail="Proof video not found.",
        )

    return FileResponse(
        path=str(proof_path),
        media_type="video/mp4",
        filename=(
            f"{video_id}_proof.mp4"
        ),
        content_disposition_type="inline",
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": (
                "no-cache, "
                "no-store, "
                "must-revalidate"
            ),
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )
