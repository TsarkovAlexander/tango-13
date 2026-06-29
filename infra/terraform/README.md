# Terraform AWS Infrastructure

This stack provisions the AWS resources used by Tango's Lambda MicroVM sandbox path:

- S3 bucket for MicroVM image artifacts, with public access blocked, versioning enabled, and KMS encryption.
- KMS key for MicroVM artifacts and logs.
- CloudWatch log group for MicroVM build and runtime logs.
- IAM roles for MicroVM image builds, MicroVM runtime execution, broker lifecycle calls, and operator smoke tests.
- A broker AWS Lambda function and IAM-authenticated Lambda Function URL.

The broker Lambda uses the Terraform outputs to create, authenticate, call, and terminate one MicroVM for each sandbox attempt.

## Prerequisites

- Terraform `>= 1.15`.
- AWS CLI credentials for the sandbox account.
- Permission to manage S3, IAM, KMS, and CloudWatch Logs resources.
- Access to the `lambda-microvms` AWS control plane in `us-east-1`.

## Remote State

`backend.tf` is configured for the default sandbox remote state bucket:

```text
bucket = "tango-test-569813798269-us-east-1-tf-state"
key    = "tango/sandbox/terraform.tfstate"
region = "us-east-1"
use_lockfile = true
```

If the state bucket does not exist yet, create it out of band before running `terraform init`:

```bash
aws s3api create-bucket \
  --region us-east-1 \
  --bucket tango-test-569813798269-us-east-1-tf-state

aws s3api put-public-access-block \
  --bucket tango-test-569813798269-us-east-1-tf-state \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

aws s3api put-bucket-versioning \
  --bucket tango-test-569813798269-us-east-1-tf-state \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption \
  --bucket tango-test-569813798269-us-east-1-tf-state \
  --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
```

The backend uses Terraform's S3 lockfile support, so no DynamoDB lock table is required. After creating the bucket, initialize this stack from `infra/terraform`:

```bash
terraform init
```

After changing existing backend settings, reinitialize with state migration:

```bash
terraform init -migrate-state
```

## Configure

Create `terraform.tfvars` only when you need to override defaults:

```hcl
aws_region  = "us-east-1"
name_prefix = "tango"
environment = "test"

microvm_image_name = "tango-sandbox-executor"

# Defaults to the current account root when empty.
microvm_operator_trusted_principal_arns = []

# Service principal for the deployed broker workload.
microvm_broker_trusted_services = ["lambda.amazonaws.com"]

# Built with `make package-lambda-broker` from the repository root.
lambda_broker_artifact_path = "../../dist/tango-broker-lambda.zip"
```

The stack validates both the AWS Region and sandbox account before applying.

## Deploy

Package the broker Lambda artifact first, then deploy from `infra/terraform`:

```bash
cd ../..
make package-lambda-broker
cd infra/terraform
terraform init
terraform fmt -check
terraform validate
terraform plan -out tfplan
terraform apply tfplan
```

Check the plan before applying:

```bash
terraform show tfplan
```

Confirm the plan creates only the expected S3, KMS, CloudWatch Logs, IAM, Lambda, and Function URL resources.

## Outputs

The broker and image build commands use these outputs:

- `microvm_artifact_bucket_uri`
- `microvm_build_role_arn`
- `microvm_execution_role_arn`
- `microvm_broker_role_arn`
- `microvm_log_group_name`
- `microvm_base_image_arn`
- `microvm_all_ingress_connector_arn`
- `microvm_image_arn`
- `lambda_broker_function_name`
- `lambda_broker_function_url`

From `infra/terraform`, export the values needed by the Makefile:

```bash
export AWS_REGION=us-east-1
export MICROVM_S3_URI="$(terraform output -raw microvm_artifact_bucket_uri)/tango-microvm.zip"
export MICROVM_BUILD_ROLE_ARN="$(terraform output -raw microvm_build_role_arn)"
export MICROVM_EXECUTION_ROLE_ARN="$(terraform output -raw microvm_execution_role_arn)"
export MICROVM_IMAGE_ARN="$(terraform output -raw microvm_image_arn)"
export MICROVM_BASE_IMAGE_ARN="$(terraform output -raw microvm_base_image_arn)"
export MICROVM_INGRESS_CONNECTOR_ARN="$(terraform output -raw microvm_all_ingress_connector_arn)"
export MICROVM_LOG_GROUP_NAME="$(terraform output -raw microvm_log_group_name)"
export TANGO_SANDBOX_API_URL="$(terraform output -raw lambda_broker_function_url)"
```

