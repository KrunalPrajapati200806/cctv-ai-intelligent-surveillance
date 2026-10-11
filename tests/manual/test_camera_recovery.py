


import asyncio

from backend.app.cameras.runtime import camera_runtime_manager


async def main() -> None:
    camera_id = "CAM01"

    print("\n=== START CAMERA ===")

    result = await camera_runtime_manager.start(
        camera_id
    )

    print("START RESULT:")
    print(result)

    pair = camera_runtime_manager.agents.get(
        camera_id
    )

    if pair is None:
        raise RuntimeError(
            "CAM01 worker generation was not created"
        )

    detector, tracker = pair

    detector_process = getattr(
        detector,
        "process",
        None,
    )

    tracker_process = getattr(
        tracker,
        "process",
        None,
    )

    print("\n=== INITIAL PROCESSES ===")

    print(
        "Detector PID:",
        getattr(
            detector_process,
            "pid",
            None,
        ),
    )

    print(
        "Tracker PID:",
        getattr(
            tracker_process,
            "pid",
            None,
        ),
    )

    print(
        "Runtime healthy:",
        camera_runtime_manager._is_running(
            camera_id
        ),
    )

    print("\n=== LET CAMERA RUN FOR 5 SECONDS ===")

    await asyncio.sleep(5)

    print(
        "Runtime healthy:",
        camera_runtime_manager._is_running(
            camera_id
        ),
    )

    print("\n=== STOP CAMERA ===")

    result = await camera_runtime_manager.stop(
        camera_id
    )

    print("STOP RESULT:")
    print(result)

    print(
        "Final state:",
        camera_runtime_manager.get_state(
            camera_id
        ),
    )


if __name__ == "__main__":
    asyncio.run(main())