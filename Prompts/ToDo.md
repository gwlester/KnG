# To Do List

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

Add download of User and System Admin Guide.

### Guides download -- review notes (Claude, 2026-09-18) -- nothing implemented

Context: every Virtual Church Musician release already attaches a **User
Manual** (the four client apps) and a **System Administrator Guide**
(installing and maintaining the Server and MIDI Player), each as a Markdown
zip, HTML and PDF. So the content exists; the questions are presentation and
access.

**Recommendations**

- A separate **Documentation** section below the picker, not another picker
  row: two cards (User Manual, System Administrator Guide), each with
  "Read online" (HTML) and "Download PDF". Skip the Markdown zip on the
  public page.
- The guides follow the **Version** control (default: current), since a
  guide matches its release; show "applies to vX.Y.Z" on each card.
- Host the HTML at stable, linkable URLs (e.g. `/docs/<version>/...`, plus a
  `latest` alias) instead of force-download redirects -- readable in the
  browser, linkable from support emails, indexable. The Virtual Church
  Musician release workflow uploads them next to the installers, same as the
  matrix.
- Public docs need no signed URLs (the 5-minute signing is for installers).
- **Air-gapped audience:** these sites often cannot look anything up during
  install. Say "download for offline use", and check whether the Server
  installer ships with the guide (or a pointer to it); if not, consider
  bundling the PDF.
- Also link the guides from the product page ("Documentation") and, for
  hardware buildouts, from the Services page.
- Put SHA256SUMS and the release notes beside them (already produced per
  release).

**Questions**

1. Public or buyers-only? The System Administrator Guide covers the paid
   Server and MIDI Player. **Recommend public** (fewer support questions, helps
   evaluation, needed before install on an air-gapped site) -- but please
   confirm it contains nothing sensitive (default credentials, internal
   hostnames) before it goes on the open web.
2. Formats: HTML + PDF only, or also the Markdown zip?
3. **Languages:** the repo has English, German and Spanish sources under
   `docs/`. Are translated guides published with each release? If yes, add a
   language selector (English default); if they are incomplete or not
   maintained, say the guides are English-only. Should the site itself stay
   English-only for now?
4. Each release, show only that version's guides, or always the latest with
   an archive of older ones?

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

- Answer: add the license agreement.

- Answer: the desktop and mobile are free.  The server and midi player are paid using one of the sales platform.

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

  - Answer: I don't want someone examining the HTMl/Javascript in their browser and see the full matrix.  We could keep the matrix in AppConfig -- and push it there from the repo.

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

- Answer:
   1. The mobile apps will be on the Play Store.
   2. The desktop, I would think in an S3 bucket that the lambda gives a signed url with a 1 week duration.
   3. The server and midi will depend on the sales platform -- not sure yet.
   4. Yes, we can add a version, default to current.  That way we can keep a previous release and have the option to offer access to betas.

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

- Answer: yes.

**Suggested implementation order (when you say go):** decide gating (above)
-> decide hosting -> matrix format + script -> picker page + tests ->
hosting/redirect wiring. The card-order/icon change in the section above is
independent and can go first.

### Round 2 (Claude, 2026-09-18) -- reacting to your answers

**Decisions I am taking as settled (tell me if wrong):** free clients
(desktop + mobile), paid Server + MIDI Player via a sales platform (platform
TBD); Android via Google Play; desktop installers in S3 behind a Lambda that
hands out signed URLs; a Version control (default: current) that also allows
older and beta releases; Windows/macOS installers are signed/notarized; the
license agreement gets linked. Icons are not used inside the select.

**1. The matrix cannot live in this repo.** `gwlester/KnG` is a *public*
repo, so a matrix committed here is public no matter where it is deployed --
"push it to AppConfig from the repo" would leak it. Also, releases happen in
the private VCM repo (`release.yml`), which is the thing that knows the tag,
file names and checksums. **Recommend: VCM's release workflow owns the
matrix.** It uploads installers to the downloads bucket and writes the
matrix there (same AWS account, via an OIDC role trusted for the VCM repo);
this repo only owns the picker UI and the Lambda. Releasing becomes one
step, with no cross-repo commit or token.

**2. What exactly must stay private? Please clarify**, because it decides the
design:

- (a) The *targets* (S3 keys, store/purchase URLs) and unlisted *beta
  versions* -- these are easy: only the Lambda ever sees them, the browser
  gets a redirect. This is what signed URLs give you.
- (b) The *availability matrix itself* (which app exists on which
  platform). That is already public marketing information (the table on the
  page), and the picker must show choices, so hiding it entirely means the
  picker fetches options from the Lambda step by step. Doable, but I would not
  bother unless you have a reason.
  **Recommend: options public/embedded, targets and betas private.**

