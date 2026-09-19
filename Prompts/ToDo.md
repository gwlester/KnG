# To Do List

## Downloads Page

**Status:** the Download page is still a static availability table with a
disabled button and a disabled Documentation section. Everything below is
design and decisions; nothing in the picker or the download backend is built.
Icons, card order, Free/Paid labels, the Privacy Policy and License pages, the
Services page, Support/FAQ, and the Features section are done (see Done.md).

### What we are building

Top to bottom on the Download page:

1. **Pick Application** (pull-down), in the same order as the Virtual Church
   Musician page: Template Editor, Service Builder, Service Runner, Admin and
   Security, Server, MIDI Player. No app is preselected ("Choose an app...").
2. **Platform.** Defaults to the platform of the visitor's browser.
   - Free apps (Template Editor, Service Builder, Service Runner, Admin and
     Security): Android, Windows, Mac, Linux. Android means *Get it on Google
     Play* (an external link, not a download). Admin is desktop-only and
     Security is Android-only, so "Admin and Security" offers Android ->
     Security and Windows/Mac/Linux -> Admin.
   - Paid apps (Server, MIDI Player): Linux, Windows, Mac (no Android).
   - When the app changes, rebuild the platform list; keep the choice if still
     valid, otherwise clear it and disable the button.
3. **Version.** Defaults to the current release; the previous release is also
   available (current and current - 1). Beta versions appear only with access
   (open question 2).
4. **Button.** Enabled only when an app and a platform are chosen (and the
   agreement box is ticked, if we adopt it -- open question 3). Helper text
   when disabled ("Choose an app and a platform"). The label follows the entry
   type: Download, Get it on Google Play, Buy, or Coming soon (disabled).
5. **License.** A link to the License Agreement beside the button, "By
   downloading you agree to the License Agreement".
6. **Documentation** (below the picker): two cards, User Manual and System
   Administrator Guide, each with *Read online* (HTML) and *Download PDF*, for
   the selected version, marked "applies to vX.Y.Z". English only for now (see
   open question 7). SHA256SUMS and the release notes sit beside them. The
   guides are also linked from the product page and the Services page.
7. **Install notes** per platform (see Launch Readiness; the installers are
   not signed or notarized).

### Decisions (settled)

- **Who can download:** the four free apps (desktop and mobile) are free.
  Server and MIDI Player are paid, sold through a sales platform (not chosen
  yet). Until it is, they show "Coming soon".
- **Android:** mobile apps are distributed through Google Play only.
- **Desktop installers:** stored in a private S3 bucket; a Lambda hands out
  signed URLs valid for 5 minutes, generated at click time (so no one-week
  links). Retention: current release plus the previous one.
- **The matrix** (which file each app/platform/version maps to) is private and
  is never stored in this public repository or shipped to the browser. No
  AppConfig; a `matrix.json` object in the private bucket instead.
- **Ownership:** the Virtual Church Musician release workflow uploads the
  installers, the guides, and the matrix (same AWS account, through an OIDC
  role); this repo owns only the picker page and the Lambda.
- **Documentation:** public (no purchase needed), HTML plus PDF only (no
  Markdown zip), hosted at stable readable URLs (`/docs/<version>/...` plus a
  `latest` alias), no signing needed. The guides ship inside the installers
  already, so air-gapped sites have them.
- **License agreement:** linked from the Download page. It names KnG
  Consulting, LLC, and the personal details are removed.
- **Typos:** fix them whenever seen, in any file.

### Open questions

Each has my recommendation; a one-line answer is enough.

1. **What must stay private?** The *targets* (file locations, purchase URLs)
   and unlisted beta versions are private. The *availability matrix itself*
   (which app exists on which platform) is already public marketing, and the
   picker must show choices. **Recommend:** the picker's options are
   embedded in the page; only targets and betas stay server-side. (Hiding the
   options too means the picker fetches every choice from the Lambda; doable,
   but I would not.) Agree?
2. **Beta access and "current".** Every release so far is a `-b.N`
   prerelease. **Recommend** a `channel` (stable | beta) on each matrix
   entry; the default Version is the latest *stable*; betas are listed only
   with an access code typed into the page (or a private link). Until the
   first stable release exists, should the public see the latest beta labelled
   "Beta", or nothing? Retention: current and current - 1 *per channel*?
3. **Agreement checkbox.** **Recommend** a required "I have read and agree to
   the License Agreement" box beside the button (much easier to defend than a
   link alone). Yes or no? And do the *free* clients need a simpler EULA, or
   does this agreement (written for online purchase) cover them?
4. **Paid products.** Which sales platform? **Recommend** a Merchant of
   Record (Paddle, Lemon Squeezy, FastSpring, Gumroad): they collect and
   remit sales tax/VAT worldwide. Key question: **how are licenses issued and
   checked for a Server that runs air-gapped?** Offline checking needs a
   license file or key the app can verify without contacting anyone. What
   exists in Virtual Church Musician today, and can the chosen platform
   generate it?
