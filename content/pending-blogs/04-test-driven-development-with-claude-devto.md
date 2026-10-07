---
title: Test Driven Development with Claude
published: false
tags: testing, ai, tdd, python
canonical_url: "{{post_url}}"
pairs_with: 04-test-driven-development-with-claude.md
note: >
  Dev.to/Hashnode cross-post. Set canonical_url to the live blog post URL
  before publishing (this is what tells search engines the KnG blog is
  the original, so cross-posting doesn't hurt its ranking). Flip
  `published` to true when ready. Body is the same article, reused
  verbatim -- Dev.to's own convention is a full cross-post, not a teaser.
---

Test driven development has always been about sequencing: write the test
that fails, write the smallest thing that makes it pass, then clean up.
Working with Claude as a pair hasn't changed that sequence. What's changed
is how cheap it's become to keep to it honestly, and how easy it would be
to cheat if you let it.

**Write the failing test first, in plain English, before any code.**
Describing the behavior you want -- "given an empty cart, applying a
discount code should be a no-op" -- before Claude writes a line of
implementation forces the same discipline TDD always demanded: you have to
know what "done" means before you start.

**Let Claude draft the test from that description, then read it before
you read the implementation.** A generated test is only useful if you'd
have written the same assertion yourself. Reviewing the test first catches
a misunderstood requirement while it's still cheap to fix, rather than
after an implementation has been built to match a subtly wrong test.

**Watch for the AI equivalent of "just make it pass."** A human under
deadline pressure sometimes weakens an assertion instead of fixing the
bug; an AI pair will do the same thing if you let the loop optimize for
"tests pass" instead of "behavior is correct." Skipped tests, loosened
assertions, and `xfail` markers that quietly appear are the same red flag
they'd be from a person -- treat them that way in review.

**Use Claude to find the edge cases you didn't think to write down.**
Once the happy-path test exists, asking directly for boundary conditions,
error paths, and "what would break this" tends to surface cases a human
working alone would only find in production. That's a genuine advantage
over solo TDD, not just a speed-up of it.

**Keep the loop small and the diffs reviewable.** Red-green-refactor
works because each step is small enough to reason about. That doesn't
change when the "green" step is written by an AI -- if anything it matters
more, since it's easy to let an agent run several cycles unattended and
end up reviewing a much bigger diff than you meant to.

**Reserve architecture decisions for yourself.** Claude is a strong
implementer once the shape of the solution is set. The decision about what
that shape should be -- what's a separate module, what the API contract
looks like, what belongs in this sprint at all -- is still a human call,
made before the first test is written, not discovered by iterating tests
until something falls out.

The net effect, on real work, has been that TDD stays disciplined for
longer. It's easy to let red-green-refactor slide after a few weeks of
solo pressure; it's a lot harder to let it slide when writing the test
first is the fastest way to get a correct implementation out of an AI
pair, not the slowest way to get any implementation at all.

---

*Originally published on the [KnG Consulting blog]({{post_url}}).*
