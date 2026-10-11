"""Camera configuration API."""

from __future__ import annotations
from pathlib import Path

from fastapi.responses import StreamingResponse
import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.app.cameras.registry import CameraConfig, CameraRegistry
from backend.app.cameras.store import (
    delete_camera_record,
    get_camera_record,
    list_camera_records,
    save_camera_record,
)
from backend.app.monitoring.agent_registry import agent_registry
from backend.app.cameras.runtime import camera_runtime_manager


router = APIRouter(prefix="/api/cameras", tags=["cameras"])

##


PROJECT_ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_ROOT = PROJECT_ROOT / "data" / "evidence"


@router.get("/{camera_id}/stream")
async def camera_stream(camera_id: str):
    record = await asyncio.to_thread(get_camera_record, camera_id)

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Camera not found",
        )

    # Use the registered camera ID to locate its latest frame.
    frame_path = (
        EVIDENCE_ROOT
        / str(record["camera_id"])
        / "latest.jpg"
    )

    async def generate_frames():
        last_mtime = None

        while True:
            try:
                if not frame_path.is_file():
                    await asyncio.sleep(0.2)
                    continue

                mtime = await asyncio.to_thread(
                    lambda: frame_path.stat().st_mtime_ns
                )

                if mtime == last_mtime:
                    await asyncio.sleep(0.1)
                    continue

                frame = await asyncio.to_thread(frame_path.read_bytes)

                if not frame:
                    await asyncio.sleep(0.1)
                    continue

                last_mtime = mtime

                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    + f"Content-Length: {len(frame)}\r\n\r\n".encode()
                    + frame
                    + b"\r\n"
                )

            except FileNotFoundError:
                await asyncio.sleep(0.2)

    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

##

class CameraCreate(BaseModel):
    camera_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    source: str = Field(min_length=1)
    location: str = "default"
    enabled: bool = True
    policy: dict[str, Any] | None = None


class CameraUpdate(BaseModel):
    name: str | None = None
    source: str | None = None
    location: str | None = None
    enabled: bool | None = None
    policy: dict[str, Any] | None = None


def _config_from_payload(payload: dict[str, Any]) -> CameraConfig:
    camera_id = CameraRegistry._normalize_camera_id(str(payload["camera_id"]))
    source = CameraRegistry._normalize_source(str(payload["source"]), camera_id)
    name = CameraRegistry._normalize_name(str(payload["name"]), camera_id)
    location = CameraRegistry._normalize_location(str(payload.get("location", "default")))
    policy = CameraRegistry._parse_policy(payload.get("policy"), camera_id)
    return CameraConfig(
        camera_id=camera_id,
        name=name,
        source=source,
        enabled=bool(payload.get("enabled", True)),
        location=location,
        policy=policy,
    )


def _response(record: dict[str, Any]) -> dict[str, Any]:
    record = dict(record)
    record["source_type"] = CameraConfig(
        camera_id=record["camera_id"],
        name=record["name"],
        source=record["source"],
    ).source_type
    return record


