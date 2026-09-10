import asyncio
import redis.asyncio as redis

from shared.schemas.event_schema import create_event


REDIS_HOST = "localhost"
REDIS_PORT = 6379
STREAM = "events.alerts"


async def main():
    client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=10,
    )

    try:
        event = create_event(
            event_type="alert.created",
            agent_id="alert-01",
            instance_id="test-instance",
            hostname="test-host",
            camera_id="CAM01",
            mode="live",
            data={
                "alert_type": "intrusion",
                "severity": "high",
                "track_ids": ["101"],
                "frame_id": 123,
                "frame_timestamp": "2026-09-04T06:30:00+00:00",
                "message": "Test intrusion detected",
            },
        )

        print("\n========== TEST EVENT ==========")
        print(event.to_json())

        redis_id = await client.xadd(
            STREAM,
            {
                "event": event.to_json(),
            },
        )

        print("\n========== PUBLISHED ==========")
        print(f"Stream   : {STREAM}")
        print(f"Redis ID : {redis_id}")
        print(f"Event ID : {event.event_id}")
        print("================================\n")

    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())