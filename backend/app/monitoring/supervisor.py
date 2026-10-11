"""
Per-agent production process supervisor.

Responsibilities
----------------

- Start production agents as isolated subprocesses.
- Create one camera-bound detection worker per enabled camera.
- Create one camera-bound tracker worker per enabled camera.
- Provide camera and agent identity configuration to subprocesses.
- Monitor process lifetime.
- Monitor heartbeat health.
- Recover only the failed agent.
- Prevent concurrent/duplicate recovery of the same agent.
- Apply exponential restart backoff.
- Limit repeated restart failures.
- Respect startup grace periods.
- Automatically retry failed startup/recovery.
- Keep one agent failure isolated from all other agents.
- Recover failed monitoring tasks themselves.

Multi-camera model
------------------

CAM01 -> person-detector-CAM01
CAM01 -> tracker-CAM01

CAM02 -> person-detector-CAM02
CAM02 -> tracker-CAM02

CAM03 -> person-detector-CAM03
CAM03 -> tracker-CAM03

Global downstream agents remain shared.

Process identity
----------------

Every subprocess generation receives:

    AGENT_ID
    AGENT_PROCESS_GENERATION
    AGENT_INSTANCE_ID

Example:

    tracker-CAM01
        generation = 1
        instance_id = tracker-CAM01-g1

After recovery:

    tracker-CAM01
        generation = 2
        instance_id = tracker-CAM01-g2

Heartbeat validation requires BOTH:

    instance_id
    process_generation

to match the supervisor's current generation.

Failure isolation
-----------------

A failure in:

    detector-CAM01

must NOT restart:

    detector-CAM02
    tracker-CAM02
    behavior
    crowd
    security
    alert
    incident
    evidence

Each SupervisedAgent owns its own:

    process
    process generation
    recovery lock
    recovery task
    process monitor
    health monitor
    failure counter
    failure-generation guards
    heartbeat-generation guards

Monitoring isolation
--------------------

Failure of:

    process monitor
    health monitor

must not terminate the supervised subprocess or unrelated
agents.

The AgentSupervisor continuously verifies that each monitoring
task exists and recreates failed monitoring tasks.
"""

from __future__ import annotations

import asyncio
import os
import re
import socket
import sys

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


from backend.app.cameras.registry import CameraRegistry
from backend.app.monitoring.agent_registry import agent_registry


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[3]

PYTHON_EXECUTABLE = sys.executable


# ============================================================
# SAFE ENVIRONMENT PARSING
# ============================================================


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


# ============================================================
# SUPERVISOR CONFIGURATION
# ============================================================

STARTUP_DELAY = _positive_float(
    "SUPERVISOR_STARTUP_DELAY",
    2.0,
)

RESTART_DELAY = _positive_float(
    "SUPERVISOR_RESTART_DELAY",
    3.0,
)

MAX_CONSECUTIVE_FAILURES = _positive_int(
    "SUPERVISOR_MAX_CONSECUTIVE_FAILURES",
    5,
)

HEALTHY_RESET_SECONDS = _positive_float(
    "SUPERVISOR_HEALTHY_RESET_SECONDS",
    60.0,
)

MAX_BACKOFF_SECONDS = _positive_float(
    "SUPERVISOR_MAX_BACKOFF_SECONDS",
    30.0,
)

HEALTH_CHECK_INTERVAL = _positive_float(
    "SUPERVISOR_HEALTH_CHECK_INTERVAL",
    2.0,
)

STARTUP_GRACE_PERIOD = _positive_float(
    "SUPERVISOR_STARTUP_GRACE_PERIOD",
    20.0,
)

PROCESS_STOP_TIMEOUT = _positive_float(
    "SUPERVISOR_PROCESS_STOP_TIMEOUT",
    10.0,
)

# How often the supervisor verifies that each monitoring task
# is still alive.
MONITORING_TASK_CHECK_INTERVAL = _positive_float(
    "SUPERVISOR_MONITORING_TASK_CHECK_INTERVAL",
    5.0,
)


# ============================================================
# HEARTBEAT CONFIGURATION
# ============================================================

HEARTBEAT_TIMEOUT = _positive_float(
    "HEARTBEAT_TIMEOUT",
    30.0,
)


# ============================================================
# AGENT CONFIGURATION
# ============================================================


@dataclass(frozen=True)
class AgentProcessConfig:
    """
    Immutable configuration for one supervised subprocess.
    """

    name: str
    agent_id: str
    script: str

    camera_id: Optional[str] = None
    camera_source: Optional[str] = None
    camera_name: Optional[str] = None
    camera_location: Optional[str] = None

    stream_name: Optional[str] = None
    consumer_group: Optional[str] = None


# ============================================================
# GLOBAL PRODUCTION AGENTS
# ============================================================

GLOBAL_PRODUCTION_AGENTS = [
    AgentProcessConfig(
        name="behavior",
        agent_id="behavior-01",
        script="agents/behavior/main.py",
    ),
    AgentProcessConfig(
        name="crowd",
        agent_id="crowd-01",
        script="agents/crowd/main.py",
    ),
    AgentProcessConfig(
        name="security",
        agent_id="security-01",
        script="agents/security/main.py",
    ),
    AgentProcessConfig(
        name="alert",
        agent_id="alert-01",
        script="agents/alert/main.py",
    ),
    AgentProcessConfig(
        name="incident",
        agent_id="incident-01",
        script="agents/incident/main.py",
    ),
    AgentProcessConfig(
        name="evidence",
        agent_id="evidence-01",
        script="agents/evidence/main.py",
    ),
]


# ============================================================
# CAMERA ID SANITIZATION
# ============================================================


def _safe_agent_id_component(
    camera_id: str,
) -> str:
    value = camera_id.strip()

    value = re.sub(
        r"[^A-Za-z0-9_.-]+",
        "-",
        value,
    )

    value = re.sub(
        r"-+",
        "-",
        value,
    )

    value = value.strip("-")

    if not value:
        raise ValueError(
            "Camera ID cannot produce a valid agent ID: "
            f"{camera_id!r}"
        )

    return value


# ============================================================
# SUPERVISED AGENT
# ============================================================


