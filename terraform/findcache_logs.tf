# FindCache debug-log uploads: the app's "Send log to KnG" button POSTs a
# user-approved debug log to a Lambda Function URL, which writes it to a
# private bucket. Objects expire after 180 days. Code:
# src/findcache_log/handler.py.

resource "aws_s3_bucket" "findcache_logs" {
  bucket = var.findcache_logs_bucket_name
}

resource "aws_s3_bucket_public_access_block" "findcache_logs" {
  bucket                  = aws_s3_bucket.findcache_logs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "findcache_logs" {
  bucket = aws_s3_bucket.findcache_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "findcache_logs" {
  bucket = aws_s3_bucket.findcache_logs.id

  rule {
    id     = "expire-logs-after-180-days"
    status = "Enabled"

    filter {}

    expiration {
      days = 180
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

data "archive_file" "findcache_log_handler" {
  type        = "zip"
  source_dir  = "${path.module}/../src/findcache_log"
  output_path = "${path.module}/findcache_log.zip"
  excludes    = ["__pycache__"]
}

resource "aws_cloudwatch_log_group" "findcache_log" {
  name              = "/aws/lambda/kng-findcache-log"
  retention_in_days = 30
}

resource "aws_iam_role" "findcache_log" {
  name               = "kng-findcache-log"
  assume_role_policy = data.aws_iam_policy_document.contact_assume.json
}

data "aws_iam_policy_document" "findcache_log" {
  statement {
    sid       = "WriteLogs"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.findcache_log.arn}:*"]
  }

  statement {
    sid       = "StoreLogs"
    effect    = "Allow"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.findcache_logs.arn}/findcache/*"]
  }
}

resource "aws_iam_role_policy" "findcache_log" {
  name   = "kng-findcache-log"
  role   = aws_iam_role.findcache_log.id
  policy = data.aws_iam_policy_document.findcache_log.json
}

resource "aws_lambda_function" "findcache_log" {
  function_name    = "kng-findcache-log"
  role             = aws_iam_role.findcache_log.arn
  runtime          = "python3.12"
  handler          = "handler.handler"
  filename         = data.archive_file.findcache_log_handler.output_path
  source_code_hash = data.archive_file.findcache_log_handler.output_base64sha256
  timeout          = 10
  memory_size      = 128

  environment {
    variables = {
      LOG_BUCKET = aws_s3_bucket.findcache_logs.bucket
    }
  }

  depends_on = [aws_cloudwatch_log_group.findcache_log, aws_iam_role_policy.findcache_log]
}

# The app is native, not a browser, so no CORS block is needed.
resource "aws_lambda_function_url" "findcache_log" {
  function_name      = aws_lambda_function.findcache_log.function_name
  authorization_type = "NONE"
}

# Same two statements as contact_url/contact_invoke: a NONE-auth Function
# URL is still denied unless the resource policy allows public invocation.
resource "aws_lambda_permission" "findcache_log_url" {
  statement_id           = "AllowPublicFunctionUrl"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.findcache_log.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "findcache_log_invoke" {
  statement_id             = "AllowPublicInvokeViaFunctionUrl"
  action                   = "lambda:InvokeFunction"
  function_name            = aws_lambda_function.findcache_log.function_name
  principal                = "*"
  invoked_via_function_url = true
}
