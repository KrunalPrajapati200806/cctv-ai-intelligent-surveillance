from pydantic import BaseModel, ConfigDict, Field


class PersonTrack(BaseModel):
    model_config = ConfigDict(extra="forbid")
    track_id: str = Field(min_length=1)
    detection_id: str = Field(min_length=1)

    bbox: list[float] = Field(min_length=4, max_length=4)

    confidence: float = Field(
        ge=0,
        le=1,
    )

    center: list[float] = Field(
        min_length=2,
        max_length=2,
    )


class PersonTrackedData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    frame_id: str = Field(min_length=1)

    tracks: list[PersonTrack]