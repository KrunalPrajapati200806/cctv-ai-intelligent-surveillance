# # # # # import asyncio
# # # # # import json

# # # # # import redis.asyncio as redis

# # # # # from app.messaging.redis_client import redis_client
# # # # # from app.monitoring.agent_registry import AgentRegistry


# # # # # STREAM_NAME = "events.system"
# # # # # GROUP_NAME = "heartbeat-workers"
# # # # # CONSUMER_NAME = "heartbeat-consumer-01"

# # # # # registry = AgentRegistry()


# # # # # async def ensure_consumer_group():
# # # # #     try:
# # # # #         await redis_client.xgroup_create(
# # # # #             STREAM_NAME,
# # # # #             GROUP_NAME,
# # # # #             id="0",
# # # # #             mkstream=True,
# # # # #         )

# # # # #         print(
# # # # #             f"Created consumer group: {GROUP_NAME}"
# # # # #         )

# # # # #     except redis.ResponseError as error:
# # # # #         if "BUSYGROUP" in str(error):
# # # # #             print(
# # # # #                 f"Consumer group already exists: {GROUP_NAME}"
# # # # #             )
# # # # #         else:
# # # # #             raise


# # # # # async def consume_heartbeats():
# # # # #     await ensure_consumer_group()

# # # # #     print(
# # # # #         f"Heartbeat consumer started: {CONSUMER_NAME}"
# # # # #     )

# # # # #     while True:
# # # # #         try:
# # # # #             messages = await redis_client.xreadgroup(
# # # # #                 groupname=GROUP_NAME,
# # # # #                 consumername=CONSUMER_NAME,
# # # # #                 streams={
# # # # #                     STREAM_NAME: ">"
# # # # #                 },
# # # # #                 count=10,
# # # # #                 block=5000,
# # # # #             )

# # # # #             if not messages:
# # # # #                 continue

# # # # #             for stream_name, stream_messages in messages:
# # # # #                 for message_id, fields in stream_messages:

# # # # #                     try:
# # # # #                         event_type = fields.get(
# # # # #                             "event_type"
# # # # #                         )

# # # # #                         if event_type != "agent.heartbeat":
# # # # #                             await redis_client.xack(
# # # # #                                 STREAM_NAME,
# # # # #                                 GROUP_NAME,
# # # # #                                 message_id,
# # # # #                             )
# # # # #                             continue

# # # # #                         agent_id = fields.get(
# # # # #                             "source_agent_id"
# # # # #                         )

# # # # #                         if not agent_id:
# # # # #                             print(
# # # # #                                 f"Invalid heartbeat: "
# # # # #                                 f"{message_id}"
# # # # #                             )

# # # # #                             await redis_client.xack(
# # # # #                                 STREAM_NAME,
# # # # #                                 GROUP_NAME,
# # # # #                                 message_id,
# # # # #                             )
# # # # #                             continue

# # # # #                         registry.update_heartbeat(
# # # # #                             agent_id
# # # # #                         )

# # # # #                         print(
# # # # #                             f"Heartbeat received: "
# # # # #                             f"{agent_id}"
# # # # #                         )

# # # # #                         await redis_client.xack(
# # # # #                             STREAM_NAME,
# # # # #                             GROUP_NAME,
# # # # #                             message_id,
# # # # #                         )

# # # # #                     except Exception as error:
# # # # #                         print(
# # # # #                             f"Heartbeat processing error "
# # # # #                             f"for {message_id}: {error}"
# # # # #                         )

# # # # #         except asyncio.CancelledError:
# # # # #             print(
# # # # #                 "Heartbeat consumer stopped."
# # # # #             )
# # # # #             raise

# # # # #         except Exception as error:
# # # # #             print(
# # # # #                 f"Heartbeat consumer error: {error}"
# # # # #             )

# # # # #             await asyncio.sleep(2)


# # # # # async def main():
# # # # #     try:
# # # # #         await consume_heartbeats()

# # # # #     finally:
# # # # #         await redis_client.aclose()


# # # # # if __name__ == "__main__":
# # # # #     asyncio.run(main())











# # # # import asyncio
# # # # import json
# # # # import os

# # # # import redis.asyncio as redis

# # # # from backend.app.monitoring.agent_registry import agent_registry


# # # # REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
# # # # REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# # # # STREAM_NAME = "events.system"
# # # # GROUP_NAME = "heartbeat-workers"
# # # # CONSUMER_NAME = os.getenv(
# # # #     "HEARTBEAT_CONSUMER_NAME",
# # # #     "heartbeat-consumer-01",
# # # # )

# # # # READ_COUNT = 10
# # # # BLOCK_MS = 5000
# # # # RETRY_DELAY = 2


# # # # def decode(value):
# # # #     if isinstance(value, bytes):
# # # #         return value.decode("utf-8")
# # # #     return value


# # # # def normalize_fields(fields):
# # # #     return {
# # # #         decode(key): decode(value)
# # # #         for key, value in fields.items()
# # # #     }


# # # # def parse_heartbeat(fields):
# # # #     """
# # # #     Supports both:
# # # #         direct Redis heartbeat fields
# # # #     and:
# # # #         {"event": "<JSON heartbeat>"}
# # # #     """

# # # #     fields = normalize_fields(fields)

# # # #     event = fields.get("event")

# # # #     if event:
# # # #         if isinstance(event, str):
# # # #             try:
# # # #                 event = json.loads(event)
# # # #             except json.JSONDecodeError:
# # # #                 return None

# # # #         if isinstance(event, dict):
# # # #             fields = {
# # # #                 **fields,
# # # #                 **event,
# # # #             }

# # # #     if fields.get("event_type") != "agent.heartbeat":
# # # #         return None

# # # #     agent_id = fields.get("source_agent_id")

# # # #     if not agent_id:
# # # #         return None

# # # #     return {
# # # #         "agent_id": agent_id,
# # # #         "status": fields.get("status", "alive"),
# # # #         "event_id": fields.get("event_id"),
# # # #         "timestamp": fields.get("timestamp"),
# # # #     }


# # # # async def ensure_consumer_group(redis_client):
# # # #     try:
# # # #         await redis_client.xgroup_create(
# # # #             STREAM_NAME,
# # # #             GROUP_NAME,
# # # #             id="0-0",
# # # #             mkstream=True,
# # # #         )
# # # #         print(
# # # #             f"Created Redis consumer group "
# # # #             f"{GROUP_NAME} on {STREAM_NAME}"
# # # #         )

# # # #     except redis.ResponseError as error:
# # # #         if "BUSYGROUP" not in str(error):
# # # #             raise


# # # # async def acknowledge(redis_client, message_id):
# # # #     await redis_client.xack(
# # # #         STREAM_NAME,
# # # #         GROUP_NAME,
# # # #         message_id,
# # # #     )


# # # # async def process_message(redis_client, message_id, fields):
# # # #     try:
# # # #         heartbeat = parse_heartbeat(fields)

# # # #         if heartbeat is None:
# # # #             await acknowledge(redis_client, message_id)
# # # #             return

# # # #         agent_id = heartbeat["agent_id"]

# # # #         # IMPORTANT:
# # # #         # Use the shared global registry.
# # # #         agent_registry.update_heartbeat(agent_id)

# # # #         print(
# # # #             f"[HEARTBEAT] {agent_id} -> ALIVE"
# # # #         )

# # # #         # ACK only after successful registry update.
# # # #         await acknowledge(redis_client, message_id)

# # # #     except Exception as error:
# # # #         print(
# # # #             f"[HEARTBEAT ERROR] "
# # # #             f"message={message_id} error={error}"
# # # #         )

# # # #         # Do NOT ACK failed processing.
# # # #         # Redis keeps the message pending.


# # # # async def heartbeat_consumer_loop(redis_client):
# # # #     await ensure_consumer_group(redis_client)

# # # #     print(
# # # #         f"Heartbeat consumer started: "
# # # #         f"{STREAM_NAME}/{GROUP_NAME}"
# # # #     )

