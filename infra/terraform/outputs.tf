output "vpc_id" {
  description = "ID of the isolated sandbox VPC."
  value       = aws_vpc.sandbox.id
}

output "sandbox_subnet_id" {
  description = "ID of the private subnet hosting sandbox instances."
  value       = aws_subnet.sandbox.id
}

output "sandbox_security_group_id" {
  description = "Security group attached to sandbox hosts."
  value       = aws_security_group.sandbox_host.id
}

output "vpc_endpoint_security_group_id" {
  description = "Security group attached to interface VPC endpoints."
  value       = aws_security_group.vpc_endpoint.id
}

output "sandbox_host_instance_ids" {
  description = "IDs of sandbox EC2 hosts."
  value       = aws_instance.sandbox_host[*].id
}

output "sandbox_host_private_ips" {
  description = "Private IPs of sandbox EC2 hosts."
  value       = aws_instance.sandbox_host[*].private_ip
}

output "sandbox_kms_key_arn" {
  description = "KMS key used for sandbox logs and root volumes."
  value       = aws_kms_key.sandbox.arn
}

output "sandbox_log_group_name" {
  description = "CloudWatch log group for sandbox host logs."
  value       = aws_cloudwatch_log_group.sandbox.name
}

output "vpc_flow_log_group_name" {
  description = "CloudWatch log group for VPC flow logs."
  value       = aws_cloudwatch_log_group.vpc_flow_logs.name
}
