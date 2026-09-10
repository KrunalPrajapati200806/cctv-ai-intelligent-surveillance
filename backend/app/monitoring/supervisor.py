# # """
# # Per-agent process supervisor.

# # Responsibilities
# # ----------------
# # - Start production agents as isolated subprocesses.
# # - Create one camera-bound detection worker per enabled camera.
# # - Provide camera and agent identity configuration to subprocesses.
# # - Monitor process lifetime.
# # - Monitor heartbeat health.
# # - Recover only the failed agent.
# # - Prevent concurrent recovery of the same agent.
# # - Apply exponential restart backoff.
# # - Limit repeated restart failures.
# # - Respect startup grace periods.
# # - Automatically retry failed startup/recovery.
# # - Keep one agent failure isolated from all other agents.

# # Multi-camera model
# # ------------------
# # For every enabled camera:

# #     CAM01 -> person-detector-CAM01
# #     CAM02 -> person-detector-CAM02
# #     CAM03 -> person-detector-CAM03

# # Each detector has its own:
# #     - subprocess
# #     - process monitor
# #     - health monitor
# #     - restart lock
# #     - failure counter
# #     - recovery lifecycle
# #     - camera configuration
# #     - agent identity

# # Global downstream agents remain shared:

# #     tracker-01
# #     behavior-01
# #     crowd-01
# #     security-01
# #     alert-01
# #     incident-01

# # Those agents consume events from all cameras and are responsible for
# # maintaining camera-partitioned state where appropriate.

# # Fault isolation
# # ---------------
# # A failure in:

# #     CAM01 detector

# # must NOT terminate or restart:

# #     CAM02 detector
# #     CAM03 detector
# #     tracker
# #     behavior
# #     crowd
# #     security
# #     alert
# #     incident

# # Recovery model
# # --------------
# # Unexpected process exit
# #         |
# #         v
# # handle_process_exit()
# #         |
# #         v
# # recover()

# # Heartbeat timeout
# #         |
# #         v
# # recover()

# # Startup failure
# #         |
# #         v
# # recover()

# # All recovery paths converge on exactly one recovery authority:

# #     recover()

# # Process-generation protection
# # -----------------------------
# # Every subprocess start creates a new process generation.

# # A monitor waiting on an older process can never act on or interfere
# # with a newer replacement process.

# # Important architecture note
# # ---------------------------
# # Heartbeat timestamps are supplied by the shared agent_registry,
# # which is normally updated by the heartbeat consumer.

# # The complete production monitoring stack should therefore run:

# #     AgentSupervisor
# #           +
# #     Heartbeat Consumer
# #           +
# #     Watchdog

# # inside the unified monitoring service.
# # """

# # from __future__ import annotations

# # import asyncio
# # import os
# # import re
# # import sys
# # from dataclasses import dataclass
# # from datetime import datetime, timezone
# # from pathlib import Path
# # from typing import Optional

# # from backend.app.cameras.registry import CameraRegistry
# # from backend.app.monitoring.agent_registry import agent_registry


# # # ============================================================
# # # PATHS
# # # ============================================================

# # PROJECT_ROOT = Path(__file__).resolve().parents[3]
# # PYTHON_EXECUTABLE = sys.executable


# # # ============================================================
# # # SAFE ENVIRONMENT PARSING
# # # ============================================================

# # def _positive_float(
# #     name: str,
# #     default: float,
# # ) -> float:
# #     try:
# #         value = float(
# #             os.getenv(
# #                 name,
# #                 str(default),
# #             )
# #         )

# #         if value <= 0:
# #             return default

# #         return value

# #     except (TypeError, ValueError):
# #         return default


# # def _positive_int(
# #     name: str,
# #     default: int,
# # ) -> int:
# #     try:
# #         value = int(
# #             os.getenv(
# #                 name,
# #                 str(default),
# #             )
# #         )

# #         if value <= 0:
# #             return default

# #         return value

# #     except (TypeError, ValueError):
# #         return default


# # # ============================================================
# # # SUPERVISOR CONFIGURATION
# # # ============================================================

# # STARTUP_DELAY = _positive_float(
# #     "SUPERVISOR_STARTUP_DELAY",
# #     2.0,
# # )

# # RESTART_DELAY = _positive_float(
# #     "SUPERVISOR_RESTART_DELAY",
# #     3.0,
# # )

# # MAX_CONSECUTIVE_FAILURES = _positive_int(
# #     "SUPERVISOR_MAX_CONSECUTIVE_FAILURES",
# #     5,
# # )

# # HEALTHY_RESET_SECONDS = _positive_float(
# #     "SUPERVISOR_HEALTHY_RESET_SECONDS",
# #     60.0,
# # )

# # MAX_BACKOFF_SECONDS = _positive_float(
# #     "SUPERVISOR_MAX_BACKOFF_SECONDS",
# #     30.0,
# # )

# # HEALTH_CHECK_INTERVAL = _positive_float(
# #     "SUPERVISOR_HEALTH_CHECK_INTERVAL",
# #     2.0,
# # )

# # STARTUP_GRACE_PERIOD = _positive_float(
# #     "SUPERVISOR_STARTUP_GRACE_PERIOD",
# #     20.0,
# # )


# # # ============================================================
# # # HEARTBEAT CONFIGURATION
# # # ============================================================

# # HEARTBEAT_TIMEOUT = _positive_float(
# #     "HEARTBEAT_TIMEOUT",
# #     30.0,
# # )


# # # ============================================================
# # # AGENT CONFIGURATION
# # # ============================================================

# # @dataclass(frozen=True)
# # class AgentProcessConfig:
# #     """
# #     Configuration for one supervised subprocess.

# #     camera_id and camera_source are used only for
# #     camera-bound workers.

# #     camera_name and camera_location are optional metadata
# #     passed to camera-bound workers for camera-aware
# #     policies and context.
# #     """

# #     name: str
# #     agent_id: str
# #     script: str
# #     camera_id: Optional[str] = None
# #     camera_source: Optional[str] = None
# #     camera_name: Optional[str] = None
# #     camera_location: Optional[str] = None


# # # ============================================================
# # # GLOBAL PRODUCTION AGENTS
# # # ============================================================

# # GLOBAL_PRODUCTION_AGENTS = [
# #     AgentProcessConfig(
# #         name="tracker",
# #         agent_id="tracker-01",
# #         script="agents/tracker/main.py",
# #     ),
# #     AgentProcessConfig(
# #         name="behavior",
# #         agent_id="behavior-01",
# #         script="agents/behavior/main.py",
# #     ),
# #     AgentProcessConfig(
# #         name="crowd",
# #         agent_id="crowd-01",
# #         script="agents/crowd/main.py",
# #     ),
# #     AgentProcessConfig(
# #         name="security",
# #         agent_id="security-01",
# #         script="agents/security/main.py",
# #     ),
# #     AgentProcessConfig(
# #         name="alert",
# #         agent_id="alert-01",
# #         script="agents/alert/main.py",
# #     ),
# #     AgentProcessConfig(
# #         name="incident",
# #         agent_id="incident-01",
# #         script="agents/incident/main.py",
# #     ),
# # ]


# # # ============================================================
# # # CAMERA ID SANITIZATION
# # # ============================================================

# # def _safe_agent_id_component(camera_id: str) -> str:
# #     """
# #     Convert a camera ID into a safe process/agent identifier.

# #     Examples:
# #         CAM01      -> CAM01
# #         camera-01  -> camera-01
# #         cam 01     -> cam-01
# #         CAM/01     -> CAM-01
# #     """

# #     value = camera_id.strip()

# #     value = re.sub(
# #         r"[^A-Za-z0-9_.-]+",
# #         "-",
# #         value,
# #     )

# #     value = re.sub(
# #         r"-+",
# #         "-",
# #         value,
# #     )

# #     value = value.strip("-")

# #     if not value:
# #         raise ValueError(
# #             f"Camera ID cannot produce a valid agent ID: {camera_id!r}"
# #         )

# #     return value


# # # ============================================================
# # # SUPERVISED AGENT
# # # ============================================================

# # class SupervisedAgent:
# #     """
# #     Supervises exactly ONE agent subprocess.

# #     Every subprocess receives an explicit AGENT_ID environment
# #     variable equal to self.agent_id.

# #     Failure detectors:
# #         1. Unexpected process exit
# #         2. Missing first heartbeat
# #         3. Heartbeat timeout
# #         4. Registry DEAD
# #         5. Failed initial startup
# #         6. Failed recovery startup

# #     All recovery paths converge on recover().

# #     Every agent has independent:
# #         - subprocess
# #         - process monitor
# #         - health monitor
# #         - restart lock
# #         - failure counter
# #         - recovery lifecycle

# #     Process-generation protection:
# #         Every subprocess receives a monotonically increasing
# #         generation number.
# #     """

# #     def __init__(
# #         self,
# #         config: AgentProcessConfig,
# #     ):
# #         self.config = config

# #         # ----------------------------------------------------
# #         # Current subprocess
# #         # ----------------------------------------------------

# #         self.process: Optional[
# #             asyncio.subprocess.Process
# #         ] = None

# #         # ----------------------------------------------------
# #         # Process generation
# #         # ----------------------------------------------------

# #         self.process_generation = 0

# #         # ----------------------------------------------------
# #         # Lifecycle
# #         # ----------------------------------------------------

# #         self.running = False
# #         self.intentional_stop = False
# #         self.stopping_for_recovery = False

# #         # ----------------------------------------------------
# #         # Recovery synchronization
# #         # ----------------------------------------------------

# #         self.restart_lock = asyncio.Lock()
# #         self.recovery_in_progress = False

# #         # ----------------------------------------------------
# #         # Timing
# #         # ----------------------------------------------------

# #         self.started_at: Optional[float] = None
# #         self.healthy_since: Optional[float] = None

# #         # ----------------------------------------------------
# #         # Failure accounting
# #         # ----------------------------------------------------

# #         self.consecutive_failures = 0

# #         # ----------------------------------------------------
# #         # Heartbeat state
# #         # ----------------------------------------------------

# #         self.heartbeat_timeout_triggered = False
# #         self.first_heartbeat_received = False

# #     # ========================================================
# #     # PROPERTIES
# #     # ========================================================

# #     @property
# #     def agent_id(self) -> str:
# #         return self.config.agent_id

# #     @property
# #     def camera_id(self) -> Optional[str]:
# #         return self.config.camera_id

# #     @property
# #     def camera_source(self) -> Optional[str]:
# #         return self.config.camera_source

# #     @property
# #     def camera_name(self) -> Optional[str]:
# #         return self.config.camera_name

# #     @property
# #     def camera_location(self) -> Optional[str]:
# #         return self.config.camera_location

# #     @property
# #     def script_path(self) -> Path:
# #         return PROJECT_ROOT / self.config.script

# #     @property
# #     def pid(self) -> Optional[int]:
# #         if self.process is None:
# #             return None

# #         return self.process.pid

# #     # ========================================================
# #     # FAILURE ACCOUNTING
# #     # ========================================================

# #     def record_failure(self) -> None:
# #         self.consecutive_failures += 1

# #         print(
# #             "[SUPERVISOR] "
# #             f"{self.agent_id} consecutive recovery "
# #             f"failures: "
# #             f"{self.consecutive_failures}/"
# #             f"{MAX_CONSECUTIVE_FAILURES}"
# #         )

# #     def reset_failures_if_healthy(self) -> None:
# #         if self.healthy_since is None:
# #             return

# #         now = asyncio.get_running_loop().time()

# #         healthy_duration = (
# #             now - self.healthy_since
# #         )

# #         if (
# #             healthy_duration >= HEALTHY_RESET_SECONDS
# #             and self.consecutive_failures > 0
# #         ):
# #             print(
# #                 "[SUPERVISOR] "
# #                 f"{self.agent_id} remained healthy "
# #                 f"for {HEALTHY_RESET_SECONDS:.0f}s. "
# #                 "Resetting recovery failure counter."
# #             )

# #             self.consecutive_failures = 0
# #             self.healthy_since = now

# #     def can_restart(self) -> bool:
# #         return (
# #             self.consecutive_failures
# #             < MAX_CONSECUTIVE_FAILURES
# #         )

# #     def get_backoff_delay(self) -> float:
# #         exponent = max(
# #             0,
# #             self.consecutive_failures - 1,
# #         )

# #         delay = (
# #             RESTART_DELAY
# #             * (2 ** exponent)
# #         )

# #         return min(
# #             delay,
# #             MAX_BACKOFF_SECONDS,
# #         )

# #     # ========================================================
# #     # START
# #     # ========================================================

# #     async def start(self) -> bool:
# #         async with self.restart_lock:
# #             return await self._start_without_lock()

# #     # ========================================================
# #     # INTERNAL START
# #     # ========================================================

# #     async def _start_without_lock(self) -> bool:
# #         """
# #         Start a fresh subprocess.

# #         IMPORTANT:
# #         AGENT_ID is explicitly injected into the child
# #         environment on every process creation.
# #         """

# #         # ----------------------------------------------------
# #         # Already running
# #         # ----------------------------------------------------

# #         if self.process is not None:
# #             if self.process.returncode is None:
# #                 print(
# #                     "[SUPERVISOR] "
# #                     f"{self.agent_id} already running "
# #                     f"(PID={self.process.pid})"
# #                 )

# #                 return True

# #         # ----------------------------------------------------
# #         # Validate script
# #         # ----------------------------------------------------

# #         if not self.script_path.exists():
# #             print(
# #                 "[SUPERVISOR] ERROR: "
# #                 f"Script does not exist: "
# #                 f"{self.script_path}"
# #             )

# #             self.running = False

# #             agent_registry.mark_dead(
# #                 self.agent_id
# #             )

# #             return False

# #         # ----------------------------------------------------
# #         # New process generation
# #         # ----------------------------------------------------

# #         self.process_generation += 1

# #         generation = self.process_generation

# #         # ----------------------------------------------------
# #         # Lifecycle
# #         # ----------------------------------------------------

# #         self.intentional_stop = False
# #         self.stopping_for_recovery = False
# #         self.running = True

# #         loop = asyncio.get_running_loop()

# #         self.started_at = loop.time()
# #         self.healthy_since = None
# #         self.heartbeat_timeout_triggered = False
# #         self.first_heartbeat_received = False

# #         # ----------------------------------------------------
# #         # Registry
# #         # ----------------------------------------------------

# #         agent_registry.mark_starting(
# #             self.agent_id
# #         )

# #         print(
# #             "[SUPERVISOR] "
# #             f"Starting {self.agent_id}"
# #         )

# #         # ----------------------------------------------------
# #         # Child environment
# #         # ----------------------------------------------------

# #         env = os.environ.copy()

# #         existing_pythonpath = env.get(
# #             "PYTHONPATH",
# #             "",
# #         )

# #         if existing_pythonpath:
# #             env["PYTHONPATH"] = (
# #                 f"{PROJECT_ROOT}"
# #                 f"{os.pathsep}"
# #                 f"{existing_pythonpath}"
# #             )
# #         else:
# #             env["PYTHONPATH"] = str(
# #                 PROJECT_ROOT
# #             )

# #         env["PYTHONUNBUFFERED"] = "1"

# #         # ----------------------------------------------------
# #         # CRITICAL IDENTITY PROPAGATION
# #         # ----------------------------------------------------

# #         env["AGENT_ID"] = self.agent_id

# #         print(
# #             "[SUPERVISOR] "
# #             f"{self.agent_id} child identity: "
# #             f"AGENT_ID={env['AGENT_ID']}"
# #         )