# # # #     while True:
# # # #         try:
# # # #             messages = await redis_client.xreadgroup(
# # # #                 groupname=GROUP_NAME,
# # # #                 consumername=CONSUMER_NAME,
# # # #                 streams={
# # # #                     STREAM_NAME: ">"
# # # #                 },
# # # #                 count=READ_COUNT,
# # # #                 block=BLOCK_MS,
# # # #             )

# # # #             if not messages:
# # # #                 continue

# # # #             for _, stream_messages in messages:
# # # #                 for message_id, fields in stream_messages:
# # # #                     await process_message(
# # # #                         redis_client,
# # # #                         message_id,
# # # #                         fields,
# # # #                     )

# # # #         except asyncio.CancelledError:
# # # #             raise

# # # #         except Exception as error:
# # # #             print(
# # # #                 f"[HEARTBEAT CONSUMER ERROR] {error}"
# # # #             )
# # # #             await asyncio.sleep(RETRY_DELAY)


# # # # async def main():
# # # #     redis_client = redis.Redis(
# # # #         host=REDIS_HOST,
# # # #         port=REDIS_PORT,
# # # #         decode_responses=True,
# # # #         socket_timeout=None,
# # # #         health_check_interval=30,
# # # #     )

# # # #     try:
# # # #         await heartbeat_consumer_loop(redis_client)

# # # #     finally:
# # # #         await redis_client.aclose()


# # # # if __name__ == "__main__":
# # # #     asyncio.run(main())


























# # # import asyncio
# # # import json
# # # import os

# # # import redis.asyncio as redis

# # # from backend.app.monitoring.agent_registry import agent_registry


# # # REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
# # # REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# # # STREAM_NAME = "events.system"
# # # GROUP_NAME = "heartbeat-workers"

# # # CONSUMER_NAME = os.getenv(
# # #     "HEARTBEAT_CONSUMER_NAME",
# # #     "heartbeat-consumer-01",
# # # )

# # # READ_COUNT = 10
# # # BLOCK_MS = 5000
# # # RETRY_DELAY = 2


# # # def decode(value):
# # #     if isinstance(value, bytes):
# # #         return value.decode("utf-8")

# # #     return value


# # # def normalize_fields(fields):
# # #     return {
# # #         decode(key): decode(value)
# # #         for key, value in fields.items()
# # #     }


# # # def parse_heartbeat(fields):
# # #     """
# # #     Parse both:

# # #     1. Current BaseAgent heartbeat format:
# # #        {"event": "<JSON>"}

# # #     2. Direct Redis fields.
# # #     """

# # #     fields = normalize_fields(fields)

# # #     event = fields.get("event")

# # #     if event:
# # #         if isinstance(event, str):
# # #             try:
# # #                 event = json.loads(event)
# # #             except json.JSONDecodeError:
# # #                 return None

# # #         if isinstance(event, dict):
# # #             merged = {
# # #                 **fields,
# # #                 **event,
# # #             }
# # #             fields = merged

# # #     if fields.get("event_type") != "agent.heartbeat":
# # #         return None

# # #     agent_id = (
# # #         fields.get("source_agent_id")
# # #         or fields.get("agent_id")
# # #     )

# # #     if not agent_id:
# # #         source = fields.get("source")

# # #         if isinstance(source, str):
# # #             try:
# # #                 source = json.loads(source)
# # #             except json.JSONDecodeError:
# # #                 source = None

# # #         if isinstance(source, dict):
# # #             agent_id = source.get("agent_id")

# # #     if not agent_id:
# # #         return None

# # #     return {
# # #         "agent_id": agent_id,
# # #         "status": fields.get(
# # #             "status",
# # #             "alive",
# # #         ),
# # #         "event_id": fields.get(
# # #             "event_id"
# # #         ),
# # #         "timestamp": fields.get(
# # #             "timestamp"
# # #         ),
# # #         "instance_id": fields.get(
# # #             "instance_id"
# # #         ),
# # #         "hostname": fields.get(
# # #             "hostname"
# # #         ),
# # #     }


# # # async def ensure_consumer_group(redis_client):
# # #     try:
# # #         await redis_client.xgroup_create(
# # #             STREAM_NAME,
# # #             GROUP_NAME,
# # #             id="0-0",
# # #             mkstream=True,
# # #         )

# # #         print(
# # #             f"[HEARTBEAT] Created consumer group "
# # #             f"{GROUP_NAME}"
# # #         )

# # #     except redis.ResponseError as error:
# # #         if "BUSYGROUP" not in str(error):
# # #             raise


# # # async def acknowledge(
# # #     redis_client,
# # #     message_id,
# # # ):
# # #     await redis_client.xack(
# # #         STREAM_NAME,
# # #         GROUP_NAME,
# # #         message_id,
# # #     )


# # # async def process_message(
# # #     redis_client,
# # #     message_id,
# # #     fields,
# # # ):
# # #     try:
# # #         heartbeat = parse_heartbeat(fields)

# # #         if heartbeat is None:
# # #             await acknowledge(
# # #                 redis_client,
# # #                 message_id,
# # #             )
# # #             return

# # #         agent_id = heartbeat["agent_id"]

# # #         agent_registry.update_heartbeat(
# # #             agent_id=agent_id,
# # #             instance_id=heartbeat.get(
# # #                 "instance_id"
# # #             ),
# # #             hostname=heartbeat.get(
# # #                 "hostname"
# # #             ),
# # #         )

# # #         print(
# # #             f"[HEARTBEAT] {agent_id} -> ALIVE"
# # #         )

# # #         # ACK only after successful
# # #         # registry update.
# # #         await acknowledge(
# # #             redis_client,
# # #             message_id,
# # #         )

# # #     except Exception as error:
# # #         print(
# # #             f"[HEARTBEAT ERROR] "
# # #             f"message={message_id} "
# # #             f"error={error}"
# # #         )

# # #         # Do NOT ACK.
# # #         # Redis keeps the message pending.


# # # async def heartbeat_consumer_loop(
# # #     redis_client,
# # # ):
# # #     await ensure_consumer_group(
# # #         redis_client
# # #     )

# # #     print(
# # #         f"[HEARTBEAT] Consumer started: "
# # #         f"{STREAM_NAME}/{GROUP_NAME}"
# # #     )

# # #     while True:
# # #         try:
# # #             messages = await redis_client.xreadgroup(
# # #                 groupname=GROUP_NAME,
# # #                 consumername=CONSUMER_NAME,
# # #                 streams={
# # #                     STREAM_NAME: ">"
# # #                 },
# # #                 count=READ_COUNT,
# # #                 block=BLOCK_MS,
# # #             )

# # #             if not messages:
# # #                 continue

# # #             for _, stream_messages in messages:

# # #                 for message_id, fields in stream_messages:

# # #                     try:
# # #                         await process_message(
# # #                             redis_client,
# # #                             message_id,
# # #                             fields,
# # #                         )

# # #                     except Exception as error:
# # #                         print(
# # #                             "[HEARTBEAT MESSAGE "
# # #                             f"ISOLATION ERROR] "
# # #                             f"{message_id}: {error}"
# # #                         )

# # #         except asyncio.CancelledError:
# # #             raise

# # #         except Exception as error:
# # #             print(
# # #                 f"[HEARTBEAT CONSUMER ERROR] "
# # #                 f"{error}"
# # #             )

# # #             await asyncio.sleep(
# # #                 RETRY_DELAY
# # #             )


# # # async def main():
# # #     redis_client = redis.Redis(
# # #         host=REDIS_HOST,
# # #         port=REDIS_PORT,
# # #         decode_responses=True,
# # #         socket_timeout=None,
# # #         health_check_interval=30,
# # #     )

# # #     try:
# # #         await heartbeat_consumer_loop(
# # #             redis_client
# # #         )

# # #     finally:
# # #         await redis_client.aclose()


# # # if __name__ == "__main__":
# # #     asyncio.run(main())





















