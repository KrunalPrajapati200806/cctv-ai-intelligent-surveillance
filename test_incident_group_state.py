import asyncio
import redis.asyncio as redis


async def main():
    r = redis.Redis(
        host="localhost",
        port=6379,
        decode_responses=True,
    )

    try:
        groups = await r.xinfo_groups("events.alerts")

        for group in groups:
            if group["name"] == "incident-workers":
                print("INCIDENT GROUP")
                print("name:", group["name"])
                print("consumers:", group["consumers"])
                print("pending:", group["pending"])
                print("last-delivered-id:", group["last-delivered-id"])
                print("entries-read:", group.get("entries-read"))
                print("lag:", group.get("lag"))

    finally:
        await r.aclose()


asyncio.run(main())