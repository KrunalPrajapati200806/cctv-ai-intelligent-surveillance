# # # import asyncio

# # # from backend.app.monitoring.heartbeat_consumer import (
# # #     heartbeat_consumer_loop,
# # # )
# # # from backend.app.monitoring.supervisor import (
# # #     AgentSupervisor,
# # # )
# # # from backend.app.monitoring.watchdog import (
# # #     watchdog_loop,
# # # )

# # # from backend.app.messaging.redis_client import (
# # #     redis_client,
# # # )


# # # # ============================================================
# # # # MONITORING SERVICE
# # # # ============================================================

# # # class MonitoringService:
# # #     """
# # #     Unified CCTV monitoring/control service.

# # #     Responsibilities
# # #     ----------------
# # #     1. Consume agent heartbeats.
# # #     2. Maintain the shared AgentRegistry.
# # #     3. Detect dead agents through the Watchdog.
# # #     4. Supervise agent subprocesses.
# # #     5. Restart failed/unresponsive agents.
# # #     6. Keep every agent failure isolated.

# # #     Architecture
# # #     ------------
# # #         Redis
# # #           │
# # #           ▼
# # #     Heartbeat Consumer
# # #           │
# # #           ▼
# # #     Agent Registry
# # #           │
# # #           ├──────────────► Watchdog
# # #           │                    │
# # #           │                    ▼
# # #           │                 DEAD
# # #           │                    │
# # #           │                    ▼
# # #           └──────────────► Supervisor
# # #                                │
# # #                                ▼
# # #                         Restart ONLY that agent
# # #     """

# # #     def __init__(self):
# # #         self.supervisor = AgentSupervisor()

# # #         self.running = False

# # #         self.heartbeat_task = None
# # #         self.watchdog_task = None
# # #         self.supervisor_task = None

# # #     # ========================================================
# # #     # START
# # #     # ========================================================

# # #     async def start(self):
# # #         print("=" * 80)
# # #         print("CCTV AI MONITORING SERVICE")
# # #         print("=" * 80)

# # #         print("[MONITORING] Starting unified monitoring service...")

# # #         self.running = True

# # #         # ----------------------------------------------------
# # #         # Redis connection
# # #         # ----------------------------------------------------

# # #         try:
# # #             await redis_client.ping()

# # #             print(
# # #                 "[MONITORING] Redis connection established."
# # #             )

# # #         except Exception as error:

# # #             print(
# # #                 "[MONITORING] FATAL: "
# # #                 f"Redis connection failed: {error}"
# # #             )

# # #             self.running = False

# # #             raise

# # #         # ----------------------------------------------------
# # #         # Start Supervisor
# # #         # ----------------------------------------------------

# # #         try:

# # #             await self.supervisor.start_all()

# # #         except Exception as error:

# # #             print(
# # #                 "[MONITORING] "
# # #                 f"Supervisor startup error: {error}"
# # #             )

# # #             # Do not terminate monitoring service because
# # #             # one startup operation failed.

# # #         # ----------------------------------------------------
# # #         # Heartbeat Consumer
# # #         # ----------------------------------------------------

# # #         self.heartbeat_task = asyncio.create_task(
# # #             self._run_heartbeat_consumer()
# # #         )

# # #         print(
# # #             "[MONITORING] "
# # #             "Heartbeat consumer started."
# # #         )

# # #         # ----------------------------------------------------
# # #         # Watchdog
# # #         # ----------------------------------------------------

# # #         self.watchdog_task = asyncio.create_task(
# # #             self._run_watchdog()
# # #         )

# # #         print(
# # #             "[MONITORING] "
# # #             "Watchdog started."
# # #         )

# # #         # ----------------------------------------------------
# # #         # Supervisor health monitoring
# # #         # ----------------------------------------------------

# # #         self.supervisor_task = asyncio.create_task(
# # #             self._run_supervisor_health()
# # #         )

# # #         print(
# # #             "[MONITORING] "
# # #             "Supervisor health monitoring started."
# # #         )

# # #         print("=" * 80)
# # #         print("[MONITORING] SERVICE READY")
# # #         print("=" * 80)

# # #     # ========================================================
# # #     # HEARTBEAT CONSUMER
# # #     # ========================================================

# # #     async def _run_heartbeat_consumer(self):
# # #         """
# # #         Run heartbeat consumer independently.

# # #         If the heartbeat consumer encounters an unexpected
# # #         failure, it is restarted without affecting agents.
# # #         """

# # #         while self.running:

# # #             try:

# # #                 await heartbeat_consumer_loop(
# # #                     redis_client
# # #                 )

# # #             except asyncio.CancelledError:

