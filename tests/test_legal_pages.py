import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

FORBIDDEN = ("Young Street", "Metairie", "@gmail.com")


class LegalPagesTests(unittest.TestCase):
    def test_no_personal_details_in_published_files(self):
        files = list((ROOT / "content" / "legal").glob("*.md")) + list((ROOT / "www").glob("*.html"))
        self.assertTrue(files)
        for path in files:
            text = path.read_text(encoding="utf-8")
            for needle in FORBIDDEN:
                with self.subTest(file=path.name, needle=needle):
                    self.assertNotIn(needle, text)

    def test_license_has_no_unfilled_placeholders(self):
        text = (ROOT / "content" / "legal" / "license-agreement.md").read_text(encoding="utf-8")
        for placeholder in ("[support email or URL]", "[State/Country]", "[30] days", "[15] days"):
            self.assertNotIn(placeholder, text)

    def test_generated_pages_exist_and_link_from_footer(self):
        for name in ("privacy.html", "license.html"):
            self.assertTrue((ROOT / "www" / name).exists(), name)
        for name in ("index.html", "download.html", "contact.html", "privacy.html"):
            html = (ROOT / "www" / name).read_text(encoding="utf-8")
            self.assertIn('href="privacy.html"', html, name)
            self.assertIn('href="license.html"', html, name)


class SitePagesTests(unittest.TestCase):
    def read(self, name):
        return (ROOT / "www" / name).read_text(encoding="utf-8")

    def test_every_page_has_the_full_nav_and_footer(self):
        import build_blog

        pages = list((ROOT / "www").glob("*.html")) + list((ROOT / "www" / "blog").glob("*.html"))
        self.assertGreater(len(pages), 8)
        for path in pages:
            html = path.read_text(encoding="utf-8")
            prefix = "../" if path.parent.name == "blog" else ""
            for href, label in build_blog.NAV_ITEMS + build_blog.FOOTER_EXTRA:
                with self.subTest(page=path.name, link=href):
                    self.assertIn(f'href="{prefix}{href}"', html)
            self.assertIn(f"{build_blog.LEGAL_ENTITY}</p>", html)

    def test_no_unfilled_tokens_or_placeholders(self):
        for path in (ROOT / "www").glob("*.html"):
            html = path.read_text(encoding="utf-8")
            with self.subTest(page=path.name):
                self.assertNotIn("{{", html)

    def test_faq_has_entries_and_valid_structured_data(self):
        html = self.read("faq.html")
        self.assertGreaterEqual(html.count('class="faq-item"'), 10)
        match = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
        self.assertIsNotNone(match)
        data = json.loads(match.group(1))
        self.assertEqual(data["@type"], "FAQPage")
        self.assertEqual(len(data["mainEntity"]), html.count('class="faq-item"'))
        self.assertIn("30 days", html)

    def test_services_page_links_each_service_to_a_valid_topic(self):
        html = self.read("services.html")
        contact = self.read("contact.html")
        for topic in ("customization", "hymnal", "hardware"):
            with self.subTest(topic=topic):
                self.assertIn(f"contact.html?topic={topic}", html)
                self.assertIn(f'<option value="{topic}">', contact)

    def test_product_and_home_pages_mention_mp3_and_midi(self):
        for name in ("index.html", "virtual-church-musician.html"):
            html = self.read(name)
            with self.subTest(page=name):
                self.assertIn("MP3", html)
                self.assertIn("MIDI", html)


if __name__ == "__main__":
    unittest.main()
