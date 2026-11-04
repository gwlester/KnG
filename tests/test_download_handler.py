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

    # --- update check: GET ?update=1&app=&platform=&channel=&current=&v=1 ---------------------------

    def update(self, current="v1.0.1", channel=None, app="template-editor", platform="android", **extra):
        qs = {"update": "1", "app": app, "platform": platform, "current": current}
        if channel is not None:
            qs["channel"] = channel
        qs.update(extra)
        status, result = self.call(**qs)
        return status, json.loads(result["body"]), result

    def releases(self, *specs):
        # spec: (tag, channel_field) -- the matrix marks every prerelease "beta", alpha and beta alike.
        self.matrix = {"FormatVersion": 1, "releases": [release(tag, channel=ch) for tag, ch in specs]}

    def test_update_stable_channel_only_offers_stable_releases(self):
        self.releases(("v1.0.3-b.1", "beta"), ("v1.0.2-a.1", "beta"), ("v1.0.2", "stable"), ("v1.0.1", "stable"))
        status, body, result = self.update(current="v1.0.1")
        self.assertEqual(status, 200)
        self.assertTrue(body["update_available"])
        self.assertEqual(body["latest"]["version"], "v1.0.2")
        self.assertEqual(body["latest"]["kind"], "stable")
        self.assertEqual(body["FormatVersion"], 1)
        self.assertIn("max-age=60", result["headers"]["Cache-Control"])

    def test_update_default_channel_is_stable(self):
        self.releases(("v1.0.2-a.1", "beta"), ("v1.0.1", "stable"))
        self.assertFalse(self.update(current="v1.0.1")[1]["update_available"])

    def test_update_beta_channel_offers_stable_and_beta_but_not_alpha(self):
        self.releases(("v1.0.3-a.1", "beta"), ("v1.0.2-b.2", "beta"), ("v1.0.1", "stable"))
        body = self.update(current="v1.0.1", channel="beta")[1]
        self.assertEqual(body["latest"]["version"], "v1.0.2-b.2")
        self.assertEqual(body["latest"]["kind"], "beta")
        self.assertTrue(body["update_available"])

    def test_update_any_channel_offers_alphas_too(self):
        self.releases(("v1.0.3-a.1", "beta"), ("v1.0.2-b.2", "beta"), ("v1.0.1", "stable"))
        body = self.update(current="v1.0.1", channel="any")[1]
        self.assertEqual(body["latest"]["version"], "v1.0.3-a.1")
        self.assertEqual(body["latest"]["kind"], "alpha")

    def test_update_orders_alpha_below_beta_below_stable_within_a_version(self):
        self.releases(("v1.0.2-a.9", "beta"), ("v1.0.2-b.1", "beta"), ("v1.0.2", "stable"))
        self.assertTrue(self.update(current="v1.0.2-a.1", channel="any")[1]["update_available"])
        self.assertEqual(self.update(current="v1.0.2-a.1", channel="any")[1]["latest"]["version"], "v1.0.2")
        self.assertTrue(self.update(current="v1.0.2-a.9", channel="beta")[1]["update_available"])
        self.assertFalse(self.update(current="v1.0.2", channel="any")[1]["update_available"])
        self.assertTrue(self.update(current="v1.0.2-b.1", channel="beta")[1]["update_available"])

    def test_update_compares_numbers_not_text(self):
        self.releases(("v1.0.10", "stable"), ("v1.0.9", "stable"))
        self.assertEqual(self.update(current="v1.0.9")[1]["latest"]["version"], "v1.0.10")
        self.assertTrue(self.update(current="v1.0.9")[1]["update_available"])
        self.assertFalse(self.update(current="v1.0.10")[1]["update_available"])

    def test_update_up_to_date_still_reports_the_latest(self):
        self.releases(("v1.0.2", "stable"))
        body = self.update(current="v1.0.2")[1]
        self.assertFalse(body["update_available"])
        self.assertEqual(body["latest"]["version"], "v1.0.2")

    def test_update_accepts_a_current_version_without_the_v(self):
        self.releases(("v1.0.2", "stable"))
        self.assertFalse(self.update(current="1.0.2")[1]["update_available"])

    def test_update_only_considers_releases_that_contain_the_app_and_platform(self):
        self.matrix = {"FormatVersion": 1, "releases": [
            release("v1.0.3", channel="stable", files=[
                {"app": "server", "platform": "linux", "arch": "amd64", "format": "deb", "default": True,
                 "key": "releases/v1.0.3/s.deb", "filename": "s.deb"}]),
            release("v1.0.2", channel="stable"),
        ]}
        body = self.update(current="v1.0.1")[1]
        self.assertEqual(body["latest"]["version"], "v1.0.2")

    def test_update_skips_deprecated_releases(self):
        self.releases(("v1.0.3", "deprecated"), ("v1.0.2", "stable"))
        self.assertEqual(self.update(current="v1.0.1")[1]["latest"]["version"], "v1.0.2")

    def test_update_with_nothing_published_for_the_app(self):
        self.matrix = {"FormatVersion": 1, "releases": []}
        body = self.update(current="v1.0.1")[1]
        self.assertFalse(body["update_available"])
        self.assertIsNone(body["latest"])

    def test_update_flags_apps_that_need_an_access_code(self):
        self.releases(("v1.0.2", "stable"))
        self.assertFalse(self.update(current="v1.0.1")[1]["requires_access_code"])
        self.assertTrue(self.update(current="v1.0.1", app="server")[1]["requires_access_code"])

    def test_update_rejects_bad_requests(self):
        self.releases(("v1.0.2", "stable"))
        self.assertEqual(self.update(current="not-a-version")[0], 400)
        self.assertEqual(self.update(current="")[0], 400)
        self.assertEqual(self.update(channel="nightly")[0], 400)
        self.assertEqual(self.update(app="Bad App")[0], 400)
        self.assertEqual(self.update(platform="")[0], 400)

    def test_update_never_exposes_file_keys(self):
        self.releases(("v1.0.2", "stable"))
        raw = self.update(current="v1.0.1")[2]["body"]
        self.assertNotIn("releases/", raw)
        self.assertNotIn("filename", raw)

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


