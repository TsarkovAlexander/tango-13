locals {
  lambda_broker_function_name = "${var.name_prefix}-${var.environment}-microvm-broker"

  common_tags = merge(
    {
      Project     = var.name_prefix
      Environment = var.environment
      ManagedBy   = "terraform"
      Component   = "sandbox"
    },
    var.additional_tags,
  )
}
