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

output "sandbox_api_load_balancer_dns_name" {
  description = "Private DNS name of the internal sandbox API load balancer."
  value       = aws_lb.sandbox_api.dns_name
}

output "sandbox_api_url" {
  description = "Private sandbox executor API URL for Temporal worker configuration."
  value       = "http://${aws_lb.sandbox_api.dns_name}:${var.sandbox_api_port}"
}

output "sandbox_host_autoscaling_group_name" {
  description = "Name of the autoscaling group managing sandbox hosts."
  value       = aws_autoscaling_group.sandbox_host.name
}

output "sandbox_host_launch_template_id" {
  description = "ID of the launch template used for sandbox hosts."
  value       = aws_launch_template.sandbox_host.id
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
