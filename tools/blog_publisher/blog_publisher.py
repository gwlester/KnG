"""Pure logic for the monthly blog-publish script: picking the next post
out of content/pending-blogs/, stamping its date, filling in the
{{post_url}} placeholder in its teaser variants, and building the
Dev.to API payload from a devto variant file. No filesystem, git, or
network calls here -- see publish_next_post.py for those. Kept separate
so this half can be unit tested the normal way.
"""
from __future__ import annotations

import re

_NUMBERED_RE = re.compile(r"^(\d+)-(.+)\.md$")
_FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)
_FRONT_MATTER_LINE_RE = re.compile(r"^(\w+):\s*(.*)$")
_DATE_LINE_RE = re.compile(r"^date:\s*.*$", re.MULTILINE)


def _group_by_number(filenames: list[str]) -> dict[int, list[str]]:
    groups: dict[int, list[str]] = {}
    for name in filenames:
        match = _NUMBERED_RE.match(name)
        if not match:
            continue
        groups.setdefault(int(match.group(1)), []).append(name)
    return groups


def find_next_post(filenames: list[str]) -> str | None:
    """The base post file (not a platform teaser variant) for the
    lowest-numbered topic still present. A base file is the shortest
    filename in its NN- group -- every variant is the base stem plus
    "-<platform>", so it's always longer. Returns None once the queue
    (content/pending-blogs/) is empty.
    """
    groups = _group_by_number(filenames)
    if not groups:
        return None
    candidates = groups[min(groups)]
    return min(candidates, key=len)


def variant_filenames(base_filename: str, filenames: list[str]) -> list[str]:
    """Every other file in the same directory that is a teaser variant of
    base_filename (its stem plus "-<platform>.md")."""
    prefix = base_filename[:-3] + "-"
    return sorted(name for name in filenames if name != base_filename and name.startswith(prefix))


def slug_from_base_filename(base_filename: str) -> str:
    """Strips the "NN-" ordering prefix and ".md" extension -- this becomes
    both the published filename (content/blog/<slug>.md) and the URL slug,
    per content/pending-blogs/README.md's documented manual process."""
    match = _NUMBERED_RE.match(base_filename)
    if not match:
        raise ValueError(f"{base_filename!r} is not an NN-<slug>.md pending-blog filename")
    return match.group(2)


def set_front_matter_date(content: str, new_date: str) -> str:
    """Replaces the draft placeholder "date:" line with the real publish
    date. Raises ValueError if the file has no date line, rather than
    silently leaving the placeholder in a live post."""
    new_content, count = _DATE_LINE_RE.subn(f"date: {new_date}", content, count=1)
    if count == 0:
        raise ValueError("no 'date:' line found in front matter")
    return new_content


def fill_post_url(content: str, url: str) -> str:
    return content.replace("{{post_url}}", url)


def parse_front_matter(content: str) -> tuple[dict[str, str], str]:
    """A deliberately simple line-by-line parser (same spirit as
    build_blog.py's own front-matter handling) -- good enough for these
    hand-written files, not a general YAML parser. Multi-line block
    scalars (e.g. "note: >") are skipped: only the first colon-led line
    for each key is kept, and unrecognized/continuation lines are ignored
    since nothing here needs them.
    """
    match = _FRONT_MATTER_RE.match(content)
    if not match:
        raise ValueError("missing '---' front matter block")
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        line_match = _FRONT_MATTER_LINE_RE.match(line)
        if line_match:
            fields[line_match.group(1)] = line_match.group(2).strip()
    return fields, match.group(2).strip()


def devto_payload(variant_content: str, post_url: str) -> dict:
    """Builds the JSON body for POST https://dev.to/api/articles from a
    pending-blogs "-devto.md" variant file's own content. Always
    publishes live (published: true) regardless of the file's own
    "published: false" placeholder -- that field is an authoring
    reminder ("flip this when ready"), and this function is only ever
    called once this script has decided it IS ready.
    """
    fields, body = parse_front_matter(variant_content)
    tags = [t.strip() for t in fields.get("tags", "").split(",") if t.strip()]
    return {
        "article": {
            "title": fields.get("title", ""),
            "published": True,
            "tags": tags,
            "canonical_url": post_url,
            "body_markdown": fill_post_url(body, post_url),
        }
    }
