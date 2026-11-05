# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
See `Version.MD` for the current base version and `ReleseNotes/` for
per-tag release notes once releases begin.

## [Unreleased]

### Changed

- Download picker: the "Current release" and "Previous release" labels now show the selected app's own releases (the status call takes an optional `app`), so they match what the Download button serves (#6).

- Downloads no longer need an access code: VCM Server and MIDI Player download like every other app, on every channel, and the license files are what protect them (decided 2026-11-04). The download Lambda drops the purchase / Test Drive code check and its per-IP rate limit; a POST from an older cached page is answered with the address as JSON and its body ignored. The update-check reply keeps `requires_access_code` (now always false) so existing clients still parse it. The page loses the Access code field; the order and Test Drive result boxes still show the reference and activation key, which are for activating the license in the Admin app. No FormatVersion change. The now-unused `PASSWORD_REQUIRED_APPS`, `RATE_LIMIT_*` and `LICENSE_ISSUANCE_TABLE` settings in `terraform/downloads.tf` can be removed in a later cleanup.
- Downloads page: new "Release channel" selector (Stable releases only, default; Stable and beta; Stable, beta and alpha) so testers can reach alphas and betas once a stable release exists. The download Lambda's status, download and document calls accept `channel=stable|beta|any` (additive, FormatVersion 1 unchanged; no channel means stable, as before) and resolve `current`/`previous` per app on that channel. An unknown channel is a 400.
- FindCache log upload accepts API version 3: the body is JSON `{"description", "log"}` and the description (1..1000 characters) is required. Each upload also writes a `<id>.json` record (id, time, version, device, description, log key) beside the `.txt`. Version 2 is still accepted with an empty description until the app update is out. New daily digest Lambda `kng-findcache-digest` emails one summary (reason, version, device, `aws s3 cp` command) to the contact inbox. A log with no `.json` record (uploaded before records existed) is listed too, from its time and size. Needs a local `terraform apply` first (new EventBridge permissions for the deploy role).
- FindCache log upload is now API version 2: the log must end with the app's own "Uploading debug log: FindCache <version>, Android <os> (API n), <device>" entry, matching `X-App-Version`, or it is rejected (400). Version 1 is told to update the app. The upload function is capped at 5 concurrent runs (needs a `terraform apply`).
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
