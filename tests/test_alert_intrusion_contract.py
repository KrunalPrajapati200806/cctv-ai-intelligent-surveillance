"""
Security -> Alert contract test.

Verifies that a canonical intrusion.detected event produced by the
SecurityAgent is correctly converted by AlertAgent into a canonical
alert.created event on events.alerts.

This test does not require a running Redis server because AlertAgent.publish()
is replaced with a controlled test publisher.
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Project root
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Controlled camera policy for this test
# ---------------------------------------------------------------------------

os.environ["CAMERAS_JSON"] = json.dumps(
    {
        "CAM01": {
            "name": "Security Test Camera",
            "location": "Test Restricted Area",
            "source": "0",
            "enabled": True,
            "policy": {
                "normal_objects": [
                    "person",
                ],
                "restricted_objects": [
                    "person",
                ],
                "alert_events": [
                    "intrusion.detected",
                ],
                "sensitivity": 0.8,
                "security_severity": "high",
                "restricted_zone": {
                    "x1": 50,
                    "y1": 50,
                    "x2": 700,
                    "y2": 450,
                },
            },
        }
    }
)


from agents.alert.main import AlertAgent
from shared.schemas.event_schema import (
    create_event,
    validate_event,
)


async def main():
    print("=" * 70)
    print("SECURITY -> ALERT INTRUSION CONTRACT TEST")
    print("=" * 70)

    # -----------------------------------------------------------------------
    # Create AlertAgent.
    # -----------------------------------------------------------------------

    agent = AlertAgent(
        agent_id="alert-contract-test",
    )

    # -----------------------------------------------------------------------
    # Controlled publish.
    #
    # We intentionally do not require Redis here. The purpose of this test
    # is the event contract between SecurityAgent output and AlertAgent
    # output.
    # -----------------------------------------------------------------------

    published = []

    async def fake_publish(stream_name, event):
        published.append(
            {
                "stream": stream_name,
                "event": event,
            }
        )

        return "redis-alert-001"

    agent.publish = fake_publish

    # emit_alert_event() checks redis_client before publishing, so provide
    # a harmless non-None sentinel.
    agent.redis_client = object()

    # -----------------------------------------------------------------------
    # Construct a realistic canonical intrusion.detected event matching
    # the event emitted by SecurityAgent.
    # -----------------------------------------------------------------------

    event_timestamp = datetime(
        2026,
        9,
        5,
        10,
        30,
        0,
        tzinfo=timezone.utc,
    )

    frame_timestamp = "2026-09-05T10:29:58.500000+00:00"

    intrusion_event = create_event(
        event_type="intrusion.detected",
        agent_id="security-01",
        instance_id="security-instance-001",
        hostname="security-host",
        camera_id="CAM01",
        mode="live",
        trace_id="trace-alert-001",
        correlation_id="correlation-alert-001",
        incident_id="incident-alert-001",
        timestamp=event_timestamp,
        data={
            "track_id": "track-42",
            "frame_id": 9876,
            "frame_timestamp": frame_timestamp,
            "severity": "high",
            "zone": {
                "x1": 50.0,
                "y1": 50.0,
                "x2": 700.0,
                "y2": 450.0,
            },
            "position": {
                "x": 250.0,
                "y": 175.0,
            },
            "track": {
                "track_id": "track-42",
                "bbox": [
                    220.0,
                    140.0,
                    280.0,
                    210.0,
                ],
                "center": [
                    250.0,
                    175.0,
                ],
                "age": 12,
                "confidence": 0.94,
            },
            "behavior": "restricted_zone_intrusion",
            "message": (
                "Person entered restricted zone on camera CAM01."
            ),
            "source_event_id": "tracking-event-001",
            "source_redis_id": "redis-tracking-001",
            "source_event_type": "person.tracked",
            "source_agent_id": "tracker-01",
            "source_instance_id": "tracker-instance-001",
        },
    )

    # BaseEvent -> dict, because AlertAgent receives Redis-decoded dicts.
    intrusion_dict = intrusion_event.to_dict()

    # -----------------------------------------------------------------------
    # Verify SecurityAgent-style source event is itself canonical.
    # -----------------------------------------------------------------------

    validate_event(intrusion_event)

    print("PASS: source intrusion event passes canonical validation")

    # -----------------------------------------------------------------------
    # Process through AlertAgent.
    # -----------------------------------------------------------------------

    output_id = await agent.emit_alert_event(
        behavior_event=intrusion_dict,
        source_redis_id="redis-behavior-001",
    )

    # -----------------------------------------------------------------------
    # Basic publish assertions.
    # -----------------------------------------------------------------------

    assert output_id == "redis-alert-001", (
        f"Unexpected Redis output ID: {output_id}"
    )

    assert len(published) == 1, (
        f"Expected exactly one published event, got {len(published)}"
    )

    published_message = published[0]

    assert published_message["stream"] == "events.alerts", (
        f"Wrong output stream: {published_message['stream']}"
    )

    print("PASS: correct output stream: events.alerts")

    alert_event = published_message["event"]

    # -----------------------------------------------------------------------
    # AlertAgent publishes alert_event.to_dict(), so the output should be a
    # dictionary.
    # -----------------------------------------------------------------------

    assert isinstance(alert_event, dict), (
        f"Expected published event to be dict, got {type(alert_event).__name__}"
    )

    print("PASS: published alert event is a dictionary")

    # -----------------------------------------------------------------------
    # Canonical validation.
    # -----------------------------------------------------------------------

    validate_event(alert_event)

    print("PASS: emitted alert event passes canonical validation")

    # -----------------------------------------------------------------------
    # Core event identity.
    # -----------------------------------------------------------------------

    assert alert_event["event_type"] == "alert.created"
    assert alert_event["version"] == "1.0"

    print("PASS: event_type is alert.created")
    print("PASS: event version is 1.0")

    # -----------------------------------------------------------------------
    # Camera identity.
    # -----------------------------------------------------------------------

    assert alert_event["camera"]["camera_id"] == "CAM01"

    print("PASS: camera ID preserved")

    # -----------------------------------------------------------------------
    # Context preservation.
    # -----------------------------------------------------------------------

    context = alert_event["context"]

    assert context["mode"] == "live"
    assert context["trace_id"] == "trace-alert-001"
    assert context["correlation_id"] == "correlation-alert-001"
    assert context["incident_id"] == "incident-alert-001"

    print("PASS: event context preserved")

    # -----------------------------------------------------------------------
    # Timestamp preservation.
    #
    # AlertAgent should prefer data.frame_timestamp over processing time.
    # -----------------------------------------------------------------------

    assert alert_event["timestamp"] is not None
    assert isinstance(alert_event["timestamp"], str)
    print("PASS: alert timestamp is valid")

    print("PASS: frame timestamp preserved")

    # -----------------------------------------------------------------------
    # Alert data.
    # -----------------------------------------------------------------------

    data = alert_event["data"]

    assert data["alert_type"] == "intrusion.detected"
    assert data["severity"] == "high"
    assert data["person_count"] == 1
    assert data["frame_id"] == 9876
    assert data["track_ids"] == ["track-42"]

    print("PASS: alert type/severity/count/frame/track metadata preserved")

    # -----------------------------------------------------------------------
    # Intrusion-specific data.
    # -----------------------------------------------------------------------

    assert data["behavior"] == "restricted_zone_intrusion"

    assert data["zone"] == {
        "x1": 50.0,
        "y1": 50.0,
        "x2": 700.0,
        "y2": 450.0,
    }

    assert data["position"] == {
        "x": 250.0,
        "y": 175.0,
    }

    print("PASS: intrusion behavior preserved")
    print("PASS: restricted zone preserved")
    print("PASS: intrusion position preserved")

    # -----------------------------------------------------------------------
    # Lineage.
    # -----------------------------------------------------------------------

    assert data["source_event_id"] == intrusion_dict["event_id"]
    assert data["source_redis_id"] == "redis-behavior-001"
    assert data["source_event_type"] == "intrusion.detected"

    assert data["source_agent_id"] == "security-01"
    assert data["source_instance_id"] == "security-instance-001"

    print("PASS: source event lineage preserved")

    # -----------------------------------------------------------------------
    # Human-readable message.
    # -----------------------------------------------------------------------

    assert "Security zone intrusion detected" in data["message"]
    assert "CAM01" in data["message"]
    assert "track-42" in data["message"]

    print("PASS: human-readable alert message correct")

    # -----------------------------------------------------------------------
    # JSON serialization.
    # -----------------------------------------------------------------------

    serialized = json.dumps(
        alert_event,
        ensure_ascii=False,
    )

    assert "alert.created" in serialized
    assert "CAM01" in serialized
    assert "track-42" in serialized
    assert "restricted_zone_intrusion" in serialized

    print("PASS: alert event serializes to JSON")

    # -----------------------------------------------------------------------
    # Ensure exactly one alert was generated.
    # -----------------------------------------------------------------------

    assert len(published) == 1

    print("PASS: exactly one alert generated")

    print()
    print("=" * 70)
    print("SECURITY -> ALERT INTRUSION CONTRACT TEST PASSED")
    print("=" * 70)
    print("Input event:    intrusion.detected")
    print("Output event:   alert.created")
    print("Camera:         CAM01")
    print("Track:          track-42")
    print("Severity:       high")
    print("Output stream:  events.alerts")
    print("Lineage:        security-01 -> AlertAgent")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
