import asyncio
import redis.asyncio as redis


STREAM = "events.alerts"
GROUP = "incident-workers"


async def main():
    r = redis.Redis(
        host="localhost",
        port=6379,
        decode_responses=True,
    )

    try:
        consumers = await r.xinfo_consumers(STREAM, GROUP)

        print(f"TOTAL CONSUMERS: {len(consumers)}")
        print()

        consumers = sorted(
            consumers,
            key=lambda x: x.get("pending", 0),
            reverse=True,
        )

        for consumer in consumers:
            print(
                f"NAME={consumer['name']} | "
                f"PENDING={consumer['pending']} | "
                f"IDLE_MS={consumer['idle']}"
            )

    finally:
        await r.aclose()


asyncio.run(main())