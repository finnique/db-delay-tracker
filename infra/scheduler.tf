# The role EventBridge Scheduler assumes to invoke the Lambda. Separate from the
# collector's own role: that one is what the function can do, this one is what
# the clock can do.
data "aws_iam_policy_document" "scheduler_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
    # Confused-deputy protection: only schedules in this account may use the role.
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  name               = "${var.project}-scheduler-role"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume.json
}

data "aws_iam_policy_document" "scheduler" {
  # Invoke this one function and nothing else.
  statement {
    sid       = "InvokeCollector"
    effect    = "Allow"
    actions   = ["lambda:InvokeFunction"]
    resources = [aws_lambda_function.collector.arn]
  }
}

resource "aws_iam_role_policy" "scheduler" {
  name   = "invoke-collector"
  role   = aws_iam_role.scheduler.id
  policy = data.aws_iam_policy_document.scheduler.json
}

locals {
  # Scheduler's smallest rate unit is 1 minute, so rchg (window ~2 min) runs every minute.
  schedules = {
    rchg = "rate(1 minute)"
    fchg = "rate(15 minutes)"
    plan = "rate(1 hour)"
  }
}

resource "aws_scheduler_schedule" "collector" {
  for_each = local.schedules

  name                = "${var.project}-${each.key}"
  schedule_expression = each.value
  state               = var.schedules_enabled ? "ENABLED" : "DISABLED"

  # No random delay: polls should fire on the minute.
  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.collector.arn
    role_arn = aws_iam_role.scheduler.arn
    input    = jsonencode({ endpoint = each.key })

    # A failed poll is not retried: a late rchg/fchg pull would only duplicate
    # what the next scheduled call fetches anyway.
    retry_policy {
      maximum_retry_attempts = 0
    }
  }
}
