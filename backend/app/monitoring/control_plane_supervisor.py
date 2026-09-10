# import asyncio
# import os
# import signal
# import subprocess
# import sys
# from pathlib import Path
# from typing import Optional


# # ============================================================
# # PROJECT CONFIGURATION
# # ============================================================

# PROJECT_ROOT = Path(__file__).resolve().parents[3]

# PYTHON_EXECUTABLE = sys.executable

# MONITORING_MODULE = "backend.app.monitoring.monitoring_service"


# # ============================================================
# # CONTROL-PLANE CONFIGURATION
# # ============================================================

# CHECK_INTERVAL = float(
#     os.getenv("CONTROL_PLANE_CHECK_INTERVAL", "2")
# )

# RESTART_DELAY = float(
#     os.getenv("CONTROL_PLANE_RESTART_DELAY", "3")
# )

# MAX_RESTART_DELAY = float(
#     os.getenv("CONTROL_PLANE_MAX_RESTART_DELAY", "30")
# )

# MAX_CONSECUTIVE_FAILURES = int(
#     os.getenv("CONTROL_PLANE_MAX_CONSECUTIVE_FAILURES", "5")
# )

# HEALTHY_RESET_SECONDS = float(
#     os.getenv("CONTROL_PLANE_HEALTHY_RESET_SECONDS", "60")
# )


# # ============================================================
# # PRODUCTION AGENT SCRIPTS
# # ============================================================

# PRODUCTION_AGENT_SCRIPTS = [
#     "agents/detection/main.py",
#     "agents/tracker/main.py",
#     "agents/behavior/main.py",
#     "agents/crowd/main.py",
#     "agents/security/main.py",
#     "agents/alert/main.py",
#     "agents/incident/main.py",
# ]


# # ============================================================
# # CONTROL PLANE SUPERVISOR
# # ============================================================

# class ControlPlaneSupervisor:

#     def __init__(self):
#         self.process: Optional[asyncio.subprocess.Process] = None

#         self.running = False
#         self.shutdown_requested = False

#         self.consecutive_failures = 0
#         self.restart_delay = RESTART_DELAY

#         self.started_at: Optional[float] = None

#     # ========================================================
#     # LOGGING
#     # ========================================================

#     def log(self, message: str):
#         print(f"[CONTROL-PLANE] {message}", flush=True)

#     # ========================================================
#     # START MONITORING SERVICE
#     # ========================================================

#     async def start_monitoring_service(self) -> bool:

#         if self.process is not None:

#             if self.process.returncode is None:

#                 self.log(
#                     f"Monitoring service already running "
#                     f"(PID={self.process.pid})"
#                 )

#                 return True

#         self.log("=" * 70)
#         self.log("STARTING MONITORING SERVICE")
#         self.log("=" * 70)

#         monitoring_script = (
#             PROJECT_ROOT
#             / "backend"
#             / "app"
#             / "monitoring"
#             / "monitoring_service.py"
#         )

#         if not monitoring_script.exists():

#             self.log(
#                 f"ERROR: Monitoring service file not found: "
#                 f"{monitoring_script}"
#             )

#             return False

#         env = os.environ.copy()

#         # Ensure project root is importable.
#         existing_pythonpath = env.get("PYTHONPATH", "")

#         if existing_pythonpath:
#             env["PYTHONPATH"] = (
#                 f"{PROJECT_ROOT}{os.pathsep}{existing_pythonpath}"
#             )
#         else:
#             env["PYTHONPATH"] = str(PROJECT_ROOT)

#         env["PYTHONUNBUFFERED"] = "1"

#         try:

#             self.process = await asyncio.create_subprocess_exec(
#                 PYTHON_EXECUTABLE,
#                 "-u",
#                 "-m",
#                 MONITORING_MODULE,
#                 cwd=str(PROJECT_ROOT),
#                 env=env,
#                 stdin=None,
#                 stdout=None,
#                 stderr=None,
#             )

#             self.started_at = asyncio.get_running_loop().time()

#             self.log(
#                 f"Monitoring service started. "
#                 f"PID={self.process.pid}"
#             )

#             self.log(
#                 f"Python={PYTHON_EXECUTABLE}"
#             )

#             self.log(
#                 f"Project root={PROJECT_ROOT}"
#             )

#             return True

#         except Exception as error:

#             self.log(
#                 f"FAILED TO START MONITORING SERVICE: {error}"
#             )