# #         # ----------------------------------------------------
# #         # Camera configuration
# #         # ----------------------------------------------------

# #         if self.camera_id is not None:
# #             env["CAMERA_ID"] = self.camera_id

# #             if self.camera_source is not None:
# #                 env["CAMERA_SOURCE"] = (
# #                     str(self.camera_source)
# #                 )

# #             if self.camera_name is not None:
# #                 env["CAMERA_NAME"] = (
# #                     str(self.camera_name)
# #                 )

# #             if self.camera_location is not None:
# #                 env["CAMERA_LOCATION"] = (
# #                     str(self.camera_location)
# #                 )

# #             print(
# #                 "[SUPERVISOR] "
# #                 f"{self.agent_id} camera configuration: "
# #                 f"camera_id={self.camera_id}, "
# #                 f"source={self.camera_source or ''}, "
# #                 f"name={self.camera_name or ''}, "
# #                 f"location={self.camera_location or ''}"
# #             )

# #         else:
# #             # Prevent accidental inheritance of camera
# #             # configuration into global agents.

# #             env.pop(
# #                 "CAMERA_ID",
# #                 None,
# #             )

# #             env.pop(
# #                 "CAMERA_SOURCE",
# #                 None,
# #             )

# #             env.pop(
# #                 "CAMERA_NAME",
# #                 None,
# #             )

# #             env.pop(
# #                 "CAMERA_LOCATION",
# #                 None,
# #             )

# #         # ----------------------------------------------------
# #         # HEARTBEAT FAILURE TEST
# #         # ----------------------------------------------------

# #         heartbeat_test_target = os.getenv(
# #             "TEST_HEARTBEAT_FAILURE_AGENT",
# #             "",
# #         ).strip()

# #         if (
# #             heartbeat_test_target
# #             and heartbeat_test_target == self.agent_id
# #         ):
# #             env[
# #                 "TEST_HEARTBEAT_FAILURE_AGENT"
# #             ] = self.agent_id

# #             print(
# #                 "[SUPERVISOR] "
# #                 "HEARTBEAT FAILURE TEST ENABLED "
# #                 f"for {self.agent_id}"
# #             )

# #         else:
# #             env.pop(
# #                 "TEST_HEARTBEAT_FAILURE_AGENT",
# #                 None,
# #             )

# #         # ----------------------------------------------------
# #         # Start subprocess
# #         # ----------------------------------------------------

# #         try:
# #             process = (
# #                 await asyncio.create_subprocess_exec(
# #                     PYTHON_EXECUTABLE,
# #                     "-m",
# #                     self._module_name(),
# #                     cwd=str(PROJECT_ROOT),
# #                     env=env,
# #                     stdin=None,
# #                     stdout=None,
# #                     stderr=None,
# #                 )
# #             )

# #         except Exception as error:
# #             self.process = None
# #             self.running = False
# #             self.started_at = None
# #             self.healthy_since = None

# #             agent_registry.mark_dead(
# #                 self.agent_id
# #             )

# #             print(
# #                 "[SUPERVISOR] "
# #                 f"FAILED TO START "
# #                 f"{self.agent_id}: "
# #                 f"{error}"
# #             )

# #             return False

# #         # ----------------------------------------------------
# #         # Publish new process only after successful creation
# #         # ----------------------------------------------------

# #         self.process = process

# #         print(
# #             "[SUPERVISOR] "
# #             f"{self.agent_id} started "
# #             f"(PID={process.pid}, "
# #             f"generation={generation})"
# #         )

# #         return True

# #     # ========================================================
# #     # MODULE NAME
# #     # ========================================================

# #     def _module_name(self) -> str:
# #         """
# #         Convert:

# #             agents/detection/main.py

# #         into:

# #             agents.detection.main
# #         """

# #         relative = Path(
# #             self.config.script
# #         )

# #         without_suffix = relative.with_suffix("")

# #         return ".".join(
# #             without_suffix.parts
# #         )

# #     # ========================================================
# #     # STOP
# #     # ========================================================

# #     async def stop(self) -> None:
# #         """
# #         Intentionally stop this agent.

# #         Process monitor must NOT recover an intentionally
# #         stopped process.
# #         """

# #         self.intentional_stop = True
# #         self.stopping_for_recovery = False
# #         self.running = False
# #         self.recovery_in_progress = False

# #         process = self.process

# #         if process is None:
# #             return

# #         if process.returncode is not None:
# #             return

# #         print(
# #             "[SUPERVISOR] "
# #             f"Stopping {self.agent_id} "
# #             f"(PID={process.pid})"
# #         )

# #         try:
# #             process.terminate()

# #             await asyncio.wait_for(
# #                 process.wait(),
# #                 timeout=10,
# #             )

# #         except asyncio.TimeoutError:
# #             print(
# #                 "[SUPERVISOR] "
# #                 f"{self.agent_id} did not stop "
# #                 "gracefully. Killing."
# #             )

# #             try:
# #                 process.kill()

# #                 await asyncio.wait_for(
# #                     process.wait(),
# #                     timeout=10,
# #                 )

# #             except Exception as error:
# #                 print(
# #                     "[SUPERVISOR] "
# #                     f"Kill error for "
# #                     f"{self.agent_id}: "
# #                     f"{error}"
# #                 )

# #         except ProcessLookupError:
# #             pass

# #         except Exception as error:
# #             print(
# #                 "[SUPERVISOR] "
# #                 f"Stop error for "
# #                 f"{self.agent_id}: "
# #                 f"{error}"
# #             )

# #     # ========================================================
# #     # PROCESS EXIT HANDLER
# #     # ========================================================

# #     async def handle_process_exit(
# #         self,
# #         return_code: int,
# #     ) -> None:
# #         """
# #         Handle an unexpected process termination.

# #         Recovery must NOT be triggered when:
# #         1. Operator/application intentionally stopped worker.
# #         2. Supervisor is intentionally replacing worker.
# #         3. Supervisor recovery is already in progress.
# #         """

# #         if self.intentional_stop:
# #             print(
# #                 "[SUPERVISOR] "
# #                 f"{self.agent_id} process exit ignored "
# #                 "(intentional stop)."
# #             )

# #             return

# #         if self.stopping_for_recovery:
# #             print(
# #                 "[SUPERVISOR] "
# #                 f"{self.agent_id} process exit acknowledged "
# #                 "(intentional recovery stop)."
# #             )

# #             return

# #         if self.recovery_in_progress:
# #             print(
# #                 "[SUPERVISOR] "
# #                 f"{self.agent_id} process exit observed "
# #                 "while recovery is already in progress. "
# #                 "Ignoring duplicate recovery trigger."
# #             )

# #             return

# #         print(
# #             "[SUPERVISOR] "
# #             f"{self.agent_id} exited "
# #             f"(code={return_code})"
# #         )

# #         self.running = False

# #         agent_registry.mark_dead(
# #             self.agent_id
# #         )

# #         await self.recover(
# #             reason="process_exit"
# #         )

# #     # ========================================================
# #     # UNIFIED RECOVERY
# #     # ========================================================

# #     async def recover(
# #         self,
# #         reason: str,
# #     ) -> None:
# #         """
# #         Single recovery authority.

# #         Recovery lifecycle:

# #             record failure
# #                   ↓
# #             mark RECOVERING
# #                   ↓
# #             mark intentional recovery stop
# #                   ↓
# #             stop failed process
# #                   ↓
# #             clear old process state
# #                   ↓
# #             exponential backoff
# #                   ↓
# #             start fresh process
# #                   ↓
# #             if startup fails:
# #                 retry through recover()
# #         """

# #         async with self.restart_lock:

# #             # ------------------------------------------------
# #             # Operator shutdown
# #             # ------------------------------------------------

# #             if self.intentional_stop:
# #                 return

# #             # ------------------------------------------------
# #             # Another recovery already owns this agent
# #             # ------------------------------------------------

# #             if self.recovery_in_progress:
# #                 return

# #             self.recovery_in_progress = True

# #             try:

# #                 # --------------------------------------------
# #                 # Failure accounting
# #                 # --------------------------------------------

# #                 self.record_failure()

# #                 if not self.can_restart():
# #                     print(
# #                         "[SUPERVISOR] "
# #                         f"Restart limit reached for "
# #                         f"{self.agent_id}."
# #                     )

# #                     print(
# #                         "[SUPERVISOR] "
# #                         f"{self.agent_id} requires "
# #                         "manual intervention."
# #                     )

# #                     self.running = False

# #                     agent_registry.mark_dead(
# #                         self.agent_id
# #                     )

# #                     return

# #                 attempt = (
# #                     self.consecutive_failures
# #                 )

# #                 delay = (
# #                     self.get_backoff_delay()
# #                 )

# #                 print(
# #                     "[SUPERVISOR] "
# #                     f"Recovering {self.agent_id} "
# #                     f"(reason={reason}, "
# #                     f"attempt={attempt}/"
# #                     f"{MAX_CONSECUTIVE_FAILURES}, "
# #                     f"backoff={delay:.1f}s)"
# #                 )

# #                 agent_registry.mark_recovering(
# #                     self.agent_id
# #                 )

# #                 # --------------------------------------------
# #                 # Capture exact process being recovered
# #                 # --------------------------------------------

# #                 process = self.process

# #                 recovery_generation = (
# #                     self.process_generation
# #                 )

# #                 # --------------------------------------------
# #                 # Mark termination intentional BEFORE killing
# #                 # --------------------------------------------

# #                 self.stopping_for_recovery = True

# #                 if process is not None:
# #                     if process.returncode is None:

# #                         print(
# #                             "[SUPERVISOR] "
# #                             f"Stopping unresponsive "
# #                             f"{self.agent_id} "
# #                             f"(PID={process.pid}, "
# #                             f"generation={recovery_generation})"
# #                         )

# #                         try:
# #                             process.kill()

# #                             await asyncio.wait_for(
# #                                 process.wait(),
# #                                 timeout=10,
# #                             )

# #                         except ProcessLookupError:
# #                             pass

# #                         except asyncio.TimeoutError:
# #                             print(
# #                                 "[SUPERVISOR] "
# #                                 f"Timed out waiting for "
# #                                 f"{self.agent_id} "
# #                                 "to terminate."
# #                             )

# #                         except Exception as error:
# #                             print(
# #                                 "[SUPERVISOR] "
# #                                 f"Failed to stop "
# #                                 f"{self.agent_id}: "
# #                                 f"{error}"
# #                             )

# #                 # --------------------------------------------
# #                 # Clear old process state
# #                 # --------------------------------------------

# #                 if (
# #                     self.process is process
# #                     and self.process_generation
# #                     == recovery_generation
# #                 ):
# #                     self.process = None

# #                 self.started_at = None
# #                 self.healthy_since = None
# #                 self.heartbeat_timeout_triggered = False
# #                 self.first_heartbeat_received = False

# #                 # --------------------------------------------
# #                 # Recovery backoff
# #                 # --------------------------------------------

# #                 await asyncio.sleep(
# #                     delay
# #                 )

# #                 if self.intentional_stop:
# #                     return

# #                 # --------------------------------------------
# #                 # Prepare fresh process
# #                 # --------------------------------------------

# #                 self.stopping_for_recovery = False
# #                 self.running = True

# #                 # --------------------------------------------
# #                 # Fresh process
# #                 # --------------------------------------------

# #                 started = (
# #                     await self._start_without_lock()
# #                 )

# #                 if not started:

# #                     print(
# #                         "[SUPERVISOR] "
# #                         f"Recovery start failed for "
# #                         f"{self.agent_id}."
# #                     )

# #                     # ----------------------------------------
# #                     # CRITICAL FIX:
# #                     # Do not leave an agent stranded with:
# #                     #
# #                     #     running=True
# #                     #     process=None
# #                     #
# #                     # Instead immediately release the current
# #                     # recovery and schedule another recovery
# #                     # attempt through the same authority.
# #                     # ----------------------------------------

# #                     self.running = False
# #                     self.process = None

# #                     agent_registry.mark_dead(
# #                         self.agent_id
# #                     )

# #                     return

# #                 print(
# #                     "[SUPERVISOR] "
# #                     f"{self.agent_id} recovery "
# #                     "process started successfully."
# #                 )

# #             finally:
# #                 self.stopping_for_recovery = False
# #                 self.recovery_in_progress = False

# #     # ========================================================
# #     # PROCESS MONITOR
# #     # ========================================================

# #     async def monitor_process(self) -> None:
# #         """
# #         Continuously monitor this agent's subprocess.

# #         The task remains alive for the lifetime of the
# #         supervisor.

# #         It monitors the exact process object + generation.
# #         """

# #         observed_generation: Optional[int] = None

# #         observed_process: Optional[
# #             asyncio.subprocess.Process
# #         ] = None

# #         while self.running:

# #             process = self.process

# #             # ------------------------------------------------
# #             # No current process
# #             # ------------------------------------------------

# #             if process is None:
# #                 observed_process = None
# #                 observed_generation = None

# #                 await asyncio.sleep(0.2)

# #                 continue

# #             current_generation = (
# #                 self.process_generation
# #             )

# #             # ------------------------------------------------
# #             # New process detected
# #             # ------------------------------------------------

# #             if (
# #                 observed_process is not process
# #                 or observed_generation
# #                 != current_generation
# #             ):
# #                 observed_process = process
# #                 observed_generation = (
# #                     current_generation
# #                 )

# #             # ------------------------------------------------
# #             # Wait for exact process
# #             # ------------------------------------------------

# #             try:
# #                 return_code = await process.wait()

# #             except asyncio.CancelledError:
# #                 raise

# #             except Exception as error:
# #                 print(
# #                     "[SUPERVISOR] "
# #                     f"Process monitor error for "
# #                     f"{self.agent_id}: "
# #                     f"{error}"
# #                 )

# #                 await asyncio.sleep(1)

# #                 continue

# #             # ------------------------------------------------
# #             # Supervisor/operator shutdown
# #             # ------------------------------------------------

# #             if not self.running:
# #                 return

# #             # ------------------------------------------------
# #             # STALE PROCESS PROTECTION
# #             # ------------------------------------------------

# #             if (
# #                 self.process is not process
# #                 or self.process_generation
# #                 != observed_generation
# #             ):
# #                 continue

# #             # ------------------------------------------------
# #             # Intentional recovery stop
# #             # ------------------------------------------------

# #             if self.stopping_for_recovery:

# #                 print(
# #                     "[SUPERVISOR] "
# #                     f"{self.agent_id} process exited "
# #                     "during intentional recovery stop."
# #                 )

# #                 old_process = process

# #                 old_generation = (
# #                     observed_generation
# #                 )

# #                 while self.running:

# #                     current_process = self.process

# #                     current_generation = (
# #                         self.process_generation
# #                     )

# #                     if (
# #                         current_process is not old_process
# #                         or current_generation
# #                         != old_generation
# #                     ):
# #                         break

# #                     await asyncio.sleep(0.2)

# #                 observed_process = None
# #                 observed_generation = None

# #                 continue

# #             # ------------------------------------------------
# #             # Recovery already owns lifecycle
# #             # ------------------------------------------------

# #             if self.recovery_in_progress:

# #                 print(
# #                     "[SUPERVISOR] "
# #                     f"{self.agent_id} process exited "
# #                     "while recovery is in progress."
# #                 )

# #                 old_process = process

# #                 old_generation = (
# #                     observed_generation
# #                 )

# #                 while self.running:

# #                     current_process = self.process

# #                     current_generation = (
# #                         self.process_generation
# #                     )

