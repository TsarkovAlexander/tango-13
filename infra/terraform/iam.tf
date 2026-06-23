data "aws_iam_policy_document" "sandbox_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "sandbox_host" {
  name               = "${var.name_prefix}-sandbox-host"
  assume_role_policy = data.aws_iam_policy_document.sandbox_assume_role.json
}

data "aws_iam_policy_document" "sandbox_host" {
  statement {
    sid = "AllowSsmSessionManager"
    actions = [
      "ssm:UpdateInstanceInformation",
      "ssmmessages:CreateControlChannel",
      "ssmmessages:CreateDataChannel",
      "ssmmessages:OpenControlChannel",
      "ssmmessages:OpenDataChannel",
      "ec2messages:AcknowledgeMessage",
      "ec2messages:DeleteMessage",
      "ec2messages:FailMessage",
      "ec2messages:GetEndpoint",
      "ec2messages:GetMessages",
      "ec2messages:SendReply",
    ]
    resources = ["*"]
  }

  statement {
    sid = "AllowCloudWatchLogs"
    actions = [
      "logs:CreateLogStream",
      "logs:DescribeLogStreams",
      "logs:PutLogEvents",
    ]
    resources = ["${aws_cloudwatch_log_group.sandbox.arn}:*"]
  }
}

resource "aws_iam_policy" "sandbox_host" {
  name   = "${var.name_prefix}-sandbox-host"
  policy = data.aws_iam_policy_document.sandbox_host.json
}

resource "aws_iam_role_policy_attachment" "sandbox_host" {
  role       = aws_iam_role.sandbox_host.name
  policy_arn = aws_iam_policy.sandbox_host.arn
}

resource "aws_iam_instance_profile" "sandbox_host" {
  name = "${var.name_prefix}-sandbox-host"
  role = aws_iam_role.sandbox_host.name
}

resource "aws_cloudwatch_log_group" "sandbox" {
  name              = "/${var.name_prefix}/sandbox-host"
  retention_in_days = 30
  kms_key_id        = aws_kms_key.sandbox.arn
}
