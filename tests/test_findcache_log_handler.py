import base64
import importlib.util
import os
import unittest
from pathlib import Path
from unittest import mock


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parent.parent / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


handler = _load("findcache_log_handler_module", "src/findcache_log/handler.py")
REAL_S3 = handler._s3


def event(body="2026-11-03 [app] hello\n", method="POST", headers=None, encoded=False):
    return {
        "requestContext": {"http": {"method": method}},
        "headers": {"X-API-Version": "1"} if headers is None else headers,
        "body": base64.b64encode(body.encode()).decode() if encoded else body,
        "isBase64Encoded": encoded,
    }


class FindCacheLogHandlerTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ, {"LOG_BUCKET": "logs-bucket"})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.s3 = mock.Mock()
        s3_patch = mock.patch.object(handler, "_s3", return_value=self.s3)
        s3_patch.start()
        self.addCleanup(s3_patch.stop)

    def test_stores_the_log_and_returns_a_reference(self):
        result = handler.handler(event(), None)
        self.assertEqual(result["statusCode"], 200)
        body = __import__("json").loads(result["body"])
        self.assertEqual(body["FormatVersion"], 1)
        kwargs = self.s3.put_object.call_args.kwargs
        self.assertEqual(kwargs["Bucket"], "logs-bucket")
        self.assertRegex(kwargs["Key"], r"^findcache/\d{4}/\d{2}/\d{2}/" + body["id"] + r"\.txt$")
        self.assertEqual(kwargs["Body"], b"2026-11-03 [app] hello\n")
        self.assertNotIn("Metadata", kwargs)

    def test_accepts_a_base64_body(self):
        result = handler.handler(event("café log", encoded=True), None)
        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(self.s3.put_object.call_args.kwargs["Body"], "café log".encode("utf-8"))

    def test_records_a_sanitised_app_version(self):
        headers = {"x-api-version": "1", "x-app-version": "2026.11.04.001 <script>"}
        handler.handler(event(headers=headers), None)
        self.assertEqual(self.s3.put_object.call_args.kwargs["Metadata"], {"app-version": "2026.11.04.001script"})

    def test_rejects_other_methods(self):
        self.assertEqual(handler.handler(event(method="GET"), None)["statusCode"], 405)

    def test_requires_the_api_version_header(self):
        self.assertEqual(handler.handler(event(headers={}), None)["statusCode"], 400)
        self.assertEqual(handler.handler(event(headers={"X-API-Version": "2"}), None)["statusCode"], 400)

    def test_rejects_an_empty_log(self):
        self.assertEqual(handler.handler(event(body="  \n"), None)["statusCode"], 400)
        self.assertEqual(handler.handler({**event(), "body": None}, None)["statusCode"], 400)

    def test_rejects_an_oversized_log(self):
        result = handler.handler(event(body="x" * (handler.MAX_LOG_BYTES + 1)), None)
        self.assertEqual(result["statusCode"], 413)
        self.s3.put_object.assert_not_called()

    def test_s3_client_is_created_lazily_and_reused(self):
        handler._s3_client = None
        fake_boto3 = mock.Mock()
        with mock.patch.dict("sys.modules", {"boto3": fake_boto3}):
            first = REAL_S3()
            second = REAL_S3()
        self.assertIs(first, second)
        fake_boto3.client.assert_called_once_with("s3")
        handler._s3_client = None


if __name__ == "__main__":
    unittest.main()
