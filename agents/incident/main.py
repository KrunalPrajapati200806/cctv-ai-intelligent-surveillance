from __future__ import annotations

import asyncio
import json
import os
import socket
import uuid
from typing import Any, Callable, Optional

from backend.app.messaging.consumer import (
    create_incident_sync,
    ensure_incidents_table,
)
from shared.agent.base_agent import BaseAgent
from shared.schemas.event_schema import validate_event


# ============================================================
# CONFIGURATION
# ============================================================

INPUT_STREAM = os.getenv(
    "INCIDENT_INPUT_STREAM",
    "events.alerts",
).strip() or "events.alerts"

GROUP_NAME = os.getenv(
    "INCIDENT_GROUP_NAME",
    "incident-workers",
).strip() or "incident-workers"

DEFAULT_AGENT_ID = os.getenv(
    "AGENT_ID",
    "incident-01",
).strip() or "incident-01"

READ_COUNT = max(
    1,
    int(
        os.getenv(
            "INCIDENT_READ_COUNT",
            "10",
        )
    ),
)

READ_BLOCK_MS = max(
    100,
    int(
        os.getenv(
            "INCIDENT_READ_BLOCK_MS",
            "5000",
        )
    ),
)

PENDING_CLAIM_IDLE_MS = max(
    1000,
    int(
        os.getenv(
            "INCIDENT_PENDING_CLAIM_IDLE_MS",
            "30000",
        )
    ),
)

RECOVERY_BLOCK_MS = max(
    100,
    int(
        os.getenv(
            "INCIDENT_RECOVERY_BLOCK_MS",
            "1000",
        )
    ),
)

LOOP_RESTART_DELAY = max(
    0.1,
    float(
        os.getenv(
            "INCIDENT_LOOP_RESTART_DELAY",
            "1.0",
        )
    ),
)

REDIS_RETRY_DELAY = max(
    0.1,
    float(
        os.getenv(
            "INCIDENT_REDIS_RETRY_DELAY",
            "2.0",
        )
    ),
)


# ============================================================
# LIVE EVIDENCE CONFIGURATION
# ============================================================

EVIDENCE_PRE_SECONDS = max(
    0.0,
    float(
        os.getenv(
            "EVIDENCE_PRE_SECONDS",
            "10",
        )
    ),
)

EVIDENCE_POST_SECONDS = max(
    0.0,
    float(
        os.getenv(
            "EVIDENCE_POST_SECONDS",
            "10",
        )
    ),
)

EVIDENCE_SOURCE_TYPE = (
    os.getenv(
        "EVIDENCE_SOURCE_TYPE",
        "rolling_buffer",
    ).strip()
    or "rolling_buffer"
)


# ============================================================
# EVIDENCE REQUEST STREAM
# ============================================================

# Incident Agent publishes evidence requests here.
#
# Evidence Agent consumes this stream.
EVIDENCE_REQUEST_STREAM = (
    os.getenv(
        "EVIDENCE_REQUEST_STREAM",
        "events.evidence.requests",
    ).strip()
    or "events.evidence.requests"
)


# ============================================================
# EVENT TYPES
# ============================================================

SUPPORTED_ALERT_EVENT = "alert.created"


# ============================================================
# EXCEPTIONS
# ============================================================


class RetryableIncidentProcessingError(Exception):
    """
    Temporary processing failure.

    The Redis message must NOT be ACKed so that it can be
    retried or recovered later.
    """


class PermanentIncidentMessageError(ValueError):
    """
    Permanent message or validation error.

    The Redis message can safely be ACKed because retrying
    will not make the message valid.
    """


# ============================================================
# REDIS / EVENT HELPERS
# ============================================================


def decode_redis_value(value: Any) -> Any:
    """
    Decode Redis bytes while leaving other values unchanged.
    """
    if isinstance(value, bytes):
        return value.decode(
            "utf-8",
            errors="replace",
        )

    return value


