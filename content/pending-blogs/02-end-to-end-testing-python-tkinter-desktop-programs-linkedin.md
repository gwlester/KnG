---
platform: LinkedIn
pairs_with: end-to-end-testing-python-tkinter-desktop-programs.md
---

**How do you end-to-end test a desktop app with no test hooks built in?**
For a Python/Tkinter app, Tcl/Tk already has the mechanism -- you just have
to use it deliberately.

The short version, from a post I just wrote:

- Run under a virtual X display (Xvfb). The real app draws to a real
  display; nothing about it knows it's headless.
- Drive it with Tk's own `send` command, which lets one Tcl/Tk process
  evaluate a script inside another -- your test talks directly to the
  running app's real widgets.
- Keep `send` calls asynchronous except when you actually need a value
  back, so your driver isn't blocked on the app's event loop.
- Generate events (`<Button-1>`, etc.) rather than calling `invoke()` or
  handler functions directly -- events exercise bindings, focus, and
  everything else a real click triggers; direct calls can pass while the
  UI is actually broken.

The full post also covers targeting the right window when more than one
instance is running, waiting on state instead of the clock, restarting
between scenarios instead of resetting in place, and pinning your Tcl/Tk
version so `send` behaves the same in CI as in production.

Read it here: {{post_url}}

#Python #Tkinter #EndToEndTesting #DesktopApps #QA
