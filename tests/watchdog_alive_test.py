import asyncio

from backend.app.monitoring.agent_registry import AgentRegistry
from backend.app.monitoring.watchdog import watchdog_loop


async def heartbeat_loop(registry, agent_id):
    """
    Simulates a healthy agent sending a heartbeat
    every 5 seconds.
    """

    while True:
        registry.update_heartbeat(agent_id)

        print(f"Heartbeat sent: {agent_id}")

        await asyncio.sleep(5)


async def main():
    registry = AgentRegistry()

    agent_id = "watchdog-alive-test-agent-01"

    # Start simulated agent heartbeat.
    heartbeat_task = asyncio.create_task(
        heartbeat_loop(registry, agent_id)
    )

    # Start watchdog.
    watchdog_task = asyncio.create_task(
        watchdog_loop(
            registry,
            check_interval=5,
        )
    )

    try:
        # Let both run for 20 seconds.
        await asyncio.sleep(20)

        agent = registry.get_agent(agent_id)

        print("\nFinal agent state:")
        print(agent)

        # Verify agent is still alive.
        assert agent["status"] == "alive"

        print("\n✅ Alive-agent watchdog test passed!")

    finally:
        heartbeat_task.cancel()
        watchdog_task.cancel()

        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass

        try:
            await watchdog_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    asyncio.run(main())