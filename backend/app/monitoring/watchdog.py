"""
Agent health watchdog.

Responsibilities
----------------

- Observe agent health from AgentRegistry.
- Detect missing/stale heartbeats.
- Report health state changes.
- Provide health snapshots for monitoring.
- Keep monitoring isolated from Redis consumption.
- Survive unexpected monitoring errors.

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
    | update_heartbeat()
    v
AgentRegistry
    |
    v
watchdog.py
    |
    | observation only
    v
supervisor.py
    |
    | recovery decision
    v
process restart

IMPORTANT
---------

This watchdog is OBSERVATION ONLY.

It does NOT:

- consume Redis
- publish Redis events
- modify AgentRegistry state
- mark agents DEAD
- restart processes
- terminate processes
- decide recovery policy

Recovery decisions belong to supervisor.py.

Fault isolation
---------------

A failure in one agent must never stop this watchdog.

A malformed registry entry must never prevent other agents
from being observed.

A registry snapshot failure must not permanently terminate
the watchdog loop.

A transient watchdog failure must trigger a bounded retry
rather than terminating the monitoring loop or creating a
CPU-burning tight loop.

Cancellation must be propagated so supervisors and asyncio
task managers can shut the watchdog down correctly.
"""

from __future__ import annotations

import asyncio
import logging
import os

from datetime import datetime, timezone
from typing import Any, Optional, Protocol

from backend.app.monitoring.agent_registry import (
    AgentRegistry,
    agent_registry,
)


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================


def _read_positive_float(
    env_name: str,
    default: str,
) -> float:
    """
    Read a positive floating-point configuration value.

    Raises
    ------
    ValueError
        If the configured value is invalid or <= 0.
    """

    raw_value = os.getenv(
        env_name,
        default,
    ).strip()

    try:
        value = float(raw_value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"{env_name} must be a valid number. "
            f"Received: {raw_value!r}"
        ) from error

    if value <= 0:
        raise ValueError(
            f"{env_name} must be greater than zero. "
            f"Received: {value}"
        )

    return value


HEARTBEAT_TIMEOUT = _read_positive_float(
    "HEARTBEAT_TIMEOUT",
    "30",
)

CHECK_INTERVAL = _read_positive_float(
    "WATCHDOG_CHECK_INTERVAL",
    "5",
)

# Retry delay after an unexpected watchdog failure.
#
# This must be shorter than the normal monitoring interval so
# that a transient failure does not create a long monitoring gap.
WATCHDOG_FAILURE_RETRY_DELAY = _read_positive_float(
    "WATCHDOG_FAILURE_RETRY_DELAY",
    "0.5",
)


# ============================================================
# REGISTRY CONTRACT
# ============================================================


class RegistryProtocol(Protocol):
    """
    Minimal interface required by the watchdog.
    """

    def get_all_agents(
        self,
    ) -> dict[str, dict[str, Any]]:
        ...


# ============================================================
# TIME
# ============================================================


def _utc_now() -> datetime:
    """
    Return the current timezone-aware UTC datetime.
    """

    return datetime.now(timezone.utc)


def _normalize_timestamp(
    timestamp: Any,
) -> Optional[datetime]:
    """
    Normalize a registry heartbeat timestamp.

    Rules
    -----

    None / invalid type
        -> None

    Naive datetime
        -> interpreted as UTC

    Timezone-aware datetime
        -> converted to UTC

    A malformed timestamp must never terminate the watchdog.
    """

    if timestamp is None:
        return None

    if not isinstance(
        timestamp,
        datetime,
    ):
        return None

    if timestamp.tzinfo is None:
        return timestamp.replace(
            tzinfo=timezone.utc,
        )

    return timestamp.astimezone(
        timezone.utc,
    )


# ============================================================
# HEALTH STATE
# ============================================================


def _health_state(
    *,
    status: str,
    heartbeat_age: Optional[float],
) -> str:
    """
    Calculate the watchdog observation state.

    Possible states
    ---------------

    STARTING
        Agent is registered but has not sent a heartbeat.

    HEALTHY
        Recent heartbeat exists.

    STALE
        Heartbeat is older than HEARTBEAT_TIMEOUT.

    UNKNOWN
        Registry data is malformed or inconsistent.

    DEAD
        Registry already reports DEAD.

    RECOVERING
        Registry reports that recovery is in progress.

    IMPORTANT
    ---------

    This function only calculates an observation.

    It does not mutate the registry.
    """

    if status == "DEAD":
        return "DEAD"

    if status == "RECOVERING":
        return "RECOVERING"

    if heartbeat_age is None:
        if status == "STARTING":
            return "STARTING"

        return "UNKNOWN"

    if heartbeat_age < 0:
        return "UNKNOWN"

    if heartbeat_age > HEARTBEAT_TIMEOUT:
        return "STALE"

    return "HEALTHY"


