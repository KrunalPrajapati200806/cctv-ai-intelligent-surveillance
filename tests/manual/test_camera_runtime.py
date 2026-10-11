import asyncio

from backend.app.cameras.runtime import camera_runtime_manager


async def main() -> None:
    print("\n=== START CAM01 ===")

    result = await camera_runtime_manager.start("CAM01")

    print("START RESULT:")
    print(result)

    print("\n=== STATE IMMEDIATELY ===")

    state = camera_runtime_manager.get_state("CAM01")
    print(state)

    print("\n=== RUNTIME HEALTH ===")

    print(
        "agents alive:",
        camera_runtime_manager._agents_are_alive("CAM01"),
    )

    print(
        "runtime running:",
        camera_runtime_manager._is_running("CAM01"),
    )

    print("\n=== WAIT 10 SECONDS ===")

    await asyncio.sleep(10)

    print("\n=== STATE AFTER 10 SECONDS ===")

    print(
        camera_runtime_manager.get_state("CAM01")
    )

    print("\n=== RUNTIME HEALTH AFTER 10 SECONDS ===")

    print(
        "agents alive:",
        camera_runtime_manager._agents_are_alive("CAM01"),
    )

    print(
        "runtime running:",
        camera_runtime_manager._is_running("CAM01"),
    )

    print("\n=== STOP CAM01 ===")

    result = await camera_runtime_manager.stop("CAM01")

    print("STOP RESULT:")
    print(result)

    print("\n=== FINAL STATE ===")

    print(
        camera_runtime_manager.get_state("CAM01")
    )


if __name__ == "__main__":
    asyncio.run(main())