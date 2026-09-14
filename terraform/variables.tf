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

variable "domain_names" {
  description = "All domains/subdomains the site should answer to. The first entry is used as the primary CloudFront alias."
  type        = list(string)
  default = [
    "kng-consulting.com",
    "www.kng-consulting.com",
    "kng-consulting.net",
    "www.kng-consulting.net",
  ]
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
