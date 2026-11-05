# GitHub Actions OIDC trust, and the role deploy-to-aws.yml assumes to run
# `terraform apply` and sync the site to S3. See terraform/README.md for the
# one-time bootstrap order -- this role has to exist before CI can use it.

resource "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 1 : 0

  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

locals {
  github_oidc_provider_arn = var.create_github_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : var.github_oidc_provider_arn
}

data "aws_iam_policy_document" "github_actions_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.github_oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # Allows any branch/tag/ref in this repo to assume the role. Tighten to
    # "repo:${var.github_repository}:ref:refs/heads/main" if deploys should
    # only ever come from main.
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "repo:${var.github_repository}:*",
        "${var.github_oidc_immutable_subject_prefix}:*",
      ]
    }
  }
}

resource "aws_iam_role" "github_actions_deploy" {
  name               = "kng-github-actions-deploy"
  assume_role_policy = data.aws_iam_policy_document.github_actions_assume_role.json
}

# Scoped to exactly what deploy-to-aws.yml's `terraform apply` and S3 sync
# steps need to manage. S3/ACM/CloudFront actions are broad ("*" resource)
# for simplicity in this single-purpose AWS account -- most of those
# services don't support fine-grained resource ARNs on the create/list
# actions this role needs anyway. IAM permissions are scoped tightly to this
# specific role and OIDC provider so the role can never touch other IAM
# resources in the account.
data "aws_iam_policy_document" "github_actions_deploy" {
  statement {
    sid    = "SiteBucket"
    effect = "Allow"
    actions = [
      "s3:Get*",
      "s3:List*",
      "s3:GetBucketPolicy",
      "s3:PutBucketPolicy",
      "s3:GetBucketOwnershipControls",
      "s3:PutBucketOwnershipControls",
      "s3:GetBucketPublicAccessBlock",
      "s3:PutBucketPublicAccessBlock",
      "s3:GetBucketTagging",
      "s3:PutBucketTagging",
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = [
      "arn:aws:s3:::${var.bucket_name}",
      "arn:aws:s3:::${var.bucket_name}/*",
    ]
  }

  statement {
    sid       = "TerraformStateBucket"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::kng-consulting-tfstate-734677164811"]
  }

  statement {
    sid       = "TerraformStateObject"
    effect    = "Allow"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["arn:aws:s3:::kng-consulting-tfstate-734677164811/kng-site/*"]
  }

  statement {
    sid       = "ContactFormLambdaAndSes"
    effect    = "Allow"
    actions   = ["lambda:*", "ses:*", "logs:*"]
    resources = ["*"]
  }

  statement {
    sid    = "ContactFormRole"
    effect = "Allow"
    actions = [
      "iam:CreateRole", "iam:DeleteRole", "iam:GetRole", "iam:GetRolePolicy",
      "iam:PutRolePolicy", "iam:DeleteRolePolicy", "iam:TagRole", "iam:UntagRole",
      "iam:UpdateAssumeRolePolicy", "iam:PassRole", "iam:List*",
    ]
    resources = [aws_iam_role.contact.arn, aws_iam_role.downloads.arn]
  }

  # License File (license_signing.tf/trial_request.tf): same pattern as
  # ContactFormRole above, for the three new execution roles.
  statement {
    sid    = "LicenseFileRoles"
    effect = "Allow"
    actions = [
      "iam:CreateRole", "iam:DeleteRole", "iam:GetRole", "iam:GetRolePolicy",
      "iam:PutRolePolicy", "iam:DeleteRolePolicy", "iam:TagRole", "iam:UntagRole",
      "iam:UpdateAssumeRolePolicy", "iam:PassRole", "iam:List*",
    ]
    resources = [
      aws_iam_role.license_activate.arn,
      aws_iam_role.license_generate_test.arn,
      aws_iam_role.trial_request.arn,
    ]
  }

  # License File: the two new DynamoDB tables -- same actions as
  # DownloadsRateLimitTable below, for the same reason (full lifecycle
  # management plus everything the provider's own read checks on every
  # plan/apply even though these tables use none of it).
  statement {
    sid    = "LicenseFileTables"
    effect = "Allow"
    actions = [
      "dynamodb:CreateTable", "dynamodb:DeleteTable", "dynamodb:DescribeTable",
      "dynamodb:UpdateTable", "dynamodb:DescribeTimeToLive", "dynamodb:UpdateTimeToLive",
      "dynamodb:TagResource", "dynamodb:UntagResource", "dynamodb:ListTagsOfResource",
      "dynamodb:DescribeContinuousBackups", "dynamodb:UpdateContinuousBackups",
      "dynamodb:DescribeKinesisStreamingDestination",
    ]
    resources = [
      aws_dynamodb_table.license_issuance.arn, aws_dynamodb_table.trial_by_email.arn,
      aws_dynamodb_table.beta_testers.arn,
    ]
  }

  # Order fulfillment (order_fulfillment.tf): same three patterns above,
  # for its own execution role. Its secrets and the license signing key
  # are SSM parameters created out of band, so CI needs no SSM or Secrets
  # Manager permissions.
  statement {
    sid    = "OrderFulfillmentRole"
    effect = "Allow"
    actions = [
      "iam:CreateRole", "iam:DeleteRole", "iam:GetRole", "iam:GetRolePolicy",
      "iam:PutRolePolicy", "iam:DeleteRolePolicy", "iam:TagRole", "iam:UntagRole",
      "iam:UpdateAssumeRolePolicy", "iam:PassRole", "iam:List*",
    ]
    resources = [aws_iam_role.order_fulfillment.arn]
  }

  # FindCache log uploads (findcache_logs.tf): the logs bucket and the
  # Lambda's execution role. The Lambda itself and its log group are covered
  # by the broad lambda:*/logs:* statement above.
  statement {
    sid    = "FindCacheLogsBucket"
    effect = "Allow"
    actions = [
      "s3:CreateBucket", "s3:DeleteBucket", "s3:Get*", "s3:List*",
      "s3:PutBucketPublicAccessBlock", "s3:PutEncryptionConfiguration",
      "s3:PutLifecycleConfiguration", "s3:PutBucketTagging",
    ]
    resources = [aws_s3_bucket.findcache_logs.arn]
  }

  statement {
    sid    = "FindCacheLogRole"
    effect = "Allow"
    actions = [
      "iam:CreateRole", "iam:DeleteRole", "iam:GetRole", "iam:GetRolePolicy",
      "iam:PutRolePolicy", "iam:DeleteRolePolicy", "iam:TagRole", "iam:UntagRole",
      "iam:UpdateAssumeRolePolicy", "iam:PassRole", "iam:List*",
    ]
    resources = [aws_iam_role.findcache_log.arn, aws_iam_role.findcache_digest.arn]
  }

  # Daily digest schedule (findcache_logs.tf): the EventBridge rule and its
  # target, limited to that one rule.
  statement {
    sid    = "FindCacheDigestSchedule"
    effect = "Allow"
    actions = [
      "events:PutRule", "events:DeleteRule", "events:DescribeRule", "events:EnableRule",
      "events:DisableRule", "events:PutTargets", "events:RemoveTargets", "events:ListTargetsByRule",
      "events:ListTagsForResource", "events:TagResource", "events:UntagResource",
    ]
    resources = [aws_cloudwatch_event_rule.findcache_digest.arn]
  }

  statement {
    sid       = "DownloadsBucket"
    effect    = "Allow"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.downloads.arn, "${aws_s3_bucket.downloads.arn}/*"]
  }

  # Kept for one apply so `terraform apply` can delete the retired
  # password-attempt rate-limit table (a literal ARN, since the resource is
  # gone); remove this statement afterwards.
  statement {
    sid    = "DownloadsRateLimitTable"
    effect = "Allow"
    actions = [
      "dynamodb:CreateTable", "dynamodb:DeleteTable", "dynamodb:DescribeTable",
      "dynamodb:UpdateTable", "dynamodb:DescribeTimeToLive", "dynamodb:UpdateTimeToLive",
      "dynamodb:TagResource", "dynamodb:UntagResource", "dynamodb:ListTagsOfResource",
      # The provider's read also checks PITR and Kinesis streaming-destination
      # status on every plan/apply, even though this table uses neither.
      "dynamodb:DescribeContinuousBackups", "dynamodb:UpdateContinuousBackups",
      "dynamodb:DescribeKinesisStreamingDestination",
    ]
    resources = ["arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/kng-downloads-ratelimit"]
  }

  statement {
    sid       = "MediaBucket"
    effect    = "Allow"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.media.arn, "${aws_s3_bucket.media.arn}/*"]
  }

  statement {
    sid       = "Acm"
    effect    = "Allow"
    actions   = ["acm:*"]
    resources = ["*"]
  }

  statement {
    sid       = "CloudFront"
    effect    = "Allow"
    actions   = ["cloudfront:*"]
    resources = ["*"]
  }

  statement {
    sid    = "SelfManageOidcAndRole"
    effect = "Allow"
    actions = [
      "iam:Get*",
      "iam:List*",
      "iam:GetRole",
      "iam:GetRolePolicy",
      "iam:PutRolePolicy",
      "iam:TagRole",
      "iam:GetOpenIDConnectProvider",
      "iam:TagOpenIDConnectProvider",
      "iam:UpdateOpenIDConnectProviderThumbprint",
    ]
    resources = [
      aws_iam_role.github_actions_deploy.arn,
      local.github_oidc_provider_arn,
    ]
  }
}

resource "aws_iam_role_policy" "github_actions_deploy" {
  name   = "kng-site-deploy"
  role   = aws_iam_role.github_actions_deploy.id
  policy = data.aws_iam_policy_document.github_actions_deploy.json
}
