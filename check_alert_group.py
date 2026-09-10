import asyncio
import redis.asyncio as redis

async def main():
    r = redis.Redis(host="localhost", port=6379, decode_responses=True)

    info = await r.xinfo_groups("events.alerts")

    for group in info:
        print(group)

    await r.aclose()

asyncio.run(main())
