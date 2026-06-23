from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.activities.run_steps import agent_task_step, plan_step, synthesize_step
    from app.activities.sandbox import sandbox_step


@workflow.defn
class MultiAgentWorkflow:
    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        workflow_id = workflow.info().workflow_id
        base_payload = {**payload, "workflow_id": workflow_id}

        plan = await _activity(plan_step, base_payload)
        agent_result = await _activity(agent_task_step, {**base_payload, "plan": plan})
        sandbox_result = await _activity(
            sandbox_step,
            {
                **base_payload,
                "attempt_id": str(workflow.info().attempt),
                "code": payload.get("input", {}).get("code", ""),
                "agent_result": agent_result,
            },
        )
        return await _activity(synthesize_step, {**base_payload, "sandbox": sandbox_result})


async def _activity(activity_fn: Any, payload: dict[str, Any]) -> dict[str, Any]:
    return await workflow.execute_activity(
        activity_fn,
        payload,
        start_to_close_timeout=timedelta(seconds=30),
        schedule_to_close_timeout=timedelta(minutes=2),
        heartbeat_timeout=timedelta(seconds=10),
        retry_policy=RetryPolicy(maximum_attempts=3),
    )
