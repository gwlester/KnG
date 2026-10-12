import base64
import hashlib
import hmac
import importlib.util
import io
import json
import os
import unittest
from pathlib import Path
from unittest import mock
from urllib import error as urllib_error


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parent.parent / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


handler = _load("order_fulfillment_handler_module", "src/order_fulfillment/handler.py")

WEBHOOK_SECRET = b"test-webhook-secret"


def _signed_event(payload: dict) -> dict:
    body = json.dumps(payload)
    signature = base64.b64encode(hmac.new(WEBHOOK_SECRET, body.encode("utf-8"), hashlib.sha256).digest()).decode(
        "ascii"
    )
    return {
        "queryStringParameters": {"webhook": "1"},
        "headers": {"X-FS-Signature": signature},
        "body": body,
    }


def _order_completed_payload(reference="order-123", email="buyer@example.org", products=None):
    products = products or ["virtual-church-musician-server"]
    return {
        "events": [
            {
                "type": "order.completed",
                "data": {
                    "reference": reference,
                    "customer": {"email": email},
                    "items": [{"product": p} for p in products],
                },
            }
        ]
    }


class OrderFulfillmentHandlerTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(
            os.environ,
            {
                "LICENSE_ISSUANCE_TABLE": "test-issuance",
                "DOWNLOADS_BUCKET": "test-bucket",
                "FASTSPRING_WEBHOOK_SECRET_ARN": "arn:fake:webhook-secret",
                "FASTSPRING_API_CREDENTIALS_SECRET_ARN": "arn:fake:api-credentials",
            },
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.dynamo = mock.Mock()
        self.dynamo.get_item.return_value = {}
        dynamo_patch = mock.patch.object(handler, "_dynamodb", return_value=self.dynamo)
        dynamo_patch.start()
        self.addCleanup(dynamo_patch.stop)
        secrets_patch = mock.patch.object(
            handler,
            "_secrets",
            return_value=mock.Mock(
                get_secret_value=lambda SecretId: {
                    "arn:fake:webhook-secret": {"SecretString": WEBHOOK_SECRET.decode("ascii")},
                    "arn:fake:api-credentials": {
                        "SecretString": json.dumps({"username": "u", "password": "p"})
                    },
                }[SecretId]
            ),
        )
        secrets_patch.start()
        self.addCleanup(secrets_patch.stop)

    def test_webhook_rejects_a_bad_signature(self):
        event = _signed_event(_order_completed_payload())
        event["headers"]["X-FS-Signature"] = "wrong"

        result = handler.handler(event, None)

        self.assertEqual(result["statusCode"], 401)
        self.dynamo.put_item.assert_not_called()

    def test_webhook_rejects_a_missing_signature(self):
        event = _signed_event(_order_completed_payload())
        del event["headers"]["X-FS-Signature"]

        result = handler.handler(event, None)

        self.assertEqual(result["statusCode"], 401)

    def test_webhook_writes_an_issuance_row_for_a_completed_order(self):
        event = _signed_event(_order_completed_payload(reference="order-123", email="buyer@example.org"))

        result = handler.handler(event, None)

        self.assertEqual(result["statusCode"], 200)
        self.dynamo.put_item.assert_called_once()
        kwargs = self.dynamo.put_item.call_args.kwargs
        self.assertEqual(kwargs["TableName"], "test-issuance")
        item = kwargs["Item"]
        self.assertEqual(item["reference"]["S"], "order-123")
        self.assertEqual(item["source"]["S"], "purchase")
        self.assertEqual(item["email"]["S"], "buyer@example.org")
        self.assertEqual(item["kinds"]["SS"], ["server"])
        self.assertIn("short_key", item)
        self.assertNotIn("valid_to", item)

    def test_webhook_maps_both_products_by_path(self):
        event = _signed_event(
            _order_completed_payload(products=["virtual-church-musician-server", "virtual-church-musician-midi-player"])
        )

        handler.handler(event, None)

        item = self.dynamo.put_item.call_args.kwargs["Item"]
        self.assertEqual(sorted(item["kinds"]["SS"]), ["midi-player", "server"])

    def test_webhook_ignores_events_that_are_not_order_completed(self):
        payload = {"events": [{"type": "order.refunded", "data": {"reference": "order-999"}}]}
        event = _signed_event(payload)

        result = handler.handler(event, None)

        self.assertEqual(result["statusCode"], 200)
        self.dynamo.put_item.assert_not_called()

    def test_webhook_does_not_overwrite_an_existing_row(self):
        self.dynamo.get_item.return_value = {"Item": {"reference": {"S": "order-123"}, "short_key": {"S": "EXISTING"}}}
        event = _signed_event(_order_completed_payload(reference="order-123"))

        handler.handler(event, None)

        self.dynamo.put_item.assert_not_called()

    def test_fulfill_requires_an_order_reference(self):
        result = handler.handler({"queryStringParameters": {"fulfill": "1"}}, None)
        self.assertEqual(result["statusCode"], 400)

    def test_fulfill_rejects_an_order_fastspring_does_not_recognize(self):
        http_error = urllib_error.HTTPError("https://api.fastspring.com/orders/order-123", 404, "Not Found", {}, io.BytesIO(b"{}"))
        with mock.patch.object(handler.urllib_request, "urlopen", side_effect=http_error):
            result = handler.handler({"queryStringParameters": {"fulfill": "1", "order": "order-123"}}, None)

        self.assertEqual(result["statusCode"], 404)

    def test_fulfill_rejects_an_incomplete_order(self):
        response = mock.Mock()
        response.read.return_value = json.dumps({"completed": False}).encode("utf-8")
        response.__enter__ = mock.Mock(return_value=response)
        response.__exit__ = mock.Mock(return_value=False)
        with mock.patch.object(handler.urllib_request, "urlopen", return_value=response):
            result = handler.handler({"queryStringParameters": {"fulfill": "1", "order": "order-123"}}, None)

        self.assertEqual(result["statusCode"], 409)

    def test_fulfill_returns_the_short_key_and_download_links_for_a_completed_order(self):
        order_body = {
            "completed": True,
            "reference": "order-123",
            "customer": {"email": "buyer@example.org"},
            "items": [{"product": "virtual-church-musician-server"}],
        }
        response = mock.Mock()
        response.read.return_value = json.dumps(order_body).encode("utf-8")
        response.__enter__ = mock.Mock(return_value=response)
        response.__exit__ = mock.Mock(return_value=False)
        matrix = {
            "releases": [
                {
                    "version": "v1.0.0",
                    "channel": "stable",
                    "files": [
                        {
                            "app": "server",
                            "platform": "linux",
                            "format": "deb",
                            "default": True,
                            "key": "releases/v1.0.0/server.deb",
                            "filename": "server.deb",
                        }
                    ],
                }
            ]
        }
        with mock.patch.object(handler.urllib_request, "urlopen", return_value=response), mock.patch.object(
            handler, "_load_matrix", return_value=matrix
        ), mock.patch.object(handler, "_presign", return_value="https://signed.example/server.deb"):
            result = handler.handler({"queryStringParameters": {"fulfill": "1", "order": "order-123"}}, None)

        self.assertEqual(result["statusCode"], 200)
        body = json.loads(result["body"])
        self.assertTrue(body["short_key"])
        self.assertEqual(body["downloads"], [{"app": "server", "platform": "linux", "format": "deb", "url": "https://signed.example/server.deb"}])

    def test_fulfill_reuses_the_short_key_from_an_existing_row(self):
        self.dynamo.get_item.return_value = {
            "Item": {"reference": {"S": "order-123"}, "short_key": {"S": "ALREADY-ISSUED"}}
        }
        order_body = {"completed": True, "reference": "order-123", "items": []}
        response = mock.Mock()
        response.read.return_value = json.dumps(order_body).encode("utf-8")
        response.__enter__ = mock.Mock(return_value=response)
        response.__exit__ = mock.Mock(return_value=False)
        with mock.patch.object(handler.urllib_request, "urlopen", return_value=response), mock.patch.object(
            handler, "_load_matrix", return_value={"releases": []}
        ):
            result = handler.handler({"queryStringParameters": {"fulfill": "1", "order": "order-123"}}, None)

        body = json.loads(result["body"])
        self.assertEqual(body["short_key"], "ALREADY-ISSUED")
        self.dynamo.put_item.assert_not_called()


if __name__ == "__main__":
    unittest.main()
