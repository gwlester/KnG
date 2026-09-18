variable "aws_region" {
  description = "AWS region for the S3 bucket and other regional resources."
  type        = string
  default     = "us-east-1"
}

variable "bucket_name" {
  description = "S3 bucket name for the site. Must be globally unique across all AWS accounts -- change this if it's taken."
  type        = string
  default     = "kng-consulting-site"
}

variable "live_domain_names" {
  description = "All domains/subdomains the live site should answer to. The first entry is used as the ACM certificate's primary domain_name; all entries are aliases on the live CloudFront distribution."
  type        = list(string)
  default = [
    "kng-consulting.com",
    "www.kng-consulting.com",
    "kng-consulting.net",
    "www.kng-consulting.net",
  ]
}

variable "preview_domain_name" {
  description = <<-EOT
    Subdomain for the preview CloudFront distribution -- always shows
    whatever build-and-upload most recently uploaded, ahead of switch-live
    promoting it, for smoke-testing the real deployed output. A SAN on the
    same ACM certificate as live_domain_names, but only aliased on the
    preview distribution, never the live one.
  EOT
  type        = string
  default     = "preview.kng-consulting.com"
}

variable "cloudfront_price_class" {
  description = "CloudFront price class. PriceClass_100 = North America + Europe only (cheapest)."
  type        = string
  default     = "PriceClass_100"
}

variable "github_repository" {
  description = "GitHub \"org/repo\" allowed to assume the deploy role via OIDC."
  type        = string
  default     = "gwlester/KnG"
}

variable "github_oidc_immutable_subject_prefix" {
  description = <<-EOT
    The repository's immutable OIDC subject prefix ("repo:<owner>@<id>/<repo>@<id>").
    This repo has use_immutable_subject enabled, so tokens carry this prefix
    instead of "repo:<owner>/<repo>". Find it with:
    gh api repos/<owner>/<repo>/actions/oidc/customization/sub
  EOT
  type        = string
  default     = "repo:gwlester@1377560/KnG@1369022652"
}

variable "create_github_oidc_provider" {
  description = <<-EOT
    Whether to create the GitHub Actions OIDC provider in this AWS account.
    An AWS account can only have ONE OIDC provider per URL -- if this account
    already has one (e.g. from another project such as
    VirtualChurchMusician), set this to false and supply
    github_oidc_provider_arn instead.
  EOT
  type        = bool
  default     = true
}

variable "github_oidc_provider_arn" {
  description = "ARN of an existing GitHub Actions OIDC provider. Only used when create_github_oidc_provider is false."
  type        = string
  default     = ""
}
