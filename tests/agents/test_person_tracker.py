import pytest

from shared.schemas.event_registry import validate_event_data
from agents.tracker.main import PersonTrackerAgent


def make_detection(detection_id, bbox, confidence=0.95):
    return {
        "detection_id": detection_id,
        "bbox": bbox,
        "confidence": confidence,
    }


def test_tracker_creates_new_track():
    agent = PersonTrackerAgent()

    tracks = agent.update_tracks(
        camera_id="camera-01",
        detections=[
            make_detection(
                "detection-001",
                [10, 20, 100, 200],
            )
        ],
        event_timestamp=agent_timestamp(),
    )

    assert len(tracks) == 1
    assert tracks[0]["detection_id"] == "detection-001"
    assert tracks[0]["track_id"].startswith("track-")


def test_tracker_reuses_track_for_nearby_detection():
    agent = PersonTrackerAgent()
    timestamp = agent_timestamp()

    first = agent.update_tracks(
        "camera-01",
        [make_detection("detection-001", [10, 20, 100, 200])],
        timestamp,
    )

    second = agent.update_tracks(
        "camera-01",
        [make_detection("detection-002", [12, 22, 102, 202])],
        timestamp,
    )

    assert first[0]["track_id"] == second[0]["track_id"]


def test_tracker_keeps_cameras_separate():
    agent = PersonTrackerAgent()
    timestamp = agent_timestamp()

    first = agent.update_tracks(
        "camera-01",
        [make_detection("detection-001", [10, 20, 100, 200])],
        timestamp,
    )

    second = agent.update_tracks(
        "camera-02",
        [make_detection("detection-002", [10, 20, 100, 200])],
        timestamp,
    )

    assert first[0]["track_id"] != second[0]["track_id"]


def test_tracked_payload_matches_canonical_contract():
    payload = {
        "frame_id": "frame-001",
        "tracks": [
            {
                "track_id": "track-test-001",
                "detection_id": "detection-test-001",
                "bbox": [10.0, 20.0, 100.0, 200.0],
                "confidence": 0.95,
                "center": [55.0, 110.0],
            }
        ],
    }

    result = validate_event_data("person.tracked", payload)

    assert result.frame_id == "frame-001"
    assert len(result.tracks) == 1


def agent_timestamp():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)