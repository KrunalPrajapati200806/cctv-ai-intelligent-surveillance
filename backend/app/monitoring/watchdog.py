# # import logging
# # from datetime import datetime, timezone
# # import redis
# # import asyncio
# # import json
# # import redis.asyncio as redis

# # from app.messaging.redis_client import redis_client
# # from app.monitoring.agent_registry import agent_registry

# # # ============================================================
# # # CONFIG
# # # ============================================================

# # STREAM_NAME = "events.system"
# # GROUP_NAME = "heartbeat-workers"
# # CONSUMER_NAME = "heartbeat-consumer-01"

# # READ_COUNT = 10
# # BLOCK_MS = 5000
# # RETRY_DELAY_SECONDS = 2

# # # Agent is considered dead if no heartbeat is received
# # # within this number of seconds.
# # HEARTBEAT_TIMEOUT_SECONDS = 30

# # # How frequently the watchdog checks for dead agents.
# # WATCHDOG_INTERVAL_SECONDS = 5


# # # ============================================================
# # # LOGGING
# # # ============================================================

# # logging.basicConfig(
# #     level=logging.INFO,
# #     format=(
# #         "%(asctime)s | "
# #         "%(levelname)s | "
# #         "%(name)s | "
# #         "%(message)s"
# #     ),
# # )

# # logger = logging.getLogger("heartbeat-watchdog")


# # # ============================================================
# # # AGENT REGISTRY
# # # ============================================================


# # # ============================================================
# # # ENSURE CONSUMER GROUP
# # # ============================================================

# # async def ensure_consumer_group():
# #     try:
# #         await redis_client.xgroup_create(
# #             name=STREAM_NAME,
# #             groupname=GROUP_NAME,
# #             id="0",
# #             mkstream=True,
# #         )

# #         logger.info(
# #             "Created consumer group: %s",
# #             GROUP_NAME,
# #         )

# #     except redis.ResponseError as error:
# #         if "BUSYGROUP" in str(error):
# #             logger.info(
# #                 "Consumer group already exists: %s",
# #                 GROUP_NAME,
# #             )
# #         else:
# #             raise


# # # ============================================================
# # # ACK MESSAGE
# # # ============================================================

# # async def acknowledge(message_id):
# #     await redis_client.xack(
# #         STREAM_NAME,
# #         GROUP_NAME,
# #         message_id,
# #     )


# # # ============================================================
# # # NORMALIZE REDIS VALUE
# # # ============================================================

# # def decode_value(value):
# #     if isinstance(value, bytes):
# #         return value.decode("utf-8")

# #     return value


# # # ============================================================
# # # NORMALIZE FIELDS
# # # ============================================================

# # def normalize_fields(fields):
# #     return {
# #         decode_value(key): decode_value(value)
# #         for key, value in fields.items()
# #     }


# # # ============================================================
# # # PARSE HEARTBEAT EVENT
# # # ============================================================

# # def parse_heartbeat(fields):
# #     """
# #     Supports both heartbeat formats.

# #     Format 1:
# #         {
# #             "event_type": "agent.heartbeat",
# #             "source_agent_id": "agent-01"
# #         }

# #     Format 2:
# #         {
# #             "event": "{\"event_type\":\"agent.heartbeat\", ...}"
# #         }

# #     Also supports:

# #         {
# #             "event": {
# #                 "event_type": "agent.heartbeat",
# #                 ...
# #             }
# #         }
# #     """

# #     fields = normalize_fields(fields)

# #     # --------------------------------------------------------
# #     # Direct Redis fields
# #     # --------------------------------------------------------

# #     event_type = fields.get("event_type")

# #     if event_type == "agent.heartbeat":
# #         agent_id = (
# #             fields.get("source_agent_id")
# #             or fields.get("agent_id")
# #         )

# #         return {
# #             "event_type": event_type,
# #             "agent_id": agent_id,
# #         }

# #     # --------------------------------------------------------
# #     # JSON event field
# #     # --------------------------------------------------------

# #     raw_event = fields.get("event")

# #     if not raw_event:
# #         return None

# #     # --------------------------------------------------------
# #     # Event already decoded as dict
# #     # --------------------------------------------------------

