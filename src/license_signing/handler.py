"""License-signing Lambda: mints and signs Virtual Church Musician license files.

Holds the production private key -- a local dev file for now
(LICENSE_SIGNING_PRIVATE_KEY_PATH), moved to AWS Secrets Manager before any
real customer-facing deployment (see the "Open items" note at the bottom of
Prompts/FastSpring_implementation.md section 4d). Two entry points share one
core mint-and-sign function:

  activate(event, context)             -- public, order/short-key-authenticated.
      POST {reference, short_key, uuid, category}. Looks up
      kng-license-issuance (one row per trial or order, written today only
      by trial_request/handler.py -- FastSpring order fulfillment writes the
      purchase case once that integration exists), verifies short_key
      against its stored hash, mints and signs a license bound to `uuid`,
      records the binding (idempotent on a repeat from the same uuid,
      refused from a different one), and returns the signed file. This is
      what both the Admin app (automatic, normal case) and
      www/activate.html (manual, air-gapped case) call.

  generate_test_license(event, context) -- IAM-only direct invoke, no public
      endpoint. {uuid, category, kind}. Skips the issuance-table lookup
      entirely (there's no real order behind a test box) and mints an
      unlimited license with a freshly-generated short_key, returning both.
      Called by the Virtual Church Musician repo's
      src/license_tools/generate_test_license.py.

See the Virtual Church Musician repo's Prompts/ToDo.md "License File" item
for the full design and the exact file format both sides agree on --
src/server/license_file.py there is this module's exact inverse.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import string
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

FORMAT_VERSION = 1
# Must exactly match src/server/license_file.py's own constants -- the two
# sides of one contract, kept in separate repos by design (no shared
# package across VCM/KnG, same as every other JSON contract between them).
_KDF_SALT = b"virtualchurchmusician-license-file-v1"
_KDF_ITERATIONS = 390_000
_CATEGORIES = ("admin", "template", "service", "runner")
_CATEGORY_FOR = {"server": _CATEGORIES, "midi_player": ()}

TRIAL_DAYS = 90

_private_key = None


def _private_key_obj():
    global _private_key
    if _private_key is None:
        secret_arn = os.environ.get("LICENSE_SIGNING_PRIVATE_KEY_SECRET_ARN")
        if secret_arn:
            # Deployed Lambda path -- the real production key lives only in
            # Secrets Manager, never on local disk or in Terraform state.
            import boto3  # bundled in the Lambda runtime; imported lazily so tests need no boto3

            pem_bytes = (
                boto3.client("secretsmanager")
                .get_secret_value(SecretId=secret_arn)["SecretString"]
                .encode("utf-8")
            )
        else:
            path = os.environ.get("LICENSE_SIGNING_PRIVATE_KEY_PATH", "secrets/license_signing_private_key.pem")
            with open(path, "rb") as handle:
                pem_bytes = handle.read()
        _private_key = serialization.load_pem_private_key(pem_bytes, password=None)
    return _private_key


def _canonical_fields_bytes(fields: dict) -> bytes:
    return json.dumps(fields, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _derive_fernet_key(short_key: str) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=_KDF_SALT, iterations=_KDF_ITERATIONS)
    return base64.urlsafe_b64encode(kdf.derive(short_key.strip().encode("utf-8")))


def generate_short_key() -> str:
    """A human-typable activation key, grouped for readability."""
    alphabet = string.ascii_uppercase + string.digits
    groups = ["".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(4)]
    return "-".join(groups)


def hash_short_key(short_key: str) -> str:
    return hashlib.sha256(short_key.strip().upper().encode("utf-8")).hexdigest()


def build_fields(
    kind: str,
    bound_uuid: str,
    valid_to: str | None,
    version_pattern: str = "*",
    max_device_count: int | None = None,
    max_registered_user_count: int | None = None,
    category_limits: dict | None = None,
) -> dict:
    """Builds the field set src/server/license_file.py verifies. `version_pattern`
    defaults to "*" (any version) -- real releases should pass the current
    major version's own pattern (e.g. "1.*") once the signing Lambda has a
    way to learn it from matrix.json; not wired up yet (see "Open items").
    """
    categories = {}
    if kind == "server":
        limits = category_limits or {}
        categories = {
            name: limits.get(name, {"max_registered": None, "max_concurrent": None}) for name in _CATEGORIES
        }
    return {
        "format_version": FORMAT_VERSION,
        "kind": kind,
        "bound_uuid": bound_uuid,
        "valid_from": datetime.now(timezone.utc).isoformat(),
        "valid_to": valid_to,
        "version_pattern": version_pattern,
        "max_device_count": max_device_count,
        "max_registered_user_count": max_registered_user_count,
        "categories": categories,
    }


def mint_and_sign(fields: dict, short_key: str) -> bytes:
    """Signs `fields` with the production private key and Fernet-encrypts the
    result with a key derived from `short_key` -- the exact inverse of
    src/server/license_file.load_and_verify in the Virtual Church Musician
    repo.
    """
    signature = _private_key_obj().sign(_canonical_fields_bytes(fields), padding.PKCS1v15(), hashes.SHA256())
    envelope = {"fields": fields, "signature": base64.b64encode(signature).decode("ascii")}
    return Fernet(_derive_fernet_key(short_key)).encrypt(json.dumps(envelope).encode("utf-8"))


_dynamodb_client = None


def _dynamodb():
    global _dynamodb_client
    if _dynamodb_client is None:
        import boto3  # bundled in the Lambda runtime; imported lazily so tests need no boto3

        _dynamodb_client = boto3.client("dynamodb")
    return _dynamodb_client


def _issuance_table() -> str:
    return os.environ["LICENSE_ISSUANCE_TABLE"]


def _json(status: int, payload: dict) -> dict:
    return {"statusCode": status, "headers": {"Content-Type": "application/json"}, "body": json.dumps(payload)}


def _error(status: int, message: str) -> dict:
    return _json(status, {"ok": False, "error": message})


def _bound_uuid_attr(category: str) -> str:
    return f"bound_uuid_{category}"


def activate(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
    except (TypeError, ValueError):
        return _error(400, "Request body must be JSON.")

    reference = str(body.get("reference", "")).strip()
    short_key = str(body.get("short_key", "")).strip()
    uuid = str(body.get("uuid", "")).strip()
    category = str(body.get("category", "")).strip()
    if not reference or not short_key or not uuid or category not in ("server", "midi_player"):
        return _error(400, "reference, short_key, uuid, and category ('server' or 'midi_player') are all required.")

    record = _dynamodb().get_item(TableName=_issuance_table(), Key={"reference": {"S": reference}}).get("Item")
    if record is None:
        return _error(404, "Unknown order or trial reference.")
    if record["short_key_hash"]["S"] != hash_short_key(short_key):
        return _error(403, "Incorrect activation key.")

    bound_attr = _bound_uuid_attr(category)
    existing_uuid = record.get(bound_attr, {}).get("S")
    if existing_uuid is not None and existing_uuid != uuid:
        return _error(409, f"This {category} license has already been activated on a different device.")

    kind = "midi_player" if category == "midi_player" else "server"
    valid_to = record.get("valid_to", {}).get("S")
    fields = build_fields(kind, uuid, valid_to)
    file_bytes = mint_and_sign(fields, short_key)

    if existing_uuid is None:
        _dynamodb().update_item(
            TableName=_issuance_table(),
            Key={"reference": {"S": reference}},
            UpdateExpression=f"SET {bound_attr} = :uuid",
            ExpressionAttributeValues={":uuid": {"S": uuid}},
        )

    return _json(200, {"ok": True, "license_file_base64": base64.b64encode(file_bytes).decode("ascii")})


def generate_test_license(event, context):
    """IAM-only entry point -- no issuance-table lookup, no public route.
    `event` is the raw payload passed to boto3's Lambda.invoke, not an API
    Gateway/Function URL event.
    """
    uuid = str(event.get("uuid", "")).strip()
    category = str(event.get("category", "")).strip()
    if not uuid or category not in ("server", "midi_player"):
        raise ValueError("uuid and category ('server' or 'midi_player') are both required.")
    kind = "midi_player" if category == "midi_player" else "server"
    short_key = generate_short_key()
    fields = build_fields(kind, uuid, valid_to=None)  # unlimited: forever, infinite counts
    file_bytes = mint_and_sign(fields, short_key)
    return {"license_file_base64": base64.b64encode(file_bytes).decode("ascii"), "short_key": short_key}