# #                     if (
# #                         current_process is not old_process
# #                         or current_generation
# #                         != old_generation
# #                     ):
# #                         break

# #                     await asyncio.sleep(0.2)

# #                 observed_process = None
# #                 observed_generation = None

# #                 continue

# #             # ------------------------------------------------
# #             # Genuine unexpected process exit
# #             # ------------------------------------------------

# #             await self.handle_process_exit(
# #                 return_code
# #             )

# #             # ------------------------------------------------
# #             # Recovery may have replaced process
# #             # ------------------------------------------------

# #             observed_process = None
# #             observed_generation = None

# #     # ========================================================
# #     # HEARTBEAT AGE
# #     # ========================================================

# #     def get_heartbeat_age(
# #         self,
# #         agent: dict,
# #     ) -> Optional[float]:

# #         last_heartbeat = agent.get(
# #             "last_heartbeat"
# #         )

# #         if last_heartbeat is None:
# #             return None

# #         try:

# #             if last_heartbeat.tzinfo is None:
# #                 last_heartbeat = (
# #                     last_heartbeat.replace(
# #                         tzinfo=timezone.utc
# #                     )
# #                 )

# #             now = datetime.now(
# #                 timezone.utc
# #             )

# #             age = (
# #                 now - last_heartbeat
# #             ).total_seconds()

# #             return max(
# #                 0.0,
# #                 age,
# #             )

# #         except Exception as error:

# #             print(
# #                 "[SUPERVISOR] "
# #                 f"Heartbeat timestamp error for "
# #                 f"{self.agent_id}: "
# #                 f"{error}"
# #             )

# #             return None

# #     # ========================================================
# #     # HEARTBEAT TIMEOUT
# #     # ========================================================

# #     def check_heartbeat_timeout(
# #         self,
# #         agent: dict,
# #     ) -> str:

# #         heartbeat_age = (
# #             self.get_heartbeat_age(
# #                 agent
# #             )
# #         )

# #         if heartbeat_age is None:
# #             return "missing"

# #         if heartbeat_age <= HEARTBEAT_TIMEOUT:
# #             return "healthy"

# #         return "timeout"

# #     # ========================================================
# #     # HEALTH CHECK
# #     # ========================================================

# #     async def check_health(self) -> None:

# #         if not self.running:
# #             return

# #         process = self.process

# #         # ----------------------------------------------------
# #         # IMPORTANT:
# #         #
# #         # A missing process while the supervisor is supposed
# #         # to be running means the agent is unhealthy.
# #         #
# #         # Previously this simply returned forever.
# #         # ----------------------------------------------------

# #         if process is None:

# #             if self.recovery_in_progress:
# #                 return

# #             if self.intentional_stop:
# #                 return

# #             print(
# #                 "[SUPERVISOR] "
# #                 f"{self.agent_id} has no active "
# #                 "process while marked running."
# #             )

# #             await self.recover(
# #                 reason="missing_process"
# #             )

# #             return

# #         if process.returncode is not None:

# #             if self.recovery_in_progress:
# #                 return

# #             return

# #         if self.started_at is None:
# #             return

# #         # ----------------------------------------------------
# #         # Recovery owns lifecycle
# #         # ----------------------------------------------------

# #         if self.recovery_in_progress:
# #             return

# #         loop = asyncio.get_running_loop()

# #         now = loop.time()

# #         age_since_start = (
# #             now - self.started_at
# #         )

# #         # ----------------------------------------------------
# #         # Registry state
# #         # ----------------------------------------------------

# #         agent = agent_registry.get_agent(
# #             self.agent_id
# #         )

# #         if agent is None:
# #             return

# #         status = agent.get(
# #             "status"
# #         )

# #         # ----------------------------------------------------
# #         # Startup grace period
# #         # ----------------------------------------------------

# #         if (
# #             age_since_start
# #             < STARTUP_GRACE_PERIOD
# #         ):
# #             return

# #         # ----------------------------------------------------
# #         # Heartbeat state
# #         # ----------------------------------------------------

# #         heartbeat_state = (
# #             self.check_heartbeat_timeout(
# #                 agent
# #             )
# #         )

# #         # ----------------------------------------------------
# #         # First heartbeat never arrived
# #         # ----------------------------------------------------

# #         if heartbeat_state == "missing":

# #             if not self.first_heartbeat_received:

# #                 print(
# #                     "[SUPERVISOR] "
# #                     "FIRST HEARTBEAT TIMEOUT: "
# #                     f"{self.agent_id} "
# #                     f"(startup_age="
# #                     f"{age_since_start:.1f}s, "
# #                     f"grace="
# #                     f"{STARTUP_GRACE_PERIOD:.1f}s)"
# #                 )

# #                 agent_registry.mark_dead(
# #                     self.agent_id
# #                 )

# #                 await self.recover(
# #                     reason="missing_first_heartbeat"
# #                 )

# #             return

# #         # ----------------------------------------------------
# #         # Heartbeat arrived
# #         # ----------------------------------------------------

# #         self.first_heartbeat_received = True

# #         # ----------------------------------------------------
# #         # Heartbeat timeout
# #         # ----------------------------------------------------

# #         if heartbeat_state == "timeout":

# #             if not self.heartbeat_timeout_triggered:

# #                 self.heartbeat_timeout_triggered = True

# #                 heartbeat_age = (
# #                     self.get_heartbeat_age(
# #                         agent
# #                     )
# #                 )

# #                 print(
# #                     "[SUPERVISOR] "
# #                     "HEARTBEAT TIMEOUT: "
# #                     f"{self.agent_id} "
# #                     f"(age="
# #                     f"{heartbeat_age:.1f}s, "
# #                     f"timeout="
# #                     f"{HEARTBEAT_TIMEOUT:.1f}s)"
# #                 )

# #                 agent_registry.mark_dead(
# #                     self.agent_id
# #                 )

# #                 await self.recover(
# #                     reason="heartbeat_timeout"
# #                 )

# #             return

# #         # ----------------------------------------------------
# #         # Registry explicitly DEAD
# #         # ----------------------------------------------------

# #         if status == "DEAD":

# #             if self.recovery_in_progress:
# #                 return

# #             print(
# #                 "[SUPERVISOR] "
# #                 f"Heartbeat failure detected for "
# #                 f"{self.agent_id}"
# #             )

# #             await self.recover(
# #                 reason="registry_dead"
# #             )

# #             return

# #         # ----------------------------------------------------
# #         # Starting / recovering
# #         # ----------------------------------------------------

# #         if status in (
# #             "STARTING",
# #             "RECOVERING",
# #         ):
# #             return

# #         # ----------------------------------------------------
# #         # Healthy
# #         # ----------------------------------------------------

# #         if status == "ALIVE":

# #             if self.healthy_since is None:
# #                 self.healthy_since = now

# #             self.reset_failures_if_healthy()

# #             return

# #         # ----------------------------------------------------
# #         # Unknown state
# #         # ----------------------------------------------------

# #         print(
# #             "[SUPERVISOR] "
# #             f"{self.agent_id} unexpected "
# #             f"registry status: {status}"
# #         )

# #     # ========================================================
# #     # HEALTH LOOP
# #     # ========================================================

# #     async def health_loop(self) -> None:

# #         while self.running:

# #             try:

# #                 await self.check_health()

# #                 await asyncio.sleep(
# #                     HEALTH_CHECK_INTERVAL
# #                 )

# #             except asyncio.CancelledError:
# #                 raise

# #             except Exception as error:

# #                 print(
# #                     "[SUPERVISOR] "
# #                     f"Health loop error for "
# #                     f"{self.agent_id}: "
# #                     f"{error}"
# #                 )

# #                 await asyncio.sleep(2)


# # # ============================================================
# # # AGENT SUPERVISOR
# # # ============================================================

# # class AgentSupervisor:
# #     """
# #     Supervises all configured production agents.

# #     Camera-bound detection workers are created independently
# #     for every enabled camera.

# #     Example:

# #         CAM01 -> person-detector-CAM01
# #         CAM02 -> person-detector-CAM02
# #         CAM03 -> person-detector-CAM03

# #     Global downstream workers remain shared.
# #     """

# #     def __init__(self):

# #         self.camera_registry = (
# #             CameraRegistry.from_environment()
# #         )

# #         self.agents: dict[
# #             str,
# #             SupervisedAgent,
# #         ] = {}

# #         self.running = False

# #         self.monitor_tasks: list[
# #             asyncio.Task
# #         ] = []

# #         self.health_tasks: list[
# #             asyncio.Task
# #         ] = []

# #         self._build_agent_configuration()

# #     # ========================================================
# #     # BUILD CONFIGURATION
# #     # ========================================================

# #     def _build_agent_configuration(self) -> None:

# #         enabled_cameras = (
# #             self.camera_registry.get_enabled()
# #         )

# #         if not enabled_cameras:

# #             print(
# #                 "[SUPERVISOR] WARNING: "
# #                 "No enabled cameras configured."
# #             )

# #         # ----------------------------------------------------
# #         # Create ONE detector per enabled camera
# #         # ----------------------------------------------------

# #         for camera in enabled_cameras:

# #             camera_component = (
# #                 _safe_agent_id_component(
# #                     camera.camera_id
# #                 )
# #             )

# #             detector_agent_id = (
# #                 f"person-detector-"
# #                 f"{camera_component}"
# #             )

# #             detection_config = AgentProcessConfig(
# #                 name="detection",
# #                 agent_id=detector_agent_id,
# #                 script="agents/detection/main.py",
# #                 camera_id=camera.camera_id,
# #                 camera_source=str(
# #                     camera.source
# #                 ),
# #                 camera_name=camera.name,
# #                 camera_location=camera.location,
# #             )

# #             if detector_agent_id in self.agents:

# #                 raise ValueError(
# #                     "Duplicate supervised agent ID "
# #                     f"generated for camera "
# #                     f"{camera.camera_id}: "
# #                     f"{detector_agent_id}"
# #                 )

# #             self.agents[
# #                 detector_agent_id
# #             ] = SupervisedAgent(
# #                 detection_config
# #             )

# #         # ----------------------------------------------------
# #         # Global agents
# #         # ----------------------------------------------------

# #         for config in GLOBAL_PRODUCTION_AGENTS:

# #             if config.agent_id in self.agents:

# #                 raise ValueError(
# #                     "Duplicate supervised agent ID: "
# #                     f"{config.agent_id}"
# #                 )

# #             self.agents[
# #                 config.agent_id
# #             ] = SupervisedAgent(
# #                 config
# #             )

# #     # ========================================================
# #     # START ALL
# #     # ========================================================

# #     async def start_all(self) -> None:

# #         print("=" * 70)
# #         print("AGENT SUPERVISOR")
# #         print("=" * 70)

# #         print(
# #             "[SUPERVISOR] "
# #             f"Python: {PYTHON_EXECUTABLE}"
# #         )

# #         print(
# #             "[SUPERVISOR] "
# #             f"Project root: {PROJECT_ROOT}"
# #         )

# #         print(
# #             "[SUPERVISOR] "
# #             f"Production agents: "
# #             f"{len(self.agents)}"
# #         )

# #         # ----------------------------------------------------
# #         # Camera information
# #         # ----------------------------------------------------

# #         all_cameras = (
# #             self.camera_registry.get_all()
# #         )

# #         enabled_cameras = (
# #             self.camera_registry.get_enabled()
# #         )

# #         print(
# #             "[SUPERVISOR] "
# #             f"Configured cameras: "
# #             f"{len(all_cameras)}"
# #         )

# #         print(
# #             "[SUPERVISOR] "
# #             f"Enabled cameras: "
# #             f"{len(enabled_cameras)}"
# #         )

# #         for camera in enabled_cameras:

# #             print(
# #                 "[SUPERVISOR] "
# #                 f"Camera: "
# #                 f"{camera.camera_id} | "
# #                 f"name={camera.name} | "
# #                 f"source={camera.source} | "
# #                 f"location={camera.location}"
# #             )

# #             detector_agent_id = (
# #                 f"person-detector-"
# #                 f"{_safe_agent_id_component(camera.camera_id)}"
# #             )

# #             print(
# #                 "[SUPERVISOR] "
# #                 f"Camera affinity: "
# #                 f"{camera.camera_id} -> "
# #                 f"{detector_agent_id}"
# #             )

# #         # ----------------------------------------------------
# #         # Health configuration
# #         # ----------------------------------------------------

# #         print(
# #             "[SUPERVISOR] "
# #             f"Heartbeat timeout: "
# #             f"{HEARTBEAT_TIMEOUT:.1f}s"
# #         )

# #         print(
# #             "[SUPERVISOR] "
# #             f"Startup grace period: "
# #             f"{STARTUP_GRACE_PERIOD:.1f}s"
# #         )

# #         # ----------------------------------------------------
# #         # Heartbeat failure-test configuration
# #         # ----------------------------------------------------

# #         heartbeat_test_target = os.getenv(
# #             "TEST_HEARTBEAT_FAILURE_AGENT",
# #             "",
# #         ).strip()

# #         if heartbeat_test_target:

# #             print(
# #                 "[SUPERVISOR] "
# #                 "Heartbeat failure test target: "
# #                 f"{heartbeat_test_target}"
# #             )

# #         print("=" * 70)

# #         self.running = True

# #         # ----------------------------------------------------
# #         # Start every agent independently
# #         # ----------------------------------------------------

# #         for agent in self.agents.values():

# #             try:

# #                 started = await agent.start()

# #                 if not started:

# #                     print(
# #                         "[SUPERVISOR] "
# #                         f"{agent.agent_id} failed "
# #                         "initial startup. "
# #                         "Scheduling automatic recovery."
# #                     )

# #                     # ------------------------------------------------
# #                     # FIX:
# #                     # A failed initial startup must enter the same
# #                     # recovery authority as every other failure.
# #                     # ------------------------------------------------

# #                     if agent.running:
# #                         agent.running = False

# #                     asyncio.create_task(
# #                         agent.recover(
# #                             reason="initial_startup_failure"
# #                         ),
# #                         name=(
# #                             f"initial-recovery-"
# #                             f"{agent.agent_id}"
# #                         ),
# #                     )

# #             except Exception as error:

# #                 print(
# #                     "[SUPERVISOR] "
# #                     f"Failed to start "
# #                     f"{agent.agent_id}: "
# #                     f"{error}"
# #                 )

# #                 agent.running = False

# #                 asyncio.create_task(
# #                     agent.recover(
# #                         reason="initial_startup_exception"
# #                     ),
# #                     name=(
# #                         f"initial-recovery-"
# #                         f"{agent.agent_id}"
# #                     ),
# #                 )

# #             await asyncio.sleep(
# #                 STARTUP_DELAY
# #             )

# #         # ----------------------------------------------------
# #         # Process monitors
# #         # ----------------------------------------------------

# #         for agent in self.agents.values():

# #             task = asyncio.create_task(
# #                 agent.monitor_process(),
# #                 name=(
# #                     f"monitor-process-"
# #                     f"{agent.agent_id}"
# #                 ),
# #             )

# #             self.monitor_tasks.append(
# #                 task
# #             )

# #         # ----------------------------------------------------
# #         # Health monitors
# #         # ----------------------------------------------------

# #         for agent in self.agents.values():

# #             task = asyncio.create_task(
# #                 agent.health_loop(),
# #                 name=(
# #                     f"health-monitor-"
# #                     f"{agent.agent_id}"
# #                 ),
# #             )

# #             self.health_tasks.append(
# #                 task
# #             )

# #         print(
# #             "[SUPERVISOR] "
# #             "All process monitors started."
# #         )

