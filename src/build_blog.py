#!/usr/bin/env python3
"""Render content/blog/*.md into www/blog/, content/legal/*.md and
content/faq.md into www/<slug>.html, refresh the shared header/footer on
the hand-written pages, and refresh the homepage's latest-posts section.
Run locally to preview, or via deploy-to-aws.yml before the S3 sync. No
arguments."""

import html as html_lib
import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import markdown

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content" / "blog"
LEGAL_DIR = REPO_ROOT / "content" / "legal"
FAQ_SOURCE = REPO_ROOT / "content" / "faq.md"
DOWNLOAD_OPTIONS = REPO_ROOT / "content" / "downloads" / "options.json"
DOWNLOAD_PAGE = REPO_ROOT / "www" / "download.html"
VIDEOS_SOURCE = REPO_ROOT / "content" / "videos" / "videos.json"
SITE_URL = "https://www.kng-consulting.com"
# Verify against the Louisiana Secretary of State registration.
LEGAL_ENTITY = "KnG Consulting, LLC"

NAV_ITEMS = [
    ("virtual-church-musician.html", "Virtual Church Musician"),
    ("services.html", "Services"),
    ("download.html", "Download"),
    ("faq.html", "Support"),
    ("blog/index.html", "Blog"),
    ("contact.html", "Contact"),
]
FOOTER_EXTRA = [
    ("privacy.html", "Privacy"),
    ("license.html", "License"),
    ("services-terms.html", "Services Terms"),
]
HEADER_START = "<!-- SITE_HEADER_START -->"
HEADER_END = "<!-- SITE_HEADER_END -->"
FOOTER_START = "<!-- SITE_FOOTER_START -->"
FOOTER_END = "<!-- SITE_FOOTER_END -->"
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


def header_html(prefix: str, current: str | None = None) -> str:
    items = "\n".join(
        f'          <li><a href="{prefix}{href}"'
        + (' aria-current="page"' if href == current else "")
        + f">{label}</a></li>"
        for href, label in NAV_ITEMS
    )
    return f"""    <header class="site-header">
      <nav class="top-nav" aria-label="Primary">
        <a class="brand" href="{prefix}index.html"><span class="brand-mark" aria-hidden="true">K</span>KnG Consulting</a>
        <ul class="nav-links">
{items}
        </ul>
      </nav>
    </header>"""


def footer_html(prefix: str) -> str:
    items = "\n".join(
        f'          <li><a href="{prefix}{href}">{label}</a></li>'
        for href, label in NAV_ITEMS + FOOTER_EXTRA
    )
    return f"""    <footer class="site-footer">
      <div class="footer-inner">
        <p>© {date.today().year} {LEGAL_ENTITY}</p>
        <ul class="footer-links">
{items}
        </ul>
      </div>
    </footer>"""


def page_shell(
    *,
    title: str,
    description: str,
    prefix: str,
    body: str,
    current: str | None = None,
    head_extra: str = "",
) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{title}</title>
    <meta name="description" content="{description}" />
    <link rel="stylesheet" href="{prefix}styles.css" />{head_extra}
  </head>
  <body>
{HEADER_START}
{header_html(prefix, current)}
{HEADER_END}
{body}
{FOOTER_START}
{footer_html(prefix)}
{FOOTER_END}
  </body>
