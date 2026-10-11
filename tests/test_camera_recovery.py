"""
Manual/integration test for automatic camera-agent recovery.

This is intentionally NOT a unittest.TestCase module.

It starts the real AgentSupervisor, observes the agents for a bounded
period, and verifies through operator-visible output that one agent can
recover without stopping the others.

Run directly:

    py tests/test_camera_recovery.py

Optional environment variables:

    CAMERA_RECOVERY_TEST_DURATION=60
    CAMERA_RECOVERY_OBSERVATION_INTERVAL=10
"""

from __future__ import annotations

import asyncio
import os
import time

from backend.app.monitoring.supervisor import AgentSupervisor


def _read_positive_float(
    env_name: str,
    default: str,
) -> float:
    """Read a positive float from an environment variable."""
    raw_value = os.getenv(env_name, default).strip()

    try:
        value = float(raw_value)
    except ValueError as error:
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


RECOVERY_TEST_DURATION = _read_positive_float(
    "CAMERA_RECOVERY_TEST_DURATION",
    "60",
)

OBSERVATION_INTERVAL = _read_positive_float(
    "CAMERA_RECOVERY_OBSERVATION_INTERVAL",
    "10",
)


def _print_separator() -> None:
    """Print a consistent section separator."""
    print("\n" + "=" * 70)


def _print_agent_state(
    supervisor: AgentSupervisor,
) -> None:
    """
    Print the current supervisor state of every managed agent.

    This function is intentionally defensive: one malformed agent
    object must not prevent the remaining agents from being displayed.
    """
    print("\n[TEST] Current agent state:")

    try:
        agents = supervisor.agents
    except Exception as error:
        print(
            "[TEST][ERROR] Unable to read supervisor.agents: "
            f"{type(error).__name__}: {error}"
        )
        return

    if not isinstance(agents, dict):
        print(
            "[TEST][ERROR] supervisor.agents is not a dictionary: "
            f"{type(agents).__name__}"
        )
        return

    if not agents:
        print("  <no agents registered>")
        return

    for name, agent in agents.items():
        try:
            process = getattr(agent, "process", None)

            pid = (
                getattr(process, "pid", None)
                if process is not None
                else None
            )

            running = getattr(
                agent,
                "running",
                None,
            )

            generation = getattr(
                agent,
                "process_generation",
                None,
            )

            print(
                f"  {str(name):30} "
                f"PID={pid} "
                f"running={running} "
                f"generation={generation}"
            )

        except Exception as error:
            print(
                f"  {str(name):30} "
                f"<unable to inspect: "
                f"{type(error).__name__}: {error}>"
            )


async def _start_supervisor(
    supervisor: AgentSupervisor,
) -> None:
    """Start the supervisor with a clear operator-visible message."""
    print("[TEST] Starting AgentSupervisor...")

    try:
        await supervisor.start_all()
    except asyncio.CancelledError:
        raise
    except Exception as error:
        print(
            "[TEST][ERROR] Supervisor startup failed: "
            f"{type(error).__name__}: {error}"
        )
        raise

    print("[TEST] Agents started.")


async def _observe_recovery(
    supervisor: AgentSupervisor,
) -> None:
    """
    Observe all agents for the configured recovery-test duration.

    The test does not itself restart or terminate agents. Recovery remains
    the responsibility of AgentSupervisor/supervisor.py.
    """
    print(
        "[TEST] Waiting "
        f"{RECOVERY_TEST_DURATION:.1f} seconds "
        "for camera failure/recovery observation..."
    )

    print(
        "[TEST] CAM01 must continue running while CAM02 "
        "fails/recoveries are being observed."
    )

    start = time.monotonic()

    while True:
        elapsed = time.monotonic() - start

        if elapsed >= RECOVERY_TEST_DURATION:
            break

        _print_agent_state(supervisor)

        remaining = max(
            0.0,
            RECOVERY_TEST_DURATION - elapsed,
        )

        sleep_for = min(
            OBSERVATION_INTERVAL,
            remaining,
        )

        try:
            await asyncio.sleep(sleep_for)
        except asyncio.CancelledError:
            raise

    _print_separator()
    print("[TEST] Recovery observation window complete.")


async def _stop_supervisor(
    supervisor: AgentSupervisor,
) -> None:
    """Stop all supervisor-managed agents safely."""
    print("[TEST] Stopping AgentSupervisor...")

    try:
        await supervisor.stop_all()
    except asyncio.CancelledError:
        raise
    except Exception as error:
        print(
            "[TEST][ERROR] Supervisor shutdown failed: "
            f"{type(error).__name__}: {error}"
        )
        raise

    print("[TEST] Agents stopped.")


async def main() -> None:
    """
    Execute the manual camera recovery integration test.
    """
    _print_separator()

    print("AUTOMATIC CAMERA FAILURE RECOVERY TEST")

    _print_separator()

    print(
        "[TEST] Configuration:"
    )
    print(
        f"  duration={RECOVERY_TEST_DURATION:.1f}s"
    )
    print(
        f"  observation_interval={OBSERVATION_INTERVAL:.1f}s"
    )

    supervisor = AgentSupervisor()

    started = False

    try:
        await _start_supervisor(
            supervisor,
        )

        started = True

        _print_agent_state(
            supervisor,
        )

        await _observe_recovery(
            supervisor,
        )

    except asyncio.CancelledError:
        print(
            "\n[TEST] Cancellation requested."
        )
        raise

    except Exception as error:
        print(
            "\n[TEST][ERROR] Camera recovery test failed:"
        )
        print(
            f"  {type(error).__name__}: {error}"
        )
        raise

    finally:
        if started:
            try:
                await _stop_supervisor(
                    supervisor,
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                # The original test failure should not be hidden by a
                # secondary shutdown failure.
                print(
                    "[TEST][ERROR] "
                    "Supervisor shutdown encountered an error."
                )

    _print_separator()

    print("TEST COMPLETE")

    _print_separator()


if __name__ == "__main__":
    asyncio.run(main())










