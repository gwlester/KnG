---
platform: LinkedIn
pairs_with: 11-shipping-translation-fixes-without-a-release.md
---

**We turned "fix a typo in a translation" from a release into a server
upgrade.**

Localizing Virtual Church Musician (our last post) solved how a
translated string reaches a screen. It didn't solve what happens when
that string is wrong, or a church wants a language we never bundled --
and on every platform we had, fixing that meant shipping new software
and waiting for someone to install it.

What we built instead, from the new post:

- A `POST /api/translations` endpoint on the Public tier -- reachable
  before a device is even enrolled -- serving the same hand-authored
  catalog the apps already compile in, not a second copy.
- Monotonic, timestamp-based versioning instead of a hash: a client only
  ever accepts a reply strictly newer than what it already has, so a
  multi-campus device roaming between two servers on different catalog
  versions can never be talked backward into an older translation.
- One shared cache across all four desktop apps (translations aren't
  app-specific) and a per-locale cache on mobile, both overlaying
  compiled-in bundles so a cache miss degrades to what shipped, never to
  blank text.
- Opening up a previously closed set of supported locales, so a language
  we never bundled can become active the moment the server has it -- no
  client release required.
- Two bugs caught before shipping: a refresh path that would have let an
  older, second server downgrade an already-current cache, and a React
  re-render gap where updating a locale's *content* didn't change the
  locale *string* a component was watching.

Full writeup: {{post_url}}

#Localization #i18n #SoftwareArchitecture #APIVersioning #ReactNative