# #         print(
# #             "[SUPERVISOR] "
# #             "All health monitors started."
# #         )

# #     # ========================================================
# #     # STOP ALL
# #     # ========================================================

# #     async def stop_all(self) -> None:

# #         if not self.running:
# #             return

# #         print(
# #             "[SUPERVISOR] "
# #             "Shutdown requested."
# #         )

# #         self.running = False

# #         # ----------------------------------------------------
# #         # Mark intentional stop BEFORE cancelling monitors
# #         # ----------------------------------------------------

# #         for agent in self.agents.values():

# #             agent.running = False
# #             agent.intentional_stop = True
# #             agent.stopping_for_recovery = False

# #         # ----------------------------------------------------
# #         # Cancel process monitors
# #         # ----------------------------------------------------

# #         for task in self.monitor_tasks:
# #             task.cancel()

# #         if self.monitor_tasks:

# #             await asyncio.gather(
# #                 *self.monitor_tasks,
# #                 return_exceptions=True,
# #             )

# #         self.monitor_tasks.clear()

# #         # ----------------------------------------------------
# #         # Cancel health monitors
# #         # ----------------------------------------------------

# #         for task in self.health_tasks:
# #             task.cancel()

# #         if self.health_tasks:

# #             await asyncio.gather(
# #                 *self.health_tasks,
# #                 return_exceptions=True,
# #             )

# #         self.health_tasks.clear()

# #         # ----------------------------------------------------
# #         # Stop processes independently
# #         # ----------------------------------------------------

# #         for agent in self.agents.values():

# #             try:

# #                 await agent.stop()

# #             except Exception as error:

# #                 print(
# #                     "[SUPERVISOR] "
# #                     f"Shutdown error for "
# #                     f"{agent.agent_id}: "
# #                     f"{error}"
# #                 )

# #         print(
# #             "[SUPERVISOR] "
# #             "All agents stopped."
# #         )


# # # ============================================================
# # # STANDALONE MAIN
# # # ============================================================

# # async def main():

# #     supervisor = AgentSupervisor()

# #     try:

# #         await supervisor.start_all()

# #         while supervisor.running:
# #             await asyncio.sleep(1)

# #     except asyncio.CancelledError:
# #         raise

# #     finally:

# #         await supervisor.stop_all()


# # # ============================================================
# # # ENTRY POINT
# # # ============================================================

# # if __name__ == "__main__":

# #     try:

# #         asyncio.run(main())

# #     except KeyboardInterrupt:

# #         print(
# #             "\n[SUPERVISOR] "
# #             "Stopped by operator."
# #         )
























































# """
# Per-agent process supervisor.

# Responsibilities
# ----------------

# - Start production agents as isolated subprocesses.
# - Create one camera-bound detection worker per enabled camera.
# - Provide camera and agent identity configuration to subprocesses.
# - Monitor process lifetime.
# - Monitor heartbeat health.
# - Recover only the failed agent.
# - Prevent concurrent recovery of the same agent.
# - Apply exponential restart backoff.
# - Limit repeated restart failures.
# - Respect startup grace periods.
# - Automatically retry failed startup/recovery.
# - Keep one agent failure isolated from all other agents.

# Multi-camera model
# ------------------

# For every enabled camera:

#     CAM01 -> person-detector-CAM01
#     CAM02 -> person-detector-CAM02
#     CAM03 -> person-detector-CAM03

# Each detector has its own:

#     - subprocess
#     - process monitor
#     - health monitor
#     - restart lock
#     - failure counter
#     - recovery lifecycle
#     - camera configuration
#     - agent identity

# Global downstream agents remain shared:

#     tracker-01
#     behavior-01
#     crowd-01
#     security-01
#     alert-01
#     incident-01

# Those agents consume events from all cameras and are responsible for
# maintaining camera-partitioned state where appropriate.

# Fault isolation
# ---------------

# A failure in:

#     CAM01 detector

# must NOT terminate or restart:

#     CAM02 detector
#     CAM03 detector
#     tracker
#     behavior
#     crowd
#     security
#     alert
#     incident

# Recovery model
# --------------

# Unexpected process exit
#         |
#         v
# handle_process_exit()
#         |
#         v
# recover()

# Heartbeat timeout
#         |
#         v
# recover()

# Startup failure
#         |
#         v
# recover()

# All recovery paths converge on exactly one recovery authority:

#     recover()

# Recovery startup failures are retried by recover() itself.

# Process-generation protection
# -----------------------------

# Every subprocess start creates a new process generation.

# A monitor waiting on an older process can never act on or interfere
# with a newer replacement process.

# Important architecture note
# ---------------------------

# Heartbeat timestamps are supplied by the shared agent_registry,
# which is normally updated by the heartbeat consumer.

# The complete production monitoring stack should therefore run:

#     AgentSupervisor
#           +
#     Heartbeat Consumer
#           +
#     Watchdog

# inside the unified monitoring service.
# """

# from __future__ import annotations

# import asyncio
# import os
# import re
# import sys

# from dataclasses import dataclass
# from datetime import datetime, timezone
# from pathlib import Path
# from typing import Optional

# from backend.app.cameras.registry import CameraRegistry
# from backend.app.monitoring.agent_registry import agent_registry


# # ============================================================
# # PATHS
# # ============================================================

# PROJECT_ROOT = Path(__file__).resolve().parents[3]
# PYTHON_EXECUTABLE = sys.executable


# # ============================================================
# # SAFE ENVIRONMENT PARSING
# # ============================================================

# def _positive_float(
#     name: str,
#     default: float,
# ) -> float:
#     try:
#         value = float(
#             os.getenv(
#                 name,
#                 str(default),
#             )
#         )

#         if value <= 0:
#             return default

#         return value

#     except (TypeError, ValueError):
#         return default


# def _positive_int(
#     name: str,
#     default: int,
# ) -> int:
#     try:
#         value = int(
#             os.getenv(
#                 name,
#                 str(default),
#             )
#         )

#         if value <= 0:
#             return default

#         return value

#     except (TypeError, ValueError):
#         return default


# # ============================================================
# # SUPERVISOR CONFIGURATION
# # ============================================================

# STARTUP_DELAY = _positive_float(
#     "SUPERVISOR_STARTUP_DELAY",
#     2.0,
# )

# RESTART_DELAY = _positive_float(
#     "SUPERVISOR_RESTART_DELAY",
#     3.0,
# )

# MAX_CONSECUTIVE_FAILURES = _positive_int(
#     "SUPERVISOR_MAX_CONSECUTIVE_FAILURES",
#     5,
# )

# HEALTHY_RESET_SECONDS = _positive_float(
#     "SUPERVISOR_HEALTHY_RESET_SECONDS",
#     60.0,
# )

# MAX_BACKOFF_SECONDS = _positive_float(
#     "SUPERVISOR_MAX_BACKOFF_SECONDS",
#     30.0,
# )

# HEALTH_CHECK_INTERVAL = _positive_float(
#     "SUPERVISOR_HEALTH_CHECK_INTERVAL",
#     2.0,
# )

# STARTUP_GRACE_PERIOD = _positive_float(
#     "SUPERVISOR_STARTUP_GRACE_PERIOD",
#     20.0,
# )


# # ============================================================
# # HEARTBEAT CONFIGURATION
# # ============================================================

# HEARTBEAT_TIMEOUT = _positive_float(
#     "HEARTBEAT_TIMEOUT",
#     30.0,
# )


# # ============================================================
# # AGENT CONFIGURATION
# # ============================================================

# @dataclass(frozen=True)
# class AgentProcessConfig:
#     """
#     Configuration for one supervised subprocess.

#     camera_id and camera_source are used only for
#     camera-bound workers.

#     camera_name and camera_location are optional metadata
#     passed to camera-bound workers for camera-aware
#     policies and context.
#     """

#     name: str
#     agent_id: str
#     script: str

#     camera_id: Optional[str] = None
#     camera_source: Optional[str] = None
#     camera_name: Optional[str] = None
#     camera_location: Optional[str] = None


# # ============================================================
# # GLOBAL PRODUCTION AGENTS
# # ============================================================

# GLOBAL_PRODUCTION_AGENTS = [
#     AgentProcessConfig(
#         name="tracker",
#         agent_id="tracker-01",
#         script="agents/tracker/main.py",
#     ),
#     AgentProcessConfig(
#         name="behavior",
#         agent_id="behavior-01",
#         script="agents/behavior/main.py",
#     ),
#     AgentProcessConfig(
#         name="crowd",
#         agent_id="crowd-01",
#         script="agents/crowd/main.py",
#     ),
#     AgentProcessConfig(
#         name="security",
#         agent_id="security-01",
#         script="agents/security/main.py",
#     ),
#     AgentProcessConfig(
#         name="alert",
#         agent_id="alert-01",
#         script="agents/alert/main.py",
#     ),
#     AgentProcessConfig(
#         name="incident",
#         agent_id="incident-01",
#         script="agents/incident/main.py",
#     ),
# ]


# # ============================================================
# # CAMERA ID SANITIZATION
# # ============================================================

# def _safe_agent_id_component(
#     camera_id: str,
# ) -> str:
#     """
#     Convert a camera ID into a safe process/agent identifier.

#     Examples:

#         CAM01      -> CAM01
#         camera-01  -> camera-01
#         cam 01     -> cam-01
#         CAM/01     -> CAM-01
#     """

#     value = camera_id.strip()

#     value = re.sub(
#         r"[^A-Za-z0-9_.-]+",
#         "-",
#         value,
#     )

#     value = re.sub(
#         r"-+",
#         "-",
#         value,
#     )

#     value = value.strip("-")

#     if not value:
#         raise ValueError(
#             "Camera ID cannot produce a valid agent ID: "
#             f"{camera_id!r}"
#         )

#     return value


# # ============================================================
# # SUPERVISED AGENT
# # ============================================================

# class SupervisedAgent:
#     """
#     Supervises exactly ONE agent subprocess.

#     Every subprocess receives an explicit AGENT_ID environment
#     variable equal to self.agent_id.

#     Failure detectors:

#         1. Unexpected process exit
#         2. Missing first heartbeat
#         3. Heartbeat timeout
#         4. Registry DEAD
#         5. Failed initial startup
#         6. Failed recovery startup

#     All recovery paths converge on recover().

#     Every agent has independent:

#         - subprocess
#         - process monitor
#         - health monitor
#         - restart lock
#         - failure counter
#         - recovery lifecycle

#     Process-generation protection:

#         Every subprocess receives a monotonically increasing
#         generation number.
#     """

#     def __init__(
#         self,
#         config: AgentProcessConfig,
#     ):
#         self.config = config

#         # ----------------------------------------------------
#         # Current subprocess
#         # ----------------------------------------------------

#         self.process: Optional[
#             asyncio.subprocess.Process
#         ] = None

#         # ----------------------------------------------------
#         # Process generation
#         # ----------------------------------------------------

#         self.process_generation = 0

#         # ----------------------------------------------------
#         # Lifecycle
#         # ----------------------------------------------------

#         self.running = False
#         self.intentional_stop = False
#         self.stopping_for_recovery = False

#         # ----------------------------------------------------
#         # Recovery synchronization
#         # ----------------------------------------------------

#         self.restart_lock = asyncio.Lock()
#         self.recovery_in_progress = False

#         # ----------------------------------------------------
#         # Timing
#         # ----------------------------------------------------

#         self.started_at: Optional[float] = None
#         self.healthy_since: Optional[float] = None

#         # ----------------------------------------------------
#         # Failure accounting
#         # ----------------------------------------------------

#         self.consecutive_failures = 0

#         # ----------------------------------------------------
#         # Heartbeat state
#         # ----------------------------------------------------

#         self.heartbeat_timeout_triggered = False
#         self.first_heartbeat_received = False

#     # ========================================================
#     # PROPERTIES
#     # ========================================================

#     @property
#     def agent_id(self) -> str:
#         return self.config.agent_id

#     @property
#     def camera_id(self) -> Optional[str]:
#         return self.config.camera_id

#     @property
#     def camera_source(self) -> Optional[str]:
#         return self.config.camera_source

#     @property
#     def camera_name(self) -> Optional[str]:
#         return self.config.camera_name

#     @property
#     def camera_location(self) -> Optional[str]:
#         return self.config.camera_location

#     @property
#     def script_path(self) -> Path:
#         return PROJECT_ROOT / self.config.script

#     @property
#     def pid(self) -> Optional[int]:
#         if self.process is None:
#             return None

#         return self.process.pid

#     # ========================================================
#     # FAILURE ACCOUNTING
#     # ========================================================

#     def record_failure(self) -> None:
#         self.consecutive_failures += 1

#         print(
#             "[SUPERVISOR] "
#             f"{self.agent_id} consecutive recovery "
#             f"failures: "
#             f"{self.consecutive_failures}/"
#             f"{MAX_CONSECUTIVE_FAILURES}"
#         )

#     def reset_failures_if_healthy(self) -> None:
#         if self.healthy_since is None:
#             return

#         now = asyncio.get_running_loop().time()

#         healthy_duration = (
#             now - self.healthy_since
#         )

#         if (
#             healthy_duration >= HEALTHY_RESET_SECONDS
#             and self.consecutive_failures > 0
#         ):
#             print(
#                 "[SUPERVISOR] "
#                 f"{self.agent_id} remained healthy "
#                 f"for {HEALTHY_RESET_SECONDS:.0f}s. "
#                 "Resetting recovery failure counter."
#             )

#             self.consecutive_failures = 0
#             self.healthy_since = now

#     def can_restart(self) -> bool:
#         return (
#             self.consecutive_failures
#             < MAX_CONSECUTIVE_FAILURES
#         )

#     def get_backoff_delay(self) -> float:
#         exponent = max(
#             0,
#             self.consecutive_failures - 1,
#         )

#         delay = (
#             RESTART_DELAY
#             * (2 ** exponent)
#         )

#         return min(
#             delay,
#             MAX_BACKOFF_SECONDS,
#         )

#     # ========================================================
#     # START
#     # ========================================================

#     async def start(self) -> bool:
#         async with self.restart_lock:
#             return await self._start_without_lock()

#     # ========================================================
#     # INTERNAL START
#     # ========================================================

#     async def _start_without_lock(self) -> bool:
#         """
#         Start a fresh subprocess.

#         IMPORTANT:

#         AGENT_ID is explicitly injected into the child
#         environment on every process creation.
#         """

#         # ----------------------------------------------------
#         # Already running
#         # ----------------------------------------------------

#         if self.process is not None:
#             if self.process.returncode is None:
#                 print(
#                     "[SUPERVISOR] "
#                     f"{self.agent_id} already running "
#                     f"(PID={self.process.pid})"
#                 )

#                 return True

#         # ----------------------------------------------------
#         # Validate script
#         # ----------------------------------------------------

#         if not self.script_path.exists():
#             print(
#                 "[SUPERVISOR] ERROR: "
#                 f"Script does not exist: "
#                 f"{self.script_path}"
#             )

#             self.running = False

#             agent_registry.mark_dead(
#                 self.agent_id
#             )

#             return False

#         # ----------------------------------------------------
#         # New process generation
#         # ----------------------------------------------------

#         self.process_generation += 1

#         generation = self.process_generation

#         # ----------------------------------------------------
#         # Lifecycle
#         # ----------------------------------------------------

#         self.intentional_stop = False
#         self.stopping_for_recovery = False
#         self.running = True

#         loop = asyncio.get_running_loop()

#         self.started_at = loop.time()
#         self.healthy_since = None

