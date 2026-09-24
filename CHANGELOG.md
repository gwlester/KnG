# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
See `Version.MD` for the current base version and `ReleseNotes/` for
per-tag release notes once releases begin.

## [Unreleased]

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