#             self.process = None

#             return False

#     # ========================================================
#     # KILL PROCESS TREE
#     # ========================================================

#     def kill_process_tree(self, pid: int):

#         if pid <= 0:
#             return

#         self.log(
#             f"Killing process tree rooted at PID {pid}..."
#         )

#         try:

#             result = subprocess.run(
#                 [
#                     "taskkill",
#                     "/PID",
#                     str(pid),
#                     "/T",
#                     "/F",
#                 ],
#                 stdout=subprocess.PIPE,
#                 stderr=subprocess.PIPE,
#                 text=True,
#                 timeout=15,
#             )

#             if result.returncode == 0:

#                 self.log(
#                     f"Process tree PID {pid} terminated."
#                 )

#             else:

#                 output = (
#                     result.stdout.strip()
#                     or result.stderr.strip()
#                 )

#                 self.log(
#                     f"taskkill returned {result.returncode}: "
#                     f"{output}"
#                 )

#         except Exception as error:

#             self.log(
#                 f"Process-tree cleanup error for PID {pid}: "
#                 f"{error}"
#             )

#     # ========================================================
#     # FIND ORPHANED AGENTS
#     # ========================================================

#     def find_orphaned_agent_pids(self):

#         """
#         Find processes whose command line contains one of the
#         production agent scripts.

#         This is deliberately restricted to the 7 production
#         agents. We do NOT kill arbitrary Python processes.
#         """

#         agent_patterns = [
#             script.replace("/", "\\")
#             for script in PRODUCTION_AGENT_SCRIPTS
#         ]

#         try:

#             result = subprocess.run(
#                 [
#                     "powershell",
#                     "-NoProfile",
#                     "-Command",
#                     (
#                         "Get-CimInstance Win32_Process | "
#                         "Where-Object { "
#                         "$_.CommandLine -ne $null -and ("
#                         + " -or ".join(
#                             [
#                                 f'$_.CommandLine -like "*{pattern}*"'
#                                 for pattern in agent_patterns
#                             ]
#                         )
#                         + ") } | "
#                         "Select-Object -ExpandProperty ProcessId"
#                     ),
#                 ],
#                 stdout=subprocess.PIPE,
#                 stderr=subprocess.PIPE,
#                 text=True,
#                 timeout=15,
#             )

#             if result.returncode != 0:

#                 self.log(
#                     "Could not inspect orphaned agent processes: "
#                     f"{result.stderr.strip()}"
#                 )

#                 return []

#             pids = []

#             for line in result.stdout.splitlines():

#                 line = line.strip()

#                 if not line:
#                     continue

#                 try:
#                     pid = int(line)

#                     if pid > 0:
#                         pids.append(pid)

#                 except ValueError:
#                     continue

#             return sorted(set(pids))

#         except Exception as error:

#             self.log(
#                 f"Agent process scan failed: {error}"
#             )

#             return []

#     # ========================================================
#     # CLEAN ORPHANED AGENTS
#     # ========================================================

#     def cleanup_orphaned_agents(self):

#         self.log(
#             "Checking for orphaned production agents..."
#         )

#         pids = self.find_orphaned_agent_pids()

#         if not pids:

#             self.log(
#                 "No orphaned production agents found."
#             )

#             return

#         self.log(
#             f"Found possible orphaned agent PIDs: {pids}"
#         )

#         for pid in pids:

#             self.kill_process_tree(pid)

#         self.log(
#             "Orphaned-agent cleanup completed."
#         )

#     # ========================================================
#     # STOP CURRENT MONITORING SERVICE
#     # ========================================================

#     async def stop_monitoring_service(self):

#         process = self.process

#         if process is None:
#             return

#         pid = process.pid

#         self.log(
#             f"Stopping monitoring service PID={pid}..."
#         )

#         # On Windows, taskkill /T /F is important here.
#         # It terminates the complete subprocess tree.
#         self.kill_process_tree(pid)

#         try:

#             await asyncio.wait_for(
#                 process.wait(),
#                 timeout=10,
#             )

#         except asyncio.TimeoutError:

#             self.log(
#                 f"Monitoring service PID={pid} "
#                 f"did not exit after taskkill."
#             )

#         except Exception as error:

#             self.log(
#                 f"Error waiting for monitoring service: "
#                 f"{error}"
#             )

#         self.process = None

#     # ========================================================
#     # HANDLE SERVICE FAILURE
#     # ========================================================