5. **Google Play.** Are all four mobile apps going on Play (Template Editor,
   Service Builder, Service Runner, Security)? Timing note: the release APK
   is currently signed with a debug key and Play needs a proper upload key and
   app bundle (tracked in the Virtual Church Musician ToDo), and a new
   personal Play account may need a closed test (about 12 testers for 14 days
   -- verify the current rule).
6. **Desktop file details.** Is the macOS `.dmg` universal (Apple Silicon and
   Intel) or Apple-Silicon-only? For Windows, which is the default, `.exe` or
   `.msi`? **Recommend** `.msi` for the paid Server and MIDI Player (service
   installs) and `.exe` for the desktop apps, but tell me what you prefer.
7. **Translation.** For now the site and guides are English only. To your
   question: **no, Google's free on-the-fly website translator is not an
   option** -- Google limited it to non-commercial sites in 2019 and is ending
   support for it on October 1, 2026; the paid Cloud Translation API needs
   developer integration. Also, any third-party translation widget adds
   scripts and cookies, which would contradict the Privacy Policy. Visitors
   can already use their own browser's built-in translate. **Recommend:**
   translate at build time into static pages (German and Spanish guide sources
   already exist), have a native speaker review, keep the English legal pages
   authoritative, and add `hreflang` links. Questions: which languages, which
   pages (whole site, or guides plus a few key pages), and is translation
   really a blocker for going live? **I would not block go-live on it** --
   ship English, add languages after. The language selector: I will build the
   structure now, but show the control only once a second language exists,
   rather than a one-item drop-down; say if you want it visible anyway.
8. **Guides review.** I scanned the English guides: they mention only
   variable names and "placeholder credentials", no real secrets or hostnames.
   Before publishing, have someone read the System Administrator Guide (built
   from the `INSTALL_*` files) once for anything that should not be public.
9. **Contact-form retention.** The Privacy Policy says messages stay in the
   mailbox "until no longer needed". Keep that wording, or set a fixed period
   (for example 24 months)? **Recommend** keeping it.

### Design notes (proposed, pending the questions above)

