import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "contact_handler"))

import handler  # noqa: E402

ORIGIN = "https://www.kng-consulting.com"


def event(body, method="POST", origin=ORIGIN):
    return {
        "requestContext": {"http": {"method": method}},
        "headers": {"origin": origin} if origin else {},
        "body": body if isinstance(body, str) else json.dumps(body),
    }


def valid(**overrides):
    payload = {
        "FormatVersion": 1,
        "name": "Pat Example",
        "email": "pat@example.com",
        "message": "Hello there",
        "website": "",
    }
    payload.update(overrides)
    return payload


class ContactHandlerTests(unittest.TestCase):
    def setUp(self):
        env = {
            "SES_SENDER": "no-reply@kng-consulting.com",
            "SES_RECIPIENT": "inquiries@kng-consulting.com",
            "ALLOWED_ORIGINS": ORIGIN,
        }
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.ses = mock.Mock()
        client = mock.patch.object(handler, "_client", return_value=self.ses)
        client.start()
        self.addCleanup(client.stop)

    def call(self, ev):
        result = handler.handler(ev, None)
        return result["statusCode"], json.loads(result["body"])

    def test_valid_submission_sends_email(self):
        status, body = self.call(event(valid()))
        self.assertEqual((status, body["ok"]), (200, True))
        kwargs = self.ses.send_email.call_args.kwargs
        self.assertEqual(kwargs["Destination"]["ToAddresses"], ["inquiries@kng-consulting.com"])
        self.assertEqual(kwargs["ReplyToAddresses"], ["pat@example.com"])
        self.assertEqual(kwargs["Source"], "no-reply@kng-consulting.com")

    def test_honeypot_is_silently_dropped(self):
        status, body = self.call(event(valid(website="http://spam")))
        self.assertEqual((status, body["ok"]), (200, True))
        self.ses.send_email.assert_not_called()

    def test_rejects_bad_input(self):
        cases = [
            valid(name=""),
            valid(email="not-an-email"),
            valid(email="a@b.com\nBcc: x@y.com"),
            valid(message=""),
            valid(message="x" * 5001),
            valid(FormatVersion=2),
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                status, body = self.call(event(payload))
                self.assertEqual((status, body["ok"]), (400, False))
        self.ses.send_email.assert_not_called()

    def test_rejects_non_json_body(self):
        status, _ = self.call(event("not json"))
        self.assertEqual(status, 400)

    def test_rejects_non_post(self):
        status, _ = self.call(event(valid(), method="GET"))
        self.assertEqual(status, 405)

    def test_rejects_disallowed_origin(self):
        status, _ = self.call(event(valid(), origin="https://evil.example"))
        self.assertEqual(status, 403)
        self.ses.send_email.assert_not_called()

    def test_newlines_in_name_cannot_break_subject(self):
        self.call(event(valid(name="Pat\r\nBcc: x@y.com")))
        subject = self.ses.send_email.call_args.kwargs["Message"]["Subject"]["Data"]
        self.assertNotIn("\n", subject)
        self.assertNotIn("\r", subject)

    def test_ses_failure_returns_502(self):
        self.ses.send_email.side_effect = RuntimeError("boom")
        status, body = self.call(event(valid()))
        self.assertEqual((status, body["ok"]), (502, False))


if __name__ == "__main__":
    unittest.main()
