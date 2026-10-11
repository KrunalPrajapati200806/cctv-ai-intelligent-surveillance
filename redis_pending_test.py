import asyncio
from backend.app.messaging.consumer import STREAM_NAME, GROUP_NAME
from backend.app.messaging.redis_client import redis_client
from redis.exceptions import ResponseError

async def main():
    try:
        print("STREAM:", STREAM_NAME)
        print("GROUP:", GROUP_NAME)
        print("PENDING:")
        try:
            result = await redis_client.xpending_range(
                STREAM_NAME,
                GROUP_NAME,
                min="-",
                max="+",
                count=20,
            )
        except ResponseError:
            result = []
            print("No stream or consumer group exists.")
        for item in result:
            print(item)
    finally:
        await redis_client.aclose()

if __name__ == "__main__":
    asyncio.run(main())
