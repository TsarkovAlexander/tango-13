from fastapi import FastAPI

from app.settings import Settings, get_settings
from sandbox_executor.executors import create_executor
from sandbox_executor.policies import SandboxRequest, SandboxResult


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    executor = create_executor(
        settings.sandbox_backend,
        docker_image=settings.sandbox_docker_image,
        docker_runtime=settings.sandbox_docker_runtime,
        docker_cpus=settings.sandbox_docker_cpus,
        docker_memory=settings.sandbox_docker_memory,
        docker_pids_limit=settings.sandbox_docker_pids_limit,
    )
    app = FastAPI(title="Tango Sandbox Executor")

    @app.post("/execute", response_model=SandboxResult)
    async def execute(request: SandboxRequest) -> SandboxResult:
        return await executor.execute(request)

    return app


app = create_app()