# #     if isinstance(raw_event, dict):
# #         event = raw_event

# #     else:
# #         if isinstance(raw_event, bytes):
# #             raw_event = raw_event.decode("utf-8")

# #         try:
# #             event = json.loads(raw_event)
# #         except (
# #             json.JSONDecodeError,
# #             TypeError,
# #         ):
# #             return None

# #     if not isinstance(event, dict):
# #         return None

# #     # --------------------------------------------------------
# #     # Validate event type
# #     # --------------------------------------------------------

# #     event_type = event.get("event_type")

# #     if event_type != "agent.heartbeat":
# #         return None

# #     # --------------------------------------------------------
# #     # Resolve agent ID
# #     # --------------------------------------------------------

# #     source = event.get("source")

# #     if not isinstance(source, dict):
# #         source = {}

# #     agent_id = (
# #         event.get("source_agent_id")
# #         or event.get("agent_id")
# #         or source.get("agent_id")
# #     )

# #     return {
# #         "event_type": event_type,
# #         "agent_id": agent_id,
# #     }


# # # ============================================================
# # # PROCESS HEARTBEAT
# # # ============================================================

# # async def process_heartbeat(
# #     message_id,
# #     fields,
# # ):
# #     try:
# #         heartbeat = parse_heartbeat(fields)

# #         # ----------------------------------------------------
# #         # Ignore non-heartbeat events
# #         # ----------------------------------------------------

# #         if heartbeat is None:
# #             await acknowledge(message_id)

# #             logger.debug(
# #                 "Ignored non-heartbeat message: %s",
# #                 message_id,
# #             )

# #             return

# #         # ----------------------------------------------------
# #         # Resolve agent ID
# #         # ----------------------------------------------------

# #         agent_id = heartbeat.get("agent_id")

# #         if not agent_id:
# #             logger.warning(
# #                 "Invalid heartbeat without agent ID: %s",
# #                 message_id,
# #             )

# #             await acknowledge(message_id)
# #             return

# #         # ----------------------------------------------------
# #         # Update registry
# #         # ----------------------------------------------------

# #         agent_registry.update_heartbeat(
# #             agent_id
# #         )

# #         logger.info(
# #             "Heartbeat received: %s",
# #             agent_id,
# #         )

# #         # ----------------------------------------------------
# #         # ACK only after successful processing
# #         # ----------------------------------------------------

# #         await acknowledge(message_id)

# #         logger.debug(
# #             "ACK: %s",
# #             message_id,
# #         )

# #     except asyncio.CancelledError:
# #         raise

# #     except Exception:
# #         logger.exception(
# #             "Heartbeat processing failed for message %s",
# #             message_id,
# #         )

# #         # IMPORTANT:
# #         # Do not ACK here.
# #         #
# #         # If registry processing fails, leaving the message
# #         # pending allows it to be recovered/reprocessed.
# #         return


# # # ============================================================
# # # MARK DEAD AGENTS
# # # ============================================================

# # def check_dead_agents():
# #     """
# #     Mark agents as dead when their last heartbeat is older
# #     than HEARTBEAT_TIMEOUT_SECONDS.
# #     """

# #     now = datetime.now(timezone.utc)

# #     agents = agent_registry.get_all_agents()

# #     for agent_id, agent in agents.items():
# #         last_heartbeat = agent.get(
# #             "last_heartbeat"
# #         )

# #         if not last_heartbeat:
# #             continue

# #         # ----------------------------------------------------
# #         # Make sure datetime is timezone-aware
# #         # ----------------------------------------------------

# #         if last_heartbeat.tzinfo is None:
# #             last_heartbeat = last_heartbeat.replace(
# #                 tzinfo=timezone.utc
# #             )

# #         age_seconds = (
# #             now - last_heartbeat
# #         ).total_seconds()

# #         # ----------------------------------------------------
# #         # Agent timeout
# #         # ----------------------------------------------------

# #         if (
# #             age_seconds
# #             > HEARTBEAT_TIMEOUT_SECONDS
# #             and agent.get("status") != "dead"
# #         ):
# #             agent_registry.mark_dead(
# #                 agent_id
# #             )

