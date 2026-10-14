"""Download Lambda: resolves a request against the private matrix and redirects.

GET  ?app=&platform=&version=&format=&arch=&v=1                   -> 302 to a 5-minute signed URL
POST ?app=&platform=&version=&format=&arch=&v=1 {reference,
                                                   short_key}       -> 200 {"ok": true, "url": ...}
                                                                       for a PASSWORD_REQUIRED_APPS
                                                                       app, checked against
                                                                       kng-license-issuance
GET  ?doc=&format=&version=&v=1                                   -> 302 to a signed URL for a guide
GET  ?status=1&v=1                                                -> JSON of availability (no file keys)

The matrix (matrix.json in the private downloads bucket) is written by the
publish-downloads workflow and never leaves the server: callers only ever get
a redirect, a presigned-URL JSON body, or the status summary. Only keys found
in the matrix are signed.

PASSWORD_REQUIRED_APPS (server, midi-player) are the two paid apps: every
download, on every channel, requires a POST body of {reference, short_key}
-- a purchase (src/order_fulfillment) or an approved beta tester's Test
Drive (src/trial_request) credential, pasted (or pre-filled by
www/picker.js) into the picker's "Access code" field, checked against the
kng-license-issuance DynamoDB table (decided 2026-10-12; the earlier raw
file-hash "password" mechanism is retired). A Test Drive credential only
works on a non-stable release; once an app's release is "stable"
(production), only a purchase-sourced credential works there -- see
_order_gated_download.
"""

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone

FORMAT_VERSION = 1
PRESIGN_SECONDS = int(os.environ.get("PRESIGN_SECONDS", "300"))
MATRIX_KEY = os.environ.get("MATRIX_KEY", "matrix.json")
CACHE_SECONDS = 60
# The two paid apps -- every download requires an order-gated access code
# on every channel (see module docstring).
_password_required_env = os.environ.get("PASSWORD_REQUIRED_APPS", "server,midi-player")
PASSWORD_REQUIRED_APPS = {a for a in _password_required_env.split(",") if a}
RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "2"))

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
FORMAT_RE = re.compile(r"^[a-z0-9]{1,10}$")
VERSION_RE = re.compile(r"^(current|previous|v[0-9A-Za-z.\-]{1,40})$")

INLINE_TYPES = {"html": "text/html", "txt": "text/plain", "md": "text/plain"}
ATTACHMENT_TYPES = {"pdf": "application/pdf"}

_s3_client = None
_cache = {"at": 0.0, "matrix": None}


def _s3():
    global _s3_client
    if _s3_client is None:
        import boto3  # bundled in the Lambda runtime; imported lazily so tests need no boto3
        from botocore.config import Config

        # Signature Version 4: the default for presigned URLs here was the legacy SigV2.
        _s3_client = boto3.client("s3", config=Config(signature_version="s3v4"))
    return _s3_client


def _bucket() -> str:
    return os.environ["DOWNLOADS_BUCKET"]


_dynamodb_client = None


def _dynamodb():
    global _dynamodb_client
    if _dynamodb_client is None:
        import boto3  # bundled in the Lambda runtime; imported lazily so tests need no boto3

        _dynamodb_client = boto3.client("dynamodb")
    return _dynamodb_client


def _issuance_table() -> str:
    return os.environ["LICENSE_ISSUANCE_TABLE"]


def _rate_limit_table() -> str:
    return os.environ["RATE_LIMIT_TABLE"]


def _client_ip(event: dict) -> str:
    return event.get("requestContext", {}).get("http", {}).get("sourceIp", "unknown")