## Build Or Update The Image

From the repository root, package the MicroVM artifact and create the image the first time:

```bash
make create-microvm-image
```

For later image revisions:

```bash
make update-microvm-image
```

Check image status until create reports `CREATED` or update reports `UPDATED`:

```bash
aws lambda-microvms get-microvm-image \
  --region "$AWS_REGION" \
  --image-identifier "$MICROVM_IMAGE_ARN"
```

Rebuild the broker Lambda artifact before planning or applying Terraform changes that deploy updated broker code:

```bash
cd ../..
make package-lambda-broker
cd infra/terraform
```

## Smoke Test

Run the broker locally against the deployed image:

```bash
TANGO_AWS_REGION="$AWS_REGION" \
TANGO_LAMBDA_MICROVM_IMAGE_IDENTIFIER="$MICROVM_IMAGE_ARN" \
TANGO_LAMBDA_MICROVM_EXECUTION_ROLE_ARN="$MICROVM_EXECUTION_ROLE_ARN" \
make run-microvm-broker
```

Call the broker:

```bash
curl -s -X POST http://127.0.0.1:8081/execute \
  -H "Content-Type: application/json" \
  -d '{"run_id":"local-run-1","attempt_id":"attempt-1","code":"print(\"hello from aws microvm\")","input":{},"policy":{"version":"2026-06-23","allow_network":false,"timeout_seconds":10,"max_input_bytes":65536,"max_output_bytes":65536}}'
```

Expected result: `status` is `succeeded`, `output.stdout` includes `hello from aws microvm`, and the broker terminates the MicroVM.

For a full local Temporal run, follow the root `README.md` end-to-end flow with `TANGO_SANDBOX_API_URL=http://127.0.0.1:8081` on the worker.

For a full AWS broker Lambda run, deploy the broker Lambda and run the worker with the IAM-authenticated Function URL:

```bash
export TANGO_SANDBOX_API_URL="$(terraform output -raw lambda_broker_function_url)"

TANGO_SANDBOX_API_URL="$TANGO_SANDBOX_API_URL" \
TANGO_SANDBOX_API_AUTH=aws-iam \
make run-worker
```

Then start the API with `TANGO_TEMPORAL_START_ENABLED=true`, submit `/runs`, and verify the SSE projection from the root `README.md` flow.

## Security Checks

Before applying, confirm:

- The artifact bucket blocks public access, enforces bucket-owner ownership, enables versioning, uses KMS encryption, and denies insecure transport.
- The MicroVM log group uses the KMS key and expected retention.
- The build role can only read artifacts, decrypt with the artifact key, and write MicroVM build logs.
- The execution role is limited to runtime log writes.
- The broker role has MicroVM lifecycle actions, `iam:PassRole` for the scoped execution role, `lambda:PassNetworkConnector` scoped to the managed ingress/egress connector ARNs, and broker log writes.
- The broker code still sends an empty `egressNetworkConnectors` list by default; any future use of the egress connector permission should require an explicit sandbox policy change.
- The broker Lambda Function URL uses `AWS_IAM`, so callers need `lambda:InvokeFunctionUrl` permission and valid AWS credentials.
- The operator role can upload artifacts, build images, run smoke tests, and pass only the build and execution roles to Lambda.

## Production Hardening

Before multi-tenant production use, add signed artifact publishing, image promotion controls, least-privilege operator principals, stricter broker trust configuration, tenant quotas, broker audit logs, log retention review, and an operational runbook for listing and terminating orphaned MicroVMs.

Keep tenant secrets out of the MicroVM image snapshot. The broker passes non-secret run metadata through `runHookPayload`; pass secret references only when needed. Do not request egress connectors for untrusted runs unless a sandbox policy explicitly allows network access. If `run-microvm` returns `ServiceQuotaExceededException`, terminate idle MicroVMs or request a quota increase. If a MicroVM terminates unexpectedly, inspect `stateReason` from `get-microvm`.

## Destroy

To tear down the sandbox infrastructure:

```bash
terraform destroy
```

Review the destroy plan carefully before confirming.

## Current Limitations

- No image promotion pipeline is included.
- Lambda MicroVM image creation is still performed through AWS CLI commands outside Terraform.
- The first secure implementation terminates each MicroVM after one attempt. Idle policy, suspend/resume, and pooling are intentionally deferred.
