import asyncio
import json
import uuid
import sys
from datetime import datetime, timezone
from pathlib import Path

import redis.asyncio as redis


# Allow the agent to import the shared schema
PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from shared.schemas.event_schema import CCTVEvent


REDIS_HOST = "localhost"
REDIS_PORT = 6379

STREAM_NAME = "events.detection"

AGENT_ID = "mock-person-detector-01"
CAMERA_ID = "CAM01"


async def main():

    client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        decode_responses=True
    )

    print("Mock Person Detection Agent started.")

    try:

        while True:

            event = CCTVEvent(

                event_id=str(
                    uuid.uuid4()
                ),

                event_type="person.detected",

                version="1.0",

                timestamp=datetime.now(
                    timezone.utc
                ),

                source={
                    "agent_id": AGENT_ID
                },

                camera={
                    "camera_id": CAMERA_ID
                },

                data={

                    "class": "person",

                    "confidence": 0.94,

                    "bbox": [
                        100,
                        120,
                        200,
                        400
                    ]

                }
            )

            message_id = await client.xadd(

                STREAM_NAME,

                {
                    "event": event.model_dump_json()
                }

            )

            print(
                f"Published event: "
                f"{event.event_type} "
                f"| Redis ID: {message_id}"
            )

            await asyncio.sleep(5)

    finally:

        await client.aclose()


if __name__ == "__main__":

    asyncio.run(main())