# # import asyncio
# # import json
# # import os

# # import redis.asyncio as redis

# # from backend.app.monitoring.agent_registry import agent_registry


# # # ============================================================
# # # REDIS CONFIGURATION
# # # ============================================================

# # REDIS_HOST = os.getenv(
# #     "REDIS_HOST",
# #     "localhost",
# # )

# # REDIS_PORT = int(
# #     os.getenv(
# #         "REDIS_PORT",
# #         "6379",
# #     )
# # )


# # # ============================================================
# # # STREAM CONFIGURATION
# # # ============================================================

# # STREAM_NAME = "events.system"

# # GROUP_NAME = "heartbeat-workers"

# # CONSUMER_NAME = os.getenv(
# #     "HEARTBEAT_CONSUMER_NAME",
# #     "heartbeat-consumer-01",
# # )


# # # ============================================================
# # # CONSUMER CONFIGURATION
# # # ============================================================

# # READ_COUNT = int(
# #     os.getenv(
# #         "HEARTBEAT_READ_COUNT",
# #         "10",
# #     )
# # )

# # BLOCK_MS = int(
# #     os.getenv(
# #         "HEARTBEAT_BLOCK_MS",
# #         "5000",
# #     )
# # )

# # RETRY_DELAY = float(
# #     os.getenv(
# #         "HEARTBEAT_RETRY_DELAY",
# #         "2",
# #     )
# # )


# # # ============================================================
# # # PENDING MESSAGE RECOVERY
# # # ============================================================

# # # A pending message older than this amount can be reclaimed.
# # #
# # # 30 seconds is appropriate for this heartbeat system because
# # # heartbeat timeout is currently 30 seconds.
# # #
# # # We deliberately use a slightly smaller value so a crashed
# # # consumer can recover pending messages promptly.
# # PENDING_IDLE_MS = int(
# #     os.getenv(
# #         "HEARTBEAT_PENDING_IDLE_MS",
# #         "15000",
# #     )
# # )


# # # ============================================================
# # # DECODING HELPERS
# # # ============================================================

# # def decode(value):
# #     """
# #     Convert Redis bytes into UTF-8 strings.

# #     Redis may return bytes when decode_responses=False.
# #     This helper keeps parsing compatible with either mode.
# #     """

# #     if isinstance(value, bytes):
# #         return value.decode(
# #             "utf-8",
# #             errors="replace",
# #         )

# #     return value


# # def normalize_fields(fields):
# #     """
# #     Normalize Redis hash fields into string keys/values.
# #     """

# #     return {
# #         decode(key): decode(value)
# #         for key, value in fields.items()
# #     }


# # # ============================================================
# # # HEARTBEAT PARSING
# # # ============================================================

# # def parse_heartbeat(fields):
# #     """
# #     Parse both supported heartbeat formats.

# #     Format 1:
# #         {
# #             "event": "<JSON>"
# #         }

# #     Format 2:
# #         Direct Redis fields.

# #     Returns:
# #         normalized heartbeat dictionary
# #         or None when the message is not a valid heartbeat.
# #     """

# #     fields = normalize_fields(fields)

# #     # --------------------------------------------------------
# #     # BaseAgent currently publishes:
# #     #
# #     # {"event": "<JSON encoded event>"}
# #     # --------------------------------------------------------

# #     event = fields.get(
# #         "event"
# #     )

# #     if event:
# #         if isinstance(event, str):
# #             try:
# #                 event = json.loads(event)

# #             except json.JSONDecodeError:
# #                 return None

# #         if isinstance(event, dict):
# #             merged = {
# #                 **fields,
# #                 **event,
# #             }

# #             fields = merged

# #     # --------------------------------------------------------
# #     # Verify event type.
# #     # --------------------------------------------------------

# #     if fields.get(
# #         "event_type"
# #     ) != "agent.heartbeat":
# #         return None

# #     # --------------------------------------------------------
# #     # Find agent ID.
# #     # --------------------------------------------------------

# #     agent_id = (
# #         fields.get(
# #             "source_agent_id"
# #         )
# #         or fields.get(
# #             "agent_id"
# #         )
# #     )

# #     # --------------------------------------------------------
# #     # Support nested source object.
# #     # --------------------------------------------------------

# #     if not agent_id:

# #         source = fields.get(
# #             "source"
# #         )

# #         if isinstance(source, str):

# #             try:
# #                 source = json.loads(
# #                     source
# #                 )

# #             except json.JSONDecodeError:
# #                 source = None

# #         if isinstance(source, dict):
# #             agent_id = source.get(
# #                 "agent_id"
# #             )

# #     if not agent_id:
# #         return None

# #     return {
# #         "agent_id": agent_id,

# #         "status": fields.get(
# #             "status",
# #             "alive",
# #         ),

# #         "event_id": fields.get(
# #             "event_id"
# #         ),

# #         "timestamp": fields.get(
# #             "timestamp"
# #         ),

# #         "instance_id": fields.get(
# #             "instance_id"
# #         ),

# #         "hostname": fields.get(
# #             "hostname"
# #         ),
# #     }


# # # ============================================================
# # # CONSUMER GROUP
# # # ============================================================

# # async def ensure_consumer_group(
# #     redis_client,
# # ):
# #     """
# #     Ensure the heartbeat consumer group exists.
# #     """

# #     try:

# #         await redis_client.xgroup_create(
# #             STREAM_NAME,
# #             GROUP_NAME,
# #             id="0-0",
# #             mkstream=True,
# #         )

# #         print(
# #             f"[HEARTBEAT] Created consumer group "
# #             f"{GROUP_NAME}"
# #         )

# #     except redis.ResponseError as error:

# #         if "BUSYGROUP" not in str(error):
# #             raise


# # # ============================================================
# # # ACKNOWLEDGEMENT
# # # ============================================================

# # async def acknowledge(
# #     redis_client,
# #     message_id,
# # ):
# #     """
# #     ACK a successfully processed message.
# #     """

# #     await redis_client.xack(
# #         STREAM_NAME,
# #         GROUP_NAME,
# #         message_id,
# #     )


# # # ============================================================
# # # MESSAGE PROCESSING
# # # ============================================================

# # async def process_message(
# #     redis_client,
# #     message_id,
# #     fields,
# # ):
# #     """
# #     Process exactly one heartbeat message.

# #     Failure of one message must NOT terminate the consumer.
# #     """

# #     try:

# #         heartbeat = parse_heartbeat(
# #             fields
# #         )

# #         # ----------------------------------------------------
# #         # Ignore irrelevant/malformed messages.
# #         #
# #         # They are ACKed so they do not permanently occupy
# #         # the pending queue.
# #         # ----------------------------------------------------

# #         if heartbeat is None:

# #             await acknowledge(
# #                 redis_client,
# #                 message_id,
# #             )

# #             return

# #         agent_id = heartbeat[
# #             "agent_id"
# #         ]

# #         # ----------------------------------------------------
# #         # Update in-memory registry.
# #         # ----------------------------------------------------

# #         agent_registry.update_heartbeat(
# #             agent_id=agent_id,
# #             instance_id=heartbeat.get(
# #                 "instance_id"
# #             ),
# #             hostname=heartbeat.get(
# #                 "hostname"
# #             ),
# #         )

# #         print(
# #             f"[HEARTBEAT] "
# #             f"{agent_id} -> ALIVE"
# #         )

# #         # ----------------------------------------------------
# #         # ACK ONLY after successful registry update.
# #         # ----------------------------------------------------

# #         await acknowledge(
# #             redis_client,
# #             message_id,
# #         )

# #     except Exception as error:

# #         print(
# #             f"[HEARTBEAT ERROR] "
# #             f"message={message_id} "
# #             f"error={error}"
# #         )

# #         # ----------------------------------------------------
# #         # IMPORTANT:
# #         #
# #         # Do NOT ACK failed messages.
# #         #
# #         # Redis keeps them pending so they can be recovered.
# #         # ----------------------------------------------------


