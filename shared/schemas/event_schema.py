# {
#   "$schema": "https://json-schema.org/draft/2020-12/schema",
#   "$id": "https://cctv-ai.local/schemas/base-event.json",
#   "title": "CCTV AI Base Event",
#   "description": "Canonical event envelope used by the CCTV AI platform.",
#   "type": "object",
#   "additionalProperties": False,
#   "required": [
#     "event_id",
#     "event_type",
#     "version",
#     "timestamp",
#     "source",
#     "camera",
#     "context",
#     "data"
#   ],
#   "properties": {
#     "event_id": {
#       "type": "string",
#       "minLength": 1
#     },

#     "event_type": {
#       "type": "string",
#       "minLength": 1
#     },

#     "version": {
#       "type": "string",
#       "pattern": "^[0-9]+\\.[0-9]+$"
#     },

#     "timestamp": {
#       "type": "string",
#       "format": "date-time"
#     },

#     "source": {
#       "type": "object",
#       "additionalProperties": False,
#       "required": [
#         "agent_id",
#         "instance_id",
#         "hostname"
#       ],
#       "properties": {
#         "agent_id": {
#           "type": "string",
#           "minLength": 1
#         },
#         "instance_id": {
#           "type": "string",
#           "minLength": 1
#         },
#         "hostname": {
#           "type": "string",
#           "minLength": 1
#         }
#       }
#     },

#     "camera": {
#       "type": "object",
#       "additionalProperties": False,
#       "required": [
#         "camera_id"
#       ],
#       "properties": {
#         "camera_id": {
#           "type": "string",
#           "minLength": 1
#         }
#       }
#     },

#     "context": {
#       "type": "object",
#       "additionalProperties": False,
#       "required": [
#         "mode",
#         "trace_id",
#         "correlation_id"
#       ],
#       "properties": {
#         "mode": {
#           "type": "string",
#           "enum": [
#             "live",
#             "historical"
#           ]
#         },

#         "trace_id": {
#           "type": "string",
#           "minLength": 1
#         },

#         "correlation_id": {
#           "type": [
#             "string",
#             "null"
#           ]
#         },

#         "incident_id": {
#           "type": [
#             "string",
#             "null"
#           ]
#         }
#       }
#     },

#     "data": {
#       "type": "object"
#     }
#   }
# }

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


EventMode = Literal["live", "historical"]


class EventSource(BaseModel):
    """
    Identifies the component that produced the event.
    """

    model_config = ConfigDict(extra="forbid")

    agent_id: str = Field(min_length=1)
    instance_id: str = Field(min_length=1)
    hostname: str = Field(min_length=1)


class EventCamera(BaseModel):
    """
    Camera associated with the event.
    """

    model_config = ConfigDict(extra="forbid")

    camera_id: str = Field(min_length=1)


class EventContext(BaseModel):
    """
    Correlation and execution context shared across the event pipeline.
    """

    model_config = ConfigDict(extra="forbid")

    mode: EventMode = "live"

    trace_id: str = Field(
        default_factory=lambda: str(uuid4()),
        min_length=1,
    )

    correlation_id: Optional[str] = None

    incident_id: Optional[str] = None


class BaseEvent(BaseModel):
    """
    Canonical event envelope used throughout the CCTV platform.

    Every normal AI/system pipeline event should use this structure.
    """

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(
        default_factory=lambda: str(uuid4()),
        min_length=1,
    )

    event_type: str = Field(min_length=1)

    version: str = "1.0"

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    source: EventSource

    camera: EventCamera

    context: EventContext = Field(
        default_factory=EventContext
    )

    data: dict[str, Any] = Field(
        default_factory=dict
    )

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        """
        Require timezone-aware timestamps and normalize them to UTC.
        """

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "timestamp must be timezone-aware"
            )

        return value.astimezone(timezone.utc)

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        """
        Event versions must use MAJOR.MINOR format.
        """

        parts = value.split(".")

        if len(parts) != 2:
            raise ValueError(
                "version must use MAJOR.MINOR format"
            )

        if not all(part.isdigit() for part in parts):
            raise ValueError(
                "version must use MAJOR.MINOR numeric format"
            )

        return value

    def to_dict(self) -> dict[str, Any]:
        """
        Return the event as a JSON-compatible dictionary.
        """

        return self.model_dump(mode="json")

    def to_json(self) -> str:
        """
        Return the event as JSON.
        """

        return self.model_dump_json()


def create_event(
    *,
    event_type: str,
    agent_id: str,
    instance_id: str,
    hostname: str,
    camera_id: str,
    data: Optional[dict[str, Any]] = None,
    mode: EventMode = "live",
    trace_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    incident_id: Optional[str] = None,
    event_id: Optional[str] = None,
    timestamp: Optional[datetime] = None,
    version: str = "1.0",
) -> BaseEvent:
    """
    Convenience factory for creating canonical events.
    """

    context = EventContext(
        mode=mode,
        trace_id=trace_id or str(uuid4()),
        correlation_id=correlation_id,
        incident_id=incident_id,
    )

    return BaseEvent(
        event_id=event_id or str(uuid4()),
        event_type=event_type,
        version=version,
        timestamp=timestamp or datetime.now(timezone.utc),
        source=EventSource(
            agent_id=agent_id,
            instance_id=instance_id,
            hostname=hostname,
        ),
        camera=EventCamera(
            camera_id=camera_id,
        ),
        context=context,
        data=data or {},
    )


def validate_event(value: Any) -> BaseEvent:
    """
    Validate the canonical envelope, then the specialized payload
    when the event_type is registered.
    """

    event = (
        value
        if isinstance(value, BaseEvent)
        else BaseEvent.model_validate(value)
    )

    from shared.schemas.event_registry import (
        get_event_data_model,
        validate_event_data,
    )

    if get_event_data_model(event.event_type) is not None:
        validate_event_data(event.event_type, event.data)

    return event


def validate_event_json(value: str) -> BaseEvent:
    """
    Validate a JSON string as a BaseEvent.
    """

    return BaseEvent.model_validate_json(value)


def is_valid_event(value: Any) -> bool:
    """
    Return True when the supplied value is a valid BaseEvent.
    """

    try:
        validate_event(value)
        return True
    except Exception:
        return False