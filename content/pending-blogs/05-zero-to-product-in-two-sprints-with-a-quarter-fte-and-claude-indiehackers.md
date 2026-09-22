---
platform: Indie Hackers
pairs_with: 05-zero-to-product-in-two-sprints-with-a-quarter-fte-and-claude.md
note: >
  IH responds well to concrete numbers (FTE, timeline, scope) and honest
  lessons-learned framing over polish. Soft mention of consulting
  availability at the end fits this community's norms better than it
  would on Reddit or HN.
---

**Milestone: shipped 10 applications in two sprints at 1/4 FTE**

Wanted to share this because the constraint (attention, not hours in the
usual sense) forced decisions I think generalize past our specific
product.

The product: Virtual Church Musician, software for churches to build a
service order, template it, and run it live with MIDI-driven
accompaniment to an actual instrument. The build: one person, roughly a
quarter of their working time, two sprints, end state of 4 desktop apps +
4 React Native apps + 2 servers -- with every desktop app and both servers
cross-platform for Windows/macOS/Linux from the first release.

What made the FTE arithmetic close:

- Almost all human hours went into product decisions (what, for whom, in
  what order) -- almost none into typing implementation, tests, or docs,
  which an AI pair (Claude) drafted together once a decision was made.
- Backlog stayed small enough to fit in one head -- one active item at a
  time, not a sprawling roadmap that's aspirational at this FTE level.
- Full test suite validation never got skipped under time pressure --
  the exact situation where a regression is most expensive, since there
  was no slack later in the week to absorb it.
- Scope stayed narrow on features, not on platforms -- shipping fewer
  things well, everywhere, beat shipping more things halfway on one OS.

Full breakdown: {{post_url}}

(We also take on consulting work built around this same approach --
happy to talk if anyone's trying to stretch a similarly small team.)
