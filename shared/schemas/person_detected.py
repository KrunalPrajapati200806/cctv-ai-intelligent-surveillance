from pydantic import BaseModel, ConfigDict, Field


class PersonDetection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detection_id: str = Field(min_length=1)

    confidence: float = Field(
        ge=0,
        le=1,
    )

    bbox: list[float] = Field(
        min_length=4,
        max_length=4,
    )

    class_id: int | None = None
    class_name: str | None = None


class PersonDetectedData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    frame_id: str = Field(min_length=1)

    detections: list[PersonDetection]

    frame_timestamp: str | None = None
    detection_count: int | None = None
    count: int | None = None
    model: str | None = None
    confidence_threshold: float | None = None