from typing import Literal

from sandbox_executor.docker_gvisor import DockerGVisorExecutor
from sandbox_executor.firecracker import FirecrackerExecutor

SandboxBackend = Literal["policy", "docker-gvisor"]


def create_executor(
    backend: SandboxBackend = "policy",
    *,
    docker_image: str = "python:3.12-slim",
    docker_runtime: str = "runsc",
    docker_cpus: str = "1",
    docker_memory: str = "256m",
    docker_pids_limit: int = 64,
) -> FirecrackerExecutor | DockerGVisorExecutor:
    if backend == "docker-gvisor":
        return DockerGVisorExecutor(
            image=docker_image,
            runtime=docker_runtime,
            cpus=docker_cpus,
            memory=docker_memory,
            pids_limit=docker_pids_limit,
        )
    return FirecrackerExecutor()
