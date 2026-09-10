# # # # # # import asyncio
# # # # # # from datetime import datetime, timezone
# # # # # # import uuid

# # # # # # import redis.asyncio as redis


# # # # # # async def send_heartbeat(
# # # # # #     redis_client: redis.Redis,
# # # # # #     agent_id: str,
# # # # # # ):
# # # # # #     event = {
# # # # # #         "event_id": str(uuid.uuid4()),
# # # # # #         "event_type": "agent.heartbeat",
# # # # # #         "version": "1.0",
# # # # # #         "timestamp": datetime.now(timezone.utc).isoformat(),
# # # # # #         "source_agent_id": agent_id,
# # # # # #         "status": "alive",
# # # # # #     }

# # # # # #     await redis_client.xadd(
# # # # # #         "events.system",
# # # # # #         event,
# # # # # #     )


# # # # # # async def heartbeat_loop(
# # # # # #     redis_client: redis.Redis,
# # # # # #     agent_id: str,
# # # # # #     interval: int = 10,
# # # # # # ):
# # # # # #     while True:
# # # # # #         try:
# # # # # #             await send_heartbeat(
# # # # # #                 redis_client,
# # # # # #                 agent_id,
# # # # # #             )

# # # # # #             print(
# # # # # #                 f"Heartbeat sent: {agent_id}"
# # # # # #             )

# # # # # #             await asyncio.sleep(interval)

# # # # # #         except asyncio.CancelledError:
# # # # # #             print(
# # # # # #                 f"Heartbeat stopped: {agent_id}"
# # # # # #             )
# # # # # #             raise

# # # # # #         except Exception as error:
# # # # # #             print(
# # # # # #                 f"Heartbeat error for {agent_id}: {error}"
# # # # # #             )

# # # # # #             await asyncio.sleep(interval)














# # # # # import asyncio
# # # # # from datetime import datetime, timezone
# # # # # import os
# # # # # import uuid

# # # # # import redis.asyncio as redis


# # # # # async def send_heartbeat(
# # # # #     redis_client: redis.Redis,
# # # # #     agent_id: str,
# # # # # ):
# # # # #     event = {
# # # # #         "event_id": str(uuid.uuid4()),
# # # # #         "event_type": "agent.heartbeat",
# # # # #         "version": "1.0",
# # # # #         "timestamp": datetime.now(timezone.utc).isoformat(),
# # # # #         "source_agent_id": agent_id,
# # # # #         "status": "alive",
# # # # #     }

# # # # #     await redis_client.xadd(
# # # # #         "events.system",
# # # # #         event,
# # # # #     )


# # # # # async def heartbeat_loop(
# # # # #     redis_client: redis.Redis,
# # # # #     agent_id: str,
# # # # #     interval: int = 10,
# # # # # ):
# # # # #     """
# # # # #     Sends periodic agent heartbeats.

# # # # #     TEST HEARTBEAT FAILURE:
# # # # #     Set TEST_HEARTBEAT_FAILURE_AGENT to an agent ID
# # # # #     to intentionally suppress heartbeats for that agent.

# # # # #     Example:
# # # # #         TEST_HEARTBEAT_FAILURE_AGENT=behavior-01

# # # # #     This is intended only for fault-isolation testing.
# # # # #     """

# # # # #     test_failure_agent = os.getenv(
# # # # #         "TEST_HEARTBEAT_FAILURE_AGENT",
# # # # #         "",
# # # # #     ).strip()

# # # # #     heartbeat_suppressed = (
# # # # #         test_failure_agent == agent_id
# # # # #     )

# # # # #     if heartbeat_suppressed:
# # # # #         print(
# # # # #             f"[HEARTBEAT TEST] Heartbeat suppression "
# # # # #             f"ENABLED for {agent_id}"
# # # # #         )

# # # # #     while True:
# # # # #         try:
# # # # #             if heartbeat_suppressed:
# # # # #                 print(
# # # # #                     f"[HEARTBEAT TEST] Suppressing heartbeat: "
# # # # #                     f"{agent_id}"
# # # # #                 )
# # # # #             else:
# # # # #                 await send_heartbeat(
# # # # #                     redis_client,
# # # # #                     agent_id,
# # # # #                 )

# # # # #                 print(
# # # # #                     f"Heartbeat sent: {agent_id}"
# # # # #                 )

# # # # #             await asyncio.sleep(interval)

