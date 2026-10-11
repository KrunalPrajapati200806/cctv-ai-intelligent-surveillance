"""
Behavior Agent

Consumes canonical ``person.tracked`` events and detects behavioral
patterns such as loitering.

Pipeline:

    events.tracking
          |
          v
    BehaviorAgent
          |
          v
    events.behavior
          |
          +--> loitering.detected

Design principles:

- Canonical event envelope
- Camera-aware state isolation
- Historical-mode timestamp preservation
- Trace/correlation/incident propagation
- Source-event lineage
- Per-message fault isolation
- ACK only after successful processing
- No silent camera fallback
- Stateful processing requires same-camera routing/affinity

Current behavior detection:

- person loitering

Important state identity:

    (camera_id, track_id)

A track ID is only meaningful inside its camera context.

Important reliability rule:

    Permanent invalid/poison message
        -> ACK

    Unexpected processing/publish failure
        -> DO NOT ACK
        -> leave message pending for recovery

IMPORTANT VALIDATION DESIGN:

The shared ``validate_event()`` function validates both:

1. the canonical BaseEvent envelope, and
2. a specialized payload when the event type is registered.

The current Tracker producer payload and the registered
``person.tracked`` specialized schema are not aligned yet.

Therefore this agent intentionally performs:

    BaseEvent.model_validate(...)
        +
    local person.tracked payload validation

instead of calling ``validate_event()`` for incoming
``person.tracked`` messages.

Generated ``loitering.detected`` events ARE validated with the
full ``validate_event()`` function because their producer and
specialized schema are expected to be aligned.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from shared.agent.base_agent import BaseAgent
from shared.schemas.event_schema import (
    BaseEvent,
    create_event,
    validate_event,
)


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_AGENT_ID = os.getenv(
    "BEHAVIOR_AGENT_ID",
    os.getenv("AGENT_ID", "behavior-01"),
)

DEFAULT_HEARTBEAT_INTERVAL = int(
    os.getenv(
        "HEARTBEAT_INTERVAL",
        "10",
    )
)

INPUT_STREAM = os.getenv(
    "BEHAVIOR_INPUT_STREAM",
    "events.tracking",
)

OUTPUT_STREAM = os.getenv(
    "BEHAVIOR_OUTPUT_STREAM",
    "events.behavior",
)

GROUP_NAME = os.getenv(
    "BEHAVIOR_GROUP",
    "behavior-workers",
)

CONSUMER_NAME = os.getenv(
    "BEHAVIOR_CONSUMER",
    f"behavior-{uuid.uuid4().hex[:8]}",
)

LOITERING_THRESHOLD = float(
    os.getenv(
        "LOITERING_THRESHOLD",
        "30.0",
    )
)

TRACK_TIMEOUT = float(
    os.getenv(
        "TRACK_TIMEOUT",
        "2.0",
    )
)


# ============================================================
# VALIDATE STATIC CONFIGURATION
# ============================================================

def _validate_positive_finite(
    name: str,
    value: float,
) -> float:
    """
    Validate a positive finite numeric configuration value.
    """

    if not math.isfinite(value):
        raise ValueError(
            f"{name} must be finite. "
            f"Received: {value!r}"
        )

    if value <= 0:
        raise ValueError(
            f"{name} must be greater than zero. "
            f"Received: {value!r}"
        )

    return value


_validate_positive_finite(
    "LOITERING_THRESHOLD",
    LOITERING_THRESHOLD,
)

_validate_positive_finite(
    "TRACK_TIMEOUT",
    TRACK_TIMEOUT,
)


# ============================================================
# BEHAVIOR AGENT
# ============================================================

class BehaviorAgent(BaseAgent):
    """
    Stateful behavior analysis worker.

    Input:
        events.tracking

    Output:
        events.behavior

    Current detection:
        person loitering

    State identity:
        (camera_id, track_id)

    Important:

    The worker assumes camera affinity is provided by the surrounding
    routing/supervision topology. Redis consumer groups alone do NOT
    guarantee that all events for one camera reach the same worker.
    """

    def __init__(self):
        super().__init__(
            agent_id=DEFAULT_AGENT_ID,
            heartbeat_interval=DEFAULT_HEARTBEAT_INTERVAL,
        )

        self.input_stream = INPUT_STREAM
        self.output_stream = OUTPUT_STREAM
        self.group_name = GROUP_NAME
        self.consumer_name = CONSUMER_NAME

        self.loitering_threshold = LOITERING_THRESHOLD
        self.track_timeout = TRACK_TIMEOUT

        # ----------------------------------------------------
        # Stateful behavior tracking.
        #
        # Key:
        #     (camera_id, track_id)
        #
        # Value:
        #     {
        #         "first_seen": datetime,
        #         "last_seen": datetime,
        #         "loitering_emitted": bool,
        #     }
        # ----------------------------------------------------

        self.track_state: Dict[
            Tuple[str, str],
            Dict[str, Any],
        ] = {}

        # ----------------------------------------------------
        # Per-camera event watermark.
        #
        # Prevents an old event from moving camera state
        # backward in time.
        # ----------------------------------------------------

        self.last_event_timestamp: Dict[
            str,
            datetime,
        ] = {}

    # ========================================================
    # TIMESTAMP PARSING
    # ========================================================

    @staticmethod
    def _parse_timestamp(
        value: Any,
    ) -> Optional[datetime]:
        """
        Parse only timezone-aware timestamps.

        Naive timestamps are rejected rather than silently being
        interpreted as UTC. This keeps live and historical event
        semantics deterministic.
        """

        if isinstance(value, datetime):
            parsed = value

        elif isinstance(value, str):
            text = value.strip()

            if not text:
                return None

            if text.endswith("Z"):
                text = text[:-1] + "+00:00"

            try:
                parsed = datetime.fromisoformat(text)

            except ValueError:
                return None

        else:
            return None

        if (
            parsed.tzinfo is None
            or parsed.utcoffset() is None
        ):
            return None

        return parsed.astimezone(
            timezone.utc
        )

    # ========================================================
    # EVENT TIME
    # ========================================================

    @classmethod
    def _event_time(
        cls,
        event: Dict[str, Any],
    ) -> Optional[datetime]:
        """
        Determine the timestamp used for behavior calculations.

        Preference:

        1. data.frame_timestamp
        2. event.timestamp

        Never fall back to runtime wall-clock time.
        """

        data = event.get("data")

        if isinstance(data, dict):
            frame_timestamp = cls._parse_timestamp(
                data.get("frame_timestamp")
            )

            if frame_timestamp is not None:
                return frame_timestamp

        return cls._parse_timestamp(
            event.get("timestamp")
        )

    # ========================================================
    # CAMERA ID
    # ========================================================

    @staticmethod
    def _extract_camera_id(
        event: Dict[str, Any],
    ) -> Optional[str]:
        """
        Extract and validate the canonical camera identity.
        """

        camera = event.get("camera")

        if not isinstance(
            camera,
            dict,
        ):
            return None

        camera_id = camera.get(
            "camera_id"
        )

        if not isinstance(
            camera_id,
            str,
        ):
            return None

        camera_id = camera_id.strip()

        if not camera_id:
            return None

        return camera_id

    # ========================================================
    # TRACK VALIDATION
    # ========================================================

    @staticmethod
    def _validate_track(
        track: Any,
    ) -> bool:
        """
        Validate the currently produced person.tracked structure.

        This is intentionally local.

        The registered specialized person.tracked schema currently
        rejects producer fields such as:

            source_event_id
            source_redis_id
            frame_timestamp
            detection_count
            track_count
            tracker

        Therefore this worker does not route incoming person.tracked
        events through the specialized registry validation.
        """

        if not isinstance(
            track,
            dict,
        ):
            return False

        track_id = track.get(
            "track_id"
        )

        if not isinstance(
            track_id,
            str,
        ) or not track_id.strip():
            return False

        bbox = track.get(
            "bbox"
        )

        if (
            not isinstance(
                bbox,
                (list, tuple),
            )
            or len(bbox) != 4
        ):
            return False

        try:
            bbox_values = [
                float(value)
                for value in bbox
            ]

        except (
            TypeError,
            ValueError,
        ):
            return False

        if not all(
            math.isfinite(value)
            for value in bbox_values
        ):
            return False

        x1, y1, x2, y2 = bbox_values

        if x2 < x1 or y2 < y1:
            return False

        center = track.get(
            "center"
        )

        if (
            not isinstance(
                center,
                (list, tuple),
            )
            or len(center) != 2
        ):
            return False

        try:
            center_values = [
                float(value)
                for value in center
            ]

        except (
            TypeError,
            ValueError,
        ):
            return False

        if not all(
            math.isfinite(value)
            for value in center_values
        ):
            return False

        confidence = track.get(
            "confidence"
        )

        if confidence is not None:
            try:
                confidence_value = float(
                    confidence
                )

            except (
                TypeError,
                ValueError,
            ):
                return False

            if (
                not math.isfinite(
                    confidence_value
                )
                or not 0.0 <= confidence_value <= 1.0
            ):
                return False

        return True

    # ========================================================
    # TRACKING PAYLOAD VALIDATION
    # ========================================================

    @classmethod
    def _validate_tracking_payload(
        cls,
        event: Dict[str, Any],
    ) -> list[Dict[str, Any]]:
        """
        Validate the current Tracker producer payload.

        Returns:
            Validated track dictionaries.

        Raises:
            ValueError:
                If the payload itself is malformed.
        """

        data = event.get(
            "data"
        )

        if not isinstance(
            data,
            dict,
        ):
            raise ValueError(
                "person.tracked data must be an object."
            )

        frame_id = data.get(
            "frame_id"
        )

        if not isinstance(
            frame_id,
            str,
        ) or not frame_id.strip():
            raise ValueError(
                "person.tracked frame_id must be "
                "a non-empty string."
            )

        tracks = data.get(
            "tracks"
        )

        if not isinstance(
            tracks,
            list,
        ):
            raise ValueError(
                "person.tracked tracks must be a list."
            )

        validated_tracks: list[
            Dict[str, Any]
        ] = []

        for index, track in enumerate(
            tracks
        ):
            if not cls._validate_track(
                track
            ):
                raise ValueError(
                    "Invalid track at index "
                    f"{index}."
                )

            validated_tracks.append(
                track
            )

        return validated_tracks

    # ========================================================
    # INCOMING CANONICAL ENVELOPE VALIDATION
    # ========================================================

    @staticmethod
    def _validate_canonical_envelope(
        event: Dict[str, Any],
    ) -> BaseEvent:
        """
        Validate ONLY the canonical BaseEvent envelope.

        Do NOT call validate_event() here.

        validate_event() additionally invokes the specialized event
        registry. The current person.tracked producer payload is not
        compatible with that specialized schema yet.

        BaseEvent.model_validate() validates:

        - event_id
        - event_type
        - version
        - timestamp
        - source
        - camera
        - context
        - data container

        The contents of data are validated separately by the local
        person.tracked validator.
        """

        return BaseEvent.model_validate(
            event
        )

    # ========================================================
    # STATE CLEANUP
    # ========================================================

    def cleanup_camera_tracks(
        self,
        camera_id: str,
        current_event_time: datetime,
    ) -> None:
        """
        Remove stale state for ONE camera only.

        A timestamp from one camera can never delete state from
        another camera.

        Out-of-order events never cause cleanup because only
        non-negative ages are considered.
        """

        stale_keys: list[
            Tuple[str, str]
        ] = []

        for (
            state_camera_id,
            track_id,
        ), state in self.track_state.items():

            if state_camera_id != camera_id:
                continue

            last_seen = state.get(
                "last_seen"
            )

            if not isinstance(
                last_seen,
                datetime,
            ):
                stale_keys.append(
                    (
                        state_camera_id,
                        track_id,
                    )
                )
                continue

            age_seconds = (
                current_event_time
                - last_seen
            ).total_seconds()

            if (
                age_seconds >= 0
                and age_seconds > self.track_timeout
            ):
                stale_keys.append(
                    (
                        state_camera_id,
                        track_id,
                    )
                )

        for key in stale_keys:
            removed_state = self.track_state.pop(
                key,
                None,
            )

            if removed_state is not None:
                _, track_id = key

                print(
                    f"[{self.agent_id}] "
                    f"Track state expired | "
                    f"Camera={camera_id} | "
                    f"Track={track_id}"
                )

    # ========================================================
    # BUILD BEHAVIOR EVENT
    # ========================================================

    def _build_behavior_event(
        self,
        source_event: Dict[str, Any],
        redis_id: str,
        camera_id: str,
        track: Dict[str, Any],
        duration: float,
        event_time: datetime,
    ) -> Dict[str, Any]:
        """
        Build canonical loitering.detected event.

        The event timestamp is always derived from the source
        tracking event. Runtime wall-clock time is never used.
        """

        source_context = source_event.get(
            "context",
            {},
        )

        if not isinstance(
            source_context,
            dict,
        ):
            source_context = {}

        source_data = source_event.get(
            "data",
            {},
        )

        if not isinstance(
            source_data,
            dict,
        ):
            source_data = {}

        track_id = str(
            track.get("track_id")
        ).strip()

        frame_id = source_data.get(
            "frame_id"
        )

        if not isinstance(
            frame_id,
            str,
        ) or not frame_id.strip():
            frame_id = redis_id

        frame_timestamp = source_data.get(
            "frame_timestamp"
        )

        if not isinstance(
            frame_timestamp,
            str,
        ) or not frame_timestamp.strip():
            frame_timestamp = (
                event_time
                .isoformat()
                .replace(
                    "+00:00",
                    "Z",
                )
            )

        behavior_data = {
            "frame_id": frame_id,
            "frame_timestamp": frame_timestamp,
            "track_id": track_id,
            "duration_seconds": round(
                max(
                    duration,
                    0.0,
                ),
                2,
            ),
            "threshold_seconds": (
                self.loitering_threshold
            ),
            "severity": "medium",
            "behavior": "loitering",

            # Source lineage.
            "source_event_id": source_event.get(
                "event_id"
            ),
            "source_redis_id": redis_id,

            "track": {
                "center": track.get(
                    "center"
                ),
                "bbox": track.get(
                    "bbox"
                ),
                "age": track.get(
                    "age"
                ),
                "match_distance": track.get(
                    "match_distance"
                ),
            },
        }

        event = create_event(
            event_type="loitering.detected",
            agent_id=self.agent_id,
            instance_id=self.instance_id,
            hostname=self.hostname,
            camera_id=camera_id,
            mode=source_context.get(
                "mode",
                "live",
            ),
            data=behavior_data,
            trace_id=source_context.get(
                "trace_id"
            ),
            correlation_id=source_context.get(
                "correlation_id"
            ),
            incident_id=source_context.get(
                "incident_id"
            ),
            timestamp=event_time,
        )

        return event.to_dict()

    # ========================================================
    # STARTUP
    # ========================================================

    async def on_start(self):
        if not self.redis_client:
            raise RuntimeError(
                "Redis client is not initialized."
            )

        try:
            await self.redis_client.xgroup_create(
                self.input_stream,
                self.group_name,
                id="0",
                mkstream=True,
            )

            print(
                f"[{self.agent_id}] "
                f"Created consumer group: "
                f"{self.group_name}"
            )

        except Exception as error:
            if "BUSYGROUP" not in str(error):
                raise

            print(
                f"[{self.agent_id}] "
                f"Consumer group already exists: "
                f"{self.group_name}"
            )

        print(
            f"[{self.agent_id}] "
            "Behavior agent ready."
        )

        print(
            f"[{self.agent_id}] "
            f"Instance: {self.instance_id}"
        )

        print(
            f"[{self.agent_id}] "
            f"Hostname: {self.hostname}"
        )

        print(
            f"[{self.agent_id}] "
            f"Input: {self.input_stream}"
        )

        print(
            f"[{self.agent_id}] "
            f"Output: {self.output_stream}"
        )

        print(
            f"[{self.agent_id}] "
            f"Consumer: {self.consumer_name}"
        )

        print(
            f"[{self.agent_id}] "
            f"Loitering threshold: "
            f"{self.loitering_threshold:.2f}s"
        )

        print(
            f"[{self.agent_id}] "
            f"Track timeout: "
            f"{self.track_timeout:.2f}s"
        )

        print(
            f"[{self.agent_id}] "
            "State model: camera + track_id"
        )

    # ========================================================
    # SHUTDOWN
    # ========================================================

    async def on_stop(self):
        self.track_state.clear()
        self.last_event_timestamp.clear()

        print(
            f"[{self.agent_id}] "
            "Behavior state cleared."
        )

    # ========================================================
    # PROCESS ONE MESSAGE
    # ========================================================

    async def process_message(
        self,
        redis_id: str,
        fields: Dict[str, Any],
    ) -> None:
        """
        Process exactly one Redis message.

        Permanent malformed input is ACKed.

        Unexpected processing or Redis/publish failures are allowed
        to propagate to the message-level isolation boundary so the
        message remains pending.
        """

        if not isinstance(
            fields,
            dict,
        ):
            print(
                f"[{self.agent_id}] "
                f"Invalid Redis fields | "
                f"Redis={redis_id}"
            )

            await self.redis_client.xack(
                self.input_stream,
                self.group_name,
                redis_id,
            )
            return

        raw_event = fields.get(
            "event"
        )

        if not raw_event:
            print(
                f"[{self.agent_id}] "
                f"Missing event payload | "
                f"Redis={redis_id}"
            )

            await self.redis_client.xack(
                self.input_stream,
                self.group_name,
                redis_id,
            )
            return

        # ----------------------------------------------------
        # Parse JSON.
        # ----------------------------------------------------

        try:
            event = json.loads(
                raw_event
            )

        except (
            TypeError,
            json.JSONDecodeError,
        ) as error:

            print(
                f"[{self.agent_id}] "
                f"Invalid JSON event | "
                f"Redis={redis_id} | "
                f"Error={error}"
            )

            await self.redis_client.xack(
                self.input_stream,
                self.group_name,
                redis_id,
            )
            return

        if not isinstance(
            event,
            dict,
        ):
            print(
                f"[{self.agent_id}] "
                f"Event is not an object | "
                f"Redis={redis_id}"
            )

            await self.redis_client.xack(
                self.input_stream,
                self.group_name,
                redis_id,
            )
            return

        # ----------------------------------------------------
        # Identify event type BEFORE validation.
        #
        # This lets the Behavior Agent decide whether the event
        # should use the envelope-only validation path.
        # ----------------------------------------------------

        event_type = event.get(
            "event_type"
        )

        if not isinstance(
            event_type,
            str,
        ) or not event_type.strip():
            print(
                f"[{self.agent_id}] "
                f"Missing event_type | "
                f"Redis={redis_id}"
            )

            await self.redis_client.xack(
                self.input_stream,
                self.group_name,
                redis_id,
            )
            return

        event_type = event_type.strip()

        # ----------------------------------------------------
        # Canonical envelope validation.
        #
        # IMPORTANT:
        #
        # Do NOT use validate_event(event) here for person.tracked.
        #
        # validate_event() invokes the specialized registry and
        # currently rejects the Tracker producer's payload.
        #
        # BaseEvent.model_validate() validates the canonical
        # envelope without invoking the specialized registry.
        # ----------------------------------------------------

        try:
            validated_event = (
                self._validate_canonical_envelope(
                    event
                )
            )

        except Exception as error:
            print(
                f"[{self.agent_id}] "
                f"Invalid canonical event | "
                f"Redis={redis_id} | "
                f"Error={error}"
            )

            await self.redis_client.xack(
                self.input_stream,
                self.group_name,
                redis_id,
            )
            return

        event = validated_event.to_dict()

        # ----------------------------------------------------
        # Only person.tracked is relevant.
        #
        # Other event types are permanent non-work for this
        # consumer and can be safely ACKed.
        # ----------------------------------------------------

        if event.get(
            "event_type"
        ) != "person.tracked":

            await self.redis_client.xack(
                self.input_stream,
                self.group_name,
                redis_id,
            )
            return

        # ----------------------------------------------------
        # Camera validation.
        # ----------------------------------------------------

        camera_id = self._extract_camera_id(
            event
        )

        if camera_id is None:
            print(
                f"[{self.agent_id}] "
                f"Invalid camera identity | "
                f"Redis={redis_id}"
            )

            await self.redis_client.xack(
                self.input_stream,
                self.group_name,
                redis_id,
            )
            return

        # ----------------------------------------------------
        # Event timestamp.
        # ----------------------------------------------------

        current_event_time = self._event_time(
            event
        )

        if current_event_time is None:
            print(
                f"[{self.agent_id}] "
                f"Missing or invalid timezone-aware "
                f"event timestamp | "
                f"Camera={camera_id} | "
                f"Redis={redis_id}"
            )

            await self.redis_client.xack(
                self.input_stream,
                self.group_name,
                redis_id,
            )
            return

        # ----------------------------------------------------
        # Per-camera ordering protection.
        #
        # This prevents an older event from mutating behavior
        # state after a newer event has already been accepted.
        # ----------------------------------------------------

        previous_camera_time = (
            self.last_event_timestamp.get(
                camera_id
            )
        )

        if (
            previous_camera_time is not None
            and current_event_time
            < previous_camera_time
        ):
            print(
                f"[{self.agent_id}] "
                f"Ignoring out-of-order camera event | "
                f"Camera={camera_id} | "
                f"EventTime="
                f"{current_event_time.isoformat()} | "
                f"LastTime="
                f"{previous_camera_time.isoformat()} | "
                f"Redis={redis_id}"
            )

            await self.redis_client.xack(
                self.input_stream,
                self.group_name,
                redis_id,
            )
            return

        # ----------------------------------------------------
        # Validate current tracking payload.
        # ----------------------------------------------------

        try:
            tracks = (
                self._validate_tracking_payload(
                    event
                )
            )

        except ValueError as error:
            print(
                f"[{self.agent_id}] "
                f"Invalid person.tracked payload | "
                f"Camera={camera_id} | "
                f"Redis={redis_id} | "
                f"Error={error}"
            )

            await self.redis_client.xack(
                self.input_stream,
                self.group_name,
                redis_id,
            )
            return

        # ----------------------------------------------------
        # Cleanup only this camera.
        #
        # This happens after camera-level ordering validation.
        # Therefore an old event cannot accidentally perform
        # cleanup against current state.
        # ----------------------------------------------------

        self.cleanup_camera_tracks(
            camera_id=camera_id,
            current_event_time=current_event_time,
        )

        # ----------------------------------------------------
        # Process all tracks.
        # ----------------------------------------------------

        for track in tracks:

            track_id = str(
                track.get(
                    "track_id"
                )
            ).strip()

            state_key = (
                camera_id,
                track_id,
            )

            state = self.track_state.get(
                state_key
            )

            # ------------------------------------------------
            # New track.
            # ------------------------------------------------

            if state is None:
                state = {
                    "first_seen": (
                        current_event_time
                    ),
                    "last_seen": (
                        current_event_time
                    ),
                    "loitering_emitted": False,
                }

                self.track_state[
                    state_key
                ] = state

            first_seen = state.get(
                "first_seen"
            )

            last_seen = state.get(
                "last_seen"
            )

            if not isinstance(
                first_seen,
                datetime,
            ):
                first_seen = (
                    current_event_time
                )
                state[
                    "first_seen"
                ] = first_seen

            if not isinstance(
                last_seen,
                datetime,
            ):
                last_seen = (
                    current_event_time
                )
                state[
                    "last_seen"
                ] = last_seen

            # ------------------------------------------------
            # Track-level ordering protection.
            # ------------------------------------------------

            if current_event_time < last_seen:
                print(
                    f"[{self.agent_id}] "
                    f"Ignoring out-of-order track event | "
                    f"Camera={camera_id} | "
                    f"Track={track_id} | "
                    f"Redis={redis_id}"
                )
                continue

            # ------------------------------------------------
            # Update observation time.
            # ------------------------------------------------

            state[
                "last_seen"
            ] = current_event_time

            duration = (
                current_event_time
                - first_seen
            ).total_seconds()

            # Defensive protection against malformed clock
            # relationships.
            if duration < 0:
                duration = 0.0

            # ------------------------------------------------
            # Loitering threshold.
            # ------------------------------------------------

            if (
                duration
                >= self.loitering_threshold
                and not state[
                    "loitering_emitted"
                ]
            ):

                behavior_event = (
                    self._build_behavior_event(
                        source_event=event,
                        redis_id=redis_id,
                        camera_id=camera_id,
                        track=track,
                        duration=duration,
                        event_time=current_event_time,
                    )
                )

                # ------------------------------------------------
                # Validate generated event.
                #
                # Here we intentionally use the FULL validation
                # path because loitering.detected should conform
                # to its registered specialized schema.
                # ------------------------------------------------

                try:
                    validate_event(
                        behavior_event
                    )

                except Exception as error:
                    raise ValueError(
                        "Generated loitering event "
                        "failed canonical/specialized "
                        "validation."
                    ) from error

                # ------------------------------------------------
                # Publish FIRST.
                #
                # Only after successful publication do we mark
                # this behavior as emitted.
                # ------------------------------------------------

                output_id = await self.publish(
                    self.output_stream,
                    behavior_event,
                )

                state[
                    "loitering_emitted"
                ] = True

                print(
                    f"[{self.agent_id}] "
                    f"LOITERING | "
                    f"Camera={camera_id} | "
                    f"Track={track_id} | "
                    f"Duration={duration:.1f}s | "
                    f"Mode="
                    f"{event.get('context', {}).get('mode', 'live')} | "
                    f"Redis={output_id}"
                )

        # ----------------------------------------------------
        # Advance camera watermark only after successful
        # processing of the complete message.
        # ----------------------------------------------------

        self.last_event_timestamp[
            camera_id
        ] = current_event_time

        # ----------------------------------------------------
        # ACK only after the complete message has succeeded.
        # ----------------------------------------------------

        await self.redis_client.xack(
            self.input_stream,
            self.group_name,
            redis_id,
        )

    # ========================================================
    # MAIN LOOP
    # ========================================================

    async def run(self):

        if not self.redis_client:
            raise RuntimeError(
                "Redis client is not initialized."
            )

        print(
            f"[{self.agent_id}] "
            "Behavior loop started."
        )

        print(
            f"[{self.agent_id}] "
            f"Consumer: {self.consumer_name}"
        )

        while self.running:

            try:
                messages = await (
                    self.redis_client.xreadgroup(
                        groupname=self.group_name,
                        consumername=self.consumer_name,
                        streams={
                            self.input_stream: ">"
                        },
                        count=10,
                        block=5000,
                    )
                )

                if not messages:
                    continue

                for (
                    _stream_name,
                    entries,
                ) in messages:

                    for (
                        redis_id,
                        fields,
                    ) in entries:

                        try:
                            await self.process_message(
                                redis_id,
                                fields,
                            )

                        except asyncio.CancelledError:
                            raise

                        except Exception as error:
                            # --------------------------------
                            # IMPORTANT:
                            #
                            # Do NOT ACK unexpected processing
                            # failures.
                            #
                            # The message remains pending and
                            # can later be reclaimed by the
                            # reliability layer.
                            #
                            # The failure is isolated to this
                            # message.
                            # --------------------------------

                            print(
                                f"[{self.agent_id}] "
                                f"Message processing failure | "
                                f"Redis={redis_id} | "
                                f"{type(error).__name__}: "
                                f"{error}"
                            )

                            continue

            except asyncio.CancelledError:
                raise

            except Exception as error:
                # --------------------------------------------
                # Redis / loop-level failure.
                #
                # Keep this worker alive for transient Redis
                # failures rather than terminating the entire
                # worker process.
                # --------------------------------------------

                print(
                    f"[{self.agent_id}] "
                    f"Behavior loop error | "
                    f"{type(error).__name__}: "
                    f"{error}"
                )

                await asyncio.sleep(
                    2
                )

        print(
            f"[{self.agent_id}] "
            "Behavior loop stopped."
        )


# ============================================================
# ENTRY POINT
# ============================================================

async def main():
    agent = BehaviorAgent()
    await agent.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
