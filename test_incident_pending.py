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
        pending = await r.xpending_range(
            STREAM,
            GROUP,
            min="-",
            max="+",
            count=20,
        )

        print(f"PENDING SAMPLE: {len(pending)}")

        for item in pending:
            print(item)

    finally:
        await r.aclose()


asyncio.run(main())