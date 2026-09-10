"""
Contract test:

alert.created -> Incident DB

Validates:

1. alert.created is accepted
2. incident is inserted
3. camera_id preserved
4. incident_id generated
5. severity preserved
6. track_ids preserved
7. frame timestamp preserved
8. live/historical mode preserved
9. duplicate alert creates only one incident
10. malformed event is isolated
11. DB failure does NOT ACK
12. successful processing DOES ACK
"""

from __future__ import annotations

import asyncio
import importlib
import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

from shared.schemas.event_schema import create_event, validate_event


# ============================================================
# ADD BACKEND TO PYTHON IMPORT PATH
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


# ============================================================
# LOAD THE REAL INCIDENT EVENT CONSUMER
# ============================================================

event_consumer = importlib.import_module(
    "app.messaging.consumer"
)

# ============================================================
# SAFETY CHECK
# ============================================================

if not hasattr(event_consumer, "DATABASE_PATH"):
    raise RuntimeError(
        "The imported app.messaging.consumer module does not "
        "contain DATABASE_PATH. "
        f"Imported module: "
        f"{getattr(event_consumer, '__file__', None)}"
    )

if not hasattr(event_consumer, "get_database_connection"):
    raise RuntimeError(
        "The imported app.messaging.consumer module does not "
        "contain get_database_connection(). "
        f"Imported module: "
        f"{getattr(event_consumer, '__file__', None)}"
    )

if not hasattr(event_consumer, "ensure_incidents_table"):
    raise RuntimeError(
        "The imported app.messaging.consumer module does not "
        "contain ensure_incidents_table(). "
        f"Imported module: "
        f"{getattr(event_consumer, '__file__', None)}"
    )

if not hasattr(event_consumer, "process_event"):
    raise RuntimeError(
        "The imported app.messaging.consumer module does not "
        "contain process_event(). "
        f"Imported module: "
        f"{getattr(event_consumer, '__file__', None)}"
    )

if not hasattr(event_consumer, "acknowledge"):
    raise RuntimeError(
        "The imported app.messaging.consumer module does not "
        "contain acknowledge(). "
        f"Imported module: "
        f"{getattr(event_consumer, '__file__', None)}"
    )


# ============================================================
# TEST DATABASE HELPERS
# ============================================================

def create_test_database() -> tuple[
    tempfile.TemporaryDirectory,
    Path,
    object,
]:
    """
    Create an isolated temporary SQLite database and redirect
    the incident consumer to it.

    Returns:
        temp_dir
        db_path
        old_database_path
    """

    temp_dir = tempfile.TemporaryDirectory()

    db_path = Path(temp_dir.name) / "incidents.db"

    old_database_path = event_consumer.DATABASE_PATH

    event_consumer.DATABASE_PATH = db_path

    # Initialize the exact same production schema used by
    # the incident consumer.
    event_consumer.ensure_incidents_table()

    return (
        temp_dir,
        db_path,
        old_database_path,
    )


def restore_database_path(old_database_path) -> None:
    """
    Restore the production database path.
    """

    event_consumer.DATABASE_PATH = old_database_path


