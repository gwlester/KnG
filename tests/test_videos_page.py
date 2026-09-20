import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


class VideosPageTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / "content" / "videos" / "videos.json").read_text(encoding="utf-8"))
        self.html = (ROOT / "www" / "videos.html").read_text(encoding="utf-8")

    def all_videos(self):
        return [v for s in self.data["sections"] for v in s["videos"]]

    def test_every_video_is_on_the_page_with_its_anchor(self):
        self.assertEqual(len(self.all_videos()), 11)
        for v in self.all_videos():
            with self.subTest(video=v["id"]):
                self.assertIn(f'id="{v["id"]}"', self.html)

    def test_unavailable_videos_show_a_placeholder_and_no_player(self):
        pending = [v for v in self.all_videos() if not v.get("available")]
        self.assertEqual(self.html.count("Coming soon</span>"), len(pending))
        if len(pending) == len(self.all_videos()):
            self.assertNotIn("<video", self.html)

    def test_available_video_renders_a_captioned_player(self):
        import build_blog

        original = build_blog.VIDEOS_SOURCE.read_text(encoding="utf-8")
        data = json.loads(original)
        data["sections"][0]["videos"][0]["available"] = True
        data["sections"][0]["videos"][0]["transcript_html"] = "<p>Hello.</p>"
        tmp = ROOT / "content" / "videos" / "_test_videos.json"
        try:
            tmp.write_text(json.dumps(data), encoding="utf-8")
            saved_src, saved_out = build_blog.VIDEOS_SOURCE, build_blog.WWW_DIR
            build_blog.VIDEOS_SOURCE = tmp
            build_blog.WWW_DIR = ROOT / "content" / "videos"
            build_blog.WWW_DIR.mkdir(exist_ok=True)
            out = build_blog.render_videos_page()
            html = out.read_text(encoding="utf-8")
            out.unlink()
        finally:
            build_blog.VIDEOS_SOURCE, build_blog.WWW_DIR = saved_src, saved_out
            tmp.unlink(missing_ok=True)
        self.assertIn('<track kind="captions"', html)
        self.assertIn("overview-v1.mp4", html)
        self.assertIn("https://d1ra9wr4fsrl0u.cloudfront.net/", html)
        self.assertIn('crossorigin="anonymous"', html)
        self.assertIn("Transcript", html)

    def test_support_links_to_the_videos_page(self):
        faq = (ROOT / "www" / "faq.html").read_text(encoding="utf-8")
        self.assertIn('href="videos.html"', faq)

    def test_videos_are_not_copied_into_the_release_bucket(self):
        # The page references media/ files; nothing in www/ may be a video file,
        # because www/ is copied to releases/<sha>/ on every deploy.
        for path in (ROOT / "www").rglob("*"):
            self.assertNotIn(path.suffix.lower(), {".mp4", ".webm", ".mov"}, str(path))


if __name__ == "__main__":
    unittest.main()
