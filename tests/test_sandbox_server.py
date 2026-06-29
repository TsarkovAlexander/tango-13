import pytest
from httpx import ASGITransport, AsyncClient

from app.settings import Settings
from sandbox_executor.server import create_app


@pytest.mark.asyncio
async def test_sandbox_healthz_reports_ready() -> None:
    app = create_app(Settings(trace_stdout=False))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
@pytest.mark.parametrize("hook", ["ready", "validate", "run", "suspend", "resume", "terminate"])
async def test_lambda_microvm_lifecycle_hooks_acknowledge_requests(hook: str) -> None:
    app = create_app(Settings(trace_stdout=False))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/aws/lambda-microvms/runtime/v1/{hook}",
            json={"microvmId": "mvm-1", "runHookPayload": "run-1"},
        )

    assert response.status_code == 200
    assert response.json() == {"hook": hook, "status": "ok"}