class SupervisedAgent:
    """
    Supervises exactly ONE subprocess.

    This class is the primary failure-isolation boundary.

    A failure in one instance must not directly affect another
    SupervisedAgent.
    """

    def __init__(
        self,
        config: AgentProcessConfig,
    ) -> None:

        self.config = config

        # ----------------------------------------------------
        # Current process
        # ----------------------------------------------------

        self.process: Optional[
            asyncio.subprocess.Process
        ] = None

        # ----------------------------------------------------
        # Process generation
        # ----------------------------------------------------

        self.process_generation = 0

        self.instance_id: Optional[str] = None

        # ----------------------------------------------------
        # Lifecycle
        # ----------------------------------------------------

        self.running = False

        self.intentional_stop = False

        self.stopping_for_recovery = False

        # ----------------------------------------------------
        # Recovery synchronization
        # ----------------------------------------------------

        self.restart_lock = asyncio.Lock()

        self.recovery_in_progress = False

        self.recovery_task: Optional[
            asyncio.Task
        ] = None

        # ----------------------------------------------------
        # Monitor tasks
        # ----------------------------------------------------

        self.process_monitor_task: Optional[
            asyncio.Task
        ] = None

        self.health_monitor_task: Optional[
            asyncio.Task
        ] = None

        # ----------------------------------------------------
        # Timing
        # ----------------------------------------------------

        self.started_at: Optional[float] = None

        self.started_at_wallclock: Optional[
            datetime
        ] = None

        self.healthy_since: Optional[float] = None

        # ----------------------------------------------------
        # Failure accounting
        # ----------------------------------------------------

        self.consecutive_failures = 0

        # ----------------------------------------------------
        # Generation-aware failure guards
        # ----------------------------------------------------

        self.process_failure_handled_generation: Optional[
            int
        ] = None

        self.heartbeat_failure_handled_generation: Optional[
            int
        ] = None

        # ----------------------------------------------------
        # Heartbeat state
        # ----------------------------------------------------

        self.first_heartbeat_received = False

        self.heartbeat_timeout_triggered = False

        # ----------------------------------------------------
        # Invalid heartbeat identity tracking
        #
        # Important:
        #
        # A stale registry heartbeat must not leave the agent
        # stuck forever.
        # ----------------------------------------------------

        self.heartbeat_identity_invalid_since: Optional[
            float
        ] = None

    # ========================================================
    # PROPERTIES
    # ========================================================

    @property
    def agent_id(self) -> str:
        return self.config.agent_id

    @property
    def camera_id(self) -> Optional[str]:
        return self.config.camera_id

    @property
    def camera_source(self) -> Optional[str]:
        return self.config.camera_source

    @property
    def camera_name(self) -> Optional[str]:
        return self.config.camera_name

    @property
    def camera_location(self) -> Optional[str]:
        return self.config.camera_location

    @property
    def script_path(self) -> Path:
        return PROJECT_ROOT / self.config.script

    @property
    def pid(self) -> Optional[int]:
        process = self.process

        if process is None:
            return None

        return process.pid

    # ========================================================
    # GENERATION IDENTITY
    # ========================================================

    def _build_instance_id(
        self,
        generation: int,
    ) -> str:
        return (
            f"{self.agent_id}"
            f"-g{generation}"
        )

    def _register_generation(
        self,
        generation: int,
    ) -> None:

        instance_id = self._build_instance_id(
            generation
        )

        self.instance_id = instance_id

        hostname = socket.gethostname()

        agent_registry.register_agent(
            agent_id=self.agent_id,
            instance_id=instance_id,
            hostname=hostname,
            process_generation=generation,
        )

        print(
            "[SUPERVISOR] "
            f"{self.agent_id} registered: "
            f"instance_id={instance_id}, "
            f"generation={generation}, "
            f"hostname={hostname}"
        )

    # ========================================================
    # FAILURE ACCOUNTING
    # ========================================================

    def record_failure(
        self,
        reason: str,
    ) -> None:

        self.consecutive_failures += 1

        print(
            "[SUPERVISOR] "
            f"{self.agent_id} recovery failure "
            f"{self.consecutive_failures}/"
            f"{MAX_CONSECUTIVE_FAILURES} "
            f"reason={reason}"
        )

    def reset_failures_if_healthy(self) -> None:

        if self.healthy_since is None:
            return

        now = (
            asyncio
            .get_running_loop()
            .time()
        )

        healthy_duration = (
            now - self.healthy_since
        )

        if (
            healthy_duration
            >= HEALTHY_RESET_SECONDS
            and self.consecutive_failures > 0
        ):

            print(
                "[SUPERVISOR] "
                f"{self.agent_id} remained healthy "
                f"for {HEALTHY_RESET_SECONDS:.0f}s. "
                "Resetting recovery failure counter."
            )

            self.consecutive_failures = 0

    def can_restart(self) -> bool:
        return (
            self.consecutive_failures
            < MAX_CONSECUTIVE_FAILURES
        )

    def get_backoff_delay(self) -> float:

        exponent = max(
            0,
            self.consecutive_failures - 1,
        )

        delay = (
            RESTART_DELAY
            * (2 ** exponent)
        )

        return min(
            delay,
            MAX_BACKOFF_SECONDS,
        )

    # ========================================================
    # FAILURE CLAIMS
    # ========================================================

    def _claim_process_failure(
        self,
        generation: int,
    ) -> bool:
        """
        Claim process-failure handling for one generation.
        """

        if (
            self.process_failure_handled_generation
            == generation
        ):
            return False

        self.process_failure_handled_generation = (
            generation
        )

        return True

    def _claim_heartbeat_failure(
        self,
        generation: int,
    ) -> bool:
        """
        Claim heartbeat-failure handling for one generation.
        """

        if (
            self.heartbeat_failure_handled_generation
            == generation
        ):
            return False

        self.heartbeat_failure_handled_generation = (
            generation
        )

        return True

    # ========================================================
    # RECOVERY REQUEST
    # ========================================================

    def request_recovery(
        self,
        reason: str,
    ) -> None:

        if self.intentional_stop:
            return

        existing = self.recovery_task

        if (
            existing is not None
            and not existing.done()
        ):

            print(
                "[SUPERVISOR] "
                f"{self.agent_id} recovery already "
                "scheduled/in progress. "
                f"Ignoring duplicate trigger: {reason}"
            )

            return

        task = asyncio.create_task(
            self.recover(
                reason=reason,
            ),
            name=(
                f"recovery-"
                f"{self.agent_id}"
            ),
        )

        self.recovery_task = task

        def _recovery_done(
            completed_task: asyncio.Task,
        ) -> None:

            if (
                self.recovery_task
                is completed_task
            ):
                self.recovery_task = None

            try:
                completed_task.result()

            except asyncio.CancelledError:
                pass

            except Exception as error:
                print(
                    "[SUPERVISOR] "
                    f"Recovery task failed for "
                    f"{self.agent_id}: "
                    f"{type(error).__name__}: "
                    f"{error}"
                )

        task.add_done_callback(
            _recovery_done
        )

    # ========================================================
    # START
    # ========================================================

    async def start(self) -> bool:

        async with self.restart_lock:
            return await self._start_without_lock()

    # ========================================================
    # INTERNAL START
    # ========================================================

    async def _start_without_lock(
        self,
    ) -> bool:

        if self.intentional_stop:
            return False

        # ----------------------------------------------------
        # Existing process
        # ----------------------------------------------------

        if self.process is not None:

            if self.process.returncode is None:
                self.running = True
                return True

            self.process = None

        # ----------------------------------------------------
        # Validate script
        # ----------------------------------------------------

        if not self.script_path.exists():

            print(
                "[SUPERVISOR] ERROR: "
                f"Script does not exist: "
                f"{self.script_path}"
            )

            self.process = None
            self.running = False
            self.started_at = None
            self.started_at_wallclock = None
            self.healthy_since = None

            agent_registry.mark_dead(
                self.agent_id
            )

            return False

        # ----------------------------------------------------
        # New generation
        # ----------------------------------------------------

        self.process_generation += 1

        generation = self.process_generation

        # ----------------------------------------------------
        # Reset generation-specific state
        # ----------------------------------------------------

        self.instance_id = None

        self.first_heartbeat_received = False

        self.heartbeat_timeout_triggered = False

        self.heartbeat_identity_invalid_since = None

        self.process_failure_handled_generation = None
        self.heartbeat_failure_handled_generation = None

        # ----------------------------------------------------
        # Register generation BEFORE spawning
        # ----------------------------------------------------

        self._register_generation(
            generation
        )

        assert self.instance_id is not None

        # ----------------------------------------------------
        # Lifecycle state
        # ----------------------------------------------------

        self.intentional_stop = False
        self.stopping_for_recovery = False
        self.running = True

        loop = asyncio.get_running_loop()

        self.started_at = loop.time()

        self.started_at_wallclock = (
            datetime.now(timezone.utc)
        )

        self.healthy_since = None

        agent_registry.mark_starting(
            self.agent_id
        )

        print(
            "[SUPERVISOR] "
            f"Starting {self.agent_id} "
            f"(generation={generation}, "
            f"instance_id={self.instance_id})"
        )

        # ----------------------------------------------------
        # Child environment
        # ----------------------------------------------------

        env = os.environ.copy()

        existing_pythonpath = env.get(
            "PYTHONPATH",
            "",
        )

        if existing_pythonpath:
            env["PYTHONPATH"] = (
                f"{PROJECT_ROOT}"
                f"{os.pathsep}"
                f"{existing_pythonpath}"
            )
        else:
            env["PYTHONPATH"] = str(
                PROJECT_ROOT
            )

        env["PYTHONUNBUFFERED"] = "1"

        # ----------------------------------------------------
        # Process identity
        # ----------------------------------------------------

        env["AGENT_ID"] = self.agent_id

        env["AGENT_PROCESS_GENERATION"] = (
            str(generation)
        )

        env["AGENT_INSTANCE_ID"] = (
            self.instance_id
        )

        # ----------------------------------------------------
        # Camera configuration
        # ----------------------------------------------------

        if self.camera_id is not None:

            env["CAMERA_ID"] = (
                self.camera_id
            )

            if self.camera_source is not None:
                env["CAMERA_SOURCE"] = str(
                    self.camera_source
                )

            if self.camera_name is not None:
                env["CAMERA_NAME"] = str(
                    self.camera_name
                )

            if self.camera_location is not None:
                env["CAMERA_LOCATION"] = str(
                    self.camera_location
                )

        else:

            env.pop(
                "CAMERA_ID",
                None,
            )

            env.pop(
                "CAMERA_SOURCE",
                None,
            )

            env.pop(
                "CAMERA_NAME",
                None,
            )

            env.pop(
                "CAMERA_LOCATION",
                None,
            )

        # ----------------------------------------------------
        # Detection configuration
        # ----------------------------------------------------

        if self.config.name == "detection":

            if self.config.stream_name is not None:

                env["DETECTION_OUTPUT_STREAM"] = (
                    self.config.stream_name
                )

        # ----------------------------------------------------
        # Tracker configuration
        # ----------------------------------------------------

        elif self.config.name == "tracker":

            env["TRACKER_CONSUMER"] = (
                self.agent_id
            )

            if self.config.stream_name is not None:

                env["TRACKER_INPUT_STREAM"] = (
                    self.config.stream_name
                )

            if self.config.consumer_group is not None:

                env["TRACKER_GROUP"] = (
                    self.config.consumer_group
                )

        # ----------------------------------------------------
        # Heartbeat failure test
        # ----------------------------------------------------

        heartbeat_test_target = os.getenv(
            "TEST_HEARTBEAT_FAILURE_AGENT",
            "",
        ).strip()

        if (
            heartbeat_test_target
            and heartbeat_test_target
            == self.agent_id
        ):

            env[
                "TEST_HEARTBEAT_FAILURE_AGENT"
            ] = self.agent_id

            print(
                "[SUPERVISOR] "
                "HEARTBEAT FAILURE TEST ENABLED "
                f"for {self.agent_id}"
            )

        else:

            env.pop(
                "TEST_HEARTBEAT_FAILURE_AGENT",
                None,
            )

        # ----------------------------------------------------
        # Spawn subprocess
        # ----------------------------------------------------

        try:

            process = (
                await asyncio.create_subprocess_exec(
                    PYTHON_EXECUTABLE,
                    "-m",
                    self._module_name(),
                    cwd=str(PROJECT_ROOT),
                    env=env,
                    stdin=None,
                    stdout=None,
                    stderr=None,
                )
            )

        except asyncio.CancelledError:

            self.process = None
            self.running = False

            agent_registry.mark_dead(
                self.agent_id
            )

            raise

        except Exception as error:

            self.process = None
            self.running = False

            self.started_at = None
            self.started_at_wallclock = None
            self.healthy_since = None

            agent_registry.mark_dead(
                self.agent_id
            )

            print(
                "[SUPERVISOR] "
                f"FAILED TO START "
                f"{self.agent_id}: "
                f"{type(error).__name__}: "
                f"{error!r}"
            )

            return False

        # ----------------------------------------------------
        # Publish process
        # ----------------------------------------------------

        self.process = process

        print(
            "[SUPERVISOR] "
            f"{self.agent_id} started "
            f"(PID={process.pid}, "
            f"generation={generation}, "
            f"instance_id={self.instance_id})"
        )

        # ----------------------------------------------------
        # Process monitor for THIS generation
        # ----------------------------------------------------

        self._start_process_monitor(
            process,
            generation,
        )

        return True

    # ========================================================
    # MODULE NAME
    # ========================================================

    def _module_name(self) -> str:

        relative = Path(
            self.config.script
        )

        without_suffix = relative.with_suffix("")

        return ".".join(
            without_suffix.parts
        )

    # ========================================================
    # PROCESS MONITOR
    # ========================================================

    def _start_process_monitor(
        self,
        process: asyncio.subprocess.Process,
        generation: int,
    ) -> None:

        existing = self.process_monitor_task

        if (
            existing is not None
            and not existing.done()
        ):

            return

        task = asyncio.create_task(
            self.monitor_process(
                process=process,
                generation=generation,
            ),
            name=(
                f"monitor-process-"
                f"{self.agent_id}-"
                f"g{generation}"
            ),
        )

        self.process_monitor_task = task

        def _monitor_done(
            completed_task: asyncio.Task,
        ) -> None:

            if (
                self.process_monitor_task
                is completed_task
            ):
                self.process_monitor_task = None

            try:
                completed_task.result()

            except asyncio.CancelledError:
                pass

            except Exception as error:

                print(
                    "[SUPERVISOR] "
                    f"Process monitor failed for "
                    f"{self.agent_id}: "
                    f"{type(error).__name__}: "
                    f"{error}"
                )

        task.add_done_callback(
            _monitor_done
        )

    # ========================================================
    # ENSURE PROCESS MONITOR
    # ========================================================

    def ensure_process_monitor(self) -> None:
        """
        Recreate a process monitor if the monitoring task itself
        unexpectedly terminated while the supervised process is
        still alive.
        """

        process = self.process

        if process is None:
            return

        if process.returncode is not None:
            return

        if self.intentional_stop:
            return

        existing = self.process_monitor_task

        if (
            existing is not None
            and not existing.done()
        ):
            return

        generation = self.process_generation

        print(
            "[SUPERVISOR] "
            f"Process monitor missing for "
            f"{self.agent_id}. "
            f"Recreating monitor for generation "
            f"{generation}."
        )

        self._start_process_monitor(
            process,
            generation,
        )

    # ========================================================
    # STOP PROCESS
    # ========================================================

    async def _stop_process(
        self,
        process: Optional[
            asyncio.subprocess.Process
        ],
    ) -> None:

        if process is None:
            return

        if process.returncode is not None:
            return

        try:

            process.terminate()

            await asyncio.wait_for(
                process.wait(),
                timeout=PROCESS_STOP_TIMEOUT,
            )

            return

        except ProcessLookupError:
            return

        except asyncio.TimeoutError:

            print(
                "[SUPERVISOR] "
                f"{self.agent_id} did not terminate "
                "gracefully. Killing."
            )

        except Exception as error:

            print(
                "[SUPERVISOR] "
                f"Terminate error for "
                f"{self.agent_id}: "
                f"{type(error).__name__}: "
                f"{error}"
            )

        # ----------------------------------------------------
        # Hard kill
        # ----------------------------------------------------

        try:

            process.kill()

            await asyncio.wait_for(
                process.wait(),
                timeout=PROCESS_STOP_TIMEOUT,
            )

        except ProcessLookupError:
            pass

        except asyncio.TimeoutError:

            print(
                "[SUPERVISOR] "
                f"Unable to reap process for "
                f"{self.agent_id} within "
                f"{PROCESS_STOP_TIMEOUT:.1f}s."
            )

        except Exception as error:

            print(
                "[SUPERVISOR] "
                f"Kill error for "
                f"{self.agent_id}: "
                f"{type(error).__name__}: "
                f"{error}"
            )

    # ========================================================
    # STOP
    # ========================================================

    async def stop(self) -> None:

        self.intentional_stop = True
        self.running = False
        self.stopping_for_recovery = False
        self.recovery_in_progress = False

        # ----------------------------------------------------
        # Cancel recovery task
        # ----------------------------------------------------

        recovery_task = self.recovery_task

        if (
            recovery_task is not None
            and not recovery_task.done()
            and recovery_task
            is not asyncio.current_task()
        ):

            recovery_task.cancel()

            try:
                await recovery_task

            except asyncio.CancelledError:
                pass

            except Exception as error:

                print(
                    "[SUPERVISOR] "
                    f"Recovery shutdown error for "
                    f"{self.agent_id}: "
                    f"{error}"
                )

        self.recovery_task = None

        # ----------------------------------------------------
        # Cancel health monitor
        # ----------------------------------------------------

        health_task = self.health_monitor_task

        if (
            health_task is not None
            and not health_task.done()
            and health_task
            is not asyncio.current_task()
        ):

            health_task.cancel()

            try:
                await health_task

            except asyncio.CancelledError:
                pass

            except Exception as error:

                print(
                    "[SUPERVISOR] "
                    f"Health monitor shutdown error "
                    f"for {self.agent_id}: "
                    f"{error}"
                )

        self.health_monitor_task = None

        # ----------------------------------------------------
        # Cancel process monitor
        # ----------------------------------------------------

        monitor_task = self.process_monitor_task

        if (
            monitor_task is not None
            and not monitor_task.done()
            and monitor_task
            is not asyncio.current_task()
        ):

            monitor_task.cancel()

            try:
                await monitor_task

            except asyncio.CancelledError:
                pass

            except Exception as error:

                print(
                    "[SUPERVISOR] "
                    f"Process monitor shutdown error "
                    f"for {self.agent_id}: "
                    f"{error}"
                )

        self.process_monitor_task = None

        # ----------------------------------------------------
        # Stop subprocess
        # ----------------------------------------------------

        process = self.process

        await self._stop_process(
            process
        )

        # ----------------------------------------------------
        # Clear process state
        # ----------------------------------------------------

        if self.process is process:
            self.process = None

        self.started_at = None
        self.started_at_wallclock = None
        self.healthy_since = None

        self.first_heartbeat_received = False
        self.heartbeat_timeout_triggered = False
        self.heartbeat_identity_invalid_since = None

        agent_registry.mark_dead(
            self.agent_id
        )

    # ========================================================
    # PROCESS EXIT HANDLER
    # ========================================================

    async def handle_process_exit(
        self,
        process: asyncio.subprocess.Process,
        generation: int,
        return_code: int,
    ) -> None:

        # ----------------------------------------------------
        # Stale generation protection
        # ----------------------------------------------------

        if (
            self.process is not process
            or self.process_generation != generation
        ):

            print(
                "[SUPERVISOR] "
                f"{self.agent_id} stale process exit "
                "ignored. "
                f"generation={generation}, "
                f"current_generation="
                f"{self.process_generation}"
            )

            return

        # ----------------------------------------------------
        # Intentional operator shutdown
        # ----------------------------------------------------

        if self.intentional_stop:

            if self.process is process:
                self.process = None

            return

        # ----------------------------------------------------
        # Intentional recovery stop
        # ----------------------------------------------------

        if self.stopping_for_recovery:
            return

        # ----------------------------------------------------
        # Duplicate failure protection
        # ----------------------------------------------------

        if not self._claim_process_failure(
            generation
        ):

            print(
                "[SUPERVISOR] "
                f"{self.agent_id} process failure "
                "already handled for generation "
                f"{generation}."
            )

            return

        # ----------------------------------------------------
        # Process failure
        # ----------------------------------------------------

        print(
            "[SUPERVISOR] "
            f"{self.agent_id} exited "
            f"(code={return_code}, "
            f"generation={generation})"
        )

        if self.process is process:
            self.process = None

        self.running = True

        agent_registry.mark_dead(
            self.agent_id
        )

        self.record_failure(
            reason=(
                f"process_exit:"
                f"{return_code}"
            )
        )

        self.request_recovery(
            reason="process_exit"
        )

    # ========================================================
    # RECOVERY
    # ========================================================

    async def recover(
        self,
        reason: str,
    ) -> None:

        async with self.restart_lock:

            if self.intentional_stop:
                return

            if self.recovery_in_progress:
                return

            self.recovery_in_progress = True

            try:

                while not self.intentional_stop:

                    # ------------------------------------------------
                    # Restart limit
                    # ------------------------------------------------

                    if not self.can_restart():

                        self.running = False
                        self.process = None

                        agent_registry.mark_dead(
                            self.agent_id
                        )

                        print(
                            "[SUPERVISOR] "
                            f"Restart limit reached for "
                            f"{self.agent_id}. "
                            "Automatic recovery stopped."
                        )

                        return

                    # ------------------------------------------------
                    # Backoff
                    # ------------------------------------------------

                    delay = (
                        self.get_backoff_delay()
                    )

                    print(
                        "[SUPERVISOR] "
                        f"Recovering {self.agent_id} "
                        f"(reason={reason}, "
                        f"backoff={delay:.1f}s, "
                        f"failures="
                        f"{self.consecutive_failures})"
                    )

                    agent_registry.mark_recovering(
                        self.agent_id
                    )

                    # ------------------------------------------------
                    # Capture current generation
                    # ------------------------------------------------

                    process = self.process
                    generation = (
                        self.process_generation
                    )

                    # ------------------------------------------------
                    # Mark recovery BEFORE stopping process.
                    # ------------------------------------------------

                    self.stopping_for_recovery = True

                    # ------------------------------------------------
                    # Stop old generation
                    # ------------------------------------------------

                    await self._stop_process(
                        process
                    )

                    # ------------------------------------------------
                    # Clear only if still current.
                    # ------------------------------------------------

                    if (
                        self.process is process
                        and self.process_generation
                        == generation
                    ):
                        self.process = None

                    self.started_at = None
                    self.started_at_wallclock = None
                    self.healthy_since = None

                    self.first_heartbeat_received = (
                        False
                    )

                    self.heartbeat_timeout_triggered = (
                        False
                    )

                    self.heartbeat_identity_invalid_since = (
                        None
                    )

                    # ------------------------------------------------
                    # Wait before replacement
                    # ------------------------------------------------

                    try:

                        await asyncio.sleep(
                            delay
                        )

                    except asyncio.CancelledError:
                        raise

                    if self.intentional_stop:
                        return

                    # ------------------------------------------------
                    # Replacement generation begins here.
                    # ------------------------------------------------

                    self.stopping_for_recovery = False
                    self.running = True

                    started = (
                        await self._start_without_lock()
                    )

                    if started:

                        print(
                            "[SUPERVISOR] "
                            f"{self.agent_id} recovery "
                            "started successfully."
                        )

                        return

                    # ------------------------------------------------
                    # Replacement startup failed.
                    # ------------------------------------------------

                    self.record_failure(
                        reason=(
                            "recovery_startup_failure"
                        )
                    )

                    agent_registry.mark_dead(
                        self.agent_id
                    )

                    # Loop continues.

            except asyncio.CancelledError:
                raise

            finally:

                self.stopping_for_recovery = False
                self.recovery_in_progress = False

    # ========================================================
    # PROCESS MONITOR
    # ========================================================

    async def monitor_process(
        self,
        process: asyncio.subprocess.Process,
        generation: int,
    ) -> None:

        try:

            return_code = (
                await process.wait()
            )

        except asyncio.CancelledError:
            raise

        except Exception as error:

            print(
                "[SUPERVISOR] "
                f"Process monitor error for "
                f"{self.agent_id}: "
                f"{type(error).__name__}: "
                f"{error}"
            )

            return

        # ----------------------------------------------------
        # Ignore stale generation
        # ----------------------------------------------------

        if (
            self.process is not process
            or self.process_generation != generation
        ):

            print(
                "[SUPERVISOR] "
                f"{self.agent_id} process monitor "
                "detected stale generation. "
                f"generation={generation}, "
                f"current={self.process_generation}"
            )

            return

        # ----------------------------------------------------
        # Operator shutdown
        # ----------------------------------------------------

        if self.intentional_stop:
            return

        # ----------------------------------------------------
        # Recovery intentionally killed process
        # ----------------------------------------------------

        if self.stopping_for_recovery:
            return

        # ----------------------------------------------------
        # Real unexpected failure
        # ----------------------------------------------------

        await self.handle_process_exit(
            process=process,
            generation=generation,
            return_code=return_code,
        )

    # ========================================================
    # HEARTBEAT AGE
    # ========================================================

    def get_heartbeat_age(
        self,
        agent: dict,
    ) -> Optional[float]:

        last_heartbeat = agent.get(
            "last_heartbeat"
        )

        if last_heartbeat is None:
            return None

        try:

            if last_heartbeat.tzinfo is None:

                last_heartbeat = (
                    last_heartbeat.replace(
                        tzinfo=timezone.utc
                    )
                )

            now = datetime.now(
                timezone.utc
            )

            age = (
                now - last_heartbeat
            ).total_seconds()

            return max(
                0.0,
                age,
            )

        except Exception as error:

            print(
                "[SUPERVISOR] "
                f"Heartbeat timestamp error for "
                f"{self.agent_id}: "
                f"{error}"
            )

            return None

    # ========================================================
    # GENERATION-AWARE HEARTBEAT
    # ========================================================

    def heartbeat_belongs_to_current_generation(
        self,
        agent: dict,
    ) -> bool:

        current_instance_id = (
            self.instance_id
        )

        current_generation = (
            self.process_generation
        )

        if current_instance_id is None:
            return False

        registered_instance = (
            agent.get("instance_id")
        )

        registered_generation = (
            agent.get("process_generation")
        )

        # ----------------------------------------------------
        # Instance ID MUST match.
        # ----------------------------------------------------

        if (
            registered_instance
            != current_instance_id
        ):
            return False

        # ----------------------------------------------------
        # Generation MUST also match.
        # ----------------------------------------------------

        if registered_generation is None:
            return False

        try:

            registered_generation = int(
                registered_generation
            )

        except (
            TypeError,
            ValueError,
        ):
            return False

        return (
            registered_generation
            == current_generation
        )

    # ========================================================
    # HEARTBEAT STATE
    # ========================================================

    def check_heartbeat_timeout(
        self,
        agent: dict,
    ) -> str:

        if not self.heartbeat_belongs_to_current_generation(
            agent
        ):
            return "invalid_identity"

        heartbeat_age = (
            self.get_heartbeat_age(
                agent
            )
        )

        if heartbeat_age is None:
            return "missing"

        if heartbeat_age <= HEARTBEAT_TIMEOUT:
            return "healthy"

        return "timeout"

    # ========================================================
    # HEARTBEAT FAILURE HANDLER
    # ========================================================

    def handle_heartbeat_failure(
        self,
        reason: str,
    ) -> None:

        generation = (
            self.process_generation
        )

        if not self._claim_heartbeat_failure(
            generation
        ):

            return

        print(
            "[SUPERVISOR] "
            f"{self.agent_id} heartbeat failure "
            f"claimed for generation={generation}, "
            f"reason={reason}"
        )

        agent_registry.mark_dead(
            self.agent_id
        )

        self.record_failure(
            reason=reason
        )

        self.request_recovery(
            reason=reason
        )

    # ========================================================
    # HEALTH CHECK
    # ========================================================

    async def check_health(self) -> None:

        if not self.running:
            return

        # ----------------------------------------------------
        # Ensure process monitor itself is alive.
        # ----------------------------------------------------

        self.ensure_process_monitor()

        process = self.process

        # ----------------------------------------------------
        # Missing process
        # ----------------------------------------------------

        if process is None:

            if (
                self.recovery_task is not None
                and not self.recovery_task.done()
            ):
                return

            if self.intentional_stop:
                return

            self.request_recovery(
                reason="missing_process"
            )

            return

        # ----------------------------------------------------
        # Process already exited.
        #
        # Process monitor owns process-exit accounting.
        # ----------------------------------------------------

        if process.returncode is not None:
            return

        # ----------------------------------------------------
        # Startup timestamp
        # ----------------------------------------------------

        if self.started_at is None:
            return

        # ----------------------------------------------------
        # Recovery already running
        # ----------------------------------------------------

        if (
            self.recovery_task is not None
            and not self.recovery_task.done()
        ):
            return

        loop = asyncio.get_running_loop()

        now = loop.time()

        age_since_start = (
            now - self.started_at
        )

        # ----------------------------------------------------
        # Registry snapshot
        # ----------------------------------------------------

        agent = (
            agent_registry.get_agent(
                self.agent_id
            )
        )

        # ----------------------------------------------------
        # Missing registry entry
        # ----------------------------------------------------

        if agent is None:

            if (
                age_since_start
                >= STARTUP_GRACE_PERIOD
            ):

                print(
                    "[SUPERVISOR] "
                    f"{self.agent_id} has a live process "
                    "but no registry entry."
                )

                self.handle_heartbeat_failure(
                    reason=(
                        "missing_registry_entry"
                    )
                )

            return

        # ----------------------------------------------------
        # GENERATION / INSTANCE VALIDATION
        #
        # This is intentionally NOT an infinite wait.
        #
        # A stale registry record is tolerated only during
        # startup grace. After grace, a live process without
        # a heartbeat belonging to its current generation is
        # considered unhealthy and is recovered.
        # ----------------------------------------------------

        if not self.heartbeat_belongs_to_current_generation(
            agent
        ):

            if (
                self.heartbeat_identity_invalid_since
                is None
            ):
                self.heartbeat_identity_invalid_since = now

            invalid_for = (
                now
                - self.heartbeat_identity_invalid_since
            )

            if (
                age_since_start
                >= STARTUP_GRACE_PERIOD
                and invalid_for
                >= STARTUP_GRACE_PERIOD
            ):

                print(
                    "[SUPERVISOR] "
                    f"{self.agent_id} current-generation "
                    "heartbeat identity not observed. "
                    f"current_instance="
                    f"{self.instance_id}, "
                    f"registry_instance="
                    f"{agent.get('instance_id')}, "
                    f"current_generation="
                    f"{self.process_generation}, "
                    f"registry_generation="
                    f"{agent.get('process_generation')}, "
                    f"invalid_for="
                    f"{invalid_for:.1f}s"
                )

                self.handle_heartbeat_failure(
                    reason=(
                        "invalid_heartbeat_generation"
                    )
                )

            return

        # ----------------------------------------------------
        # Valid generation observed.
        # ----------------------------------------------------

        self.heartbeat_identity_invalid_since = None

        # ----------------------------------------------------
        # Startup grace period
        # ----------------------------------------------------

        if (
            age_since_start
            < STARTUP_GRACE_PERIOD
        ):
            return

        # ----------------------------------------------------
        # Heartbeat
        # ----------------------------------------------------

        heartbeat_state = (
            self.check_heartbeat_timeout(
                agent
            )
        )

        # ----------------------------------------------------
        # First heartbeat missing
        # ----------------------------------------------------

        if heartbeat_state == "missing":

            if not self.first_heartbeat_received:

                print(
                    "[SUPERVISOR] "
                    "FIRST HEARTBEAT TIMEOUT: "
                    f"{self.agent_id} "
                    f"(startup_age="
                    f"{age_since_start:.1f}s, "
                    f"grace="
                    f"{STARTUP_GRACE_PERIOD:.1f}s, "
                    f"generation="
                    f"{self.process_generation})"
                )

                self.handle_heartbeat_failure(
                    reason=(
                        "missing_first_heartbeat"
                    )
                )

            return

        # ----------------------------------------------------
        # Valid heartbeat received
        # ----------------------------------------------------

        self.first_heartbeat_received = True

        # ----------------------------------------------------
        # Heartbeat timeout
        # ----------------------------------------------------

        if heartbeat_state == "timeout":

            heartbeat_age = (
                self.get_heartbeat_age(
                    agent
                )
            )

            heartbeat_age_text = (
                f"{heartbeat_age:.1f}s"
                if heartbeat_age is not None
                else "unknown"
            )

            print(
                "[SUPERVISOR] "
                "HEARTBEAT TIMEOUT: "
                f"{self.agent_id} "
                f"(age="
                f"{heartbeat_age_text}, "
                f"timeout="
                f"{HEARTBEAT_TIMEOUT:.1f}s, "
                f"generation="
                f"{self.process_generation})"
            )

            self.handle_heartbeat_failure(
                reason="heartbeat_timeout"
            )

            return

        # ----------------------------------------------------
        # Registry DEAD
        # ----------------------------------------------------

        if agent.get("status") == "DEAD":

            self.handle_heartbeat_failure(
                reason="registry_dead"
            )

            return

        # ----------------------------------------------------
        # Starting / recovering
        # ----------------------------------------------------

        if agent.get("status") in (
            "STARTING",
            "RECOVERING",
        ):
            return

        # ----------------------------------------------------
        # Healthy
        # ----------------------------------------------------

        if agent.get("status") == "ALIVE":

            self.heartbeat_timeout_triggered = (
                False
            )

            if self.healthy_since is None:
                self.healthy_since = now

            self.reset_failures_if_healthy()

            return

        # ----------------------------------------------------
        # Unknown state
        # ----------------------------------------------------

        print(
            "[SUPERVISOR] "
            f"{self.agent_id} unexpected "
            f"registry status: "
            f"{agent.get('status')}"
        )

    # ========================================================
    # HEALTH LOOP
    # ========================================================

    async def health_loop(self) -> None:

        try:

            while self.running:

                try:

                    await self.check_health()

                except asyncio.CancelledError:
                    raise

                except Exception as error:

                    print(
                        "[SUPERVISOR] "
                        f"Health check error for "
                        f"{self.agent_id}: "
                        f"{type(error).__name__}: "
                        f"{error}"
                    )

                await asyncio.sleep(
                    HEALTH_CHECK_INTERVAL
                )

        except asyncio.CancelledError:
            raise


