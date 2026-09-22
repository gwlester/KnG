---
platform: LinkedIn
pairs_with: 09-what-we-did-for-localization.md
---

**Localization looks like a content problem. It's mostly an architecture
problem.**

Rolling out US English, Spanish, and German across Virtual Church
Musician's desktop and mobile apps meant fewer decisions about translation
quality and more about where a few specific lines get drawn:

- One `tr()` lookup helper per platform, with locale resolved in a fixed
  order every time -- CLI flag, then environment variables, then the host
  OS's own language setting, falling back to US English.
- Every locale bundle has to define the exact same set of keys. A key
  missing from one language isn't a typo for later -- it's a bug, tested
  like one.
- The line that mattered most: never localize a value that logic depends
  on, only the label shown to a person. We caught a real bug where an
  internal sentinel value would have broken a selection check the moment
  it got translated -- fixed with formatters that sit strictly between the
  stored value and the display string.
- Mobile needed its own answer, not a port: OS locale detection through
  `react-native-localize` instead of JS's own `Intl` (which reflects the
  engine, not the device), and dynamic language switching built on
  `AppState`'s resume-to-active transition after discovering, by checking
  the actual installed package rather than assuming, that the library had
  dropped its own change-event API.
- Localization doesn't stop at the UI -- the User Manual and Admin Guide
  build per locale, and installers deploy the one matching the host OS.

Full writeup: {{post_url}}

#Localization #i18n #SoftwareArchitecture #ReactNative #Python
