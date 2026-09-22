---
platform: LinkedIn
pairs_with: 08-the-importance-of-format-version-and-type.md
---

**Every API response and every exported file is a promise about its own
shape. That promise only holds if the format names itself.**

Without an explicit type and version, "what shape is this data" becomes a
guess based on which fields happen to be present -- and guesses like that
eventually guess wrong, usually at the worst possible time.

Two places this matters most, from a new post:

- **APIs** -- a `FormatVersion` field or `X-API-Version` header lets a
  client and server that have drifted apart detect it and handle it
  deliberately, instead of "detecting" it by crashing on a field that
  moved.
- **Import/export/backup formats** -- higher stakes than an API, because
  a backup file might not be opened again for two years, by a version of
  the software that doesn't exist yet. An unversioned file leaves that
  future reader guessing exactly when guessing is most expensive.

The practical rules I hold to: put type and version at the very top of the
format, unconditionally, so it's the one thing that never changes even as
everything else does; treat a version bump as a real compatibility
decision, not a formality; and make "I don't know how to read this yet" an
explicit, clear failure -- never a silent partial import.

None of this shows up in a demo. It shows up two years later.

Full post: {{post_url}}

#APIDesign #SoftwareEngineering #BackwardCompatibility #DataFormats