#         self.heartbeat_timeout_triggered = False
#         self.first_heartbeat_received = False

#         # ----------------------------------------------------
#         # Registry
#         # ----------------------------------------------------

#         agent_registry.mark_starting(
#             self.agent_id
#         )

#         print(
#             "[SUPERVISOR] "
#             f"Starting {self.agent_id}"
#         )

#         # ----------------------------------------------------
#         # Child environment
#         # ----------------------------------------------------

#         env = os.environ.copy()

#         existing_pythonpath = env.get(
#             "PYTHONPATH",
#             "",
#         )

#         if existing_pythonpath:
#             env["PYTHONPATH"] = (
#                 f"{PROJECT_ROOT}"
#                 f"{os.pathsep}"
#                 f"{existing_pythonpath}"
#             )
#         else:
#             env["PYTHONPATH"] = str(
#                 PROJECT_ROOT
#             )

#         env["PYTHONUNBUFFERED"] = "1"

#         # ----------------------------------------------------
#         # CRITICAL IDENTITY PROPAGATION
#         # ----------------------------------------------------

#         env["AGENT_ID"] = self.agent_id

#         print(
#             "[SUPERVISOR] "
#             f"{self.agent_id} child identity: "
#             f"AGENT_ID={env['AGENT_ID']}"
#         )

#         # ----------------------------------------------------
#         # Camera configuration
#         # ----------------------------------------------------

#         if self.camera_id is not None:
#             env["CAMERA_ID"] = self.camera_id

#             if self.camera_source is not None:
#                 env["CAMERA_SOURCE"] = (
#                     str(self.camera_source)
#                 )

#             if self.camera_name is not None:
#                 env["CAMERA_NAME"] = (
#                     str(self.camera_name)
#                 )

#             if self.camera_location is not None:
#                 env["CAMERA_LOCATION"] = (
#                     str(self.camera_location)
#                 )

#             print(
#                 "[SUPERVISOR] "
#                 f"{self.agent_id} camera configuration: "
#                 f"camera_id={self.camera_id}, "
#                 f"source={self.camera_source or ''}, "
#                 f"name={self.camera_name or ''}, "
#                 f"location={self.camera_location or ''}"
#             )

#         else:
#             # Prevent accidental inheritance of camera
#             # configuration into global agents.

#             env.pop(
#                 "CAMERA_ID",
#                 None,
#             )

#             env.pop(
#                 "CAMERA_SOURCE",
#                 None,
#             )

#             env.pop(
#                 "CAMERA_NAME",
#                 None,
#             )

#             env.pop(
#                 "CAMERA_LOCATION",
#                 None,
#             )

#         # ----------------------------------------------------
#         # HEARTBEAT FAILURE TEST
#         # ----------------------------------------------------

#         heartbeat_test_target = os.getenv(
#             "TEST_HEARTBEAT_FAILURE_AGENT",
#             "",
#         ).strip()

#         if (
#             heartbeat_test_target
#             and heartbeat_test_target == self.agent_id
#         ):
#             env[
#                 "TEST_HEARTBEAT_FAILURE_AGENT"
#             ] = self.agent_id

#             print(
#                 "[SUPERVISOR] "
#                 "HEARTBEAT FAILURE TEST ENABLED "
#                 f"for {self.agent_id}"
#             )

#         else:
#             env.pop(
#                 "TEST_HEARTBEAT_FAILURE_AGENT",
#                 None,
#             )

#         # ----------------------------------------------------
#         # Start subprocess
#         # ----------------------------------------------------

#         try:
#             process = (
#                 await asyncio.create_subprocess_exec(
#                     PYTHON_EXECUTABLE,
#                     "-m",
#                     self._module_name(),
#                     cwd=str(PROJECT_ROOT),
#                     env=env,
#                     stdin=None,
#                     stdout=None,
#                     stderr=None,
#                 )
#             )

#         except Exception as error:
#             self.process = None
#             self.running = False
#             self.started_at = None
#             self.healthy_since = None

#             agent_registry.mark_dead(
#                 self.agent_id
#             )

#             print(
#                 "[SUPERVISOR] "
#                 f"FAILED TO START "
#                 f"{self.agent_id}: "
#                 f"{error}"
#             )

#             return False

#         # ----------------------------------------------------
#         # Publish new process only after successful creation
#         # ----------------------------------------------------

#         self.process = process

#         print(
#             "[SUPERVISOR] "
#             f"{self.agent_id} started "
#             f"(PID={process.pid}, "
#             f"generation={generation})"
#         )

#         return True

#     # ========================================================
#     # MODULE NAME
#     # ========================================================

#     def _module_name(self) -> str:
#         """
#         Convert:

#             agents/detection/main.py

#         into:

#             agents.detection.main
#         """

#         relative = Path(
#             self.config.script
#         )

#         without_suffix = relative.with_suffix("")

#         return ".".join(
#             without_suffix.parts
#         )

#     # ========================================================
#     # STOP
#     # ========================================================

#     async def stop(self) -> None:
#         """
#         Intentionally stop this agent.

#         Process monitor must NOT recover an intentionally
#         stopped process.
#         """

#         self.intentional_stop = True
#         self.stopping_for_recovery = False
#         self.running = False
#         self.recovery_in_progress = False

#         process = self.process

#         if process is None:
#             return

#         if process.returncode is not None:
#             return

#         print(
#             "[SUPERVISOR] "
#             f"Stopping {self.agent_id} "
#             f"(PID={process.pid})"
#         )

#         try:
#             process.terminate()

#             await asyncio.wait_for(
#                 process.wait(),
#                 timeout=10,
#             )

#         except asyncio.TimeoutError:
#             print(
#                 "[SUPERVISOR] "
#                 f"{self.agent_id} did not stop "
#                 "gracefully. Killing."
#             )

#             try:
#                 process.kill()

#                 await asyncio.wait_for(
#                     process.wait(),
#                     timeout=10,
#                 )

#             except Exception as error:
#                 print(
#                     "[SUPERVISOR] "
#                     f"Kill error for "
#                     f"{self.agent_id}: "
#                     f"{error}"
#                 )

#         except ProcessLookupError:
#             pass

#         except Exception as error:
#             print(
#                 "[SUPERVISOR] "
#                 f"Stop error for "
#                 f"{self.agent_id}: "
#                 f"{error}"
#             )

#     # ========================================================
#     # PROCESS EXIT HANDLER
#     # ========================================================

#     async def handle_process_exit(
#         self,
#         return_code: int,
#     ) -> None:
#         """
#         Handle an unexpected process termination.

#         Recovery must NOT be triggered when:

#         1. Operator/application intentionally stopped worker.
#         2. Supervisor is intentionally replacing worker.
#         3. Supervisor recovery is already in progress.
#         """

#         if self.intentional_stop:
#             print(
#                 "[SUPERVISOR] "
#                 f"{self.agent_id} process exit ignored "
#                 "(intentional stop)."
#             )

#             return

#         if self.stopping_for_recovery:
#             print(
#                 "[SUPERVISOR] "
#                 f"{self.agent_id} process exit acknowledged "
#                 "(intentional recovery stop)."
#             )

#             return

#         if self.recovery_in_progress:
#             print(
#                 "[SUPERVISOR] "
#                 f"{self.agent_id} process exit observed "
#                 "while recovery is already in progress. "
#                 "Ignoring duplicate recovery trigger."
#             )

#             return

#         print(
#             "[SUPERVISOR] "
#             f"{self.agent_id} exited "
#             f"(code={return_code})"
#         )

#         self.running = False

#         agent_registry.mark_dead(
#             self.agent_id
#         )

#         await self.recover(
#             reason="process_exit"
#         )

#     # ========================================================
#     # UNIFIED RECOVERY
#     # ========================================================

#     async def recover(
#         self,
#         reason: str,
#     ) -> None:
#         """
#         Single recovery authority.

#         Recovery lifecycle:

#             record failure
#                   ↓
#             mark RECOVERING
#                   ↓
#             stop failed process
#                   ↓
#             clear old process state
#                   ↓
#             exponential backoff
#                   ↓
#             start fresh process
#                   ↓
#             startup success?
#               /          \
#             YES          NO
#              |            |
#              v            v
#           finish      record another
#                       failure + retry

#         Recovery startup failures are retried here.

#         No second recovery mechanism is required.
#         """

#         async with self.restart_lock:

#             # ------------------------------------------------
#             # Operator shutdown
#             # ------------------------------------------------

#             if self.intentional_stop:
#                 return

#             # ------------------------------------------------
#             # Another recovery already owns this agent
#             # ------------------------------------------------

#             if self.recovery_in_progress:
#                 return

#             self.recovery_in_progress = True

#             try:
#                 while not self.intentional_stop:

#                     # ----------------------------------------
#                     # Failure accounting
#                     # ----------------------------------------

#                     self.record_failure()

#                     if not self.can_restart():
#                         print(
#                             "[SUPERVISOR] "
#                             f"Restart limit reached for "
#                             f"{self.agent_id}."
#                         )

#                         print(
#                             "[SUPERVISOR] "
#                             f"{self.agent_id} requires "
#                             "manual intervention."
#                         )

#                         self.running = False

#                         self.process = None

#                         self.started_at = None
#                         self.healthy_since = None

#                         agent_registry.mark_dead(
#                             self.agent_id
#                         )

#                         return

#                     attempt = (
#                         self.consecutive_failures
#                     )

#                     delay = (
#                         self.get_backoff_delay()
#                     )

#                     print(
#                         "[SUPERVISOR] "
#                         f"Recovering {self.agent_id} "
#                         f"(reason={reason}, "
#                         f"attempt={attempt}/"
#                         f"{MAX_CONSECUTIVE_FAILURES}, "
#                         f"backoff={delay:.1f}s)"
#                     )

#                     agent_registry.mark_recovering(
#                         self.agent_id
#                     )

#                     # ----------------------------------------
#                     # Capture exact process being recovered
#                     # ----------------------------------------

#                     process = self.process

#                     recovery_generation = (
#                         self.process_generation
#                     )

#                     # ----------------------------------------
#                     # Mark termination intentional BEFORE
#                     # killing the old process
#                     # ----------------------------------------

#                     self.stopping_for_recovery = True

#                     if process is not None:

#                         if process.returncode is None:

#                             print(
#                                 "[SUPERVISOR] "
#                                 f"Stopping unresponsive "
#                                 f"{self.agent_id} "
#                                 f"(PID={process.pid}, "
#                                 f"generation="
#                                 f"{recovery_generation})"
#                             )

#                             try:
#                                 process.kill()

#                                 await asyncio.wait_for(
#                                     process.wait(),
#                                     timeout=10,
#                                 )

#                             except ProcessLookupError:
#                                 pass

#                             except asyncio.TimeoutError:
#                                 print(
#                                     "[SUPERVISOR] "
#                                     f"Timed out waiting for "
#                                     f"{self.agent_id} "
#                                     "to terminate."
#                                 )

#                             except Exception as error:
#                                 print(
#                                     "[SUPERVISOR] "
#                                     f"Failed to stop "
#                                     f"{self.agent_id}: "
#                                     f"{error}"
#                                 )

#                     # ----------------------------------------
#                     # Clear old process state
#                     # ----------------------------------------

#                     if (
#                         self.process is process
#                         and self.process_generation
#                         == recovery_generation
#                     ):
#                         self.process = None

#                     self.started_at = None
#                     self.healthy_since = None

#                     self.heartbeat_timeout_triggered = False
#                     self.first_heartbeat_received = False

#                     # ----------------------------------------
#                     # Recovery backoff
#                     # ----------------------------------------

#                     try:
#                         await asyncio.sleep(delay)
#                     finally:
#                         pass

#                     if self.intentional_stop:
#                         return

#                     # ----------------------------------------
#                     # Prepare fresh process
#                     # ----------------------------------------

#                     self.stopping_for_recovery = False
#                     self.running = True

#                     # ----------------------------------------
#                     # Fresh process
#                     # ----------------------------------------

#                     started = (
#                         await self._start_without_lock()
#                     )

#                     if started:
#                         print(
#                             "[SUPERVISOR] "
#                             f"{self.agent_id} recovery "
#                             "process started successfully."
#                         )

#                         return

#                     # ----------------------------------------
#                     # IMPORTANT:
#                     #
#                     # Startup failed.
#                     #
#                     # _start_without_lock() sets running=False.
#                     #
#                     # Do NOT return here.
#                     #
#                     # Re-enter the same recovery loop so the
#                     # agent receives another isolated retry.
#                     # ----------------------------------------

#                     print(
#                         "[SUPERVISOR] "
#                         f"Recovery start failed for "
#                         f"{self.agent_id}. "
#                         "Retrying through the same recovery "
#                         "authority."
#                     )

#                     self.running = True
#                     self.process = None

#                     agent_registry.mark_dead(
#                         self.agent_id
#                     )

#                     # Continue loop.
#                     #
#                     # The next iteration records another failure,
#                     # calculates a larger backoff, and retries.

#             finally:
#                 self.stopping_for_recovery = False
#                 self.recovery_in_progress = False

#     # ========================================================
#     # PROCESS MONITOR
#     # ========================================================

#     async def monitor_process(self) -> None:
#         """
#         Continuously monitor this agent's subprocess.

#         The task remains alive for the lifetime of the
#         supervisor.

#         It monitors the exact process object + generation.
#         """

#         observed_generation: Optional[int] = None

#         observed_process: Optional[
#             asyncio.subprocess.Process
#         ] = None

#         while self.running:

#             process = self.process

#             # ------------------------------------------------
#             # No current process
#             # ------------------------------------------------

#             if process is None:
#                 observed_process = None
#                 observed_generation = None

#                 await asyncio.sleep(0.2)

#                 continue

#             current_generation = (
#                 self.process_generation
#             )

#             # ------------------------------------------------
#             # New process detected
#             # ------------------------------------------------

#             if (
#                 observed_process is not process
#                 or observed_generation
#                 != current_generation
#             ):
#                 observed_process = process

#                 observed_generation = (
#                     current_generation
#                 )

#             # ------------------------------------------------
#             # Wait for exact process
#             # ------------------------------------------------

#             try:
#                 return_code = await process.wait()

#             except asyncio.CancelledError:
#                 raise

#             except Exception as error:
#                 print(
#                     "[SUPERVISOR] "
#                     f"Process monitor error for "
#                     f"{self.agent_id}: "
#                     f"{error}"
#                 )

#                 await asyncio.sleep(1)

#                 continue

#             # ------------------------------------------------
#             # Supervisor/operator shutdown
#             # ------------------------------------------------

#             if not self.running:
#                 return

#             # ------------------------------------------------
#             # STALE PROCESS PROTECTION
#             # ------------------------------------------------

#             if (
#                 self.process is not process
#                 or self.process_generation
#                 != observed_generation
#             ):
#                 continue

#             # ------------------------------------------------
#             # Intentional recovery stop
#             # ------------------------------------------------

#             if self.stopping_for_recovery:
#                 print(
#                     "[SUPERVISOR] "
#                     f"{self.agent_id} process exited "
#                     "during intentional recovery stop."
#                 )

#                 old_process = process

#                 old_generation = (
#                     observed_generation
#                 )

#                 while self.running:

#                     current_process = self.process

#                     current_generation = (
#                         self.process_generation
#                     )

#                     if (
#                         current_process is not old_process
#                         or current_generation
#                         != old_generation
#                     ):
#                         break

#                     await asyncio.sleep(0.2)

#                 observed_process = None
#                 observed_generation = None

#                 continue

