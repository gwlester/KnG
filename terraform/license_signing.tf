# License File: signing Lambda for Virtual Church Musician license
# activation. One source zip, two entry points sharing handler.py's own
# mint_and_sign core (src/license_signing/handler.py), deployed as two
# separate Lambda functions with very different exposure:
#   - license_activate: public (Function URL, no IAM auth) -- order/
#     short-key authenticated inside the handler itself.
#   - license_generate_test: no Function URL at all. Invoked directly via
#     IAM (aws lambda invoke), restricted to Gerald's own IAM user, for
#     the Virtual Church Musician repo's test-license CLI
#     (src/license_tools/generate_test_license.py).
# See Prompts/FastSpring_implementation.md section 4d and the Virtual
# Church Musician repo's Prompts/ToDo.md "License File" item for the
# full design.

resource "aws_dynamodb_table" "license_issuance" {
  name         = "kng-license-issuance"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "reference"

  attribute {
    name = "reference"
    type = "S"
  }
}

resource "aws_dynamodb_table" "trial_by_email" {
  name         = "kng-trial-by-email"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "email_kind"

  attribute {
    name = "email_kind"
    type = "S"
  }
}

# Approved beta testers for the Server/MIDI Player betas (decided
# 2026-10-12): Test Drive now requires the requesting email to be on this
# list -- it's no longer an open "anyone can request a 90-day trial" page.
# One row per approved email covers both products; maintained by hand via
# tools/sales_browser (read/write), read-only by trial_request.
resource "aws_dynamodb_table" "beta_testers" {
  name         = "kng-beta-testers"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "email"

  attribute {
    name = "email"
    type = "S"
  }
}

# The signing key lives in SSM Parameter Store as a standard-tier
# SecureString (free, encrypted with the AWS-managed aws/ssm key). The
# parameter is created and populated out of band (tools/migrate_secrets_to_ssm.sh
# or `aws ssm put-parameter --type SecureString`), never through Terraform
# state or this repo -- Terraform only references it by name for IAM.
locals {
  ssm_param_arn_prefix = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter"

  license_signing_key_param = "/kng/license-signing-private-key"
  license_signing_key_arn   = "${local.ssm_param_arn_prefix}${local.license_signing_key_param}"
}

data "aws_caller_identity" "current" {}

# Built by terraform/build_license_signing.sh before `terraform apply`
# (vendors cryptography's compiled wheel for the Lambda runtime -- not a
# pure-Python dependency boto3-style bundling can skip). See that
# script's own header for why this can't just be
# `source_dir = "../src/license_signing"` directly, the way every other
# Lambda here does.
data "archive_file" "license_signing_handler" {
  type        = "zip"
  source_dir  = "${path.module}/build/license_signing"
  output_path = "${path.module}/license_signing.zip"
  excludes    = ["__pycache__"]
}

resource "aws_cloudwatch_log_group" "license_activate" {
  name              = "/aws/lambda/kng-license-activate"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "license_generate_test" {
  name              = "/aws/lambda/kng-license-generate-test"
  retention_in_days = 30
}

data "aws_iam_policy_document" "license_signing_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "license_activate" {
  name               = "kng-license-activate"
  assume_role_policy = data.aws_iam_policy_document.license_signing_assume.json
}

resource "aws_iam_role" "license_generate_test" {
  name               = "kng-license-generate-test"
  assume_role_policy = data.aws_iam_policy_document.license_signing_assume.json
}

data "aws_iam_policy_document" "license_activate" {
  statement {
    sid       = "WriteLogs"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.license_activate.arn}:*"]
  }

  statement {
    sid       = "ReadSigningKey"
    effect    = "Allow"
    actions   = ["ssm:GetParameter"]
    resources = [local.license_signing_key_arn]
  }

  statement {
    sid       = "ReadWriteIssuance"
    effect    = "Allow"
    actions   = ["dynamodb:GetItem", "dynamodb:UpdateItem"]
    resources = [aws_dynamodb_table.license_issuance.arn]
  }
}

resource "aws_iam_role_policy" "license_activate" {
  name   = "kng-license-activate"
  role   = aws_iam_role.license_activate.id
  policy = data.aws_iam_policy_document.license_activate.json
}

data "aws_iam_policy_document" "license_generate_test" {
  statement {
    sid       = "WriteLogs"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.license_generate_test.arn}:*"]
  }

  statement {
    sid       = "ReadSigningKey"
    effect    = "Allow"
    actions   = ["ssm:GetParameter"]
    resources = [local.license_signing_key_arn]
  }
}

resource "aws_iam_role_policy" "license_generate_test" {
  name   = "kng-license-generate-test"
  role   = aws_iam_role.license_generate_test.id
  policy = data.aws_iam_policy_document.license_generate_test.json
}

resource "aws_lambda_function" "license_activate" {
  function_name    = "kng-license-activate"
  role             = aws_iam_role.license_activate.arn
  runtime          = "python3.12"
  handler          = "handler.activate"
  filename         = data.archive_file.license_signing_handler.output_path
  source_code_hash = data.archive_file.license_signing_handler.output_base64sha256
  timeout          = 15
  memory_size      = 256

  environment {
    variables = {
      LICENSE_ISSUANCE_TABLE                 = aws_dynamodb_table.license_issuance.name
      LICENSE_SIGNING_PRIVATE_KEY_PARAM = local.license_signing_key_param
    }
  }

  depends_on = [aws_cloudwatch_log_group.license_activate, aws_iam_role_policy.license_activate]
}

resource "aws_lambda_function" "license_generate_test" {
  function_name    = "kng-license-generate-test"
  role             = aws_iam_role.license_generate_test.arn
  runtime          = "python3.12"
  handler          = "handler.generate_test_license"
  filename         = data.archive_file.license_signing_handler.output_path
  source_code_hash = data.archive_file.license_signing_handler.output_base64sha256
  timeout          = 15
  memory_size      = 256

  environment {
    variables = {
      LICENSE_SIGNING_PRIVATE_KEY_PARAM = local.license_signing_key_param
    }
  }

  depends_on = [aws_cloudwatch_log_group.license_generate_test, aws_iam_role_policy.license_generate_test]
}

resource "aws_lambda_function_url" "license_activate" {
  function_name      = aws_lambda_function.license_activate.function_name
  authorization_type = "NONE"

  cors {
    allow_origins = local.downloads_allowed_origins
    allow_methods = ["POST"]
    allow_headers = ["content-type"]
    max_age       = 3600
  }
}

resource "aws_lambda_permission" "license_activate_url" {
  statement_id           = "AllowPublicFunctionUrl"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.license_activate.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "license_activate_invoke" {
  statement_id             = "AllowPublicInvokeViaFunctionUrl"
  action                   = "lambda:InvokeFunction"
  function_name            = aws_lambda_function.license_activate.function_name
  principal                = "*"
  invoked_via_function_url = true
}

# IAM-only -- no Function URL, no public invoke permission. Restricted to
# Gerald's own IAM user (the only human principal in this account besides
# Claude's own deploy user) so his test boxes' generate_test_license.py
# CLI can call it, and nothing else can.
resource "aws_lambda_permission" "license_generate_test_invoke" {
  statement_id  = "AllowGeraldDirectInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.license_generate_test.function_name
  principal     = "arn:aws:iam::734677164811:user/gwlester"
}
