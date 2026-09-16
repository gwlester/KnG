# To Do List

## Create Terraform for AWS Components

**Status: code written and `terraform validate`-clean (2026-09-14); not yet
applied.** Written under `terraform/` (`versions.tf`, `providers.tf`,
`variables.tf`, `oidc.tf`, `s3.tf`, `acm.tf`, `cloudfront.tf`, `outputs.tf`,
`README.md`). Covers: GitHub OIDC provider + a scoped deploy role,
private S3 bucket + CloudFront (OAC) + ACM cert for all four domains. The
component choices and domain/DNS decisions it implements are recorded in
`Prompts/Done.md`'s "Suggest AWS Components" entry.

**Not moving this to Done.md yet** — applying real AWS infrastructure
(and the IAM trust policy it creates) needs your own AWS credentials and a
deliberate decision, not something to run unattended. The one-time
bootstrap sequence (create the cert, add its validation CNAMEs at GoDaddy,
full apply, then add the `www` CNAMEs + apex forwarding at GoDaddy, then
set the four GitHub repo variables) is written out step by step in
`Prompts/AWS_Deployment.md`. Move this to Done.md once you've run it and
the site is actually live behind CloudFront.