#             # ------------------------------------------------
#             # Recovery already owns lifecycle
#             # ------------------------------------------------

#             if self.recovery_in_progress:
#                 print(
#                     "[SUPERVISOR] "
#                     f"{self.agent_id} process exited "
#                     "while recovery is in progress."
#                 )

#                 old_process = process

#                 old_generation = (
#                     observed_generation
#                 )

#                 while self.running:

#                     current_process = self.process

#                     current_generation = (
#                         self.process_generation
#                     )

#                     if (
#                         current_process is not old_process
#                         or current_generation
#                         != old_generation
#                     ):
#                         break

#                     await asyncio.sleep(0.2)

#                 observed_process = None
#                 observed_generation = None

#                 continue

#             # ------------------------------------------------
#             # Genuine unexpected process exit
#             # ------------------------------------------------

#             await self.handle_process_exit(
#                 return_code
#             )

#             # ------------------------------------------------
#             # Recovery may have replaced process
#             # ------------------------------------------------

#             observed_process = None
#             observed_generation = None

#     # ========================================================
#     # HEARTBEAT AGE
#     # ========================================================

#     def get_heartbeat_age(
#         self,
#         agent: dict,
#     ) -> Optional[float]:

#         last_heartbeat = agent.get(
#             "last_heartbeat"
#         )

#         if last_heartbeat is None:
#             return None

#         try:

#             if last_heartbeat.tzinfo is None:
#                 last_heartbeat = (
#                     last_heartbeat.replace(
#                         tzinfo=timezone.utc
#                     )
#                 )

#             now = datetime.now(
#                 timezone.utc
#             )

#             age = (
#                 now - last_heartbeat
#             ).total_seconds()

#             return max(
#                 0.0,
#                 age,
#             )

#         except Exception as error:
#             print(
#                 "[SUPERVISOR] "
#                 f"Heartbeat timestamp error for "
#                 f"{self.agent_id}: "
#                 f"{error}"
#             )

#             return None

#     # ========================================================
#     # HEARTBEAT TIMEOUT
#     # ========================================================

#     def check_heartbeat_timeout(
#         self,
#         agent: dict,
#     ) -> str:

#         heartbeat_age = (
#             self.get_heartbeat_age(
#                 agent
#             )
#         )

#         if heartbeat_age is None:
#             return "missing"

#         if heartbeat_age <= HEARTBEAT_TIMEOUT:
#             return "healthy"

#         return "timeout"

#     # ========================================================
#     # HEALTH CHECK
#     # ========================================================

#     async def check_health(self) -> None:

#         if not self.running:
#             return

#         process = self.process

#         # ----------------------------------------------------
#         # Missing process while supervisor expects worker
#         # ----------------------------------------------------

#         if process is None:

#             if self.recovery_in_progress:
#                 return

#             if self.intentional_stop:
#                 return

#             print(
#                 "[SUPERVISOR] "
#                 f"{self.agent_id} has no active "
#                 "process while marked running."
#             )

#             await self.recover(
#                 reason="missing_process"
#             )

#             return

#         # ----------------------------------------------------
#         # Process already exited
#         # ----------------------------------------------------

#         if process.returncode is not None:

#             if self.recovery_in_progress:
#                 return

#             return

#         # ----------------------------------------------------
#         # Startup timestamp unavailable
#         # ----------------------------------------------------

#         if self.started_at is None:
#             return

#         # ----------------------------------------------------
#         # Recovery owns lifecycle
#         # ----------------------------------------------------

#         if self.recovery_in_progress:
#             return

#         loop = asyncio.get_running_loop()

#         now = loop.time()

#         age_since_start = (
#             now - self.started_at
#         )

#         # ----------------------------------------------------
#         # Registry state
#         # ----------------------------------------------------

#         agent = agent_registry.get_agent(
#             self.agent_id
#         )

#         if agent is None:
#             return

#         status = agent.get(
#             "status"
#         )

#         # ----------------------------------------------------
#         # Startup grace period
#         # ----------------------------------------------------

#         if (
#             age_since_start
#             < STARTUP_GRACE_PERIOD
#         ):
#             return

#         # ----------------------------------------------------
#         # Heartbeat state
#         # ----------------------------------------------------

#         heartbeat_state = (
#             self.check_heartbeat_timeout(
#                 agent
#             )
#         )

#         # ----------------------------------------------------
#         # First heartbeat never arrived
#         # ----------------------------------------------------

#         if heartbeat_state == "missing":

#             if not self.first_heartbeat_received:

#                 print(
#                     "[SUPERVISOR] "
#                     "FIRST HEARTBEAT TIMEOUT: "
#                     f"{self.agent_id} "
#                     f"(startup_age="
#                     f"{age_since_start:.1f}s, "
#                     f"grace="
#                     f"{STARTUP_GRACE_PERIOD:.1f}s)"
#                 )

#                 agent_registry.mark_dead(
#                     self.agent_id
#                 )

#                 await self.recover(
#                     reason="missing_first_heartbeat"
#                 )

#             return

#         # ----------------------------------------------------
#         # Heartbeat arrived
#         # ----------------------------------------------------

#         self.first_heartbeat_received = True

#         # ----------------------------------------------------
#         # Heartbeat timeout
#         # ----------------------------------------------------

#         if heartbeat_state == "timeout":

#             if not self.heartbeat_timeout_triggered:

#                 self.heartbeat_timeout_triggered = True

#                 heartbeat_age = (
#                     self.get_heartbeat_age(
#                         agent
#                     )
#                 )

#                 print(
#                     "[SUPERVISOR] "
#                     "HEARTBEAT TIMEOUT: "
#                     f"{self.agent_id} "
#                     f"(age="
#                     f"{heartbeat_age:.1f}s, "
#                     f"timeout="
#                     f"{HEARTBEAT_TIMEOUT:.1f}s)"
#                 )

#                 agent_registry.mark_dead(
#                     self.agent_id
#                 )

#                 await self.recover(
#                     reason="heartbeat_timeout"
#                 )

#             return

#         # ----------------------------------------------------
#         # Registry explicitly DEAD
#         # ----------------------------------------------------

#         if status == "DEAD":

#             if self.recovery_in_progress:
#                 return

#             print(
#                 "[SUPERVISOR] "
#                 f"Heartbeat failure detected for "
#                 f"{self.agent_id}"
#             )

#             await self.recover(
#                 reason="registry_dead"
#             )

#             return

#         # ----------------------------------------------------
#         # Starting / recovering
#         # ----------------------------------------------------

#         if status in (
#             "STARTING",
#             "RECOVERING",
#         ):
#             return

#         # ----------------------------------------------------
#         # Healthy
#         # ----------------------------------------------------

#         if status == "ALIVE":

#             if self.healthy_since is None:
#                 self.healthy_since = now

#             self.reset_failures_if_healthy()

#             return

#         # ----------------------------------------------------
#         # Unknown state
#         # ----------------------------------------------------

#         print(
#             "[SUPERVISOR] "
#             f"{self.agent_id} unexpected "
#             f"registry status: {status}"
#         )

#     # ========================================================
#     # HEALTH LOOP
#     # ========================================================

#     async def health_loop(self) -> None:

#         while self.running:

#             try:

#                 await self.check_health()

#                 await asyncio.sleep(
#                     HEALTH_CHECK_INTERVAL
#                 )

#             except asyncio.CancelledError:
#                 raise

#             except Exception as error:

#                 print(
#                     "[SUPERVISOR] "
#                     f"Health loop error for "
#                     f"{self.agent_id}: "
#                     f"{error}"
#                 )

#                 await asyncio.sleep(2)


# # ============================================================
# # AGENT SUPERVISOR
# # ============================================================

# class AgentSupervisor:
#     """
#     Supervises all configured production agents.

#     Camera-bound detection workers are created independently
#     for every enabled camera.

#     Example:

#         CAM01 -> person-detector-CAM01
#         CAM02 -> person-detector-CAM02
#         CAM03 -> person-detector-CAM03

#     Global downstream workers remain shared.
#     """

#     def __init__(self):

#         self.camera_registry = (
#             CameraRegistry.from_environment()
#         )

#         self.agents: dict[
#             str,
#             SupervisedAgent,
#         ] = {}

#         self.running = False

#         self.monitor_tasks: list[
#             asyncio.Task
#         ] = []

#         self.health_tasks: list[
#             asyncio.Task
#         ] = []

#         self._build_agent_configuration()

#     # ========================================================
#     # BUILD CONFIGURATION
#     # ========================================================

#     def _build_agent_configuration(self) -> None:

#         enabled_cameras = (
#             self.camera_registry.get_enabled()
#         )

#         if not enabled_cameras:
#             print(
#                 "[SUPERVISOR] WARNING: "
#                 "No enabled cameras configured."
#             )

#         # ----------------------------------------------------
#         # Create ONE detector per enabled camera
#         # ----------------------------------------------------

#         for camera in enabled_cameras:

#             camera_component = (
#                 _safe_agent_id_component(
#                     camera.camera_id
#                 )
#             )

#             detector_agent_id = (
#                 f"person-detector-"
#                 f"{camera_component}"
#             )

#             detection_config = AgentProcessConfig(
#                 name="detection",
#                 agent_id=detector_agent_id,
#                 script="agents/detection/main.py",
#                 camera_id=camera.camera_id,
#                 camera_source=str(
#                     camera.source
#                 ),
#                 camera_name=camera.name,
#                 camera_location=camera.location,
#             )

#             if detector_agent_id in self.agents:
#                 raise ValueError(
#                     "Duplicate supervised agent ID "
#                     f"generated for camera "
#                     f"{camera.camera_id}: "
#                     f"{detector_agent_id}"
#                 )

#             self.agents[
#                 detector_agent_id
#             ] = SupervisedAgent(
#                 detection_config
#             )

#         # ----------------------------------------------------
#         # Global agents
#         # ----------------------------------------------------

#         for config in GLOBAL_PRODUCTION_AGENTS:

#             if config.agent_id in self.agents:
#                 raise ValueError(
#                     "Duplicate supervised agent ID: "
#                     f"{config.agent_id}"
#                 )

#             self.agents[
#                 config.agent_id
#             ] = SupervisedAgent(
#                 config
#             )

#     # ========================================================
#     # START ALL
#     # ========================================================

#     async def start_all(self) -> None:

#         print("=" * 70)
#         print("AGENT SUPERVISOR")
#         print("=" * 70)

#         print(
#             "[SUPERVISOR] "
#             f"Python: {PYTHON_EXECUTABLE}"
#         )

#         print(
#             "[SUPERVISOR] "
#             f"Project root: {PROJECT_ROOT}"
#         )

#         print(
#             "[SUPERVISOR] "
#             f"Production agents: "
#             f"{len(self.agents)}"
#         )

#         # ----------------------------------------------------
#         # Camera information
#         # ----------------------------------------------------

#         all_cameras = (
#             self.camera_registry.get_all()
#         )

#         enabled_cameras = (
#             self.camera_registry.get_enabled()
#         )

#         print(
#             "[SUPERVISOR] "
#             f"Configured cameras: "
#             f"{len(all_cameras)}"
#         )

#         print(
#             "[SUPERVISOR] "
#             f"Enabled cameras: "
#             f"{len(enabled_cameras)}"
#         )

#         for camera in enabled_cameras:

#             print(
#                 "[SUPERVISOR] "
#                 f"Camera: "
#                 f"{camera.camera_id} | "
#                 f"name={camera.name} | "
#                 f"source={camera.source} | "
#                 f"location={camera.location}"
#             )

#             detector_agent_id = (
#                 f"person-detector-"
#                 f"{_safe_agent_id_component(camera.camera_id)}"
#             )

#             print(
#                 "[SUPERVISOR] "
#                 f"Camera affinity: "
#                 f"{camera.camera_id} -> "
#                 f"{detector_agent_id}"
#             )

#         # ----------------------------------------------------
#         # Health configuration
#         # ----------------------------------------------------

#         print(
#             "[SUPERVISOR] "
#             f"Heartbeat timeout: "
#             f"{HEARTBEAT_TIMEOUT:.1f}s"
#         )

#         print(
#             "[SUPERVISOR] "
#             f"Startup grace period: "
#             f"{STARTUP_GRACE_PERIOD:.1f}s"
#         )

#         # ----------------------------------------------------
#         # Heartbeat failure-test configuration
#         # ----------------------------------------------------

#         heartbeat_test_target = os.getenv(
#             "TEST_HEARTBEAT_FAILURE_AGENT",
#             "",
#         ).strip()

#         if heartbeat_test_target:

#             print(
#                 "[SUPERVISOR] "
#                 "Heartbeat failure test target: "
#                 f"{heartbeat_test_target}"
#             )

#         print("=" * 70)

#         self.running = True

#         # ----------------------------------------------------
#         # Start every agent independently
#         # ----------------------------------------------------

#         for agent in self.agents.values():

#             try:

#                 started = await agent.start()

#                 if not started:

#                     print(
#                         "[SUPERVISOR] "
#                         f"{agent.agent_id} failed "
#                         "initial startup. "
#                         "Scheduling automatic recovery."
#                     )

#                     agent.running = False

#                     asyncio.create_task(
#                         agent.recover(
#                             reason="initial_startup_failure"
#                         ),
#                         name=(
#                             f"initial-recovery-"
#                             f"{agent.agent_id}"
#                         ),
#                     )

#             except Exception as error:

#                 print(
#                     "[SUPERVISOR] "
#                     f"Failed to start "
#                     f"{agent.agent_id}: "
#                     f"{error}"
#                 )

#                 agent.running = False

#                 asyncio.create_task(
#                     agent.recover(
#                         reason="initial_startup_exception"
#                     ),
#                     name=(
#                         f"initial-recovery-"
#                         f"{agent.agent_id}"
#                     ),
#                 )

#             await asyncio.sleep(
#                 STARTUP_DELAY
#             )

#         # ----------------------------------------------------
#         # Process monitors
#         # ----------------------------------------------------

#         for agent in self.agents.values():

#             task = asyncio.create_task(
#                 agent.monitor_process(),
#                 name=(
#                     f"monitor-process-"
#                     f"{agent.agent_id}"
#                 ),
#             )

#             self.monitor_tasks.append(
#                 task
#             )

#         # ----------------------------------------------------
#         # Health monitors
#         # ----------------------------------------------------

#         for agent in self.agents.values():

#             task = asyncio.create_task(
#                 agent.health_loop(),
#                 name=(
#                     f"health-monitor-"
#                     f"{agent.agent_id}"
#                 ),
#             )

#             self.health_tasks.append(
#                 task
#             )

#         print(
#             "[SUPERVISOR] "
#             "All process monitors started."
#         )

#         print(
#             "[SUPERVISOR] "
#             "All health monitors started."
#         )

#     # ========================================================
#     # STOP ALL
#     # ========================================================

#     async def stop_all(self) -> None:

#         if not self.running:
#             return

#         print(
#             "[SUPERVISOR] "
#             "Shutdown requested."
#         )

#         self.running = False

#         # ----------------------------------------------------
#         # Mark intentional stop BEFORE cancelling monitors
#         # ----------------------------------------------------

#         for agent in self.agents.values():

#             agent.running = False
#             agent.intentional_stop = True
#             agent.stopping_for_recovery = False

#         # ----------------------------------------------------
#         # Cancel process monitors
#         # ----------------------------------------------------

#         for task in self.monitor_tasks:
#             task.cancel()

#         if self.monitor_tasks:

#             await asyncio.gather(
#                 *self.monitor_tasks,
#                 return_exceptions=True,
#             )

#         self.monitor_tasks.clear()

