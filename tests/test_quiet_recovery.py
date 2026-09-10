import asyncio
import os
import time

from backend.app.monitoring.monitoring_service import MonitoringService


async def main():
    service = MonitoringService()

    print("\n" + "=" * 70)
    print("QUIET CAMERA WORKER RECOVERY TEST")
    print("=" * 70)

    await service.start()

    print("\n[TEST] Monitoring service started.")
    print("[TEST] Waiting up to 75 seconds...")
    print("[TEST] Target: person-detector-CAM02")
    print("[TEST] CAM01 must remain healthy.\n")

    target = "person-detector-CAM02"
    start = time.monotonic()
    last_generation = {}

    while time.monotonic() - start < 75:
        agent = service.supervisor.agents.get(target)

        if agent is not None:
            generation = agent.process_generation
            running = agent.running

            if target not in last_generation:
                last_generation[target] = generation
                print(
                    f"[TEST] {target}: "
                    f"generation={generation}, running={running}"
                )

            elif generation != last_generation[target]:
                print(
                    f"\n[TEST] >>> RECOVERY DETECTED <<<"
                )
                print(
                    f"[TEST] {target}: "
                    f"generation {last_generation[target]} "
                    f"-> {generation}"
                )
                print(
                    f"[TEST] running={running}\n"
                )
                last_generation[target] = generation

        # Check CAM01 independently.
        cam01 = service.supervisor.agents.get(
            "person-detector-CAM01"
        )

        if cam01 is not None and not cam01.running:
            print(
                "\n[TEST] !!! FAILURE: CAM01 STOPPED !!!"
            )

        await asyncio.sleep(2)

    print("\n" + "=" * 70)
    print("FINAL AGENT STATE")
    print("=" * 70)

    for name, agent in service.supervisor.agents.items():
        process = agent.process
        pid = process.pid if process is not None else None

        print(
            f"{name:30} "
            f"PID={pid} "
            f"running={agent.running} "
            f"generation={agent.process_generation}"
        )

    target_agent = service.supervisor.agents.get(target)
    cam01_agent = service.supervisor.agents.get(
        "person-detector-CAM01"
    )

    print("\n" + "=" * 70)

    if (
        target_agent is not None
        and target_agent.process_generation >= 2
        and cam01_agent is not None
        and cam01_agent.running
    ):
        print("RESULT: PASS")
        print("CAM02 automatically recovered.")
        print("CAM01 remained running.")
    else:
        print("RESULT: CHECK REQUIRED")
        print(
            "CAM02 did not reach generation 2 "
            "or CAM01 stopped."
        )

    print("=" * 70)

    await service.stop()


if __name__ == "__main__":
    asyncio.run(main())