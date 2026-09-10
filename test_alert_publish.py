import asyncio
import json
import uuid
from datetime import datetime, timezone

import redis.asyncio as redis

async def main():
    event_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    event = {
        "event_id": event_id,
        "event_type": "alert.created",
        "version": "1.0",
        "timestamp": now,
        "source": {
            "agent_id": "alert-01",
            "instance_id": "test-instance-01",
            "hostname": "test-host"
        },
        "camera": {
            "camera_id": "CAM01"
        },
        "context": {
            "mode": "live",
            "trace_id": str(uuid.uuid4()),
            "correlation_id": str(uuid.uuid4()),
            "incident_id": None
        },
        "data": {
            "alert_type": "intrusion.detected",
            "severity": "high",
            "person_count": 1,
            "threshold": 0,
            "frame_id": "test-frame-001",
            "frame_timestamp": now,
            "track_ids": ["track-test-001"],
            "message": "Vertical slice incident persistence test",
            "source_video": None
        }
    }

    r = redis.Redis(
        host="localhost",
        port=6379,
        decode_responses=True
    )

    message_id = await r.xadd(
        "events.alerts",
        {"data": json.dumps(event)}
    )

    print("REDIS ID:", message_id)
    print("EVENT ID:", event_id)

    await r.aclose()

asyncio.run(main())
