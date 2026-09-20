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

  statement {
    sid       = "DownloadsBucket"
    effect    = "Allow"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.downloads.arn, "${aws_s3_bucket.downloads.arn}/*"]
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
