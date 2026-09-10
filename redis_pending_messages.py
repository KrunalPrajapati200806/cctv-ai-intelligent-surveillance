import asyncio
from backend.app.messaging.consumer import STREAM_NAME, GROUP_NAME
from backend.app.messaging.redis_client import redis_client

async def main():
    ids = [
        "1788602468336-0",
        "1788603616882-0",
    ]

    for message_id in ids:
        print("\n" + "=" * 80)
        print("MESSAGE:", message_id)
        print("=" * 80)

        result = await redis_client.xrange(
            STREAM_NAME,
            min=message_id,
            max=message_id,
        )

        for item in result:
            print(item)

    await redis_client.aclose()

asyncio.run(main())
