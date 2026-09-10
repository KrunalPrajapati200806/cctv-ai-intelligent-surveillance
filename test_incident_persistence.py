import asyncio
import json
import redis.asyncio as redis

from backend.app.messaging.consumer import create_incident_sync

STREAM = "events.alerts"
MESSAGE_ID = "1788602468336-0"


async def main():
    r = redis.Redis(
        host="localhost",
        port=6379,
        decode_responses=True,
    )

    try:
        result = await r.xrange(
            STREAM,
            min=MESSAGE_ID,
            max=MESSAGE_ID,
        )

        if not result:
            print("MESSAGE NOT FOUND")
            return

        redis_id, fields = result[0]

        raw_event = fields.get("event")

        if not raw_event:
            print("NO 'event' FIELD")
            return

        event = json.loads(raw_event)

        print("REDIS ID:", redis_id)
        print("EVENT ID:", event.get("event_id"))
        print("EVENT TYPE:", event.get("event_type"))
        print("CAMERA:", event.get("camera", {}).get("camera_id"))

        print("\nCALLING create_incident_sync(event)...")

        result = await asyncio.to_thread(
            create_incident_sync,
            event,
        )

        print("\nSUCCESS")
        print("RESULT:")
        print(result)

    except Exception as exc:
        print("\nFAILED")
        print("EXCEPTION TYPE:", type(exc).__name__)
        print("EXCEPTION:", str(exc))
        raise

    finally:
        await r.aclose()


asyncio.run(main())
