# Terraform AWS Deployment

This directory provisions the first AWS sandbox-host baseline for Tango:

- isolated VPC and private sandbox subnet;
- no public IPs and no NAT gateway;
- VPC endpoints for private AWS control-plane access;
- sandbox host security group with tightly scoped egress;
- EC2 instance profile for SSM Session Manager and CloudWatch Logs;
- customer-managed KMS encryption for logs and root volumes;
- VPC flow logs for network auditability;
- one or more sandbox EC2 hosts from a hardened AMI.

This is infrastructure scaffolding for the sandbox host tier. It does not build the AMI, install Firecracker, deploy the Python service, or configure a production load balancer.

## Prerequisites

- Terraform `>= 1.6`.
- AWS CLI credentials configured for the target account.
- Permission to create VPC, subnet, route table, VPC endpoint, EC2, IAM, KMS, VPC Flow Logs, and CloudWatch Logs resources.
- A hardened sandbox AMI with:
  - Firecracker and jailer installed and pinned;
  - SSM agent installed;
  - sandbox executor service or bootstrap path;
  - required kernel/rootfs artifacts;
  - successful `spikes/firecracker_smoke` validation on the target instance family.

## Configure Variables

Copy `terraform.tfvars.example` to `terraform.tfvars` and edit the values:

```hcl
aws_region             = "us-east-1"
name_prefix            = "tango"
environment            = "prod"
sandbox_ami_id         = "ami-xxxxxxxxxxxxxxxxx"
sandbox_instance_type  = "c7i.large"
sandbox_host_count     = 1
vpc_cidr               = "10.42.0.0/16"
sandbox_subnet_cidr    = "10.42.10.0/24"
sandbox_api_port       = 8080
sandbox_host_disable_api_termination = true
```

Required variables:

- `aws_region`
- `sandbox_ami_id`

Most other values have conservative defaults.

Before shared team or CI use, configure the commented S3 backend in `backend.tf` with your real state bucket and lock table.

## Deploy

From `infra/terraform`:

```bash
terraform init
terraform fmt -check
terraform validate
terraform plan -out tfplan
terraform apply tfplan
```

Key outputs include:

- `vpc_id`
- `sandbox_subnet_id`
- `sandbox_security_group_id`
- `vpc_endpoint_security_group_id`
- `sandbox_host_instance_ids`
- `sandbox_host_private_ips`
- `sandbox_kms_key_arn`
- `sandbox_log_group_name`
- `vpc_flow_log_group_name`

## Verify Security Properties

Check the Terraform plan before applying:

```bash
terraform show tfplan
```

Confirm:

- sandbox EC2 instances have `associate_public_ip_address = false`;
- the sandbox subnet route table has no default route to an internet gateway or NAT gateway;
- interface VPC endpoints exist for SSM, SSM messages, EC2 messages, CloudWatch Logs, and KMS;
- an S3 gateway endpoint is attached to the sandbox route table for future private S3 access;
- sandbox host egress allows only HTTPS to the VPC endpoint security group;
- IMDSv2 is required on sandbox EC2 instances;
- root EBS volumes and CloudWatch log groups use the sandbox KMS key;
- VPC flow logs are enabled;
- IAM permissions are limited to SSM Session Manager and CloudWatch Logs writes.

## Connect To A Sandbox Host

Use SSM Session Manager after the instance is online:

```bash
aws ssm start-session \
  --region <aws-region> \
  --target <instance-id>
```

There is no SSH ingress rule and no public IP by design.

## Run Firecracker Smoke Check

After connecting to a sandbox host, run the repository smoke check with host-specific paths:

```bash
export FIRECRACKER_BIN=/usr/local/bin/firecracker
export JAILER_BIN=/usr/local/bin/jailer
export KERNEL_IMAGE=/opt/tango/images/vmlinux
export ROOTFS_IMAGE=/opt/tango/images/rootfs.ext4

spikes/firecracker_smoke/run.sh
```

The smoke check must pass before treating the instance family and AMI as valid for sandbox execution.

## Destroy

To tear down the sandbox infrastructure:

```bash
terraform destroy
```

Review the destroy plan carefully before confirming.

## Current Limitations

- `backend.tf` contains a commented S3/DynamoDB backend template; fill it in before team or CI use.
- No AMI build pipeline is included.
- No autoscaling group, load balancer, service discovery, or deployment automation is included.
- No production sandbox executor systemd unit or image rollout is defined here.
- The VPC endpoint list may need expansion if the AMI or runtime needs additional private AWS APIs.
