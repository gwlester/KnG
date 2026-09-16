# AWS Deployment Bootstrap

One-time setup checklist for standing up the AWS infrastructure in
`terraform/` and wiring it to `deploy-to-aws.yml`. Run every command from
`terraform/` on a machine with AWS CLI credentials for the target account.

## 0. Before you start

- **AWS credentials.** Get: an access key (AWS Console -> IAM -> your user
  -> Security credentials -> Create access key) or an SSO login, with
  roughly administrator access (IAM roles/OIDC, S3, ACM, CloudFront) --
  this is a one-time requirement, CI doesn't need it. Put it: locally, via
  `aws configure` (or `aws sso login`) so Terraform's AWS provider can find
  it. If more than one AWS account is available (e.g. a different account
  than VirtualChurchMusician's), confirm the credentials point at the
  right one before continuing.
- **GoDaddy account access.** No value to record -- just be logged in
  when you reach the DNS steps below.
- **Name collisions with the pre-existing infrastructure -- already
  checked, clear.** The domains are currently live on other AWS
  infrastructure in this **same** AWS account (see "Pre-existing
  infrastructure" in `Prompts/ToDo.md`'s "Blue-Green Deployments" item for
  the full bucket inventory). Confirmed 2026-09-16: no existing S3 bucket
  named `kng-consulting-site` and no existing IAM role named
  `kng-github-actions-deploy` -- `terraform/variables.tf`/`oidc.tf`'s
  defaults are safe to apply as-is, nothing to override.

## 1. Check for an existing GitHub OIDC provider

Get:
```
aws iam list-open-id-connect-providers
```
Look for an ARN containing `token.actions.githubusercontent.com` (an AWS
account can only have one).

Put it: if found, create `terraform/terraform.tfvars` (already gitignored)
with:
```
create_github_oidc_provider = false
github_oidc_provider_arn    = "<arn from above>"
```
If none found, skip this file -- Terraform creates one.

## 2. Init and request the certificate

```
terraform init
terraform apply -target=aws_acm_certificate.site
```

Get the validation records:
```
terraform output -json dns_records_to_add_at_godaddy
```

Put them at GoDaddy -- for each entry: My Products -> DNS (on the domain
the record's `name` ends with) -> Add Record ->

- Type: the record's `type` (CNAME)
- Name: the record's `name` with the trailing `.kng-consulting.com.` /
  `.kng-consulting.net.` stripped off -- GoDaddy adds the domain itself.
  E.g. `_1a2b3c4d.kng-consulting.com.` -> enter `_1a2b3c4d`.
- Value: the record's `value`, pasted exactly as shown (trailing dot
  included; drop it only if GoDaddy's form rejects it)
- TTL: default (1 hour) is fine

Wait for DNS to propagate (usually minutes, can take longer) before
continuing.

## 3. Full apply

```
terraform apply
```
Creates the OIDC provider/role (if needed), S3 bucket, and CloudFront
distribution; validates the certificate against the records from step 2.

Get:
```
terraform output
```

| Output | Put it |
| --- | --- |
| `github_actions_deploy_role_arn` | GitHub repo variable `AWS_DEPLOY_ROLE_ARN` |
| `s3_bucket_name` | GitHub repo variable `S3_BUCKET_NAME` |
| `cloudfront_distribution_id` | GitHub repo variable `CLOUDFRONT_DISTRIBUTION_ID` |
| `cloudfront_domain_name` | GoDaddy CNAME target, step 4 below (not a GitHub variable) |

Also set GitHub repo variable `AWS_REGION` = `us-east-1` (the Terraform
default; only different if `var.aws_region` was changed) and
`TERRAFORM_WORKING_DIRECTORY` = `terraform`.

Put GitHub repo variables at: repo -> Settings -> Secrets and variables ->
Actions -> Variables tab -> New repository variable. Or script it (`gh`
CLI):
```
gh variable set AWS_REGION --body "us-east-1"
gh variable set AWS_DEPLOY_ROLE_ARN --body "<value>"
gh variable set S3_BUCKET_NAME --body "<value>"
gh variable set CLOUDFRONT_DISTRIBUTION_ID --body "<value>"
gh variable set TERRAFORM_WORKING_DIRECTORY --body "terraform"
```

## 4. Remaining DNS at GoDaddy

Get:
```
terraform output -json dns_records_to_add_at_godaddy
```
Now also lists `www.kng-consulting.com` and `www.kng-consulting.net` as
CNAMEs.

Put them: same Add Record steps as step 2, Value = `cloudfront_domain_name`
from the table above.

For the two apex domains (`kng-consulting.com`, `kng-consulting.net` --
GoDaddy can't CNAME the zone root): that domain -> Forwarding -> Domain ->
forward to `https://www.<same domain>`.

## Done

From here on, pushes to `main` run `terraform apply` in CI (using the role
created above) before syncing `www/` to S3 and invalidating CloudFront --
no more manual `terraform apply` needed unless GoDaddy-side DNS records
need to change.
