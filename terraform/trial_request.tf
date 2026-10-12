# License File: issues a 90-day trial reference + activation key. Public
# (Function URL, no auth) -- email + one-trial-per-email-and-kind is the
# whole anti-abuse check, done inside the handler
# (src/trial_request/handler.py). See license_signing.tf for the Lambda
# that actually mints/signs the resulting license.

data "archive_file" "trial_request_handler" {
  type        = "zip"
  source_dir  = "${path.module}/../src/trial_request"
  output_path = "${path.module}/trial_request.zip"
  excludes    = ["__pycache__"]
}

resource "aws_cloudwatch_log_group" "trial_request" {
  name              = "/aws/lambda/kng-trial-request"
  retention_in_days = 30
}

resource "aws_iam_role" "trial_request" {
  name               = "kng-trial-request"
  assume_role_policy = data.aws_iam_policy_document.license_signing_assume.json
}

data "aws_iam_policy_document" "trial_request" {
  statement {
    sid       = "WriteLogs"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.trial_request.arn}:*"]
  }

  statement {
    sid       = "ReadWriteTrialTables"
    effect    = "Allow"
    actions   = ["dynamodb:GetItem", "dynamodb:PutItem"]
    resources = [aws_dynamodb_table.license_issuance.arn, aws_dynamodb_table.trial_by_email.arn]
  }
}

resource "aws_iam_role_policy" "trial_request" {
  name   = "kng-trial-request"
  role   = aws_iam_role.trial_request.id
  policy = data.aws_iam_policy_document.trial_request.json
}

resource "aws_lambda_function" "trial_request" {
  function_name    = "kng-trial-request"
  role             = aws_iam_role.trial_request.arn
  runtime          = "python3.12"
  handler          = "handler.handler"
  filename         = data.archive_file.trial_request_handler.output_path
  source_code_hash = data.archive_file.trial_request_handler.output_base64sha256
  timeout          = 10
  memory_size      = 128

  environment {
    variables = {
      LICENSE_ISSUANCE_TABLE = aws_dynamodb_table.license_issuance.name
      TRIAL_BY_EMAIL_TABLE   = aws_dynamodb_table.trial_by_email.name
    }
  }

  depends_on = [aws_cloudwatch_log_group.trial_request, aws_iam_role_policy.trial_request]
}

resource "aws_lambda_function_url" "trial_request" {
  function_name      = aws_lambda_function.trial_request.function_name
  authorization_type = "NONE"

  cors {
    allow_origins = local.downloads_allowed_origins
    allow_methods = ["POST"]
    allow_headers = ["content-type"]
    max_age       = 3600
  }
}

resource "aws_lambda_permission" "trial_request_url" {
  statement_id           = "AllowPublicFunctionUrl"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.trial_request.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "trial_request_invoke" {
  statement_id             = "AllowPublicInvokeViaFunctionUrl"
  action                   = "lambda:InvokeFunction"
  function_name            = aws_lambda_function.trial_request.function_name
  principal                = "*"
  invoked_via_function_url = true
}
