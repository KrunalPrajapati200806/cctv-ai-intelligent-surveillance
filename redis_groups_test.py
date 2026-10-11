import asyncio
from backend.app.messaging.consumer import STREAM_NAME, EVIDENCE_STREAM_NAME
from backend.app.messaging.redis_client import redis_client
from redis.exceptions import ResponseError

async def main():
    try:
        print("ALERT STREAM:", STREAM_NAME)
        try:
            print("ALERT GROUPS:", await redis_client.xinfo_groups(STREAM_NAME))
        except ResponseError:
            print("ALERT GROUPS: stream does not exist")
        print("EVIDENCE STREAM:", EVIDENCE_STREAM_NAME)
        try:
            print("EVIDENCE GROUPS:", await redis_client.xinfo_groups(EVIDENCE_STREAM_NAME))
        except ResponseError:
            print("EVIDENCE GROUPS: stream does not exist")
    finally:
        await redis_client.aclose()

if __name__ == "__main__":
    asyncio.run(main())
