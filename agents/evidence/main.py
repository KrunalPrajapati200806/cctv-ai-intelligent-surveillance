"""
Evidence Agent for the CCTV AI surveillance platform.

Responsibilities
----------------
- Consume canonical alert.created events from Redis.
- Isolate each evidence job from other jobs.
- Generate proof-video evidence when a source video is available.
- Support live rolling-buffer evidence requests.
- Read rolling-buffer manifest metadata safely.
- Select rolling-buffer segments covering the requested window.
- Wait for finalized post-event buffer coverage.
- Stitch rolling-buffer segments into a temporary source video.
- Convert wall-clock event time into source-relative event time.
- Publish canonical evidence.generated / evidence.failed events.
- Recover stale Redis pending messages after process failure.
- ACK permanently impossible live-buffer requests.
- Keep the agent alive when an individual evidence job fails.
- Support graceful shutdown through BaseAgent.

This agent does NOT:
- detect objects
- track people
- generate alerts
- create incidents
- perform LLM reasoning
- own the incident database
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from agents.evidence.ffmpeg import require_ffmpeg
from agents.evidence.generator import create_proof_video
from shared.agent.base_agent import BaseAgent
from shared.schemas.event_schema import (
    BaseEvent,
    create_event,
    validate_event,
)


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "data"
EVIDENCE_ROOT = DATA_ROOT / "evidence"
PROOF_DIR = DATA_ROOT / "proof_videos"
STAGING_DIR = EVIDENCE_ROOT / "_staging"

EVIDENCE_ROOT.mkdir(
    parents=True,
    exist_ok=True,
)

PROOF_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

STAGING_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# REDIS CONFIGURATION
# ============================================================

DEFAULT_INPUT_STREAM = "events.evidence.requests"
DEFAULT_OUTPUT_STREAM = "events.evidence"
DEFAULT_GROUP_NAME = "evidence-workers"


# ============================================================
# ENVIRONMENT HELPERS
# ============================================================

def _env_int(
    name: str,
    default: int,
    *,
    minimum: Optional[int] = None,
) -> int:
    """Read an integer environment variable safely."""

    raw = os.getenv(name)

    if raw is None or not raw.strip():
        value = default
    else:
        try:
            value = int(raw)
        except ValueError:
            print(
                f"[EVIDENCE] Invalid integer "
                f"{name}={raw!r}; using {default}."
            )
            value = default

    if minimum is not None and value < minimum:
        print(
            f"[EVIDENCE] {name}={value} is below "
            f"minimum {minimum}; using {minimum}."
        )
        value = minimum

    return value


def _env_float(
    name: str,
    default: float,
    *,
    minimum: Optional[float] = None,
) -> float:
    """Read a floating-point environment variable safely."""

    raw = os.getenv(name)

    if raw is None or not raw.strip():
        value = default
    else:
        try:
            value = float(raw)
        except ValueError:
            print(
                f"[EVIDENCE] Invalid float "
                f"{name}={raw!r}; using {default}."
            )
            value = default

    if minimum is not None and value < minimum:
        print(
            f"[EVIDENCE] {name}={value} is below "
            f"minimum {minimum}; using {minimum}."
        )
        value = minimum

    return value


# ============================================================
# CONFIGURATION
# ============================================================

AGENT_ID = (
    os.getenv(
        "EVIDENCE_AGENT_ID",
        "evidence-01",
    ).strip()
    or "evidence-01"
)

INPUT_STREAM = (
    os.getenv(
        "EVIDENCE_INPUT_STREAM",
        DEFAULT_INPUT_STREAM,
    ).strip()
    or DEFAULT_INPUT_STREAM
)

OUTPUT_STREAM = (
    os.getenv(
        "EVIDENCE_OUTPUT_STREAM",
        DEFAULT_OUTPUT_STREAM,
    ).strip()
    or DEFAULT_OUTPUT_STREAM
)

GROUP_NAME = (
    os.getenv(
        "EVIDENCE_GROUP_NAME",
        DEFAULT_GROUP_NAME,
    ).strip()
    or DEFAULT_GROUP_NAME
)

CONSUMER_NAME = (
    os.getenv(
        "EVIDENCE_CONSUMER_NAME",
        "",
    ).strip()
)

BLOCK_MS = _env_int(
    "EVIDENCE_BLOCK_MS",
    5000,
    minimum=100,
)

BATCH_SIZE = _env_int(
    "EVIDENCE_BATCH_SIZE",
    10,
    minimum=1,
)

MAX_RETRIES = _env_int(
    "EVIDENCE_MAX_RETRIES",
    3,
    minimum=0,
)

RETRY_DELAY_SECONDS = _env_float(
    "EVIDENCE_RETRY_DELAY_SECONDS",
    2.0,
    minimum=0.0,
)

PENDING_CLAIM_IDLE_MS = _env_int(
    "EVIDENCE_PENDING_CLAIM_IDLE_MS",
    30000,
    minimum=1000,
)

PENDING_CLAIM_BATCH_SIZE = _env_int(
    "EVIDENCE_PENDING_CLAIM_BATCH_SIZE",
    10,
    minimum=1,
)

PENDING_RECOVERY_INTERVAL_SECONDS = _env_float(
    "EVIDENCE_PENDING_RECOVERY_INTERVAL_SECONDS",
    5.0,
    minimum=0.5,
)

LIVE_SOURCE_WAIT_SECONDS = _env_float(
    "EVIDENCE_LIVE_SOURCE_WAIT_SECONDS",
    30.0,
    minimum=0.0,
)

LIVE_SOURCE_POLL_SECONDS = _env_float(
    "EVIDENCE_LIVE_SOURCE_POLL_SECONDS",
    1.0,
    minimum=0.1,
)

DEFAULT_PRE_SECONDS = _env_float(
    "EVIDENCE_DEFAULT_PRE_SECONDS",
    10.0,
    minimum=0.0,
)

DEFAULT_POST_SECONDS = _env_float(
    "EVIDENCE_DEFAULT_POST_SECONDS",
    10.0,
    minimum=0.0,
)

FFMPEG_STITCH_TIMEOUT_SECONDS = _env_float(
    "EVIDENCE_FFMPEG_STITCH_TIMEOUT_SECONDS",
    120.0,
    minimum=5.0,
)

VIDEO_SEARCH_ROOT = Path(
    os.getenv(
        "EVIDENCE_VIDEO_ROOT",
        str(DATA_ROOT),
    )
).expanduser()

VIDEO_SEARCH_ROOT.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# EVENT HELPERS
# ============================================================

def _decode_value(value: Any) -> Any:
    """Decode Redis byte values."""

    if isinstance(value, bytes):
        return value.decode(
            "utf-8",
            errors="replace",
        )

    return value


def _extract_event_payload(
    fields: dict[str, Any],
) -> Optional[dict[str, Any]]:
    """
    Extract canonical event JSON from Redis fields.

    Preferred:
        {"event": "<JSON>"}

    Compatibility:
        single-field Redis message containing JSON.
    """

    if not fields:
        return None

    normalized = {
        str(_decode_value(key)): _decode_value(value)
        for key, value in fields.items()
    }

    raw_event = normalized.get("event")

    if raw_event is None:
        if len(normalized) == 1:
            raw_event = next(
                iter(normalized.values())
            )
        else:
            return None

    if isinstance(raw_event, dict):
        return raw_event

    if not isinstance(raw_event, str):
        return None

    try:
        payload = json.loads(raw_event)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None

    return payload


def _safe_string(
    value: Any,
    default: str = "",
) -> str:
    """Convert a value to a safe string."""

    if value is None:
        return default

    text = str(value).strip()

    return text if text else default


def _event_data(
    event: BaseEvent,
) -> dict[str, Any]:
    """Return event.data as a dictionary."""

    data = event.data

    if isinstance(data, dict):
        return dict(data)

    return {}


def _nested_evidence_request(
    event: BaseEvent,
) -> dict[str, Any]:
    """Return optional nested evidence_request."""

    data = _event_data(event)

    request = data.get("evidence_request")

    if isinstance(request, dict):
        return dict(request)

    return {}


def _is_live_evidence_request(
    event: BaseEvent,
) -> bool:
    """Determine whether the event uses the rolling buffer."""

    data = _event_data(event)
    request = _nested_evidence_request(event)

    source_type = _safe_string(
        request.get(
            "source_type",
            data.get("source_type", ""),
        )
    ).lower()

    if source_type in {
        "rolling_buffer",
        "live_buffer",
        "live",
        "buffer",
    }:
        return True

    if request.get("live") is True:
        return True

    if data.get("live_evidence") is True:
        return True

    return False


# ============================================================
# CAMERA / PATH HELPERS
# ============================================================

def _safe_camera_directory_name(
    camera_id: str,
) -> str:
    """Convert camera ID into filesystem-safe directory name."""

    safe_chars: list[str] = []

    for char in camera_id:
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

    return result[:120] or "unknown-camera"


def _camera_evidence_root(
    camera_id: str,
) -> Path:
    safe_camera_id = _safe_camera_directory_name(
        camera_id
    )

    return EVIDENCE_ROOT / safe_camera_id


def _camera_buffer_root(
    camera_id: str,
) -> Path:
    return (
        _camera_evidence_root(camera_id)
        / "buffer"
    )


def _camera_manifest_path(
    camera_id: str,
) -> Path:
    return (
        _camera_buffer_root(camera_id)
        / "manifest.json"
    )


def _allowed_video_roots() -> tuple[Path, ...]:
    """Return allowed filesystem roots."""

    roots = [
        VIDEO_SEARCH_ROOT,
        DATA_ROOT,
        EVIDENCE_ROOT,
        PROOF_DIR,
        STAGING_DIR,
    ]

    resolved: list[Path] = []
    seen: set[str] = set()

    for root in roots:
        try:
            resolved_root = root.resolve()
        except OSError:
            continue

        key = str(
            resolved_root
        ).lower()

        if key in seen:
            continue

        seen.add(key)
        resolved.append(
            resolved_root
        )

    return tuple(resolved)


def _is_path_allowed(
    path: Path,
) -> bool:
    """Return True if path is inside an allowed root."""

    try:
        resolved_path = path.resolve()
    except OSError:
        return False

    for root in _allowed_video_roots():
        try:
            resolved_path.relative_to(root)
            return True
        except ValueError:
            continue

    return False


# ============================================================
# TIME HELPERS
# ============================================================

def _parse_epoch(
    value: Any,
) -> Optional[float]:
    """
    Convert supported time representations into Unix epoch seconds.

    Supported:
    - int
    - float
    - numeric string
    - ISO-8601 string
    """

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        value_float = float(value)

        if value_float <= 0:
            return None

        return value_float

    if not isinstance(value, str):
        return None

    text = value.strip()

    if not text:
        return None

    try:
        numeric = float(text)

        if numeric <= 0:
            return None

        return numeric

    except ValueError:
        pass

    try:
        normalized = text

        if normalized.endswith("Z"):
            normalized = (
                normalized[:-1]
                + "+00:00"
            )

        parsed = datetime.fromisoformat(
            normalized
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        timestamp = parsed.timestamp()

        if timestamp <= 0:
            return None

        return timestamp

    except (
        ValueError,
        OverflowError,
    ):
        return None


def _event_time_epoch(
    event: BaseEvent,
) -> Optional[float]:
    """
    Resolve event time.

    Priority:
    1. evidence_request.event_time
    2. data.event_time
    3. data.frame_timestamp
    4. data.timestamp_seconds
    5. canonical event timestamp
    """

    data = _event_data(event)
    request = _nested_evidence_request(event)

    candidates = [
        request.get("event_time"),
        data.get("event_time"),
        data.get("frame_timestamp"),
        data.get("timestamp_seconds"),
        event.timestamp,
    ]

    for value in candidates:
        epoch = _parse_epoch(value)

        if epoch is not None:
            return epoch

    return None


def _request_window(
    event: BaseEvent,
) -> tuple[float, float]:
    """Return requested pre/post evidence window."""

    data = _event_data(event)
    request = _nested_evidence_request(event)

    pre_value = request.get(
        "pre_seconds",
        data.get(
            "pre_seconds",
            DEFAULT_PRE_SECONDS,
        ),
    )

    post_value = request.get(
        "post_seconds",
        data.get(
            "post_seconds",
            DEFAULT_POST_SECONDS,
        ),
    )

    try:
        pre_seconds = max(
            0.0,
            float(pre_value),
        )
    except (
        TypeError,
        ValueError,
    ):
        pre_seconds = DEFAULT_PRE_SECONDS

    try:
        post_seconds = max(
            0.0,
            float(post_value),
        )
    except (
        TypeError,
        ValueError,
    ):
        post_seconds = DEFAULT_POST_SECONDS

    return (
        pre_seconds,
        post_seconds,
    )


# ============================================================
# ROLLING BUFFER MANIFEST
# ============================================================

def _load_buffer_manifest_once(
    camera_id: str,
) -> list[dict[str, Any]]:
    """
    Read the rolling-buffer manifest once.

    Invalid/incomplete files are ignored.
    """

    manifest_path = _camera_manifest_path(
        camera_id
    )

    if not manifest_path.exists():
        return []

    try:
        with manifest_path.open(
            "r",
            encoding="utf-8",
        ) as handle:
            payload = json.load(handle)

    except (
        PermissionError,
        OSError,
        json.JSONDecodeError,
    ) as error:
        raise RuntimeError(
            f"manifest_read_failed: {error}"
        ) from error

    if isinstance(payload, dict):
        entries = payload.get(
            "segments",
            payload.get(
                "items",
                [],
            ),
        )

    elif isinstance(payload, list):
        entries = payload

    else:
        return []

    if not isinstance(entries, list):
        return []

    try:
        buffer_root = (
            _camera_buffer_root(
                camera_id
            ).resolve()
        )
    except OSError:
        return []

    valid: list[dict[str, Any]] = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        raw_path = entry.get("path")

        if not raw_path:
            raw_path = entry.get("filename")

        if not isinstance(raw_path, str):
            continue

        raw_path = raw_path.strip()

        if not raw_path:
            continue

        try:
            candidate = Path(
                raw_path
            ).expanduser()

            if not candidate.is_absolute():
                candidate = (
                    buffer_root
                    / candidate.name
                )

            candidate = candidate.resolve()

        except (
            OSError,
            ValueError,
        ):
            continue

        try:
            candidate.relative_to(
                buffer_root
            )
        except ValueError:
            continue

        try:
            if (
                not candidate.exists()
                or not candidate.is_file()
                or candidate.stat().st_size <= 0
            ):
                continue
        except OSError:
            continue

        normalized = dict(entry)

        normalized["path"] = str(
            candidate
        )

        normalized.setdefault(
            "filename",
            candidate.name,
        )

        start_epoch = _parse_epoch(
            normalized.get(
                "start_epoch"
            )
        )

        end_epoch = _parse_epoch(
            normalized.get(
                "end_epoch"
            )
        )

        if start_epoch is None:
            start_epoch = _parse_epoch(
                normalized.get(
                    "start_time"
                )
            )

        if end_epoch is None:
            end_epoch = _parse_epoch(
                normalized.get(
                    "end_time"
                )
            )

        if start_epoch is None:
            continue

        if end_epoch is None:
            end_epoch = start_epoch

        if end_epoch < start_epoch:
            continue

        normalized[
            "start_epoch"
        ] = start_epoch

        normalized[
            "end_epoch"
        ] = end_epoch

        valid.append(
            normalized
        )

    valid.sort(
        key=lambda item: (
            float(
                item.get(
                    "start_epoch",
                    0.0,
                )
            ),
            float(
                item.get(
                    "end_epoch",
                    0.0,
                )
            ),
        )
    )

    return valid


def _load_buffer_manifest(
    camera_id: str,
) -> list[dict[str, Any]]:
    """
    Read manifest with short retries.

    This protects against the buffer writer temporarily replacing,
    truncating, or locking manifest.json.
    """

    attempts = 3

    for attempt in range(
        1,
        attempts + 1,
    ):
        try:
            return _load_buffer_manifest_once(
                camera_id
            )

        except RuntimeError as error:
            if attempt >= attempts:
                print(
                    f"[EVIDENCE] Cannot read buffer "
                    f"manifest camera={camera_id}: "
                    f"{error}"
                )
                return []

            # Small blocking sleep is intentional here because
            # this function runs through asyncio.to_thread().
            import time

            time.sleep(
                0.05 * attempt
            )

    return []


def _segments_covering_window(
    segments: list[dict[str, Any]],
    start_epoch: float,
    end_epoch: float,
) -> list[dict[str, Any]]:
    """
    Select every finalized segment overlapping the requested window.
    """

    selected: list[
        dict[str, Any]
    ] = []

    for segment in segments:
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

        if (
            segment_end >= start_epoch
            and segment_start <= end_epoch
        ):
            selected.append(
                segment
            )

    selected.sort(
        key=lambda item: (
            float(
                item.get(
                    "start_epoch",
                    0.0,
                )
            ),
            float(
                item.get(
                    "end_epoch",
                    0.0,
                )
            ),
        )
    )

    return selected


def _segments_cover_entire_window(
    segments: list[dict[str, Any]],
    start_epoch: float,
    end_epoch: float,
) -> bool:
    """
    Determine whether selected finalized segments cover the
    complete requested window.
    """

    if not segments:
        return False

    ordered = sorted(
        segments,
        key=lambda item: float(
            item.get(
                "start_epoch",
                0.0,
            )
        ),
    )

    current = start_epoch

    # Segment boundaries can differ slightly from requested
    # timestamps because of encoder timing.
    tolerance = 0.75

    for segment in ordered:
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

        if segment_end < current:
            continue

        if segment_start > current + tolerance:
            return False

        current = max(
            current,
            segment_end,
        )

        if current >= (
            end_epoch - tolerance
        ):
            return True

    return current >= (
        end_epoch - tolerance
    )


def _buffer_bounds(
    segments: list[dict[str, Any]],
) -> tuple[
    Optional[float],
    Optional[float],
]:
    """Return oldest and newest finalized buffer timestamps."""

    if not segments:
        return None, None

    starts: list[float] = []
    ends: list[float] = []

    for segment in segments:
        try:
            starts.append(
                float(
                    segment[
                        "start_epoch"
                    ]
                )
            )

            ends.append(
                float(
                    segment[
                        "end_epoch"
                    ]
                )
            )
        except (
            KeyError,
            TypeError,
            ValueError,
        ):
            continue

    if not starts or not ends:
        return None, None

    return (
        min(starts),
        max(ends),
    )


# ============================================================
# FFMPEG
# ============================================================

def _ffmpeg_binary() -> str:
    """Resolve FFmpeg executable."""

    return str(
        require_ffmpeg()
    )


def _ffmpeg_concat_file_line(
    path: Path,
) -> str:
    """Create safe FFmpeg concat-demuxer file line."""

    resolved = str(
        path.resolve()
    )

    escaped = resolved.replace(
        "'",
        "'\\''",
    )

    return f"file '{escaped}'"


def _stitch_segments_sync(
    segments: list[dict[str, Any]],
    output_path: Path,
) -> Path:
    """
    Stitch rolling-buffer MP4 segments.

    First tries stream-copy.
    Falls back to H.264 re-encoding.
    """

    if not segments:
        raise ValueError(
            "Cannot stitch an empty segment list."
        )

    output_path = output_path.resolve()

    if not _is_path_allowed(
        output_path
    ):
        raise ValueError(
            f"Stitch output is outside "
            f"allowed roots: {output_path}"
        )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    validated_paths: list[
        Path
    ] = []

    for segment in segments:
        raw_path = segment.get(
            "path"
        )

        if not isinstance(
            raw_path,
            str,
        ):
            raise ValueError(
                "Rolling-buffer segment "
                "has no valid path."
            )

        path = Path(
            raw_path
        ).resolve()

        if not _is_path_allowed(
            path
        ):
            raise ValueError(
                f"Segment path is outside "
                f"allowed roots: {path}"
            )

        try:
            size = path.stat().st_size
        except OSError as error:
            raise ValueError(
                f"Cannot stat segment: "
                f"{path}: {error}"
            ) from error

        if (
            not path.exists()
            or not path.is_file()
            or size <= 0
        ):
            raise ValueError(
                f"Rolling-buffer segment "
                f"is invalid: {path}"
            )

        validated_paths.append(
            path
        )

    ffmpeg = _ffmpeg_binary()

    concat_file: Optional[
        Path
    ] = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".txt",
            prefix="evidence_concat_",
            dir=str(
                output_path.parent
            ),
            delete=False,
            encoding="utf-8",
        ) as handle:

            concat_file = Path(
                handle.name
            ).resolve()

            for path in validated_paths:
                handle.write(
                    _ffmpeg_concat_file_line(
                        path
                    )
                )
                handle.write("\n")

        # ----------------------------------------------------
        # Attempt 1: stream copy
        # ----------------------------------------------------

        copy_command = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(output_path),
        ]

        print(
            f"[EVIDENCE] Stitching "
            f"{len(validated_paths)} segment(s) "
            f"using stream copy."
        )

        copy_result = subprocess.run(
            copy_command,
            capture_output=True,
            text=True,
            timeout=FFMPEG_STITCH_TIMEOUT_SECONDS,
        )

        if (
            copy_result.returncode == 0
            and output_path.exists()
            and output_path.stat().st_size > 0
        ):
            print(
                "[EVIDENCE] Rolling-buffer "
                "stitch completed using "
                f"stream copy: {output_path}"
            )

            return output_path

        if output_path.exists():
            try:
                output_path.unlink()
            except OSError:
                pass

        copy_error = (
            copy_result.stderr.strip()
            or "FFmpeg stream-copy "
            "concatenation failed."
        )

        print(
            "[EVIDENCE] Stream-copy stitch "
            f"failed: {copy_error}"
        )

        # ----------------------------------------------------
        # Attempt 2: H.264 re-encode
        # ----------------------------------------------------

        encode_command = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output_path),
        ]

        print(
            "[EVIDENCE] Retrying rolling-buffer "
            "stitch using H.264 re-encoding."
        )

        encode_result = subprocess.run(
            encode_command,
            capture_output=True,
            text=True,
            timeout=FFMPEG_STITCH_TIMEOUT_SECONDS,
        )

        if (
            encode_result.returncode != 0
            or not output_path.exists()
            or output_path.stat().st_size <= 0
        ):
            encode_error = (
                encode_result.stderr.strip()
                or "FFmpeg H.264 "
                "concatenation failed."
            )

            raise RuntimeError(
                "Rolling-buffer stitching failed. "
                f"stream_copy_error={copy_error}; "
                f"reencode_error={encode_error}"
            )

        print(
            "[EVIDENCE] Rolling-buffer stitch "
            "completed using H.264 re-encoding: "
            f"{output_path}"
        )

        return output_path

    finally:
        if concat_file is not None:
            try:
                concat_file.unlink(
                    missing_ok=True
                )
            except OSError:
                pass


# ============================================================
# LIVE SOURCE RESULT
# ============================================================

class LiveSourceResult:
    """
    Result of resolving a live rolling-buffer source.

    source_path:
        Stitched temporary video.

    source_start_epoch:
        Exact wall-clock timestamp corresponding to the beginning
        of the stitched source.

    reason:
        Populated when the source cannot be produced.
    """

    def __init__(
        self,
        source_path: Optional[Path],
        source_start_epoch: Optional[float],
        reason: Optional[str] = None,
        metadata: Optional[
            dict[str, Any]
        ] = None,
    ) -> None:
        self.source_path = source_path
        self.source_start_epoch = (
            source_start_epoch
        )
        self.reason = reason
        self.metadata = (
            metadata
            if metadata is not None
            else {}
        )


# ============================================================
# LIVE BUFFER SOURCE
# ============================================================

async def _wait_for_rolling_buffer_source(
    event: BaseEvent,
) -> LiveSourceResult:
    """
    Wait for finalized rolling-buffer coverage.

    Important behavior:

    - A genuinely recent event may require waiting for post-event
      segments to become finalized.
    - An event older than the currently retained buffer is not
      retried forever.
    """

    request = _nested_evidence_request(
        event
    )

    camera_id = _safe_string(
        request.get(
            "camera_id",
            event.camera.camera_id,
        )
    )

    if not camera_id:
        return LiveSourceResult(
            source_path=None,
            source_start_epoch=None,
            reason="missing_camera_id",
        )

    event_epoch = _event_time_epoch(
        event
    )

    if event_epoch is None:
        return LiveSourceResult(
            source_path=None,
            source_start_epoch=None,
            reason="missing_event_time",
        )

    pre_seconds, post_seconds = (
        _request_window(event)
    )

    target_start = (
        event_epoch - pre_seconds
    )

    target_end = (
        event_epoch + post_seconds
    )

    print(
        "[EVIDENCE] Rolling-buffer window "
        f"camera={camera_id} "
        f"event={event.event_id} "
        f"start={target_start:.3f} "
        f"event_time={event_epoch:.3f} "
        f"end={target_end:.3f}"
    )

    deadline = (
        asyncio.get_running_loop().time()
        + LIVE_SOURCE_WAIT_SECONDS
    )

    last_signature: Optional[
        tuple[
            tuple[str, float, float],
            ...,
        ]
    ] = None

    while True:
        segments = await asyncio.to_thread(
            _load_buffer_manifest,
            camera_id,
        )

        oldest_start, newest_end = (
            _buffer_bounds(
                segments
            )
        )

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # If the requested event is older than the oldest
        # retained finalized segment, it is impossible to
        # satisfy using the rolling buffer.
        #
        # Do NOT leave this Redis message pending forever.
        # ----------------------------------------------------

        if (
            oldest_start is not None
            and target_start < (
                oldest_start - 0.75
            )
        ):
            print(
                "[EVIDENCE] Rolling-buffer "
                "window expired "
                f"camera={camera_id} "
                f"event={event.event_id} "
                f"requested_start={target_start:.3f} "
                f"oldest_available={oldest_start:.3f}"
            )

            return LiveSourceResult(
                source_path=None,
                source_start_epoch=None,
                reason="buffer_window_expired",
                metadata={
                    "requested_start": target_start,
                    "requested_end": target_end,
                    "event_epoch": event_epoch,
                    "oldest_available": oldest_start,
                    "newest_available": newest_end,
                },
            )

        selected = (
            _segments_covering_window(
                segments,
                target_start,
                target_end,
            )
        )

        signature = tuple(
            (
                str(
                    item.get(
                        "path",
                        "",
                    )
                ),
                float(
                    item.get(
                        "start_epoch",
                        0.0,
                    )
                ),
                float(
                    item.get(
                        "end_epoch",
                        0.0,
                    )
                ),
            )
            for item in selected
        )

        if signature != last_signature:
            print(
                "[EVIDENCE] Buffer coverage "
                f"camera={camera_id} "
                f"available_segments={len(segments)} "
                f"selected_segments={len(selected)}"
            )

            if (
                oldest_start is not None
                or newest_end is not None
            ):
                print(
                    "[EVIDENCE] Available buffer "
                    f"window "
                    f"oldest={oldest_start} "
                    f"newest={newest_end}"
                )

            last_signature = signature

        if selected:
            coverage_complete = (
                _segments_cover_entire_window(
                    selected,
                    target_start,
                    target_end,
                )
            )

            selected_start = min(
                float(
                    item[
                        "start_epoch"
                    ]
                )
                for item in selected
            )

            selected_end = max(
                float(
                    item[
                        "end_epoch"
                    ]
                )
                for item in selected
            )

            print(
                "[EVIDENCE] Selected buffer "
                f"segments={len(selected)} "
                f"start={selected_start:.3f} "
                f"end={selected_end:.3f} "
                f"complete={coverage_complete}"
            )

            if coverage_complete:
                safe_event_id = (
                    _safe_filename_component(
                        event.event_id
                    )
                )

                output_path = (
                    STAGING_DIR
                    / (
                        f"{safe_event_id}_"
                        "rolling_source.mp4"
                    )
                )

                try:
                    output_path.unlink(
                        missing_ok=True
                    )
                except OSError:
                    pass

                try:
                    stitched = (
                        await asyncio.to_thread(
                            _stitch_segments_sync,
                            selected,
                            output_path,
                        )
                    )

                except asyncio.CancelledError:
                    raise

                except Exception as error:
                    print(
                        "[EVIDENCE] Rolling-buffer "
                        "stitch failed "
                        f"event={event.event_id}: "
                        f"{error}"
                    )

                    # Do not immediately fail.
                    # The buffer may have changed or a segment may
                    # have been finalized incorrectly.
                    if (
                        asyncio.get_running_loop().time()
                        >= deadline
                    ):
                        return LiveSourceResult(
                            source_path=None,
                            source_start_epoch=None,
                            reason=(
                                "rolling_buffer_stitch_failed"
                            ),
                            metadata={
                                "error": str(
                                    error
                                ),
                            },
                        )

                    await asyncio.sleep(
                        LIVE_SOURCE_POLL_SECONDS
                    )

                    continue

                try:
                    if (
                        stitched.exists()
                        and stitched.is_file()
                        and stitched.stat().st_size > 0
                        and _is_path_allowed(
                            stitched
                        )
                    ):
                        # CRITICAL:
                        #
                        # Capture the source start NOW.
                        #
                        # Do not query the rolling manifest again after
                        # stitching because the rolling buffer can rotate.
                        #
                        # The source actually stitched starts at the
                        # beginning of the first selected segment.
                        source_start_epoch = (
                            selected_start
                        )

                        print(
                            "[EVIDENCE] Created "
                            "stitched rolling "
                            "source "
                            f"camera={camera_id} "
                            f"source={stitched} "
                            f"source_start="
                            f"{source_start_epoch:.3f}"
                        )

                        return LiveSourceResult(
                            source_path=stitched,
                            source_start_epoch=(
                                source_start_epoch
                            ),
                            metadata={
                                "camera_id": camera_id,
                                "selected_segments": len(
                                    selected
                                ),
                                "buffer_start": (
                                    selected_start
                                ),
                                "buffer_end": (
                                    selected_end
                                ),
                            },
                        )

                except OSError:
                    pass

        # ----------------------------------------------------
        # Timeout
        # ----------------------------------------------------

        if (
            asyncio.get_running_loop().time()
            >= deadline
        ):
            break

        await asyncio.sleep(
            LIVE_SOURCE_POLL_SECONDS
        )

    print(
        "[EVIDENCE] Rolling-buffer source "
        "not ready before timeout "
        f"camera={camera_id} "
        f"event={event.event_id}"
    )

    return LiveSourceResult(
        source_path=None,
        source_start_epoch=None,
        reason="rolling_buffer_not_ready",
        metadata={
            "requested_start": target_start,
            "requested_end": target_end,
            "event_epoch": event_epoch,
        },
    )


# ============================================================
# VIDEO RESOLUTION
# ============================================================

def _candidate_video_paths(
    event: BaseEvent,
) -> list[Path]:
    """Build possible historical source-video paths."""

    data = _event_data(event)
    request = _nested_evidence_request(event)

    candidates: list[str] = []

    request_path_keys = (
        "source_path",
        "source_video",
        "source_video_path",
        "video_path",
        "recording_path",
        "file_path",
        "video_file",
    )

    for key in request_path_keys:
        value = request.get(key)

        if isinstance(
            value,
            str,
        ) and value.strip():
            candidates.append(
                value.strip()
            )

    direct_path_keys = (
        "video_path",
        "source_video",
        "source_video_path",
        "recording_path",
        "file_path",
        "video_file",
        "source_path",
    )

    for key in direct_path_keys:
        value = data.get(key)

        if isinstance(
            value,
            str,
        ) and value.strip():
            candidates.append(
                value.strip()
            )

    identifier_keys = (
        "video_id",
        "recording_id",
        "file_name",
    )

    for key in identifier_keys:
        value = data.get(key)

        if isinstance(
            value,
            str,
        ) and value.strip():
            candidates.append(
                value.strip()
            )

    camera_id = _safe_string(
        request.get(
            "camera_id",
            event.camera.camera_id,
        )
    )

    if camera_id:
        safe_camera_id = (
            _safe_camera_directory_name(
                camera_id
            )
        )

        candidates.extend(
            [
                str(
                    EVIDENCE_ROOT
                    / safe_camera_id
                ),
                str(
                    DATA_ROOT
                    / "recorded_videos"
                    / safe_camera_id
                ),
                str(
                    DATA_ROOT
                    / "recorded_videos"
                    / camera_id
                ),
            ]
        )

    resolved: list[Path] = []

    video_extensions = (
        ".mp4",
        ".avi",
        ".mov",
        ".mkv",
        ".webm",
    )

    for candidate in candidates:
        try:
            original_path = Path(
                candidate
            ).expanduser()
        except (
            TypeError,
            ValueError,
        ):
            continue

        is_absolute = (
            original_path.is_absolute()
        )

        if is_absolute:
            path = original_path
        else:
            path = (
                VIDEO_SEARCH_ROOT
                / original_path
            )

        try:
            path = path.resolve()
        except OSError:
            continue

        if _is_path_allowed(path):
            try:
                if (
                    path.exists()
                    and path.is_file()
                    and path.stat().st_size > 0
                ):
                    resolved.append(
                        path
                    )
                    continue
            except OSError:
                pass

        if (
            path.exists()
            and path.is_dir()
            and _is_path_allowed(path)
        ):
            try:
                for extension in video_extensions:
                    for match in path.glob(
                        f"*{extension}"
                    ):
                        try:
                            resolved_match = (
                                match.resolve()
                            )
                        except OSError:
                            continue

                        if not _is_path_allowed(
                            resolved_match
                        ):
                            continue

                        try:
                            if (
                                resolved_match.exists()
                                and resolved_match.is_file()
                                and resolved_match.stat().st_size > 0
                            ):
                                resolved.append(
                                    resolved_match
                                )
                        except OSError:
                            continue

            except OSError:
                pass

        if (
            not is_absolute
            and VIDEO_SEARCH_ROOT.exists()
        ):
            search_names: list[str] = []

            name = original_path.name

            if name:
                search_names.append(
                    name
                )

                if not original_path.suffix:
                    search_names.extend(
                        f"{name}{extension}"
                        for extension in video_extensions
                    )

            for search_name in search_names:
                try:
                    matches = list(
                        VIDEO_SEARCH_ROOT.rglob(
                            search_name
                        )
                    )
                except OSError:
                    matches = []

                for match in matches:
                    try:
                        resolved_match = (
                            match.resolve()
                        )
                    except OSError:
                        continue

                    if not _is_path_allowed(
                        resolved_match
                    ):
                        continue

                    try:
                        if (
                            resolved_match.exists()
                            and resolved_match.is_file()
                            and resolved_match.stat().st_size > 0
                        ):
                            resolved.append(
                                resolved_match
                            )
                    except OSError:
                        continue

    recording_root = (
        DATA_ROOT
        / "recorded_videos"
    )

    for key in (
        "video_id",
        "recording_id",
    ):
        value = data.get(key)

        if not isinstance(
            value,
            str,
        ):
            continue

        identifier = value.strip()

        if not identifier:
            continue

        for extension in video_extensions:
            candidate_path = (
                recording_root
                / f"{identifier}{extension}"
            )

            try:
                candidate_path = (
                    candidate_path.resolve()
                )
            except OSError:
                continue

            if not _is_path_allowed(
                candidate_path
            ):
                continue

            try:
                if (
                    candidate_path.exists()
                    and candidate_path.is_file()
                    and candidate_path.stat().st_size > 0
                ):
                    resolved.append(
                        candidate_path
                    )
            except OSError:
                continue

    unique: list[Path] = []
    seen: set[str] = set()

    for path in resolved:
        key = str(path).lower()

        if key in seen:
            continue

        seen.add(key)
        unique.append(path)

    return unique


def resolve_source_video(
    event: BaseEvent,
) -> Optional[Path]:
    """Resolve a usable historical source video."""

    candidates = _candidate_video_paths(
        event
    )

    for path in candidates:
        try:
            if (
                path.exists()
                and path.is_file()
                and path.stat().st_size > 0
            ):
                return path
        except OSError:
            continue

    return None


# ============================================================
# PROOF PATH
# ============================================================

def _safe_filename_component(
    value: str,
) -> str:
    """Convert identifier into safe filename component."""

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

    return result or "unknown"


def _build_proof_path(
    event: BaseEvent,
) -> Path:
    """Build deterministic proof-video path."""

    data = _event_data(event)

    video_id = _safe_string(
        data.get("video_id")
    )

    incident_id = _safe_string(
        event.context.incident_id
    )

    event_id = _safe_string(
        event.event_id,
        "unknown-event",
    )

    if video_id:
        safe_video_id = (
            _safe_filename_component(
                video_id
            )
        )

        if incident_id:
            safe_incident_id = (
                _safe_filename_component(
                    incident_id
                )
            )

            return (
                PROOF_DIR
                / (
                    f"{safe_video_id}_"
                    f"{safe_incident_id}_proof.mp4"
                )
            )

        safe_event_id = (
            _safe_filename_component(
                event_id
            )
        )

        return (
            PROOF_DIR
            / (
                f"{safe_video_id}_"
                f"{safe_event_id}_proof.mp4"
            )
        )

    safe_event_id = (
        _safe_filename_component(
            event_id
        )
    )

    return (
        PROOF_DIR
        / f"{safe_event_id}_proof.mp4"
    )


# ============================================================
# EVIDENCE EVENT
# ============================================================

def _build_evidence_event(
    self: "EvidenceAgent",
    event: BaseEvent,
    *,
    evidence_type: str,
    status: str,
    proof_path: Optional[Path] = None,
    metadata: Optional[
        dict[str, Any]
    ] = None,
) -> BaseEvent:
    """Create canonical evidence.generated/evidence.failed."""

    data = _event_data(event)
    request = _nested_evidence_request(
        event
    )

    result_data: dict[str, Any] = {
        "status": status,
        "evidence_type": evidence_type,
        "source_event_id": event.event_id,
        "source_event_type": event.event_type,
        "source_agent_id": event.source.agent_id,
        "source_instance_id": event.source.instance_id,
        "source_hostname": event.source.hostname,
    }

    for key in (
        "video_id",
        "recording_id",
        "file_name",
        "frame_id",
        "frame_timestamp",
        "timestamp_seconds",
        "event_time",
        "track_ids",
        "alert_type",
        "severity",
        "source_type",
    ):
        if key in data:
            result_data[key] = data[key]

    for key in (
        "camera_id",
        "event_time",
        "pre_seconds",
        "post_seconds",
        "source_type",
        "source_path",
        "buffer_id",
    ):
        if key in request:
            result_data[key] = request[key]

    if proof_path is not None:
        result_data[
            "proof_path"
        ] = str(
            proof_path
        )

        result_data[
            "proof_filename"
        ] = proof_path.name

    if metadata:
        result_data.update(
            metadata
        )

    result_event = create_event(
        event_type=(
            "evidence.generated"
            if status == "completed"
            else "evidence.failed"
        ),
        agent_id=self.agent_id,
        instance_id=self.instance_id,
        hostname=self.hostname,
        camera_id=event.camera.camera_id,
        mode=event.context.mode,
        data=result_data,
        trace_id=event.context.trace_id,
        correlation_id=event.context.correlation_id,
        incident_id=event.context.incident_id,
    )

    validate_event(
        result_event
    )

    return result_event


# ============================================================
# EVIDENCE AGENT
# ============================================================

class EvidenceAgent(BaseAgent):
    """Independently supervised Evidence Agent."""

    def __init__(
        self,
        agent_id: str = AGENT_ID,
        *,
        redis_host: Optional[str] = None,
        redis_port: Optional[int] = None,
        heartbeat_interval: Optional[int] = None,
    ) -> None:
        super().__init__(
            agent_id,
            redis_host=redis_host,
            redis_port=redis_port,
            heartbeat_interval=heartbeat_interval,
        )

        self.input_stream = INPUT_STREAM
        self.output_stream = OUTPUT_STREAM
        self.group_name = GROUP_NAME

        self.consumer_name = (
            CONSUMER_NAME
            or (
                f"{self.agent_id}:"
                f"{self.hostname}:"
                f"{self.instance_id}"
            )
        )

        self._shutdown_event = (
            asyncio.Event()
        )

        self._consumer_group_ready = False

        self._last_pending_recovery = 0.0

    # ========================================================
    # START
    # ========================================================

    async def on_start(self) -> None:
        """Prepare Redis consumer group."""

        if self.redis_client is None:
            raise RuntimeError(
                "Redis client unavailable during "
                "Evidence Agent startup."
            )

        try:
            await self.redis_client.xgroup_create(
                name=self.input_stream,
                groupname=self.group_name,
                id="0",
                mkstream=True,
            )

            print(
                f"[EVIDENCE] Created consumer group "
                f"{self.group_name} on "
                f"{self.input_stream}"
            )

        except Exception as error:
            if "BUSYGROUP" not in str(
                error
            ).upper():
                raise

            print(
                f"[EVIDENCE] Consumer group already exists: "
                f"{self.group_name}"
            )

        self._consumer_group_ready = True
        self._shutdown_event.clear()

        print(
            f"[EVIDENCE] Consumer ready "
            f"stream={self.input_stream} "
            f"group={self.group_name} "
            f"consumer={self.consumer_name}"
        )

        print(
            f"[EVIDENCE] Agent identity "
            f"agent_id={self.agent_id} "
            f"instance_id={self.instance_id} "
            f"hostname={self.hostname}"
        )

    # ========================================================
    # STOP
    # ========================================================

    async def on_stop(self) -> None:
        """Signal consumer loop to stop."""

        self._shutdown_event.set()
        self._consumer_group_ready = False

        print(
            f"[EVIDENCE] Shutdown requested "
            f"for {self.agent_id}"
        )

    # ========================================================
    # ACK
    # ========================================================

    async def _ack(
        self,
        message_id: str,
    ) -> bool:
        """Acknowledge one Redis message."""

        if self.redis_client is None:
            print(
                f"[EVIDENCE] Cannot ACK "
                f"{message_id}: Redis unavailable."
            )
            return False

        try:
            acknowledged = (
                await self.redis_client.xack(
                    self.input_stream,
                    self.group_name,
                    message_id,
                )
            )

            if acknowledged:
                return True

            print(
                f"[EVIDENCE] ACK returned 0 "
                f"for message={message_id}"
            )

            return False

        except Exception as error:
            print(
                f"[EVIDENCE] ACK failed "
                f"message={message_id}: {error}"
            )

            return False

    # ========================================================
    # PUBLISH
    # ========================================================

    async def _publish_result(
        self,
        result_event: BaseEvent,
    ) -> None:
        """Publish canonical evidence result."""

        validate_event(
            result_event
        )

        await self.publish(
            self.output_stream,
            result_event,
        )

    # ========================================================
    # PROOF GENERATION
    # ========================================================

    async def _generate_proof_with_retries(
        self,
        event: BaseEvent,
        source_video: Path,
        proof_path: Path,
        *,
        generator_event: Optional[
            dict[str, Any]
        ] = None,
    ) -> dict[str, Any]:
        """Generate proof video with bounded retries."""

        attempts = max(
            1,
            MAX_RETRIES + 1,
        )

        last_error: Optional[
            Exception
        ] = None

        generator_payload = (
            generator_event
            if generator_event is not None
            else _event_to_generator_dict(
                event
            )
        )

        for attempt in range(
            1,
            attempts + 1,
        ):
            try:
                print(
                    f"[EVIDENCE] Proof attempt "
                    f"{attempt}/{attempts} "
                    f"event={event.event_id}"
                )

                result = (
                    await asyncio.to_thread(
                        create_proof_video,
                        source_video,
                        proof_path,
                        generator_payload,
                    )
                )

                if not isinstance(
                    result,
                    dict,
                ):
                    result = {}

                return result

            except asyncio.CancelledError:
                raise

            except Exception as error:
                last_error = error

                print(
                    f"[EVIDENCE] Proof attempt "
                    f"failed event={event.event_id} "
                    f"attempt={attempt}/{attempts}: "
                    f"{error}"
                )

                if attempt >= attempts:
                    break

                if RETRY_DELAY_SECONDS > 0:
                    await asyncio.sleep(
                        RETRY_DELAY_SECONDS
                    )

        if last_error is None:
            raise RuntimeError(
                "Proof generation failed "
                "without an exception."
            )

        raise last_error

    # ========================================================
    # LIVE SOURCE
    # ========================================================

    async def _wait_for_live_source(
        self,
        event: BaseEvent,
    ) -> LiveSourceResult:
        """
        Resolve live rolling-buffer source.

        First preference:
            explicit source_path

        Otherwise:
            rolling-buffer manifest + stitching.
        """

        request = _nested_evidence_request(
            event
        )

        explicit_source = _safe_string(
            request.get(
                "source_path"
            )
        )

        if explicit_source:
            try:
                path = (
                    Path(
                        explicit_source
                    )
                    .expanduser()
                    .resolve()
                )
            except (
                OSError,
                ValueError,
            ):
                path = None

            if (
                path is not None
                and _is_path_allowed(path)
                and path.exists()
                and path.is_file()
            ):
                try:
                    if path.stat().st_size > 0:
                        print(
                            f"[EVIDENCE] Using explicit "
                            f"live source={path}"
                        )

                        # An explicit source does not necessarily
                        # correspond to the rolling buffer, so its
                        # source-relative timing is not changed here.
                        return LiveSourceResult(
                            source_path=path,
                            source_start_epoch=None,
                            reason=None,
                            metadata={
                                "explicit_source": True
                            },
                        )

                except OSError:
                    pass

        return (
            await _wait_for_rolling_buffer_source(
                event
            )
        )

    # ========================================================
    # PROCESS EVENT
    # ========================================================

    async def process_event(
        self,
        event: BaseEvent,
        message_id: str,
    ) -> bool:
        """
        Process exactly one evidence request.

        Returns:
            True  -> message can be ACKed.
            False -> message remains recoverable.
        """

        live_request = (
            _is_live_evidence_request(
                event
            )
        )

        source_video: Optional[
            Path
        ] = None

        temporary_live_source = False

        generator_event: Optional[
            dict[str, Any]
        ] = None

        # ----------------------------------------------------
        # LIVE ROLLING BUFFER
        # ----------------------------------------------------

        if live_request:
            print(
                f"[EVIDENCE] Live evidence request "
                f"event={event.event_id}; "
                "checking rolling-buffer coverage."
            )

            live_result = (
                await self._wait_for_live_source(
                    event
                )
            )

            source_video = (
                live_result.source_path
            )

            if source_video is None:
                reason = (
                    live_result.reason
                    or "live_source_unavailable"
                )

                print(
                    f"[EVIDENCE] Live source "
                    f"unavailable "
                    f"event={event.event_id} "
                    f"reason={reason}"
                )

                # ------------------------------------------------
                # PERMANENT FAILURE
                #
                # A rolling buffer expiration can never be fixed
                # by retrying the same Redis message.
                # ------------------------------------------------

                if reason == (
                    "buffer_window_expired"
                ):
                    failure_event = (
                        _build_evidence_event(
                            self,
                            event,
                            evidence_type=(
                                "proof_video"
                            ),
                            status="failed",
                            metadata={
                                "reason": reason,
                                "message_id": (
                                    message_id
                                ),
                                **live_result.metadata,
                            },
                        )
                    )

                    try:
                        await self._publish_result(
                            failure_event
                        )
                    except Exception as error:
                        print(
                            "[EVIDENCE] Failed to "
                            "publish permanent "
                            "buffer-expired failure "
                            f"event={event.event_id}: "
                            f"{error}"
                        )

                        # Keep pending if the failure event itself
                        # could not be published.
                        return False

                    print(
                        "[EVIDENCE] Permanently "
                        "unavailable live request "
                        f"ACKing message={message_id}"
                    )

                    return True

                # ------------------------------------------------
                # TRANSIENT FAILURE
                #
                # Leave pending so another attempt can recover it.
                # ------------------------------------------------

                return False

            temporary_live_source = (
                "_staging"
                in source_video.parts
            )

            # ------------------------------------------------
            # CRITICAL:
            #
            # The source start is returned together with the
            # exact stitched source. Never query the moving
            # rolling manifest again here.
            # ------------------------------------------------

            source_start_epoch = (
                live_result.source_start_epoch
            )

            event_epoch = (
                _event_time_epoch(event)
            )

            if (
                source_start_epoch is None
                or event_epoch is None
            ):
                print(
                    f"[EVIDENCE] Cannot calculate "
                    f"source-relative event time "
                    f"event={event.event_id}"
                )

                return False

            relative_event_time = (
                event_epoch
                - source_start_epoch
            )

            if relative_event_time < 0:
                relative_event_time = 0.0

            generator_event = (
                _event_to_generator_dict(
                    event
                )
            )

            generator_event[
                "event_time"
            ] = relative_event_time

            generator_event[
                "time"
            ] = relative_event_time

            generator_event[
                "event_epoch"
            ] = event_epoch

            generator_event[
                "source_start_epoch"
            ] = source_start_epoch

            print(
                f"[EVIDENCE] Live source timing "
                f"event={event.event_id} "
                f"source_start="
                f"{source_start_epoch:.3f} "
                f"event_epoch="
                f"{event_epoch:.3f} "
                f"relative_event_time="
                f"{relative_event_time:.3f}s"
            )

        # ----------------------------------------------------
        # HISTORICAL SOURCE
        # ----------------------------------------------------

        else:
            try:
                source_video = (
                    await asyncio.to_thread(
                        resolve_source_video,
                        event,
                    )
                )

            except asyncio.CancelledError:
                raise

            except Exception as error:
                print(
                    "[EVIDENCE] Source-video "
                    "resolution failed "
                    f"event={event.event_id}: "
                    f"{error}"
                )

                source_video = None

            if source_video is None:
                print(
                    f"[EVIDENCE] No source video "
                    f"for event={event.event_id}; "
                    "leaving message recoverable."
                )

                return False

        # ----------------------------------------------------
        # FINAL SOURCE VALIDATION
        # ----------------------------------------------------

        if source_video is None:
            return False

        try:
            if (
                not source_video.exists()
                or not source_video.is_file()
                or source_video.stat().st_size <= 0
                or not _is_path_allowed(
                    source_video
                )
            ):
                print(
                    "[EVIDENCE] Source became "
                    "invalid "
                    f"event={event.event_id} "
                    f"source={source_video}"
                )

                return False

        except OSError:
            return False

        # ----------------------------------------------------
        # PROOF PATH
        # ----------------------------------------------------

        proof_path = _build_proof_path(
            event
        )

        print(
            f"[EVIDENCE] Generating proof "
            f"event={event.event_id} "
            f"source={source_video} "
            f"output={proof_path}"
        )

        try:
            result = (
                await self._generate_proof_with_retries(
                    event,
                    source_video,
                    proof_path,
                    generator_event=generator_event,
                )
            )

            evidence_event = (
                _build_evidence_event(
                    self,
                    event,
                    evidence_type="proof_video",
                    status="completed",
                    proof_path=proof_path,
                    metadata={
                        "message_id": message_id,
                        "source_video": str(
                            source_video
                        ),
                        "source_type": (
                            "rolling_buffer"
                            if live_request
                            else "recorded_video"
                        ),
                        "start_time": result.get(
                            "start_time"
                        ),
                        "end_time": result.get(
                            "end_time"
                        ),
                        "duration": result.get(
                            "duration"
                        ),
                        "fps": result.get(
                            "fps"
                        ),
                        "frames_written": result.get(
                            "frames_written"
                        ),
                    },
                )
            )

            await self._publish_result(
                evidence_event
            )

            print(
                f"[EVIDENCE] Completed "
                f"event={event.event_id} "
                f"proof={proof_path}"
            )

            return True

        except asyncio.CancelledError:
            raise

        except Exception as error:
            print(
                f"[EVIDENCE] Job failed "
                f"event={event.event_id}: "
                f"{error}"
            )

            failure_event = (
                _build_evidence_event(
                    self,
                    event,
                    evidence_type="proof_video",
                    status="failed",
                    metadata={
                        "reason": (
                            "proof_generation_failed"
                        ),
                        "error": str(error),
                        "message_id": message_id,
                        "source_video": str(
                            source_video
                        ),
                        "source_type": (
                            "rolling_buffer"
                            if live_request
                            else "recorded_video"
                        ),
                    },
                )
            )

            try:
                await self._publish_result(
                    failure_event
                )

            except Exception as publish_error:
                print(
                    "[EVIDENCE] Failed to publish "
                    "evidence.failed "
                    f"for event={event.event_id}: "
                    f"{publish_error}"
                )

                return False

            return True

        finally:
            if (
                temporary_live_source
                and source_video is not None
            ):
                try:
                    source_video.unlink(
                        missing_ok=True
                    )

                    print(
                        "[EVIDENCE] Removed temporary "
                        f"rolling source "
                        f"{source_video}"
                    )

                except OSError as cleanup_error:
                    print(
                        "[EVIDENCE] Temporary source "
                        "cleanup failed "
                        f"source={source_video}: "
                        f"{cleanup_error}"
                    )

    # ========================================================
    # REDIS MESSAGE
    # ========================================================

    async def _process_message(
        self,
        message_id: str,
        fields: dict[str, Any],
    ) -> None:
        """Isolate and process one Redis message."""

        payload = _extract_event_payload(
            fields
        )

        if payload is None:
            print(
                "[EVIDENCE] Malformed Redis "
                f"message {message_id}; "
                "ACKing poison message."
            )

            await self._ack(
                message_id
            )

            return

        try:
            event = BaseEvent.model_validate(
                payload
            )

            validate_event(
                event
            )

        except Exception as error:
            print(
                "[EVIDENCE] Invalid event "
                f"message={message_id}: "
                f"{error}; ACKing poison message."
            )

            await self._ack(
                message_id
            )

            return

        if event.event_type != (
            "alert.created"
        ):
            print(
                "[EVIDENCE] Ignoring unsupported "
                f"event_type={event.event_type} "
                f"message={message_id}"
            )

            await self._ack(
                message_id
            )

            return

        try:
            processed = (
                await self.process_event(
                    event,
                    message_id,
                )
            )

        except asyncio.CancelledError:
            raise

        except Exception as error:
            print(
                "[EVIDENCE] Unexpected "
                "per-message failure "
                f"message={message_id}: "
                f"{error}"
            )

            processed = False

        if not processed:
            return

        acknowledged = await self._ack(
            message_id
        )

        if not acknowledged:
            print(
                "[EVIDENCE] Message remains "
                "recoverable because ACK failed "
                f"message={message_id}"
            )

    # ========================================================
    # NEW MESSAGE CONSUMPTION
    # ========================================================

    async def _consume_once(
        self,
    ) -> int:
        """Consume one batch of new Redis messages."""

        if self.redis_client is None:
            raise RuntimeError(
                "Redis client unavailable."
            )

        response = (
            await self.redis_client.xreadgroup(
                groupname=self.group_name,
                consumername=self.consumer_name,
                streams={
                    self.input_stream: ">"
                },
                count=BATCH_SIZE,
                block=BLOCK_MS,
            )
        )

        processed_count = 0

        for _stream_name, messages in response:
            for message_id, fields in messages:
                processed_count += 1

                try:
                    await self._process_message(
                        str(message_id),
                        fields,
                    )

                except asyncio.CancelledError:
                    raise

                except Exception as error:
                    print(
                        "[EVIDENCE] Message "
                        "isolation boundary caught "
                        f"error message={message_id}: "
                        f"{error}"
                    )

        return processed_count

    # ========================================================
    # OWN PENDING
    # ========================================================

    async def _recover_own_pending_once(
        self,
    ) -> int:
        """Recover pending messages owned by this consumer."""

        if self.redis_client is None:
            raise RuntimeError(
                "Redis client unavailable."
            )

        response = (
            await self.redis_client.xreadgroup(
                groupname=self.group_name,
                consumername=self.consumer_name,
                streams={
                    self.input_stream: "0-0"
                },
                count=PENDING_CLAIM_BATCH_SIZE,
                block=1,
            )
        )

        recovered_count = 0

        for _stream_name, messages in response:
            for message_id, fields in messages:
                recovered_count += 1

                try:
                    await self._process_message(
                        str(message_id),
                        fields,
                    )

                except asyncio.CancelledError:
                    raise

                except Exception as error:
                    print(
                        "[EVIDENCE] Own-pending "
                        "recovery failed "
                        f"message={message_id}: "
                        f"{error}"
                    )

        return recovered_count

    # ========================================================
    # STALE PENDING
    # ========================================================

    async def _recover_stale_pending_once(
        self,
    ) -> int:
        """
        Claim stale pending messages from failed
        Evidence Agent instances.
        """

        if self.redis_client is None:
            raise RuntimeError(
                "Redis client unavailable."
            )

        try:
            result = (
                await self.redis_client.xautoclaim(
                    name=self.input_stream,
                    groupname=self.group_name,
                    consumername=self.consumer_name,
                    min_idle_time=(
                        PENDING_CLAIM_IDLE_MS
                    ),
                    start_id="0-0",
                    count=(
                        PENDING_CLAIM_BATCH_SIZE
                    ),
                )
            )

        except Exception as error:
            print(
                f"[EVIDENCE] XAUTOCLAIM failed: "
                f"{error}"
            )

            return 0

        if not result or len(result) < 2:
            return 0

        messages = result[1]

        if not messages:
            return 0

        recovered_count = 0

        for message_id, fields in messages:
            recovered_count += 1

            try:
                print(
                    "[EVIDENCE] Recovering "
                    f"stale pending "
                    f"message={message_id}"
                )

                await self._process_message(
                    str(message_id),
                    fields,
                )

            except asyncio.CancelledError:
                raise

            except Exception as error:
                print(
                    "[EVIDENCE] Stale pending "
                    "recovery failed "
                    f"message={message_id}: "
                    f"{error}"
                )

        return recovered_count

    async def _maybe_recover_pending(
        self,
    ) -> int:
        """Periodically recover pending messages."""

        now = (
            asyncio.get_running_loop().time()
        )

        if (
            now - self._last_pending_recovery
            < PENDING_RECOVERY_INTERVAL_SECONDS
        ):
            return 0

        self._last_pending_recovery = now

        total_recovered = 0

        own_recovered = (
            await self._recover_own_pending_once()
        )

        if own_recovered:
            print(
                f"[EVIDENCE] Recovered "
                f"{own_recovered} own pending "
                "message(s)."
            )

        total_recovered += (
            own_recovered
        )

        stale_recovered = (
            await self._recover_stale_pending_once()
        )

        if stale_recovered:
            print(
                f"[EVIDENCE] Recovered "
                f"{stale_recovered} stale pending "
                "message(s)."
            )

        total_recovered += (
            stale_recovered
        )

        return total_recovered

    # ========================================================
    # RUN
    # ========================================================

    async def run(
        self,
    ) -> None:
        """
        Main Evidence Agent loop.

        Redis/network errors are retried.

        Individual evidence-job failures remain isolated.
        """

        if not self._consumer_group_ready:
            raise RuntimeError(
                "Evidence consumer group "
                "is not ready."
            )

        print(
            f"[EVIDENCE] Agent running "
            f"agent_id={self.agent_id} "
            f"instance_id={self.instance_id} "
            f"hostname={self.hostname}"
        )

        print(
            f"[EVIDENCE] Live source wait="
            f"{LIVE_SOURCE_WAIT_SECONDS}s "
            f"poll={LIVE_SOURCE_POLL_SECONDS}s"
        )

        print(
            f"[EVIDENCE] Default evidence window "
            f"pre={DEFAULT_PRE_SECONDS}s "
            f"post={DEFAULT_POST_SECONDS}s"
        )

        print(
            f"[EVIDENCE] FFmpeg stitch timeout="
            f"{FFMPEG_STITCH_TIMEOUT_SECONDS}s"
        )

        print(
            "[EVIDENCE] Expired rolling-buffer "
            "requests will be ACKed after "
            "evidence.failed is published."
        )

        consecutive_errors = 0

        while self.running:
            try:
                await self._maybe_recover_pending()

                processed = (
                    await self._consume_once()
                )

                if processed:
                    consecutive_errors = 0

            except asyncio.CancelledError:
                raise

            except Exception as error:
                consecutive_errors += 1

                print(
                    f"[EVIDENCE] Consumer error "
                    f"#{consecutive_errors}: "
                    f"{error}"
                )

                await asyncio.sleep(
                    min(
                        RETRY_DELAY_SECONDS
                        * max(
                            1,
                            consecutive_errors,
                        ),
                        30.0,
                    )
                )

        print(
            f"[EVIDENCE] Run loop stopped "
            f"for {self.agent_id}"
        )


# ============================================================
# EVENT CONVERSION
# ============================================================

def _event_to_generator_dict(
    event: BaseEvent,
) -> dict[str, Any]:
    """
    Convert canonical BaseEvent into dictionary expected
    by evidence generator.
    """

    data = _event_data(event)
    request = _nested_evidence_request(
        event
    )

    result = dict(
        data
    )

    if request:
        result[
            "evidence_request"
        ] = dict(request)

        for key, value in request.items():
            result.setdefault(
                key,
                value,
            )

    result[
        "event_id"
    ] = event.event_id

    result[
        "event_type"
    ] = event.event_type

    result[
        "type"
    ] = event.event_type

    result[
        "timestamp"
    ] = event.timestamp.isoformat()

    result[
        "camera_id"
    ] = event.camera.camera_id

    event_time = request.get(
        "event_time"
    )

    if event_time is None:
        event_time = data.get(
            "event_time"
        )

    if event_time is None:
        event_time = data.get(
            "frame_timestamp"
        )

    if event_time is None:
        event_time = data.get(
            "timestamp_seconds"
        )

    if event_time is not None:
        result[
            "event_time"
        ] = event_time

        result[
            "time"
        ] = event_time

    return result


# ============================================================
# ENTRY POINT
# ============================================================

async def _main() -> None:
    """Start one independently supervised Evidence Agent."""

    agent = EvidenceAgent()

    await agent.run_forever()


def main() -> None:
    """Synchronous process entry point."""

    try:
        asyncio.run(
            _main()
        )

    except KeyboardInterrupt:
        print(
            "[EVIDENCE] Keyboard interrupt; "
            "agent stopped."
        )


if __name__ == "__main__":
    main()