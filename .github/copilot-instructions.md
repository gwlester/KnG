# KnG Instructions

## Working Practices

- Prefer the smallest root-cause fix consistent with the existing site and infrastructure abstractions.
- Before editing a tracked work item, use an isolated `work/<work-item-name>` branch.
- Never commit, revert, or overwrite unrelated user changes.
- Add focused validation for changed behavior and run the full available validation before closing a work item.
- Keep user-facing documentation synchronized with implementation changes.
- Use ASCII by default and preserve the repository's existing style.
- Do not commit changes unless the user requests it or the established work-item or release workflow requires it.

## Work Item Tracking

When `Prompts/ToDo.md` and `Prompts/Done.md` exist:

- Treat the first incomplete `##` section in `Prompts/ToDo.md` as the current work item.
- Keep the section in `Prompts/ToDo.md` until implementation, tests, and documentation are complete.
- Move the completed section to `Prompts/Done.md` only after validation passes.

## Compatibility and Infrastructure

- Every JSON or API contract change requires an explicit `FormatVersion` or `X-API-Version` compatibility decision.
- Changes to existing databases require a versioned migration; keep the base schema current for new databases, but do not use it instead of a migration.
- Validate Terraform changes before deploying them, and preserve the AWS OIDC deployment model in `.github/workflows/deploy-to-aws.yml` unless the task explicitly changes it.

## Releases

When `Version.MD` and `ReleseNotes/` are introduced:

- Advance the base version only as part of a release. Use sequential `vX.Y.Z-a.N` or `vX.Y.Z-b.N` prerelease tags.
- Prepare release notes at `ReleseNotes/<exact-tag>.md`.
- Use a `release/vX.Y.Z` branch only for release-note changes and the matching top-level README download link.
- Stop for explicit user approval before merging a release branch, pushing a release tag, or publishing a GitHub Release.