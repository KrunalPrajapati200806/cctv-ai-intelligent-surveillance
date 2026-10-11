"""
Generic Redis event-stream query helpers.

This module is intentionally separate from the Incident Agent consumer.

Responsibilities:
    - Read historical/latest events from Redis Streams.
    - Decode Redis byte values.
    - Normalize stream fields.
    - Parse canonical event JSON.
    - Validate canonical events.
    - Provide lightweight API-facing stream queries.

Non-responsibilities:
    - Creating incidents.
    - Updating incidents.
    - Evidence generation.
    - Incident recovery.
    - Agent supervision.
    - Running background consumers.

Incident processing belongs to:
    backend.app.messaging.consumer
"""

from __future__ import annotations

import json
from typing import Any

from backend.app.messaging.redis_client import redis_client
from shared.schemas.event_schema import validate_event


# ============================================================
# STREAM CONFIGURATION
# ============================================================

STREAMS: dict[str, str] = {
    "detection": "events.detection",
    "tracking": "events.tracking",
    "behavior": "events.behavior",
}


# ============================================================
# REDIS VALUE HELPERS
# ============================================================

def decode_value(value: Any) -> Any:
    """
    Decode Redis bytes into UTF-8 strings.

    Non-byte values are returned unchanged.
    """
    if isinstance(value, bytes):
        return value.decode("utf-8")

    return value


def normalize_fields(fields: Any) -> dict[str, Any]:
    """
    Normalize Redis stream fields into a Python dictionary.

    Redis clients may return byte keys and byte values.
    """
    if not isinstance(fields, dict):
        return {}

    return {
        decode_value(key): decode_value(value)
        for key, value in fields.items()
    }


# ============================================================
# EVENT PARSING
# ============================================================

def parse_event(fields: Any) -> dict[str, Any] | None:
    """
    Parse a Redis stream message into a canonical event dictionary.

    Expected Redis format:

        {
            "event": "<JSON>"
        }

    A dictionary event is also accepted for compatibility.

    Invalid events return None rather than raising so that one
    malformed event cannot break API-level event retrieval.
    """
    normalized_fields = normalize_fields(fields)

    raw_event = normalized_fields.get("event")

    if raw_event is None:
        return None

    try:
        if isinstance(raw_event, str):
            event = json.loads(raw_event)

        elif isinstance(raw_event, dict):
            event = raw_event

        else:
            return None

    except (
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ):
        return None

    if not isinstance(event, dict):
        return None

    try:
        validated_event = validate_event(event)
    except Exception:
        return None

    return validated_event.to_dict()


# ============================================================
# STREAM VALIDATION
# ============================================================

def validate_stream(stream_name: str) -> str:
    """
    Validate that an API-requested stream belongs to the
    known application streams.

    Raises:
        ValueError: if the stream is not registered.
    """
    if not isinstance(stream_name, str):
        raise ValueError("stream_name must be a string")

    normalized = stream_name.strip()

    if not normalized:
        raise ValueError("stream_name cannot be empty")

    if normalized not in STREAMS.values():
        raise ValueError(
            f"Unsupported event stream: {normalized}"
        )

    return normalized


# ============================================================
# EVENT RETRIEVAL
# ============================================================

async def get_events(
    stream_name: str,
    last_id: str = "0-0",
    count: int = 20,
) -> list[dict[str, Any]]:
    """
    Retrieve events from a Redis stream.

    Args:
        stream_name:
            One of the registered application streams.

        last_id:
            Redis stream ID from which to read.
            Example: "0-0".

        count:
            Maximum number of events to retrieve.

    Returns:
        A list of validated canonical event dictionaries.

    Notes:
        Invalid/malformed events are skipped rather than allowing
        one bad stream entry to break the entire API request.
    """
    stream_name = validate_stream(stream_name)

    try:
        count = int(count)
    except (TypeError, ValueError):
        count = 20

    count = max(1, min(count, 100))

    if not isinstance(last_id, str) or not last_id.strip():
        last_id = "0-0"

    try:
        messages = await redis_client.xrange(
            name=stream_name,
            min=last_id,
            count=count,
        )
    except Exception as exc:
        print(
            "[EVENT_CONSUMER] Redis read error: "
            f"stream={stream_name} "
            f"error={exc}"
        )
        return []

    events: list[dict[str, Any]] = []

    for redis_message_id, fields in messages:
        try:
            event = parse_event(fields)

            if event is None:
                continue

            event["_redis_id"] = decode_value(
                redis_message_id
            )

            events.append(event)

        except Exception as exc:
            print(
                "[EVENT_CONSUMER] Event parsing failed; "
                f"stream={stream_name} "
                f"redis_id={decode_value(redis_message_id)} "
                f"error={exc}"
            )

    return events


# ============================================================
# LATEST EVENTS
# ============================================================

async def get_latest_events(
    stream_name: str,
    count: int = 20,
) -> list[dict[str, Any]]:
    """
    Retrieve the latest validated events from a Redis stream.

    Uses XREVRANGE so the newest events are returned first.
    """
    stream_name = validate_stream(stream_name)

    try:
        count = int(count)
    except (TypeError, ValueError):
        count = 20

    count = max(1, min(count, 100))

    try:
        messages = await redis_client.xrevrange(
            name=stream_name,
            max="+",
            min="-",
            count=count,
        )
    except Exception as exc:
        print(
            "[EVENT_CONSUMER] Redis latest-events error: "
            f"stream={stream_name} "
            f"error={exc}"
        )
        return []

    events: list[dict[str, Any]] = []

    for redis_message_id, fields in messages:
        try:
            event = parse_event(fields)

            if event is None:
                continue

            event["_redis_id"] = decode_value(
                redis_message_id
            )

            events.append(event)

        except Exception as exc:
            print(
                "[EVENT_CONSUMER] Latest event parsing failed; "
                f"stream={stream_name} "
                f"redis_id={decode_value(redis_message_id)} "
                f"error={exc}"
            )

    return events


# ============================================================
# STREAM-SPECIFIC HELPERS
# ============================================================

async def get_detection_events(
    last_id: str = "0-0",
    count: int = 20,
) -> list[dict[str, Any]]:
    """
    Retrieve validated detection events.
    """
    return await get_events(
        STREAMS["detection"],
        last_id,
        count,
    )


async def get_tracking_events(
    last_id: str = "0-0",
    count: int = 20,
) -> list[dict[str, Any]]:
    """
    Retrieve validated tracking events.
    """
    return await get_events(
        STREAMS["tracking"],
        last_id,
        count,
    )


async def get_behavior_events(
    last_id: str = "0-0",
    count: int = 20,
) -> list[dict[str, Any]]:
    """
    Retrieve validated behavior events.
    """
    return await get_events(
        STREAMS["behavior"],
        last_id,
        count,
    )


# ============================================================
# PUBLIC API
# ============================================================

__all__ = [
    "STREAMS",
    "decode_value",
    "normalize_fields",
    "parse_event",
    "validate_stream",
    "get_events",
    "get_latest_events",
    "get_detection_events",
    "get_tracking_events",
    "get_behavior_events",
]