#         # ----------------------------------------------------
#         # Cancel health monitors
#         # ----------------------------------------------------

#         for task in self.health_tasks:
#             task.cancel()

#         if self.health_tasks:

#             await asyncio.gather(
#                 *self.health_tasks,
#                 return_exceptions=True,
#             )

#         self.health_tasks.clear()

#         # ----------------------------------------------------
#         # Stop processes independently
#         # ----------------------------------------------------

#         for agent in self.agents.values():

#             try:

#                 await agent.stop()

#             except Exception as error:

#                 print(
#                     "[SUPERVISOR] "
#                     f"Shutdown error for "
#                     f"{agent.agent_id}: "
#                     f"{error}"
#                 )

#         print(
#             "[SUPERVISOR] "
#             "All agents stopped."
#         )


# # ============================================================
# # STANDALONE MAIN
# # ============================================================

# async def main():

#     supervisor = AgentSupervisor()

#     try:

#         await supervisor.start_all()

#         while supervisor.running:
#             await asyncio.sleep(1)

#     except asyncio.CancelledError:
#         raise

#     finally:
#         await supervisor.stop_all()


# # ============================================================
# # ENTRY POINT
# # ============================================================

# if __name__ == "__main__":

#     try:

#         asyncio.run(main())

#     except KeyboardInterrupt:

#         print(
#             "\n[SUPERVISOR] "
#             "Stopped by operator."
#         )





























































"""
Per-agent process supervisor.

Responsibilities
----------------
- Start production agents as isolated subprocesses.
- Create one camera-bound detection worker per enabled camera.
- Provide camera and agent identity configuration to subprocesses.
- Monitor process lifetime.
- Monitor heartbeat health.
- Recover only the failed agent.
- Prevent concurrent recovery of the same agent.
- Apply exponential restart backoff.
- Limit repeated restart failures.
- Respect startup grace periods.
- Automatically retry failed startup/recovery.
- Keep one agent failure isolated from all other agents.

Multi-camera model
------------------
For every enabled camera:

    CAM01 -> person-detector-CAM01
    CAM02 -> person-detector-CAM02
    CAM03 -> person-detector-CAM03

Each detector has its own:
    - subprocess
    - process monitor
    - health monitor
    - restart lock
    - failure counter
    - recovery lifecycle
    - camera configuration
    - agent identity

Global downstream agents remain shared:

    tracker-01
    behavior-01
    crowd-01
    security-01
    alert-01
    incident-01
    evidence-01

Those agents consume events from all cameras and are responsible for
maintaining camera-partitioned state where appropriate.

Fault isolation
---------------
A failure in:

    CAM01 detector

must NOT terminate or restart:

    CAM02 detector
    CAM03 detector
    tracker
    behavior
    crowd
    security
    alert
    incident
    evidence

Recovery model
--------------
Unexpected process exit
        |
        v
handle_process_exit()
        |
        v
recover()

Heartbeat timeout
        |
        v
recover()

Startup failure
        |
        v
recover()

All recovery paths converge on exactly one recovery authority:

    recover()

Recovery startup failures are retried by recover() itself.

Process-generation protection
-----------------------------
Every subprocess start creates a new process generation.

A monitor waiting on an older process can never act on or interfere
with a newer replacement process.

Important architecture note
---------------------------
Heartbeat timestamps are supplied by the shared agent_registry,
which is normally updated by the heartbeat consumer.

The complete production monitoring stack should therefore run:

    AgentSupervisor
          +
    Heartbeat Consumer
          +
    Watchdog

inside the unified monitoring service.
"""

from __future__ import annotations

import asyncio
import os
import re
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
    Configuration for one supervised subprocess.

    camera_id and camera_source are used only for
    camera-bound workers.

    camera_name and camera_location are optional metadata
    passed to camera-bound workers for camera-aware
    policies and context.
    """

    name: str
    agent_id: str
    script: str
    camera_id: Optional[str] = None
    camera_source: Optional[str] = None
    camera_name: Optional[str] = None
    camera_location: Optional[str] = None


# ============================================================
# GLOBAL PRODUCTION AGENTS
# ============================================================

GLOBAL_PRODUCTION_AGENTS = [
    AgentProcessConfig(
        name="tracker",
        agent_id="tracker-01",
        script="agents/tracker/main.py",
    ),
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
    """
    Convert a camera ID into a safe process/agent identifier.

    Examples:
        CAM01      -> CAM01
        camera-01  -> camera-01
        cam 01     -> cam-01
        CAM/01     -> CAM-01
    """

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
    Supervises exactly ONE agent subprocess.

    Every subprocess receives an explicit AGENT_ID environment
    variable equal to self.agent_id.

    Failure detectors:
        1. Unexpected process exit
        2. Missing first heartbeat
        3. Heartbeat timeout
        4. Registry DEAD
        5. Failed initial startup
        6. Failed recovery startup

    All recovery paths converge on recover().

    Every agent has independent:
        - subprocess
        - process monitor
        - health monitor
        - restart lock
        - failure counter
        - recovery lifecycle

    Process-generation protection:
        Every subprocess receives a monotonically increasing
        generation number.
    """

    def __init__(
        self,
        config: AgentProcessConfig,
    ):
        self.config = config

        # ----------------------------------------------------
        # Current subprocess
        # ----------------------------------------------------

        self.process: Optional[
            asyncio.subprocess.Process
        ] = None

        # ----------------------------------------------------
        # Process generation
        # ----------------------------------------------------

        self.process_generation = 0

        # ----------------------------------------------------
        # Lifecycle
        # ----------------------------------------------------

        # running means the supervisor expects this worker
        # to be active or recovering.
        #
        # It does NOT necessarily mean that a subprocess
        # currently exists.
        self.running = False

        self.intentional_stop = False
        self.stopping_for_recovery = False

        # ----------------------------------------------------
        # Recovery synchronization
        # ----------------------------------------------------

        self.restart_lock = asyncio.Lock()
        self.recovery_in_progress = False

        # ----------------------------------------------------
        # Timing
        # ----------------------------------------------------

        self.started_at: Optional[float] = None
        self.healthy_since: Optional[float] = None

        # ----------------------------------------------------
        # Failure accounting
        # ----------------------------------------------------

        self.consecutive_failures = 0

        # ----------------------------------------------------
        # Heartbeat state
        # ----------------------------------------------------

        self.heartbeat_timeout_triggered = False
        self.first_heartbeat_received = False

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
        if self.process is None:
            return None

        return self.process.pid

    # ========================================================
    # FAILURE ACCOUNTING
    # ========================================================

    def record_failure(self) -> None:
        self.consecutive_failures += 1

        print(
            "[SUPERVISOR] "
            f"{self.agent_id} consecutive recovery "
            f"failures: "
            f"{self.consecutive_failures}/"
            f"{MAX_CONSECUTIVE_FAILURES}"
        )

    def reset_failures_if_healthy(self) -> None:
        if self.healthy_since is None:
            return

        now = asyncio.get_running_loop().time()

        healthy_duration = (
            now - self.healthy_since
        )

        if (
            healthy_duration >= HEALTHY_RESET_SECONDS
            and self.consecutive_failures > 0
        ):
            print(
                "[SUPERVISOR] "
                f"{self.agent_id} remained healthy "
                f"for {HEALTHY_RESET_SECONDS:.0f}s. "
                "Resetting recovery failure counter."
            )

            self.consecutive_failures = 0
            self.healthy_since = now

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
    # START
    # ========================================================

    async def start(self) -> bool:
        async with self.restart_lock:
            return await self._start_without_lock()

    # ========================================================
    # INTERNAL START
    # ========================================================

    async def _start_without_lock(self) -> bool:
        """
        Start a fresh subprocess.

        IMPORTANT:
        AGENT_ID is explicitly injected into the child
        environment on every process creation.
        """

        # ----------------------------------------------------
        # Already running
        # ----------------------------------------------------

        if self.process is not None:
            if self.process.returncode is None:
                print(
                    "[SUPERVISOR] "
                    f"{self.agent_id} already running "
                    f"(PID={self.process.pid})"
                )

                self.running = True

                return True

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
            self.healthy_since = None

            agent_registry.mark_dead(
                self.agent_id
            )

            return False

        # ----------------------------------------------------
        # New process generation
        # ----------------------------------------------------

        self.process_generation += 1

        generation = self.process_generation

        # ----------------------------------------------------
        # Lifecycle
        # ----------------------------------------------------

        self.intentional_stop = False
        self.stopping_for_recovery = False
        self.running = True

        loop = asyncio.get_running_loop()

        self.started_at = loop.time()
        self.healthy_since = None

        self.heartbeat_timeout_triggered = False
        self.first_heartbeat_received = False

        # ----------------------------------------------------
        # Registry
        # ----------------------------------------------------

        agent_registry.mark_starting(
            self.agent_id
        )

        print(
            "[SUPERVISOR] "
            f"Starting {self.agent_id}"
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
        # CRITICAL IDENTITY PROPAGATION
        # ----------------------------------------------------

        env["AGENT_ID"] = self.agent_id

        print(
            "[SUPERVISOR] "
            f"{self.agent_id} child identity: "
            f"AGENT_ID={env['AGENT_ID']}"
        )

        # ----------------------------------------------------
        # Camera configuration
        # ----------------------------------------------------

        if self.camera_id is not None:
            env["CAMERA_ID"] = self.camera_id

            if self.camera_source is not None:
                env["CAMERA_SOURCE"] = (
                    str(self.camera_source)
                )

            if self.camera_name is not None:
                env["CAMERA_NAME"] = (
                    str(self.camera_name)
                )

            if self.camera_location is not None:
                env["CAMERA_LOCATION"] = (
                    str(self.camera_location)
                )

            print(
                "[SUPERVISOR] "
                f"{self.agent_id} camera configuration: "
                f"camera_id={self.camera_id}, "
                f"source={self.camera_source or ''}, "
                f"name={self.camera_name or ''}, "
                f"location={self.camera_location or ''}"
            )

        else:
            # Prevent accidental inheritance of camera
            # configuration into global agents.
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
        # HEARTBEAT FAILURE TEST
        # ----------------------------------------------------

        heartbeat_test_target = os.getenv(
            "TEST_HEARTBEAT_FAILURE_AGENT",
            "",
        ).strip()

        if (
            heartbeat_test_target
            and heartbeat_test_target == self.agent_id
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
        # Start subprocess
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

        except Exception as error:
            self.process = None
            self.running = False
            self.started_at = None
            self.healthy_since = None

            agent_registry.mark_dead(
                self.agent_id
            )

            print(
                "[SUPERVISOR] "
                f"FAILED TO START "
                f"{self.agent_id}: "
                f"{error}"
            )

            return False

        # ----------------------------------------------------
        # Publish new process only after successful creation
        # ----------------------------------------------------

        self.process = process

        print(
            "[SUPERVISOR] "
            f"{self.agent_id} started "
            f"(PID={process.pid}, "
            f"generation={generation})"
        )

        return True

    # ========================================================
    # MODULE NAME
    # ========================================================

    def _module_name(self) -> str:
        """
        Convert:

            agents/detection/main.py

        into:

            agents.detection.main
        """

        relative = Path(
            self.config.script
        )

        without_suffix = relative.with_suffix("")

        return ".".join(
            without_suffix.parts
        )

    # ========================================================
    # STOP
    # ========================================================

    async def stop(self) -> None:
        """
        Intentionally stop this agent.

        Process monitor must NOT recover an intentionally
        stopped process.
        """

        self.intentional_stop = True
        self.stopping_for_recovery = False
        self.running = False
        self.recovery_in_progress = False

        process = self.process

        if process is None:
            return

        if process.returncode is not None:
            return

        print(
            "[SUPERVISOR] "
            f"Stopping {self.agent_id} "
            f"(PID={process.pid})"
        )

        try:
            process.terminate()

            await asyncio.wait_for(
                process.wait(),
                timeout=10,
            )

        except asyncio.TimeoutError:
            print(
                "[SUPERVISOR] "
                f"{self.agent_id} did not stop "
                "gracefully. Killing."
            )

            try:
                process.kill()

                await asyncio.wait_for(
                    process.wait(),
                    timeout=10,
                )

            except Exception as error:
                print(
                    "[SUPERVISOR] "
                    f"Kill error for "
                    f"{self.agent_id}: "
                    f"{error}"
                )

        except ProcessLookupError:
            pass

        except Exception as error:
            print(
                "[SUPERVISOR] "
                f"Stop error for "
                f"{self.agent_id}: "
                f"{error}"
            )

    # ========================================================
    # PROCESS EXIT HANDLER
    # ========================================================

    async def handle_process_exit(
        self,
        return_code: int,
    ) -> None:
        """
        Handle an unexpected process termination.

        Recovery must NOT be triggered when:

        1. Operator/application intentionally stopped worker.
        2. Supervisor is intentionally replacing worker.
        3. Supervisor recovery is already in progress.
        """

        if self.intentional_stop:
            print(
                "[SUPERVISOR] "
                f"{self.agent_id} process exit ignored "
                "(intentional stop)."
            )

            return

        if self.stopping_for_recovery:
            print(
                "[SUPERVISOR] "
                f"{self.agent_id} process exit acknowledged "
                "(intentional recovery stop)."
            )

            return

        if self.recovery_in_progress:
            print(
                "[SUPERVISOR] "
                f"{self.agent_id} process exit observed "
                "while recovery is already in progress. "
                "Ignoring duplicate recovery trigger."
            )

            return

        print(
            "[SUPERVISOR] "
            f"{self.agent_id} exited "
            f"(code={return_code})"
        )

        # IMPORTANT:
        #
        # Do NOT set self.running=False here.
        #
        # running means the supervisor expects this worker
        # to exist or be recovering.
        #
        # Setting it False can terminate the health loop
        # while recovery is starting.
        #
        self.running = True

        agent_registry.mark_dead(
            self.agent_id
        )

        await self.recover(
            reason="process_exit"
        )

    # ========================================================
    # UNIFIED RECOVERY
    # ========================================================

    async def recover(
        self,
        reason: str,
    ) -> None:
        """
        Single recovery authority.

        Recovery lifecycle:

            record failure
                  ↓
            mark RECOVERING
                  ↓
            stop failed process
                  ↓
            clear old process state
                  ↓
            exponential backoff
                  ↓
            start fresh process
                  ↓
            startup success?
              /          \
            YES          NO
             |            |
             v            v
          finish      record another
                      failure + retry

        Recovery startup failures are retried here.

        No second recovery mechanism is required.
        """

        async with self.restart_lock:

            # ------------------------------------------------
            # Operator shutdown
            # ------------------------------------------------

            if self.intentional_stop:
                return

            # ------------------------------------------------
            # Another recovery already owns this agent
            # ------------------------------------------------

            if self.recovery_in_progress:
                return

            self.recovery_in_progress = True

            try:
                while not self.intentional_stop:

                    # ----------------------------------------
                    # The supervisor remains responsible for
                    # this agent during the entire recovery.
                    # ----------------------------------------

                    self.running = True

                    # ----------------------------------------
                    # Failure accounting
                    # ----------------------------------------

                    self.record_failure()

                    if not self.can_restart():
                        print(
                            "[SUPERVISOR] "
                            f"Restart limit reached for "
                            f"{self.agent_id}."
                        )

                        print(
                            "[SUPERVISOR] "
                            f"{self.agent_id} requires "
                            "manual intervention."
                        )

                        self.running = False
                        self.process = None
                        self.started_at = None
                        self.healthy_since = None

                        agent_registry.mark_dead(
                            self.agent_id
                        )

                        return

                    attempt = (
                        self.consecutive_failures
                    )

                    delay = (
                        self.get_backoff_delay()
                    )

                    print(
                        "[SUPERVISOR] "
                        f"Recovering {self.agent_id} "
                        f"(reason={reason}, "
                        f"attempt={attempt}/"
                        f"{MAX_CONSECUTIVE_FAILURES}, "
                        f"backoff={delay:.1f}s)"
                    )

                    agent_registry.mark_recovering(
                        self.agent_id
                    )

                    # ----------------------------------------
                    # Capture exact process being recovered
                    # ----------------------------------------

                    process = self.process

                    recovery_generation = (
                        self.process_generation
                    )

                    # ----------------------------------------
                    # Mark termination intentional BEFORE
                    # killing the old process.
                    # ----------------------------------------

                    self.stopping_for_recovery = True

                    if process is not None:
                        if process.returncode is None:
                            print(
                                "[SUPERVISOR] "
                                f"Stopping unresponsive "
                                f"{self.agent_id} "
                                f"(PID={process.pid}, "
                                f"generation="
                                f"{recovery_generation})"
                            )

                            try:
                                process.kill()

                                await asyncio.wait_for(
                                    process.wait(),
                                    timeout=10,
                                )

                            except ProcessLookupError:
                                pass

                            except asyncio.TimeoutError:
                                print(
                                    "[SUPERVISOR] "
                                    f"Timed out waiting for "
                                    f"{self.agent_id} "
                                    "to terminate."
                                )

                            except Exception as error:
                                print(
                                    "[SUPERVISOR] "
                                    f"Failed to stop "
                                    f"{self.agent_id}: "
                                    f"{error}"
                                )

                    # ----------------------------------------
                    # Clear old process state
                    # ----------------------------------------

                    if (
                        self.process is process
                        and self.process_generation
                        == recovery_generation
                    ):
                        self.process = None

                    self.started_at = None
                    self.healthy_since = None
                    self.heartbeat_timeout_triggered = False
                    self.first_heartbeat_received = False

                    # ----------------------------------------
                    # Recovery backoff
                    # ----------------------------------------

                    try:
                        await asyncio.sleep(delay)
                    finally:
                        pass

                    if self.intentional_stop:
                        return

                    # ----------------------------------------
                    # Prepare fresh process
                    # ----------------------------------------

                    self.stopping_for_recovery = False
                    self.running = True

                    # ----------------------------------------
                    # Fresh process
                    # ----------------------------------------

                    started = (
                        await self._start_without_lock()
                    )

                    if started:
                        print(
                            "[SUPERVISOR] "
                            f"{self.agent_id} recovery "
                            "process started successfully."
                        )

                        return

                    # ----------------------------------------
                    # Startup failed.
                    #
                    # _start_without_lock() sets running=False.
                    #
                    # Restore supervisor ownership and retry
                    # through this same recovery authority.
                    # ----------------------------------------

                    print(
                        "[SUPERVISOR] "
                        f"Recovery start failed for "
                        f"{self.agent_id}. "
                        "Retrying through the same recovery "
                        "authority."
                    )

                    self.running = True
                    self.process = None
                    self.started_at = None
                    self.healthy_since = None

                    agent_registry.mark_dead(
                        self.agent_id
                    )

                    # Continue loop.
                    #
                    # Next iteration:
                    #   record another failure
                    #   calculate larger backoff
                    #   retry isolated startup

            finally:
                self.stopping_for_recovery = False
                self.recovery_in_progress = False

    # ========================================================
    # PROCESS MONITOR
    # ========================================================

    async def monitor_process(self) -> None:
        """
        Continuously monitor this agent's subprocess.

        The task remains alive for the lifetime of the
        supervisor.

        It monitors the exact process object + generation.
        """

        observed_generation: Optional[int] = None

        observed_process: Optional[
            asyncio.subprocess.Process
        ] = None

        while self.running:

            process = self.process

            # ------------------------------------------------
            # No current process
            # ------------------------------------------------

            if process is None:
                observed_process = None
                observed_generation = None

                await asyncio.sleep(0.2)

                continue

            current_generation = (
                self.process_generation
            )

            # ------------------------------------------------
            # New process detected
            # ------------------------------------------------

            if (
                observed_process is not process
                or observed_generation
                != current_generation
            ):
                observed_process = process

                observed_generation = (
                    current_generation
                )

            # ------------------------------------------------
            # Wait for exact process
            # ------------------------------------------------

            try:
                return_code = await process.wait()

            except asyncio.CancelledError:
                raise

            except Exception as error:
                print(
                    "[SUPERVISOR] "
                    f"Process monitor error for "
                    f"{self.agent_id}: "
                    f"{error}"
                )

                await asyncio.sleep(1)

                continue

            # ------------------------------------------------
            # Supervisor/operator shutdown
            # ------------------------------------------------

            if not self.running:
                return

            # ------------------------------------------------
            # STALE PROCESS PROTECTION
            # ------------------------------------------------

            if (
                self.process is not process
                or self.process_generation
                != observed_generation
            ):
                continue

            # ------------------------------------------------
            # Intentional recovery stop
            # ------------------------------------------------

            if self.stopping_for_recovery:
                print(
                    "[SUPERVISOR] "
                    f"{self.agent_id} process exited "
                    "during intentional recovery stop."
                )

                old_process = process

                old_generation = (
                    observed_generation
                )

                while self.running:

                    current_process = self.process

                    current_generation = (
                        self.process_generation
                    )

                    if (
                        current_process is not old_process
                        or current_generation
                        != old_generation
                    ):
                        break

                    await asyncio.sleep(0.2)

                observed_process = None
                observed_generation = None

                continue

            # ------------------------------------------------
            # Recovery already owns lifecycle
            # ------------------------------------------------

            if self.recovery_in_progress:
                print(
                    "[SUPERVISOR] "
                    f"{self.agent_id} process exited "
                    "while recovery is in progress."
                )

                old_process = process

                old_generation = (
                    observed_generation
                )

                while self.running:

                    current_process = self.process

                    current_generation = (
                        self.process_generation
                    )

                    if (
                        current_process is not old_process
                        or current_generation
                        != old_generation
                    ):
                        break

                    await asyncio.sleep(0.2)

                observed_process = None
                observed_generation = None

                continue

            # ------------------------------------------------
            # Genuine unexpected process exit
            # ------------------------------------------------

            await self.handle_process_exit(
                return_code
            )

            # ------------------------------------------------
            # Recovery may have replaced process
            # ------------------------------------------------

            observed_process = None
            observed_generation = None

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
    # HEARTBEAT TIMEOUT
    # ========================================================

    def check_heartbeat_timeout(
        self,
        agent: dict,
    ) -> str:

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
    # HEALTH CHECK
    # ========================================================

    async def check_health(self) -> None:

        if not self.running:
            return

        process = self.process

        # ----------------------------------------------------
        # Missing process while supervisor expects worker
        # ----------------------------------------------------

        if process is None:

            if self.recovery_in_progress:
                return

            if self.intentional_stop:
                return

            print(
                "[SUPERVISOR] "
                f"{self.agent_id} has no active "
                "process while marked running."
            )

            await self.recover(
                reason="missing_process"
            )

            return

        # ----------------------------------------------------
        # Process already exited
        # ----------------------------------------------------

        if process.returncode is not None:

            if self.recovery_in_progress:
                return

            # Process monitor normally handles this.
            return

        # ----------------------------------------------------
        # Startup timestamp unavailable
        # ----------------------------------------------------

        if self.started_at is None:
            return

        # ----------------------------------------------------
        # Recovery owns lifecycle
        # ----------------------------------------------------

        if self.recovery_in_progress:
            return

        loop = asyncio.get_running_loop()

        now = loop.time()

        age_since_start = (
            now - self.started_at
        )

        # ----------------------------------------------------
        # Registry state
        # ----------------------------------------------------

        agent = agent_registry.get_agent(
            self.agent_id
        )

        if agent is None:
            return

        status = agent.get(
            "status"
        )

        # ----------------------------------------------------
        # Startup grace period
        # ----------------------------------------------------

        if (
            age_since_start
            < STARTUP_GRACE_PERIOD
        ):
            return

        # ----------------------------------------------------
        # Heartbeat state
        # ----------------------------------------------------

        heartbeat_state = (
            self.check_heartbeat_timeout(
                agent
            )
        )

        # ----------------------------------------------------
        # First heartbeat never arrived
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
                    f"{STARTUP_GRACE_PERIOD:.1f}s)"
                )

                agent_registry.mark_dead(
                    self.agent_id
                )

                await self.recover(
                    reason="missing_first_heartbeat"
                )

            return

        # ----------------------------------------------------
        # Heartbeat arrived
        # ----------------------------------------------------

        self.first_heartbeat_received = True

        # ----------------------------------------------------
        # Heartbeat timeout
        # ----------------------------------------------------

        if heartbeat_state == "timeout":

            if not self.heartbeat_timeout_triggered:

                self.heartbeat_timeout_triggered = True

                heartbeat_age = (
                    self.get_heartbeat_age(
                        agent
                    )
                )

                print(
                    "[SUPERVISOR] "
                    "HEARTBEAT TIMEOUT: "
                    f"{self.agent_id} "
                    f"(age="
                    f"{heartbeat_age:.1f}s, "
                    f"timeout="
                    f"{HEARTBEAT_TIMEOUT:.1f}s)"
                )

                agent_registry.mark_dead(
                    self.agent_id
                )

                await self.recover(
                    reason="heartbeat_timeout"
                )

            return

        # ----------------------------------------------------
        # Registry explicitly DEAD
        # ----------------------------------------------------

        if status == "DEAD":

            if self.recovery_in_progress:
                return

            print(
                "[SUPERVISOR] "
                f"Heartbeat failure detected for "
                f"{self.agent_id}"
            )

            await self.recover(
                reason="registry_dead"
            )

            return

        # ----------------------------------------------------
        # Starting / recovering
        # ----------------------------------------------------

        if status in (
            "STARTING",
            "RECOVERING",
        ):
            return

        # ----------------------------------------------------
        # Healthy
        # ----------------------------------------------------

        if status == "ALIVE":

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
            f"registry status: {status}"
        )

    # ========================================================
    # HEALTH LOOP
    # ========================================================

    async def health_loop(self) -> None:

        while self.running:

            try:
                await self.check_health()

                await asyncio.sleep(
                    HEALTH_CHECK_INTERVAL
                )

            except asyncio.CancelledError:
                raise

            except Exception as error:
                print(
                    "[SUPERVISOR] "
                    f"Health loop error for "
                    f"{self.agent_id}: "
                    f"{error}"
                )

                await asyncio.sleep(2)


