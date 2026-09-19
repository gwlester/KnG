# To Do List

## Virtual Church Musician HTML Page Changes

1. Card order should be
   1. Template Editor
   2. Service Builder
   3. Service Runner
   4. Admin and Security
   5. Server
   6. MIDI Player
2. How do you feel about adding the icons to the above cards?

### Review notes (Claude, 2026-09-18) -- nothing implemented

**Card order (item 1)** -- straightforward; the home page's "Prepare"
card text ("Service Builder and Template Editor") should be reordered to
match. Questions and suggestions:

- The cards currently carry workflow pills (Prepare / Run / Manage). The new
  order puts MIDI Player last, but its pill says "Run", so the pills no
  longer sit in runs. Options: (a) drop the pills, (b) relabel MIDI Player
  "Play", or (c) keep the pills and accept the interleaving. **Recommend
  (a) or (b).**
- The Download page's app order (Runner, Builder, Editor, ...) differs from
  this page's (Editor, Builder, Runner, ...). Intentional? If so, fine
  (product page = workflow order, download = most-wanted first); otherwise
  **recommend using one order everywhere** so the site feels consistent.

**Icons (item 2)** -- **Recommend yes.** Real app icons are the cheapest way
to make this page feel like a product page and to help visitors recognise
the apps after install. Notes:

- The icons exist in the VCM repo (`builds/icons/<app>/`), but `preview.png`
  is only 64x64 -- soft on retina screens at card size. Use the larger PNGs
  under each app's `linux/hicolor/` directory, or export from the `.icns`,
  or supply SVGs if source artwork exists. Target roughly 96 px displayed,
  192 px source.
- Admin and Security is one card, so the shared Admin icon (README notes no
  dedicated Security artwork) is not a problem here.
- Questions: is the artwork yours to publish (no third-party assets)? OK to
  copy the files into this repo under `www/img/` (they become public)?
- Decorative use: `alt=""` since the app name sits next to it. On the
  Download page, icons inside a native `<select>` are not possible; see the
  picker note below.

## Downloads Page

Order from top to botton:
1. Pick Application
   - Pull down with order:
      1. Service Runner
      2. Service Builder
      3. Template Editor
      4. Admin and Security
      5. Server
      6. MIDI Player
2. Plaform
   - Defaults to the platform accessing the web page.
   - For 1 to 4, option order is:
      1. Andriod
      2. Windows
      3. Mac
      4. Linux
   - For 5 and 6, option order is:
      1. Linux
      2. Windows
      3. Mac
3. Button that says **Download**
   - Only enabled when 1 and 2 are selected.

Hits a lambda that returns a redirect based on a JSON "matrix" -- currently all redirects to a "Comming Soon" page.

### Review notes (Claude, 2026-09-18) -- nothing implemented

Typos to fix when written up: "botton", "Plaform", "Andriod", "Comming
Soon".

**Biggest question first: is a download gated by purchase?** The VCM repo's
`licenses/agreement.md` is a *Commercial* license titled "Online Purchase and
Download License", and the site copy talks about a "sales platform". If
installers are only for paying customers, the design changes (a public
redirect would let anyone skip payment). Please decide:

1. Free download / public beta -- anyone can download. Simple.
2. Paid, with the sales platform (Gumroad, Paddle, Lemon Squeezy, ...)
   hosting or delivering the files -- this page becomes a "Buy" / "Get it"
   page and the picker mostly disappears.
3. Paid, but files hosted by us behind a license key or signed, expiring
   links -- needs a real backend (this is where a Lambda earns its keep).

