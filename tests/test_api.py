import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models import RunEvent, RunStatus
from app.settings import Settings


@pytest.mark.asyncio
async def test_create_run_records_status_projection() -> None:
    app = create_app(Settings(temporal_start_enabled=False, trace_stdout=False))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/runs", json={"tenant_id": "tenant-a", "input": {}})

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "accepted"
    assert body["run_id"].startswith("run-")

    projection = app.state.run_projection
    assert await projection.latest_status(body["run_id"]) in {RunStatus.ACCEPTED, RunStatus.RUNNING}


@pytest.mark.asyncio
async def test_unknown_run_events_returns_404() -> None:
    app = create_app(Settings(temporal_start_enabled=False, trace_stdout=False))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/runs/missing/events")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_completed_history_stream_stops_after_terminal_event() -> None:
    app = create_app(Settings(temporal_start_enabled=False, trace_stdout=False))
    projection = app.state.run_projection
    await projection.publish(
        RunEvent(
            run_id="run-complete",
            status=RunStatus.SUCCEEDED,
            step="temporal.completed",
            message="done",
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/runs/run-complete/events")

    assert response.status_code == 200
    assert "event: succeeded" in response.text
