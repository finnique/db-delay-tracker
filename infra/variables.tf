variable "region" {
  description = "AWS region for all resources."
  type        = string
  default     = "eu-central-1"
}

variable "project" {
  description = "Prefix for resource names."
  type        = string
  default     = "db-delay-tracker"
}

variable "log_retention_days" {
  description = "CloudWatch log retention for the collector Lambda."
  type        = number
  default     = 14
}

variable "alert_email" {
  description = "Email address that receives the CloudWatch alarm notifications. Set in terraform.tfvars (gitignored)."
  type        = string
}

variable "schedules_enabled" {
  description = "Switch for the EventBridge schedules (and the silence alarm). Keep false until the Lambda has been invoked by hand and verified."
  type        = bool
  default     = false
}
