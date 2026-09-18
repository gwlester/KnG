# Contact form: browser -> Lambda Function URL -> SES -> inquiries mailbox.
# Handler source: src/contact_handler/handler.py.

locals {
  contact_domain = element(split("@", var.contact_sender), 1)
  contact_allowed_origins = [
    for d in concat(var.live_domain_names, [var.preview_domain_name]) : "https://${d}"
  ]
}

# Easy DKIM: the domain is verified once the three DKIM CNAMEs (see the
# dns_records_to_add_at_godaddy output) resolve.
resource "aws_sesv2_email_identity" "contact_domain" {
  email_identity = local.contact_domain
}

# Needed while the SES account is in the sandbox, which only delivers to
# verified addresses. SES emails a confirmation link to this address on
# creation. Harmless to keep after leaving the sandbox.
resource "aws_sesv2_email_identity" "contact_recipient" {
  email_identity = var.contact_recipient
}

data "archive_file" "contact_handler" {
  type        = "zip"
  source_dir  = "${path.module}/../src/contact_handler"
  output_path = "${path.module}/contact_handler.zip"
  excludes    = ["__pycache__"]
}

resource "aws_cloudwatch_log_group" "contact" {
  name              = "/aws/lambda/kng-contact-form"
  retention_in_days = 30
}

data "aws_iam_policy_document" "contact_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "contact" {
  name               = "kng-contact-form"
  assume_role_policy = data.aws_iam_policy_document.contact_assume.json
}

data "aws_iam_policy_document" "contact" {
  statement {
    sid       = "SendFromContactDomain"
    effect    = "Allow"
    actions   = ["ses:SendEmail"]
    resources = [aws_sesv2_email_identity.contact_domain.arn, aws_sesv2_email_identity.contact_recipient.arn]
  }

  statement {
    sid       = "WriteLogs"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.contact.arn}:*"]
  }
}

resource "aws_iam_role_policy" "contact" {
  name   = "kng-contact-form"
  role   = aws_iam_role.contact.id
  policy = data.aws_iam_policy_document.contact.json
}

resource "aws_lambda_function" "contact" {
  function_name    = "kng-contact-form"
  role             = aws_iam_role.contact.arn
  runtime          = "python3.12"
  handler          = "handler.handler"
  filename         = data.archive_file.contact_handler.output_path
  source_code_hash = data.archive_file.contact_handler.output_base64sha256
  timeout          = 10
  memory_size      = 128

  environment {
    variables = {
      SES_SENDER      = var.contact_sender
      SES_RECIPIENT   = var.contact_recipient
      ALLOWED_ORIGINS = join(",", local.contact_allowed_origins)
    }
  }

  depends_on = [aws_cloudwatch_log_group.contact, aws_iam_role_policy.contact]
}

resource "aws_lambda_function_url" "contact" {
  function_name      = aws_lambda_function.contact.function_name
  authorization_type = "NONE"

  cors {
    allow_origins = local.contact_allowed_origins
    allow_methods = ["POST"]
    allow_headers = ["content-type"]
    max_age       = 3600
  }
}
