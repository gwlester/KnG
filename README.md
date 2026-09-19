# KnG
KnG website, Terraform, and site files.

## Layout

- `www/` — the static site that gets deployed (HTML, CSS, ...); `www/blog/`
  is generated, see below
- `content/blog/` — blog posts, as Markdown with front matter
- `content/legal/` — privacy policy, services terms, and license agreement
  (Markdown); `content/faq.md` — the Support/FAQ page. `build_blog.py`
  renders them to `www/<slug>.html` and refreshes the shared header/footer
  (between the `SITE_HEADER`/`SITE_FOOTER` markers) on every hand-written page
- `src/` — Python: `build_blog.py` renders `content/blog/` into
  `www/blog/`; `contact_handler/` is the contact-form Lambda
- `content/downloads/` — `options.json` (public picker options for the Download
  page) and `artifact_map.json` (which Virtual Church Musician release assets are
  published where); `src/download_handler/` is the download Lambda and
  `src/publish_release.py` plans a release publication and
  `src/verify_signatures.py` detects whether its installers are signed, both run by
  the manual `publish-downloads.yml` workflow. `publish_release.py check-live` is
  the go-live gate that `switch-live` runs: no unsigned release may be listed
- `tests/` — `python3 -m unittest discover -s tests`
- `terraform/` — AWS infrastructure (S3, ACM, CloudFront, the GitHub Actions
  deploy role) — see `terraform/README.md` for setup

## Preview locally

```
pip install -r requirements.txt
python3 src/build_blog.py
```

Then open `www/index.html` from the repository root in a browser, or serve
the `www/` directory with a simple static file server. Re-run
`build_blog.py` after adding or editing a post under `content/blog/`.

## GitHub Actions AWS deployment

The repository includes `.github/workflows/deploy-to-aws.yml` for a simple AWS deployment flow:

- runs on pushes to `main` and on manual dispatch
- uses GitHub OIDC to assume an AWS deployment role
- applies Terraform first when `.tf` files are present
- syncs `www/`'s contents to S3
- optionally invalidates CloudFront when a distribution ID is configured

Configure these GitHub repository variables before running the workflow:

- `AWS_REGION`
- `AWS_DEPLOY_ROLE_ARN`
- `S3_BUCKET_NAME`

Optional variables:

- `TERRAFORM_WORKING_DIRECTORY`
- `CLOUDFRONT_DISTRIBUTION_ID`
