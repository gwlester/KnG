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
   available (current and current - 1). Until the first stable release exists,
   every release is public and labelled **Beta**.
4. **Button.** Enabled only when an app and a platform are chosen. Helper text
   when disabled ("Choose an app and a platform"). The label follows the entry
   type: Download, Get it on Google Play, Buy, or Coming soon (disabled).
5. **License.** A notice and link beside the button ("By downloading you agree
   to the License Agreement"). No checkbox on the page: acceptance is recorded
   by the apps on first use, and by the checkout for paid products (open
   question 1).
6. **Documentation** (below the picker): two cards, User Manual and System
   Administrator Guide, each with *Read online* (HTML) and *Download PDF*, for
   the selected version, marked "applies to vX.Y.Z". English only for now (see
   see Decisions: translation). SHA256SUMS and the release notes sit beside them. The
   guides are also linked from the product page and the Services page.
7. **Install notes** per platform (see Launch Readiness; the installers are
   not signed or notarized).

### Decisions (settled)

- **Who can download:** the four free apps (desktop and mobile) are free.
  Server and MIDI Player are paid, sold through a sales platform (leaning
  FastSpring, still evaluating). Until it is chosen they show "Coming soon".
- **Android:** mobile apps are distributed through Google Play only.
- **Desktop installers:** stored in a private S3 bucket; a Lambda hands out
  signed URLs valid for 5 minutes, generated at click time (so no one-week
  links). Retention: current release plus the previous one.
- **The matrix** (which file each app/platform/version maps to) is private and
  is never stored in this public repository or shipped to the browser. No
  AppConfig; a `matrix.json` object in the private bucket instead. The
  picker's *options* (which apps exist on which platforms) are embedded in the
  page and public; only *targets* (file locations, purchase URLs) and
  unlisted betas stay server-side.
- **Ownership:** the Virtual Church Musician release workflow uploads the
  installers, the guides, and the matrix (same AWS account, through an OIDC
  role); this repo owns only the picker page and the Lambda.
- **Versions and betas:** every release so far is a `-b.N` prerelease, so until
  a stable release exists the public sees the latest releases labelled "Beta".
  Matrix entries still carry a `channel` (stable | beta) so betas can be
  hidden once a stable release exists (decide that at the first stable release).
- **One EULA:** a single License Agreement covers free and paid apps. The free
  apps already make each person accept it on first use. The Download page links
  it; it does not add a checkbox.
- **Desktop file details:** the macOS `.dmg` is a universal build (one Mac
  option). Both `.exe` and `.msi` exist for the Windows apps.
- **Documentation:** public (no purchase needed), HTML plus PDF only (no
  Markdown zip), hosted at stable readable URLs (`/docs/<version>/...` plus a
  `latest` alias), no signing needed. The guides ship inside the installers
  already, so air-gapped sites have them. Gerald will read the System
  Administrator Guide once for anything that should not be public (my scan
  found only variable names and "placeholder credentials").
- **Translation:** English only at launch. Translations come afterwards, as
  build-time static pages (German and Spanish guide sources already exist),
  reviewed by a native speaker; the English legal pages stay authoritative.
  Google's free website translator is not an option (non-commercial only since
  2019, support ends October 1, 2026), and any third-party translation widget
  would add scripts and cookies that contradict the Privacy Policy. A
  language selector is built into the page structure but shows only once a
  second language exists. **Translation does not block going live.**
