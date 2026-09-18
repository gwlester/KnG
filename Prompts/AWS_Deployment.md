# AWS Deployment Bootstrap

One-time setup checklist for standing up the AWS infrastructure in
`terraform/` and wiring it to `deploy-to-aws.yml`. Run every command from
`terraform/` on a machine with AWS CLI credentials for the target account.

## 0. Before you start

- **AWS credentials.** Get: browser-based temporary credentials via
  `aws login` (AWS CLI v2.36+) -- opens a browser, you approve against
  your AWS Console session, and the CLI caches temporary credentials good
  for 12h (renewable up to 90 days without re-authenticating). Preferred
  over a static IAM access key: nothing long-lived ever lands in a config
  file. Needs roughly administrator access (IAM roles/OIDC, S3, ACM,
  CloudFront) on the account you log into -- this is a one-time
  requirement, CI doesn't need it (it uses the OIDC role Terraform
  creates). Put it: just run `aws login`; Terraform's AWS provider picks
  up the cached credentials automatically. If more than one AWS account is
  available (e.g. a different account than VirtualChurchMusician's),
  confirm with `aws sts get-caller-identity` that you logged into the
  right one before continuing. (An IAM access key + `aws configure` still
  works if `aws login` isn't available in your CLI version.)
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

## 0b. Create the Terraform state bucket (once, before `terraform init`)

State lives in S3 so CI's `terraform apply` shares it with local runs.
Terraform can't manage the bucket that holds its own state, so create it
by hand:
```
B=kng-consulting-tfstate-<account-id>
aws s3api create-bucket --bucket $B --region us-east-1
aws s3api put-public-access-block --bucket $B --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-versioning --bucket $B --versioning-configuration Status=Enabled
aws s3api put-bucket-encryption --bucket $B --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
```
The name must match `backend "s3"` in `terraform/versions.tf`. Locking uses
S3's native lockfile (Terraform >= 1.10), no DynamoDB table. If you already
have a local `terraform.tfstate`, move it with `terraform init -migrate-state`.

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
| `preview_cloudfront_distribution_id` | GitHub repo variable `PREVIEW_CLOUDFRONT_DISTRIBUTION_ID` |
| `cloudfront_domain_name` | GoDaddy CNAME target, step 4 below (not a GitHub variable) |
| `preview_cloudfront_domain_name` | GoDaddy CNAME target, step 4 below (not a GitHub variable) |

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
gh variable set PREVIEW_CLOUDFRONT_DISTRIBUTION_ID --body "<value>"
gh variable set TERRAFORM_WORKING_DIRECTORY --body "terraform"
```

## 4. Remaining DNS at GoDaddy

Get:
```
terraform output -json dns_records_to_add_at_godaddy
```
Now also lists `www.kng-consulting.com`, `www.kng-consulting.net`, and
`preview.kng-consulting.com` as CNAMEs.

Put them: same Add Record steps as step 2, Value = each record's own
`value` field (the preview entry points at `preview_cloudfront_domain_name`,
not the same CloudFront domain as the other two -- it's a separate
distribution, see `terraform/cloudfront_preview.tf`).

For the two apex domains (`kng-consulting.com`, `kng-consulting.net` --
GoDaddy can't CNAME the zone root): that domain -> Forwarding -> Domain ->
forward to `https://www.<same domain>`.

## 5. Contact form (SES + Lambda)

Handler: `src/contact_handler/handler.py`. Infra: `terraform/contact.tf`.
The form posts `{FormatVersion: 1, name, email, message, website}` (the
`website` field is a spam honeypot) to a Lambda Function URL, which emails
`inquiries@kng-consulting.com` through SES.

Order matters -- the CI deploy role must be allowed to manage the new
resources before CI ever applies them (see the `ContactFormLambdaAndSes` and
`ContactFormRole` statements in `terraform/oidc.tf`).

Do:
```
terraform apply
terraform output -json dns_records_to_add_at_godaddy
terraform output contact_function_url
```

Then:

- GoDaddy: add the three `SES DKIM` CNAMEs (same Add Record steps as step 2).
  SES marks the domain verified once they resolve.
- Mailbox: SES emails a confirmation link to `inquiries@kng-consulting.com`;
  click it. While the SES account is in the sandbox, only verified
  recipients receive mail, so this is required. Sandbox limits (200
  messages/day) are plenty for a contact form.
- Endpoint: paste `contact_function_url` into `data-endpoint` in
  `www/contact.html`, commit, and push.

Smoke test: submit the form on the preview site and confirm the email
arrives with Reply-To set to the submitter.

## Done

From here on, pushes to `master` run `terraform apply` in CI (using the
role created above), upload `www/` to a new `releases/<sha>/` prefix, and
point the preview distribution at it automatically -- then wait at the
`production-switch` environment's approval gate. Approving promotes that
release to the live distribution and invalidates it; see
`Prompts/ToDo.md`'s "Blue-Green Deployments" item for the full mechanics,
and `.github/workflows/rollback.yml` for rolling back. No more manual
`terraform apply` needed unless GoDaddy-side DNS records need to change.
