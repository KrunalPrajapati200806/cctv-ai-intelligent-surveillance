import asyncio

from shared.agent.base_agent import BaseAgent


class TestAgent(BaseAgent):
    async def on_start(self):
        print(f"[{self.agent_id}] on_start() called")

    async def on_stop(self):
        print(f"[{self.agent_id}] on_stop() called")

    async def run(self):
        print(f"[{self.agent_id}] run() started")

        # Keep the test alive long enough to observe heartbeat.
        await asyncio.sleep(25)

        print(f"[{self.agent_id}] run() completed")


async def main():
    agent = TestAgent(
        agent_id="base-agent-test-01",
        heartbeat_interval=5,
    )

    await agent.run_forever()


if __name__ == "__main__":
    asyncio.run(main())