</html>
"""


def _replace_between(html: str, start: str, end: str, replacement: str, path: Path) -> str:
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    if not pattern.search(html):
        raise ValueError(f"{path}: missing {start} / {end} markers")
    return pattern.sub(lambda _m: f"{start}\n{replacement}\n{end}", html)


def refresh_chrome() -> None:
    """Rewrite the shared header/footer in the hand-written top-level pages."""
    for path in sorted(WWW_DIR.glob("*.html")):
        html = path.read_text(encoding="utf-8")
        if HEADER_START not in html:
            continue
        html = _replace_between(html, HEADER_START, HEADER_END, header_html("", path.name), path)
        html = _replace_between(html, FOOTER_START, FOOTER_END, footer_html(""), path)
        path.write_text(html, encoding="utf-8")


def render_tokens(text: str) -> str:
    """Fill {{legal_entity}} and {{refund_days}} in Markdown content."""
    license_text = (LEGAL_DIR / "license-agreement.md").read_text(encoding="utf-8")
    refund = re.search(r"refund within \*\*(\d+) days\*\*", license_text)
    if not refund:
        raise ValueError("license-agreement.md: could not find the refund period")
    return text.replace("{{legal_entity}}", LEGAL_ENTITY).replace("{{refund_days}}", refund.group(1))


def render_post_page(post: Post) -> str:
    body = f"""
    <main>
      <article class="section">
        <div class="container post-body">
          <p class="post-meta">By {post.author} · {post.date_display}</p>
          <h1>{post.title}</h1>
          {post.body_html}
          <p><a class="button button-secondary" href="index.html">← Back to all posts</a></p>
        </div>
      </article>
    </main>"""
    return page_shell(
        title=f"{post.title} | KnG Consulting Blog",
        description=post.summary,
        prefix="../",
        body=body,
        current="blog/index.html",
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
        <div class="container">
          <div class="section-heading">
            <p class="eyebrow">Blog</p>
            <h1>Notes from Gerald Lester</h1>
          </div>
          <div class="card-grid">
{cards}
          </div>
        </div>
      </section>
    </main>"""
    return page_shell(
        title="Blog | KnG Consulting",
        description="Product direction, practical lessons, and what comes next for KnG Consulting.",
        prefix="../",
        body=body,
        current="blog/index.html",
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


def render_legal_pages() -> list[Path]:
    """Render content/legal/*.md (front matter: title, slug, description)
    into www/<slug>.html. Returns the written paths."""
    written = []
    for path in sorted(LEGAL_DIR.glob("*.md")):
        match = FRONT_MATTER_RE.match(path.read_text(encoding="utf-8"))
        if not match:
            raise ValueError(f"{path}: missing '---' front matter block")
        fields = {}
        for line in match.group(1).splitlines():
            key, _, value = line.partition(":")
            if key.strip():
                fields[key.strip()] = value.strip()
        for required in ("title", "slug"):
            if required not in fields:
                raise ValueError(f"{path}: front matter missing '{required}'")
        body_html = markdown.markdown(render_tokens(match.group(2)).strip(), extensions=["extra"])
        body = f"""
    <main>
      <article class="section">
        <div class="container post-body">
          <h1>{fields["title"]}</h1>
          {body_html}
        </div>
      </article>
    </main>"""
        out = WWW_DIR / f"{slugify(fields['slug'])}.html"
        out.write_text(
            page_shell(
                title=f"{fields['title']} | KnG Consulting",
                description=fields.get("description", ""),
                prefix="",
                body=body,
            ),
            encoding="utf-8",
        )
        written.append(out)
    return written


def render_faq_page() -> Path:
    """Render content/faq.md (front matter, an intro, then one '## Question'
    heading per entry) into www/faq.html, with FAQPage structured data."""
    match = FRONT_MATTER_RE.match(FAQ_SOURCE.read_text(encoding="utf-8"))
    if not match:
        raise ValueError(f"{FAQ_SOURCE}: missing '---' front matter block")
    fields = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        if key.strip():
            fields[key.strip()] = value.strip()
    parts = re.split(r"^## (.+)$", render_tokens(match.group(2)), flags=re.MULTILINE)
    intro_html = markdown.markdown(parts[0].strip(), extensions=["extra"])
    entries = []
    for question, answer in zip(parts[1::2], parts[2::2]):
        entries.append((question.strip(), markdown.markdown(answer.strip(), extensions=["extra"])))
    if not entries:
        raise ValueError(f"{FAQ_SOURCE}: no '## Question' entries found")

    items = "\n".join(
        f"""          <details class="faq-item">
            <summary>{q}</summary>
            <div class="faq-answer">{a}</div>
          </details>"""
        for q, a in entries
    )
    body = f"""
    <main>
      <article class="section">
        <div class="container post-body">
          <h1>{fields["title"]}</h1>
          {intro_html}
          <div class="faq-list">
{items}
          </div>
        </div>
      </article>
    </main>"""

    def plain(fragment: str) -> str:
        return html_lib.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()

    ld = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": plain(a)},
            }
            for q, a in entries
        ],
    }
    head_extra = (
        '\n    <script type="application/ld+json">'
        + json.dumps(ld, ensure_ascii=False).replace("</", "<\\/")
        + "</script>"
    )
    out = WWW_DIR / "faq.html"
    out.write_text(
        page_shell(
            title=f"{fields['title']} | KnG Consulting",
            description=fields.get("description", ""),
            prefix="",
            body=body,
            current="faq.html",
            head_extra=head_extra,
        ),
        encoding="utf-8",
    )
    return out


