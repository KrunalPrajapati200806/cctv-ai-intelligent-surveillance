from datetime import datetime, timedelta, timezone

import pytest

from agents.tracker.main import PersonTrackerAgent


def make_agent(monkeypatch, mode="live"):
    monkeypatch.setenv("TRACKER_MODE", mode)
    monkeypatch.setenv("LIVE_EVENT_MAX_AGE", "5")
    monkeypatch.delenv("TRACKER_INPUT_STREAM", raising=False)
    return PersonTrackerAgent()


def test_live_tracker_rejects_old_recovery_event(monkeypatch):
    agent = make_agent(monkeypatch)
    now = datetime.now(timezone.utc)

    assert agent._is_stale_live_event(
        now - timedelta(seconds=6),
        now=now,
    )


def test_live_tracker_accepts_recent_event(monkeypatch):
    agent = make_agent(monkeypatch)
    now = datetime.now(timezone.utc)

    assert not agent._is_stale_live_event(
        now - timedelta(seconds=4),
        now=now,
    )


def test_historical_tracker_does_not_apply_live_age_filter(monkeypatch):
    agent = make_agent(monkeypatch, mode="historical")
    old_timestamp = datetime(2020, 1, 1, tzinfo=timezone.utc)

    assert agent.input_stream == "events.detection.historical"
    assert not agent._is_stale_live_event(old_timestamp)


def test_tracker_rejects_unknown_mode(monkeypatch):
    monkeypatch.setenv("TRACKER_MODE", "replay")

    with pytest.raises(ValueError, match="TRACKER_MODE"):
        PersonTrackerAgent()