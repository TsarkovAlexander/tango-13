terraform {
  required_version = ">= 1.15.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.common_tags
  }
}

variable "aws_region" {
  type        = string
  description = "AWS region for Lambda MicroVM resources."
  default     = "us-east-1"

  validation {
    condition     = var.aws_region == "us-east-1"
    error_message = "aws_region must be us-east-1."
  }
}

variable "name_prefix" {
  type        = string
  description = "Name prefix for provisioned resources."
  default     = "tango"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,30}$", var.name_prefix))
    error_message = "name_prefix must start with a lowercase letter and contain only lowercase letters, numbers, and hyphens."
  }
}

variable "environment" {
  type        = string
  description = "Deployment environment name."
  default     = "test"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,30}$", var.environment))
    error_message = "environment must start with a lowercase letter and contain only lowercase letters, numbers, and hyphens."
  }
}

variable "additional_tags" {
  type        = map(string)
  description = "Additional tags applied to every supported resource."
  default     = {}
}

variable "sandbox_account_id" {
  type        = string
  description = "Expected AWS sandbox account ID used as a guardrail for deployments."
  default     = "569813798269"

  validation {
    condition     = can(regex("^[0-9]{12}$", var.sandbox_account_id))
    error_message = "sandbox_account_id must be a 12-digit AWS account ID."
  }
}

check "sandbox_account" {
  assert {
    condition     = data.aws_caller_identity.current.account_id == var.sandbox_account_id
    error_message = "Configure AWS credentials for sandbox account ${var.sandbox_account_id} before applying this stack."
  }
}

