# To Do List

## Blue-Green Deployments

**Status: scoped (2026-09-16), not designed/implemented.**

**Current state:** `deploy-to-aws.yml` runs `aws s3 sync www
s3://$S3_BUCKET_NAME --delete` directly against the one bucket CloudFront
serves from, then invalidates `/*`. A bad deploy is live the moment the
sync finishes, and "rollback" today means finding the last good commit and
re-running the whole pipeline (Terraform apply, blog build, sync,
invalidate) — there's no fast switch-back.

**What it will take:**

1. **Release-prefixed S3 layout.** Sync each deploy to
   `s3://$S3_BUCKET_NAME/releases/<git-sha>/` instead of the bucket root
   (`--delete` scoped to that one prefix only, never touching other
   releases) — this is what actually makes blue/green possible: the new
   release exists in S3 before anything user-facing changes.
2. **CloudFront Origin Path as the switch.** Point
   `aws_cloudfront_distribution.site`'s origin at whichever release prefix
   is "live" via its `origin_path`. Going live = update the distribution's
   origin path to the new release prefix + invalidate `/*`. Rollback =
   flip origin path back to a previous (still-retained) release prefix +
   invalidate — no rebuild or re-upload needed. (Chosen over two separate
   buckets, or two CloudFront distributions behind weighted DNS — the
   latter would need Route53, and DNS stays at GoDaddy per the existing
   AWS Components decision.)
3. **Terraform vs. CLI for the switch.** Flipping `origin_path` on every
   deploy via `terraform apply` fights with Terraform's own state if
   anyone/anything else ever touches it directly — decide whether the
   switch step is Terraform-managed (a variable + apply) or a plain `aws
   cloudfront update-distribution` CLI call in the workflow, decoupled
   from the Terraform-managed baseline config.
4. **Split "upload" from "switch" in the workflow** — two distinct steps
   (or jobs) so a bad build can be caught (smoke-tested against its
   release-prefix URL) before it's switched live, instead of today's
   single sync-and-you're-live step.
5. **Retention/cleanup.** Old release prefixes need an S3 lifecycle rule
   (expire after N days, or keep last N releases) so storage doesn't grow
   unbounded — still cheap either way, but not free forever.
6. **Rollback trigger.** A `workflow_dispatch` input ("roll back to
   release `<sha>`") that just re-points `origin_path` + invalidates, with
   no rebuild.

**Open questions:**

- How many past releases to retain (storage cost vs. rollback depth)?
- CloudFront distribution updates typically take a few minutes to
  propagate globally — is "flip and wait a few minutes" an acceptable
  definition of "switch" here, or is that a dealbreaker for this site?
- Does going live need a smoke-test gate before the origin-path flip, or
  is "flip and watch" fine given how small/low-traffic this site is?
- Should the switch require manual approval (like the release-tag gate
  elsewhere in this project) or run automatically on every successful
  build?

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
