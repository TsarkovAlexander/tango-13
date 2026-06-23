resource "aws_lb" "sandbox_api" {
  name               = "${var.name_prefix}-sandbox-api"
  internal           = true
  load_balancer_type = "network"
  security_groups    = [aws_security_group.sandbox_api_lb.id]
  subnets            = [aws_subnet.sandbox.id]

  enable_deletion_protection = var.sandbox_api_lb_deletion_protection

  tags = {
    Name      = "${var.name_prefix}-sandbox-api"
    TrustZone = "sandbox"
  }
}

resource "aws_lb_target_group" "sandbox_api" {
  name        = "${var.name_prefix}-sandbox-api"
  port        = var.sandbox_api_port
  protocol    = "TCP"
  target_type = "instance"
  vpc_id      = aws_vpc.sandbox.id

  deregistration_delay = 30

  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200-399"
    path                = var.sandbox_api_health_check_path
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 10
    unhealthy_threshold = 2
  }

  tags = {
    Name      = "${var.name_prefix}-sandbox-api"
    TrustZone = "sandbox"
  }
}

resource "aws_lb_listener" "sandbox_api" {
  load_balancer_arn = aws_lb.sandbox_api.arn
  port              = var.sandbox_api_port
  protocol          = "TCP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.sandbox_api.arn
  }
}
