"""
Agent heartbeat infrastructure.

Heartbeat events are system/liveness events.

Responsibilities
----------------
- Publish periodic agent heartbeats.
- Keep heartbeat publishing isolated from agent processing.
- Never terminate an agent because Redis temporarily fails.
- Provide deterministic heartbeat failure injection for testing.

Heartbeat failure test
----------------------
Set:

    TEST_HEARTBEAT_FAILURE_AGENT=person-detector-01

The targeted agent will:

1. Send exactly one heartbeat.
2. Stop sending heartbeats.
3. Continue running normally.

This allows the monitoring system to detect:

    heartbeat timeout
        ->
    DEAD
        ->
    supervisor recovery

The failure is intentionally limited to heartbeat publication.
The worker process itself remains alive.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import uuid
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as redis


# ============================================================
# CONFIGURATION
# ============================================================

HEARTBEAT_STREAM = os.getenv(
    "HEARTBEAT_STREAM",
    "events.system",
)

HEARTBEAT_STATUS = "alive"


# ============================================================
# HELPERS
# ============================================================

def utc_now_iso() -> str:
    """
    Return current UTC time in ISO-8601 format.
    """
    return datetime.now(timezone.utc).isoformat()


def _json(value: object) -> str:
    """
    Serialize nested heartbeat data into a Redis-safe scalar.
    """
    return json.dumps(
        value,
        separators=(",", ":"),
        ensure_ascii=False,
    )


# ============================================================
# HEARTBEAT
# ============================================================

async def send_heartbeat(
    redis_client: redis.Redis,
    *,
    agent_id: str,
    instance_id: str,
    hostname: Optional[str] = None,
    status: str = HEARTBEAT_STATUS,
) -> bool:
    """
    Publish one heartbeat.

    Returns:
        True  -> heartbeat published
        False -> heartbeat failed

    Redis errors are intentionally swallowed so that the
    heartbeat mechanism itself cannot crash the worker.
    """

    hostname = hostname or socket.gethostname()

    event_id = str(uuid.uuid4())
    timestamp = utc_now_iso()

    source = {
        "agent_id": agent_id,
        "instance_id": instance_id,
        "hostname": hostname,
    }

    data = {
        "status": status,
    }

    # Redis Streams require scalar values.
    redis_event = {
        "event_id": event_id,
        "event_type": "agent.heartbeat",
        "version": "1.0",
        "timestamp": timestamp,

        # Nested structures are serialized.
        "source": _json(source),
        "data": _json(data),

        # Important fields remain directly searchable.
        "agent_id": agent_id,
        "instance_id": instance_id,
        "hostname": hostname,
        "status": status,
    }

    try:
        await redis_client.xadd(
            HEARTBEAT_STREAM,
            redis_event,
        )
        return True

    except asyncio.CancelledError:
        raise

    except Exception as error:
        print(
            "[HEARTBEAT] Failed for "
            f"{agent_id} "
            f"(instance={instance_id}): "
            f"{error}"
        )
        return False


# ============================================================
# FAILURE INJECTION
# ============================================================

def heartbeat_failure_test_enabled(
    agent_id: str,
) -> bool:
    """
    Determine whether heartbeat failure injection is enabled.

    Environment variable:

        TEST_HEARTBEAT_FAILURE_AGENT=person-detector-01

    The environment is evaluated when the heartbeat loop starts.
    """

    target = os.getenv(
        "TEST_HEARTBEAT_FAILURE_AGENT",
        "",
    ).strip()

    return bool(
        target and target == agent_id
    )


# ============================================================
# HEARTBEAT LOOP
# ============================================================

async def heartbeat_loop(
    redis_client: redis.Redis,
    *,
    agent_id: str,
    instance_id: str,
    hostname: Optional[str] = None,
    interval: int = 10,
) -> None:
    """
    Continuously publish heartbeats.

    Normal mode
    -----------
    Heartbeat is published every `interval` seconds.

    Failure-test mode
    ------------------
    If TEST_HEARTBEAT_FAILURE_AGENT matches this agent:

        - exactly one heartbeat is sent
        - subsequent heartbeats are suppressed
        - worker process remains alive

    This simulates a broken heartbeat/liveness signal without
    killing the actual worker.
    """

    if interval <= 0:
        raise ValueError(
            "Heartbeat interval must be greater than zero."
        )

    hostname = hostname or socket.gethostname()

    test_enabled = heartbeat_failure_test_enabled(
        agent_id
    )

    heartbeat_suppressed = False

    if test_enabled:
        print(
            "[HEARTBEAT] "
            "FAILURE INJECTION ENABLED for "
            f"{agent_id}"
        )
        print(
            "[HEARTBEAT] "
            "This worker will send ONE heartbeat "
            "and then stop heartbeats."
        )

    while True:
        try:

            # ==================================================
            # HEARTBEAT FAILURE TEST
            # ==================================================

            if test_enabled:

                if not heartbeat_suppressed:

                    success = await send_heartbeat(
                        redis_client,
                        agent_id=agent_id,
                        instance_id=instance_id,
                        hostname=hostname,
                    )

                    if success:
                        print(
                            "[HEARTBEAT] "
                            f"Initial test heartbeat sent "
                            f"for {agent_id}"
                        )

                        heartbeat_suppressed = True

                        print(
                            "[HEARTBEAT] "
                            f"Heartbeat suppression ACTIVE "
                            f"for {agent_id}"
                        )

                else:
                    # IMPORTANT:
                    # Do NOT send another heartbeat.
                    print(
                        "[HEARTBEAT] "
                        f"Suppressing heartbeat for "
                        f"failure test: {agent_id}"
                    )

            # ==================================================
            # NORMAL MODE
            # ==================================================

            else:

                await send_heartbeat(
                    redis_client,
                    agent_id=agent_id,
                    instance_id=instance_id,
                    hostname=hostname,
                )

            await asyncio.sleep(interval)

        except asyncio.CancelledError:

            print(
                "[HEARTBEAT] "
                f"Stopped for {agent_id}"
            )

            raise

        except Exception as error:

            # The heartbeat mechanism must NEVER become
            # the reason the worker process dies.

            print(
                "[HEARTBEAT] "
                f"Loop error for {agent_id}: "
                f"{error}"
            )

            try:
                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                raise