# # #                 raise

# # #             except Exception as error:

# # #                 print(
# # #                     "[MONITORING] "
# # #                     f"Heartbeat consumer crashed: {error}"
# # #                 )

# # #                 print(
# # #                     "[MONITORING] "
# # #                     "Restarting heartbeat consumer..."
# # #                 )

# # #                 await asyncio.sleep(2)

# # #     # ========================================================
# # #     # WATCHDOG
# # #     # ========================================================

# # #     async def _run_watchdog(self):
# # #         """
# # #         Run watchdog against the SAME in-memory AgentRegistry
# # #         used by the Supervisor.

# # #         Watchdog only detects and marks agents DEAD.

# # #         It does NOT restart processes.
# # #         """

# # #         while self.running:

# # #             try:

# # #                 await watchdog_loop()

# # #             except asyncio.CancelledError:

# # #                 raise

# # #             except Exception as error:

# # #                 print(
# # #                     "[MONITORING] "
# # #                     f"Watchdog crashed: {error}"
# # #                 )

# # #                 print(
# # #                     "[MONITORING] "
# # #                     "Restarting watchdog..."
# # #                 )

# # #                 await asyncio.sleep(2)

# # #     # ========================================================
# # #     # SUPERVISOR HEALTH MONITOR
# # #     # ========================================================

# # #     async def _run_supervisor_health(self):
# # #         """
# # #         Supervisor owns recovery.

# # #         Individual SupervisedAgent.health_loop() instances
# # #         inspect AgentRegistry and recover only their own agent.
# # #         """

# # #         while self.running:

# # #             try:

# # #                 # The individual agent health loops were already
# # #                 # created by supervisor.start_all().
# # #                 #
# # #                 # This task simply keeps the unified monitoring
# # #                 # service alive and provides a central supervisor
# # #                 # health boundary.

# # #                 await asyncio.sleep(5)

# # #             except asyncio.CancelledError:

# # #                 raise

# # #             except Exception as error:

# # #                 print(
# # #                     "[MONITORING] "
# # #                     f"Supervisor health boundary error: {error}"
# # #                 )

# # #                 await asyncio.sleep(2)

# # #     # ========================================================
# # #     # WAIT
# # #     # ========================================================

# # #     async def wait_forever(self):
# # #         """
# # #         Keep the monitoring service alive.
# # #         """

# # #         while self.running:

# # #             await asyncio.sleep(1)

# # #     # ========================================================
# # #     # STOP
# # #     # ========================================================

# # #     async def stop(self):
# # #         """
# # #         Gracefully shut down the entire monitoring service.
# # #         """

# # #         if not self.running:
# # #             return

# # #         print("=" * 80)
# # #         print("[MONITORING] Shutdown requested.")
# # #         print("=" * 80)

# # #         self.running = False

# # #         # ----------------------------------------------------
# # #         # Cancel heartbeat consumer
# # #         # ----------------------------------------------------

# # #         if self.heartbeat_task:

# # #             self.heartbeat_task.cancel()

# # #         # ----------------------------------------------------
# # #         # Cancel watchdog
# # #         # ----------------------------------------------------

# # #         if self.watchdog_task:

# # #             self.watchdog_task.cancel()

# # #         # ----------------------------------------------------
# # #         # Cancel supervisor health boundary
# # #         # ----------------------------------------------------

# # #         if self.supervisor_task:

# # #             self.supervisor_task.cancel()

# # #         # ----------------------------------------------------
# # #         # Wait for monitoring tasks
# # #         # ----------------------------------------------------

# # #         tasks = [
# # #             task
# # #             for task in (
# # #                 self.heartbeat_task,
# # #                 self.watchdog_task,
# # #                 self.supervisor_task,
# # #             )
# # #             if task is not None
# # #         ]

# # #         if tasks:

# # #             await asyncio.gather(
# # #                 *tasks,
# # #                 return_exceptions=True,
# # #             )

# # #         self.heartbeat_task = None
# # #         self.watchdog_task = None
# # #         self.supervisor_task = None

# # #         # ----------------------------------------------------
# # #         # Stop all supervised agents
# # #         # ----------------------------------------------------

# # #         try:

# # #             await self.supervisor.stop_all()

# # #         except Exception as error:

# # #             print(
# # #                 "[MONITORING] "
# # #                 f"Supervisor shutdown error: {error}"
# # #             )

# # #         # ----------------------------------------------------
# # #         # Close Redis
# # #         # ----------------------------------------------------

# # #         try:

# # #             await redis_client.aclose()

# # #         except Exception as error:

# # #             print(
# # #                 "[MONITORING] "
# # #                 f"Redis shutdown error: {error}"
# # #             )