# #             logger.warning(
# #                 "Agent marked DEAD: %s "
# #                 "(last heartbeat %.1fs ago)",
# #                 agent_id,
# #                 age_seconds,
# #             )


# # # ============================================================
# # # WATCHDOG LOOP
# # # ============================================================

# # async def watchdog_loop():
# #     logger.info(
# #         "Agent watchdog started"
# #     )

# #     while True:
# #         try:
# #             check_dead_agents()

# #             await asyncio.sleep(
# #                 WATCHDOG_INTERVAL_SECONDS
# #             )

# #         except asyncio.CancelledError:
# #             logger.info(
# #                 "Agent watchdog stopped."
# #             )
# #             raise

# #         except Exception:
# #             logger.exception(
# #                 "Agent watchdog error"
# #             )

# #             await asyncio.sleep(
# #                 RETRY_DELAY_SECONDS
# #             )


# # # ============================================================
# # # HEARTBEAT CONSUMER
# # # ============================================================

# # async def consume_heartbeats():
# #     await ensure_consumer_group()

# #     logger.info(
# #         "Heartbeat consumer started: %s",
# #         CONSUMER_NAME,
# #     )

# #     while True:
# #         try:
# #             messages = await redis_client.xreadgroup(
# #                 groupname=GROUP_NAME,
# #                 consumername=CONSUMER_NAME,
# #                 streams={
# #                     STREAM_NAME: ">"
# #                 },
# #                 count=READ_COUNT,
# #                 block=BLOCK_MS,
# #             )

# #             if not messages:
# #                 continue

# #             for stream_name, stream_messages in messages:
# #                 logger.debug(
# #                     "Received %d message(s) from %s",
# #                     len(stream_messages),
# #                     stream_name,
# #                 )

# #                 for message_id, fields in stream_messages:
# #                     await process_heartbeat(
# #                         message_id,
# #                         fields,
# #                     )

# #         except asyncio.CancelledError:
# #             logger.info(
# #                 "Heartbeat consumer stopped."
# #             )
# #             raise

# #         except Exception:
# #             logger.exception(
# #                 "Heartbeat consumer error"
# #             )

# #             await asyncio.sleep(
# #                 RETRY_DELAY_SECONDS
# #             )


# # # ============================================================
# # # MAIN
# # # ============================================================

# # async def main():
# #     consumer_task = asyncio.create_task(
# #         consume_heartbeats()
# #     )

# #     watchdog_task = asyncio.create_task(
# #         watchdog_loop()
# #     )

# #     try:
# #         await asyncio.gather(
# #             consumer_task,
# #             watchdog_task,
# #         )

# #     except asyncio.CancelledError:
# #         logger.info(
# #             "Watchdog service shutting down."
# #         )

# #         consumer_task.cancel()
# #         watchdog_task.cancel()

# #         await asyncio.gather(
# #             consumer_task,
# #             watchdog_task,
# #             return_exceptions=True,
# #         )

# #         raise


# # # ============================================================
# # # DIRECT EXECUTION
# # # ============================================================

# # if __name__ == "__main__":
# #     try:
# #         asyncio.run(main())

# #     except KeyboardInterrupt:
# #         logger.info(
# #             "Heartbeat watchdog interrupted."
# #         )



























# import asyncio
# import os
# from datetime import datetime, timezone

# import redis.asyncio as redis

# from backend.app.monitoring.agent_registry import agent_registry


# STREAM_NAME = "events.system"
# GROUP_NAME = "heartbeat-workers"
# CONSUMER_NAME = os.getenv(
#     "WATCHDOG_CONSUMER_NAME",
#     "watchdog-01",
# )

# READ_COUNT = 10
# BLOCK_MS = 5000

# HEARTBEAT_TIMEOUT = float(
#     os.getenv(
#         "HEARTBEAT_TIMEOUT",
#         "30",
#     )
# )

# CHECK_INTERVAL = float(
#     os.getenv(
#         "WATCHDOG_CHECK_INTERVAL",
#         "5",
#     )
# )

# RETRY_DELAY = 2


