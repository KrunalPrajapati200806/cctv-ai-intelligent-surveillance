import asyncio

from backend.app.monitoring.agent_registry import AgentRegistry
from backend.app.monitoring.watchdog import watchdog_loop


async def main():
    registry = AgentRegistry()

    agent_id = "watchdog-test-agent-01"

    # Simulate an agent sending its heartbeat.
    registry.update_heartbeat(agent_id)

    print("\nInitial agent state:")
    print(registry.get_agent(agent_id))

    # Run the watchdog in the background.
    watchdog_task = asyncio.create_task(
        watchdog_loop(
            registry,
            check_interval=5,
        )
    )

    try:
        # Wait long enough for the 15-second timeout.
        await asyncio.sleep(20)

        print("\nFinal agent state:")
        print(registry.get_agent(agent_id))

    finally:
        watchdog_task.cancel()

        try:
            await watchdog_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    asyncio.run(main())