# # #         print("=" * 80)
# # #         print("[MONITORING] SERVICE STOPPED")
# # #         print("=" * 80)


# # # # ============================================================
# # # # MAIN
# # # # ============================================================

# # # async def main():

# # #     service = MonitoringService()

# # #     try:

# # #         await service.start()

# # #         await service.wait_forever()

# # #     except asyncio.CancelledError:

# # #         raise

# # #     except KeyboardInterrupt:

# # #         print(
# # #             "\n[MONITORING] "
# # #             "Keyboard interrupt received."
# # #         )

# # #     finally:

# # #         await service.stop()


# # # # ============================================================
# # # # ENTRY POINT
# # # # ============================================================

# # # if __name__ == "__main__":

# # #     try:

# # #         asyncio.run(main())

# # #     except KeyboardInterrupt:

# # #         print(
# # #             "\n[MONITORING] "
# # #             "Stopped by operator."
# # #         )













# # import asyncio

# # from backend.app.messaging.redis_client import redis_client
# # from backend.app.monitoring.heartbeat_consumer import (
# #     heartbeat_consumer_loop,
# # )
# # from backend.app.monitoring.supervisor import AgentSupervisor
# # from backend.app.monitoring.watchdog import watchdog_loop


# # # ============================================================
# # # MONITORING SERVICE
# # # ============================================================

# # class MonitoringService:
# #     """
# #     Unified CCTV monitoring/control service.

# #     Responsibilities
# #     ----------------
# #     1. Consume agent heartbeats.
# #     2. Maintain the shared AgentRegistry.
# #     3. Detect dead agents through the Watchdog.
# #     4. Supervise agent subprocesses.
# #     5. Restart failed/unresponsive agents.
# #     6. Keep every agent failure isolated.

# #     Architecture
# #     ------------

# #         Agent Processes
# #               │
# #               │ heartbeat
# #               ▼
# #         Redis: events.system
# #               │
# #               ▼
# #        Heartbeat Consumer
# #               │
# #               ▼
# #         Shared AgentRegistry
# #               │
# #               ▼
# #            Watchdog
# #               │
# #               │ mark DEAD
# #               ▼
# #         Agent Supervisor
# #               │
# #               ▼
# #       Restart ONLY that agent

# #     Important
# #     ---------
# #     MonitoringService is the coordinator.

# #     AgentSupervisor is the ONLY restart authority.

# #     Watchdog only detects failures and marks agents DEAD.

# #     HeartbeatConsumer only updates AgentRegistry.

# #     Individual SupervisedAgent health loops inside the
# #     AgentSupervisor handle recovery of their own agents.
# #     """

# #     def __init__(self):
# #         self.supervisor = AgentSupervisor()

# #         self.running = False

# #         self.heartbeat_task: asyncio.Task | None = None
# #         self.watchdog_task: asyncio.Task | None = None

# #     # ========================================================
# #     # START
# #     # ========================================================

# #     async def start(self):
# #         """
# #         Start the complete monitoring stack.

# #         Startup order:

# #         1. Redis
# #         2. Agent Supervisor
# #         3. Heartbeat Consumer
# #         4. Watchdog
# #         """

# #         print("=" * 80)
# #         print("CCTV AI MONITORING SERVICE")
# #         print("=" * 80)

# #         print("[MONITORING] Starting unified monitoring service...")

# #         self.running = True

# #         # ----------------------------------------------------
# #         # Redis connection
# #         # ----------------------------------------------------

# #         try:
# #             await redis_client.ping()

# #             print(
# #                 "[MONITORING] Redis connection established."
# #             )

# #         except Exception as error:
# #             print(
# #                 "[MONITORING] FATAL: "
# #                 f"Redis connection failed: {error}"
# #             )

# #             self.running = False
# #             raise

# #         # ----------------------------------------------------
# #         # Start Supervisor
# #         # ----------------------------------------------------

# #         try:
# #             await self.supervisor.start_all()

# #         except Exception as error:
# #             print(
# #                 "[MONITORING] "
# #                 f"Supervisor startup error: {error}"
# #             )

# #             # IMPORTANT:
# #             # Monitoring service remains alive.
# #             #
# #             # AgentSupervisor isolates individual startup
# #             # failures, so one failed agent must not terminate
# #             # the monitoring service.

# #         # ----------------------------------------------------
# #         # Start Heartbeat Consumer
# #         # ----------------------------------------------------

# #         self.heartbeat_task = asyncio.create_task(
# #             self._run_heartbeat_consumer(),
# #             name="monitoring-heartbeat-consumer",
# #         )

