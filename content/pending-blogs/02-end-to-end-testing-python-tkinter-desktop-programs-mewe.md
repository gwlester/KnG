---
platform: MeWe
pairs_with: end-to-end-testing-python-tkinter-desktop-programs.md
---

For anyone testing Tkinter apps: Tk's `send` command plus Xvfb gets you real
end-to-end tests against the actual running app, no mocks involved. Wrote
up the details -- async sends, real events instead of calling handlers
directly, restarting between scenarios instead of resetting in place.
Linux/Unix only, which is the one catch.

{{post_url}}