# # # # #         except asyncio.CancelledError:
# # # # #             print(
# # # # #                 f"Heartbeat stopped: {agent_id}"
# # # # #             )
# # # # #             raise

# # # # #         except Exception as error:
# # # # #             print(
# # # # #                 f"Heartbeat error for {agent_id}: "
# # # # #                 f"{error}"
# # # # #             )

# # # # #             await asyncio.sleep(interval)


















# # # # import asyncio
# # # # from datetime import datetime, timezone
# # # # import os
# # # # import uuid

# # # # import redis.asyncio as redis


# # # # async def send_heartbeat(
# # # #     redis_client: redis.Redis,
# # # #     agent_id: str,
# # # # ):
# # # #     event = {
# # # #         "event_id": str(uuid.uuid4()),
# # # #         "event_type": "agent.heartbeat",
# # # #         "version": "1.0",
# # # #         "timestamp": datetime.now(timezone.utc).isoformat(),
# # # #         "source_agent_id": agent_id,
# # # #         "status": "alive",
# # # #     }

# # # #     await redis_client.xadd(
# # # #         "events.system",
# # # #         event,
# # # #     )


# # # # async def heartbeat_loop(
# # # #     redis_client: redis.Redis,
# # # #     agent_id: str,
# # # #     interval: int = 10,
# # # # ):
# # # #     """
# # # #     Sends periodic agent heartbeats.

# # # #     TEST MODE:
# # # #     TEST_HEARTBEAT_FAILURE_AGENT=behavior-01

# # # #     The heartbeat failure is intentionally triggered only for
# # # #     the FIRST process instance of the target agent.

# # # #     A marker file is created so that when the supervisor
# # # #     restarts the agent, the new process sends normal heartbeats.

# # # #     This allows us to test:

# # # #         heartbeat failure
# # # #               ↓
# # # #         watchdog detects DEAD
# # # #               ↓
# # # #         supervisor recovery
# # # #               ↓
# # # #         new agent starts
# # # #               ↓
# # # #         heartbeat becomes ALIVE again
# # # #     """

# # # #     test_failure_agent = os.getenv(
# # # #         "TEST_HEARTBEAT_FAILURE_AGENT",
# # # #         "",
# # # #     ).strip()

# # # #     marker_dir = os.path.join(
# # # #         os.getcwd(),
# # # #         "data",
# # # #         "heartbeat_tests",
# # # #     )

# # # #     marker_file = os.path.join(
# # # #         marker_dir,
# # # #         f"{agent_id}.triggered",
# # # #     )

# # # #     heartbeat_suppressed = False

# # # #     if test_failure_agent == agent_id:
# # # #         os.makedirs(
# # # #             marker_dir,
# # # #             exist_ok=True,
# # # #         )

# # # #         if not os.path.exists(marker_file):
# # # #             try:
# # # #                 with open(
# # # #                     marker_file,
# # # #                     "w",
# # # #                     encoding="utf-8",
# # # #                 ) as file:
# # # #                     file.write(
# # # #                         "heartbeat failure test triggered\n"
# # # #                     )

# # # #                 heartbeat_suppressed = True

# # # #                 print(
# # # #                     f"[HEARTBEAT TEST] One-shot heartbeat "
# # # #                     f"suppression ENABLED for {agent_id}"
# # # #                 )

# # # #             except Exception as error:
# # # #                 print(
# # # #                     f"[HEARTBEAT TEST] Could not create "
# # # #                     f"marker file: {error}"
# # # #                 )

# # # #         else:
# # # #             print(
# # # #                 f"[HEARTBEAT TEST] Marker already exists. "
# # # #                 f"Normal heartbeat enabled for {agent_id}"
# # # #             )

# # # #     while True:
# # # #         try:
# # # #             if heartbeat_suppressed:
# # # #                 print(
# # # #                     f"[HEARTBEAT TEST] Suppressing heartbeat: "
# # # #                     f"{agent_id}"
# # # #                 )
# # # #             else:
# # # #                 await send_heartbeat(
# # # #                     redis_client,
# # # #                     agent_id,
# # # #                 )

# # # #                 print(
# # # #                     f"Heartbeat sent: {agent_id}"
# # # #                 )

# # # #             await asyncio.sleep(interval)

# # # #         except asyncio.CancelledError:
# # # #             print(
# # # #                 f"Heartbeat stopped: {agent_id}"
# # # #             )
# # # #             raise

