import pytest

from app.activities import run_steps
from app.settings import Settings
from app.tracing import TraceEvent


@pytest.mark.asyncio
async def test_workflow_steps_emit_trace_with_input_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    emitted: list[TraceEvent] = []

    async def capture_trace(event: TraceEvent, settings: Settings) -> None:
        emitted.append(event)

    monkeypatch.setattr(run_steps, "emit_trace", capture_trace)
    monkeypatch.setattr(run_steps, "get_settings", lambda: Settings(trace_stdout=False))

    payload = {"run_id": "run-1", "tenant_id": "tenant-a", "workflow_id": "workflow-1"}

    await run_steps.plan_step(payload)
    await run_steps.agent_task_step(payload)
    await run_steps.synthesize_step(payload)

    assert [event.step for event in emitted] == ["plan", "agent_task", "synthesis"]
    for event in emitted:
        assert event.trace_id == "run-1"
        assert event.run_id == "run-1"
        assert event.tenant_id == "tenant-a"
        assert event.workflow_id == "workflow-1"
        assert event.span_id
        assert event.status == "ok"
        assert event.input_ref == "run-input:run-1"
