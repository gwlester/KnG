# Terraform

Manages the AWS side of the KnG Consulting site: a private S3 bucket behind
CloudFront (Origin Access Control, no public bucket), an ACM certificate
covering `kng-consulting.com`, `www.kng-consulting.com`,
`kng-consulting.net`, and `www.kng-consulting.net`, and the IAM role
`deploy-to-aws.yml` assumes via GitHub OIDC.

DNS for both domains stays at GoDaddy (not Route53), so validation and the
final CNAMEs can't be fully automated -- see the bootstrap steps below.

## One-time bootstrap (run locally, not from CI)

You need local AWS credentials with roughly administrator access for this
first run -- after it, CI can keep everything in sync using the role this
creates.

1. `cd terraform && terraform init`
2. If this AWS account **already has** a GitHub Actions OIDC provider (e.g.
   from another project), set `create_github_oidc_provider = false` and
   `github_oidc_provider_arn = "<existing arn>"` in a `terraform.tfvars`
   file before continuing. Otherwise the defaults are fine.
3. Request the certificate first, without waiting on CloudFront:
   ```
   terraform apply -target=aws_acm_certificate.site
   ```
4. Get the validation records and add them at GoDaddy as CNAME records:
   ```
   terraform output -json dns_records_to_add_at_godaddy
   ```
   (Before the full apply, this only shows the ACM validation records --
   the `www` CNAMEs appear after step 5, once the CloudFront distribution
   exists.) Wait for DNS to propagate (usually minutes, can take longer).
5. Run the full apply -- this validates the certificate (now that the DNS
   records resolve), then creates the OIDC provider/role, S3 bucket, and
   CloudFront distribution:
   ```
   terraform apply
   ```
6. Add the remaining DNS records at GoDaddy:
   - `terraform output -json dns_records_to_add_at_godaddy` now also lists
     `www.kng-consulting.com` and `www.kng-consulting.net` as CNAMEs
     pointing at the CloudFront domain.
   - For the two apex domains (`kng-consulting.com`, `kng-consulting.net`),
     GoDaddy can't CNAME the zone root -- use GoDaddy's domain forwarding
     to redirect each apex to its `www` counterpart instead.
7. Set these as GitHub repository variables (Settings -> Secrets and
   variables -> Actions -> Variables) so `deploy-to-aws.yml` can use them:
   - `AWS_REGION` = `us-east-1` (or whatever `var.aws_region` is)
   - `AWS_DEPLOY_ROLE_ARN` = `terraform output github_actions_deploy_role_arn`
   - `S3_BUCKET_NAME` = `terraform output s3_bucket_name`
   - `CLOUDFRONT_DISTRIBUTION_ID` = `terraform output cloudfront_distribution_id`
   - `TERRAFORM_WORKING_DIRECTORY` = `terraform`

From here on, pushes to `main` run `terraform apply` in CI (using the role
created above) before syncing `www/` to S3 and invalidating CloudFront --
no more manual `terraform apply` needed unless GoDaddy-side DNS records
need to change.

## Notes

- S3 bucket names are globally unique across *all* AWS accounts -- if
  `kng-consulting-site` (the `bucket_name` default) is taken, override it.
- ACM/CloudFront permissions in the deploy role are broad (`acm:*`,
  `cloudfront:*`) rather than resource-scoped, since neither service
  supports meaningful resource-level restriction on the create/list actions
  this role needs. Acceptable here since this AWS account is single-purpose
  for this site; tighten if that stops being true.