# # # #         except Exception as error:
# # # #             print(
# # # #                 f"Heartbeat error for {agent_id}: "
# # # #                 f"{error}"
# # # #             )

# # # #             await asyncio.sleep(interval)
















# # # import asyncio
# # # from datetime import datetime, timezone
# # # import os
# # # import uuid

# # # import redis.asyncio as redis


# # # async def send_heartbeat(
# # #     redis_client: redis.Redis,
# # #     agent_id: str,
# # # ):
# # #     event = {
# # #         "event_id": str(uuid.uuid4()),
# # #         "event_type": "agent.heartbeat",
# # #         "version": "1.0",
# # #         "timestamp": datetime.now(timezone.utc).isoformat(),
# # #         "source_agent_id": agent_id,
# # #         "status": "alive",
# # #     }

# # #     await redis_client.xadd(
# # #         "events.system",
# # #         event,
# # #     )


# # # async def heartbeat_loop(
# # #     redis_client: redis.Redis,
# # #     agent_id: str,
# # #     interval: int = 10,
# # # ):
# # #     """
# # #     Sends periodic agent heartbeats.

# # #     TEST MODE:
# # #         SUPERVISOR_TEST_HEARTBEAT_FAILURE_AGENT=behavior-01

# # #     The target agent sends ONE normal heartbeat first.
# # #     Then heartbeats are suppressed.

# # #     This allows the watchdog to observe:
# # #         ALIVE -> heartbeat timeout -> DEAD -> recovery

# # #     A marker file ensures the failure is triggered only once.
# # #     After supervisor restart, the marker exists and the
# # #     restarted agent sends normal heartbeats.
# # #     """

# # #     test_failure_agent = os.getenv(
# # #         "TEST_HEARTBEAT_FAILURE_AGENT",
# # #         "",
# # #     ).strip()

# # #     marker_dir = os.path.join(
# # #         os.getcwd(),
# # #         "data",
# # #         "heartbeat_tests",
# # #     )

# # #     marker_file = os.path.join(
# # #         marker_dir,
# # #         f"{agent_id}.triggered",
# # #     )

# # #     heartbeat_suppressed = False
# # #     first_heartbeat_sent = False

# # #     if test_failure_agent == agent_id:
# # #         os.makedirs(
# # #             marker_dir,
# # #             exist_ok=True,
# # #         )

# # #         if os.path.exists(marker_file):
# # #             print(
# # #                 f"[HEARTBEAT TEST] Marker already exists. "
# # #                 f"Normal heartbeat enabled for {agent_id}"
# # #             )
# # #         else:
# # #             print(
# # #                 f"[HEARTBEAT TEST] "
# # #                 f"Target detected for {agent_id}. "
# # #                 f"First heartbeat will be normal."
# # #             )

# # #     while True:
# # #         try:
# # #             # --------------------------------------------------
# # #             # HEARTBEAT FAILURE TEST
# # #             # --------------------------------------------------

# # #             if (
# # #                 test_failure_agent == agent_id
# # #                 and not os.path.exists(marker_file)
# # #             ):
# # #                 # Send ONE normal heartbeat first.
# # #                 await send_heartbeat(
# # #                     redis_client,
# # #                     agent_id,
# # #                 )

# # #                 print(
# # #                     f"[HEARTBEAT TEST] "
# # #                     f"Initial heartbeat sent: {agent_id}"
# # #                 )

# # #                 # Create marker after first heartbeat.
# # #                 try:
# # #                     with open(
# # #                         marker_file,
# # #                         "w",
# # #                         encoding="utf-8",
# # #                     ) as file:
# # #                         file.write(
# # #                             "heartbeat failure test triggered\n"
# # #                         )

# # #                     heartbeat_suppressed = True

# # #                     print(
# # #                         f"[HEARTBEAT TEST] "
# # #                         f"Heartbeat suppression ENABLED "
# # #                         f"for {agent_id}"
# # #                     )

# # #                 except Exception as error:
# # #                     print(
# # #                         f"[HEARTBEAT TEST] "
# # #                         f"Could not create marker: {error}"
# # #                     )

# # #             elif (
# # #                 test_failure_agent == agent_id
# # #                 and heartbeat_suppressed
# # #             ):
# # #                 print(
# # #                     f"[HEARTBEAT TEST] "
# # #                     f"Suppressing heartbeat: {agent_id}"
# # #                 )

# # #             else:
# # #                 # Normal production heartbeat.
# # #                 await send_heartbeat(
# # #                     redis_client,
# # #                     agent_id,
# # #                 )