def _rate_limited(ip: str) -> bool:
    """True if `ip` already made RATE_LIMIT_PER_MINUTE order-gated download
    attempts in the current 60-second window. One atomic conditional
    update, checked before any DynamoDB lookup of the access code itself.

    Duck-types the error instead of importing botocore.exceptions.ClientError:
    boto3's real client raises exactly this shape (a `.response` dict with
    `Error.Code`), and this way the module has no hard botocore dependency for
    tests to work around."""
    window = int(time.time() // 60)
    try:
        _dynamodb().update_item(
            TableName=_rate_limit_table(),
            Key={"pk": {"S": f"{ip}#{window}"}},
            UpdateExpression="SET #ttl = :ttl ADD #attempts :one",
            ConditionExpression="attribute_not_exists(#attempts) OR #attempts < :limit",
            ExpressionAttributeNames={"#ttl": "ttl", "#attempts": "attempts"},
            ExpressionAttributeValues={
                ":one": {"N": "1"},
                ":limit": {"N": str(RATE_LIMIT_PER_MINUTE)},
                ":ttl": {"N": str(window * 60 + 120)},
            },
        )
        return False
    except Exception as exc:  # noqa: BLE001 -- see docstring
        code = getattr(exc, "response", {}).get("Error", {}).get("Code")
        if code == "ConditionalCheckFailedException":
            return True
        raise


def _hash_short_key(short_key: str) -> str:
    # Duplicated from src/license_signing/handler.py rather than imported:
    # each Lambda here deploys as its own standalone zip, so a
    # cross-directory import would only work at test time.
    return hashlib.sha256(short_key.strip().upper().encode("utf-8")).hexdigest()


def _load_matrix() -> dict:
    now = time.time()
    if _cache["matrix"] is not None and now - _cache["at"] < CACHE_SECONDS:
        return _cache["matrix"]
    try:
        body = _s3().get_object(Bucket=_bucket(), Key=MATRIX_KEY)["Body"].read()
        matrix = json.loads(body)
    except Exception:
        matrix = {"FormatVersion": FORMAT_VERSION, "releases": []}
    _cache["at"], _cache["matrix"] = now, matrix
    return matrix


def _json(status: int, payload: dict, cache: str = "no-store") -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Cache-Control": cache},
        "body": json.dumps(payload),
    }


def _error(status: int, message: str) -> dict:
    return _json(status, {"ok": False, "error": message})


def _redirect(url: str) -> dict:
    return {"statusCode": 302, "headers": {"Location": url, "Cache-Control": "no-store"}, "body": ""}


def visible_releases(matrix: dict) -> list:
    """Stable releases once any exist; until then every release (labelled
    Beta). A "deprecated" release (no longer offered for download -- see
    publish_release.py's deprecate_matrix) is excluded either way, before
    the stable/beta fallback is even considered."""
    releases = [r for r in matrix.get("releases", []) if r.get("channel") != "deprecated"]
    stable = [r for r in releases if r.get("channel") == "stable"]
    return stable or releases


def resolve_release(matrix: dict, version: str):
    visible = visible_releases(matrix)
    if version == "current":
        return visible[0] if visible else None
    if version == "previous":
        return visible[1] if len(visible) > 1 else None
    # An exact version tag is searched for across every release, not just
    # the stable-filtered "visible" ones -- an approved beta tester must
    # still be able to reach a specific beta release by its own tag even
    # once some other release has gone stable and taken over
    # "current"/"previous" (decided 2026-10-12). picker.js doesn't yet
    # have a UI path that requests an explicit non-current/previous
    # version -- this makes the backend capable of it; wiring an actual
    # "beta" selector into the picker is a follow-up, not done here.
    # A deprecated release is deliberately not reachable even here
    # (decided 2026-10-14): unlike the stable-filter above, this isn't a
    # UI-convenience exemption, it's "this build doesn't work with the
    # licensing system" -- the same exclusion applies to every path.
    for release in matrix.get("releases", []):
        if release.get("channel") == "deprecated":
            continue
        if release.get("version") == version:
            return release
    return None


def _presign(key: str, filename: str, fmt: str) -> str:
    if not key.startswith("releases/"):
        raise ValueError("unexpected key")
    params = {"Bucket": _bucket(), "Key": key}
    if fmt in INLINE_TYPES:
        params["ResponseContentType"] = INLINE_TYPES[fmt]
        params["ResponseContentDisposition"] = f'inline; filename="{filename}"'
    else:
        if fmt in ATTACHMENT_TYPES:
            params["ResponseContentType"] = ATTACHMENT_TYPES[fmt]
        params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
    return _s3().generate_presigned_url("get_object", Params=params, ExpiresIn=PRESIGN_SECONDS)


