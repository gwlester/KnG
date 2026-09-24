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
    ("training.html", "Training"),
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
    def plain_text(self) -> str:
        return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", self.body_html))).strip()

    @property
    def month_key(self) -> str:
        return self.date.strftime("%Y-%m")

    @property
    def month_label(self) -> str:
        return self.date.strftime("%B %Y")

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


BLOG_FILTER_MIN_POSTS = 10  # the filter is in the page but hidden until there are MORE than this many posts


def render_archive_page(posts: list[Post]) -> str:
    latest, older = posts[0], posts[1:]
    esc = html_lib.escape
    latest_html = f"""          <article class="card blog-latest" id="{latest.slug}">
            <p class="post-meta">Latest · {latest.date_display}</p>
            <h2><a href="{latest.slug}.html">{latest.title}</a></h2>
            <p>{latest.summary}</p>
            <a class="button button-secondary" href="{latest.slug}.html">Read the full post</a>
          </article>"""
    show_filter = len(posts) > BLOG_FILTER_MIN_POSTS
    months = []
    for post in posts:
        if (post.month_key, post.month_label) not in months:
            months.append((post.month_key, post.month_label))
    options = "\n".join(f'                <option value="{k}">{lbl}</option>' for k, lbl in months)
    filter_html = f"""          <form class="blog-filter" id="blog-filter" role="search" aria-label="Filter posts"{'' if show_filter else ' hidden'}>
            <label>Search <input type="search" id="blog-text" placeholder="Words in a post" /></label>
            <label>Month
              <select id="blog-month">
                <option value="">All dates</option>
{options}
              </select>
            </label>
            <button type="button" class="button button-secondary" id="blog-clear">Clear</button>
            <p class="blog-count" id="blog-count" aria-live="polite"></p>
          </form>"""
    items = "\n".join(
        f"""            <details class="faq-item blog-item" id="{p.slug}" data-month="{p.month_key}" data-search="{esc((p.title + ' ' + p.summary + ' ' + p.plain_text).lower(), quote=True)}">
              <summary><span class="post-meta">{p.date_display}</span> {p.title}</summary>
              <div class="faq-answer">
                <p>{p.summary}</p>
                <p><a href="{p.slug}.html">Read the full post</a></p>
              </div>
            </details>"""
        for p in older
    )
    older_html = (
        f"""          <h2 class="blog-older-heading">Earlier posts</h2>
{filter_html}
          <div class="faq-list blog-list" id="blog-list">
{items}
          </div>""" if older else ""
    )
    body = f"""
    <main>
      <section class="section">
        <div class="container">
          <div class="section-heading">
            <p class="eyebrow">Blog</p>
            <h1>Notes from Gerald Lester</h1>
          </div>
{latest_html}
{older_html}
        </div>
      </section>
      <script src="../blog.js" defer></script>
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
        f"""          <details class="faq-item" id="{slugify(q)}">
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
    """Render content/videos/videos.json into www/training.html: a finder (role, platform, administrator task) that
    fills a "Your videos" panel, then every video grouped by role. A video whose 'available' flag is false shows a
    'Coming soon' placeholder; when it is true the card has a captioned player and a transcript. Video files live
    outside the blue-green site bucket, under the 'media_base' URL. Without scripts the page is simply the grouped list."""
    data = json.loads(VIDEOS_SOURCE.read_text(encoding="utf-8"))
    base = data.get("media_base", "media/")

    def card(v: dict, always: bool) -> str:
        meta_bits = [b for b in (v.get("audience"), v.get("length")) if b]
        meta = f'<p class="video-meta">{" &middot; ".join(_esc(b) for b in meta_bits)}</p>' if meta_bits else ""
        use = f'<p class="video-use"><strong>Use it when</strong> {_esc(v["use_when"])}.</p>' if v.get("use_when") else ""
        status = v["length"] if v.get("available") else "Coming soon"
        if v.get("available"):
            # Versioned file names (id-v<n>) so a re-recorded video is never served stale from the CDN.
            stem = f'{v["id"]}-v{v.get("version", 1)}'
            poster = f' poster="{base}{stem}.jpg"'
            media = (
                f'<video controls preload="none" crossorigin="anonymous"{poster}>'
                f'<source src="{base}{stem}.mp4" type="video/mp4" />'
                f'<track kind="captions" src="{base}{stem}.vtt" srclang="en" label="English" default />'
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
        attrs = (
            f'data-roles="{_esc(",".join(v.get("roles", [])))}" data-platforms="{_esc(",".join(v.get("platforms", [])))}" '
            f'data-task="{_esc(v.get("task") or "")}" data-always="{"true" if always else "false"}" '
            f'data-use="{_esc(v.get("use_when", ""))}" data-status="{_esc(status)}"'
        )
        return f"""          <article class="video-card" id="{_esc(v["id"])}" {attrs}>
            {media}
            <h3>{_esc(v["title"])}</h3>
            {meta}{use}
            <p>{_esc(v["blurb"])}</p>{extra}
          </article>"""

    sections = "\n".join(
        f"""        <section class="video-section" id="{_esc(sec["id"])}">
          <h2>{_esc(sec["title"])}</h2>{f'<p class="video-note">{_esc(sec["note"])}</p>' if sec.get("note") else ""}
          <div class="video-grid">
{chr(10).join(card(v, sec["id"] == "see-it") for v in sec["videos"])}
          </div>
        </section>"""
        for sec in data["sections"]
    )

    def options(items, first):
        return f'<option value="">{_esc(first)}</option>' + "".join(f'<option value="{_esc(i["id"])}">{_esc(i["label"])}</option>' for i in items)

    finder = f"""          <div class="finder" id="finder" hidden>
            <h2>Find your videos</h2>
            <p>Tell us a little and we will show just the videos that fit. Nothing is saved or sent anywhere.</p>
            <div class="finder-fields">
              <p><label for="finder-role">I am the&hellip;</label>
                <select id="finder-role">{options(data["roles"], "Choose a role")}</select></p>
              <p><label for="finder-platform">I use&hellip;</label>
                <select id="finder-platform"><option value="both">Any device</option>{"".join(f'<option value="{_esc(p["id"])}">{_esc(p["label"])}</option>' for p in data["platforms"])}</select></p>
              <p id="finder-task-wrap" hidden><label for="finder-task">I need to&hellip;</label>
                <select id="finder-task">{options(data["admin_tasks"], "Show all administrator videos")}</select></p>
              <p><button type="button" class="button button-secondary" id="finder-reset">Show all videos</button></p>
            </div>
            <section id="your-videos" aria-live="polite" hidden>
              <h3 id="your-videos-title">Your videos</h3>
              <ol id="your-videos-list"></ol>
            </section>
          </div>"""
    body = f"""
    <main>
      <article class="section">
        <div class="container">
          <h1>Training</h1>
          <p class="lead">{_esc(data["intro"])} Need something else? See <a href="faq.html">Support and FAQ</a> or <a href="contact.html">contact us</a>.</p>
{finder}
{sections}
        </div>
      </article>
      <script src="training.js" defer></script>
    </main>"""
    out = WWW_DIR / "training.html"
    out.write_text(
        page_shell(
            title="Training | KnG Consulting",
            description="Training and demo videos for Virtual Church Musician, by role: connecting to your VCM Server, and using VCM Administrator, VCM Templates, VCM Services and VCM Runner.",
            prefix="",
            body=body,
            current="training.html",
        ),
        encoding="utf-8",
    )
    return out


COMMERCIAL_ID = "ready-when-you-are"


def _commercial(data: dict) -> dict | None:
    for sec in data["sections"]:
        for v in sec["videos"]:
            if v["id"] == COMMERCIAL_ID and v.get("available"):
                return v
    return None


def _player(v: dict, base: str, extra_class: str = "") -> str:
    stem = f'{v["id"]}-v{v.get("version", 1)}'
    return (
        f'<video class="{extra_class}" controls preload="none" crossorigin="anonymous" poster="{base}{stem}.jpg">'
        f'<source src="{base}{stem}.mp4" type="video/mp4" />'
        f'<track kind="captions" src="{base}{stem}.vtt" srclang="en" label="English" default />'
        "Your browser does not play this video.</video>"
    )


def refresh_commercial_hooks(www_dir: Path | None = None, data: dict | None = None) -> None:
    """The commercial appears on the home page (a button that opens a watch page in a new tab), on the product page
    (an embedded player, no autoplay) and on its own watch page, but only once its 'available' flag is true in
    content/videos/videos.json. Until then all three are empty and no watch page is written."""
    www = www_dir or WWW_DIR
    data = data or json.loads(VIDEOS_SOURCE.read_text(encoding="utf-8"))
    v = _commercial(data)
    base = data.get("media_base", "media/")
    button = ""
    player = ""
    watch = www / "watch.html"
    if v:
        button = (
            f'            <a class="button button-secondary" href="watch.html" target="_blank" rel="noopener">'
            f'Watch the story ({_esc(v["length"].replace("about ", ""))}) <span class="new-tab-icon" aria-hidden="true">&#8599;</span></a>'
        )
        player = (
            '        <div class="hero-video">\n          ' + _player(v, base) + "\n"
            '          <p class="video-disclosure">Dramatization. Scenes created with AI.</p>\n        </div>'
        )
        transcript = v.get("transcript_html", "")
        body = f"""
    <main>
      <article class="section">
        <div class="container watch">
          <h1>{_esc(v["title"])}</h1>
          <p class="lead">{_esc(v["blurb"])}</p>
          {_player(v, base, "watch-video")}
          <p class="video-disclosure">Dramatization. Scenes created with AI.</p>{f'<details class="video-transcript"><summary>Transcript</summary>{transcript}</details>' if transcript else ""}
          <p class="hero-actions"><a class="button button-primary" href="download.html">Download</a>
            <a class="button button-secondary" href="training.html">Training videos</a></p>
        </div>
      </article>
    </main>"""
        watch.write_text(
            page_shell(title=f'{v["title"]} | KnG Consulting', description=v["blurb"], prefix="", body=body),
            encoding="utf-8",
        )
    elif watch.exists():
        watch.unlink()
    for name, start, end, text in (
        ("index.html", "<!-- COMMERCIAL_BUTTON_START -->", "<!-- COMMERCIAL_BUTTON_END -->", button),
        ("virtual-church-musician.html", "<!-- COMMERCIAL_PLAYER_START -->", "<!-- COMMERCIAL_PLAYER_END -->", player),
    ):
        path = www / name
        html = path.read_text(encoding="utf-8")
        path.write_text(_replace_between(html, start, end, text, path), encoding="utf-8")


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
            <div class="field" id="pick-password-wrap" hidden>
              <label for="pick-password">Access code</label>
              <input type="text" id="pick-password" autocomplete="off" spellcheck="false" />
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
    cols = [("mac", "macOS"), ("windows", "Windows"), ("linux", "Linux"), ("raspberry-pi", "Raspberry Pi"), ("android", "Android")]
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
    refresh_commercial_hooks()
    refresh_download_page()
    refresh_chrome()
    print(f"Rendered {len(posts)} post(s) to {BLOG_OUT_DIR}")
    print(f"Rendered {len(legal)} legal page(s) to {WWW_DIR}")


if __name__ == "__main__":
    main()