# # #                 print(
# # #                     f"Heartbeat sent: {agent_id}"
# # #                 )

# # #             await asyncio.sleep(interval)

# # #         except asyncio.CancelledError:
# # #             print(
# # #                 f"Heartbeat stopped: {agent_id}"
# # #             )
# # #             raise

# # #         except Exception as error:
# # #             print(
# # #                 f"Heartbeat error for {agent_id}: "
# # #                 f"{error}"
# # #             )

# # #             await asyncio.sleep(interval)




# # """
# # Agent heartbeat infrastructure.

# # Heartbeat events are system/liveness events.

# # They are intentionally kept separate from normal AI event
# # processing semantics.

# # Heartbeat contains:
# # - agent identity
# # - process instance identity
# # - hostname
# # - status
# # - timestamp
# # - basic lifecycle information

# # The heartbeat loop must never terminate the agent merely
# # because Redis temporarily becomes unavailable.
# # """

# # from __future__ import annotations

# # import asyncio
# # import os
# # import socket
# # import uuid
# # from datetime import datetime, timezone
# # from pathlib import Path
# # from typing import Optional

# # import redis.asyncio as redis


# # # ============================================================
# # # CONFIGURATION
# # # ============================================================

# # HEARTBEAT_STREAM = os.getenv(
# #     "HEARTBEAT_STREAM",
# #     "events.system",
# # )

# # HEARTBEAT_STATUS = "alive"


# # # ============================================================
# # # HELPERS
# # # ============================================================

# # def utc_now_iso() -> str:
# #     """
# #     Return current UTC time in ISO-8601 format.
# #     """

# #     return datetime.now(
# #         timezone.utc
# #     ).isoformat()


# # # ============================================================
# # # HEARTBEAT
# # # ============================================================

# # async def send_heartbeat(
# #     redis_client: redis.Redis,
# #     *,
# #     agent_id: str,
# #     instance_id: str,
# #     hostname: Optional[str] = None,
# #     status: str = HEARTBEAT_STATUS,
# # ) -> bool:
# #     """
# #     Publish one heartbeat.

# #     Returns:
# #         True  -> heartbeat published
# #         False -> heartbeat failed

# #     Redis errors are intentionally handled here so a temporary
# #     Redis outage does not crash the agent process.
# #     """

# #     hostname = hostname or socket.gethostname()

# #     event = {
# #         "event_id": str(uuid.uuid4()),
# #         "event_type": "agent.heartbeat",
# #         "version": "1.0",
# #         "timestamp": utc_now_iso(),

# #         "source": {
# #             "agent_id": agent_id,
# #             "instance_id": instance_id,
# #             "hostname": hostname,
# #         },

# #         "data": {
# #             "status": status,
# #         },
# #     }

# #     try:
# #         await redis_client.xadd(
# #             HEARTBEAT_STREAM,
# #             event,
# #         )

# #         return True

# #     except asyncio.CancelledError:
# #         raise

# #     except Exception as error:
# #         print(
# #             f"[HEARTBEAT] Failed for "
# #             f"{agent_id} "
# #             f"(instance={instance_id}): "
# #             f"{error}"
# #         )

# #         return False


# # # ============================================================
# # # TEST FAILURE MODE
# # # ============================================================

# # def heartbeat_failure_test_enabled(
# #     agent_id: str,
# # ) -> bool:
# #     """
# #     Determine whether heartbeat failure injection is enabled
# #     for this agent.

# #     Environment variable:

# #         TEST_HEARTBEAT_FAILURE_AGENT=behavior-01
# #     """

# #     target = os.getenv(
# #         "TEST_HEARTBEAT_FAILURE_AGENT",
# #         "",
# #     ).strip()

# #     return bool(
# #         target and target == agent_id
# #     )


# # def get_marker_file(
# #     agent_id: str,
# # ) -> Path:
# #     """
# #     Return the heartbeat failure-test marker path.

# #     The project root can be explicitly configured with
# #     PROJECT_ROOT. Otherwise the current working directory
# #     is used.
# #     """

# #     project_root = Path(
# #         os.getenv(
# #             "PROJECT_ROOT",
# #             os.getcwd(),
# #         )
# #     )

# #     marker_dir = (
# #         project_root
# #         / "data"
# #         / "heartbeat_tests"
# #     )

# #     marker_dir.mkdir(
# #         parents=True,
# #         exist_ok=True,
# #     )