**3. AppConfig vs. the alternatives.** AppConfig works (validation, staged
rollout, rollback) but adds a service, a Lambda layer, several Terraform
resources and IAM, for a JSON file that changes once per release. **Recommend
a `matrix.json` object in the private downloads bucket instead**: bucket
versioning gives rollback, the release workflow uploads it together with the
installers, and the Lambda caches it for ~60 s. Is there a reason you want
AppConfig (gradual rollout, feature flags)? If not, skip it.

**4. The one-week signed URL will not work as described.** A URL presigned
by a Lambda (temporary role credentials) stops working when those credentials
expire -- hours, not a week; a true 7-day presign needs a long-lived IAM
user key, which I would not create. It is also unnecessary if the Download
button generates the URL at click time: **5-15 minutes is plenty** (the
signature only has to be valid when the download *starts*). Why a week --
emailing links after purchase, or resumable downloads? If long-lived links
are needed, use **CloudFront signed URLs/cookies** in front of the bucket
(any expiry, cheaper egress, custom domain such as `downloads.` later).
**Recommend CloudFront in front of the private bucket (OAC) for all desktop
files.**

**5. Free files do not need signing.** For public releases, plain CloudFront
URLs are simpler, cacheable and resumable. Signing is only needed for betas
and paid files. Do you want signed URLs on the free releases too (e.g., to
count downloads or block hot-linking)? Counting works without signing --
the Lambda's redirect log is the count.

**6. Beta access: how is it granted?** Options: a private link
(`?channel=beta&code=...`), a code typed into the page, or invite-only. And
what is "current" today? Every VCM release so far is a `-b.N` prerelease.
**Recommend an explicit `channel` (stable | beta) per release in the matrix**:
default Version = latest *stable*; betas listed only with a code; until the
first stable exists, decide whether the public gets the latest beta (labelled
"Beta") or nothing. Also decide retention (how many old releases stay in the
bucket) -- a lifecycle rule can enforce it.

**7. Android = Google Play, so no APK matrix.** The Android choice becomes
"Get it on Google Play" (an external link, not a download); the sideload help
I suggested is no longer needed. Questions: are all four mobile apps going on
Play? Heads-up: Play requires a publicly hosted **privacy policy** URL and a
developer contact -- **recommend adding Privacy Policy (and Terms) pages
to this site**; and new personal developer accounts must run a closed test
(12 testers, 14 days) before production -- verify the current rule, as it
affects the schedule.

**8. Server and MIDI Player (paid).** Until the sales platform is chosen,
model them as `type: purchase, available: false` ("Coming soon"). Each
matrix entry then has a `type`: `download` (signed/CloudFront link), `store`
(Play), `purchase` (sales-platform page) or `coming-soon`, and the button
label follows ("Download", "Get it on Google Play", "Buy"). When choosing a
platform, **recommend a Merchant of Record** (Paddle, Lemon Squeezy,
FastSpring, Gumroad): they collect and remit sales tax/VAT worldwide,
which is a large burden for a solo seller; plain Stripe Payment Links do not.
Key question: how does the app validate a purchase -- the VCM repo has
`license_config.json`; will the platform's license-key service be used, or
your own? That affects which platforms fit.

**9. License agreement -- three flags before it goes on the web.**
- The agreement (`licenses/agreement.md` in VCM) names you personally
  and includes a **home street address**, and `license_config.json` lists a
  personal Gmail as support contact. Publishing it exposes both. Use a
  business address/PO box and `inquiries@kng-consulting.com`? Is KnG
  Consulting a legal entity that should be the licensor?
- It is written as an *Online Purchase* license. Do the **free** clients need
  their own (simpler) EULA, or does this cover them?
