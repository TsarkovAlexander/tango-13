# tango-13

Temporal-orchestrated sandbox execution service with a FastAPI control plane and a dedicated AWS Lambda MicroVM sandbox boundary.

## What Is Implemented

- `POST /runs` accepts a tenant-scoped run and records it in a run-status projection.
- `GET /runs/{id}/events` streams projection updates as server-sent events and closes after a terminal status.
- `MultiAgentWorkflow` models deterministic Temporal workflow steps.
- Temporal activities perform external work and emit replay-safe structured traces.
- `sandbox_executor` exposes a policy-enforcing execution boundary with a default local policy path and a Lambda MicroVM runtime path.
- `sandbox_executor.microvm_broker` wraps the same `/execute` contract with one AWS Lambda MicroVM per sandbox attempt.
- `Dockerfile.microvm` and `make package-microvm` create the Lambda MicroVM image artifact.
- `infra/terraform` contains the AWS infrastructure for the Lambda MicroVM sandbox path.

The default local executor is a policy smoke implementation for workflow and API testing only; do not use it for untrusted code execution. Production execution stays behind the same `SandboxRequest`/`SandboxResult` boundary and uses the Lambda MicroVM broker.

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
- `TANGO_SANDBOX_API_URL`: sandbox executor API URL. If unset, the sandbox activity uses the configured in-process sandbox backend.
- `TANGO_SANDBOX_API_AUTH`: `none` for unsigned local broker calls or `aws-iam` for an IAM-authenticated broker Lambda Function URL. Default: `none`.
- `TANGO_SANDBOX_BACKEND`: `policy` for the default non-executing smoke path or `microvm-python` for code execution inside a Lambda MicroVM. Default: `policy`.
- `TANGO_BROKER_TIMEOUT_SECONDS`: HTTP timeout for worker calls to the sandbox broker. Default: `30`.
- `TANGO_AWS_REGION`: AWS Region for Lambda MicroVM API calls. Default: `us-east-1`.
- `TANGO_LAMBDA_MICROVM_IMAGE_IDENTIFIER`: Lambda MicroVM image ARN or name used by the broker.
- `TANGO_LAMBDA_MICROVM_IMAGE_VERSION`: optional pinned image version.
- `TANGO_LAMBDA_MICROVM_EXECUTION_ROLE_ARN`: optional runtime role passed to `run-microvm`.
- `TANGO_LAMBDA_MICROVM_AUTH_TOKEN_EXPIRATION_MINUTES`: endpoint auth token lifetime. Default: `5`.
- `TANGO_LAMBDA_MICROVM_PORT`: application port inside each MicroVM. Default: `8080`.
- `TANGO_LAMBDA_MICROVM_RUN_HOOK_PAYLOAD_ENABLED`: include non-secret run metadata in the MicroVM `runHookPayload` when `true`. Default: `false`.
- `TANGO_LAMBDA_MICROVM_MAXIMUM_DURATION_SECONDS`: hard cap for one MicroVM attempt. Default: `60`.
- `TANGO_TRACE_STDOUT`: emit trace JSON to stdout. Default: `true`.
- `TANGO_TRACE_HTTP_URL`: optional HTTP trace sink.
- `TANGO_MAX_INPUT_BYTES`, `TANGO_MAX_OUTPUT_BYTES`, `TANGO_SANDBOX_TIMEOUT_SECONDS`: local sandbox policy limits.

## AWS Lambda MicroVM Sandbox Path

Production sandbox execution uses AWS Lambda MicroVMs behind the same `SandboxRequest`/`SandboxResult` API used in local testing. The Temporal worker calls a stable sandbox HTTP URL through `TANGO_SANDBOX_API_URL`; in production that URL should point to the MicroVM broker.

AWS provisioning, Terraform state, image build/update commands, broker Lambda packaging, and AWS smoke checks live in `infra/terraform/README.md`.

To test the full Temporal flow against a locally running MicroVM broker, repeat the local end-to-end flow above with `TANGO_SANDBOX_API_URL=http://127.0.0.1:8081` on the worker.

To test the full Temporal flow against the broker hosted as an AWS Lambda Function URL, deploy the AWS resources from `infra/terraform`, then run the worker with:

```bash
TANGO_SANDBOX_API_URL="<lambda_broker_function_url>" \
TANGO_SANDBOX_API_AUTH=aws-iam \
make run-worker
```

Start the API with `TANGO_TEMPORAL_START_ENABLED=true`, submit `/runs`, and verify the SSE projection as in the local flow. The API does not call the sandbox broker directly; the worker setting is the one that controls remote sandbox execution.

## Isolation Model

Untrusted code must not run in the API or Temporal worker process. Local development defaults to the non-executing policy path.

For production, the broker starts one Lambda MicroVM per sandbox attempt, sends the existing `SandboxRequest` to the MicroVM's dedicated `/execute` endpoint, and terminates the MicroVM in a cleanup path. The MicroVM image sets `TANGO_SANDBOX_BACKEND=microvm-python`, so untrusted code runs in a Python subprocess inside the isolated MicroVM. Endpoint access uses a short-lived Lambda MicroVM auth token scoped to port 8080. The broker requests an ingress connector for inbound `/execute` calls but does not request any egress connector, matching the default `allow_network=False` sandbox policy.

Each Lambda MicroVM attempt uses:

- a fresh MicroVM lifecycle for each sandbox attempt;
- an optional per-attempt `runHookPayload` containing non-secret run metadata;
- the packaged Lambda MicroVM image artifact;
- a scoped execution role;
- a short-lived endpoint auth token;
- bounded inputs, outputs, and execution timeout;
- broker cleanup with `terminate-microvm` after success, failure, or timeout.

Pooling is intentionally out of scope for the first secure implementation.

## Retry And Timeout Model

Temporal workflows own durable orchestration. Workflow code must remain deterministic: no direct network calls, wall-clock reads, random values, or trace writes from replay paths. Activities own external effects and use bounded start-to-close, schedule-to-close, heartbeat, and retry settings. Temporal history allows a run to resume after worker restarts without rerunning completed deterministic workflow decisions.

Sandbox requests include `run_id` and `attempt_id` so retries do not reuse stale artifacts.

For Lambda MicroVM execution, a retry creates a new MicroVM for the new sandbox activity attempt. The broker always calls `terminate-microvm` after success, failure, or timeout so a failed HTTP call does not leave compute running.

## Tracing

Activities emit Langfuse-style trace events through `app.tracing`. Each event includes identifiers such as `trace_id`, `run_id`, `tenant_id`, `workflow_id`, `step`, `span_id`, `status`, and timing metadata. Raw payloads and secret-like values are redacted by default. Large or sensitive inputs and outputs should be stored separately and referenced with `input_ref`/`output_ref`.
