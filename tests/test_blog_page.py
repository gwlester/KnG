import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def make_posts(n):
    import build_blog
    return [build_blog.Post(slug=f"post-{i}", title=f"Post number {i}", date=date(2026, 9 - (i % 3), 20 - i), summary=f"Teaser {i}",
                            author="G", body_html=f"<p>Body of post {i} mentions widgets.</p>") for i in range(n)]


class BlogPageTests(unittest.TestCase):
    def setUp(self):
        import build_blog
        self.b = build_blog

    def test_latest_shows_teaser_older_are_collapsed(self):
        html = self.b.render_archive_page(make_posts(3))
        self.assertIn("Teaser 0", html)
        self.assertEqual(html.count('class="card blog-latest"'), 1)
        self.assertEqual(html.count("<details"), 2)
        self.assertIn("Read the full post", html)

    def test_filter_is_in_the_page_but_hidden_up_to_ten_posts(self):
        for n in (2, 5, 10):
            with self.subTest(n=n):
                self.assertRegex(self.b.render_archive_page(make_posts(n)), r'id="blog-filter"[^>]*\shidden')

    def test_filter_shows_with_more_than_ten_posts(self):
        html = self.b.render_archive_page(make_posts(11))
        self.assertIn('id="blog-filter"', html)
        self.assertNotRegex(html, r'id="blog-filter"[^>]*\shidden')

    def test_items_carry_month_and_search_text(self):
        html = self.b.render_archive_page(make_posts(3))
        self.assertIn('data-month="2026-', html)
        self.assertIn("widgets", html)

    def test_single_post_has_no_earlier_section(self):
        self.assertNotIn("Earlier posts", self.b.render_archive_page(make_posts(1)))


if __name__ == "__main__":
    unittest.main()
