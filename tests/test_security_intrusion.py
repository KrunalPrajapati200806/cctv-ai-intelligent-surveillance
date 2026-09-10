import os
import asyncio
from unittest.mock import AsyncMock

CAMERAS_JSON = r'''
[
  {
    "camera_id": "CAM01",
    "name": "Entrance Camera",
    "source": "0",
    "enabled": true,
    "location": "entrance",
    "policy": {
      "normal_objects": ["person"],
      "restricted_objects": [],
      "alert_events": ["intrusion.detected"],
      "sensitivity": 0.7,
      "security_severity": "high",
      "restricted_zone": {
        "x1": 50,
        "y1": 50,
        "x2": 700,
        "y2": 450
      }
    }
  },
  {
    "camera_id": "CAM02",
    "name": "Bank Locker Camera",
    "source": "1",
    "enabled": true,
    "location": "bank-locker",
    "policy": {
      "normal_objects": [],
      "restricted_objects": ["person"],
      "alert_events": ["person.detected"],
      "sensitivity": 0.9,
      "security_severity": "critical",
      "restricted_zone": {
        "x1": 100,
        "y1": 100,
        "x2": 500,
        "y2": 400
      }
    }
  }
]
'''

os.environ["CAMERAS_JSON"] = CAMERAS_JSON

from agents.security.main import SecurityAgent


def make_event(camera_id, track_id, x, y, timestamp, frame_id):
    return {
        "event_id": f"event-{camera_id}-{frame_id}",
        "event_type": "person.tracked",
        "version": "1.0",
        "timestamp": timestamp,
        "source": {
            "agent_id": "tracker-01",
            "instance_id": "tracker-test",
            "hostname": "test-host",
        },
        "camera": {
            "camera_id": camera_id,
        },
        "context": {
            "mode": "live",
            "trace_id": f"trace-{camera_id}-{frame_id}",
            "correlation_id": f"corr-{camera_id}-{track_id}",
            "incident_id": None,
        },
        "data": {
            "tracks": [
                {
                    "track_id": str(track_id),
                    "center": [x, y],
                    "bbox": [x - 10, y - 10, x + 10, y + 10],
                }
            ],
            "frame_id": frame_id,
            "frame_timestamp": timestamp,
        },
    }


