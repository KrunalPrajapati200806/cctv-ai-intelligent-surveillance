"""Camera-scoped runtime lifecycle manager.

This module provides the runtime boundary for individual cameras.

Design goals
------------
- Every camera owns its own detector/tracker worker generation.
- Camera failures are isolated from other cameras.
- Dead worker processes are never considered running.
- Failed worker generations are discarded before recovery.
- Worker subprocess monitoring/recovery remains owned by SupervisedAgent.
- Runtime state is separate from immutable camera configuration.
- Lifecycle operations for different cameras can execute concurrently.
- Cancellation is handled explicitly so workers are not leaked.
- Stale generations are never allowed to overlap with new generations.
- A failure in one camera must not stop or block unrelated cameras.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.app.cameras.registry import (
    CameraConfig,
    CameraRegistry,
    CameraRuntimeState,
    CameraRuntimeStatus,
)
from backend.app.cameras.store import save_camera_record
from backend.app.monitoring.supervisor import (
    AgentProcessConfig,
    SupervisedAgent,
    _safe_agent_id_component,
)


logger = logging.getLogger(__name__)


class CameraRuntimeManager:
    """Own the runtime lifecycle of configured cameras.

    Each camera is an independent runtime boundary.

    A camera owns:

        detector worker generation
        tracker worker generation
        lifecycle lock
        runtime state

    ``SupervisedAgent`` owns the actual subprocess lifecycle,
    health monitoring, process monitoring, and worker recovery.

    This manager owns camera-level lifecycle coordination only.
    """

    def __init__(self) -> None:
        self.registry = CameraRegistry.from_environment()

        # --------------------------------------------------------------
        # Worker generations
        #
        # camera_id -> (detector, tracker)
        #
        # A pair represents ONE runtime generation.
        #
        # A failed generation is completely discarded before a new
        # generation is created.
        # --------------------------------------------------------------
        self.agents: dict[
            str,
            tuple[SupervisedAgent, SupervisedAgent],
        ] = {}

        # --------------------------------------------------------------
        # Mutable runtime state
        # --------------------------------------------------------------
        self.states: dict[
            str,
            CameraRuntimeState,
        ] = {}

        # --------------------------------------------------------------
        # Per-camera lifecycle locks.
        #
        # IMPORTANT:
        # Never use one global lifecycle lock.
        #
        # Camera CAM01 must never block CAM02 from starting/stopping/
        # restarting.
        # --------------------------------------------------------------
        self.lifecycle_locks: dict[
            str,
            asyncio.Lock,
        ] = {}

    # ==================================================================
    # INTERNAL HELPERS
    # ==================================================================

    def _lifecycle_lock(
        self,
        camera_id: str,
    ) -> asyncio.Lock:
        """Return the lifecycle lock for one camera."""

        lock = self.lifecycle_locks.get(camera_id)

        if lock is None:
            lock = asyncio.Lock()
            self.lifecycle_locks[camera_id] = lock

        return lock

    def _state(
        self,
        camera: CameraConfig,
    ) -> CameraRuntimeState:
        """Return or create mutable runtime state for a camera."""

        state = self.states.get(
            camera.camera_id
        )

        if state is None:
            state = CameraRuntimeState(
                camera_id=camera.camera_id,
            )

            self.states[camera.camera_id] = state

        return state

    @staticmethod
    def _process_is_alive(
        agent: SupervisedAgent,
    ) -> bool:
        """Return whether the agent's subprocess appears alive.

        The supervisor may use either ``asyncio.subprocess.Process`` or
        another process-like implementation.

        For asyncio subprocesses:

            process.returncode is None
                -> process is still running

            process.returncode is not None
                -> process has exited

        Some custom process implementations expose ``poll()`` instead.
        That case is supported defensively.

        IMPORTANT:
        We do not treat the mere existence of a process object as proof
        that the process is alive when a return code is available.
        """

        process = getattr(
            agent,
            "process",
            None,
        )

        if process is None:
            return False

        # --------------------------------------------------------------
        # asyncio.subprocess.Process
        # --------------------------------------------------------------
        if hasattr(
            process,
            "returncode",
        ):
            try:
                return (
                    process.returncode is None
                )
            except Exception:
                logger.exception(
                    "Failed to inspect subprocess returncode"
                )
                return False

        # --------------------------------------------------------------
        # subprocess.Popen-like implementation
        # --------------------------------------------------------------
        poll = getattr(
            process,
            "poll",
            None,
        )

        if callable(poll):
            try:
                return poll() is None
            except Exception:
                logger.exception(
                    "Failed to inspect worker process state"
                )
                return False

        # --------------------------------------------------------------
        # Defensive fallback for custom process implementations.
        #
        # If the supervisor provides a process-like object without
        # returncode or poll(), the existence of that object is the best
        # information available to this runtime layer.
        # --------------------------------------------------------------
        return True

    def _agents_are_alive(
        self,
        camera_id: str,
    ) -> bool:
        """Return True only when both camera workers are alive."""

        pair = self.agents.get(
            camera_id
        )

        if pair is None:
            return False

        detector, tracker = pair

        return (
            self._process_is_alive(
                detector
            )
            and self._process_is_alive(
                tracker
            )
        )

    def _is_running(
        self,
        camera_id: str,
    ) -> bool:
        """Return True only when the complete worker generation is alive.

        ``SupervisedAgent`` owns the worker monitoring/recovery tasks.

        Therefore this runtime manager intentionally does NOT create
        duplicate monitor tasks.

        A camera runtime is considered active when both detector and
        tracker subprocesses are currently alive.
        """

        return self._agents_are_alive(
            camera_id
        )

    def _configs(
        self,
        camera: CameraConfig,
    ) -> tuple[
        AgentProcessConfig,
        AgentProcessConfig,
    ]:
        """Build detector and tracker configuration for one camera."""

        component = _safe_agent_id_component(
            camera.camera_id
        )

        stream = (
            f"events.detection.{component}"
        )

        detector = AgentProcessConfig(
            name="detection",
            agent_id=(
                f"person-detector-{component}"
            ),
            script="agents/detection/main.py",
            camera_id=camera.camera_id,
            camera_source=camera.source,
            camera_name=camera.name,
            camera_location=camera.location,
            stream_name=stream,
        )

        tracker = AgentProcessConfig(
            name="tracker",
            agent_id=(
                f"tracker-{component}"
            ),
            script="agents/tracker/main.py",
            camera_id=camera.camera_id,
            stream_name=stream,
            consumer_group=(
                f"tracker-workers.{component}"
            ),
        )

        return (
            detector,
            tracker,
        )

    def _create_worker_pair(
        self,
        camera: CameraConfig,
    ) -> tuple[
        SupervisedAgent,
        SupervisedAgent,
    ]:
        """Create a completely fresh worker generation."""

        detector_config, tracker_config = (
            self._configs(camera)
        )

        return (
            SupervisedAgent(
                detector_config
            ),
            SupervisedAgent(
                tracker_config
            ),
        )

    async def _dispose_worker_pair(
        self,
        camera_id: str,
        *,
        pair: tuple[
            SupervisedAgent,
            SupervisedAgent,
        ]
        | None = None,
    ) -> None:
        """Stop and discard one worker generation.

        Detector and tracker are stopped independently.

        Failure while stopping one worker must not prevent the other
        worker from being stopped.
        """

        worker_pair = (
            pair
            if pair is not None
            else self.agents.get(
                camera_id
            )
        )

        if worker_pair is None:
            return

        results = await asyncio.gather(
            *(
                agent.stop()
                for agent in worker_pair
            ),
            return_exceptions=True,
        )

        for index, result in enumerate(
            results
        ):
            if not isinstance(
                result,
                BaseException,
            ):
                continue

            worker_name = (
                "detector"
                if index == 0
                else "tracker"
            )

            if isinstance(
                result,
                asyncio.CancelledError,
            ):
                logger.debug(
                    "%s worker stop cancelled: %s",
                    worker_name,
                    camera_id,
                )
            else:
                logger.warning(
                    "Failed to stop %s worker for %s: %s",
                    worker_name,
                    camera_id,
                    result,
                )

        # --------------------------------------------------------------
        # Remove only if this is still the active generation.
        #
        # This prevents an old generation from deleting a newer
        # generation if lifecycle logic is changed later to allow
        # overlapping asynchronous operations.
        # --------------------------------------------------------------
        current_pair = self.agents.get(
            camera_id
        )

        if current_pair is worker_pair:
            self.agents.pop(
                camera_id,
                None,
            )

    async def _cleanup_generation(
        self,
        camera_id: str,
        pair: tuple[
            SupervisedAgent,
            SupervisedAgent,
        ]
        | None = None,
    ) -> None:
        """Fully clean one camera runtime generation."""

        await self._dispose_worker_pair(
            camera_id,
            pair=pair,
        )

    def _set_status(
        self,
        camera: CameraConfig,
        status: CameraRuntimeStatus,
        *,
        error: str | None = None,
    ) -> None:
        """Update mutable runtime state."""

        state = self._state(
            camera
        )

        state.status = status

        if error is not None:
            state.last_error = error

        elif status not in {
            CameraRuntimeStatus.ERROR,
            CameraRuntimeStatus.FAILED,
        }:
            state.last_error = None

    async def _persist_status(
        self,
        camera: CameraConfig,
        status: CameraRuntimeStatus,
    ) -> dict[str, Any]:
        """Persist operational status without blocking the event loop."""

        return await asyncio.to_thread(
            save_camera_record,
            camera,
            status=status.value,
        )

    # ==================================================================
    # CAMERA REGISTRATION / SYNCHRONIZATION
    # ==================================================================

    def sync_camera(
        self,
        camera: CameraConfig,
    ) -> None:
        """Synchronize immutable camera configuration.

        A camera cannot be synchronized while it owns a runtime
        generation.

        Call ``stop(camera_id)`` before changing its configuration.
        """

        camera_id = camera.camera_id

        if (
            camera_id in self.agents
        ):
            raise RuntimeError(
                "Cannot synchronize a camera with an active or stale "
                f"runtime generation: {camera_id}. "
                "Stop the camera first."
            )

        existing = self.registry.get(
            camera_id
        )

        if existing is not None:
            self.registry.unregister(
                camera_id
            )

        self.states.pop(
            camera_id,
            None,
        )

        self.registry.register(
            camera
        )

    async def remove_camera(
        self,
        camera_id: str,
    ) -> None:
        """Stop and remove one camera safely."""

        camera = self.registry.get_required(
            camera_id
        )

        lock = self._lifecycle_lock(
            camera_id
        )

        async with lock:
            await self._stop_unlocked(
                camera
            )

            self.registry.unregister(
                camera_id
            )

            self.agents.pop(
                camera_id,
                None,
            )

            self.states.pop(
                camera_id,
                None,
            )

            self.lifecycle_locks.pop(
                camera_id,
                None,
            )

    # ==================================================================
    # RUNTIME STATE
    # ==================================================================

    def get_state(
        self,
        camera_id: str,
    ) -> CameraRuntimeState | None:
        """Return a detached runtime-state snapshot."""

        state = self.states.get(
            camera_id
        )

        if state is None:
            return None

        return CameraRuntimeState(
            camera_id=state.camera_id,
            status=state.status,
            last_heartbeat=state.last_heartbeat,
            fps=state.fps,
            frames_processed=state.frames_processed,
            uptime_seconds=state.uptime_seconds,
            restart_count=state.restart_count,
            last_error=state.last_error,
        )

    def get_all_states(
        self,
    ) -> dict[
        str,
        CameraRuntimeState,
    ]:
        """Return detached runtime snapshots for all cameras."""

        return {
            camera_id: CameraRuntimeState(
                camera_id=state.camera_id,
                status=state.status,
                last_heartbeat=state.last_heartbeat,
                fps=state.fps,
                frames_processed=state.frames_processed,
                uptime_seconds=state.uptime_seconds,
                restart_count=state.restart_count,
                last_error=state.last_error,
            )
            for camera_id, state
            in self.states.items()
        }

    # ==================================================================
    # START
    # ==================================================================

    async def start(
        self,
        camera_id: str,
    ) -> dict[str, Any]:
        """Start one camera runtime."""

        camera = self.registry.get_required(
            camera_id
        )

        lock = self._lifecycle_lock(
            camera_id
        )

        async with lock:
            return await self._start_unlocked(
                camera
            )

    async def _start_unlocked(
        self,
        camera: CameraConfig,
    ) -> dict[str, Any]:
        """Internal camera start implementation."""

        camera_id = camera.camera_id
        state = self._state(
            camera
        )

        # --------------------------------------------------------------
        # Disabled camera
        # --------------------------------------------------------------
        if not camera.enabled:
            self._set_status(
                camera,
                CameraRuntimeStatus.DISABLED,
            )

            await self._persist_status(
                camera,
                CameraRuntimeStatus.DISABLED,
            )

            raise ValueError(
                f"Camera is disabled: {camera_id}"
            )

        # --------------------------------------------------------------
        # Already healthy
        # --------------------------------------------------------------
        if self._is_running(
            camera_id
        ):
            if (
                state.status
                != CameraRuntimeStatus.ONLINE
            ):
                self._set_status(
                    camera,
                    CameraRuntimeStatus.ONLINE,
                )

            return await self._persist_status(
                camera,
                CameraRuntimeStatus.ONLINE,
            )

        # --------------------------------------------------------------
        # Existing but unhealthy/stale generation
        #
        # IMPORTANT:
        # Never reuse a failed worker generation.
        # --------------------------------------------------------------
        if camera_id in self.agents:
            logger.warning(
                "Discarding stale/failed camera runtime generation: %s",
                camera_id,
            )

            stale_pair = self.agents.get(
                camera_id
            )

            await self._cleanup_generation(
                camera_id,
                stale_pair,
            )

        # --------------------------------------------------------------
        # STARTING
        # --------------------------------------------------------------
        self._set_status(
            camera,
            CameraRuntimeStatus.STARTING,
        )

        state.last_error = None

        await self._persist_status(
            camera,
            CameraRuntimeStatus.STARTING,
        )

        # --------------------------------------------------------------
        # Create a completely fresh worker generation.
        # --------------------------------------------------------------
        generation = (
            self._create_worker_pair(
                camera
            )
        )

        detector, tracker = generation

        self.agents[camera_id] = generation

        try:
            # ----------------------------------------------------------
            # Detector
            # ----------------------------------------------------------
            detector_started = bool(
                await detector.start()
            )

            if not detector_started:
                raise RuntimeError(
                    "Detector worker failed to start"
                )

            # ----------------------------------------------------------
            # Tracker
            # ----------------------------------------------------------
            tracker_started = bool(
                await tracker.start()
            )

            if not tracker_started:
                raise RuntimeError(
                    "Tracker worker failed to start"
                )

            # ----------------------------------------------------------
            # Verify immediately after startup.
            # ----------------------------------------------------------
            if not self._agents_are_alive(
                camera_id
            ):
                raise RuntimeError(
                    "One or more worker processes died immediately "
                    "after startup"
                )

            # ----------------------------------------------------------
            # SupervisedAgent owns:
            #
            # - process monitor
            # - health monitor
            # - recovery
            # - generation handling
            #
            # Therefore runtime.py intentionally does not create
            # duplicate monitor_process()/health_loop() tasks.
            # ----------------------------------------------------------

            self._set_status(
                camera,
                CameraRuntimeStatus.ONLINE,
            )

            return await self._persist_status(
                camera,
                CameraRuntimeStatus.ONLINE,
            )

        except asyncio.CancelledError:
            self._set_status(
                camera,
                CameraRuntimeStatus.ERROR,
                error="Camera startup cancelled",
            )

            await self._cleanup_generation(
                camera_id,
                generation,
            )

            try:
                await self._persist_status(
                    camera,
                    CameraRuntimeStatus.ERROR,
                )
            except Exception:
                logger.exception(
                    "Failed to persist cancellation status: %s",
                    camera_id,
                )

            raise

        except Exception as exc:
            self._set_status(
                camera,
                CameraRuntimeStatus.ERROR,
                error=str(exc),
            )

            logger.exception(
                "Camera startup failed: %s",
                camera_id,
            )

            await self._cleanup_generation(
                camera_id,
                generation,
            )

            try:
                await self._persist_status(
                    camera,
                    CameraRuntimeStatus.ERROR,
                )
            except Exception:
                logger.exception(
                    "Failed to persist startup failure status: %s",
                    camera_id,
                )

            raise

    # ==================================================================
    # STOP
    # ==================================================================

    async def stop(
        self,
        camera_id: str,
    ) -> dict[str, Any]:
        """Stop all workers belonging to one camera."""

        camera = self.registry.get_required(
            camera_id
        )

        lock = self._lifecycle_lock(
            camera_id
        )

        async with lock:
            return await self._stop_unlocked(
                camera
            )

    async def _stop_unlocked(
        self,
        camera: CameraConfig,
    ) -> dict[str, Any]:
        """Internal camera stop implementation."""

        camera_id = camera.camera_id

        self._set_status(
            camera,
            CameraRuntimeStatus.STOPPING,
        )

        await self._persist_status(
            camera,
            CameraRuntimeStatus.STOPPING,
        )

        stop_errors: list[str] = []

        # --------------------------------------------------------------
        # Remove the active generation from the registry first.
        #
        # This prevents later lifecycle checks from treating the
        # generation as active while shutdown is in progress.
        # --------------------------------------------------------------
        pair = self.agents.pop(
            camera_id,
            None,
        )

        # --------------------------------------------------------------
        # Stop detector/tracker independently.
        #
        # SupervisedAgent.stop() is responsible for stopping its own
        # process monitor / health monitor / recovery tasks.
        # --------------------------------------------------------------
        if pair is not None:
            results = await asyncio.gather(
                *(
                    agent.stop()
                    for agent in pair
                ),
                return_exceptions=True,
            )

            for index, result in enumerate(
                results
            ):
                if not isinstance(
                    result,
                    BaseException,
                ):
                    continue

                if isinstance(
                    result,
                    asyncio.CancelledError,
                ):
                    continue

                worker_name = (
                    "detector"
                    if index == 0
                    else "tracker"
                )

                stop_errors.append(
                    f"{worker_name}: {result}"
                )

        state = self._state(
            camera
        )

        # --------------------------------------------------------------
        # Reset camera-level runtime metrics.
        # --------------------------------------------------------------
        state.fps = 0.0
        state.uptime_seconds = 0.0
        state.last_heartbeat = None

        if stop_errors:
            final_status = (
                CameraRuntimeStatus.ERROR
            )

            state.last_error = (
                "; ".join(stop_errors)
            )
        elif camera.enabled:
            final_status = (
                CameraRuntimeStatus.OFFLINE
            )

            state.last_error = None
        else:
            final_status = (
                CameraRuntimeStatus.DISABLED
            )

            state.last_error = None

        self._set_status(
            camera,
            final_status,
            error=(
                "; ".join(stop_errors)
                if stop_errors
                else None
            ),
        )

        return await self._persist_status(
            camera,
            final_status,
        )

    # ==================================================================
    # RESTART
    # ==================================================================

    async def restart(
        self,
        camera_id: str,
    ) -> dict[str, Any]:
        """Restart one camera runtime in isolation."""

        camera = self.registry.get_required(
            camera_id
        )

        lock = self._lifecycle_lock(
            camera_id
        )

        async with lock:
            state = self._state(
                camera
            )

            state.restart_count += 1

            await self._stop_unlocked(
                camera
            )

            self._set_status(
                camera,
                CameraRuntimeStatus.RECOVERING,
            )

            await self._persist_status(
                camera,
                CameraRuntimeStatus.RECOVERING,
            )

            return await self._start_unlocked(
                camera
            )

    # ==================================================================
    # SHUTDOWN
    # ==================================================================

    async def shutdown(
        self,
    ) -> None:
        """Gracefully stop every camera independently."""

        cameras = list(
            self.registry.get_all()
        )

        if not cameras:
            return

        results = await asyncio.gather(
            *(
                self.stop(
                    camera.camera_id
                )
                for camera in cameras
            ),
            return_exceptions=True,
        )

        for camera, result in zip(
            cameras,
            results,
        ):
            if not isinstance(
                result,
                BaseException,
            ):
                continue

            if isinstance(
                result,
                asyncio.CancelledError,
            ):
                continue

            logger.error(
                "Failed to stop camera during shutdown: "
                "%s: %s",
                camera.camera_id,
                result,
            )


# ======================================================================
# GLOBAL RUNTIME MANAGER
# ======================================================================

camera_runtime_manager = CameraRuntimeManager()
