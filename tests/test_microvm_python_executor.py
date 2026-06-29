import pytest

from sandbox_executor.microvm_python import MicrovmPythonExecutor
from sandbox_executor.policies import SandboxPolicy, SandboxRequest


@pytest.mark.asyncio
async def test_microvm_python_executor_runs_code_in_python_subprocess() -> None:
    result = await MicrovmPythonExecutor().execute(
        SandboxRequest(
            run_id="run-1",
            attempt_id="attempt-1",
            code="print(SANDBOX_INPUT['message'])",
            input={"message": "hello from microvm"},
        )
    )

    assert result.status == "succeeded"
    assert result.output["stdout"] == "hello from microvm\n"
    assert result.output["exit_code"] == 0
    assert result.network_allowed is False


@pytest.mark.asyncio
async def test_microvm_python_executor_enforces_network_policy_before_execution() -> None:
    result = await MicrovmPythonExecutor().execute(
        SandboxRequest(
            run_id="run-1",
            attempt_id="attempt-1",
            code="import socket\nsocket.socket()",
            policy=SandboxPolicy(allow_network=False),
        )
    )

    assert result.status == "failed"
    assert result.error == "sandbox policy blocks network access"


@pytest.mark.asyncio
async def test_microvm_python_executor_kills_process_when_output_exceeds_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeStream:
        def __init__(self, chunks: list[bytes]) -> None:
            self.chunks = chunks

        async def read(self, _: int = -1) -> bytes:
            if not self.chunks:
                return b""
            return self.chunks.pop(0)

    class FakeProcess:
        def __init__(self) -> None:
            self.returncode = 0
            self.stdout = FakeStream([b"too ", b"large"])
            self.stderr = FakeStream([])
            self.killed = False

        async def communicate(self, input: bytes) -> tuple[bytes, bytes]:
            return b"too large", b""

        def kill(self) -> None:
            self.killed = True

        async def wait(self) -> int:
            return self.returncode

    process = FakeProcess()

    async def fake_create_subprocess_exec(*args: object, **kwargs: object) -> FakeProcess:
        return process

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_create_subprocess_exec)

    result = await MicrovmPythonExecutor().execute(
        SandboxRequest(
            run_id="run-1",
            attempt_id="attempt-1",
            code="print('too large')",
            policy=SandboxPolicy(max_output_bytes=3),
        )
    )

    assert result.status == "failed"
    assert result.error == "sandbox output exceeds policy limit"
    assert process.killed is True
