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

        print("CONSUMERS WITH PENDING MESSAGES:")
        for c in consumers:
            if c["pending"] > 0:
                print(
                    f"name={c['name']} "
                    f"pending={c['pending']} "
                    f"idle={c['idle']}ms"
                )

                pending = await r.xpending_range(
                    STREAM,
                    GROUP,
                    min="-",
                    max="+",
                    count=10,
                    consumername=c["name"],
                )

                print("  SAMPLE PENDING:")
                for p in pending:
                    print(f"    {p}")

    finally:
        await r.aclose()

asyncio.run(main())
