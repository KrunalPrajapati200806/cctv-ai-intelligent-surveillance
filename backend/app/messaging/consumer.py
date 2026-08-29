import asyncio
import json

from app.messaging.redis_client import redis_client


STREAM_NAME = "events.detection"
GROUP_NAME = "detection-workers"
CONSUMER_NAME = "backend-consumer-01"


async def consume_events():

    print(
        f"Consumer started: {CONSUMER_NAME}"
    )

    while True:

        try:

            messages = await redis_client.xreadgroup(
                groupname=GROUP_NAME,
                consumername=CONSUMER_NAME,
                streams={
                    STREAM_NAME: ">"
                },
                count=5,
                block=5000
            )

            if not messages:
                continue

            for stream_name, entries in messages:

                for message_id, fields in entries:

                    if "event" not in fields:
                        continue

                    try:

                        event = json.loads(
                            fields["event"]
                        )

                        print(
                            "\nReceived event:"
                        )

                        print(
                            f"Redis ID: {message_id}"
                        )

                        print(
                            f"Type: {event['event_type']}"
                        )

                        print(
                            f"Agent: "
                            f"{event['source']['agent_id']}"
                        )

                        print(
                            f"Camera: "
                            f"{event['camera']['camera_id']}"
                        )

                        await redis_client.xack(
                            STREAM_NAME,
                            GROUP_NAME,
                            message_id
                        )

                        print(
                            f"ACK: {message_id}"
                        )

                    except (
                        json.JSONDecodeError,
                        KeyError,
                        TypeError
                    ) as error:

                        print(
                            f"Invalid event "
                            f"{message_id}: {error}"
                        )

        except Exception as error:

            print(
                f"Consumer error: {error}"
            )

            await asyncio.sleep(2)


if __name__ == "__main__":

    asyncio.run(
        consume_events()
    )