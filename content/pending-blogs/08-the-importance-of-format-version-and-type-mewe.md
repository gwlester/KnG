---
platform: MeWe
pairs_with: 08-the-importance-of-format-version-and-type.md
---

For anyone designing file formats or APIs: put a type and version field at
the very top, unconditionally, before you ship the first version. Wrote up
why this matters more for import/export/backup formats than for APIs --
a backup might get opened again in two years by software that doesn't
exist yet.

{{post_url}}