# #     return marker_dir / f"{agent_id}.triggered"


# # # ============================================================
# # # HEARTBEAT LOOP
# # # ============================================================

# # async def heartbeat_loop(
# #     redis_client: redis.Redis,
# #     *,
# #     agent_id: str,
# #     instance_id: str,
# #     hostname: Optional[str] = None,
# #     interval: int = 10,
# # ) -> None:
# #     """
# #     Continuously publish heartbeats.

# #     Important:

# #     Redis failure does NOT terminate the loop.

# #     The supervisor should detect missing heartbeats and
# #     independently decide whether the agent needs recovery.
# #     """

# #     if interval <= 0:
# #         raise ValueError(
# #             "Heartbeat interval must be greater than zero."
# #         )

# #     hostname = hostname or socket.gethostname()

# #     test_enabled = heartbeat_failure_test_enabled(
# #         agent_id
# #     )

# #     marker_file = get_marker_file(
# #         agent_id
# #     )

# #     heartbeat_suppressed = False

# #     if test_enabled:
# #         print(
# #             f"[HEARTBEAT] Failure injection enabled "
# #             f"for {agent_id}"
# #         )

# #     while True:

# #         try:

# #             # ------------------------------------------------
# #             # Failure injection
# #             # ------------------------------------------------

# #             if test_enabled:

# #                 if (
# #                     not heartbeat_suppressed
# #                     and not marker_file.exists()
# #                 ):
# #                     success = await send_heartbeat(
# #                         redis_client,
# #                         agent_id=agent_id,
# #                         instance_id=instance_id,
# #                         hostname=hostname,
# #                     )

# #                     if success:
# #                         print(
# #                             f"[HEARTBEAT] Initial test "
# #                             f"heartbeat sent for {agent_id}"
# #                         )

# #                         try:
# #                             marker_file.write_text(
# #                                 "heartbeat failure test triggered\n",
# #                                 encoding="utf-8",
# #                             )

# #                             heartbeat_suppressed = True

# #                             print(
# #                                 f"[HEARTBEAT] Suppression enabled "
# #                                 f"for {agent_id}"
# #                             )

# #                         except Exception as error:
# #                             print(
# #                                 f"[HEARTBEAT] Could not create "
# #                                 f"test marker for {agent_id}: "
# #                                 f"{error}"
# #                             )

# #                 elif heartbeat_suppressed:

# #                     print(
# #                         f"[HEARTBEAT] Suppressing heartbeat "
# #                         f"for failure test: {agent_id}"
# #                     )

# #                 else:

# #                     await send_heartbeat(
# #                         redis_client,
# #                         agent_id=agent_id,
# #                         instance_id=instance_id,
# #                         hostname=hostname,
# #                     )

# #             # ------------------------------------------------
# #             # Normal mode
# #             # ------------------------------------------------

# #             else:

# #                 await send_heartbeat(
# #                     redis_client,
# #                     agent_id=agent_id,
# #                     instance_id=instance_id,
# #                     hostname=hostname,
# #                 )

# #             await asyncio.sleep(
# #                 interval
# #             )

# #         except asyncio.CancelledError:

# #             print(
# #                 f"[HEARTBEAT] Stopped for "
# #                 f"{agent_id}"
# #             )

# #             raise

# #         except Exception as error:

# #             # The heartbeat mechanism itself must never
# #             # become the reason an agent dies.

# #             print(
# #                 f"[HEARTBEAT] Loop error for "
# #                 f"{agent_id}: {error}"
# #             )

# #             try:
# #                 await asyncio.sleep(
# #                     interval
# #                 )
# #             except asyncio.CancelledError:
# #                 raise

















# """
# Agent heartbeat infrastructure.

# Heartbeat events are system/liveness events.

# They are intentionally kept separate from normal AI event
# processing semantics.

# Heartbeat contains:

# - agent identity
# - process instance identity
# - hostname
# - status
# - timestamp
# - basic lifecycle information

# Redis Streams require scalar field values. Nested heartbeat
# objects are therefore serialized as JSON strings before being
# published.

# The heartbeat loop must never terminate the agent merely
# because Redis temporarily becomes unavailable.
# """

# from __future__ import annotations

# import asyncio
# import json
# import os
# import socket
# import uuid
# from datetime import datetime, timezone
# from pathlib import Path
# from typing import Optional

# import redis.asyncio as redis


# # ============================================================
# # CONFIGURATION
# # ============================================================

