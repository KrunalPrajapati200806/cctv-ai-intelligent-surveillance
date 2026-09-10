"""
Canonical event contract registry.

This module maps event_type values to their specialized Pydantic
payload models.

Important:
- BaseEvent validates the common event envelope.
- This registry validates the event-specific `data` payload.
- Producers and consumers should eventually use the same registry.
"""

from __future__ import annotations

from typing import Any, Type

from pydantic import BaseModel, ValidationError

from shared.schemas.crowd_detected import CrowdDetectedData
from shared.schemas.event_schema import BaseEvent
from shared.schemas.person_detected import PersonDetectedData
from shared.schemas.person_tracked import PersonTrackedData
from shared.schemas.vehicle_detected import VehicleDetectedData


# ---------------------------------------------------------------------------
# Event contract registry
# ---------------------------------------------------------------------------

EVENT_DATA_MODELS: dict[str, Type[BaseModel]] = {
    "person.detected": PersonDetectedData,
    "person.tracked": PersonTrackedData,
    "crowd.detected": CrowdDetectedData,
    "vehicle.detected": VehicleDetectedData,
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_event_data_model(event_type: str) -> Type[BaseModel] | None:
    """
    Return the specialized payload model for an event type.

    Returns None when the event type does not yet have a registered
    specialized contract.
    """
    if not isinstance(event_type, str):
        return None

    return EVENT_DATA_MODELS.get(event_type.strip())


def is_registered_event_type(event_type: str) -> bool:
    """Return True when a specialized contract exists for event_type."""
    return get_event_data_model(event_type) is not None


def validate_event_data(
    event_type: str,
    data: dict[str, Any],
) -> BaseModel:
    """
    Validate the event-specific payload.

    Raises:
        ValueError:
            If the event type is unknown or the payload is invalid.
    """
    model = get_event_data_model(event_type)

    if model is None:
        raise ValueError(
            f"No specialized event contract registered for "
            f"event_type={event_type!r}"
        )

    if not isinstance(data, dict):
        raise ValueError(
            f"Event data must be an object/dict for "
            f"event_type={event_type!r}"
        )

    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise ValueError(
            f"Invalid payload for event_type={event_type!r}: {exc}"
        ) from exc


def validate_registered_event(
    value: BaseEvent | dict[str, Any],
) -> BaseEvent:
    """
    Validate both:

    1. the canonical BaseEvent envelope
    2. the specialized event payload

    The returned BaseEvent contains the original event data.
    """
    event = (
        value
        if isinstance(value, BaseEvent)
        else BaseEvent.model_validate(value)
    )

    validate_event_data(
        event.event_type,
        event.data,
    )

    return event


def list_registered_event_types() -> tuple[str, ...]:
    """Return registered event types in deterministic order."""
    return tuple(sorted(EVENT_DATA_MODELS))
