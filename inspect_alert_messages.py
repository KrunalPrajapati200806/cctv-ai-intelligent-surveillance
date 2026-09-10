import asyncio
import redis.asyncio as redis
import json

STREAM = "events.alerts"

IDS = [
    "1788602468336-0",
    "1788611313882-0",
    "1788628652735-0",
]

async def main():
    r = redis.Redis(
        host="localhost",
        port=6379,
        decode_responses=True,
    )

    try:
        for message_id in IDS:
            print("\n" + "=" * 80)
            print("MESSAGE:", message_id)

            result = await r.xrange(
                STREAM,
                min=message_id,
                max=message_id,
            )

            if not result:
                print("NOT FOUND")
                continue

            for redis_id, fields in result:
                print("REDIS ID:", redis_id)

                for key, value in fields.items():
                    if key == "data":
                        try:
                            data = json.loads(value)
                            print(
                                "DATA:",
                                json.dumps(
                                    data,
                                    indent=2,
                                    ensure_ascii=False,
                                ),
                            )
                        except Exception:
                            print("DATA:", value)
                    else:
                        print(f"{key}: {value}")

    finally:
        await r.aclose()

asyncio.run(main())