# HEARTBEAT_STREAM = os.getenv(
#     "HEARTBEAT_STREAM",
#     "events.system",
# )

# HEARTBEAT_STATUS = "alive"


# # ============================================================
# # HELPERS
# # ============================================================

# def utc_now_iso() -> str:
#     """
#     Return current UTC time in ISO-8601 format.
#     """
#     return datetime.now(timezone.utc).isoformat()


# def _json(value: object) -> str:
#     """
#     Serialize a Python object into a compact JSON string.

#     Redis Streams accept scalar field values, not nested
#     dictionaries/lists.
#     """
#     return json.dumps(
#         value,
#         separators=(",", ":"),
#         ensure_ascii=False,
#     )


# # ============================================================
# # HEARTBEAT
# # ============================================================

# async def send_heartbeat(
#     redis_client: redis.Redis,
#     *,
#     agent_id: str,
#     instance_id: str,
#     hostname: Optional[str] = None,
#     status: str = HEARTBEAT_STATUS,
# ) -> bool:
#     """
#     Publish one heartbeat.

#     Returns:
#         True  -> heartbeat published
#         False -> heartbeat failed

#     Redis errors are intentionally handled here so a temporary
#     Redis outage does not crash the agent process.
#     """

#     hostname = hostname or socket.gethostname()

#     event_id = str(uuid.uuid4())
#     timestamp = utc_now_iso()

#     source = {
#         "agent_id": agent_id,
#         "instance_id": instance_id,
#         "hostname": hostname,
#     }

#     data = {
#         "status": status,
#     }

#     # --------------------------------------------------------
#     # Redis Streams require scalar values.
#     #
#     # Keep important top-level fields directly accessible and
#     # serialize nested structures as JSON strings.
#     # --------------------------------------------------------
#     redis_event = {
#         "event_id": event_id,
#         "event_type": "agent.heartbeat",
#         "version": "1.0",
#         "timestamp": timestamp,
#         "source": _json(source),
#         "data": _json(data),
#         "agent_id": agent_id,
#         "instance_id": instance_id,
#         "hostname": hostname,
#         "status": status,
#     }

#     try:
#         await redis_client.xadd(
#             HEARTBEAT_STREAM,
#             redis_event,
#         )

#         return True

#     except asyncio.CancelledError:
#         raise

#     except Exception as error:
#         print(
#             f"[HEARTBEAT] Failed for "
#             f"{agent_id} "
#             f"(instance={instance_id}): "
#             f"{error}"
#         )
#         return False


# # ============================================================
# # TEST FAILURE MODE
# # ============================================================

# def heartbeat_failure_test_enabled(
#     agent_id: str,
# ) -> bool:
#     """
#     Determine whether heartbeat failure injection is enabled
#     for this agent.

#     Environment variable:

#         TEST_HEARTBEAT_FAILURE_AGENT=behavior-01
#     """

#     target = os.getenv(
#         "TEST_HEARTBEAT_FAILURE_AGENT",
#         "",
#     ).strip()

#     return bool(
#         target and target == agent_id
#     )


# def get_marker_file(
#     agent_id: str,
# ) -> Path:
#     """
#     Return the heartbeat failure-test marker path.

#     The project root can be explicitly configured with
#     PROJECT_ROOT. Otherwise the current working directory
#     is used.
#     """

#     project_root = Path(
#         os.getenv(
#             "PROJECT_ROOT",
#             os.getcwd(),
#         )
#     )

#     marker_dir = (
#         project_root
#         / "data"
#         / "heartbeat_tests"
#     )

#     marker_dir.mkdir(
#         parents=True,
#         exist_ok=True,
#     )

#     return marker_dir / f"{agent_id}.triggered"


# # ============================================================
# # HEARTBEAT LOOP
# # ============================================================

# async def heartbeat_loop(
#     redis_client: redis.Redis,
#     *,
#     agent_id: str,
#     instance_id: str,
#     hostname: Optional[str] = None,
#     interval: int = 10,
# ) -> None:
#     """
#     Continuously publish heartbeats.

#     Important:

#     Redis failure does NOT terminate the loop.

#     The supervisor should detect missing heartbeats and
#     independently decide whether the agent needs recovery.
#     """

#     if interval <= 0:
#         raise ValueError(
#             "Heartbeat interval must be greater than zero."
#         )

#     hostname = hostname or socket.gethostname()

