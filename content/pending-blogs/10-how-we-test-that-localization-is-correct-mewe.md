---
platform: MeWe
pairs_with: 10-how-we-test-that-localization-is-correct.md
---

Testing localization well means testing for silent fallback and
accidentally-translated logic, not just "does Spanish text show up
somewhere." Also shared: how our own headless-macOS CI runner caught a
localization test that was secretly the only one in the repo still
opening a real Tk window -- and how we closed off that whole category of
bug afterward.

{{post_url}}
