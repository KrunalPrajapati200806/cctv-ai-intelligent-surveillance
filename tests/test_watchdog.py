import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from backend.app.monitoring.agent_registry import AgentRegistry
from backend.app.monitoring import watchdog

class TestWatchdogHealthObservation(unittest.TestCase):
    """Tests for deterministic watchdog health observation."""

    def setUp(self) -> None:
        self.registry = AgentRegistry()
        self.agent_id = "watchdog-test-agent-01"

    def test_starting_agent_is_reported_as_starting(self) -> None:
        self.registry.register_agent(
            agent_id=self.agent_id,
            instance_id=f"{self.agent_id}-instance-01",
            hostname="test-host",
        )

        snapshot = watchdog.check_agent_health(self.registry)

        self.assertIn(self.agent_id, snapshot)

        observation = snapshot[self.agent_id]

        self.assertEqual(
            observation["agent_id"],
            self.agent_id,
        )
        self.assertEqual(
            observation["health"],
            "STARTING",
        )
        self.assertIsNone(
            observation["heartbeat_age"],
        )

    def test_recent_heartbeat_is_healthy(self) -> None:
        self.registry.register_agent(
            agent_id=self.agent_id,
            instance_id=f"{self.agent_id}-instance-01",
            hostname="test-host",
        )

        accepted = self.registry.update_heartbeat(
            agent_id=self.agent_id,
            instance_id=f"{self.agent_id}-instance-01",
            hostname="test-host",
        )

        self.assertTrue(accepted)

        snapshot = watchdog.check_agent_health(
            self.registry
        )

        observation = snapshot[self.agent_id]

        self.assertEqual(
            observation["health"],
            "HEALTHY",
        )
        self.assertIsNotNone(
            observation["heartbeat_age"],
        )
        self.assertGreaterEqual(
            observation["heartbeat_age"],
            0,
        )

    def test_old_heartbeat_is_stale(self) -> None:
        self.registry.register_agent(
            agent_id=self.agent_id,
            instance_id=f"{self.agent_id}-instance-01",
            hostname="test-host",
        )

        old_timestamp = (
            datetime.now(timezone.utc)
            - timedelta(
                seconds=watchdog.HEARTBEAT_TIMEOUT + 10
            )
        )

        agent = self.registry.get_agent(
            self.agent_id
        )

        self.assertIsNotNone(agent)

        # Patch the registry timestamp directly only for
        # deterministic watchdog observation testing.
        with patch.object(
            self.registry,
            "get_all_agents",
            return_value={
                self.agent_id: {
                    **agent,
                    "status": "ALIVE",
                    "last_heartbeat": old_timestamp,
                }
            },
        ):
            snapshot = watchdog.check_agent_health(
                self.registry
            )

        observation = snapshot[self.agent_id]

        self.assertEqual(
            observation["health"],
            "STALE",
        )

        self.assertGreater(
            observation["heartbeat_age"],
            watchdog.HEARTBEAT_TIMEOUT,
        )

    def test_dead_registry_state_is_reported_as_dead(self) -> None:
        self.registry.register_agent(
            agent_id=self.agent_id,
            instance_id=f"{self.agent_id}-instance-01",
            hostname="test-host",
        )

        self.registry.mark_dead(
            self.agent_id
        )

        snapshot = watchdog.check_agent_health(
            self.registry
        )

        self.assertEqual(
            snapshot[self.agent_id]["health"],
            "DEAD",
        )

    def test_recovering_registry_state_is_reported_as_recovering(
        self,
    ) -> None:
        self.registry.register_agent(
            agent_id=self.agent_id,
            instance_id=f"{self.agent_id}-instance-01",
            hostname="test-host",
        )

        self.registry.mark_recovering(
            self.agent_id
        )

        snapshot = watchdog.check_agent_health(
            self.registry
        )

        self.assertEqual(
            snapshot[self.agent_id]["health"],
            "RECOVERING",
        )

    def test_future_heartbeat_is_not_reported_as_healthy(self) -> None:
        self.registry.register_agent(
            agent_id=self.agent_id,
            instance_id=f"{self.agent_id}-instance-01",
            hostname="test-host",
        )

        agent = self.registry.get_agent(
            self.agent_id
        )

        self.assertIsNotNone(agent)

        future_timestamp = (
            datetime.now(timezone.utc)
            + timedelta(seconds=60)
        )

        with patch.object(
            self.registry,
            "get_all_agents",
            return_value={
                self.agent_id: {
                    **agent,
                    "status": "ALIVE",
                    "last_heartbeat": future_timestamp,
                }
            },
        ):
            snapshot = watchdog.check_agent_health(
                self.registry
            )

        self.assertEqual(
            snapshot[self.agent_id]["health"],
            "UNKNOWN",
        )

    def test_naive_timestamp_is_treated_as_utc(self) -> None:
        timestamp = datetime.utcnow()

        normalized = watchdog._normalize_timestamp(
            timestamp
        )

        self.assertIsNotNone(normalized)
        self.assertEqual(
            normalized.tzinfo,
            timezone.utc,
        )

    def test_invalid_timestamp_does_not_crash_watchdog(self) -> None:
        self.registry.register_agent(
            agent_id=self.agent_id,
            instance_id=f"{self.agent_id}-instance-01",
            hostname="test-host",
        )

        agent = self.registry.get_agent(
            self.agent_id
        )

        self.assertIsNotNone(agent)

        with patch.object(
            self.registry,
            "get_all_agents",
            return_value={
                self.agent_id: {
                    **agent,
                    "status": "ALIVE",
                    "last_heartbeat": "INVALID-TIMESTAMP",
                }
            },
        ):
            snapshot = watchdog.check_agent_health(
                self.registry
            )

        observation = snapshot[self.agent_id]

        self.assertEqual(
            observation["health"],
            "UNKNOWN",
        )
        self.assertIsNone(
            observation["heartbeat_age"],
        )

    def test_one_malformed_agent_does_not_break_other_agents(
        self,
    ) -> None:
        healthy_agent_id = (
            "watchdog-healthy-agent"
        )
        broken_agent_id = (
            "watchdog-broken-agent"
        )

        self.registry.register_agent(
            agent_id=healthy_agent_id,
            instance_id="healthy-instance",
            hostname="healthy-host",
        )

        self.registry.update_heartbeat(
            agent_id=healthy_agent_id,
            instance_id="healthy-instance",
            hostname="healthy-host",
        )

        healthy_agent = self.registry.get_agent(
            healthy_agent_id
        )

        self.assertIsNotNone(healthy_agent)

        broken_agent = {
            "agent_id": broken_agent_id,
            "status": "ALIVE",
            "instance_id": "broken-instance",
            "hostname": "broken-host",
            "last_heartbeat": object(),
        }

        with patch.object(
            self.registry,
            "get_all_agents",
            return_value={
                healthy_agent_id: healthy_agent,
                broken_agent_id: broken_agent,
            },
        ):
            snapshot = watchdog.check_agent_health(
                self.registry
            )

        self.assertIn(
            healthy_agent_id,
            snapshot,
        )
        self.assertIn(
            broken_agent_id,
            snapshot,
        )

        self.assertEqual(
            snapshot[healthy_agent_id]["health"],
            "HEALTHY",
        )

        self.assertEqual(
            snapshot[broken_agent_id]["health"],
            "UNKNOWN",
        )

    def test_check_agent_health_does_not_mutate_registry(
        self,
    ) -> None:
        self.registry.register_agent(
            agent_id=self.agent_id,
            instance_id=f"{self.agent_id}-instance-01",
            hostname="test-host",
        )

        self.registry.update_heartbeat(
            agent_id=self.agent_id,
            instance_id=f"{self.agent_id}-instance-01",
            hostname="test-host",
        )

        before = self.registry.get_agent(
            self.agent_id
        )

        watchdog.check_agent_health(
            self.registry
        )

        after = self.registry.get_agent(
            self.agent_id
        )

        self.assertEqual(
            before,
            after,
        )


