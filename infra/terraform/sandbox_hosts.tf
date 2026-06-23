variable "sandbox_ami_id" {
  type        = string
  description = "Hardened AMI with Firecracker, jailer, SSM agent, and pinned sandbox images."

  validation {
    condition     = can(regex("^ami-[0-9a-f]{8,17}$", var.sandbox_ami_id))
    error_message = "sandbox_ami_id must look like a valid AMI ID."
  }
}

variable "sandbox_instance_type" {
  type        = string
  description = "EC2 instance type validated by the Firecracker smoke spike."
  default     = "c7i.large"
}

variable "sandbox_host_count" {
  type        = number
  description = "Number of sandbox hosts to launch."
  default     = 1

  validation {
    condition     = var.sandbox_host_count >= 1 && var.sandbox_host_count <= 20
    error_message = "sandbox_host_count must be between 1 and 20."
  }
}

variable "sandbox_host_disable_api_termination" {
  type        = bool
  description = "Whether to enable EC2 termination protection for sandbox hosts."
  default     = true
}

resource "aws_instance" "sandbox_host" {
  count                                = var.sandbox_host_count
  ami                                  = var.sandbox_ami_id
  instance_type                        = var.sandbox_instance_type
  subnet_id                            = aws_subnet.sandbox.id
  vpc_security_group_ids               = [aws_security_group.sandbox_host.id]
  iam_instance_profile                 = aws_iam_instance_profile.sandbox_host.name
  disable_api_termination              = var.sandbox_host_disable_api_termination
  monitoring                           = true
  instance_initiated_shutdown_behavior = "stop"

  associate_public_ip_address = false

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "enabled"
  }

  root_block_device {
    encrypted             = true
    kms_key_id            = aws_kms_key.sandbox.arn
    volume_type           = "gp3"
    delete_on_termination = true
  }

  tags = {
    Name        = "${var.name_prefix}-sandbox-${count.index}"
    SsmManaged  = "true"
    TrustZone   = "sandbox"
    NetworkMode = "no-nat"
  }
}
