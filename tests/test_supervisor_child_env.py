import asyncio

from backend.app.monitoring.supervisor import AgentSupervisor


async def main():
    supervisor = AgentSupervisor()

    print("--- SUPERVISOR CONFIG ---")
    for agent in supervisor.agents.values():
        print(
            agent.agent_id,
            "| camera=", agent.camera_id,
            "| source=", agent.camera_source,
        )

    print("\n--- STARTING AGENTS ---")
    await supervisor.start_all()

    try:
        await asyncio.sleep(10)

        print("\n--- LIVE PROCESSES ---")
        for agent in supervisor.agents.values():
            pid = agent.process.pid if agent.process else None

            print(
                agent.agent_id,
                "| PID=", pid,
                "| camera=", agent.camera_id,
                "| source=", agent.camera_source,
                "| running=", agent.running,
            )

    finally:
        print("\n--- STOPPING AGENTS ---")
        await supervisor.stop_all()
        print("--- TEST COMPLETE ---")


if __name__ == "__main__":
    asyncio.run(main())
