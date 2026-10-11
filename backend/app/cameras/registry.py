from __future__ import annotations

import json
import math
import os

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from backend.app.cameras.policy import (
    CameraPolicy,
    RestrictedZone,
)


class CameraRuntimeStatus(str, Enum):
    REGISTERED = "REGISTERED"
    STARTING = "STARTING"
    ONLINE = "ONLINE"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    RECOVERING = "RECOVERING"
    ERROR = "ERROR"
    FAILED = "FAILED"
    DISABLED = "DISABLED"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"


@dataclass
class CameraRuntimeState:
    """
    Mutable runtime state for one camera.

    CameraConfig describes what the camera IS.

    CameraRuntimeState describes what the camera is DOING RIGHT NOW.

    Runtime state remains separate from immutable camera configuration
    because workers, supervisors and health monitoring update it.
    """

    camera_id: str

    status: CameraRuntimeStatus = (
        CameraRuntimeStatus.REGISTERED
    )

    last_heartbeat: Optional[float] = None

    fps: float = 0.0

    frames_processed: int = 0

    uptime_seconds: float = 0.0

    restart_count: int = 0

    last_error: Optional[str] = None


@dataclass(frozen=True)
class CameraConfig:
    """
    Immutable configuration for one camera.

    `source` may represent:

      - local camera index: "0"
      - video file: "data/videos/test.mp4"
      - RTSP URL: "rtsp://..."
      - HTTP stream: "http://..."

    `source_type` is derived from the source so existing callers that
    construct CameraConfig(source=...) continue to work.

    Runtime state such as ONLINE, ERROR, RECOVERING, heartbeat,
    FPS, restart count, etc. does NOT belong here.
    """

    camera_id: str
    name: str
    source: str

    enabled: bool = True

    location: str = "default"

    # IMPORTANT:
    # Create a separate default CameraPolicy for every CameraConfig.
    policy: CameraPolicy = field(
        default_factory=CameraPolicy
    )

    @property
    def source_type(self) -> str:
        """
        Return the normalized type of camera source.

        Supported types:

            webcam
            file
            rtsp
            http
            invalid
            unknown
        """

        source = self.source.strip().lower()

        # Local webcam / camera index.
        #
        # Examples:
        #   "0"
        #   "1"
        #   "2"
        if source.isdigit():
            return "webcam"

        # RTSP camera stream.
        if source.startswith("rtsp://"):
            return "rtsp"

        # HTTP/HTTPS camera stream.
        if (
            source.startswith("http://")
            or source.startswith("https://")
        ):
            return "http"

        # Intentionally invalid/test source.
        if (
            source.startswith("invalid://")
            or source.startswith("invalid:")
        ):
            return "invalid"

        # Common video-file extensions.
        video_extensions = (
            ".mp4",
            ".avi",
            ".mov",
            ".mkv",
            ".webm",
            ".m4v",
            ".mpeg",
            ".mpg",
            ".wmv",
        )

        if source.endswith(video_extensions):
            return "file"

        return "unknown"


DEFAULT_CAMERAS: list[CameraConfig] = [
    CameraConfig(
        camera_id="CAM01",
        name="Local Camera",
        source="0",
        enabled=True,
        location="default",
    )
]


