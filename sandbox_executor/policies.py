from pydantic import BaseModel, Field


NETWORK_TOKENS = (
    "socket",
    "requests.",
    "httpx.",
    "urllib.",
    "curl ",
    "wget ",
    "nc ",
    "dig ",
)


class SandboxPolicy(BaseModel):
    version: str = "2026-06-23"
    max_input_bytes: int = Field(default=64 * 1024, ge=1)
    max_output_bytes: int = Field(default=64 * 1024, ge=1)
    timeout_seconds: int = Field(default=10, ge=1)
    allow_network: bool = False


class SandboxRequest(BaseModel):
    run_id: str
    attempt_id: str
    code: str
    input: dict = Field(default_factory=dict)
    policy: SandboxPolicy = Field(default_factory=SandboxPolicy)


class SandboxResult(BaseModel):
    run_id: str
    attempt_id: str
    status: str
    output: dict = Field(default_factory=dict)
    error: str | None = None
    policy_version: str
    network_allowed: bool


class SandboxPolicyError(ValueError):
    pass


def validate_request(request: SandboxRequest) -> None:
    encoded_code = request.code.encode("utf-8")
    if len(encoded_code) > request.policy.max_input_bytes:
        raise SandboxPolicyError("sandbox input exceeds policy limit")

    if not request.policy.allow_network:
        lowered = request.code.lower()
        if any(token in lowered for token in NETWORK_TOKENS):
            raise SandboxPolicyError("sandbox policy blocks network access")


def validate_output_size(output: bytes, policy: SandboxPolicy) -> None:
    if len(output) > policy.max_output_bytes:
        raise SandboxPolicyError("sandbox output exceeds policy limit")
