# KnG
KnG website, Terraform, and site files.

## Layout

- `www/` — the static site that gets deployed (HTML, CSS, ...); `www/blog/`
  is generated, see below
- `content/blog/` — blog posts, as Markdown with front matter
- `content/legal/` — privacy policy and license agreement (Markdown);
  `build_blog.py` renders them to `www/privacy.html` and `www/license.html`
- `src/` — Python: `build_blog.py` renders `content/blog/` into
  `www/blog/`; `contact_handler/` is the contact-form Lambda
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
