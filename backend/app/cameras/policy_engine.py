from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.app.cameras.policy import CameraPolicy


@dataclass(frozen=True)
class PolicyDecision:
    """
    Result of evaluating one canonical event against a camera policy.
    """

    camera_id: str
    event_type: str
    decision: str
    reason: str
    should_alert: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "event_type": self.event_type,
            "decision": self.decision,
            "reason": self.reason,
            "should_alert": self.should_alert,
        }


class CameraPolicyEngine:
    """
    Evaluates canonical events using camera-specific policies.

    Detection remains independent from policy.

    Detection:
        Camera -> CV/ML -> structured event

    Policy:
        structured event -> camera policy -> decision

    This class does NOT perform:
        - object detection
        - tracking
        - video processing
        - alert delivery
        - incident creation
    """

    def __init__(
        self,
        policies: dict[str, CameraPolicy] | None = None,
    ) -> None:
        self._policies: dict[str, CameraPolicy] = {}

        if policies:
            for camera_id, policy in policies.items():
                self.register_policy(
                    camera_id=camera_id,
                    policy=policy,
                )

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_registry(
        cls,
        registry: Any,
    ) -> "CameraPolicyEngine":
        """
        Build a policy engine from a CameraRegistry.

        The registry is intentionally accepted by duck typing so this
        module does not create a hard circular dependency on registry.py.

        Expected registry interface:
            registry.get_all()

        Each camera must expose:
            camera.camera_id
            camera.policy
        """

        if registry is None:
            raise ValueError("registry cannot be None")

        get_all = getattr(registry, "get_all", None)

        if not callable(get_all):
            raise TypeError(
                "registry must provide a callable get_all() method"
            )

        engine = cls()

        for camera in get_all():
            camera_id = str(
                getattr(camera, "camera_id", "")
            ).strip()

            if not camera_id:
                raise ValueError(
                    "Camera registry contains a camera "
                    "without camera_id"
                )

            policy = getattr(camera, "policy", None)

            if not isinstance(policy, CameraPolicy):
                raise TypeError(
                    f"Camera '{camera_id}' has invalid policy"
                )

            engine.register_policy(
                camera_id=camera_id,
                policy=policy,
            )

        return engine

    # ------------------------------------------------------------------
    # Policy registration
    # ------------------------------------------------------------------

    def register_policy(
        self,
        camera_id: str,
        policy: CameraPolicy,
    ) -> None:
        """
        Register or replace a policy for one camera.
        """

        if not isinstance(camera_id, str):
            raise TypeError(
                "camera_id must be a string"
            )

        camera_id = camera_id.strip()

        if not camera_id:
            raise ValueError(
                "camera_id cannot be empty"
            )

        if not isinstance(policy, CameraPolicy):
            raise TypeError(
                "policy must be a CameraPolicy instance"
            )

        self._policies[camera_id] = policy

    def unregister_policy(
        self,
        camera_id: str,
    ) -> CameraPolicy | None:
        """
        Remove a camera policy.
        """

        camera_id = self._normalize_camera_id(
            camera_id
        )

        return self._policies.pop(
            camera_id,
            None,
        )

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_camera_id(
        camera_id: str,
    ) -> str:
        if not isinstance(camera_id, str):
            raise TypeError(
                "camera_id must be a string"
            )

        normalized = camera_id.strip()

        if not normalized:
            raise ValueError(
                "camera_id cannot be empty"
            )

        return normalized

    def get_policy(
        self,
        camera_id: str,
    ) -> CameraPolicy | None:
        """
        Return the configured policy for a camera.
        """

        camera_id = self._normalize_camera_id(
            camera_id
        )

        return self._policies.get(camera_id)

    def has_policy(
        self,
        camera_id: str,
    ) -> bool:
        return self.get_policy(camera_id) is not None

    def camera_ids(self) -> list[str]:
        """
        Return all cameras currently configured in the engine.
        """

        return list(self._policies.keys())

    def count(self) -> int:
        return len(self._policies)

    # ------------------------------------------------------------------
    # Event evaluation
    # ------------------------------------------------------------------

    def evaluate(
        self,
        event: dict[str, Any],
    ) -> PolicyDecision:
        """
        Evaluate a canonical event.

        Expected structure:

        {
            "event_type": "person.detected",
            "camera": {
                "camera_id": "CAM01"
            },
            "data": {
                "object_type": "person"
            }
        }
        """

        if not isinstance(event, dict):
            raise ValueError(
                "Event must be a dictionary"
            )

        event_type = str(
            event.get("event_type", "")
        ).strip().lower()

        if not event_type:
            raise ValueError(
                "Event is missing event_type"
            )

        camera = event.get("camera")

        if not isinstance(camera, dict):
            raise ValueError(
                "Event is missing camera information"
            )

        camera_id = str(
            camera.get("camera_id", "")
        ).strip()

        if not camera_id:
            raise ValueError(
                "Event is missing camera_id"
            )

        policy = self.get_policy(camera_id)

        if policy is None:
            return PolicyDecision(
                camera_id=camera_id,
                event_type=event_type,
                decision="unknown",
                reason="No policy configured for camera",
                should_alert=False,
            )

        # --------------------------------------------------------------
        # Explicit event-level alert rule has highest priority.
        # --------------------------------------------------------------

        if policy.should_alert_event(event_type):
            return PolicyDecision(
                camera_id=camera_id,
                event_type=event_type,
                decision="alert",
                reason=(
                    "Event explicitly configured as "
                    "an alert event"
                ),
                should_alert=True,
            )

        # --------------------------------------------------------------
        # Object-level policy.
        # --------------------------------------------------------------

        data = event.get("data", {})

        if not isinstance(data, dict):
            data = {}

        object_type = str(
            data.get("object_type", "")
        ).strip().lower()

        if object_type:

            if policy.is_restricted_object(
                object_type
            ):
                return PolicyDecision(
                    camera_id=camera_id,
                    event_type=event_type,
                    decision="alert",
                    reason=(
                        f"Object '{object_type}' is restricted "
                        "for this camera"
                    ),
                    should_alert=True,
                )

            if policy.is_normal_object(
                object_type
            ):
                return PolicyDecision(
                    camera_id=camera_id,
                    event_type=event_type,
                    decision="normal",
                    reason=(
                        f"Object '{object_type}' is normal "
                        "for this camera"
                    ),
                    should_alert=False,
                )

        # --------------------------------------------------------------
        # No rule matched.
        # --------------------------------------------------------------

        return PolicyDecision(
            camera_id=camera_id,
            event_type=event_type,
            decision="unknown",
            reason="No matching policy rule",
            should_alert=False,
        )


__all__ = [
    "CameraPolicyEngine",
    "PolicyDecision",
]