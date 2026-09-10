import asyncio
from backend.app.messaging.consumer import STREAM_NAME, GROUP_NAME
from backend.app.messaging.redis_client import redis_client

async def main():
    print("STREAM:", STREAM_NAME)
    print("GROUP:", GROUP_NAME)
    print("PENDING:")
    result = await redis_client.xpending_range(
        STREAM_NAME,
        GROUP_NAME,
        min="-",
        max="+",
        count=20,
    )
    for item in result:
        print(item)

    await redis_client.aclose()

asyncio.run(main())
