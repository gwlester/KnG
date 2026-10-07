---
platform: LinkedIn
pairs_with: unit-testing-python-tkinter-desktop-programs.md
---

**Tkinter code is testable. Most teams just never separate the two things
they're testing.**

"You can't really unit test a GUI" is one of those lines that's technically
true and practically wrong. You can't meaningfully unit test a widget --
but you were never trying to. The logic behind the widget (what gets
validated, what gets enabled, what gets saved) is ordinary Python, and it
tests like ordinary Python once you stop letting Tk sneak into the test
run.

Two habits do most of the work:

1. Mock every Tk interaction. A unit test should never construct a real
   widget or touch a real display.
2. Run the suite headless -- DISPLAY unset, no Xvfb -- so a missed mock
   fails loudly in CI instead of quietly on one developer's machine.

In the full post I go through those two plus half a dozen more: keeping
state in plain Python instead of `StringVar`/`IntVar`, injecting the root
window instead of reaching for a module-level `Tk()`, isolating the
handful of tests that genuinely need a real window, and using coverage to
catch a mock that's never actually asked to do anything.

None of it is really Tkinter-specific -- it's the same discipline that
makes any UI layer testable. Tkinter just makes it unusually easy to skip.

Read the full post: {{post_url}}

#Python #Tkinter #SoftwareTesting #DesktopApps #UnitTesting
