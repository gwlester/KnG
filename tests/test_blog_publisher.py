import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools" / "blog_publisher"))

from blog_publisher import (  # noqa: E402
    devto_payload,
    fill_post_url,
    find_next_post,
    platform_from_variant,
    parse_front_matter,
    set_front_matter_date,
    slug_from_base_filename,
    variant_filenames,
)

PENDING_FILES = [
    "README.md",
    "01-unit-testing-python-tkinter-desktop-programs.md",
    "01-unit-testing-python-tkinter-desktop-programs-linkedin.md",
    "01-unit-testing-python-tkinter-desktop-programs-facebook.md",
    "01-unit-testing-python-tkinter-desktop-programs-mewe.md",
    "02-end-to-end-testing-python-tkinter-desktop-programs.md",
    "02-end-to-end-testing-python-tkinter-desktop-programs-linkedin.md",
]


class FindNextPostTests(unittest.TestCase):
    def test_picks_the_lowest_numbered_base_post(self):
        self.assertEqual(find_next_post(PENDING_FILES), "01-unit-testing-python-tkinter-desktop-programs.md")

    def test_skips_a_consumed_topic_whose_files_are_gone(self):
        remaining = [f for f in PENDING_FILES if not f.startswith("01-")]
        self.assertEqual(
            find_next_post(remaining), "02-end-to-end-testing-python-tkinter-desktop-programs.md"
        )

    def test_returns_none_once_the_queue_is_empty(self):
        self.assertIsNone(find_next_post(["README.md"]))
        self.assertIsNone(find_next_post([]))

    def test_ignores_files_with_no_numeric_prefix(self):
        self.assertIsNone(find_next_post(["README.md", "not-a-numbered-post.md"]))


class VariantFilenamesTests(unittest.TestCase):
    def test_finds_every_sibling_teaser(self):
        result = variant_filenames("01-unit-testing-python-tkinter-desktop-programs.md", PENDING_FILES)
        self.assertEqual(
            result,
            [
                "01-unit-testing-python-tkinter-desktop-programs-facebook.md",
                "01-unit-testing-python-tkinter-desktop-programs-linkedin.md",
                "01-unit-testing-python-tkinter-desktop-programs-mewe.md",
            ],
        )

    def test_does_not_pick_up_a_different_topics_variants(self):
        result = variant_filenames("01-unit-testing-python-tkinter-desktop-programs.md", PENDING_FILES)
        self.assertNotIn("02-end-to-end-testing-python-tkinter-desktop-programs-linkedin.md", result)


class PlatformFromVariantTests(unittest.TestCase):
    def test_extracts_the_platform_name(self):
        base = "06-remote-logging-for-a-smaller-project.md"
        self.assertEqual(platform_from_variant(base, "06-remote-logging-for-a-smaller-project-linkedin.md"), "linkedin")
        self.assertEqual(platform_from_variant(base, "06-remote-logging-for-a-smaller-project-reddit-programming.md"), "reddit-programming")


class SlugFromBaseFilenameTests(unittest.TestCase):
    def test_strips_the_ordering_prefix_and_extension(self):
        self.assertEqual(
            slug_from_base_filename("01-unit-testing-python-tkinter-desktop-programs.md"),
            "unit-testing-python-tkinter-desktop-programs",
        )

    def test_rejects_a_filename_with_no_numeric_prefix(self):
        with self.assertRaises(ValueError):
            slug_from_base_filename("not-numbered.md")


class SetFrontMatterDateTests(unittest.TestCase):
    def test_replaces_the_placeholder_date(self):
        content = "---\ntitle: X\ndate: 2026-09-22\nsummary: Y\n---\n\nBody.\n"
        result = set_front_matter_date(content, "2026-11-03")
        self.assertIn("date: 2026-11-03", result)
        self.assertNotIn("2026-09-22", result)
        self.assertIn("Body.", result)

    def test_raises_when_there_is_no_date_line(self):
        with self.assertRaises(ValueError):
            set_front_matter_date("---\ntitle: X\n---\n\nBody.\n", "2026-11-03")


class FillPostUrlTests(unittest.TestCase):
    def test_replaces_every_occurrence(self):
        content = "Read it here: {{post_url}}\n\nAlso see {{post_url}}."
        result = fill_post_url(content, "https://www.kng-consulting.com/blog/x.html")
        self.assertNotIn("{{post_url}}", result)
        self.assertEqual(result.count("https://www.kng-consulting.com/blog/x.html"), 2)


class ParseFrontMatterTests(unittest.TestCase):
    def test_parses_simple_fields_and_skips_block_scalars(self):
        content = (
            "---\n"
            "title: Test Driven Development with Claude\n"
            "published: false\n"
            "tags: testing, ai, tdd, python\n"
            'canonical_url: "{{post_url}}"\n'
            "note: >\n"
            "  Multi-line instructions that\n"
            "  should not break parsing.\n"
            "---\n"
            "\n"
            "Body text.\n"
        )
        fields, body = parse_front_matter(content)
        self.assertEqual(fields["title"], "Test Driven Development with Claude")
        self.assertEqual(fields["tags"], "testing, ai, tdd, python")
        self.assertEqual(body, "Body text.")

    def test_raises_without_a_front_matter_block(self):
        with self.assertRaises(ValueError):
            parse_front_matter("Just a body, no front matter.")


class DevtoPayloadTests(unittest.TestCase):
    def test_builds_the_expected_payload(self):
        content = (
            "---\n"
            "title: Test Driven Development with Claude\n"
            "published: false\n"
            "tags: testing, ai, tdd, python\n"
            'canonical_url: "{{post_url}}"\n'
            "---\n"
            "\n"
            "Body with a link: {{post_url}}\n"
        )
        payload = devto_payload(content, "https://www.kng-consulting.com/blog/tdd.html")
        article = payload["article"]
        self.assertEqual(article["title"], "Test Driven Development with Claude")
        self.assertIs(article["published"], True)
        self.assertEqual(article["tags"], ["testing", "ai", "tdd", "python"])
        self.assertEqual(article["canonical_url"], "https://www.kng-consulting.com/blog/tdd.html")
        self.assertIn("https://www.kng-consulting.com/blog/tdd.html", article["body_markdown"])
        self.assertNotIn("{{post_url}}", article["body_markdown"])


if __name__ == "__main__":
    unittest.main()
