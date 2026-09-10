# from __future__ import annotations

from dataclasses import dataclass, field
import math


@dataclass(frozen=True)
class RestrictedZone:
    """
    Camera-specific restricted rectangular zone.

    Coordinates are expressed in the camera frame:

        (x1, y1) ----------------
          |                      |
          |     restricted       |
          |        zone           |
          |                      |
          ---------------- (x2,y2)

    The zone is intentionally camera-specific because every camera can
    have a different resolution, viewpoint, and restricted area.
    """

    x1: float
    y1: float
    x2: float
    y2: float

    def __post_init__(self) -> None:
        values = {
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
        }

        for name, value in values.items():
            if isinstance(value, bool):
                raise ValueError(
                    f"Restricted zone {name} must be a number"
                )

            try:
                numeric_value = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Restricted zone {name} must be a number"
                ) from exc

            if not math.isfinite(numeric_value):
                raise ValueError(
                    f"Restricted zone {name} must be finite"
                )

        if self.x1 >= self.x2:
            raise ValueError(
                "Restricted zone requires x1 < x2"
            )

        if self.y1 >= self.y2:
            raise ValueError(
                "Restricted zone requires y1 < y2"
            )

    def contains_point(
        self,
        x: float,
        y: float,
    ) -> bool:
        """
        Return True when a point lies inside the restricted zone.

        Boundary points are considered inside.
        """

        try:
            x_value = float(x)
            y_value = float(y)
        except (TypeError, ValueError):
            return False

        if not math.isfinite(x_value) or not math.isfinite(y_value):
            return False

        return (
            self.x1 <= x_value <= self.x2
            and self.y1 <= y_value <= self.y2
        )

    def to_dict(self) -> dict[str, float]:
        """
        Serialize the zone into a JSON-compatible dictionary.
        """

        return {
            "x1": float(self.x1),
            "y1": float(self.y1),
            "x2": float(self.x2),
            "y2": float(self.y2),
        }


@dataclass(frozen=True)
class CameraPolicy:
    """
    Camera-specific interpretation rules.

    Detection agents detect facts.

    CameraPolicy describes what those facts mean for this camera.

    Example:

        Entrance camera:
            normal_objects = {"person"}
            alert_events = {"intrusion.detected"}

        Bank locker camera:
            restricted_objects = {"person"}
            alert_events = {"person.detected"}

        Restricted-area camera:
            restricted_zone = RestrictedZone(...)
            security_severity = "high"

    Important architectural rule:

        Detection -> facts
        CameraPolicy -> interpretation
        Security/Alert/Incident -> downstream action

    Camera-specific rules must remain here rather than being hardcoded
    inside individual detection agents.
    """

    normal_objects: frozenset[str] = field(
        default_factory=frozenset
    )

    restricted_objects: frozenset[str] = field(
        default_factory=frozenset
    )

    alert_events: frozenset[str] = field(
        default_factory=frozenset
    )

    sensitivity: float = 0.5

    security_severity: str = "high"

    restricted_zone: RestrictedZone | None = None

    def __post_init__(self) -> None:
        # --------------------------------------------------------------
        # Sensitivity validation
        # --------------------------------------------------------------

        if isinstance(self.sensitivity, bool):
            raise ValueError(
                "Camera policy sensitivity must be a number"
            )

        try:
            sensitivity = float(self.sensitivity)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Camera policy sensitivity must be a number"
            ) from exc

        if not math.isfinite(sensitivity):
            raise ValueError(
                "Camera policy sensitivity must be finite"
            )

        if not 0.0 <= sensitivity <= 1.0:
            raise ValueError(
                "Camera policy sensitivity must be between 0.0 and 1.0"
            )

        # --------------------------------------------------------------
        # Security severity validation
        # --------------------------------------------------------------

        if not isinstance(self.security_severity, str):
            raise ValueError(
                "Camera policy security_severity must be a string"
            )

        severity = self.security_severity.strip().lower()

        if not severity:
            raise ValueError(
                "Camera policy security_severity cannot be empty"
            )

        # Keep the field normalized even when constructed directly.
        object.__setattr__(
            self,
            "security_severity",
            severity,
        )

        # --------------------------------------------------------------
        # Restricted zone validation
        # --------------------------------------------------------------

        if self.restricted_zone is not None:
            if not isinstance(
                self.restricted_zone,
                RestrictedZone,
            ):
                raise TypeError(
                    "Camera policy restricted_zone must be a "
                    "RestrictedZone instance or None"
                )

    def is_restricted_object(
        self,
        object_type: str,
    ) -> bool:
        """
        Return True if the object is restricted for this camera.
        """

        if not isinstance(object_type, str):
            return False

        return (
            object_type.strip().lower()
            in self.restricted_objects
        )

    def is_normal_object(
        self,
        object_type: str,
    ) -> bool:
        """
        Return True if the object is considered normal for this camera.
        """

        if not isinstance(object_type, str):
            return False

        return (
            object_type.strip().lower()
            in self.normal_objects
        )

    def should_alert_event(
        self,
        event_type: str,
    ) -> bool:
        """
        Return True if this camera explicitly marks the event type
        as alert-worthy.
        """

        if not isinstance(event_type, str):
            return False

        return (
            event_type.strip().lower()
            in self.alert_events
        )

    def has_restricted_zone(self) -> bool:
        """
        Return True when a restricted zone is configured.
        """

        return self.restricted_zone is not None


__all__ = [
    "CameraPolicy",
    "RestrictedZone",
]
