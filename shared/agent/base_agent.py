# import asyncio
# import os
# import socket
# import uuid
# from datetime import datetime, timezone
# from typing import Optional

# import redis.asyncio as redis

# from shared.heartbeat.heartbeat import heartbeat_loop


# class BaseAgent:
#     """
#     Common runtime for all CCTV AI agents.

#     Responsibilities:
#     - Agent identity
#     - Redis connection
#     - Heartbeats
#     - Graceful startup/shutdown
#     - Isolated error handling
#     - Agent lifecycle logging

#     AI-specific logic must be implemented by subclasses.
#     """

#     def __init__(
#         self,
#         agent_id: str,
#         redis_host: Optional[str] = None,
#         redis_port: Optional[int] = None,
#         heartbeat_interval: Optional[int] = None,
#     ):
#         self.agent_id = agent_id

#         self.redis_host = redis_host or os.getenv(
#             "REDIS_HOST",
#             "localhost",
#         )

#         self.redis_port = redis_port or int(
#             os.getenv(
#                 "REDIS_PORT",
#                 "6379",
#             )
#         )

#         self.heartbeat_interval = heartbeat_interval or int(
#             os.getenv(
#                 "HEARTBEAT_INTERVAL",
#                 "10",
#             )
#         )

#         self.redis_client: Optional[redis.Redis] = None
#         self.heartbeat_task: Optional[asyncio.Task] = None

#         self.running = False

#         self.hostname = socket.gethostname()
#         self.instance_id = str(uuid.uuid4())

#     # ---------------------------------------------------------
#     # Lifecycle
#     # ---------------------------------------------------------

#     async def start(self):
#         """
#         Start common agent infrastructure.
#         """

#         print("=" * 60)
#         print(f"STARTING AGENT: {self.agent_id}")
#         print(f"HOST: {self.hostname}")
#         print(f"INSTANCE: {self.instance_id}")
#         print(
#             f"REDIS: {self.redis_host}:{self.redis_port}"
#         )
#         print("=" * 60)

#         self.redis_client = redis.Redis(
#             host=self.redis_host,
#             port=self.redis_port,
#             decode_responses=True,
#             socket_timeout=None,
#             health_check_interval=30,
#         )

#         # Verify Redis connection.
#         await self.redis_client.ping()

#         print(
#             f"[{self.agent_id}] Redis connection established."
#         )

#         self.running = True

#         # Start heartbeat independently from AI processing.
#         self.heartbeat_task = asyncio.create_task(
#             heartbeat_loop(
#                 redis_client=self.redis_client,
#                 agent_id=self.agent_id,
#                 interval=self.heartbeat_interval,
#             )
#         )

#         print(
#             f"[{self.agent_id}] Heartbeat started "
#             f"(interval={self.heartbeat_interval}s)"
#         )

#         await self.on_start()

#     async def stop(self):
#         """
#         Gracefully stop the agent.
#         """

#         if not self.running:
#             return

#         print(
#             f"[{self.agent_id}] Shutting down..."
#         )

#         self.running = False

#         # Stop heartbeat.
#         if self.heartbeat_task:
#             self.heartbeat_task.cancel()

#             try:
#                 await self.heartbeat_task
#             except asyncio.CancelledError:
#                 pass

#             self.heartbeat_task = None

#         # Allow subclass cleanup.
#         try:
#             await self.on_stop()
#         except Exception as error:
#             print(
#                 f"[{self.agent_id}] "
#                 f"Shutdown cleanup error: {error}"
#             )

#         # Close Redis.
#         if self.redis_client:
#             try:
#                 await self.redis_client.aclose()
#             except Exception as error:
#                 print(
#                     f"[{self.agent_id}] "
#                     f"Redis close error: {error}"
#                 )

#             self.redis_client = None

#         print(
#             f"[{self.agent_id}] Stopped."
#         )

#     # ---------------------------------------------------------
#     # Hooks
#     # ---------------------------------------------------------

#     async def on_start(self):
#         """
#         Optional startup hook for subclasses.
#         """
#         pass

#     async def on_stop(self):
#         """
#         Optional shutdown hook for subclasses.
#         """
#         pass

#     # ---------------------------------------------------------
#     # Main agent logic
#     # ---------------------------------------------------------

#     async def run(self):
#         """
#         Main runtime.

#         Subclasses must implement this method.
#         """

#         raise NotImplementedError(
#             "Agent must implement run()."
#         )

#     async def run_forever(self):
#         """
#         Complete agent lifecycle.

#         A failure in this agent is contained here and does
#         not directly terminate other agents.
#         """

#         try:
#             await self.start()

#             await self.run()

#         except asyncio.CancelledError:
#             print(
#                 f"[{self.agent_id}] "
#                 f"Cancellation received."
#             )
#             raise

#         except Exception as error:
#             print(
#                 f"[{self.agent_id}] "
#                 f"FATAL AGENT ERROR: {error}"
#             )

