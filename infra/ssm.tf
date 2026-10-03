# The real values are NOT in Terraform. Terraform creates the parameters with a
# placeholder; you set the real values once with the CLI (see README / PROGRESS.md).
# ignore_changes stops later applies from overwriting them, and keeps the secrets
# out of the state file (state only ever holds the placeholder).

resource "aws_ssm_parameter" "db_client_id" {
  name  = "/${var.project}/db-client-id"
  type  = "SecureString" # encrypted with the AWS-managed key alias/aws/ssm (free)
  value = "placeholder-set-with-aws-cli"

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "db_api_key" {
  name  = "/${var.project}/db-api-key"
  type  = "SecureString"
  value = "placeholder-set-with-aws-cli"

  lifecycle {
    ignore_changes = [value]
  }
}
