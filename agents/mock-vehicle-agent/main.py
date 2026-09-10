import asyncio
import json
import os
import uuid
from datetime import datetime, timezone

import redis.asyncio as redis


REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

STREAM_NAME = "events.vehicle"
AGENT_ID = "mock-vehicle-detector-01"
CAMERA_ID = "CAM01"


async def main():
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        decode_responses=True,
    )

    print("Mock Vehicle Detection Agent started.")

    try:
        while True:
            event = {
                "event_id": str(uuid.uuid4()),
                "event_type": "vehicle.detected",
                "version": "1.0",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": {
                    "agent_id": AGENT_ID,
                },
                "camera": {
                    "camera_id": CAMERA_ID,
                },
                "data": {
                    "class": "car",
                    "confidence": 0.91,
                    "bbox": [300, 150, 600, 400],
                },
            }

            redis_id = await redis_client.xadd(
                STREAM_NAME,
                {"event": json.dumps(event)},
            )

            print(
                f"Published event: vehicle.detected | "
                f"Redis ID: {redis_id}"
            )

            await asyncio.sleep(5)

    finally:
        await redis_client.aclose()
        print("Mock Vehicle Detection Agent stopped.")


if __name__ == "__main__":
    asyncio.run(main())