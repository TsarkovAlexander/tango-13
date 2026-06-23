import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from app.models import RunEvent, RunRequest, RunResponse, RunStatus, new_run_id
from app.settings import Settings, get_settings
from app.status import RunStatusProjection
from app.temporal_client import start_run_workflow, wait_run_workflow_result


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    projection = RunStatusProjection(queue_size=resolved_settings.run_event_queue_size)

    app = FastAPI(title="Tango Sandbox API")
    app.state.settings = resolved_settings
    app.state.run_projection = projection

    @app.post("/runs", response_model=RunResponse, status_code=202)
    async def create_run(request: RunRequest) -> RunResponse:
        run_id = new_run_id()
        workflow_id = run_id
        await projection.publish(
            RunEvent(
                run_id=run_id,
                status=RunStatus.ACCEPTED,
                step="api.accepted",
                message="Run accepted",
                details={"tenant_id": request.tenant_id},
            )
        )

        if resolved_settings.temporal_start_enabled:
            workflow_id = await start_run_workflow(
                settings=resolved_settings,
                run_id=run_id,
                request=request,
            )
            await projection.publish(
                RunEvent(
                    run_id=run_id,
                    status=RunStatus.RUNNING,
                    step="temporal.started",
                    message="Temporal workflow started",
                    details={"workflow_id": workflow_id},
                )
            )
            asyncio.create_task(
                _project_temporal_completion(
                    settings=resolved_settings,
                    projection=projection,
                    run_id=run_id,
                    workflow_id=workflow_id,
                )
            )
        else:
            asyncio.create_task(_publish_local_demo_status(projection, run_id))

        return RunResponse(run_id=run_id, workflow_id=workflow_id, status=RunStatus.ACCEPTED)

    @app.get("/runs/{run_id}/events")
    async def run_events(
        run_id: str,
        status_projection: RunStatusProjection = Depends(lambda: projection),
    ) -> StreamingResponse:
        if await status_projection.latest_status(run_id) is None:
            raise HTTPException(status_code=404, detail="run not found")
        return StreamingResponse(
            _sse_events(status_projection, run_id),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    return app


async def _publish_local_demo_status(projection: RunStatusProjection, run_id: str) -> None:
    await asyncio.sleep(0)
    await projection.publish(
        RunEvent(
            run_id=run_id,
            status=RunStatus.RUNNING,
            step="local.placeholder",
            message="Temporal start is disabled; run recorded in local projection only",
        )
    )


async def _project_temporal_completion(
    *,
    settings: Settings,
    projection: RunStatusProjection,
    run_id: str,
    workflow_id: str,
) -> None:
    try:
        result = await wait_run_workflow_result(settings=settings, workflow_id=workflow_id)
        await projection.publish(
            RunEvent(
                run_id=run_id,
                status=RunStatus.SUCCEEDED,
                step="temporal.completed",
                message="Temporal workflow completed",
                details={"workflow_id": workflow_id, "result": result},
            )
        )
    except Exception as exc:
        await projection.publish(
            RunEvent(
                run_id=run_id,
                status=RunStatus.FAILED,
                step="temporal.failed",
                message="Temporal workflow failed",
                details={"workflow_id": workflow_id, "error": str(exc)},
            )
        )


async def _sse_events(projection: RunStatusProjection, run_id: str) -> AsyncIterator[str]:
    async for event in projection.events(run_id):
        yield f"event: {event.status.value}\ndata: {json.dumps(event.model_dump(mode='json'))}\n\n"


app = create_app()
