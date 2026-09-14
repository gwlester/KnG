# KnG
KnG website, Terraform, and site files.

## Layout

- `www/` — the static site that gets deployed (HTML, CSS, ...)
- `terraform/` — AWS infrastructure (S3, ACM, CloudFront, the GitHub Actions
  deploy role) — see `terraform/README.md` for setup
- `src/` — Python Lambdas, if/when any are needed (none yet)

## Preview locally

Open `www/index.html` from the repository root in a browser, or serve the
`www/` directory with a simple static file server.

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
