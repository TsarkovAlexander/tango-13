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
  description = "Bare-metal EC2 instance type validated by the Firecracker smoke spike."
  default     = "m7i.metal-24xl"

  validation {
    condition     = can(regex("\\.metal", var.sandbox_instance_type))
    error_message = "sandbox_instance_type must be a bare-metal EC2 instance type so Firecracker can access KVM."
  }
}

variable "sandbox_host_desired_capacity" {
  type        = number
  description = "Desired number of sandbox hosts in the autoscaling group."
  default     = 1

  validation {
    condition     = var.sandbox_host_desired_capacity >= 1 && var.sandbox_host_desired_capacity <= 20
    error_message = "sandbox_host_desired_capacity must be between 1 and 20."
  }
}

variable "sandbox_host_min_size" {
  type        = number
  description = "Minimum number of sandbox hosts in the autoscaling group."
  default     = 1

  validation {
    condition     = var.sandbox_host_min_size >= 1 && var.sandbox_host_min_size <= 20
    error_message = "sandbox_host_min_size must be between 1 and 20."
  }
}

variable "sandbox_host_max_size" {
  type        = number
  description = "Maximum number of sandbox hosts in the autoscaling group."
  default     = 2

  validation {
    condition     = var.sandbox_host_max_size >= 1 && var.sandbox_host_max_size <= 20
    error_message = "sandbox_host_max_size must be between 1 and 20."
  }
}

variable "sandbox_host_disable_api_termination" {
  type        = bool
  description = "Whether to enable EC2 termination protection for sandbox hosts."
  default     = true
}

variable "sandbox_root_device_name" {
  type        = string
  description = "Root block device name used by the hardened sandbox AMI."
  default     = "/dev/xvda"
}

resource "aws_launch_template" "sandbox_host" {
  name_prefix            = "${var.name_prefix}-sandbox-host-"
  image_id               = var.sandbox_ami_id
  instance_type          = var.sandbox_instance_type
  update_default_version = true

  disable_api_termination              = var.sandbox_host_disable_api_termination
  instance_initiated_shutdown_behavior = "stop"
  user_data                            = filebase64("${path.module}/scripts/firecracker_bootstrap.sh")

  iam_instance_profile {
    name = aws_iam_instance_profile.sandbox_host.name
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "enabled"
  }

  monitoring {
    enabled = true
  }

  network_interfaces {
    associate_public_ip_address = false
    delete_on_termination       = true
    security_groups             = [aws_security_group.sandbox_host.id]
  }

  block_device_mappings {
    device_name = var.sandbox_root_device_name

    ebs {
      encrypted             = true
      kms_key_id            = aws_kms_key.sandbox.arn
      volume_type           = "gp3"
      delete_on_termination = true
    }
  }

  tag_specifications {
    resource_type = "instance"

    tags = {
      Name        = "${var.name_prefix}-sandbox-host"
      SsmManaged  = "true"
      TrustZone   = "sandbox"
      NetworkMode = "no-nat"
    }
  }

  tag_specifications {
    resource_type = "volume"

    tags = {
      Name      = "${var.name_prefix}-sandbox-host-root"
      TrustZone = "sandbox"
    }
  }

  tags = {
    Name = "${var.name_prefix}-sandbox-host"
  }
}

resource "aws_autoscaling_group" "sandbox_host" {
  name                = "${var.name_prefix}-sandbox-host"
  vpc_zone_identifier = [aws_subnet.sandbox.id]
  min_size            = var.sandbox_host_min_size
  max_size            = var.sandbox_host_max_size
  desired_capacity    = var.sandbox_host_desired_capacity

  health_check_type         = "ELB"
  health_check_grace_period = 300
  target_group_arns         = [aws_lb_target_group.sandbox_api.arn]

  launch_template {
    id      = aws_launch_template.sandbox_host.id
    version = "$Latest"
  }

  instance_refresh {
    strategy = "Rolling"

    preferences {
      min_healthy_percentage = 50
    }
  }

  tag {
    key                 = "Name"
    value               = "${var.name_prefix}-sandbox-host"
    propagate_at_launch = true
  }

  tag {
    key                 = "TrustZone"
    value               = "sandbox"
    propagate_at_launch = true
  }

  tag {
    key                 = "NetworkMode"
    value               = "no-nat"
    propagate_at_launch = true
  }

  tag {
    key                 = "SsmManaged"
    value               = "true"
    propagate_at_launch = true
  }
}
