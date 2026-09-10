import asyncio
from backend.app.messaging.consumer import STREAM_NAME, EVIDENCE_STREAM_NAME
from backend.app.messaging.redis_client import redis_client

async def main():
    print("ALERT STREAM:", STREAM_NAME)
    print("ALERT GROUPS:", await redis_client.xinfo_groups(STREAM_NAME))
    print("EVIDENCE STREAM:", EVIDENCE_STREAM_NAME)
    print("EVIDENCE GROUPS:", await redis_client.xinfo_groups(EVIDENCE_STREAM_NAME))
    await redis_client.aclose()

asyncio.run(main())