#     async def recover_monitoring_service(
#         self,
#         return_code: Optional[int],
#     ):

#         if self.shutdown_requested:
#             return

#         self.consecutive_failures += 1

#         self.log("=" * 70)
#         self.log("MONITORING SERVICE FAILURE DETECTED")
#         self.log("=" * 70)

#         self.log(
#             f"Exit code: {return_code}"
#         )

#         self.log(
#             f"Consecutive failures: "
#             f"{self.consecutive_failures}"
#         )

#         # ----------------------------------------------------
#         # Make absolutely sure no old agent tree survives.
#         # ----------------------------------------------------

#         if self.process is not None:

#             pid = self.process.pid

#             self.log(
#                 f"Cleaning monitoring-service tree PID={pid}"
#             )

#             self.kill_process_tree(pid)

#         self.process = None

#         # ----------------------------------------------------
#         # Catch orphaned agents left behind by an unexpected
#         # process termination.
#         # ----------------------------------------------------

#         self.cleanup_orphaned_agents()

#         # ----------------------------------------------------
#         # Failure limit
#         # ----------------------------------------------------

#         if (
#             self.consecutive_failures
#             >= MAX_CONSECUTIVE_FAILURES
#         ):

#             self.log(
#                 "Maximum consecutive control-plane failures "
#                 f"reached ({MAX_CONSECUTIVE_FAILURES})."
#             )

#             self.log(
#                 "Increasing restart backoff."
#             )

#         # ----------------------------------------------------
#         # Backoff
#         # ----------------------------------------------------

#         delay = min(
#             self.restart_delay,
#             MAX_RESTART_DELAY,
#         )

#         self.log(
#             f"Waiting {delay:.1f}s before restart..."
#         )

#         try:

#             await asyncio.sleep(delay)

#         except asyncio.CancelledError:

#             raise

#         if self.shutdown_requested:
#             return

#         # Increase backoff for repeated failures.
#         self.restart_delay = min(
#             max(self.restart_delay * 2, RESTART_DELAY),
#             MAX_RESTART_DELAY,
#         )

#         # ----------------------------------------------------
#         # Restart
#         # ----------------------------------------------------

#         started = await self.start_monitoring_service()

#         if started:

#             self.log(
#                 "Monitoring service recovery STARTED."
#             )

#         else:

#             self.log(
#                 "Monitoring service restart FAILED."
#             )

#     # ========================================================
#     # MONITOR LOOP
#     # ========================================================

#     async def monitor_loop(self):

#         self.log("=" * 70)
#         self.log("CONTROL-PLANE SUPERVISOR")
#         self.log("=" * 70)

#         self.log(
#             f"Project root: {PROJECT_ROOT}"
#         )

#         self.log(
#             f"Python executable: {PYTHON_EXECUTABLE}"
#         )

#         self.log(
#             f"Check interval: {CHECK_INTERVAL}s"
#         )

#         self.log(
#             f"Restart delay: {RESTART_DELAY}s"
#         )

#         self.log(
#             "Independent monitoring of monitoring_service.py "
#             "enabled."
#         )

#         self.log("=" * 70)

#         started = await self.start_monitoring_service()

#         if not started:

#             self.log(
#                 "Initial monitoring-service start failed."
#             )

#         while not self.shutdown_requested:

#             try:

#                 await asyncio.sleep(CHECK_INTERVAL)

#                 if self.process is None:

#                     if self.shutdown_requested:
#                         break

#                     self.log(
#                         "Monitoring service process is missing."
#                     )

#                     await self.recover_monitoring_service(
#                         return_code=None
#                     )

#                     continue

#                 return_code = self.process.returncode

#                 # ------------------------------------------------
#                 # Process is alive.
#                 # ------------------------------------------------

#                 if return_code is None:

#                     # If it has been healthy long enough,
#                     # reset failure counters/backoff.
#                     if self.started_at is not None:

#                         uptime = (
#                             asyncio.get_running_loop().time()
#                             - self.started_at
#                         )

#                         if (
#                             uptime
#                             >= HEALTHY_RESET_SECONDS
#                         ):

#                             if (
#                                 self.consecutive_failures
#                                 != 0
#                             ):

#                                 self.log(
#                                     "Monitoring service has "
#                                     "remained healthy."
#                                 )

#                                 self.log(
#                                     "Resetting control-plane "
#                                     "failure counter."
#                                 )

