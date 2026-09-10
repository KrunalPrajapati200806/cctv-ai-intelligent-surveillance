from __future__ import annotations

from agents.evidence.main import _is_live_evidence_request
from shared.schemas.event_schema import create_event


def test_explicit_rolling_buffer_request_is_live() -> None:
    event = create_event(
        event_type="evidence.generate",
        agent_id="incident-01",
        instance_id="inst-1",
        hostname="host",
        camera_id="CAM01",
        data={
            "evidence_request": {
                "camera_id": "CAM01",
                "event_time": "2026-09-07T10:30:20Z",
                "pre_seconds": 10,
                "post_seconds": 10,
                "source_type": "rolling_buffer",
            }
        },
    )

    assert _is_live_evidence_request(event) is True
