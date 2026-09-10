import asyncio
import redis.asyncio as redis

async def main():
    r = redis.Redis(
        host="localhost",
        port=6379,
        decode_responses=True,
    )

    try:
        consumers = await r.xinfo_consumers(
            "events.alerts",
            "incident-workers",
        )
        print("INCIDENT CONSUMERS:")
        for consumer in consumers:
            print(consumer)
    finally:
        await r.aclose()

asyncio.run(main())
