# The collector function. The code is built outside Terraform by
# scripts/build_lambda.py (run it first); Terraform only uploads the zip and
# redeploys when its hash changes. The IAM role and log group live in iam.tf.

resource "aws_lambda_function" "collector" {
  function_name = local.collector_function_name
  role          = aws_iam_role.collector.arn

  filename         = "${path.module}/../build/lambda.zip"
  source_code_hash = filebase64sha256("${path.module}/../build/lambda.zip")

  runtime       = "python3.13" # must match PYTHON_VERSION in scripts/build_lambda.py
  architectures = ["arm64"]    # must match PLATFORM in scripts/build_lambda.py
  handler       = "db_delay_tracker.handler.handler"

  # 8 stations are fetched one after another; the client allows 10 s per call.
  timeout     = 90
  memory_size = 256

  environment {
    variables = {
      BUCKET_NAME = aws_s3_bucket.data.bucket
      SSM_PREFIX  = "/${var.project}"
    }
  }

  # The log group is created in iam.tf; make sure it exists before the function
  # so Lambda does not auto-create one with infinite retention.
  depends_on = [aws_cloudwatch_log_group.collector, aws_iam_role_policy.collector]
}