def render_videos_page() -> Path:
    """Render content/videos/videos.json into www/videos.html. A video whose
    'available' flag is false shows a 'Coming soon' placeholder; when it is
    true the page shows a captioned player and a transcript. Video files live
    outside the blue-green site bucket, under the 'media_base' path."""
    data = json.loads(VIDEOS_SOURCE.read_text(encoding="utf-8"))
    base = data.get("media_base", "media/")

    def card(v: dict) -> str:
        meta = f'<p class="video-meta">{_esc(v["audience"])} &middot; {_esc(v["length"])}</p>'
        if v.get("available"):
            poster = f' poster="{base}{v["id"]}.jpg"'
            media = (
                f'<video controls preload="metadata"{poster}>'
                f'<source src="{base}{v["id"]}.mp4" type="video/mp4" />'
                f'<track kind="captions" src="{base}{v["id"]}.vtt" srclang="en" label="English" default />'
                "Your browser does not play this video.</video>"
            )
            transcript = v.get("transcript_html", "")
            extra = (
                f'\n            <details class="video-transcript"><summary>Transcript</summary>{transcript}</details>'
                if transcript
                else ""
            )
        else:
            media = '<div class="video-placeholder" role="img" aria-label="Video coming soon"><span>Coming soon</span></div>'
            extra = ""
        return f"""          <article class="video-card" id="{_esc(v["id"])}">
            {media}
            <h3>{_esc(v["title"])}</h3>
            {meta}
            <p>{_esc(v["blurb"])}</p>{extra}
          </article>"""

    sections = "\n".join(
        f"""        <section class="video-section" id="{_esc(sec["id"])}">
          <h2>{_esc(sec["title"])}</h2>
          <div class="video-grid">
{chr(10).join(card(v) for v in sec["videos"])}
          </div>
        </section>"""
        for sec in data["sections"]
    )
    body = f"""
    <main>
      <article class="section">
        <div class="container">
          <h1>Videos</h1>
          <p class="lead">{_esc(data["intro"])} Need something else? See <a href="faq.html">Support and FAQ</a> or <a href="contact.html">contact us</a>.</p>
{sections}
        </div>
      </article>
    </main>"""
    out = WWW_DIR / "videos.html"
    out.write_text(
        page_shell(
            title="Videos | KnG Consulting",
            description="Training and demo videos for Virtual Church Musician: connecting to your Server, and using the Template Editor, Service Builder, Service Runner and Administration Console.",
            prefix="",
            body=body,
            current="faq.html",
        ),
        encoding="utf-8",
    )
    return out


def _esc(text: str) -> str:
    return html_lib.escape(text, quote=True)


def render_picker(options: dict) -> str:
    app_options = "\n".join(
        f'                <option value="{_esc(a["id"])}">{_esc(a["name"])}</option>' for a in options["apps"]
    )
    label = options.get("channel_label", "")
    current = f"Current release ({label})" if label else "Current release"
    data = json.dumps(options, ensure_ascii=False).replace("</", "<\\/")
    return f"""<div class="section-heading" id="picker-heading">
            <p class="eyebrow">Choose your download</p>
            <h2>Pick an app and a platform</h2>
          </div>
          <form class="picker" id="download-picker" data-endpoint="{_esc(options.get("endpoint", ""))}" onsubmit="return false">
            <div class="field">
              <label for="pick-app">Application</label>
              <select id="pick-app">
                <option value="">Choose an app...</option>
{app_options}
              </select>
            </div>
            <fieldset class="field platform-field">
              <legend>Platform</legend>
              <div id="pick-platforms" class="radio-row"></div>
            </fieldset>
            <div class="field">
              <label for="pick-version">Version</label>
              <select id="pick-version">
                <option value="current">{_esc(current)}</option>
                <option value="previous">Previous release</option>
              </select>
            </div>
            <p class="picker-note" id="pick-note" role="status" aria-live="polite">Choose an app and a platform.</p>
            <div class="picker-actions">
              <button class="button button-primary" type="button" id="pick-go" disabled>Download</button>
              <a id="pick-alt" href="#" hidden></a>
            </div>
            <p class="license-note">By downloading you agree to the <a href="license.html">License Agreement</a>.</p>
            <noscript><p class="picker-note">The picker needs JavaScript. The table below shows what is planned.</p></noscript>
          </form>
          <script type="application/json" id="picker-options">{data}</script>"""


