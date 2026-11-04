import importlib.util
import json
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parent.parent / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


digest = _load("findcache_digest_handler_module", "src/findcache_digest/handler.py")
DAY = datetime(2026, 11, 3, tzinfo=timezone.utc)


def record(n=1, **kw):
    base = {
        "id": f"20261103-10000{n}-abcd",
        "received": f"2026-11-03T10:00:0{n}Z",
        "app_version": "2026.11.04.006",
        "device": "Google Pixel 10 Pro",
        "description": "The map froze",
        "log_key": f"findcache/2026/11/03/20261103-10000{n}-abcd.txt",
    }
    return {**base, **kw}


class DigestTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(
            os.environ, {"LOG_BUCKET": "logs-bucket", "SES_SENDER": "no-reply@x.test", "SES_RECIPIENT": "me@x.test"}
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.s3 = mock.Mock()
        self.ses = mock.Mock()
        for name, client in (("_s3", self.s3), ("_ses", self.ses)):
            p = mock.patch.object(digest, name, return_value=client)
            p.start()
            self.addCleanup(p.stop)

    def stored(self, records):
        keys = [{"Key": r["log_key"][:-4] + ".json"} for r in records] + [{"Key": "findcache/2026/11/03/x.txt"}]
        self.s3.list_objects_v2.return_value = {"Contents": keys}
        bodies = {k["Key"]: json.dumps(r).encode() for k, r in zip(keys, records)}
        self.s3.get_object.side_effect = lambda Bucket, Key: {"Body": mock.Mock(read=lambda: bodies[Key])}

    def test_no_uploads_sends_nothing(self):
        self.s3.list_objects_v2.return_value = {}
        self.assertEqual(digest.handler({}, None), {"sent": False, "uploads": 0})
        self.ses.send_email.assert_not_called()

    def test_sends_one_email_with_reason_and_copy_command(self):
        self.stored([record(2), record(1, description="Crashed on start")])
        with mock.patch.object(digest, "datetime") as dt:
            dt.now.return_value = datetime(2026, 11, 4, 13, tzinfo=timezone.utc)
            result = digest.handler({}, None)
        self.assertEqual(result, {"sent": True, "uploads": 2})
        self.assertEqual(self.s3.list_objects_v2.call_args.kwargs["Prefix"], "findcache/2026/11/03/")
        kwargs = self.ses.send_email.call_args.kwargs
        self.assertEqual(kwargs["Destination"], {"ToAddresses": ["me@x.test"]})
        text = kwargs["Message"]["Body"]["Text"]["Data"]
        self.assertIn("Problem: Crashed on start", text)
        self.assertIn("aws s3 cp s3://logs-bucket/findcache/2026/11/03/20261103-100001-abcd.txt .", text)
        self.assertLess(text.index("Crashed on start"), text.index("The map froze"))
        self.assertEqual(kwargs["Message"]["Subject"]["Data"], "FindCache log uploads 2026-11-03: 2")

    def test_descriptions_are_cleaned_and_capped(self):
        subject, text = digest.build_digest("b", DAY, [record(description="hi\x00\x1b[31m" + "y" * 2000)])
        self.assertNotIn("\x00", text)
        self.assertNotIn("\x1b", text)
        self.assertLess(len(text), 2000)

    def test_entries_are_capped(self):
        subject, text = digest.build_digest("b", DAY, [record(1)] * 60)
        self.assertEqual(text.count("aws s3 cp"), digest.MAX_ENTRIES)
        self.assertIn("and 10 more", text)

    def test_missing_description_is_labelled(self):
        _, text = digest.build_digest("b", DAY, [record(description="")])
        self.assertIn("Problem: (none given)", text)


if __name__ == "__main__":
    unittest.main()
