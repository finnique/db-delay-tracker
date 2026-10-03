output "bucket_name" {
  value = aws_s3_bucket.data.bucket
}

output "collector_role_arn" {
  value = aws_iam_role.collector.arn
}

output "ssm_parameter_names" {
  value = [
    aws_ssm_parameter.db_client_id.name,
    aws_ssm_parameter.db_api_key.name,
  ]
}
