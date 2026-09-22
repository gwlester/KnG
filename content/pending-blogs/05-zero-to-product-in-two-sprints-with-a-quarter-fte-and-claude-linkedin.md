---
platform: LinkedIn
pairs_with: 05-zero-to-product-in-two-sprints-with-a-quarter-fte-and-claude.md
---

**A quarter of one person's time, two sprints, ten shipped applications.**
Four desktop apps, four React Native companions, and the two servers
behind them -- every desktop app and both servers cross-platform for
Windows, macOS, and Linux from day one. Here's the part that actually made
the arithmetic work.

It wasn't that AI assistance made the human faster at the same tasks. It's
that almost none of the available hours went to the tasks an AI pair
handles well -- boilerplate, first-draft tests, routine documentation, and
the repetitive work of doing it again for the next OS -- which left the
human quarter almost entirely for the things it can't do: deciding what
the product should actually do, for whom, in what order.

A few things that made the difference, from a new post:

- Keep the backlog to one active item at a time -- large enough is a lie
  at this FTE, and "what's next" should never need a meeting.
- Let the AI draft the implementation, tests, and doc update together as
  one piece of work once a decision is made; review that combination
  instead of writing each piece by hand.
- Review for correctness and shape -- "does this do what's needed" -- not
  for style the tooling already enforces.
- Never skip the full validation run under time pressure; low FTE is
  exactly when a regression is most expensive, because there's no slack
  later to catch it.
- Ship narrow and real rather than broad and half-done -- narrow in
  features, not in platforms.

This is Virtual Church Musician's actual build story, not a hypothetical.
Full post: {{post_url}}

#ProductDevelopment #AI #Claude #StartupLessons #SoftwareDevelopment