# # # ============================================================
# # # PENDING MESSAGE RECOVERY
# # # ============================================================

# # async def recover_pending_messages(
# #     redis_client,
# # ):
# #     """
# #     Recover stale pending messages belonging to crashed or
# #     disconnected heartbeat consumers.

# #     This closes the reliability gap where a message was
# #     delivered to an old consumer but never ACKed.

# #     XAUTOCLAIM transfers ownership of stale pending messages
# #     to the current consumer.
# #     """

# #     print(
# #         "[HEARTBEAT] "
# #         f"Checking pending messages "
# #         f"(idle >= {PENDING_IDLE_MS}ms)"
# #     )

# #     start_id = "0-0"

# #     recovered_total = 0

# #     while True:

# #         try:

# #             result = await redis_client.xautoclaim(
# #                 STREAM_NAME,
# #                 GROUP_NAME,
# #                 CONSUMER_NAME,
# #                 PENDING_IDLE_MS,
# #                 start_id,
# #                 count=READ_COUNT,
# #             )

# #         except redis.ResponseError as error:

# #             print(
# #                 "[HEARTBEAT] "
# #                 f"Pending recovery error: {error}"
# #             )

# #             return

# #         # redis-py returns:
# #         #
# #         # [
# #         #     next_start_id,
# #         #     messages,
# #         #     deleted_ids
# #         # ]
# #         #
# #         # Some Redis/client versions may return slightly
# #         # different structures, so handle defensively.

# #         if not result:
# #             return

# #         next_start_id = result[0]

# #         messages = result[1]

# #         if messages:

# #             print(
# #                 f"[HEARTBEAT] "
# #                 f"Recovering {len(messages)} "
# #                 f"pending message(s)"
# #             )

# #         for message_id, fields in messages:

# #             try:

# #                 await process_message(
# #                     redis_client,
# #                     message_id,
# #                     fields,
# #                 )

# #                 recovered_total += 1

# #             except Exception as error:

# #                 print(
# #                     "[HEARTBEAT PENDING "
# #                     "ISOLATION ERROR] "
# #                     f"{message_id}: {error}"
# #                 )

# #         # ----------------------------------------------------
# #         # XAUTOCLAIM returns the next cursor.
# #         # When it reaches 0-0, recovery is complete.
# #         # ----------------------------------------------------

# #         next_start_id = decode(
# #             next_start_id
# #         )

# #         if (
# #             not messages
# #             and next_start_id == "0-0"
# #         ):
# #             break

# #         if next_start_id == "0-0":
# #             break

# #         start_id = next_start_id

# #     if recovered_total:

# #         print(
# #             f"[HEARTBEAT] "
# #             f"Recovered {recovered_total} "
# #             f"pending message(s)"
# #         )

# #     else:

# #         print(
# #             "[HEARTBEAT] "
# #             "No stale pending messages recovered."
# #         )


# # # ============================================================
# # # NEW MESSAGE CONSUMPTION
# # # ============================================================

# # async def consume_new_messages(
# #     redis_client,
# # ):
# #     """
# #     Consume new messages from events.system.
# #     """

# #     messages = await redis_client.xreadgroup(
# #         groupname=GROUP_NAME,
# #         consumername=CONSUMER_NAME,
# #         streams={
# #             STREAM_NAME: ">"
# #         },
# #         count=READ_COUNT,
# #         block=BLOCK_MS,
# #     )

# #     if not messages:
# #         return

# #     for _, stream_messages in messages:

# #         for message_id, fields in stream_messages:

# #             try:

# #                 await process_message(
# #                     redis_client,
# #                     message_id,
# #                     fields,
# #                 )

# #             except Exception as error:

# #                 print(
# #                     "[HEARTBEAT MESSAGE "
# #                     "ISOLATION ERROR] "
# #                     f"{message_id}: {error}"
# #                 )


# # # ============================================================
# # # MAIN CONSUMER LOOP
# # # ============================================================

# # async def heartbeat_consumer_loop(
# #     redis_client,
# # ):
# #     """
# #     Main heartbeat consumer.

# #     Lifecycle:

# #         Redis connection
# #              ↓
# #         Ensure consumer group
# #              ↓
# #         Recover stale pending messages
# #              ↓
# #         Consume new heartbeats forever
# #              ↓
# #         Recover automatically after transient errors
# #     """

# #     await ensure_consumer_group(
# #         redis_client
# #     )

# #     print(
# #         f"[HEARTBEAT] Consumer started: "
# #         f"{STREAM_NAME}/{GROUP_NAME}"
# #     )

# #     # --------------------------------------------------------
# #     # Recover messages left behind by a previous consumer.
# #     # --------------------------------------------------------

# #     try:

# #         await recover_pending_messages(
# #             redis_client
# #         )

# #     except Exception as error:

# #         print(
# #             "[HEARTBEAT] "
# #             f"Initial pending recovery failed: {error}"
# #         )

# #     # --------------------------------------------------------
# #     # Continuous consumption.
# #     # --------------------------------------------------------

# #     while True:

# #         try:

# #             await consume_new_messages(
# #                 redis_client
# #             )

# #         except asyncio.CancelledError:

# #             print(
# #                 "[HEARTBEAT] "
# #                 "Consumer cancellation received."
# #             )

# #             raise

# #         except Exception as error:

# #             print(
# #                 "[HEARTBEAT CONSUMER ERROR] "
# #                 f"{error}"
# #             )

# #             # ------------------------------------------------
# #             # Redis/network failure should affect only the
# #             # heartbeat consumer.
# #             # ------------------------------------------------

# #             await asyncio.sleep(
# #                 RETRY_DELAY
# #             )

# #             # ------------------------------------------------
# #             # Retry pending recovery after a consumer error.
# #             # ------------------------------------------------

# #             try:

# #                 await recover_pending_messages(
# #                     redis_client
# #                 )

# #             except Exception as recovery_error:

# #                 print(
# #                     "[HEARTBEAT] "
# #                     f"Pending recovery retry failed: "
# #                     f"{recovery_error}"
# #                 )


# # # ============================================================
# # # STANDALONE ENTRY POINT
# # # ============================================================

# # async def main():

# #     redis_client = redis.Redis(
# #         host=REDIS_HOST,
# #         port=REDIS_PORT,
# #         decode_responses=True,
# #         socket_timeout=None,
# #         health_check_interval=30,
# #     )

# #     try:

# #         await heartbeat_consumer_loop(
# #             redis_client
# #         )

# #     finally:

# #         await redis_client.aclose()


# # if __name__ == "__main__":

# #     asyncio.run(
# #         main()
# #     )






























# import asyncio
# import json
# import os

# import redis.asyncio as redis

# from backend.app.monitoring.agent_registry import agent_registry


# # ============================================================
# # REDIS CONFIGURATION
# # ============================================================

# REDIS_HOST = os.getenv(
#     "REDIS_HOST",
#     "localhost",
# )

# REDIS_PORT = int(
#     os.getenv(
#         "REDIS_PORT",
#         "6379",
#     )
# )


# # ============================================================
# # STREAM CONFIGURATION
# # ============================================================

# STREAM_NAME = "events.system"

# GROUP_NAME = "heartbeat-workers"

# CONSUMER_NAME = os.getenv(
#     "HEARTBEAT_CONSUMER_NAME",
#     "heartbeat-consumer-01",
# )


# # ============================================================
# # CONSUMER CONFIGURATION
# # ============================================================

# READ_COUNT = int(
#     os.getenv(
#         "HEARTBEAT_READ_COUNT",
#         "10",
#     )
# )

# BLOCK_MS = int(
#     os.getenv(
#         "HEARTBEAT_BLOCK_MS",
#         "5000",
#     )
# )

# RETRY_DELAY = float(
#     os.getenv(
#         "HEARTBEAT_RETRY_DELAY",
#         "2",
#     )
# )


# # ============================================================
# # PENDING MESSAGE RECOVERY
# # ============================================================