- **Matrix entry:** `{app, platform, version, channel, type, target, sha256,
  available}` with `type` = `download` | `store` | `purchase` | `coming-soon`,
  in a `matrix.json` with a `FormatVersion` (CLAUDE.md's compatibility rule).
- **Endpoint:** `GET /download?app=&platform=&version=&v=1` returning a 302
  (works as a plain link, no CORS). It only ever redirects to targets found in
  the matrix; unknown input is rejected. Redirect logs give download counts.
  Because live and preview share one Lambda, it must stay backward-compatible
  with whichever page is live.
- **Signing method:** S3 pre-signed URLs from the Lambda (5 minutes is well
  inside the Lambda role's credential lifetime). Move to CloudFront signed URLs
  only if egress cost or a custom download domain matters later.
- **Cost guard:** add an AWS Budgets alert (about $10/month) before launch.
- **Platform detection:** check Android before Linux; iPhone/iPad and unknown
  platforms get no default plus an honest note ("not available on iOS yet");
  Apple Silicon versus Intel cannot be detected, hence question 6. Platform as
  radio buttons (detected one preselected) rather than a second pull-down.

### Build plan

1. Answer the open questions above (1-6 block the backend; 7-9 do not).
2. **Virtual Church Musician repo:** extend the release workflow to upload
   installers, guides, and `matrix.json` to the downloads bucket (new work
   item there once the questions are settled).
3. **Terraform (this repo):** downloads bucket, Lambda + Function URL, and an
   OIDC role for the Virtual Church Musician release workflow. The CI role
   needs widening again, and you run those applies.
4. **This repo:** picker page, agreement link/box, Documentation section,
   tests, plus the matrix format validator.
5. As they become available: Google Play links, the sales-platform product
   pages, translations.

## Launch Readiness

Everything that must be true before promoting a release to live and cutting
DNS over. Not started as a group; each line names where the work lives.

- [ ] **Merge the Virtual Church Musician branches** `work/License_Match_Privacy_Policy`
  (license: offline, no data collection, KnG Consulting, LLC as licensor, no
  personal details) and `work/todo-pi-build-and-signing`. That repo's full local
  test gate must run first. Until the first is merged, apps built from `main`
  still ship the old license text.
- [ ] **Counsel review** of the License Agreement, Services Terms, and Privacy
  Policy. The Services Terms and the license edits were drafted by me.
- [ ] **Raspberry Pi arm64 packages** (Virtual Church Musician ToDo). The site
  already recommends the Pi 4/5; released Linux packages are amd64 only, and the
  package installer needs internet for `pip`. Either finish this before
  launch or soften the Pi wording until it ships.
- [ ] **Installer signing and notarization** (Virtual Church Musician ToDo),
  and, meanwhile, a per-platform "Installing" note on the Download page. The
  installers are not notarized (macOS shows "damaged"; FAQ has the fix); test
  what Windows shows (SmartScreen) and write it down.
- [ ] **Sales platform chosen** (question 4) and **Google Play listing**
  (question 5), or the paid apps and Android stay "Coming soon" at launch.
- [ ] **Hardware buildout details for the Services page:** what a custom Pi
  build includes (Pi model, power, case, storage, USB audio interface, USB MIDI
  interface), whether the Server/MIDI Player licenses are included in the price,
  warranty and return terms, and a short recommended-hardware list for people
  who supply their own. Until then the page says only "we set it up" and
  "prices are by quote".
- [ ] **About section:** only public facts are on it now. Add background, a
  photo, and any church willing to be quoted.
- [ ] **Publish the guides** after the review in question 8; wire the
  Documentation links to real URLs.
- [ ] **Translation**, only if you decide it must precede launch (question 7).
- [ ] **Go live** (see Blue-Green Deployments): promote a release, swap the
  `www` CNAMEs and apex forwarding at GoDaddy, delete the old buckets.
- [ ] Optional after launch: one blog post per service; per-item pricing once
  you have engagements.

## Blue-Green Deployments

**Status: built and exercised against real AWS.** Pushes to `master` apply
Terraform, upload the site to `releases/<sha>/`, and point
`preview.kng-consulting.com` at it, then stop. **Remaining:** promote a release
to live, cut DNS over at GoDaddy, and tear down the old buckets (listed
below). Not scheduled; expected to be days out. See Launch Readiness.

**How it works (as built):**

- Pushes to `master` (`.github/workflows/deploy-to-aws.yml`): `terraform apply`,
  then `build-and-upload` syncs to `releases/$GITHUB_SHA/` and points the
  preview distribution at it. Nothing user-facing changes.
- **Going live is manual:** Actions -> Deploy to AWS -> Run workflow (on
  `master`) -> approve at the `production-switch` GitHub Environment (required
  reviewer `gwlester`). `switch-live` flips the live distribution's
  `origin_path`, invalidates the cache, and deletes every `releases/*` prefix
  except the new live one and the one before it. It runs only on manual dispatch
  because a push run waiting for approval held the concurrency lock and blocked
  later pushes.
- **Rollback:** `.github/workflows/rollback.yml`, `workflow_dispatch` with a
  `release_sha`; flips `origin_path` back and invalidates. No approval gate.
- **Preview** (`terraform/cloudfront_preview.tf`): a second CloudFront
  distribution aliased to `preview.kng-consulting.com`, same bucket and OAC,
  caching disabled, so the reviewer always sees the release just uploaded. Only
  entries in `live_domain_names` alias the live distribution
  (CloudFront requires each alias on exactly one distribution).
- **Shared script:** `.github/scripts/set_cloudfront_origin_path.sh` does the
  `origin_path` flip for preview, switch-live, and rollback.
- **State:** Terraform state is in the S3 bucket
  `kng-consulting-tfstate-734677164811` (native lockfile), so CI and local runs
  share it.
- **The live distribution has `lifecycle { ignore_changes = [origin] }`**, so
  Terraform never fights the CLI switch. Tradeoff: it also will not notice a
  future change to the bucket or OAC -- remove `ignore_changes` for one apply if
  either is ever replaced. (A related limit: new CloudFront behaviors or origins
  cannot be added to the live distribution through Terraform.)
- **CI lessons, for whoever touches the workflow next:** `hashFiles()` is not
  allowed in a job-level `if` (it silently produced "workflow file issue" and
  zero jobs for weeks); the deploy role's OIDC trust must accept the repo's
  immutable subject claim (`repo:gwlester@<id>/KnG@<id>:...`); the deploy role
  needs read access as well as write access for Terraform's refresh.

**Decisions:** S3 release prefixes plus a CloudFront `origin_path` switch (no
second bucket, no Route 53, DNS stays at GoDaddy); the switch is done by CLI, not
Terraform; a manual smoke test on the preview URL is always required before
approving; retention is the live release plus one previous; the switch needs
explicit approval.

**Pre-existing infrastructure.** Manually created (not IaC-managed), in the
same AWS account, region us-east-2 (Ohio); this Terraform defaults to
us-east-1, and the two do not need to match. `kng-consulting.com`/`.net` are
live there through GoDaddy DNS, so the DNS flip to the new CloudFront
distribution's domain is the actual go-live moment, not any Terraform apply.

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

No name collisions with this Terraform (`kng-consulting-site` bucket,
`kng-github-actions-deploy` role) were found. Gerald tears down the old
infrastructure manually once the new stack is confirmed live, whenever he is
satisfied it is safe to -- not scripted, not run unattended.
