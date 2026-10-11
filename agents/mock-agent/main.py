import asyncio
import json
import os
import sys
import uuid

from datetime import datetime, timezone
from pathlib import Path

import redis.asyncio as redis


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# CONFIG
# ============================================================

REDIS_HOST = os.getenv(
    "REDIS_HOST",
    "localhost",
)

REDIS_PORT = int(
    os.getenv(
        "REDIS_PORT",
        "6379",
    )
)

STREAM_NAME = "events.detection"

AGENT_ID = "mock-person-detector-01"

CAMERA_ID = "CAM01"


# ============================================================
# SIMULATED PEOPLE
# ============================================================

PERSONS = [

    [100, 120, 200, 400],

    [300, 120, 400, 400],

    [500, 120, 600, 400],

]


# ============================================================
# CREATE PERSON DETECTION EVENT
# ============================================================

def create_event():

    frame_id = str(
        uuid.uuid4()
    )

    detections = []

    for bbox in PERSONS:

        detections.append(
            {
                "detection_id": str(
                    uuid.uuid4()
                ),

                "confidence": 0.94,

                "bbox": [
                    float(value)
                    for value in bbox
                ],
            }
        )

    return {

        "event_id": str(
            uuid.uuid4()
        ),

        "event_type":
            "person.detected",

        "version":
            "1.0",

        "timestamp":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "source": {

            "agent_id":
                AGENT_ID,
        },

        "camera": {

            "camera_id":
                CAMERA_ID,
        },

        "data": {

            "frame_id":
                frame_id,

            "detections":
                detections,
        },
    }


# ============================================================
# MAIN
# ============================================================

async def main():

    redis_client = redis.Redis(

        host=REDIS_HOST,

        port=REDIS_PORT,

        decode_responses=True,
    )

    print(
        "Mock Person Detection Agent started."
    )

    print(
        f"Simulating "
        f"{len(PERSONS)} people."
    )

    print(
        f"Stream: {STREAM_NAME}"
    )

    try:

        while True:

            event = create_event()

            redis_id = await redis_client.xadd(

                STREAM_NAME,

                {
                    "event":
                        json.dumps(
                            event
                        )
                },
            )

            print(
                f"Published person.detected | "
                f"Persons={len(PERSONS)} | "
                f"Redis={redis_id}"
            )

            await asyncio.sleep(1)

    finally:

        await redis_client.aclose()

        print(
            "Mock Person Detection Agent stopped."
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    asyncio.run(main())