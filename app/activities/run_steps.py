from time import monotonic
from typing import Any
from uuid import uuid4

from temporalio import activity

from app.settings import get_settings
from app.tracing import TraceEvent, emit_trace


@activity.defn
async def plan_step(payload: dict[str, Any]) -> dict[str, Any]:
    return await _traced_step(payload, "plan", {"next": ["agent_task", "sandbox", "synthesis"]})


@activity.defn
async def agent_task_step(payload: dict[str, Any]) -> dict[str, Any]:
    return await _traced_step(payload, "agent_task", {"status": "prepared"})


@activity.defn
async def synthesize_step(payload: dict[str, Any]) -> dict[str, Any]:
    return await _traced_step(payload, "synthesis", {"status": "complete", "sandbox": payload})


async def _traced_step(
    payload: dict[str, Any],
    step: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    settings = get_settings()
    started_at = monotonic()
    status = "ok"
    error = None
    try:
        return result
    except Exception as exc:
        status = "error"
        error = str(exc)
        raise
    finally:
        duration_ms = int((monotonic() - started_at) * 1000)
        await emit_trace(
            TraceEvent(
                trace_id=payload["run_id"],
                run_id=payload["run_id"],
                tenant_id=payload["tenant_id"],
                workflow_id=payload.get("workflow_id"),
                step=step,
                span_id=uuid4().hex,
                status=status,
                error=error,
                duration_ms=duration_ms,
                metadata={"input_ref": f"run-input:{payload['run_id']}"},
            ),
            settings,
        )
