from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CrowdDetectedData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    frame_id: str = Field(min_length=1)

    person_count: int = Field(
        ge=0,
    )

    density: float = Field(
        ge=0,
    )

    threshold: float = Field(
        ge=0,
    )

    severity: Literal[
        "low",
        "medium",
        "high",
        "critical",
    ]

    track_ids: list[str] = Field(
        default_factory=list,
    )