class CameraRegistry:
    """
    Central camera configuration registry.

    Responsibilities:

      - Store camera configuration.
      - Validate camera configuration.
      - Store camera-specific policy.
      - Store camera-specific restricted zones.
      - Store camera-specific security severity.
      - Provide enabled/disabled camera lists.
      - Support future dynamic camera registration/removal.
      - Remain independent from detection/processing agents.

    Agents receive camera configuration from the supervisor.
    """

    def __init__(
        self,
        cameras: list[CameraConfig] | None = None,
    ) -> None:
        self._cameras: dict[str, CameraConfig] = {}

        initial_cameras = (
            DEFAULT_CAMERAS
            if cameras is None
            else cameras
        )

        for camera in initial_cameras:
            self.register(camera)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_camera_id(
        camera_id: str,
    ) -> str:
        if not isinstance(camera_id, str):
            raise ValueError(
                "camera_id must be a string"
            )

        normalized = camera_id.strip()

        if not normalized:
            raise ValueError(
                "camera_id cannot be empty"
            )

        return normalized

    @staticmethod
    def _normalize_source(
        source: str,
        camera_id: str,
    ) -> str:
        if not isinstance(source, str):
            raise ValueError(
                f"Camera source must be a string: {camera_id}"
            )

        normalized = source.strip()

        if not normalized:
            raise ValueError(
                f"Camera source cannot be empty: {camera_id}"
            )

        return normalized

    @staticmethod
    def _normalize_name(
        name: str,
        camera_id: str,
    ) -> str:
        if not isinstance(name, str):
            raise ValueError(
                f"Camera name must be a string: {camera_id}"
            )

        normalized = name.strip()

        if not normalized:
            return camera_id

        return normalized

    @staticmethod
    def _normalize_location(
        location: str,
    ) -> str:
        if not isinstance(location, str):
            raise ValueError(
                "Camera location must be a string"
            )

        normalized = location.strip()

        return normalized or "default"

    @staticmethod
    def _parse_bool(
        value: Any,
        field_name: str,
    ) -> bool:
        """
        Safely parse boolean configuration.

        Important:

            bool("false") == True

        Therefore string values are explicitly interpreted.
        """

        if isinstance(value, bool):
            return value

        if isinstance(value, int) and value in (0, 1):
            return bool(value)

        if isinstance(value, str):
            normalized = value.strip().lower()

            if normalized in {
                "true",
                "1",
                "yes",
                "on",
                "enabled",
            }:
                return True

            if normalized in {
                "false",
                "0",
                "no",
                "off",
                "disabled",
            }:
                return False

        raise ValueError(
            f"{field_name} must be a boolean"
        )

    @staticmethod
    def _parse_string_set(
        value: Any,
        field_name: str,
    ) -> frozenset[str]:
        """
        Parse a policy collection.

        Accepted:

            ["person", "vehicle"]

        Empty/null:

            None -> empty set
            []   -> empty set
        """

        if value is None:
            return frozenset()

        if not isinstance(
            value,
            (
                list,
                tuple,
                set,
                frozenset,
            ),
        ):
            raise ValueError(
                f"{field_name} must be a list"
            )

        normalized: set[str] = set()

        for item in value:
            if not isinstance(item, str):
                raise ValueError(
                    f"{field_name} must contain only strings"
                )

            item_value = item.strip().lower()

            if item_value:
                normalized.add(item_value)

        return frozenset(normalized)

    @staticmethod
    def _parse_restricted_zone(
        value: Any,
        camera_id: str,
    ) -> RestrictedZone | None:
        """
        Parse a camera-specific restricted zone.

        Expected format:

            "restricted_zone": {
                "x1": 50,
                "y1": 50,
                "x2": 700,
                "y2": 450
            }

        None means that this camera does not have a configured
        restricted zone.
        """

        if value is None:
            return None

        if not isinstance(value, dict):
            raise ValueError(
                "policy.restricted_zone must be an object: "
                f"{camera_id}"
            )

        required_fields = (
            "x1",
            "y1",
            "x2",
            "y2",
        )

        for field_name in required_fields:
            if field_name not in value:
                raise ValueError(
                    "policy.restricted_zone is missing "
                    f"'{field_name}': {camera_id}"
                )

        coordinates: dict[str, float] = {}

        for field_name in required_fields:
            raw_value = value[field_name]

            if isinstance(raw_value, bool):
                raise ValueError(
                    "policy.restricted_zone."
                    f"{field_name} must be a number: "
                    f"{camera_id}"
                )

            try:
                numeric_value = float(raw_value)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "policy.restricted_zone."
                    f"{field_name} must be a number: "
                    f"{camera_id}"
                ) from exc

            if not math.isfinite(numeric_value):
                raise ValueError(
                    "policy.restricted_zone."
                    f"{field_name} must be finite: "
                    f"{camera_id}"
                )

            coordinates[field_name] = numeric_value

        try:
            return RestrictedZone(
                x1=coordinates["x1"],
                y1=coordinates["y1"],
                x2=coordinates["x2"],
                y2=coordinates["y2"],
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Invalid policy.restricted_zone: "
                f"{camera_id}: {exc}"
            ) from exc

    @staticmethod
    def _parse_security_severity(
        value: Any,
        camera_id: str,
    ) -> str:
        """
        Parse camera-specific security severity.

        The value is normalized but not restricted to a closed list,
        keeping the policy extensible.
        """

        if value is None:
            return "high"

        if not isinstance(value, str):
            raise ValueError(
                "policy.security_severity must be a string: "
                f"{camera_id}"
            )

        normalized = value.strip().lower()

        if not normalized:
            raise ValueError(
                "policy.security_severity cannot be empty: "
                f"{camera_id}"
            )

        return normalized

    @classmethod
    def _parse_policy(
        cls,
        value: Any,
        camera_id: str,
    ) -> CameraPolicy:
        """
        Convert JSON policy configuration into CameraPolicy.
        """

        if value is None:
            return CameraPolicy()

        if not isinstance(value, dict):
            raise ValueError(
                f"policy must be an object: {camera_id}"
            )

        normal_objects = cls._parse_string_set(
            value.get("normal_objects"),
            f"policy.normal_objects for {camera_id}",
        )

        restricted_objects = cls._parse_string_set(
            value.get("restricted_objects"),
            f"policy.restricted_objects for {camera_id}",
        )

        alert_events = cls._parse_string_set(
            value.get("alert_events"),
            f"policy.alert_events for {camera_id}",
        )

        sensitivity_value = value.get(
            "sensitivity",
            0.5,
        )

        if isinstance(sensitivity_value, bool):
            raise ValueError(
                "policy.sensitivity must be a number: "
                f"{camera_id}"
            )

        try:
            sensitivity = float(
                sensitivity_value
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "policy.sensitivity must be a number: "
                f"{camera_id}"
            ) from exc

        if not math.isfinite(sensitivity):
            raise ValueError(
                "policy.sensitivity must be finite: "
                f"{camera_id}"
            )

        security_severity = (
            cls._parse_security_severity(
                value.get(
                    "security_severity",
                    "high",
                ),
                camera_id,
            )
        )

        restricted_zone = (
            cls._parse_restricted_zone(
                value.get(
                    "restricted_zone"
                ),
                camera_id,
            )
        )

        return CameraPolicy(
            normal_objects=normal_objects,
            restricted_objects=restricted_objects,
            alert_events=alert_events,
            sensitivity=sensitivity,
            security_severity=security_severity,
            restricted_zone=restricted_zone,
        )

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        camera: CameraConfig,
    ) -> None:
        """
        Register a new camera.

        Duplicate camera IDs are rejected rather than silently
        overwriting an existing configuration.
        """

        if not isinstance(
            camera,
            CameraConfig,
        ):
            raise TypeError(
                "camera must be a CameraConfig instance"
            )

        camera_id = (
            self._normalize_camera_id(
                camera.camera_id
            )
        )

        source = (
            self._normalize_source(
                camera.source,
                camera_id,
            )
        )

        name = (
            self._normalize_name(
                camera.name,
                camera_id,
            )
        )

        location = (
            self._normalize_location(
                camera.location
            )
        )

        if not isinstance(
            camera.policy,
            CameraPolicy,
        ):
            raise TypeError(
                "camera.policy must be a CameraPolicy "
                f"instance: {camera_id}"
            )

        normalized_camera = CameraConfig(
            camera_id=camera_id,
            name=name,
            source=source,
            enabled=self._parse_bool(
                camera.enabled,
                f"enabled for {camera_id}",
            ),
            location=location,
            policy=camera.policy,
        )

        if camera_id in self._cameras:
            raise ValueError(
                f"Duplicate camera_id: {camera_id}"
            )

        self._cameras[camera_id] = (
            normalized_camera
        )

    def unregister(
        self,
        camera_id: str,
    ) -> CameraConfig | None:
        """
        Remove a camera from the registry.

        The runtime manager/supervisor is responsible for stopping
        running agents associated with the removed camera.
        """

        normalized_id = (
            self._normalize_camera_id(
                camera_id
            )
        )

        return self._cameras.pop(
            normalized_id,
            None,
        )

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(
        self,
        camera_id: str,
    ) -> CameraConfig | None:
        """
        Return a camera configuration or None.
        """

        normalized_id = (
            self._normalize_camera_id(
                camera_id
            )
        )

        return self._cameras.get(
            normalized_id
        )

    def get_required(
        self,
        camera_id: str,
    ) -> CameraConfig:
        """
        Return a camera configuration.

        Raises:
            KeyError: if the camera does not exist.
        """

        normalized_id = (
            self._normalize_camera_id(
                camera_id
            )
        )

        camera = self._cameras.get(
            normalized_id
        )

        if camera is None:
            raise KeyError(
                f"Camera not found: {normalized_id}"
            )

        return camera

    def get_enabled(
        self,
    ) -> list[CameraConfig]:
        """
        Return all enabled cameras.
        """

        return [
            camera
            for camera in self._cameras.values()
            if camera.enabled
        ]

    def get_disabled(
        self,
    ) -> list[CameraConfig]:
        """
        Return all disabled cameras.
        """

        return [
            camera
            for camera in self._cameras.values()
            if not camera.enabled
        ]

    def get_all(
        self,
    ) -> list[CameraConfig]:
        """
        Return all registered cameras.
        """

        return list(
            self._cameras.values()
        )

    def count(
        self,
    ) -> int:
        """
        Return total number of registered cameras.
        """

        return len(
            self._cameras
        )

    def enabled_count(
        self,
    ) -> int:
        """
        Return number of enabled cameras.
        """

        return len(
            self.get_enabled()
        )

    # ------------------------------------------------------------------
    # Environment / persistence configuration
    # ------------------------------------------------------------------

    @classmethod
    def from_environment(
        cls,
    ) -> "CameraRegistry":
        """
        Load camera configuration.

        Priority:

            1. CAMERAS_JSON environment variable
            2. persisted camera records
            3. DEFAULT_CAMERAS
        """

        raw = os.getenv(
            "CAMERAS_JSON",
            "",
        ).strip()

        # --------------------------------------------------------------
        # No environment override.
        #
        # Load persistent camera configuration first.
        # --------------------------------------------------------------
        if not raw:
            from backend.app.cameras.store import (
                list_camera_records,
            )

            persisted = list_camera_records()

            if persisted:
                cameras: list[
                    CameraConfig
                ] = []

                for item in persisted:
                    if not isinstance(
                        item,
                        dict,
                    ):
                        continue

                    if (
                        "camera_id"
                        not in item
                    ):
                        raise ValueError(
                            "Persisted camera record is missing "
                            "'camera_id'"
                        )

                    if (
                        "source"
                        not in item
                    ):
                        raise ValueError(
                            "Persisted camera record is missing "
                            "'source'"
                        )

                    raw_camera_id = item[
                        "camera_id"
                    ]

                    camera_id = (
                        cls._normalize_camera_id(
                            str(
                                raw_camera_id
                            )
                        )
                    )

                    source = (
                        cls._normalize_source(
                            str(
                                item[
                                    "source"
                                ]
                            ),
                            camera_id,
                        )
                    )

                    name = (
                        cls._normalize_name(
                            str(
                                item.get(
                                    "name",
                                    camera_id,
                                )
                            ),
                            camera_id,
                        )
                    )

                    enabled = (
                        cls._parse_bool(
                            item.get(
                                "enabled",
                                True,
                            ),
                            f"enabled for {camera_id}",
                        )
                    )

                    location = (
                        cls._normalize_location(
                            str(
                                item.get(
                                    "location",
                                    "default",
                                )
                            )
                        )
                    )

                    policy = (
                        cls._parse_policy(
                            item.get(
                                "policy"
                            ),
                            camera_id,
                        )
                    )

                    cameras.append(
                        CameraConfig(
                            camera_id=camera_id,
                            name=name,
                            source=source,
                            enabled=enabled,
                            location=location,
                            policy=policy,
                        )
                    )

                if cameras:
                    return cls(
                        cameras
                    )

            return cls()

        # --------------------------------------------------------------
        # CAMERAS_JSON override.
        # --------------------------------------------------------------
        try:
            payload: Any = json.loads(
                raw
            )
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid CAMERAS_JSON: {exc}"
            ) from exc

        if not isinstance(
            payload,
            list,
        ):
            raise ValueError(
                "CAMERAS_JSON must be a JSON list"
            )

        cameras: list[
            CameraConfig
        ] = []

        for index, item in enumerate(
            payload
        ):
            if not isinstance(
                item,
                dict,
            ):
                raise ValueError(
                    "Each camera configuration must be "
                    f"an object (index={index})"
                )

            if "camera_id" not in item:
                raise ValueError(
                    f"Camera configuration at index {index} "
                    "is missing 'camera_id'"
                )

            if "source" not in item:
                raise ValueError(
                    f"Camera configuration at index {index} "
                    "is missing 'source'"
                )

            camera_id = (
                cls._normalize_camera_id(
                    str(
                        item[
                            "camera_id"
                        ]
                    )
                )
            )

            source = (
                cls._normalize_source(
                    str(
                        item[
                            "source"
                        ]
                    ),
                    camera_id,
                )
            )

            name = (
                cls._normalize_name(
                    str(
                        item.get(
                            "name",
                            camera_id,
                        )
                    ),
                    camera_id,
                )
            )

            enabled = (
                cls._parse_bool(
                    item.get(
                        "enabled",
                        True,
                    ),
                    f"enabled for {camera_id}",
                )
            )

            location = (
                cls._normalize_location(
                    str(
                        item.get(
                            "location",
                            "default",
                        )
                    )
                )
            )

            policy = (
                cls._parse_policy(
                    item.get(
                        "policy"
                    ),
                    camera_id,
                )
            )

            cameras.append(
                CameraConfig(
                    camera_id=camera_id,
                    name=name,
                    source=source,
                    enabled=enabled,
                    location=location,
                    policy=policy,
                )
            )

        return cls(
            cameras
        )


__all__ = [
    "CameraConfig",
    "CameraRegistry",
    "CameraRuntimeState",
    "CameraRuntimeStatus",
    "DEFAULT_CAMERAS",
]