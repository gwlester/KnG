---
platform: LinkedIn
pairs_with: 10-how-we-test-that-localization-is-correct.md
---

**"Is it translated" is the wrong test for localization. Here's what
actually matters.**

The real failure modes are quieter than missing text: a locale silently
falling back to English with no one noticing, a translated value leaking
into logic it was never meant to touch, and localization tests that only
pass because they happen to run somewhere with a real screen attached.

What we test for instead, from a new post:

- An exhaustive check that unions every translation key across every
  locale bundle and confirms each one exists -- and actually translates --
  in all three languages. That single test is what catches drift; a spot
  check on the Spanish text never would have.
- Every fallback path as its own assertion: locale aliases normalizing
  correctly, an unsupported locale falling back cleanly, a missing key
  falling back through English, then a default, then the key itself --
  none of it allowed to raise.
- A real production incident, caught by our own test suite: the
  window-title localization tests were the one place in the repo still
  opening a real Tk window, which meant they were the one thing that broke
  when our headless macOS release runner -- no GUI session at all -- tried
  to run them. Rewritten onto a mocked root, same coverage, zero display
  required, plus a guardrail so no unit test can silently reach for a real
  window again.
- On mobile: a live re-render test that actually switches locale on a
  mounted screen against the real bundles, and a full validation pass that
  builds and installs a real release APK with the on-device locale library
  wired in.

Full post: {{post_url}}

#Localization #SoftwareTesting #QA #i18n #CI
