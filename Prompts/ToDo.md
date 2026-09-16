# To Do List

## Blue-Green Deployments

**Status: Terraform + workflow implemented (2026-09-16); not yet
exercised against real AWS** -- same blocker as "Create Terraform for
AWS Components" below (needs the AWS bootstrap run first). Including
the pre-existing-infrastructure note further down -- fully resolved, no
open questions left on this item.

**What's actually built, per the numbered list below:**

- `terraform/cloudfront.tf`: the origin's `origin_path` plus a
  `lifecycle { ignore_changes = [origin] }` on the distribution, so
  Terraform sets it once on creation and never fights the CLI switch
  again. Tradeoff, deliberate: this also means Terraform won't notice a
  future change to the bucket/OAC either -- remove `ignore_changes`
  temporarily for that one apply if the bucket or OAC is ever replaced.
- `.github/workflows/deploy-to-aws.yml`: split into `build-and-upload`
  (syncs to `releases/$GITHUB_SHA/`, nothing user-facing changes) and
  `switch-live` (flips `origin_path` via `aws cloudfront
  update-distribution` + `jq`, invalidates, then deletes every
  `releases/*` prefix except the new live one and the one it replaced).
- `.github/workflows/rollback.yml` (new): `workflow_dispatch` with a
  `release_sha` input, flips `origin_path` back + invalidates. No
  approval gate on this one -- see the file's own comment for why.
- **GitHub Environments created via the API (2026-09-16):** `production`
  (no restrictions) and `production-switch` (required reviewer:
  `gwlester`) -- `switch-live` runs under `production-switch`, so it
  pauses for manual approval before anything user-facing changes.

**Smoke test, as actually implemented (upgraded 2026-09-16):** a real
pre-switch preview URL now exists -- see "Preview environment" below.
`build-and-upload` points `preview.kng-consulting.com` at every uploaded
release automatically (no approval needed, it's not user-facing), so the
`production-switch` approval step's smoke test is now: open
`https://preview.kng-consulting.com`, check it, then approve.

**Preview environment (added 2026-09-16):** a second CloudFront
distribution (`terraform/cloudfront_preview.tf`), aliased to
`preview.kng-consulting.com` (a SAN on the same ACM cert, via the new
`preview_domain_name` variable), sharing the same OAC and S3 bucket
(bucket policy in `s3.tf` now allows both distributions' ARNs). Uses the
AWS managed "CachingDisabled" policy instead of "CachingOptimized" --
every request goes straight to S3, so the reviewer always sees the exact
release just uploaded with no invalidation step needed. `rollback.yml`
also points preview at whatever it rolls back to, so it never shows a
stale release. `variables.tf`'s old `domain_names` was renamed
`live_domain_names` to make room for this (only entries in
`live_domain_names` are live-distribution aliases; `preview_domain_name`
is only ever aliased on the preview distribution -- CloudFront requires
each alias belong to exactly one distribution). New GitHub repo variable
needed at bootstrap: `PREVIEW_CLOUDFRONT_DISTRIBUTION_ID` (optional --
the preview-flip steps no-op without it), plus one more GoDaddy CNAME --
both added to `Prompts/AWS_Deployment.md`.

The three places that flip a distribution's `origin_path` (preview flip,
switch-live, rollback) now share one script,
`.github/scripts/set_cloudfront_origin_path.sh`, instead of three copies
of near-identical `jq`/`aws cloudfront` calls.

**Found while wiring this up, unrelated to blue-green itself:** every
push-triggered run of `deploy-to-aws.yml` so far (20+ runs, going back to
before this session) had failed instantly with zero jobs and GitHub's
generic "workflow file issue" message -- including runs from commits
that never touched the workflow file. Root cause found and fixed
2026-09-16: the workflow's `on.push.branches` said `main`, but this
repo's actual (and only) branch is `master` -- so no push should have
triggered it via that filter at all, yet every push somehow still
produced a run; changed the trigger to `master`, but since manually
dispatching the workflow to verify is blocked by this session's auto
mode classifier (protected-scope IaC apply), the fix is unverified --
watch the next real push's run in the Actions tab.

**Previous state, now replaced by the above:** `deploy-to-aws.yml` used
to run `aws s3 sync www s3://$S3_BUCKET_NAME --delete` directly against
the one bucket CloudFront serves from, then invalidate `/*` every push --
a bad deploy was live the moment the sync finished, with no fast
switch-back.

**Design notes below, for reference (all decided and implemented above):**

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
   release prefix plus the one immediately before it are kept.
   Implemented as an explicit delete step in `switch-live` (not an S3
   lifecycle rule -- lifecycle rules work on object age, not "keep the
   last N," so an explicit step reading the distribution's own prior
   `origin_path` was the more precise fit).
8. **Rollback trigger.** A `workflow_dispatch` input ("roll back to
   release `<sha>`") that just re-points `origin_path` + invalidates, with
   no rebuild -- limited to the 1 retained previous release per the
   retention decision above.

**Pre-existing infrastructure (resolved 2026-09-16).** Manually created
(not IaC-managed), in the same AWS account, region us-east-2 (Ohio) --
this Terraform's default `aws_region` is us-east-1, which is fine, the
two don't need to match. `kng-consulting.com`/`.net` are currently live
there via GoDaddy DNS, so the DNS flip to the new CloudFront
distribution's domain remains the actual go-green cutover moment, not
the Terraform apply itself.

Existing S3 buckets in the account, all confirmed safe to delete once
the new stack is live (kept here for the eventual manual teardown):

| Bucket | Created |
| --- | --- |
| `kng-consulting.com` | 2020-02-13 |
| `www.kng-consulting.com` | 2020-02-13 |
| `kng-consulting.net` | 2020-02-13 |
| `www.kng-consulting.net` | 2020-02-13 |
| `private.kng-consulting.net` | 2020-02-16 |
| `kngconsulting` | 2020-01-17 |
| `kngconsultingwebsite` | 2020-01-18 |
| `gwlester` | 2021-07-27 |
| `gerald.lester` | 2021-07-27 |

(All region us-east-2.) The domain-named buckets match the classic S3
static-website-hosting naming convention (bucket name = domain, so a
plain CNAME/website-endpoint setup works without CloudFront) -- likely
no CloudFront/ACM in the old setup at all. Unconfirmed, but consistent
with everything else here, and not something this project needs to rely
on either way.

**Name-collision check: clear, confirmed 2026-09-16.** No bucket above
is named `kng-consulting-site` (this Terraform's `bucket_name` default),
and no `kng-github-actions-deploy` IAM role exists either. `terraform
apply` can proceed with `terraform/variables.tf`/`oidc.tf`'s defaults
as-is -- no rename needed, and `Prompts/AWS_Deployment.md` step 0's
collision check is already satisfied, no need to re-run it.

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
