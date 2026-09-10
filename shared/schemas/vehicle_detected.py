from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VehicleDetection(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    detection_id: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    bbox: list[float] = Field(min_length=4, max_length=4)

    class_id: int | None = None
    class_name: str | None = None
    vehicle_class: str | None = Field(default=None, alias="class")


class VehicleDetectedData(BaseModel):
    """
    Runtime contract for vehicle.detected.

    The JSON schema documents `detections`. Live detection currently publishes
    `vehicles`. Both are accepted; `detections` is the canonical list after
    validation.
    """

    model_config = ConfigDict(extra="forbid")

    frame_id: str = Field(min_length=1)
    detections: list[VehicleDetection] = Field(default_factory=list)
    vehicles: list[VehicleDetection] = Field(default_factory=list)

    frame_timestamp: str | None = None
    vehicle_count: int | None = None
    count: int | None = None
    model: str | None = None
    confidence_threshold: float | None = None

    @model_validator(mode="before")
    @classmethod
    def _canonicalize_lists(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        payload = dict(value)
        detections = payload.get("detections")
        vehicles = payload.get("vehicles")

        if not detections and isinstance(vehicles, list):
            payload["detections"] = vehicles

        return payload
