# Downloads: private bucket for release installers and guides, plus a Lambda
# (Function URL) that redirects to 5-minute signed URLs. Code:
# src/download_handler/handler.py. The publish-downloads workflow fills the
# bucket and writes matrix.json.

locals {
  downloads_allowed_origins = [
    for d in concat(var.live_domain_names, [var.preview_domain_name]) : "https://${d}"
  ]
}

resource "aws_s3_bucket" "downloads" {
  bucket = var.downloads_bucket_name
}

resource "aws_s3_bucket_public_access_block" "downloads" {
  bucket                  = aws_s3_bucket.downloads.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "downloads" {
  bucket = aws_s3_bucket.downloads.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "downloads" {
  bucket = aws_s3_bucket.downloads.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Versioning keeps matrix.json recoverable; superseded versions expire.
resource "aws_s3_bucket_lifecycle_configuration" "downloads" {
  bucket = aws_s3_bucket.downloads.id

  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 30
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  depends_on = [aws_s3_bucket_versioning.downloads]
}

data "archive_file" "downloads_handler" {
  type        = "zip"
  source_dir  = "${path.module}/../src/download_handler"
  output_path = "${path.module}/download_handler.zip"
  excludes    = ["__pycache__"]
}

resource "aws_cloudwatch_log_group" "downloads" {
  name              = "/aws/lambda/kng-downloads"
  retention_in_days = 30
}

data "aws_iam_policy_document" "downloads_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "downloads" {
  name               = "kng-downloads"
  assume_role_policy = data.aws_iam_policy_document.downloads_assume.json
}

# GetObject is what lets the signed URLs work: they carry this role's authority.
data "aws_iam_policy_document" "downloads" {
  statement {
    sid       = "ReadDownloads"
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.downloads.arn}/*"]
  }

  statement {
    sid       = "WriteLogs"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.downloads.arn}:*"]
  }
}

resource "aws_iam_role_policy" "downloads" {
  name   = "kng-downloads"
  role   = aws_iam_role.downloads.id
  policy = data.aws_iam_policy_document.downloads.json
}

resource "aws_lambda_function" "downloads" {
  function_name    = "kng-downloads"
  role             = aws_iam_role.downloads.arn
  runtime          = "python3.12"
  handler          = "handler.handler"
  filename         = data.archive_file.downloads_handler.output_path
  source_code_hash = data.archive_file.downloads_handler.output_base64sha256
  timeout          = 10
  memory_size      = 128

  environment {
    variables = {
      DOWNLOADS_BUCKET = aws_s3_bucket.downloads.bucket
      PRESIGN_SECONDS  = "300"
      BLOCKED_APPS     = "server,midi-player"
    }
  }

  depends_on = [aws_cloudwatch_log_group.downloads, aws_iam_role_policy.downloads]
}

resource "aws_lambda_function_url" "downloads" {
  function_name      = aws_lambda_function.downloads.function_name
  authorization_type = "NONE"

  # Downloads are plain navigation; CORS is only for the picker's status fetch.
  cors {
    allow_origins = local.downloads_allowed_origins
    allow_methods = ["GET"]
    max_age       = 3600
  }
}

resource "aws_lambda_permission" "downloads_url" {
  statement_id           = "AllowPublicFunctionUrl"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.downloads.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "downloads_invoke" {
  statement_id             = "AllowPublicInvokeViaFunctionUrl"
  action                   = "lambda:InvokeFunction"
  function_name            = aws_lambda_function.downloads.function_name
  principal                = "*"
  invoked_via_function_url = true
}
