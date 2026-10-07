---
title: End to End Testing of React Native Programs
date: 2026-09-22
summary: Emulator-based end to end tests for React Native live or die on teardown discipline -- give runs time to fully exit, reset state deliberately, and clean up what they leave behind.
---

React Native's end to end story is more mature than a desktop toolkit's --
there's a real emulator, real gestures, and mature frameworks around both.
Most of the pain isn't in driving the app; it's in the housekeeping around
each run.

**Use an emulator, not just unit-level component tests.** Component tests
prove a screen renders correctly in isolation. Only an emulator run
proves the actual app -- navigation, native modules, permissions, the
real bridge -- behaves once installed on something that looks like a
phone.

**Pause between runs to allow full teardown.** Killing an emulator (or the
app under test) doesn't mean it's gone. Processes linger, ports stay bound,
and the next run's install or launch can silently race the previous run's
cleanup. A short, deliberate pause -- or better, waiting on an explicit
"fully stopped" signal -- turns an intermittent, hard-to-reproduce failure
into a non-issue.

**Clean up temp directories and files.** Build artifacts, downloaded test
fixtures, and anything the app itself writes to device storage will
accumulate across runs if nothing removes them, eventually changing disk
space, first-run behavior, or which files a "fresh install" test actually
sees.

A few more points worth planning for:

- **Reset app storage and permissions, not just files.** AsyncStorage,
  granted permissions, and keychain/keystore entries all persist across
  app restarts on the same emulator; a "clean" run needs a clean sandbox,
  not just a clean disk.
- **Decide deliberately between cold-boot and snapshot emulator images.**
  Snapshots start faster but can carry over stale state between runs;
  cold boots are slower but genuinely fresh. Pick one on purpose rather
  than inheriting whatever the CI image happens to do.
- **Disable animations in test builds.** Animation timing is one of the
  most common sources of flaky waits in RN end to end suites -- turning
  them off in the test configuration removes an entire class of
  flakiness for a real feature no one's actually testing.
- **Mock or record/replay the backend.** A live server the app depends on
  is one more thing that can be down, slow, or return different data
  between runs. Deterministic responses make failures mean something.
- **Pin the device clock and timezone.** Anything date- or time-sensitive
  in the UI will behave differently depending on where and when CI
  happens to run, unless you fix both explicitly.
- **Capture logcat and screen recording on failure.** An emulator failure
  without a video and device log is a coin flip to reproduce later.
- **Test a fresh install and an upgrade-from-previous-version separately.**
  Migration bugs -- schema changes, renamed storage keys -- only show up
  on the upgrade path, and a suite that only ever installs fresh will
  never catch them.

The pattern underneath most of this: an emulator is a shared, stateful
thing pretending to be a fresh device. Treat every run as needing to earn
that fiction back, rather than assuming the last run cleaned up after
itself.