- **Contact-form retention:** keep the Privacy Policy wording ("until no longer
  needed").
- **Typos:** fix them whenever seen, in any file.

### Open questions

1. **Free apps, EULA, and the "purchased" checkbox.** Please confirm my reading
   of "keep it simple": no agreement checkbox on the Download page, only the
   notice and link. Separately, the apps' first-use screen has two boxes: "My
   congregation has purchased a copy of the Virtual Church Musician for use"
   and "I have read and agree to the ... License Agreement". That matches
   "free to download, but it connects to a Server that is paid", but "free"
   without that context could mislead a church. **Recommend** wording the
   Free label and the FAQ as "free to download; connects to your church's
   Server" (the FAQ already says the free apps need the Server). OK to add that
   to the product page, Download page, and FAQ?
2. **License enforcement is not on the Virtual Church Musician ToDo.** I looked
   at `main` and at my branch: the tracked items are the temp-directory
   cleanup, read-only install tree, self-hosted runners, Windows end-to-end
   tests, and the first-use configuration GUI, plus the Pi and signing items I
   added. Nothing covers issuing or checking a *purchase* (the app only records
   license acceptance). Did you mean acceptance (done), or is a purchase-check
   item missing? If missing, want me to draft it? **Recommended approach for a
   Server that must run air-gapped:** the sales platform's fulfillment calls a
   small issuing service (FastSpring supports remote-server and script
   fulfillments and third-party license integrations); the customer receives a
   *signed license file* that the Server verifies offline with an embedded
   public key. Nothing phones home. Trade-off: an offline license cannot be
   revoked remotely, so refunds are handled by policy rather than technology.
   Decisions the item must record: the license unit (per congregation? per
   Server? number of MIDI Players), perpetual versus term, and what the free
   clients check.
3. **Google Play is not a tracked item either.** It appears only as a note
   inside the signing item I added. Want a "Google Play Release" item (upload
   key and app bundle instead of the debug-signed APK, Play App Signing, store
   listing, privacy policy URL, content rating, a Data safety form declaring
   that no data is collected, and closed testing if the account needs it)?
   Confirm all four mobile apps go on Play: Template Editor, Service Builder,
   Service Runner, and Security.
4. **FastSpring evaluation.** What would settle it? Suggested checklist:
   Merchant-of-Record and tax handling for the countries you sell to; fees and
   payout schedule; remote-server or script fulfillment able to deliver your
   license file; EULA acceptance captured at checkout; how refunds (30 days in
   the License Agreement) are processed; hosted versus embedded storefront; a
   test mode. Any hard requirement I am missing (for example, sales to
   churches by purchase order or invoice)? When do you need the decision --
   it blocks the paid rows of the picker and the sales-platform line in Launch
   Readiness.
5. **Windows and Linux picker details** (recommendations; say if you object).
   Show one "Windows" choice that downloads the `.exe` for the four desktop
   apps and the `.msi` for the Server and MIDI Player (service installs), with
   a small "other installer type" link for the alternative. For Linux, add an
   architecture choice (amd64 or arm64 / Raspberry Pi) for the Server and MIDI
   Player once arm64 packages exist. Mac is a single choice.
6. **Paid products during beta.** Every release is still a beta. Will the
   Server and MIDI Player be sold while in beta (with wording and perhaps a
   discount), or stay "Coming soon" until a stable release? That decides what
   the launch looks like.

### Design notes (proposed)

- **Matrix entry:** `{app, platform, arch, version, channel, type, target,
  sha256, available}` with `type` = `download` | `store` | `purchase` |
  `coming-soon`, in a `matrix.json` with a `FormatVersion` (CLAUDE.md's
  compatibility rule). `arch` is there for the Linux arm64 case.
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
  Apple Silicon versus Intel is moot (universal `.dmg`). Platform as radio
  buttons (detected one preselected) rather than a second pull-down.

### Build plan

1. Answer the open questions above (1 is a wording change; 2-4 gate the paid
   and Android rows; 5-6 are quick).
2. **Virtual Church Musician repo:** extend the release workflow to upload
   installers, guides, and `matrix.json` to the downloads bucket. Related items
   there: license issuance/enforcement (question 2), Google Play release
   (question 3), Pi arm64 packages, signing and notarization.
3. **Terraform (this repo):** downloads bucket, Lambda + Function URL, and an
   OIDC role for the Virtual Church Musician release workflow. The CI role
   needs widening again, and you run those applies.
4. **This repo:** picker page, agreement notice, Documentation section, tests,
   plus the matrix format validator. The free-download rows can ship before the
   paid and Android rows.
5. As they become available: Google Play links, the sales-platform product
   pages, then translations.

## Launch Readiness

Everything that must be true before promoting a release to live and cutting
DNS over. Not started as a group; each line names where the work lives.

- [ ] **Decide where internal planning lives.** `gwlester/KnG` is a *public*
  repository, so this file and Done.md (sales-platform choice, licensing model,
  hardware plans, publisher discussions) are visible to anyone. Options: keep
  going but never name partners or prices here; move `Prompts/` to a private
  repository; or make this repository private (GitHub Actions minutes are then
  limited). **Recommend** at least keeping partner names, prices, and contract
  terms out of the repo now; the publisher below is deliberately unnamed.
- [ ] **Publisher editions:** decide whether they are in scope for launch
  (**recommend not**; see the item below), but settle the edition-ID and
  bundle-signing hooks while license enforcement is designed.
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
- [ ] **Sales platform chosen** (leaning FastSpring; open question 4), with
  **license issuance/enforcement** built (open question 2), and a **Google Play
  listing** (open question 3) -- or the paid apps and Android stay "Coming
  soon" at launch (open question 6).
- [ ] **Hardware buildout details for the Services page:** what a custom Pi
  build includes (Pi model, power, case, storage, USB audio interface, USB MIDI
  interface), whether the Server/MIDI Player licenses are included in the price,
  warranty and return terms, and a short recommended-hardware list for people
  who supply their own. Until then the page says only "we set it up" and
  "prices are by quote".
- [ ] **About section:** only public facts are on it now. Add background, a
  photo, and any church willing to be quoted.
- [ ] **Publish the guides** after Gerald's read of the System Administrator
  Guide; wire the Documentation links to real URLs.
- [ ] **Go live** (see Blue-Green Deployments): promote a release, swap the
  `www` CNAMEs and apex forwarding at GoDaddy, delete the old buckets.
- [ ] After launch (not blockers): German and Spanish translations; one blog
  post per service; per-item pricing once you have engagements.

## Publisher (White-Label) Editions

**Status: idea recorded; nothing built.** Beyond custom versions for individual
churches, KnG will also customize and brand Virtual Church Musician for a
publishing house, and lock features, for example a branded edition (the
publisher's name, icons, and colors) that only loads that publisher's own
bundles. (The publisher is deliberately not named here: this repository is
public.) Customers cannot change the code; KnG, as the owner, can.

### Why this needs its own plan

A one-off church customization is a project. A publisher edition is an ongoing
product line: every release must be built, tested, signed, and delivered once
per edition, and it needs contract terms that the current License Agreement
(licensor to end user) does not cover.

### Recommendations

- **One codebase, build-time "editions," no forks.** An edition is a small
  configuration (edition ID, brand assets and strings, feature switches,
  allowed bundle signers) applied at build. Forks would multiply every fix.
- **Lock by signature, not by filename.** The Server accepts only bundles
  signed by keys the edition allows (for example an Ed25519 signature the
  publisher's tooling adds to each bundle). "Their bundles only" then cannot
  be bypassed by renaming a file.
- **Put the edition ID in the license file** (see license enforcement in the
  Downloads open questions). A branded edition cannot then be activated as the
  standard product or as another publisher's edition, and vice versa. This is
  cheap to design in now and expensive to retrofit.
- **Separate identities per edition:** application ID and package name, icons,
  installer names, Play listing, and signing keys, so editions can coexist on
  one machine and each publisher owns its brand.
- **Contract first, with counsel:** an OEM / white-label agreement covering
  trademark licenses in both directions, who is the licensor of the end-user
  EULA (KnG's, a publisher addendum, or the publisher's own), revenue model,
  support tiers, exclusivity, and termination. Not covered by any current
  document.
- **Site copy:** describe the offer generically ("branded and locked editions
  for publishers") on the Services page. Name a publisher only with their
  written permission.

### Questions

1. Is a conversation with a publisher already under way, or is this a
   capability you want to offer? (It sets the urgency, and whether I draft
   Services-page copy now.)
2. **What exactly is locked?** Loading catalog definitions, music files, or
   both? Can a church still add its own hymns and files, or only the
   publisher's? Can churches still build their own services and templates?
3. **What is branding?** Name, icons, colors, splash and About text, license
   text, support contact, default language, installer names? Does the
   publisher expect its own website download page, or does KnG host it?
4. **Who sells and supports?** Publisher sells and KnG is paid a royalty, or
   KnG sells directly? Who is first-line support for end users?
5. **Who is the licensor for these editions?** KnG under its own EULA, a
   publisher addendum, or the publisher's EULA?
6. **Pricing model:** a setup fee plus per-license royalty, revenue share, an
   annual maintenance fee, or a mix?
7. **Distribution:** for mobile, does the publisher publish under its own
   Google Play account (recommended, since it owns the brand), or does KnG?
8. **Release cadence:** does the publisher's edition track every KnG release
   or only selected ones? (This drives the per-edition build cost.)

### Dependencies

Virtual Church Musician repo: an "Editions" work item (build-time edition
config, bundle signing and verification, per-edition packaging) plus the
license-enforcement item. KnG repo: Services-page copy after question 1, and
possibly a Terms addendum. Counsel: the agreement above.

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