# ============================================================
# SINGLE AGENT OBSERVATION
# ============================================================


def _observe_agent(
    agent_id: str,
    agent: dict[str, Any],
    now: datetime,
) -> tuple[str, Optional[float]]:
    """
    Observe one registry entry.

    Returns
    -------

    tuple[str, Optional[float]]
        (
            health_state,
            heartbeat_age_seconds,
        )

    This function never mutates the registry.
    """

    del agent_id

    status = str(
        agent.get(
            "status",
            "UNKNOWN",
        )
    ).upper()

    last_heartbeat = _normalize_timestamp(
        agent.get(
            "last_heartbeat",
        )
    )

    if last_heartbeat is None:
        return (
            _health_state(
                status=status,
                heartbeat_age=None,
            ),
            None,
        )

    age = (
        now - last_heartbeat
    ).total_seconds()

    return (
        _health_state(
            status=status,
            heartbeat_age=age,
        ),
        age,
    )


# ============================================================
# SINGLE AGENT SNAPSHOT
# ============================================================


def _build_agent_observation(
    agent_id: str,
    agent: dict[str, Any],
    now: datetime,
) -> dict[str, Any]:
    """
    Build a detached observation dictionary for one agent.
    """

    status = str(
        agent.get(
            "status",
            "UNKNOWN",
        )
    ).upper()

    health, heartbeat_age = _observe_agent(
        agent_id,
        agent,
        now,
    )

    return {
        "agent_id": agent_id,
        "status": status,
        "health": health,
        "heartbeat_age": heartbeat_age,
        "instance_id": agent.get(
            "instance_id",
        ),
        "process_generation": agent.get(
            "process_generation",
        ),
        "hostname": agent.get(
            "hostname",
        ),
        "first_seen": agent.get(
            "first_seen",
        ),
        "last_heartbeat": agent.get(
            "last_heartbeat",
        ),
        "last_status_change": agent.get(
            "last_status_change",
        ),
        "failure_count": agent.get(
            "failure_count",
            0,
        ),
        "observed_at": now,
    }


# ============================================================
# WATCHDOG CHECK
# ============================================================


