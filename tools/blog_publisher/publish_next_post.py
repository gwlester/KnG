#!/usr/bin/env python3
"""Monthly blog-publish script: moves the next queued post out of
content/pending-blogs/ into content/blog/, regenerates the site, posts
the Dev.to cross-post (if that topic has one) via Dev.to's API, and
stages every other teaser's filled-in text in the GitHub Actions step
summary for Gerald to paste in by hand (Facebook/MeWe/LinkedIn --
none of those have a posting API that's both official and usable for
this, see Prompts/ToDo.md's "Monthly Blog Publishing" item).

Does not touch git at all -- the calling workflow commits/pushes the
result. Run from the repository root:

    python3 tools/blog_publisher/publish_next_post.py [--today YYYY-MM-DD] [--dry-run]

Exit code 0 whether or not a post was found (an empty queue is not a
failure); non-zero only on an actual error.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blog_publisher import (  # noqa: E402
    devto_payload,
    fill_post_url,
    find_next_post,
    set_front_matter_date,
    slug_from_base_filename,
    variant_filenames,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PENDING_DIR = REPO_ROOT / "content" / "pending-blogs"
BLOG_DIR = REPO_ROOT / "content" / "blog"
SITE_URL = "https://www.kng-consulting.com"
DEVTO_API_URL = "https://dev.to/api/articles"


def _write_summary(text: str) -> None:
    print(text)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(text + "\n")


def _post_to_devto(payload: dict, api_key: str) -> str:
    req = urllib.request.Request(
        DEVTO_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"api-key": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        body = json.loads(response.read().decode("utf-8"))
    return body.get("url", "(no url in response)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--today", default=date.today().isoformat(), help="Publish date (YYYY-MM-DD).")
    parser.add_argument("--dry-run", action="store_true", help="Do everything except write/delete/post.")
    args = parser.parse_args()

    filenames = sorted(p.name for p in PENDING_DIR.glob("*.md"))
    base_filename = find_next_post(filenames)
    if base_filename is None:
        _write_summary("## Monthly blog post\n\ncontent/pending-blogs/ is empty -- nothing to publish this month.")
        return 0

    slug = slug_from_base_filename(base_filename)
    post_url = f"{SITE_URL}/blog/{slug}.html"
    variants = variant_filenames(base_filename, filenames)

    base_path = PENDING_DIR / base_filename
    content = set_front_matter_date(base_path.read_text(encoding="utf-8"), args.today)
    dest_path = BLOG_DIR / f"{slug}.md"

    _write_summary(f"## Monthly blog post\n\nPublishing **{slug}** ({post_url}).")

    if args.dry_run:
        print(f"[dry-run] would write {dest_path}")
    else:
        dest_path.write_text(content, encoding="utf-8")
        base_path.unlink()

    if not args.dry_run:
        subprocess.run([sys.executable, "src/build_blog.py"], cwd=REPO_ROOT, check=True)

    devto_api_key = os.environ.get("DEVTO_API_KEY")
    for variant_name in variants:
        variant_path = PENDING_DIR / variant_name
        variant_content = fill_post_url(variant_path.read_text(encoding="utf-8"), post_url)

        if variant_name.endswith("-devto.md"):
            if devto_api_key and not args.dry_run:
                url = _post_to_devto(devto_payload(variant_content, post_url), devto_api_key)
                _write_summary(f"- Posted to Dev.to: {url}")
            else:
                _write_summary(
                    f"- **Dev.to (not posted{' -- dry run' if args.dry_run else ' -- DEVTO_API_KEY not set'}):**\n"
                    f"```\n{variant_content}\n```"
                )
        else:
            platform = variant_name[len(base_filename[:-3]) + 1 : -3]
            _write_summary(f"- **{platform} (paste this in by hand):**\n```\n{variant_content}\n```")

        if not args.dry_run:
            variant_path.unlink()

    _write_summary(
        "\nThe live site switch still needs manual approval in GitHub Actions "
        "(the production-switch environment's required reviewer) -- this script "
        "only updated preview via the normal push-triggered deploy."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
