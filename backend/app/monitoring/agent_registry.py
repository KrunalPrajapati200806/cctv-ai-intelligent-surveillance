from __future__ import annotations

import logging
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Literal


logger = logging.getLogger(__name__)


AgentStatus = Literal[
    "STARTING",
    "ALIVE",
    "RECOVERING",
    "DEAD",
]


class AgentRegistry:
    """
    Thread-safe in-memory registry of agent process health.

    Responsibilities
    ----------------
    - Track agent discovery.
    - Track latest heartbeat.
    - Track lifecycle status.
    - Track failure count.
    - Track process instance identity.
    - Track process generation.
    - Track hostname.
    - Provide detached snapshots for watchdog/supervisor/recovery layers.

    This class deliberately does NOT:

    - restart processes
    - terminate processes
    - consume Redis
    - publish events
    - execute recovery policies
    - make restart decisions
    - manage subprocesses

    Architecture
    ------------
    The registry is a state store only.

        Agent Process
             |
             | register / heartbeat
             v
        AgentRegistry
             |
             v
        Watchdog / Supervisor
             |
             v
        Recovery Manager

    Process identity
    ----------------
    Every running subprocess should have a unique instance_id.

    Example:

        tracker-01
            instance_id = tracker-01-abc123
            process_generation = 1

        tracker-01 restarts
            instance_id = tracker-01-def456
            process_generation = 2

    When a newer process instance/generation is registered, the previous
    heartbeat is cleared immediately.

    This prevents a stale heartbeat from an old process from making a
    replacement process appear healthy.

    Thread safety
    -------------
    All access to the internal agent dictionary is protected by _lock.

    Callers receive detached dictionary snapshots rather than references
    to internal registry state.
    """

    # ================================================================
    # LIFECYCLE STATUS
    # ================================================================

    STARTING: AgentStatus = "STARTING"
    ALIVE: AgentStatus = "ALIVE"
    RECOVERING: AgentStatus = "RECOVERING"
    DEAD: AgentStatus = "DEAD"

    # ================================================================
    # INITIALIZATION
    # ================================================================

    def __init__(self) -> None:
        self.agents: dict[str, dict[str, Any]] = {}
        self._lock = Lock()

    # ================================================================
    # TIME
    # ================================================================

    @staticmethod
    def _now() -> datetime:
        """
        Return the current UTC time as a timezone-aware datetime.
        """
        return datetime.now(timezone.utc)

    # ================================================================
    # VALIDATION
    # ================================================================

    @staticmethod
    def _validate_agent_id(agent_id: str) -> None:
        if not isinstance(agent_id, str) or not agent_id.strip():
            raise ValueError("agent_id cannot be empty")

    @staticmethod
    def _validate_instance_id(instance_id: str | None) -> None:
        if instance_id is not None:
            if not isinstance(instance_id, str) or not instance_id.strip():
                raise ValueError("instance_id cannot be empty")

    @staticmethod
    def _validate_generation(
        process_generation: int | None,
    ) -> None:
        if process_generation is None:
            return

        # bool is technically an int subclass, but it is not a valid
        # process generation.
        if isinstance(process_generation, bool):
            raise ValueError(
                "process_generation must be a positive integer"
            )

        if (
            not isinstance(process_generation, int)
            or process_generation <= 0
        ):
            raise ValueError(
                "process_generation must be a positive integer"
            )

    @staticmethod
    def _validate_hostname(
        hostname: str | None,
    ) -> None:
        if hostname is not None:
            if not isinstance(hostname, str) or not hostname.strip():
                raise ValueError("hostname cannot be empty")

    # ================================================================
    # INTERNAL HELPERS
    # ================================================================

    @staticmethod
    def _set_status(
        agent: dict[str, Any],
        status: AgentStatus,
        now: datetime,
    ) -> None:
        """
        Change lifecycle status and update the transition timestamp
        only when the status actually changes.
        """
        previous_status = agent.get("status")

        if previous_status != status:
            agent["status"] = status
            agent["last_status_change"] = now

    # ================================================================
    # REGISTER AGENT
    # ================================================================

    def register_agent(
        self,
        agent_id: str,
        instance_id: str | None = None,
        hostname: str | None = None,
        process_generation: int | None = None,
    ) -> None:
        """
        Register an agent process instance.

        Parameters
        ----------
        agent_id:
            Logical agent identity.

        instance_id:
            Unique identity of the currently running process instance.

        hostname:
            Host running the process.

        process_generation:
            Monotonically increasing generation assigned by the
            supervisor.

        Behavior
        --------
        First registration creates the agent.

        If the logical agent already exists and the instance_id or
        process_generation changes, the registry treats the registration
        as a new process generation.

        The previous heartbeat is cleared.

        Generation rollback is rejected.

        Backward compatibility
        ----------------------
        instance_id and process_generation are optional so older agents
        can continue working while the platform migrates toward explicit
        process identity.
        """

        self._validate_agent_id(agent_id)
        self._validate_instance_id(instance_id)
        self._validate_generation(process_generation)
        self._validate_hostname(hostname)

        now = self._now()

        with self._lock:
            existing = self.agents.get(agent_id)

            # --------------------------------------------------------
            # First registration
            # --------------------------------------------------------

            if existing is None:
                self.agents[agent_id] = {
                    "agent_id": agent_id,
                    "status": self.STARTING,
                    "last_heartbeat": None,
                    "first_seen": now,
                    "last_status_change": now,
                    "failure_count": 0,
                    "instance_id": instance_id,
                    "process_generation": process_generation,
                    "hostname": hostname,
                }

                logger.info(
                    "Registered new agent: "
                    "agent_id=%s instance_id=%s generation=%s hostname=%s",
                    agent_id,
                    instance_id,
                    process_generation,
                    hostname,
                )

                return

            # --------------------------------------------------------
            # Existing logical agent
            # --------------------------------------------------------

            previous_instance_id = existing.get(
                "instance_id"
            )

            previous_generation = existing.get(
                "process_generation"
            )

            # --------------------------------------------------------
            # Generation rollback protection
            # --------------------------------------------------------

            if (
                process_generation is not None
                and previous_generation is not None
                and process_generation < previous_generation
            ):
                logger.warning(
                    "Ignoring older process generation: "
                    "agent_id=%s generation=%s current_generation=%s",
                    agent_id,
                    process_generation,
                    previous_generation,
                )

                return

            # --------------------------------------------------------
            # Determine whether this represents a new process
            # --------------------------------------------------------

            new_instance = (
                instance_id is not None
                and instance_id != previous_instance_id
            )

            new_generation = (
                process_generation is not None
                and process_generation != previous_generation
            )

            new_process = (
                new_instance
                or new_generation
            )

            # --------------------------------------------------------
            # New process instance / generation
            # --------------------------------------------------------

            if new_process:
                if instance_id is not None:
                    existing["instance_id"] = instance_id

                if process_generation is not None:
                    existing["process_generation"] = (
                        process_generation
                    )

                if hostname is not None:
                    existing["hostname"] = hostname

                # CRITICAL:
                #
                # The new process has not sent a heartbeat yet.
                #
                # Never inherit the old process heartbeat.
                existing["last_heartbeat"] = None

                self._set_status(
                    existing,
                    self.STARTING,
                    now,
                )

                logger.info(
                    "Registered new process generation: "
                    "agent_id=%s instance_id=%s generation=%s",
                    agent_id,
                    existing.get("instance_id"),
                    existing.get("process_generation"),
                )

                return

            # --------------------------------------------------------
            # Same process registering again
            # --------------------------------------------------------

            if instance_id is not None:
                existing["instance_id"] = instance_id

            if process_generation is not None:
                existing["process_generation"] = (
                    process_generation
                )

            if hostname is not None:
                existing["hostname"] = hostname

            logger.debug(
                "Agent registration refreshed: "
                "agent_id=%s instance_id=%s generation=%s",
                agent_id,
                existing.get("instance_id"),
                existing.get("process_generation"),
            )

    # ================================================================
    # UPDATE HEARTBEAT
    # ================================================================

    def update_heartbeat(
        self,
        agent_id: str,
        instance_id: str,
        hostname: str | None = None,
        process_generation: int | None = None,
    ) -> bool:
        """
        Record a heartbeat from an agent process.

        Returns
        -------
        bool
            True if the heartbeat was accepted.
            False if it was rejected as stale or unknown.

        Validation
        ----------
        A heartbeat is accepted only when:

        1. The logical agent exists.
        2. The instance_id matches the registered process instance,
           when the registry has an instance identity.
        3. The process_generation matches the registered generation,
           when both sides provide generation information.

        Unknown processes cannot create an agent merely by sending
        heartbeats.

        Stale process instances cannot revive replacement processes.
        """

        self._validate_agent_id(agent_id)
        self._validate_instance_id(instance_id)

        if instance_id is None:
            raise ValueError(
                "instance_id is required for heartbeat"
            )

        self._validate_generation(process_generation)
        self._validate_hostname(hostname)

        now = self._now()

        with self._lock:
            existing = self.agents.get(agent_id)

            # --------------------------------------------------------
            # Unknown agent
            # --------------------------------------------------------

            if existing is None:
                logger.warning(
                    "Ignoring heartbeat from unknown agent: "
                    "agent_id=%s instance_id=%s generation=%s",
                    agent_id,
                    instance_id,
                    process_generation,
                )

                return False

            registered_instance_id = existing.get(
                "instance_id"
            )

            registered_generation = existing.get(
                "process_generation"
            )

            # --------------------------------------------------------
            # Instance validation
            # --------------------------------------------------------

            if (
                registered_instance_id is not None
                and instance_id != registered_instance_id
            ):
                logger.warning(
                    "Ignoring stale heartbeat: "
                    "agent_id=%s instance_id=%s current_instance=%s",
                    agent_id,
                    instance_id,
                    registered_instance_id,
                )

                return False

            # --------------------------------------------------------
            # Generation validation
            # --------------------------------------------------------

            if (
                registered_generation is not None
                and process_generation is not None
                and process_generation != registered_generation
            ):
                logger.warning(
                    "Ignoring stale generation heartbeat: "
                    "agent_id=%s generation=%s current_generation=%s",
                    agent_id,
                    process_generation,
                    registered_generation,
                )

                return False

            # --------------------------------------------------------
            # If registry has no instance identity yet, adopt it.
            # This supports migration from older agents.
            # --------------------------------------------------------

            if registered_instance_id is None:
                existing["instance_id"] = instance_id

            # --------------------------------------------------------
            # If registry has no generation yet, adopt it.
            # --------------------------------------------------------

            if (
                registered_generation is None
                and process_generation is not None
            ):
                existing["process_generation"] = (
                    process_generation
                )

            # --------------------------------------------------------
            # Hostname
            # --------------------------------------------------------

            if hostname is not None:
                existing["hostname"] = hostname

            # --------------------------------------------------------
            # Lifecycle update
            # --------------------------------------------------------

            self._set_status(
                existing,
                self.ALIVE,
                now,
            )

            existing["last_heartbeat"] = now

            return True

    # ================================================================
    # GET ONE AGENT
    # ================================================================

    def get_agent(
        self,
        agent_id: str,
    ) -> dict[str, Any] | None:
        """
        Return a detached snapshot of one agent.

        Modifying the returned dictionary does not modify the registry.
        """

        self._validate_agent_id(agent_id)

        with self._lock:
            agent = self.agents.get(agent_id)

            if agent is None:
                return None

            return dict(agent)

    # ================================================================
    # GET ALL AGENTS
    # ================================================================

    def get_all_agents(
        self,
    ) -> dict[str, dict[str, Any]]:
        """
        Return detached snapshots of all registered agents.

        The returned dictionaries are safe for callers to inspect or
        modify without mutating registry state.
        """

        with self._lock:
            return {
                agent_id: dict(agent)
                for agent_id, agent in self.agents.items()
            }

    # ================================================================
    # MARK DEAD
    # ================================================================

    def mark_dead(
        self,
        agent_id: str,
    ) -> bool:
        """
        Mark an existing agent as DEAD.

        This method is intended for the supervisor/recovery layer.

        The registry itself does not decide whether an agent is dead.

        Returns
        -------
        bool
            True if the agent exists.
            False otherwise.

        Failure count
        -------------
        failure_count is incremented only when transitioning into DEAD.

        Repeated calls while already DEAD do not repeatedly increment
        the counter.
        """

        self._validate_agent_id(agent_id)

        now = self._now()

        with self._lock:
            agent = self.agents.get(agent_id)

            if agent is None:
                return False

            previous_status = agent.get("status")

            if previous_status != self.DEAD:
                self._set_status(
                    agent,
                    self.DEAD,
                    now,
                )

                agent["failure_count"] = (
                    agent.get("failure_count", 0) + 1
                )

            return True

    # ================================================================
    # MARK RECOVERING
    # ================================================================

    def mark_recovering(
        self,
        agent_id: str,
    ) -> bool:
        """
        Mark an existing agent as RECOVERING.

        Recovery owns the lifecycle while the supervisor attempts
        to replace or restart the process.

        The previous heartbeat is cleared so the old process cannot
        continue appearing healthy while recovery is in progress.
        """

        self._validate_agent_id(agent_id)

        now = self._now()

        with self._lock:
            agent = self.agents.get(agent_id)

            if agent is None:
                return False

            self._set_status(
                agent,
                self.RECOVERING,
                now,
            )

            # Old process is no longer considered healthy.
            agent["last_heartbeat"] = None

            return True

    # ================================================================
    # MARK STARTING
    # ================================================================

    def mark_starting(
        self,
        agent_id: str,
    ) -> bool:
        """
        Mark an existing agent as STARTING.

        The supervisor should call this before launching a replacement
        process.

        The previous heartbeat is cleared so an old process cannot
        remain healthy while a replacement is starting.
        """

        self._validate_agent_id(agent_id)

        now = self._now()

        with self._lock:
            agent = self.agents.get(agent_id)

            if agent is None:
                return False

            self._set_status(
                agent,
                self.STARTING,
                now,
            )

            # Critical:
            #
            # A new process must not inherit the previous process's
            # heartbeat.
            agent["last_heartbeat"] = None

            return True

    # ================================================================
    # REMOVE AGENT
    # ================================================================

    def remove_agent(
        self,
        agent_id: str,
    ) -> bool:
        """
        Permanently remove an agent from the registry.

        Returns True if an entry existed and was removed.
        """

        self._validate_agent_id(agent_id)

        with self._lock:
            return (
                self.agents.pop(
                    agent_id,
                    None,
                )
                is not None
            )

    # ================================================================
    # COUNT
    # ================================================================

    def count(self) -> int:
        """
        Return the number of currently registered logical agents.
        """

        with self._lock:
            return len(self.agents)


# ====================================================================
# GLOBAL REGISTRY INSTANCE
# ====================================================================

agent_registry = AgentRegistry()


__all__ = [
    "AgentRegistry",
    "AgentStatus",
    "agent_registry",
]