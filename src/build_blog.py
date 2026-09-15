#!/usr/bin/env python3
"""Render content/blog/*.md into www/blog/ and refresh the homepage's
latest-posts section. Run locally to preview, or via deploy-to-aws.yml
before the S3 sync. No arguments."""

import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import markdown

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content" / "blog"
WWW_DIR = REPO_ROOT / "www"
BLOG_OUT_DIR = WWW_DIR / "blog"
INDEX_HTML = WWW_DIR / "index.html"
LATEST_POST_COUNT = 2

FRONT_MATTER_RE = re.compile(r"\A---\n(.*?\n)---\n(.*)\Z", re.DOTALL)
BLOG_LATEST_START = "<!-- BLOG_LATEST_START -->"
BLOG_LATEST_END = "<!-- BLOG_LATEST_END -->"


@dataclass
class Post:
    slug: str
    title: str
    date: date
    summary: str
    author: str
    body_html: str

    @property
    def date_display(self) -> str:
        return self.date.strftime("%B %-d, %Y")


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def parse_post(path: Path) -> Post:
    match = FRONT_MATTER_RE.match(path.read_text(encoding="utf-8"))
    if not match:
        raise ValueError(f"{path}: missing '---' front matter block")

    fields = {}
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()

    for required in ("title", "date"):
        if required not in fields:
            raise ValueError(f"{path}: front matter missing '{required}'")

    return Post(
        slug=slugify(fields.get("slug", path.stem)),
        title=fields["title"],
        date=date.fromisoformat(fields["date"]),
        summary=fields.get("summary", ""),
        author=fields.get("author", "Gerald Lester"),
        body_html=markdown.markdown(match.group(2).strip(), extensions=["extra"]),
    )


def load_posts() -> list[Post]:
    paths = sorted(CONTENT_DIR.glob("*.md"))
    posts = [parse_post(p) for p in paths]

    seen: dict[str, Path] = {}
    for path, post in zip(paths, posts):
        if post.slug in seen:
            raise ValueError(
                f"{path} and {seen[post.slug]} both resolve to slug '{post.slug}' -- "
                "add an explicit 'slug:' front-matter field to one of them"
            )
        seen[post.slug] = path

    posts.sort(key=lambda p: p.date, reverse=True)
    return posts


def page_shell(*, title: str, description: str, prefix: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{title}</title>
    <meta name="description" content="{description}" />
    <link rel="stylesheet" href="{prefix}styles.css" />
  </head>
  <body>
    <header class="hero">
      <nav class="top-nav" aria-label="Primary">
        <a class="brand" href="{prefix}index.html">KnG Consulting</a>
        <ul class="nav-links">
          <li><a href="{prefix}index.html#products">Products</a></li>
          <li><a href="{prefix}blog/index.html">Blog</a></li>
          <li><a href="{prefix}coming-soon.html#contact">Contact</a></li>
        </ul>
      </nav>
    </header>
{body}
    <footer class="site-footer">
      <p>© {date.today().year} KnG Consulting</p>
    </footer>
  </body>
</html>
"""


def render_post_page(post: Post) -> str:
    body = f"""
    <main>
      <article class="section post-body">
        <p class="post-meta">By {post.author} · {post.date_display}</p>
        <h1>{post.title}</h1>
        {post.body_html}
        <p><a class="button button-secondary" href="index.html">← Back to all posts</a></p>
      </article>
    </main>"""
    return page_shell(
        title=f"{post.title} | KnG Consulting Blog",
        description=post.summary,
        prefix="../",
        body=body,
    )


def render_archive_page(posts: list[Post]) -> str:
    cards = "\n".join(
        f"""          <article class="card">
            <p class="post-meta">{post.date_display}</p>
            <h3><a href="{post.slug}.html">{post.title}</a></h3>
            <p>{post.summary}</p>
            <a class="button button-secondary" href="{post.slug}.html">Read more</a>
          </article>"""
        for post in posts
    )
    body = f"""
    <main>
      <section class="section">
        <div class="section-heading">
          <p class="eyebrow">Blog</p>
          <h1>Notes from Gerald Lester</h1>
        </div>
        <div class="card-grid">
{cards}
        </div>
      </section>
    </main>"""
    return page_shell(
        title="Blog | KnG Consulting",
        description="Product direction, practical lessons, and what comes next for KnG Consulting.",
        prefix="../",
        body=body,
    )


def render_latest_block(posts: list[Post]) -> str:
    cards = "\n".join(
        f"""        <article class="post-card">
          <p class="post-meta">By {post.author} · {post.date_display}</p>
          <h3><a href="blog/{post.slug}.html">{post.title}</a></h3>
          <p>{post.summary}</p>
        </article>"""
        for post in posts[:LATEST_POST_COUNT]
    )
    return (
        f"{BLOG_LATEST_START}\n"
        f'        <div class="card-grid">\n{cards}\n        </div>\n'
        f'        <p><a class="button button-secondary" href="blog/index.html">View all posts</a></p>\n'
        f"        {BLOG_LATEST_END}"
    )


def update_homepage(posts: list[Post]) -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    pattern = re.compile(
        re.escape(BLOG_LATEST_START) + r".*?" + re.escape(BLOG_LATEST_END), re.DOTALL
    )
    if not pattern.search(html):
        raise ValueError(
            f"{INDEX_HTML}: missing {BLOG_LATEST_START} / {BLOG_LATEST_END} markers"
        )
    html = pattern.sub(render_latest_block(posts), html)
    INDEX_HTML.write_text(html, encoding="utf-8")


def main() -> None:
    posts = load_posts()
    if not posts:
        print(f"No posts found under {CONTENT_DIR}", file=sys.stderr)
        return

    if BLOG_OUT_DIR.exists():
        for existing in BLOG_OUT_DIR.glob("*.html"):
            existing.unlink()
    BLOG_OUT_DIR.mkdir(parents=True, exist_ok=True)

    for post in posts:
        (BLOG_OUT_DIR / f"{post.slug}.html").write_text(
            render_post_page(post), encoding="utf-8"
        )
    (BLOG_OUT_DIR / "index.html").write_text(
        render_archive_page(posts), encoding="utf-8"
    )
    update_homepage(posts)
    print(f"Rendered {len(posts)} post(s) to {BLOG_OUT_DIR}")


if __name__ == "__main__":
    main()
