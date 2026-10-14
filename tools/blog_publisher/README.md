# Monthly blog publisher

Runs automatically via `.github/workflows/publish-blog-post.yml`, first
Monday of the month. Picks the lowest-numbered topic still in
`content/pending-blogs/`, moves its base post into `content/blog/` with
today's date, regenerates the site (`src/build_blog.py`), and fills in
`{{post_url}}` on every teaser variant for that topic.

## What gets automated vs. staged

- **Dev.to**: posted live via its API, if a `-devto.md` variant exists
  for the topic and the `DEVTO_API_KEY` repository secret is set.
  Without that secret, its filled-in content is staged in the workflow's
  step summary instead (same as the manual channels below), so nothing
  silently fails to post.
- **Everything else** (LinkedIn, Facebook, MeWe, Reddit, Hacker News,
  etc.): staged only, never posted automatically. Facebook killed
  personal-profile and group posting years ago; MeWe's API is a gated
  beta; the rest (Reddit, Hacker News, Discord, Indie Hackers, Peerlist)
  are communities that explicitly expect a real person posting, not a
  bot, per `Prompts/BlogPromotionChannels.md`. The ready-to-paste text
  for each lands in the GitHub Actions run's step summary.

## What happens to the live site

The workflow commits the published post and pushes to `master`, which
triggers `deploy-to-aws.yml` automatically and updates **preview**. It
then queues that same workflow's live-switch job via
`gh workflow run deploy-to-aws.yml` -- that job still waits for the
`production-switch` environment's required-reviewer approval, same as
any other deploy. This workflow does not and cannot bypass that gate;
it only saves the step of triggering it by hand.

## Setup needed

- Add a `DEVTO_API_KEY` repository secret (Dev.to -> Settings -> Extensions
  -> DEV API Keys) to enable automatic Dev.to cross-posting. Without it,
  Dev.to content is staged like every other channel.

## Running it by hand

```
python3 tools/blog_publisher/publish_next_post.py [--today YYYY-MM-DD] [--dry-run]
```

`--dry-run` does everything except write/delete files and post to
Dev.to -- use it to preview what the next run would publish. The
workflow itself can also be run manually (`workflow_dispatch`) with its
own `dry_run` input, which skips the commit/push/live-switch-queue
steps too.
