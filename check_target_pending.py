import asyncio
import redis.asyncio as redis

TARGET = "1788684419947-0"

async def main():
    r = redis.Redis(
        host="localhost",
        port=6379,
        decode_responses=True
    )

    result = await r.xpending_range(
        "events.alerts",
        "incident-workers",
        min=TARGET,
        max=TARGET,
        count=10,
    )

    print("RESULT:")
    for item in result:
        print(item)

    await r.aclose()

asyncio.run(main())
