import asyncio
import os
import time

from backend.app.monitoring.supervisor import AgentSupervisor


async def main():
    supervisor = AgentSupervisor()

    print("\n" + "=" * 70)
    print("AUTOMATIC CAMERA FAILURE RECOVERY TEST")
    print("=" * 70)

    await supervisor.start_all()

    print("\n[TEST] Agents started.")
    print("[TEST] Waiting 60 seconds for CAM02 heartbeat failure + recovery...")
    print("[TEST] CAM01 must continue running during CAM02 recovery.\n")

    start = time.monotonic()

    while time.monotonic() - start < 60:
        print("\n[TEST] Current agent state:")

        for name, agent in supervisor.agents.items():
            process = agent.process
            pid = process.pid if process is not None else None

            print(
                f"  {name:30} "
                f"PID={pid} "
                f"running={agent.running} "
                f"generation={agent.process_generation}"
            )

        await asyncio.sleep(10)

    print("\n[TEST] 60-second observation complete.")

    await supervisor.stop_all()

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
