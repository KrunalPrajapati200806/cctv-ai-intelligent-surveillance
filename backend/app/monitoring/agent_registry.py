# # from datetime import datetime, timezone
# # from threading import Lock


# # # ============================================================
# # # AGENT REGISTRY
# # # ============================================================

# # class AgentRegistry:
# #     """
# #     In-memory registry for monitoring agent heartbeats.

# #     Each agent record contains:
# #         - agent_id
# #         - last_heartbeat
# #         - status

# #     Status values:
# #         - alive
# #         - dead
# #     """

# #     def __init__(self):
# #         self.agents = {}
# #         self._lock = Lock()

# #     # ========================================================
# #     # UPDATE HEARTBEAT
# #     # ========================================================

# #     def update_heartbeat(self, agent_id: str):
# #         """
# #         Register an agent or refresh its heartbeat.

# #         A heartbeat always marks the agent as alive.
# #         """

# #         if not agent_id:
# #             return False

# #         now = datetime.now(timezone.utc)

# #         with self._lock:
# #             self.agents[agent_id] = {
# #                 "agent_id": agent_id,
# #                 "last_heartbeat": now,
# #                 "status": "alive",
# #             }

# #         return True

# #     # ========================================================
# #     # GET SINGLE AGENT
# #     # ========================================================

# #     def get_agent(self, agent_id: str):
# #         """
# #         Return a copy of an agent record.

# #         Returns None if the agent is not registered.
# #         """

# #         with self._lock:
# #             agent = self.agents.get(agent_id)

# #             if agent is None:
# #                 return None

# #             return agent.copy()

# #     # ========================================================
# #     # GET ALL AGENTS
# #     # ========================================================

# #     def get_all_agents(self):
# #         """
# #         Return a snapshot of all registered agents.
# #         """

# #         with self._lock:
# #             return {
# #                 agent_id: agent.copy()
# #                 for agent_id, agent in self.agents.items()
# #             }

# #     # ========================================================
# #     # MARK AGENT DEAD
# #     # ========================================================

# #     def mark_dead(self, agent_id: str):
# #         """
# #         Mark an existing agent as dead.

# #         Returns:
# #             True  -> agent existed and was marked dead
# #             False -> agent was not found
# #         """

# #         with self._lock:
# #             agent = self.agents.get(agent_id)

# #             if agent is None:
# #                 return False

# #             agent["status"] = "dead"

# #             return True

# #     # ========================================================
# #     # REMOVE AGENT
# #     # ========================================================

# #     def remove_agent(self, agent_id: str):
# #         """
# #         Remove an agent from the registry.
# #         """

# #         with self._lock:
# #             if agent_id not in self.agents:
# #                 return False

# #             del self.agents[agent_id]

# #             return True

# #     # ========================================================
# #     # AGENT COUNT
# #     # ========================================================

# #     def count(self):
# #         """
# #         Return the number of registered agents.
# #         """

# #         with self._lock:
# #             return len(self.agents)


# # # ============================================================
# # # GLOBAL REGISTRY INSTANCE
# # # ============================================================

# # agent_registry = AgentRegistry()
















# from datetime import datetime, timezone
# from threading import Lock


# class AgentRegistry:

#     def __init__(self):
#         self.agents = {}
#         self._lock = Lock()

#     def update_heartbeat(self, agent_id: str):
#         if not agent_id or not agent_id.strip():
#             raise ValueError("agent_id cannot be empty")

#         now = datetime.now(timezone.utc)

#         with self._lock:
#             existing = self.agents.get(agent_id, {})

#             self.agents[agent_id] = {
#                 "agent_id": agent_id,
#                 "status": "alive",
#                 "last_heartbeat": now,
#                 "failure_count": existing.get(
#                     "failure_count",
#                     0,
#                 ),
#             }

#     def get_agent(self, agent_id: str):
#         with self._lock:
#             agent = self.agents.get(agent_id)

#             if agent is None:
#                 return None

#             return dict(agent)

#     def get_all_agents(self):
#         with self._lock:
#             return {
#                 agent_id: dict(agent)
#                 for agent_id, agent in self.agents.items()
#             }

#     def mark_dead(self, agent_id: str):
#         with self._lock:
#             if agent_id not in self.agents:
#                 return False

#             self.agents[agent_id]["status"] = "dead"
#             self.agents[agent_id]["failure_count"] = (
#                 self.agents[agent_id].get(
#                     "failure_count",
#                     0,
#                 ) + 1
#             )

