"""
Heartbeat consumer and monitoring bridge.

Responsibilities
----------------
- Consume agent heartbeat events from Redis Streams.
- Parse the current heartbeat event format.
- Support practical legacy/wrapped heartbeat formats.
- Validate heartbeat identity and timestamps.
- Reject stale and out-of-order heartbeats.
- Update AgentRegistry with accepted liveness.
- Recover stale pending messages with XAUTOCLAIM.
- Never allow one malformed heartbeat to terminate the consumer.
- Never acknowledge a message before it has been intentionally handled.
- Isolate failures between individual messages.
- Survive Redis/network/registry errors.

Heartbeat stream
----------------
events.system

Consumer group
--------------
heartbeat-workers

Architecture
------------
Agent
    |
    | heartbeat
    v
Redis events.system
    |
    v
heartbeat_consumer.py
    |
    | accepted heartbeat
    v
AgentRegistry
    |
    v
watchdog.py
    |
    v
supervisor.py

Important
---------
This component does NOT:
- restart processes
- terminate processes
- mark agents DEAD
- make recovery decisions
- consume camera streams
- process video frames
- run AI inference

Recovery belongs to supervisor.py.
Observation belongs to watchdog.py.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import socket
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import redis.asyncio as redis

from backend.app.monitoring.agent_registry import agent_registry


# ============================================================
# REDIS CONFIGURATION
# ============================================================

REDIS_HOST = os.getenv(
    "REDIS_HOST",
    "localhost",
).strip() or "localhost"


def _positive_int(
    name: str,
    default: int,
) -> int:
    raw = os.getenv(
        name,
        str(default),
    )

    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default

    return value if value > 0 else default


def _non_negative_int(
    name: str,
    default: int,
) -> int:
    raw = os.getenv(
        name,
        str(default),
    )

    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default

    return value if value >= 0 else default


def _positive_float(
    name: str,
    default: float,
) -> float:
    raw = os.getenv(
        name,
        str(default),
    )

    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default

    return value if value > 0 else default


REDIS_PORT = _positive_int(
    "REDIS_PORT",
    6379,
)


# ============================================================
# STREAM CONFIGURATION
# ============================================================

STREAM_NAME = (
    os.getenv(
        "HEARTBEAT_STREAM",
        "events.system",
    ).strip()
    or "events.system"
)

GROUP_NAME = (
    os.getenv(
        "HEARTBEAT_GROUP",
        "heartbeat-workers",
    ).strip()
    or "heartbeat-workers"
)

DEFAULT_CONSUMER_NAME = (
    f"heartbeat-consumer-"
    f"{socket.gethostname()}-"
    f"{uuid.uuid4().hex[:8]}"
)

CONSUMER_NAME = (
    os.getenv(
        "HEARTBEAT_CONSUMER_NAME",
        DEFAULT_CONSUMER_NAME,
    ).strip()
    or DEFAULT_CONSUMER_NAME
)


# ============================================================
# CONSUMER CONFIGURATION
# ============================================================

READ_COUNT = _positive_int(
    "HEARTBEAT_READ_COUNT",
    10,
)

BLOCK_MS = _positive_int(
    "HEARTBEAT_BLOCK_MS",
    5000,
)

RETRY_DELAY = _positive_float(
    "HEARTBEAT_RETRY_DELAY",
    2.0,
)

PENDING_RECOVERY_INTERVAL = _positive_float(
    "HEARTBEAT_PENDING_RECOVERY_INTERVAL",
    15.0,
)


# ============================================================
# PENDING MESSAGE RECOVERY
# ============================================================

PENDING_IDLE_MS = _non_negative_int(
    "HEARTBEAT_PENDING_IDLE_MS",
    15000,
)


# ============================================================
# LIVENESS CONFIGURATION
# ============================================================

HEARTBEAT_TIMEOUT = _positive_float(
    "HEARTBEAT_TIMEOUT",
    30.0,
)

MAX_CLOCK_SKEW_SECONDS = _positive_float(
    "HEARTBEAT_MAX_CLOCK_SKEW",
    10.0,
)


# ============================================================
# REDIS SOCKET CONFIGURATION
# ============================================================

REDIS_SOCKET_CONNECT_TIMEOUT = _positive_float(
    "REDIS_CONNECT_TIMEOUT",
    5.0,
)

REDIS_SOCKET_TIMEOUT = _positive_float(
    "REDIS_SOCKET_TIMEOUT",
    10.0,
)


# ============================================================
# HEARTBEAT EVENT CONFIGURATION
# ============================================================

HEARTBEAT_EVENT_TYPE = "agent.heartbeat"

VALID_HEARTBEAT_STATUSES = {
    "alive",
}


# ============================================================
# DATA MODEL
# ============================================================

@dataclass(frozen=True)
class Heartbeat:
    """
    Normalized heartbeat representation.
    """

    agent_id: str
    instance_id: str
    hostname: Optional[str]
    status: str
    timestamp: datetime
    event_id: Optional[str]
    event_type: str
    version: Optional[str]
    generation: Optional[int]


# ============================================================
# DECODING HELPERS
# ============================================================

def decode(
    value: Any,
) -> Any:
    """
    Decode Redis bytes safely.

    Supports both:
    - decode_responses=True
    - decode_responses=False
    """

    if isinstance(value, bytes):
        return value.decode(
            "utf-8",
            errors="replace",
        )

    return value


def normalize_fields(
    fields: Any,
) -> dict[str, Any]:
    """
    Normalize Redis stream fields.
    """

    if not isinstance(
        fields,
        dict,
    ):
        return {}

    return {
        str(decode(key)): decode(value)
        for key, value in fields.items()
    }


# ============================================================
# JSON HELPERS
# ============================================================

def parse_json_object(
    value: Any,
) -> Optional[dict[str, Any]]:
    """
    Parse a dictionary or JSON object string.
    """

    if isinstance(
        value,
        dict,
    ):
        return value

    value = decode(value)

    if not isinstance(
        value,
        str,
    ):
        return None

    value = value.strip()

    if not value:
        return None

    try:
        parsed = json.loads(value)
    except (
        json.JSONDecodeError,
        TypeError,
    ):
        return None

    if isinstance(
        parsed,
        dict,
    ):
        return parsed

    return None


# ============================================================
# TIMESTAMP HELPERS
# ============================================================

def parse_timestamp(
    timestamp: Any,
) -> Optional[datetime]:
    """
    Parse ISO-8601 timestamp and normalize to UTC.
    """

    timestamp = decode(timestamp)

    if not isinstance(
        timestamp,
        str,
    ):
        return None

    timestamp = timestamp.strip()

    if not timestamp:
        return None

    try:
        parsed = datetime.fromisoformat(
            timestamp.replace(
                "Z",
                "+00:00",
            )
        )
    except (
        ValueError,
        TypeError,
    ):
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc,
        )

    return parsed.astimezone(
        timezone.utc
    )


def heartbeat_age_seconds(
    timestamp: datetime,
    *,
    now: Optional[datetime] = None,
) -> Optional[float]:
    """
    Calculate heartbeat age.

    Future timestamps beyond MAX_CLOCK_SKEW_SECONDS
    are rejected.
    """

    if now is None:
        now = datetime.now(
            timezone.utc
        )

    age = (
        now - timestamp
    ).total_seconds()

    if age < -MAX_CLOCK_SKEW_SECONDS:
        return None

    return max(
        0.0,
        age,
    )


# ============================================================
# GENERATION HELPERS
# ============================================================

def parse_generation(
    value: Any,
) -> Optional[int]:
    """
    Parse optional process generation.

    Generation is optional here for compatibility with older
    heartbeat producers.

    If present, it must be a non-negative integer.
    """

    if value is None:
        return None

    value = decode(value)

    if isinstance(
        value,
        bool,
    ):
        return None

    try:
        generation = int(value)
    except (
        TypeError,
        ValueError,
    ):
        return None

    if generation < 0:
        return None

    return generation


# ============================================================
# HEARTBEAT PARSING
# ============================================================

def parse_heartbeat(
    fields: Any,
) -> Optional[Heartbeat]:
    """
    Parse and normalize a heartbeat event.

    Supported current format:

        {
            "event_id": "...",
            "event_type": "agent.heartbeat",
            "version": "1.0",
            "timestamp": "...",
            "source": "{...}",
            "data": "{...}",
            "agent_id": "...",
            "instance_id": "...",
            "hostname": "...",
            "generation": 1,
            "status": "alive"
        }

    Legacy support:
    - event={JSON object}
    - source={JSON object}
    - data={JSON object}
    """

    normalized = normalize_fields(
        fields
    )

    if not normalized:
        return None

    # --------------------------------------------------------
    # Legacy wrapped event
    # --------------------------------------------------------

    wrapped_event = parse_json_object(
        normalized.get("event")
    )

    if wrapped_event:
        merged = {
            **normalized,
            **wrapped_event,
        }
    else:
        merged = dict(normalized)

    # --------------------------------------------------------
    # Source/data payloads
    # --------------------------------------------------------

    source = parse_json_object(
        merged.get("source")
    )

    data = parse_json_object(
        merged.get("data")
    )

    # --------------------------------------------------------
    # Event type
    # --------------------------------------------------------

    event_type = (
        merged.get("event_type")
        or merged.get("type")
    )

    if event_type is not None:
        event_type = str(
            event_type
        ).strip()

    # Practical legacy compatibility.
    if event_type not in {
        HEARTBEAT_EVENT_TYPE,
        "heartbeat",
        "agent_heartbeat",
    }:
        return None

    # --------------------------------------------------------
    # Agent identity
    # --------------------------------------------------------

    agent_id = (
        merged.get("agent_id")
        or merged.get("source_agent_id")
    )

    if not agent_id and source:
        agent_id = source.get(
            "agent_id"
        )

    if not agent_id and data:
        agent_id = data.get(
            "agent_id"
        )

    if agent_id is None:
        return None

    agent_id = str(
        agent_id
    ).strip()

    if not agent_id:
        return None

    # --------------------------------------------------------
    # Instance identity
    # --------------------------------------------------------

    instance_id = (
        merged.get("instance_id")
        or merged.get("source_instance_id")
    )

    if not instance_id and source:
        instance_id = source.get(
            "instance_id"
        )

    if not instance_id and data:
        instance_id = data.get(
            "instance_id"
        )

    if instance_id is None:
        return None

    instance_id = str(
        instance_id
    ).strip()

    if not instance_id:
        return None

    # --------------------------------------------------------
    # Hostname
    # --------------------------------------------------------

    hostname = (
        merged.get("hostname")
        or (
            source.get("hostname")
            if source
            else None
        )
        or (
            data.get("hostname")
            if data
            else None
        )
    )

    if hostname is not None:
        hostname = str(
            hostname
        ).strip()

        if not hostname:
            hostname = None

    # --------------------------------------------------------
    # Status
    # --------------------------------------------------------

    status = (
        merged.get("status")
        or (
            data.get("status")
            if data
            else None
        )
        or "alive"
    )

    status = str(
        status
    ).strip().lower()

    if status not in VALID_HEARTBEAT_STATUSES:
        return None

    # --------------------------------------------------------
    # Timestamp
    # --------------------------------------------------------

    timestamp_raw = (
        merged.get("timestamp")
        or (
            data.get("timestamp")
            if data
            else None
        )
    )

    timestamp = parse_timestamp(
        timestamp_raw
    )

    if timestamp is None:
        return None

    # --------------------------------------------------------
    # Generation
    # --------------------------------------------------------

    generation_raw = (
        merged.get("generation")
        or merged.get("process_generation")
        or (
            source.get("generation")
            if source
            else None
        )
        or (
            data.get("generation")
            if data
            else None
        )
    )

    generation = parse_generation(
        generation_raw
    )

    # If generation was explicitly supplied but invalid,
    # reject the heartbeat rather than silently accepting it.
    if (
        generation_raw is not None
        and generation is None
    ):
        return None

    # --------------------------------------------------------
    # Event metadata
    # --------------------------------------------------------

    event_id = merged.get(
        "event_id"
    )

    if event_id is not None:
        event_id = str(
            event_id
        ).strip() or None

    version = merged.get(
        "version"
    )

    if version is not None:
        version = str(
            version
        ).strip() or None

    return Heartbeat(
        agent_id=agent_id,
        instance_id=instance_id,
        hostname=hostname,
        status=status,
        timestamp=timestamp,
        event_id=event_id,
        event_type=HEARTBEAT_EVENT_TYPE,
        version=version,
        generation=generation,
    )


# ============================================================
# EVENT ORDER PROTECTION
# ============================================================

class HeartbeatOrderingGuard:
    """
    Prevent an older heartbeat from refreshing liveness after
    a newer heartbeat was already accepted.

    Key:
        (agent_id, instance_id)

    Important:
    This is a process-local safety layer.

    AgentRegistry should ideally persist the accepted heartbeat
    event timestamp itself for cross-consumer/restart protection.
    """

    def __init__(self) -> None:
        self._latest: dict[
            tuple[str, str],
            datetime,
        ] = {}

    def is_newer_or_equal(
        self,
        heartbeat: Heartbeat,
    ) -> bool:
        key = (
            heartbeat.agent_id,
            heartbeat.instance_id,
        )

        previous = self._latest.get(
            key
        )

        if (
            previous is not None
            and heartbeat.timestamp < previous
        ):
            return False

        return True

    def accept(
        self,
        heartbeat: Heartbeat,
    ) -> None:
        key = (
            heartbeat.agent_id,
            heartbeat.instance_id,
        )

        previous = self._latest.get(
            key
        )

        if (
            previous is None
            or heartbeat.timestamp > previous
        ):
            self._latest[key] = (
                heartbeat.timestamp
            )

    def remove_instance(
        self,
        agent_id: str,
        instance_id: str,
    ) -> None:
        self._latest.pop(
            (
                agent_id,
                instance_id,
            ),
            None,
        )


heartbeat_ordering_guard = (
    HeartbeatOrderingGuard()
)


# ============================================================
# AGENT REGISTRY COMPATIBILITY
# ============================================================

def _registry_update_supports(
    parameter_name: str,
) -> bool:
    """
    Detect whether the current AgentRegistry implementation
    supports an optional heartbeat parameter.

    This keeps the consumer compatible while AgentRegistry is
    evolving through Section 1.
    """

    try:
        signature = inspect.signature(
            agent_registry.update_heartbeat
        )
    except (
        TypeError,
        ValueError,
    ):
        return False

    parameters = signature.parameters

    return (
        parameter_name in parameters
        or any(
            parameter.kind
            == inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        )
    )


_REGISTRY_SUPPORTS_TIMESTAMP = (
    _registry_update_supports(
        "heartbeat_timestamp"
    )
    or _registry_update_supports(
        "timestamp"
    )
)

_REGISTRY_SUPPORTS_GENERATION = (
    _registry_update_supports(
        "generation"
    )
    or _registry_update_supports(
        "process_generation"
    )
)


def update_agent_registry(
    heartbeat: Heartbeat,
) -> bool:
    """
    Update AgentRegistry using the strongest API supported
    by the currently installed registry implementation.

    Returns:
        True  -> accepted
        False -> intentionally rejected
    """

    kwargs: dict[str, Any] = {
        "agent_id": heartbeat.agent_id,
        "instance_id": heartbeat.instance_id,
        "hostname": heartbeat.hostname,
    }

    try:
        signature = inspect.signature(
            agent_registry.update_heartbeat
        )

        parameters = signature.parameters

        if (
            heartbeat.generation is not None
            and _REGISTRY_SUPPORTS_GENERATION
        ):
            if "generation" in parameters:
                kwargs["generation"] = (
                    heartbeat.generation
                )
            elif "process_generation" in parameters:
                kwargs["process_generation"] = (
                    heartbeat.generation
                )
            else:
                kwargs["generation"] = (
                    heartbeat.generation
                )

        if _REGISTRY_SUPPORTS_TIMESTAMP:
            if "heartbeat_timestamp" in parameters:
                kwargs["heartbeat_timestamp"] = (
                    heartbeat.timestamp
                )
            elif "timestamp" in parameters:
                kwargs["timestamp"] = (
                    heartbeat.timestamp
                )
            else:
                kwargs["heartbeat_timestamp"] = (
                    heartbeat.timestamp
                )

        return bool(
            agent_registry.update_heartbeat(
                **kwargs
            )
        )

    except TypeError:
        # Compatibility fallback for the currently installed
        # registry API.
        return bool(
            agent_registry.update_heartbeat(
                agent_id=heartbeat.agent_id,
                instance_id=heartbeat.instance_id,
                hostname=heartbeat.hostname,
            )
        )


# ============================================================
# CONSUMER GROUP
# ============================================================

async def ensure_consumer_group(
    redis_client: redis.Redis,
) -> None:
    """
    Ensure the consumer group exists.

    GROUP_START_ID controls the initial position only when
    the group is created for the first time.

    Default:
        $

    This prevents a newly deployed heartbeat consumer from
    replaying an entire historical events.system stream.
    """

    group_start_id = (
        os.getenv(
            "HEARTBEAT_GROUP_START_ID",
            "$",
        ).strip()
        or "$"
    )

    try:
        await redis_client.xgroup_create(
            STREAM_NAME,
            GROUP_NAME,
            id=group_start_id,
            mkstream=True,
        )

        print(
            "[HEARTBEAT] Created consumer group "
            f"{GROUP_NAME} at {group_start_id}"
        )

    except redis.ResponseError as error:
        if "BUSYGROUP" in str(error):
            return

        raise


# ============================================================
# ACKNOWLEDGEMENT
# ============================================================

async def acknowledge(
    redis_client: redis.Redis,
    message_id: Any,
) -> None:
    """
    ACK one successfully handled message.
    """

    await redis_client.xack(
        STREAM_NAME,
        GROUP_NAME,
        message_id,
    )


# ============================================================
# MESSAGE PROCESSING
# ============================================================

async def process_message(
    redis_client: redis.Redis,
    message_id: Any,
    fields: Any,
    *,
    recovered: bool = False,
) -> bool:
    """
    Process exactly one heartbeat.

    ACK policy
    ----------
    ACK when:
    - message is malformed
    - message is irrelevant
    - timestamp is invalid
    - timestamp is too old
    - heartbeat is out-of-order
    - registry intentionally rejects it
    - heartbeat is successfully accepted

    DO NOT ACK when:
    - Redis ACK itself fails
    - AgentRegistry raises an unexpected exception
    - another unexpected processing failure occurs

    Returns:
        True  -> message handled and ACK attempted successfully
        False -> message remains pending for later recovery
    """

    try:
        heartbeat = parse_heartbeat(
            fields
        )

        # ----------------------------------------------------
        # Malformed / irrelevant message
        # ----------------------------------------------------

        if heartbeat is None:
            print(
                "[HEARTBEAT] Ignoring malformed or "
                "irrelevant message: "
                f"{message_id}"
            )

            await acknowledge(
                redis_client,
                message_id,
            )

            return True

        now = datetime.now(
            timezone.utc
        )

        # ----------------------------------------------------
        # Future timestamp protection
        # ----------------------------------------------------

        age = heartbeat_age_seconds(
            heartbeat.timestamp,
            now=now,
        )

        if age is None:
            print(
                "[HEARTBEAT] Rejecting future-dated "
                f"heartbeat: agent={heartbeat.agent_id} "
                f"instance={heartbeat.instance_id} "
                f"message={message_id}"
            )

            await acknowledge(
                redis_client,
                message_id,
            )

            return True

        # ----------------------------------------------------
        # Stale heartbeat protection
        # ----------------------------------------------------

        if age > HEARTBEAT_TIMEOUT:
            print(
                "[HEARTBEAT] Ignoring stale heartbeat: "
                f"agent={heartbeat.agent_id} "
                f"age={age:.1f}s "
                f"timeout={HEARTBEAT_TIMEOUT:.1f}s "
                f"recovered={recovered}"
            )

            await acknowledge(
                redis_client,
                message_id,
            )

            return True

        # ----------------------------------------------------
        # Out-of-order heartbeat protection
        # ----------------------------------------------------

        if not heartbeat_ordering_guard.is_newer_or_equal(
            heartbeat
        ):
            print(
                "[HEARTBEAT] Ignoring out-of-order "
                f"heartbeat: agent={heartbeat.agent_id} "
                f"instance={heartbeat.instance_id} "
                f"timestamp={heartbeat.timestamp.isoformat()} "
                f"recovered={recovered}"
            )

            await acknowledge(
                redis_client,
                message_id,
            )

            return True

        # ----------------------------------------------------
        # Registry update
        # ----------------------------------------------------

        accepted = update_agent_registry(
            heartbeat
        )

        # ----------------------------------------------------
        # Registry intentionally rejected heartbeat
        # ----------------------------------------------------

        if not accepted:
            print(
                "[HEARTBEAT] Registry rejected heartbeat: "
                f"agent={heartbeat.agent_id} "
                f"instance={heartbeat.instance_id} "
                f"generation={heartbeat.generation}"
            )

            await acknowledge(
                redis_client,
                message_id,
            )

            return True

        # Registry accepted the heartbeat.
        heartbeat_ordering_guard.accept(
            heartbeat
        )

        # ----------------------------------------------------
        # Success logging
        # ----------------------------------------------------

        mode = (
            "RECOVERED"
            if recovered
            else "LIVE"
        )

        print(
            "[HEARTBEAT] "
            f"{mode} | "
            f"agent={heartbeat.agent_id} | "
            f"instance={heartbeat.instance_id} | "
            f"generation={heartbeat.generation} | "
            f"age={age:.2f}s"
        )

        # ----------------------------------------------------
        # ACK ONLY AFTER SUCCESS
        # ----------------------------------------------------

        await acknowledge(
            redis_client,
            message_id,
        )

        return True

    except asyncio.CancelledError:
        raise

    except Exception as error:
        print(
            "[HEARTBEAT ERROR] "
            f"message={message_id} "
            f"error={type(error).__name__}: "
            f"{error}"
        )

        # DO NOT ACK.
        #
        # Redis will keep the message pending and the
        # recovery mechanism can retry it later.

        return False


# ============================================================
# PENDING MESSAGE RECOVERY
# ============================================================

def _parse_xautoclaim_result(
    result: Any,
) -> tuple[Any, list[Any]]:
    """
    Normalize redis-py XAUTOCLAIM response.

    Legacy response:
        [
            next_start_id,
            messages,
            deleted_message_ids
        ]

    Unified/alternate clients may return a different shape.

    This function deliberately accepts the standard redis-py
    positional response while failing safely on unexpected data.
    """

    if not isinstance(
        result,
        (list, tuple),
    ):
        return "0-0", []

    if len(result) < 2:
        return "0-0", []

    next_start_id = result[0]
    messages = result[1]

    if not isinstance(
        messages,
        (list, tuple),
    ):
        messages = []

    return (
        next_start_id,
        list(messages),
    )


async def recover_pending_messages(
    redis_client: redis.Redis,
) -> int:
    """
    Recover stale pending heartbeat messages.

    Uses XAUTOCLAIM.

    Returns:
        Number of pending messages examined.

    Redis XAUTOCLAIM transfers ownership of idle pending
    entries to this consumer. The command is available from
    Redis 6.2+. :contentReference[oaicite:2]{index=2}
    """

    start_id = "0-0"
    examined_total = 0

    while True:
        try:
            result = await redis_client.xautoclaim(
                STREAM_NAME,
                GROUP_NAME,
                CONSUMER_NAME,
                PENDING_IDLE_MS,
                start_id,
                count=READ_COUNT,
            )

        except asyncio.CancelledError:
            raise

        except redis.ResponseError as error:
            print(
                "[HEARTBEAT] Pending recovery Redis "
                f"error: {error}"
            )
            return examined_total

        except Exception as error:
            print(
                "[HEARTBEAT] Pending recovery "
                f"unexpected error: {type(error).__name__}: "
                f"{error}"
            )
            return examined_total

        next_start_id, messages = (
            _parse_xautoclaim_result(
                result
            )
        )

        for message_id, fields in messages:
            examined_total += 1

            try:
                await process_message(
                    redis_client,
                    message_id,
                    fields,
                    recovered=True,
                )

            except asyncio.CancelledError:
                raise

            except Exception as error:
                print(
                    "[HEARTBEAT PENDING "
                    "ISOLATION ERROR] "
                    f"message={message_id} "
                    f"error={type(error).__name__}: "
                    f"{error}"
                )

        next_start_id = decode(
            next_start_id
        )

        if next_start_id in (
            "0-0",
            b"0-0",
            None,
        ):
            break

        start_id = str(
            next_start_id
        )

    if examined_total:
        print(
            "[HEARTBEAT] Examined "
            f"{examined_total} pending heartbeat(s)"
        )

    return examined_total


# ============================================================
# NEW MESSAGE CONSUMPTION
# ============================================================

async def consume_new_messages(
    redis_client: redis.Redis,
) -> int:
    """
    Consume newly delivered heartbeat messages.

    Returns:
        Number of messages received.
    """

    messages = await redis_client.xreadgroup(
        groupname=GROUP_NAME,
        consumername=CONSUMER_NAME,
        streams={
            STREAM_NAME: ">"
        },
        count=READ_COUNT,
        block=BLOCK_MS,
    )

    if not messages:
        return 0

    processed_count = 0

    for stream_name, stream_messages in messages:
        _ = stream_name

        for message_id, fields in stream_messages:
            try:
                await process_message(
                    redis_client,
                    message_id,
                    fields,
                    recovered=False,
                )

                processed_count += 1

            except asyncio.CancelledError:
                raise

            except Exception as error:
                print(
                    "[HEARTBEAT MESSAGE "
                    "ISOLATION ERROR] "
                    f"message={message_id} "
                    f"error={type(error).__name__}: "
                    f"{error}"
                )

    return processed_count


# ============================================================
# MAIN CONSUMER LOOP
# ============================================================

async def heartbeat_consumer_loop(
    redis_client: redis.Redis,
) -> None:
    """
    Main heartbeat consumer lifecycle.

    Redis
        ↓
    Consumer Group
        ↓
    Pending Recovery
        ↓
    New Heartbeats
        ↓
    AgentRegistry
        ↓
    Watchdog / Supervisor
    """

    await ensure_consumer_group(
        redis_client
    )

    print(
        "[HEARTBEAT] Consumer started | "
        f"stream={STREAM_NAME} | "
        f"group={GROUP_NAME} | "
        f"consumer={CONSUMER_NAME}"
    )

    print(
        "[HEARTBEAT] Configuration | "
        f"timeout={HEARTBEAT_TIMEOUT}s | "
        f"pending_idle={PENDING_IDLE_MS}ms | "
        f"read_count={READ_COUNT}"
    )

    print(
        "[HEARTBEAT] Ordering protection enabled"
    )

    # --------------------------------------------------------
    # Initial recovery
    # --------------------------------------------------------

    try:
        await recover_pending_messages(
            redis_client
        )

    except asyncio.CancelledError:
        raise

    except Exception as error:
        print(
            "[HEARTBEAT] Initial pending recovery "
            f"failed: {type(error).__name__}: {error}"
        )

    # --------------------------------------------------------
    # Continuous processing
    # --------------------------------------------------------

    last_pending_recovery = (
        asyncio.get_running_loop().time()
    )

    while True:
        try:
            await consume_new_messages(
                redis_client
            )

            now = (
                asyncio.get_running_loop().time()
            )

            if (
                now
                - last_pending_recovery
                >= PENDING_RECOVERY_INTERVAL
            ):
                await recover_pending_messages(
                    redis_client
                )

                last_pending_recovery = now

        except asyncio.CancelledError:
            print(
                "[HEARTBEAT] Consumer cancellation "
                "received."
            )
            raise

        except (
            redis.ConnectionError,
            redis.TimeoutError,
        ) as error:
            print(
                "[HEARTBEAT REDIS ERROR] "
                f"{type(error).__name__}: "
                f"{error}"
            )

            await asyncio.sleep(
                RETRY_DELAY
            )

        except Exception as error:
            print(
                "[HEARTBEAT CONSUMER ERROR] "
                f"{type(error).__name__}: "
                f"{error}"
            )

            await asyncio.sleep(
                RETRY_DELAY
            )

            try:
                await recover_pending_messages(
                    redis_client
                )

            except asyncio.CancelledError:
                raise

            except Exception as recovery_error:
                print(
                    "[HEARTBEAT] Recovery retry "
                    f"failed: "
                    f"{type(recovery_error).__name__}: "
                    f"{recovery_error}"
                )


# ============================================================
# REDIS CLIENT
# ============================================================

def create_redis_client() -> redis.Redis:
    """
    Create the standalone async Redis client.
    """

    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        decode_responses=True,
        socket_connect_timeout=(
            REDIS_SOCKET_CONNECT_TIMEOUT
        ),
        socket_timeout=(
            REDIS_SOCKET_TIMEOUT
        ),
        health_check_interval=30,
    )


# ============================================================
# STANDALONE ENTRY POINT
# ============================================================

async def main() -> None:
    """
    Standalone heartbeat consumer entry point.
    """

    redis_client = (
        create_redis_client()
    )

    try:
        await redis_client.ping()

        print(
            "[HEARTBEAT] Redis connection established."
        )

        await heartbeat_consumer_loop(
            redis_client
        )

    finally:
        await redis_client.aclose()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    asyncio.run(
        main()
    )