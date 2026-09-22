---
platform: Discord (Church IT Network, and similar ministry-IT servers)
pairs_with: 05-zero-to-product-in-two-sprints-with-a-quarter-fte-and-claude.md
note: >
  Conversational, peer-to-peer tone -- this audience is IT-minded church
  staff/volunteers, not a marketing audience. Lead with a question, not a
  pitch, and only drop this in a #show-and-tell / #projects-style channel,
  never general chat, per most Discord servers' own norms.
---

Curious how other church IT folks are handling the "we need an app for
this, but there's no budget or dev time" problem.

We just went through it building Virtual Church Musician -- ended up
shipping 10 separate apps (4 desktop, 4 React Native, plus the Server and
MIDI Player behind them) in two sprints on about a quarter of one person's
time. Only way the math worked was pairing with Claude for basically
everything downstream of a product decision -- implementation, tests, and
docs together -- and keeping the human time almost entirely on "what
should this actually do for a church" instead of typing.

Everything desktop-side and both servers are cross-platform (Windows,
macOS, Linux) from the start, not one platform first.

Wrote up how the workflow actually held together at that FTE level, in
case it's useful to anyone else here trying to stretch limited hours:
{{post_url}}

Happy to talk through specifics if anyone's trying something similar.