async def test_intrusion_lifecycle():
    agent = SecurityAgent(agent_id="security-test")

    # ---------------------------------------------------------
    # Replace publishing with a mock.
    # This lets us test SecurityAgent logic without Redis.
    # ---------------------------------------------------------

    agent.emit_intrusion_event = AsyncMock(
        return_value="test-intrusion-event"
    )

    # ---------------------------------------------------------
    # 1. CAM01 enters restricted zone.
    # ---------------------------------------------------------

    event1 = make_event(
        "CAM01",
        "track-1",
        100,
        100,
        "2026-09-04T10:00:00+00:00",
        1,
    )

    await agent.process_tracking_event(
        event1,
        "redis-1",
    )

    assert agent.emit_intrusion_event.await_count == 1

    print("PASS: first zone entry generated exactly one intrusion")

    # ---------------------------------------------------------
    # 2. Same person remains inside.
    # ---------------------------------------------------------

    event2 = make_event(
        "CAM01",
        "track-1",
        150,
        150,
        "2026-09-04T10:00:01+00:00",
        2,
    )

    await agent.process_tracking_event(
        event2,
        "redis-2",
    )

    assert agent.emit_intrusion_event.await_count == 1

    print("PASS: staying inside does not generate duplicate intrusion")

    # ---------------------------------------------------------
    # 3. Temporary tracker dropout.
    # ---------------------------------------------------------
    # Empty track list.
    # This must NOT immediately clear the alert.
    # ---------------------------------------------------------

    event3 = {
        "event_id": "event-CAM01-3",
        "event_type": "person.tracked",
        "version": "1.0",
        "timestamp": "2026-09-04T10:00:02+00:00",
        "source": {
            "agent_id": "tracker-01",
            "instance_id": "tracker-test",
            "hostname": "test-host",
        },
        "camera": {
            "camera_id": "CAM01",
        },
        "context": {
            "mode": "live",
            "trace_id": "trace-CAM01-3",
            "correlation_id": "corr-CAM01-track-1",
            "incident_id": None,
        },
        "data": {
            "tracks": [],
            "frame_id": 3,
            "frame_timestamp": "2026-09-04T10:00:02+00:00",
        },
    }

    await agent.process_tracking_event(
        event3,
        "redis-3",
    )

    assert agent.emit_intrusion_event.await_count == 1
    assert "track-1" in agent.alerted_tracks["CAM01"]

    print("PASS: temporary tracker dropout does not duplicate intrusion")

    # ---------------------------------------------------------
    # 4. Person appears again inside after short dropout.
    # ---------------------------------------------------------

    event4 = make_event(
        "CAM01",
        "track-1",
        160,
        160,
        "2026-09-04T10:00:03+00:00",
        4,
    )

    await agent.process_tracking_event(
        event4,
        "redis-4",
    )

    assert agent.emit_intrusion_event.await_count == 1

    print("PASS: recovered track does not generate duplicate intrusion")

    # ---------------------------------------------------------
    # 5. Person exits the restricted zone.
    # ---------------------------------------------------------

    event5 = make_event(
        "CAM01",
        "track-1",
        800,
        500,
        "2026-09-04T10:00:04+00:00",
        5,
    )

    await agent.process_tracking_event(
        event5,
        "redis-5",
    )

    assert (
        "CAM01" not in agent.alerted_tracks
        or "track-1" not in agent.alerted_tracks.get("CAM01", set())
    )

    print("PASS: leaving the zone clears the alerted track")

    # ---------------------------------------------------------
    # 6. Person re-enters.
    # ---------------------------------------------------------

    event6 = make_event(
        "CAM01",
        "track-1",
        200,
        200,
        "2026-09-04T10:00:05+00:00",
        6,
    )

    await agent.process_tracking_event(
        event6,
        "redis-6",
    )

    assert agent.emit_intrusion_event.await_count == 2

    print("PASS: re-entry generates a new intrusion")

    # ---------------------------------------------------------
    # 7. Out-of-order event.
    # ---------------------------------------------------------
    # This event is older than the latest event.
    # It must be ignored.
    # ---------------------------------------------------------

    event7 = make_event(
        "CAM01",
        "track-1",
        300,
        300,
        "2026-09-04T09:59:00+00:00",
        7,
    )

    await agent.process_tracking_event(
        event7,
        "redis-7",
    )

    assert agent.emit_intrusion_event.await_count == 2

    print("PASS: out-of-order event was ignored")

    # ---------------------------------------------------------
    # 8. CAM02 must have independent state.
    # ---------------------------------------------------------

    event8 = make_event(
        "CAM02",
        "track-1",
        200,
        200,
        "2026-09-04T10:00:00+00:00",
        8,
    )

    await agent.process_tracking_event(
        event8,
        "redis-8",
    )

    assert agent.emit_intrusion_event.await_count == 3

    assert "CAM02" in agent.alerted_tracks
    assert "track-1" in agent.alerted_tracks["CAM02"]

    print("PASS: CAM02 generated its own independent intrusion")

    # ---------------------------------------------------------
    # 9. CAM01 and CAM02 states remain isolated.
    # ---------------------------------------------------------

    assert "CAM01" in agent.alerted_tracks
    assert "CAM02" in agent.alerted_tracks

    assert "track-1" in agent.alerted_tracks["CAM01"]
    assert "track-1" in agent.alerted_tracks["CAM02"]

    print("PASS: CAM01/CAM02 alert state is isolated")

    # ---------------------------------------------------------
    # 10. Verify the actual emit calls.
    # ---------------------------------------------------------

    calls = agent.emit_intrusion_event.await_args_list

    assert len(calls) == 3

    cameras = [
        call.kwargs["tracking_event"]["camera"]["camera_id"]
        for call in calls
    ]

    assert cameras == [
        "CAM01",
        "CAM01",
        "CAM02",
    ]

    print("PASS: emitted intrusion events belong to correct cameras")

    print()
    print("=" * 70)
    print("SECURITY INTRUSION LIFECYCLE TEST PASSED")
    print("=" * 70)
    print("Intrusions emitted:", agent.emit_intrusion_event.await_count)
    print("Expected:", 3)
    print("CAM01 state:", agent.alerted_tracks.get("CAM01"))
    print("CAM02 state:", agent.alerted_tracks.get("CAM02"))
    print("=" * 70)


if __name__ == "__main__":
    try:
        asyncio.run(test_intrusion_lifecycle())
    finally:
        os.environ.pop("CAMERAS_JSON", None)
