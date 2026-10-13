"""Beta-access-request Lambda: issues a 90-day beta reference + activation
key for an approved beta tester.

POST {email, kind} where kind is "server" or "midi_player" -> 200
{reference, short_key, valid_to}.

Decided 2026-10-12: this is no longer an open "anyone can request a
trial" page. The requesting email must be on the kng-beta-testers
allowlist (maintained by hand via tools/sales_browser) or the request is
rejected with a pointer to the contact form. One approval per email
covers both products; which product this particular request is for is
still tracked per kind, same as before.

An approved tester can come back and request again: while their
existing credential is still within its 90-day window, the same
reference/short_key is returned unchanged (so it can be reused/re-shown
by the picker without inventing a new one); once it has expired, the
same reference is renewed in place with a fresh key and a fresh 90-day
window, rather than erroring out the way a one-shot trial would. Any
prior device binding on that reference (license_signing.handler's
bound_uuid_<category>) is cleared on renewal, so a tester who moved to a
new test device isn't stuck bound to their previous one.

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
_NOT_APPROVED_MESSAGE = "This email is not on our approved beta tester list. Use the contact form to request access."


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


def _beta_testers_table() -> str:
    return os.environ["BETA_TESTERS_TABLE"]


def _json(status: int, payload: dict) -> dict:
    return {"statusCode": status, "headers": {"Content-Type": "application/json"}, "body": json.dumps(payload)}


def _error(status: int, message: str) -> dict:
    return _json(status, {"ok": False, "error": message})


def _is_approved_beta_tester(email: str) -> bool:
    item = _dynamodb().get_item(TableName=_beta_testers_table(), Key={"email": {"S": email}}).get("Item")
    return item is not None


def _renew_issuance_row(reference: str, now: datetime) -> tuple[str, str]:
    """Refreshes an existing (expired) beta-access row in place -- same
    reference, fresh short_key and 90-day window -- and clears any prior
    device binding so a tester on a new device isn't stuck bound to the
    one they used last cycle. Returns (short_key, valid_to)."""
    short_key = generate_short_key()
    valid_to = (now + timedelta(days=TRIAL_DAYS)).isoformat()
    _dynamodb().update_item(
        TableName=_issuance_table(),
        Key={"reference": {"S": reference}},
        UpdateExpression=(
            "SET short_key = :sk, short_key_hash = :skh, valid_to = :vt, created_at = :ca "
            "REMOVE bound_uuid_server, bound_uuid_midi_player"
        ),
        ExpressionAttributeValues={
            ":sk": {"S": short_key},
            ":skh": {"S": hash_short_key(short_key)},
            ":vt": {"S": valid_to},
            ":ca": {"S": now.isoformat()},
        },
    )
    return short_key, valid_to


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

    if not _is_approved_beta_tester(email):
        return _error(403, _NOT_APPROVED_MESSAGE)

    email_kind_key = f"{email}#{kind}"
    existing = _dynamodb().get_item(
        TableName=_trial_by_email_table(), Key={"email_kind": {"S": email_kind_key}}
    ).get("Item")

    now = datetime.now(timezone.utc)

    if existing is not None:
        reference = existing["reference"]["S"]
        issuance = _dynamodb().get_item(TableName=_issuance_table(), Key={"reference": {"S": reference}}).get("Item")
        valid_to = issuance.get("valid_to", {}).get("S") if issuance else None
        if issuance is not None and valid_to and datetime.fromisoformat(valid_to) > now:
            # Still within the window: hand back the same credential so an
            # approved tester can keep coming back, instead of the 409 a
            # one-shot trial would have returned here.
            return _json(
                200,
                {"ok": True, "reference": reference, "short_key": issuance["short_key"]["S"], "valid_to": valid_to},
            )
        short_key, new_valid_to = _renew_issuance_row(reference, now)
        return _json(200, {"ok": True, "reference": reference, "short_key": short_key, "valid_to": new_valid_to})

    reference = f"trial-{secrets.token_hex(8)}"
    short_key = generate_short_key()
    valid_to = (now + timedelta(days=TRIAL_DAYS)).isoformat()

    _dynamodb().put_item(
        TableName=_issuance_table(),
        Item={
            "reference": {"S": reference},
            "source": {"S": "trial"},
            "email": {"S": email},
            "kinds": {"SS": ["midi-player" if kind == "midi_player" else kind]},
            "short_key": {"S": short_key},
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