def parse_redis_event(
    fields: dict[str, Any],
) -> dict[str, Any]:
    """
    Extract, decode, and validate the canonical event envelope.

    Canonical Redis field:
        event

    Compatibility Redis field:
        data

    If both fields exist, they must contain the same payload.
    """

    if not isinstance(fields, dict):
        raise PermanentIncidentMessageError(
            "Redis fields must be a dictionary."
        )

    raw_event = fields.get("event")
    compatibility_raw_event = fields.get("data")

    if (
        raw_event is None
        and compatibility_raw_event is None
    ):
        raise PermanentIncidentMessageError(
            "Redis message is missing both "
            "'event' and 'data' fields."
        )

    # --------------------------------------------------------
    # Prefer canonical "event" field.
    # --------------------------------------------------------

    if raw_event is not None:
        raw_event = decode_redis_value(raw_event)

        if compatibility_raw_event is not None:
            compatibility_raw_event = decode_redis_value(
                compatibility_raw_event
            )

            if raw_event != compatibility_raw_event:
                raise PermanentIncidentMessageError(
                    "Redis message contains conflicting "
                    "'event' and 'data' fields."
                )

    # --------------------------------------------------------
    # Compatibility fallback.
    # --------------------------------------------------------

    else:
        raw_event = decode_redis_value(
            compatibility_raw_event
        )

    # --------------------------------------------------------
    # Decode JSON event.
    # --------------------------------------------------------

    if isinstance(raw_event, str):
        try:
            event = json.loads(raw_event)
        except json.JSONDecodeError as exc:
            raise PermanentIncidentMessageError(
                f"Invalid event JSON: {exc}"
            ) from exc

    elif isinstance(raw_event, dict):
        event = raw_event

    else:
        raise PermanentIncidentMessageError(
            "Event payload must be JSON text or a dictionary."
        )

    # --------------------------------------------------------
    # Validate decoded event object.
    # --------------------------------------------------------

    if not isinstance(event, dict):
        raise PermanentIncidentMessageError(
            "Decoded event must be an object."
        )

    try:
        validated = validate_event(event)
    except Exception as exc:
        raise PermanentIncidentMessageError(
            f"Event schema validation failed: {exc}"
        ) from exc

    if hasattr(validated, "model_dump"):
        return validated.model_dump(
            mode="json"
        )

    if isinstance(validated, dict):
        return validated

    raise PermanentIncidentMessageError(
        "Validated event has an unsupported type."
    )


def make_consumer_name(
    agent_id: str,
    instance_id: Optional[str] = None,
) -> str:
    """
    Create a unique Redis consumer identity.
    """

    safe_agent_id = (
        str(agent_id)
        .strip()
        .replace(" ", "-")
        or "incident"
    )

    safe_instance_id = (
        str(instance_id).strip()
        if instance_id
        else uuid.uuid4().hex
    )

    hostname = (
        socket.gethostname().strip()
        or "unknown-host"
    )

    return (
        f"{safe_agent_id}:"
        f"{hostname}:"
        f"{safe_instance_id}"
    )


# ============================================================
# EVIDENCE TIMESTAMP HELPER
# ============================================================


def extract_event_time(
    alert_event: dict[str, Any],
) -> Optional[str]:
    """
    Extract the most useful event timestamp for evidence
    generation.

    Preference order:

        1. top-level timestamp
        2. top-level event_timestamp
        3. data.frame_timestamp
        4. data.event_timestamp
        5. data.timestamp
        6. data.created_at

    The returned value remains a string.

    The Evidence Agent is responsible for interpreting the
    timestamp and resolving it against the rolling-buffer
    manifest.
    """

    candidates: list[Any] = [
        alert_event.get("timestamp"),
        alert_event.get("event_timestamp"),
    ]

    data = alert_event.get(
        "data",
        {},
    )

    if isinstance(data, dict):
        candidates.extend(
            [
                data.get("frame_timestamp"),
                data.get("event_timestamp"),
                data.get("timestamp"),
                data.get("created_at"),
            ]
        )

    for value in candidates:
        if value is None:
            continue

        value = str(value).strip()

        if value:
            return value

    return None


# ============================================================
# INCIDENT AGENT
# ============================================================


