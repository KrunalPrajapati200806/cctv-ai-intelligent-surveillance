import asyncio
from datetime import datetime, timezone

from backend.app.monitoring.agent_registry import AgentRegistry


# An agent is considered dead if no heartbeat is received
# within this many seconds.
HEARTBEAT_TIMEOUT_SECONDS = 15


async def watchdog_loop(
    registry: AgentRegistry,
    check_interval: int = 5,
):
    """
    Periodically checks all registered agents.

    If an agent has not sent a heartbeat within
    HEARTBEAT_TIMEOUT_SECONDS, mark it as dead.
    """

    print("Agent watchdog started.")

    while True:
        try:
            now = datetime.now(timezone.utc)

            agents = registry.get_all_agents()

            for agent_id, agent in agents.items():
                last_heartbeat = agent.get("last_heartbeat")

                if last_heartbeat is None:
                    continue

                elapsed = (now - last_heartbeat).total_seconds()

                if elapsed > HEARTBEAT_TIMEOUT_SECONDS:
                    if agent.get("status") != "dead":
                        registry.mark_dead(agent_id)

                        print(
                            f"⚠️ Agent marked DEAD: {agent_id} "
                            f"(last heartbeat {elapsed:.1f}s ago)"
                        )

            await asyncio.sleep(check_interval)

        except asyncio.CancelledError:
            print("Agent watchdog stopped.")
            raise

        except Exception as exc:
            # The watchdog itself should not crash the whole system.
            print(f"Watchdog error: {exc}")
            await asyncio.sleep(check_interval)