# PENDING_IDLE_MS = int(
#     os.getenv(
#         "HEARTBEAT_PENDING_IDLE_MS",
#         "15000",
#     )
# )


# # ============================================================
# # DECODING HELPERS
# # ============================================================

# def decode(value):
#     """
#     Convert Redis bytes into UTF-8 strings.

#     Compatible with both:
#         decode_responses=True
#         decode_responses=False
#     """

#     if isinstance(value, bytes):
#         return value.decode(
#             "utf-8",
#             errors="replace",
#         )

#     return value


# def normalize_fields(fields):
#     """
#     Normalize Redis fields into string keys/values.
#     """

#     return {
#         decode(key): decode(value)
#         for key, value in fields.items()
#     }


# # ============================================================
# # HEARTBEAT PARSING
# # ============================================================

# def parse_heartbeat(fields):
#     """
#     Parse supported heartbeat formats.

#     Supported formats:

#     1. BaseAgent:
#         {
#             "event": "<JSON>"
#         }

#     2. Direct Redis fields.

#     Returns:
#         normalized heartbeat dictionary
#         or None
#     """

#     fields = normalize_fields(fields)

#     event = fields.get("event")

#     if event:
#         if isinstance(event, str):
#             try:
#                 event = json.loads(event)
#             except json.JSONDecodeError:
#                 return None

#         if isinstance(event, dict):
#             merged = {
#                 **fields,
#                 **event,
#             }

#             fields = merged

#     # --------------------------------------------------------
#     # Verify event type
#     # --------------------------------------------------------

#     if fields.get("event_type") != "agent.heartbeat":
#         return None

#     # --------------------------------------------------------
#     # Find agent ID
#     # --------------------------------------------------------

#     agent_id = (
#         fields.get("source_agent_id")
#         or fields.get("agent_id")
#     )

#     # --------------------------------------------------------
#     # Support nested source object
#     # --------------------------------------------------------

#     if not agent_id:

#         source = fields.get("source")

#         if isinstance(source, str):
#             try:
#                 source = json.loads(source)
#             except json.JSONDecodeError:
#                 source = None

#         if isinstance(source, dict):
#             agent_id = source.get("agent_id")

#     if not agent_id:
#         return None

#     return {
#         "agent_id": agent_id,
#         "status": fields.get(
#             "status",
#             "alive",
#         ),
#         "event_id": fields.get(
#             "event_id"
#         ),
#         "timestamp": fields.get(
#             "timestamp"
#         ),
#         "instance_id": fields.get(
#             "instance_id"
#         ),
#         "hostname": fields.get(
#             "hostname"
#         ),
#     }


# # ============================================================
# # CONSUMER GROUP
# # ============================================================

# async def ensure_consumer_group(
#     redis_client,
# ):
#     """
#     Ensure the heartbeat consumer group exists.
#     """

#     try:

#         await redis_client.xgroup_create(
#             STREAM_NAME,
#             GROUP_NAME,
#             id="0-0",
#             mkstream=True,
#         )

#         print(
#             f"[HEARTBEAT] Created consumer group "
#             f"{GROUP_NAME}"
#         )

#     except redis.ResponseError as error:

#         if "BUSYGROUP" not in str(error):
#             raise


# # ============================================================
# # ACKNOWLEDGEMENT
# # ============================================================

# async def acknowledge(
#     redis_client,
#     message_id,
# ):
#     """
#     ACK a successfully processed message.
#     """

#     await redis_client.xack(
#         STREAM_NAME,
#         GROUP_NAME,
#         message_id,
#     )


# # ============================================================
# # MESSAGE PROCESSING
# # ============================================================

# async def process_message(
#     redis_client,
#     message_id,
#     fields,
#     *,
#     recovered=False,
# ):
#     """
#     Process exactly one heartbeat message.

#     Important:

#     A Redis message timestamp is NOT the same thing as the
#     time at which the consumer processed the message.

#     For normal heartbeats, registry update is valid.

#     For recovered pending messages, the heartbeat is only
#     accepted if its event timestamp is still reasonably fresh.

#     This prevents XAUTOCLAIM from converting an old heartbeat
#     into a brand-new heartbeat.
#     """

#     try:

#         heartbeat = parse_heartbeat(fields)

#         # ----------------------------------------------------
#         # Ignore irrelevant / malformed messages
#         # ----------------------------------------------------

#         if heartbeat is None:

#             await acknowledge(
#                 redis_client,
#                 message_id,
#             )

#             return

#         agent_id = heartbeat["agent_id"]

#         # ----------------------------------------------------
#         # Determine whether this heartbeat is fresh
#         # ----------------------------------------------------

#         heartbeat_timestamp = heartbeat.get(
#             "timestamp"
#         )

#         heartbeat_age = None

#         if heartbeat_timestamp:

#             try:

#                 from datetime import datetime, timezone

#                 heartbeat_dt = datetime.fromisoformat(
#                     heartbeat_timestamp.replace(
#                         "Z",
#                         "+00:00",
#                     )
#                 )

#                 if heartbeat_dt.tzinfo is None:
#                     heartbeat_dt = heartbeat_dt.replace(
#                         tzinfo=timezone.utc
#                     )

#                 now = datetime.now(timezone.utc)

#                 heartbeat_age = (
#                     now - heartbeat_dt
#                 ).total_seconds()

#             except Exception as timestamp_error:

#                 print(
#                     "[HEARTBEAT] "
#                     f"Invalid timestamp for "
#                     f"{agent_id}: "
#                     f"{timestamp_error}"
#                 )

#         # ----------------------------------------------------
#         # Recovered messages
#         # ----------------------------------------------------

#         if recovered:

#             # ------------------------------------------------
#             # If timestamp is available and already older than
#             # the heartbeat timeout, do NOT refresh the agent.
#             #
#             # The supervisor must be allowed to detect the
#             # actual heartbeat gap.
#             # ------------------------------------------------

#             heartbeat_timeout = float(
#                 os.getenv(
#                     "HEARTBEAT_TIMEOUT",
#                     "30",
#                 )
#             )

#             if (
#                 heartbeat_age is not None
#                 and heartbeat_age > heartbeat_timeout
#             ):

#                 print(
#                     "[HEARTBEAT] Ignoring stale recovered "
#                     f"heartbeat for {agent_id} "
#                     f"(age={heartbeat_age:.1f}s)"
#                 )

#                 await acknowledge(
#                     redis_client,
#                     message_id,
#                 )

#                 return

#         # ----------------------------------------------------
#         # Update registry
#         # ----------------------------------------------------

#         agent_registry.update_heartbeat(
#             agent_id=agent_id,
#             instance_id=heartbeat.get(
#                 "instance_id"
#             ),
#             hostname=heartbeat.get(
#                 "hostname"
#             ),
#         )

#         if recovered:

#             print(
#                 "[HEARTBEAT] "
#                 f"Recovered heartbeat accepted: "
#                 f"{agent_id}"
#             )

#         else:

#             print(
#                 "[HEARTBEAT] "
#                 f"{agent_id} -> ALIVE"
#             )

#         # ----------------------------------------------------
#         # ACK only after successful registry update
#         # ----------------------------------------------------

#         await acknowledge(
#             redis_client,
#             message_id,
#         )

#     except Exception as error:

#         print(
#             "[HEARTBEAT ERROR] "
#             f"message={message_id} "
#             f"error={error}"
#         )

#         # Do NOT ACK failed messages.
#         #
#         # Redis keeps them pending so they can be recovered.


# # ============================================================
# # PENDING MESSAGE RECOVERY
# # ============================================================

# async def recover_pending_messages(
#     redis_client,
# ):
#     """
#     Recover stale pending messages belonging to crashed
#     heartbeat consumers.

#     Uses XAUTOCLAIM.

#     IMPORTANT:
#     Old heartbeat events are not allowed to refresh an
#     agent's heartbeat timestamp.
#     """

