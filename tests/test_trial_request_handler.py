import importlib.util
import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parent.parent / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


handler = _load("trial_request_handler_module", "src/trial_request/handler.py")

ISSUANCE_TABLE = "test-issuance"
TRIAL_BY_EMAIL_TABLE = "test-trial-by-email"
BETA_TESTERS_TABLE = "test-beta-testers"


def event(body: dict):
    return {"body": json.dumps(body)}


class TrialRequestHandlerTests(unittest.TestCase):
    """A small fake DynamoDB keyed by table name, since the handler now
    reads/writes three different tables (approval, dedup, issuance) in
    one request -- a single blanket get_item return value isn't enough
    to exercise the renew-vs-reuse branching realistically."""

    def setUp(self):
        patcher = mock.patch.dict(
            os.environ,
            {
                "LICENSE_ISSUANCE_TABLE": ISSUANCE_TABLE,
                "TRIAL_BY_EMAIL_TABLE": TRIAL_BY_EMAIL_TABLE,
                "BETA_TESTERS_TABLE": BETA_TESTERS_TABLE,
            },
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        self.approved_emails = set()
        self.trial_by_email_items: dict[str, dict] = {}
        self.issuance_items: dict[str, dict] = {}

        self.dynamo = mock.Mock()
        self.dynamo.get_item.side_effect = self._get_item
        self.dynamo.put_item.side_effect = self._put_item
        self.dynamo.update_item.side_effect = self._update_item
        dynamo_patch = mock.patch.object(handler, "_dynamodb", return_value=self.dynamo)
        dynamo_patch.start()
        self.addCleanup(dynamo_patch.stop)

    def approve(self, email: str) -> None:
        self.approved_emails.add(email)

    def seed_issuance(self, reference: str, **fields) -> None:
        item = {"reference": {"S": reference}}
        item.update(fields)
        self.issuance_items[reference] = item

    def seed_trial_by_email(self, email: str, kind: str, reference: str) -> None:
        self.trial_by_email_items[f"{email}#{kind}"] = {
            "email_kind": {"S": f"{email}#{kind}"}, "reference": {"S": reference},
        }

    def _get_item(self, TableName, Key):
        if TableName == BETA_TESTERS_TABLE:
            email = Key["email"]["S"]
            return {"Item": {"email": {"S": email}}} if email in self.approved_emails else {}
        if TableName == TRIAL_BY_EMAIL_TABLE:
            item = self.trial_by_email_items.get(Key["email_kind"]["S"])
            return {"Item": item} if item else {}
        if TableName == ISSUANCE_TABLE:
            item = self.issuance_items.get(Key["reference"]["S"])
            return {"Item": item} if item else {}
        raise AssertionError(f"unexpected table {TableName}")

    def _put_item(self, TableName, Item):
        if TableName == TRIAL_BY_EMAIL_TABLE:
            self.trial_by_email_items[Item["email_kind"]["S"]] = Item
        elif TableName == ISSUANCE_TABLE:
            self.issuance_items[Item["reference"]["S"]] = Item
        else:
            raise AssertionError(f"unexpected put to {TableName}")
        return {}

    def _update_item(self, TableName, Key, UpdateExpression, ExpressionAttributeValues):
        assert TableName == ISSUANCE_TABLE
        item = self.issuance_items[Key["reference"]["S"]]
        item["short_key"] = ExpressionAttributeValues[":sk"]
        item["short_key_hash"] = ExpressionAttributeValues[":skh"]
        item["valid_to"] = ExpressionAttributeValues[":vt"]
        item["created_at"] = ExpressionAttributeValues[":ca"]
        item.pop("bound_uuid_server", None)
        item.pop("bound_uuid_midi_player", None)
        return {}

    def test_issues_a_reference_and_short_key_for_an_approved_tester(self):
        self.approve("pastor@example.org")

        result = handler.handler(event({"email": "pastor@example.org", "kind": "server"}), None)

        self.assertEqual(result["statusCode"], 200)
        body = json.loads(result["body"])
        self.assertTrue(body["reference"].startswith("trial-"))
        self.assertRegex(body["short_key"], r"^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$")
        self.assertIn("valid_to", body)
        self.assertEqual(self.dynamo.put_item.call_count, 2)

    def test_rejects_an_email_not_on_the_beta_tester_list(self):
        result = handler.handler(event({"email": "stranger@example.org", "kind": "server"}), None)

        self.assertEqual(result["statusCode"], 403)
        body = json.loads(result["body"])
        self.assertIn("contact form", body["error"])
        self.dynamo.put_item.assert_not_called()

    def test_rejects_an_invalid_email(self):
        result = handler.handler(event({"email": "not-an-email", "kind": "server"}), None)
        self.assertEqual(result["statusCode"], 400)
        self.dynamo.put_item.assert_not_called()
        self.dynamo.get_item.assert_not_called()

    def test_rejects_an_unknown_kind(self):
        result = handler.handler(event({"email": "pastor@example.org", "kind": "template-editor"}), None)
        self.assertEqual(result["statusCode"], 400)

    def test_a_second_request_within_the_window_returns_the_same_credential(self):
        self.approve("pastor@example.org")
        self.seed_trial_by_email("pastor@example.org", "server", "trial-abc123")
        future = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
        self.seed_issuance(
            "trial-abc123", short_key={"S": "AAAA-BBBB-CCCC-DDDD"}, short_key_hash={"S": "irrelevant"},
            valid_to={"S": future},
        )

        result = handler.handler(event({"email": "pastor@example.org", "kind": "server"}), None)

        self.assertEqual(result["statusCode"], 200)
        body = json.loads(result["body"])
        self.assertEqual(body["reference"], "trial-abc123")
        self.assertEqual(body["short_key"], "AAAA-BBBB-CCCC-DDDD")
        self.assertEqual(body["valid_to"], future)
        self.dynamo.update_item.assert_not_called()
        self.dynamo.put_item.assert_not_called()

    def test_an_expired_request_is_renewed_in_place_with_a_fresh_key(self):
        self.approve("pastor@example.org")
        self.seed_trial_by_email("pastor@example.org", "server", "trial-abc123")
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        self.seed_issuance(
            "trial-abc123", short_key={"S": "OLD1-OLD1-OLD1-OLD1"}, short_key_hash={"S": "old-hash"},
            valid_to={"S": past}, bound_uuid_server={"S": "some-old-device-uuid"},
        )

        result = handler.handler(event({"email": "pastor@example.org", "kind": "server"}), None)

        self.assertEqual(result["statusCode"], 200)
        body = json.loads(result["body"])
        self.assertEqual(body["reference"], "trial-abc123")
        self.assertNotEqual(body["short_key"], "OLD1-OLD1-OLD1-OLD1")
        self.assertGreater(body["valid_to"], past)
        self.dynamo.update_item.assert_called_once()
        self.assertNotIn("bound_uuid_server", self.issuance_items["trial-abc123"])

    def test_same_email_may_still_request_the_other_kind(self):
        self.approve("pastor@example.org")
        self.seed_trial_by_email("pastor@example.org", "midi_player", "trial-existing")
        future = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
        self.seed_issuance(
            "trial-existing", short_key={"S": "AAAA-BBBB-CCCC-DDDD"}, short_key_hash={"S": "irrelevant"},
            valid_to={"S": future},
        )

        result = handler.handler(event({"email": "pastor@example.org", "kind": "server"}), None)

        self.assertEqual(result["statusCode"], 200)
        body = json.loads(result["body"])
        self.assertNotEqual(body["reference"], "trial-existing")

    def test_email_is_case_and_whitespace_normalized(self):
        self.approve("pastor@example.org")

        result = handler.handler(event({"email": "  Pastor@Example.ORG  ", "kind": "server"}), None)

        self.assertEqual(result["statusCode"], 200)
        self.assertIn("pastor@example.org#server", self.trial_by_email_items)


if __name__ == "__main__":
    unittest.main()
