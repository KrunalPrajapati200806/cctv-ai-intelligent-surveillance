from __future__ import annotations

import threading
import unittest
from datetime import datetime, timezone

from backend.app.monitoring.agent_registry import AgentRegistry


class TestAgentRegistry(unittest.TestCase):
    """
    Production-level unit tests for AgentRegistry.

    These tests verify:
    - registration
    - heartbeat lifecycle
    - stale instance protection
    - stale generation protection
    - generation rollback protection
    - lifecycle transitions
    - failure counting
    - detached snapshots
    - thread-safe access
    """

    def setUp(self) -> None:
        self.registry = AgentRegistry()

    # ================================================================
    # REGISTRATION
    # ================================================================

    def test_register_agent_starts_in_starting_state(self) -> None:
        self.registry.register_agent(
            agent_id="tracker-01",
            instance_id="tracker-01-instance-a",
            hostname="DESKTOP-TEST",
            process_generation=1,
        )

        agent = self.registry.get_agent("tracker-01")

        self.assertIsNotNone(agent)

        assert agent is not None

        self.assertEqual(
            agent["agent_id"],
            "tracker-01",
        )

        self.assertEqual(
            agent["status"],
            AgentRegistry.STARTING,
        )

        self.assertIsNone(
            agent["last_heartbeat"],
        )

        self.assertEqual(
            agent["instance_id"],
            "tracker-01-instance-a",
        )

        self.assertEqual(
            agent["process_generation"],
            1,
        )

        self.assertEqual(
            agent["hostname"],
            "DESKTOP-TEST",
        )

        self.assertEqual(
            agent["failure_count"],
            0,
        )

        self.assertIsInstance(
            agent["first_seen"],
            datetime,
        )

        self.assertIsInstance(
            agent["last_status_change"],
            datetime,
        )

        self.assertIsNotNone(
            agent["first_seen"].tzinfo,
        )

        self.assertIsNotNone(
            agent["last_status_change"].tzinfo,
        )

    # ================================================================
    # HEARTBEAT
    # ================================================================

    def test_valid_heartbeat_changes_starting_to_alive(self) -> None:
        self.registry.register_agent(
            agent_id="tracker-01",
            instance_id="tracker-01-instance-a",
            process_generation=1,
        )

        accepted = self.registry.update_heartbeat(
            agent_id="tracker-01",
            instance_id="tracker-01-instance-a",
            process_generation=1,
        )

        self.assertTrue(accepted)

        agent = self.registry.get_agent("tracker-01")

        self.assertIsNotNone(agent)

        assert agent is not None

        self.assertEqual(
            agent["status"],
            AgentRegistry.ALIVE,
        )

        self.assertIsNotNone(
            agent["last_heartbeat"],
        )

        self.assertEqual(
            agent["instance_id"],
            "tracker-01-instance-a",
        )

        self.assertEqual(
            agent["process_generation"],
            1,
        )

    def test_unknown_agent_heartbeat_is_rejected(self) -> None:
        accepted = self.registry.update_heartbeat(
            agent_id="unknown-agent",
            instance_id="unknown-agent-instance",
            process_generation=1,
        )

        self.assertFalse(accepted)

        self.assertIsNone(
            self.registry.get_agent("unknown-agent"),
        )

        self.assertEqual(
            self.registry.count(),
            0,
        )

    # ================================================================
    # STALE INSTANCE PROTECTION
    # ================================================================

    def test_stale_instance_heartbeat_is_rejected(self) -> None:
        self.registry.register_agent(
            agent_id="tracker-01",
            instance_id="tracker-01-instance-a",
            process_generation=1,
        )

        accepted = self.registry.update_heartbeat(
            agent_id="tracker-01",
            instance_id="tracker-01-instance-a",
            process_generation=1,
        )

        self.assertTrue(accepted)

        # Replacement process.
        self.registry.register_agent(
            agent_id="tracker-01",
            instance_id="tracker-01-instance-b",
            process_generation=2,
        )

        agent = self.registry.get_agent("tracker-01")

        self.assertIsNotNone(agent)

        assert agent is not None

        self.assertEqual(
            agent["instance_id"],
            "tracker-01-instance-b",
        )

        self.assertEqual(
            agent["process_generation"],
            2,
        )

        self.assertEqual(
            agent["status"],
            AgentRegistry.STARTING,
        )

        self.assertIsNone(
            agent["last_heartbeat"],
        )

        # Old process sends a delayed heartbeat.
        accepted = self.registry.update_heartbeat(
            agent_id="tracker-01",
            instance_id="tracker-01-instance-a",
            process_generation=1,
        )

        self.assertFalse(accepted)

        # Replacement must still be STARTING.
        agent = self.registry.get_agent("tracker-01")

        self.assertIsNotNone(agent)

        assert agent is not None

        self.assertEqual(
            agent["instance_id"],
            "tracker-01-instance-b",
        )

        self.assertEqual(
            agent["process_generation"],
            2,
        )

        self.assertEqual(
            agent["status"],
            AgentRegistry.STARTING,
        )

        self.assertIsNone(
            agent["last_heartbeat"],
        )

    # ================================================================
    # GENERATION PROTECTION
    # ================================================================

    def test_stale_process_generation_heartbeat_is_rejected(self) -> None:
        self.registry.register_agent(
            agent_id="tracker-01",
            instance_id="tracker-01-instance-b",
            process_generation=5,
        )

        accepted = self.registry.update_heartbeat(
            agent_id="tracker-01",
            instance_id="tracker-01-instance-b",
            process_generation=4,
        )

        self.assertFalse(accepted)

        agent = self.registry.get_agent("tracker-01")

        self.assertIsNotNone(agent)

        assert agent is not None

        self.assertEqual(
            agent["process_generation"],
            5,
        )

        self.assertEqual(
            agent["status"],
            AgentRegistry.STARTING,
        )

        self.assertIsNone(
            agent["last_heartbeat"],
        )

    def test_generation_rollback_is_rejected(self) -> None:
        self.registry.register_agent(
            agent_id="tracker-01",
            instance_id="tracker-01-instance-a",
            process_generation=5,
        )

        self.registry.register_agent(
            agent_id="tracker-01",
            instance_id="tracker-01-instance-old",
            process_generation=4,
        )

        agent = self.registry.get_agent("tracker-01")

        self.assertIsNotNone(agent)

        assert agent is not None

        self.assertEqual(
            agent["process_generation"],
            5,
        )

        self.assertEqual(
            agent["instance_id"],
            "tracker-01-instance-a",
        )

    # ================================================================
    # NEW PROCESS HEARTBEAT RESET
    # ================================================================

    def test_new_process_clears_previous_heartbeat(self) -> None:
        self.registry.register_agent(
            agent_id="tracker-01",
            instance_id="tracker-01-instance-a",
            process_generation=1,
        )

        accepted = self.registry.update_heartbeat(
            agent_id="tracker-01",
            instance_id="tracker-01-instance-a",
            process_generation=1,
        )

        self.assertTrue(accepted)

        old_agent = self.registry.get_agent("tracker-01")

        self.assertIsNotNone(old_agent)

        assert old_agent is not None

        self.assertIsNotNone(
            old_agent["last_heartbeat"],
        )

        # New process.
        self.registry.register_agent(
            agent_id="tracker-01",
            instance_id="tracker-01-instance-b",
            process_generation=2,
        )

        new_agent = self.registry.get_agent("tracker-01")

        self.assertIsNotNone(new_agent)

        assert new_agent is not None

        self.assertEqual(
            new_agent["status"],
            AgentRegistry.STARTING,
        )

        self.assertIsNone(
            new_agent["last_heartbeat"],
        )

        self.assertEqual(
            new_agent["instance_id"],
            "tracker-01-instance-b",
        )

        self.assertEqual(
            new_agent["process_generation"],
            2,
        )

    # ================================================================
    # LIFECYCLE TRANSITIONS
    # ================================================================

    def test_mark_dead_increments_failure_count(self) -> None:
        self.registry.register_agent(
            agent_id="tracker-01",
            instance_id="tracker-01-instance-a",
            process_generation=1,
        )

        self.registry.update_heartbeat(
            agent_id="tracker-01",
            instance_id="tracker-01-instance-a",
            process_generation=1,
        )

        self.assertTrue(
            self.registry.mark_dead("tracker-01"),
        )

        agent = self.registry.get_agent("tracker-01")

        self.assertIsNotNone(agent)

        assert agent is not None

        self.assertEqual(
            agent["status"],
            AgentRegistry.DEAD,
        )

        self.assertEqual(
            agent["failure_count"],
            1,
        )

    def test_repeated_mark_dead_does_not_double_increment(self) -> None:
        self.registry.register_agent(
            agent_id="tracker-01",
            instance_id="tracker-01-instance-a",
            process_generation=1,
        )

        self.assertTrue(
            self.registry.mark_dead("tracker-01"),
        )

        self.assertTrue(
            self.registry.mark_dead("tracker-01"),
        )

        agent = self.registry.get_agent("tracker-01")

        self.assertIsNotNone(agent)

        assert agent is not None

        self.assertEqual(
            agent["status"],
            AgentRegistry.DEAD,
        )

        self.assertEqual(
            agent["failure_count"],
            1,
        )

    def test_mark_recovering_clears_heartbeat(self) -> None:
        self.registry.register_agent(
            agent_id="tracker-01",
            instance_id="tracker-01-instance-a",
            process_generation=1,
        )

        self.registry.update_heartbeat(
            agent_id="tracker-01",
            instance_id="tracker-01-instance-a",
            process_generation=1,
        )

        self.assertTrue(
            self.registry.mark_recovering("tracker-01"),
        )

        agent = self.registry.get_agent("tracker-01")

        self.assertIsNotNone(agent)

        assert agent is not None

        self.assertEqual(
            agent["status"],
            AgentRegistry.RECOVERING,
        )

        self.assertIsNone(
            agent["last_heartbeat"],
        )

    def test_mark_starting_clears_heartbeat(self) -> None:
        self.registry.register_agent(
            agent_id="tracker-01",
            instance_id="tracker-01-instance-a",
            process_generation=1,
        )

        self.registry.update_heartbeat(
            agent_id="tracker-01",
            instance_id="tracker-01-instance-a",
            process_generation=1,
        )

        self.assertTrue(
            self.registry.mark_starting("tracker-01"),
        )

        agent = self.registry.get_agent("tracker-01")

        self.assertIsNotNone(agent)

        assert agent is not None

        self.assertEqual(
            agent["status"],
            AgentRegistry.STARTING,
        )

        self.assertIsNone(
            agent["last_heartbeat"],
        )

    # ================================================================
    # RECOVERY FLOW
    # ================================================================

    def test_recovery_flow_old_process_cannot_revive_new_process(
        self,
    ) -> None:
        # Generation 1.
        self.registry.register_agent(
            agent_id="tracker-01",
            instance_id="tracker-01-instance-a",
            process_generation=1,
        )

        self.assertTrue(
            self.registry.update_heartbeat(
                agent_id="tracker-01",
                instance_id="tracker-01-instance-a",
                process_generation=1,
            ),
        )

        self.assertTrue(
            self.registry.mark_dead("tracker-01"),
        )

        self.assertTrue(
            self.registry.mark_recovering("tracker-01"),
        )

        # Generation 2 starts.
        self.registry.register_agent(
            agent_id="tracker-01",
            instance_id="tracker-01-instance-b",
            process_generation=2,
        )

        # Old generation attempts to revive itself.
        self.assertFalse(
            self.registry.update_heartbeat(
                agent_id="tracker-01",
                instance_id="tracker-01-instance-a",
                process_generation=1,
            ),
        )

        agent = self.registry.get_agent("tracker-01")

        self.assertIsNotNone(agent)

        assert agent is not None

        self.assertEqual(
            agent["status"],
            AgentRegistry.STARTING,
        )

        self.assertIsNone(
            agent["last_heartbeat"],
        )

        # New generation becomes healthy.
        self.assertTrue(
            self.registry.update_heartbeat(
                agent_id="tracker-01",
                instance_id="tracker-01-instance-b",
                process_generation=2,
            ),
        )

        agent = self.registry.get_agent("tracker-01")

        self.assertIsNotNone(agent)

        assert agent is not None

        self.assertEqual(
            agent["status"],
            AgentRegistry.ALIVE,
        )

        self.assertEqual(
            agent["instance_id"],
            "tracker-01-instance-b",
        )

        self.assertEqual(
            agent["process_generation"],
            2,
        )

        self.assertIsNotNone(
            agent["last_heartbeat"],
        )

    # ================================================================
    # SNAPSHOT ISOLATION
    # ================================================================

    def test_get_agent_returns_detached_snapshot(self) -> None:
        self.registry.register_agent(
            agent_id="tracker-01",
            instance_id="tracker-01-instance-a",
            process_generation=1,
        )

        snapshot = self.registry.get_agent("tracker-01")

        self.assertIsNotNone(snapshot)

        assert snapshot is not None

        snapshot["status"] = AgentRegistry.DEAD

        internal = self.registry.get_agent("tracker-01")

        self.assertIsNotNone(internal)

        assert internal is not None

        self.assertEqual(
            internal["status"],
            AgentRegistry.STARTING,
        )

    def test_get_all_agents_returns_detached_snapshots(self) -> None:
        self.registry.register_agent(
            agent_id="tracker-01",
            instance_id="tracker-01-instance-a",
            process_generation=1,
        )

        self.registry.register_agent(
            agent_id="detector-01",
            instance_id="detector-01-instance-a",
            process_generation=1,
        )

        agents = self.registry.get_all_agents()

        self.assertEqual(
            len(agents),
            2,
        )

        agents["tracker-01"]["status"] = AgentRegistry.DEAD

        internal = self.registry.get_agent("tracker-01")

        self.assertIsNotNone(internal)

        assert internal is not None

        self.assertEqual(
            internal["status"],
            AgentRegistry.STARTING,
        )

    # ================================================================
    # REMOVE
    # ================================================================

    def test_remove_agent(self) -> None:
        self.registry.register_agent(
            agent_id="tracker-01",
            instance_id="tracker-01-instance-a",
            process_generation=1,
        )

        self.assertTrue(
            self.registry.remove_agent("tracker-01"),
        )

        self.assertIsNone(
            self.registry.get_agent("tracker-01"),
        )

        self.assertFalse(
            self.registry.remove_agent("tracker-01"),
        )

    # ================================================================
    # COUNT
    # ================================================================

    def test_count(self) -> None:
        self.assertEqual(
            self.registry.count(),
            0,
        )

        self.registry.register_agent(
            agent_id="tracker-01",
            instance_id="tracker-01-instance-a",
            process_generation=1,
        )

        self.registry.register_agent(
            agent_id="detector-01",
            instance_id="detector-01-instance-a",
            process_generation=1,
        )

        self.assertEqual(
            self.registry.count(),
            2,
        )

    # ================================================================
    # VALIDATION
    # ================================================================

    def test_empty_agent_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.registry.register_agent("")

    def test_empty_instance_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.registry.register_agent(
                agent_id="tracker-01",
                instance_id="",
            )

    def test_invalid_generation_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.registry.register_agent(
                agent_id="tracker-01",
                instance_id="tracker-01-instance-a",
                process_generation=0,
            )

    def test_negative_generation_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.registry.register_agent(
                agent_id="tracker-01",
                instance_id="tracker-01-instance-a",
                process_generation=-1,
            )

    # ================================================================
    # THREAD SAFETY
    # ================================================================

    def test_concurrent_registration_and_heartbeat(self) -> None:
        agent_count = 20

        def worker(index: int) -> None:
            agent_id = f"tracker-{index:02d}"
            instance_id = f"{agent_id}-instance-a"

            self.registry.register_agent(
                agent_id=agent_id,
                instance_id=instance_id,
                process_generation=1,
            )

            accepted = self.registry.update_heartbeat(
                agent_id=agent_id,
                instance_id=instance_id,
                process_generation=1,
            )

            self.assertTrue(accepted)

        threads = [
            threading.Thread(
                target=worker,
                args=(index,),
            )
            for index in range(agent_count)
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        self.assertEqual(
            self.registry.count(),
            agent_count,
        )

        agents = self.registry.get_all_agents()

        self.assertEqual(
            len(agents),
            agent_count,
        )

        for agent in agents.values():
            self.assertEqual(
                agent["status"],
                AgentRegistry.ALIVE,
            )

            self.assertIsNotNone(
                agent["last_heartbeat"],
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)