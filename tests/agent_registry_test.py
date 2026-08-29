from backend.app.monitoring.agent_registry import AgentRegistry


def main():
    registry = AgentRegistry()

    print("Testing AgentRegistry...")

    # First heartbeat
    registry.update_heartbeat("person-detector-01")

    agent = registry.get_agent("person-detector-01")

    print("\nAgent:")
    print(agent)

    # Test second agent
    registry.update_heartbeat("vehicle-detector-01")

    print("\nAll agents:")
    print(registry.get_all_agents())

    # Basic assertions
    assert agent is not None
    assert agent["agent_id"] == "person-detector-01"
    assert agent["status"] == "alive"
    assert agent["last_heartbeat"] is not None

    assert len(registry.get_all_agents()) == 2

    print("\n✅ AgentRegistry test passed!")


if __name__ == "__main__":
    main()