---
platform: LinkedIn
pairs_with: end-to-end-testing-react-native-programs.md
---

**Most React Native end-to-end flakiness isn't about the app -- it's about
the emulator between runs.**

Driving the app itself is the easy part now; the frameworks are mature.
What actually breaks CI is housekeeping: a process that hasn't fully
exited, storage that carried over from the last run, temp files quietly
piling up on disk.

Three habits I put at the top of a new post:

- Pause between runs for full teardown -- killing an emulator or app
  doesn't mean it's actually gone; races with the next install/launch are
  a classic source of "flaky" failures that aren't flaky at all.
- Clean up temp directories and files after every run, not just at the
  end of a suite.
- Reset app storage and permissions (AsyncStorage, granted permissions,
  keychain entries), not just the filesystem -- a "clean" run needs a
  clean sandbox.

The full post also covers cold-boot vs. snapshot emulator images,
disabling animations to remove a whole class of timing flakiness, pinning
the device clock/timezone, and testing a fresh install separately from an
upgrade path (migration bugs only show up on the second one).

Read it here: {{post_url}}

#ReactNative #MobileTesting #EndToEndTesting #QA #CI
