# Terraform

Manages the AWS side of the KnG Consulting site: a private S3 bucket behind
CloudFront (Origin Access Control, no public bucket), an ACM certificate
covering `kng-consulting.com`, `www.kng-consulting.com`,
`kng-consulting.net`, and `www.kng-consulting.net`, and the IAM role
`deploy-to-aws.yml` assumes via GitHub OIDC.

DNS for both domains stays at GoDaddy (not Route53), so validation and the
final CNAMEs can't be fully automated.

## One-time bootstrap

See [`Prompts/AWS_Deployment.md`](../Prompts/AWS_Deployment.md) for the
step-by-step checklist (what to get from AWS/GoDaddy and exactly where it
goes). Run it locally, not from CI -- after it, CI keeps everything in sync
using the role it creates.

## Notes

- S3 bucket names are globally unique across *all* AWS accounts -- if
  `kng-consulting-site` (the `bucket_name` default) is taken, override it.
- ACM/CloudFront permissions in the deploy role are broad (`acm:*`,
  `cloudfront:*`) rather than resource-scoped, since neither service
  supports meaningful resource-level restriction on the create/list actions
  this role needs. Acceptable here since this AWS account is single-purpose
  for this site; tighten if that stops being true.
