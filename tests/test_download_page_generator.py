import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


class DownloadPageGeneratorTests(unittest.TestCase):
    """render_picker()/refresh_download_page() fully regenerate the
    PICKER_START/PICKER_END block in www/download.html from
    content/downloads/options.json on every build_blog.py run (including
    the "Build blog" step of .github/workflows/deploy-to-aws.yml) --
    confirmed live 2026-10-12 when that step silently wiped the FastSpring
    Popup checkout script tag and #purchase-result div a hand-edit had
    added directly to www/download.html, since neither existed in
    options.json. These tests guard the fix: the generator itself must
    emit them, not a one-off hand-edit of the rendered page.
    """

    def setUp(self):
        import build_blog

        self.b = build_blog
        self.options = {
            "endpoint": "https://downloads.example/",
            "order_fulfillment_endpoint": "https://fulfillment.example/",
            "fastspring_storefront": "example.test.onfastspring.com/popup-test",
            "channel_label": "Beta",
            "apps": [{"id": "server", "name": "VCM Server", "platforms": []}],
            "extras": [],
        }

    def test_render_picker_includes_the_order_fulfillment_endpoint(self):
        html = self.b.render_picker(self.options)
        self.assertIn('data-order-fulfillment-endpoint="https://fulfillment.example/"', html)

    def test_render_picker_includes_the_fastspring_script_tag(self):
        html = self.b.render_picker(self.options)
        self.assertIn('id="fsc-api"', html)
        self.assertIn('data-storefront="example.test.onfastspring.com/popup-test"', html)
        self.assertIn('data-popup-closed="onFSPopupClosed"', html)

    def test_render_picker_includes_the_purchase_result_container(self):
        html = self.b.render_picker(self.options)
        self.assertIn('id="purchase-result"', html)

    def test_refresh_download_page_preserves_fastspring_integration(self):
        """The actual end-to-end regression: running the full generator
        against the real options.json must not drop what render_picker
        adds -- this is what CI's "Build blog" step runs before upload.
        """
        self.b.refresh_download_page()
        html = self.b.DOWNLOAD_PAGE.read_text(encoding="utf-8")
        self.assertIn('id="fsc-api"', html)
        self.assertIn('id="purchase-result"', html)
        self.assertIn("data-order-fulfillment-endpoint", html)


if __name__ == "__main__":
    unittest.main()
