from fastapi import FastAPI

from sandbox_executor.firecracker import FirecrackerExecutor
from sandbox_executor.policies import SandboxRequest, SandboxResult


def create_app() -> FastAPI:
    executor = FirecrackerExecutor()
    app = FastAPI(title="Tango Sandbox Executor")

    @app.post("/execute", response_model=SandboxResult)
    async def execute(request: SandboxRequest) -> SandboxResult:
        return await executor.execute(request)

    return app


app = create_app()
