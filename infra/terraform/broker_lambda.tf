variable "lambda_broker_artifact_path" {
  type        = string
  description = "Path to the packaged broker Lambda zip artifact."
  default     = "../../dist/tango-broker-lambda.zip"
}

variable "lambda_broker_timeout_seconds" {
  type        = number
  description = "Broker Lambda timeout in seconds."
  default     = 45

  validation {
    condition     = var.lambda_broker_timeout_seconds >= 1 && var.lambda_broker_timeout_seconds <= 900
    error_message = "lambda_broker_timeout_seconds must be between 1 and 900."
  }
}

variable "lambda_broker_memory_size" {
  type        = number
  description = "Broker Lambda memory size in MB."
  default     = 512

  validation {
    condition     = var.lambda_broker_memory_size >= 128 && var.lambda_broker_memory_size <= 10240
    error_message = "lambda_broker_memory_size must be between 128 and 10240."
  }
}

resource "aws_cloudwatch_log_group" "lambda_broker" {
  name              = "/aws/lambda/${local.lambda_broker_function_name}"
  retention_in_days = 30
  kms_key_id        = aws_kms_key.sandbox.arn
}

resource "aws_lambda_function" "microvm_broker" {
  function_name    = local.lambda_broker_function_name
  description      = "Tango Lambda MicroVM broker"
  role             = aws_iam_role.microvm_broker.arn
  filename         = var.lambda_broker_artifact_path
  source_code_hash = filebase64sha256(var.lambda_broker_artifact_path)
  handler          = "sandbox_executor.lambda_broker.handler"
  runtime          = "python3.12"
  architectures    = ["arm64"]
  timeout          = var.lambda_broker_timeout_seconds
  memory_size      = var.lambda_broker_memory_size

  environment {
    variables = {
      TANGO_AWS_REGION                            = data.aws_region.current.name
      TANGO_LAMBDA_MICROVM_EXECUTION_ROLE_ARN    = aws_iam_role.microvm_execution.arn
      TANGO_LAMBDA_MICROVM_IMAGE_IDENTIFIER      = local.microvm_image_arn
      TANGO_LAMBDA_MICROVM_MAXIMUM_DURATION_SECONDS = "60"
      TANGO_TRACE_STDOUT                         = "true"
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda_broker,
    aws_iam_role_policy_attachment.microvm_broker,
  ]
}

resource "aws_lambda_function_url" "microvm_broker" {
  function_name      = aws_lambda_function.microvm_broker.function_name
  authorization_type = "AWS_IAM"
}