#     test_enabled = heartbeat_failure_test_enabled(
#         agent_id
#     )

#     marker_file = get_marker_file(
#         agent_id
#     )

#     heartbeat_suppressed = False

#     if test_enabled:
#         print(
#             f"[HEARTBEAT] Failure injection enabled "
#             f"for {agent_id}"
#         )

#     while True:
#         try:
#             # ------------------------------------------------
#             # Failure injection
#             # ------------------------------------------------

#             if test_enabled:

#                 if (
#                     not heartbeat_suppressed
#                     and not marker_file.exists()
#                 ):
#                     success = await send_heartbeat(
#                         redis_client,
#                         agent_id=agent_id,
#                         instance_id=instance_id,
#                         hostname=hostname,
#                     )

#                     if success:
#                         print(
#                             f"[HEARTBEAT] Initial test "
#                             f"heartbeat sent for {agent_id}"
#                         )

#                         try:
#                             marker_file.write_text(
#                                 "heartbeat failure test triggered\n",
#                                 encoding="utf-8",
#                             )

#                             heartbeat_suppressed = True

#                             print(
#                                 f"[HEARTBEAT] Suppression enabled "
#                                 f"for {agent_id}"
#                             )

#                         except Exception as error:
#                             print(
#                                 f"[HEARTBEAT] Could not create "
#                                 f"test marker for {agent_id}: "
#                                 f"{error}"
#                             )

#                 elif heartbeat_suppressed:

#                     print(
#                         f"[HEARTBEAT] Suppressing heartbeat "
#                         f"for failure test: {agent_id}"
#                     )

#                 else:

#                     await send_heartbeat(
#                         redis_client,
#                         agent_id=agent_id,
#                         instance_id=instance_id,
#                         hostname=hostname,
#                     )

#             # ------------------------------------------------
#             # Normal mode
#             # ------------------------------------------------

#             else:

#                 await send_heartbeat(
#                     redis_client,
#                     agent_id=agent_id,
#                     instance_id=instance_id,
#                     hostname=hostname,
#                 )

#             await asyncio.sleep(interval)

#         except asyncio.CancelledError:

#             print(
#                 f"[HEARTBEAT] Stopped for "
#                 f"{agent_id}"
#             )

#             raise

#         except Exception as error:

#             # The heartbeat mechanism itself must never
#             # become the reason an agent dies.

#             print(
#                 f"[HEARTBEAT] Loop error for "
#                 f"{agent_id}: {error}"
#             )

#             try:
#                 await asyncio.sleep(interval)

#             except asyncio.CancelledError:
#                 raise