#     print(
#         "[HEARTBEAT] "
#         f"Checking pending messages "
#         f"(idle >= {PENDING_IDLE_MS}ms)"
#     )

#     start_id = "0-0"

#     recovered_total = 0

#     while True:

#         try:

#             result = await redis_client.xautoclaim(
#                 STREAM_NAME,
#                 GROUP_NAME,
#                 CONSUMER_NAME,
#                 PENDING_IDLE_MS,
#                 start_id,
#                 count=READ_COUNT,
#             )

#         except redis.ResponseError as error:

#             print(
#                 "[HEARTBEAT] "
#                 f"Pending recovery error: {error}"
#             )

#             return

#         if not result:
#             return

#         next_start_id = result[0]

#         messages = result[1]

#         if messages:

#             print(
#                 "[HEARTBEAT] "
#                 f"Recovering {len(messages)} "
#                 f"pending message(s)"
#             )

#         for message_id, fields in messages:

#             try:

#                 await process_message(
#                     redis_client,
#                     message_id,
#                     fields,
#                     recovered=True,
#                 )

#                 recovered_total += 1

#             except Exception as error:

#                 print(
#                     "[HEARTBEAT PENDING "
#                     "ISOLATION ERROR] "
#                     f"{message_id}: {error}"
#                 )

#         next_start_id = decode(
#             next_start_id
#         )

#         if next_start_id == "0-0":
#             break

#         start_id = next_start_id

#     if recovered_total:

#         print(
#             "[HEARTBEAT] "
#             f"Recovered {recovered_total} "
#             f"pending message(s)"
#         )

#     else:

#         print(
#             "[HEARTBEAT] "
#             "No stale pending messages recovered."
#         )


# # ============================================================
# # NEW MESSAGE CONSUMPTION
# # ============================================================

# async def consume_new_messages(
#     redis_client,
# ):
#     """
#     Consume newly delivered messages.
#     """

#     messages = await redis_client.xreadgroup(
#         groupname=GROUP_NAME,
#         consumername=CONSUMER_NAME,
#         streams={
#             STREAM_NAME: ">"
#         },
#         count=READ_COUNT,
#         block=BLOCK_MS,
#     )

#     if not messages:
#         return

#     for _, stream_messages in messages:

#         for message_id, fields in stream_messages:

#             try:

#                 await process_message(
#                     redis_client,
#                     message_id,
#                     fields,
#                     recovered=False,
#                 )

#             except Exception as error:

#                 print(
#                     "[HEARTBEAT MESSAGE "
#                     "ISOLATION ERROR] "
#                     f"{message_id}: {error}"
#                 )


# # ============================================================
# # MAIN CONSUMER LOOP
# # ============================================================

# async def heartbeat_consumer_loop(
#     redis_client,
# ):
#     """
#     Main heartbeat consumer.

#     Lifecycle:

#         Redis
#           ↓
#         Consumer Group
#           ↓
#         Pending Recovery
#           ↓
#         New Heartbeats
#           ↓
#         AgentRegistry
#     """

#     await ensure_consumer_group(
#         redis_client
#     )

#     print(
#         "[HEARTBEAT] Consumer started: "
#         f"{STREAM_NAME}/{GROUP_NAME}"
#     )

#     # --------------------------------------------------------
#     # Recover pending messages left by previous consumers
#     # --------------------------------------------------------

#     try:

#         await recover_pending_messages(
#             redis_client
#         )

#     except Exception as error:

#         print(
#             "[HEARTBEAT] "
#             f"Initial pending recovery failed: "
#             f"{error}"
#         )

#     # --------------------------------------------------------
#     # Continuous consumption
#     # --------------------------------------------------------

#     while True:

#         try:

#             await consume_new_messages(
#                 redis_client
#             )

#         except asyncio.CancelledError:

#             print(
#                 "[HEARTBEAT] "
#                 "Consumer cancellation received."
#             )

#             raise

#         except Exception as error:

#             print(
#                 "[HEARTBEAT CONSUMER ERROR] "
#                 f"{error}"
#             )

#             await asyncio.sleep(
#                 RETRY_DELAY
#             )

#             try:

#                 await recover_pending_messages(
#                     redis_client
#                 )

#             except Exception as recovery_error:

#                 print(
#                     "[HEARTBEAT] "
#                     f"Pending recovery retry failed: "
#                     f"{recovery_error}"
#                 )


# # ============================================================
# # STANDALONE ENTRY POINT
# # ============================================================

# async def main():

#     redis_client = redis.Redis(
#         host=REDIS_HOST,
#         port=REDIS_PORT,
#         decode_responses=True,
#         socket_timeout=None,
#         health_check_interval=30,
#     )

#     try:

#         await heartbeat_consumer_loop(
#             redis_client
#         )

#     finally:

#         await redis_client.aclose()


# # ============================================================
# # ENTRY POINT
# # ============================================================

# if __name__ == "__main__":

#     asyncio.run(
#         main()
#     )























