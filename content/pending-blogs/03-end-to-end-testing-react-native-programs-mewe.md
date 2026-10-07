---
platform: MeWe
pairs_with: end-to-end-testing-react-native-programs.md
---

React Native folks: most of the "flaky emulator test" pain I've seen is
actually a teardown problem, not a test problem. Wrote up the checklist --
pausing for full teardown between runs, resetting AsyncStorage/permissions
(not just files), disabling animations, and testing fresh-install and
upgrade paths separately.

{{post_url}}