def _log(**fields) -> None:
    print(json.dumps({"event": "download", **fields}))


def _status(matrix: dict) -> dict:
    def summarize(release):
        if release is None:
            return None
        files = {}
        for f in release.get("files", []):
            # A paid app's file is always reported available, on every
            # channel: it's always order-gated now (purchase or, on a
            # non-stable channel, an approved beta tester's Test Drive
            # credential), never hidden outright the way "sold elsewhere,
            # not here" used to hide a stable release's file.
            files.setdefault(f'{f["app"]}:{f["platform"]}', set()).add(f["format"])
        for link_key, link in matrix.get("links", {}).items():
            files.setdefault(link_key, set()).add(link["type"])
        docs = {}
        for d in release.get("documents", []):
            docs.setdefault(d["kind"], set()).add(d["format"])
        return {
            "version": release["version"],
            "channel": release.get("channel", "beta"),
            "published": release.get("published", ""),
            "signed": release.get("signed"),
            "available": {k: sorted(v) for k, v in files.items()},
            "documents": {k: sorted(v) for k, v in docs.items()},
        }

    return _json(
        200,
        {
            "FormatVersion": FORMAT_VERSION,
            "current": summarize(resolve_release(matrix, "current")),
            "previous": summarize(resolve_release(matrix, "previous")),
        },
        cache=f"public, max-age={CACHE_SECONDS}",
    )


def _order_gated_download(chosen: dict, body: dict, channel: str, ip: str) -> dict:
    """chosen's access is governed by a kng-license-issuance row -- the
    reference+short_key pair a purchase or an approved beta tester's
    Test Drive response gave them, pasted (or pre-filled by picker.js)
    into the picker's Access code field. This is the only gated-download
    path for server/midi-player now (decided 2026-10-12) -- the old raw
    file-hash "password" mechanism is retired, but the same per-IP rate
    limit that guarded it still applies here, checked before the
    DynamoDB lookup so a guessing attempt never costs that read.

    channel is the specific release being requested, not "whether any
    stable release exists at all" -- an approved beta tester's Test
    Drive credential keeps working against a beta release even after
    some other release has gone stable, as long as that beta release's
    own files are still resolvable (see resolve_release). Only a
    purchase-sourced row works once the release being requested is
    itself stable, matching "production must be purchased on the
    download page." A Test Drive credential also stops working outright
    once it's past its own valid_to -- same 90-day window as the
    license file itself, not just a one-time cutoff on requesting it.
    """
    reference = str(body.get("reference") or "").strip() if isinstance(body, dict) else ""
    short_key = str(body.get("short_key") or "").strip() if isinstance(body, dict) else ""
    if not reference or not short_key:
        return _error(401, "A valid access code is required for this download.")

    if _rate_limited(ip):
        return _error(429, "Too many attempts from this address. Try again in a minute.")

    item = _dynamodb().get_item(
        TableName=_issuance_table(), Key={"reference": {"S": reference}}
    ).get("Item")
    if item is None or item.get("short_key_hash", {}).get("S") != _hash_short_key(short_key):
        _log(app=chosen["app"], platform=chosen["platform"], order_check="failed")
        return _error(403, "That access code doesn't match an order.")

    kinds = item.get("kinds", {}).get("SS", [])
    if chosen["app"] not in kinds:
        return _error(403, "That access code doesn't cover this product.")

    valid_to = item.get("valid_to", {}).get("S")
    if valid_to and datetime.fromisoformat(valid_to) <= datetime.now(timezone.utc):
        return _error(403, "This Test Drive access code has expired.")

    if channel == "stable" and item.get("source", {}).get("S") != "purchase":
        return _error(403, "This release requires a purchase -- Test Drive access doesn't cover it.")

    try:
        url = _presign(chosen["key"], chosen["filename"], chosen["format"])
    except ValueError:
        return _error(404, "That download is not available yet.")
    _log(app=chosen["app"], platform=chosen["platform"], format=chosen["format"],
         order_check=True)
    return _json(200, {"ok": True, "url": url, "filename": chosen["filename"]})


