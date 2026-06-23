# tango-13

Temporal-orchestrated sandbox execution service with a FastAPI control plane and a dedicated Firecracker sandbox boundary.

## What Is Implemented

- `POST /runs` accepts a tenant-scoped run and records it in a run-status projection.
- `GET /runs/{id}/events` streams projection updates as server-sent events and closes after a terminal status.
- `MultiAgentWorkflow` models deterministic Temporal workflow steps.
- Temporal activities perform external work and emit replay-safe structured traces.
- `sandbox_executor` exposes a policy-enforcing execution boundary that rejects network-like code and size violations.
- `spikes/firecracker_smoke` defines the first EC2 host validation gate for direct Firecracker execution.
- `infra/terraform` sketches the private sandbox VPC, VPC endpoints, sandbox host IAM, and no-public-IP EC2 hosts.

The local executor is a policy smoke implementation. It does not execute arbitrary code; production execution must be implemented behind the same `SandboxRequest`/`SandboxResult` boundary after the Firecracker smoke spike passes on target hosts.

## Full Local Temporal End-To-End Test

1. Create the virtual environment, install Python dependencies, and install the Temporal CLI on macOS:

```bash
make init
```

If any `make run-*` command fails with `address already in use`, stop the local dev processes and start this end-to-end flow again from Terminal 1:

```bash
make clean
```

Run each long-lived process in a separate terminal.

2. Start Temporal in Terminal 1:

```bash
make run-temporal
```

Temporal listens on `localhost:7233`; the local UI is available at `http://localhost:8233`.

3. Start the sandbox API in Terminal 2:

```bash
make run-sandbox
```

4. Start the Temporal worker in Terminal 3:

```bash
TANGO_SANDBOX_API_URL=http://127.0.0.1:8080 make run-worker
```

5. Start the FastAPI app in Terminal 4:

```bash
TANGO_TEMPORAL_START_ENABLED=true \
TANGO_SANDBOX_API_URL=http://127.0.0.1:8080 \
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

6. Submit a run:

```bash
curl -s -X POST http://127.0.0.1:8000/runs \
  -H "Content-Type: application/json" \
  -d '{"tenant_id":"tenant-a","input":{"code":"print(\"hello temporal\")"}}'
```

7. Verify the workflow:

```bash
temporal workflow describe --namespace default --workflow-id <run_id>
```

8. Verify the SSE projection:

```bash
curl -N http://127.0.0.1:8000/runs/<run_id>/events
```

Expected events: `accepted`, `running`, then `succeeded`. The `succeeded` event includes the Temporal result and sandbox policy result.

9. Stop local dev processes after completion of testing:

```bash
make clean
```

## Configuration

Settings are read from environment variables with the `TANGO_` prefix:

- `TANGO_TEMPORAL_START_ENABLED`: start Temporal workflows from the API when `true`.
- `TANGO_TEMPORAL_ADDRESS`: Temporal frontend address. Default: `localhost:7233`.
- `TANGO_TEMPORAL_NAMESPACE`: Temporal namespace. Default: `default`.
- `TANGO_TEMPORAL_TASK_QUEUE`: worker task queue. Default: `tango-runs`.
- `TANGO_SANDBOX_API_URL`: sandbox executor API URL. If unset, the sandbox activity uses the local policy executor directly.
- `TANGO_TRACE_STDOUT`: emit trace JSON to stdout. Default: `true`.
- `TANGO_TRACE_HTTP_URL`: optional HTTP trace sink.
- `TANGO_MAX_INPUT_BYTES`, `TANGO_MAX_OUTPUT_BYTES`, `TANGO_SANDBOX_TIMEOUT_SECONDS`: local sandbox policy limits.

## Isolation Model

Untrusted code must not run in the API or Temporal worker process. Workers call the internal sandbox API, and the sandbox host is responsible for creating one fresh Firecracker microVM per run attempt with:

- no guest network device by default;
- read-only base image plus per-run writable overlay or tmpfs;
- cgroup CPU/memory/process limits, disk quotas, and VM kill deadlines;
- jailer/seccomp host confinement;
- bounded inputs and outputs;
- temporary state cleanup after execution.

Pooling is intentionally out of scope for the first secure implementation.

## Retry And Timeout Model

Temporal workflows own durable orchestration. Workflow code must remain deterministic: no direct network calls, wall-clock reads, random values, or trace writes from replay paths. Activities own external effects and use bounded start-to-close, schedule-to-close, heartbeat, and retry settings.

Sandbox requests include `run_id` and `attempt_id` so retries do not reuse stale artifacts.

## Tracing

Activities emit Langfuse-style trace events through `app.tracing`. Raw payloads and secret-like values are redacted by default. Large or sensitive inputs and outputs should be stored separately and referenced with `input_ref`/`output_ref`.

## AWS Hardening

Sandbox hosts belong in private subnets with no NAT gateway and no public IPs. Required AWS control-plane access should use VPC endpoints for SSM, EC2 messages, CloudWatch Logs, KMS, and S3. Instance roles should be least privilege, IMDSv2 is required, and break-glass operator access should go through audited SSM Session Manager.

See `infra/terraform/README.md` for the AWS sandbox-host deployment baseline.

AWS Lambda can be a simpler fallback when direct Firecracker lifecycle control is not required. Docker or gVisor is only a local development approximation for this threat model.