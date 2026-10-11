"""
Base class for all CCTV AI agents.

Responsibilities
----------------
- agent identity
- process instance identity
- supervisor process generation
- hostname
- Redis lifecycle
- agent-registry registration
- heartbeat lifecycle
- graceful shutdown
- common event publishing
- common timing helpers

Agents should implement:

    on_start()

    on_stop()

    run()
"""

from __future__ import annotations

import asyncio
import os
import socket
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import redis.asyncio as redis

from backend.app.monitoring.agent_registry import agent_registry
from shared.heartbeat.heartbeat import heartbeat_loop
from shared.schemas.event_schema import BaseEvent


class BaseAgent:
    """
    Common lifecycle foundation for every CCTV AI agent.

    Each process gets:

        agent_id
        instance_id
        process_generation
        hostname

    The instance_id uniquely identifies the actual running process.

    The process generation is supplied by the external supervisor through:

        AGENT_PROCESS_GENERATION

    The registry uses instance_id to reject heartbeats from an older
    process instance.
    """

    # ========================================================
    # INITIALIZATION
    # ========================================================

    def __init__(
        self,
        agent_id: str,
        *,
        redis_host: Optional[str] = None,
        redis_port: Optional[int] = None,
        heartbeat_interval: Optional[int] = None,
    ) -> None:

        if not agent_id or not agent_id.strip():
            raise ValueError(
                "agent_id must not be empty."
            )

        self.agent_id = agent_id.strip()

        # ----------------------------------------------------
        # Supervisor process generation
        # ----------------------------------------------------

        raw_generation = os.getenv(
            "AGENT_PROCESS_GENERATION",
            "0",
        ).strip()

        try:
            self.process_generation = int(
                raw_generation
            )
        except ValueError:
            self.process_generation = 0

        if self.process_generation < 0:
            self.process_generation = 0

        # ----------------------------------------------------
        # Unique process instance
        # ----------------------------------------------------
        #
        # The UUID guarantees that every actual process
        # instance gets a different identity.
        #
        # Including the supervisor generation makes debugging
        # and lifecycle tracing much easier.
        #
        # Example:
        #
        # tracker-CAM01-g12-8c2c...
        #
        # Process restart:
        #
        # tracker-CAM01-g13-a19f...
        #
        # The registry will therefore reject heartbeats from
        # the previous instance.
        # ----------------------------------------------------

        self.instance_id = (
            f"{self.agent_id}"
            f"-g{self.process_generation}"
            f"-{uuid.uuid4().hex}"
        )

        self.hostname = socket.gethostname()

        # ----------------------------------------------------
        # Redis configuration
        # ----------------------------------------------------

        self.redis_host = (
            redis_host
            if redis_host is not None
            else os.getenv(
                "REDIS_HOST",
                "localhost",
            )
        )

        if redis_port is not None:
            self.redis_port = redis_port
        else:
            raw_port = os.getenv(
                "REDIS_PORT",
                "6379",
            )

            try:
                self.redis_port = int(
                    raw_port
                )
            except (TypeError, ValueError) as error:
                raise ValueError(
                    "REDIS_PORT must be a valid integer."
                ) from error

        # ----------------------------------------------------
        # Heartbeat configuration
        # ----------------------------------------------------

        if heartbeat_interval is not None:
            self.heartbeat_interval = (
                heartbeat_interval
            )
        else:
            raw_interval = os.getenv(
                "HEARTBEAT_INTERVAL",
                "10",
            )

            try:
                self.heartbeat_interval = int(
                    raw_interval
                )
            except (TypeError, ValueError) as error:
                raise ValueError(
                    "HEARTBEAT_INTERVAL must be a valid integer."
                ) from error

        if self.redis_port <= 0:
            raise ValueError(
                "redis_port must be greater than zero."
            )

        if self.heartbeat_interval <= 0:
            raise ValueError(
                "heartbeat_interval must be greater than zero."
            )

        # ----------------------------------------------------
        # Runtime state
        # ----------------------------------------------------

        self.redis_client: Optional[
            redis.Redis
        ] = None

        self.heartbeat_task: Optional[
            asyncio.Task
        ] = None

        self.running = False

    # ========================================================
    # START
    # ========================================================

    async def start(self) -> None:
        """
        Start the agent.

        Order:

        1. Create Redis connection.
        2. Verify Redis.
        3. Mark agent running.
        4. Register this exact process instance.
        5. Start heartbeat.
        6. Run subclass startup hook.

        Registration happens before the heartbeat task starts so
        the registry has an explicit process identity before any
        heartbeat can be accepted.
        """

        if self.running:
            return

        print(
            f"[AGENT] Starting "
            f"{self.agent_id}"
        )

        print(
            f"[AGENT] instance_id="
            f"{self.instance_id}"
        )

        print(
            f"[AGENT] process_generation="
            f"{self.process_generation}"
        )

        print(
            f"[AGENT] hostname="
            f"{self.hostname}"
        )

        # ----------------------------------------------------
        # Redis
        # ----------------------------------------------------

        client: Optional[
            redis.Redis
        ] = None

        try:

            client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=10,
                health_check_interval=30,
            )

            await client.ping()

            self.redis_client = client

            # ------------------------------------------------
            # Mark running only after Redis is reachable.
            # ------------------------------------------------

            self.running = True

            # ------------------------------------------------
            # Register exact process instance
            # ------------------------------------------------

            agent_registry.register_agent(
                agent_id=self.agent_id,
                instance_id=self.instance_id,
                hostname=self.hostname,
            )

            print(
                "[AGENT] Registered process instance: "
                f"agent_id={self.agent_id}, "
                f"instance_id={self.instance_id}, "
                f"generation={self.process_generation}"
            )

            # ------------------------------------------------
            # Heartbeat
            # ------------------------------------------------
            #
            # heartbeat_loop receives the same instance_id
            # registered above.
            # ------------------------------------------------

            self.heartbeat_task = (
                asyncio.create_task(
                    heartbeat_loop(
                        self.redis_client,
                        agent_id=self.agent_id,
                        instance_id=self.instance_id,
                        hostname=self.hostname,
                        interval=self.heartbeat_interval,
                    ),
                    name=(
                        f"heartbeat-"
                        f"{self.agent_id}"
                    ),
                )
            )

            # ------------------------------------------------
            # Subclass startup
            # ------------------------------------------------

            await self.on_start()

            print(
                f"[AGENT] Started "
                f"{self.agent_id} "
                f"(generation="
                f"{self.process_generation})"
            )

        except asyncio.CancelledError:

            self.running = False

            await self._cleanup_start_failure()

            raise

        except Exception:

            self.running = False

            await self._cleanup_start_failure()

            raise

    # ========================================================
    # START FAILURE CLEANUP
    # ========================================================

    async def _cleanup_start_failure(self) -> None:
        """
        Cleanup resources when startup fails.

        This method is intentionally isolated from normal stop()
        so partial startup failures do not accidentally execute
        subclass shutdown logic that assumes successful startup.
        """

        # ----------------------------------------------------
        # Heartbeat
        # ----------------------------------------------------

        heartbeat_task = (
            self.heartbeat_task
        )

        self.heartbeat_task = None

        if heartbeat_task is not None:

            if not heartbeat_task.done():

                heartbeat_task.cancel()

            try:

                await heartbeat_task

            except asyncio.CancelledError:
                pass

            except Exception as error:

                print(
                    "[AGENT] Heartbeat startup "
                    f"cleanup error for "
                    f"{self.agent_id}: "
                    f"{error}"
                )

        # ----------------------------------------------------
        # Redis
        # ----------------------------------------------------

        client = self.redis_client

        self.redis_client = None

        if client is not None:

            try:

                await client.aclose()

            except Exception as error:

                print(
                    "[AGENT] Redis startup "
                    f"cleanup error for "
                    f"{self.agent_id}: "
                    f"{error}"
                )

    # ========================================================
    # STOP
    # ========================================================

    async def stop(self) -> None:
        """
        Gracefully stop the agent.
        """

        if (
            not self.running
            and self.redis_client is None
        ):
            return

        print(
            f"[AGENT] Stopping "
            f"{self.agent_id}"
        )

        # ----------------------------------------------------
        # Stop accepting normal lifecycle work.
        # ----------------------------------------------------

        self.running = False

        # ----------------------------------------------------
        # Heartbeat
        # ----------------------------------------------------

        heartbeat_task = (
            self.heartbeat_task
        )

        self.heartbeat_task = None

        if heartbeat_task is not None:

            if not heartbeat_task.done():

                heartbeat_task.cancel()

            try:

                await heartbeat_task

            except asyncio.CancelledError:
                pass

            except Exception as error:

                print(
                    "[AGENT] Heartbeat cleanup "
                    f"error for "
                    f"{self.agent_id}: "
                    f"{error}"
                )

        # ----------------------------------------------------
        # Subclass cleanup
        # ----------------------------------------------------

        try:

            await self.on_stop()

        except asyncio.CancelledError:

            raise

        except Exception as error:

            print(
                "[AGENT] on_stop failed for "
                f"{self.agent_id}: "
                f"{error}"
            )

        # ----------------------------------------------------
        # Redis
        # ----------------------------------------------------

        client = self.redis_client

        self.redis_client = None

        if client is not None:

            try:

                await client.aclose()

            except Exception as error:

                print(
                    "[AGENT] Redis cleanup "
                    f"error for "
                    f"{self.agent_id}: "
                    f"{error}"
                )

        print(
            f"[AGENT] Stopped "
            f"{self.agent_id}"
        )

    # ========================================================
    # HOOKS
    # ========================================================

    async def on_start(self) -> None:
        """
        Optional subclass startup hook.
        """

    async def on_stop(self) -> None:
        """
        Optional subclass cleanup hook.
        """

    # ========================================================
    # RUN
    # ========================================================

    async def run(self) -> None:
        """
        Main agent workload.

        Subclasses must implement this.
        """

        raise NotImplementedError(
            f"{self.__class__.__name__}.run() "
            "must be implemented."
        )

    # ========================================================
    # RUN FOREVER
    # ========================================================

    async def run_forever(self) -> None:
        """
        Full agent lifecycle.

        Fatal errors are re-raised after cleanup so the external
        supervisor can observe a non-zero process failure and
        perform recovery.
        """

        startup_succeeded = False

        try:

            await self.start()

            startup_succeeded = True

            await self.run()

        except asyncio.CancelledError:

            raise

        except Exception as error:

            print(
                f"[AGENT] Fatal error in "
                f"{self.agent_id}: "
                f"{error}"
            )

            raise

        finally:

            try:

                await self.stop()

            except asyncio.CancelledError:

                raise

            except Exception as cleanup_error:

                print(
                    f"[AGENT] Cleanup error in "
                    f"{self.agent_id}: "
                    f"{cleanup_error}"
                )

            # Explicit lifecycle marker retained for
            # future extensions.
            _ = startup_succeeded

    # ========================================================
    # PUBLISH
    # ========================================================

    async def publish(
        self,
        stream: str,
        event: BaseEvent | dict[str, Any],
    ) -> str:
        """
        Publish an event to a Redis Stream.

        The event must already be validated when possible.
        """

        if not stream or not stream.strip():

            raise ValueError(
                "stream must not be empty."
            )

        if self.redis_client is None:

            raise RuntimeError(
                f"Redis client is unavailable "
                f"for {self.agent_id}"
            )

        if isinstance(event, BaseEvent):

            payload = event.to_dict()

        elif isinstance(event, dict):

            payload = event

        else:

            raise TypeError(
                "event must be BaseEvent or dict."
            )

        validated_event = (
            BaseEvent.model_validate(
                payload
            )
        )

        return await self.redis_client.xadd(
            stream,
            {
                "event": (
                    validated_event.to_json()
                )
            },
        )

    # ========================================================
    # TIME
    # ========================================================

    @staticmethod
    def now() -> str:
        """
        Return current UTC timestamp.
        """

        return datetime.now(
            timezone.utc
        ).isoformat()

    # ========================================================
    # SLEEP
    # ========================================================

    @staticmethod
    async def sleep(
        seconds: float,
    ) -> None:
        """
        Async sleep helper.
        """

        if seconds < 0:

            raise ValueError(
                "seconds cannot be negative."
            )

        await asyncio.sleep(
            seconds
        )
