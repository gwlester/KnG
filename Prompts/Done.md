# Completed Work Items

## Build a Blog Pipeline

Replaced the single hardcoded `<article>` in `www/index.html`'s `#blog`
section with a real pipeline:

- Posts are authored as Markdown with front matter (`title`, `date`,
  optional `summary`/`author`) under `content/blog/*.md`.
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