#         finally:
#             await self.stop()

#     # ---------------------------------------------------------
#     # Utility
#     # ---------------------------------------------------------

#     def now(self) -> str:
#         """
#         Return UTC timestamp.
#         """

#         return datetime.now(
#             timezone.utc
#         ).isoformat()

#     async def publish(
#         self,
#         stream: str,
#         event: dict,
#     ) -> str:
#         """
#         Publish an event to a Redis Stream.
#         """

#         if not self.redis_client:
#             raise RuntimeError(
#                 "Redis client is not initialized."
#             )

#         redis_id = await self.redis_client.xadd(
#             stream,
#             {
#                 "event": __import__("json").dumps(
#                     event
#                 )
#             },
#         )

#         return redis_id

#     async def sleep(self, seconds: float):
#         """
#         Cooperative async sleep.
#         """

#         await asyncio.sleep(seconds)





"""
Base class for all CCTV AI agents.

Responsibilities:
- agent identity
- process instance identity
- hostname
- Redis lifecycle
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
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import redis.asyncio as redis

from shared.heartbeat.heartbeat import heartbeat_loop
from shared.schemas.event_schema import BaseEvent


class BaseAgent:
    """
    Common lifecycle foundation for every CCTV AI agent.
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

        # A new UUID identifies this exact process instance.
        #
        # Example:
        #
        # tracker-01
        #   instance A → process restart
        #   instance B → new UUID
        #
        self.instance_id = str(
            uuid.uuid4()
        )

        self.hostname = socket.gethostname()

        self.redis_host = (
            redis_host
            if redis_host is not None
            else os.getenv(
                "REDIS_HOST",
                "localhost",
            )
        )

        self.redis_port = (
            redis_port
            if redis_port is not None
            else int(
                os.getenv(
                    "REDIS_PORT",
                    "6379",
                )
            )
        )

        self.heartbeat_interval = (
            heartbeat_interval
            if heartbeat_interval is not None
            else int(
                os.getenv(
                    "HEARTBEAT_INTERVAL",
                    "10",
                )
            )
        )

        if self.redis_port <= 0:
            raise ValueError(
                "redis_port must be greater than zero."
            )

        if self.heartbeat_interval <= 0:
            raise ValueError(
                "heartbeat_interval must be greater than zero."
            )

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
        4. Start heartbeat.
        5. Run subclass startup hook.
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

                # Keep command timeouts bounded.
                socket_timeout=10,

                health_check_interval=30,
            )

            await client.ping()

            self.redis_client = client

            self.running = True

            # ------------------------------------------------
            # Heartbeat
            # ------------------------------------------------

            self.heartbeat_task = asyncio.create_task(
                heartbeat_loop(
                    self.redis_client,
                    agent_id=self.agent_id,
                    instance_id=self.instance_id,
                    hostname=self.hostname,
                    interval=self.heartbeat_interval,
                )
            )

            # ------------------------------------------------
            # Subclass startup
            # ------------------------------------------------

            await self.on_start()

            print(
                f"[AGENT] Started "
                f"{self.agent_id}"
            )

        except Exception:

            self.running = False

            # If startup fails before normal lifecycle
            # cleanup becomes available, close Redis here.
            if self.heartbeat_task is not None:

                self.heartbeat_task.cancel()

                try:
                    await self.heartbeat_task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass

                self.heartbeat_task = None

            if client is not None:

                try:
                    await client.aclose()
                except Exception:
                    pass

            self.redis_client = None

            raise

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

        self.running = False

        # ----------------------------------------------------
        # Heartbeat
        # ----------------------------------------------------

        heartbeat_task = (
            self.heartbeat_task
        )

        self.heartbeat_task = None

        if heartbeat_task is not None:

            heartbeat_task.cancel()

            try:
                await heartbeat_task

            except asyncio.CancelledError:
                pass

            except Exception as error:
                print(
                    f"[AGENT] Heartbeat cleanup "
                    f"error for {self.agent_id}: "
                    f"{error}"
                )

        # ----------------------------------------------------
        # Subclass cleanup
        # ----------------------------------------------------

        try:
            await self.on_stop()

        except Exception as error:

            print(
                f"[AGENT] on_stop failed for "
                f"{self.agent_id}: {error}"
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
                    f"[AGENT] Redis cleanup "
                    f"error for {self.agent_id}: "
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

        Fatal errors are re-raised after cleanup so the
        external supervisor can observe a non-zero process
        failure and perform recovery.
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
                f"{self.agent_id}: {error}"
            )

            raise

        finally:

            try:
                await self.stop()

            except Exception as cleanup_error:

                print(
                    f"[AGENT] Cleanup error in "
                    f"{self.agent_id}: "
                    f"{cleanup_error}"
                )

            # This variable intentionally exists to make the
            # lifecycle state explicit for future extensions.
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

        return await self.redis_client.xadd(
            stream,
            {
                "event": BaseEvent.model_validate(
                    payload
                ).to_json()
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
