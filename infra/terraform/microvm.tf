variable "microvm_artifact_bucket_name" {
  type        = string
  description = "Optional S3 bucket name for Lambda MicroVM image artifacts."
  default     = null
}

variable "microvm_image_name" {
  type        = string
  description = "Lambda MicroVM image name used for logs and build commands."
  default     = "tango-sandbox-executor"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,62}$", var.microvm_image_name))
    error_message = "microvm_image_name must start with a lowercase letter and contain lowercase letters, numbers, and hyphens."
  }
}

variable "microvm_base_image_name" {
  type        = string
  description = "AWS-managed Lambda MicroVM base image name."
  default     = "al2023-1"
}

variable "microvm_broker_trusted_services" {
  type        = list(string)
  description = "AWS service principals allowed to assume the broker role."
  default     = ["lambda.amazonaws.com"]
}

variable "microvm_operator_trusted_principal_arns" {
  type        = list(string)
  description = "AWS principals allowed to assume the operator role for local artifact upload, image creation, and smoke tests. Defaults to the current account root."
  default     = []
}

locals {
  microvm_artifact_bucket_name = coalesce(
    var.microvm_artifact_bucket_name,
    "${var.name_prefix}-${var.environment}-${data.aws_caller_identity.current.account_id}-${data.aws_region.current.name}-microvm-artifacts",
  )
  microvm_operator_trusted_principal_arns = length(var.microvm_operator_trusted_principal_arns) > 0 ? var.microvm_operator_trusted_principal_arns : ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
  microvm_base_image_arn                  = "arn:aws:lambda:${data.aws_region.current.name}:aws:microvm-image:${var.microvm_base_image_name}"
  microvm_all_ingress_connector_arn       = "arn:aws:lambda:${data.aws_region.current.name}:aws:network-connector:aws-network-connector:ALL_INGRESS"
  microvm_internet_egress_connector_arn   = "arn:aws:lambda:${data.aws_region.current.name}:aws:network-connector:aws-network-connector:INTERNET_EGRESS"
  microvm_image_arn                       = "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:microvm-image:${var.microvm_image_name}"
}

resource "aws_s3_bucket" "microvm_artifacts" {
  bucket = local.microvm_artifact_bucket_name
}

