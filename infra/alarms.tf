resource "aws_sns_topic" "alerts" {
  name = "${var.project}-alerts"
}

# Email subscriptions stay "pending" until the recipient clicks the confirmation link.
resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# 1) The collector ran but stations failed. The handler raises when any station
#    fails, which Lambda counts as an error. 3 in 15 minutes ignores one-off API blips.
resource "aws_cloudwatch_metric_alarm" "errors" {
  alarm_name          = "${var.project}-collector-errors"
  alarm_description   = "Collector Lambda failed 3+ times in 15 minutes. Check the log group ${aws_cloudwatch_log_group.collector.name}."
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = aws_lambda_function.collector.function_name }
  statistic           = "Sum"
  period              = 900
  evaluation_periods  = 1
  threshold           = 3
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
}

# 2) Nothing ran at all (schedules disabled or broken). Expected: ~16 invocations
#    per 15 minutes (15 rchg + 1 fchg + plan). A dead schedule produces no errors,
#    so alarm 1 would stay silent. Missing data counts as breaching for that reason.
#    Notifications are off while schedules_enabled is false.
resource "aws_cloudwatch_metric_alarm" "silence" {
  alarm_name          = "${var.project}-collector-silence"
  alarm_description   = "Fewer than 10 collector invocations in 15 minutes. Schedules disabled or broken?"
  namespace           = "AWS/Lambda"
  metric_name         = "Invocations"
  dimensions          = { FunctionName = aws_lambda_function.collector.function_name }
  statistic           = "Sum"
  period              = 900
  evaluation_periods  = 1
  threshold           = 10
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = "breaching"
  actions_enabled     = var.schedules_enabled
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
}
