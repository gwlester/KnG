import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

APK_URL = "https://github.com/gwlester/findit/releases/latest/download/findcache.apk"
GUIDE_SLUGS = (
    "findcache-getting-started",
    "findcache-saving-places",
    "findcache-finding-a-place",
    "findcache-maps",
    "findcache-sharing",
    "findcache-files",
    "findcache-settings",
    "findcache-help",
)


def read(name):
    return (ROOT / "www" / name).read_text(encoding="utf-8")


class FunNavTests(unittest.TestCase):
    def test_just_for_fun_is_in_the_nav_after_training(self):
        import build_blog

        items = build_blog.NAV_ITEMS
        self.assertIn(("fun.html", "Just for Fun"), items)
        self.assertEqual(items.index(("fun.html", "Just for Fun")), items.index(("training.html", "Training")) + 1)

    def test_findcache_privacy_is_in_the_footer(self):
        import build_blog

        self.assertIn(("findcache-privacy.html", "FindCache Privacy"), build_blog.FOOTER_EXTRA)


class FunLandingPageTests(unittest.TestCase):
    def test_teaser_qr_and_link(self):
        html = read("fun.html")
        self.assertIn('aria-current="page">Just for Fun', html)
        self.assertIn('href="findcache.html"', html)
        self.assertIn("FindCache", html)
        self.assertIn("averag", html.lower())
        self.assertIn(f'href="{APK_URL}"', html)
        self.assertRegex(html, r'<img[^>]+src="img/findcache/qr\.svg"[^>]+alt="[^"]+"')

    def test_qr_file_exists_and_is_svg(self):
        svg = (ROOT / "www" / "img" / "findcache" / "qr.svg").read_text(encoding="utf-8")
        self.assertTrue(svg.lstrip().startswith("<svg"))


class FindCachePagesTests(unittest.TestCase):
    def test_every_content_file_becomes_a_page_in_the_fun_section(self):
        sources = sorted((ROOT / "content" / "findcache").glob("*.md"))
        slugs = {p.stem for p in sources}
        self.assertEqual(slugs, {"findcache", *GUIDE_SLUGS})
        for slug in slugs:
            with self.subTest(page=slug):
                html = read(f"{slug}.html")
                self.assertIn('aria-current="page">Just for Fun', html)
                self.assertIn("<h1>", html)
                self.assertNotIn("{{", html)

    def test_overview_links_to_every_guide_page_and_each_links_back(self):
        overview = read("findcache.html")
        for slug in GUIDE_SLUGS:
            with self.subTest(page=slug):
                self.assertIn(f'href="{slug}.html"', overview)
                self.assertIn('href="findcache.html"', read(f"{slug}.html"))

    def test_overview_has_qr_download_and_privacy_link(self):
        html = read("findcache.html")
        self.assertIn(f'href="{APK_URL}"', html)
        self.assertIn('src="img/findcache/qr.svg"', html)
        self.assertIn('href="findcache-privacy.html"', html)

    def test_findcache_privacy_page_is_published(self):
        html = read("findcache-privacy.html")
        self.assertIn("FindCache", html)
        self.assertIn("no account, no ads and no analytics", html)

    def test_internal_links_and_images_resolve(self):
        names = ["fun.html", "findcache.html", "findcache-privacy.html"] + [f"{s}.html" for s in GUIDE_SLUGS]
        for name in names:
            html = read(name)
            for ref in re.findall(r'(?:href|src)="([^"#:]+?)(?:#[^"]*)?"', html):
                if ref.startswith(("http", "mailto")):
                    continue
                with self.subTest(page=name, ref=ref):
                    self.assertTrue((ROOT / "www" / ref).exists(), ref)

    def test_screenshots_have_alt_text(self):
        for slug in ("findcache", *GUIDE_SLUGS):
            for tag in re.findall(r"<img[^>]*>", read(f"{slug}.html")):
                with self.subTest(page=slug, tag=tag):
                    self.assertRegex(tag, r'alt="[^"]+"')


if __name__ == "__main__":
    unittest.main()
