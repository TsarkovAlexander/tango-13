from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class RunStatus(StrEnum):
    ACCEPTED = "accepted"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class RunRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    input: dict[str, Any] = Field(default_factory=dict)


class RunResponse(BaseModel):
    run_id: str
    workflow_id: str
    status: RunStatus


class RunEvent(BaseModel):
    run_id: str
    status: RunStatus
    step: str
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = Field(default_factory=dict)


def new_run_id() -> str:
    return f"run-{uuid4().hex}"
