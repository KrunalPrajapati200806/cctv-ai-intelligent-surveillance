import asyncio
from datetime import datetime, timezone
import uuid

import redis.asyncio as redis


async def send_heartbeat(
    redis_client: redis.Redis,
    agent_id: str,
):
    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "agent.heartbeat",
        "version": "1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_agent_id": agent_id,
        "status": "alive",
    }

    await redis_client.xadd(
        "events.system",
        event,
    )


async def heartbeat_loop(
    redis_client: redis.Redis,
    agent_id: str,
    interval: int = 10,
):
    while True:
        try:
            await send_heartbeat(
                redis_client,
                agent_id,
            )

            print(
                f"Heartbeat sent: {agent_id}"
            )

            await asyncio.sleep(interval)

        except asyncio.CancelledError:
            print(
                f"Heartbeat stopped: {agent_id}"
            )
            raise

        except Exception as error:
            print(
                f"Heartbeat error for {agent_id}: {error}"
            )

            await asyncio.sleep(interval)