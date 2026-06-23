import json
import re
from datetime import datetime, timezone
from typing import Any

import httpx
from pydantic import BaseModel, Field

from app.settings import Settings


SECRET_KEY_PATTERN = re.compile(r"(api[_-]?key|authorization|password|secret|token)", re.I)
SECRET_VALUE_PATTERN = re.compile(r"(sk-[A-Za-z0-9_-]{12,}|AKIA[0-9A-Z]{16})")


class TraceEvent(BaseModel):
    trace_id: str
    run_id: str
    tenant_id: str
    workflow_id: str | None = None
    step: str
    span_id: str
    parent_span_id: str | None = None
    status: str
    input_ref: str | None = None
    output_ref: str | None = None
    error: str | None = None
    retry_attempt: int | None = None
    duration_ms: int | None = None
    sandbox_image_digest: str | None = None
    policy_version: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[redacted]" if SECRET_KEY_PATTERN.search(str(key)) else redact(nested)
            for key, nested in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return SECRET_VALUE_PATTERN.sub("[redacted]", value)
    return value


async def emit_trace(event: TraceEvent, settings: Settings) -> None:
    payload = redact(event.model_dump(mode="json", exclude_none=True))
    if settings.trace_stdout:
        print(json.dumps(payload, sort_keys=True))

    if settings.trace_http_url is not None:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(str(settings.trace_http_url), json=payload)
