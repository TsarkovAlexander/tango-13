import json

import pytest

from app.settings import Settings
from sandbox_executor.microvm_broker import LambdaMicrovmBroker, _microvm_execute_url
from sandbox_executor.policies import SandboxPolicy, SandboxRequest


class FakeMicrovmClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def run_microvm(self, **kwargs: object) -> dict:
        self.calls.append(("run_microvm", kwargs))
        return {
            "microvmId": "mvm-1",
            "state": "PENDING",
            "endpoint": "mvm-1.lambda-microvm.us-east-1.on.aws",
        }

    def get_microvm(self, **kwargs: object) -> dict:
        self.calls.append(("get_microvm", kwargs))
        return {"state": "RUNNING"}

    def create_microvm_auth_token(self, **kwargs: object) -> dict:
        self.calls.append(("create_microvm_auth_token", kwargs))
        return {"authToken": {"X-aws-proxy-auth": "token-1"}}

    def terminate_microvm(self, **kwargs: object) -> dict:
        self.calls.append(("terminate_microvm", kwargs))
        return {}


@pytest.mark.asyncio
async def test_microvm_broker_runs_invokes_and_terminates_microvm() -> None:
    client = FakeMicrovmClient()
    posted: list[dict] = []

    async def post_execute(url: str, headers: dict[str, str], payload: dict, timeout: int) -> dict:
        posted.append({"url": url, "headers": headers, "payload": payload, "timeout": timeout})
        return {
            "run_id": "run-1",
            "attempt_id": "attempt-1",
            "status": "succeeded",
            "output": {"stdout": "hello\n"},
            "policy_version": "2026-06-23",
            "network_allowed": False,
        }

    broker = LambdaMicrovmBroker(
        settings=Settings(
            trace_stdout=False,
            lambda_microvm_image_identifier="arn:aws:lambda:us-east-1:569813798269:microvm-image:tango",
        ),
        microvm_client=client,
        post_execute=post_execute,
    )
    request = SandboxRequest(
        run_id="run-1",
        attempt_id="attempt-1",
        code="print('hello')",
        policy=SandboxPolicy(allow_network=False),
    )

    result = await broker.execute(request)

    assert result.status == "succeeded"
    assert posted == [
        {
            "url": "https://mvm-1.lambda-microvm.us-east-1.on.aws/execute",
            "headers": {"X-aws-proxy-auth": "token-1", "X-aws-proxy-port": "8080"},
            "payload": request.model_dump(mode="json"),
            "timeout": 10,
        }
    ]
    assert [name for name, _ in client.calls] == [
        "run_microvm",
        "get_microvm",
        "create_microvm_auth_token",
        "terminate_microvm",
    ]
    assert client.calls[0][1]["imageIdentifier"] == (
        "arn:aws:lambda:us-east-1:569813798269:microvm-image:tango"
    )
    assert client.calls[0][1]["egressNetworkConnectors"] == []
    assert "runHookPayload" not in client.calls[0][1]
    assert client.calls[2][1]["allowedPorts"] == [{"port": 8080}]
    assert client.calls[-1][1] == {"microvmIdentifier": "mvm-1"}


def test_microvm_broker_includes_run_hook_payload_when_enabled() -> None:
    broker = LambdaMicrovmBroker(
        settings=Settings(
            trace_stdout=False,
            lambda_microvm_image_identifier="arn:aws:lambda:us-east-1:569813798269:microvm-image:tango",
            lambda_microvm_run_hook_payload_enabled=True,
        ),
        microvm_client=FakeMicrovmClient(),
    )
    params = broker._run_microvm_params(
        SandboxRequest(run_id="run-1", attempt_id="attempt-1", code="")
    )

    assert json.loads(params["runHookPayload"]) == {
        "run_id": "run-1",
        "attempt_id": "attempt-1",
    }


@pytest.mark.asyncio
async def test_microvm_broker_terminates_microvm_when_invoke_fails() -> None:
    client = FakeMicrovmClient()

    async def post_execute(
        url: str,
        headers: dict[str, str],
        payload: dict,
        timeout: int,
    ) -> dict:
        raise RuntimeError("invoke failed")

    broker = LambdaMicrovmBroker(
        settings=Settings(
            trace_stdout=False,
            lambda_microvm_image_identifier="arn:aws:lambda:us-east-1:569813798269:microvm-image:tango",
        ),
        microvm_client=client,
        post_execute=post_execute,
    )

    with pytest.raises(RuntimeError, match="invoke failed"):
        await broker.execute(SandboxRequest(run_id="run-1", attempt_id="attempt-1", code=""))

    assert client.calls[-1] == ("terminate_microvm", {"microvmIdentifier": "mvm-1"})


def test_microvm_execute_url_accepts_host_or_full_url() -> None:
    assert (
        _microvm_execute_url("mvm-1.lambda-microvm.us-east-1.on.aws")
        == "https://mvm-1.lambda-microvm.us-east-1.on.aws/execute"
    )
    assert (
        _microvm_execute_url("https://mvm-1.lambda-microvm.us-east-1.on.aws")
        == "https://mvm-1.lambda-microvm.us-east-1.on.aws/execute"
    )
    assert (
        _microvm_execute_url("https://mvm-1.lambda-microvm.us-east-1.on.aws/")
        == "https://mvm-1.lambda-microvm.us-east-1.on.aws/execute"
    )


@pytest.mark.asyncio
async def test_microvm_broker_runs_aws_sdk_calls_off_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeMicrovmClient()
    threaded_calls: list[str] = []

    async def fake_to_thread(func, /, *args, **kwargs):  # type: ignore[no-untyped-def]
        threaded_calls.append(func.__name__)
        return func(*args, **kwargs)

    async def post_execute(url: str, headers: dict[str, str], payload: dict, timeout: int) -> dict:
        return {
            "run_id": "run-1",
            "attempt_id": "attempt-1",
            "status": "succeeded",
            "output": {"stdout": "hello\n"},
            "policy_version": "2026-06-23",
            "network_allowed": False,
        }

    monkeypatch.setattr("asyncio.to_thread", fake_to_thread)
    broker = LambdaMicrovmBroker(
        settings=Settings(
            trace_stdout=False,
            lambda_microvm_image_identifier="arn:aws:lambda:us-east-1:569813798269:microvm-image:tango",
        ),
        microvm_client=client,
        post_execute=post_execute,
    )

    await broker.execute(SandboxRequest(run_id="run-1", attempt_id="attempt-1", code=""))

    assert threaded_calls == [
        "run_microvm",
        "get_microvm",
        "create_microvm_auth_token",
        "terminate_microvm",
    ]
