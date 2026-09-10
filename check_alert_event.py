import asyncio
import redis.asyncio as redis

async def main():
    r = redis.Redis(host="localhost", port=6379, decode_responses=True)

    messages = await r.xrange("events.alerts", "-", "+", count=20)

    for msg_id, fields in messages:
        data = fields.get("data", "")
        if "0664d69d-7134-4b12-b7e2-42cd04ad8003" in data:
            print("FOUND MESSAGE")
            print("REDIS ID:", msg_id)
            print("DATA:", data)

    await r.aclose()

asyncio.run(main())
