from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TANGO_", env_file=".env", extra="ignore")

    service_name: str = "tango-13"
    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "tango-runs"
    temporal_start_enabled: bool = False

    sandbox_api_url: AnyHttpUrl | None = None
    sandbox_backend: Literal["policy", "docker-gvisor"] = "policy"
    sandbox_docker_image: str = "python:3.12-slim"
    sandbox_docker_runtime: str = "runsc"
    sandbox_docker_cpus: str = "1"
    sandbox_docker_memory: str = "256m"
    sandbox_docker_pids_limit: int = Field(default=64, ge=1)
    trace_http_url: AnyHttpUrl | None = None
    trace_stdout: bool = True

    run_event_queue_size: int = Field(default=100, ge=1)
    max_input_bytes: int = Field(default=64 * 1024, ge=1)
    max_output_bytes: int = Field(default=64 * 1024, ge=1)
    sandbox_timeout_seconds: int = Field(default=10, ge=1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