# ============================================================
# AGENT SUPERVISOR
# ============================================================

class AgentSupervisor:
    """
    Supervises all configured production agents.

    Camera-bound detection workers are created independently
    for every enabled camera.

    Example:

        CAM01 -> person-detector-CAM01
        CAM02 -> person-detector-CAM02
        CAM03 -> person-detector-CAM03

    Global downstream workers remain shared.
    """

    def __init__(self):

        self.camera_registry = (
            CameraRegistry.from_environment()
        )

        self.agents: dict[
            str,
            SupervisedAgent,
        ] = {}

        self.running = False

        self.monitor_tasks: list[
            asyncio.Task
        ] = []

        self.health_tasks: list[
            asyncio.Task
        ] = []

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
        # Create ONE detector per enabled camera
        # ----------------------------------------------------

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
    # START ALL
    # ========================================================

    async def start_all(self) -> None:

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
        # Camera information
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

            print(
                "[SUPERVISOR] "
                f"Camera: "
                f"{camera.camera_id} | "
                f"name={camera.name} | "
                f"source={camera.source} | "
                f"location={camera.location}"
            )

            detector_agent_id = (
                f"person-detector-"
                f"{_safe_agent_id_component(camera.camera_id)}"
            )

            print(
                "[SUPERVISOR] "
                f"Camera affinity: "
                f"{camera.camera_id} -> "
                f"{detector_agent_id}"
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

        # ----------------------------------------------------
        # Heartbeat failure-test configuration
        # ----------------------------------------------------

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
        # Start every agent independently
        # ----------------------------------------------------

        for agent in self.agents.values():

            try:
                started = await agent.start()

                if not started:

                    print(
                        "[SUPERVISOR] "
                        f"{agent.agent_id} failed "
                        "initial startup. "
                        "Scheduling automatic recovery."
                    )

                    # Keep the supervisor responsible for
                    # this agent during recovery.
                    agent.running = True

                    asyncio.create_task(
                        agent.recover(
                            reason="initial_startup_failure"
                        ),
                        name=(
                            f"initial-recovery-"
                            f"{agent.agent_id}"
                        ),
                    )

            except Exception as error:

                print(
                    "[SUPERVISOR] "
                    f"Failed to start "
                    f"{agent.agent_id}: "
                    f"{error}"
                )

                agent.running = True

                asyncio.create_task(
                    agent.recover(
                        reason="initial_startup_exception"
                    ),
                    name=(
                        f"initial-recovery-"
                        f"{agent.agent_id}"
                    ),
                )

            await asyncio.sleep(
                STARTUP_DELAY
            )

        # ----------------------------------------------------
        # Process monitors
        # ----------------------------------------------------

        for agent in self.agents.values():

            task = asyncio.create_task(
                agent.monitor_process(),
                name=(
                    f"monitor-process-"
                    f"{agent.agent_id}"
                ),
            )

            self.monitor_tasks.append(
                task
            )

        # ----------------------------------------------------
        # Health monitors
        # ----------------------------------------------------

        for agent in self.agents.values():

            task = asyncio.create_task(
                agent.health_loop(),
                name=(
                    f"health-monitor-"
                    f"{agent.agent_id}"
                ),
            )

            self.health_tasks.append(
                task
            )

        print(
            "[SUPERVISOR] "
            "All process monitors started."
        )

        print(
            "[SUPERVISOR] "
            "All health monitors started."
        )

    # ========================================================
    # STOP ALL
    # ========================================================

    async def stop_all(self) -> None:

        if not self.running:
            return

        print(
            "[SUPERVISOR] "
            "Shutdown requested."
        )

        self.running = False

        # ----------------------------------------------------
        # Mark intentional stop BEFORE cancelling monitors
        # ----------------------------------------------------

        for agent in self.agents.values():

            agent.running = False
            agent.intentional_stop = True
            agent.stopping_for_recovery = False

        # ----------------------------------------------------
        # Cancel process monitors
        # ----------------------------------------------------

        for task in self.monitor_tasks:
            task.cancel()

        if self.monitor_tasks:

            await asyncio.gather(
                *self.monitor_tasks,
                return_exceptions=True,
            )

        self.monitor_tasks.clear()

        # ----------------------------------------------------
        # Cancel health monitors
        # ----------------------------------------------------

        for task in self.health_tasks:
            task.cancel()

        if self.health_tasks:

            await asyncio.gather(
                *self.health_tasks,
                return_exceptions=True,
            )

        self.health_tasks.clear()

        # ----------------------------------------------------
        # Stop processes independently
        # ----------------------------------------------------

        for agent in self.agents.values():

            try:
                await agent.stop()

            except Exception as error:

                print(
                    "[SUPERVISOR] "
                    f"Shutdown error for "
                    f"{agent.agent_id}: "
                    f"{error}"
                )

        print(
            "[SUPERVISOR] "
            "All agents stopped."
        )


# ============================================================
# STANDALONE MAIN
# ============================================================

async def main():

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