# #         print(
# #             "[MONITORING] "
# #             "Heartbeat consumer started."
# #         )

# #         # ----------------------------------------------------
# #         # Start Watchdog
# #         # ----------------------------------------------------

# #         self.watchdog_task = asyncio.create_task(
# #             self._run_watchdog(),
# #             name="monitoring-watchdog",
# #         )

# #         print(
# #             "[MONITORING] "
# #             "Watchdog started."
# #         )

# #         # ----------------------------------------------------
# #         # Service ready
# #         # ----------------------------------------------------

# #         print("=" * 80)
# #         print("[MONITORING] SERVICE READY")
# #         print("=" * 80)

# #     # ========================================================
# #     # HEARTBEAT CONSUMER
# #     # ========================================================

# #     async def _run_heartbeat_consumer(self):
# #         """
# #         Run heartbeat consumer independently.

# #         If the heartbeat consumer itself crashes unexpectedly,
# #         restart only the heartbeat consumer.

# #         Agent processes are NOT affected.
# #         """

# #         while self.running:

# #             try:
# #                 await heartbeat_consumer_loop(
# #                     redis_client
# #                 )

# #             except asyncio.CancelledError:
# #                 raise

# #             except Exception as error:

# #                 print(
# #                     "[MONITORING] "
# #                     f"Heartbeat consumer crashed: {error}"
# #                 )

# #                 if not self.running:
# #                     break

# #                 print(
# #                     "[MONITORING] "
# #                     "Restarting heartbeat consumer..."
# #                 )

# #                 await asyncio.sleep(2)

# #     # ========================================================
# #     # WATCHDOG
# #     # ========================================================

# #     async def _run_watchdog(self):
# #         """
# #         Run watchdog independently.

# #         Watchdog:

# #         - checks AgentRegistry
# #         - detects heartbeat timeout
# #         - marks agent DEAD

# #         Watchdog does NOT restart agents.

# #         AgentSupervisor remains the single restart authority.
# #         """

# #         while self.running:

# #             try:
# #                 await watchdog_loop()

# #             except asyncio.CancelledError:
# #                 raise

# #             except Exception as error:

# #                 print(
# #                     "[MONITORING] "
# #                     f"Watchdog crashed: {error}"
# #                 )

# #                 if not self.running:
# #                     break

# #                 print(
# #                     "[MONITORING] "
# #                     "Restarting watchdog..."
# #                 )

# #                 await asyncio.sleep(2)

# #     # ========================================================
# #     # WAIT
# #     # ========================================================

# #     async def wait_forever(self):
# #         """
# #         Keep the monitoring service alive.
# #         """

# #         while self.running:
# #             await asyncio.sleep(1)

# #     # ========================================================
# #     # STOP
# #     # ========================================================

# #     async def stop(self):
# #         """
# #         Gracefully shut down the complete monitoring service.

# #         Shutdown order:

# #         1. Stop accepting monitoring work.
# #         2. Cancel heartbeat consumer.
# #         3. Cancel watchdog.
# #         4. Stop supervised agents.
# #         5. Close shared Redis connection.
# #         """

# #         if not self.running:
# #             return

# #         print("=" * 80)
# #         print("[MONITORING] Shutdown requested.")
# #         print("=" * 80)

# #         # ----------------------------------------------------
# #         # Stop service loops
# #         # ----------------------------------------------------

# #         self.running = False

# #         # ----------------------------------------------------
# #         # Cancel heartbeat consumer
# #         # ----------------------------------------------------

# #         if self.heartbeat_task:
# #             self.heartbeat_task.cancel()

# #         # ----------------------------------------------------
# #         # Cancel watchdog
# #         # ----------------------------------------------------

# #         if self.watchdog_task:
# #             self.watchdog_task.cancel()

# #         # ----------------------------------------------------
# #         # Wait for monitoring tasks
# #         # ----------------------------------------------------

# #         tasks = [
# #             task
# #             for task in (
# #                 self.heartbeat_task,
# #                 self.watchdog_task,
# #             )
# #             if task is not None
# #         ]

# #         if tasks:

# #             await asyncio.gather(
# #                 *tasks,
# #                 return_exceptions=True,
# #             )

# #         self.heartbeat_task = None
# #         self.watchdog_task = None

# #         # ----------------------------------------------------
# #         # Stop supervised agents
# #         # ----------------------------------------------------

# #         try:

# #             await self.supervisor.stop_all()

# #         except Exception as error:

# #             print(
# #                 "[MONITORING] "
# #                 f"Supervisor shutdown error: {error}"
# #             )

# #         # ----------------------------------------------------
# #         # Close shared Redis connection
# #         # ----------------------------------------------------

# #         try:

