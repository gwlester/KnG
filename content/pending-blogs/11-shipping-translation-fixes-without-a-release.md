---
title: Shipping Translation Fixes Without a Release
date: 2026-10-07
summary: Moving Virtual Church Musician's translation catalog onto the server turned a typo fix or a new language into a server upgrade instead of an app release, with a monotonic versioning scheme so no device can ever be downgraded by an older server.
---

Localizing the apps (see our last post) answered how a translated string
gets to a screen. It didn't answer a harder question that surfaced almost
immediately afterward: what happens when one of those strings is wrong,
or a church wants a language we haven't bundled at all? Before this, the
answer was the same on every platform -- ship a new release and wait for
someone to install it. Desktop and mobile have different mechanics (a
manual reinstall versus an app-store review), but the shape of the
problem is identical: fixing a translation took as long as shipping
software.

**The server becomes the source of truth at runtime, not just at build
time.** `POST /api/translations` is reachable on the Public tier -- no
device certificate required -- because a translation fix shouldn't be
gated behind enrollment. It reads straight from
`desktop_common.locales.BUNDLES`, the same hand-authored catalog the apps
already compile in; there's no second copy of the strings to keep in
sync, just one catalog served two ways.

**Versioning is a timestamp, not a hash, on purpose.** Every locale file
on both platforms picked up a `LOCALE_BUNDLE_UPDATED_AT`, bumped by hand
whenever its content changes. A hash would tell a client "this changed,"
but not "in which direction" -- and the real deployment this has to
survive is a multi-campus church whose devices roam between two servers
running different catalog versions. A client only ever accepts a reply
that's strictly newer than the newest version it has already cached, for
the active locale and always for the `en_US` fallback. No device can be
talked backward into an older translation by whichever server happens to
answer first.

**Each platform caches independently, but the rule is the same.** Desktop
gets one shared cache file (`desktop_common/translation_cache.py`) across
all four apps, not four separate ones -- translations aren't
app-specific, so there's no reason Builder and Runner should ever
disagree about German. Mobile gets `mobile_common/translationCache.ts`,
one `AsyncStorage` key per locale. On both platforms, `tr()`/
`useTranslation()` overlay the cache on top of the compiled-in bundle, so
a cache miss degrades to exactly what shipped in the app, never to a
blank string.

**A previously closed set of locales had to open up.** `normalize_locale()`/
`normalizeLocale()` used to collapse anything it didn't recognize down to
`en_US`. That's the wrong behavior once the server can hand a device a
language it was never built with, so an unbundled-but-plausible locale
now passes through unchanged instead of being collapsed, and
`SupportedLocale` widened from a closed union to a plain string
(`BundledLocale` is the new name for the old closed, compile-time set).
A church wanting French doesn't need a new release; the catalog needs a
French bundle, and the next discovery does the rest.

**Two bugs were worth finding before they shipped, not after.** The
first: the refresh path initially saved anything the server reported as
"updated" without rechecking that it was actually newer than the
client's own best-known value -- fine against a single server, but the
server only ever compares against its own current value, with no
history, so a second and *older* server answering "updated" with stale
data would have downgraded a device that had already fetched something
newer. The fix is the same strict recency check described above, run
independently by the client on every refresh rather than trusted from the
server's own say-so. The second was React-specific:
`useTranslation()`'s `useSyncExternalStore` watched only the locale
string, so a refresh that updated the *content* of the already-active
locale changed nothing that string-based snapshot could see, and a
mounted screen simply wouldn't re-render. A second `useSyncExternalStore`
on a new `translationsVersion` counter fixed it.

**The payoff is specifically the thing this was built for.** A typo
fixed only in `desktop_common/locales/*.py`, with no client code touched
at all, shows up in both a desktop app and a mobile app on their next
discovery of an upgraded server -- confirmed live, not assumed. Correcting
a translation, or adding one we never bundled, is now an operations task
on the server, not a release.
