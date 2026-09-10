import asyncio
import redis.asyncio as redis

IDS = [
    "1788688692972-0",
    "1788688693259-0",
    "1788688693596-0",
    "1788688693928-0",
    "1788688694248-0",
]

async def main():
    r = redis.Redis(
        host="localhost",
        port=6379,
        decode_responses=True,
    )

    for message_id in IDS:
        rows = await r.xrange(
            "events.alerts",
            min=message_id,
            max=message_id,
        )
        print("\nREDIS ID:", message_id)
        print(rows)

    await r.aclose()

asyncio.run(main())