# #             await redis_client.aclose()

# #         except Exception as error:

# #             print(
# #                 "[MONITORING] "
# #                 f"Redis shutdown error: {error}"
# #             )

# #         # ----------------------------------------------------
# #         # Final status
# #         # ----------------------------------------------------

# #         print("=" * 80)
# #         print("[MONITORING] SERVICE STOPPED")
# #         print("=" * 80)


# # # ============================================================
# # # MAIN
# # # ============================================================

# # async def main():

# #     service = MonitoringService()

# #     try:

# #         await service.start()

# #         await service.wait_forever()

# #     except asyncio.CancelledError:
# #         raise

# #     except KeyboardInterrupt:

# #         print(
# #             "\n[MONITORING] "
# #             "Keyboard interrupt received."
# #         )

# #     finally:

# #         await service.stop()


# # # ============================================================
# # # ENTRY POINT
# # # ============================================================

# # if __name__ == "__main__":

# #     try:

# #         asyncio.run(main())

# #     except KeyboardInterrupt:

# #         print(
# #             "\n[MONITORING] "
# #             "Stopped by operator."
# #         )




























# import asyncio

# from backend.app.messaging.redis_client import redis_client

# from backend.app.monitoring.heartbeat_consumer import (
#     heartbeat_consumer_loop,
# )

# from backend.app.monitoring.supervisor import AgentSupervisor

# from backend.app.monitoring.watchdog import watchdog_loop


# # ============================================================
# # MONITORING SERVICE
# # ============================================================

# class MonitoringService:
#     """
#     Unified CCTV monitoring/control service.

#     Responsibilities
#     ----------------
#     1. Consume agent heartbeats.
#     2. Maintain shared AgentRegistry.
#     3. Supervise agent subprocesses.
#     4. Detect heartbeat failures.
#     5. Restart failed/unresponsive agents.
#     6. Keep every agent failure isolated.

#     Architecture
#     ------------

#         Agent Processes
#                │
#                │ heartbeat
#                ▼
#         Redis: events.system
#                │
#                ▼
#         Heartbeat Consumer
#                │
#                ▼
#         Shared AgentRegistry
#                │
#                ▼
#         Agent Supervisor
#                │
#                ▼
#         Heartbeat Timeout
#                │
#                ▼
#         Unified Recovery
#                │
#                ▼
#         Restart ONLY failed agent

#     Recovery authority
#     ------------------
#     AgentSupervisor.recover()

#     Watchdog is observational only.
#     """

#     def __init__(self):

#         self.supervisor = AgentSupervisor()

#         self.running = False

#         self.heartbeat_task = None

#         self.watchdog_task = None

#     # ========================================================
#     # START
#     # ========================================================

#     async def start(self):

#         print("=" * 80)

#         print(
#             "CCTV AI MONITORING SERVICE"
#         )

#         print("=" * 80)

#         print(
#             "[MONITORING] "
#             "Starting unified monitoring service..."
#         )

#         self.running = True

#         # ----------------------------------------------------
#         # Redis
#         # ----------------------------------------------------

#         try:

#             await redis_client.ping()

#             print(
#                 "[MONITORING] "
#                 "Redis connection established."
#             )

#         except Exception as error:

#             print(
#                 "[MONITORING] FATAL: "
#                 f"Redis connection failed: {error}"
#             )

#             self.running = False

#             raise

#         # ----------------------------------------------------
#         # Supervisor
#         # ----------------------------------------------------

#         try:

#             await self.supervisor.start_all()

#         except Exception as error:

#             print(
#                 "[MONITORING] "
#                 f"Supervisor startup error: {error}"
#             )

#         # ----------------------------------------------------
#         # Heartbeat Consumer
#         # ----------------------------------------------------

#         self.heartbeat_task = asyncio.create_task(
#             self._run_heartbeat_consumer(),
#             name="monitoring-heartbeat-consumer",
#         )

#         print(
#             "[MONITORING] "
#             "Heartbeat consumer started."
#         )

#         # ----------------------------------------------------
#         # Watchdog
#         #
#         # Observational health monitor.
#         # Supervisor remains the recovery authority.
#         # ----------------------------------------------------

#         self.watchdog_task = asyncio.create_task(
#             self._run_watchdog(),
#             name="monitoring-watchdog",
#         )

#         print(
#             "[MONITORING] "
#             "Watchdog started."
#         )

#         # ----------------------------------------------------
#         # Ready
#         # ----------------------------------------------------

#         print("=" * 80)

#         print(
#             "[MONITORING] SERVICE READY"
#         )

#         print("=" * 80)

#     # ========================================================
#     # HEARTBEAT CONSUMER
#     # ========================================================

