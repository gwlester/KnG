"""FindCache debug-log upload Lambda: stores a user-sent debug log in S3.

The app's Settings -> Troubleshooting -> "Send log to KnG" button POSTs the
log as plain text (text/plain, UTF-8). Nothing is sent unless the user taps
the button and confirms.

Contract (API version 2): the request must carry "X-API-Version: 2" and
"X-App-Version"; the body is the log text, at most MAX_LOG_BYTES, whose last
non-empty line is the app's own "Uploading debug log: FindCache <version>,
Android <os> (API <n>), <device>" entry, with <version> equal to
X-App-Version. A log that does not end that way is rejected (400) and nothing
is stored. This keeps stray or hand-made posts out; it is not a security
control against someone who copies the format. Version 1 (no such line) is no
longer accepted. On success the response is
200 {"FormatVersion": 1, "id": "<reference>"}, where the reference is what
the user quotes when asking for the log to be looked at. Logs are written
to the private logs bucket and expire after 180 days (bucket lifecycle
rule, terraform/findcache_logs.tf).

The X-App-Version header (the FindCache version, e.g. 2026.11.04.001) is
stored as S3 object metadata after sanitising.
"""

import base64
import json
import os
import re
import secrets
from datetime import datetime, timezone

API_VERSION = "2"
FORMAT_VERSION = 1
MAX_LOG_BYTES = 1_000_000
_VERSION_RE = re.compile(r"[^0-9A-Za-z._-]")
_LAST_LINE_RE = re.compile(
    r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3} \[app\] Uploading debug log: "
    r"FindCache (?P<version>[0-9A-Za-z._-]{1,32}), Android [^,]{1,40} \(API \d{1,3}\), [^\r\n]{1,80}$"
)

_s3_client = None


def _s3():
    global _s3_client
    if _s3_client is None:
        import boto3  # bundled in the Lambda runtime; imported lazily so tests need no boto3

        _s3_client = boto3.client("s3")
    return _s3_client


def _response(status: int, payload: dict) -> dict:
    return {"statusCode": status, "headers": {"Content-Type": "application/json"}, "body": json.dumps(payload)}


def _error(status: int, message: str) -> dict:
    return _response(status, {"FormatVersion": FORMAT_VERSION, "error": message})


def _body_bytes(event: dict) -> bytes:
    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        return base64.b64decode(body)
    return body.encode("utf-8")


def handler(event, context):
    if event.get("requestContext", {}).get("http", {}).get("method") != "POST":
        return _error(405, "Use POST.")
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    if headers.get("x-api-version") == "1":
        return _error(400, "Please update FindCache to send logs.")
    if headers.get("x-api-version") != API_VERSION:
        return _error(400, "Unsupported or missing X-API-Version.")
    data = _body_bytes(event)
    if not data.strip():
        return _error(400, "The log is empty.")
    if len(data) > MAX_LOG_BYTES:
        return _error(413, "The log is too large.")

    try:
        lines = [line for line in data.decode("utf-8").splitlines() if line.strip()]
    except UnicodeDecodeError:
        return _error(400, "The log is not valid text.")
    match = _LAST_LINE_RE.match(lines[-1].rstrip()) if lines else None
    if match is None or match.group("version") != _VERSION_RE.sub("", headers.get("x-app-version", "")):
        return _error(400, "The log must end with its upload entry.")

    now = datetime.now(timezone.utc)
    log_id = f"{now:%Y%m%d-%H%M%S}-{secrets.token_hex(4)}"
    version = _VERSION_RE.sub("", headers.get("x-app-version", ""))[:32]
    extra = {"Metadata": {"app-version": version}} if version else {}
    _s3().put_object(
        Bucket=os.environ["LOG_BUCKET"],
        Key=f"findcache/{now:%Y/%m/%d}/{log_id}.txt",
        Body=data,
        ContentType="text/plain; charset=utf-8",
        **extra,
    )
    return _response(200, {"FormatVersion": FORMAT_VERSION, "id": log_id})
