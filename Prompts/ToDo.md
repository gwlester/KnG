# To Do List

## Blue-Green Deployments

**Status: implemented and exercised against real AWS (2026-09-18).**
Pushes to `master` apply Terraform, upload `releases/<sha>/`, and point
`preview.kng-consulting.com` at it. **Remaining:** promote a release to live
(manual "Run workflow" + `production-switch` approval), then cut DNS over at
GoDaddy (swap the `www` CNAMEs to the live CloudFront domain, forward the
apex domains to `https://www.<domain>`), then tear down the old buckets
listed below. Not scheduled -- expected to be days out. Including
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
`https://preview.kng-consulting.com`, check it, then approve. **Changed
2026-09-18:** `switch-live` now runs only on a manual `workflow_dispatch`
(pushes just upload and update preview), because a push run waiting for
approval held the deploy concurrency lock and blocked every later push.

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

**CI "workflow file issue" -- resolved 2026-09-18.** Every push run of
`deploy-to-aws.yml` used to fail instantly with zero jobs. Root cause: a
job-level `if: hashFiles(...)`, which GitHub only allows in step-level
expressions. Removing it fixed it (the earlier `main`->`master` and missing
Environments theories were red herrings). Follow-on fixes the same day:
the deploy role's OIDC trust now also accepts the repo's immutable subject
claim (`use_immutable_subject` is on), Terraform state moved to S3, the
role got read access for refresh, and `switch-live` now runs only on manual
dispatch so an unapproved push can't hold the concurrency lock.

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
