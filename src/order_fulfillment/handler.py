"""Order-fulfillment Lambda: the FastSpring `order.completed` webhook
receiver, plus the order-verification + download-link route the "thank
you" redirect page (`www/purchase-complete.html`) and a later
self-service re-download page call.

A verified purchase becomes a `source: "purchase"` row in the same
`kng-license-issuance` DynamoDB table `src/license_signing/handler.py`'s
`activate()` already reads from -- exactly like a trial's `source:
"trial"` row, so `/activate` needs no changes to serve purchases too.
See the Virtual Church Musician repo's `Prompts/ToDo.md` "License File"
item and this repo's `Prompts/FastSpring_implementation.md`.

Routes (one Function URL, query-param-dispatched like
src/download_handler/handler.py):
  POST ?webhook=1               -- the order.completed webhook. Verifies
                                    FastSpring's X-FS-Signature
                                    (HMAC-SHA256 over the raw body,
                                    base64), then upserts the issuance
                                    row for the order.
  GET  ?fulfill=1&order=<ref>   -- re-verifies the order server-side
                                    against FastSpring's Orders API
                                    (never trusts the query param alone,
                                    per FastSpring's own documented
                                    guidance), then returns the order's
                                    reference/short_key/kinds for the
                                    main download picker (picker.js) to
                                    fill itself in with -- the actual
                                    download happens through the same
                                    access-code-gated flow as any other
                                    beta download, not a separate link
                                    list here.

The webhook and the fulfillment call commonly race (both fire around
the same moment); _upsert_issuance_row is idempotent either way, and
the short_key is stored in the row itself (not withheld after first
creation) so whichever of the two the buyer's own page depends on can
always read it back.

NOTE: this maps a FastSpring order's line items to our own app IDs by
product *path* (_PRODUCT_TO_APP_ID below) rather than a custom
attribute surviving into the webhook payload -- simpler and more
reliable with only two products. The exact JSON shape of FastSpring's
order.completed payload and Orders API response (field names for
reference/customer/items) is modeled on their documented format but
not yet exercised against a real sandbox order -- verify and adjust
_app_ids_for_order/_order_reference/_order_email below against a real
payload before trusting this with real orders (Prompts/
FastSpring_implementation.md section 6).

generate_short_key/hash_short_key are intentionally duplicated from
src/license_signing/handler.py (same reason src/trial_request/handler.py
duplicates them): each Lambda here deploys as its own standalone zip
(see terraform/order_fulfillment.tf's archive_file), so a cross-directory
import would only work at test time, not at runtime.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import string
from datetime import datetime, timezone
from urllib import error as urllib_error
from urllib import request as urllib_request

# Product path (FastSpring) -> our own app id, the same namespace
# matrix.json/picker.js/download_handler.py already use.
_PRODUCT_TO_APP_ID = {
    "virtual-church-musician-server": "server",
    "virtual-church-musician-midi-player": "midi-player",
}


def generate_short_key() -> str:
    alphabet = string.ascii_uppercase + string.digits
    groups = ["".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(4)]
    return "-".join(groups)


def hash_short_key(short_key: str) -> str:
    return hashlib.sha256(short_key.strip().upper().encode("utf-8")).hexdigest()


_dynamodb_client = None


def _dynamodb():
    global _dynamodb_client
    if _dynamodb_client is None:
        import boto3  # bundled in the Lambda runtime; imported lazily so tests need no boto3

        _dynamodb_client = boto3.client("dynamodb")
    return _dynamodb_client


def _issuance_table() -> str:
    return os.environ["LICENSE_ISSUANCE_TABLE"]


_secrets_client = None


def _secrets():
    global _secrets_client
    if _secrets_client is None:
        import boto3

        _secrets_client = boto3.client("secretsmanager")
    return _secrets_client


def _fastspring_credentials() -> tuple[str, str]:
    value = json.loads(
        _secrets().get_secret_value(SecretId=os.environ["FASTSPRING_API_CREDENTIALS_SECRET_ARN"])["SecretString"]
    )
    return value["username"], value["password"]


def _webhook_secret() -> bytes:
    return _secrets().get_secret_value(SecretId=os.environ["FASTSPRING_WEBHOOK_SECRET_ARN"])[
        "SecretString"
    ].encode("utf-8")


def _json(status: int, payload: dict) -> dict:
    return {"statusCode": status, "headers": {"Content-Type": "application/json"}, "body": json.dumps(payload)}


def _error(status: int, message: str) -> dict:
    return _json(status, {"ok": False, "error": message})


def _verify_signature(raw_body: bytes, signature_header: str | None) -> bool:
    if not signature_header:
        return False
    try:
        secret = _webhook_secret()
    except Exception:
        return False
    expected = base64.b64encode(hmac.new(secret, raw_body, hashlib.sha256).digest()).decode("ascii")
    return hmac.compare_digest(expected, signature_header)


def _app_ids_for_order(order: dict) -> list[str]:
    app_ids: list[str] = []
    for item in order.get("items", []):
        app_id = _PRODUCT_TO_APP_ID.get(str(item.get("product") or ""))
        if app_id and app_id not in app_ids:
            app_ids.append(app_id)
    return app_ids


def _order_reference(order: dict) -> str:
    return str(order.get("reference") or order.get("id") or "")


def _order_email(order: dict) -> str:
    # Lowercased for the same reason trial_request.handler lowercases its
    # own email -- consistent matching/display regardless of how
    # FastSpring (or the buyer) capitalized it.
    return str((order.get("customer") or {}).get("email") or "").strip().lower()


def _upsert_issuance_row(reference: str, email: str, app_ids: list[str]) -> dict:
    """Idempotent: the webhook and an immediate fulfillment-page call
    commonly race (both fire around the same moment) -- whichever gets
    here first creates the row with a fresh short_key; the other just
    reads it back unchanged. The short_key is stored in the row itself
    (not withheld after first creation) so either caller can always
    report it to the buyer, regardless of which one actually created it.
    """
    existing = _dynamodb().get_item(TableName=_issuance_table(), Key={"reference": {"S": reference}}).get("Item")
    if existing is not None:
        return existing
    short_key = generate_short_key()
    item = {
        "reference": {"S": reference},
        "source": {"S": "purchase"},
        "email": {"S": email},
        "kinds": {"SS": app_ids or ["server"]},
        "short_key": {"S": short_key},
        "short_key_hash": {"S": hash_short_key(short_key)},
        "created_at": {"S": datetime.now(timezone.utc).isoformat()},
        # No "valid_to" attribute at all -- activate() treats a missing
        # one as None, i.e. "forever" (a purchase, not a trial).
    }
    try:
        _dynamodb().put_item(
            TableName=_issuance_table(), Item=item, ConditionExpression="attribute_not_exists(#r)",
            ExpressionAttributeNames={"#r": "reference"},
        )
    except Exception as exc:  # noqa: BLE001 -- duck-typed, see license_signing.handler's precedent
        code = getattr(exc, "response", {}).get("Error", {}).get("Code")
        if code != "ConditionalCheckFailedException":
            raise
        return _dynamodb().get_item(TableName=_issuance_table(), Key={"reference": {"S": reference}})["Item"]
    return item


def webhook(event, context):
    raw_body = event.get("body") or ""
    body_bytes = base64.b64decode(raw_body) if event.get("isBase64Encoded") else raw_body.encode("utf-8")
    headers = {str(k).lower(): v for k, v in (event.get("headers") or {}).items()}
    if not _verify_signature(body_bytes, headers.get("x-fs-signature")):
        return _error(401, "Invalid signature.")
    try:
        payload = json.loads(body_bytes.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return _error(400, "Invalid JSON body.")
    for evt in payload.get("events", []):
        if evt.get("type") != "order.completed":
            continue
        order = evt.get("data") or {}
        # Logged deliberately (not just on error): this is the only place
        # FastSpring's real order.completed shape ever gets captured --
        # 2026-10-12's first sandbox test showed the webhook and the
        # immediate fulfillment call disagreeing on the reference (see the
        # fix in fulfill() below), caught only by comparing DynamoDB rows
        # after the fact. Logging the fields we actually extract here
        # means the next discrepancy is diagnosable from CloudWatch
        # without another live test.
        print(json.dumps({
            "event": "webhook_order_completed",
            "order_id": order.get("id"),
            "order_reference": order.get("reference"),
            "derived_reference": _order_reference(order),
            "email": _order_email(order),
            "item_products": [i.get("product") for i in order.get("items", [])],
        }))
        reference = _order_reference(order)
        if not reference:
            continue
        _upsert_issuance_row(reference, _order_email(order), _app_ids_for_order(order))
    return _json(200, {"ok": True})


def fulfill(event, context):
    requested_id = str((event.get("queryStringParameters") or {}).get("order") or "").strip()
    if not requested_id:
        return _error(400, "order is required.")
    username, password = _fastspring_credentials()
    req = urllib_request.Request(f"https://api.fastspring.com/orders/{requested_id}", method="GET")
    req.add_header("Authorization", "Basic " + base64.b64encode(f"{username}:{password}".encode()).decode("ascii"))
    try:
        with urllib_request.urlopen(req, timeout=10) as response:
            order = json.loads(response.read().decode("utf-8"))
    except urllib_error.HTTPError:
        return _error(404, "Order not found.")
    except (OSError, urllib_error.URLError):
        return _error(502, "Could not verify the order with FastSpring.")
    if not order.get("completed"):
        return _error(409, "This order has not completed.")
    # Derive the canonical reference from the order body itself -- the
    # exact same way webhook() does -- rather than trusting whatever id
    # the popup-closed JS callback happened to query by. Those two can
    # differ (FastSpring's own order id vs. its human-readable order
    # reference); using _order_reference() here, not requested_id,
    # guarantees this call and the webhook agree on one DynamoDB row for
    # the same real-world order. Falls back to requested_id only if the
    # order body has neither field, so this never produces an empty key.
    reference = _order_reference(order) or requested_id
    print(json.dumps({
        "event": "fulfill_order_verified",
        "requested_id": requested_id,
        "order_id": order.get("id"),
        "order_reference": order.get("reference"),
        "derived_reference": reference,
        "email": _order_email(order),
        "item_products": [i.get("product") for i in order.get("items", [])],
    }))
    app_ids = _app_ids_for_order(order)
    row = _upsert_issuance_row(reference, _order_email(order), app_ids)
    return _json(
        200,
        {
            "ok": True,
            "reference": reference,
            "short_key": row.get("short_key", {}).get("S"),
            "kinds": app_ids or row.get("kinds", {}).get("SS", []),
        },
    )


def handler(event, context):
    query = event.get("queryStringParameters") or {}
    if query.get("webhook") == "1":
        return webhook(event, context)
    if query.get("fulfill") == "1":
        return fulfill(event, context)
    return _error(404, "Unknown route.")