class ChannelSelectorTests(DownloadHandlerTests):
    __test__ = True
    """The download page's Stable / Beta / Alpha selector: status, download and documents take a channel."""

    def load(self):
        def rel(tag, channel):
            return release(tag, channel=channel, published="2026-11-0" + ("4" if "a." in tag or "b." in tag else "1"))
        self.matrix = {"FormatVersion": 1, "releases": [
            rel("template-editor-v1.0.2-a.2", "beta"),
            rel("template-editor-v1.0.2-b.1", "beta"),
            rel("v1.0.1", "stable"),
        ]}

    def status(self, **qs):
        status, result = self.call(status="1", **qs)
        return status, json.loads(result["body"])

    def test_default_is_stable_only(self):
        self.load()
        self.assertEqual(self.status()[1]["current"]["version"], "v1.0.1")
        self.assertEqual(self.status(channel="stable")[1]["current"]["version"], "v1.0.1")
        self.assertIsNone(self.status(channel="stable")[1]["previous"])

    def test_beta_adds_betas_but_not_alphas(self):
        self.load()
        body = self.status(channel="beta")[1]
        self.assertEqual(body["current"]["version"], "template-editor-v1.0.2-b.1")
        self.assertEqual(body["previous"]["version"], "v1.0.1")

    def test_any_adds_alphas_newest_first(self):
        self.load()
        body = self.status(channel="any")[1]
        self.assertEqual(body["current"]["version"], "template-editor-v1.0.2-b.1")
        self.assertEqual(body["previous"]["version"], "template-editor-v1.0.2-a.2")
        self.matrix["releases"].pop(1)
        self.assertEqual(self.status(channel="any")[1]["current"]["version"], "template-editor-v1.0.2-a.2")

    def test_a_channel_with_nothing_newer_falls_back_to_the_stable_rule(self):
        self.matrix = {"FormatVersion": 1, "releases": [release("v1.0.1", channel="stable")]}
        self.assertEqual(self.status(channel="any")[1]["current"]["version"], "v1.0.1")
        self.matrix = {"FormatVersion": 1, "releases": [release("v0.9.0-a.1", channel="beta")]}
        self.assertEqual(self.status(channel="any")[1]["current"]["version"], "v0.9.0-a.1")

    def test_download_and_documents_resolve_current_on_the_same_channel(self):
        self.load()
        def where(**qs):
            status, result = self.call(**qs)
            self.assertEqual(status, 302)
            return result["headers"]["Location"]

        file_qs = {"app": "template-editor", "platform": "windows", "format": "exe", "version": "current"}
        self.assertIn("template-editor-v1.0.2-b.1", where(channel="any", **file_qs))
        self.assertIn("releases/v1.0.1/", where(**file_qs))
        doc_qs = {"doc": "user-manual", "format": "pdf"}
        self.assertIn("template-editor-v1.0.2-b.1", where(version="current", channel="any", **doc_qs))
        self.assertIn("releases/v1.0.1/", where(version="previous", channel="beta", **doc_qs))

    def test_an_unknown_channel_is_rejected_everywhere(self):
        self.load()
        for qs in ({"status": "1"}, {"app": "template-editor", "platform": "windows"}, {"doc": "user-manual"}):
            with self.subTest(qs=qs):
                self.assertEqual(self.call(channel="nightly", **qs)[0], 400)