def render_availability(options: dict) -> str:
    cols = [("mac", "macOS"), ("windows", "Windows"), ("linux", "Linux"), ("android", "Android")]
    supported = {}
    for app in options["apps"]:
        for plat in app["platforms"]:
            supported.setdefault(plat["matrix_app"], set()).add(plat["id"])
    head = "".join(f'<th scope="col">{label}</th>' for _, label in cols)
    rows = []
    for key, info in options["matrix_apps"].items():
        cells = "".join(
            '<td class="yes">Yes</td>' if pid in supported.get(key, set()) else '<td class="no">-</td>'
            for pid, _ in cols
        )
        rows.append(
            f'                <tr>\n                  <th scope="row">{_esc(info["name"])}<span>{_esc(info["blurb"])}</span></th>\n                  {cells}\n                </tr>'
        )
    body = "\n".join(rows)
    return f"""<div class="table-wrap">
            <table class="platform-table">
              <thead>
                <tr>
                  <th scope="col">App</th>
                  {head}
                </tr>
              </thead>
              <tbody>
{body}
              </tbody>
            </table>
          </div>"""


NEW_TAB_ICON = (
    '<svg class="new-tab-icon" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" focusable="false">'
    '<path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
    'd="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>'
    '<span class="visually-hidden"> (opens in a new tab)</span>'
)


def _doc_link(endpoint: str, kind: str, fmt: str, label: str, available: bool) -> str:
    """HTML guides open in a new tab (with an icon); PDFs and other files download."""
    new_tab = fmt == "html"
    attrs = f'data-doc-kind="{kind}" data-doc-format="{fmt}" data-label="{label}"'
    if new_tab:
        attrs += ' target="_blank" rel="noopener noreferrer"'
    icon = NEW_TAB_ICON if new_tab else ""
    if endpoint and available:
        href = f"{endpoint}?doc={kind}&amp;format={fmt}&amp;version=current&amp;v=1"
        return f'<a class="button button-secondary" href="{href}" {attrs}><span class="doc-label">{label}</span>{icon}</a>'
    return f'<a class="button button-secondary" aria-disabled="true" role="link" {attrs}><span class="doc-label">{label} (coming soon)</span>{icon}</a>'


def render_documents(options: dict) -> str:
    endpoint = options.get("endpoint", "")
    labels = {"html": "Read online", "pdf": "Download PDF"}
    cards = []
    for doc in options["documents"]:
        buttons = " ".join(
            _doc_link(endpoint, doc["kind"], f, labels.get(f, f.upper()), doc["available"]) for f in doc["formats"]
        )
        cards.append(
            f"""            <article class="card">
              <h3>{_esc(doc["title"])}</h3>
              <p>{_esc(doc["description"])}</p>
              <p class="card-actions">{buttons}</p>
            </article>"""
        )
    extras = " &middot; ".join(
        _doc_link(endpoint, e["kind"], e["format"], _esc(e["label"]), e["available"]).replace('class="button button-secondary"', 'class="text-link"')
        for e in options.get("extras", [])
    )
    cards_html = "\n".join(cards)
    return f"""<div class="grid">
{cards_html}
          </div>
          <p class="extras">{extras}</p>"""


def refresh_download_page() -> None:
    options = json.loads(DOWNLOAD_OPTIONS.read_text(encoding="utf-8"))
    html = DOWNLOAD_PAGE.read_text(encoding="utf-8")
    for start, end, block in (
        ("<!-- PICKER_START -->", "<!-- PICKER_END -->", render_picker(options)),
        ("<!-- AVAILABILITY_START -->", "<!-- AVAILABILITY_END -->", render_availability(options)),
        ("<!-- DOCS_START -->", "<!-- DOCS_END -->", render_documents(options)),
    ):
        html = _replace_between(html, start, end, "          " + block, DOWNLOAD_PAGE)
    DOWNLOAD_PAGE.write_text(html, encoding="utf-8")


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
    legal = render_legal_pages()
    render_faq_page()
    render_videos_page()
    refresh_download_page()
    refresh_chrome()
    print(f"Rendered {len(posts)} post(s) to {BLOG_OUT_DIR}")
    print(f"Rendered {len(legal)} legal page(s) to {WWW_DIR}")


if __name__ == "__main__":
    main()