class TestWatchdogLoop(unittest.IsolatedAsyncioTestCase):
    """Tests for watchdog lifecycle and fault isolation."""

    async def test_watchdog_loop_can_be_cancelled_cleanly(
        self,
    ) -> None:
        registry = AgentRegistry()

        task = asyncio.create_task(
            watchdog.watchdog_loop(
                registry=registry,
                check_interval=0.01,
            )
        )

        await asyncio.sleep(0.03)

        task.cancel()

        with self.assertRaises(
            asyncio.CancelledError
        ):
            await task

        self.assertTrue(
            task.cancelled()
        )

    async def test_watchdog_loop_survives_check_failure(
        self,
    ) -> None:
        registry = AgentRegistry()

        original_check = (
            watchdog.check_agent_health
        )

        call_count = 0

        def failing_then_healthy_check(
            registry_arg,
        ):
            nonlocal call_count

            call_count += 1

            if call_count == 1:
                raise RuntimeError(
                    "simulated watchdog failure"
                )

            return original_check(
                registry_arg
            )

        with patch.object(
            watchdog,
            "check_agent_health",
            side_effect=failing_then_healthy_check,
        ):
            task = asyncio.create_task(
                watchdog.watchdog_loop(
                    registry=registry,
                    check_interval=0.01,
                )
            )

            try:
                await asyncio.sleep(0.05)

                self.assertGreaterEqual(
                    call_count,
                    2,
                )

                self.assertFalse(
                    task.done()
                )

            finally:
                task.cancel()

                with self.assertRaises(
                    asyncio.CancelledError
                ):
                    await task

    async def test_watchdog_loop_rejects_invalid_interval(
        self,
    ) -> None:
        registry = AgentRegistry()

        with self.assertRaises(
            ValueError
        ):
            await watchdog.watchdog_loop(
                registry=registry,
                check_interval=0,
            )


if __name__ == "__main__":
    unittest.main()