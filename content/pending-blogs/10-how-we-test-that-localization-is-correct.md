---
title: How We Test That Localization Is Correct
date: 2026-09-22
summary: "Did we translate everything" is the wrong question to test for -- the real risks are silent fallback, a translated value that breaks logic, and localization tests that quietly need a real display and skip themselves on headless CI.
---

"Is it translated" is a spot check. The failures that actually matter are
quieter: a locale silently falling back to English without anyone
noticing, a display string leaking into a comparison it was never meant to
be part of, and localization tests that only pass because they happen to
run somewhere with a real screen attached. Testing localization well means
testing for those three things specifically, not just checking that some
Spanish text shows up somewhere.

**An exhaustive key check, not a spot check.** One test unions every key
across every locale bundle and asserts each one exists -- and actually
translates to something other than the bare key -- in US English, Spanish,
and German alike. That single test is what actually prevents translation
drift; nothing about "the Spanish text I looked at seemed fine" would have
caught a bundle quietly falling one key behind. The mobile side runs the
same check in Jest against its own three bundles.

**Fallback gets tested as a first-class behavior, not a hope.** A locale
alias (`es_ES.UTF-8`, `en_GB`) has to normalize to something supported; an
unsupported locale (`fr_FR`) has to fall back to US English cleanly; a key
missing from a supported bundle has to fall back to English, then to an
explicit default, then to the key itself -- and none of those paths are
allowed to raise. Each one is its own assertion, because "probably falls
back fine" is exactly the kind of thing that's true until the one time it
isn't.

**The end-to-end tests uncovered a real production bug -- in themselves.**
The tests that launch each desktop app with `--locale es` and `--locale
de` and check the window title were, for a while, the one place in the
repo that still opened a real `tk.Tk()` window to do it. That was invisible
until the self-hosted macOS release runner -- a headless launchd service
with no GUI session -- tried to run them and failed outright, because Tk 9
can't create a window at all without one. Every other test in the codebase
already followed the rule from testing Tkinter apps in general: mock every
Tk interaction, never open a real window in a unit-level test. These three
tests were the exception, and the exception is what broke. They were
rewritten to build each app on a mocked root with its Tk collaborators
patched, and assert that `root.title` was called with the correctly
localized string -- same coverage, zero display required.

**Guardrails, not just a fix.** The specific bug got fixed; the category
of bug got closed off. A shared test fixture now fails immediately, with a
message pointing at the mocking pattern, if any unit test constructs a
real `tk.Tk()`. On Linux, `DISPLAY` is pointed at a nonexistent X server
for the entire test session, so anything that does reach for a real screen
fails the same way locally that it would on the headless runner --
turning "works on my machine, fails in CI" into "fails everywhere,
immediately," which is a far cheaper bug to have.

**Mobile verifies the switch actually happens, live.** Beyond the engine
tests (locale detection, fallback, string formatting with placeholders),
one test per app mounts a real screen and calls the locale setter directly,
then asserts the screen re-renders with the new language's text -- against
the real locale bundles, not a stub standing in for them. The full
validation suite goes a step further and builds, installs, and launches an
actual release APK on the Android emulator with the real
`react-native-localize` native dependency wired in, so "does this even
build with the on-device locale library" gets answered on something
closer to a real phone, not assumed from a unit test.

**Automated coverage was the actual gate.** The original scope for this
work said it would be "complete only when QA confirms the fallback
behavior is correct." Once the automated suite -- including that real
APK build, install, and launch -- covered every case the manual test plan
called for, that was treated as satisfying the gate on its own. Writing
the exhaustive automated checks first is what made trusting them instead
of a manual sign-off a reasonable call, not a shortcut.
