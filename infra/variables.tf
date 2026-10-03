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