"""
Heartbeat consumer and monitoring bridge.

Responsibilities:

- Consume agent heartbeat events from Redis Streams.
- Parse the current heartbeat format emitted by shared.heartbeat.
- Support legacy heartbeat formats where practical.
- Update AgentRegistry with agent identity and liveness.
- Recover stale pending messages with XAUTOCLAIM.
- Never allow one malformed heartbeat to terminate the consumer.
- Never acknowledge a heartbeat before successful processing.
- Never allow an old recovered heartbeat to falsely refresh liveness.

Heartbeat stream:

    events.system

Consumer group:

    heartbeat-workers
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

import redis.asyncio as redis

from backend.app.monitoring.agent_registry import agent_registry


# ============================================================
# REDIS CONFIGURATION
# ============================================================

REDIS_HOST = os.getenv(
    "REDIS_HOST",
    "localhost",
)

try:
    REDIS_PORT = int(
        os.getenv(
            "REDIS_PORT",
            "6379",
        )
    )
except ValueError:
    REDIS_PORT = 6379


# ============================================================
# STREAM CONFIGURATION
# ============================================================

STREAM_NAME = os.getenv(
    "HEARTBEAT_STREAM",
    "events.system",
)

GROUP_NAME = os.getenv(
    "HEARTBEAT_GROUP",
    "heartbeat-workers",
)

CONSUMER_NAME = os.getenv(
    "HEARTBEAT_CONSUMER_NAME",
    "heartbeat-consumer-01",
)


# ============================================================
# CONSUMER CONFIGURATION
# ============================================================

def _positive_int(
    name: str,
    default: int,
) -> int:
    try:
        value = int(
            os.getenv(
                name,
                str(default),
            )
        )

        if value <= 0:
            return default

        return value

    except (TypeError, ValueError):
        return default


def _non_negative_int(
    name: str,
    default: int,
) -> int:
    try:
        value = int(
            os.getenv(
                name,
                str(default),
            )
        )

        if value < 0:
            return default

        return value

    except (TypeError, ValueError):
        return default


def _positive_float(
    name: str,
    default: float,
) -> float:
    try:
        value = float(
            os.getenv(
                name,
                str(default),
            )
        )

        if value <= 0:
            return default

        return value

    except (TypeError, ValueError):
        return default


READ_COUNT = _positive_int(
    "HEARTBEAT_READ_COUNT",
    10,
)

BLOCK_MS = _positive_int(
    "HEARTBEAT_BLOCK_MS",
    5000,
)

RETRY_DELAY = _positive_float(
    "HEARTBEAT_RETRY_DELAY",
    2.0,
)


# ============================================================
# PENDING MESSAGE RECOVERY
# ============================================================

PENDING_IDLE_MS = _non_negative_int(
    "HEARTBEAT_PENDING_IDLE_MS",
    15000,
)


# ============================================================
# LIVENESS CONFIGURATION
# ============================================================

HEARTBEAT_TIMEOUT = _positive_float(
    "HEARTBEAT_TIMEOUT",
    30.0,
)


# ============================================================
# REDIS TIMEOUT CONFIGURATION
# ============================================================

REDIS_SOCKET_CONNECT_TIMEOUT = _positive_float(
    "REDIS_CONNECT_TIMEOUT",
    5.0,
)

REDIS_SOCKET_TIMEOUT = _positive_float(
    "REDIS_SOCKET_TIMEOUT",
    10.0,
)


# ============================================================
# DECODING HELPERS
# ============================================================

def decode(
    value: Any,
) -> Any:
    """
    Convert Redis bytes to UTF-8 strings.

    Works with both:

        decode_responses=True
        decode_responses=False
    """

    if isinstance(value, bytes):
        return value.decode(
            "utf-8",
            errors="replace",
        )

    return value


def normalize_fields(
    fields: Any,
) -> dict[str, Any]:
    """
    Normalize Redis stream field keys and values.
    """

    if not isinstance(fields, dict):
        return {}

    return {
        str(decode(key)): decode(value)
        for key, value in fields.items()
    }


# ============================================================
# JSON HELPERS
# ============================================================

def parse_json_object(
    value: Any,
) -> Optional[dict[str, Any]]:
    """
    Parse a dictionary or JSON-encoded dictionary.

    Returns None for invalid/non-object values.
    """

    if isinstance(value, dict):
        return value

    if not isinstance(value, str):
        return None

    value = value.strip()

    if not value:
        return None

    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None

    if isinstance(parsed, dict):
        return parsed

    return None


# ============================================================
# TIMESTAMP HELPERS
# ============================================================

def parse_timestamp(
    timestamp: Any,
) -> Optional[datetime]:
    """
    Convert an ISO-8601 timestamp to timezone-aware UTC.

    Returns None when the timestamp cannot be parsed.
    """

    if not isinstance(timestamp, str):
        return None

    timestamp = timestamp.strip()

    if not timestamp:
        return None

    try:
        parsed = datetime.fromisoformat(
            timestamp.replace(
                "Z",
                "+00:00",
            )
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc,
            )

        return parsed.astimezone(
            timezone.utc
        )

    except (ValueError, TypeError):
        return None


def heartbeat_age_seconds(
    timestamp: Any,
) -> Optional[float]:
    """
    Calculate heartbeat age using the heartbeat event timestamp.
    """

    parsed = parse_timestamp(
        timestamp
    )

    if parsed is None:
        return None

    now = datetime.now(
        timezone.utc
    )

    age = (
        now - parsed
    ).total_seconds()

    # Future timestamps should not produce a negative age.
    return max(
        0.0,
        age,
    )


# ============================================================
# HEARTBEAT PARSING
# ============================================================

def parse_heartbeat(
    fields: Any,
) -> Optional[dict[str, Any]]:
    """
    Parse the current heartbeat format.

    Current producer format:

        {
            "event_id": "...",
            "event_type": "agent.heartbeat",
            "version": "1.0",
            "timestamp": "...",
            "source": "<JSON string>",
            "data": "<JSON string>",
            "agent_id": "...",
            "instance_id": "...",
            "hostname": "...",
            "status": "alive"
        }

    Also supports older formats where heartbeat data may be
    wrapped inside an "event" JSON field.

    Returns:

        normalized heartbeat dictionary

    or:

        None
    """

    fields = normalize_fields(
        fields
    )

    if not fields:
        return None

    # --------------------------------------------------------
    # Legacy / wrapped event format
    # --------------------------------------------------------

    event = fields.get(
        "event"
    )

    if event is not None:

        parsed_event = parse_json_object(
            event
        )

        if parsed_event is not None:

            merged = {
                **fields,
                **parsed_event,
            }

            fields = merged

    # --------------------------------------------------------
    # Event type
    # --------------------------------------------------------

    event_type = fields.get(
        "event_type"
    )

    if event_type != "agent.heartbeat":
        return None

    # --------------------------------------------------------
    # Parse source
    # --------------------------------------------------------

    source = parse_json_object(
        fields.get(
            "source"
        )
    )

    # --------------------------------------------------------
    # Parse data
    # --------------------------------------------------------

    data = parse_json_object(
        fields.get(
            "data"
        )
    )

    # --------------------------------------------------------
    # Agent identity
    #
    # Current producer exposes these directly:
    #
    #   agent_id
    #   instance_id
    #   hostname
    #
    # Older formats may use:
    #
    #   source_agent_id
    #   source.instance
    # --------------------------------------------------------

    agent_id = (
        fields.get("agent_id")
        or fields.get("source_agent_id")
    )

    if not agent_id and source:
        agent_id = source.get(
            "agent_id"
        )

    if not agent_id:
        return None

    instance_id = (
        fields.get("instance_id")
        or fields.get("source_instance_id")
    )

    if not instance_id and source:
        instance_id = source.get(
            "instance_id"
        )

    hostname = fields.get(
        "hostname"
    )

    if not hostname and source:
        hostname = source.get(
            "hostname"
        )

    # --------------------------------------------------------
    # Status
    # --------------------------------------------------------

    status = fields.get(
        "status"
    )

    if not status and data:
        status = data.get(
            "status"
        )

    if not status:
        status = "alive"

    return {
        "agent_id": str(
            agent_id
        ),
        "instance_id": (
            str(instance_id)
            if instance_id is not None
            else None
        ),
        "hostname": (
            str(hostname)
            if hostname is not None
            else None
        ),
        "status": str(
            status
        ),
        "event_id": fields.get(
            "event_id"
        ),
        "event_type": event_type,
        "version": fields.get(
            "version"
        ),
        "timestamp": fields.get(
            "timestamp"
        ),
    }


# ============================================================
# CONSUMER GROUP
# ============================================================

async def ensure_consumer_group(
    redis_client: redis.Redis,
) -> None:
    """
    Ensure the heartbeat consumer group exists.
    """

    try:

        await redis_client.xgroup_create(
            STREAM_NAME,
            GROUP_NAME,
            id="0-0",
            mkstream=True,
        )

        print(
            "[HEARTBEAT] Created consumer group "
            f"{GROUP_NAME}"
        )

    except redis.ResponseError as error:

        if "BUSYGROUP" in str(error):
            return

        raise


# ============================================================
# ACKNOWLEDGEMENT
# ============================================================

async def acknowledge(
    redis_client: redis.Redis,
    message_id: Any,
) -> None:
    """
    ACK a successfully processed message.
    """

    await redis_client.xack(
        STREAM_NAME,
        GROUP_NAME,
        message_id,
    )


# ============================================================
# MESSAGE PROCESSING
# ============================================================

async def process_message(
    redis_client: redis.Redis,
    message_id: Any,
    fields: Any,
    *,
    recovered: bool = False,
) -> None:
    """
    Process exactly one heartbeat.

    Rules:

    1. Malformed heartbeat -> isolate + ACK.
    2. Irrelevant event -> isolate + ACK.
    3. Valid heartbeat -> update registry.
    4. Registry success -> ACK.
    5. Processing failure -> DO NOT ACK.
    6. Old recovered heartbeat -> ACK but do not refresh liveness.

    The consumer itself must never die because of one bad
    heartbeat.
    """

    try:

        heartbeat = parse_heartbeat(
            fields
        )

        # ----------------------------------------------------
        # Ignore malformed / irrelevant messages
        # ----------------------------------------------------

        if heartbeat is None:

            print(
                "[HEARTBEAT] Ignoring malformed or "
                "irrelevant message: "
                f"{message_id}"
            )

            await acknowledge(
                redis_client,
                message_id,
            )

            return

        agent_id = heartbeat[
            "agent_id"
        ]

        # ----------------------------------------------------
        # Calculate heartbeat age
        # ----------------------------------------------------

        timestamp = heartbeat.get(
            "timestamp"
        )

        age = heartbeat_age_seconds(
            timestamp
        )

        # ----------------------------------------------------
        # Invalid timestamp handling
        # ----------------------------------------------------

        if timestamp and age is None:

            print(
                "[HEARTBEAT] Invalid timestamp for "
                f"{agent_id}; message={message_id}"
            )

        # ----------------------------------------------------
        # Recovered heartbeat
        # ----------------------------------------------------
        #
        # A heartbeat that sat pending longer than the
        # heartbeat timeout must NOT resurrect/refresh an
        # agent.
        #
        # We ACK it because it has been handled, but do not
        # update the registry.
        # ----------------------------------------------------

        if recovered:

            if (
                age is not None
                and age > HEARTBEAT_TIMEOUT
            ):

                print(
                    "[HEARTBEAT] Ignoring stale recovered "
                    f"heartbeat for {agent_id} "
                    f"(age={age:.1f}s, "
                    f"timeout={HEARTBEAT_TIMEOUT:.1f}s)"
                )

                await acknowledge(
                    redis_client,
                    message_id,
                )

                return

        # ----------------------------------------------------
        # Update registry
        # ----------------------------------------------------

        agent_registry.update_heartbeat(
            agent_id=agent_id,
            instance_id=heartbeat.get(
                "instance_id"
            ),
            hostname=heartbeat.get(
                "hostname"
            ),
        )

        # ----------------------------------------------------
        # Logging
        # ----------------------------------------------------

        if recovered:

            print(
                "[HEARTBEAT] Recovered heartbeat accepted: "
                f"{agent_id}"
            )

        else:

            print(
                "[HEARTBEAT] "
                f"{agent_id} -> ALIVE"
            )

        # ----------------------------------------------------
        # ACK ONLY AFTER SUCCESS
        # ----------------------------------------------------

        await acknowledge(
            redis_client,
            message_id,
        )

    except asyncio.CancelledError:
        raise

    except Exception as error:

        print(
            "[HEARTBEAT ERROR] "
            f"message={message_id} "
            f"error={error}"
        )

        # ----------------------------------------------------
        # IMPORTANT
        #
        # Do NOT ACK here.
        #
        # Redis keeps the message pending and the recovery
        # mechanism can retry it later.
        # ----------------------------------------------------


# ============================================================
# PENDING MESSAGE RECOVERY
# ============================================================

async def recover_pending_messages(
    redis_client: redis.Redis,
) -> None:
    """
    Recover stale pending heartbeat messages.

    Uses Redis XAUTOCLAIM.

    Old heartbeat events are never allowed to refresh
    liveness after their timestamp has expired.
    """

    print(
        "[HEARTBEAT] Checking pending messages "
        f"(idle >= {PENDING_IDLE_MS}ms)"
    )

    start_id = "0-0"

    recovered_total = 0

    while True:

        try:

            result = await redis_client.xautoclaim(
                STREAM_NAME,
                GROUP_NAME,
                CONSUMER_NAME,
                PENDING_IDLE_MS,
                start_id,
                count=READ_COUNT,
            )

        except asyncio.CancelledError:
            raise

        except redis.ResponseError as error:

            print(
                "[HEARTBEAT] Pending recovery error: "
                f"{error}"
            )

            return

        except Exception as error:

            print(
                "[HEARTBEAT] Pending recovery "
                f"unexpected error: {error}"
            )

            return

        if not result:
            return

        next_start_id = result[0]

        messages = result[1]

        # ----------------------------------------------------
        # Redis-py can return deleted-message metadata as a
        # third element depending on Redis/server version.
        # We intentionally ignore it.
        # ----------------------------------------------------

        if messages:

            print(
                "[HEARTBEAT] Recovering "
                f"{len(messages)} pending message(s)"
            )

        for message_id, fields in messages:

            try:

                await process_message(
                    redis_client,
                    message_id,
                    fields,
                    recovered=True,
                )

                recovered_total += 1

            except asyncio.CancelledError:
                raise

            except Exception as error:

                print(
                    "[HEARTBEAT PENDING "
                    "ISOLATION ERROR] "
                    f"{message_id}: {error}"
                )

        next_start_id = decode(
            next_start_id
        )

        if next_start_id == "0-0":
            break

        start_id = str(
            next_start_id
        )

    if recovered_total:

        print(
            "[HEARTBEAT] Recovered "
            f"{recovered_total} pending message(s)"
        )

    else:

        print(
            "[HEARTBEAT] "
            "No stale pending messages recovered."
        )


# ============================================================
# NEW MESSAGE CONSUMPTION
# ============================================================

async def consume_new_messages(
    redis_client: redis.Redis,
) -> None:
    """
    Consume newly delivered heartbeat messages.
    """

    messages = await redis_client.xreadgroup(
        groupname=GROUP_NAME,
        consumername=CONSUMER_NAME,
        streams={
            STREAM_NAME: ">"
        },
        count=READ_COUNT,
        block=BLOCK_MS,
    )

    if not messages:
        return

    for _, stream_messages in messages:

        for message_id, fields in stream_messages:

            try:

                await process_message(
                    redis_client,
                    message_id,
                    fields,
                    recovered=False,
                )

            except asyncio.CancelledError:
                raise

            except Exception as error:

                print(
                    "[HEARTBEAT MESSAGE "
                    "ISOLATION ERROR] "
                    f"{message_id}: {error}"
                )


# ============================================================
# MAIN CONSUMER LOOP
# ============================================================

async def heartbeat_consumer_loop(
    redis_client: redis.Redis,
) -> None:
    """
    Main heartbeat consumer.

    Lifecycle:

        Redis
          ↓
        Consumer Group
          ↓
        Pending Recovery
          ↓
        New Heartbeats
          ↓
        AgentRegistry
          ↓
        Watchdog / Supervisor
    """

    await ensure_consumer_group(
        redis_client
    )

    print(
        "[HEARTBEAT] Consumer started: "
        f"{STREAM_NAME}/{GROUP_NAME}"
    )

    # --------------------------------------------------------
    # Initial pending recovery
    # --------------------------------------------------------

    try:

        await recover_pending_messages(
            redis_client
        )

    except asyncio.CancelledError:
        raise

    except Exception as error:

        print(
            "[HEARTBEAT] Initial pending recovery "
            f"failed: {error}"
        )

    # --------------------------------------------------------
    # Continuous consumption
    # --------------------------------------------------------

    while True:

        try:

            await consume_new_messages(
                redis_client
            )

        except asyncio.CancelledError:

            print(
                "[HEARTBEAT] Consumer cancellation "
                "received."
            )

            raise

        except Exception as error:

            print(
                "[HEARTBEAT CONSUMER ERROR] "
                f"{error}"
            )

            # ------------------------------------------------
            # Redis/network/application failure must not kill
            # the heartbeat consumer permanently.
            # ------------------------------------------------

            await asyncio.sleep(
                RETRY_DELAY
            )

            try:

                await recover_pending_messages(
                    redis_client
                )

            except asyncio.CancelledError:
                raise

            except Exception as recovery_error:

                print(
                    "[HEARTBEAT] Pending recovery retry "
                    f"failed: {recovery_error}"
                )


# ============================================================
# REDIS CLIENT
# ============================================================

def create_redis_client() -> redis.Redis:
    """
    Create the Redis client used by the standalone consumer.
    """

    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        decode_responses=True,

        # Prevent indefinite network hangs.
        socket_connect_timeout=(
            REDIS_SOCKET_CONNECT_TIMEOUT
        ),

        socket_timeout=(
            REDIS_SOCKET_TIMEOUT
        ),

        health_check_interval=30,
    )


# ============================================================
# STANDALONE ENTRY POINT
# ============================================================

async def main() -> None:
    """
    Standalone heartbeat consumer entry point.
    """

    redis_client = create_redis_client()

    try:

        # ----------------------------------------------------
        # Verify Redis before entering the consumer loop.
        # ----------------------------------------------------

        await redis_client.ping()

        print(
            "[HEARTBEAT] Redis connection established."
        )

        await heartbeat_consumer_loop(
            redis_client
        )

    finally:

        await redis_client.aclose()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    asyncio.run(
        main()
    )