# def decode(value):
#     if isinstance(value, bytes):
#         return value.decode("utf-8")

#     return value


# def normalize_fields(fields):
#     return {
#         decode(key): decode(value)
#         for key, value in fields.items()
#     }


# def parse_heartbeat(fields):
#     fields = normalize_fields(fields)

#     if fields.get("event_type") == "agent.heartbeat":
#         agent_id = fields.get("source_agent_id")

#         if agent_id:
#             return agent_id

#     event = fields.get("event")

#     if isinstance(event, str):
#         try:
#             import json

#             event = json.loads(event)

#         except Exception:
#             return None

#     if isinstance(event, dict):
#         if event.get("event_type") != "agent.heartbeat":
#             return None

#         agent_id = event.get("source_agent_id")

#         if agent_id:
#             return agent_id

#     return None


# async def ensure_consumer_group(redis_client):
#     try:
#         await redis_client.xgroup_create(
#             STREAM_NAME,
#             GROUP_NAME,
#             id="0-0",
#             mkstream=True,
#         )

#         print(
#             f"Created watchdog consumer group "
#             f"{GROUP_NAME}"
#         )

#     except redis.ResponseError as error:
#         if "BUSYGROUP" not in str(error):
#             raise


# async def process_heartbeat(
#     redis_client,
#     message_id,
#     fields,
# ):
#     try:
#         agent_id = parse_heartbeat(fields)

#         if not agent_id:
#             await redis_client.xack(
#                 STREAM_NAME,
#                 GROUP_NAME,
#                 message_id,
#             )
#             return

#         agent_registry.update_heartbeat(agent_id)

#         await redis_client.xack(
#             STREAM_NAME,
#             GROUP_NAME,
#             message_id,
#         )

#         print(
#             f"[WATCHDOG] heartbeat received: "
#             f"{agent_id}"
#         )

#     except Exception as error:
#         print(
#             f"[WATCHDOG HEARTBEAT ERROR] "
#             f"{message_id}: {error}"
#         )


# async def heartbeat_consumer_loop(redis_client):
#     await ensure_consumer_group(redis_client)

#     while True:
#         try:
#             messages = await redis_client.xreadgroup(
#                 groupname=GROUP_NAME,
#                 consumername=CONSUMER_NAME,
#                 streams={
#                     STREAM_NAME: ">"
#                 },
#                 count=READ_COUNT,
#                 block=BLOCK_MS,
#             )

#             if not messages:
#                 continue

#             for _, stream_messages in messages:
#                 for message_id, fields in stream_messages:
#                     await process_heartbeat(
#                         redis_client,
#                         message_id,
#                         fields,
#                     )

#         except asyncio.CancelledError:
#             raise

#         except Exception as error:
#             print(
#                 f"[WATCHDOG CONSUMER ERROR] {error}"
#             )

#             await asyncio.sleep(
#                 RETRY_DELAY
#             )


# def check_dead_agents():
#     now = datetime.now(timezone.utc)

#     agents = agent_registry.get_all_agents()

#     for agent_id, agent in agents.items():

#         last_heartbeat = agent.get(
#             "last_heartbeat"
#         )

#         if not last_heartbeat:
#             continue

#         age = (
#             now - last_heartbeat
#         ).total_seconds()

#         if age > HEARTBEAT_TIMEOUT:

#             if agent.get("status") != "dead":

#                 agent_registry.mark_dead(
#                     agent_id
#                 )

#                 print(
#                     f"[WATCHDOG] "
#                     f"AGENT DEAD: {agent_id} "
#                     f"(last heartbeat "
#                     f"{age:.1f}s ago)"
#                 )


# async def watchdog_loop(
#     registry=None,
#     check_interval=None,
# ):
#     """
#     Background watchdog.

#     registry is kept as an optional argument
#     for compatibility with existing tests.
#     """

#     active_registry = registry or agent_registry

#     interval = (
#         check_interval
#         if check_interval is not None
#         else CHECK_INTERVAL
#     )

#     while True:
#         try:
#             now = datetime.now(timezone.utc)

#             agents = active_registry.get_all_agents()

#             for agent_id, agent in agents.items():

