---
title: From Zero to Product in Two Sprints with 1/4 FTE and Claude
date: 2026-09-22
summary: A quarter of one person's time and an AI pair got a real product from nothing to shippable in two sprints -- by spending the human quarter almost entirely on decisions an AI can't make.
---

The constraint wasn't time in the usual sense -- it was attention. A
quarter of one person's working hours, split across two sprints, is not a
lot of hours to turn into a shippable product. It worked because almost
none of those hours went to the things that normally eat a sprint:
boilerplate, first-draft tests, repetitive documentation, and the general
overhead of getting from "I know what I want" to "there's code for it."

That's the part an AI pair is good at, and handing it over is what made
the quarter FTE arithmetic work at all -- especially given the actual
scope: by the end of those two sprints, Virtual Church Musician wasn't one
app, it was ten. Four desktop apps (Admin, Services, Templates, Runner),
four React Native companions covering the same four roles on phones, and
the two servers behind all of them (the Church Music Server and the MIDI
Player) -- and every one of the desktop apps and both servers built for
Windows, macOS, and Linux from day one, not one platform first and the
rest deferred. At a quarter FTE, across two sprints, that's not a number
that works if the human is also the one typing, and retyping, every
platform-specific line.

**Spend the human time on product decisions, not typing.** What Virtual
Church Musician needed to do, for whom, in what order -- that's domain
knowledge about how churches actually run music, and no amount of AI
assistance substitutes for having it. Every hour spent deciding scope
paid for itself many times over; hours spent writing code that Claude
could draft correctly on the first pass did not.

**Keep the backlog small enough to fit in your head.** With this little
time, a large backlog isn't aspirational, it's a lie. The work that
mattered lived in `Prompts/ToDo.md` as one active item at a time, not a
sprawling board -- small enough that "what's next" was never a question
that needed a meeting.

**Let the AI produce the first draft of everything downstream of a
decision.** Once a feature's shape was settled, Claude wrote the
implementation, the tests, and the doc update together, as one piece of
work. Reviewing that combination took a fraction of the time writing it
from scratch would have.

**Review for correctness and shape, not for style.** At a quarter FTE,
there's no time to bikeshed formatting or naming conventions the tools
already enforce. Review time went to "does this actually do what the
church needs" and "is this the right abstraction," which are the
questions a human still has to answer.

**Treat validation as non-negotiable, even under time pressure.** The
temptation at low FTE is to skip the full test run "just this once." It's
also exactly the situation where a regression is most expensive, because
there's no slack later in the week to catch it. Running the full suite
before closing a work item stayed non-negotiable the entire time.

**Ship narrow, ship real -- narrow in features, not in platforms.** Two
sprints produced something a real church could actually use, not a demo,
across every OS a church's own hardware was likely to already be running.
Narrow feature scope, done properly and cross-platform from the start,
beat broad feature scope done halfway on one platform -- especially with
this little room for rework.

None of this is a claim that AI assistance replaces product thinking. It's
closer to the opposite: constraining the human time to almost nothing
except product thinking is what made two sprints at a quarter FTE turn
into a real, working product instead of a promising prototype.