class IncidentAgent(BaseAgent):
    """
    Incident processing agent.

    Ownership:

        events.alerts
            |
            v
        alert.created
            |
            v
        create incident
            |
            v
        events.evidence.requests
            |
            v
        Evidence Agent

    Evidence Agent then publishes:

        events.evidence
            |
            v
        backend consumer.py
            |
            v
        update incident evidence

    IMPORTANT:

    This agent is the owner of:

        alert -> incident -> evidence request

    This agent does NOT consume events.evidence.

    Evidence result persistence is owned by
    backend.app.messaging.consumer.

    This agent does NOT perform:

        - object detection
        - person detection
        - vehicle detection
        - tracking
        - behavior analysis
        - security policy evaluation
        - evidence generation
        - video processing
        - LLM reasoning
    """

    def __init__(
        self,
        agent_id: Optional[str] = None,
    ):
        super().__init__(
            agent_id=agent_id or DEFAULT_AGENT_ID
        )

        instance_id = getattr(
            self,
            "instance_id",
            None,
        )

        self.alert_consumer_name = make_consumer_name(
            self.agent_id,
            instance_id,
        )

    # ========================================================
    # STARTUP
    # ========================================================

    async def on_start(self) -> None:
        """
        Initialize the database and alert consumer group.
        """

        await asyncio.to_thread(
            ensure_incidents_table
        )

        await self.ensure_consumer_group(
            INPUT_STREAM,
            GROUP_NAME,
        )

        print(
            f"[{self.agent_id}] "
            f"Incident agent ready."
        )

        print(
            f"[{self.agent_id}] "
            f"Alert stream: {INPUT_STREAM}"
        )

        print(
            f"[{self.agent_id}] "
            f"Alert group: {GROUP_NAME}"
        )

        print(
            f"[{self.agent_id}] "
            f"Alert consumer: "
            f"{self.alert_consumer_name}"
        )

        print(
            f"[{self.agent_id}] "
            f"Evidence request stream: "
            f"{EVIDENCE_REQUEST_STREAM}"
        )

        print(
            f"[{self.agent_id}] "
            f"Evidence source type: "
            f"{EVIDENCE_SOURCE_TYPE}"
        )

        print(
            f"[{self.agent_id}] "
            f"Evidence window: "
            f"pre={EVIDENCE_PRE_SECONDS}s "
            f"post={EVIDENCE_POST_SECONDS}s"
        )

        print(
            f"[{self.agent_id}] "
            f"Evidence result persistence: "
            f"backend.app.messaging.consumer"
        )

    # ========================================================
    # SHUTDOWN
    # ========================================================

    async def on_stop(self) -> None:
        """
        Gracefully stop the agent.

        We intentionally do NOT call XGROUP DELCONSUMER.

        Pending messages remain recoverable through XAUTOCLAIM.
        """

        print(
            f"[{self.agent_id}] "
            f"Incident agent stopped."
        )

    # ========================================================
    # CONSUMER GROUP MANAGEMENT
    # ========================================================

    async def ensure_consumer_group(
        self,
        stream_name: str,
        group_name: str,
    ) -> None:
        """
        Create the Redis consumer group if it does not exist.
        """

        if not self.redis_client:
            raise RuntimeError(
                "Redis client is not initialized."
            )

        try:
            await self.redis_client.xgroup_create(
                name=stream_name,
                groupname=group_name,
                id="0-0",
                mkstream=True,
            )

            print(
                f"[{self.agent_id}] "
                f"Created consumer group "
                f"{group_name} for "
                f"{stream_name}"
            )

        except Exception as exc:
            if "BUSYGROUP" in str(exc):
                return

            raise

    # ========================================================
    # ACK
    # ========================================================

    async def ack_alert(
        self,
        redis_id: str,
    ) -> None:
        """
        ACK one alert message.
        """

        if not self.redis_client:
            raise RuntimeError(
                "Redis client is not initialized."
            )

        await self.redis_client.xack(
            INPUT_STREAM,
            GROUP_NAME,
            redis_id,
        )

    # ========================================================
    # EVIDENCE REQUEST CREATION
    # ========================================================

    async def publish_evidence_request(
        self,
        alert_event: dict[str, Any],
        incident: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Publish an evidence request only after the incident
        has successfully been created/persisted.

        The request preserves the canonical BaseEvent envelope.

        Evidence-specific configuration is stored under:

            data.evidence_request

        The Evidence Agent resolves the physical rolling-buffer
        files using:

            camera_id
            event_time
            source_type
            pre_seconds
            post_seconds

        IMPORTANT:

        Do NOT put arbitrary fields into context because
        EventContext uses extra="forbid".
        """

        if not self.redis_client:
            raise RuntimeError(
                "Redis client is not initialized."
            )

        # ----------------------------------------------------
        # Incident ID
        # ----------------------------------------------------

        incident_id = incident.get(
            "incident_id"
        )

        if not incident_id:
            raise RetryableIncidentProcessingError(
                "Created incident is missing incident_id."
            )

        # ----------------------------------------------------
        # Original alert event ID
        # ----------------------------------------------------

        event_id = alert_event.get(
            "event_id"
        )

        if not event_id:
            raise PermanentIncidentMessageError(
                "Alert event is missing event_id."
            )

        # ----------------------------------------------------
        # Camera
        # ----------------------------------------------------

        camera = alert_event.get(
            "camera",
            {},
        )

        if not isinstance(
            camera,
            dict,
        ):
            raise PermanentIncidentMessageError(
                "Alert event camera must be an object."
            )

        camera_id = camera.get(
            "camera_id"
        )

        if not camera_id:
            raise PermanentIncidentMessageError(
                "Alert event is missing "
                "camera.camera_id."
            )

        # ----------------------------------------------------
        # Event timestamp
        # ----------------------------------------------------

        event_time = extract_event_time(
            alert_event
        )

        if not event_time:
            raise PermanentIncidentMessageError(
                "Alert event does not contain a usable "
                "event timestamp."
            )

        # ----------------------------------------------------
        # Evidence configuration
        # ----------------------------------------------------

        if EVIDENCE_SOURCE_TYPE == "":
            raise PermanentIncidentMessageError(
                "EVIDENCE_SOURCE_TYPE cannot be empty."
            )

        # ----------------------------------------------------
        # Copy original event.
        #
        # Never mutate the original alert event because it is
        # also used for incident persistence/idempotency.
        # ----------------------------------------------------

        evidence_request = dict(
            alert_event
        )

        # ----------------------------------------------------
        # Preserve existing context.
        #
        # IMPORTANT:
        #
        # Only fields allowed by EventContext may be placed
        # here. In particular, DO NOT add incident_event_id.
        # ----------------------------------------------------

        existing_context = evidence_request.get(
            "context",
            {},
        )

        if existing_context is None:
            existing_context = {}

        if not isinstance(
            existing_context,
            dict,
        ):
            raise PermanentIncidentMessageError(
                "Alert event context must be an object."
            )

        context = dict(
            existing_context
        )

        # EventContext supports incident_id.
        context["incident_id"] = str(
            incident_id
        )

        evidence_request["context"] = context

        # ----------------------------------------------------
        # Evidence request payload
        # ----------------------------------------------------

        existing_data = evidence_request.get(
            "data",
            {},
        )

        if existing_data is None:
            existing_data = {}

        if not isinstance(
            existing_data,
            dict,
        ):
            raise PermanentIncidentMessageError(
                "Alert event data must be an object."
            )

        data = dict(
            existing_data
        )

        data["evidence_request"] = {
            "camera_id": str(camera_id),
            "event_time": str(event_time),
            "source_type": EVIDENCE_SOURCE_TYPE,
            "pre_seconds": EVIDENCE_PRE_SECONDS,
            "post_seconds": EVIDENCE_POST_SECONDS,
            "incident_id": str(incident_id),
            "incident_event_id": str(event_id),
        }

        evidence_request["data"] = data

        # ----------------------------------------------------
        # Validate complete canonical event.
        # ----------------------------------------------------

        try:
            validated = validate_event(
                evidence_request
            )
        except Exception as exc:
            raise PermanentIncidentMessageError(
                f"Evidence request validation failed: {exc}"
            ) from exc

        if hasattr(
            validated,
            "model_dump",
        ):
            evidence_request = validated.model_dump(
                mode="json"
            )

        elif isinstance(
            validated,
            dict,
        ):
            evidence_request = validated

        else:
            raise PermanentIncidentMessageError(
                "Validated evidence request has "
                "an unsupported type."
            )

        # ----------------------------------------------------
        # Publish to evidence request stream.
        # ----------------------------------------------------

        try:
            redis_id = await self.redis_client.xadd(
                EVIDENCE_REQUEST_STREAM,
                {
                    "event": json.dumps(
                        evidence_request,
                        ensure_ascii=False,
                    )
                },
            )

        except asyncio.CancelledError:
            raise

        except Exception as exc:
            raise RetryableIncidentProcessingError(
                "Failed to publish evidence request: "
                f"{exc}"
            ) from exc

        print(
            f"[{self.agent_id}] "
            f"Evidence request published | "
            f"redis_id={redis_id} | "
            f"event_id={event_id} | "
            f"incident_id={incident_id} | "
            f"camera={camera_id} | "
            f"event_time={event_time} | "
            f"source={EVIDENCE_SOURCE_TYPE} | "
            f"pre={EVIDENCE_PRE_SECONDS}s | "
            f"post={EVIDENCE_POST_SECONDS}s"
        )

        return evidence_request

    # ========================================================
    # ALERT PROCESSING
    # ========================================================

    async def process_alert_event(
        self,
        alert_event: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Persist one alert.created event and then publish the
        evidence request.

        Order is intentionally:

            1. validate alert
            2. create incident
            3. publish evidence request
            4. ACK original Redis message
        """

        event_type = alert_event.get(
            "event_type"
        )

        if event_type != SUPPORTED_ALERT_EVENT:
            raise PermanentIncidentMessageError(
                f"Unsupported alert event type: "
                f"{event_type}"
            )

        # ----------------------------------------------------
        # Camera validation
        # ----------------------------------------------------

        camera = alert_event.get(
            "camera",
            {},
        )

        if not isinstance(
            camera,
            dict,
        ):
            raise PermanentIncidentMessageError(
                "Alert event camera must be an object."
            )

        camera_id = camera.get(
            "camera_id"
        )

        if not camera_id:
            raise PermanentIncidentMessageError(
                "Alert event is missing "
                "camera.camera_id."
            )

        # ----------------------------------------------------
        # Data validation
        # ----------------------------------------------------

        data = alert_event.get(
            "data",
            {},
        )

        if not isinstance(
            data,
            dict,
        ):
            raise PermanentIncidentMessageError(
                "Alert event data must be an object."
            )

        # ----------------------------------------------------
        # Event ID
        # ----------------------------------------------------

        event_id = alert_event.get(
            "event_id"
        )

        if not event_id:
            raise PermanentIncidentMessageError(
                "Alert event is missing event_id."
            )

        print(
            f"[{self.agent_id}] "
            f"Processing alert | "
            f"event_id={event_id} | "
            f"camera={camera_id} | "
            f"alert={data.get('alert_type', 'unknown')}"
        )

        # ----------------------------------------------------
        # STEP 1:
        #
        # Create/persist incident.
        # ----------------------------------------------------

        try:
            incident = await asyncio.to_thread(
                create_incident_sync,
                alert_event,
            )

        except ValueError as exc:
            raise PermanentIncidentMessageError(
                str(exc)
            ) from exc

        except Exception as exc:
            raise RetryableIncidentProcessingError(
                str(exc)
            ) from exc

        if not isinstance(
            incident,
            dict,
        ):
            raise RetryableIncidentProcessingError(
                "Incident persistence returned "
                "an invalid result."
            )

        incident_id = incident.get(
            "incident_id"
        )

        if not incident_id:
            raise RetryableIncidentProcessingError(
                "Incident persistence returned "
                "no incident_id."
            )

        print(
            f"[{self.agent_id}] "
            f"Incident "
            f"{incident.get('action', 'UNKNOWN')} | "
            f"incident_id={incident_id} | "
            f"camera={incident.get('camera_id')} | "
            f"alert={incident.get('alert_type')}"
        )

        # ----------------------------------------------------
        # STEP 2:
        #
        # ONLY after successful incident persistence,
        # publish evidence request.
        # ----------------------------------------------------

        await self.publish_evidence_request(
            alert_event,
            incident,
        )

        return incident

    # ========================================================
    # ALERT MESSAGE HANDLER
    # ========================================================

    async def handle_alert_message(
        self,
        redis_id: str,
        fields: dict[str, Any],
    ) -> None:
        """
        Process one alert message.

        ACK only after:

            1. incident persistence succeeds
            2. evidence request publication succeeds

        Permanent validation errors are ACKed.

        Retryable errors remain pending.
        """

        try:
            alert_event = parse_redis_event(
                fields
            )

            await self.process_alert_event(
                alert_event
            )

            await self.ack_alert(
                redis_id
            )

            print(
                f"[{self.agent_id}] "
                f"ACK alert {redis_id}"
            )

        except PermanentIncidentMessageError as exc:
            print(
                f"[{self.agent_id}] "
                f"Permanent alert error | "
                f"Redis={redis_id} | "
                f"{exc}"
            )

            # Poison/permanently invalid messages should not
            # remain in the pending list forever.
            await self.ack_alert(
                redis_id
            )

        except RetryableIncidentProcessingError as exc:
            print(
                f"[{self.agent_id}] "
                f"Retryable alert error | "
                f"Redis={redis_id} | "
                f"{exc}"
            )

            raise

        except asyncio.CancelledError:
            raise

        except Exception as exc:
            print(
                f"[{self.agent_id}] "
                f"Unexpected alert error | "
                f"Redis={redis_id} | "
                f"{type(exc).__name__}: {exc}"
            )

            raise

    # ========================================================
    # OWN PENDING ALERT MESSAGES
    # ========================================================

    async def process_pending_alert_messages(
        self,
    ) -> None:
        """
        Process one bounded batch of messages already pending
        for this consumer.
        """

        if not self.redis_client:
            raise RuntimeError(
                "Redis client is not initialized."
            )

        try:
            messages = await self.redis_client.xreadgroup(
                groupname=GROUP_NAME,
                consumername=self.alert_consumer_name,
                streams={
                    INPUT_STREAM: "0-0",
                },
                count=READ_COUNT,
                block=RECOVERY_BLOCK_MS,
            )

        except asyncio.CancelledError:
            raise

        except Exception as exc:
            print(
                f"[{self.agent_id}] "
                f"Pending alert read error | "
                f"{type(exc).__name__}: {exc}"
            )

            return

        if not messages:
            return

        for (
            stream_name,
            stream_messages,
        ) in messages:

            for (
                redis_id,
                fields,
            ) in stream_messages:

                try:
                    await self.handle_alert_message(
                        redis_id,
                        fields,
                    )

                except Exception as exc:
                    print(
                        f"[{self.agent_id}] "
                        f"Pending alert {redis_id} "
                        f"remains pending | "
                        f"{type(exc).__name__}: {exc}"
                    )

    # ========================================================
    # STALE ALERT RECOVERY
    # ========================================================

    async def claim_stale_alert_messages(
        self,
    ) -> None:
        """
        Recover stale alert messages owned by failed consumers.
        """

        if not self.redis_client:
            raise RuntimeError(
                "Redis client is not initialized."
            )

        try:
            result = await self.redis_client.xautoclaim(
                INPUT_STREAM,
                GROUP_NAME,
                self.alert_consumer_name,
                min_idle_time=PENDING_CLAIM_IDLE_MS,
                start_id="0-0",
                count=READ_COUNT,
            )

        except asyncio.CancelledError:
            raise

        except Exception as exc:
            print(
                f"[{self.agent_id}] "
                f"Alert XAUTOCLAIM error | "
                f"{type(exc).__name__}: {exc}"
            )

            return

        if not result or len(result) < 2:
            return

        claimed_messages = result[1]

        if not claimed_messages:
            return

        print(
            f"[{self.agent_id}] "
            f"Recovered "
            f"{len(claimed_messages)} "
            f"stale alert message(s)."
        )

        for (
            redis_id,
            fields,
        ) in claimed_messages:

            try:
                await self.handle_alert_message(
                    redis_id,
                    fields,
                )

            except Exception as exc:
                print(
                    f"[{self.agent_id}] "
                    f"Recovered alert {redis_id} "
                    f"still failed | "
                    f"{type(exc).__name__}: {exc}"
                )

    # ========================================================
    # ALERT LOOP
    # ========================================================

    async def alert_loop(
        self,
    ) -> None:
        """
        Main alert consumption loop.
        """

        if not self.redis_client:
            raise RuntimeError(
                "Redis client is not initialized."
            )

        # Recover messages previously owned by this consumer.
        await self.process_pending_alert_messages()

        while self.running:

            # Recover stale messages from failed consumers.
            await self.claim_stale_alert_messages()

            try:
                messages = await self.redis_client.xreadgroup(
                    groupname=GROUP_NAME,
                    consumername=self.alert_consumer_name,
                    streams={
                        INPUT_STREAM: ">",
                    },
                    count=READ_COUNT,
                    block=READ_BLOCK_MS,
                )

            except asyncio.CancelledError:
                raise

            except Exception as exc:
                print(
                    f"[{self.agent_id}] "
                    f"Alert Redis read error | "
                    f"{type(exc).__name__}: {exc}"
                )

                await asyncio.sleep(
                    REDIS_RETRY_DELAY
                )

                continue

            if not messages:
                continue

            for (
                stream_name,
                stream_messages,
            ) in messages:

                for (
                    redis_id,
                    fields,
                ) in stream_messages:

                    try:
                        await self.handle_alert_message(
                            redis_id,
                            fields,
                        )

                    except Exception as exc:
                        print(
                            f"[{self.agent_id}] "
                            f"Alert {redis_id} "
                            f"left pending | "
                            f"{type(exc).__name__}: {exc}"
                        )

    # ========================================================
    # LOOP SUPERVISOR
    # ========================================================

    async def supervise_loop(
        self,
        loop_factory: Callable[[], Any],
        loop_name: str,
    ) -> None:
        """
        Restart the alert processing loop independently.
        """

        while self.running:

            try:
                await loop_factory()

            except asyncio.CancelledError:
                raise

            except Exception as exc:
                print(
                    f"[{self.agent_id}] "
                    f"{loop_name} crashed | "
                    f"{type(exc).__name__}: {exc}"
                )

                if self.running:
                    await asyncio.sleep(
                        LOOP_RESTART_DELAY
                    )

    # ========================================================
    # RUN
    # ========================================================

    async def run(
        self,
    ) -> None:
        """
        Run the Incident Agent.

        This agent owns only:

            alerts -> incidents -> evidence requests
        """

        if not self.redis_client:
            raise RuntimeError(
                "Redis client is not initialized."
            )

        print(
            f"[{self.agent_id}] "
            f"Incident processing started."
        )

        alert_task = asyncio.create_task(
            self.supervise_loop(
                self.alert_loop,
                "Alert loop",
            ),
            name=(
                f"{self.agent_id}-alert-loop"
            ),
        )

        try:
            await alert_task

        except asyncio.CancelledError:
            raise

        finally:
            if not alert_task.done():
                alert_task.cancel()

            await asyncio.gather(
                alert_task,
                return_exceptions=True,
            )

            print(
                f"[{self.agent_id}] "
                f"Incident processing stopped."
            )


# ============================================================
# ENTRY POINT
# ============================================================


async def main() -> None:
    agent = IncidentAgent(
        agent_id=os.getenv(
            "AGENT_ID",
            DEFAULT_AGENT_ID,
        )
    )

    await agent.run_forever()


if __name__ == "__main__":
    asyncio.run(
        main()
    )