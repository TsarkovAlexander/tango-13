terraform {
  required_version = ">= 1.6.0"

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
  description = "AWS region for the sandbox VPC."
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
  default     = "prod"

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

variable "vpc_cidr" {
  type        = string
  description = "CIDR block for the isolated sandbox VPC."
  default     = "10.42.0.0/16"

  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "vpc_cidr must be a valid IPv4 CIDR block."
  }
}

variable "sandbox_subnet_cidr" {
  type        = string
  description = "CIDR block for sandbox hosts."
  default     = "10.42.10.0/24"

  validation {
    condition     = can(cidrhost(var.sandbox_subnet_cidr, 0))
    error_message = "sandbox_subnet_cidr must be a valid IPv4 CIDR block."
  }
}

variable "sandbox_api_port" {
  type        = number
  description = "Internal sandbox executor API port."
  default     = 8080

  validation {
    condition     = var.sandbox_api_port > 0 && var.sandbox_api_port <= 65535
    error_message = "sandbox_api_port must be between 1 and 65535."
  }
}