def read_incidents(db_path: Path) -> list[dict]:
    """
    Read all incidents from the test database.
    """

    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row

    try:
        rows = connection.execute(
            """
            SELECT *
            FROM incidents
            ORDER BY rowid
            """
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        connection.close()


# ============================================================
# ACK MOCK HELPER
# ============================================================

def make_ack_mock():
    """
    Replace acknowledge() with an AsyncMock so the contract test
    never requires a running Redis server.

    Returns:
        ack_mock
        original_acknowledge
    """

    ack_mock = AsyncMock()

    original_acknowledge = event_consumer.acknowledge

    async def fake_acknowledge(*args, **kwargs):
        await ack_mock(*args, **kwargs)

    event_consumer.acknowledge = fake_acknowledge

    return (
        ack_mock,
        original_acknowledge,
    )


def restore_acknowledge(original_acknowledge) -> None:
    """
    Restore production acknowledge().
    """

    event_consumer.acknowledge = original_acknowledge


# ============================================================
# BUILD CANONICAL ALERT EVENT
# ============================================================

def build_alert_event(
    *,
    event_id: str = "alert-event-001",
    camera_id: str = "CAM01",
    mode: str = "live",
    severity: str = "high",
    track_ids: list[str] | None = None,
):
    """
    Build a canonical alert.created event.
    """

    if track_ids is None:
        track_ids = ["track-42"]

    event = create_event(
        event_type="alert.created",
        agent_id="alert-01",
        instance_id="alert-instance-01",
        hostname="test-host",
        camera_id=camera_id,
        mode=mode,
        trace_id="trace-001",
        correlation_id="correlation-001",
        incident_id=None,
        timestamp="2026-09-04T10:00:05+00:00",
        data={
            "alert_type": "intrusion.detected",
            "severity": severity,
            "person_count": 1,
            "threshold": 1,
            "frame_id": 1234,
            "frame_timestamp": "2026-09-04T10:00:04+00:00",
            "track_ids": track_ids,
            "message": (
                f"Person entered restricted zone "
                f"on camera {camera_id}."
            ),
            "behavior": "restricted_zone_intrusion",
            "source_event_id": "intrusion-event-001",
            "source_redis_id": "redis-intrusion-001",
            "source_event_type": "intrusion.detected",
            "source_agent_id": "security-01",
            "source_instance_id": "security-instance-01",
            "zone": {
                "x1": 50.0,
                "y1": 50.0,
                "x2": 700.0,
                "y2": 450.0,
            },
            "position": {
                "x": 100.0,
                "y": 100.0,
            },
        },
    )

    # Pydantic models should not be mutated directly.
    # Create a new canonical event with the requested event_id.
    event = event.model_copy(
        update={
            "event_id": event_id,
        }
    )

    assert validate_event(event)

    return event


def redis_fields_from_event(event) -> dict:
    """
    process_event() expects Redis-style fields.
    """

    return {
        "event": event.to_json(),
    }


# ============================================================
# TEST 1
# ============================================================

def test_successful_alert_creates_incident():
    print(
        "\n[TEST 1] Successful alert.created -> incident insertion"
    )

    temp_dir, db_path, old_database_path = (
        create_test_database()
    )

    ack_mock, original_acknowledge = make_ack_mock()

    try:
        event = build_alert_event(
            event_id="alert-success-001",
            camera_id="CAM01",
            mode="live",
            severity="high",
            track_ids=["track-42"],
        )

        redis_id = "1710000000000-0"

        asyncio.run(
            event_consumer.process_event(
                redis_id,
                redis_fields_from_event(event),
            )
        )

        incidents = read_incidents(db_path)

        assert len(incidents) == 1

        incident = incidents[0]

        assert incident["incident_id"]

        assert (
            incident["alert_event_id"]
            == "alert-success-001"
        )

        assert (
            incident["event_id"]
            == "alert-success-001"
        )

        assert incident["camera_id"] == "CAM01"

        assert incident["severity"] == "high"

        ack_mock.assert_awaited_once()

        print(
            "PASS: alert.created inserted exactly one incident"
        )
        print("PASS: incident_id generated")
        print("PASS: alert_event_id preserved")
        print("PASS: camera_id preserved")
        print("PASS: severity preserved")
        print("PASS: successful event ACKed")

    finally:
        restore_acknowledge(original_acknowledge)
        restore_database_path(old_database_path)
        temp_dir.cleanup()


# ============================================================
# TEST 2
# ============================================================

def test_metadata_preservation():
    print(
        "\n[TEST 2] Incident metadata preservation"
    )

    temp_dir, db_path, old_database_path = (
        create_test_database()
    )

    ack_mock, original_acknowledge = make_ack_mock()

    try:
        event = build_alert_event(
            event_id="alert-metadata-001",
            camera_id="CAM02",
            mode="historical",
            severity="critical",
            track_ids=[
                "track-10",
                "track-20",
            ],
        )

        asyncio.run(
            event_consumer.process_event(
                "1710000000001-0",
                redis_fields_from_event(event),
            )
        )

        incidents = read_incidents(db_path)

        assert len(incidents) == 1

        incident = incidents[0]

        assert incident["camera_id"] == "CAM02"

        assert incident["severity"] == "critical"

        assert incident["mode"] == "historical"

        assert incident["frame_id"] == "1234"

        assert (
            incident["frame_timestamp"]
            == "2026-09-04T10:00:04+00:00"
        )

        track_ids = json.loads(
            incident["track_ids"]
        )

        assert track_ids == [
            "track-10",
            "track-20",
        ]

        assert (
            incident["alert_type"]
            == "intrusion.detected"
        )

        assert (
            incident["trace_id"]
            == "trace-001"
        )

        assert (
            incident["correlation_id"]
            == "correlation-001"
        )

        assert (
            incident["source_agent_id"]
            == "alert-01"
        )

        assert (
            incident["source_instance_id"]
            == "alert-instance-01"
        )

        ack_mock.assert_awaited_once()

        print("PASS: camera_id preserved")
        print("PASS: severity preserved")
        print("PASS: historical mode preserved")
        print("PASS: frame_id preserved")
        print("PASS: frame_timestamp preserved")
        print("PASS: track_ids preserved")
        print("PASS: alert_type preserved")
        print("PASS: trace_id preserved")
        print("PASS: correlation_id preserved")
        print("PASS: source lineage preserved")

    finally:
        restore_acknowledge(original_acknowledge)
        restore_database_path(old_database_path)
        temp_dir.cleanup()


# ============================================================
# TEST 3
# ============================================================

def test_live_mode_preserved():
    print(
        "\n[TEST 3] Live mode preservation"
    )

    temp_dir, db_path, old_database_path = (
        create_test_database()
    )

    ack_mock, original_acknowledge = make_ack_mock()

    try:
        event = build_alert_event(
            event_id="alert-live-001",
            camera_id="CAM01",
            mode="live",
        )

        asyncio.run(
            event_consumer.process_event(
                "1710000000002-0",
                redis_fields_from_event(event),
            )
        )

        incidents = read_incidents(db_path)

        assert len(incidents) == 1

        assert incidents[0]["mode"] == "live"

        ack_mock.assert_awaited_once()

        print("PASS: live mode preserved")

    finally:
        restore_acknowledge(original_acknowledge)
        restore_database_path(old_database_path)
        temp_dir.cleanup()


# ============================================================
# TEST 4
# ============================================================

def test_duplicate_alert_creates_only_one_incident():
    print(
        "\n[TEST 4] Duplicate alert protection"
    )

    temp_dir, db_path, old_database_path = (
        create_test_database()
    )

    ack_mock, original_acknowledge = make_ack_mock()

    try:
        event = build_alert_event(
            event_id="alert-duplicate-001",
            camera_id="CAM01",
        )

        fields = redis_fields_from_event(event)

        asyncio.run(
            event_consumer.process_event(
                "1710000000003-0",
                fields,
            )
        )

        asyncio.run(
            event_consumer.process_event(
                "1710000000004-0",
                fields,
            )
        )

        incidents = read_incidents(db_path)

        assert len(incidents) == 1

        assert (
            incidents[0]["alert_event_id"]
            == "alert-duplicate-001"
        )

        assert ack_mock.await_count == 2

        print(
            "PASS: duplicate alert created only one incident"
        )

        print(
            "PASS: both successfully processed messages ACKed"
        )

    finally:
        restore_acknowledge(original_acknowledge)
        restore_database_path(old_database_path)
        temp_dir.cleanup()


# ============================================================
# TEST 5
# ============================================================

def test_malformed_event_is_isolated():
    print(
        "\n[TEST 5] Malformed event isolation"
    )

    temp_dir, db_path, old_database_path = (
        create_test_database()
    )

    ack_mock, original_acknowledge = make_ack_mock()

    try:
        malformed_fields = {
            "event": "{this-is-not-valid-json"
        }

        result = asyncio.run(
            event_consumer.process_event(
                "1710000000005-0",
                malformed_fields,
            )
        )

        incidents = read_incidents(db_path)

        assert len(incidents) == 0

        # Poison messages are permanently discarded by the
        # production consumer, therefore they should be ACKed.
        assert result is None

        ack_mock.assert_awaited_once()

        print(
            "PASS: malformed event did not crash consumer"
        )

        print(
            "PASS: malformed event created no incident"
        )

        print(
            "PASS: malformed poison message was ACKed"
        )

    finally:
        restore_acknowledge(original_acknowledge)
        restore_database_path(old_database_path)
        temp_dir.cleanup()


# ============================================================
# TEST 6
# ============================================================

def test_unsupported_event_is_ignored():
    print(
        "\n[TEST 6] Unsupported event isolation"
    )

    temp_dir, db_path, old_database_path = (
        create_test_database()
    )

    ack_mock, original_acknowledge = make_ack_mock()

    try:
        event = create_event(
            event_type="person.detected",
            agent_id="person-detector-CAM01",
            instance_id="detector-instance-01",
            hostname="test-host",
            camera_id="CAM01",
            mode="live",
            timestamp="2026-09-04T10:00:00+00:00",
            data={
                "frame_id": 100,
            },
        )

        assert validate_event(event)

        result = asyncio.run(
            event_consumer.process_event(
                "1710000000006-0",
                {
                    "event": event.to_json(),
                },
            )
        )

        incidents = read_incidents(db_path)

        assert len(incidents) == 0

        assert result is None

        ack_mock.assert_awaited_once()

        print(
            "PASS: unsupported event was ignored"
        )

        print(
            "PASS: no incident created"
        )

        print(
            "PASS: unsupported event was ACKed"
        )

    finally:
        restore_acknowledge(original_acknowledge)
        restore_database_path(old_database_path)
        temp_dir.cleanup()


# ============================================================
# TEST 7
# ============================================================

def test_db_failure_does_not_ack():
    print(
        "\n[TEST 7] Database failure -> no ACK"
    )

    event = build_alert_event(
        event_id="alert-db-failure-001",
        camera_id="CAM01",
    )

    ack_mock, original_acknowledge = make_ack_mock()

    try:
        with patch.object(
            event_consumer,
            "create_incident",
            new=AsyncMock(
                side_effect=sqlite3.OperationalError(
                    "simulated database failure"
                )
            ),
        ):
            raised = False

            try:
                asyncio.run(
                    event_consumer.process_event(
                        "1710000000007-0",
                        redis_fields_from_event(event),
                    )
                )

            except sqlite3.OperationalError:
                raised = True

            assert raised is True

            ack_mock.assert_not_awaited()

        print(
            "PASS: database failure propagated"
        )

        print(
            "PASS: failed event was NOT acknowledged"
        )

    finally:
        restore_acknowledge(original_acknowledge)


# ============================================================
# TEST 8
# ============================================================

def test_successful_processing_acknowledges():
    print(
        "\n[TEST 8] Successful processing -> ACK"
    )

    temp_dir, db_path, old_database_path = (
        create_test_database()
    )

    ack_mock, original_acknowledge = make_ack_mock()

    try:
        event = build_alert_event(
            event_id="alert-ack-success-001",
            camera_id="CAM01",
        )

        redis_id = "1710000000008-0"

        asyncio.run(
            event_consumer.process_event(
                redis_id,
                redis_fields_from_event(event),
            )
        )

        incidents = read_incidents(db_path)

        assert len(incidents) == 1

        ack_mock.assert_awaited_once_with(
            redis_id
        )

        print(
            "PASS: incident persisted"
        )

        print(
            "PASS: successful processing triggered ACK"
        )

        print(
            "PASS: ACK used correct Redis message ID"
        )

    finally:
        restore_acknowledge(original_acknowledge)
        restore_database_path(old_database_path)
        temp_dir.cleanup()


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 70)

    print(
        "ALERT.CREATED -> INCIDENT DB CONTRACT TEST"
    )

    print("=" * 70)

    print()

    print(
        "Using incident consumer module:"
    )

    print(
        f"  {event_consumer.__file__}"
    )

    print()

    tests = [
        test_successful_alert_creates_incident,
        test_metadata_preservation,
        test_live_mode_preserved,
        test_duplicate_alert_creates_only_one_incident,
        test_malformed_event_is_isolated,
        test_unsupported_event_is_ignored,
        test_db_failure_does_not_ack,
        test_successful_processing_acknowledges,
    ]

    passed = 0

    for test in tests:
        test()
        passed += 1

    print()

    print("=" * 70)

    print(
        "ALERT.CREATED -> INCIDENT DB CONTRACT TEST PASSED"
    )

    print("=" * 70)

    print(
        f"Tests passed: {passed}/{len(tests)}"
    )

    print()

    print("Verified:")

    print("  alert.created -> Incident DB")
    print("  Camera ID preservation")
    print("  Incident ID generation")
    print("  Severity preservation")
    print("  Track ID preservation")
    print("  Frame timestamp preservation")
    print("  Live/historical mode preservation")
    print("  Trace/correlation preservation")
    print("  Source lineage preservation")
    print("  Duplicate protection")
    print("  Malformed event isolation")
    print("  Unsupported event isolation")
    print("  DB failure -> NO ACK")
    print("  Successful processing -> ACK")

    print("=" * 70)


if __name__ == "__main__":
    main()