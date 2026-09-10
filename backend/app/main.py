# from fastapi import FastAPI
# from fastapi.responses import StreamingResponse
# from fastapi.middleware.cors import CORSMiddleware

# from backend.api.routes.video_analysis import router as video_analysis_router
# from backend.api.routes.incidents import router as incident_router
# from backend.app.messaging.redis_client import redis_client
# from backend.app.messaging.event_consumer import (
#     get_events,
#     STREAMS,
# )

# import os
# import time


# # ============================================================
# # APP
# # ============================================================

# app = FastAPI(
#     title="CCTV AI Intelligent Surveillance",
#     version="1.0.0",
# )


# # ============================================================
# # CORS
# # ============================================================

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=[
#         "http://localhost:5173",
#         "http://127.0.0.1:5173",
#     ],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# app.include_router(video_analysis_router)
# # ============================================================
# # ROUTERS
# # ============================================================

# app.include_router(
#     incident_router
# )


# # ============================================================
# # HEALTH
# # ============================================================

# @app.get("/health")
# async def health():
#     return {
#         "status": "healthy"
#     }


# # ============================================================
# # REDIS TEST
# # ============================================================

# @app.get("/redis-test")
# async def redis_test():

#     result = await redis_client.ping()

#     return {
#         "redis": (
#             "connected"
#             if result
#             else "not connected"
#         )
#     }


# # ============================================================
# # EVENT STREAMS
# # ============================================================

# @app.get("/events/detection")
# async def detection_events(
#     last_id: str = "0-0",
#     count: int = 20,
# ):

#     events = await get_events(
#         STREAMS["detection"],
#         last_id,
#         count,
#     )

#     return {
#         "stream": STREAMS["detection"],
#         "count": len(events),
#         "events": events,
#     }


# @app.get("/events/tracking")
# async def tracking_events(
#     last_id: str = "0-0",
#     count: int = 20,
# ):

#     events = await get_events(
#         STREAMS["tracking"],
#         last_id,
#         count,
#     )

#     return {
#         "stream": STREAMS["tracking"],
#         "count": len(events),
#         "events": events,
#     }


# @app.get("/events/behavior")
# async def behavior_events(
#     last_id: str = "0-0",
#     count: int = 20,
# ):

#     events = await get_events(
#         STREAMS["behavior"],
#         last_id,
#         count,
#     )

#     return {
#         "stream": STREAMS["behavior"],
#         "count": len(events),
#         "events": events,
#     }


# # ============================================================
# # CAMERA FRAME
# # ============================================================

# # Project root:
# #
# # cctv-ai-intelligent-surveillance/
# #
# # backend/
# #   app/
# #     main.py
# #
# # camera_latest.jpg
# #

# PROJECT_ROOT = os.path.abspath(
#     os.path.join(
#         os.path.dirname(__file__),
#         "..",
#         "..",
#     )
# )

# CAMERA_FRAME = os.path.join(
#     PROJECT_ROOT,
#     "camera_latest.jpg",
# )


# # ============================================================
# # CAMERA STREAM GENERATOR
# # ============================================================

# def generate_camera_stream():

#     print(
#         "=========================================="
#     )
#     print(
#         "Camera stream generator started"
#     )
#     print(
#         f"Camera file: {CAMERA_FRAME}"
#     )
#     print(
#         "=========================================="
#     )

#     last_modified = 0

#     while True:

#         try:

#             # ------------------------------------------------
#             # Check whether camera_latest.jpg exists
#             # ------------------------------------------------

#             if not os.path.exists(CAMERA_FRAME):

#                 time.sleep(0.1)
#                 continue

#             # ------------------------------------------------
#             # Get file modification time
#             # ------------------------------------------------

#             modified = os.path.getmtime(
#                 CAMERA_FRAME
#             )

#             # ------------------------------------------------
#             # Only send a new frame when the image changes
#             # ------------------------------------------------

#             if modified == last_modified:

#                 time.sleep(0.03)
#                 continue

#             last_modified = modified

#             # ------------------------------------------------
#             # Read JPEG
#             # ------------------------------------------------

#             with open(
#                 CAMERA_FRAME,
#                 "rb",
#             ) as file:

#                 frame = file.read()

#             if not frame:

#                 time.sleep(0.03)
#                 continue

#             # ------------------------------------------------
#             # MJPEG frame
#             # ------------------------------------------------

#             yield (
#                 b"--frame\r\n"
#                 b"Content-Type: image/jpeg\r\n"
#                 b"Content-Length: "
#                 + str(len(frame)).encode()
#                 + b"\r\n"
#                 b"Cache-Control: no-cache\r\n"
#                 b"\r\n"
#                 + frame
#                 + b"\r\n"
#             )

#         except GeneratorExit:

#             print(
#                 "Camera stream client disconnected."
#             )

#             break

#         except Exception as error:

#             print(
#                 f"Camera stream error: {error}"
#             )

#             time.sleep(0.5)


# # ============================================================
# # CAMERA STREAM API
# # ============================================================

# @app.get("/api/camera/stream")
# def camera_stream():

#     print(
#         "Camera stream request received."
#     )

#     return StreamingResponse(
#         generate_camera_stream(),
#         media_type=(
#             "multipart/x-mixed-replace;"
#             " boundary=frame"
#         ),
#         headers={
#             "Cache-Control": "no-cache, "
#             "no-store, must-revalidate",
#             "Pragma": "no-cache",
#             "Expires": "0",
#             "Connection": "keep-alive",
#         },
#     )






















from __future__ import annotations

import os
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from backend.api.routes.incidents import router as incident_router
from backend.api.routes.video_analysis import router as video_analysis_router
from backend.app.messaging.event_consumer import STREAMS, get_events
from backend.app.messaging.redis_client import redis_client


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="CCTV AI Intelligent Surveillance",
    version="1.0.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# ROUTERS
# ============================================================

# Historical video analysis API
app.include_router(video_analysis_router)

# Incident management API
#
# IMPORTANT:
# Incident creation/update from Redis events belongs to
# IncidentAgent.
#
# This router is for API access:
#   GET    /api/incidents
#   GET    /api/incidents/stats/summary
#   GET    /api/incidents/{incident_id}
#   PATCH  /api/incidents/{incident_id}/status
#
app.include_router(incident_router)


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
async def health():
    return {
        "status": "healthy",
    }


# ============================================================
# REDIS TEST
# ============================================================

@app.get("/redis-test")
async def redis_test():
    result = await redis_client.ping()

    return {
        "redis": (
            "connected"
            if result
            else "not connected"
        ),
    }


# ============================================================
# EVENT STREAMS
# ============================================================

@app.get("/events/detection")
async def detection_events(
    last_id: str = "0-0",
    count: int = 20,
):
    events = await get_events(
        STREAMS["detection"],
        last_id,
        count,
    )

    return {
        "stream": STREAMS["detection"],
        "count": len(events),
        "events": events,
    }


@app.get("/events/tracking")
async def tracking_events(
    last_id: str = "0-0",
    count: int = 20,
):
    events = await get_events(
        STREAMS["tracking"],
        last_id,
        count,
    )

    return {
        "stream": STREAMS["tracking"],
        "count": len(events),
        "events": events,
    }


@app.get("/events/behavior")
async def behavior_events(
    last_id: str = "0-0",
    count: int = 20,
):
    events = await get_events(
        STREAMS["behavior"],
        last_id,
        count,
    )

    return {
        "stream": STREAMS["behavior"],
        "count": len(events),
        "events": events,
    }


# ============================================================
# DEVELOPMENT CAMERA FRAME
# ============================================================
#
# IMPORTANT:
# This is currently only a development preview.
#
# Final architecture will use:
#
#   /api/cameras/{camera_id}/stream
#
# with frames supplied by the corresponding camera worker.
#
# Do not use this implementation as the final multi-camera
# streaming architecture.
# ============================================================

PROJECT_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
    )
)

