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
            │                │
            │                │ observation
            │                ▼
            │            Health State
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
        - heartbeat consumer
        - watchdog

    must not intentionally terminate unrelated agents.

    Redis ownership
    ---------------
    `redis_client` is imported from the application's shared
    messaging layer.

    MonitoringService uses that client but does NOT close it.

    The application-level Redis lifecycle owns creation and
    shutdown of the shared client.
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
            print(
                "[MONITORING] "
                "Service is already running."
            )
            return

        print("=" * 80)
        print("CCTV AI MONITORING SERVICE")
        print("=" * 80)

        print(
            "[MONITORING] "
            "Starting unified monitoring service..."
        )

        self.running = True
        self._started = False

        # ----------------------------------------------------
        # Redis
        # ----------------------------------------------------

        try:
            await redis_client.ping()

            print(
                "[MONITORING] "
                "Redis connection established."
            )

        except asyncio.CancelledError:
            self.running = False
            raise

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

        except asyncio.CancelledError:
            self.running = False

            try:
                await self.supervisor.stop_all()
            except Exception as cleanup_error:
                print(
                    "[MONITORING] "
                    "Supervisor cleanup after cancellation "
                    f"failed: {cleanup_error}"
                )

            raise

        except Exception as error:
            print(
                "[MONITORING] "
                f"Supervisor startup error: {error}"
            )

            self.running = False

            try:
                await self.supervisor.stop_all()

            except asyncio.CancelledError:
                raise

            except Exception as cleanup_error:
                print(
                    "[MONITORING] "
                    "Supervisor cleanup after startup failure "
                    f"also failed: {cleanup_error}"
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

        except asyncio.CancelledError:
            self.running = False

            await self._cancel_monitoring_tasks()

            try:
                await self.supervisor.stop_all()
            except Exception as cleanup_error:
                print(
                    "[MONITORING] "
                    "Supervisor cleanup after cancellation "
                    f"failed: {cleanup_error}"
                )

            raise

        except Exception as error:
            print(
                "[MONITORING] "
                f"Failed to start heartbeat consumer: {error}"
            )

            self.running = False

            await self._cancel_monitoring_tasks()

            try:
                await self.supervisor.stop_all()
            except Exception as cleanup_error:
                print(
                    "[MONITORING] "
                    f"Supervisor cleanup failed: {cleanup_error}"
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

        except asyncio.CancelledError:
            self.running = False

            await self._cancel_monitoring_tasks()

            try:
                await self.supervisor.stop_all()
            except Exception as cleanup_error:
                print(
                    "[MONITORING] "
                    "Supervisor cleanup after cancellation "
                    f"failed: {cleanup_error}"
                )

            raise

        except Exception as error:
            print(
                "[MONITORING] "
                f"Failed to start watchdog: {error}"
            )

            self.running = False

            await self._cancel_monitoring_tasks()

            try:
                await self.supervisor.stop_all()
            except Exception as cleanup_error:
                print(
                    "[MONITORING] "
                    f"Supervisor cleanup failed: {cleanup_error}"
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

                if self.running:
                    print(
                        "[MONITORING] "
                        "Heartbeat consumer exited unexpectedly."
                    )

                    await asyncio.sleep(1)

            except asyncio.CancelledError:
                print(
                    "[MONITORING] "
                    "Heartbeat consumer cancellation received."
                )
                raise

            except Exception as error:
                print(
                    "[MONITORING] "
                    "Heartbeat consumer crashed: "
                    f"{type(error).__name__}: {error}"
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

                if self.running:
                    print(
                        "[MONITORING] "
                        "Watchdog exited unexpectedly."
                    )

                    await asyncio.sleep(1)

            except asyncio.CancelledError:
                print(
                    "[MONITORING] "
                    "Watchdog cancellation received."
                )
                raise

            except Exception as error:
                print(
                    "[MONITORING] "
                    f"Watchdog crashed: "
                    f"{type(error).__name__}: {error}"
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

        tasks: list[asyncio.Task] = []

        heartbeat_task = self.heartbeat_task

        if heartbeat_task is not None:

            if (
                not heartbeat_task.done()
                and not heartbeat_task.cancelled()
            ):
                heartbeat_task.cancel()

            tasks.append(heartbeat_task)

        watchdog_task = self.watchdog_task

        if watchdog_task is not None:

            if (
                not watchdog_task.done()
                and not watchdog_task.cancelled()
            ):
                watchdog_task.cancel()

            tasks.append(watchdog_task)

        if tasks:
            await asyncio.gather(
                *tasks,
                return_exceptions=True,
            )

        self.heartbeat_task = None
        self.watchdog_task = None

    # ========================================================
    # TASK STATUS
    # ========================================================

    @staticmethod
    def _task_failure(
        task: asyncio.Task | None,
    ) -> BaseException | None:
        """
        Safely retrieve a task exception.

        Important:
            task.exception() raises CancelledError when the task
            was cancelled, so cancellation must be checked first.
        """

        if task is None:
            return None

        if not task.done():
            return None

        if task.cancelled():
            return None

        try:
            return task.exception()
        except asyncio.CancelledError:
            return None
        except Exception as error:
            return error

    # ========================================================
    # WAIT
    # ========================================================

    async def wait_forever(self) -> None:
        """
        Keep the monitoring service alive.

        Monitoring tasks normally self-recover through their
        wrapper loops.

        This method only observes unexpected task termination
        and never directly restarts agents.
        """

        while self.running:

            # ------------------------------------------------
            # Heartbeat task
            # ------------------------------------------------

            heartbeat_task = self.heartbeat_task

            if (
                heartbeat_task is not None
                and heartbeat_task.done()
                and self.running
            ):
                error = self._task_failure(
                    heartbeat_task
                )

                if error is not None:
                    print(
                        "[MONITORING] "
                        "Heartbeat monitoring task terminated: "
                        f"{type(error).__name__}: {error}"
                    )

            # ------------------------------------------------
            # Watchdog task
            # ------------------------------------------------

            watchdog_task = self.watchdog_task

            if (
                watchdog_task is not None
                and watchdog_task.done()
                and self.running
            ):
                error = self._task_failure(
                    watchdog_task
                )

                if error is not None:
                    print(
                        "[MONITORING] "
                        "Watchdog monitoring task terminated: "
                        f"{type(error).__name__}: {error}"
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
            application owns Redis lifecycle

        The shared `redis_client` is intentionally NOT closed here.
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

        except asyncio.CancelledError:
            raise

        except Exception as error:
            print(
                "[MONITORING] "
                "Monitoring task shutdown error: "
                f"{type(error).__name__}: {error}"
            )

        # ----------------------------------------------------
        # Stop supervised agents
        # ----------------------------------------------------

        try:
            await self.supervisor.stop_all()

        except asyncio.CancelledError:
            raise

        except Exception as error:
            print(
                "[MONITORING] "
                "Supervisor shutdown error: "
                f"{type(error).__name__}: {error}"
            )

        # ----------------------------------------------------
        # Redis
        # ----------------------------------------------------
        #
        # IMPORTANT:
        #
        # redis_client is the shared application Redis client.
        # MonitoringService does not own its lifecycle.
        #
        # The application/bootstrap layer should call:
        #
        #     await redis_client.aclose()
        #
        # when the entire application shuts down.
        #
        # ----------------------------------------------------

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
            f"Fatal service error: "
            f"{type(error).__name__}: {error}"
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