class PerAppReleaseTests(DownloadHandlerTests):
    __test__ = True
    """Apps are released independently: per-app tags, per-app current/previous."""

    def app_release(self, tag, channel, app):
        files = [{"app": app, "platform": "android", "arch": "any", "format": "apk", "default": True,
                  "key": f"releases/{tag}/x.apk", "filename": "x.apk"}]
        return release(tag, channel=channel, files=files)

    def test_current_is_decided_per_app(self):
        self.matrix = {"FormatVersion": 1, "releases": [
            self.app_release("service-runner-v1.0.3-a.1", "beta", "service-runner"),
            self.app_release("template-editor-v1.0.2", "stable", "template-editor"),
            self.app_release("service-runner-v1.0.1", "stable", "service-runner"),
        ]}
        # service-runner has a stable release, so its prerelease is not "current"; template-editor's own stable is.
        self.assertEqual(handler.resolve_release(self.matrix, "current", "service-runner")["version"], "service-runner-v1.0.1")
        self.assertEqual(handler.resolve_release(self.matrix, "current", "template-editor")["version"], "template-editor-v1.0.2")
        self.assertIsNone(handler.resolve_release(self.matrix, "current", "admin"))
        # An exact per-app tag is reachable by anyone who asks for it.
        self.assertEqual(handler.resolve_release(self.matrix, "service-runner-v1.0.3-a.1", "service-runner")["channel"], "beta")

    def test_status_reports_every_apps_own_current(self):
        self.matrix = {"FormatVersion": 1, "releases": [
            self.app_release("template-editor-v1.0.2", "stable", "template-editor"),
            self.app_release("service-runner-v1.0.1", "stable", "service-runner"),
        ]}
        body = json.loads(self.call(status="1")[1]["body"])
        self.assertEqual(set(body["current"]["available"]), {"template-editor:android", "service-runner:android"})

    def test_update_check_uses_the_apps_own_per_app_releases(self):
        self.matrix = {"FormatVersion": 1, "releases": [
            self.app_release("service-runner-v1.0.2-a.2", "beta", "service-runner"),
            self.app_release("template-editor-v1.0.9", "stable", "template-editor"),
        ]}
        status, result = self.call(update="1", app="service-runner", platform="android", channel="any", current="v1.0.2-a.1")
        body = json.loads(result["body"])
        self.assertTrue(body["update_available"])
        self.assertEqual(body["latest"]["version"], "service-runner-v1.0.2-a.2")
        # ...and the exact per-app tag it returns is accepted by the download endpoint.
        status, _ = self.call(app="service-runner", platform="android", format="apk", version="service-runner-v1.0.2-a.2", v="1")
        self.assertEqual(status, 302)
        self.assertEqual(handler.parse_tag("service-runner-v1.0.2-a.2")[0], (1, 0, 2, 0, 2))
        status, _ = self.call(update="1", app="template-editor", platform="android", channel="any", current="v1.0.2-a.1")
        self.assertEqual(status, 200)


if __name__ == "__main__":
    unittest.main()
