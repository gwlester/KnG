# Completed Work Items

## Reorganize Directory Structure

Split the repo into `terraform/`, `www/`, and `src/` (for any Python
Lambdas). Meta/workflow files (`README.md`, `CLAUDE.md`, `LICENSE`,
`CONTRIBUTING.md`, `CHANGELOG.md`, `Version.MD`, `Prompts/`,
`ReleseNotes/`, `.github/`) stayed at the repo root — they aren't deployed
site content.

- Moved `index.html`, `coming-soon.html`, `styles.css` into `www/`.
- Updated `deploy-to-aws.yml`'s "Sync site files to S3" step from
  `aws s3 sync . s3://$BUCKET --delete` (with a long exclude list) to
  `aws s3 sync www s3://$S3_BUCKET_NAME --delete`, landed in the same
  change as the move so `main` was never left with a workflow pointed at
  the wrong path.
- `README.md` updated to match the new layout.

(Completed 2026-09-14. Note: the `TERRAFORM_WORKING_DIRECTORY` GitHub repo
variable still needs to be set to `terraform` as part of the still-open
AWS bootstrap in `Prompts/AWS_Deployment.md` -- not part of this item.)

## Suggest AWS Components

Decided 2026-09-14. Domains confirmed: `kng-consulting.com` (primary) plus
alias `kng-consulting.net`, both with `www` subdomains. Implemented in
`terraform/` -- see the "Create Terraform for AWS Components" item in
`Prompts/ToDo.md` for that item's own status.

### Goal

