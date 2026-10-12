import base64
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parent.parent / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


handler = _load("license_signing_handler_module", "src/license_signing/handler.py")

UUID = "a1b2c3d4-0000-0000-0000-000000000000"


def event(body: dict):
    return {"body": json.dumps(body)}


class LicenseSigningHandlerTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.public_key = private_key.public_key()
        key_path = Path(self._tmpdir.name) / "key.pem"
        key_path.write_bytes(
            private_key.private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
            )
        )
        patcher = mock.patch.dict(
            os.environ,
            {"LICENSE_SIGNING_PRIVATE_KEY_PATH": str(key_path), "LICENSE_ISSUANCE_TABLE": "test-issuance"},
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        handler._private_key = None  # force a fresh load against this test's own key
        self.addCleanup(lambda: setattr(handler, "_private_key", None))
        self.dynamo = mock.Mock()
        dynamo_patch = mock.patch.object(handler, "_dynamodb", return_value=self.dynamo)
        dynamo_patch.start()
        self.addCleanup(dynamo_patch.stop)

    def _verify_file(self, file_bytes: bytes, short_key: str) -> dict:
        plaintext = __import__("cryptography.fernet", fromlist=["Fernet"]).Fernet(
            handler._derive_fernet_key(short_key)
        ).decrypt(file_bytes)
        envelope = json.loads(plaintext)
        self.public_key.verify(
            base64.b64decode(envelope["signature"]),
            handler._canonical_fields_bytes(envelope["fields"]),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return envelope["fields"]

    def _issuance_item(self, reference, short_key, kind="server", valid_to=None, bound_uuid=None, category="server"):
        item = {
            "reference": {"S": reference},
            "source": {"S": "trial"},
            "kind": {"S": kind},
            "short_key_hash": {"S": handler.hash_short_key(short_key)},
        }
        if valid_to is not None:
            item["valid_to"] = {"S": valid_to}
        if bound_uuid is not None:
            item[f"bound_uuid_{category}"] = {"S": bound_uuid}
        return item

    def test_activate_mints_a_verifiable_license_bound_to_the_given_uuid(self):
        short_key = "ABCD-1234-EFGH-5678"
        self.dynamo.get_item.return_value = {"Item": self._issuance_item("ref-1", short_key)}

        result = handler.activate(event({"reference": "ref-1", "short_key": short_key, "uuid": UUID, "category": "server"}), None)

        self.assertEqual(result["statusCode"], 200)
        body = json.loads(result["body"])
        file_bytes = base64.b64decode(body["license_file_base64"])
        fields = self._verify_file(file_bytes, short_key)
        self.assertEqual(fields["bound_uuid"], UUID)
        self.assertEqual(fields["kind"], "server")
        self.dynamo.update_item.assert_called_once()

    def test_activate_rejects_the_wrong_short_key(self):
        self.dynamo.get_item.return_value = {"Item": self._issuance_item("ref-1", "REAL-KEY")}

        result = handler.activate(
            event({"reference": "ref-1", "short_key": "WRONG-KEY", "uuid": UUID, "category": "server"}), None
        )

        self.assertEqual(result["statusCode"], 403)
        self.dynamo.update_item.assert_not_called()

    def test_activate_rejects_an_unknown_reference(self):
        self.dynamo.get_item.return_value = {}

        result = handler.activate(
            event({"reference": "missing", "short_key": "KEY", "uuid": UUID, "category": "server"}), None
        )

        self.assertEqual(result["statusCode"], 404)

    def test_activate_is_idempotent_for_the_same_uuid(self):
        short_key = "ABCD-1234-EFGH-5678"
        self.dynamo.get_item.return_value = {
            "Item": self._issuance_item("ref-1", short_key, bound_uuid=UUID)
        }

        result = handler.activate(
            event({"reference": "ref-1", "short_key": short_key, "uuid": UUID, "category": "server"}), None
        )

        self.assertEqual(result["statusCode"], 200)
        self.dynamo.update_item.assert_not_called()  # already bound to this uuid -- nothing new to record

    def test_activate_rejects_a_different_uuid_once_already_bound(self):
        short_key = "ABCD-1234-EFGH-5678"
        self.dynamo.get_item.return_value = {
            "Item": self._issuance_item("ref-1", short_key, bound_uuid="some-other-uuid")
        }

        result = handler.activate(
            event({"reference": "ref-1", "short_key": short_key, "uuid": UUID, "category": "server"}), None
        )

        self.assertEqual(result["statusCode"], 409)

    def test_activate_requires_all_fields(self):
        result = handler.activate(event({"reference": "ref-1"}), None)
        self.assertEqual(result["statusCode"], 400)

    def test_activate_rejects_an_unknown_category(self):
        result = handler.activate(
            event({"reference": "ref-1", "short_key": "KEY", "uuid": UUID, "category": "runner"}), None
        )
        self.assertEqual(result["statusCode"], 400)

    def test_generate_test_license_mints_an_unlimited_license_with_a_fresh_key(self):
        result = handler.generate_test_license({"uuid": UUID, "category": "server"}, None)

        file_bytes = base64.b64decode(result["license_file_base64"])
        fields = self._verify_file(file_bytes, result["short_key"])
        self.assertEqual(fields["bound_uuid"], UUID)
        self.assertIsNone(fields["valid_to"])
        self.assertIsNone(fields["max_device_count"])

    def test_generate_test_license_requires_uuid_and_category(self):
        with self.assertRaises(ValueError):
            handler.generate_test_license({"category": "server"}, None)

    def test_generate_test_license_midi_player_has_no_categories(self):
        result = handler.generate_test_license({"uuid": UUID, "category": "midi_player"}, None)
        fields = self._verify_file(base64.b64decode(result["license_file_base64"]), result["short_key"])
        self.assertEqual(fields["kind"], "midi_player")
        self.assertEqual(fields["categories"], {})


if __name__ == "__main__":
    unittest.main()