def check_agent_health(
    registry: RegistryProtocol | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Observe health of every registered agent.

    Observation only.

    This function does NOT:

    - consume Redis
    - publish Redis events
    - modify AgentRegistry
    - mark agents DEAD
    - restart processes
    - terminate processes
    - invoke supervisor recovery

    Fault isolation
    ---------------

    A malformed entry for one agent is isolated from all
    other agents.

    If obtaining the registry snapshot fails, an empty snapshot
    is returned so the watchdog loop can continue monitoring.
    """

    active_registry: RegistryProtocol = (
        registry
        if registry is not None
        else agent_registry
    )

    now = _utc_now()

    # --------------------------------------------------------
    # Registry-level fault isolation
    # --------------------------------------------------------

    try:
        agents = active_registry.get_all_agents()
    except Exception:
        logger.exception(
            "Watchdog failed to obtain AgentRegistry snapshot."
        )
        return {}

    if not isinstance(
        agents,
        dict,
    ):
        logger.error(
            "Watchdog received invalid registry snapshot "
            "type=%s",
            type(agents).__name__,
        )
        return {}

    snapshot: dict[
        str,
        dict[str, Any],
    ] = {}

    # --------------------------------------------------------
    # Per-agent fault isolation
    # --------------------------------------------------------

    for agent_id, agent in agents.items():
        try:
            if not isinstance(
                agent_id,
                str,
            ):
                raise TypeError(
                    "agent_id must be a string"
                )

            if not isinstance(
                agent,
                dict,
            ):
                raise TypeError(
                    "agent registry entry must be a dictionary"
                )

            snapshot[agent_id] = (
                _build_agent_observation(
                    agent_id,
                    agent,
                    now,
                )
            )

        except Exception as error:
            # One broken agent must never affect another agent.
            logger.exception(
                "Watchdog failed to observe agent %r.",
                agent_id,
            )

            instance_id = None
            hostname = None

            if isinstance(
                agent,
                dict,
            ):
                try:
                    instance_id = agent.get(
                        "instance_id"
                    )
                except Exception:
                    instance_id = None

                try:
                    hostname = agent.get(
                        "hostname"
                    )
                except Exception:
                    hostname = None

            snapshot[str(agent_id)] = {
                "agent_id": str(agent_id),
                "status": "UNKNOWN",
                "health": "UNKNOWN",
                "heartbeat_age": None,
                "instance_id": instance_id,
                "process_generation": None,
                "hostname": hostname,
                "observed_at": now,
                "error": (
                    f"{type(error).__name__}: "
                    f"{error}"
                ),
            }

    return snapshot


# ============================================================
# HEALTH LOGGING
# ============================================================


def _format_health_message(
    observation: dict[str, Any],
) -> str:
    """
    Format one health observation for logging.
    """

    agent_id = observation.get(
        "agent_id",
        "UNKNOWN",
    )

    status = observation.get(
        "status",
        "UNKNOWN",
    )

    health = observation.get(
        "health",
        "UNKNOWN",
    )

    instance_id = observation.get(
        "instance_id",
    )

    process_generation = observation.get(
        "process_generation",
    )

    hostname = observation.get(
        "hostname",
    )

    heartbeat_age = observation.get(
        "heartbeat_age",
    )

    if heartbeat_age is None:
        heartbeat_text = "missing"
    else:
        heartbeat_text = (
            f"{heartbeat_age:.1f}s"
        )

    if process_generation is None:
        generation_text = "unknown"
    else:
        generation_text = str(
            process_generation
        )

    return (
        "Agent health state changed | "
        f"agent_id={agent_id} | "
        f"status={status} | "
        f"health={health} | "
        f"heartbeat_age={heartbeat_text} | "
        f"instance_id={instance_id or 'unknown'} | "
        f"process_generation={generation_text} | "
        f"hostname={hostname or 'unknown'}"
    )


# ============================================================
# WATCHDOG LOOP
# ============================================================


async def watchdog_loop(
    registry: RegistryProtocol | None = None,
    check_interval: float | None = None,
) -> None:
    """
    Periodically observe agent health.

    Normal iteration
    ----------------

        check -> sleep(check_interval)

    Transient failure
    -----------------

        failure
            |
            v
        sleep(retry_delay)
            |
            v
        retry check
            |
            v
        normal cadence

    Recovery remains the responsibility of supervisor.py.

    Cancellation
    ------------

    asyncio.CancelledError is deliberately re-raised.
    """

    active_registry: RegistryProtocol = (
        registry
        if registry is not None
        else agent_registry
    )

    interval = (
        check_interval
        if check_interval is not None
        else CHECK_INTERVAL
    )

    if interval <= 0:
        raise ValueError(
            "check_interval must be greater than zero."
        )

    logger.info(
        "Agent health watchdog started | "
        "heartbeat_timeout=%ss | "
        "check_interval=%ss | "
        "failure_retry_delay=%ss | "
        "mode=observer-only",
        HEARTBEAT_TIMEOUT,
        interval,
        WATCHDOG_FAILURE_RETRY_DELAY,
    )

    # --------------------------------------------------------
    # Previous health state cache.
    #
    # Owned exclusively by watchdog.
    # AgentRegistry is never modified.
    # --------------------------------------------------------

    previous_states: dict[
        str,
        str,
    ] = {}

    while True:
        try:
            snapshot = check_agent_health(
                active_registry,
            )

            for agent_id, observation in snapshot.items():
                try:
                    current_state = str(
                        observation.get(
                            "health",
                            "UNKNOWN",
                        )
                    )

                    previous_state = (
                        previous_states.get(
                            agent_id,
                        )
                    )

                    # Log only transitions.
                    if previous_state != current_state:
                        logger.info(
                            _format_health_message(
                                observation
                            )
                        )

                    previous_states[
                        agent_id
                    ] = current_state

                except Exception:
                    # A logging/formatting problem for one agent
                    # must not terminate the monitoring loop.
                    logger.exception(
                        "Watchdog failed while processing "
                        "observation for agent %r.",
                        agent_id,
                    )

            # ------------------------------------------------
            # Remove disappeared agents from local cache.
            # ------------------------------------------------

            active_agent_ids = set(
                snapshot.keys()
            )

            stale_cache_ids = (
                set(previous_states.keys())
                - active_agent_ids
            )

            for agent_id in stale_cache_ids:
                previous_states.pop(
                    agent_id,
                    None,
                )

            # ------------------------------------------------
            # Normal monitoring cadence.
            # ------------------------------------------------

            await asyncio.sleep(
                interval,
            )

        except asyncio.CancelledError:
            logger.info(
                "Agent health watchdog shutdown requested."
            )
            raise

        except Exception:
            # ------------------------------------------------
            # Watchdog-level fault isolation.
            #
            # A transient failure must not terminate the loop.
            # Retry sooner than the normal monitoring interval,
            # but never faster than the configured retry delay.
            # ------------------------------------------------

            logger.exception(
                "Unexpected watchdog loop error; "
                "continuing monitoring."
            )

            retry_delay = min(
                WATCHDOG_FAILURE_RETRY_DELAY,
                interval,
            )

            try:
                await asyncio.sleep(
                    retry_delay,
                )
            except asyncio.CancelledError:
                logger.info(
                    "Agent health watchdog shutdown requested "
                    "during failure recovery."
                )
                raise


# ============================================================
# MAIN
# ============================================================


async def main() -> None:
    """
    Standalone watchdog entry point.
    """

    await watchdog_loop()


if __name__ == "__main__":
    asyncio.run(main())