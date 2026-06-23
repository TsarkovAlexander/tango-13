from temporalio.client import Client

from app.models import RunRequest
from app.settings import Settings
from app.workflows.multi_agent import MultiAgentWorkflow


async def start_run_workflow(
    *,
    settings: Settings,
    run_id: str,
    request: RunRequest,
) -> str:
    workflow_id = run_id
    client = await Client.connect(
        settings.temporal_address,
        namespace=settings.temporal_namespace,
    )
    await client.start_workflow(
        MultiAgentWorkflow.run,
        {
            "run_id": run_id,
            "tenant_id": request.tenant_id,
            "input": request.input,
        },
        id=workflow_id,
        task_queue=settings.temporal_task_queue,
    )
    return workflow_id


async def wait_run_workflow_result(*, settings: Settings, workflow_id: str) -> dict:
    client = await Client.connect(
        settings.temporal_address,
        namespace=settings.temporal_namespace,
    )
    handle = client.get_workflow_handle(workflow_id)
    return await handle.result()
