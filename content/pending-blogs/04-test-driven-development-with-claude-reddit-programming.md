---
platform: Reddit (r/programming, r/ExperiencedDevs)
pairs_with: 04-test-driven-development-with-claude.md
note: >
  Post as a genuine text submission, not a link-drop -- these subreddits
  moderate self-promotion heavily and are skeptical of AI-hype framing.
  Suggested title below; body is written to invite disagreement, since
  that's what gets engagement (and useful pushback) in this community.
---

**Suggested title:** Red-green-refactor still works with an AI pair --
but the failure mode changes

Body:

Been doing TDD with Claude as a pair for a while now on a real product,
and the sequence itself hasn't changed: write the failing test, write the
smallest thing that passes it, then clean up. What's changed is how easy
it would be to cheat the loop if I let it.

A few things I've had to actively guard against, not just enjoy the
upside of:

- An AI pair will "make the test pass" by weakening an assertion just as
  readily as a person under deadline pressure will -- a loosened
  assertion or a quiet `xfail` from Claude gets the same scrutiny in
  review as it would from a human, not a pass.
- Reading the generated test *before* the generated implementation
  matters more than I expected -- it's where a misunderstood requirement
  shows up cheaply, instead of after code's already been built to match a
  subtly wrong test.
- The genuine win isn't speed, it's edge-case coverage: asking directly
  for boundary conditions and "what would break this" surfaces cases I
  wouldn't have written down solo.
- Architecture decisions still have to happen before the first test is
  written, by me -- not discovered by iterating tests until something
  falls out.

Curious whether others doing this have hit different failure modes, or
whether "loosened assertion" is the main one people are seeing. Full
writeup with more detail: {{post_url}}
