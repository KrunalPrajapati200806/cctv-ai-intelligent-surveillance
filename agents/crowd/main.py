"""
Crowd Agent

Consumes canonical ``person.tracked`` events and detects crowd conditions.

Pipeline:

    events.tracking
          |
          v
      CrowdAgent
          |
          v
    events.behavior
          |
          +--> crowd.detected

Design principles:
- Canonical event envelope
- Camera-scoped state isolation
- Historical-mode timestamp correctness
- Out-of-order event protection
- No runtime/background mutation of event-time state
- Trace/correlation/incident propagation
- Source-event lineage
- Per-message fault isolation
- ACK only after successful processing
- No silent camera fallback
- Same-camera routing/affinity required for stateful workers

Important:
Crowd state is driven ONLY by incoming tracking observations.

A background asyncio task must never fabricate observations by calling
update_crowd_state(). This is especially important for historical processing,
where wall-clock time has no relationship to the footage timeline.

NOTE:
Redis consumer groups do not inherently guarantee camera affinity. The
deployment topology must eventually partition/rout events so all events for
one camera are processed by the same state owner.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from shared.agent.base_agent import BaseAgent
from shared.schemas.event_schema import create_event, validate_event


class CrowdAgent(BaseAgent):
    """
    Stateful crowd analysis agent.

    Input:
        events.tracking

    Output:
        events.behavior

    Detection:
        crowd.detected

    State is partitioned by camera_id.

    This worker must eventually receive all events for a given camera
    through the same state owner.
    """

    INPUT_EVENT_TYPE = "person.tracked"
    OUTPUT_EVENT_TYPE = "crowd.detected"

    def __init__(self):
        super().__init__(
            agent_id=os.getenv("AGENT_ID", "crowd-01"),
            heartbeat_interval=int(
                os.getenv("HEARTBEAT_INTERVAL", "10")
            ),
        )

        self.input_stream = os.getenv(
            "CROWD_INPUT_STREAM",
            "events.tracking",
        )

        self.output_stream = os.getenv(
            "CROWD_OUTPUT_STREAM",
            "events.behavior",
        )

        self.group_name = os.getenv(
            "CROWD_GROUP",
            "crowd-workers",
        )

        self.consumer_name = os.getenv(
            "CROWD_CONSUMER",
            f"crowd-{uuid.uuid4().hex[:8]}",
        )

        self.crowd_threshold = self._positive_int(
            os.getenv("CROWD_THRESHOLD", "5"),
            "CROWD_THRESHOLD",
        )

        self.track_timeout = self._positive_float(
            os.getenv("TRACK_TIMEOUT_SECONDS", "0.8"),
            "TRACK_TIMEOUT_SECONDS",
        )

        self.activation_observations = self._positive_int(
            os.getenv(
                "CROWD_ACTIVATION_OBSERVATIONS",
                "1",
            ),
            "CROWD_ACTIVATION_OBSERVATIONS",
        )

        self.clear_observations = self._positive_int(
            os.getenv(
                "CROWD_CLEAR_OBSERVATIONS",
                "1",
            ),
            "CROWD_CLEAR_OBSERVATIONS",
        )

        # ------------------------------------------------------------
        # Camera-scoped track state
        #
        # {
        #     "CAM01": {
        #         "track-1": datetime(...),
        #         "track-2": datetime(...),
        #     }
        # }
        #
        # ------------------------------------------------------------

        self.camera_tracks: Dict[
            str,
            Dict[str, datetime],
        ] = {}

        # ------------------------------------------------------------
        # Camera-scoped crowd state
        #
        # {
        #     "CAM01": {
        #         "active": False,
        #         "above_threshold_observations": 0,
        #         "below_threshold_observations": 0,
        #         "event_emitted": False,
        #         "last_processed_timestamp": datetime | None,
        #         "last_event_timestamp": datetime | None,
        #     }
        # }
        #
        # last_processed_timestamp:
        #     Last accepted tracking observation for this camera.
        #
        # last_event_timestamp:
        #     Timestamp associated with the last emitted crowd event.
        #
        # Keeping these separate avoids coupling event emission with
        # event ordering.
        # ------------------------------------------------------------

        self.crowd_state: Dict[
            str,
            Dict[str, Any],
        ] = {}

    # ================================================================
    # CONFIGURATION
    # ================================================================

    @staticmethod
    def _positive_int(
        value: str,
        name: str,
    ) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"{name} must be an integer"
            ) from error

        if parsed <= 0:
            raise ValueError(
                f"{name} must be greater than 0"
            )

        return parsed

    @staticmethod
    def _positive_float(
        value: str,
        name: str,
    ) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"{name} must be a number"
            ) from error

        if parsed <= 0:
            raise ValueError(
                f"{name} must be greater than 0"
            )

        if not math.isfinite(parsed):
            raise ValueError(
                f"{name} must be finite"
            )

        return parsed

    # ================================================================
    # TIMESTAMP
    # ================================================================

    @staticmethod
    def _parse_timestamp(
        value: Any,
        field_name: str,
    ) -> datetime:
        """
        Parse an ISO timestamp and normalize it to UTC.

        Naive timestamps are rejected.

        The canonical event schema requires timezone-aware timestamps.
        Silently treating a naive timestamp as UTC can corrupt historical
        event ordering, so this agent deliberately rejects it.
        """

        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"{field_name} must be a non-empty ISO timestamp"
            )

        normalized = value.strip()

        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"

        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as error:
            raise ValueError(
                f"Invalid {field_name}: {value}"
            ) from error

        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError(
                f"{field_name} must be timezone-aware"
            )

        return parsed.astimezone(timezone.utc)

    def _event_timestamp(
        self,
        event: Dict[str, Any],
        data: Dict[str, Any],
    ) -> datetime:
        """
        Determine the timestamp representing the tracking observation.

        Prefer data.frame_timestamp because it represents the source
        frame's processing/observation time.

        Fall back to the canonical event timestamp.
        """

        frame_timestamp = data.get("frame_timestamp")

        if frame_timestamp is not None:
            return self._parse_timestamp(
                frame_timestamp,
                "data.frame_timestamp",
            )

        return self._parse_timestamp(
            event.get("timestamp"),
            "event.timestamp",
        )

    # ================================================================
    # CAMERA STATE
    # ================================================================

    def _ensure_camera_state(
        self,
        camera_id: str,
    ) -> None:
        """
        Create state for a camera without affecting any other camera.
        """

        if camera_id not in self.camera_tracks:
            self.camera_tracks[camera_id] = {}

        if camera_id not in self.crowd_state:
            self.crowd_state[camera_id] = {
                "active": False,
                "above_threshold_observations": 0,
                "below_threshold_observations": 0,
                "event_emitted": False,
                "last_processed_timestamp": None,
                "last_event_timestamp": None,
            }

    # ================================================================
    # TRACK CLEANUP
    # ================================================================

    def remove_expired_tracks(
        self,
        camera_id: str,
        event_timestamp: datetime,
    ) -> None:
        """
        Remove tracks that have not appeared within track_timeout.

        This function is called ONLY when a new tracking observation
        arrives.

        It uses event time, never wall-clock time.

        Therefore it works for:
        - live streams
        - historical footage
        - replayed footage
        """

        tracks = self.camera_tracks.get(camera_id)

        if not tracks:
            return

        expired_tracks: List[str] = []

        for track_id, last_seen in list(tracks.items()):
            age = (
                event_timestamp - last_seen
            ).total_seconds()

            # An older observation must never cause a track to expire.
            if age < 0:
                continue

            if age > self.track_timeout:
                expired_tracks.append(track_id)

        for track_id in expired_tracks:
            tracks.pop(track_id, None)

        if expired_tracks:
            print(
                f"[{self.agent_id}] "
                f"Expired tracks | "
                f"Camera={camera_id} | "
                f"Count={len(expired_tracks)}"
            )

    def get_person_count(
        self,
        camera_id: str,
    ) -> int:
        """
        Return the number of currently active tracks for one camera.
        """

        return len(
            self.camera_tracks.get(
                camera_id,
                {},
            )
        )

    # ================================================================
    # SEVERITY
    # ================================================================

    def calculate_severity(
        self,
        person_count: int,
    ) -> str:
        """
        Convert person count into crowd severity.

        These thresholds are currently configuration-independent
        MVP defaults and can later become camera-policy driven.
        """

        if person_count >= 10:
            return "critical"

        if person_count >= 7:
            return "high"

        if person_count >= 5:
            return "medium"

        return "low"

    # ================================================================
    # CROWD STATE
    # ================================================================

    def update_crowd_state(
        self,
        camera_id: str,
        person_count: int,
    ) -> Dict[str, Any]:
        """
        Update crowd state using exactly ONE accepted observation.

        This function must NEVER be called by a periodic cleanup task.
        Each invocation represents an actual tracking observation.
        """

        if person_count < 0:
            raise ValueError(
                "person_count cannot be negative"
            )

        self._ensure_camera_state(camera_id)

        state = self.crowd_state[camera_id]

        if person_count >= self.crowd_threshold:
            state["above_threshold_observations"] += 1
            state["below_threshold_observations"] = 0

            if (
                not state["active"]
                and state["above_threshold_observations"]
                >= self.activation_observations
            ):
                state["active"] = True

                print(
                    f"[{self.agent_id}] "
                    f"Crowd condition ACTIVE | "
                    f"Camera={camera_id} | "
                    f"Count={person_count}"
                )

        else:
            state["below_threshold_observations"] += 1
            state["above_threshold_observations"] = 0

            if (
                state["active"]
                and state["below_threshold_observations"]
                >= self.clear_observations
            ):
                state["active"] = False

                print(
                    f"[{self.agent_id}] "
                    f"Crowd condition CLEARED | "
                    f"Camera={camera_id} | "
                    f"Count={person_count}"
                )

        return state

    # ================================================================
    # EVENT BUILDING
    # ================================================================

    def build_crowd_event(
        self,
        source_event: Dict[str, Any],
        redis_id: str,
        camera_id: str,
        frame_id: Any,
        frame_timestamp: datetime,
        person_count: int,
        active_track_ids: List[str],
    ) -> Dict[str, Any]:
        """
        Build one canonical crowd.detected event.

        The specialized payload registry is intentionally not invoked
        here yet because the project's person/tracked and crowd
        contracts are still being aligned with all producers.
        """

        source = source_event.get("source", {})
        context = source_event.get("context", {})

        if not isinstance(source, dict):
            source = {}

        if not isinstance(context, dict):
            context = {}

        mode = context.get("mode", "live")

        if mode not in {"live", "historical"}:
            raise ValueError(
                f"Invalid event context mode: {mode!r}"
            )

        trace_id = context.get("trace_id")

        if not isinstance(trace_id, str) or not trace_id.strip():
            raise ValueError(
                "Source event context.trace_id is required"
            )

        severity = self.calculate_severity(
            person_count
        )

        frame_timestamp_text = (
            frame_timestamp.isoformat()
        )

        event = create_event(
            event_type=self.OUTPUT_EVENT_TYPE,
            agent_id=self.agent_id,
            instance_id=self.instance_id,
            hostname=self.hostname,
            camera_id=camera_id,
            mode=mode,
            trace_id=trace_id,
            correlation_id=context.get(
                "correlation_id"
            ),
            incident_id=context.get(
                "incident_id"
            ),
            timestamp=frame_timestamp,
            data={
                "frame_id": frame_id,
                "frame_timestamp": frame_timestamp_text,
                "person_count": person_count,

                # Compatibility field.
                #
                # This is NOT physical crowd density.
                # Physical density requires scene geometry,
                # calibration and/or an occupied-area estimate.
                "density": float(person_count),

                "threshold": self.crowd_threshold,
                "severity": severity,
                "track_ids": active_track_ids,

                # Source lineage.
                "source_event_id": source_event.get(
                    "event_id"
                ),
                "source_redis_id": redis_id,

                # Provenance.
                "source_agent_id": source.get(
                    "agent_id"
                ),
                "source_instance_id": source.get(
                    "instance_id"
                ),
            },
        )

        # Validate the canonical envelope.
        #
        # Specialized payload validation will be enabled once all
        # event contracts are aligned with their actual producers.
        validate_event(event)

        return event

    # ================================================================
    # EMIT
    # ================================================================

    async def emit_crowd_event(
        self,
        source_event: Dict[str, Any],
        redis_id: str,
        camera_id: str,
        frame_id: Any,
        frame_timestamp: datetime,
        person_count: int,
    ) -> Optional[str]:
        """
        Emit exactly one crowd.detected event for the current
        active crowd condition.

        event_emitted is changed ONLY after Redis publish succeeds.
        """

        self._ensure_camera_state(camera_id)

        state = self.crowd_state[camera_id]

        if not state.get("active", False):
            return None

        if state.get("event_emitted", False):
            return None

        active_track_ids = list(
            self.camera_tracks.get(
                camera_id,
                {},
            ).keys()
        )

        crowd_event = self.build_crowd_event(
            source_event=source_event,
            redis_id=redis_id,
            camera_id=camera_id,
            frame_id=frame_id,
            frame_timestamp=frame_timestamp,
            person_count=person_count,
            active_track_ids=active_track_ids,
        )

        # If publish fails, this exception propagates.
        #
        # The state remains event_emitted=False, allowing the pending
        # source message to be retried without permanently losing the
        # crowd event.
        output_id = await self.publish(
            self.output_stream,
            crowd_event,
        )

        # Mark emitted ONLY after successful Redis publish.
        state["event_emitted"] = True
        state["last_event_timestamp"] = frame_timestamp

        print(
            f"[{self.agent_id}] "
            f"CROWD DETECTED | "
            f"Camera={camera_id} | "
            f"Count={person_count} | "
            f"Threshold={self.crowd_threshold} | "
            f"Severity={crowd_event['data']['severity']} | "
            f"Tracks={active_track_ids} | "
            f"Redis={output_id}"
        )

        return output_id

    # ================================================================
    # TRACKING EVENT VALIDATION
    # ================================================================

    @staticmethod
    def _validate_tracking_payload(
        data: Dict[str, Any],
    ) -> None:
        """
        Validate the currently produced person.tracked payload.

        The current Tracker emits:
            frame_id
            frame_timestamp
            tracks[]

        Each track contains at minimum:
            track_id
            detection_id
            bbox
            confidence
            center

        Additional Tracker fields are allowed because the canonical
        specialized contract is still being aligned with producers.
        """

        if "frame_id" not in data:
            raise ValueError(
                "person.tracked event missing frame_id"
            )

        tracks = data.get("tracks", [])

        if not isinstance(tracks, list):
            raise ValueError(
                "person.tracked tracks must be a list"
            )

        for index, track in enumerate(tracks):
            if not isinstance(track, dict):
                raise ValueError(
                    f"Track at index {index} must be an object"
                )

            track_id = track.get("track_id")

            if (
                not isinstance(track_id, str)
                or not track_id.strip()
            ):
                raise ValueError(
                    f"Track at index {index} has invalid track_id"
                )

            bbox = track.get("bbox")

            if (
                not isinstance(bbox, list)
                or len(bbox) != 4
            ):
                raise ValueError(
                    f"Track {track_id!r} must contain "
                    f"a 4-value bbox"
                )

            for value in bbox:
                if (
                    not isinstance(value, (int, float))
                    or isinstance(value, bool)
                    or not math.isfinite(float(value))
                ):
                    raise ValueError(
                        f"Track {track_id!r} contains "
                        f"invalid bbox values"
                    )

            confidence = track.get("confidence")

            if (
                not isinstance(confidence, (int, float))
                or isinstance(confidence, bool)
                or not math.isfinite(float(confidence))
                or not 0 <= float(confidence) <= 1
            ):
                raise ValueError(
                    f"Track {track_id!r} has invalid confidence"
                )

            center = track.get("center")

            if (
                not isinstance(center, list)
                or len(center) != 2
            ):
                raise ValueError(
                    f"Track {track_id!r} must contain "
                    f"a 2-value center"
                )

            for value in center:
                if (
                    not isinstance(value, (int, float))
                    or isinstance(value, bool)
                    or not math.isfinite(float(value))
                ):
                    raise ValueError(
                        f"Track {track_id!r} contains "
                        f"invalid center values"
                    )

    # ================================================================
    # PROCESS TRACKING EVENT
    # ================================================================

    async def process_tracking_event(
        self,
        redis_id: str,
        event: Dict[str, Any],
    ) -> None:
        """
        Process one canonical person.tracked event.

        State mutation is camera-scoped and event-time ordered.
        """

        # Envelope validation.
        validate_event(event)

        if event.get("event_type") != self.INPUT_EVENT_TYPE:
            return

        # ------------------------------------------------------------
        # Camera
        # ------------------------------------------------------------

        camera = event.get("camera")

        if not isinstance(camera, dict):
            raise ValueError(
                "person.tracked event missing camera object"
            )

        camera_id = camera.get("camera_id")

        if (
            not isinstance(camera_id, str)
            or not camera_id.strip()
        ):
            raise ValueError(
                "person.tracked event missing valid camera_id"
            )

        camera_id = camera_id.strip()

        # ------------------------------------------------------------
        # Data
        # ------------------------------------------------------------

        data = event.get("data")

        if not isinstance(data, dict):
            raise ValueError(
                "person.tracked event data must be an object"
            )

        self._validate_tracking_payload(data)

        frame_id = data.get("frame_id")

        # ------------------------------------------------------------
        # Event timestamp
        # ------------------------------------------------------------

        event_timestamp = self._event_timestamp(
            event,
            data,
        )

        self._ensure_camera_state(camera_id)

        state = self.crowd_state[camera_id]

        # ------------------------------------------------------------
        # Out-of-order protection
        # ------------------------------------------------------------

        last_processed_timestamp = state.get(
            "last_processed_timestamp"
        )

        if (
            isinstance(
                last_processed_timestamp,
                datetime,
            )
            and event_timestamp < last_processed_timestamp
        ):
            print(
                f"[{self.agent_id}] "
                f"Ignoring out-of-order event | "
                f"Camera={camera_id} | "
                f"EventTime={event_timestamp.isoformat()} | "
                f"LastTime="
                f"{last_processed_timestamp.isoformat()} | "
                f"Redis={redis_id}"
            )

            # This is not a processing failure.
            # The event is valid but obsolete for this state owner.
            return

        # ------------------------------------------------------------
        # Remove tracks that disappeared before this observation.
        # ------------------------------------------------------------

        self.remove_expired_tracks(
            camera_id=camera_id,
            event_timestamp=event_timestamp,
        )

        # ------------------------------------------------------------
        # Update current tracks.
        # ------------------------------------------------------------

        camera_tracks = self.camera_tracks[camera_id]

        tracked_items = data.get(
            "tracks",
            [],
        )

        for tracked_item in tracked_items:
            track_id = str(
                tracked_item["track_id"]
            ).strip()

            previous_timestamp = camera_tracks.get(
                track_id
            )

            # Never move an individual track backward in time.
            if (
                previous_timestamp is not None
                and event_timestamp < previous_timestamp
            ):
                continue

            camera_tracks[track_id] = event_timestamp

        # ------------------------------------------------------------
        # Current camera state
        # ------------------------------------------------------------

        person_count = self.get_person_count(
            camera_id
        )

        active_track_ids = list(
            camera_tracks.keys()
        )

        print(
            f"[{self.agent_id}] "
            f"Camera={camera_id} | "
            f"Time={event_timestamp.isoformat()} | "
            f"ActivePersons={person_count} | "
            f"Tracks={active_track_ids}"
        )

        # ------------------------------------------------------------
        # One accepted observation -> one state update.
        # ------------------------------------------------------------

        state = self.update_crowd_state(
            camera_id=camera_id,
            person_count=person_count,
        )

        # Advance event-time cursor only after the observation has
        # successfully passed validation and state processing.
        state["last_processed_timestamp"] = event_timestamp

        # ------------------------------------------------------------
        # Crowd activation
        # ------------------------------------------------------------

        if (
            person_count >= self.crowd_threshold
            and state.get("active", False)
            and not state.get("event_emitted", False)
        ):
            await self.emit_crowd_event(
                source_event=event,
                redis_id=redis_id,
                camera_id=camera_id,
                frame_id=frame_id,
                frame_timestamp=event_timestamp,
                person_count=person_count,
            )

        # ------------------------------------------------------------
        # Crowd cleared
        #
        # Once inactive, the next future crowd condition is allowed
        # to emit another crowd.detected event.
        # ------------------------------------------------------------

        elif not state.get("active", False):
            state["event_emitted"] = False

    # ================================================================
    # REDIS GROUP
    # ================================================================

    async def on_start(self):
        """
        Create the Redis consumer group.

        No background task mutates event-time state.
        """

        try:
            await self.redis_client.xgroup_create(
                name=self.input_stream,
                groupname=self.group_name,
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
            f"Crowd agent ready."
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
            f"Crowd threshold: "
            f"{self.crowd_threshold}"
        )

        print(
            f"[{self.agent_id}] "
            f"Track timeout: "
            f"{self.track_timeout}s"
        )

        print(
            f"[{self.agent_id}] "
            f"Activation observations: "
            f"{self.activation_observations}"
        )

        print(
            f"[{self.agent_id}] "
            f"Clear observations: "
            f"{self.clear_observations}"
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
            f"Consumer: {self.consumer_name}"
        )

    # ================================================================
    # STOP
    # ================================================================

    async def on_stop(self):
        """
        Clear in-memory state on graceful shutdown.

        State is intentionally not persisted here yet.
        Persistent/checkpointed state can be added later if required.
        """

        self.camera_tracks.clear()
        self.crowd_state.clear()

        print(
            f"[{self.agent_id}] "
            f"Crowd state cleared."
        )

    # ================================================================
    # REDIS MESSAGE ACK
    # ================================================================

    async def _ack(
        self,
        redis_id: str,
    ) -> None:
        """
        ACK one message.

        ACK failures are allowed to propagate because an ACK failure
        means Redis still considers the message pending.
        """

        await self.redis_client.xack(
            self.input_stream,
            self.group_name,
            redis_id,
        )

    # ================================================================
    # MAIN REDIS LOOP
    # ================================================================

    async def run(self):
        """
        Consume new tracking events.

        Reliability semantics:

        Permanent poison message:
            ACK it so it does not block the worker forever.

        Successful processing:
            ACK it.

        Unexpected processing failure:
            DO NOT ACK.
            Message remains pending for recovery.

        Redis/network failure:
            Keep the worker alive and retry.
        """

        print(
            f"[{self.agent_id}] "
            f"Crowd processing loop started."
        )

        while self.running:
            try:
                messages = await self.redis_client.xreadgroup(
                    groupname=self.group_name,
                    consumername=self.consumer_name,
                    streams={
                        self.input_stream: ">"
                    },
                    count=10,
                    block=5000,
                )

                if not messages:
                    continue

                for _, stream_messages in messages:
                    for redis_id, fields in stream_messages:
                        try:
                            # ------------------------------------------------
                            # Redis fields
                            # ------------------------------------------------

                            if not isinstance(fields, dict):
                                print(
                                    f"[{self.agent_id}] "
                                    f"Invalid Redis fields | "
                                    f"Redis={redis_id}"
                                )

                                await self._ack(redis_id)
                                continue

                            raw_event = fields.get("event")

                            # ------------------------------------------------
                            # Missing payload
                            # ------------------------------------------------

                            if not raw_event:
                                print(
                                    f"[{self.agent_id}] "
                                    f"Missing event payload | "
                                    f"Redis={redis_id}"
                                )

                                # Permanent poison message.
                                await self._ack(redis_id)
                                continue

                            # ------------------------------------------------
                            # JSON
                            # ------------------------------------------------

                            try:
                                event = json.loads(raw_event)

                            except (
                                TypeError,
                                json.JSONDecodeError,
                            ) as error:
                                print(
                                    f"[{self.agent_id}] "
                                    f"Invalid JSON | "
                                    f"Redis={redis_id} | "
                                    f"Error={error}"
                                )

                                # Permanent poison message.
                                await self._ack(redis_id)
                                continue

                            if not isinstance(event, dict):
                                print(
                                    f"[{self.agent_id}] "
                                    f"Event must be JSON object | "
                                    f"Redis={redis_id}"
                                )

                                # Permanent poison message.
                                await self._ack(redis_id)
                                continue

                            # ------------------------------------------------
                            # Event type
                            # ------------------------------------------------

                            if (
                                event.get("event_type")
                                != self.INPUT_EVENT_TYPE
                            ):
                                # The stream may eventually contain other
                                # tracking events. They are not this
                                # consumer's responsibility.
                                await self._ack(redis_id)
                                continue

                            # ------------------------------------------------
                            # Processing
                            # ------------------------------------------------

                            await self.process_tracking_event(
                                redis_id=redis_id,
                                event=event,
                            )

                            # ------------------------------------------------
                            # ACK only after successful processing.
                            # ------------------------------------------------

                            await self._ack(redis_id)

                        except asyncio.CancelledError:
                            raise

                        except ValueError as error:
                            # ------------------------------------------------
                            # ValueError here represents a permanently
                            # malformed/invalid event according to the
                            # current CrowdAgent contract.
                            #
                            # ACK prevents a poison message from being
                            # retried forever.
                            # ------------------------------------------------

                            print(
                                f"[{self.agent_id}] "
                                f"Permanent event validation error | "
                                f"Redis={redis_id} | "
                                f"{type(error).__name__}: "
                                f"{error}"
                            )

                            try:
                                await self._ack(redis_id)
                            except Exception as ack_error:
                                print(
                                    f"[{self.agent_id}] "
                                    f"ACK failed after permanent "
                                    f"validation error | "
                                    f"Redis={redis_id} | "
                                    f"{type(ack_error).__name__}: "
                                    f"{ack_error}"
                                )

                        except Exception as error:
                            print(
                                f"[{self.agent_id}] "
                                f"Message processing error | "
                                f"Redis={redis_id} | "
                                f"{type(error).__name__}: "
                                f"{error}"
                            )

                            # IMPORTANT:
                            #
                            # Do NOT ACK unexpected processing failures.
                            #
                            # The message remains pending and can later
                            # be recovered by the Redis reliability layer.
                            continue

            except asyncio.CancelledError:
                raise

            except Exception as error:
                print(
                    f"[{self.agent_id}] "
                    f"Crowd loop error | "
                    f"{type(error).__name__}: "
                    f"{error}"
                )

                # Redis/network failure must not terminate this worker.
                await asyncio.sleep(2)

        print(
            f"[{self.agent_id}] "
            f"Crowd processing loop stopped."
        )


# ====================================================================
# ENTRY POINT
# ====================================================================

async def main():
    agent = CrowdAgent()
    await agent.run_forever()


if __name__ == "__main__":
    asyncio.run(main())