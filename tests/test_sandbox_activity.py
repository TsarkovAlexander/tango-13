import pytest

from app.activities import sandbox
from app.settings import Settings


@pytest.mark.asyncio
async def test_sandbox_api_call_uses_broker_timeout_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_timeouts: list[float] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "run_id": "run-1",
                "attempt_id": "attempt-1",
                "status": "succeeded",
                "output": {"stdout": "ok\n"},
                "policy_version": "2026-06-23",
                "network_allowed": False,
            }

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            captured_timeouts.append(timeout)

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, *, json: dict) -> FakeResponse:
            return FakeResponse()

    async def capture_trace(*args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr(sandbox, "emit_trace", capture_trace)
    monkeypatch.setattr(sandbox.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(
        sandbox,
        "get_settings",
        lambda: Settings(
            trace_stdout=False,
            sandbox_api_url="http://127.0.0.1:8081",
            sandbox_timeout_seconds=10,
            broker_timeout_seconds=35,
        ),
    )

    result = await sandbox.sandbox_step(
        {
            "run_id": "run-1",
            "attempt_id": "attempt-1",
            "tenant_id": "tenant-a",
            "code": "print('ok')",
        }
    )

    assert result["status"] == "succeeded"
    assert captured_timeouts == [35]


@pytest.mark.asyncio
async def test_sandbox_api_call_uses_aws_iam_auth_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_headers: list[dict[str, str] | None] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "run_id": "run-1",
                "attempt_id": "attempt-1",
                "status": "succeeded",
                "output": {"stdout": "ok\n"},
                "policy_version": "2026-06-23",
                "network_allowed": False,
            }

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            pass

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(
            self,
            url: str,
            *,
            content: bytes,
            headers: dict[str, str] | None = None,
        ) -> FakeResponse:
            assert content
            captured_headers.append(headers)
            return FakeResponse()

    async def capture_trace(*args: object, **kwargs: object) -> None:
        return None

    def fake_sigv4_headers(url: str, payload: dict, region: str) -> dict[str, str]:
        assert url == "https://broker.lambda-url.us-east-1.on.aws/execute"
        assert payload["run_id"] == "run-1"
        assert region == "us-east-1"
        return {"Authorization": "AWS4-HMAC-SHA256 signed", "X-Amz-Date": "20260629T000000Z"}

    monkeypatch.setattr(sandbox, "emit_trace", capture_trace)
    monkeypatch.setattr(sandbox.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(sandbox, "_aws_sigv4_headers", fake_sigv4_headers)
    monkeypatch.setattr(
        sandbox,
        "get_settings",
        lambda: Settings(
            trace_stdout=False,
            sandbox_api_url="https://broker.lambda-url.us-east-1.on.aws",
            sandbox_api_auth="aws-iam",
            aws_region="us-east-1",
        ),
    )

    result = await sandbox.sandbox_step(
        {
            "run_id": "run-1",
            "attempt_id": "attempt-1",
            "tenant_id": "tenant-a",
            "code": "print('ok')",
        }
    )

    assert result["status"] == "succeeded"
    assert captured_headers == [
        {"Authorization": "AWS4-HMAC-SHA256 signed", "X-Amz-Date": "20260629T000000Z"}
    ]