Either way, the agreement says downloading means accepting it, so the page
should link the agreement near the button ("By downloading you agree to
the license agreement") -- worth doing in every case.

**Lambda vs. static -- recommend static unless you need gating or counts.**

- A Lambda is only necessary if we want to (a) gate downloads, (b) count
  them, or (c) change targets without a site deploy.
- Static alternative: a `downloads.json` matrix shipped *inside each release*
  (`releases/<sha>/`), with the button doing `window.location = url` in
  JS. Advantage specific to our blue-green setup: preview shows the
  *preview* release's matrix and live shows live's; promoting or rolling
  back moves the matrix along with the page. A single shared Lambda with the
  matrix baked in would change what live visitors download the moment CI
  applies it, before any promotion.
- If a Lambda is wanted anyway (e.g. counts via CloudWatch logs): make the
  Download button a plain GET form/link to a Function URL (`?app=&platform=`),
  returning a 302. That works without CORS or fetch, and JS only handles
  defaults and enable/disable. Only ever redirect to URLs found in the matrix,
  never to anything from the query string (no open redirect).
- A single source of truth: keep the matrix in the repo
  (e.g. `content/downloads/matrix.json`), have the build render the existing
  availability table *and* embed the JSON for the picker, so the table, the
  picker and the redirects can never disagree. Give it a `FormatVersion`
  (per CLAUDE.md's contract rule).

**Where do the files live?** The VCM repo is *private*, so its GitHub
release URLs will 404 for the public. Options: (a) copy release assets to a
public location we control (S3 + CloudFront path such as `/dl/`, or a second
bucket) -- **recommended**, also lets us keep the "keep 1 previous release"
idea; (b) a separate public releases-only repo; (c) hand off to the sales
platform. Related: who updates the matrix per release? VCM's README table is
already generated from deterministic tag-based URLs, so a small script
(`update_downloads.py <tag>`) could produce the matrix; the VCM release
workflow could call it, but writing into this repo needs a token -- start
manual (run the script, commit) and automate later if releases get frequent.

**Picker design / behaviour:**

- Platform detection: check Android *before* Linux (Android UAs contain
  "Linux"); prefer `navigator.userAgentData.platform` with a UA fallback.
  iPhone/iPad and ChromeOS/unknown: no default, plus an honest note
  ("iOS is not available yet").
- Mac chip (Apple Silicon vs Intel) cannot be detected reliably. Question:
  is the `.dmg` universal? If not, we need an extra choice.
- Platform is a better fit as radio buttons (3-4 options, detected one
  pre-selected) than a second pull-down; the app pull-down is fine as a
  native `<select>` (accessible, works on mobile).
- Cascading rules to specify: when the app changes, rebuild the platform
  list, keep the selection if still valid, otherwise clear it and disable the
  button. Example: Android detected + "Server" chosen -> Android is not
  offered, so nothing is selected.
- Options are not uniform per app. From the VCM README: Admin is
  desktop-only, **Security is Android-only** -- so "Admin and Security" needs
  a rule: Android -> Security.apk, Windows/Mac/Linux -> Admin. Please
  confirm that is intended (and whether the label should say so).
- Windows has both `.exe` and `.msi`; Linux is `.deb` only (Debian/Ubuntu).
  Which is the default for Windows? Label options clearly, e.g. "Windows
  (64-bit)", "Linux (.deb, 64-bit)".
- Disabled button: add a line of helper text ("Choose an app and a platform")
  rather than a silent grey button.

**"Coming Soon" target.** `coming-soon.html` no longer exists. Rather than
redirecting people to a dead-end page, **recommend** an `available: false`
flag per matrix entry: the UI keeps the button disabled and shows "Coming
soon" next to the choice. When a release is ready, flip flags -- no lambda
or redirect change.

**Suggested extras (cheap, high value):** show the version and a "Beta"
label (the latest VCM release is a `-b.N` prerelease); links to the User
Manual, System Administrator Guide, SHA256SUMS and release notes (all
already produced per release); brief install notes per platform. Ask:
are the Windows/macOS installers signed/notarized? Unsigned ones trigger
SmartScreen/Gatekeeper warnings, and Android APKs need "install unknown
apps" -- worth a short help section either way.

**Suggested implementation order (when you say go):** decide gating (above)
-> decide hosting -> matrix format + script -> picker page + tests ->
hosting/redirect wiring. The card-order/icon change in the section above is
independent and can go first.

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
