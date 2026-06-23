data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_region" "current" {}

resource "aws_vpc" "sandbox" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.name_prefix}-sandbox"
  }
}

resource "aws_subnet" "sandbox" {
  vpc_id                  = aws_vpc.sandbox.id
  cidr_block              = var.sandbox_subnet_cidr
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = false

  tags = {
    Name = "${var.name_prefix}-sandbox-private"
  }
}

resource "aws_route_table" "sandbox" {
  vpc_id = aws_vpc.sandbox.id

  tags = {
    Name = "${var.name_prefix}-sandbox-no-internet"
  }
}

resource "aws_route_table_association" "sandbox" {
  subnet_id      = aws_subnet.sandbox.id
  route_table_id = aws_route_table.sandbox.id
}

resource "aws_security_group" "sandbox_host" {
  name        = "${var.name_prefix}-sandbox-host"
  description = "Sandbox hosts accept only internal sandbox API traffic."
  vpc_id      = aws_vpc.sandbox.id

  ingress {
    description = "Internal sandbox API"
    from_port   = var.sandbox_api_port
    to_port     = var.sandbox_api_port
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  tags = {
    Name = "${var.name_prefix}-sandbox-host"
  }
}

resource "aws_security_group" "vpc_endpoint" {
  name        = "${var.name_prefix}-vpc-endpoints"
  description = "Private AWS API endpoint access from sandbox hosts."
  vpc_id      = aws_vpc.sandbox.id

  ingress {
    description     = "HTTPS from sandbox hosts"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.sandbox_host.id]
  }

  tags = {
    Name = "${var.name_prefix}-vpc-endpoints"
  }
}

resource "aws_vpc_security_group_egress_rule" "sandbox_to_vpc_endpoints" {
  security_group_id            = aws_security_group.sandbox_host.id
  referenced_security_group_id = aws_security_group.vpc_endpoint.id
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
  description                  = "Allow only private AWS API endpoint access."
}

locals {
  interface_endpoint_services = [
    "com.amazonaws.${data.aws_region.current.name}.ec2messages",
    "com.amazonaws.${data.aws_region.current.name}.kms",
    "com.amazonaws.${data.aws_region.current.name}.logs",
    "com.amazonaws.${data.aws_region.current.name}.ssm",
    "com.amazonaws.${data.aws_region.current.name}.ssmmessages",
  ]
}

resource "aws_vpc_endpoint" "interface" {
  for_each            = toset(local.interface_endpoint_services)
  vpc_id              = aws_vpc.sandbox.id
  service_name        = each.value
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.sandbox.id]
  security_group_ids  = [aws_security_group.vpc_endpoint.id]
  private_dns_enabled = true

  tags = {
    Name = "${var.name_prefix}-${replace(each.key, ".", "-")}"
  }
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.sandbox.id
  service_name      = "com.amazonaws.${data.aws_region.current.name}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.sandbox.id]

  tags = {
    Name = "${var.name_prefix}-s3"
  }
}
