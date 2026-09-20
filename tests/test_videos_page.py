import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


class VideosPageTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / "content" / "videos" / "videos.json").read_text(encoding="utf-8"))
        self.html = (ROOT / "www" / "training.html").read_text(encoding="utf-8")

    def all_videos(self):
        return [v for s in self.data["sections"] for v in s["videos"]]

    def test_every_video_is_on_the_page_with_its_anchor(self):
        self.assertEqual(len(self.all_videos()), 28)
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

    def test_every_video_has_a_role_a_platform_and_a_use_line(self):
        roles = {r["id"] for r in self.data["roles"]}
        platforms = {p["id"] for p in self.data["platforms"]}
        tasks = {t["id"] for t in self.data["admin_tasks"]}
        for v in self.all_videos():
            with self.subTest(video=v["id"]):
                self.assertTrue(v["roles"] and set(v["roles"]) <= roles)
                self.assertTrue(v["platforms"] and set(v["platforms"]) <= platforms)
                self.assertTrue(v["use_when"])
                if v.get("task") and "admin" in v["roles"]:
                    self.assertIn(v["task"], tasks)

    def test_the_finder_is_in_the_page_and_the_full_list_works_without_scripts(self):
        self.assertIn('id="finder"', self.html)
        self.assertIn("hidden>", self.html.split('id="finder"', 1)[1][:80] + ">")
        self.assertIn('src="training.js"', self.html)
        self.assertEqual(self.html.count("class=\"video-card\""), 28)
        for role in self.data["roles"]:
            self.assertIn(f'<option value="{role["id"]}">', self.html)

    def test_support_links_to_the_videos_page(self):
        faq = (ROOT / "www" / "faq.html").read_text(encoding="utf-8")
        self.assertIn('href="training.html"', faq)

    def test_videos_are_not_copied_into_the_release_bucket(self):
        # The page references media/ files; nothing in www/ may be a video file,
        # because www/ is copied to releases/<sha>/ on every deploy.
        for path in (ROOT / "www").rglob("*"):
            self.assertNotIn(path.suffix.lower(), {".mp4", ".webm", ".mov"}, str(path))


class CommercialHooksTests(unittest.TestCase):
    def setUp(self):
        import build_blog
        self.build_blog = build_blog
        self.data = json.loads((ROOT / "content" / "videos" / "videos.json").read_text(encoding="utf-8"))

    def make_www(self, tmp):
        import shutil
        for name in ("index.html", "virtual-church-musician.html"):
            shutil.copy(ROOT / "www" / name, tmp / name)
        return tmp

    def test_nothing_appears_until_the_commercial_is_available(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = self.make_www(Path(d))
            self.build_blog.refresh_commercial_hooks(tmp, self.data)
            self.assertFalse((tmp / "watch.html").exists())
            self.assertNotIn("watch.html", (tmp / "index.html").read_text(encoding="utf-8"))
            self.assertNotIn("<video", (tmp / "virtual-church-musician.html").read_text(encoding="utf-8"))

    def test_button_player_and_watch_page_appear_when_available(self):
        import copy, tempfile
        data = copy.deepcopy(self.data)
        for sec in data["sections"]:
            for v in sec["videos"]:
                if v["id"] == "ready-when-you-are":
                    v["available"] = True
        with tempfile.TemporaryDirectory() as d:
            tmp = self.make_www(Path(d))
            self.build_blog.refresh_commercial_hooks(tmp, data)
            home = (tmp / "index.html").read_text(encoding="utf-8")
            self.assertIn('href="watch.html" target="_blank" rel="noopener"', home)
            product = (tmp / "virtual-church-musician.html").read_text(encoding="utf-8")
            self.assertIn('preload="none"', product)
            self.assertNotIn("autoplay", product)
            self.assertIn("Dramatization. Scenes created with AI.", product)
            self.assertIn('kind="captions"', product)
            watch = (tmp / "watch.html").read_text(encoding="utf-8")
            self.assertIn('kind="captions"', watch)
            self.assertNotIn("autoplay", watch)
            # turning it back off removes the watch page again
            self.build_blog.refresh_commercial_hooks(tmp, self.data)
            self.assertFalse((tmp / "watch.html").exists())


if __name__ == "__main__":
    unittest.main()
