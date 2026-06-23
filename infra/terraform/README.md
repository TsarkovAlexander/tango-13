# Terraform AWS Deployment

This directory provisions the first AWS sandbox-host baseline for Tango:

- isolated VPC and private sandbox subnet;
- no public IPs and no NAT gateway;
- VPC endpoints for private AWS control-plane access;
- internal sandbox executor API load balancer;
- autoscaled sandbox hosts with tightly scoped ingress and egress;
- EC2 instance profile for SSM Session Manager and CloudWatch Logs;
- customer-managed KMS encryption for logs and root volumes;
- VPC flow logs for network auditability;
- Firecracker bootstrap checks after each EC2 host launches.

This is infrastructure scaffolding for the sandbox host tier. It does not build the AMI or implement the per-request Firecracker lifecycle. The hardened AMI and sandbox executor are responsible for starting one jailed Firecracker microVM for each untrusted step.

## Prerequisites

- Terraform `>= 1.6`.
- AWS CLI credentials configured for the target account.
- Permission to create VPC, subnet, route table, VPC endpoint, EC2, IAM, KMS, VPC Flow Logs, and CloudWatch Logs resources.
- A bare-metal EC2 instance type. Firecracker uses Linux KVM, and EC2 exposes KVM to guests only on `.metal` instances.
- A hardened sandbox AMI with:
  - a supported Linux host kernel, patched microcode, and `/dev/kvm`;
  - matching Firecracker and jailer binaries installed and pinned;
  - SSM agent installed;
  - `tango-sandbox-executor.service` installed as a systemd unit;
  - required kernel/rootfs artifacts;
  - cgroups mounted and swap disabled unless explicitly accepted;
  - successful `spikes/firecracker_smoke` validation on the target instance family.

## Configure Variables

Copy `terraform.tfvars.example` to `terraform.tfvars` and edit the values:

```hcl
aws_region             = "us-east-1"
name_prefix            = "tango"
environment            = "prod"
sandbox_ami_id         = "ami-xxxxxxxxxxxxxxxxx"
sandbox_instance_type  = "m7i.metal-24xl"
sandbox_host_min_size = 1
sandbox_host_desired_capacity = 1
sandbox_host_max_size = 2
vpc_cidr               = "10.42.0.0/16"
sandbox_subnet_cidr    = "10.42.10.0/24"
sandbox_api_port       = 8080
sandbox_api_health_check_path = "/healthz"
sandbox_api_allowed_cidr_blocks = ["10.42.0.0/16"]
sandbox_host_disable_api_termination = true
sandbox_api_lb_deletion_protection = true
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
- `sandbox_api_load_balancer_dns_name`
- `sandbox_api_url`
- `sandbox_host_autoscaling_group_name`
- `sandbox_host_launch_template_id`
- `sandbox_kms_key_arn`
- `sandbox_log_group_name`
- `vpc_flow_log_group_name`

Use `sandbox_api_url` as the private value for worker configuration such as `TANGO_SANDBOX_API_URL`.

## Firecracker Isolation Model

The Terraform layer isolates the sandbox host tier. Hosts run in a private subnet with no internet gateway, no NAT gateway, no public IPs, no SSH ingress, and egress limited to private AWS VPC endpoints needed for SSM, CloudWatch Logs, and KMS.

The sandbox executor must isolate each untrusted step inside a fresh Firecracker microVM. In production it should launch Firecracker through the same-version `jailer`, place each microVM in a dedicated cgroup/chroot, drop privileges to a non-root UID/GID, enforce CPU/memory/disk/file-descriptor limits, and clean up the jail after execution.

Untrusted microVMs should not be configured with Firecracker network interfaces or host TAP devices. Inputs and outputs should flow through bounded files or virtio-vsock when interactive exchange is required. Terraform's no-NAT VPC controls host egress, but guest network isolation depends on the executor never attaching guest networking for untrusted steps.

## Bootstrap Behavior

Each sandbox host launch template runs `scripts/firecracker_bootstrap.sh` through EC2 user data. The script is intentionally Firecracker-specific and offline-safe because the subnet has no NAT. It verifies:

- Firecracker and jailer are installed and report the same version;
- `/dev/kvm` exists and is accessible;
- cgroups are mounted;
- swap is disabled unless `ALLOW_SANDBOX_SWAP=true` is explicitly set;
- kernel and rootfs artifacts exist under `/opt/tango/images`;
- runtime directories such as `/srv/jailer` and `/var/lib/tango/sandbox` are root-owned and non-world-writable;
- `tango-sandbox-executor.service` starts successfully.

If any check fails, bootstrap exits non-zero and the host should stay unhealthy behind the internal load balancer.

## Retry And Timeout Strategy

Temporal owns workflow durability and activity retry. The infrastructure supports that model by keeping the API layer out of the execution path, placing the sandbox executor behind an internal load balancer, and letting the autoscaling group replace unhealthy sandbox hosts.

Each sandbox activity should send a bounded, idempotent request to `sandbox_api_url`. The executor should enforce per-step wall-clock, CPU, memory, output-size, and disk limits. Temporal retries should use idempotency keys so a retried activity can safely ignore or clean up a previous failed attempt.

## Verify Security Properties

Check the Terraform plan before applying:

```bash
terraform show tfplan
```

Confirm:

- sandbox EC2 launch template has `associate_public_ip_address = false`;
- sandbox instance type is a `.metal` type validated for Firecracker/KVM;
- the sandbox subnet route table has no default route to an internet gateway or NAT gateway;
- interface VPC endpoints exist for SSM, SSM messages, EC2 messages, CloudWatch Logs, and KMS;
- an S3 gateway endpoint is attached to the sandbox route table for future private S3 access;
- sandbox host egress allows only HTTPS to the VPC endpoint security group;
- sandbox host API ingress comes only from the internal load balancer security group;
- the load balancer accepts sandbox API traffic only from `sandbox_api_allowed_cidr_blocks`;
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

## Production Hardening Notes

Before multi-tenant production use, add an AMI build pipeline with signed artifacts, regular kernel and microcode patching, explicit SMT/KSM policy, swap disabled or encrypted, host vulnerability scanning, endpoint policies, stricter worker/control-plane CIDRs, multi-AZ subnets, and tenant quota enforcement.

Firecracker itself does not filter guest egress traffic. The strongest setting for this workload is to omit guest network devices entirely. If guest networking is ever enabled for a different workload class, enforce host-level nftables or iptables filtering and explicitly block IMDS (`169.254.169.254`).

Guest-controlled logs and serial output must be bounded. Prefer disabling guest serial output for production, or route it to fixed-size buffers with rotation. Trace payloads should redact sensitive inputs and store large artifacts by reference.

## Destroy

To tear down the sandbox infrastructure:

```bash
terraform destroy
```

Review the destroy plan carefully before confirming.

## Current Limitations

- `backend.tf` contains a commented S3/DynamoDB backend template; fill it in before team or CI use.
- No AMI build pipeline is included.
- No production sandbox executor implementation or image rollout is defined here.
- Multi-AZ sandbox subnets are not included yet.
- The VPC endpoint list may need expansion if the AMI or runtime needs additional private AWS APIs.
