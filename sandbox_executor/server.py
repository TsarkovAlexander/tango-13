from fastapi import FastAPI

from app.settings import Settings, get_settings
from sandbox_executor.executors import create_executor
from sandbox_executor.policies import SandboxRequest, SandboxResult


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    executor = create_executor(settings.sandbox_backend)
    app = FastAPI(title="Tango Sandbox Executor")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/execute", response_model=SandboxResult)
    async def execute(request: SandboxRequest) -> SandboxResult:
        return await executor.execute(request)

    @app.post("/aws/lambda-microvms/runtime/v1/{hook_name}")
    async def lifecycle_hook(hook_name: str) -> dict[str, str]:
        return {"hook": hook_name, "status": "ok"}

    return app


app = create_app()
