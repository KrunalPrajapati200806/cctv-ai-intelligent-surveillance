from datetime import datetime, timezone


class AgentRegistry:
    def __init__(self):
        self.agents = {}

    def update_heartbeat(self, agent_id: str):
        self.agents[agent_id] = {
            "agent_id": agent_id,
            "last_heartbeat": datetime.now(timezone.utc),
            "status": "alive",
        }

    def get_agent(self, agent_id: str):
        return self.agents.get(agent_id)

    def get_all_agents(self):
        return self.agents.copy()

    def mark_dead(self, agent_id: str):
        """
        Mark an existing agent as dead.
        """

        if agent_id in self.agents:
            self.agents[agent_id]["status"] = "dead"
            return True

        return False