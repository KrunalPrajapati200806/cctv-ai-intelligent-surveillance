# # import asyncio
# # import uuid
# # import sys
# # from datetime import datetime, timezone
# # from pathlib import Path

# # import redis.asyncio as redis


# # # Allow the agent to import the shared schema
# # PROJECT_ROOT = Path(__file__).resolve().parents[2]

# # if str(PROJECT_ROOT) not in sys.path:
# #     sys.path.insert(0, str(PROJECT_ROOT))


# # from shared.schemas.event_schema import CCTVEvent


# # REDIS_HOST = "localhost"
# # REDIS_PORT = 6379

# # STREAM_NAME = "events.detection"

# # AGENT_ID = "mock-person-detector-01"
# # CAMERA_ID = "CAM01"


# # # Simulate 3 different people.
# # PERSONS = [
# #     [100, 120, 200, 400],
# #     [300, 120, 400, 400],
# #     [500, 120, 600, 400],
# # ]


# # async def main():

# #     client = redis.Redis(
# #         host=REDIS_HOST,
# #         port=REDIS_PORT,
# #         decode_responses=True,
# #     )

# #     print("Mock Person Detection Agent started.")
# #     print(f"Simulating {len(PERSONS)} people.")

# #     try:

# #         while True:

# #             for bbox in PERSONS:

# #                 event = CCTVEvent(

# #                     event_id=str(uuid.uuid4()),

# #                     event_type="person.detected",

# #                     version="1.0",

# #                     timestamp=datetime.now(
# #                         timezone.utc
# #                     ),

# #                     source={
# #                         "agent_id": AGENT_ID
# #                     },

# #                     camera={
# #                         "camera_id": CAMERA_ID
# #                     },

# #                     data={
# #                         "class": "person",
# #                         "confidence": 0.94,
# #                         "bbox": bbox,
# #                     }
# #                 )

# #                 message_id = await client.xadd(
# #                     STREAM_NAME,
# #                     {
# #                         "event": event.model_dump_json()
# #                     }
# #                 )

# #                 print(
# #                     f"Published person.detected "
# #                     f"| bbox={bbox} "
# #                     f"| Redis ID={message_id}"
# #                 )

# #                 await asyncio.sleep(1)

# #     finally:

# #         await client.aclose()


# # if __name__ == "__main__":

# #     asyncio.run(main())






# import asyncio
# import json
# import os
# import uuid
# from datetime import datetime, timezone

# import redis.asyncio as redis


# REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
# REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# STREAM_NAME = "events.detection"

# AGENT_ID = "mock-person-detector-01"
# CAMERA_ID = "CAM01"


# PERSONS = [
#     {
#         "detection_id": "person-1",
#         "bbox": [100, 120, 200, 400],
#         "confidence": 0.94,
#     },
#     {
#         "detection_id": "person-2",
#         "bbox": [300, 120, 400, 400],
#         "confidence": 0.93,
#     },
#     {
#         "detection_id": "person-3",
#         "bbox": [500, 120, 600, 400],
#         "confidence": 0.95,
#     },
# ]


# async def main():

#     redis_client = redis.Redis(
#         host=REDIS_HOST,
#         port=REDIS_PORT,
#         decode_responses=True,
#     )

#     print("Mock Person Detection Agent started.")
#     print(f"Simulating {len(PERSONS)} people.")

#     try:

#         while True:

#             frame_id = str(uuid.uuid4())

#             detections = []

#             for person in PERSONS:

#                 detections.append(
#                     {
#                         "detection_id": str(uuid.uuid4()),
#                         "confidence": person["confidence"],
#                         "bbox": person["bbox"],
#                     }
#                 )

#             event = {
#                 "event_id": str(uuid.uuid4()),
#                 "event_type": "person.detected",
#                 "version": "1.0",
#                 "timestamp": datetime.now(
#                     timezone.utc
#                 ).isoformat(),
#                 "source": {
#                     "agent_id": AGENT_ID,
#                 },
#                 "camera": {
#                     "camera_id": CAMERA_ID,
#                 },
#                 "data": {
#                     "frame_id": frame_id,
#                     "detections": detections,
#                 },
#             }

#             redis_id = await redis_client.xadd(
#                 STREAM_NAME,
#                 {
#                     "event": json.dumps(event)
#                 },
#             )

#             print(
#                 f"Published person.detected | "
#                 f"Persons={len(detections)} | "
#                 f"Redis ID={redis_id}"
#             )

#             await asyncio.sleep(1)

#     finally:

#         await redis_client.aclose()

#         print(
#             "Mock Person Detection Agent stopped."
#         )


# if __name__ == "__main__":
#     asyncio.run(main())









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