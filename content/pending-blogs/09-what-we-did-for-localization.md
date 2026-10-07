---
title: What We Did for Localization
date: 2026-09-22
summary: Localizing Virtual Church Musician meant one translation lookup helper, three locale bundles, a strict layer between stored values and displayed text, and a mobile team that had to build its own answer to a desktop problem.
---

Localization sounds like a content problem -- translate the strings, ship
three copies. In practice, most of the real decisions were architectural:
where locale detection lives, what never gets translated even though it
looks like text, and how a setting picked on a desktop app should behave
differently from the same setting on a phone that changes language while
backgrounded.

**One lookup helper, layered detection.** Every desktop app shares a
single `i18n` engine (`src/desktop_common/i18n.py`) built around a `tr()`
function: give it a key, get back the string for whatever locale is
active. That locale comes from the first source that supplies one -- a
`--locale` CLI flag, then a short list of environment variables, then the
host OS's own language setting -- falling back to US English the moment
nothing recognized applies. The same layered order shows up on every app,
so "why is this app in Spanish" always has the same three places to check.

**Three bundles, one contract.** US English, Spanish, and German each get
a resource bundle of key-to-string mappings. The contract that matters
isn't the translation quality -- it's that every bundle defines the same
set of keys. A key present in English but missing in Spanish isn't a typo
to fix later; it's a bug in the exact same category as a broken function
call, and it gets caught the same way (more on that below).

**Never localize the value, only the display.** The sharpest lesson from
the sweep: a value like an application's internal name, or a sentinel like
"none selected," has to stay locale-invariant everywhere it's compared,
matched, or stored -- only the label shown to a person gets translated.
Get that backwards and a perfectly good `if value == "--none--"` check
starts failing the moment someone runs the app in German. It happened once
during the sweep; the fix was formatters (`format_application_name()`,
`format_item_type()`, `format_boolean_indicator()`) that sit strictly
between the real value and the label a user sees, so nothing downstream
ever compares against translated text by accident.

**Mobile needed its own answer, not a port.** The four React Native apps
mirror the desktop approach -- a shared `tr()`/`useTranslation()` engine in
`src/mobile_common/i18n.ts`, the same three bundles -- but OS locale
detection uses `react-native-localize`'s `getLocales()` rather than the
JavaScript engine's own `Intl` object, because `Intl` reflects the engine's
locale, not the device's actual system language, and offers no way to
learn about a change. Reacting to that change turned out to need its own
answer too: rather than the library's own change-event listener, locale
re-detection is driven off `AppState`'s resume-to-active transition --
found only by checking the actually-installed package rather than
assuming from memory, since that listener API had quietly been dropped
when the library moved to React Native's newer architecture. It's also
the more honest mechanism regardless: an OS language change backgrounds
the app first on both platforms, so "changed while backgrounded, then
resumed" is the only scenario that was ever going to happen.

**Localization doesn't stop at the UI.** The User Manual and System
Administrator Guide get built per locale as PDF, HTML, and zip artifacts,
and the desktop installers deploy the documentation matching the host
OS's language at install time -- or prompt for a choice where the
installer format supports it. A product that's localized in the app but
ships English-only documentation has only done half the job.

None of this required anything exotic -- a lookup function, a fallback
chain, and a firm line between stored values and displayed ones. Most of
the effort went into finding the places that line was already, quietly,
in the wrong spot.