CAMERA_FRAME = os.path.join(
    PROJECT_ROOT,
    "camera_latest.jpg",
)


# ============================================================
# CAMERA STREAM GENERATOR
# ============================================================

def generate_camera_stream():
    print(
        "=========================================="
    )
    print(
        "Camera stream generator started"
    )
    print(
        f"Camera file: {CAMERA_FRAME}"
    )
    print(
        "=========================================="
    )

    last_modified = 0.0

    while True:
        try:
            # ------------------------------------------------
            # Check whether camera_latest.jpg exists
            # ------------------------------------------------

            if not os.path.exists(CAMERA_FRAME):
                time.sleep(0.1)
                continue

            # ------------------------------------------------
            # Get file modification time
            # ------------------------------------------------

            modified = os.path.getmtime(
                CAMERA_FRAME
            )

            # ------------------------------------------------
            # Only send a new frame when the image changes
            # ------------------------------------------------

            if modified == last_modified:
                time.sleep(0.03)
                continue

            last_modified = modified

            # ------------------------------------------------
            # Read JPEG
            # ------------------------------------------------

            with open(
                CAMERA_FRAME,
                "rb",
            ) as file:
                frame = file.read()

            if not frame:
                time.sleep(0.03)
                continue

            # ------------------------------------------------
            # MJPEG frame
            # ------------------------------------------------

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: "
                + str(len(frame)).encode()
                + b"\r\n"
                b"Cache-Control: no-cache\r\n"
                b"\r\n"
                + frame
                + b"\r\n"
            )

        except GeneratorExit:
            print(
                "Camera stream client disconnected."
            )
            break

        except Exception as error:
            print(
                f"Camera stream error: {error}"
            )
            time.sleep(0.5)


# ============================================================
# DEVELOPMENT CAMERA STREAM API
# ============================================================

@app.get("/api/camera/stream")
def camera_stream():
    print(
        "Camera stream request received."
    )

    return StreamingResponse(
        generate_camera_stream(),
        media_type=(
            "multipart/x-mixed-replace;"
            " boundary=frame"
        ),
        headers={
            "Cache-Control": (
                "no-cache, "
                "no-store, "
                "must-revalidate"
            ),
            "Pragma": "no-cache",
            "Expires": "0",
            "Connection": "keep-alive",
        },
    )