# ============================================================
# AGENT SUPERVISOR
# ============================================================


class AgentSupervisor:
    """
    Supervises all configured production agents.

    Every SupervisedAgent is an independent failure boundary.

    The supervisor also watches its own monitoring tasks so that
    a failed health monitor does not silently remove monitoring
    from an otherwise healthy agent.
    """

    def __init__(self) -> None:

        self.camera_registry = (
            CameraRegistry.from_environment()
        )

        self.agents: dict[
            str,
            SupervisedAgent,
        ] = {}

        self.running = False

        self.health_tasks: list[
            asyncio.Task
        ] = []

        self.monitoring_supervisor_task: Optional[
            asyncio.Task
        ] = None

        self._build_agent_configuration()

    # ========================================================
    # BUILD CONFIGURATION
    # ========================================================

    def _build_agent_configuration(self) -> None:

        enabled_cameras = (
            self.camera_registry.get_enabled()
        )

        if not enabled_cameras:

            print(
                "[SUPERVISOR] WARNING: "
                "No enabled cameras configured."
            )

        # ----------------------------------------------------
        # Camera-specific agents
        # ----------------------------------------------------

        for camera in enabled_cameras:

            camera_component = (
                _safe_agent_id_component(
                    camera.camera_id
                )
            )

            # ------------------------------------------------
            # Detector
            # ------------------------------------------------

            detector_agent_id = (
                f"person-detector-"
                f"{camera_component}"
            )

            detection_config = AgentProcessConfig(
                name="detection",
                agent_id=detector_agent_id,
                script="agents/detection/main.py",
                camera_id=camera.camera_id,
                camera_source=str(
                    camera.source
                ),
                camera_name=camera.name,
                camera_location=camera.location,
                stream_name=(
                    f"events.detection."
                    f"{camera_component}"
                ),
            )

            if detector_agent_id in self.agents:

                raise ValueError(
                    "Duplicate supervised agent ID "
                    f"generated for camera "
                    f"{camera.camera_id}: "
                    f"{detector_agent_id}"
                )

            self.agents[
                detector_agent_id
            ] = SupervisedAgent(
                detection_config
            )

            # ------------------------------------------------
            # Tracker
            # ------------------------------------------------

            tracker_agent_id = (
                f"tracker-"
                f"{camera_component}"
            )

            tracker_config = AgentProcessConfig(
                name="tracker",
                agent_id=tracker_agent_id,
                script="agents/tracker/main.py",
                camera_id=camera.camera_id,
                stream_name=(
                    f"events.detection."
                    f"{camera_component}"
                ),
                consumer_group=(
                    f"tracker-workers."
                    f"{camera_component}"
                ),
            )

            if tracker_agent_id in self.agents:

                raise ValueError(
                    "Duplicate supervised agent ID "
                    f"generated for camera "
                    f"{camera.camera_id}: "
                    f"{tracker_agent_id}"
                )

            self.agents[
                tracker_agent_id
            ] = SupervisedAgent(
                tracker_config
            )

        # ----------------------------------------------------
        # Global agents
        # ----------------------------------------------------

        for config in GLOBAL_PRODUCTION_AGENTS:

            if config.agent_id in self.agents:

                raise ValueError(
                    "Duplicate supervised agent ID: "
                    f"{config.agent_id}"
                )

            self.agents[
                config.agent_id
            ] = SupervisedAgent(
                config
            )

    # ========================================================
    # START ONE AGENT + HEALTH MONITOR
    # ========================================================

    async def _start_agent_with_monitors(
        self,
        agent: SupervisedAgent,
    ) -> None:

        try:

            started = await agent.start()

            if not started:

                print(
                    "[SUPERVISOR] "
                    f"{agent.agent_id} failed "
                    "initial startup. "
                    "Scheduling automatic recovery."
                )

                agent.running = True

                agent.record_failure(
                    reason="initial_startup_failure"
                )

                agent.request_recovery(
                    reason="initial_startup_failure"
                )

        except asyncio.CancelledError:
            raise

        except Exception as error:

            print(
                "[SUPERVISOR] "
                f"Failed to start "
                f"{agent.agent_id}: "
                f"{type(error).__name__}: "
                f"{error}"
            )

            agent.running = True

            agent.record_failure(
                reason="initial_startup_exception"
            )

            agent.request_recovery(
                reason="initial_startup_exception"
            )

        # ----------------------------------------------------
        # One health monitor for THIS agent.
        # ----------------------------------------------------

        self._ensure_health_monitor(
            agent
        )

    # ========================================================
    # ENSURE HEALTH MONITOR
    # ========================================================

    def _ensure_health_monitor(
        self,
        agent: SupervisedAgent,
    ) -> None:
        """
        Create the health monitor if it is missing.

        If the existing monitor is still alive, nothing happens.
        """

        if not self.running:
            return

        existing = agent.health_monitor_task

        if (
            existing is not None
            and not existing.done()
        ):
            return

        task = asyncio.create_task(
            agent.health_loop(),
            name=(
                f"health-monitor-"
                f"{agent.agent_id}"
            ),
        )

        agent.health_monitor_task = task

        if task not in self.health_tasks:
            self.health_tasks.append(
                task
            )

        def _health_done(
            completed_task: asyncio.Task,
        ) -> None:

            try:

                completed_task.result()

            except asyncio.CancelledError:
                return

            except Exception as error:

                print(
                    "[SUPERVISOR] "
                    f"Health monitor failed for "
                    f"{agent.agent_id}: "
                    f"{type(error).__name__}: "
                    f"{error}"
                )

        task.add_done_callback(
            _health_done
        )

    # ========================================================
    # MONITORING TASK SUPERVISOR
    # ========================================================

    async def _monitor_monitoring_tasks(self) -> None:
        """
        Protect the monitoring layer itself.

        This task does NOT recover application agents directly.

        It only ensures that:

            health monitor
            process monitor

        remain alive.

        Each failed monitor is recreated only for its own
        SupervisedAgent.
        """

        try:

            while self.running:

                for agent in self.agents.values():

                    if not self.running:
                        break

                    try:

                        # ------------------------------------------------
                        # Health monitor
                        # ------------------------------------------------

                        self._ensure_health_monitor(
                            agent
                        )

                        # ------------------------------------------------
                        # Process monitor
                        # ------------------------------------------------

                        agent.ensure_process_monitor()

                    except Exception as error:

                        print(
                            "[SUPERVISOR] "
                            f"Monitoring-task recovery error "
                            f"for {agent.agent_id}: "
                            f"{type(error).__name__}: "
                            f"{error}"
                        )

                await asyncio.sleep(
                    MONITORING_TASK_CHECK_INTERVAL
                )

        except asyncio.CancelledError:
            raise

    # ========================================================
    # START MONITORING SUPERVISOR
    # ========================================================

    def _start_monitoring_supervisor(self) -> None:

        existing = (
            self.monitoring_supervisor_task
        )

        if (
            existing is not None
            and not existing.done()
        ):
            return

        task = asyncio.create_task(
            self._monitor_monitoring_tasks(),
            name="supervisor-monitoring-supervisor",
        )

        self.monitoring_supervisor_task = task

        def _monitoring_supervisor_done(
            completed_task: asyncio.Task,
        ) -> None:

            if (
                self.monitoring_supervisor_task
                is completed_task
            ):
                self.monitoring_supervisor_task = None

            try:
                completed_task.result()

            except asyncio.CancelledError:
                pass

            except Exception as error:

                print(
                    "[SUPERVISOR] "
                    "Monitoring supervisor itself failed: "
                    f"{type(error).__name__}: "
                    f"{error}"
                )

                # If the monitoring supervisor itself dies,
                # recreate it while AgentSupervisor is alive.
                if self.running:

                    try:
                        self._start_monitoring_supervisor()
                    except Exception as restart_error:
                        print(
                            "[SUPERVISOR] "
                            "Unable to recreate monitoring "
                            "supervisor: "
                            f"{type(restart_error).__name__}: "
                            f"{restart_error}"
                        )

        task.add_done_callback(
            _monitoring_supervisor_done
        )

    # ========================================================
    # START ALL
    # ========================================================

    async def start_all(self) -> None:

        if self.running:

            print(
                "[SUPERVISOR] "
                "Supervisor is already running."
            )

            return

        print("=" * 70)
        print("AGENT SUPERVISOR")
        print("=" * 70)

        print(
            "[SUPERVISOR] "
            f"Python: {PYTHON_EXECUTABLE}"
        )

        print(
            "[SUPERVISOR] "
            f"Project root: {PROJECT_ROOT}"
        )

        print(
            "[SUPERVISOR] "
            f"Production agents: "
            f"{len(self.agents)}"
        )

        # ----------------------------------------------------
        # Cameras
        # ----------------------------------------------------

        all_cameras = (
            self.camera_registry.get_all()
        )

        enabled_cameras = (
            self.camera_registry.get_enabled()
        )

        print(
            "[SUPERVISOR] "
            f"Configured cameras: "
            f"{len(all_cameras)}"
        )

        print(
            "[SUPERVISOR] "
            f"Enabled cameras: "
            f"{len(enabled_cameras)}"
        )

        for camera in enabled_cameras:

            camera_component = (
                _safe_agent_id_component(
                    camera.camera_id
                )
            )

            detector_agent_id = (
                f"person-detector-"
                f"{camera_component}"
            )

            tracker_agent_id = (
                f"tracker-"
                f"{camera_component}"
            )

            print(
                "[SUPERVISOR] "
                f"Camera: "
                f"{camera.camera_id} | "
                f"name={camera.name} | "
                f"source={camera.source} | "
                f"location={camera.location}"
            )

            print(
                "[SUPERVISOR] "
                f"Camera affinity: "
                f"{camera.camera_id} -> "
                f"{detector_agent_id}, "
                f"{tracker_agent_id}"
            )

        # ----------------------------------------------------
        # Health configuration
        # ----------------------------------------------------

        print(
            "[SUPERVISOR] "
            f"Heartbeat timeout: "
            f"{HEARTBEAT_TIMEOUT:.1f}s"
        )

        print(
            "[SUPERVISOR] "
            f"Startup grace period: "
            f"{STARTUP_GRACE_PERIOD:.1f}s"
        )

        print(
            "[SUPERVISOR] "
            f"Max consecutive failures: "
            f"{MAX_CONSECUTIVE_FAILURES}"
        )

        print(
            "[SUPERVISOR] "
            f"Healthy reset period: "
            f"{HEALTHY_RESET_SECONDS:.1f}s"
        )

        print(
            "[SUPERVISOR] "
            f"Monitoring task check interval: "
            f"{MONITORING_TASK_CHECK_INTERVAL:.1f}s"
        )

        heartbeat_test_target = os.getenv(
            "TEST_HEARTBEAT_FAILURE_AGENT",
            "",
        ).strip()

        if heartbeat_test_target:

            print(
                "[SUPERVISOR] "
                "Heartbeat failure test target: "
                f"{heartbeat_test_target}"
            )

        print("=" * 70)

        self.running = True

        # ----------------------------------------------------
        # Start independently.
        # ----------------------------------------------------

        agents = list(
            self.agents.values()
        )

        for index, agent in enumerate(
            agents
        ):

            await self._start_agent_with_monitors(
                agent
            )

            if index < len(agents) - 1:

                await asyncio.sleep(
                    STARTUP_DELAY
                )

        # ----------------------------------------------------
        # Start monitoring-task supervisor AFTER all
        # individual monitors exist.
        # ----------------------------------------------------

        self._start_monitoring_supervisor()

        print(
            "[SUPERVISOR] "
            "All agent health monitors started."
        )

        print(
            "[SUPERVISOR] "
            "Monitoring-task supervisor started."
        )

    # ========================================================
    # STOP ALL
    # ========================================================

    async def stop_all(self) -> None:

        if (
            not self.running
            and not self.health_tasks
            and self.monitoring_supervisor_task is None
        ):
            return

        print(
            "[SUPERVISOR] "
            "Shutdown requested."
        )

        self.running = False

        # ----------------------------------------------------
        # Tell every agent shutdown is intentional BEFORE
        # cancelling/terminating anything.
        # ----------------------------------------------------

        for agent in self.agents.values():

            agent.running = False
            agent.intentional_stop = True
            agent.stopping_for_recovery = False

        # ----------------------------------------------------
        # Cancel monitoring supervisor.
        # ----------------------------------------------------

        monitoring_supervisor_task = (
            self.monitoring_supervisor_task
        )

        if (
            monitoring_supervisor_task is not None
            and not monitoring_supervisor_task.done()
        ):

            monitoring_supervisor_task.cancel()

            try:

                await monitoring_supervisor_task

            except asyncio.CancelledError:
                pass

            except Exception as error:

                print(
                    "[SUPERVISOR] "
                    "Monitoring supervisor shutdown "
                    f"error: {error}"
                )

        self.monitoring_supervisor_task = None

        # ----------------------------------------------------
        # Cancel health monitors.
        # ----------------------------------------------------

        health_tasks = list(
            self.health_tasks
        )

        for task in health_tasks:

            if not task.done():
                task.cancel()

        if health_tasks:

            await asyncio.gather(
                *health_tasks,
                return_exceptions=True,
            )

        self.health_tasks.clear()

        # ----------------------------------------------------
        # Stop every agent independently.
        # ----------------------------------------------------

        shutdown_tasks = [
            self._stop_agent_safely(
                agent
            )
            for agent in self.agents.values()
        ]

        if shutdown_tasks:

            await asyncio.gather(
                *shutdown_tasks,
                return_exceptions=True,
            )

        print(
            "[SUPERVISOR] "
            "All agents stopped."
        )

    # ========================================================
    # SAFE INDIVIDUAL SHUTDOWN
    # ========================================================

    async def _stop_agent_safely(
        self,
        agent: SupervisedAgent,
    ) -> None:

        try:

            await agent.stop()

        except asyncio.CancelledError:
            raise

        except Exception as error:

            print(
                "[SUPERVISOR] "
                f"Shutdown error for "
                f"{agent.agent_id}: "
                f"{type(error).__name__}: "
                f"{error}"
            )


# ============================================================
# STANDALONE MAIN
# ============================================================


async def main() -> None:

    supervisor = AgentSupervisor()

    try:

        await supervisor.start_all()

        while supervisor.running:

            await asyncio.sleep(1)

    except asyncio.CancelledError:
        raise

    finally:

        await supervisor.stop_all()


# ============================================================
# ENTRY POINT
# ============================================================


if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:

        print(
            "\n[SUPERVISOR] "
            "Stopped by operator."
        )