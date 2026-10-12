# FastSpring order fulfillment: the order.completed webhook receiver,
# plus the order-verification route picker.js calls after the Popup
# Checkout closes. See src/order_fulfillment/handler.py's own docstring
# and Prompts/FastSpring_implementation.md section 4.
#
# Writes into the same kng-license-issuance table license_signing.tf's
# Lambda already reads from -- no separate "orders" table.

resource "aws_cloudwatch_log_group" "order_fulfillment" {
  name              = "/aws/lambda/kng-order-fulfillment"
  retention_in_days = 30
}

data "archive_file" "order_fulfillment_handler" {
  type        = "zip"
  source_dir  = "${path.module}/../src/order_fulfillment"
  output_path = "${path.module}/order_fulfillment.zip"
  excludes    = ["__pycache__"]
}

# Container only -- FastSpring API credentials and the webhook HMAC
# secret are both set out of band (aws secretsmanager put-secret-value),
# never through Terraform or committed to this repo. The webhook secret
# in particular doesn't exist until the webhook itself is created in
# FastSpring's dashboard (it needs this Lambda's URL first), so this
# starts empty and the webhook fails signature verification (closed,
# safely) until it's populated.
resource "aws_secretsmanager_secret" "fastspring_api_credentials" {
  name                    = "kng/fastspring-api-credentials"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret" "fastspring_webhook_secret" {
  name                    = "kng/fastspring-webhook-secret"
  recovery_window_in_days = 7
}

resource "aws_iam_role" "order_fulfillment" {
  name               = "kng-order-fulfillment"
  assume_role_policy = data.aws_iam_policy_document.license_signing_assume.json
}

data "aws_iam_policy_document" "order_fulfillment" {
  statement {
    sid       = "WriteLogs"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.order_fulfillment.arn}:*"]
  }

  statement {
    sid       = "ReadWriteIssuance"
    effect    = "Allow"
    actions   = ["dynamodb:GetItem", "dynamodb:PutItem"]
    resources = [aws_dynamodb_table.license_issuance.arn]
  }

  statement {
    sid       = "ReadSecrets"
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.fastspring_api_credentials.arn, aws_secretsmanager_secret.fastspring_webhook_secret.arn]
  }
}

resource "aws_iam_role_policy" "order_fulfillment" {
  name   = "kng-order-fulfillment"
  role   = aws_iam_role.order_fulfillment.id
  policy = data.aws_iam_policy_document.order_fulfillment.json
}

resource "aws_lambda_function" "order_fulfillment" {
  function_name    = "kng-order-fulfillment"
  role             = aws_iam_role.order_fulfillment.arn
  runtime          = "python3.12"
  handler          = "handler.handler"
  filename         = data.archive_file.order_fulfillment_handler.output_path
  source_code_hash = data.archive_file.order_fulfillment_handler.output_base64sha256
  timeout          = 15
  memory_size      = 256

  environment {
    variables = {
      LICENSE_ISSUANCE_TABLE                = aws_dynamodb_table.license_issuance.name
      FASTSPRING_API_CREDENTIALS_SECRET_ARN = aws_secretsmanager_secret.fastspring_api_credentials.arn
      FASTSPRING_WEBHOOK_SECRET_ARN         = aws_secretsmanager_secret.fastspring_webhook_secret.arn
    }
  }

  depends_on = [aws_cloudwatch_log_group.order_fulfillment, aws_iam_role_policy.order_fulfillment]
}

resource "aws_lambda_function_url" "order_fulfillment" {
  function_name      = aws_lambda_function.order_fulfillment.function_name
  authorization_type = "NONE"

  cors {
    allow_origins = local.downloads_allowed_origins
    allow_methods = ["GET", "POST"]
    allow_headers = ["content-type", "x-fs-signature"]
    max_age       = 3600
  }
}

resource "aws_lambda_permission" "order_fulfillment_url" {
  statement_id           = "AllowPublicFunctionUrl"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.order_fulfillment.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "order_fulfillment_invoke" {
  statement_id             = "AllowPublicInvokeViaFunctionUrl"
  action                   = "lambda:InvokeFunction"
  function_name            = aws_lambda_function.order_fulfillment.function_name
  principal                = "*"
  invoked_via_function_url = true
}
