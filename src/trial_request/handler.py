"""Trial-request Lambda: issues a 90-day trial reference + activation key.

POST {email, kind} where kind is "server" or "midi_player" -> 200
{reference, short_key, valid_to}. One trial per email per kind (Prompts/
ToDo.md "License File" Round 2's answer to repeated-trial abuse), checked
against a small lookup table before writing the real issuance record that
src/license_signing/handler.py's activate() later looks up.

Deliberately does not hand back an installer download link -- that stays
the existing download_handler/matrix.json/picker.js flow (Prompts/ToDo.md's
"Selling the Server and MIDI Player" item), unrelated to issuing the
license credential this module is responsible for.

generate_short_key/hash_short_key/TRIAL_DAYS are intentionally duplicated
from src/license_signing/handler.py rather than imported: each Lambda here
deploys as its own standalone zip of just its own directory (see
terraform/downloads.tf's archive_file for the existing pattern), so a
cross-directory import would only work at test time, not at runtime. Same
reasoning as VCM/KnG having no shared package for the license file format
itself -- keep both copies in sync by hand if either ever changes.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import string
from datetime import datetime, timedelta, timezone

TRIAL_DAYS = 90
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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


def _trial_by_email_table() -> str:
    return os.environ["TRIAL_BY_EMAIL_TABLE"]


def _json(status: int, payload: dict) -> dict:
    return {"statusCode": status, "headers": {"Content-Type": "application/json"}, "body": json.dumps(payload)}


def _error(status: int, message: str) -> dict:
    return _json(status, {"ok": False, "error": message})


def handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
    except (TypeError, ValueError):
        return _error(400, "Request body must be JSON.")

    email = str(body.get("email", "")).strip().lower()
    kind = str(body.get("kind", "")).strip()
    if not _EMAIL_RE.match(email):
        return _error(400, "A valid email address is required.")
    if kind not in ("server", "midi_player"):
        return _error(400, "kind must be 'server' or 'midi_player'.")

    email_kind_key = f"{email}#{kind}"
    existing = _dynamodb().get_item(
        TableName=_trial_by_email_table(), Key={"email_kind": {"S": email_kind_key}}
    ).get("Item")
    if existing is not None:
        return _error(409, "A trial for this email and product has already been issued.")

    reference = f"trial-{secrets.token_hex(8)}"
    short_key = generate_short_key()
    now = datetime.now(timezone.utc)
    valid_to = (now + timedelta(days=TRIAL_DAYS)).isoformat()

    _dynamodb().put_item(
        TableName=_issuance_table(),
        Item={
            "reference": {"S": reference},
            "source": {"S": "trial"},
            "email": {"S": email},
            "kinds": {"SS": ["midi-player" if kind == "midi_player" else kind]},
            "short_key_hash": {"S": hash_short_key(short_key)},
            "valid_to": {"S": valid_to},
            "created_at": {"S": now.isoformat()},
        },
    )
    _dynamodb().put_item(
        TableName=_trial_by_email_table(),
        Item={"email_kind": {"S": email_kind_key}, "reference": {"S": reference}, "created_at": {"S": now.isoformat()}},
    )

    return _json(200, {"ok": True, "reference": reference, "short_key": short_key, "valid_to": valid_to})
