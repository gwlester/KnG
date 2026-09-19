import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

import importlib.util


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parent.parent / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


handler = _load("download_handler_module", "src/download_handler/handler.py")


def release(version, channel="beta", published="2026-09-11", files=None, documents=None):
    return {
        "version": version,
        "channel": channel,
        "published": published,
        "files": files
        or [
            {"app": "template-editor", "platform": "windows", "arch": "x64", "format": "exe", "default": True,
             "key": f"releases/{version}/TemplateEditor.exe", "filename": "TemplateEditor.exe"},
            {"app": "template-editor", "platform": "windows", "arch": "x64", "format": "msi",
             "key": f"releases/{version}/TemplateEditor.msi", "filename": "TemplateEditor.msi"},
            {"app": "template-editor", "platform": "android", "arch": "any", "format": "apk", "default": True,
             "key": f"releases/{version}/TemplateEditor.apk", "filename": "TemplateEditor.apk"},
        ],
        "documents": documents
        or [
            {"kind": "user-manual", "format": "html", "key": f"releases/{version}/UserManual.html", "filename": "UserManual.html"},
            {"kind": "user-manual", "format": "pdf", "key": f"releases/{version}/UserManual.pdf", "filename": "UserManual.pdf"},
        ],
    }


def event(**qs):
    return {"requestContext": {"http": {"method": "GET"}}, "queryStringParameters": qs or None}


class DownloadHandlerTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ, {"DOWNLOADS_BUCKET": "test-bucket"})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.s3 = mock.Mock()
        self.s3.generate_presigned_url.side_effect = lambda op, Params, ExpiresIn: (
            f"https://signed.example/{Params['Key']}?exp={ExpiresIn}&d={Params['ResponseContentDisposition']}"
        )
        client = mock.patch.object(handler, "_s3", return_value=self.s3)
        client.start()
        self.addCleanup(client.stop)
        self.matrix = {"FormatVersion": 1, "releases": [release("v1.0.1-b.7"), release("v1.0.1-b.6")]}
        loader = mock.patch.object(handler, "_load_matrix", side_effect=lambda: self.matrix)
        loader.start()
        self.addCleanup(loader.stop)

    def call(self, **qs):
        result = handler.handler(event(**qs), None)
        return result["statusCode"], result

    def test_download_redirects_to_a_five_minute_signed_url(self):
        status, result = self.call(app="template-editor", platform="windows", v="1")
        self.assertEqual(status, 302)
        self.assertIn("releases/v1.0.1-b.7/TemplateEditor.exe", result["headers"]["Location"])
        self.assertIn("exp=300", result["headers"]["Location"])
        self.assertEqual(result["headers"]["Cache-Control"], "no-store")

    def test_previous_version_and_explicit_format(self):
        _, result = self.call(app="template-editor", platform="windows", version="previous", format="msi")
        self.assertIn("releases/v1.0.1-b.6/TemplateEditor.msi", result["headers"]["Location"])

    def test_exact_version_is_matched_only_if_visible(self):
        status, _ = self.call(app="template-editor", platform="windows", version="v1.0.1-b.6")
        self.assertEqual(status, 302)
        status, _ = self.call(app="template-editor", platform="windows", version="v9.9.9")
        self.assertEqual(status, 404)

    def test_betas_are_hidden_once_a_stable_release_exists(self):
        self.matrix["releases"].insert(0, release("v1.1.0", channel="stable"))
        _, result = self.call(app="template-editor", platform="windows")
        self.assertIn("releases/v1.1.0/", result["headers"]["Location"])
        status, _ = self.call(app="template-editor", platform="windows", version="previous")
        self.assertEqual(status, 404)
        status, _ = self.call(app="template-editor", platform="windows", version="v1.0.1-b.7")
        self.assertEqual(status, 404)

    def test_missing_downloads_and_bad_input(self):
        self.assertEqual(self.call(app="server", platform="windows")[0], 404)
        self.assertEqual(self.call(app="../etc", platform="windows")[0], 400)
        self.assertEqual(self.call(app="template-editor", platform="windows", version="bogus")[0], 400)
        self.assertEqual(self.call(app="template-editor", platform="windows", format="exe;rm")[0], 400)
        self.assertEqual(self.call(app="template-editor", platform="windows", v="2")[0], 400)
        self.assertEqual(self.call()[0], 400)

    def test_never_signs_a_key_outside_releases(self):
        self.matrix["releases"][0]["files"][0]["key"] = "matrix.json"
        status, _ = self.call(app="template-editor", platform="windows", format="exe")
        self.assertEqual(status, 404)
        self.s3.generate_presigned_url.assert_not_called()

    def test_store_link_takes_precedence_and_must_be_https(self):
        self.matrix["links"] = {"template-editor:android": {"type": "store", "url": "https://play.google.com/store/apps/details?id=x"}}
        _, result = self.call(app="template-editor", platform="android")
        self.assertTrue(result["headers"]["Location"].startswith("https://play.google.com/"))
        self.matrix["links"]["template-editor:android"]["url"] = "http://evil.example/"
        _, result = self.call(app="template-editor", platform="android")
        self.assertIn("releases/v1.0.1-b.7/TemplateEditor.apk", result["headers"]["Location"])

    def test_paid_apps_are_never_served_even_if_present_in_the_matrix(self):
        self.matrix["releases"][0]["files"].append(
            {"app": "server", "platform": "linux", "arch": "amd64", "format": "deb",
             "key": "releases/v1.0.1-b.7/server.deb", "filename": "server.deb"}
        )
        self.assertEqual(self.call(app="server", platform="linux")[0], 404)
        body = json.loads(self.call(status="1")[1]["body"])
        self.assertNotIn("server:linux", body["current"]["available"])

    def test_documents(self):
        _, html = self.call(doc="user-manual", format="html")
        self.assertIn("inline", html["headers"]["Location"])
        _, pdf = self.call(doc="user-manual", format="pdf")
        self.assertIn("attachment", pdf["headers"]["Location"])
        self.assertEqual(self.call(doc="system-admin-guide", format="html")[0], 404)

    def test_status_lists_availability_without_file_locations(self):
        status, result = self.call(status="1")
        self.assertEqual(status, 200)
        body = json.loads(result["body"])
        self.assertEqual(body["current"]["version"], "v1.0.1-b.7")
        self.assertEqual(body["previous"]["version"], "v1.0.1-b.6")
        self.assertEqual(body["current"]["available"]["template-editor:windows"], ["exe", "msi"])
        self.assertEqual(body["current"]["documents"]["user-manual"], ["html", "pdf"])
        self.assertIn("signed", body["current"])
        self.assertNotIn("releases/", result["body"])
        self.assertNotIn("key", result["body"])
        self.assertIn("max-age=60", result["headers"]["Cache-Control"])

    def test_status_with_an_empty_matrix(self):
        self.matrix = {"FormatVersion": 1, "releases": []}
        body = json.loads(self.call(status="1")[1]["body"])
        self.assertIsNone(body["current"])
        self.assertEqual(self.call(app="template-editor", platform="windows")[0], 404)

    def test_only_get_and_head_are_allowed(self):
        result = handler.handler({"requestContext": {"http": {"method": "POST"}}}, None)
        self.assertEqual(result["statusCode"], 405)


if __name__ == "__main__":
    unittest.main()
