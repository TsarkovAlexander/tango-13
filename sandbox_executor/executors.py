from typing import Literal

from sandbox_executor.firecracker import FirecrackerExecutor
from sandbox_executor.microvm_python import MicrovmPythonExecutor

SandboxBackend = Literal["policy", "microvm-python"]


def create_executor(
    backend: SandboxBackend = "policy",
) -> FirecrackerExecutor | MicrovmPythonExecutor:
    if backend == "microvm-python":
        return MicrovmPythonExecutor()
    return FirecrackerExecutor()
