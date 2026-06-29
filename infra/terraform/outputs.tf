output "sandbox_kms_key_arn" {
  description = "KMS key used for Lambda MicroVM artifacts and logs."
  value       = aws_kms_key.sandbox.arn
}

output "microvm_artifact_bucket_name" {
  description = "S3 bucket for Lambda MicroVM build artifacts."
  value       = aws_s3_bucket.microvm_artifacts.bucket
}

output "microvm_artifact_bucket_uri" {
  description = "S3 URI prefix for Lambda MicroVM build artifacts."
  value       = "s3://${aws_s3_bucket.microvm_artifacts.bucket}"
}

output "microvm_build_role_arn" {
  description = "IAM role ARN assumed by Lambda while building MicroVM images."
  value       = aws_iam_role.microvm_build.arn
}

output "microvm_execution_role_arn" {
  description = "IAM role ARN available to running Lambda MicroVMs."
  value       = aws_iam_role.microvm_execution.arn
}

output "microvm_broker_role_arn" {
  description = "IAM role ARN for the service that brokers per-attempt MicroVMs."
  value       = aws_iam_role.microvm_broker.arn
}

output "microvm_operator_role_arn" {
  description = "IAM role ARN for local/CI operators that upload artifacts, create images, and run smoke tests."
  value       = aws_iam_role.microvm_operator.arn
}

output "microvm_log_group_name" {
  description = "CloudWatch log group for Lambda MicroVM build and runtime logs."
  value       = aws_cloudwatch_log_group.microvm.name
}

output "microvm_base_image_arn" {
  description = "AWS-managed Lambda MicroVM base image ARN for create-microvm-image."
  value       = local.microvm_base_image_arn
}

output "microvm_all_ingress_connector_arn" {
  description = "AWS-managed Lambda MicroVM ingress connector ARN for smoke tests."
  value       = local.microvm_all_ingress_connector_arn
}

output "microvm_image_name" {
  description = "Configured Lambda MicroVM image name."
  value       = var.microvm_image_name
}

output "microvm_image_arn" {
  description = "Expected Lambda MicroVM image ARN after create-microvm-image succeeds."
  value       = local.microvm_image_arn
}

output "lambda_broker_function_name" {
  description = "Name of the broker Lambda function."
  value       = aws_lambda_function.microvm_broker.function_name
}

output "lambda_broker_function_url" {
  description = "IAM-authenticated Lambda Function URL for the MicroVM broker."
  value       = aws_lambda_function_url.microvm_broker.function_url
}
