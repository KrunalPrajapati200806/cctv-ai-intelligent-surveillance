from __future__ import annotations

from datetime import datetime, timezone

import pytest

from shared.schemas.event_registry import (
    is_registered_event_type,
    validate_event_data,
)
from shared.schemas.event_schema import create_event, validate_event


def test_vehicle_detected_is_registered() -> None:
    assert is_registered_event_type("vehicle.detected")


def test_vehicle_detected_accepts_live_vehicles_payload() -> None:
    data = validate_event_data(
        "vehicle.detected",
        {
            "frame_id": "1",
            "frame_timestamp": datetime.now(timezone.utc).isoformat(),
            "vehicle_count": 1,
            "count": 1,
            "vehicles": [
                {
                    "detection_id": "det-1",
                    "class_id": 2,
                    "class_name": "car",
                    "confidence": 0.9,
                    "bbox": [1.0, 2.0, 3.0, 4.0],
                }
            ],
            "model": "yolo.pt",
            "confidence_threshold": 0.4,
        },
    )

    assert len(data.detections) == 1
    assert data.detections[0].detection_id == "det-1"


def test_person_detected_rejects_wrong_payload() -> None:
    with pytest.raises(ValueError):
        validate_event(
            create_event(
                event_type="person.detected",
                agent_id="detection-01",
                instance_id="inst-1",
                hostname="host",
                camera_id="CAM01",
                data={"completely_wrong": True},
            ).to_dict()
        )


def test_unregistered_event_type_still_validates_envelope() -> None:
    event = validate_event(
        create_event(
            event_type="alert.created",
            agent_id="alert-01",
            instance_id="inst-1",
            hostname="host",
            camera_id="CAM01",
            data={"alert_type": "intrusion"},
        ).to_dict()
    )

    assert event.event_type == "alert.created"
