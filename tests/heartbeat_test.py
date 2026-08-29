import asyncio

import redis.asyncio as redis

from shared.heartbeat.heartbeat import heartbeat_loop


REDIS_HOST = "localhost"
REDIS_PORT = 6379

AGENT_ID = "heartbeat-test-agent-01"


async def main():
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        decode_responses=True,
        socket_timeout=None,
        health_check_interval=30,
    )

    print(f"Starting heartbeat test: {AGENT_ID}")

    try:
        await heartbeat_loop(
            redis_client=redis_client,
            agent_id=AGENT_ID,
            interval=5,
        )

    finally:
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())