#                             self.consecutive_failures = 0
#                             self.restart_delay = RESTART_DELAY

#                     continue

#                 # ------------------------------------------------
#                 # Process exited.
#                 # ------------------------------------------------

#                 self.log(
#                     f"Monitoring service exited. "
#                     f"Return code={return_code}"
#                 )

#                 await self.recover_monitoring_service(
#                     return_code=return_code
#                 )

#             except asyncio.CancelledError:

#                 raise

#             except Exception as error:

#                 self.log(
#                     f"CONTROL-PLANE MONITOR ERROR: {error}"
#                 )

#                 await asyncio.sleep(CHECK_INTERVAL)

#     # ========================================================
#     # START
#     # ========================================================

#     async def start(self):

#         self.running = True
#         self.shutdown_requested = False

#         await self.monitor_loop()

#     # ========================================================
#     # STOP
#     # ========================================================

#     async def stop(self):

#         if not self.running:
#             return

#         self.shutdown_requested = True
#         self.running = False

#         self.log("=" * 70)
#         self.log("CONTROL-PLANE SHUTDOWN")
#         self.log("=" * 70)

#         # Stop monitoring service and its complete tree.
#         await self.stop_monitoring_service()

#         # Extra safety check.
#         self.cleanup_orphaned_agents()

#         self.log(
#             "Control-plane supervisor stopped."
#         )


# # ============================================================
# # MAIN
# # ============================================================

# async def main():

#     supervisor = ControlPlaneSupervisor()

#     try:

#         await supervisor.start()

#     except asyncio.CancelledError:

#         supervisor.log(
#             "Cancellation received."
#         )

#     except KeyboardInterrupt:

#         supervisor.log(
#             "Keyboard interrupt received."
#         )

#     except Exception as error:

#         supervisor.log(
#             f"FATAL CONTROL-PLANE ERROR: {error}"
#         )

#     finally:

#         await supervisor.stop()


# if __name__ == "__main__":

#     try:
#         asyncio.run(main())

#     except KeyboardInterrupt:
#         pass














import asyncio
import ctypes
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional


# ============================================================
# PROJECT CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[3]

PYTHON_EXECUTABLE = sys.executable

MONITORING_MODULE = "backend.app.monitoring.monitoring_service"


# ============================================================
# CONTROL-PLANE CONFIGURATION
# ============================================================

CHECK_INTERVAL = float(
    os.getenv("CONTROL_PLANE_CHECK_INTERVAL", "2")
)

RESTART_DELAY = float(
    os.getenv("CONTROL_PLANE_RESTART_DELAY", "3")
)

MAX_RESTART_DELAY = float(
    os.getenv("CONTROL_PLANE_MAX_RESTART_DELAY", "30")
)

MAX_CONSECUTIVE_FAILURES = int(
    os.getenv("CONTROL_PLANE_MAX_CONSECUTIVE_FAILURES", "5")
)

HEALTHY_RESET_SECONDS = float(
    os.getenv("CONTROL_PLANE_HEALTHY_RESET_SECONDS", "60")
)


# ============================================================
# SINGLETON CONFIGURATION
# ============================================================

CONTROL_PLANE_MUTEX_NAME = (
    "CCTV_AI_CONTROL_PLANE_SUPERVISOR_SINGLETON"
)


# ============================================================
# PRODUCTION AGENTS
# ============================================================

PRODUCTION_AGENT_SCRIPTS = [
    "agents/detection/main.py",
    "agents/tracker/main.py",
    "agents/behavior/main.py",
    "agents/crowd/main.py",
    "agents/security/main.py",
    "agents/alert/main.py",
    "agents/incident/main.py",
]


# ============================================================
# CONTROL-PLANE SUPERVISOR
# ============================================================

