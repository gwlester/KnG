---
platform: LinkedIn
pairs_with: 04-test-driven-development-with-claude.md
---

**Red, green, refactor doesn't change when your pair is an AI. What
changes is how tempting it becomes to skip a step.**

TDD has always been about sequencing: write the failing test, write the
smallest thing that passes it, then clean up. Working with Claude hasn't
changed that sequence -- but it has changed how cheap it is to keep to it
honestly, and how easy it would be to cheat.

A few things I've settled into:

- Describe the behavior in plain English and let the test get written
  before any implementation exists -- same discipline TDD always demanded.
- Read the generated test before the generated implementation. A test
  you wouldn't have written yourself is a misunderstanding caught early.
- Treat a loosened assertion, a skipped test, or a quiet `xfail` from an
  AI pair exactly like you would from a person under deadline pressure --
  as a red flag, not a resolution.
- Use the AI to find edge cases you didn't think to write down. This is
  a genuine advantage over solo TDD, not just a speed-up.
- Keep architecture decisions -- what's a module, what the contract looks
  like, what belongs in this sprint -- as a human call made before the
  first test, not something you discover by iterating.

Full post: {{post_url}}

#TDD #SoftwareEngineering #AI #Claude #TestDrivenDevelopment