resource "aws_s3_bucket_ownership_controls" "microvm_artifacts" {
  bucket = aws_s3_bucket.microvm_artifacts.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "microvm_artifacts" {
  bucket = aws_s3_bucket.microvm_artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "microvm_artifacts" {
  bucket = aws_s3_bucket.microvm_artifacts.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "microvm_artifacts" {
  bucket = aws_s3_bucket.microvm_artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.sandbox.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

data "aws_iam_policy_document" "microvm_artifacts_bucket" {
  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"
    actions = [
      "s3:*",
    ]
    resources = [
      aws_s3_bucket.microvm_artifacts.arn,
      "${aws_s3_bucket.microvm_artifacts.arn}/*",
    ]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "microvm_artifacts" {
  bucket = aws_s3_bucket.microvm_artifacts.id
  policy = data.aws_iam_policy_document.microvm_artifacts_bucket.json
}

resource "aws_cloudwatch_log_group" "microvm" {
  name              = "/aws/lambda/microvms/${var.microvm_image_name}"
  retention_in_days = 30
  kms_key_id        = aws_kms_key.sandbox.arn
}

data "aws_iam_policy_document" "microvm_lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "microvm_build" {
  name               = "${var.name_prefix}-${var.environment}-microvm-build"
  assume_role_policy = data.aws_iam_policy_document.microvm_lambda_assume_role.json
}

data "aws_iam_policy_document" "microvm_build" {
  statement {
    sid       = "ReadMicrovmArtifact"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.microvm_artifacts.arn}/*"]
  }

  statement {
    sid       = "DecryptMicrovmArtifact"
    actions   = ["kms:Decrypt"]
    resources = [aws_kms_key.sandbox.arn]
  }

  statement {
    sid       = "CreateMicrovmBuildLogGroup"
    actions   = ["logs:CreateLogGroup"]
    resources = ["*"]
  }

  statement {
    sid = "WriteMicrovmBuildLogs"
    actions = [
      "logs:CreateLogStream",
      "logs:DescribeLogStreams",
      "logs:PutLogEvents",
    ]
    resources = [
      aws_cloudwatch_log_group.microvm.arn,
      "${aws_cloudwatch_log_group.microvm.arn}:*",
    ]
  }
}

resource "aws_iam_policy" "microvm_build" {
  name   = "${var.name_prefix}-${var.environment}-microvm-build"
  policy = data.aws_iam_policy_document.microvm_build.json
}

resource "aws_iam_role_policy_attachment" "microvm_build" {
  role       = aws_iam_role.microvm_build.name
  policy_arn = aws_iam_policy.microvm_build.arn
}

resource "aws_iam_role" "microvm_execution" {
  name               = "${var.name_prefix}-${var.environment}-microvm-execution"
  assume_role_policy = data.aws_iam_policy_document.microvm_lambda_assume_role.json
}

data "aws_iam_policy_document" "microvm_execution" {
  statement {
    sid = "WriteMicrovmRuntimeLogs"
    actions = [
      "logs:CreateLogStream",
      "logs:DescribeLogStreams",
      "logs:PutLogEvents",
    ]
    resources = ["${aws_cloudwatch_log_group.microvm.arn}:*"]
  }
}

resource "aws_iam_policy" "microvm_execution" {
  name   = "${var.name_prefix}-${var.environment}-microvm-execution"
  policy = data.aws_iam_policy_document.microvm_execution.json
}

resource "aws_iam_role_policy_attachment" "microvm_execution" {
  role       = aws_iam_role.microvm_execution.name
  policy_arn = aws_iam_policy.microvm_execution.arn
}

data "aws_iam_policy_document" "microvm_broker_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = var.microvm_broker_trusted_services
    }
  }
}

resource "aws_iam_role" "microvm_broker" {
  name               = "${var.name_prefix}-${var.environment}-microvm-broker"
  assume_role_policy = data.aws_iam_policy_document.microvm_broker_assume_role.json
}

data "aws_iam_policy_document" "microvm_broker" {
  statement {
    sid = "ManagePerAttemptMicrovms"
    actions = [
      "lambda:CreateMicrovmAuthToken",
      "lambda:GetMicrovm",
      "lambda:RunMicrovm",
      "lambda:TerminateMicrovm",
    ]
    resources = ["*"]
  }

  statement {
    sid       = "PassMicrovmExecutionRole"
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.microvm_execution.arn]
  }

  statement {
    sid     = "PassManagedMicrovmNetworkConnectors"
    actions = ["lambda:PassNetworkConnector"]
    resources = [
      local.microvm_all_ingress_connector_arn,
      local.microvm_internet_egress_connector_arn,
    ]
  }

  statement {
    sid = "WriteBrokerLambdaLogs"
    actions = [
      "logs:CreateLogStream",
      "logs:DescribeLogStreams",
      "logs:PutLogEvents",
    ]
    resources = [
      aws_cloudwatch_log_group.lambda_broker.arn,
      "${aws_cloudwatch_log_group.lambda_broker.arn}:*",
    ]
  }
}

resource "aws_iam_policy" "microvm_broker" {
  name   = "${var.name_prefix}-${var.environment}-microvm-broker"
  policy = data.aws_iam_policy_document.microvm_broker.json
}

resource "aws_iam_role_policy_attachment" "microvm_broker" {
  role       = aws_iam_role.microvm_broker.name
  policy_arn = aws_iam_policy.microvm_broker.arn
}

data "aws_iam_policy_document" "microvm_operator_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "AWS"
      identifiers = local.microvm_operator_trusted_principal_arns
    }
  }
}

resource "aws_iam_role" "microvm_operator" {
  name               = "${var.name_prefix}-${var.environment}-microvm-operator"
  assume_role_policy = data.aws_iam_policy_document.microvm_operator_assume_role.json
}

data "aws_iam_policy_document" "microvm_operator" {
  statement {
    sid = "ManageMicrovmArtifacts"
    actions = [
      "s3:GetObject",
      "s3:ListBucket",
      "s3:PutObject",
    ]
    resources = [
      aws_s3_bucket.microvm_artifacts.arn,
      "${aws_s3_bucket.microvm_artifacts.arn}/*",
    ]
  }

  statement {
    sid = "UseArtifactEncryptionKey"
    actions = [
      "kms:Decrypt",
      "kms:Encrypt",
      "kms:GenerateDataKey",
    ]
    resources = [aws_kms_key.sandbox.arn]
  }

  statement {
    sid = "BuildAndSmokeTestMicrovms"
    actions = [
      "lambda:CreateMicrovmAuthToken",
      "lambda:CreateMicrovmImage",
      "lambda:GetMicrovm",
      "lambda:GetMicrovmImage",
      "lambda:ListMicrovmImages",
      "lambda:ListMicrovms",
      "lambda:RunMicrovm",
      "lambda:TerminateMicrovm",
    ]
    resources = ["*"]
  }

  statement {
    sid     = "PassMicrovmBuildAndExecutionRoles"
    actions = ["iam:PassRole"]
    resources = [
      aws_iam_role.microvm_build.arn,
      aws_iam_role.microvm_execution.arn,
    ]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values = [
        "lambda.amazonaws.com",
        "lambda-microvms.amazonaws.com",
      ]
    }
  }

  statement {
    sid       = "InvokeBrokerFunctionUrl"
    actions   = ["lambda:InvokeFunctionUrl"]
    resources = [aws_lambda_function.microvm_broker.arn]
  }

  statement {
    sid     = "PassManagedMicrovmNetworkConnectors"
    actions = ["lambda:PassNetworkConnector"]
    resources = [
      local.microvm_all_ingress_connector_arn,
      local.microvm_internet_egress_connector_arn,
    ]
  }
}

resource "aws_iam_policy" "microvm_operator" {
  name   = "${var.name_prefix}-${var.environment}-microvm-operator"
  policy = data.aws_iam_policy_document.microvm_operator.json
}

resource "aws_iam_role_policy_attachment" "microvm_operator" {
  role       = aws_iam_role.microvm_operator.name
  policy_arn = aws_iam_policy.microvm_operator.arn
}