#     async def _run_heartbeat_consumer(self):

#         while self.running:

#             try:

#                 await heartbeat_consumer_loop(
#                     redis_client
#                 )

#             except asyncio.CancelledError:

#                 raise

#             except Exception as error:

#                 print(
#                     "[MONITORING] "
#                     f"Heartbeat consumer crashed: "
#                     f"{error}"
#                 )

#                 if not self.running:
#                     break

#                 print(
#                     "[MONITORING] "
#                     "Restarting heartbeat consumer..."
#                 )

#                 await asyncio.sleep(2)

#     # ========================================================
#     # WATCHDOG
#     # ========================================================

#     async def _run_watchdog(self):

#         while self.running:

#             try:

#                 await watchdog_loop()

#             except asyncio.CancelledError:

#                 raise

#             except Exception as error:

#                 print(
#                     "[MONITORING] "
#                     f"Watchdog crashed: {error}"
#                 )

#                 if not self.running:
#                     break

#                 print(
#                     "[MONITORING] "
#                     "Restarting watchdog..."
#                 )

#                 await asyncio.sleep(2)

#     # ========================================================
#     # WAIT
#     # ========================================================

#     async def wait_forever(self):

#         while self.running:

#             await asyncio.sleep(1)

#     # ========================================================
#     # STOP
#     # ========================================================

#     async def stop(self):

#         if not self.running:
#             return

#         print("=" * 80)

#         print(
#             "[MONITORING] "
#             "Shutdown requested."
#         )

#         print("=" * 80)

#         self.running = False

#         # ----------------------------------------------------
#         # Cancel monitoring tasks
#         # ----------------------------------------------------

#         if self.heartbeat_task:

#             self.heartbeat_task.cancel()

#         if self.watchdog_task:

#             self.watchdog_task.cancel()

#         tasks = [
#             task
#             for task in (
#                 self.heartbeat_task,
#                 self.watchdog_task,
#             )
#             if task is not None
#         ]

#         if tasks:

#             await asyncio.gather(
#                 *tasks,
#                 return_exceptions=True,
#             )

#         self.heartbeat_task = None

#         self.watchdog_task = None

#         # ----------------------------------------------------
#         # Stop agents
#         # ----------------------------------------------------

#         try:

#             await self.supervisor.stop_all()

#         except Exception as error:

#             print(
#                 "[MONITORING] "
#                 f"Supervisor shutdown error: "
#                 f"{error}"
#             )

#         # ----------------------------------------------------
#         # Close Redis
#         # ----------------------------------------------------

#         try:

#             await redis_client.aclose()

#         except Exception as error:

#             print(
#                 "[MONITORING] "
#                 f"Redis shutdown error: "
#                 f"{error}"
#             )

#         print("=" * 80)

#         print(
#             "[MONITORING] SERVICE STOPPED"
#         )

#         print("=" * 80)


# # ============================================================
# # MAIN
# # ============================================================

# async def main():

#     service = MonitoringService()

#     try:

#         await service.start()

#         await service.wait_forever()

#     except asyncio.CancelledError:

#         raise

#     except KeyboardInterrupt:

#         print(
#             "\n[MONITORING] "
#             "Keyboard interrupt received."
#         )

#     finally:

#         await service.stop()


# # ============================================================
# # ENTRY POINT
# # ============================================================

# if __name__ == "__main__":

#     try:

#         asyncio.run(main())

#     except KeyboardInterrupt:

#         print(
#             "\n[MONITORING] "
#             "Stopped by operator."
#         )

























from __future__ import annotations

import asyncio

from backend.app.messaging.redis_client import redis_client
from backend.app.monitoring.heartbeat_consumer import (
    heartbeat_consumer_loop,
)
from backend.app.monitoring.supervisor import AgentSupervisor
from backend.app.monitoring.watchdog import watchdog_loop


# ============================================================
# MONITORING SERVICE
# ============================================================