#                 last_heartbeat = agent.get(
#                     "last_heartbeat"
#                 )

#                 if not last_heartbeat:
#                     continue

#                 age = (
#                     now - last_heartbeat
#                 ).total_seconds()

#                 if age > HEARTBEAT_TIMEOUT:

#                     if agent.get("status") != "dead":

#                         active_registry.mark_dead(
#                             agent_id
#                         )

#                         print(
#                             f"[WATCHDOG] "
#                             f"AGENT DEAD: "
#                             f"{agent_id} "
#                             f"(age={age:.1f}s)"
#                         )

#             await asyncio.sleep(interval)

#         except asyncio.CancelledError:
#             raise

#         except Exception as error:
#             print(
#                 f"[WATCHDOG LOOP ERROR] "
#                 f"{error}"
#             )

#             await asyncio.sleep(interval)


# async def main():
#     redis_client = redis.Redis(
#         host=os.getenv(
#             "REDIS_HOST",
#             "localhost",
#         ),
#         port=int(
#             os.getenv(
#                 "REDIS_PORT",
#                 "6379",
#             )
#         ),
#         decode_responses=True,
#         socket_timeout=None,
#         health_check_interval=30,
#     )

#     try:

#         consumer_task = asyncio.create_task(
#             heartbeat_consumer_loop(
#                 redis_client
#             )
#         )

#         watchdog_task = asyncio.create_task(
#             watchdog_loop()
#         )

#         await asyncio.gather(
#             consumer_task,
#             watchdog_task,
#         )

#     finally:
#         await redis_client.aclose()


# if __name__ == "__main__":
#     asyncio.run(main())




























import asyncio
import os
from datetime import datetime, timezone

from backend.app.monitoring.agent_registry import (
    agent_registry,
)


HEARTBEAT_TIMEOUT = float(
    os.getenv(
        "HEARTBEAT_TIMEOUT",
        "30",
    )
)

CHECK_INTERVAL = float(
    os.getenv(
        "WATCHDOG_CHECK_INTERVAL",
        "5",
    )
)


def check_dead_agents(
    registry=None,
):
    """
    Check every registered agent.

    This function does NOT consume Redis.
    Heartbeats are consumed by heartbeat_consumer.py.
    """

    active_registry = (
        registry or agent_registry
    )

    now = datetime.now(timezone.utc)

    agents = (
        active_registry.get_all_agents()
    )

    for agent_id, agent in agents.items():

        last_heartbeat = agent.get(
            "last_heartbeat"
        )

        if not last_heartbeat:
            continue

        age = (
            now - last_heartbeat
        ).total_seconds()

        status = agent.get(
            "status"
        )

        if (
            age > HEARTBEAT_TIMEOUT
            and status != "DEAD"
        ):

            active_registry.mark_dead(
                agent_id
            )

            print(
                f"[WATCHDOG] "
                f"AGENT DEAD: "
                f"{agent_id} "
                f"(age={age:.1f}s)"
            )


async def watchdog_loop(
    registry=None,
    check_interval=None,
):
    """
    Periodically checks agent health.

    No Redis consumption occurs here.
    """

    active_registry = (
        registry or agent_registry
    )

    interval = (
        check_interval
        if check_interval is not None
        else CHECK_INTERVAL
    )

    print(
        "[WATCHDOG] Health monitor started."
    )

    print(
        f"[WATCHDOG] "
        f"Heartbeat timeout: "
        f"{HEARTBEAT_TIMEOUT}s"
    )

    print(
        f"[WATCHDOG] "
        f"Check interval: "
        f"{interval}s"
    )

    while True:
        try:

            check_dead_agents(
                active_registry
            )

            await asyncio.sleep(
                interval
            )

        except asyncio.CancelledError:
            print(
                "[WATCHDOG] "
                "Shutdown requested."
            )
            raise

        except Exception as error:

            print(
                f"[WATCHDOG ERROR] "
                f"{error}"
            )

            # Watchdog itself must survive
            # unexpected errors.
            await asyncio.sleep(
                interval
            )


async def main():
    await watchdog_loop()


if __name__ == "__main__":
    asyncio.run(main())