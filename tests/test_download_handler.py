import hashlib
import io
import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
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


def event(method="GET", body=None, source_ip="203.0.113.5", **qs):
    ev = {
        "requestContext": {"http": {"method": method, "sourceIp": source_ip}},
        "queryStringParameters": qs or None,
    }
    if body is not None:
        ev["body"] = json.dumps(body)
    return ev


class _ConditionalCheckFailed(Exception):
    """Stands in for botocore's ClientError shape without needing botocore
    installed -- handler._rate_limited() duck-types on `.response`."""

    def __init__(self):
        super().__init__("conditional check failed")
        self.response = {"Error": {"Code": "ConditionalCheckFailedException"}}


SERVER_FILE_BYTES = b"pretend-server-installer-bytes"
SERVER_FILE_SHA256 = hashlib.sha256(SERVER_FILE_BYTES).hexdigest()


class DownloadHandlerTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(
            os.environ,
            {
                "DOWNLOADS_BUCKET": "test-bucket",
                "RATE_LIMIT_TABLE": "test-ratelimit",
                "LICENSE_ISSUANCE_TABLE": "test-issuance",
            },
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.s3 = mock.Mock()
        self.s3.generate_presigned_url.side_effect = lambda op, Params, ExpiresIn: (
            f"https://signed.example/{Params['Key']}?exp={ExpiresIn}&d={Params['ResponseContentDisposition']}"
        )
        client = mock.patch.object(handler, "_s3", return_value=self.s3)
        client.start()
        self.addCleanup(client.stop)
        self.dynamo = mock.Mock()
        self.dynamo.update_item.return_value = {}
        dynamo_client = mock.patch.object(handler, "_dynamodb", return_value=self.dynamo)
        dynamo_client.start()
        self.addCleanup(dynamo_client.stop)
        self.matrix = {"FormatVersion": 1, "releases": [release("v1.0.1-b.7"), release("v1.0.1-b.6")]}
        loader = mock.patch.object(handler, "_load_matrix", side_effect=lambda: self.matrix)
        loader.start()
        self.addCleanup(loader.stop)

    def call(self, **qs):
        result = handler.handler(event(**qs), None)
        return result["statusCode"], result

    def post(self, **qs):
        result = handler.handler(event(method="POST", body={}, **qs), None)
        return result["statusCode"], result

    def post_order(self, reference=None, short_key=None, **qs):
        body = {}
        if reference is not None:
            body["reference"] = reference
        if short_key is not None:
            body["short_key"] = short_key
        result = handler.handler(event(method="POST", body=body, **qs), None)
        return result["statusCode"], result

    def issuance_item(self, kinds, short_key, source=None, valid_to=None):
        item = {
            "kinds": {"SS": kinds},
            "short_key_hash": {"S": hashlib.sha256(short_key.strip().upper().encode("utf-8")).hexdigest()},
        }
        if source is not None:
            item["source"] = {"S": source}
        if valid_to is not None:
            item["valid_to"] = {"S": valid_to}
        return item

    def add_server_file(self, release_index=0, sha256=None):
        rel = self.matrix["releases"][release_index]
        entry = {
            "app": "server", "platform": "linux", "arch": "amd64", "format": "deb",
            "key": f"releases/{rel['version']}/server.deb", "filename": "server.deb",
        }
        if sha256 is not None:
            entry["sha256"] = sha256
        rel["files"].append(entry)

    def mock_server_file_body(self):
        self.s3.get_object.return_value = {"Body": io.BytesIO(SERVER_FILE_BYTES)}

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

    def test_betas_drop_out_of_current_and_previous_once_a_stable_release_exists(self):
        self.matrix["releases"].insert(0, release("v1.1.0", channel="stable"))
        _, result = self.call(app="template-editor", platform="windows")
        self.assertIn("releases/v1.1.0/", result["headers"]["Location"])
        status, _ = self.call(app="template-editor", platform="windows", version="previous")
        self.assertEqual(status, 404)

    def test_an_old_beta_stays_reachable_by_its_exact_version_even_once_stable_exists(self):
        # Decided 2026-10-12: an approved beta tester must still be able to
        # reach a specific beta release by tag, even though it no longer
        # shows up as "current" or "previous" once some release has gone
        # stable -- only current/previous are stable-filtered.
        self.matrix["releases"].insert(0, release("v1.1.0", channel="stable"))
        status, _ = self.call(app="template-editor", platform="windows", version="v1.0.1-b.7")
        self.assertEqual(status, 302)

    def test_deprecated_release_is_excluded_from_current_and_previous(self):
        self.matrix["releases"][1]["channel"] = "deprecated"  # v1.0.1-b.6
        _, result = self.call(app="template-editor", platform="windows")
        self.assertIn("releases/v1.0.1-b.7/", result["headers"]["Location"])
        status, _ = self.call(app="template-editor", platform="windows", version="previous")
        self.assertEqual(status, 404)

    def test_deprecated_release_is_not_reachable_by_exact_version_either(self):
        # Decided 2026-10-14: unlike an ordinary old beta (see the test
        # above this one), a deprecated release doesn't work with the
        # licensing system, so it's refused on every path, not just
        # current/previous.
        self.matrix["releases"][1]["channel"] = "deprecated"  # v1.0.1-b.6
        status, _ = self.call(app="template-editor", platform="windows", version="v1.0.1-b.6")
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

    def test_paid_app_on_a_stable_release_requires_a_purchase_code_not_a_trial_one(self):
        self.matrix["releases"].insert(0, release("v1.1.0", channel="stable"))
        self.add_server_file(release_index=0)
        self.mock_server_file_body()
        # Available in status now -- "sold elsewhere, not here" no longer
        # hides it; purchasers must be able to redownload it.
        body = json.loads(self.call(status="1")[1]["body"])
        self.assertEqual(body["current"]["available"]["server:linux"], ["deb"])

        self.dynamo.get_item.return_value = {
            "Item": self.issuance_item(["server"], "AAAA-BBBB-CCCC-DDDD", source="trial")
        }
        status, _ = self.post_order(reference="trial-abc", short_key="AAAA-BBBB-CCCC-DDDD",
                                     app="server", platform="linux")
        self.assertEqual(status, 403)
        self.s3.get_object.assert_not_called()

        self.dynamo.get_item.return_value = {
            "Item": self.issuance_item(["server"], "AAAA-BBBB-CCCC-DDDD", source="purchase")
        }
        status, result = self.post_order(reference="order-123", short_key="AAAA-BBBB-CCCC-DDDD",
                                          app="server", platform="linux")
        self.assertEqual(status, 200)
        self.assertIn("releases/v1.1.0/server.deb", json.loads(result["body"])["url"])

    def test_paid_app_appears_in_status_once_a_file_exists_on_a_beta_release(self):
        self.add_server_file()
        body = json.loads(self.call(status="1")[1]["body"])
        self.assertEqual(body["current"]["available"]["server:linux"], ["deb"])

    def test_paid_app_download_without_an_access_code_is_rejected_before_touching_dynamo(self):
        self.add_server_file()
        status, _ = self.call(app="server", platform="linux")  # GET: no body at all
        self.assertEqual(status, 401)
        self.dynamo.get_item.assert_not_called()

    def test_paid_app_rate_limits_before_touching_dynamo(self):
        self.add_server_file()
        self.dynamo.update_item.side_effect = _ConditionalCheckFailed()
        status, _ = self.post_order(reference="order-123", short_key="AAAA-BBBB-CCCC-DDDD",
                                     app="server", platform="linux")
        self.assertEqual(status, 429)
        self.dynamo.get_item.assert_not_called()

    def test_expired_trial_order_code_is_rejected(self):
        self.add_server_file()
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        self.dynamo.get_item.return_value = {
            "Item": self.issuance_item(["server"], "AAAA-BBBB-CCCC-DDDD", source="trial", valid_to=past)
        }
        status, _ = self.post_order(reference="trial-abc", short_key="AAAA-BBBB-CCCC-DDDD",
                                     app="server", platform="linux")
        self.assertEqual(status, 403)
        self.s3.get_object.assert_not_called()

    def test_a_trial_order_code_still_within_its_window_works(self):
        self.add_server_file()
        self.mock_server_file_body()
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        self.dynamo.get_item.return_value = {
            "Item": self.issuance_item(["server"], "AAAA-BBBB-CCCC-DDDD", source="trial", valid_to=future)
        }
        status, _ = self.post_order(reference="trial-abc", short_key="AAAA-BBBB-CCCC-DDDD",
                                     app="server", platform="linux")
        self.assertEqual(status, 200)

    def test_a_purchase_order_code_has_no_expiry(self):
        self.add_server_file()
        self.mock_server_file_body()
        # Purchase rows never carry a valid_to attribute at all.
        self.dynamo.get_item.return_value = {
            "Item": self.issuance_item(["server"], "AAAA-BBBB-CCCC-DDDD", source="purchase")
        }
        status, _ = self.post_order(reference="order-123", short_key="AAAA-BBBB-CCCC-DDDD",
                                     app="server", platform="linux")
        self.assertEqual(status, 200)

    def test_paid_app_order_code_unknown_reference_is_rejected(self):
        self.add_server_file()
        self.dynamo.get_item.return_value = {}
        status, _ = self.post_order(reference="no-such-order", short_key="AAAA-AAAA-AAAA-AAAA",
                                     app="server", platform="linux")
        self.assertEqual(status, 403)
        self.s3.get_object.assert_not_called()

    def test_paid_app_order_code_wrong_short_key_is_rejected(self):
        self.add_server_file()
        self.dynamo.get_item.return_value = {"Item": self.issuance_item(["server"], "RIGHT-KEY1-AAAA-AAAA")}
        status, _ = self.post_order(reference="KNGCONSULTING1-1", short_key="WRONG-KEY1-AAAA-AAAA",
                                     app="server", platform="linux")
        self.assertEqual(status, 403)
        self.s3.get_object.assert_not_called()

    def test_paid_app_order_code_not_covering_this_app_is_rejected(self):
        self.add_server_file()
        self.dynamo.get_item.return_value = {"Item": self.issuance_item(["midi-player"], "AAAA-BBBB-CCCC-DDDD")}
        status, _ = self.post_order(reference="KNGCONSULTING1-1", short_key="AAAA-BBBB-CCCC-DDDD",
                                     app="server", platform="linux")
        self.assertEqual(status, 403)
        self.s3.get_object.assert_not_called()

    def test_paid_app_order_code_success_returns_json_not_a_redirect(self):
        self.add_server_file()
        self.mock_server_file_body()
        self.dynamo.get_item.return_value = {"Item": self.issuance_item(["server"], "AAAA-BBBB-CCCC-DDDD")}
        status, result = self.post_order(reference="KNGCONSULTING1-1", short_key="AAAA-BBBB-CCCC-DDDD",
                                          app="server", platform="linux")
        self.assertEqual(status, 200)
        body = json.loads(result["body"])
        self.assertTrue(body["ok"])
        self.assertIn("releases/v1.0.1-b.7/server.deb", body["url"])

    def test_paid_app_order_code_is_case_and_whitespace_insensitive(self):
        self.add_server_file()
        self.mock_server_file_body()
        self.dynamo.get_item.return_value = {"Item": self.issuance_item(["server"], "AAAA-BBBB-CCCC-DDDD")}
        status, _ = self.post_order(reference="KNGCONSULTING1-1", short_key="  aaaa-bbbb-cccc-dddd  ",
                                     app="server", platform="linux")
        self.assertEqual(status, 200)

    def test_paid_app_order_code_for_a_trial_reference_works_the_same_way(self):
        # Trial rows (source: "trial") share the same table/shape as
        # purchase rows -- this is what closes the "how do I download"
        # gap for the Test Drive flow.
        self.add_server_file()
        self.mock_server_file_body()
        self.dynamo.get_item.return_value = {"Item": self.issuance_item(["server"], "AAAA-BBBB-CCCC-DDDD")}
        status, _ = self.post_order(reference="trial-f14c889e89d42925", short_key="AAAA-BBBB-CCCC-DDDD",
                                     app="server", platform="linux")
        self.assertEqual(status, 200)

    def test_paid_app_order_code_missing_short_key_is_rejected_before_touching_dynamo(self):
        self.add_server_file()
        status, _ = self.post_order(reference="KNGCONSULTING1-1", app="server", platform="linux")
        self.assertEqual(status, 401)
        self.dynamo.get_item.assert_not_called()

    def test_free_apps_are_unaffected_by_the_password_flow(self):
        self.assertEqual(self.call(app="template-editor", platform="windows")[0], 302)
        self.dynamo.update_item.assert_not_called()

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

    def test_post_is_allowed_but_other_verbs_are_not(self):
        # POST exists only to carry a password (see the module docstring); a
        # bare POST with nothing requested behaves like a bare GET.
        self.assertEqual(self.call(app="template-editor", platform="windows")[0], 302)
        status, _ = self.post(app="template-editor", platform="windows")
        self.assertEqual(status, 302)  # free apps ignore the body entirely
        result = handler.handler(event(method="POST"), None)
        self.assertEqual(result["statusCode"], 400)
        result = handler.handler(event(method="PUT"), None)
        self.assertEqual(result["statusCode"], 405)
        result = handler.handler(event(method="DELETE"), None)
        self.assertEqual(result["statusCode"], 405)


if __name__ == "__main__":
    unittest.main()
