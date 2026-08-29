import asyncio
import json

import redis.asyncio as redis

from backend.app.messaging.redis_client import redis_client
from backend.app.monitoring.agent_registry import AgentRegistry


STREAM_NAME = "events.system"
GROUP_NAME = "heartbeat-workers"
CONSUMER_NAME = "heartbeat-consumer-01"

registry = AgentRegistry()


async def ensure_consumer_group():
    try:
        await redis_client.xgroup_create(
            STREAM_NAME,
            GROUP_NAME,
            id="0",
            mkstream=True,
        )

        print(
            f"Created consumer group: {GROUP_NAME}"
        )

    except redis.ResponseError as error:
        if "BUSYGROUP" in str(error):
            print(
                f"Consumer group already exists: {GROUP_NAME}"
            )
        else:
            raise


async def consume_heartbeats():
    await ensure_consumer_group()

    print(
        f"Heartbeat consumer started: {CONSUMER_NAME}"
    )

    while True:
        try:
            messages = await redis_client.xreadgroup(
                groupname=GROUP_NAME,
                consumername=CONSUMER_NAME,
                streams={
                    STREAM_NAME: ">"
                },
                count=10,
                block=5000,
            )

            if not messages:
                continue

            for stream_name, stream_messages in messages:
                for message_id, fields in stream_messages:

                    try:
                        event_type = fields.get(
                            "event_type"
                        )

                        if event_type != "agent.heartbeat":
                            await redis_client.xack(
                                STREAM_NAME,
                                GROUP_NAME,
                                message_id,
                            )
                            continue

                        agent_id = fields.get(
                            "source_agent_id"
                        )

                        if not agent_id:
                            print(
                                f"Invalid heartbeat: "
                                f"{message_id}"
                            )

                            await redis_client.xack(
                                STREAM_NAME,
                                GROUP_NAME,
                                message_id,
                            )
                            continue

                        registry.update_heartbeat(
                            agent_id
                        )

                        print(
                            f"Heartbeat received: "
                            f"{agent_id}"
                        )

                        await redis_client.xack(
                            STREAM_NAME,
                            GROUP_NAME,
                            message_id,
                        )

                    except Exception as error:
                        print(
                            f"Heartbeat processing error "
                            f"for {message_id}: {error}"
                        )

        except asyncio.CancelledError:
            print(
                "Heartbeat consumer stopped."
            )
            raise

        except Exception as error:
            print(
                f"Heartbeat consumer error: {error}"
            )

            await asyncio.sleep(2)


async def main():
    try:
        await consume_heartbeats()

    finally:
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())