class ControlPlaneSupervisor:

    def __init__(self):
        self.process: Optional[asyncio.subprocess.Process] = None

        self.running = False

        self.shutdown_requested = False

        self.consecutive_failures = 0

        self.restart_delay = RESTART_DELAY

        self.started_at: Optional[float] = None

        # Windows named mutex handle.
        self.mutex_handle = None

        self.singleton_acquired = False


    # ========================================================
    # LOGGING
    # ========================================================

    def log(self, message: str):
        print(
            f"[CONTROL-PLANE] {message}",
            flush=True,
        )


    # ========================================================
    # SINGLETON LOCK
    # ========================================================

    def acquire_singleton(self) -> bool:
        """
        Acquire a Windows named mutex.

        If another control-plane supervisor already owns
        the mutex, this process exits without starting
        another monitoring service.
        """

        if os.name != "nt":
            self.log(
                "Non-Windows platform detected. "
                "Windows mutex singleton is unavailable."
            )

            # Current project is Windows-based.
            # Continue without mutex on non-Windows.
            self.singleton_acquired = True
            return True

        try:

            kernel32 = ctypes.windll.kernel32

            kernel32.CreateMutexW.restype = ctypes.c_void_p

            kernel32.GetLastError.restype = ctypes.c_ulong

            ERROR_ALREADY_EXISTS = 183

            mutex_handle = kernel32.CreateMutexW(
                None,
                False,
                CONTROL_PLANE_MUTEX_NAME,
            )

            if not mutex_handle:
                self.log(
                    "ERROR: Failed to create control-plane mutex."
                )
                return False

            last_error = kernel32.GetLastError()

            if last_error == ERROR_ALREADY_EXISTS:

                self.log(
                    "Another control-plane supervisor "
                    "is already running."
                )

                kernel32.CloseHandle(mutex_handle)

                return False

            self.mutex_handle = mutex_handle

            self.singleton_acquired = True

            self.log(
                "Singleton lock acquired successfully."
            )

            return True

        except Exception as error:

            self.log(
                f"Singleton initialization failed: {error}"
            )

            return False


    def release_singleton(self):

        if not self.singleton_acquired:
            return

        if os.name != "nt":
            self.singleton_acquired = False
            return

        try:

            kernel32 = ctypes.windll.kernel32

            if self.mutex_handle:

                kernel32.ReleaseMutex(
                    self.mutex_handle
                )

                kernel32.CloseHandle(
                    self.mutex_handle
                )

                self.mutex_handle = None

            self.singleton_acquired = False

            self.log(
                "Singleton lock released."
            )

        except Exception as error:

            self.log(
                f"Singleton lock release error: {error}"
            )


    # ========================================================
    # START MONITORING SERVICE
    # ========================================================

    async def start_monitoring_service(self) -> bool:

        if self.process is not None:

            if self.process.returncode is None:

                self.log(
                    "Monitoring service already running "
                    f"(PID={self.process.pid})"
                )

                return True


        self.log("=" * 70)

        self.log(
            "STARTING MONITORING SERVICE"
        )

        self.log("=" * 70)


        monitoring_script = (
            PROJECT_ROOT
            / "backend"
            / "app"
            / "monitoring"
            / "monitoring_service.py"
        )


        if not monitoring_script.exists():

            self.log(
                "ERROR: Monitoring service file not found: "
                f"{monitoring_script}"
            )

            return False


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


        try:

            self.process = (
                await asyncio.create_subprocess_exec(

                    PYTHON_EXECUTABLE,

                    "-u",

                    "-m",

                    MONITORING_MODULE,

                    cwd=str(PROJECT_ROOT),

                    env=env,

                    stdin=None,

                    stdout=None,

                    stderr=None,
                )
            )


            self.started_at = (
                asyncio.get_running_loop().time()
            )


            self.log(
                "Monitoring service started. "
                f"PID={self.process.pid}"
            )

            self.log(
                f"Python={PYTHON_EXECUTABLE}"
            )

            self.log(
                f"Project root={PROJECT_ROOT}"
            )


            return True


        except Exception as error:

            self.log(
                "FAILED TO START MONITORING SERVICE: "
                f"{error}"
            )

            self.process = None

            return False


    # ========================================================
    # WINDOWS PROCESS TREE KILL
    # ========================================================

    def kill_process_tree(self, pid: int):

        if pid <= 0:
            return


        self.log(
            f"Killing process tree rooted at PID {pid}..."
        )


        try:

            result = subprocess.run(

                [
                    "taskkill",
                    "/PID",
                    str(pid),
                    "/T",
                    "/F",
                ],

                stdout=subprocess.PIPE,

                stderr=subprocess.PIPE,

                text=True,

                timeout=15,
            )


            if result.returncode == 0:

                self.log(
                    f"Process tree PID {pid} terminated."
                )

                return


            output = (
                result.stdout.strip()
                or result.stderr.strip()
            )


            # Process already disappeared.
            if (
                "not found" in output.lower()
                or "no running instance" in output.lower()
                or "already been terminated" in output.lower()
            ):

                self.log(
                    f"Process tree PID {pid} "
                    "was already terminated."
                )

                return


            self.log(
                f"taskkill returned "
                f"{result.returncode}: {output}"
            )


        except Exception as error:

            self.log(
                f"Process-tree cleanup error "
                f"for PID {pid}: {error}"
            )


    # ========================================================
    # FIND ORPHANED AGENTS
    # ========================================================

    def find_orphaned_agent_pids(self):

        agent_patterns = [
            script.replace("/", "\\")
            for script in PRODUCTION_AGENT_SCRIPTS
        ]


        try:

            result = subprocess.run(

                [
                    "powershell",
                    "-NoProfile",
                    "-Command",

                    (
                        "Get-CimInstance Win32_Process | "
                        "Where-Object { "
                        "$_.CommandLine -ne $null -and ("

                        +

                        " -or ".join(

                            [
                                f'$_.CommandLine -like '
                                f'"*{pattern}*"'
                                for pattern
                                in agent_patterns
                            ]

                        )

                        +

                        ") } | "

                        "Select-Object "
                        "-ExpandProperty ProcessId"
                    ),
                ],

                stdout=subprocess.PIPE,

                stderr=subprocess.PIPE,

                text=True,

                timeout=15,
            )


            if result.returncode != 0:

                self.log(
                    "Could not inspect orphaned "
                    "agent processes: "
                    f"{result.stderr.strip()}"
                )

                return []


            pids = []


            for line in result.stdout.splitlines():

                line = line.strip()

                if not line:
                    continue


                try:

                    pid = int(line)

                    if pid > 0:
                        pids.append(pid)

                except ValueError:

                    continue


            return sorted(set(pids))


        except Exception as error:

            self.log(
                f"Agent process scan failed: {error}"
            )

            return []


    # ========================================================
    # CLEAN ORPHANED AGENTS
    # ========================================================

    def cleanup_orphaned_agents(self):

        self.log(
            "Checking for orphaned production agents..."
        )


        pids = self.find_orphaned_agent_pids()


        if not pids:

            self.log(
                "No orphaned production agents found."
            )

            return


        self.log(
            "Found possible orphaned agent PIDs: "
            f"{pids}"
        )


        for pid in pids:

            self.kill_process_tree(pid)


        self.log(
            "Orphaned-agent cleanup completed."
        )


    # ========================================================
    # STOP MONITORING SERVICE
    # ========================================================

    async def stop_monitoring_service(self):

        process = self.process


        if process is None:
            return


        pid = process.pid


        self.log(
            f"Stopping monitoring service PID={pid}..."
        )


        self.kill_process_tree(pid)


        try:

            await asyncio.wait_for(
                process.wait(),
                timeout=10,
            )

        except asyncio.TimeoutError:

            self.log(
                f"Monitoring service PID={pid} "
                "did not exit after taskkill."
            )

        except Exception as error:

            self.log(
                "Error waiting for monitoring service: "
                f"{error}"
            )


        self.process = None


    # ========================================================
    # RECOVER MONITORING SERVICE
    # ========================================================

    async def recover_monitoring_service(
        self,
        return_code: Optional[int],
    ):

        if self.shutdown_requested:
            return


        self.consecutive_failures += 1


        self.log("=" * 70)

        self.log(
            "MONITORING SERVICE FAILURE DETECTED"
        )

        self.log("=" * 70)


        self.log(
            f"Exit code: {return_code}"
        )

        self.log(
            "Consecutive failures: "
            f"{self.consecutive_failures}"
        )


        if self.process is not None:

            pid = self.process.pid

            self.log(
                "Cleaning monitoring-service tree "
                f"PID={pid}"
            )

            self.kill_process_tree(pid)


        self.process = None


        # Remove agents belonging to the dead
        # monitoring service.

        self.cleanup_orphaned_agents()


        if (
            self.consecutive_failures
            >= MAX_CONSECUTIVE_FAILURES
        ):

            self.log(
                "Maximum consecutive control-plane "
                "failures reached "
                f"({MAX_CONSECUTIVE_FAILURES})."
            )

            self.log(
                "Increasing restart backoff."
            )


        delay = min(
            self.restart_delay,
            MAX_RESTART_DELAY,
        )


        self.log(
            f"Waiting {delay:.1f}s before restart..."
        )


        try:

            await asyncio.sleep(delay)

        except asyncio.CancelledError:

            raise


        if self.shutdown_requested:
            return


        self.restart_delay = min(

            max(
                self.restart_delay * 2,
                RESTART_DELAY,
            ),

            MAX_RESTART_DELAY,
        )


        started = (
            await self.start_monitoring_service()
        )


        if started:

            self.log(
                "Monitoring service recovery STARTED."
            )

        else:

            self.log(
                "Monitoring service restart FAILED."
            )


    # ========================================================
    # MAIN MONITOR LOOP
    # ========================================================

    async def monitor_loop(self):

        self.log("=" * 70)

        self.log(
            "CONTROL-PLANE SUPERVISOR"
        )

        self.log("=" * 70)


        self.log(
            f"Project root: {PROJECT_ROOT}"
        )

        self.log(
            f"Python executable: "
            f"{PYTHON_EXECUTABLE}"
        )

        self.log(
            f"Check interval: "
            f"{CHECK_INTERVAL}s"
        )

        self.log(
            f"Restart delay: "
            f"{RESTART_DELAY}s"
        )

        self.log(
            "Independent monitoring of "
            "monitoring_service.py enabled."
        )

        self.log("=" * 70)


        started = (
            await self.start_monitoring_service()
        )


        if not started:

            self.log(
                "Initial monitoring-service "
                "start failed."
            )


        while not self.shutdown_requested:

            try:

                await asyncio.sleep(
                    CHECK_INTERVAL
                )


                # ----------------------------------------
                # Missing process
                # ----------------------------------------

                if self.process is None:

                    if self.shutdown_requested:
                        break


                    self.log(
                        "Monitoring service process "
                        "is missing."
                    )


                    await self.recover_monitoring_service(
                        return_code=None
                    )


                    continue


                # ----------------------------------------
                # Check process state
                # ----------------------------------------

                return_code = (
                    self.process.returncode
                )


                # ----------------------------------------
                # Process still alive
                # ----------------------------------------

                if return_code is None:

                    if self.started_at is not None:

                        uptime = (
                            asyncio.get_running_loop()
                            .time()
                            - self.started_at
                        )


                        if (
                            uptime
                            >= HEALTHY_RESET_SECONDS
                        ):

                            if (
                                self.consecutive_failures
                                != 0
                            ):

                                self.log(
                                    "Monitoring service "
                                    "has remained healthy."
                                )

                                self.log(
                                    "Resetting "
                                    "control-plane "
                                    "failure counter."
                                )


                            self.consecutive_failures = 0

                            self.restart_delay = (
                                RESTART_DELAY
                            )


                    continue


                # ----------------------------------------
                # Process exited
                # ----------------------------------------

                self.log(
                    "Monitoring service exited. "
                    f"Return code={return_code}"
                )


                await self.recover_monitoring_service(
                    return_code=return_code
                )


            except asyncio.CancelledError:

                raise


            except Exception as error:

                self.log(
                    "CONTROL-PLANE MONITOR ERROR: "
                    f"{error}"
                )

                await asyncio.sleep(
                    CHECK_INTERVAL
                )


    # ========================================================
    # START
    # ========================================================

    async def start(self):

        self.running = True

        self.shutdown_requested = False


        # Singleton must be acquired BEFORE
        # starting Monitoring Service.

        if not self.acquire_singleton():

            self.log(
                "Control-plane startup aborted."
            )

            self.running = False

            return


        await self.monitor_loop()


    # ========================================================
    # STOP
    # ========================================================

    async def stop(self):

        if not self.running:

            self.release_singleton()

            return


        self.shutdown_requested = True

        self.running = False


        self.log("=" * 70)

        self.log(
            "CONTROL-PLANE SHUTDOWN"
        )

        self.log("=" * 70)


        await self.stop_monitoring_service()


        self.cleanup_orphaned_agents()


        self.release_singleton()


        self.log(
            "Control-plane supervisor stopped."
        )


# ============================================================
# MAIN
# ============================================================

async def main():

    supervisor = ControlPlaneSupervisor()


    try:

        await supervisor.start()


    except asyncio.CancelledError:

        supervisor.log(
            "Cancellation received."
        )


    except KeyboardInterrupt:

        supervisor.log(
            "Keyboard interrupt received."
        )


    except Exception as error:

        supervisor.log(
            "FATAL CONTROL-PLANE ERROR: "
            f"{error}"
        )


    finally:

        await supervisor.stop()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:

        pass