import os
import asyncio

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
  }
]
'''

os.environ["CAMERAS_JSON"] = CAMERAS_JSON

from agents.security.main import SecurityAgent
from shared.schemas.event_schema import validate_event


def make_tracking_event():
    return {
        "event_id": "tracking-event-001",
        "event_type": "person.tracked",
        "version": "1.0",
        "timestamp": "2026-09-04T10:00:00+00:00",
        "source": {
            "agent_id": "tracker-01",
            "instance_id": "tracker-instance-01",
            "hostname": "test-host",
        },
        "camera": {
            "camera_id": "CAM01",
        },
        "context": {
            "mode": "live",
            "trace_id": "trace-001",
            "correlation_id": "correlation-001",
            "incident_id": "incident-001",
        },
        "data": {
            "tracks": [
                {
                    "track_id": "track-42",
                    "center": [200, 200],
                    "bbox": [180, 180, 220, 220],
                    "age": 15,
                    "confidence": 0.94,
                }
            ],
            "frame_id": 123,
            "frame_timestamp": "2026-09-04T10:00:00+00:00",
        },
    }


async def test_intrusion_event_contract():

    agent = SecurityAgent(
        agent_id="security-test"
    )

    published_events = []

    async def fake_publish(
        stream_name,
        event,
    ):
        published_events.append(
            (
                stream_name,
                event,
            )
        )
        return "redis-intrusion-001"

    agent.publish = fake_publish

    tracking_event = make_tracking_event()

    track = tracking_event["data"]["tracks"][0]

    redis_id = await agent.emit_intrusion_event(
        tracking_event=tracking_event,
        track=track,
        redis_source_id="redis-tracking-001",
    )

    assert redis_id == "redis-intrusion-001"

    assert len(published_events) == 1

    stream_name, event = published_events[0]

    print("Published stream:", stream_name)

    assert stream_name == "events.behavior"

    print("PASS: correct output stream")

    # ------------------------------------------------------------
    # Canonical event object
    # ------------------------------------------------------------

    assert validate_event(event)

    print("PASS: emitted event passes canonical validation")

    event_dict = event.to_dict()

    print("Event object type:", type(event).__name__)

    # ------------------------------------------------------------
    # Core event identity
    # ------------------------------------------------------------

    assert event_dict["event_type"] == "intrusion.detected"

    print("PASS: event_type is intrusion.detected")

    assert event_dict["version"] == "1.0"

    print("PASS: event version is valid")

    assert event_dict["camera"]["camera_id"] == "CAM01"

    print("PASS: camera ID preserved")

    # ------------------------------------------------------------
    # Context
    # ------------------------------------------------------------

    assert event_dict["context"]["mode"] == "live"

    assert event_dict["context"]["trace_id"] == "trace-001"

    assert (
        event_dict["context"]["correlation_id"]
        == "correlation-001"
    )

    assert (
        event_dict["context"]["incident_id"]
        == "incident-001"
    )

    print("PASS: event context preserved")

    # ------------------------------------------------------------
    # Tracking metadata
    # ------------------------------------------------------------

    data = event_dict["data"]

    assert data["track_id"] == "track-42"

    assert data["frame_id"] == 123

    assert (
        data["frame_timestamp"]
        == "2026-09-04T10:00:00+00:00"
    )

    print("PASS: tracking metadata preserved")

    # ------------------------------------------------------------
    # Camera policy
    # ------------------------------------------------------------

    assert data["severity"] == "high"

    print("PASS: camera-specific severity preserved")

    assert data["zone"] == {
        "x1": 50.0,
        "y1": 50.0,
        "x2": 700.0,
        "y2": 450.0,
    }

    print(
        "PASS: camera-specific restricted zone preserved"
    )

    # ------------------------------------------------------------
    # Position
    # ------------------------------------------------------------

    assert data["position"] == {
        "x": 200,
        "y": 200,
    }

    print("PASS: intrusion position preserved")

    # ------------------------------------------------------------
    # Track information
    # ------------------------------------------------------------

    assert data["track"]["track_id"] == "track-42"

    assert data["track"]["bbox"] == [
        180,
        180,
        220,
        220,
    ]

    assert data["track"]["center"] == [
        200,
        200,
    ]

    assert data["track"]["age"] == 15

    assert data["track"]["confidence"] == 0.94

    print("PASS: complete track data preserved")

    # ------------------------------------------------------------
    # Behavior
    # ------------------------------------------------------------

    assert (
        data["behavior"]
        == "restricted_zone_intrusion"
    )

    print(
        "PASS: behavior classification preserved"
    )

    # ------------------------------------------------------------
    # Lineage
    # ------------------------------------------------------------

    assert (
        data["source_event_id"]
        == "tracking-event-001"
    )

    assert (
        data["source_redis_id"]
        == "redis-tracking-001"
    )

    assert (
        data["source_event_type"]
        == "person.tracked"
    )

    assert (
        data["source_agent_id"]
        == "tracker-01"
    )

    assert (
        data["source_instance_id"]
        == "tracker-instance-01"
    )

    print("PASS: event lineage preserved")

    # ------------------------------------------------------------
    # Human-readable message
    # ------------------------------------------------------------

    assert (
        data["message"]
        == "Person entered restricted zone on camera CAM01."
    )

    print(
        "PASS: human-readable intrusion message correct"
    )

    # ------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------

    serialized = event.to_json()

    assert isinstance(serialized, str)

    assert "intrusion.detected" in serialized

    assert "CAM01" in serialized

    assert "track-42" in serialized

    print("PASS: canonical event serializes to JSON")

    print()
    print("=" * 70)
    print("INTRUSION EVENT CONTRACT TEST PASSED")
    print("=" * 70)
    print("Event type:", event_dict["event_type"])
    print("Camera:", event_dict["camera"]["camera_id"])
    print("Track:", data["track_id"])
    print("Severity:", data["severity"])
    print("Output stream:", stream_name)
    print("Source event:", data["source_event_id"])
    print("Serialized JSON: PASS")
    print("=" * 70)


if __name__ == "__main__":
    try:
        asyncio.run(
            test_intrusion_event_contract()
        )
    finally:
        os.environ.pop(
            "CAMERAS_JSON",
            None
        )
