from pydantic import BaseModel, ConfigDict, Field, field_validator


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

    detections: list[PersonDetection] = Field(default_factory=list)

    @field_validator("frame_id", mode="before")
    @classmethod
    def normalize_frame_id(cls, value):
        return str(value)

    frame_timestamp: str | None = None
    detection_count: int | None = None
    count: int | None = None
    model: str | None = None
    confidence_threshold: float | None = None