@router.get("")
async def list_cameras() -> list[dict[str, Any]]:
    records = await asyncio.to_thread(list_camera_records)
    if not records:
        registry = CameraRegistry.from_environment()
        records = [
            {
                "camera_id": camera.camera_id,
                "name": camera.name,
                "source": camera.source,
                "source_type": camera.source_type,
                "enabled": camera.enabled,
                "location": camera.location,
                "status": "REGISTERED",
            }
            for camera in registry.get_all()
        ]
        return records
    return [_response(record) for record in records]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_camera(payload: CameraCreate) -> dict[str, Any]:
    if await asyncio.to_thread(get_camera_record, payload.camera_id):
        raise HTTPException(status_code=409, detail="Camera already exists")
    try:
        camera = _config_from_payload(payload.model_dump())
        initial_status = "ERROR" if camera.source_type == "invalid" else "REGISTERED"
        record = await asyncio.to_thread(
            save_camera_record,
            camera,
            status=initial_status,
        )
        camera_runtime_manager.sync_camera(camera)
        return _response(record)
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/{camera_id}")
async def get_camera(camera_id: str) -> dict[str, Any]:
    record = await asyncio.to_thread(get_camera_record, camera_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    return _response(record)


@router.get("/{camera_id}/health")
async def camera_health(camera_id: str) -> dict[str, Any]:
    record = await asyncio.to_thread(get_camera_record, camera_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    detector = agent_registry.get_agent(f"person-detector-{camera_id}")
    tracker = agent_registry.get_agent(f"tracker-{camera_id}")
    agents = [agent for agent in (detector, tracker) if agent is not None]
    statuses = {str(agent.get("status")) for agent in agents}
    if "DEAD" in statuses:
        status = "ERROR"
    elif agents and statuses == {"ALIVE"}:
        status = "ONLINE"
    elif agents:
        status = "DEGRADED"
    else:
        status = record.get("status", "REGISTERED")

    last_heartbeat = max(
        (agent.get("last_heartbeat") for agent in agents if agent.get("last_heartbeat")),
        default=None,
    )
    return {
        "camera_id": camera_id,
        "status": status,
        "last_heartbeat": last_heartbeat,
        "fps": 0.0,
        "frames_processed": 0,
        "uptime_seconds": 0.0,
        "restart_count": sum(int(agent.get("failure_count", 0)) for agent in agents),
        "last_error": None,
        "workers": agents,
    }


@router.get("/{camera_id}/runtime")
async def camera_runtime(camera_id: str) -> dict[str, Any]:
    health = await camera_health(camera_id)
    health["runtime"] = "enabled" if health["status"] not in {"DISABLED", "ERROR"} else "stopped"
    return health


@router.post("/{camera_id}/start")
async def start_camera(camera_id: str) -> dict[str, Any]:
    try:
        await camera_runtime_manager.start(camera_id)
        return await camera_health(camera_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/{camera_id}/stop")
async def stop_camera(camera_id: str) -> dict[str, Any]:
    try:
        await camera_runtime_manager.stop(camera_id)
        return await camera_health(camera_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/{camera_id}/restart")
async def restart_camera(camera_id: str) -> dict[str, Any]:
    try:
        await camera_runtime_manager.restart(camera_id)
        return await camera_health(camera_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.put("/{camera_id}")
async def update_camera(camera_id: str, payload: CameraUpdate) -> dict[str, Any]:
    existing = await asyncio.to_thread(get_camera_record, camera_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    values = dict(existing)
    values.update({key: value for key, value in payload.model_dump(exclude_unset=True).items() if value is not None})
    values["camera_id"] = camera_id
    try:
        camera = _config_from_payload(values)
        record = await asyncio.to_thread(save_camera_record, camera, status=existing["status"])
        camera_runtime_manager.sync_camera(camera)
        return _response(record)
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_camera(camera_id: str) -> None:
    try:
        await camera_runtime_manager.stop(camera_id)
    except (KeyError, ValueError):
        pass
    deleted = await asyncio.to_thread(delete_camera_record, camera_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Camera not found")
    await camera_runtime_manager.remove_camera(camera_id)






















# PROJECT_ROOT = Path(__file__).resolve().parents[3]
# EVIDENCE_ROOT = PROJECT_ROOT / "data" / "evidence"


# @router.get("/{camera_id}/stream")
# async def camera_stream(camera_id: str):
#     record = await asyncio.to_thread(get_camera_record, camera_id)

#     if record is None:
#         raise HTTPException(
#             status_code=404,
#             detail="Camera not found",
#         )

#     # Use the registered camera ID to locate its latest frame.
#     frame_path = (
#         EVIDENCE_ROOT
#         / str(record["camera_id"])
#         / "latest.jpg"
#     )

#     async def generate_frames():
#         last_mtime = None

#         while True:
#             try:
#                 if not frame_path.is_file():
#                     await asyncio.sleep(0.2)
#                     continue

#                 mtime = await asyncio.to_thread(
#                     lambda: frame_path.stat().st_mtime_ns
#                 )

#                 if mtime == last_mtime:
#                     await asyncio.sleep(0.1)
#                     continue

#                 frame = await asyncio.to_thread(frame_path.read_bytes)

#                 if not frame:
#                     await asyncio.sleep(0.1)
#                     continue

#                 last_mtime = mtime

#                 yield (
#                     b"--frame\r\n"
#                     b"Content-Type: image/jpeg\r\n"
#                     + f"Content-Length: {len(frame)}\r\n\r\n".encode()
#                     + frame
#                     + b"\r\n"
#                 )

#             except FileNotFoundError:
#                 await asyncio.sleep(0.2)

#     return StreamingResponse(
#         generate_frames(),
#         media_type="multipart/x-mixed-replace; boundary=frame",
#         headers={
#             "Cache-Control": "no-cache, no-store, must-revalidate",
#             "Pragma": "no-cache",
#             "X-Accel-Buffering": "no",
#         },
#     )