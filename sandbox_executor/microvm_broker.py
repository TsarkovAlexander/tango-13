from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from fastapi import FastAPI

from app.settings import Settings, get_settings
from sandbox_executor.policies import SandboxRequest, SandboxResult

PostExecute = Callable[[str, dict[str, str], dict[str, Any], int], Awaitable[dict[str, Any]]]


class LambdaMicrovmBroker:
    def __init__(
        self,
        *,
        settings: Settings,
        microvm_client: Any | None = None,
        post_execute: PostExecute | None = None,
    ) -> None:
        self.settings = settings
        self.microvm_client = microvm_client or _default_microvm_client(settings)
        self.post_execute = post_execute or _post_execute

    async def execute(self, request: SandboxRequest) -> SandboxResult:
        microvm_id: str | None = None
        run_response = await asyncio.to_thread(
            self.microvm_client.run_microvm,
            **self._run_microvm_params(request),
        )
        microvm_id = run_response["microvmId"]
        endpoint = run_response["endpoint"]
        try:
            await self._wait_until_running(microvm_id, run_response.get("state"))
            token = await self._create_auth_token(microvm_id)
            response = await self.post_execute(
                _microvm_execute_url(endpoint),
                {
                    "X-aws-proxy-auth": token,
                    "X-aws-proxy-port": str(self.settings.lambda_microvm_port),
                },
                request.model_dump(mode="json"),
                request.policy.timeout_seconds,
            )
            return SandboxResult.model_validate(response)
        finally:
            if microvm_id is not None:
                await asyncio.to_thread(
                    self.microvm_client.terminate_microvm,
                    microvmIdentifier=microvm_id,
                )

    def _run_microvm_params(self, request: SandboxRequest) -> dict[str, Any]:
        if self.settings.lambda_microvm_image_identifier is None:
            raise RuntimeError("TANGO_LAMBDA_MICROVM_IMAGE_IDENTIFIER must be configured")

        params: dict[str, Any] = {
            "imageIdentifier": self.settings.lambda_microvm_image_identifier,
            "ingressNetworkConnectors": [_managed_ingress_connector(self.settings.aws_region)],
            "egressNetworkConnectors": [],
            "maximumDurationInSeconds": self.settings.lambda_microvm_maximum_duration_seconds,
        }
        if self.settings.lambda_microvm_run_hook_payload_enabled:
            params["runHookPayload"] = json.dumps(
                {"run_id": request.run_id, "attempt_id": request.attempt_id},
                separators=(",", ":"),
                sort_keys=True,
            )
        if self.settings.lambda_microvm_image_version is not None:
            params["imageVersion"] = self.settings.lambda_microvm_image_version
        if self.settings.lambda_microvm_execution_role_arn is not None:
            params["executionRoleArn"] = self.settings.lambda_microvm_execution_role_arn
        return params

    async def _wait_until_running(self, microvm_id: str, initial_state: str | None) -> None:
        state = initial_state
        for _ in range(self.settings.lambda_microvm_wait_attempts):
            if state == "RUNNING":
                return
            await asyncio.sleep(self.settings.lambda_microvm_wait_delay_seconds)
            response = await asyncio.to_thread(
                self.microvm_client.get_microvm,
                microvmIdentifier=microvm_id,
            )
            state = response["state"]
        raise TimeoutError(f"MicroVM {microvm_id} did not reach RUNNING state")

    async def _create_auth_token(self, microvm_id: str) -> str:
        response = await asyncio.to_thread(
            self.microvm_client.create_microvm_auth_token,
            microvmIdentifier=microvm_id,
            expirationInMinutes=self.settings.lambda_microvm_auth_token_expiration_minutes,
            allowedPorts=[{"port": self.settings.lambda_microvm_port}],
        )
        token = response["authToken"]
        if isinstance(token, dict):
            return token["X-aws-proxy-auth"]
        return str(token)


def create_app(
    settings: Settings | None = None,
    *,
    microvm_client: Any | None = None,
    post_execute: PostExecute | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    app = FastAPI(title="Tango Lambda MicroVM Broker")

    @app.post("/execute", response_model=SandboxResult)
    async def execute(request: SandboxRequest) -> SandboxResult:
        broker = LambdaMicrovmBroker(
            settings=resolved_settings,
            microvm_client=microvm_client,
            post_execute=post_execute,
        )
        return await broker.execute(request)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


async def _post_execute(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: int,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()


def _default_microvm_client(settings: Settings) -> Any:
    import boto3
    from botocore.config import Config

    return boto3.client(
        "lambda-microvms",
        region_name=settings.aws_region,
        config=Config(
            connect_timeout=5,
            read_timeout=10,
            retries={"mode": "adaptive", "total_max_attempts": 5},
        ),
    )


def _managed_ingress_connector(region: str) -> str:
    return f"arn:aws:lambda:{region}:aws:network-connector:aws-network-connector:ALL_INGRESS"


def _microvm_execute_url(endpoint: str) -> str:
    normalized = endpoint.rstrip("/")
    if not normalized.startswith(("http://", "https://")):
        normalized = f"https://{normalized}"
    return f"{normalized}/execute"


app = create_app()
