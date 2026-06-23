locals {
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
