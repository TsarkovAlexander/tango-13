import json
from time import monotonic
from typing import Any
from uuid import uuid4

import httpx
from botocore.awsrequest import AWSRequest
from botocore.auth import SigV4Auth
from botocore.session import get_session
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
            result = await create_executor(settings.sandbox_backend).execute(request)
        else:
            broker_url = f"{str(settings.sandbox_api_url).rstrip('/')}/execute"
            request_payload = request.model_dump(mode="json")
            async with httpx.AsyncClient(timeout=settings.broker_timeout_seconds) as client:
                if settings.sandbox_api_auth == "aws-iam":
                    body = _json_body(request_payload)
                    response = await client.post(
                        broker_url,
                        content=body,
                        headers=_aws_sigv4_headers(broker_url, request_payload, settings.aws_region),
                    )
                else:
                    response = await client.post(broker_url, json=request_payload)
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


def _aws_sigv4_headers(url: str, payload: dict[str, Any], region: str) -> dict[str, str]:
    body = _json_body(payload)
    headers = {"Content-Type": "application/json"}
    credentials = get_session().get_credentials()
    if credentials is None:
        raise RuntimeError("AWS credentials are required for TANGO_SANDBOX_API_AUTH=aws-iam")
    request = AWSRequest(method="POST", url=url, data=body, headers=headers)
    SigV4Auth(credentials.get_frozen_credentials(), "lambda", region).add_auth(request)
    return dict(request.headers.items())


def _json_body(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
