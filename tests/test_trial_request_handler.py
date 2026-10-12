import importlib.util
import json
import os
import unittest
from pathlib import Path
from unittest import mock


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parent.parent / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


handler = _load("trial_request_handler_module", "src/trial_request/handler.py")


def event(body: dict):
    return {"body": json.dumps(body)}


class TrialRequestHandlerTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(
            os.environ,
            {"LICENSE_ISSUANCE_TABLE": "test-issuance", "TRIAL_BY_EMAIL_TABLE": "test-trial-by-email"},
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.dynamo = mock.Mock()
        self.dynamo.get_item.return_value = {}
        dynamo_patch = mock.patch.object(handler, "_dynamodb", return_value=self.dynamo)
        dynamo_patch.start()
        self.addCleanup(dynamo_patch.stop)

    def test_issues_a_trial_reference_and_short_key(self):
        result = handler.handler(event({"email": "pastor@example.org", "kind": "server"}), None)

        self.assertEqual(result["statusCode"], 200)
        body = json.loads(result["body"])
        self.assertTrue(body["reference"].startswith("trial-"))
        self.assertRegex(body["short_key"], r"^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$")
        self.assertIn("valid_to", body)
        self.assertEqual(self.dynamo.put_item.call_count, 2)

    def test_rejects_an_invalid_email(self):
        result = handler.handler(event({"email": "not-an-email", "kind": "server"}), None)
        self.assertEqual(result["statusCode"], 400)
        self.dynamo.put_item.assert_not_called()

    def test_rejects_an_unknown_kind(self):
        result = handler.handler(event({"email": "pastor@example.org", "kind": "template-editor"}), None)
        self.assertEqual(result["statusCode"], 400)

    def test_rejects_a_second_trial_for_the_same_email_and_kind(self):
        self.dynamo.get_item.return_value = {"Item": {"email_kind": {"S": "pastor@example.org#server"}}}

        result = handler.handler(event({"email": "pastor@example.org", "kind": "server"}), None)

        self.assertEqual(result["statusCode"], 409)
        self.dynamo.put_item.assert_not_called()

    def test_same_email_may_still_trial_the_other_kind(self):
        # The email-by-kind lookup key includes `kind`, so a lookup for
        # "server" finds nothing even though a midi_player trial exists.
        self.dynamo.get_item.side_effect = lambda TableName, Key: (
            {"Item": {"email_kind": Key["email_kind"]}} if "midi_player" in Key["email_kind"]["S"] else {}
        )

        result = handler.handler(event({"email": "pastor@example.org", "kind": "server"}), None)

        self.assertEqual(result["statusCode"], 200)

    def test_email_is_case_and_whitespace_normalized_for_the_dedup_check(self):
        handler.handler(event({"email": "  Pastor@Example.ORG  ", "kind": "server"}), None)

        lookup_key = self.dynamo.get_item.call_args.kwargs["Key"]["email_kind"]["S"]
        self.assertEqual(lookup_key, "pastor@example.org#server")


if __name__ == "__main__":
    unittest.main()
