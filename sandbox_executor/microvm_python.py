import asyncio
import json
import sys
from contextlib import suppress
from dataclasses import dataclass

from sandbox_executor.policies import (
    SandboxPolicyError,
    SandboxRequest,
    SandboxResult,
    validate_output_size,
    validate_request,
)

PYTHON_RUNNER = """
import json
import sys

payload = json.load(sys.stdin)
SANDBOX_INPUT = payload.get("input", {})
code = payload.get("code", "")
exec(compile(code, "<sandbox>", "exec"), {"SANDBOX_INPUT": SANDBOX_INPUT})
""".strip()


@dataclass(frozen=True)
class PythonRunResult:
    returncode: int
    stdout: bytes
    stderr: bytes


class MicrovmPythonExecutor:
    """Executor used inside a fresh Lambda MicroVM for one sandbox attempt."""

    async def execute(self, request: SandboxRequest) -> SandboxResult:
        try:
            validate_request(request)
            completed = await self._run_python(request)
            combined_output = completed.stdout + completed.stderr
            validate_output_size(combined_output, request.policy)

            stdout = completed.stdout.decode("utf-8", errors="replace")
            stderr = completed.stderr.decode("utf-8", errors="replace")
            if completed.returncode != 0:
                return _result(
                    request,
                    status="failed",
                    error=stderr.strip() or f"sandbox exited with code {completed.returncode}",
                    output={"stdout": stdout, "stderr": stderr, "exit_code": completed.returncode},
                )

            return _result(
                request,
                status="succeeded",
                output={
                    "stdout": stdout,
                    "stderr": stderr,
                    "exit_code": completed.returncode,
                    "runtime": "microvm-python",
                },
            )
        except SandboxPolicyError as exc:
            return _result(request, status="failed", error=str(exc))
        except TimeoutError:
            return _result(request, status="failed", error="sandbox execution timed out")

    async def _run_python(self, request: SandboxRequest) -> PythonRunResult:
        payload = json.dumps({"code": request.code, "input": request.input}).encode("utf-8")
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-I",
            "-c",
            PYTHON_RUNNER,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_buffer = bytearray()
        stderr_buffer = bytearray()
        total_output_bytes = 0

        async def read_stream(stream: asyncio.StreamReader | None, buffer: bytearray) -> None:
            nonlocal total_output_bytes
            if stream is None:
                return
            while True:
                chunk = await stream.read(4096)
                if not chunk:
                    return
                total_output_bytes += len(chunk)
                if total_output_bytes > request.policy.max_output_bytes:
                    raise SandboxPolicyError("sandbox output exceeds policy limit")
                buffer.extend(chunk)

        stdin = getattr(process, "stdin", None)
        if stdin is not None:
            stdin.write(payload)
            with suppress(BrokenPipeError, ConnectionResetError):
                await stdin.drain()
            stdin.close()
            wait_closed = getattr(stdin, "wait_closed", None)
            if wait_closed is not None:
                with suppress(BrokenPipeError, ConnectionResetError):
                    await wait_closed()

        try:
            await asyncio.wait_for(
                asyncio.gather(
                    read_stream(process.stdout, stdout_buffer),
                    read_stream(process.stderr, stderr_buffer),
                ),
                timeout=request.policy.timeout_seconds,
            )
            await process.wait()
        except TimeoutError:
            with suppress(ProcessLookupError):
                process.kill()
            await process.wait()
            raise
        except SandboxPolicyError:
            with suppress(ProcessLookupError):
                process.kill()
            await process.wait()
            raise
        return PythonRunResult(process.returncode or 0, bytes(stdout_buffer), bytes(stderr_buffer))


def _result(
    request: SandboxRequest,
    *,
    status: str,
    output: dict | None = None,
    error: str | None = None,
) -> SandboxResult:
    return SandboxResult(
        run_id=request.run_id,
        attempt_id=request.attempt_id,
        status=status,
        output=output or {},
        error=error,
        policy_version=request.policy.version,
        network_allowed=request.policy.allow_network,
    )
