# To Do List

## Blue-Green Deployments

**Status: decided (2026-09-16), not yet implemented.** See also the
pre-existing-infrastructure note at the end -- still being clarified,
may change some of this.

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
3. **Terraform vs. CLI for the switch -- decided: CLI.** The switch step
   runs a plain `aws cloudfront update-distribution` call in the workflow,
   not a `terraform apply` of an `origin_path` variable -- keeps the
   switch decoupled from the Terraform-managed baseline config, so nothing
   fights Terraform's state if the origin path is ever touched directly.
4. **Split "upload" from "switch" in the workflow.** Two distinct steps
   (or jobs): upload a new release prefix, then a separate, later step
   does the switch. A few minutes of CloudFront propagation delay on the
   switch itself is acceptable for this site.
5. **Smoke test -- decided: manual, always.** Before the switch step
   runs, a manual smoke test against the new release prefix's URL is
   required, in addition to whatever automated smoke test the workflow
   also runs. Not "flip and watch."
6. **Switch approval -- decided: manual, at this time.** The switch does
   not run automatically on a successful build/smoke test -- it needs an
   explicit go-ahead (e.g. a GitHub Environment protection rule requiring
   approval, or a separate manually-triggered `workflow_dispatch` step),
   the same shape as the release-tag approval gate elsewhere in this
   project. Revisit later if that becomes unnecessary friction.
7. **Retention -- decided: keep 1 previous release.** Only the live
   release prefix plus the one immediately before it are kept; anything
   older is cleaned up (S3 lifecycle rule capped at 2 release prefixes, or
   an explicit delete step when a new release goes live) rather than
   growing indefinitely.
8. **Rollback trigger.** A `workflow_dispatch` input ("roll back to
   release `<sha>`") that just re-points `origin_path` + invalidates, with
   no rebuild -- limited to the 1 retained previous release per the
   retention decision above.

**Pre-existing infrastructure to account for (raised 2026-09-16).** There
is AWS infrastructure already in place, serving the KnG domains today,
that this Terraform-managed stack is replacing. Confirmed so far:

- `kng-consulting.com`/`.net` **are currently live there** via GoDaddy
  DNS right now -- so the eventual DNS flip to the new CloudFront
  distribution's domain is the actual go-green cutover moment, not the
  Terraform apply itself.
- It's in the **same AWS account** this Terraform bootstraps into --
  real risk of resource-name collisions, not just a theoretical one.
- **Still unknown, Gerald to find out and update this item:** what the
  pre-existing setup actually is (S3+CloudFront by hand, something else
  entirely).

**Given same-account is confirmed, check before running
`terraform apply` for the first time** (also called out in
`Prompts/AWS_Deployment.md` step 0 now):

- Does the old setup use an S3 bucket named `kng-consulting-site` (this
  Terraform's default, in `terraform/variables.tf`'s `bucket_name`)? Two
  buckets can't share a name while both exist -- override `bucket_name`
  if so.
- Does an IAM role named `kng-github-actions-deploy` already exist (this
  Terraform's `terraform/oidc.tf`)? Would collide the same way -- rename
  via `aws_iam_role.github_actions_deploy`'s `name` if so.
- Everything else (ACM cert, CloudFront distribution) can coexist safely
  under different resource IDs regardless -- no collision risk there.

Gerald tears down the old infrastructure manually once the new stack is
confirmed live, whenever he's satisfied it's safe to -- not scripted, not
run unattended.

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