#             return True

#     def mark_recovering(self, agent_id: str):
#         with self._lock:
#             if agent_id not in self.agents:
#                 return False

#             self.agents[agent_id]["status"] = "recovering"

#             return True

#     def remove_agent(self, agent_id: str):
#         with self._lock:
#             return self.agents.pop(
#                 agent_id,
#                 None,
#             ) is not None

#     def count(self):
#         with self._lock:
#             return len(self.agents)


# agent_registry = AgentRegistry()








from datetime import datetime, timezone
from threading import Lock


class AgentRegistry:
    """
    Thread-safe in-memory registry of agent health.

    Responsibilities:
    - Track agent discovery
    - Track latest heartbeat
    - Track lifecycle status
    - Track failures
    - Provide snapshots for watchdog/supervisor
    """

    def __init__(self):
        self.agents = {}
        self._lock = Lock()

    def register_agent(
        self,
        agent_id: str,
        instance_id: str | None = None,
        hostname: str | None = None,
    ):
        if not agent_id or not agent_id.strip():
            raise ValueError("agent_id cannot be empty")

        now = datetime.now(timezone.utc)

        with self._lock:
            existing = self.agents.get(agent_id, {})

            self.agents[agent_id] = {
                "agent_id": agent_id,
                "status": existing.get("status", "STARTING"),
                "last_heartbeat": existing.get(
                    "last_heartbeat"
                ),
                "first_seen": existing.get(
                    "first_seen",
                    now,
                ),
                "last_status_change": existing.get(
                    "last_status_change",
                    now,
                ),
                "failure_count": existing.get(
                    "failure_count",
                    0,
                ),
                "instance_id": (
                    instance_id
                    if instance_id is not None
                    else existing.get("instance_id")
                ),
                "hostname": (
                    hostname
                    if hostname is not None
                    else existing.get("hostname")
                ),
            }

    def update_heartbeat(
        self,
        agent_id: str,
        instance_id: str | None = None,
        hostname: str | None = None,
    ):
        if not agent_id or not agent_id.strip():
            raise ValueError("agent_id cannot be empty")

        now = datetime.now(timezone.utc)

        with self._lock:
            existing = self.agents.get(agent_id)

            if existing is None:
                self.agents[agent_id] = {
                    "agent_id": agent_id,
                    "status": "ALIVE",
                    "last_heartbeat": now,
                    "first_seen": now,
                    "last_status_change": now,
                    "failure_count": 0,
                    "instance_id": instance_id,
                    "hostname": hostname,
                }
                return

            previous_status = existing.get(
                "status",
                "STARTING",
            )

            existing["status"] = "ALIVE"
            existing["last_heartbeat"] = now

            if instance_id is not None:
                existing["instance_id"] = instance_id

            if hostname is not None:
                existing["hostname"] = hostname

            if previous_status != "ALIVE":
                existing["last_status_change"] = now

    def get_agent(self, agent_id: str):
        with self._lock:
            agent = self.agents.get(agent_id)

            if agent is None:
                return None

            return dict(agent)

    def get_all_agents(self):
        with self._lock:
            return {
                agent_id: dict(agent)
                for agent_id, agent in self.agents.items()
            }

    def mark_dead(self, agent_id: str):
        now = datetime.now(timezone.utc)

        with self._lock:
            if agent_id not in self.agents:
                return False

            agent = self.agents[agent_id]

            if agent.get("status") != "DEAD":
                agent["status"] = "DEAD"
                agent["last_status_change"] = now
                agent["failure_count"] = (
                    agent.get("failure_count", 0) + 1
                )

            return True

    def mark_recovering(self, agent_id: str):
        now = datetime.now(timezone.utc)

        with self._lock:
            if agent_id not in self.agents:
                return False

            agent = self.agents[agent_id]

            agent["status"] = "RECOVERING"
            agent["last_status_change"] = now

            return True

    def mark_starting(self, agent_id: str):
        now = datetime.now(timezone.utc)

        with self._lock:
            if agent_id not in self.agents:
                return False

            agent = self.agents[agent_id]

            agent["status"] = "STARTING"
            agent["last_status_change"] = now

            return True

    def remove_agent(self, agent_id: str):
        with self._lock:
            return (
                self.agents.pop(
                    agent_id,
                    None,
                )
                is not None
            )

    def count(self):
        with self._lock:
            return len(self.agents)


agent_registry = AgentRegistry()