class MonitoringService:
    """
    Unified CCTV monitoring/control service.

    Responsibilities
    ----------------
    1. Consume agent heartbeats.
    2. Maintain the shared AgentRegistry.
    3. Supervise agent subprocesses.
    4. Detect heartbeat failures.
    5. Restart failed/unresponsive agents.
    6. Keep every agent failure isolated.
    7. Keep monitoring components themselves recoverable.

    Architecture
    ------------

        Agent Processes
              │
              │ heartbeat
              ▼
        Redis: events.system
              │
              ▼
        Heartbeat Consumer
              │
              ▼
        Shared AgentRegistry
              │
              ├──────────────► Watchdog
              │                  │
              │                  │ observation
              │                  ▼
              │             Health State
              │
              ▼
        Agent Supervisor
              │
              ▼
        Heartbeat Timeout
              │
              ▼
        Unified Recovery
              │
              ▼
        Restart ONLY failed agent

    Recovery authority
    ------------------
    AgentSupervisor.recover()

    Watchdog is observational only.

    Fault isolation
    ---------------
    Failure of:
        - one camera
        - one camera stream
        - one detector
        - one agent
        - one heartbeat
        - one processing worker
        - watchdog
        - heartbeat consumer

    must not intentionally terminate unrelated agents.
    """

    def __init__(self) -> None:
        self.supervisor = AgentSupervisor()

        self.running = False

        self.heartbeat_task: asyncio.Task | None = None
        self.watchdog_task: asyncio.Task | None = None

        self._started = False

    # ========================================================
    # START
    # ========================================================

    async def start(self) -> None:
        """
        Start the complete monitoring stack.

        Startup order:

            Redis
              ↓
            Supervisor / agents
              ↓
            Heartbeat consumer
              ↓
            Watchdog
              ↓
            SERVICE READY
        """

        if self.running:
            print("[MONITORING] Service is already running.")
            return

        print("=" * 80)
        print("CCTV AI MONITORING SERVICE")
        print("=" * 80)

        print(
            "[MONITORING] "
            "Starting unified monitoring service..."
        )

        self.running = True

        # ----------------------------------------------------
        # Redis
        # ----------------------------------------------------

        try:
            await redis_client.ping()

            print(
                "[MONITORING] "
                "Redis connection established."
            )

        except Exception as error:
            self.running = False

            print(
                "[MONITORING] FATAL: "
                f"Redis connection failed: {error}"
            )

            raise

        # ----------------------------------------------------
        # Supervisor
        # ----------------------------------------------------

        try:
            await self.supervisor.start_all()

        except Exception as error:
            print(
                "[MONITORING] "
                f"Supervisor startup error: {error}"
            )

            # The supervisor may already have started some
            # isolated agents before encountering an exception.
            #
            # Do not falsely declare the service ready.
            self.running = False

            try:
                await self.supervisor.stop_all()
            except Exception as stop_error:
                print(
                    "[MONITORING] "
                    "Supervisor cleanup after startup failure "
                    f"also failed: {stop_error}"
                )

            raise

        # ----------------------------------------------------
        # Heartbeat Consumer
        # ----------------------------------------------------

        try:
            self.heartbeat_task = asyncio.create_task(
                self._run_heartbeat_consumer(),
                name="monitoring-heartbeat-consumer",
            )

            print(
                "[MONITORING] "
                "Heartbeat consumer started."
            )

        except Exception as error:
            print(
                "[MONITORING] "
                f"Failed to start heartbeat consumer: {error}"
            )

            self.running = False

            try:
                await self.supervisor.stop_all()
            except Exception as stop_error:
                print(
                    "[MONITORING] "
                    f"Supervisor cleanup failed: {stop_error}"
                )

            raise

        # ----------------------------------------------------
        # Watchdog
        #
        # Observational health monitor.
        #
        # Supervisor remains the recovery authority.
        # ----------------------------------------------------

        try:
            self.watchdog_task = asyncio.create_task(
                self._run_watchdog(),
                name="monitoring-watchdog",
            )

            print(
                "[MONITORING] "
                "Watchdog started."
            )

        except Exception as error:
            print(
                "[MONITORING] "
                f"Failed to start watchdog: {error}"
            )

            self.running = False

            await self._cancel_monitoring_tasks()

            try:
                await self.supervisor.stop_all()
            except Exception as stop_error:
                print(
                    "[MONITORING] "
                    f"Supervisor cleanup failed: {stop_error}"
                )

            raise

        # ----------------------------------------------------
        # Ready
        # ----------------------------------------------------

        self._started = True

        print("=" * 80)
        print("[MONITORING] SERVICE READY")
        print("=" * 80)

    # ========================================================
    # HEARTBEAT CONSUMER
    # ========================================================

    async def _run_heartbeat_consumer(self) -> None:
        """
        Run heartbeat consumer continuously.

        If the consumer crashes, restart it without touching
        unrelated camera/agent processes.
        """

        while self.running:

            try:
                await heartbeat_consumer_loop(
                    redis_client
                )

                # Normally heartbeat_consumer_loop() should remain
                # alive. If it returns unexpectedly while the
                # service is still running, do not silently stop
                # monitoring.
                if self.running:
                    print(
                        "[MONITORING] "
                        "Heartbeat consumer exited unexpectedly."
                    )

                    await asyncio.sleep(1)

            except asyncio.CancelledError:
                raise

            except Exception as error:
                print(
                    "[MONITORING] "
                    "Heartbeat consumer crashed: "
                    f"{error}"
                )

                if not self.running:
                    break

                print(
                    "[MONITORING] "
                    "Restarting heartbeat consumer..."
                )

                await asyncio.sleep(2)

    # ========================================================
    # WATCHDOG
    # ========================================================

    async def _run_watchdog(self) -> None:
        """
        Run watchdog continuously.

        Watchdog observes health state.

        It does NOT directly restart agents.

        AgentSupervisor remains the single recovery authority.
        """

        while self.running:

            try:
                await watchdog_loop()

                # A watchdog loop returning unexpectedly should
                # not silently disable health monitoring.
                if self.running:
                    print(
                        "[MONITORING] "
                        "Watchdog exited unexpectedly."
                    )

                    await asyncio.sleep(1)

            except asyncio.CancelledError:
                raise

            except Exception as error:
                print(
                    "[MONITORING] "
                    f"Watchdog crashed: {error}"
                )

                if not self.running:
                    break

                print(
                    "[MONITORING] "
                    "Restarting watchdog..."
                )

                await asyncio.sleep(2)

    # ========================================================
    # MONITORING TASK CLEANUP
    # ========================================================

    async def _cancel_monitoring_tasks(self) -> None:
        """
        Cancel heartbeat/watchdog tasks safely.

        This function does not stop supervised agents.
        """

        tasks = []

        if self.heartbeat_task is not None:
            if not self.heartbeat_task.done():
                self.heartbeat_task.cancel()

            tasks.append(self.heartbeat_task)

        if self.watchdog_task is not None:
            if not self.watchdog_task.done():
                self.watchdog_task.cancel()

            tasks.append(self.watchdog_task)

        if tasks:
            await asyncio.gather(
                *tasks,
                return_exceptions=True,
            )

        self.heartbeat_task = None
        self.watchdog_task = None

    # ========================================================
    # WAIT
    # ========================================================

    async def wait_forever(self) -> None:
        """
        Keep the monitoring service alive.
        """

        while self.running:

            # Detect a monitoring task that unexpectedly died.

            if (
                self.heartbeat_task is not None
                and self.heartbeat_task.done()
                and self.running
            ):
                error = self.heartbeat_task.exception()

                if error is not None:
                    print(
                        "[MONITORING] "
                        "Heartbeat monitoring task terminated: "
                        f"{error}"
                    )

            if (
                self.watchdog_task is not None
                and self.watchdog_task.done()
                and self.running
            ):
                error = self.watchdog_task.exception()

                if error is not None:
                    print(
                        "[MONITORING] "
                        "Watchdog monitoring task terminated: "
                        f"{error}"
                    )

            await asyncio.sleep(1)

    # ========================================================
    # STOP
    # ========================================================

    async def stop(self) -> None:
        """
        Stop the complete monitoring service safely.

        Shutdown order:

            stop service
                 ↓
            cancel monitoring tasks
                 ↓
            stop supervised agents
                 ↓
            close Redis
        """

        if not self.running and not self._started:
            return

        print("=" * 80)
        print("[MONITORING] Shutdown requested.")
        print("=" * 80)

        self.running = False

        # ----------------------------------------------------
        # Cancel monitoring tasks
        # ----------------------------------------------------

        try:
            await self._cancel_monitoring_tasks()

        except Exception as error:
            print(
                "[MONITORING] "
                f"Monitoring task shutdown error: {error}"
            )

        # ----------------------------------------------------
        # Stop supervised agents
        # ----------------------------------------------------

        try:
            await self.supervisor.stop_all()

        except Exception as error:
            print(
                "[MONITORING] "
                f"Supervisor shutdown error: {error}"
            )

        # ----------------------------------------------------
        # Close Redis
        # ----------------------------------------------------

        try:
            await redis_client.aclose()

        except Exception as error:
            print(
                "[MONITORING] "
                f"Redis shutdown error: {error}"
            )

        self._started = False

        print("=" * 80)
        print("[MONITORING] SERVICE STOPPED")
        print("=" * 80)


# ============================================================
# MAIN
# ============================================================

async def main() -> None:
    service = MonitoringService()

    try:
        await service.start()
        await service.wait_forever()

    except asyncio.CancelledError:
        raise

    except KeyboardInterrupt:
        print(
            "\n[MONITORING] "
            "Keyboard interrupt received."
        )

    except Exception as error:
        print(
            "\n[MONITORING] "
            f"Fatal service error: {error}"
        )

    finally:
        await service.stop()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        print(
            "\n[MONITORING] "
            "Stopped by operator."
        )