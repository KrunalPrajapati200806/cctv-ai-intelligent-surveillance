from __future__ import annotations

import asyncio
import json
import math
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from shared.agent.base_agent import BaseAgent
from shared.schemas.event_schema import create_event


class PersonTrackerAgent(BaseAgent):
    """
    Stateful person-tracking worker.

    Pipeline:

        events.detection
              |
              | person.detected
              v
        PersonTrackerAgent
              |
              | person.tracked
              v
        events.tracking

    IMPORTANT:

        Tracking state is maintained per camera.

        Therefore, in production, all events belonging to the
        same camera MUST be routed to the same tracker worker/
        partition. A generic Redis consumer group can otherwise
        distribute events from one camera across multiple workers
        and break tracking continuity.

    Current tracker implementation:

        Center-distance nearest-neighbour tracker.

    This is intentionally kept behind a simple internal interface
    so it can later be replaced by ByteTrack / BoT-SORT without
    changing the event contract.
    """

    INPUT_STREAM = "events.detection"
    HISTORICAL_INPUT_STREAM = "events.detection.historical"
    OUTPUT_STREAM = "events.tracking"

    INPUT_EVENT_TYPE = "person.detected"
    OUTPUT_EVENT_TYPE = "person.tracked"

    def __init__(self):
        super().__init__(
            agent_id=os.getenv(
                "AGENT_ID",
                "tracker-01",
            ),
            heartbeat_interval=int(
                os.getenv(
                    "HEARTBEAT_INTERVAL",
                    "10",
                )
            ),
        )

        self.input_stream = self.INPUT_STREAM
        self.output_stream = self.OUTPUT_STREAM
        self.input_stream = os.getenv(
            "TRACKER_INPUT_STREAM",
            self.input_stream,
        ).strip()

        self.camera_id = os.getenv(
            "CAMERA_ID",
            "",
        ).strip()

        self.mode = os.getenv(
            "TRACKER_MODE",
            "live",
        ).strip().lower()

        if self.mode not in {
            "live",
            "historical",
        }:
            raise ValueError(
                "TRACKER_MODE must be 'live' or 'historical'."
            )

        if self.mode == "historical":
            self.input_stream = os.getenv(
                "TRACKER_INPUT_STREAM",
                self.HISTORICAL_INPUT_STREAM,
            ).strip()

        self.group_name = os.getenv(
            "TRACKER_GROUP",
            (
                "tracker-workers"
                if self.mode == "live"
                else "tracker-workers-historical"
            ),
        ).strip()

        self.consumer_name = os.getenv(
            "TRACKER_CONSUMER",
            f"tracker-{uuid.uuid4().hex[:8]}",
        ).strip()

        try:
            self.distance_threshold = float(
                os.getenv(
                    "TRACK_DISTANCE_THRESHOLD",
                    "160",
                )
            )
        except ValueError as error:
            raise ValueError(
                "TRACK_DISTANCE_THRESHOLD must be a valid number."
            ) from error

        if self.distance_threshold <= 0:
            raise ValueError(
                "TRACK_DISTANCE_THRESHOLD must be greater than 0."
            )

        try:
            self.track_timeout = float(
                os.getenv(
                    "TRACK_TIMEOUT",
                    "0.8",
                )
            )
        except ValueError as error:
            raise ValueError(
                "TRACK_TIMEOUT must be a valid number."
            ) from error

        if self.track_timeout <= 0:
            raise ValueError(
                "TRACK_TIMEOUT must be greater than 0."
            )

        try:
            self.live_event_max_age = float(
                os.getenv(
                    "LIVE_EVENT_MAX_AGE",
                    "5",
                )
            )
        except ValueError as error:
            raise ValueError(
                "LIVE_EVENT_MAX_AGE must be a valid number."
            ) from error

        if self.live_event_max_age <= 0:
            raise ValueError(
                "LIVE_EVENT_MAX_AGE must be greater than 0."
            )

        try:
            self.pending_claim_idle_ms = int(
                os.getenv(
                    "TRACKER_PENDING_CLAIM_IDLE_MS",
                    "30000",
                )
            )
        except ValueError as error:
            raise ValueError(
                "TRACKER_PENDING_CLAIM_IDLE_MS must be a valid integer."
            ) from error

        if self.pending_claim_idle_ms < 0:
            raise ValueError(
                "TRACKER_PENDING_CLAIM_IDLE_MS cannot be negative."
            )

        self.dedupe_ttl_seconds = int(
            os.getenv(
                "TRACKER_DEDUPE_TTL_SECONDS",
                "86400",
            )
        )

        if self.dedupe_ttl_seconds <= 0:
            raise ValueError(
                "TRACKER_DEDUPE_TTL_SECONDS must be greater than 0."
            )

        # ---------------------------------------------------------
        # Per-camera tracking state.
        #
        # {
        #     camera_id: {
        #         track_id: {
        #             center: [x, y],
        #             bbox: [x1, y1, x2, y2],
        #             last_seen_event_time: datetime,
        #             last_seen_runtime: float,
        #             age: int,
        #         }
        #     }
        # }
        # ---------------------------------------------------------

        self.tracks: dict[
            str,
            dict[str, dict[str, Any]],
        ] = {}

        print(
            f"[{self.agent_id}] "
            f"Initialized tracker."
        )

        print(
            f"[{self.agent_id}] "
            f"Consumer: {self.consumer_name}"
        )

        print(
            f"[{self.agent_id}] "
            f"Group: {self.group_name}"
        )

    # =========================================================
    # Lifecycle
    # =========================================================

    async def on_start(self):
        if not self.redis_client:
            raise RuntimeError(
                "Redis client is not initialized."
            )

        try:
            await self.redis_client.xgroup_create(
                self.input_stream,
                self.group_name,
                id="$" if self.mode == "live" else "0",
                mkstream=True,
            )

        except Exception as error:
            if "BUSYGROUP" not in str(error):
                raise

        print(
            f"[{self.agent_id}] "
            f"Tracker ready."
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
            f"Camera-affine state tracking enabled."
        )

    async def on_stop(self):
        self.tracks.clear()

        print(
            f"[{self.agent_id}] "
            f"Tracker state cleared."
        )

    # =========================================================
    # Geometry
    # =========================================================

    @staticmethod
    def distance(
        center_a: list[float],
        center_b: list[float],
    ) -> float:
        return math.sqrt(
            (center_a[0] - center_b[0]) ** 2
            + (center_a[1] - center_b[1]) ** 2
        )

    @staticmethod
    def bbox_center(
        bbox: list[float],
    ) -> list[float]:
        return [
            (bbox[0] + bbox[2]) / 2.0,
            (bbox[1] + bbox[3]) / 2.0,
        ]

    # =========================================================
    # Timestamp handling
    # =========================================================

    @staticmethod
    def _parse_timestamp(
        value: Any,
    ) -> datetime | None:
        """
        Parse an event timestamp into timezone-aware UTC.

        The tracker must use event time rather than process/runtime
        time so that historical footage remains temporally correct.
        """

        if isinstance(value, datetime):
            timestamp = value

        elif isinstance(value, str):
            text = value.strip()

            if not text:
                return None

            try:
                timestamp = datetime.fromisoformat(
                    text.replace(
                        "Z",
                        "+00:00",
                    )
                )
            except ValueError:
                return None

        else:
            return None

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(
                tzinfo=timezone.utc
            )

        return timestamp.astimezone(
            timezone.utc
        )

    def _is_stale_live_event(
        self,
        event_timestamp: datetime,
        now: datetime | None = None,
    ) -> bool:
        """Return whether a live event is too old to affect live state."""
        if self.mode != "live":
            return False

        current_time = now or datetime.now(timezone.utc)
        age = (
            current_time - event_timestamp
        ).total_seconds()

        return age > self.live_event_max_age

    # =========================================================
    # Track cleanup
    # =========================================================

    def cleanup_tracks(
        self,
        camera_id: str,
        event_timestamp: datetime,
    ):
        """
        Remove tracks that have not been seen within TRACK_TIMEOUT.

        Uses event timestamps rather than asyncio monotonic time.

        This is important for:

            live mode
            historical mode
            replay
            deterministic testing
        """

        camera_tracks = self.tracks.get(
            camera_id
        )

        if not camera_tracks:
            return

        stale_ids: list[str] = []

        for track_id, track in camera_tracks.items():
            last_seen = track.get(
                "last_seen_event_time"
            )

            if not isinstance(
                last_seen,
                datetime,
            ):
                stale_ids.append(track_id)
                continue

            elapsed = (
                event_timestamp - last_seen
            ).total_seconds()

            # If events arrive out of chronological order,
            # do not delete a track merely because the current
            # event timestamp is older.
            if elapsed >= self.track_timeout:
                stale_ids.append(track_id)

        for track_id in stale_ids:
            camera_tracks.pop(
                track_id,
                None,
            )

        if not camera_tracks:
            self.tracks.pop(
                camera_id,
                None,
            )

    # =========================================================
    # Tracking
    # =========================================================

    def update_tracks(
        self,
        camera_id: str,
        detections: list[dict[str, Any]],
        event_timestamp: datetime,
    ) -> list[dict[str, Any]]:
        """
        Update tracks for one camera.

        IMPORTANT:

            This function assumes all events for camera_id are
            processed by the same tracker worker.

        The matching strategy is:

            detection -> nearest unmatched existing track

        If no track is close enough, a new track is created.
        """

        if camera_id not in self.tracks:
            self.tracks[camera_id] = {}

        camera_tracks = self.tracks[camera_id]

        self.cleanup_tracks(
            camera_id,
            event_timestamp,
        )

        camera_tracks = self.tracks.setdefault(
            camera_id,
            {},
        )

        matched_track_ids: set[str] = set()

        output_tracks: list[dict[str, Any]] = []

        for detection in detections:
            if not isinstance(
                detection,
                dict,
            ):
                continue

            detection_id = detection.get(
                "detection_id"
            )

            bbox = detection.get(
                "bbox"
            )

            confidence = detection.get(
                "confidence"
            )

            if not detection_id:
                continue

            if (
                not isinstance(
                    bbox,
                    list,
                )
                or len(bbox) != 4
            ):
                continue

            try:
                bbox = [
                    float(value)
                    for value in bbox
                ]

                confidence = float(
                    confidence
                )

            except (
                TypeError,
                ValueError,
            ):
                continue

            x1, y1, x2, y2 = bbox

            if x2 < x1 or y2 < y1:
                continue

            center = self.bbox_center(
                bbox
            )

            best_track_id: str | None = None
            best_distance = float("inf")

            for (
                track_id,
                track,
            ) in camera_tracks.items():

                if track_id in matched_track_ids:
                    continue

                previous_center = track.get(
                    "center"
                )

                if (
                    not isinstance(
                        previous_center,
                        list,
                    )
                    or len(previous_center) != 2
                ):
                    continue

                candidate_distance = self.distance(
                    center,
                    previous_center,
                )

                if (
                    candidate_distance
                    <= self.distance_threshold
                    and candidate_distance
                    < best_distance
                ):
                    best_distance = candidate_distance
                    best_track_id = track_id

            # -------------------------------------------------
            # Create new track
            # -------------------------------------------------

            if best_track_id is None:
                best_track_id = (
                    f"track-"
                    f"{uuid.uuid4().hex}"
                )

                camera_tracks[
                    best_track_id
                ] = {
                    "track_id": best_track_id,
                    "center": center,
                    "bbox": bbox,
                    "last_seen_event_time": (
                        event_timestamp
                    ),
                    "age": 1,
                }

            # -------------------------------------------------
            # Update existing track
            # -------------------------------------------------

            else:
                track = camera_tracks[
                    best_track_id
                ]

                track["center"] = center
                track["bbox"] = bbox
                track[
                    "last_seen_event_time"
                ] = event_timestamp

                track["age"] = (
                    int(
                        track.get(
                            "age",
                            0,
                        )
                    )
                    + 1
                )

            matched_track_ids.add(
                best_track_id
            )

            output_tracks.append(
                {
                    "track_id": best_track_id,
                    "detection_id": detection_id,
                    # "class": detection.get(
                    #     "class",
                    #     "person",
                    # ),
                    # "class_id": detection.get(
                    #     "class_id",
                    #     0,
                    # ),
                    "bbox": bbox,
                    "confidence": confidence,
                    "center": center,
                    # "match_distance": (
                    #     None
                    #     if best_distance == float("inf")
                    #     else best_distance
                    # ),
                    # "age": camera_tracks[
                    #     best_track_id
                    # ]["age"],
                }
            )

        return output_tracks

    # =========================================================
    # Event validation
    # =========================================================

    @staticmethod
    def _extract_event(
        raw_event: str,
    ) -> dict[str, Any]:
        try:
            event = json.loads(
                raw_event
            )
        except json.JSONDecodeError as error:
            raise ValueError(
                f"Invalid event JSON: {error}"
            ) from error

        if not isinstance(
            event,
            dict,
        ):
            raise ValueError(
                "Event must be a JSON object."
            )

        return event

    @staticmethod
    def _require_camera_id(
        event: dict[str, Any],
    ) -> str:
        camera = event.get(
            "camera"
        )

        if not isinstance(
            camera,
            dict,
        ):
            raise ValueError(
                "Event is missing camera object."
            )

        camera_id = camera.get(
            "camera_id"
        )

        if not isinstance(
            camera_id,
            str,
        ):
            raise ValueError(
                "Event is missing camera.camera_id."
            )

        camera_id = camera_id.strip()

        if not camera_id:
            raise ValueError(
                "camera.camera_id cannot be empty."
            )

        return camera_id

    # =========================================================
    # Message processing
    # =========================================================

    def _dedupe_key(self, source_event_id: str) -> str:
        return (
            f"tracker:processed:{self.mode}:"
            f"{source_event_id}"
        )

    async def _claim_event_for_processing(
        self,
        source_event_id: str,
    ) -> bool:
        """Claim a source event, returning false for completed replays."""
        if not self.redis_client:
            raise RuntimeError(
                "Redis client is not initialized."
            )

        key = self._dedupe_key(source_event_id)
        state = await self.redis_client.get(key)

        if state != "done":
            return True

        if state == "done":
            return False

        return False

    async def _mark_event_done(self, source_event_id: str) -> None:
        if not self.redis_client:
            raise RuntimeError(
                "Redis client is not initialized."
            )

        await self.redis_client.set(
            self._dedupe_key(source_event_id),
            "done",
            ex=self.dedupe_ttl_seconds,
        )

    async def process_message(
        self,
        redis_id: str,
        fields: dict[str, Any],
    ):
        try:
            raw_event = fields.get(
                "event"
            )

            if not raw_event:
                raise ValueError(
                    "Redis message is missing 'event' field."
                )

            event = self._extract_event(
                raw_event
            )

            event_type = event.get(
                "event_type"
            )

            if event_type != self.INPUT_EVENT_TYPE:
                # This worker only owns person.detected.
                await self.redis_client.xack(
                    self.input_stream,
                    self.group_name,
                    redis_id,
                )

                return

            # -------------------------------------------------
            # Required canonical event structures
            # -------------------------------------------------

            source = event.get(
                "source"
            )

            context = event.get(
                "context"
            )

            data = event.get(
                "data"
            )

            if not isinstance(
                source,
                dict,
            ):
                raise ValueError(
                    "Input event is missing source."
                )

            if not isinstance(
                context,
                dict,
            ):
                raise ValueError(
                    "Input event is missing context."
                )

            if not isinstance(
                data,
                dict,
            ):
                raise ValueError(
                    "Input event is missing data."
                )

            source_event_id = event.get(
                "event_id"
            )

            if not source_event_id:
                raise ValueError(
                    "Input event is missing event_id."
                )

            if not await self._claim_event_for_processing(
                source_event_id,
            ):
                await self.redis_client.xack(
                    self.input_stream,
                    self.group_name,
                    redis_id,
                )
                print(
                    f"[{self.agent_id}] Ignoring duplicate event "
                    f"{source_event_id}."
                )
                return

            camera_id = self._require_camera_id(
                event
            )

            if self.camera_id and camera_id != self.camera_id:
                raise ValueError(
                    "Event camera does not match tracker camera: "
                    f"{camera_id} != {self.camera_id}"
                )

            # -------------------------------------------------
            # Preserve event time
            # -------------------------------------------------

            event_timestamp = self._parse_timestamp(
                event.get("timestamp")
            )

            if event_timestamp is None:
                raise ValueError(
                    "Input event contains an invalid timestamp."
                )

            if self._is_stale_live_event(event_timestamp):
                print(
                    f"[{self.agent_id}] "
                    f"Discarding stale live event {redis_id} "
                    f"({event_timestamp.isoformat()})."
                )

                await self._mark_event_done(source_event_id)

                await self.redis_client.xack(
                    self.input_stream,
                    self.group_name,
                    redis_id,
                )

                return

            # -------------------------------------------------
            # Extract detections
            # -------------------------------------------------

            detections = data.get(
                "detections",
                [],
            )

            if not isinstance(
                detections,
                list,
            ):
                raise ValueError(
                    "data.detections must be a list."
                )

            # -------------------------------------------------
            # Update camera-local tracking state
            # -------------------------------------------------

            tracks = self.update_tracks(
                camera_id=camera_id,
                detections=detections,
                event_timestamp=event_timestamp,
            )

            # -------------------------------------------------
            # Preserve lineage
            # -------------------------------------------------

            trace_id = context.get(
                "trace_id"
            )

            correlation_id = context.get(
                "correlation_id"
            )

            incident_id = context.get(
                "incident_id"
            )

            input_mode = context.get(
                "mode",
                self.mode,
            )

            if input_mode not in {
                "live",
                "historical",
            }:
                raise ValueError(
                    f"Unsupported event mode: {input_mode}"
                )

            if input_mode != self.mode:
                raise ValueError(
                    "Input event mode does not match tracker mode: "
                    f"{input_mode} != {self.mode}"
                )

            mode = self.mode

            # -------------------------------------------------
            # Build canonical tracking event
            # -------------------------------------------------

            tracked_event = create_event(
                event_type=self.OUTPUT_EVENT_TYPE,
                agent_id=self.agent_id,
                instance_id=self.instance_id,
                hostname=self.hostname,
                camera_id=camera_id,
                event_id=source_event_id,
                mode=mode,
                timestamp=event_timestamp,
                trace_id=trace_id,
                correlation_id=correlation_id,
                incident_id=incident_id,
                data={
                    # "source_event_id": source_event_id,
                    # "source_redis_id": redis_id,
                    "frame_id": data.get(
                        "frame_id"
                    ),
                    # "frame_timestamp": data.get(
                    #     "frame_timestamp"
                    # ),
                    # "detection_count": len(
                    #     detections
                    # ),
                    # "track_count": len(
                    #     tracks
                    # ),
                    "tracks": tracks,
                    # "tracker": {
                    #     "type": "center-distance",
                    #     "distance_threshold": (
                    #         self.distance_threshold
                    #     ),
                    #     "track_timeout": (
                    #         self.track_timeout
                    #     ),
                    # },
                },
            )

            # -------------------------------------------------
            # Publish downstream event
            # -------------------------------------------------

            output_id = await self.publish(
                self.output_stream,
                tracked_event,
            )

            await self._mark_event_done(source_event_id)

            print(
                f"TRACKED | "
                f"Camera={camera_id} | "
                f"Frame={data.get('frame_id')} | "
                f"Persons={len(tracks)} | "
                f"Redis={output_id} | "
                f"Event={tracked_event.event_id}"
            )

            # -------------------------------------------------
            # ACK only after successful publish
            # -------------------------------------------------

            await self.redis_client.xack(
                self.input_stream,
                self.group_name,
                redis_id,
            )

        except asyncio.CancelledError:
            raise

        except Exception as error:
            print(
                f"[{self.agent_id}] "
                f"Message processing error "
                f"for {redis_id}: "
                f"{type(error).__name__}: {error}"
            )

            # IMPORTANT:
            #
            # Do NOT ACK failed messages.
            #
            # Redis keeps them pending so the future reliability
            # layer can recover/retry/DLQ them.
            #
            # The exception is deliberately re-raised so the
            # current message remains unacknowledged.
            raise

    # =========================================================
    # Main consumer loop
    # =========================================================

    async def recover_pending_messages(self) -> None:
        """Reclaim and process idle messages from failed consumers."""
        if not self.redis_client:
            raise RuntimeError(
                "Redis client is not initialized."
            )

        cursor = "0-0"
        recovered = 0

        while self.running:
            try:
                result = await self.redis_client.xautoclaim(
                    self.input_stream,
                    self.group_name,
                    self.consumer_name,
                    min_idle_time=self.pending_claim_idle_ms,
                    start_id=cursor,
                    count=10,
                )
            except asyncio.CancelledError:
                raise
            except Exception as error:
                print(
                    f"[{self.agent_id}] Pending recovery error: "
                    f"{type(error).__name__}: {error}"
                )
                return

            if not result or len(result) < 2:
                return

            next_cursor, entries = result[0], result[1]

            for redis_id, fields in entries:
                try:
                    await self.process_message(redis_id, fields)
                    recovered += 1
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    print(
                        f"[{self.agent_id}] Recovered message failed "
                        f"{redis_id}: {type(error).__name__}: {error}"
                    )

            if next_cursor in ("0-0", b"0-0"):
                break
            cursor = next_cursor

        if recovered:
            print(
                f"[{self.agent_id}] Recovered "
                f"{recovered} pending message(s)."
            )

    async def run(self):
        if not self.redis_client:
            raise RuntimeError(
                "Redis client is not initialized."
            )

        print(
            f"[{self.agent_id}] "
            f"Tracking loop started."
        )

        while self.running:
            try:
                await self.recover_pending_messages()

                messages = (
                    await self.redis_client.xreadgroup(
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
                    stream_name,
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
                            print(
                                f"[{self.agent_id}] "
                                f"Failed message "
                                f"{redis_id}: "
                                f"{type(error).__name__}: "
                                f"{error}"
                            )

                            # One bad event must not terminate
                            # the tracker process.
                            #
                            # The message remains pending because
                            # process_message did not ACK it.

                            continue

            except asyncio.CancelledError:
                raise

            except Exception as error:
                print(
                    f"[{self.agent_id}] "
                    f"Tracking loop error: "
                    f"{type(error).__name__}: "
                    f"{error}"
                )

                # Redis/network failure should not immediately
                # crash the entire worker. Give Redis a moment
                # before retrying.
                await asyncio.sleep(2)

        print(
            f"[{self.agent_id}] "
            f"Tracking loop stopped."
        )


async def main():
    agent = PersonTrackerAgent()

    await agent.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
