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
