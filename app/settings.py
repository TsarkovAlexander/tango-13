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
    sandbox_api_auth: Literal["none", "aws-iam"] = "none"
    sandbox_backend: Literal["policy", "microvm-python"] = "policy"
    aws_region: str = "us-east-1"
    lambda_microvm_image_identifier: str | None = None
    lambda_microvm_image_version: str | None = None
    lambda_microvm_execution_role_arn: str | None = None
    lambda_microvm_auth_token_expiration_minutes: int = Field(default=5, ge=1)
    lambda_microvm_port: int = Field(default=8080, ge=1, le=65535)
    lambda_microvm_run_hook_payload_enabled: bool = False
    lambda_microvm_wait_attempts: int = Field(default=20, ge=1)
    lambda_microvm_wait_delay_seconds: float = Field(default=0.5, ge=0)
    lambda_microvm_maximum_duration_seconds: int = Field(default=60, ge=1, le=28_800)
    trace_http_url: AnyHttpUrl | None = None
    trace_stdout: bool = True

    run_event_queue_size: int = Field(default=100, ge=1)
    max_input_bytes: int = Field(default=64 * 1024, ge=1)
    max_output_bytes: int = Field(default=64 * 1024, ge=1)
    sandbox_timeout_seconds: int = Field(default=10, ge=1)
    broker_timeout_seconds: int = Field(default=30, ge=1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
