from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EventSource(BaseModel):
    agent_id: str


class EventCamera(BaseModel):
    camera_id: str


class CCTVEvent(BaseModel):
    event_id: str
    event_type: str
    version: str = "1.0"
    timestamp: datetime

    source: EventSource
    camera: EventCamera

    data: dict[str, Any] = Field(
        default_factory=dict
    )