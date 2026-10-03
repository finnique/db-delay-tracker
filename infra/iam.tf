locals {
  collector_function_name = "${var.project}-collector"
}

# Trust policy: only the Lambda service may assume this role.
data "aws_iam_policy_document" "lambda_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "collector" {
  name               = "${local.collector_function_name}-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

# Created here (not by Lambda) so we control retention and the role needs no logs:CreateLogGroup.
resource "aws_cloudwatch_log_group" "collector" {
  name              = "/aws/lambda/${local.collector_function_name}"
  retention_in_days = var.log_retention_days
}

# Permissions policy: the minimum the collector needs.
data "aws_iam_policy_document" "collector" {
  # Write raw files. PutObject only: no read, no delete, no list.
  # Scoped to raw/ so the collector cannot touch staged/ or marts.
  statement {
    sid       = "WriteRawObjects"
    effect    = "Allow"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.data.arn}/raw/*"]
  }

  # Read exactly the two API credentials. The AWS-managed key alias/aws/ssm lets any
  # principal in the account that is allowed to call SSM decrypt via SSM, so no
  # kms:Decrypt statement is needed (it would be if we used a customer-managed key).
  statement {
    sid     = "ReadApiCredentials"
    effect  = "Allow"
    actions = ["ssm:GetParameter"]
    resources = [
      aws_ssm_parameter.db_client_id.arn,
      aws_ssm_parameter.db_api_key.arn,
    ]
  }

  # Write logs to its own log group only. ":*" covers the log streams inside the group.
  statement {
    sid       = "WriteOwnLogs"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.collector.arn}:*"]
  }
}

resource "aws_iam_role_policy" "collector" {
  name   = "collector-permissions"
  role   = aws_iam_role.collector.id
  policy = data.aws_iam_policy_document.collector.json
}
