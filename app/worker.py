import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from app.activities.run_steps import agent_task_step, plan_step, synthesize_step
from app.activities.sandbox import sandbox_step
from app.settings import get_settings
from app.workflows.multi_agent import MultiAgentWorkflow


async def main() -> None:
    settings = get_settings()
    client = await Client.connect(
        settings.temporal_address,
        namespace=settings.temporal_namespace,
    )
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[MultiAgentWorkflow],
        activities=[plan_step, agent_task_step, sandbox_step, synthesize_step],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