def _download(matrix: dict, qs: dict, body: dict, ip: str) -> dict:
    app, platform = qs.get("app", ""), qs.get("platform", "")
    fmt, arch = qs.get("format", ""), qs.get("arch", "")
    version = qs.get("version", "current")
    if not NAME_RE.match(app) or not NAME_RE.match(platform):
        return _error(400, "Unknown app or platform.")
    if fmt and not FORMAT_RE.match(fmt) or arch and not FORMAT_RE.match(arch):
        return _error(400, "Invalid format or architecture.")
    if not VERSION_RE.match(version):
        return _error(400, "Invalid version.")

    link = matrix.get("links", {}).get(f"{app}:{platform}")
    if link and link.get("url", "").startswith("https://") and not fmt:
        _log(app=app, platform=platform, version="link", type=link.get("type"))
        return _redirect(link["url"])

    release = resolve_release(matrix, version)
    if release is None:
        return _error(404, "That version is not available.")

    order_gated = app in PASSWORD_REQUIRED_APPS

    candidates = [f for f in release.get("files", []) if f["app"] == app and f["platform"] == platform]
    if arch:
        candidates = [f for f in candidates if f.get("arch") == arch]
    if fmt:
        candidates = [f for f in candidates if f["format"] == fmt]
    if not candidates:
        return _error(404, "That download is not available yet.")
    chosen = next((f for f in candidates if f.get("default")), candidates[0])

    if order_gated:
        return _order_gated_download(chosen, body if isinstance(body, dict) else {}, release.get("channel"), ip)

    try:
        url = _presign(chosen["key"], chosen["filename"], chosen["format"])
    except ValueError:
        return _error(404, "That download is not available yet.")
    _log(app=app, platform=platform, version=release["version"], format=chosen["format"])
    return _redirect(url)


def _document(matrix: dict, qs: dict) -> dict:
    kind, fmt = qs.get("doc", ""), qs.get("format", "")
    version = qs.get("version", "current")
    if not NAME_RE.match(kind) or (fmt and not FORMAT_RE.match(fmt)):
        return _error(400, "Unknown document.")
    if not VERSION_RE.match(version):
        return _error(400, "Invalid version.")
    release = resolve_release(matrix, version)
    if release is None:
        return _error(404, "That version is not available.")
    candidates = [d for d in release.get("documents", []) if d["kind"] == kind]
    if fmt:
        candidates = [d for d in candidates if d["format"] == fmt]
    if not candidates:
        return _error(404, "That document is not available yet.")
    chosen = candidates[0]
    try:
        url = _presign(chosen["key"], chosen["filename"], chosen["format"])
    except ValueError:
        return _error(404, "That document is not available yet.")
    _log(doc=kind, version=release["version"], format=chosen["format"])
    return _redirect(url)


def _parse_json_body(event: dict) -> dict:
    """POST body for the password-gated flow only; empty/unparsable is fine
    everywhere else since only _password_gated_download ever looks at it."""
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        import base64

        raw = base64.b64decode(raw).decode("utf-8", "replace")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def handler(event, context):
    method = event.get("requestContext", {}).get("http", {}).get("method", "")
    # POST exists only to carry a password to _download without it landing in
    # a query string (browser history, request logs); every other verb/path
    # ignores the body entirely.
    if method not in ("GET", "HEAD", "POST"):
        return _error(405, "Method not allowed.")
    qs = event.get("queryStringParameters") or {}
    if qs.get("v", "1") != "1":
        return _error(400, "Unsupported API version.")
    matrix = _load_matrix()
    if qs.get("status"):
        return _status(matrix)
    if qs.get("doc"):
        return _document(matrix, qs)
    if qs.get("app"):
        body = _parse_json_body(event) if method == "POST" else {}
        return _download(matrix, qs, body, _client_ip(event))
    return _error(400, "Nothing requested.")
