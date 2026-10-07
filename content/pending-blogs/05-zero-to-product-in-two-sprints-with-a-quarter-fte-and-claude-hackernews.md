---
platform: Hacker News
pairs_with: 05-zero-to-product-in-two-sprints-with-a-quarter-fte-and-claude.md
note: >
  Submit as a plain link with this as the accompanying first comment, not
  a "Show HN" -- that tag implies something visitors can try live in a
  browser, which a downloadable desktop/mobile suite isn't. HN rewards
  understatement and concrete detail over enthusiasm; keep hedges in.
---

Suggested submission title: "From zero to 10 shipped apps in two sprints
at 1/4 FTE, pairing with an AI on all of it"

First comment (post this yourself shortly after submitting, HN convention
for context the title can't hold):

Some context since the title undersells the constraint: this was one
person at roughly a quarter of their normal working hours, across two
sprints, building a real product (church service-planning and live
MIDI-driven playback software) -- not a prototype. End state was 4 desktop
apps, 4 React Native apps, and 2 backend servers, with the desktop apps
and both servers cross-platform (Windows/macOS/Linux) from the first
release, not one platform first.

The part I think is actually interesting, versus "AI helps you code
faster": the FTE math only worked because almost none of the available
hours went to implementation, tests, or docs -- an AI pair handled the
first draft of all three together once a decision was made. What was left
for the human was almost entirely product decisions: what the thing
should do, for whom, in what order. Full validation (the complete test
suite) stayed non-negotiable the whole time, specifically because there
was no slack to absorb a regression later.

Wrote up the specifics, including where it didn't just work on the first
attempt: {{post_url}}