"""
Agent heartbeat infrastructure.

Heartbeat events are system/liveness events.

Responsibilities
----------------
- Publish periodic agent heartbeats.
- Keep heartbeat publishing isolated from agent processing.
- Never terminate an agent because Redis temporarily fails.
- Provide deterministic heartbeat failure injection for testing.

Heartbeat failure test
----------------------
Set:

    TEST_HEARTBEAT_FAILURE_AGENT=person-detector-01

The targeted agent will:

1. Send exactly one heartbeat.
2. Stop sending heartbeats.
3. Continue running normally.

This allows the monitoring system to detect:

    heartbeat timeout
        ->
    DEAD
        ->
    supervisor recovery

The failure is intentionally limited to heartbeat publication.
The worker process itself remains alive.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import uuid
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as redis


# ============================================================
# CONFIGURATION
# ============================================================

HEARTBEAT_STREAM = os.getenv(
    "HEARTBEAT_STREAM",
    "events.system",
)

HEARTBEAT_STATUS = "alive"


# ============================================================
# HELPERS
# ============================================================

def utc_now_iso() -> str:
    """
    Return current UTC time in ISO-8601 format.
    """
    return datetime.now(timezone.utc).isoformat()


def _json(value: object) -> str:
    """
    Serialize nested heartbeat data into a Redis-safe scalar.
    """
    return json.dumps(
        value,
        separators=(",", ":"),
        ensure_ascii=False,
    )


# ============================================================
# HEARTBEAT
# ============================================================

async def send_heartbeat(
    redis_client: redis.Redis,
    *,
    agent_id: str,
    instance_id: str,
    hostname: Optional[str] = None,
    status: str = HEARTBEAT_STATUS,
) -> bool:
    """
    Publish one heartbeat.

    Returns:
        True  -> heartbeat published
        False -> heartbeat failed

    Redis errors are intentionally swallowed so that the
    heartbeat mechanism itself cannot crash the worker.
    """

    hostname = hostname or socket.gethostname()

    event_id = str(uuid.uuid4())
    timestamp = utc_now_iso()

    source = {
        "agent_id": agent_id,
        "instance_id": instance_id,
        "hostname": hostname,
    }

    data = {
        "status": status,
    }

    # Redis Streams require scalar values.
    redis_event = {
        "event_id": event_id,
        "event_type": "agent.heartbeat",
        "version": "1.0",
        "timestamp": timestamp,

        # Nested structures are serialized.
        "source": _json(source),
        "data": _json(data),

        # Important fields remain directly searchable.
        "agent_id": agent_id,
        "instance_id": instance_id,
        "hostname": hostname,
        "status": status,
    }

    try:
        await redis_client.xadd(
            HEARTBEAT_STREAM,
            redis_event,
        )
        return True

    except asyncio.CancelledError:
        raise

    except Exception as error:
        print(
            "[HEARTBEAT] Failed for "
            f"{agent_id} "
            f"(instance={instance_id}): "
            f"{error}"
        )
        return False


# ============================================================
# FAILURE INJECTION
# ============================================================

def heartbeat_failure_test_enabled(
    agent_id: str,
) -> bool:
    """
    Determine whether heartbeat failure injection is enabled.

    Environment variable:

        TEST_HEARTBEAT_FAILURE_AGENT=person-detector-01

    The environment is evaluated when the heartbeat loop starts.
    """

    target = os.getenv(
        "TEST_HEARTBEAT_FAILURE_AGENT",
        "",
    ).strip()

    return bool(
        target and target == agent_id
    )


# ============================================================
# HEARTBEAT LOOP
# ============================================================

async def heartbeat_loop(
    redis_client: redis.Redis,
    *,
    agent_id: str,
    instance_id: str,
    hostname: Optional[str] = None,
    interval: int = 10,
) -> None:
    """
    Continuously publish heartbeats.

    Normal mode
    -----------
    Heartbeat is published every `interval` seconds.

    Failure-test mode
    ------------------
    If TEST_HEARTBEAT_FAILURE_AGENT matches this agent:

        - exactly one heartbeat is sent
        - subsequent heartbeats are suppressed
        - worker process remains alive

    This simulates a broken heartbeat/liveness signal without
    killing the actual worker.
    """

    if interval <= 0:
        raise ValueError(
            "Heartbeat interval must be greater than zero."
        )

    hostname = hostname or socket.gethostname()

    test_enabled = heartbeat_failure_test_enabled(
        agent_id
    )

    heartbeat_suppressed = False

    if test_enabled:
        print(
            "[HEARTBEAT] "
            "FAILURE INJECTION ENABLED for "
            f"{agent_id}"
        )
        print(
            "[HEARTBEAT] "
            "This worker will send ONE heartbeat "
            "and then stop heartbeats."
        )

    while True:
        try:

            # ==================================================
            # HEARTBEAT FAILURE TEST
            # ==================================================

            if test_enabled:

                if not heartbeat_suppressed:

                    success = await send_heartbeat(
                        redis_client,
                        agent_id=agent_id,
                        instance_id=instance_id,
                        hostname=hostname,
                    )

                    if success:
                        print(
                            "[HEARTBEAT] "
                            f"Initial test heartbeat sent "
                            f"for {agent_id}"
                        )

                        heartbeat_suppressed = True

                        print(
                            "[HEARTBEAT] "
                            f"Heartbeat suppression ACTIVE "
                            f"for {agent_id}"
                        )

                else:
                    # IMPORTANT:
                    # Do NOT send another heartbeat.
                    print(
                        "[HEARTBEAT] "
                        f"Suppressing heartbeat for "
                        f"failure test: {agent_id}"
                    )

            # ==================================================
            # NORMAL MODE
            # ==================================================

            else:

                await send_heartbeat(
                    redis_client,
                    agent_id=agent_id,
                    instance_id=instance_id,
                    hostname=hostname,
                )

            await asyncio.sleep(interval)

        except asyncio.CancelledError:

            print(
                "[HEARTBEAT] "
                f"Stopped for {agent_id}"
            )

            raise

        except Exception as error:

            # The heartbeat mechanism must NEVER become
            # the reason the worker process dies.

            print(
                "[HEARTBEAT] "
                f"Loop error for {agent_id}: "
                f"{error}"
            )

            try:
                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                raise