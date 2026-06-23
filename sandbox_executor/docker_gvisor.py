import asyncio
import json
import re
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
class DockerRunResult:
    returncode: int
    stdout: bytes
    stderr: bytes


class DockerGVisorExecutor:
    """Local development executor using Docker with the gVisor runsc runtime."""

    def __init__(
        self,
        *,
        image: str = "python:3.12-slim",
        runtime: str = "runsc",
        cpus: str = "1",
        memory: str = "256m",
        pids_limit: int = 64,
    ) -> None:
        self.image = image
        self.runtime = runtime
        self.cpus = cpus
        self.memory = memory
        self.pids_limit = pids_limit

    async def execute(self, request: SandboxRequest) -> SandboxResult:
        container_name = _container_name(request.run_id, request.attempt_id)
        try:
            validate_request(request)
            completed = await self._run_container(request, container_name)
            combined_output = completed.stdout + completed.stderr
            validate_output_size(combined_output, request.policy)

            stdout = completed.stdout.decode("utf-8", errors="replace")
            stderr = completed.stderr.decode("utf-8", errors="replace")
            if completed.returncode != 0:
                return _result(
                    request,
                    status="failed",
                    error=stderr.strip() or f"sandbox exited with code {completed.returncode}",
                    output={
                        "stdout": stdout,
                        "stderr": stderr,
                        "exit_code": completed.returncode,
                    },
                )

            return _result(
                request,
                status="succeeded",
                output={
                    "stdout": stdout,
                    "stderr": stderr,
                    "exit_code": completed.returncode,
                    "runtime": self.runtime,
                    "image": self.image,
                },
            )
        except SandboxPolicyError as exc:
            return _result(request, status="failed", error=str(exc))
        except TimeoutError:
            await _force_remove_container(container_name)
            return _result(request, status="failed", error="sandbox execution timed out")
        except FileNotFoundError:
            return _result(request, status="failed", error="docker executable not found")

    async def _run_container(
        self,
        request: SandboxRequest,
        container_name: str,
    ) -> DockerRunResult:
        command = [
            "docker",
            "run",
            "--rm",
            "-i",
            "--name",
            container_name,
            "--runtime",
            self.runtime,
            "--network",
            "bridge" if request.policy.allow_network else "none",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=64m",
            "--workdir",
            "/tmp",
            "--cpus",
            self.cpus,
            "--memory",
            self.memory,
            "--pids-limit",
            str(self.pids_limit),
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            "65532:65532",
            "--env",
            "HOME=/tmp",
            "--env",
            "PYTHONDONTWRITEBYTECODE=1",
            self.image,
            "python",
            "-c",
            PYTHON_RUNNER,
        ]
        payload = json.dumps({"code": request.code, "input": request.input}).encode("utf-8")
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=payload),
                timeout=request.policy.timeout_seconds,
            )
        except TimeoutError:
            with suppress(ProcessLookupError):
                process.kill()
            await process.wait()
            raise
        return DockerRunResult(process.returncode or 0, stdout, stderr)


def _container_name(run_id: str, attempt_id: str) -> str:
    raw = f"tango-sandbox-{run_id}-{attempt_id}".lower()
    safe = re.sub(r"[^a-z0-9_.-]+", "-", raw).strip("-.")
    return safe[:128] or "tango-sandbox"


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


async def _force_remove_container(container_name: str) -> None:
    process = await asyncio.create_subprocess_exec(
        "docker",
        "rm",
        "-f",
        container_name,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await process.wait()
