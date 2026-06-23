from hashlib import sha256

from sandbox_executor.policies import (
    SandboxPolicyError,
    SandboxRequest,
    SandboxResult,
    validate_output_size,
    validate_request,
)


class FirecrackerExecutor:
    """Policy boundary for one-shot Firecracker execution.

    This class is intentionally a local smoke implementation until the EC2 spike
    validates kernel, rootfs, jailer, cgroup, and vsock details on target hosts.
    """

    async def execute(self, request: SandboxRequest) -> SandboxResult:
        try:
            validate_request(request)
            output = {
                "code_sha256": sha256(request.code.encode("utf-8")).hexdigest(),
                "input_keys": sorted(request.input.keys()),
            }
            encoded_output = str(output).encode("utf-8")
            validate_output_size(encoded_output, request.policy)
            return SandboxResult(
                run_id=request.run_id,
                attempt_id=request.attempt_id,
                status="succeeded",
                output=output,
                policy_version=request.policy.version,
                network_allowed=request.policy.allow_network,
            )
        except SandboxPolicyError as exc:
            return SandboxResult(
                run_id=request.run_id,
                attempt_id=request.attempt_id,
                status="failed",
                error=str(exc),
                policy_version=request.policy.version,
                network_allowed=request.policy.allow_network,
            )