1. Minimize AWS cost
2. Minimize GitHub cost (already effectively free — this repo is public, so
   standard GitHub Actions runners are unlimited/free; treated as "don't
   run deploy jobs for no reason," not an actual dollar concern)

### Context

- Domain is registered at **GoDaddy**; DNS stays at GoDaddy (no Route53
  hosted zone) to skip the ~$0.50/mo zone cost. GoDaddy remains the source
  of truth for DNS records.
- No dynamic/backend behavior exists yet — the site is fully static. The
  `src/` (Lambda) directory is for future use, not an immediate need,
  **except** the coming-soon page already has a Contact section with no
  working submit action yet — a contact-form handler is the most likely
  first real use of `src/`, if/when that's built.

### Components chosen

- **S3 bucket** (private — no public bucket policy/static-website-hosting
  endpoint) holding `www/`'s contents, read only via CloudFront using
  Origin Access Control (OAC). Storage + request cost for a small site is
  pennies/month.
- **ACM certificate** in `us-east-1` (required region for CloudFront),
  DNS-validated. Since DNS lives at GoDaddy, Terraform can't create the
  validation record automatically — `terraform apply`, read the
  validation CNAME from the Terraform output, and add it in GoDaddy by
  hand (one-time, rarely changes). Free.
- **CloudFront distribution** in front of the bucket, `PriceClass_100`
  (North America + Europe edge locations only) unless there's a reason to
  expect a wider audience — cuts cost vs. `PriceClass_All` with no
  practical latency difference for a US-based audience. Custom domain
  alias(es) for the apex and/or `www` subdomain, backed by the ACM cert
  above.
- **DNS at GoDaddy:** point `www.<domain>` at the CloudFront distribution's
  domain name via CNAME. For the apex domain, GoDaddy doesn't support a
  Route53-style ALIAS record at the zone root — use GoDaddy's domain
  forwarding (apex → `www`) unless GoDaddy's DNS product supports CNAME
  flattening, which is worth a quick check when this is actually built.
- **No Lambda/Lambda@Edge/API Gateway yet.** If/when the contact form needs
  real handling, prefer a plain Lambda behind a small API Gateway (or a
  Function URL) over Lambda@Edge — simpler and this isn't a
  request-manipulation-at-the-edge use case. If a future need is just
  redirects/header rewrites, CloudFront Functions is cheaper than
  Lambda@Edge ($0.10 vs $0.60 per million invocations) and should be
  preferred for that narrower case.
- **CloudFront invalidations:** first 1,000 paths/month are free, trivial
  for a site this size — not a cost concern, just invalidate `/*` on
  deploy as the existing workflow already plans to.

Revisit if the contact form (or anything else dynamic) actually gets
built, since that adds a real Lambda/API Gateway cost line (still small,
but not zero).

## Build a Blog Pipeline

Replaced the single hardcoded `<article>` in `www/index.html`'s `#blog`
section with a real pipeline:

- Posts are authored as Markdown with front matter (`title`, `date`,
  optional `summary`/`author`/`slug`) under `content/blog/*.md`. `slug`
  defaults to the filename (so URLs stay stable across CI runs and across
  title edits) but can be set explicitly to decouple the URL from the
  filename -- e.g. so a file can be renamed for tidiness without breaking
  a bookmarked `/blog/<slug>.html` link. Two posts resolving to the same
  slug is a build error, not a silent overwrite.
- `src/build_blog.py` (dependency: `markdown`, in `requirements.txt`)
  renders each post to `www/blog/<slug>.html` and an archive at
  `www/blog/index.html`, both sharing the site's header/nav/footer and
  `styles.css`. It also rewrites `www/index.html`'s latest-posts block
  (between `<!-- BLOG_LATEST_START -->`/`END` markers) with the 2 most
  recent posts plus a "View all posts" link.
- `deploy-to-aws.yml` runs `pip install -r requirements.txt` and
  `python3 src/build_blog.py` before the S3 sync, so the deployed site
  always reflects current `content/blog/`.
- Top-nav "Blog" link and the hero's "Read the Blog" button now point at
  `blog/index.html` instead of the old `#blog` anchor.
- Migrated the existing post to
  `content/blog/designing-software-that-earns-its-place.md`; ran the
  script locally and verified `www/index.html`, `www/blog/index.html`,
  and the post page all serve correctly (200 OK via a local static
  server) with working navigation between them.

Resolved the three open implementation questions from the design pass:
Markdown library is `markdown` (stdlib has none); post sources live at
`content/blog/`; no separate preview script needed -- running
`build_blog.py` locally *is* the preview (documented in `README.md`).

## Create Terraform for AWS Components

Completed 2026-09-18. `terraform/` (`versions.tf`, `providers.tf`,
`variables.tf`, `oidc.tf`, `s3.tf`, `acm.tf`, `cloudfront.tf`,
`cloudfront_preview.tf`, `contact.tf`, `outputs.tf`, `README.md`) is applied
to AWS account 734677164811: GitHub OIDC provider and scoped deploy role,
private S3 bucket + live and preview CloudFront distributions (OAC), and an
ACM certificate for all five names. State lives in the S3 bucket
`kng-consulting-tfstate-734677164811` (native lockfile), so CI's
`terraform apply` shares it with local runs. The one-time bootstrap is
recorded step by step in `Prompts/AWS_Deployment.md`. The DNS cutover of the
live `www` CNAMEs/apex forwarding is tracked under "Blue-Green Deployments"
in ToDo.md, not here.

## Redesign Site and Add Contact Form

Completed 2026-09-18. Multi-page site (Home, Virtual Church Musician,
Download, Blog, Contact) with a shared navy/amber theme; `build_blog.py`
emits the same header/footer. The contact form posts JSON
(`FormatVersion: 1`, honeypot field) to a Lambda Function URL
(`src/contact_handler/handler.py`, `terraform/contact.tf`) that emails
`inquiries@kng-consulting.com` through SES; unit tests in `tests/`. The
Download page lists the real app/platform matrix but its links are disabled
until installers have a public host (the Virtual Church Musician repo is
private).

## Virtual Church Musician HTML Page Changes

Completed 2026-09-18. Cards now run Template Editor, Service Builder,
Service Runner, Admin and Security, Server, MIDI Player; the workflow pills
were replaced with Free / Paid labels (the four clients are free, Server and
MIDI Player are paid); each card has its app icon (192 px PNGs under
`www/img/apps/`, resized from the Virtual Church Musician artwork). The home
page text and the Download page's availability table use the same order.

## Privacy Policy and License Pages

Completed 2026-09-18. `content/legal/*.md` is rendered by
`src/build_blog.py` into `www/privacy.html` and `www/license.html`, both
linked from every footer. The privacy policy states that the apps send no
information to KnG and that the website has no accounts, cookies, or
analytics. The license is a copy of Virtual Church Musician's
`licenses/agreement.md` (dated 2026-08-29) with its blanks filled from
`license_config.json`, the personal street address removed, and the support
contact set to `inquiries@kng-consulting.com`. `tests/test_legal_pages.py`
guards against the personal details reappearing.