- **Recommend a required "I have read and agree" checkbox** beside the
  button (enabled only with app + platform + checkbox), not just a link:
  it is much easier to defend than link-only. (Not legal advice -- worth a
  lawyer's look before launch.) Where should the source of truth live so
  the site never shows a stale copy: rendered from the VCM file at build
  time, or copied in when the agreement changes (it is dated 2026-08-29)?

**10. API contract and rollout notes.**
- **Endpoint shape:** `GET /download?app=&platform=&version=&v=1` returning
  302, so it works as a plain link with no CORS. `v` (or an `X-API-Version`)
  and the matrix `FormatVersion` satisfy CLAUDE.md's compatibility rule --
  and because the live page and the preview page both call one shared Lambda,
  **the Lambda must stay backward-compatible** with the page currently live.
- **Validation:** only ever redirect to URLs from the matrix; reject unknown
  app/platform/version.
- **New AWS pieces** (S3 downloads bucket, CloudFront distribution + OAC,
  Lambda + Function URL, IAM for the VCM release role) will need CI-role
  widening again -- you will be running those applies, same as before.
- **Cost guard:** public downloads can get expensive if abused. **Recommend
  an AWS Budgets alert** (e.g. $10/month) before launch.

**Revised order of work (still nothing implemented):** (1) card order,
pills, icons (independent, do first) -> (2) your answers to #2, #4, #6, #9
-> (3) matrix format + VCM release-workflow step -> (4) downloads bucket +
CloudFront + Lambda in Terraform -> (5) picker page + agreement page + tests
-> (6) Play Store and sales-platform links as they become available.

### Decisions and status (2026-09-18)

**Decided:** the matrix does not live in this (public) repo; signed URLs
last 5 minutes and are generated at click time; no AppConfig; Free/Paid
labels; privacy policy added; personal details removed from the published
license; the license agreement gets linked from the Download page.

**Done:** icons, card order, Free/Paid labels, Privacy Policy and License
pages (see Done.md). The Download page itself is still the static
availability table with a disabled button.

**Still open (blocks building the picker):**

1. Privacy scope (#2 above): confirm options stay public and only targets
   and betas are private (my recommendation).
2. Beta access (#6): private link, typed code, or invite; and what "current"
   means while every release is a `-b.N` prerelease.
3. Required "I agree" checkbox beside the button (recommended) -- yes/no?
4. Licensor identity: the license still names you personally. Should KnG
   Consulting (if it is an entity or DBA) be the licensor instead?
5. ~~License vs. privacy-policy consistency~~ **Resolved 2026-09-18:** the
   license (sections 5 and 11) now says the software runs offline, never
   contacts the Licensor, hosts no customer data and collects no usage
   information. Lawyer review of the whole agreement is still advised.
6. ~~Source-of-truth drift~~ **Resolved 2026-09-18** on the Virtual Church
   Musician branch `work/License_Match_Privacy_Policy` (address removed,
   `support_contact` -> `inquiries@kng-consulting.com`, bundled copies
   regenerated, tests updated). **Not yet merged into `main`:** that repo's
   mandatory full local test-suite gate has to run first. This site's copy is
   regenerated from that branch's `agreement.md` -- re-copy it whenever the
   agreement changes.
7. ~~Server phone-home~~ **Resolved 2026-09-18:** no -- it works fully
   air-gapped; the privacy policy now says so.
8. Retention wording: the policy says contact-form messages stay in the
   mailbox "until no longer needed" -- fine, or do you want a fixed period?

### Status update (2026-09-18, later) -- Services / Support / Documentation first cut done

**Answers taken:** hymnal bundles = hymnal metadata definitions;
customization = custom versions built by KnG (customers cannot change the
code); KnG is an LLC; SES only for the contact form to you, no customer
emails; documentation section on the Download page; FAQ first cut; features
as a section on the product page (a separate Features page can wait until
there are screenshots).

**Please verify or decide:**

1. **Legal name.** The site uses "KnG Consulting, LLC" (one constant,
   `LEGAL_ENTITY` in `src/build_blog.py`; the license text comes from the
   Virtual Church Musician repo). Check it against the Louisiana Secretary of
   State registration.
2. **Reply time.** The pages say "usually within two business days". Change
   it if you cannot commit to that.
3. **Free apps need the Server.** The user guide says every app connects to
   the Church Music Server, so the free apps are only useful with the paid
   Server. The site now says so (product page, FAQ). Is that the message you
   want, or should "free" be framed differently?
4. **macOS notarization.** You said the installers are signed/notarized, but
   the user guide tells macOS users the app "has not been notarized yet" and
   points them to `fix_app_permissions.command`, and the release workflow
   publishes unsigned artifacts when signing credentials are missing. The FAQ
   currently follows the guide. Which is true today? Same question for
   Windows SmartScreen.
5. **Services Terms** are a first draft (fees, IP, hardware, liability,
   Louisiana law). Have counsel review them, and the whole license, before
   the site goes live.
6. **Hardware business model** is still open: do you sell and ship hardware,
   configure hardware the church buys, or install on-site? The page
   deliberately says only "we build out and configure" and "prices are by
   quote" -- no shipping, warranty, packages or prices until decided. Also
   still useful: a recommended-hardware list, and which of Server / MIDI
   Player licenses are included in a buildout.
7. **About section** is minimal (only facts already public). Add background,
   experience, photo, and any church willing to be quoted.
8. **Guides:** links are disabled. Before publishing them, confirm the
   System Administrator Guide holds nothing sensitive, and decide languages
   (English, German and Spanish sources exist) and formats (HTML + PDF).
9. Optional follow-ups: one blog post per service; a public-domain demo
   hymnal-metadata download; per-item pricing once you have engagements.

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
