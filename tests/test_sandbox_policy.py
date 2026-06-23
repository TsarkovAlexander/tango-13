import pytest

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


def test_output_size_limit_is_enforced() -> None:
    with pytest.raises(SandboxPolicyError, match="sandbox output exceeds policy limit"):
        validate_output_size(b"too large", SandboxPolicy(max_output_bytes=3))
