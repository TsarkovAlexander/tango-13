import pytest

from sandbox_executor.docker_gvisor import DockerGVisorExecutor
from sandbox_executor.firecracker import FirecrackerExecutor
from sandbox_executor.policies import (
    SandboxPolicy,
    SandboxPolicyError,
    SandboxRequest,
    validate_output_size,
)


@pytest.mark.asyncio
async def test_sandbox_blocks_network_access_by_default() -> None:
    result = await FirecrackerExecutor().execute(
        SandboxRequest(
            run_id="run-1",
            attempt_id="1",
            code="import socket\nsocket.socket()",
            policy=SandboxPolicy(allow_network=False),
        )
    )

    assert result.status == "failed"
    assert result.error == "sandbox policy blocks network access"
    assert result.network_allowed is False


@pytest.mark.asyncio
async def test_sandbox_returns_bounded_deterministic_result() -> None:
    result = await FirecrackerExecutor().execute(
        SandboxRequest(
            run_id="run-1",
            attempt_id="1",
            code="print('hello')",
            input={"b": 1, "a": 2},
        )
    )

    assert result.status == "succeeded"
    assert result.output["input_keys"] == ["a", "b"]
    assert len(result.output["code_sha256"]) == 64


@pytest.mark.asyncio
async def test_docker_gvisor_executor_runs_with_runsc_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_command = []
    captured_input = b""

    class FakeProcess:
        returncode = 0

        async def communicate(self, input: bytes) -> tuple[bytes, bytes]:
            nonlocal captured_input
            captured_input = input
            return b"hello\n", b""

    async def fake_create_subprocess_exec(*command: str, **_: object) -> FakeProcess:
        captured_command.extend(command)
        return FakeProcess()

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_create_subprocess_exec)

    result = await DockerGVisorExecutor().execute(
        SandboxRequest(run_id="run-1", attempt_id="1", code="print('hello')")
    )

    assert result.status == "succeeded"
    assert result.output["stdout"] == "hello\n"
    assert "--runtime" in captured_command
    assert "runsc" in captured_command
    assert "--network" in captured_command
    assert "none" in captured_command
    assert b"print('hello')" in captured_input


@pytest.mark.asyncio
async def test_docker_gvisor_executor_reports_nonzero_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeProcess:
        returncode = 1

        async def communicate(self, input: bytes) -> tuple[bytes, bytes]:
            return b"", b"boom\n"

    async def fake_create_subprocess_exec(*_: str, **__: object) -> FakeProcess:
        return FakeProcess()

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_create_subprocess_exec)

    result = await DockerGVisorExecutor().execute(
        SandboxRequest(run_id="run-1", attempt_id="1", code="raise RuntimeError('boom')")
    )

    assert result.status == "failed"
    assert result.error == "boom"
    assert result.output["exit_code"] == 1


def test_output_size_limit_is_enforced() -> None:
    with pytest.raises(SandboxPolicyError, match="sandbox output exceeds policy limit"):
        validate_output_size(b"too large", SandboxPolicy(max_output_bytes=3))
