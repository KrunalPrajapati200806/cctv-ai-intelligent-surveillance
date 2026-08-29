import json

from app.messaging.redis_client import redis_client


STREAM_NAME = "events.detection"


async def get_events(
    last_id: str = "0-0",
    count: int = 10
):
    messages = await redis_client.xrange(
        STREAM_NAME,
        min=last_id,
        count=count
    )

    events = []

    for message_id, fields in messages:

        if "event" not in fields:
            continue

        try:
            event = json.loads(fields["event"])

            events.append(
                {
                    "redis_id": message_id,
                    "event": event
                }
            )

        except json.JSONDecodeError:
            continue

    return events