# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
See `Version.MD` for the current base version and `ReleseNotes/` for
per-tag release notes once releases begin.

## [Unreleased]

### Changed

- Downloads: VCM apps are released independently. `publish_release.py` accepts per-app tags (`runner-v1.0.2-a.2`: publishes only that app's files, adds `scope` to the matrix entry, retention counted per app, `deprecate --before <app>-v...` touches only that app); the download Lambda resolves `current`/`previous` per app, accepts per-app tags, and reports each app's own current in the status call. Additive, matrix FormatVersion 1 unchanged; suite tags (`v1.0.2-a.1`) behave as before.
- Download Lambda: new update-check call `GET ?update=1&app=&platform=&channel=stable|beta|any&current=&v=1` for the VCM mobile apps (additive, FormatVersion 1). Answers with the newest release containing the app on the chosen channel and whether it is newer than `current`.
- License-signing and order-fulfillment Lambdas read their secrets from SSM Parameter Store (standard SecureString, free) instead of AWS Secrets Manager; `tools/migrate_secrets_to_ssm.sh` copies existing values.

### Added

- Coming-soon site with product and blog sections.
- AWS deployment workflow (Terraform + S3/CloudFront via GitHub OIDC).
- Working-instructions housekeeping: `CLAUDE.md`, `Prompts/ToDo.md` and
  `Prompts/Done.md`, `Version.MD`, `ReleseNotes/`, `LICENSE`,
  `CONTRIBUTING.md`, this changelog.
- Password-gated alpha/beta downloads for the Server and MIDI Player: the
  password must equal the file's own SHA-256, hashed fresh from S3 on every
  request (never stored, never read from a checksums file), rate-limited
  per source IP. Stable-channel releases of those two apps are unaffected --
  still sold through whatever sales platform is eventually chosen.

### Fixed

- Deploy pipeline: the GitHub Actions deploy role was missing DynamoDB
  permissions for the new password-attempt rate-limit table, so
  `terraform apply` failed and the password-gated downloads feature never
  actually reached the site (the picker still showed the old ungated
  behavior and download requests errored instead of prompting for a
  password).
