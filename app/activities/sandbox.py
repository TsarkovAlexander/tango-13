from time import monotonic
from typing import Any
from uuid import uuid4

import httpx
from temporalio import activity

from app.settings import get_settings
from app.tracing import TraceEvent, emit_trace
from sandbox_executor.executors import create_executor
from sandbox_executor.policies import SandboxPolicy, SandboxRequest, SandboxResult


@activity.defn
async def sandbox_step(payload: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    started_at = monotonic()
    result: SandboxResult | None = None
    error = None

    request = SandboxRequest(
        run_id=payload["run_id"],
        attempt_id=payload["attempt_id"],
        code=payload.get("code", ""),
        input=payload.get("input", {}),
        policy=SandboxPolicy(
            max_input_bytes=settings.max_input_bytes,
            max_output_bytes=settings.max_output_bytes,
            timeout_seconds=settings.sandbox_timeout_seconds,
            allow_network=False,
        ),
    )

    try:
        if settings.sandbox_api_url is None:
            result = await create_executor(
                settings.sandbox_backend,
                docker_image=settings.sandbox_docker_image,
                docker_runtime=settings.sandbox_docker_runtime,
                docker_cpus=settings.sandbox_docker_cpus,
                docker_memory=settings.sandbox_docker_memory,
                docker_pids_limit=settings.sandbox_docker_pids_limit,
            ).execute(request)
        else:
            async with httpx.AsyncClient(timeout=settings.sandbox_timeout_seconds) as client:
                response = await client.post(
                    f"{str(settings.sandbox_api_url).rstrip('/')}/execute",
                    json=request.model_dump(mode="json"),
                )
                response.raise_for_status()
                result = SandboxResult.model_validate(response.json())

        if result.status != "succeeded":
            raise RuntimeError(result.error or "sandbox execution failed")
        return result.model_dump(mode="json")
    except Exception as exc:
        error = str(exc)
        raise
    finally:
        duration_ms = int((monotonic() - started_at) * 1000)
        await emit_trace(
            TraceEvent(
                trace_id=payload["run_id"],
                run_id=payload["run_id"],
                tenant_id=payload["tenant_id"],
                workflow_id=payload.get("workflow_id"),
                step="sandbox",
                span_id=uuid4().hex,
                status="ok" if error is None else "error",
                error=error,
                duration_ms=duration_ms,
                output_ref=f"sandbox-result:{payload['run_id']}:{payload['attempt_id']}"
                if result is not None
                else None,
                policy_version=request.policy.version,
            ),
            settings,
        )
