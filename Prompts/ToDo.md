# To Do List

## Build a Blog Pipeline

**Status: design decided (2026-09-15), not yet implemented.**

Today the blog is one hardcoded `<article>` inside `www/index.html`'s
`#blog` section — no archive, no per-post pages, no way to add a post
without hand-editing the homepage.

**Decided approach:**

- Posts are authored as Markdown files with front matter (title, date,
  slug) rather than hand-written HTML.
- A Python build script (fits the already-reserved `src/` directory) runs
  as a step in `deploy-to-aws.yml`, before the S3 sync, and renders:
  - `www/blog/<slug>.html` — one page per post, from a shared template
    matching the site's existing header/footer/`styles.css`.
  - `www/blog/index.html` — an archive listing every post, newest first.
- Each post gets its own URL (`/blog/<slug>.html`), not just an entry on a
  scrolling page — independently linkable/shareable and indexable by
  search engines.
- The homepage's `#blog` section becomes just the 1-2 most recent posts
  (rendered by the same script) with a "View all posts" link to
  `/blog/index.html`; the top-nav "Blog" link points there once it exists,
  replacing the `#blog` anchor.

**Open implementation questions, not yet decided:**

- Markdown library choice for the Python script (stdlib has none; would
  add a dependency such as `markdown` or `mistune` — first real Python
  dependency in this repo).
- Where post source files live (e.g. a top-level `content/blog/` next to
  `www/`, `src/`, `terraform/`).
- Whether the build step needs a "preview locally" command too (so a post
  can be checked before pushing), not just the CI-time render.

## Reorganize Directory Structure

**Status: done (2026-09-14).** `www/`, `src/`, and `terraform/` created;
`index.html`/`coming-soon.html`/`styles.css` moved into `www/`;
`deploy-to-aws.yml`'s sync step and `README.md` updated to match.

Split the repo into `terraform/`, `www/`, and `src/` (for any Python Lambdas we
might need). Meta/workflow files (`README.md`, `CLAUDE.md`, `LICENSE`,
`CONTRIBUTING.md`, `CHANGELOG.md`, `Version.MD`, `Prompts/`, `ReleseNotes/`,
`.github/`) stay at the repo root — they aren't deployed site content.

**Depends on this workflow change, not optional:** `deploy-to-aws.yml`'s
"Sync site files to S3" step currently runs `aws s3 sync . s3://$BUCKET
--delete` against the repo root with a long exclude list. Once site files
move to `www/`, that step must become `aws s3 sync www
s3://$S3_BUCKET_NAME --delete` (the exclude list goes away entirely). Land
the directory move and this workflow edit in the same commit/branch so
`main` is never left with a workflow pointed at the wrong path.

Also set the `TERRAFORM_WORKING_DIRECTORY` GitHub repo variable to
`terraform` once that directory exists, rather than relying on the
workflow's auto-detect-by-`find` fallback.

## Suggest AWS Components

**Status: decided (2026-09-14)**, implemented in the Terraform below.
Domains confirmed: `kng-consulting.com` (primary) plus alias
`kng-consulting.net`, both with `www` subdomains.

### Goal

1. Minimize AWS cost
2. Minimize GitHub cost (already effectively free — this repo is public, so
   standard GitHub Actions runners are unlimited/free; treat this goal as
   "don't run deploy jobs for no reason," not an actual dollar concern)

### Context (decided 2026-09-14)

- Domain is registered at **GoDaddy**; DNS stays at GoDaddy (no Route53
  hosted zone) to skip the ~$0.50/mo zone cost. GoDaddy remains the source
  of truth for DNS records.
- No dynamic/backend behavior exists yet — the site is fully static. The
  `src/` (Lambda) directory is for future use, not an immediate need,
  **except** the coming-soon page already has a Contact section with no
  working submit action yet — a contact-form handler is the most likely
  first real use of `src/`, if/when that's built.

### Recommended components

- **S3 bucket** (private — no public bucket policy/static-website-hosting
  endpoint) holding `www/`'s contents, read only via CloudFront using
  Origin Access Control (OAC). Storage + request cost for a small site is
  pennies/month.
- **ACM certificate** in `us-east-1` (required region for CloudFront),
  DNS-validated. Since DNS lives at GoDaddy, Terraform can't create the
  validation record automatically — plan to `terraform apply`, read the
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

### Open question

None currently blocking — the above is enough to start the Terraform work
below. Revisit if the contact form (or anything else dynamic) actually gets
built, since that adds a real Lambda/API Gateway cost line (still small,
but not zero).

## Create Terraform for AWS Components

**Status: code written and `terraform validate`-clean (2026-09-14); not yet
applied.** Written under `terraform/` (`versions.tf`, `providers.tf`,
`variables.tf`, `oidc.tf`, `s3.tf`, `acm.tf`, `cloudfront.tf`, `outputs.tf`,
`README.md`). Covers: GitHub OIDC provider + a scoped deploy role,
private S3 bucket + CloudFront (OAC) + ACM cert for all four domains.

**Not moving this to Done.md yet** — applying real AWS infrastructure
(and the IAM trust policy it creates) needs your own AWS credentials and a
deliberate decision, not something to run unattended. The one-time
bootstrap sequence (create the cert, add its validation CNAMEs at GoDaddy,
full apply, then add the `www` CNAMEs + apex forwarding at GoDaddy, then
set the four GitHub repo variables) is written out step by step in
`Prompts/AWS_Deployment.md`. Move this to Done.md once you've run it and
the site is actually live behind CloudFront.

Implement the components above under `terraform/` once the directory
reorganization lands. Suggested resource breakdown: `s3.tf` (bucket +
bucket policy for OAC), `acm.tf` (certificate + output the DNS validation
record for manual entry at GoDaddy), `cloudfront.tf` (distribution + OAC),
`variables.tf`/`outputs.tf` (domain name(s), bucket name, distribution ID —
the latter two feed `S3_BUCKET_NAME` and `CLOUDFRONT_DISTRIBUTION_ID` back
into the GitHub repo variables the deploy workflow already reads).
