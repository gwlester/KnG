---
platform: Facebook
pairs_with: 10-how-we-test-that-localization-is-correct.md
---

Our localization tests found a real bug -- in themselves. The window-title
tests were the one place still opening a real Tk window, and it broke the
moment our headless macOS build server tried to run them. New post on
testing localization for the failures that actually matter: silent
fallback, translated values breaking logic, and tests that secretly need
a real screen.

{{post_url}}
